import json
import os
import glob
import time
import shutil
import threading
import logging
from datetime import datetime
from django.db import transaction
from typing import List, Dict, Any, Optional, Tuple
from .question_processing import generate_question_hash, check_question_similarity

logger = logging.getLogger(__name__)

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

# Per-filepath locks so parallel workers never collide on the same JSON file
_file_locks: Dict[str, threading.Lock] = {}
_file_locks_mutex = threading.Lock()


def _get_file_lock(filepath: str) -> threading.Lock:
    with _file_locks_mutex:
        if filepath not in _file_locks:
            _file_locks[filepath] = threading.Lock()
        return _file_locks[filepath]


# ── File I/O ───────────────────────────────────────────────────────────────────

def write_json_safely(filepath: str, data: list, question_type: str = "question"):
    """Cross-platform JSON append — thread-safe via per-file lock."""
    lock = _get_file_lock(filepath)
    with lock:
        try:
            if HAS_FCNTL:
                with open(filepath, 'r+', encoding='utf-8') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    try:
                        f.seek(0)
                        existing_data = json.load(f)
                    except (json.JSONDecodeError, ValueError):
                        existing_data = []
                    existing_data.extend(data if isinstance(data, list) else [data])
                    f.seek(0)
                    f.truncate()
                    json.dump(existing_data, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                    return len(existing_data)
            else:
                # Windows path: write to unique temp file, then replace
                for attempt in range(5):
                    try:
                        existing_data = []
                        if os.path.exists(filepath):
                            with open(filepath, 'r', encoding='utf-8') as f:
                                try:
                                    existing_data = json.load(f)
                                except (json.JSONDecodeError, ValueError):
                                    pass
                        existing_data.extend(data if isinstance(data, list) else [data])
                        # Use a unique temp name per attempt to avoid stale .tmp collisions
                        temp_path = f"{filepath}.{os.getpid()}_{attempt}.tmp"
                        with open(temp_path, 'w', encoding='utf-8') as f:
                            json.dump(existing_data, f, indent=2, ensure_ascii=False)
                            f.flush()
                            os.fsync(f.fileno())
                        # shutil.move handles Windows cross-device and open-file cases better
                        shutil.move(temp_path, filepath)
                        return len(existing_data)
                    except (IOError, OSError) as e:
                        # Clean up stale temp if it exists
                        try:
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                        except OSError:
                            pass
                        if attempt == 4:
                            raise
                        time.sleep(0.05 * (attempt + 1))
        except Exception as e:
            logger.error(f"write_json_safely failed: {e}")
            raise


def _get_or_create_output_file(game_type: str) -> str:
    """Return path to the most recent output file for game_type (within 1 hour), or a new one."""
    output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'question_outputs')
    os.makedirs(output_dir, exist_ok=True)
    existing = glob.glob(os.path.join(output_dir, f"{game_type}_*.json"))
    cutoff = time.time() - 3600

    def safe_ctime(f):
        try:
            return os.path.getctime(f)
        except OSError:
            return 0

    recent = next(
        (f for f in sorted(existing, key=safe_ctime, reverse=True)
         if safe_ctime(f) > cutoff and os.path.exists(f)),
        None
    )
    if recent:
        return recent
    filename = f"{game_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return os.path.join(output_dir, filename)


def export_question_to_json(question_obj, game_type: str):
    """Append a saved question to question_outputs/*.json."""
    try:
        filepath = _get_or_create_output_file(game_type)
        game_data = question_obj.game_data or {}

        if game_type == 'coding':
            minimal_game_data = {
                'normal': {
                    'question_text':  question_obj.question_text,
                    'function_name':  game_data.get('function_name', ''),
                    'sample_input':   game_data.get('sample_input', ''),
                    'sample_output':  game_data.get('sample_output', ''),
                    'hidden_tests':   game_data.get('hidden_tests', []),
                    'clean_solution': game_data.get('clean_solution') or game_data.get('correct_code', ''),
                    'explanation':    game_data.get('explanation', ''),
                },
                'buggy': {
                    'buggy_question_text':   game_data.get('buggy_question_text', ''),
                    'code_shown_to_student': game_data.get('code_shown_to_student') or game_data.get('buggy_code', ''),
                    'code_with_bug_fixed':   game_data.get('code_with_bug_fixed') or game_data.get('buggy_correct_code', ''),
                    'buggy_explanation':     game_data.get('buggy_explanation') or game_data.get('buggy_code_explanation', ''),
                },
                'generation_timestamp': game_data.get('generation_timestamp', datetime.now().isoformat()),
            }
            question_data = {
                'game_type':  question_obj.game_type,
                'difficulty': question_obj.estimated_difficulty,
                'subtopic':   question_obj.subtopic.name if question_obj.subtopic else None,
                'game_data':  minimal_game_data,
                'created_at': question_obj.created_at.isoformat() if getattr(question_obj, 'created_at', None) else datetime.now().isoformat(),
                'exported_at': datetime.now().isoformat(),
            }
        else:
            question_data = {
                'question_text':  question_obj.question_text,
                'correct_answer': question_obj.correct_answer,
                'game_type':      question_obj.game_type,
                'difficulty':     question_obj.estimated_difficulty,
                'subtopic':       question_obj.subtopic.name if question_obj.subtopic else None,
                'game_data': {
                    'explanation':          game_data.get('explanation', ''),
                    'generation_timestamp': game_data.get('generation_timestamp', datetime.now().isoformat()),
                },
                'created_at':  question_obj.created_at.isoformat() if getattr(question_obj, 'created_at', None) else datetime.now().isoformat(),
                'exported_at': datetime.now().isoformat(),
            }

        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=2)

        total = write_json_safely(filepath, question_data, game_type)
        logger.debug(f"{game_type.upper()} question exported (#{total}): {question_obj.question_text[:50]}...")

    except Exception as e:
        logger.error(f"Failed to export {game_type} question to JSON: {e}", exc_info=True)


def export_preassessment_question_to_json(question_obj):
    """Append a pre-assessment question to question_outputs/pre_assessment_*.json."""
    try:
        output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'question_outputs')
        os.makedirs(output_dir, exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        existing = glob.glob(os.path.join(output_dir, f"pre_assessment_{date_str}_*.json"))
        if existing:
            filepath = max(existing, key=os.path.getctime)
        else:
            filepath = os.path.join(output_dir, f"pre_assessment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

        question_data = {
            'id':                   question_obj.id,
            'question_text':        question_obj.question_text,
            'answer_options':       question_obj.answer_options,
            'correct_answer':       question_obj.correct_answer,
            'estimated_difficulty': question_obj.estimated_difficulty,
            'topic_ids':            question_obj.topic_ids,
            'subtopic_ids':         question_obj.subtopic_ids,
            'order':                question_obj.order,
            'created_at':           question_obj.created_at.isoformat() if getattr(question_obj, 'created_at', None) else None,
        }

        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=2)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            existing_data = []

        existing_data.append(question_data)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Failed to export pre-assessment question to JSON: {e}")


# ── Database saves ─────────────────────────────────────────────────────────────

def save_minigame_questions_to_db_enhanced(questions_json: List[Dict[str, Any]],
                                           subtopic_combination,
                                           difficulty: str,
                                           game_type: str,
                                           rag_context: str,
                                           zone,
                                           thread_manager=None,
                                           max_to_save: Optional[int] = None) -> Tuple[List, List]:
    """Persist questions with deduplication and JSON export."""
    from question_generation.models import GeneratedQuestion

    subtopic_names = [s.name for s in subtopic_combination]
    subtopic_ids   = [s.id   for s in subtopic_combination]
    primary_subtopic = subtopic_combination[0]

    saved_questions = []
    duplicate_questions = []

    with transaction.atomic():
        to_save = questions_json[:max_to_save] if max_to_save is not None else questions_json

        for q in to_save:
            try:
                question_text = q.get('question_text') or q.get('question', '')
                question_hash = generate_question_hash(question_text, subtopic_combination, game_type, difficulty)

                existing = GeneratedQuestion.objects.filter(game_data__question_hash=question_hash).first()
                if existing:
                    logger.debug(f"Duplicate (hash {question_hash[:8]}…), skipping")
                    duplicate_questions.append({
                        'question_text': question_text[:100],
                        'hash': question_hash,
                        'existing_id': existing.id,
                        'subtopic_combination': subtopic_names,
                        'difficulty': difficulty,
                        'reason': 'duplicate_hash',
                    })
                    continue

                similar_qs = GeneratedQuestion.objects.filter(
                    subtopic__in=subtopic_combination,
                    estimated_difficulty=difficulty,
                    game_type=game_type
                ).exclude(id__in=[sq.id for sq in saved_questions])

                for sim_q in similar_qs:
                    if check_question_similarity(question_text, sim_q.question_text):
                        logger.debug(f"Similar question detected (similar to ID {sim_q.id}), skipping")
                        duplicate_questions.append({
                            'question_text': question_text[:100],
                            'similar_to_id': sim_q.id,
                            'subtopic_combination': subtopic_names,
                            'difficulty': difficulty,
                            'reason': 'similar_question',
                        })
                        break
                else:
                    if game_type == 'coding':
                        # New prompt field names with legacy fallbacks
                        clean_solution          = q.get('clean_solution') or q.get('correct_code', '')
                        code_shown_to_student   = q.get('code_shown_to_student') or q.get('buggy_code', '')
                        code_with_bug_fixed     = q.get('code_with_bug_fixed') or q.get('buggy_correct_code', '')
                        correct_answer          = clean_solution
                        function_name           = q.get('function_name', '')
                        sample_input            = q.get('sample_input', '')
                        sample_output           = q.get('sample_output', '')
                        hidden_tests            = q.get('hidden_tests', [])
                        buggy_question_text     = q.get('buggy_question_text', '')
                        explanation             = q.get('explanation', '')
                        buggy_explanation       = q.get('buggy_explanation', '')
                    else:
                        correct_answer          = q.get('answer', '')
                        explanation             = q.get('explanation', '')
                        function_name           = ''
                        sample_input            = ''
                        sample_output           = ''
                        hidden_tests            = []
                        clean_solution          = ''
                        code_shown_to_student   = ''
                        code_with_bug_fixed     = ''
                        buggy_question_text     = ''
                        buggy_explanation       = ''

                    question_obj = GeneratedQuestion.objects.create(
                        question_text=question_text,
                        correct_answer=correct_answer,
                        subtopic=primary_subtopic,
                        topic=primary_subtopic.topic,
                        estimated_difficulty=difficulty,
                        game_type=game_type,
                        game_data={
                            'question_hash':        question_hash,
                            'function_name':        function_name,
                            'sample_input':         sample_input,
                            'sample_output':        sample_output,
                            'hidden_tests':         hidden_tests,
                            'clean_solution':       clean_solution,
                            'code_shown_to_student': code_shown_to_student,
                            'code_with_bug_fixed':  code_with_bug_fixed,
                            'buggy_question_text':  buggy_question_text,
                            'explanation':          explanation,
                            'buggy_explanation':    buggy_explanation,
                            'subtopic_names':       subtopic_names,
                            'subtopic_ids':         subtopic_ids,
                            'zone_name':            zone.name,
                            'zone_order':           zone.order,
                            'rag_context':          rag_context[:2000] if rag_context else '',
                        }
                    )
                    saved_questions.append(question_obj)
                    try:
                        export_question_to_json(question_obj, game_type)
                    except Exception as json_err:
                        logger.warning(f"Failed to export question to JSON: {json_err}")

            except Exception as e:
                logger.error(f"Error saving question '{q.get('question_text', 'N/A')[:100]}': {e}")
                duplicate_questions.append({
                    'question_text': q.get('question_text', 'N/A')[:100],
                    'error': str(e),
                    'subtopic_combination': subtopic_names,
                    'difficulty': difficulty,
                    'reason': 'save_error',
                })

    return saved_questions, duplicate_questions


def save_questions_batch(questions_data: List[Dict[str, Any]],
                         subtopic,
                         game_type: str,
                         difficulty: str) -> List:
    """Simplified batch save (no deduplication)."""
    from question_generation.models import GeneratedQuestion

    saved_questions = []
    with transaction.atomic():
        for q_data in questions_data:
            try:
                question_obj = GeneratedQuestion.objects.create(
                    question_text=q_data.get('question_text', ''),
                    correct_answer=q_data.get('correct_answer', ''),
                    subtopic=subtopic,
                    difficulty=difficulty,
                    game_type=game_type,
                    rag_context=q_data.get('rag_context', ''),
                    game_data=q_data.get('game_data', {}),
                )
                saved_questions.append(question_obj)
            except Exception as e:
                logger.error(f"Error saving question in batch: {e}")
    return saved_questions


# ── Queries ────────────────────────────────────────────────────────────────────

def get_existing_questions_count(subtopic=None, game_type: str = None, difficulty: str = None) -> int:
    from question_generation.models import GeneratedQuestion
    qs = GeneratedQuestion.objects.all()
    if subtopic:
        qs = qs.filter(subtopic=subtopic)
    if game_type:
        qs = qs.filter(game_type=game_type)
    if difficulty:
        qs = qs.filter(difficulty=difficulty)
    return qs.count()


def delete_questions_by_criteria(subtopic=None, game_type: str = None, difficulty: str = None) -> int:
    from question_generation.models import GeneratedQuestion
    qs = GeneratedQuestion.objects.all()
    if subtopic:
        qs = qs.filter(subtopic=subtopic)
    if game_type:
        qs = qs.filter(game_type=game_type)
    if difficulty:
        qs = qs.filter(difficulty=difficulty)
    count = qs.count()
    qs.delete()
    return count
