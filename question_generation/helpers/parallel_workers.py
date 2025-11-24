"""
Parallel worker utilities for handling multiple zone-difficulty combinations.
Provides utilities for distributed question generation processing with enhanced 
batch processing and smart subtopic combinations.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from itertools import combinations
from django.conf import settings

logger = logging.getLogger(__name__)

# Import models here to avoid circular imports
def get_models():
    from content_ingestion.models import Subtopic
    from content_ingestion.models import GameZone  
    return Subtopic, GameZone

from .generation_core import generate_questions_for_subtopic_combination
from .generation_status import generation_status_tracker

# Utility functions
def extract_object_names(objects):
    """Extract names from objects safely."""
    return [getattr(obj, 'name', str(obj)) for obj in objects]


def create_smart_subtopic_combinations(subtopics: List, max_combinations: int = None, difficulty: str = None) -> List[List]:
    """
    Create smart subtopic combinations focused on 1-2 subtopics like preassessment.
    Prioritizes individual subtopics and pairs for comprehensive coverage.

    Args:
        subtopics: List of subtopics to combine
        max_combinations: Maximum number of combinations to generate
        difficulty: Difficulty level (used for logging only)

    Returns:
        List of subtopic combinations (1-2 subtopics each)
    """
    logger.debug(f"🔍 DEBUG: Creating 1-2 subtopic combinations for {len(subtopics)} subtopics, difficulty: {difficulty}")
    all_combinations = []

    # Special case: If only 1 subtopic is selected, use it
    if len(subtopics) == 1:
        logger.info(f"🔄 Single subtopic selected: {subtopics[0].name}")
        all_combinations.append([subtopics[0]])
        return all_combinations

    # 1. Always include all individual subtopics (like preassessment comprehensive coverage)
    logger.info(f"📚 Adding {len(subtopics)} individual subtopics")
    for subtopic in subtopics:
        all_combinations.append([subtopic])

    # 2. Add strategic pairs for integrated understanding (like preassessment)
    # Group by topic to create meaningful pairs
    topic_groups = {}
    for subtopic in subtopics:
        topic_name = subtopic.topic.name
        if topic_name not in topic_groups:
            topic_groups[topic_name] = []
        topic_groups[topic_name].append(subtopic)

    # Add same-topic pairs (complementary subtopics within same topic)
    same_topic_pairs = []
    for topic_subtopics in topic_groups.values():
        if len(topic_subtopics) >= 2:
            # Add all possible pairs within the same topic
            for pair in combinations(topic_subtopics, 2):
                same_topic_pairs.append(list(pair))

    # Add cross-topic pairs (connecting different topics)
    cross_topic_pairs = []
    if len(topic_groups) >= 2:
        # Get one representative from each topic
        topic_representatives = [group[0] for group in topic_groups.values()]
        # Create pairs between different topics
        for pair in combinations(topic_representatives, 2):
            cross_topic_pairs.append(list(pair))

    # Combine and prioritize: individuals first, then pairs
    all_pairs = same_topic_pairs + cross_topic_pairs

    # Limit pairs to prevent explosion (max 50% of individuals)
    max_pairs = len(subtopics) // 2
    selected_pairs = all_pairs[:max_pairs]

    logger.info(f"🔗 Adding {len(selected_pairs)} subtopic pairs ({len(same_topic_pairs)} same-topic, {len(cross_topic_pairs)} cross-topic)")
    all_combinations.extend(selected_pairs)

    # Remove duplicates while preserving order
    unique_combinations = []
    seen = set()
    for combo in all_combinations:
        combo_ids = tuple(sorted([s.id for s in combo]))
        if combo_ids not in seen:
            unique_combinations.append(combo)
            seen.add(combo_ids)

    # Apply max_combinations limit if specified
    if max_combinations and len(unique_combinations) > max_combinations:
        unique_combinations = unique_combinations[:max_combinations]

    # Log final combination breakdown
    individuals = len([c for c in unique_combinations if len(c) == 1])
    pairs = len([c for c in unique_combinations if len(c) == 2])

    logger.info(f"📊 Final combinations: {len(unique_combinations)} total ({individuals} individuals, {pairs} pairs)")
    return unique_combinations


def calculate_questions_per_combination(num_subtopics: int,
                                       num_questions_per_subtopic: int,
                                       num_combinations: int,
                                       difficulty: str) -> int:
    """
    Calculate how many questions each combination should generate
    for a specific difficulty level.

    Each difficulty gets its own full budget of questions per subtopic.

    Args:
        num_subtopics: Number of individual subtopics
        num_questions_per_subtopic: Questions requested per subtopic per difficulty
        num_combinations: Total combinations generated for this difficulty
        difficulty: The difficulty level being processed

    Returns:
        Questions per combination for this difficulty level
    """
    # Each difficulty gets the full budget independently
    total_budget_per_difficulty = num_subtopics * num_questions_per_subtopic

    # Distribute evenly among all combinations for this difficulty
    if num_combinations == 0:
        logger.warning(f"⚠️ No combinations generated for {difficulty} difficulty with {num_subtopics} subtopics")
        return 0

    questions_per_combination = max(1, total_budget_per_difficulty // num_combinations)

    logger.debug(f"📊 {difficulty.upper()} distribution: {total_budget_per_difficulty} budget ÷ {num_combinations} combinations = {questions_per_combination} questions per combination")
    return questions_per_combination


def generate_questions_for_single_subtopic_batch(subtopic, difficulty_levels: List[str],
                                                total_questions_needed: int, game_type: str,
                                                session_id: str) -> Dict[str, Any]:
    """
    Generate questions for a single subtopic across multiple difficulties.
    Distributes questions evenly across difficulties.

    Args:
        subtopic: Single subtopic to generate questions for
        difficulty_levels: List of difficulty levels
        total_questions_needed: Total questions to generate
        game_type: 'coding' or 'non_coding'
        session_id: Session ID for tracking

    Returns:
        Dict with success status and questions_saved count
    """
    try:
        # Distribute questions across difficulties
        questions_per_difficulty = total_questions_needed // len(difficulty_levels)
        extra_questions = total_questions_needed % len(difficulty_levels)

        total_saved = 0

        for i, difficulty in enumerate(difficulty_levels):
            # Add extra question to first difficulties if needed
            questions_for_this_difficulty = questions_per_difficulty + (1 if i < extra_questions else 0)

            if questions_for_this_difficulty > 0:
                logger.debug(f"🎯 Generating {questions_for_this_difficulty} {difficulty} questions for {subtopic.name}")

                result = generate_questions_for_subtopic_combination(
                    subtopic_combination=[subtopic],
                    difficulty=difficulty,
                    num_questions=questions_for_this_difficulty,
                    game_type=game_type,
                    zone=subtopic.topic.zone,
                    session_id=session_id
                )

                if result['success']:
                    questions_saved = result.get('questions_saved', 0)
                    total_saved += questions_saved
                    logger.debug(f"✅ Generated {questions_saved} {difficulty} questions for {subtopic.name}")
                else:
                    logger.warning(f"❌ Failed to generate {difficulty} questions for {subtopic.name}: {result.get('error', 'Unknown error')}")

        return {
            'success': total_saved > 0,
            'questions_saved': total_saved,
            'error': None if total_saved > 0 else 'No questions generated'
        }

    except Exception as e:
        logger.error(f"❌ Error in single subtopic batch generation: {str(e)}")
        return {
            'success': False,
            'questions_saved': 0,
            'error': str(e)
        }


def run_subtopic_specific_generation(subtopic_ids: List[int],
                                   difficulty_levels: List[str],
                                   num_questions_per_subtopic: int,
                                   game_type: str,
                                   session_id: str) -> None:
    """
    Generate questions for specific subtopics across multiple difficulties.

    Args:
        subtopic_ids: List of subtopic IDs to generate questions for
        difficulty_levels: List of difficulty levels to process
        num_questions_per_subtopic: Number of questions to generate per subtopic
        game_type: Either 'coding' or 'non_coding'
        session_id: Session ID for tracking progress
    """
    try:
        Subtopic, _ = get_models()
        
        # Get the specific subtopics
        subtopics = list(Subtopic.objects.filter(id__in=subtopic_ids).select_related('topic__zone'))
        logger.info(f"🔍 DEBUG: Processing {len(subtopics)} subtopics: {[s.name for s in subtopics]}")

        if not subtopics:
            raise ValueError("No subtopics found for the provided IDs")

        logger.info(f"🚀 Starting subtopic-specific generation for {len(subtopics)} subtopics, {len(difficulty_levels)} difficulties")
        logger.info(f"🔍 DEBUG: Difficulty levels: {difficulty_levels}")

        # Special handling for single subtopic: use question-based workers instead of difficulty-based
        if len(subtopics) == 1:
            single_subtopic = subtopics[0]
            logger.info(f"🔄 Single subtopic detected: {single_subtopic.name} - switching to question-based worker allocation")

            # Calculate total questions needed across all difficulties
            total_questions_needed = len(difficulty_levels) * num_questions_per_subtopic
            questions_per_worker = max(1, total_questions_needed // settings.QUESTION_GENERATION_WORKERS)
            actual_workers = min(settings.QUESTION_GENERATION_WORKERS, total_questions_needed)

            logger.info(f"📊 Single subtopic mode: {total_questions_needed} total questions, {actual_workers} workers, {questions_per_worker} questions per worker")

            # Create question batches for workers
            question_batches = []
            questions_assigned = 0

            for worker_id in range(actual_workers):
                remaining_questions = total_questions_needed - questions_assigned
                worker_questions = min(questions_per_worker, remaining_questions)

                if worker_questions > 0:
                    batch = {
                        'worker_id': worker_id,
                        'subtopic': single_subtopic,
                        'difficulty_levels': difficulty_levels,
                        'questions_needed': worker_questions,
                        'game_type': game_type,
                        'session_id': session_id
                    }
                    question_batches.append(batch)
                    questions_assigned += worker_questions

            # Update session status
            generation_status_tracker.update_status(session_id, {
                'status': 'processing',
                'total_tasks': len(question_batches),  # Correct total tasks for single subtopic
                'completed_tasks': 0,
                'successful_tasks': 0,
                'total_questions': 0
            })

            # Process question batches with workers
            completed_tasks = 0
            successful_tasks = 0
            total_questions = 0

            for batch in question_batches:
                try:
                    # Check for cancellation
                    if generation_status_tracker.is_session_cancelled(session_id):
                        logger.info(f"📝 Session {session_id} cancelled during batch processing")
                        break

                    worker_id = batch['worker_id']
                    questions_needed = batch['questions_needed']

                    logger.info(f"🎯 Worker {worker_id}: Generating {questions_needed} questions for {single_subtopic.name}")

                    # Generate questions for this batch across all difficulties
                    batch_result = generate_questions_for_single_subtopic_batch(
                        subtopic=single_subtopic,
                        difficulty_levels=difficulty_levels,
                        total_questions_needed=questions_needed,
                        game_type=game_type,
                        session_id=session_id
                    )

                    if batch_result['success']:
                        successful_tasks += 1
                        questions_generated = batch_result.get('questions_saved', 0)
                        total_questions += questions_generated
                        logger.info(f"✅ Worker {worker_id}: Generated {questions_generated} questions")
                    else:
                        logger.warning(f"❌ Worker {worker_id}: Failed to generate questions: {batch_result.get('error', 'Unknown error')}")

                    completed_tasks += 1

                    # Update status
                    generation_status_tracker.update_status(session_id, {
                        'completed_tasks': completed_tasks,
                        'successful_tasks': successful_tasks,
                        'total_questions': total_questions,
                        'current_batch': f"Worker {worker_id}",
                        'progress_percentage': (completed_tasks / len(question_batches)) * 100
                    })

                except Exception as e:
                    logger.error(f"❌ Error in worker {batch['worker_id']}: {str(e)}")
                    completed_tasks += 1

            # Final status update
            final_status = {
                'status': 'completed' if successful_tasks > 0 else 'error',
                'total_questions': total_questions,
                'completed_tasks': completed_tasks,
                'successful_tasks': successful_tasks
            }
            generation_status_tracker.update_status(session_id, final_status)

            logger.info(f"🏁 Single subtopic generation completed: {total_questions} questions generated by {successful_tasks}/{len(question_batches)} workers")
            return

        # Original multi-subtopic logic continues below...
        all_difficulty_combinations = {}
        all_difficulty_questions_per_combo = {}
        total_tasks = 0

        for difficulty in difficulty_levels:
            logger.info(f"🔧 Preparing combinations for difficulty: {difficulty.upper()}")
            logger.info(f"   ├── Input subtopics: {len(subtopics)} total")
            logger.info(f"   ├── Subtopic IDs: {[s.id for s in subtopics]}")

            max_combinations_per_difficulty = 50  # Reasonable limit per difficulty
            difficulty_combinations = create_smart_subtopic_combinations(
                subtopics,
                max_combinations=max_combinations_per_difficulty,
                difficulty=difficulty
            )

            logger.info(f"🔍 DEBUG: {difficulty.upper()} - {len(subtopics)} subtopics generated {len(difficulty_combinations)} combinations")

            if len(difficulty_combinations) == 0:
                logger.warning(f"⚠️ No combinations generated for {difficulty} with {len(subtopics)} subtopics")
                continue  # Skip this difficulty if no combinations

            # Log combination types
            individuals = len([c for c in difficulty_combinations if len(c) == 1])
            pairs = len([c for c in difficulty_combinations if len(c) == 2])
            logger.info(f"   └── Combination breakdown: {individuals} individuals, {pairs} pairs")

            # Calculate questions per combination for this difficulty level
            questions_per_combo = calculate_questions_per_combination(
                num_subtopics=len(subtopics),
                num_questions_per_subtopic=num_questions_per_subtopic,
                num_combinations=len(difficulty_combinations),
                difficulty=difficulty
            )

            all_difficulty_combinations[difficulty] = difficulty_combinations
            all_difficulty_questions_per_combo[difficulty] = questions_per_combo
            total_tasks += len(difficulty_combinations)

            # Calculate expected questions for this difficulty
            expected_questions = len(difficulty_combinations) * questions_per_combo
            budget_per_difficulty = len(subtopics) * num_questions_per_subtopic

            logger.info(f"📊 {difficulty.upper()}: {len(difficulty_combinations)} combinations × {questions_per_combo} questions = {expected_questions} total")
            logger.info(f"   └── Budget: {budget_per_difficulty} questions ({len(subtopics)} subtopics × {num_questions_per_subtopic})")

        logger.info(f"📊 Total tasks across all difficulties: {total_tasks}")

        # Update session status with correct total_tasks
        generation_status_tracker.update_status(session_id, {
            'total_tasks': total_tasks,  # Override the placeholder
            'status': 'processing',
            'completed_tasks': 0,
            'successful_tasks': 0,
            'total_questions': 0
        })

        # Process each difficulty with its specific combinations
        completed_tasks = 0
        successful_tasks = 0
        total_questions = 0

        logger.info(f"🎯 STARTING PARALLEL PROCESSING OF {len(difficulty_levels)} DIFFICULTY LEVELS: {difficulty_levels}")
        logger.info(f"📋 Each difficulty uses parallel workers, then moves to next difficulty")
        logger.info(f"⚡ ThreadPoolExecutor: {settings.QUESTION_GENERATION_WORKERS} concurrent workers per difficulty")

        for difficulty_idx, difficulty in enumerate(difficulty_levels):
            logger.info(f"")
            logger.info(f"🎯 DIFFICULTY {difficulty_idx + 1}/{len(difficulty_levels)}: STARTING {difficulty.upper()}")
            logger.info(f"🔄 Processing difficulty {difficulty_idx + 1}/{len(difficulty_levels)}: {difficulty.upper()}")

            # Check for cancellation before processing each difficulty
            if generation_status_tracker.is_session_cancelled(session_id):
                logger.info(f"📝 Session {session_id} cancelled during difficulty {difficulty}")
                break

            # Get the combinations and question count for this specific difficulty
            subtopic_combinations = all_difficulty_combinations[difficulty]
            questions_per_combo = all_difficulty_questions_per_combo[difficulty]

            # Log worker goals clearly
            individuals = len([c for c in subtopic_combinations if len(c) == 1])
            pairs = len([c for c in subtopic_combinations if len(c) == 2])
            trios = len([c for c in subtopic_combinations if len(c) == 3])

            total_questions_for_difficulty = len(subtopic_combinations) * questions_per_combo

            logger.info(f"🔄 Processing {difficulty.upper()} level:")
            logger.info(f"   └── {len(subtopic_combinations)} combinations ({individuals} individuals, {pairs} pairs, {trios} trios)")
            logger.info(f"   └── {questions_per_combo} questions per combination = {total_questions_for_difficulty} total questions")
            logger.info(f"   └── Budget: {len(subtopics)} subtopics × {num_questions_per_subtopic} = {len(subtopics) * num_questions_per_subtopic} questions")
            logger.info(f"⚡ Using ThreadPoolExecutor with {settings.QUESTION_GENERATION_WORKERS} workers for parallel processing")

            # Process combinations in parallel using ThreadPoolExecutor
            import concurrent.futures
            difficulty_completed_tasks = 0
            difficulty_successful_tasks = 0
            difficulty_questions = 0

            def process_single_combination(combination_idx, subtopic_combination):
                """Process a single subtopic combination and return results."""
                try:
                    # Check for cancellation
                    if generation_status_tracker.is_session_cancelled(session_id):
                        return {
                            'success': False,
                            'error': 'cancelled',
                            'combination_idx': combination_idx,
                            'questions_saved': 0
                        }

                    subtopic_names = [sub.name for sub in subtopic_combination]
                    combination_type = "individual" if len(subtopic_combination) == 1 else f"{len(subtopic_combination)}-subtopic combo"

                    logger.debug(f"🎯 Worker processing: {questions_per_combo} {difficulty} {game_type} questions for {combination_type}: {subtopic_names}")

                    result = generate_questions_for_subtopic_combination(
                        subtopic_combination=subtopic_combination,
                        difficulty=difficulty,
                        num_questions=questions_per_combo,
                        game_type=game_type,
                        zone=subtopic_combination[0].topic.zone,
                        session_id=session_id
                    )

                    if result['success']:
                        questions_saved = result.get('questions_saved', 0)
                        logger.debug(f"✅ Worker completed: {questions_saved} questions for {combination_type}: {subtopic_names} - {difficulty}")

                        return {
                            'success': True,
                            'combination_idx': combination_idx,
                            'questions_saved': questions_saved,
                            'subtopic_names': subtopic_names,
                            'combination_type': combination_type
                        }
                    else:
                        logger.warning(f"❌ Worker failed: {combination_type}: {subtopic_names} - {difficulty}: {result.get('error', 'Unknown error')}")

                        return {
                            'success': False,
                            'combination_idx': combination_idx,
                            'questions_saved': 0,
                            'error': result.get('error', 'Unknown error'),
                            'subtopic_names': subtopic_names,
                            'combination_type': combination_type
                        }

                except Exception as e:
                    logger.error(f"❌ Worker error processing combination {combination_idx}: {str(e)}")
                    return {
                        'success': False,
                        'combination_idx': combination_idx,
                        'questions_saved': 0,
                        'error': str(e)
                    }

            # Submit all combinations for this difficulty to the thread pool
            with concurrent.futures.ThreadPoolExecutor(max_workers=settings.QUESTION_GENERATION_WORKERS) as executor:
                # Submit all tasks
                future_to_idx = {
                    executor.submit(process_single_combination, idx, combination): idx
                    for idx, combination in enumerate(subtopic_combinations)
                }

                # Process results as they complete
                for future in concurrent.futures.as_completed(future_to_idx):
                    try:
                        result = future.result()
                        combination_idx = result['combination_idx']

                        if result['success']:
                            difficulty_successful_tasks += 1
                            difficulty_questions += result['questions_saved']
                            logger.info(f"✅ Completed combination {combination_idx + 1}/{len(subtopic_combinations)}: {result['questions_saved']} questions")
                        else:
                            if result.get('error') != 'cancelled':
                                logger.warning(f"❌ Failed combination {combination_idx + 1}/{len(subtopic_combinations)}: {result.get('error', 'Unknown error')}")

                        difficulty_completed_tasks += 1

                        # Update global counters
                        completed_tasks += 1
                        successful_tasks += 1 if result['success'] else successful_tasks
                        total_questions += result['questions_saved']

                        # Update status with current progress
                        current_combination = result.get('subtopic_names', [])
                        current_type = result.get('combination_type', '')

                        generation_status_tracker.update_status(session_id, {
                            'completed_tasks': completed_tasks,
                            'successful_tasks': successful_tasks,
                            'total_questions': total_questions,
                            'current_combination': current_combination,
                            'current_combination_type': current_type,
                            'current_difficulty': difficulty,
                            'progress_percentage': round((completed_tasks / total_tasks) * 100, 1)
                        })

                    except Exception as e:
                        logger.error(f"❌ Error processing future result: {str(e)}")
                        completed_tasks += 1

            # Log completion of this difficulty
            logger.info(f"✅ DIFFICULTY {difficulty.upper()} COMPLETED:")
            logger.info(f"   └── Processed {len(subtopic_combinations)} combinations")
            logger.info(f"   └── Successful: {difficulty_successful_tasks}/{difficulty_completed_tasks}")
            logger.info(f"   └── Questions generated: {difficulty_questions}")
            logger.info(f"   └── Cumulative total: {total_questions} questions")
            logger.info(f"🎯 DIFFICULTY {difficulty_idx + 1}/{len(difficulty_levels)}: COMPLETED {difficulty.upper()}")
            logger.info(f"")

        # Final status update
        final_status = 'cancelled' if generation_status_tracker.is_session_cancelled(session_id) else 'completed'

        logger.info(f"🎉 ALL DIFFICULTIES PROCESSED!")
        logger.info(f"📊 Final Summary:")
        logger.info(f"   ├── Difficulties processed: {len(difficulty_levels)} ({', '.join(difficulty_levels)})")
        logger.info(f"   ├── Total combinations: {total_tasks}")
        logger.info(f"   ├── Successful tasks: {successful_tasks}/{completed_tasks}")
        logger.info(f"   └── Total questions generated: {total_questions}")

        generation_status_tracker.update_status(session_id, {
            'status': final_status,
            'completed_tasks': completed_tasks,
            'successful_tasks': successful_tasks,
            'total_questions': total_questions,
            'completion_time': time.time(),
            'success_rate': round((successful_tasks / completed_tasks) * 100, 1) if completed_tasks > 0 else 0
        })

        logger.info(f"🏁 Subtopic-specific generation {final_status} for session {session_id}: "
                    f"{successful_tasks}/{completed_tasks} successful tasks, {total_questions} total questions")

    except Exception as e:
        logger.error(f"❌ Critical error in subtopic-specific generation for session {session_id}: {str(e)}")
        generation_status_tracker.update_status(session_id, {
            'status': 'error',
            'error': str(e),
            'completion_time': time.time()
        })
        raise


def get_subtopic_generation_summary(subtopic_ids: List[int],
                                  difficulty_levels: List[str],
                                  num_questions_per_subtopic: int) -> Dict[str, Any]:
    """
    Get a summary of what will be generated for the given parameters.

    Args:
        subtopic_ids: List of subtopic IDs
        difficulty_levels: List of difficulty levels
        num_questions_per_subtopic: Questions per subtopic

    Returns:
        Summary dictionary with generation details
    """
    try:
        Subtopic, _ = get_models()
        
        subtopics = list(Subtopic.objects.filter(id__in=subtopic_ids).select_related('topic__zone'))
        if not subtopics:
            return {'error': 'No subtopics found for the provided IDs'}

        # Group subtopics by zone and topic
        zones = {}
        for subtopic in subtopics:
            zone_name = subtopic.topic.zone.name
            topic_name = subtopic.topic.name

            if zone_name not in zones:
                zones[zone_name] = {}
            if topic_name not in zones[zone_name]:
                zones[zone_name][topic_name] = []

            zones[zone_name][topic_name].append(subtopic.name)

        return {
            'subtopic_count': len(subtopics),
            'difficulty_levels': difficulty_levels,
            'zones_and_topics': zones,
            'generation_scope': {
                'total_subtopics': len(subtopics),
                'difficulty_levels': len(difficulty_levels),
                'questions_per_subtopic': num_questions_per_subtopic
            }
        }

    except Exception as e:
        logger.error(f"Error getting subtopic generation summary: {str(e)}")
        return {'error': str(e)}


def get_worker_details(session_id: str) -> Dict[str, Any]:
    """
    Get detailed worker information for a generation session.

    Args:
        session_id: Session ID to get worker details for

    Returns:
        Dictionary with worker details or error
    """
    try:
        session_status = generation_status_tracker.get_session_status(session_id)

        if not session_status:
            return {'error': 'Session not found'}

        # Handle different session types
        if session_status.get('type') == 'pre_assessment':
            # Pre-assessment doesn't use traditional workers
            return {
                'session_id': session_id,
                'session_type': 'pre_assessment',
                'status': session_status['status'],
                'current_step': session_status.get('step', ''),
                'progress': {
                    'questions_requested': session_status.get('total_questions', 0),
                    'questions_generated': session_status.get('questions_generated', 0),
                    'topics_covered': len(session_status.get('topics', []))
                },
                'message': 'Pre-assessment generation uses a single process, not multiple workers'
            }

        # Handle bulk generation with traditional workers
        workers = session_status.get('workers', {})

        # If no traditional workers (subtopic-specific generation), create synthetic worker info
        if not workers:
            # Create a synthetic worker representation for subtopic-specific generation
            synthetic_worker = {
                'worker_id': 'subtopic_worker_0',
                'status': session_status.get('status', 'unknown'),
                'zone_name': 'Multiple Zones',
                'difficulty': session_status.get('current_difficulty', 'Multiple'),
                'current_step': f"Processing {session_status.get('current_combination', [])}",
                'progress': {
                    'completed_tasks': session_status.get('completed_tasks', 0),
                    'total_tasks': session_status.get('total_tasks', 0),
                    'successful_tasks': session_status.get('successful_tasks', 0),
                    'total_questions': session_status.get('total_questions', 0),
                    'progress_percentage': session_status.get('progress_percentage', 0)
                },
                'start_time': session_status.get('start_time', time.time()),
                'last_activity': session_status.get('last_updated', time.time()),
                'estimated_completion': None,
                'duration': (time.time() - session_status.get('start_time', time.time())) if session_status.get('start_time') else 0
            }

            return {
                'session_id': session_id,
                'session_type': 'subtopic_specific',
                'workers': [synthetic_worker],
                'summary': {
                    'total_workers': 1,
                    'active_workers': 1 if synthetic_worker['status'] == 'processing' else 0,
                    'completed_workers': 1 if synthetic_worker['status'] == 'completed' else 0,
                    'failed_workers': 1 if synthetic_worker['status'] in ['error', 'failed'] else 0,
                    'pending_workers': 0
                }
            }

        # Format traditional worker details for frontend consumption
        worker_details = []
        for worker_id, worker in workers.items():
            worker_detail = {
                'worker_id': worker_id,
                'status': worker['status'],
                'zone_name': worker['zone_name'],
                'difficulty': worker['difficulty'],
                'current_step': worker['current_step'],
                'progress': worker['progress'],
                'start_time': worker['start_time'],
                'last_activity': worker['last_activity'],
                'estimated_completion': worker.get('estimated_completion'),
                'duration': (time.time() - worker['start_time']) if worker['start_time'] else 0
            }
            worker_details.append(worker_detail)

        # Sort by worker_id for consistent ordering
        worker_details.sort(key=lambda x: x['worker_id'])

        return {
            'session_id': session_id,
            'session_type': 'bulk_generation',
            'workers': worker_details,
            'summary': {
                'total_workers': len(worker_details),
                'active_workers': len([w for w in worker_details if w['status'] == 'processing']),
                'completed_workers': len([w for w in worker_details if w['status'] == 'completed']),
                'failed_workers': len([w for w in worker_details if w['status'] in ['error', 'failed']]),
                'pending_workers': len([w for w in worker_details if w['status'] == 'pending'])
            }
        }

    except Exception as e:
        logger.error(f"Error getting worker details for session {session_id}: {str(e)}")
        return {'error': str(e)}