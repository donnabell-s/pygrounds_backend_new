# Bayesian Weighted Sampling (BWS) for question selection using EIG

import random
import math
from typing import List, Dict
from django.db.models import QuerySet
from question_generation.models import GeneratedQuestion
from user_learning.models import UserAbility
from .eig_bkt import compute_eig_scores
from .helpers import sample_random_by_offsets
from .constants import CODING_MINIGAMES


# BWS sampling parameters
EVAL_CANDIDATES_PER_BUCKET = 50  # Sample size for EIG evaluation
SOFTMAX_TEMPERATURE = 0.3  # Controls exploration vs exploitation


def normalize_difficulty_to_01(est_diff) -> float:
    """
    Normalize difficulty to [0, 1] range for EIG computation.
    """
    if est_diff is None:
        return 0.5
    
    if isinstance(est_diff, (int, float)):
        if 0.0 <= est_diff <= 1.0:
            return float(est_diff)
        if 1 <= est_diff <= 4:
            return (est_diff - 1) / 3.0
        return 0.5
    
    if isinstance(est_diff, str):
        tier_map = {
            "beginner": 0.0,
            "intermediate": 0.33,
            "advanced": 0.67,
            "master": 1.0,
        }
        return tier_map.get(est_diff.lower(), 0.5)
    
    return 0.5


def bws_pick_ids_by_eig(
    user,
    qs: QuerySet,
    take: int,
    mastery_by_sub: Dict[int, float],
    constrain_subtopics: bool = True
) -> List[int]:
    """
    Select question IDs using Expected Information Gain (EIG) + Bayesian Weighted Sampling.
    
    Process:
    1. Load user ability
    2. Sample candidate pool from QuerySet
    3. Compute EIG scores for all candidates
    4. Apply softmax to EIG scores to get sampling probabilities
    5. Sample questions using weighted probabilities
    6. Optional: Enforce subtopic diversity (max 1 per subtopic when possible)
    
    Args:
        user: User object
        qs: QuerySet of candidate questions
        take: Number of questions to select
        mastery_by_sub: Dict mapping subtopic_id -> mastery_level (0-100)
        constrain_subtopics: If True, limit to 1 question per subtopic when possible
    
    Returns:
        List of selected question IDs
    """
    if take <= 0:
        return []
    
    count = qs.count()
    if count == 0:
        return []
    
    # Load user ability
    try:
        ability_obj = UserAbility.objects.get(user=user)
        ability_score = float(ability_obj.ability_score)
        ability_score = max(0.0, min(1.0, ability_score))
    except UserAbility.DoesNotExist:
        ability_score = 0.5
    
    # Sample candidate pool (more than needed for better coverage)
    sample_size = min(count, max(take * 10, EVAL_CANDIDATES_PER_BUCKET))
    cand_ids = list(qs.values_list('id', flat=True)[:sample_size])
    
    if not cand_ids:
        return []
    
    # Fetch question details
    questions = list(GeneratedQuestion.objects.filter(id__in=cand_ids).select_related('subtopic'))
    
    # Build maps for EIG computation
    question_subtopic_map = {}
    question_difficulty_map = {}
    
    for q in questions:
        if not hasattr(q, 'subtopic_id') or q.subtopic_id is None:
            continue
        question_subtopic_map[q.id] = q.subtopic_id
        
        # Normalize difficulty
        est_diff = getattr(q, 'estimated_difficulty', None)
        question_difficulty_map[q.id] = normalize_difficulty_to_01(est_diff)
    
    if not question_subtopic_map:
        # Fallback to random if no valid candidates
        return random.sample(cand_ids, min(take, len(cand_ids)))
    
    # Compute EIG scores
    eig_scores = compute_eig_scores(
        ability_score,
        mastery_by_sub,
        question_subtopic_map,
        question_difficulty_map
    )
    
    if not eig_scores:
        return random.sample(cand_ids, min(take, len(cand_ids)))
    
    # Apply softmax to get sampling probabilities
    valid_ids = list(eig_scores.keys())
    eig_values = [eig_scores[qid] for qid in valid_ids]
    
    # Softmax with temperature
    max_eig = max(eig_values) if eig_values else 0.0
    exp_values = [math.exp((eig - max_eig) / SOFTMAX_TEMPERATURE) for eig in eig_values]
    sum_exp = sum(exp_values)
    
    if sum_exp == 0:
        probabilities = [1.0 / len(exp_values)] * len(exp_values)
    else:
        probabilities = [e / sum_exp for e in exp_values]
    
    # Sample questions using weighted probabilities
    selected_ids = []
    picked_subtopics = set()
    remaining_pool = list(zip(valid_ids, probabilities))
    
    for _ in range(take):
        if not remaining_pool:
            break
        
        # Filter by subtopic diversity if enabled
        if constrain_subtopics and picked_subtopics:
            # Try to pick from unpicked subtopics first
            available = [(qid, prob) for qid, prob in remaining_pool 
                        if question_subtopic_map.get(qid) not in picked_subtopics]
            
            if available:
                pool_to_use = available
            else:
                # All subtopics picked, allow repeats
                pool_to_use = remaining_pool
        else:
            pool_to_use = remaining_pool
        
        # Normalize probabilities for current pool
        pool_ids, pool_probs = zip(*pool_to_use)
        prob_sum = sum(pool_probs)
        if prob_sum > 0:
            normalized_probs = [p / prob_sum for p in pool_probs]
        else:
            normalized_probs = [1.0 / len(pool_probs)] * len(pool_probs)
        
        # Sample one question
        chosen_id = random.choices(pool_ids, weights=normalized_probs, k=1)[0]
        selected_ids.append(chosen_id)
        
        # Track picked subtopic
        if constrain_subtopics:
            subtopic_id = question_subtopic_map.get(chosen_id)
            if subtopic_id:
                picked_subtopics.add(subtopic_id)
        
        # Remove chosen question from pool
        remaining_pool = [(qid, prob) for qid, prob in remaining_pool if qid != chosen_id]
    
    return selected_ids
