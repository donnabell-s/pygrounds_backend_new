# adaptive_engine.py
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import math

from django.db.models import Avg
from question_generation.models import PreAssessmentQuestion
from user_learning.models import (
    UserZoneProgress,
    UserTopicProficiency,
    UserSubtopicMastery,
)
from content_ingestion.models import Topic, Subtopic, GameZone


# ──────────────────────────────────────────────────────────────────────────────
# Config: game-type impact weights (coding hits harder)
# ──────────────────────────────────────────────────────────────────────────────
GAME_TYPE_WEIGHTS = {
    "coding": 3.0,       # Debugging, Hangman, etc.
    "non_coding": 1.0,   # Crossword, WordSearch, etc.
}

# Helper: map minigame names to game_type buckets
CODING_MINIGAMES = {"debugging", "hangman"}
NONCODING_MINIGAMES = {"crossword", "wordsearch"}

def _game_weight(entry: dict) -> float:
    """
    Determine impact weight for this attempt.
    Uses entry['game_type'] if present; otherwise maps from ['minigame_type'] or ['game'].
    Falls back to non_coding.
    """
    g = (entry.get("game_type") or "").strip().lower()
    m = (entry.get("minigame_type") or entry.get("game") or "").strip().lower()

    if g in GAME_TYPE_WEIGHTS:
        return GAME_TYPE_WEIGHTS[g]
    if m in CODING_MINIGAMES:
        return GAME_TYPE_WEIGHTS["coding"]
    if m in NONCODING_MINIGAMES:
        return GAME_TYPE_WEIGHTS["non_coding"]
    # Heuristic: if unknown but looks coding-ish
    if m in {"code", "coding"}:
        return GAME_TYPE_WEIGHTS["coding"]
    return GAME_TYPE_WEIGHTS["non_coding"]


# ──────────────────────────────────────────────────────────────────────────────
# Difficulty handling
# ──────────────────────────────────────────────────────────────────────────────
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


# ──────────────────────────────────────────────────────────────────────────────
# BKT core
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class BKTParams:
    p_L0: float = 0.20  # prior knowledge
    p_T:  float = 0.10  # learn after each opportunity
    p_S:  float = 0.10  # slip
    p_G:  float = 0.20  # guess

def bkt_update_once(p_know: float, correct: bool, p: BKTParams) -> float:
    """Single-step BKT update: posterior after observation, then learn."""
    if correct:
        num = p_know * (1.0 - p.p_S)
        den = num + (1.0 - p_know) * p.p_G
    else:
        num = p_know * p.p_S
        den = num + (1.0 - p_know) * (1.0 - p.p_G)
    post = 0.0 if den == 0 else num / den
    return post + (1.0 - post) * p.p_T

def bkt_update_weighted(p_know: float, correct: bool, p: BKTParams, weight: float) -> float:
    """
    Apply a BKT update with an 'impact weight'.
    We approximate by repeating the same observation round(weight) times.
    This is simple, stable, and gives coding items a stronger nudge.
    """
    rounds = max(1, int(round(max(0.1, weight))))
    for _ in range(rounds):
        p_know = bkt_update_once(p_know, correct, p)
    return p_know


# ──────────────────────────────────────────────────────────────────────────────
# PFA-lite core (logistic over wins/fails + difficulty bias)
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class PFACoeffs:
    beta0: float = -0.50     # intercept
    beta_win: float = 0.35   # each prior success
    beta_fail: float = -0.30 # each prior failure
    # difficulty biases (beginner..master)
    b_beg: float = +0.30
    b_int: float = 0.00
    b_adv: float = -0.25
    b_mas: float = -0.45

def pfa_prob(wins: float, fails: float, difficulty: str, c: PFACoeffs) -> float:
    beg, inter, adv, mas = DIFF_ONEHOT[_norm_diff(difficulty)]
    z = (
        c.beta0
        + c.beta_win * wins
        + c.beta_fail * fails
        + c.b_beg * beg
        + c.b_int * inter
        + c.b_adv * adv
        + c.b_mas * mas
    )
    return 1.0 / (1.0 + math.exp(-z))


# ──────────────────────────────────────────────────────────────────────────────
# Blending schedule: move from PFA-heavy to BKT-heavy as attempts grow
# ──────────────────────────────────────────────────────────────────────────────
def blend_alpha(num_attempts: float) -> float:
    """
    0 attempts  -> 0.20  (lean PFA)
    ~10 attempts (weighted) -> 0.80  (lean BKT)
    """
    return max(0.20, min(0.80, 0.20 + 0.06 * num_attempts))

def hybrid_mastery(p_bkt: float, p_pfa: float, n: float) -> float:
    a = blend_alpha(n)
    return a * p_bkt + (1.0 - a) * p_pfa


# ──────────────────────────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────────────────────────
def _mistakes_from_entry(entry: dict) -> int:
    for key in ("mistakes", "mistake_count", "num_mistakes", "attempts_before_correct", "attempts"):
        if key in entry and entry[key] is not None:
            try:
                v = int(entry[key])
                return max(0, v)
            except (TypeError, ValueError):
                continue
    return 0

def _get_mapping_from_question(entry: dict) -> Tuple[List[int], List[int]]:
    """Fallback to PreAssessmentQuestion for topic/subtopic mapping when not provided."""
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


# ──────────────────────────────────────────────────────────────────────────────
# Hybrid recalibration with game-type impact weights
# ──────────────────────────────────────────────────────────────────────────────
def recalibrate_topic_proficiency(user, results: list):
    """
    Hybrid BKT + PFA recalibration with game-type impact weights.
    - Coding attempts are weighted more (default 1.5x) so their evidence and learning impact is larger.
    - Final mastery per subtopic = 100 * hybrid_mastery(last_p_bkt, p_pfa_from_final_counts, weighted_attempts)
    - Topic proficiency = avg(subtopic mastery)
    - Zone completion   = avg(topic proficiency)
    """

    # Per-subtopic state for THIS recalibration batch
    # s_id -> {"wins": float, "fails": float, "attempts": float, "p_bkt": float}
    per_subtopic_state: Dict[int, Dict[str, float]] = {}

    # Seed BKT from existing mastery if available (maps 0-100 -> 0-1)
    existing_mastery: Dict[int, float] = {
        m.subtopic_id: (m.mastery_level or 0.0) / 100.0
        for m in UserSubtopicMastery.objects.filter(user=user).only("subtopic_id", "mastery_level")
    }

    default_bkt = BKTParams()
    default_pfa = PFACoeffs()

    # ── Stream through results and update states
    for entry in results or []:
        is_correct = bool(entry.get("is_correct", False))
        difficulty = _norm_diff(entry.get("estimated_difficulty"))
        mistakes = _mistakes_from_entry(entry)
        weight = float(_game_weight(entry))

        subtopic_ids, _topic_ids = _get_mapping_from_question(entry)
        if not subtopic_ids:
            continue

        # Convert mistakes into extra fails on the PFA side
        extra_fails = max(0, mistakes)

        for s_id in subtopic_ids:
            st = per_subtopic_state.get(s_id)
            if st is None:
                seed = existing_mastery.get(s_id, default_bkt.p_L0)
                st = per_subtopic_state[s_id] = {
                    "wins": 0.0,
                    "fails": 0.0,
                    "attempts": 0.0,
                    "p_bkt": float(seed),
                }

            # 1) BKT update with impact weight (repeat update ~ weight times)
            st["p_bkt"] = bkt_update_weighted(st["p_bkt"], is_correct, default_bkt, weight)

            # 2) PFA counts & attempts weighted
            st["attempts"] += weight
            if is_correct:
                st["wins"] += weight
                # If you prefer not to penalize mistakes when the final answer is correct, comment next line:
                st["fails"] += weight * extra_fails
            else:
                st["fails"] += weight * (1 + extra_fails)

            # (We compute p_pfa at the end from final counts)

    # ── Compute final per-subtopic mastery and write to DB
    for s_id, st in per_subtopic_state.items():
        # Using final counts and a neutral difficulty for PFA probability;
        # you can also average per-item difficulties if you store them.
        p_pfa = pfa_prob(st["wins"], st["fails"], "intermediate", default_pfa)
        p_bkt = float(st["p_bkt"])
        attempts = float(st["attempts"])

        p_mastery = hybrid_mastery(p_bkt, p_pfa, attempts)  # 0..1
        pct = max(0.0, min(100.0, 100.0 * p_mastery))

        subtopic = Subtopic.objects.filter(id=s_id).first()
        if subtopic:
            # Optional EMA smoothing:
            # old0_1 = existing_mastery.get(s_id)  # 0..1
            # if old0_1 is not None:
            #     pct = 0.7 * (old0_1 * 100.0) + 0.3 * pct
            UserSubtopicMastery.objects.update_or_create(
                user=user,
                subtopic=subtopic,
                defaults={"mastery_level": pct},
            )

    # ── Recalculate topic proficiency from subtopics (avg mastery)
    for topic in Topic.objects.all():
        topic_subtopics = Subtopic.objects.filter(topic=topic)
        avg_mastery = (
            UserSubtopicMastery.objects
            .filter(user=user, subtopic__in=topic_subtopics)
            .aggregate(avg=Avg("mastery_level"))["avg"] or 0.0
        )
        UserTopicProficiency.objects.update_or_create(
            user=user,
            topic=topic,
            defaults={"proficiency_percent": avg_mastery},
        )

    # ── Recalculate zone completion from topics (avg proficiency)
    for zone in GameZone.objects.all().order_by("order"):
        zone_topics = Topic.objects.filter(zone=zone)
        avg_proficiency = (
            UserTopicProficiency.objects
            .filter(user=user, topic__in=zone_topics)
            .aggregate(avg=Avg("proficiency_percent"))["avg"] or 0.0
        )
        UserZoneProgress.objects.update_or_create(
            user=user,
            zone=zone,
            defaults={"completion_percent": avg_proficiency},
        )
    # No return
