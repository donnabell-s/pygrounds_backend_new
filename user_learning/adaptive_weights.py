import math
from typing import Dict


def clamp(x: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, x))


def normalize_difficulty(est_diff) -> float:

    if est_diff is None:
        return 0.5
    
    # If already float in [0, 1]
    if isinstance(est_diff, (int, float)):
        if 0.0 <= est_diff <= 1.0:
            return float(est_diff)
        # Assume 1..4 tier system
        if 1 <= est_diff <= 4:
            return (est_diff - 1) / 3.0
        return 0.5
    
    # String tier mapping
    if isinstance(est_diff, str):
        tier_map = {
            "beginner": 0.0,
            "intermediate": 0.33,
            "advanced": 0.67,
            "master": 1.0,
        }
        return tier_map.get(est_diff.lower(), 0.5)
    
    return 0.5


def compute_difficulty_weight(est_diff) -> float:

    d_norm = normalize_difficulty(est_diff)
    return clamp(0.70 + 0.65 * d_norm, 0.70, 1.35)


def compute_time_weight(time_taken: float, entry: dict) -> float:

    if time_taken is None or time_taken <= 0:
        return 1.0
    
    # Determine reference time
    if "expected_time" in entry and entry["expected_time"]:
        t_ref = float(entry["expected_time"])
    else:
        # Default reference times by game type
        game_type = entry.get("game_type", "").lower()
        minigame_type = entry.get("minigame_type", "").lower()
        
        # Practice-heavy games (coding): 45s
        if game_type == "coding" or minigame_type in ("hangman", "debugging"):
            t_ref = 45.0
        # Conceptual games: 30s
        else:
            t_ref = 30.0
    
    ratio = time_taken / t_ref
    # Exponential decay: lambda = 0.8
    # Faster than expected (ratio < 1): significant boost
    # Slower than expected (ratio > 1): steeper penalty
    w_time_raw = math.exp(-0.8 * (ratio - 1.0))
    return clamp(w_time_raw, 0.70, 1.20)


def compute_lives_weight(lives_remaining, max_lives) -> float:

    if lives_remaining is not None and max_lives and max_lives > 0:
        frac = lives_remaining / max_lives
        return clamp(0.70 + 0.65 * frac, 0.70, 1.35)
    return 1.0


def compute_effective_correctness(entry: dict) -> float:

    is_correct = bool(entry.get("is_correct", False))
    
    # If incorrect, no credit regardless of other factors
    if not is_correct:
        return 0.0
    
    # Compute individual weights
    w_diff = compute_difficulty_weight(entry.get("estimated_difficulty"))
    w_time = compute_time_weight(entry.get("minigame_time_taken"), entry)
    w_lives = compute_lives_weight(
        entry.get("lives_remaining"),
        entry.get("max_lives")
    )
    
    # Combine weights
    effective = w_diff * w_time * w_lives
    
    return clamp(effective, 0.0, 1.0)
