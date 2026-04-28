def bkt_update(mastery: float, is_correct: bool, p_slip: float, p_guess: float) -> float:
    """
    Applies BKT posterior update.
    Returns updated mastery probability clamped to [0.05, 0.95].
    mastery is expected in [0, 1].
    """
    if is_correct:
        numerator   = mastery * (1 - p_slip)
        denominator = numerator + (1 - mastery) * p_guess
    else:
        numerator   = mastery * p_slip
        denominator = numerator + (1 - mastery) * (1 - p_guess)

    posterior = numerator / denominator if denominator > 0 else mastery
    return max(0.05, min(0.95, posterior))
