# question_generation/utils/pre_assessment_rule_engine.py

import re

"""
PRE-ASSESSMENT RULE ENGINE
--------------------------
This classifier is ONLY for the 30 fixed pre-assessment questions.

Difficulty Levels:
- beginner
- intermediate
- advanced
(pre-assessment should NOT have 'master' level)

The logic focuses on:
- basic syntax               → beginner
- simple numeric operations  → beginner
- basic loops & conditions   → intermediate
- more complex logic/multiple concepts → advanced
"""

# ----------------------------
# KEYWORD GROUPS
# ----------------------------

BEGINNER_KEYWORDS = [
    r"\bprint\b",
    r"\bvariable\b",
    r"\bassign\b",
    r"\bstore\b",
    r"\bstring\b",
    r"\bnumber\b",
    r"\blen\b",
    r"\badd\b",
    r"\bplus\b",
    r"\binput\b",
    r"\bcomment\b",
]

INTERMEDIATE_KEYWORDS = [
    r"\bif\b",
    r"\belif\b",
    r"\belse\b",
    r"\bcomparison\b",
    r"\bgreater\b",
    r"\bless\b",
    r"\bequal\b",
    r"\blist\b",
    r"\brange\b",
    r"\bfor\b",
    r"\bloop\b",
]

ADVANCED_KEYWORDS = [
    r"\bnested\b",
    r"\bmultiple conditions\b",
    r"\blogic\b",
    r"\bboolean\b",
    r"\bcomplex\b",
]


# ----------------------------
# MAIN RULE ENGINE FUNCTION
# ----------------------------

def pre_assessment_rule_engine(text: str):
    """Return difficulty classification for pre-assessment questions."""

    t = text.lower()

    # Check ADVANCED first (rare)
    for kw in ADVANCED_KEYWORDS:
        if re.search(kw, t):
            return "advanced"

    # Check INTERMEDIATE
    for kw in INTERMEDIATE_KEYWORDS:
        if re.search(kw, t):
            return "intermediate"

    # Default if beginner keywords hit
    for kw in BEGINNER_KEYWORDS:
        if re.search(kw, t):
            return "beginner"

    # Fallback — if no keyword matched:
    # pre-assessment questions should be simple by design
    return "beginner"
