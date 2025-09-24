# File: user_learning/adaptive_engine.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import math

from django.db import transaction
from django.db.models import Avg
from question_generation.models import PreAssessmentQuestion
from user_learning.models import (
    UserZoneProgress,
    UserTopicProficiency,
    UserSubtopicMastery,
    # add this model via the snippet below
    UserSubtopicLearningRate,
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


# ---- New: fractional-impact update (smooth) ---------------------------------
def bkt_update_fractional(p_know: float, correct: bool, p: BKTParams, impact: float) -> float:
    """
    Apply BKT update 'impact' times, allowing fractional impact via a softened final pass.
    Keeps semantics of repeated updates but avoids integer rounding artifacts.
    """
    import math as _math

    # integer passes
    rounds = int(max(0, _math.floor(impact)))
    for _ in range(rounds):
        p_know = bkt_update_once(p_know, correct, p)

    # leftover fraction
    frac = max(0.0, impact - rounds)
    if frac > 1e-6:
        # soften learning + forgetting proportionally to frac
        p_soft = BKTParams(
            p_L0=p.p_L0,
            p_T=max(1e-6, min(0.95, p.p_T * frac)),          # scale learning by fraction
            p_S=p.p_S,
            p_G=p.p_G,
            decay_wrong=1.0 - (1.0 - p.decay_wrong) * frac,  # interpolate toward 1.0
            min_floor=p.min_floor,
            max_ceiling=p.max_ceiling,
        )
        p_know = bkt_update_once(p_know, correct, p_soft)

    return p_know


# -----------------------------------------------------------------------------
# PFA-lite (used only for seeding/tuning, not blended to final)
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
# Individualization helpers (PFA -> BKT seeding/tuning) + EMA persistence
# -----------------------------------------------------------------------------
def _pfa_seed_prior_or_default(
    existing_mastery_pct: Optional[float],
    wins: float,
    fails: float,
    difficulty: str,
    pfa: PFACoeffs,
    base_prior: float,
) -> float:
    """
    Choose an initial p(L0) for BKT:
      1) If we already have an existing mastery percent for this subtopic, use it (scaled 0..1).
      2) Else, if there is any practice signal in this batch (wins/fails), use PFA as a prior.
      3) Else, fall back to the base prior.
    """
    if existing_mastery_pct is not None:
        return max(0.0, min(1.0, float(existing_mastery_pct) / 100.0))
    if (wins + fails) > 0.0:
        return pfa_prob(wins, fails, difficulty, pfa)
    return float(base_prior)


def _lr_mult_from_practice(wins: float, fails: float) -> float:
    """
    Bounded per-learner learning-rate multiplier in [0.5, 1.5] from practice balance.
    - perf in [-1..+1] where +1 means all wins, -1 all fails.
    """
    n = max(1.0, wins + fails)
    perf = (wins - fails) / n  # [-1..+1]
    alpha = 0.5  # scale
    m = 1.0 + alpha * perf     # [0.5..1.5]
    return max(0.5, min(1.5, m))


def _ema_update(old: float, new: float, alpha: float) -> float:
    # classic EMA: newer value has weight alpha
    return (1.0 - alpha) * old + alpha * new


def _load_pT_scale(user, subtopic_obj: Subtopic, default=1.0) -> float:
    rec = UserSubtopicLearningRate.objects.filter(user=user, subtopic=subtopic_obj).only('pT_scale').first()
    return float(rec.pT_scale) if rec else float(default)


@transaction.atomic
def _save_pT_scale(user, subtopic_obj: Subtopic, new_scale: float, alpha: float = 0.2):
    rec, _ = UserSubtopicLearningRate.objects.select_for_update().get_or_create(
        user=user, subtopic=subtopic_obj, defaults={'pT_scale': 1.0, 'count': 0}
    )
    # bound and EMA
    new_scale = max(0.5, min(1.5, new_scale))
    if rec.count == 0:
        rec.pT_scale = new_scale
        rec.count = 1
    else:
        rec.pT_scale = _ema_update(rec.pT_scale, new_scale, alpha)
        rec.count += 1
    rec.save()


# -----------------------------------------------------------------------------
# Recalibration (Individualized BKT core, time-aware)
# -----------------------------------------------------------------------------
def recalibrate_topic_proficiency(user, results: list):
    """
    Individualized-BKT core:
      - PFA-like signals seed p(L0) and modulate p(T) per student.
      - Final mastery is BKT-only (no blending with PFA output).
      - Time/game weights remain in effect (session-level time multiplier).
      - Persist per-user×subtopic learning rate with EMA for stability across sessions.
    """
    per_subtopic_state: Dict[int, Dict[str, object]] = {}

    # Load existing mastery (used to seed priors when available)
    existing_mastery: Dict[int, float] = {
        m.subtopic_id: (m.mastery_level or 0.0)  # store as 0..100
        for m in UserSubtopicMastery.objects.filter(user=user).only("subtopic_id", "mastery_level")
    }

    base_bkt = BKTParams()   # global baselines
    pfa = PFACoeffs()        # used only for seeding/tuning, not for final blending

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
                subtopic_obj = Subtopic.objects.filter(id=s_id).first()
                if not subtopic_obj:
                    continue
                # Build the state once per subtopic for this batch
                st = per_subtopic_state[s_id] = {
                    "wins": 0.0,
                    "fails": 0.0,
                    "attempts": 0.0,
                    "p_bkt": None,            # initialized after we have (wins/fails) seed
                    "p_L0_seeded": False,     # whether we've seeded p(L0) explicitly
                    "subtopic_obj": subtopic_obj,
                    # persisted long-term scale loaded once per batch
                    "pT_scale_persisted": _load_pT_scale(user, subtopic_obj),
                }

            # Update PFA-like counters first (so seeding/tuning can see prior practice)
            st["attempts"] = float(st["attempts"]) + impact
            if is_correct:
                st["wins"] = float(st["wins"]) + impact
                st["fails"] = float(st["fails"]) + impact * extra_fails
            else:
                st["fails"] = float(st["fails"]) + impact * (1 + extra_fails)

            # Seed p(L0) once: prefer existing mastery, else PFA signal, else base prior
            if not st["p_L0_seeded"]:
                seeded = _pfa_seed_prior_or_default(
                    existing_mastery_pct=existing_mastery.get(s_id),
                    wins=float(st["wins"]),
                    fails=float(st["fails"]),
                    difficulty=difficulty,
                    pfa=pfa,
                    base_prior=base_bkt.p_L0,
                )
                st["p_bkt"] = float(seeded)
                st["p_L0_seeded"] = True

            # Build individualized BKT params for this learner & subtopic step
            # - combine persisted pT scale with within-batch multiplier (geometric mean)
            lr_mult_batch = _lr_mult_from_practice(float(st["wins"]), float(st["fails"]))
            lr_mult_persisted = max(0.5, min(1.5, float(st["pT_scale_persisted"])))
            lr_mult_combined = math.sqrt(lr_mult_persisted * lr_mult_batch)

            p_step = BKTParams(
                p_L0=float(st["p_bkt"]),   # doc only; running value used below
                p_T=max(1e-4, min(0.95, base_bkt.p_T * lr_mult_combined)),
                p_S=base_bkt.p_S,
                p_G=base_bkt.p_G,
                decay_wrong=base_bkt.decay_wrong,
                min_floor=base_bkt.min_floor,
                max_ceiling=base_bkt.max_ceiling,
            )

            # Smooth BKT update (fractional impact)
            st["p_bkt"] = bkt_update_fractional(float(st["p_bkt"]), is_correct, p_step, impact)

    # Persist subtopic masteries (BKT only) + update EMA of pT_scale
    for s_id, st in per_subtopic_state.items():
        p_mastery = float(st["p_bkt"]) if st["p_bkt"] is not None else base_bkt.p_L0
        pct = max(0.0, min(100.0, 100.0 * p_mastery))

        subtopic_obj: Subtopic = st["subtopic_obj"]  # already fetched
        # session-level recommended scale from observed batch
        session_scale = _lr_mult_from_practice(float(st["wins"]), float(st["fails"]))
        combined = math.sqrt(max(0.5, min(1.5, float(st["pT_scale_persisted"]))) * session_scale)
        _save_pT_scale(user, subtopic_obj, combined, alpha=0.2)

        UserSubtopicMastery.objects.update_or_create(
            user=user,
            subtopic=subtopic_obj,
            defaults={"mastery_level": pct},
        )

    # Roll up to topics
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

    # Roll up to zones
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
