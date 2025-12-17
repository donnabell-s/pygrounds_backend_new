import random
import math
from typing import List, Dict
from django.db.models import QuerySet
from question_generation.models import GeneratedQuestion
from user_learning.models import UserAbility
from .eig_bkt import compute_eig_scores
from .helpers import sample_random_by_offsets
from .constants import CODING_MINIGAMES, EVAL_CANDIDATES_PER_BUCKET, SOFTMAX_TEMPERATURE


def normalize_difficulty_to_01(est_diff) -> float:

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

    if take <= 0:
        return []
    
    count = qs.count()
    if count == 0:
        return []
    
    try:
        ability_obj = UserAbility.objects.get(user=user)
        ability_score = float(ability_obj.ability_score)
        ability_score = max(0.0, min(1.0, ability_score))
    except UserAbility.DoesNotExist:
        ability_score = 0.5
    
    sample_size = min(count, max(take * 10, EVAL_CANDIDATES_PER_BUCKET))

    cand_ids = sample_random_by_offsets(qs.only('id'), sample_size)
    
    if not cand_ids:
        return []
    
    questions = list(GeneratedQuestion.objects.filter(id__in=cand_ids).select_related('subtopic'))
    
    question_subtopic_map = {}
    question_difficulty_map = {}
    
    for q in questions:
        if not hasattr(q, 'subtopic_id') or q.subtopic_id is None:
            continue
        question_subtopic_map[q.id] = q.subtopic_id
        
        est_diff = getattr(q, 'estimated_difficulty', None)
        question_difficulty_map[q.id] = normalize_difficulty_to_01(est_diff)
    
    if not question_subtopic_map:
        return random.sample(cand_ids, min(take, len(cand_ids)))
    
    #if question pool lacks diverse subtopics, resample
    unique_subtopics = len(set(question_subtopic_map.values()))
    min_diversity = min(6, take * 3)
    if unique_subtopics < min_diversity and count > sample_size:

        larger_sample_size = min(count, sample_size * 2)
        cand_ids = sample_random_by_offsets(qs.only('id'), larger_sample_size)
        
        if cand_ids:
            questions = list(GeneratedQuestion.objects.filter(id__in=cand_ids).select_related('subtopic'))
            question_subtopic_map = {}
            question_difficulty_map = {}
            
            for q in questions:
                if not hasattr(q, 'subtopic_id') or q.subtopic_id is None:
                    continue
                question_subtopic_map[q.id] = q.subtopic_id
                est_diff = getattr(q, 'estimated_difficulty', None)
                question_difficulty_map[q.id] = normalize_difficulty_to_01(est_diff)
            
            if not question_subtopic_map:
                return random.sample(cand_ids, min(take, len(cand_ids)))
    
    eig_scores = compute_eig_scores(
        ability_score,
        mastery_by_sub,
        question_subtopic_map,
        question_difficulty_map
    )
    
    if not eig_scores:
        return random.sample(cand_ids, min(take, len(cand_ids)))
    
    #apply softmax
    valid_ids = list(eig_scores.keys())
    eig_values = [eig_scores[qid] for qid in valid_ids]
    
    #softmax with temp
    max_eig = max(eig_values) if eig_values else 0.0
    exp_values = [math.exp((eig - max_eig) / SOFTMAX_TEMPERATURE) for eig in eig_values]
    sum_exp = sum(exp_values)
    
    if sum_exp == 0:
        probabilities = [1.0 / len(exp_values)] * len(exp_values)
    else:
        probabilities = [e / sum_exp for e in exp_values]
    
    #sample q with weighted probabilities
    selected_ids = []
    picked_subtopics = set()
    remaining_pool = list(zip(valid_ids, probabilities))
    
    for _ in range(take):
        if not remaining_pool:
            break
        

        if constrain_subtopics and picked_subtopics:
            available = [(qid, prob) for qid, prob in remaining_pool 
                        if question_subtopic_map.get(qid) not in picked_subtopics]
            
            if available:
                pool_to_use = available
            else:
                pool_to_use = remaining_pool
        else:
            pool_to_use = remaining_pool
        
        #normalize probability
        pool_ids, pool_probs = zip(*pool_to_use)
        prob_sum = sum(pool_probs)
        if prob_sum > 0:
            normalized_probs = [p / prob_sum for p in pool_probs]
        else:
            normalized_probs = [1.0 / len(pool_probs)] * len(pool_probs)
        
        chosen_id = random.choices(pool_ids, weights=normalized_probs, k=1)[0]
        selected_ids.append(chosen_id)
        
        if constrain_subtopics:
            subtopic_id = question_subtopic_map.get(chosen_id)
            if subtopic_id:
                picked_subtopics.add(subtopic_id)
        
        #remove q from pool
        remaining_pool = [(qid, prob) for qid, prob in remaining_pool if qid != chosen_id]
    
    return selected_ids
