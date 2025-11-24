import math
from typing import Optional, Tuple, List
from question_generation.models import PreAssessmentQuestion
from .config import GAME_TYPE_WEIGHTS, DEFAULT_TIME_LIMITS, CODING_MINIGAMES, NONCODING_MINIGAMES

def _game_weight(entry: dict) -> float:
    g = (entry.get("game_type") or "").strip().lower()
    m = (entry.get("minigame_type") or entry.get("game") or "").strip().lower()
    if g in GAME_TYPE_WEIGHTS:
        return GAME_TYPE_WEIGHTS[g]
    if m in CODING_MINIGAMES:
        return GAME_TYPE_WEIGHTS["coding"]
    if m in NONCODING_MINIGAMES:
        return GAME_TYPE_WEIGHTS["non_coding"]
    if m in {"code", "coding"}:
        return GAME_TYPE_WEIGHTS["coding"]
    return GAME_TYPE_WEIGHTS["non_coding"]

def _safe_float(v, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default

def _expected_time(entry: dict) -> float:
    T = _safe_float(entry.get("time_limit"), 0.0)
    if T > 0:
        return T
    m = (entry.get("minigame_type") or entry.get("game_type") or "").strip().lower()
    if m in DEFAULT_TIME_LIMITS:
        return DEFAULT_TIME_LIMITS[m]
    return 300.0

def _observed_time(entry: dict) -> float:
    t = _safe_float(entry.get("minigame_time_taken"), 0.0)
    T = _expected_time(entry)
    return max(0.0, min(t, 2.0 * T))

def _time_multiplier(entry: dict, is_correct: bool) -> float:
    t = _observed_time(entry)
    if t <= 0:
        return 1.0
    T = max(1e-6, _expected_time(entry))
    r = min(2.0, max(0.0, t / T))
    r0 = 0.8
    beta = 2.0
    alpha = 0.20
    signed = 1.0 if is_correct else -1.0
    mult = 1.0 + signed * alpha * math.tanh(beta * (r0 - r))
    return max(0.90, min(1.10, mult))

def _norm_diff(d: Optional[str]) -> str:
    if not d:
        return "intermediate"
    d = str(d).strip().lower()
    if d in {"beginner", "intermediate", "advanced", "master"}:
        return d
    if d.startswith("beg"):
        return "beginner"
    if d.startswith("inter"):
        return "intermediate"
    if d.startswith("adv"):
        return "advanced"
    if d.startswith("mast"):
        return "master"
    return "intermediate"

DIFF_ONEHOT = {
    "beginner": (1, 0, 0, 0),
    "intermediate": (0, 1, 0, 0),
    "advanced": (0, 0, 1, 0),
    "master": (0, 0, 0, 1),
}
DIFF_LEVELS = {"beginner": 0, "intermediate": 1, "advanced": 2, "master": 3}

def _diff_level(d: Optional[str]) -> int:
    return DIFF_LEVELS.get(_norm_diff(d), 1)

def _diff_centered(level: int) -> float:
    return (max(0, min(3, level)) - 1.5) / 1.5

def _impact_with_difficulty(base_impact: float, correct: bool, level: int) -> float:
    c = _diff_centered(level)
    k = 0.20
    scale = (1.0 + k * c) if correct else (1.0 - k * c)
    return max(0.5, min(5.0, base_impact * scale))

def _mistakes_from_entry(entry: dict) -> int:
    for key in ("mistakes", "mistake_count", "num_mistakes", "attempts_before_correct", "attempts"):
        if key in entry and entry[key] is not None:
            try:
                return min(3, max(0, int(entry[key])))
            except (TypeError, ValueError):
                continue
    return 0

def _get_mapping_from_question(entry: dict) -> Tuple[List[int], List[int]]:
    subtopic_ids = entry.get("subtopic_ids") or []
    topic_ids = entry.get("topic_ids") or []
    if subtopic_ids or topic_ids:
        return subtopic_ids, topic_ids
    q_id = entry.get("question_id")
    if not q_id:
        return [], []
    try:
        q = PreAssessmentQuestion.objects.get(id=q_id)
        return getattr(q, "subtopic_ids", []) or [], getattr(q, "topic_ids", []) or []
    except PreAssessmentQuestion.DoesNotExist:
        return [], []
