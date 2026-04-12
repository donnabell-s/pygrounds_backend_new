import time
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

from ..helpers.deepseek_prompts import deepseek_prompt_manager
from ..helpers.llm_utils import invoke_deepseek, CODING_TEMPERATURE, NON_CODING_TEMPERATURE
from ..helpers.rag_context import get_rag_context_for_subtopic, get_combined_rag_context
from ..helpers.question_processing import (
    parse_llm_json_response,
    format_question_for_game_type,
    validate_question_data,
    create_generation_context,
    extract_subtopic_names,
)
from ..helpers.db_operations import save_minigame_questions_to_db_enhanced


# ── Core generation ────────────────────────────────────────────────────────────

def generate_questions_for_subtopic_combination(subtopic_combination,
                                                difficulty: str,
                                                num_questions: int,
                                                game_type: str,
                                                zone,
                                                thread_manager=None,
                                                session_id=None,
                                                rag_context=None) -> Dict[str, Any]:
    """Generate and persist questions for a subtopic combination."""

    def _cancelled_result():
        return {
            'success': False,
            'error': 'Generation was cancelled',
            'subtopic_names': extract_subtopic_names(subtopic_combination),
            'difficulty': difficulty,
            'questions_saved': 0,
        }

    def _is_cancelled() -> bool:
        if not session_id:
            return False
        from .generation_status import generation_status_tracker
        return generation_status_tracker.is_session_cancelled(session_id)

    if _is_cancelled():
        return _cancelled_result()

    try:
        subtopic_names = extract_subtopic_names(subtopic_combination)

        if _is_cancelled():
            return _cancelled_result()

        if rag_context is None:
            rag_context = (
                get_rag_context_for_subtopic(subtopic_combination[0], difficulty, game_type)
                if len(subtopic_combination) == 1
                else get_combined_rag_context(subtopic_combination, difficulty, game_type)
            )

        if _is_cancelled():
            return _cancelled_result()

        context = create_generation_context(subtopic_combination, difficulty, num_questions, rag_context)
        system_prompt = create_system_prompt(subtopic_names, difficulty, num_questions, game_type, zone)
        prompt = deepseek_prompt_manager.get_prompt_for_minigame(game_type, context)
        temperature = CODING_TEMPERATURE if game_type == 'coding' else NON_CODING_TEMPERATURE

        if _is_cancelled():
            return _cancelled_result()

        llm_response = invoke_deepseek(
            prompt,
            system_prompt=system_prompt,
            model="deepseek-chat",
            temperature=temperature,
            max_tokens=8000,
        )

        if _is_cancelled():
            return _cancelled_result()

        questions_json = parse_llm_json_response(llm_response, game_type)
        if not questions_json:
            return {
                'success': False,
                'error': 'Failed to parse LLM response',
                'subtopic_names': subtopic_names,
                'difficulty': difficulty,
            }

        valid_questions = []
        for q in questions_json:
            if _is_cancelled():
                return _cancelled_result()
            if validate_question_data(q, game_type):
                valid_questions.append(format_question_for_game_type(q, game_type))

        if len(valid_questions) > num_questions:
            valid_questions = valid_questions[:num_questions]

        if not valid_questions:
            return {
                'success': False,
                'error': 'No valid questions generated',
                'subtopic_names': subtopic_names,
                'difficulty': difficulty,
            }

        if _is_cancelled():
            return _cancelled_result()

        logger.info(f"Requested {num_questions}, validated {len(valid_questions)} items")
        saved_questions, duplicates = save_minigame_questions_to_db_enhanced(
            valid_questions, subtopic_combination, difficulty, game_type,
            rag_context, zone, thread_manager, max_to_save=num_questions,
        )
        logger.info(f"Saved {len(saved_questions)}, skipped {len(duplicates)} duplicates")

        return {
            'success': True,
            'questions_generated': len(valid_questions),
            'questions_saved': len(saved_questions),
            'duplicates_skipped': len(duplicates),
            'subtopic_names': subtopic_names,
            'difficulty': difficulty,
            'saved_questions': saved_questions,
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'subtopic_names': extract_subtopic_names(subtopic_combination),
            'difficulty': difficulty,
        }


# ── Prompt helpers ─────────────────────────────────────────────────────────────

def create_system_prompt(subtopic_names: List[str],
                         difficulty: str,
                         num_questions: int,
                         game_type: str,
                         zone) -> str:
    if game_type == 'coding':
        keys = [
            "question_text", "buggy_question_text", "explanation", "buggy_explanation",
            "function_name", "sample_input", "sample_output",
            "hidden_tests", "clean_solution", "code_shown_to_student", "code_with_bug_fixed", "difficulty",
        ]
        return (
            f"Generate {num_questions} Python DEBUGGING questions for {len(subtopic_names)} subtopics: "
            f"{', '.join(subtopic_names)}. Zone: {zone.name} (Zone {zone.order}), Difficulty: {difficulty}. "
            f"CRITICAL: EVERY item MUST include EXACTLY these {len(keys)} keys (spelling exact): {', '.join(keys)}. "
            f'"explanation" MUST state why clean_solution solves the `question_text` (20–40 words). '
            f'"buggy_explanation" MUST state the root cause in `code_shown_to_student` and how code_with_bug_fixed fixes it (20–40 words). '
            f"If any key is missing/empty in any item, REVISE internally and output ONLY a JSON array with exactly {num_questions} valid items."
        )
    else:
        return (
            f"Generate {num_questions} knowledge questions for {len(subtopic_names)} subtopics: "
            f"{', '.join(subtopic_names)}. Zone: {zone.name} (Zone {zone.order}), Difficulty: {difficulty}. "
            f"Format as JSON array: question_text, answer, difficulty"
        )


# ── Zone/difficulty processing ─────────────────────────────────────────────────

def process_zone_difficulty_combination(args) -> Dict[str, Any]:
    """Process a single (zone, difficulty) task."""
    (zone, difficulty, num_questions_per_subtopic, game_type, thread_id, session_id, max_total_questions) = args

    result = {
        'thread_id':        thread_id,
        'zone_id':          zone.id,
        'zone_name':        zone.name,
        'difficulty':       difficulty,
        'total_generated':  0,
        'combination_stats': {'successful': 0, 'failed': 0},
        'success':          False,
    }

    try:
        worker_start_time = time.time()
        if session_id:
            from .generation_status import generation_status_tracker
            generation_status_tracker.update_worker_status(session_id, {
                'worker_id':    thread_id,
                'status':       'processing',
                'zone_name':    zone.name,
                'difficulty':   difficulty,
                'current_step': 'starting',
                'start_time':   worker_start_time,
                'progress': {
                    'total_combinations':      0,
                    'processed_combinations':  0,
                    'successful_combinations': 0,
                    'failed_combinations':     0,
                    'questions_generated':     0,
                },
            })
            if generation_status_tracker.is_session_cancelled(session_id):
                generation_status_tracker.update_worker_status(session_id, {
                    'worker_id': thread_id, 'status': 'cancelled', 'current_step': 'cancelled',
                })
                result['error'] = 'cancelled'
                return result

        from content_ingestion.models import Subtopic
        from itertools import combinations

        logger.info(f"Thread {thread_id}: Zone {zone.order} '{zone.name}' — {difficulty}")

        zone_subtopics = list(Subtopic.objects.filter(topic__zone=zone).select_related('topic'))
        if not zone_subtopics:
            result['error'] = f"No subtopics in zone {zone.name}"
            return result

        if num_questions_per_subtopic == 1 or (max_total_questions and max_total_questions <= 1):
            max_combination_size = 1
        else:
            difficulty_combo_map = {'beginner': 1, 'intermediate': 2, 'advanced': 3, 'master': 3}
            max_combination_size = min(
                difficulty_combo_map.get(difficulty, 3),
                len(zone_subtopics)
            )

        all_combinations = [
            combo
            for size in range(1, max_combination_size + 1)
            for combo in combinations(zone_subtopics, size)
        ]

        if session_id:
            from .generation_status import generation_status_tracker
            generation_status_tracker.update_worker_status(session_id, {
                'worker_id':    thread_id,
                'current_step': 'batch_rag_context',
                'progress': {
                    'total_combinations':      len(all_combinations),
                    'processed_combinations':  0,
                    'successful_combinations': 0,
                    'failed_combinations':     0,
                    'questions_generated':     0,
                },
            })
            if generation_status_tracker.is_session_cancelled(session_id):
                generation_status_tracker.update_worker_status(session_id, {
                    'worker_id': thread_id, 'status': 'cancelled', 'current_step': 'cancelled',
                })
                result['error'] = 'cancelled'
                return result

        rag_contexts = {}
        if all_combinations:
            from ..helpers.rag_context import get_batched_rag_contexts
            logger.info(f"Thread {thread_id}: Fetching RAG contexts for {len(all_combinations)} combinations")
            rag_contexts = get_batched_rag_contexts(all_combinations, difficulty, game_type)

        processed = 0
        for subtopic_combination in all_combinations:
            try:
                if session_id:
                    from .generation_status import generation_status_tracker
                    if generation_status_tracker.is_session_cancelled(session_id):
                        result['error'] = 'cancelled'
                        break

                combo_key = tuple(subtopic_combination) if isinstance(subtopic_combination, (list, tuple)) else (subtopic_combination,)
                generation_result = generate_questions_for_subtopic_combination(
                    subtopic_combination, difficulty, num_questions_per_subtopic,
                    game_type, zone, thread_manager=None, session_id=session_id,
                    rag_context=rag_contexts.get(combo_key),
                )

                if generation_result['success']:
                    result['total_generated'] += generation_result['questions_saved']
                    result['combination_stats']['successful'] += 1
                else:
                    result['combination_stats']['failed'] += 1
                    if len(subtopic_combination) > 1 and 'error' in generation_result:
                        for individual in subtopic_combination:
                            try:
                                if session_id:
                                    from .generation_status import generation_status_tracker
                                    if generation_status_tracker.is_session_cancelled(session_id):
                                        result['error'] = 'cancelled'
                                        break
                                fallback = generate_questions_for_subtopic_combination(
                                    [individual], difficulty, num_questions_per_subtopic,
                                    game_type, zone, thread_manager=None, session_id=session_id,
                                    rag_context=rag_contexts.get((individual,)),
                                )
                                if fallback['success']:
                                    result['total_generated'] += fallback['questions_saved']
                                    result['combination_stats']['successful'] += 1
                            except Exception as e:
                                logger.error(f"Thread {thread_id}: Fallback failed: {e}")
                        if result.get('error') == 'cancelled':
                            break

            except Exception as e:
                result['combination_stats']['failed'] += 1
                logger.error(f"Thread {thread_id}: Error processing combination: {e}")

            processed += 1
            if session_id:
                from .generation_status import generation_status_tracker
                generation_status_tracker.update_worker_status(session_id, {
                    'worker_id':    thread_id,
                    'current_step': 'generating',
                    'progress': {
                        'total_combinations':      len(all_combinations),
                        'processed_combinations':  processed,
                        'successful_combinations': result['combination_stats']['successful'],
                        'failed_combinations':     result['combination_stats']['failed'],
                        'questions_generated':     result['total_generated'],
                    },
                })

        if session_id and result.get('error') == 'cancelled':
            from .generation_status import generation_status_tracker
            generation_status_tracker.update_worker_status(session_id, {
                'worker_id': thread_id, 'status': 'cancelled', 'current_step': 'cancelled',
            })
            result['success'] = False
            return result

        result['success'] = True
        logger.info(f"Thread {thread_id}: Completed '{zone.name}' {difficulty} — {result['total_generated']} questions")

        if session_id:
            from .generation_status import generation_status_tracker
            generation_status_tracker.update_worker_status(session_id, {
                'worker_id':    thread_id,
                'status':       'completed',
                'current_step': 'completed',
                'progress': {
                    'total_combinations':      len(all_combinations),
                    'processed_combinations':  len(all_combinations),
                    'successful_combinations': result['combination_stats']['successful'],
                    'failed_combinations':     result['combination_stats']['failed'],
                    'questions_generated':     result['total_generated'],
                },
            })

    except Exception as e:
        result['error'] = f"Zone-difficulty processing failed: {e}"
        logger.error(f"Thread {thread_id}: Error in '{zone.name}' {difficulty}: {e}")
        if session_id:
            from .generation_status import generation_status_tracker
            stats = result['combination_stats']
            generation_status_tracker.update_worker_status(session_id, {
                'worker_id':    thread_id,
                'status':       'failed',
                'current_step': 'error',
                'progress': {
                    'total_combinations':      stats['successful'] + stats['failed'],
                    'processed_combinations':  stats['successful'] + stats['failed'],
                    'successful_combinations': stats['successful'],
                    'failed_combinations':     stats['failed'],
                    'questions_generated':     result.get('total_generated', 0),
                },
            })

    return result


def run_multithreaded_generation(zones,
                                 difficulty_levels: List[str],
                                 num_questions_per_subtopic: int,
                                 game_type: str,
                                 session_id: str = None,
                                 max_workers: int = None,
                                 max_total_questions: int = None) -> Dict[str, Any]:
    """Run generation across zones/difficulties using a thread pool."""
    from concurrent.futures import ThreadPoolExecutor
    from django.conf import settings

    if max_workers is None:
        worker_setting = {
            'coding':         'CODING_QUESTION_WORKERS',
            'non_coding':     'NON_CODING_QUESTION_WORKERS',
            'pre_assessment': 'PRE_ASSESSMENT_WORKERS',
        }.get(game_type, 'QUESTION_GENERATION_WORKERS')
        max_workers = getattr(settings, worker_setting, 4)

    if session_id:
        from .generation_status import generation_status_tracker
        generation_status_tracker.create_session(
            session_id=session_id,
            total_workers=len(zones) * len(difficulty_levels),
            zones=[z.name for z in zones],
            difficulties=difficulty_levels,
        )

    tasks = [
        (zone, difficulty, num_questions_per_subtopic, game_type, thread_id, session_id, max_total_questions)
        for thread_id, (zone, difficulty) in enumerate(
            (z, d) for z in zones for d in difficulty_levels
        )
    ]

    logger.info(f"Starting {game_type} generation: {max_workers} workers, {len(tasks)} tasks")

    results = []
    successful_results = []
    failed_results = []
    cancelled = False
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        try:
            futures = []
            for task in tasks:
                if session_id:
                    from .generation_status import generation_status_tracker
                    if generation_status_tracker.is_session_cancelled(session_id):
                        cancelled = True
                        break
                try:
                    futures.append(executor.submit(process_zone_difficulty_combination, task))
                except RuntimeError as e:
                    if 'cannot schedule new futures' in str(e):
                        logger.warning("Interpreter shutting down — stopping task submission")
                        cancelled = True
                        break
                    raise

            for future in futures:
                try:
                    if session_id:
                        from .generation_status import generation_status_tracker
                        if generation_status_tracker.is_session_cancelled(session_id):
                            cancelled = True
                            for f in futures:
                                f.cancel()
                            break
                    result = future.result(timeout=None)
                    results.append(result)
                    (successful_results if result.get('success') else failed_results).append(result)
                    if session_id:
                        from .generation_status import generation_status_tracker
                        generation_status_tracker.update_status(session_id, {
                            'completed_workers':  len(results),
                            'successful_workers': len(successful_results),
                            'failed_workers':     len(failed_results),
                        })
                except Exception as e:
                    failed_results.append({'success': False, 'error': str(e)})
        except RuntimeError as e:
            if 'cannot schedule new futures' in str(e):
                logger.warning("Interpreter shutting down during bulk generation")
                cancelled = True
            else:
                return {'success': False, 'error': f'Generation failed: {e}', 'partial_results': results}
        except Exception as e:
            return {'success': False, 'error': f'Generation failed: {e}', 'partial_results': results}

    total_generated = sum(r.get('total_generated', 0) for r in successful_results)
    execution_time  = time.time() - start_time

    if session_id:
        from .generation_status import generation_status_tracker
        generation_status_tracker.update_status(session_id, {
            'status':             'cancelled' if cancelled else 'completed',
            'completed_workers':  len(results),
            'successful_workers': len(successful_results),
            'failed_workers':     len(failed_results),
            'total_questions':    total_generated,
            'success_rate':       len(successful_results) / len(tasks) if tasks else 0,
            'total_duration':     execution_time,
        })

    return {
        'success':         True,
        'cancelled':       cancelled,
        'total_generated': total_generated,
        'successful_tasks': len(successful_results),
        'failed_tasks':    len(failed_results),
        'results':         results,
        'execution_time':  execution_time,
    }
