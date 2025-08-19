# File: user_learning/adaptive_engine.py
from __future__ import annotations
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


# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
GAME_TYPE_WEIGHTS = {
    "coding": 3.0,
    "non_coding": 1.0,
}

DEFAULT_TIME_LIMITS = {
    "debugging": 300.0,
    "hangman": 300.0,
    "crossword": 300.0,
    "wordsearch": 300.0,
}

CODING_MINIGAMES = {"debugging", "hangman"}
NONCODING_MINIGAMES = {"crossword", "wordsearch"}


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
    # Only session-level time is considered
    t = _safe_float(entry.get("minigame_time_taken"), 0.0)
    return max(0.0, t)


def _time_multiplier(entry: dict, is_correct: bool) -> float:
    # Smooth bounded effect; avoids brittle thresholds
    t = _observed_time(entry)
    if t <= 0:
        return 1.0
    T = max(1e-6, _expected_time(entry))

    r = min(2.0, max(0.0, t / T))
    r0 = 0.6
    beta = 2.0
    alpha = 0.25

    signed = 1.0 if is_correct else -1.0
    mult = 1.0 + signed * alpha * math.tanh(beta * (r0 - r))
    return max(0.75, min(1.25, mult))


# -----------------------------------------------------------------------------
# Difficulty helpers
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# BKT with forgetting
# -----------------------------------------------------------------------------
@dataclass
class BKTParams:
    p_L0: float = 0.20
    p_T: float = 0.10
    p_S: float = 0.10
    p_G: float = 0.20
    decay_wrong: float = 0.85
    min_floor: float = 0.001
    max_ceiling: float = 0.999


def bkt_update_once(p_know: float, correct: bool, p: BKTParams) -> float:
    if correct:
        num = p_know * (1.0 - p.p_S)
        den = num + (1.0 - p_know) * p.p_G
    else:
        num = p_know * p.p_S
        den = num + (1.0 - p_know) * (1.0 - p.p_G)
    post = 0.0 if den == 0 else num / den

    p_next = post + (1.0 - post) * p.p_T
    if not correct:
        p_next *= p.decay_wrong

    return max(p.min_floor, min(p.max_ceiling, p_next))


def bkt_update_weighted(p_know: float, correct: bool, p: BKTParams, weight: float) -> float:
    rounds = max(1, int(round(max(0.1, weight))))
    for _ in range(rounds):
        p_know = bkt_update_once(p_know, correct, p)
    return p_know


# -----------------------------------------------------------------------------
# PFA-lite
# -----------------------------------------------------------------------------
@dataclass
class PFACoeffs:
    beta0: float = -1.00
    beta_win: float = 0.35
    beta_fail: float = -0.60
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


# -----------------------------------------------------------------------------
# Blending
# -----------------------------------------------------------------------------

def blend_alpha(num_attempts: float) -> float:
    return max(0.20, min(0.80, 0.20 + 0.06 * num_attempts))


def hybrid_mastery(p_bkt: float, p_pfa: float, n: float) -> float:
    a = blend_alpha(n)
    return a * p_bkt + (1.0 - a) * p_pfa


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

def _mistakes_from_entry(entry: dict) -> int:
    for key in ("mistakes", "mistake_count", "num_mistakes", "attempts_before_correct", "attempts"):
        if key in entry and entry[key] is not None:
            try:
                return max(0, int(entry[key]))
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


# -----------------------------------------------------------------------------
# Recalibration (time-aware via session elapsed only)
# -----------------------------------------------------------------------------

def recalibrate_topic_proficiency(user, results: list):
    """Time effect is session-level only; no model changes required."""
    per_subtopic_state: Dict[int, Dict[str, float]] = {}

    existing_mastery: Dict[int, float] = {
        m.subtopic_id: (m.mastery_level or 0.0) / 100.0
        for m in UserSubtopicMastery.objects.filter(user=user).only("subtopic_id", "mastery_level")
    }

    bkt = BKTParams()
    pfa = PFACoeffs()

    for entry in results or []:
        is_correct = bool(entry.get("is_correct", False))
        difficulty = _norm_diff(entry.get("estimated_difficulty"))
        mistakes = _mistakes_from_entry(entry)
        base_weight = float(_game_weight(entry))
        time_mult = _time_multiplier(entry, is_correct)
        impact = base_weight * time_mult

        subtopic_ids, _topic_ids = _get_mapping_from_question(entry)
        if not subtopic_ids:
            continue

        extra_fails = max(0, mistakes)

        for s_id in subtopic_ids:
            st = per_subtopic_state.get(s_id)
            if st is None:
                seed = existing_mastery.get(s_id, bkt.p_L0)
                st = per_subtopic_state[s_id] = {
                    "wins": 0.0,
                    "fails": 0.0,
                    "attempts": 0.0,
                    "p_bkt": float(seed),
                }

            st["p_bkt"] = bkt_update_weighted(st["p_bkt"], is_correct, bkt, impact)
            st["attempts"] += impact
            if is_correct:
                st["wins"] += impact
                st["fails"] += impact * extra_fails
            else:
                st["fails"] += impact * (1 + extra_fails)

    for s_id, st in per_subtopic_state.items():
        p_pfa = pfa_prob(st["wins"], st["fails"], "intermediate", pfa)
        p_bkt = float(st["p_bkt"])
        attempts = float(st["attempts"])
        p_mastery = hybrid_mastery(p_bkt, p_pfa, attempts)
        pct = max(0.0, min(100.0, 100.0 * p_mastery))

        subtopic = Subtopic.objects.filter(id=s_id).first()
        if subtopic:
            UserSubtopicMastery.objects.update_or_create(
                user=user,
                subtopic=subtopic,
                defaults={"mastery_level": pct},
            )

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
