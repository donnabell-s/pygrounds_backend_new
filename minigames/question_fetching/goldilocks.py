# Goldilocks filter-based question selection with constrained random tie-breaking
import random
from typing import List, Dict, Tuple
from django.db.models import QuerySet
from question_generation.models import GeneratedQuestion
from user_learning.models import UserAbility
from .constants import GOLDILOCKS_BAND_PRACTICE, GOLDILOCKS_BAND_CONCEPTUAL, CODING_MINIGAMES


def get_user_ability(user) -> float:
    """
    Load user ability score from database.
    
    Returns:
        Ability score (0-1), defaults to 0.5 if not found
    """
    try:
        ability = UserAbility.objects.get(user=user)
        score = float(ability.ability_score)
        return max(0.0, min(1.0, score))
    except UserAbility.DoesNotExist:
        return 0.5


def get_subtopic_prior_map(user, mastery_map: Dict[int, float]) -> Dict[int, float]:
    """
    Compute personalized prior for each subtopic.
    
    Formula (paper-aligned):
      K_s = mastery_level(s) / 100  (convert to 0-1)
      A = ability_score
      prior_s = 0.7*K_s + 0.3*A
    
    Args:
        user: User object
        mastery_map: Dict mapping subtopic_id -> mastery_level (0-100)
    
    Returns:
        Dict mapping subtopic_id -> prior_s (0-1)
    """
    ability_score = get_user_ability(user)
    
    prior_map = {}
    for subtopic_id, mastery_level in mastery_map.items():
        K_s = mastery_level / 100.0
        K_s = max(0.0, min(1.0, K_s))
        prior_s = 0.7 * K_s + 0.3 * ability_score
        prior_map[subtopic_id] = max(0.0, min(1.0, prior_s))
    
    return prior_map


def get_goldilocks_band(game_type: str) -> Tuple[float, float]:
    """
    Return acceptable difficulty band (low, high) based on game type.
    
    - Practice-heavy games (coding): [0.65, 0.85]
    - Conceptual/assessment games (non-coding): [0.55, 0.80]
    
    Args:
        game_type: Type of game (coding/non_coding)
    
    Returns:
        Tuple of (band_low, band_high)
    """
    if game_type.lower() in CODING_MINIGAMES:
        return GOLDILOCKS_BAND_PRACTICE
    return GOLDILOCKS_BAND_CONCEPTUAL


def pick_constrained_random(
    question_list: List[GeneratedQuestion],
    band_low: float,
    band_high: float,
    prior_map: Dict[int, float],
    k: int,
    exclude_ids: set = None
) -> List[int]:
    """
    Apply Goldilocks filter and randomly sample from acceptable candidates.
    
    Process:
    1. Filter questions where predicted_success is within [band_low, band_high]
    2. If filtered list is non-empty: randomly sample k questions
    3. Else fallback: randomly sample k questions from all candidates
    
    Args:
        question_list: List of GeneratedQuestion objects
        band_low: Lower bound of acceptable difficulty
        band_high: Upper bound of acceptable difficulty
        prior_map: Dict mapping subtopic_id -> prior_s (predicted success)
        k: Number of questions to select
        exclude_ids: Set of question IDs to exclude
    
    Returns:
        List of selected question IDs
    """
    if not question_list or k <= 0:
        return []
    
    exclude_ids = exclude_ids or set()
    
    # Filter out excluded questions
    candidates = [q for q in question_list if q.id not in exclude_ids]
    if not candidates:
        return []
    
    # Apply Goldilocks band filter
    filtered = []
    for q in candidates:
        sid = getattr(q, 'subtopic_id', None)
        if sid is None:
            continue
        
        predicted_success = prior_map.get(sid, 0.5)
        if band_low <= predicted_success <= band_high:
            filtered.append(q)
    
    # Use filtered list if non-empty, otherwise fallback to all candidates
    pool = filtered if filtered else candidates
    
    # Randomly sample k questions
    sample_size = min(k, len(pool))
    selected = random.sample(pool, sample_size)
    
    return [q.id for q in selected]


def pick_questions_by_subtopic(
    user,
    qs: QuerySet,
    take: int,
    mastery_by_sub: Dict[int, float],
    game_type: str,
    exclude_ids: set = None
) -> List[int]:
    """
    Select questions using Goldilocks filter + constrained random selection.
    
    This is the main entry point for question selection. It:
    1. Loads user ability and computes subtopic priors
    2. Gets the Goldilocks acceptable difficulty band
    3. Fetches candidate questions from QuerySet
    4. Applies filter and randomly samples from acceptable candidates
    
    Args:
        user: User object
        qs: QuerySet of candidate questions
        take: Number of questions to select
        mastery_by_sub: Dict mapping subtopic_id -> mastery_level (0-100)
        game_type: Type of game (coding/non_coding)
        exclude_ids: Set of question IDs to exclude
    
    Returns:
        List of selected question IDs
    """
    if take <= 0:
        return []
    
    exclude_ids = exclude_ids or set()
    
    # Compute personalized priors for all subtopics
    prior_map = get_subtopic_prior_map(user, mastery_by_sub)
    
    # Get acceptable difficulty band
    band_low, band_high = get_goldilocks_band(game_type)
    
    # Fetch candidate questions (limit sample size for efficiency)
    count = qs.count()
    if count == 0:
        return []
    
    # Sample more candidates than needed to ensure good coverage after filtering
    sample_size = min(count, take * 10)
    candidate_ids = list(qs.values_list('id', flat=True)[:sample_size])
    
    if not candidate_ids:
        return []
    
    # Fetch full question objects
    questions = list(GeneratedQuestion.objects.filter(id__in=candidate_ids).select_related('subtopic'))
    
    # Apply Goldilocks filter and random selection
    selected_ids = pick_constrained_random(
        questions,
        band_low,
        band_high,
        prior_map,
        take,
        exclude_ids
    )
    
    return selected_ids
