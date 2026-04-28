CODING_MULTIPLIER = 1.5


def apply_coding_multiplier(mastery_delta: float) -> float:
    """
    Amplifies mastery gain for coding games because P(G) ≈ 0.
    Only called when game_type is a coding game (hangman, debugging).
    Multiplier is 1.5 — a correct coding answer is stronger mastery evidence.
    """
    return mastery_delta * CODING_MULTIPLIER
