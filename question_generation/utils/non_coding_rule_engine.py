# question_generation/utils/non_coding_rule_engine.py

import re
from typing import List, Tuple


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def _looks_like_flashcard_statement(t: str) -> bool:
    """
    Detect statement-style prompts (common in your dataset) like:
    "A tuple's value is fixed only if..."
    "Generator expressions share..."
    These are recall/definition even without "What is/Define".
    """
    s = (t or "").strip()
    if not s:
        return False

    low = s.lower()

    # already a question
    if "?" in s:
        return False

    # starts like definition statement
    if re.match(r"^(a|an|the|this|these|those)\b", low):
        return True

    # noun phrase + verb style
    if re.match(
        r"^[a-z][a-z\s'/-]{3,60}\b(is|are|can|cannot|will|share|uses|allow|allows|means|refers)\b",
        low,
    ):
        return True

    return False


def _noncoding_score(text: str) -> Tuple[int, List[str], bool, bool]:
    """
    Returns: (score, reasons, has_trace_intent, has_example)
    Cognitive scoring based on intent + reasoning demand (no topic keywords).
    """
    t = (text or "").strip()
    low = t.lower()
    score = 0
    reasons: List[str] = []

    # -------- Intent signals --------
    # Recall/Define (question form)
    if _has(r"\b(define|definition|what is|identify|name|meaning|which of the following|choose)\b", low):
        score += 1
        reasons.append("Intent: recall/define (+1)")

    # Recall/Define (flashcard statement)
    if _looks_like_flashcard_statement(t):
        score += 1
        reasons.append("Intent: flashcard/definition statement (+1)")

    # Explain / Describe
    if _has(r"\b(explain|describe|summarize)\b", low):
        score += 2
        reasons.append("Intent: explain/describe (+2)")

    # Apply / Use
    if _has(r"\b(how do you use|how to|use|apply|write|create|implement)\b", low):
        score += 2
        reasons.append("Intent: apply/use (+2)")

    # Analyze / Compare / Justify
    if _has(r"\b(analyze|compare|contrast|justify|trade[-\s]?off|difference between)\b", low):
        score += 3
        reasons.append("Intent: analyze/compare/justify (+3)")

    # Causal reasoning
    if _has(r"\b(why|how does|what happens if|effect of|reason)\b", low):
        score += 3
        reasons.append("Intent: causal reasoning (+3)")

    # Debug / error reasoning
    if _has(r"\b(debug|fix|error|incorrect|bug)\b", low):
        score += 3
        reasons.append("Intent: debug/error reasoning (+3)")

    # Trace / output / evaluate
    has_trace_intent = _has(r"\b(output|what will be printed|trace|evaluate)\b", low)
    if has_trace_intent:
        score += 3
        reasons.append("Intent: trace/predict/evaluate (+3)")

    # -------- Complexity signals --------
    if _has(r"\b(step|steps|first|then|after|before|next)\b", low):
        score += 1
        reasons.append("Complexity: multi-step phrasing (+1)")

    if _count(r"\b(and|or|but|however)\b", low) >= 2:
        score += 1
        reasons.append("Complexity: multiple clauses (+1)")

    # Example/expression/snippet presence
    has_code_block = _has(r"```", t)
    has_expression = _has(r"[()\[\]{}=+\-*/%<>]", t)
    has_codeish = _has(r"\bfor\b|\bwhile\b|\bif\b|\bdef\b|print\(", t)
    has_example = has_code_block or has_codeish or has_expression

    if has_example:
        score += 1
        reasons.append("Context: contains example/expression (+1)")

    return score, reasons, has_trace_intent, has_example


def _score_to_label(score: int) -> str:
    if score >= 8:
        return "master"
    if score >= 6:
        return "advanced"
    if score >= 4:
        return "intermediate"
    return "beginner"


# ============================================================
# ✅ MAIN API used by ml_classifier.py
# ============================================================

def predict_non_coding_difficulty(text: str) -> str:
    """
    Non-coding difficulty using cognitive scoring (NO ML).
    Hard-minimum rule:
      trace/output/evaluate + example => at least INTERMEDIATE (only raise, never downgrade)
    """
    t = (text or "").strip()
    if not t:
        return "beginner"

    score, reasons, has_trace_intent, has_example = _noncoding_score(t)
    base = _score_to_label(score)

    # hard minimum: trace + example must be at least intermediate
    if has_trace_intent and has_example and base == "beginner":
        return "intermediate"

    return base


def predict_non_coding_difficulty_debug(text: str) -> dict:
    """
    Debug version for non-coding cognitive scoring.
    """
    t = (text or "").strip()
    score, reasons, has_trace_intent, has_example = _noncoding_score(t)
    base = _score_to_label(score)

    final_label = base
    note = "cognitive scoring"

    if has_trace_intent and has_example and base == "beginner":
        final_label = "intermediate"
        note = "hard minimum applied (beginner -> intermediate)"
    elif has_trace_intent and has_example and base != "beginner":
        note = "hard minimum checked (already >= intermediate)"

    return {
        "score": score,
        "base_label": base,
        "final_label": final_label,
        "has_trace_intent": has_trace_intent,
        "has_example": has_example,
        "reasons": reasons,
        "flashcard_statement": _looks_like_flashcard_statement(t),
        "note": note,
    }
