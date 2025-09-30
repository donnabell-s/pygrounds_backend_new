"""
Enhanced question generation with smart subtopic combinations.

This module handles:
- Difficulty-based combination generation
- Smart subtopic pairing and grouping
- Question budget distribution
- Parallel worker orchestration
"""

import time
import logging
from itertools import combinations
from typing import List, Dict, Any, Tuple

from .common_utils import (
    validate_positive_integer, 
    validate_string_list, 
    format_duration_human,
    calculate_percentage,
    log_performance,
    extract_object_names
)

from content_ingestion.models import Subtopic
from ..helpers.generation_core import generate_questions_for_subtopic_combination
from ..helpers.generation_status import generation_status_tracker

logger = logging.getLogger(__name__)


# Configuration constants
DIFFICULTY_RULES = {
    'easy': {
        'include_individuals': True,
        'max_same_topic_pairs': 2,
        'max_cross_topic_pairs': 0,
        'include_trios': False,
        'max_trios': 0
    },
    'intermediate': {
        'include_individuals': True,
        'max_same_topic_pairs': 3,
        'max_cross_topic_pairs': 2,
        'include_trios': False,
        'max_trios': 0
    },
    'advanced': {
        'include_individuals': False,
        'max_same_topic_pairs': 4,
        'max_cross_topic_pairs': 3,
        'include_trios': True,
        'include_same_topic_trios': True,
        'include_cross_topic_trios': False,
        'max_trios': 2
    },
    'master': {
        'include_individuals': False,
        'max_same_topic_pairs': 5,
        'max_cross_topic_pairs': 4,
        'include_trios': True,
        'include_same_topic_trios': True,
        'include_cross_topic_trios': True,
        'max_trios': 3
    }
}


def get_difficulty_rules(difficulty: str) -> Dict[str, Any]:
    """Get combination rules for a difficulty level."""
    return DIFFICULTY_RULES.get(difficulty, DIFFICULTY_RULES['intermediate'])


def group_subtopics_by_topic(subtopics: List[Subtopic]) -> Dict[str, List[Subtopic]]:
    """Group subtopics by their topic names."""
    topic_groups = {}
    for subtopic in subtopics:
        topic_name = subtopic.topic.name
        if topic_name not in topic_groups:
            topic_groups[topic_name] = []
        topic_groups[topic_name].append(subtopic)
    return topic_groups


def create_individual_combinations(subtopics: List[Subtopic]) -> List[List[Subtopic]]:
    """Create individual subtopic combinations."""
    return [[subtopic] for subtopic in subtopics]


def create_same_topic_pairs(topic_groups: Dict[str, List[Subtopic]], 
                           max_pairs: int) -> List[List[Subtopic]]:
    """Create pairs from the same topic."""
    pairs = []
    pairs_added = 0
    
    for topic_subtopics in topic_groups.values():
        if len(topic_subtopics) >= 2 and pairs_added < max_pairs:
            topic_pairs = list(combinations(topic_subtopics, 2))
            pairs_to_add = min(len(topic_pairs), max_pairs - pairs_added)
            
            for pair in topic_pairs[:pairs_to_add]:
                pairs.append(list(pair))
                pairs_added += 1
                
                if pairs_added >= max_pairs:
                    break
    
    return pairs


def create_cross_topic_pairs(topic_groups: Dict[str, List[Subtopic]], 
                            max_pairs: int) -> List[List[Subtopic]]:
    """Create pairs from different topics."""
    if len(topic_groups) < 2 or max_pairs == 0:
        return []
    
    # Use first subtopic from each topic as representative
    representatives = [subtopics[0] for subtopics in topic_groups.values()]
    cross_pairs = list(combinations(representatives, 2))
    
    return [list(pair) for pair in cross_pairs[:max_pairs]]


def create_trio_combinations(topic_groups: Dict[str, List[Subtopic]], 
                            rules: Dict[str, Any]) -> List[List[Subtopic]]:
    """Create trio combinations based on rules."""
    trios = []
    max_trios = rules['max_trios']
    
    if not rules['include_trios'] or max_trios == 0:
        return trios
    
    # Same-topic trios
    if rules.get('include_same_topic_trios', False):
        for topic_subtopics in topic_groups.values():
            if len(topic_subtopics) >= 3 and len(trios) < max_trios:
                trio = list(combinations(topic_subtopics, 3))[0]  # Take first trio
                trios.append(list(trio))
    
    # Cross-topic trios
    if rules.get('include_cross_topic_trios', False) and len(topic_groups) >= 3:
        if len(trios) < max_trios:
            representatives = [subtopics[0] for subtopics in topic_groups.values()]
            if len(representatives) >= 3:
                trio = list(combinations(representatives, 3))[0]
                trios.append(list(trio))
    
    return trios[:max_trios]


def create_smart_subtopic_combinations(subtopics: List, max_combinations: int = None, difficulty: str = None) -> List[List]:
    """
    Create smart subtopic combinations for more dynamic question generation.
    Adjusts combination complexity based on difficulty level.
    
    Args:
        subtopics: List of subtopics to combine
        max_combinations: Maximum number of combinations to generate
        difficulty: Difficulty level ('easy', 'intermediate', 'advanced', 'master')
        
    Returns:
        List of subtopic combinations optimized for diversity and difficulty
    """
    # Get difficulty-based combination rules
    difficulty_rules = get_difficulty_rules(difficulty)
    
    all_combinations = []
    
    # 1. Individual subtopics (always include these for easy, optional for higher)
    if difficulty_rules['include_individuals']:
        for subtopic in subtopics:
            all_combinations.append([subtopic])
    
    # 2. Group subtopics by topic
    topic_groups = {}
    for subtopic in subtopics:
        topic_name = subtopic.topic.name
        if topic_name not in topic_groups:
            topic_groups[topic_name] = []
        topic_groups[topic_name].append(subtopic)
    
    # 3. Same-topic pairs (based on difficulty rules)
    same_topic_pairs_added = 0
    max_same_topic_pairs = difficulty_rules['max_same_topic_pairs']
    
    for topic_subtopics in topic_groups.values():
        if len(topic_subtopics) >= 2 and same_topic_pairs_added < max_same_topic_pairs:
            # For higher difficulties, limit pairs per topic
            pairs_from_topic = list(combinations(topic_subtopics, 2))
            pairs_to_add = min(len(pairs_from_topic), max_same_topic_pairs - same_topic_pairs_added)
            
            for pair in pairs_from_topic[:pairs_to_add]:
                all_combinations.append(list(pair))
                same_topic_pairs_added += 1
                
                if same_topic_pairs_added >= max_same_topic_pairs:
                    break
    
    # 4. Cross-topic pairs (based on difficulty rules)
    cross_topic_pairs_added = 0
    max_cross_topic_pairs = difficulty_rules['max_cross_topic_pairs']
    
    if len(topic_groups) > 1 and max_cross_topic_pairs > 0:
        # For intermediate+, create strategic cross-topic pairs
        topic_representatives = []
        for topic_subtopics in topic_groups.values():
            # Take first subtopic from each topic as representative
            topic_representatives.append(topic_subtopics[0])
        
        # Create cross-topic pairs up to the limit
        cross_topic_pair_combinations = list(combinations(topic_representatives, 2))
        pairs_to_add = min(len(cross_topic_pair_combinations), max_cross_topic_pairs)
        
        for pair in cross_topic_pair_combinations[:pairs_to_add]:
            all_combinations.append(list(pair))
            cross_topic_pairs_added += 1
    
    # 5. Strategic trios (advanced+ only)
    if difficulty_rules['include_trios'] and len(subtopics) >= 3:
        trios_added = 0
        max_trios = difficulty_rules['max_trios']
        
        # Add some trios from same topic (for advanced)
        if difficulty_rules['include_same_topic_trios']:
            for topic_subtopics in topic_groups.values():
                if len(topic_subtopics) >= 3 and trios_added < max_trios:
                    trio = list(combinations(topic_subtopics, 3))[0]  # Just one trio per topic
                    all_combinations.append(trio)
                    trios_added += 1
        
        # Add cross-topic trios (for master level)
        if difficulty_rules['include_cross_topic_trios'] and len(topic_groups) >= 3 and trios_added < max_trios:
            topic_representatives = [group[0] for group in topic_groups.values()]
            if len(topic_representatives) >= 3:
                trio = list(combinations(topic_representatives, 3))[0]
                all_combinations.append(trio)
                trios_added += 1
    
    # Remove duplicates while preserving order
    unique_combinations = []
    seen = set()
    for combo in all_combinations:
        combo_key = tuple(sorted([s.id for s in combo]))
        if combo_key not in seen:
            seen.add(combo_key)
            unique_combinations.append(combo)
    
    # Limit combinations if specified
    if max_combinations and len(unique_combinations) > max_combinations:
        # Prioritize: individuals -> same-topic pairs -> cross-topic pairs -> trios
        priority_combinations = []
        
        # Add individuals first
        individuals = [c for c in unique_combinations if len(c) == 1]
        priority_combinations.extend(individuals)
        
        # Add pairs
        pairs = [c for c in unique_combinations if len(c) == 2]
        priority_combinations.extend(pairs[:max_combinations - len(individuals)])
        
        # Add trios if space remains
        if len(priority_combinations) < max_combinations:
            trios = [c for c in unique_combinations if len(c) == 3]
            remaining_space = max_combinations - len(priority_combinations)
            priority_combinations.extend(trios[:remaining_space])
        
        unique_combinations = priority_combinations[:max_combinations]
    
    # Log difficulty-based summary using common utilities
    individuals = len([c for c in unique_combinations if len(c) == 1])
    pairs = len([c for c in unique_combinations if len(c) == 2])
    trios = len([c for c in unique_combinations if len(c) == 3])
    
    difficulty_display = difficulty.upper() if difficulty else "DEFAULT"
    logger.info(f"Created {len(unique_combinations)} {difficulty_display} combinations: {individuals} individuals, {pairs} pairs, {trios} trios")
    
    if logger.isEnabledFor(logging.DEBUG):
        for i, combo in enumerate(unique_combinations):
            combo_names = extract_object_names(combo)
            combo_type = f"{len(combo)}-subtopic" if len(combo) > 1 else "individual"
            logger.debug(f"  {i+1}. {combo_names} ({combo_type})")
    
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
    questions_per_combination = max(1, total_budget_per_difficulty // num_combinations)
    
    logger.debug(f"📊 {difficulty.upper()} distribution: {total_budget_per_difficulty} budget ÷ {num_combinations} combinations = {questions_per_combination} questions per combination")
    
    return questions_per_combination


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
        # Get the specific subtopics
        subtopics = list(Subtopic.objects.filter(id__in=subtopic_ids).select_related('topic__zone'))
        
        if not subtopics:
            raise ValueError("No subtopics found for the provided IDs")
        
        logger.info(f"🚀 Starting subtopic-specific generation for {len(subtopics)} subtopics, {len(difficulty_levels)} difficulties")
        
        # Generate difficulty-specific combinations and calculate question distribution
        all_difficulty_combinations = {}
        all_difficulty_questions_per_combo = {}
        total_tasks = 0
        
        for difficulty in difficulty_levels:
            max_combinations_per_difficulty = 50  # Reasonable limit per difficulty
            difficulty_combinations = create_smart_subtopic_combinations(
                subtopics, 
                max_combinations=max_combinations_per_difficulty,
                difficulty=difficulty
            )
            
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
        
        # Update session status
        generation_status_tracker.update_status(session_id, {
            'status': 'processing',
            'total_tasks': total_tasks,
            'completed_tasks': 0,
            'successful_tasks': 0,
            'total_questions': 0
        })
        
        # Process each difficulty with its specific combinations
        completed_tasks = 0
        successful_tasks = 0
        total_questions = 0
        
        for difficulty in difficulty_levels:
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
                
            for subtopic_combination in subtopic_combinations:
                try:
                    # Check for cancellation before each combination
                    if generation_status_tracker.is_session_cancelled(session_id):
                        logger.info(f"📝 Session {session_id} cancelled during combination processing")
                        break
                        
                    subtopic_names = [sub.name for sub in subtopic_combination]
                    combination_type = "individual" if len(subtopic_combination) == 1 else f"{len(subtopic_combination)}-subtopic combo"
                    
                    logger.debug(f"🎯 Worker Goal: Generate {questions_per_combo} {difficulty} {game_type} questions")
                    logger.debug(f"   └── Combination: {subtopic_names} ({combination_type})")
                    logger.debug(f"   └── Expected output: {questions_per_combo} questions with explanations")
                    
                    result = generate_questions_for_subtopic_combination(
                        subtopic_combination=subtopic_combination,
                        difficulty=difficulty,
                        num_questions=questions_per_combo,
                        game_type=game_type,
                        zone=subtopic_combination[0].topic.zone,  # Use the zone from first subtopic
                        session_id=session_id
                    )
                    
                    if result['success']:
                        successful_tasks += 1
                        questions_saved = result.get('questions_saved', 0)
                        total_questions += questions_saved
                        logger.info(f"✅ Generated {questions_saved} questions for {combination_type}: {subtopic_names} - {difficulty}")
                    else:
                        logger.warning(f"❌ Failed to generate questions for {combination_type}: {subtopic_names} - {difficulty}: {result.get('error', 'Unknown error')}")
                    
                    completed_tasks += 1
                    
                    # Update status with progress
                    generation_status_tracker.update_status(session_id, {
                        'completed_tasks': completed_tasks,
                        'successful_tasks': successful_tasks,
                        'total_questions': total_questions,
                        'current_combination': subtopic_names,
                        'current_combination_type': combination_type,
                        'current_difficulty': difficulty,
                        'progress_percentage': round((completed_tasks / total_tasks) * 100, 1)
                    })
                    
                except Exception as e:
                    logger.error(f"❌ Error processing subtopic combination {[sub.name for sub in subtopic_combination]} - {difficulty}: {str(e)}")
                    completed_tasks += 1
                    
                    # Update status even on error
                    generation_status_tracker.update_status(session_id, {
                        'completed_tasks': completed_tasks,
                        'failed_combinations': generation_status_tracker.get_session_status(session_id).get('failed_combinations', 0) + 1
                    })
        
        # Final status update
        final_status = 'cancelled' if generation_status_tracker.is_session_cancelled(session_id) else 'completed'
        
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


def get_worker_details_data(session_id: str) -> Dict[str, Any]:
    """
    Get detailed worker information for a generation session.
    
    Args:
        session_id: Session ID to get worker details for
        
    Returns:
        Dictionary with worker details and summary
    """
    try:
        from ..helpers.generation_status import generation_status_tracker
        
        session_status = generation_status_tracker.get_session_status(session_id)
        
        if not session_status:
            return {'error': 'Session not found'}
        
        # Format worker details for frontend consumption
        worker_details = []
        workers = session_status.get('workers', {})
        
        for worker_id, worker in workers.items():
            worker_detail = {
                'worker_id': worker_id,
                'status': worker.get('status', 'unknown'),
                'zone_name': worker.get('zone_name', 'Unknown'),
                'difficulty': worker.get('difficulty', 'Unknown'),
                'current_step': worker.get('current_step', 'Unknown'),
                'progress': worker.get('progress', {}),
                'start_time': worker.get('start_time', 0),
                'last_activity': worker.get('last_activity', 0),
                'estimated_completion': worker.get('estimated_completion'),
                'duration': (time.time() - worker.get('start_time', 0)) if worker.get('start_time') else 0
            }
            worker_details.append(worker_detail)
        
        # Sort by worker_id for consistent ordering
        worker_details.sort(key=lambda x: x['worker_id'])
        
        return {
            'session_id': session_id,
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
        return {'error': f'Failed to get worker details: {str(e)}'}


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