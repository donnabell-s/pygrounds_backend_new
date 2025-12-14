# Core generation helpers

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import List, Dict, Any, Tuple, Optional
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
    extract_subtopic_names
)
from ..helpers.db_operations import save_minigame_questions_to_db_enhanced


def generate_questions_for_subtopic_combination(subtopic_combination,
                                              difficulty: str,
                                              num_questions: int,
                                              game_type: str,
                                              zone,
                                              thread_manager=None,
                                              session_id=None,
                                              rag_context=None) -> Dict[str, Any]:
    # Generate + persist questions for a subtopic combo

    def _cancelled_result():
        return {
            'success': False,
            'error': 'Generation was cancelled',
            'subtopic_names': extract_subtopic_names(subtopic_combination),
            'difficulty': difficulty,
            'questions_saved': 0
        }

    def _is_cancelled() -> bool:
        if not session_id:
            return False
        from .generation_status import generation_status_tracker
        return generation_status_tracker.is_session_cancelled(session_id)

    # Check for cancellation if session_id provided
    if _is_cancelled():
        return _cancelled_result()

    try:
        subtopic_names = extract_subtopic_names(subtopic_combination)

        if _is_cancelled():
            return _cancelled_result()

        # Get RAG context (use provided context or fetch if not provided)
        if rag_context is None:
            if len(subtopic_combination) == 1:
                rag_context = get_rag_context_for_subtopic(subtopic_combination[0], difficulty, game_type)
            else:
                rag_context = get_combined_rag_context(subtopic_combination, difficulty, game_type)

        if _is_cancelled():
            return _cancelled_result()

        # Create context for prompt generation
        context = create_generation_context(subtopic_combination, difficulty, num_questions, rag_context)

        # Create system prompt based on game type
        system_prompt = create_system_prompt(subtopic_names, difficulty, num_questions, game_type, zone)

        # Get LLM prompt
        prompt = deepseek_prompt_manager.get_prompt_for_minigame(game_type, context)

        # Set temperature based on game type
        temperature = CODING_TEMPERATURE if game_type == 'coding' else NON_CODING_TEMPERATURE

        # Call LLM
        if _is_cancelled():
            return _cancelled_result()

        llm_response = invoke_deepseek(
            prompt,
            system_prompt=system_prompt,
            model="deepseek-chat",
            temperature=temperature,
            max_tokens=8000  # Higher token limit for complete responses with all fields
        )

        if _is_cancelled():
            return _cancelled_result()

        # Parse response
        questions_json = parse_llm_json_response(llm_response, game_type)
        if not questions_json:
            return {
                'success': False,
                'error': 'Failed to parse LLM response',
                'subtopic_names': subtopic_names,
                'difficulty': difficulty
            }

        # Validate and format questions
        valid_questions = []
        for q in questions_json:
            if _is_cancelled():
                return _cancelled_result()
            if validate_question_data(q, game_type):
                formatted_q = format_question_for_game_type(q, game_type)
                valid_questions.append(formatted_q)

        # Enforce requested number of questions: trim to num_questions if LLM returned more
        if len(valid_questions) > num_questions:
            valid_questions = valid_questions[:num_questions]

        if not valid_questions:
            return {
                'success': False,
                'error': 'No valid questions generated',
                'subtopic_names': subtopic_names,
                'difficulty': difficulty
            }

        if _is_cancelled():
            return _cancelled_result()

        # Save to database (defensive: ensure we don't persist more than requested)
        logger.info(f"Requested num_questions={num_questions}, validated_items={len(valid_questions)}")
        saved_questions, duplicates = save_minigame_questions_to_db_enhanced(
            valid_questions, subtopic_combination, difficulty, game_type, rag_context, zone, thread_manager,
            max_to_save=num_questions
        )
        logger.info(f"Saved_questions={len(saved_questions)}, duplicates_skipped={len(duplicates)}")

        return {
            'success': True,
            'questions_generated': len(valid_questions),
            'questions_saved': len(saved_questions),
            'duplicates_skipped': len(duplicates),
            'subtopic_names': subtopic_names,
            'difficulty': difficulty,
            'saved_questions': saved_questions
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'subtopic_names': extract_subtopic_names(subtopic_combination),
            'difficulty': difficulty
        }


def create_system_prompt(subtopic_names: List[str],
                        difficulty: str,
                        num_questions: int,
                        game_type: str,
                        zone) -> str:
    # System prompt for DeepSeek
    if game_type == 'coding':
        keys = [
            "question_text", "buggy_question_text",
            "explanation", "buggy_explanation",
            "function_name", "sample_input", "sample_output",
            "hidden_tests", "buggy_code", "correct_code",
            "buggy_correct_code", "difficulty"
        ]
        return (
            f"Generate {num_questions} Python DEBUGGING questions for {len(subtopic_names)} subtopics: "
            f"{', '.join(subtopic_names)}. Zone: {zone.name} (Zone {zone.order}), Difficulty: {difficulty}. "
            f"CRITICAL: EVERY item MUST include EXACTLY these {len(keys)} keys (spelling exact): {', '.join(keys)}. "
            f'"explanation" MUST state why correct_code solves the `question_text` (20–40 words). '
            f'"buggy_explanation" MUST state the root cause in `buggy_code` and how buggy_correct_code fixes it (20–40 words). '
            f"If any key is missing/empty in any item, REVISE internally and output ONLY a JSON array with exactly {num_questions} valid items."
        )
    else:  # non_coding
        return (
            f"Generate {num_questions} knowledge questions "
            f"for {len(subtopic_names)} subtopics: {', '.join(subtopic_names)}. "
            f"Zone: {zone.name} (Zone {zone.order}), Difficulty: {difficulty}. "
            f"Format as JSON array: question_text, answer, difficulty"
        )


def process_zone_difficulty_combination(args) -> Dict[str, Any]:
    # Process a single (zone, difficulty) task
    (zone, difficulty, num_questions_per_subtopic, game_type, thread_id, session_id, max_total_questions) = args
    
    result = {
        'thread_id': thread_id,
        'zone_id': zone.id,
        'zone_name': zone.name,
        'difficulty': difficulty,
        'total_generated': 0,
        'combination_stats': {'successful': 0, 'failed': 0},
        'success': False
    }
    
    try:
        worker_start_time = time.time()
        if session_id:
            from .generation_status import generation_status_tracker
            generation_status_tracker.update_worker_status(session_id, {
                'worker_id': thread_id,
                'status': 'processing',
                'zone_name': zone.name,
                'difficulty': difficulty,
                'current_step': 'starting',
                'start_time': worker_start_time,
                'progress': {
                    'total_combinations': 0,
                    'processed_combinations': 0,
                    'successful_combinations': 0,
                    'failed_combinations': 0,
                    'questions_generated': 0,
                },
            })

            # If cancelled before starting, exit early.
            if generation_status_tracker.is_session_cancelled(session_id):
                generation_status_tracker.update_worker_status(session_id, {
                    'worker_id': thread_id,
                    'status': 'cancelled',
                    'current_step': 'cancelled',
                })
                result['error'] = 'cancelled'
                return result

        from content_ingestion.models import Subtopic
        from itertools import combinations
        
        print(f"🚀 Thread {thread_id}: Processing Zone {zone.order}: {zone.name} - {difficulty}")
        
        # Get all subtopics in this zone
        zone_subtopics = list(Subtopic.objects.filter(topic__zone=zone).select_related('topic'))
        
        if not zone_subtopics:
            result['error'] = f"No subtopics found in zone {zone.name}"
            return result
        
        # Determine max combination size. If only 1 question per subtopic is requested,
        # prefer single-subtopic generation to avoid producing cross-subtopic combinations.
        if num_questions_per_subtopic == 1:
            max_combination_size = 1
            print(f"🔧 Thread {thread_id}: Limiting to single subtopics only (num_questions_per_subtopic={num_questions_per_subtopic})")
        elif max_total_questions and max_total_questions <= 1:
            # For very small total limits, only generate single subtopic questions to avoid combinatorial explosion
            max_combination_size = 1
            print(f"🔧 Thread {thread_id}: Limiting to single subtopics only (max_total_questions={max_total_questions})")
        else:
            # Normal behavior: singles, pairs, and trios
            max_combination_size = min(3, len(zone_subtopics))

        # Collect all combinations first for batch RAG context retrieval
        all_combinations = []
        for combination_size in range(1, max_combination_size + 1):
            for subtopic_combination in combinations(zone_subtopics, combination_size):
                all_combinations.append(subtopic_combination)

        if session_id:
            from .generation_status import generation_status_tracker
            generation_status_tracker.update_worker_status(session_id, {
                'worker_id': thread_id,
                'current_step': 'batch_rag_context',
                'progress': {
                    'total_combinations': len(all_combinations),
                    'processed_combinations': 0,
                    'successful_combinations': 0,
                    'failed_combinations': 0,
                    'questions_generated': 0,
                },
            })
        
        # Batch fetch RAG contexts for all combinations to reduce database connections
        rag_contexts = {}
        if all_combinations:
            if session_id:
                from .generation_status import generation_status_tracker
                if generation_status_tracker.is_session_cancelled(session_id):
                    generation_status_tracker.update_worker_status(session_id, {
                        'worker_id': thread_id,
                        'status': 'cancelled',
                        'current_step': 'cancelled',
                    })
                    result['error'] = 'cancelled'
                    return result

            from ..helpers.rag_context import get_batched_rag_contexts
            print(f"📚 Thread {thread_id}: Batch fetching RAG contexts for {len(all_combinations)} combinations")
            rag_contexts = get_batched_rag_contexts(all_combinations, difficulty, game_type)
            print(f"✅ Thread {thread_id}: Retrieved {len(rag_contexts)} RAG contexts")
        
        # Process each combination using pre-fetched RAG contexts
        processed = 0
        for subtopic_combination in all_combinations:
            try:
                if session_id:
                    from .generation_status import generation_status_tracker
                    if generation_status_tracker.is_session_cancelled(session_id):
                        result['error'] = 'cancelled'
                        break

                # Get pre-fetched RAG context for this combination
                combination_key = tuple(subtopic_combination) if isinstance(subtopic_combination, (list, tuple)) else (subtopic_combination,)
                pre_fetched_rag_context = rag_contexts.get(combination_key)

                generation_result = generate_questions_for_subtopic_combination(
                    subtopic_combination, difficulty, num_questions_per_subtopic, 
                    game_type, zone, thread_manager=None, session_id=session_id,
                    rag_context=pre_fetched_rag_context
                )
                
                if generation_result['success']:
                    result['total_generated'] += generation_result['questions_saved']
                    result['combination_stats']['successful'] += 1
                else:
                    result['combination_stats']['failed'] += 1
                    subtopic_names = generation_result['subtopic_names']
                    combination_type = "single subtopic" if len(subtopic_combination) == 1 else f"{len(subtopic_combination)}-subtopic combination"
                    print(f"❌ Thread {thread_id}: Failed {combination_type}: {subtopic_names}")
                    
                    # Only try fallback for combinations of size > 1
                    if len(subtopic_combination) > 1 and 'error' in generation_result:
                        print(f"🔄 Thread {thread_id}: Attempting fallback to individual subtopics")
                        # Try each subtopic individually as a fallback
                        for individual_subtopic in subtopic_combination:
                            try:
                                if session_id:
                                    from .generation_status import generation_status_tracker
                                    if generation_status_tracker.is_session_cancelled(session_id):
                                        result['error'] = 'cancelled'
                                        break

                                # Get pre-fetched RAG context for individual subtopic
                                individual_key = (individual_subtopic,)
                                individual_rag_context = rag_contexts.get(individual_key)

                                fallback_result = generate_questions_for_subtopic_combination(
                                    [individual_subtopic], difficulty, num_questions_per_subtopic,
                                    game_type, zone, thread_manager=None, session_id=session_id,
                                    rag_context=individual_rag_context
                                )
                                
                                if fallback_result['success']:
                                    result['total_generated'] += fallback_result['questions_saved']
                                    result['combination_stats']['successful'] += 1
                                    print(f"✅ Thread {thread_id}: Fallback successful for: {fallback_result['subtopic_names']}")
                            except Exception as e:
                                print(f"❌ Thread {thread_id}: Fallback failed for subtopic: {str(e)}")

                        if result.get('error') == 'cancelled':
                            break
                    
            except Exception as e:
                result['combination_stats']['failed'] += 1
                print(f"❌ Thread {thread_id}: Error processing combination: {str(e)}")

            processed += 1
            if session_id:
                from .generation_status import generation_status_tracker
                generation_status_tracker.update_worker_status(session_id, {
                    'worker_id': thread_id,
                    'current_step': 'generating',
                    'progress': {
                        'total_combinations': len(all_combinations),
                        'processed_combinations': processed,
                        'successful_combinations': result['combination_stats']['successful'],
                        'failed_combinations': result['combination_stats']['failed'],
                        'questions_generated': result['total_generated'],
                    },
                })

        if session_id and result.get('error') == 'cancelled':
            from .generation_status import generation_status_tracker
            generation_status_tracker.update_worker_status(session_id, {
                'worker_id': thread_id,
                'status': 'cancelled',
                'current_step': 'cancelled',
            })
            result['success'] = False
            return result
        
        result['success'] = True
        print(f"✅ Thread {thread_id}: Completed {zone.name} - {difficulty}: {result['total_generated']} questions")

        if session_id:
            from .generation_status import generation_status_tracker
            generation_status_tracker.update_worker_status(session_id, {
                'worker_id': thread_id,
                'status': 'completed',
                'current_step': 'completed',
                'progress': {
                    'total_combinations': len(all_combinations),
                    'processed_combinations': len(all_combinations),
                    'successful_combinations': result['combination_stats']['successful'],
                    'failed_combinations': result['combination_stats']['failed'],
                    'questions_generated': result['total_generated'],
                },
            })
        
    except Exception as e:
        result['error'] = f"Zone-difficulty processing failed: {str(e)}"
        print(f"❌ Thread {thread_id}: Error in {zone.name} - {difficulty}: {str(e)}")

        if session_id:
            from .generation_status import generation_status_tracker
            generation_status_tracker.update_worker_status(session_id, {
                'worker_id': thread_id,
                'status': 'failed',
                'current_step': 'error',
                'progress': {
                    'total_combinations': result.get('combination_stats', {}).get('successful', 0) + result.get('combination_stats', {}).get('failed', 0),
                    'processed_combinations': result.get('combination_stats', {}).get('successful', 0) + result.get('combination_stats', {}).get('failed', 0),
                    'successful_combinations': result.get('combination_stats', {}).get('successful', 0),
                    'failed_combinations': result.get('combination_stats', {}).get('failed', 0),
                    'questions_generated': result.get('total_generated', 0),
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
    # Run generation across zones/difficulties
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from django.conf import settings
    
    # Set default max_workers if not provided - use game-type-specific optimization
    if max_workers is None:
        # Use game-type-specific worker counts to optimize database usage
        if game_type == 'coding':
            max_workers = getattr(settings, 'CODING_QUESTION_WORKERS', 3)
        elif game_type == 'non_coding':
            max_workers = getattr(settings, 'NON_CODING_QUESTION_WORKERS', 6)
        elif game_type == 'pre_assessment':
            max_workers = getattr(settings, 'PRE_ASSESSMENT_WORKERS', 6)
        else:
            # Fallback to default
            max_workers = getattr(settings, 'QUESTION_GENERATION_WORKERS', 4)
    
    # Track session progress if session_id provided
    if session_id:
        from .generation_status import generation_status_tracker
        zone_names = [zone.name for zone in zones]
        generation_status_tracker.create_session(
            session_id=session_id,
            total_workers=len(zones) * len(difficulty_levels),
            zones=zone_names,
            difficulties=difficulty_levels
        )

    print(f"🎯 Starting {game_type} question generation with {max_workers} workers (optimized for {game_type} database patterns)")
    print(f"⚙️ Worker scaling: Coding={getattr(settings, 'CODING_QUESTION_WORKERS', 3)}, Non-coding={getattr(settings, 'NON_CODING_QUESTION_WORKERS', 6)}, Pre-assessment={getattr(settings, 'PRE_ASSESSMENT_WORKERS', 6)}")
    
    # Prepare tasks: each task is a (zone, difficulty) combination
    tasks = []
    thread_id = 0
    for zone in zones:
        for difficulty in difficulty_levels:
            task_args = (zone, difficulty, num_questions_per_subtopic, game_type, thread_id, session_id, max_total_questions)
            tasks.append(task_args)
            thread_id += 1
    
    # Execute tasks
    results = []
    successful_results = []
    failed_results = []
    cancelled = False
    start_time = time.time()

    print(f"🚀 ThreadPoolExecutor starting with {max_workers} workers for {len(tasks)} tasks")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        try:
            futures = []
            for task in tasks:
                # Check for cancellation before submitting each task
                if session_id:
                    from .generation_status import generation_status_tracker
                    if generation_status_tracker.is_session_cancelled(session_id):
                        cancelled = True
                        break
                
                future = executor.submit(process_zone_difficulty_combination, task)
                futures.append(future)
            
            # Collect results
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
                    
                    if result.get('success', False):
                        successful_results.append(result)
                    else:
                        failed_results.append(result)
                        
                    if session_id:
                        from .generation_status import generation_status_tracker
                        generation_status_tracker.update_status(session_id, {
                            'completed_workers': len(results),
                            'successful_workers': len(successful_results),
                            'failed_workers': len(failed_results)
                        })
                            
                except Exception as e:
                    failed_results.append({
                        'success': False,
                        'error': str(e)
                    })
        except Exception as e:
            return {
                'success': False,
                'error': f'Generation failed: {str(e)}',
                'partial_results': results
            }
    
    # Calculate final statistics
    total_generated = sum(r.get('total_generated', 0) for r in successful_results)
    success_rate = len(successful_results) / len(tasks) if tasks else 0
    execution_time = time.time() - start_time
    
    # Update final session status if session_id provided
    if session_id:
        from .generation_status import generation_status_tracker
        final_status = {
            'status': 'cancelled' if cancelled else 'completed',
            'completed_workers': len(results),
            'successful_workers': len(successful_results),
            'failed_workers': len(failed_results),
            'total_questions': total_generated,
            'success_rate': success_rate,
            'total_duration': execution_time
        }
        generation_status_tracker.update_status(session_id, final_status)
    
    return {
        'success': True,
        'cancelled': cancelled,
        'total_generated': total_generated,
        'successful_tasks': len(successful_results),
        'failed_tasks': len(failed_results),
        'results': results,
        'execution_time': execution_time
    }
