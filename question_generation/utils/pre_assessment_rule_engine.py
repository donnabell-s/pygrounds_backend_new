import re
from dataclasses import dataclass
from typing import List, Tuple, Dict


@dataclass
class FeatureHit:
    name: str
    points: int
    reason: str


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def _extract_code_blocks(text: str) -> str:
    """
    Extract code-ish content to detect tracing/debugging tasks.
    Supports markdown code blocks ```...``` and code-like lines.
    """
    if not text:
        return ""

    # Markdown code blocks
    blocks = re.findall(r"```(?:python)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    code = "\n".join(blocks).strip()

    # If no code blocks, collect lines that look like Python code
    if not code:
        code_like = []
        for line in text.splitlines():
            if re.search(r"\bfor\b|\bwhile\b|\bif\b|\bdef\b|print\s*\(|=\s*|range\s*\(", line):
                code_like.append(line)
        code = "\n".join(code_like).strip()

    return code


def _score_preassessment(text: str) -> Tuple[int, List[FeatureHit]]:
    """
    Cognitive scoring for PRE-ASSESSMENT:
    - Beginner: recall/understand
    - Intermediate: apply/trace
    - Advanced: analyze/debug/multi-step logic

    Returns: (score, hits)
    """
    t = (text or "").strip()
    low = t.lower()
    code = _extract_code_blocks(t)

    score = 0
    hits: List[FeatureHit] = []

    # ----------------------------
    # A) TASK VERBS (Bloom-aligned)
    # ----------------------------
    # Recall / Understand (Beginner-ish)
    if _has(r"\b(define|definition|what is|identify|name)\b", low):
        score += 1
        hits.append(FeatureHit("Recall/Definition task", 1, "Asks for definition/identification."))

    # Apply / Construct (Intermediate-ish)
    if _has(r"\b(write|create|use|convert|compute|calculate|implement)\b", low):
        score += 2
        hits.append(FeatureHit("Apply/Construct task", 2, "Asks to produce or apply a concept."))

    # Analyze / Debug (Advanced-ish)
    if _has(r"\b(debug|fix|correct|error|why|explain why|analyze)\b", low):
        score += 3
        hits.append(FeatureHit("Analyze/Debug task", 3, "Requires analysis/debugging/explanation."))

    # Trace output (usually higher than recall)
    if _has(r"\b(output|what will be printed|what is printed|result of this code|trace)\b", low):
        score += 3
        hits.append(FeatureHit("Tracing/Output prediction", 3, "Requires mental execution/tracing."))

    # ----------------------------
    # B) CODE CONTEXT & STRUCTURE
    # ----------------------------
    if code:
        score += 1
        hits.append(FeatureHit("Contains code", 1, "Learner must interpret code context."))

    # Conditionals
    if _has(r"\bif\b|\belif\b|\belse\b", low) or _has(r"\bif\b|\belif\b|\belse\b", code):
        score += 2
        hits.append(FeatureHit("Conditionals", 2, "Requires conditional reasoning."))

    # Loops
    if _has(r"\bfor\b|\bwhile\b", low) or _has(r"\bfor\b|\bwhile\b", code):
        score += 2
        hits.append(FeatureHit("Loops", 2, "Requires iterative reasoning."))

    # Nesting / multi-branch complexity
    if _has(r"\bnested\b", low) or (_count(r"\bfor\b|\bwhile\b", code) >= 2) or (_count(r"\bif\b", code) >= 2):
        score += 2
        hits.append(FeatureHit("Nesting / multi-branch", 2, "Multiple layers increase cognitive load."))

    # Multiple conditions (and/or)
    if _has(r"\b(and|or)\b", low) or _has(r"\band\b|\bor\b", code):
        score += 1
        hits.append(FeatureHit("Multiple conditions", 1, "Combining conditions increases reasoning demand."))

    # Functions (often intermediate)
    if _has(r"\bdef\b|\bfunction\b", low) or _has(r"\bdef\b", code):
        score += 2
        hits.append(FeatureHit("Functions", 2, "Procedural decomposition required."))

    # Basic data structures (small bump)
    if _has(r"\blist\b|\bdict\b|\btuple\b|\bset\b", low) or _has(r"\[|\{", code):
        score += 1
        hits.append(FeatureHit("Data structures", 1, "Uses collections / structures."))

    # Exception handling (advanced-ish)
    if _has(r"\btry\b|\bexcept\b", low) or _has(r"\btry\b|\bexcept\b", code):
        score += 2
        hits.append(FeatureHit("Exception handling", 2, "Requires error-flow reasoning."))

    return score, hits


def _score_to_level(score: int) -> str:
    """
    Map score to difficulty for PRE-ASSESSMENT only.
    You can tune these thresholds later if needed.
    """
    if score >= 7:
        return "advanced"
    if score >= 4:
        return "intermediate"
    return "beginner"


def pre_assessment_cognitive_engine(text: str) -> str:
    """
    Main pre-assessment difficulty checker (cognitive scoring).
    Returns: beginner | intermediate | advanced
    """
    score, _hits = _score_preassessment(text)
    return _score_to_level(score)


def pre_assessment_cognitive_engine_debug(text: str) -> Dict:
    """
    Optional debug helper (for defense/demo).
    Shows which features fired and the final score.
    """
    score, hits = _score_preassessment(text)
    return {
        "score": score,
        "final": _score_to_level(score),
        "hits": [h.__dict__ for h in hits],
    }
