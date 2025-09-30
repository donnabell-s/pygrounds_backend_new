# Core question generation functionality
# Handles generating questions for topics/subtopics with RAG context and LLM integration

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import List, Dict, Any, Tuple, Optional

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
                                              session_id=None) -> Dict[str, Any]:
    # Generate questions for given subtopics using RAG context
    # Parameters:
    # - subtopic_combination: List of subtopics to combine content from
    # - difficulty: Question difficulty level
    # - num_questions: How many questions to generate
    # - game_type: Either 'coding' or 'non_coding'
    # - zone: The zone these subtopics belong to
    # - thread_manager: Optional manager for parallel processing
    # - session_id: Optional session ID for cancellation checking
    
    # Check for cancellation if session_id provided
    if session_id:
        from .generation_status import generation_status_tracker
        if generation_status_tracker.is_session_cancelled(session_id):
            return {
                'success': False,
                'error': 'Generation was cancelled',
                'subtopic_names': extract_subtopic_names(subtopic_combination),
                'difficulty': difficulty,
                'questions_saved': 0
            }
    
    try:
        subtopic_names = extract_subtopic_names(subtopic_combination)
        
        # Get RAG context
        if len(subtopic_combination) == 1:
            rag_context = get_rag_context_for_subtopic(subtopic_combination[0], difficulty)
        else:
            rag_context = get_combined_rag_context(subtopic_combination, difficulty)
        
        # Create context for prompt generation
        context = create_generation_context(subtopic_combination, difficulty, num_questions, rag_context)
        
        # Create system prompt based on game type
        system_prompt = create_system_prompt(subtopic_names, difficulty, num_questions, game_type, zone)
        
        # Get LLM prompt
        prompt = deepseek_prompt_manager.get_prompt_for_minigame(game_type, context)
        
        # Set temperature based on game type
        temperature = CODING_TEMPERATURE if game_type == 'coding' else NON_CODING_TEMPERATURE
        
        # Call LLM
        llm_response = invoke_deepseek(
            prompt,
            system_prompt=system_prompt,
            model="deepseek-chat",
            temperature=temperature,
            max_tokens=8000  # Higher token limit for complete responses with all fields
        )
        
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
            if validate_question_data(q, game_type):
                formatted_q = format_question_for_game_type(q, game_type)
                valid_questions.append(formatted_q)
        
        if not valid_questions:
            return {
                'success': False,
                'error': 'No valid questions generated',
                'subtopic_names': subtopic_names,
                'difficulty': difficulty
            }
        
        # Save to database
        saved_questions, duplicates = save_minigame_questions_to_db_enhanced(
            valid_questions, subtopic_combination, difficulty, game_type, rag_context, zone, thread_manager
        )
        
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
    """
    Create system prompt based on game type and parameters.
    
    Args:
        subtopic_names: List of subtopic names
        difficulty: Difficulty level
        num_questions: Number of questions to generate
        game_type: 'coding' or 'non_coding'
        zone: GameZone instance
        
    Returns:
        System prompt string
    """
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
    """
    Worker function to process a single zone-difficulty combination.
    Generates questions for all subtopic combinations within this zone-difficulty pair.
    
    Args:
        args: Tuple of (zone, difficulty, num_questions_per_subtopic, game_type, thread_id, session_id)
        
    Returns:
        Dictionary with processing results
    """
    (zone, difficulty, num_questions_per_subtopic, game_type, thread_id, session_id) = args
    
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
        from content_ingestion.models import Subtopic
        from itertools import combinations
        
        print(f"🚀 Thread {thread_id}: Processing Zone {zone.order}: {zone.name} - {difficulty}")
        
        # Get all subtopics in this zone
        zone_subtopics = list(Subtopic.objects.filter(topic__zone=zone).select_related('topic'))
        
        if not zone_subtopics:
            result['error'] = f"No subtopics found in zone {zone.name}"
            return result
        
        # Generate combinations (singles, pairs, and trios only)
        max_combination_size = min(3, len(zone_subtopics))
        
        for combination_size in range(1, max_combination_size + 1):
            for subtopic_combination in combinations(zone_subtopics, combination_size):
                try:
                    generation_result = generate_questions_for_subtopic_combination(
                        subtopic_combination, difficulty, num_questions_per_subtopic, 
                        game_type, zone, thread_manager=None, session_id=session_id
                    )
                    
                    if generation_result['success']:
                        result['total_generated'] += generation_result['questions_saved']
                        result['combination_stats']['successful'] += 1
                    else:
                        result['combination_stats']['failed'] += 1
                        subtopic_names = generation_result['subtopic_names']
                        print(f"❌ Thread {thread_id}: Failed combination: {subtopic_names}")
                        
                        # Only try fallback for combinations of size > 1
                        if combination_size > 1 and 'error' in generation_result:
                            print(f"🔄 Thread {thread_id}: Attempting fallback to individual subtopics")
                            # Try each subtopic individually as a fallback
                            for individual_subtopic in subtopic_combination:
                                try:
                                    fallback_result = generate_questions_for_subtopic_combination(
                                        [individual_subtopic], difficulty, num_questions_per_subtopic,
                                        game_type, zone, thread_manager=None, session_id=session_id
                                    )
                                    
                                    if fallback_result['success']:
                                        result['total_generated'] += fallback_result['questions_saved']
                                        result['combination_stats']['successful'] += 1
                                        print(f"✅ Thread {thread_id}: Fallback successful for: {fallback_result['subtopic_names']}")
                                except Exception as e:
                                    print(f"❌ Thread {thread_id}: Fallback failed for subtopic: {str(e)}")
                        
                except Exception as e:
                    result['combination_stats']['failed'] += 1
                    print(f"❌ Thread {thread_id}: Error processing combination: {str(e)}")
        
        result['success'] = True
        print(f"✅ Thread {thread_id}: Completed {zone.name} - {difficulty}: {result['total_generated']} questions")
        
    except Exception as e:
        result['error'] = f"Zone-difficulty processing failed: {str(e)}"
        print(f"❌ Thread {thread_id}: Error in {zone.name} - {difficulty}: {str(e)}")
    
    return result


def run_multithreaded_generation(zones, 
                                difficulty_levels: List[str], 
                                num_questions_per_subtopic: int, 
                                game_type: str, 
                                session_id: str = None,
                                max_workers: int = 4) -> Dict[str, Any]:
    """
    Run multithreaded question generation across zones and difficulties.
    
    Args:
        zones: QuerySet or list of GameZone instances
        difficulty_levels: List of difficulty levels to process
        num_questions_per_subtopic: Number of questions to generate per subtopic
        game_type: 'coding' or 'non_coding'
        session_id: Optional session ID for tracking generation progress
        max_workers: Maximum number of concurrent workers
        
    Returns:
        Dictionary with generation results and statistics
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor
    
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
    
    print(f"🎯 Starting multithreaded generation with {max_workers} workers")
    
    # Prepare tasks: each task is a (zone, difficulty) combination
    tasks = []
    thread_id = 0
    for zone in zones:
        for difficulty in difficulty_levels:
            task_args = (zone, difficulty, num_questions_per_subtopic, game_type, thread_id, session_id)
            tasks.append(task_args)
            thread_id += 1
    
    # Execute tasks
    results = []
    successful_results = []
    failed_results = []
    cancelled = False
    start_time = time.time()
    
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
