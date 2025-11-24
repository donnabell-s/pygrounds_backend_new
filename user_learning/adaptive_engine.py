import math
from typing import Dict, List
from .bkt_models import BKTParams, PFACoeffs, bkt_update_once, bkt_update_fractional, pfa_prob, _observe_params_with_difficulty
from .utils import _mistakes_from_entry, _get_mapping_from_question, _norm_diff, _diff_level, _impact_with_difficulty, _game_weight, _time_multiplier
from .config import MASTERY_BANDS, MASTERY_THRESHOLD, CONVERGENCE_EPS, CONVERGENCE_K
from .persistence import _ema_update, _load_pT_scale, _save_pT_scale, _pfa_seed_prior_or_default, _lr_mult_from_practice
from django.db import transaction
from django.db.models import Avg
from user_learning.models import UserZoneProgress, UserTopicProficiency, UserSubtopicMastery, UserSubtopicLearningRate
from content_ingestion.models import Topic, Subtopic, GameZone

def _band_of(p: float) -> str:
    if p >= MASTERY_BANDS["master_min"]:
        return "mastered"
    if p >= MASTERY_BANDS["review_min"]:
        return "review"
    return "weak"

def recalibrate_topic_proficiency(user, results: list) -> dict:
    """
    Individualized-BKT core (thesis‑aligned):
      - PFA-like signals seed p(L0) and modulate p(T) per student.
      - Final mastery is BKT-only (no blending with PFA output).
      - Time/game weights remain in effect (session-level time multiplier).
      - Difficulty influences impact sizing, slip/guess, and wrong-answer decay.
      - Persist per-user×subtopic learning rate with EMA for stability across sessions.
      - Returns per‑subtopic summary including convergence and threshold flags for MCT-support.
    """
    per_subtopic_state = {}

    # Load existing mastery (used to seed priors when available)
    existing_mastery = {
        m.subtopic_id: (m.mastery_level or 0.0)
        for m in UserSubtopicMastery.objects.filter(user=user).only("subtopic_id", "mastery_level")
    }

    base_bkt = BKTParams()
    pfa = PFACoeffs()

    for entry in results or []:
        is_correct = bool(entry.get("is_correct", False))
        difficulty = _norm_diff(entry.get("estimated_difficulty"))
        diff_level = _diff_level(difficulty)

        mistakes = _mistakes_from_entry(entry)
        base_weight = float(_game_weight(entry))
        time_mult = _time_multiplier(entry, is_correct)
        impact_raw = base_weight * time_mult

        # Difficulty-aware impact
        impact = _impact_with_difficulty(impact_raw, is_correct, diff_level)

        subtopic_ids, _topic_ids = _get_mapping_from_question(entry)
        if not subtopic_ids:
            continue

        # If an item maps to multiple subtopics, distribute impact to avoid over-updating
        k = max(1, len(subtopic_ids))
        impact_each = impact / k

        extra_fails = mistakes  # already capped in _mistakes_from_entry

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
                    "p_prev": None,           # previous step value for delta tracking
                    "last_deltas": [],        # trailing window of |Δp|
                    "p_L0_seeded": False,     # whether we've seeded p(L0) explicitly
                    "subtopic_obj": subtopic_obj,
                    # persisted long-term scale loaded once per batch
                    "pT_scale_persisted": _load_pT_scale(user, subtopic_obj),
                }

            # Update PFA-like counters first (so seeding/tuning can see prior practice)
            st["attempts"] = float(st["attempts"]) + impact_each
            if is_correct:
                st["wins"] = float(st["wins"]) + impact_each
                st["fails"] = float(st["fails"]) + impact_each * extra_fails
            else:
                st["fails"] = float(st["fails"]) + impact_each * (1 + extra_fails)

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
                st["p_prev"] = float(seeded)
                st["p_L0_seeded"] = True

            # Build individualized BKT params for this learner & subtopic step
            # - combine persisted pT scale with within-batch multiplier (geometric mean)
            lr_mult_batch = _lr_mult_from_practice(float(st["wins"]), float(st["fails"]))
            lr_mult_persisted = max(0.5, min(1.5, float(st["pT_scale_persisted"])))
            lr_mult_combined = math.sqrt(lr_mult_persisted * lr_mult_batch)

            # Difficulty-aware observation parameters
            p_S_eff, p_G_eff, decay_eff = _observe_params_with_difficulty(base_bkt, diff_level)

            p_step = BKTParams(
                p_L0=float(st["p_bkt"]),   # doc only; running value used below
                p_T=max(1e-4, min(0.95, base_bkt.p_T * lr_mult_combined)),
                p_T_wrong=base_bkt.p_T_wrong,
                p_S=p_S_eff,
                p_G=p_G_eff,
                decay_wrong=decay_eff,
                min_floor=base_bkt.min_floor,
                max_ceiling=base_bkt.max_ceiling,
            )

            # Smooth BKT update (fractional impact) + delta tracking
            new_p = bkt_update_fractional(float(st["p_bkt"]), is_correct, p_step, impact_each)
            if st["p_prev"] is not None:
                st["last_deltas"].append(abs(new_p - float(st["p_prev"])) )
                # keep only last K deltas for convergence check
                if len(st["last_deltas"]) > CONVERGENCE_K:
                    st["last_deltas"] = st["last_deltas"][-CONVERGENCE_K:]
            st["p_prev"] = new_p
            st["p_bkt"] = new_p

    # Persist subtopic masteries (BKT only) + update EMA of pT_scale
    summary: Dict[int, Dict[str, float]] = {}

    for s_id, st in per_subtopic_state.items():
        p_mastery = float(st["p_bkt"]) if st["p_bkt"] is not None else base_bkt.p_L0
        pct = max(0.0, min(100.0, 100.0 * p_mastery))

        subtopic_obj: Subtopic = st["subtopic_obj"]  # already fetched
        # session-level recommended scale from observed batch
        session_scale = _lr_mult_from_practice(float(st["wins"]), float(st["fails"]))
        combined = math.sqrt(max(0.5, min(1.5, float(st["pT_scale_persisted"])) ) * session_scale)
        _save_pT_scale(user, subtopic_obj, combined, alpha=0.2)

        UserSubtopicMastery.objects.update_or_create(
            user=user,
            subtopic=subtopic_obj,
            defaults={"mastery_level": pct},
        )

        # MCT-support flags for the caller (UI/session controller)
        deltas: List[float] = list(st.get("last_deltas", []))
        converged = len(deltas) >= CONVERGENCE_K and all(d <= CONVERGENCE_EPS for d in deltas)
        threshold_reached = p_mastery >= MASTERY_THRESHOLD

        summary[s_id] = {
            "p_mastery": p_mastery,
            "mastery_pct": pct,
            "band": _band_of(p_mastery),
            "converged": 1.0 if converged else 0.0,
            "threshold_reached": 1.0 if threshold_reached else 0.0,
        }

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

    return summary
