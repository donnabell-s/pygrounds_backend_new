# Configuration and constants for adaptive engine

GAME_TYPE_WEIGHTS = {
    "coding": 2.0,
    "non_coding": 1.0,
}

DEFAULT_TIME_LIMITS = {
    "debugging": 300.0,
    "hangman": 300.0,
    "crossword": 300.0,
    "wordsearch": 300.0,
}

MASTERY_BANDS = {
    "weak_max": 0.90,
    "review_min": 0.90,
    "master_min": 0.99,
}

MASTERY_THRESHOLD = 0.95
CONVERGENCE_EPS = 0.01
CONVERGENCE_K = 3

CODING_MINIGAMES = {"debugging", "hangman"}
NONCODING_MINIGAMES = {"crossword", "wordsearch"}
