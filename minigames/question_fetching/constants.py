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

# Goldilocks acceptable difficulty bands (filter, not target)
# Format: (low, high) for predicted success probability
GOLDILOCKS_BAND_PRACTICE = (0.65, 0.85)      # practice-heavy games (hangman, debugging)
GOLDILOCKS_BAND_CONCEPTUAL = (0.55, 0.80)    # conceptual/assessment games (crossword, wordsearch)
