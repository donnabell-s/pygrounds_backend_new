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
                                              thread_manager=None) -> Dict[str, Any]:
    # Generate questions for given subtopics using RAG context
    # Parameters:
    # - subtopic_combination: List of subtopics to combine content from
    # - difficulty: Question difficulty level
    # - num_questions: How many questions to generate
    # - game_type: Either 'coding' or 'non_coding'
    # - zone: The zone these subtopics belong to
    # - thread_manager: Optional manager for parallel processing
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
            temperature=temperature
        )
        
        # Parse response
        questions_json = parse_llm_json_response(llm_response)
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
        return (
            f"Generate {num_questions} coding challenges "
            f"for {len(subtopic_names)} subtopics: {', '.join(subtopic_names)}. "
            f"Zone: {zone.name} (Zone {zone.order}), Difficulty: {difficulty}. "
            f"Format as JSON array: question_text, function_name, sample_input, sample_output, hidden_tests, buggy_code, difficulty"
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
        args: Tuple of (zone, difficulty, num_questions_per_subtopic, game_type, thread_id, thread_manager)
        
    Returns:
        Dictionary with processing results
    """
    (zone, difficulty, num_questions_per_subtopic, game_type, thread_id, thread_manager) = args
    
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
                        game_type, zone, thread_manager
                    )
                    
                    if generation_result['success']:
                        result['total_generated'] += generation_result['questions_saved']
                        result['combination_stats']['successful'] += 1
                    else:
                        result['combination_stats']['failed'] += 1
                        print(f"❌ Thread {thread_id}: Failed combination: {generation_result['subtopic_names']}")
                        
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
                                max_workers: int = None) -> Dict[str, Any]:
    """
    Run multithreaded question generation across zones and difficulties.
    
    Args:
        zones: QuerySet or list of GameZone instances
        difficulty_levels: List of difficulty levels to process
        num_questions_per_subtopic: Questions to generate per subtopic combination
        game_type: 'coding' or 'non_coding'
        max_workers: Optional max worker threads
        
    Returns:
        Dictionary with generation results and statistics
    """
    from ..helpers.threading_manager import LLMThreadPoolManager
    
    # Initialize thread manager
    thread_manager = LLMThreadPoolManager(max_workers=max_workers, game_type=game_type)
    
    if not thread_manager.initialize_json_file():
        return {
            'success': False,
            'error': 'Failed to initialize JSON file',
            'results': []
        }
    
    print(f"🎯 Starting multithreaded generation with {thread_manager.max_workers} workers")
    
    # Prepare tasks: each task is a (zone, difficulty) combination
    tasks = []
    for zone in zones:
        for difficulty in difficulty_levels:
            task_args = (zone, difficulty, num_questions_per_subtopic, game_type, len(tasks), thread_manager)
            tasks.append(task_args)
    
    # Execute tasks
    results = []
    successful_results = []
    failed_results = []
    
    with ThreadPoolExecutor(max_workers=thread_manager.max_workers) as executor:
        try:
            # Submit all tasks with timeout
            future_results = executor.map(
                process_zone_difficulty_combination, 
                tasks, 
                timeout=thread_manager.task_timeout * len(tasks)
            )
            
            # Collect results
            for result in future_results:
                results.append(result)
                if result.get('success', False):
                    successful_results.append(result)
                else:
                    failed_results.append(result)
                    
        except TimeoutError:
            return {
                'success': False,
                'error': 'Generation timed out',
                'partial_results': results,
                'timeout_seconds': thread_manager.task_timeout * len(tasks)
            }
    
    # Calculate final statistics
    total_generated = sum(r.get('total_generated', 0) for r in successful_results)
    thread_stats = thread_manager.get_stats()
    
    # Finalize JSON file
    additional_stats = {
        'total_zones_processed': len(set(r['zone_id'] for r in successful_results)),
        'total_difficulties_processed': len(difficulty_levels),
        'successful_zone_difficulty_pairs': len(successful_results),
        'failed_zone_difficulty_pairs': len(failed_results)
    }
    
    thread_manager.finalize_json_file(additional_stats)
    
    return {
        'success': True,
        'total_generated': total_generated,
        'duplicates_skipped': thread_stats['duplicate_count'],
        'thread_stats': thread_stats,
        'successful_results': len(successful_results),
        'failed_results': len(failed_results),
        'json_filename': thread_manager.json_filename,
        'results': results
    }
