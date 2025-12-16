# Constants and tunables for question fetching

MIX_WEAK       = 0.75   # <100% or no mastery row
MIX_REVIEW     = 0.15   # near-mastered (>=90%)
MIX_MAINT      = 0.10   # mastered (=100%)

MAINT_PROB_CODING = 0.15

GRID_REGEX = r"[A-Za-z]+"

CODING_MINIGAMES    = {"hangman", "debugging"}
NONCODING_MINIGAMES = {"crossword", "wordsearch"}

DIFF_LOW  = ["beginner", "intermediate"]
DIFF_HIGH = ["advanced", "master"]
DIFF_ALL  = ["beginner", "intermediate", "advanced", "master"]

DIFF_LEVELS = {"beginner": 0, "intermediate": 1, "advanced": 2, "master": 3}

# BWS (Bayesian Weighted Sampling) parameters
EVAL_CANDIDATES_PER_BUCKET = 50  # Candidate pool size for EIG evaluation
SOFTMAX_TEMPERATURE = 0.3  # Controls exploration vs exploitation in sampling
