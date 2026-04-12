import time
import logging
import concurrent.futures
from typing import List, Dict, Any
from django.conf import settings

logger = logging.getLogger(__name__)

from .generation_core import generate_questions_for_subtopic_combination
from .generation_status import generation_status_tracker


# ── Model loader (avoids circular imports) ─────────────────────────────────────

def _get_models():
    from content_ingestion.models import Subtopic, GameZone
    return Subtopic, GameZone


# ── Combination helpers ────────────────────────────────────────────────────────

def create_smart_subtopic_combinations(subtopics: List, max_combinations: int = None,
                                        difficulty: str = None) -> List[List]:
    """Build singles, pairs, and triples based on difficulty level."""
    from itertools import combinations

    if len(subtopics) == 1:
        return [[subtopics[0]]]

    difficulty_combo_map = {'beginner': 1, 'intermediate': 2, 'advanced': 3, 'master': 3}
    max_combo_size = difficulty_combo_map.get(difficulty, 3) if difficulty else 3
    max_combo_size = min(max_combo_size, len(subtopics))

    all_combinations = [[s] for s in subtopics]

    if max_combo_size >= 2:
        topic_groups: Dict[str, list] = {}
        for s in subtopics:
            topic_groups.setdefault(s.topic.name, []).append(s)

        same_topic_pairs = [
            list(pair)
            for group in topic_groups.values()
            if len(group) >= 2
            for pair in combinations(group, 2)
        ]
        cross_topic_pairs = [
            list(pair)
            for pair in combinations([g[0] for g in topic_groups.values()], 2)
        ] if len(topic_groups) >= 2 else []

        max_pairs = len(subtopics) // 2
        all_combinations.extend((same_topic_pairs + cross_topic_pairs)[:max_pairs])

    if max_combo_size >= 3:
        triples = list(combinations(subtopics, 3))
        max_triples = len(subtopics) // 3
        all_combinations.extend([list(t) for t in triples[:max_triples]])

    seen: set = set()
    unique = []
    for combo in all_combinations:
        key = tuple(sorted(s.id for s in combo))
        if key not in seen:
            unique.append(combo)
            seen.add(key)

    if max_combinations and len(unique) > max_combinations:
        unique = unique[:max_combinations]

    individuals = sum(1 for c in unique if len(c) == 1)
    pairs       = sum(1 for c in unique if len(c) == 2)
    logger.info(f"Combinations: {len(unique)} total ({individuals} individuals, {pairs} pairs)")
    return unique


def calculate_questions_per_combination(num_subtopics: int, num_questions_per_subtopic: int,
                                         num_combinations: int, difficulty: str) -> int:
    if num_combinations == 0:
        logger.warning(f"No combinations for {difficulty} ({num_subtopics} subtopics)")
        return 0
    budget = num_subtopics * num_questions_per_subtopic
    return max(1, budget // num_combinations)


# ── Single-subtopic batch ──────────────────────────────────────────────────────

def generate_questions_for_single_subtopic_batch(subtopic, difficulty_levels: List[str],
                                                  total_questions_needed: int, game_type: str,
                                                  session_id: str) -> Dict[str, Any]:
    """Distribute questions for a single subtopic across difficulty levels."""
    try:
        per_difficulty = total_questions_needed // len(difficulty_levels)
        extra          = total_questions_needed % len(difficulty_levels)
        total_saved    = 0

        for i, difficulty in enumerate(difficulty_levels):
            count = per_difficulty + (1 if i < extra else 0)
            if not count:
                continue
            result = generate_questions_for_subtopic_combination(
                subtopic_combination=[subtopic],
                difficulty=difficulty,
                num_questions=count,
                game_type=game_type,
                zone=subtopic.topic.zone,
                session_id=session_id,
            )
            if result['success']:
                total_saved += result.get('questions_saved', 0)
            else:
                logger.warning(f"Failed {difficulty} questions for {subtopic.name}: {result.get('error')}")

        return {
            'success':        total_saved > 0,
            'questions_saved': total_saved,
            'error':          None if total_saved > 0 else 'No questions generated',
        }
    except Exception as e:
        logger.error(f"Single subtopic batch error: {e}")
        return {'success': False, 'questions_saved': 0, 'error': str(e)}


# ── Subtopic-specific generation ───────────────────────────────────────────────

def run_subtopic_specific_generation(subtopic_ids: List[int],
                                      difficulty_levels: List[str],
                                      num_questions_per_subtopic: int,
                                      game_type: str,
                                      session_id: str) -> None:
    """Generate questions for explicit subtopics (no zone-wide combinations)."""
    try:
        Subtopic, _ = _get_models()
        subtopics = list(Subtopic.objects.filter(id__in=subtopic_ids).select_related('topic__zone'))
        if not subtopics:
            raise ValueError("No subtopics found for the provided IDs")

        logger.info(f"Subtopic-specific generation: {len(subtopics)} subtopics, {len(difficulty_levels)} difficulties")

        # ── Single-subtopic path ───────────────────────────────────────────────
        if len(subtopics) == 1:
            single = subtopics[0]
            total_needed      = len(difficulty_levels) * num_questions_per_subtopic
            actual_workers    = min(settings.QUESTION_GENERATION_WORKERS, total_needed)
            questions_per_worker = max(1, total_needed // actual_workers)

            batches = []
            assigned = 0
            for worker_id in range(actual_workers):
                worker_q = min(questions_per_worker, total_needed - assigned)
                if worker_q > 0:
                    batches.append({
                        'worker_id':        worker_id,
                        'subtopic':         single,
                        'difficulty_levels': difficulty_levels,
                        'questions_needed': worker_q,
                    })
                    assigned += worker_q

            generation_status_tracker.update_status(session_id, {
                'status': 'processing', 'total_tasks': len(batches),
                'completed_tasks': 0, 'successful_tasks': 0, 'total_questions': 0,
            })

            completed = successful = total_q = 0
            for batch in batches:
                if generation_status_tracker.is_session_cancelled(session_id):
                    break
                result = generate_questions_for_single_subtopic_batch(
                    subtopic=batch['subtopic'],
                    difficulty_levels=batch['difficulty_levels'],
                    total_questions_needed=batch['questions_needed'],
                    game_type=game_type,
                    session_id=session_id,
                )
                if result['success']:
                    successful += 1
                    total_q    += result.get('questions_saved', 0)
                else:
                    logger.warning(f"Worker {batch['worker_id']} failed: {result.get('error')}")
                completed += 1
                generation_status_tracker.update_status(session_id, {
                    'completed_tasks': completed, 'successful_tasks': successful,
                    'total_questions': total_q,
                    'progress_percentage': (completed / len(batches)) * 100,
                })

            generation_status_tracker.update_status(session_id, {
                'status': 'completed' if successful > 0 else 'error',
                'total_questions': total_q,
                'completed_tasks': completed, 'successful_tasks': successful,
            })
            return

        # ── Multi-subtopic path ────────────────────────────────────────────────
        all_combos: Dict[str, list] = {}
        all_q_per_combo: Dict[str, int] = {}
        total_tasks = 0

        for difficulty in difficulty_levels:
            combos = create_smart_subtopic_combinations(
                subtopics, max_combinations=50, difficulty=difficulty,
            )
            if not combos:
                logger.warning(f"No combinations for {difficulty}")
                continue
            q_per_combo = calculate_questions_per_combination(
                len(subtopics), num_questions_per_subtopic, len(combos), difficulty,
            )
            all_combos[difficulty]       = combos
            all_q_per_combo[difficulty]  = q_per_combo
            total_tasks                 += len(combos)
            logger.info(f"{difficulty.upper()}: {len(combos)} combinations × {q_per_combo} questions")

        generation_status_tracker.update_status(session_id, {
            'total_tasks': total_tasks, 'status': 'processing',
            'completed_tasks': 0, 'successful_tasks': 0, 'total_questions': 0,
        })

        completed = successful = total_q = 0

        def _process_combination(combination_idx, subtopic_combination, difficulty, questions_per_combo):
            if generation_status_tracker.is_session_cancelled(session_id):
                return {'success': False, 'error': 'cancelled',
                        'combination_idx': combination_idx, 'questions_saved': 0}
            names = [s.name for s in subtopic_combination]
            combo_type = "individual" if len(subtopic_combination) == 1 else f"{len(subtopic_combination)}-subtopic combo"
            result = generate_questions_for_subtopic_combination(
                subtopic_combination=subtopic_combination,
                difficulty=difficulty,
                num_questions=questions_per_combo,
                game_type=game_type,
                zone=subtopic_combination[0].topic.zone,
                session_id=session_id,
            )
            if result['success']:
                return {'success': True, 'combination_idx': combination_idx,
                        'questions_saved': result.get('questions_saved', 0),
                        'subtopic_names': names, 'combination_type': combo_type}
            logger.warning(f"Failed {combo_type} {names} — {difficulty}: {result.get('error')}")
            return {'success': False, 'combination_idx': combination_idx, 'questions_saved': 0,
                    'error': result.get('error'), 'subtopic_names': names, 'combination_type': combo_type}

        for difficulty in difficulty_levels:
            if generation_status_tracker.is_session_cancelled(session_id):
                break
            subtopic_combos = all_combos.get(difficulty, [])
            q_per_combo     = all_q_per_combo.get(difficulty, 1)

            try:
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=settings.QUESTION_GENERATION_WORKERS
                ) as executor:
                    try:
                        future_map = {
                            executor.submit(_process_combination, idx, combo, difficulty, q_per_combo): idx
                            for idx, combo in enumerate(subtopic_combos)
                        }
                    except RuntimeError as e:
                        if 'cannot schedule new futures' in str(e):
                            logger.warning(f"Interpreter shutting down during {difficulty} — stopping generation")
                            break
                        raise
                    for future in concurrent.futures.as_completed(future_map):
                        try:
                            result = future.result()
                            if result['success']:
                                successful += 1
                                total_q    += result['questions_saved']
                            elif result.get('error') != 'cancelled':
                                logger.warning(f"Failed combination {result['combination_idx']}: {result.get('error')}")
                            completed += 1
                            generation_status_tracker.update_status(session_id, {
                                'completed_tasks':    completed,
                                'successful_tasks':   successful,
                                'total_questions':    total_q,
                                'current_difficulty': difficulty,
                                'progress_percentage': round((completed / total_tasks) * 100, 1),
                            })
                        except Exception as e:
                            logger.error(f"Future result error: {e}")
                            completed += 1
            except RuntimeError as e:
                if 'cannot schedule new futures' in str(e):
                    logger.warning(f"Interpreter shutting down during {difficulty} — stopping generation")
                    break
                raise

            logger.info(f"{difficulty.upper()} done — {total_q} questions cumulative")

        final_status = 'cancelled' if generation_status_tracker.is_session_cancelled(session_id) else 'completed'
        generation_status_tracker.update_status(session_id, {
            'status':           final_status,
            'completed_tasks':  completed,
            'successful_tasks': successful,
            'total_questions':  total_q,
            'completion_time':  time.time(),
            'success_rate':     round((successful / completed) * 100, 1) if completed else 0,
        })
        logger.info(f"Generation {final_status}: {successful}/{completed} tasks, {total_q} questions")

    except Exception as e:
        logger.error(f"Critical error in subtopic-specific generation (session {session_id}): {e}")
        generation_status_tracker.update_status(session_id, {
            'status': 'error', 'error': str(e), 'completion_time': time.time(),
        })
        raise


# ── Summary / worker details ───────────────────────────────────────────────────

def get_subtopic_generation_summary(subtopic_ids: List[int],
                                     difficulty_levels: List[str],
                                     num_questions_per_subtopic: int) -> Dict[str, Any]:
    try:
        Subtopic, _ = _get_models()
        subtopics = list(Subtopic.objects.filter(id__in=subtopic_ids).select_related('topic__zone'))
        if not subtopics:
            return {'error': 'No subtopics found for the provided IDs'}

        zones: Dict[str, Dict] = {}
        for s in subtopics:
            zones.setdefault(s.topic.zone.name, {}).setdefault(s.topic.name, []).append(s.name)

        return {
            'subtopic_count':    len(subtopics),
            'difficulty_levels': difficulty_levels,
            'zones_and_topics':  zones,
            'generation_scope': {
                'total_subtopics':     len(subtopics),
                'difficulty_levels':   len(difficulty_levels),
                'questions_per_subtopic': num_questions_per_subtopic,
            },
        }
    except Exception as e:
        logger.error(f"Error getting subtopic generation summary: {e}")
        return {'error': str(e)}


def get_worker_details(session_id: str) -> Dict[str, Any]:
    try:
        session = generation_status_tracker.get_session_status(session_id)
        if not session:
            return {'error': 'Session not found'}

        if session.get('type') == 'pre_assessment':
            return {
                'session_id':   session_id,
                'session_type': 'pre_assessment',
                'status':       session['status'],
                'current_step': session.get('step', ''),
                'progress': {
                    'questions_requested': session.get('total_questions', 0),
                    'questions_generated': session.get('questions_generated', 0),
                    'topics_covered':      len(session.get('topics', [])),
                },
                'message': 'Pre-assessment generation uses a single process, not multiple workers',
            }

        workers = session.get('workers', {})

        if not workers:
            synthetic = {
                'worker_id':    'subtopic_worker_0',
                'status':       session.get('status', 'unknown'),
                'zone_name':    'Multiple Zones',
                'difficulty':   session.get('current_difficulty', 'Multiple'),
                'current_step': f"Processing {session.get('current_combination', [])}",
                'progress': {
                    'completed_tasks':    session.get('completed_tasks', 0),
                    'total_tasks':        session.get('total_tasks', 0),
                    'successful_tasks':   session.get('successful_tasks', 0),
                    'total_questions':    session.get('total_questions', 0),
                    'progress_percentage': session.get('progress_percentage', 0),
                },
                'start_time':          session.get('start_time', time.time()),
                'last_activity':       session.get('last_updated', time.time()),
                'estimated_completion': None,
                'duration': (time.time() - session['start_time']) if session.get('start_time') else 0,
            }
            active = 1 if synthetic['status'] == 'processing' else 0
            return {
                'session_id':   session_id,
                'session_type': 'subtopic_specific',
                'workers':      [synthetic],
                'summary': {
                    'total_workers':     1,
                    'active_workers':    active,
                    'completed_workers': 1 if synthetic['status'] == 'completed' else 0,
                    'failed_workers':    1 if synthetic['status'] in ('error', 'failed') else 0,
                    'pending_workers':   0,
                },
            }

        worker_details = sorted([
            {
                'worker_id':            wid,
                'status':               w['status'],
                'zone_name':            w['zone_name'],
                'difficulty':           w['difficulty'],
                'current_step':         w['current_step'],
                'progress':             w['progress'],
                'start_time':           w['start_time'],
                'last_activity':        w['last_activity'],
                'estimated_completion': w.get('estimated_completion'),
                'duration':             (time.time() - w['start_time']) if w['start_time'] else 0,
            }
            for wid, w in workers.items()
        ], key=lambda x: x['worker_id'])

        return {
            'session_id':   session_id,
            'session_type': 'bulk_generation',
            'workers':      worker_details,
            'summary': {
                'total_workers':     len(worker_details),
                'active_workers':    sum(1 for w in worker_details if w['status'] == 'processing'),
                'completed_workers': sum(1 for w in worker_details if w['status'] == 'completed'),
                'failed_workers':    sum(1 for w in worker_details if w['status'] in ('error', 'failed')),
                'pending_workers':   sum(1 for w in worker_details if w['status'] == 'pending'),
            },
        }

    except Exception as e:
        logger.error(f"Error getting worker details for session {session_id}: {e}")
        return {'error': str(e)}
