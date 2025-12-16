import math
import random
import re
from typing import Iterable, List, Sequence, Optional, Dict, Tuple

from django.db.models import Q, QuerySet

from content_ingestion.models import Subtopic, GameZone
from user_learning.models import UserZoneProgress, UserSubtopicMastery
from question_generation.models import GeneratedQuestion

# If available in the same app, prefer importing from adaptive_engine to keep logic in sync
try:
    from user_learning.adaptive_engine import (
        BKTParams,
        bkt_update_once,
    )
except Exception:
    # Minimal local fallback to avoid circular/import errors during migrations
    from dataclasses import dataclass

    @dataclass
    class BKTParams:  # type: ignore
        p_L0: float = 0.20
        p_T: float = 0.10
        p_S: float = 0.10
        p_G: float = 0.20
        decay_wrong: float = 0.85
        min_floor: float = 0.001
        max_ceiling: float = 0.999

    def bkt_update_once(p_know: float, correct: bool, p: BKTParams) -> float:  # type: ignore
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


# ──────────────────────────────────────────────────────────────────────────────
# Tunables
# ──────────────────────────────────────────────────────────────────────────────

# Mix for NON-CODING questions (current zone only)
# "Occasionally" = small but non-zero maintenance (mastered) sampling
MIX_WEAK       = 0.75   # <100% or no mastery row
MIX_REVIEW     = 0.15   # near-mastered (>=90%)
MIX_MAINT      = 0.10   # mastered (=100%)

# Coding picks exactly one item. Chance to pull maintenance instead of weak:
MAINT_PROB_CODING = 0.15

# Grid‑compatible answers (crossword/wordsearch) must contain letters
GRID_REGEX = r"[A-Za-z]+"

# Map minigame string → game_type
CODING_MINIGAMES    = {"hangman", "debugging"}
NONCODING_MINIGAMES = {"crossword", "wordsearch"}

# Difficulty targeting by mastery band
DIFF_LOW  = ["beginner", "intermediate"]
DIFF_HIGH = ["advanced", "master"]
DIFF_ALL  = ["beginner", "intermediate", "advanced", "master"]

# EIG + BWS settings
EVAL_CANDIDATES_PER_BUCKET = 80   # evaluate up to N per bucket before sampling
SOFTMAX_TEMPERATURE         = 0.20  # lower = greedier toward max‑EIG

# Difficulty normalization & mapping
DIFF_LEVELS = {"beginner": 0, "intermediate": 1, "advanced": 2, "master": 3}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _game_type_of(minigame: str) -> str:
    m = (minigame or '').strip().lower()
    if m in CODING_MINIGAMES:
        return 'coding'
    if m in NONCODING_MINIGAMES:
        return 'non_coding'
    return 'non_coding'


def _pick_one_random(qs: QuerySet):
    """Return one random row without ORDER BY RANDOM()."""
    n = qs.count()
    if n == 0:
        return None
    return qs[random.randrange(n)]


def _sample_random_by_offsets(qs: QuerySet, k: int) -> List[int]:
    """
    Return up to k random primary keys using LIMIT/OFFSET strategy.
    Pass qs.only('id') for efficiency.
    """
    n = qs.count()
    if n == 0:
        return []
    k = min(k, n)
    offsets = sorted(random.sample(range(n), k))
    ids: List[int] = []
    for off in offsets:
        row = qs.only('id')[off]
        ids.append(row.id)
    return ids


def _fetch_objects_preserve_order_by_id(qmodel, ids: Sequence[int]) -> List[object]:
    if not ids:
        return []
    objs = list(qmodel.objects.filter(id__in=ids))
    by_id = {o.id: o for o in objs}
    return [by_id[i] for i in ids if i in by_id]


def _current_zone(user) -> Optional[GameZone]:
    """First zone <100% complete, else last zone."""
    progresses = (
        UserZoneProgress.objects
        .filter(user=user)
        .select_related('zone')
        .order_by('zone__order')
    )
    if not progresses.exists():
        return GameZone.objects.order_by('order').first()
    for p in progresses:
        if (p.completion_percent or 0) < 100:
            return p.zone
    return progresses.last().zone


def _zone_subtopics(zone: GameZone) -> QuerySet:
    return Subtopic.objects.filter(topic__zone=zone)


def _weak_subtopics_in_zone(user, zone: GameZone) -> QuerySet:
    """Subtopics in zone with mastery <90 or no mastery row."""
    return (
        Subtopic.objects
        .filter(topic__zone=zone)
        .filter(
            Q(usersubtopicmastery__user=user, usersubtopicmastery__mastery_level__lt=90)
            | ~Q(usersubtopicmastery__user=user)
        )
        .distinct()
    )


def _review_subtopics_in_zone(user, zone: GameZone) -> QuerySet:
    """Subtopics in zone that are near mastered (>=90 and <100)."""
    return (
        Subtopic.objects
        .filter(topic__zone=zone,
                usersubtopicmastery__user=user,
                usersubtopicmastery__mastery_level__gte=90,
                usersubtopicmastery__mastery_level__lt=100)
        .distinct()
    )


def _maintenance_subtopics_in_zone(user, zone: GameZone) -> QuerySet:
    """Subtopics in zone that are mastered (=100)."""
    return (
        Subtopic.objects
        .filter(topic__zone=zone,
                usersubtopicmastery__user=user,
                usersubtopicmastery__mastery_level__gte=100)
        .distinct()
    )


def _mastery_map(user, subtopics: QuerySet) -> Dict[int, float]:
    """Map subtopic_id -> mastery (0..100), default 0 if none."""
    ms = list(
        UserSubtopicMastery.objects
        .filter(user=user, subtopic__in=subtopics.values_list('id', flat=True))
        .values('subtopic_id', 'mastery_level')
    )
    return {m['subtopic_id']: float(m['mastery_level'] or 0.0) for m in ms}


# ──────────────────────────────────────────────────────────────────────────────
# EIG‑BKT core
# ──────────────────────────────────────────────────────────────────────────────

def _norm_diff(d: Optional[str]) -> str:
    if not d:
        return 'intermediate'
    d = str(d).strip().lower()
    if d in DIFF_LEVELS:
        return d
    if d.startswith('beg'):
        return 'beginner'
    if d.startswith('inter'):
        return 'intermediate'
    if d.startswith('adv'):
        return 'advanced'
    if d.startswith('mast'):
        return 'master'
    return 'intermediate'


def _diff_level(d: Optional[str]) -> int:
    return DIFF_LEVELS.get(_norm_diff(d), 1)


def _diff_centered(level: int) -> float:
    # beginner:-1, intermediate:-0.333..., advanced:+0.333..., master:+1
    return (max(0, min(3, level)) - 1.5) / 1.5


def _observe_params_with_difficulty(base: BKTParams, level: int) -> Tuple[float, float, float]:
    """Mirror adaptive_engine difficulty nudges for slip/guess/decay."""
    c = _diff_centered(level)              # [-1..+1]
    s_k, g_k, d_k = 0.04, 0.04, 0.07

    p_S_eff = max(0.02, min(0.30, base.p_S + s_k * c))
    p_G_eff = max(0.05, min(0.35, base.p_G - g_k * c))

    target_easy, target_hard = 0.80, 0.98
    target = target_hard if c > 0 else target_easy
    decay_eff = base.decay_wrong + d_k * (target - base.decay_wrong)
    decay_eff = decay_eff + 0.05 * c
    decay_eff = max(0.75, min(0.98, decay_eff))
    return p_S_eff, p_G_eff, decay_eff


def _binary_entropy(p: float) -> float:
    p = max(1e-9, min(1 - 1e-9, p))
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def _p_correct(p_know: float, p_S: float, p_G: float) -> float:
    return p_know * (1 - p_S) + (1 - p_know) * p_G


def _eig_for_question(p_know: float, diff_level: int, base: Optional[BKTParams] = None) -> float:
    """
    Expected Information Gain using BKT update for a single observation (impact≈1).
    EIG = H(p) − [ P(c)·H(p'|c) + P(w)·H(p'|w) ]
    """
    base = base or BKTParams()
    p_S, p_G, decay_wrong = _observe_params_with_difficulty(base, diff_level)

    # Prior entropy
    H_prior = _binary_entropy(p_know)

    # Predictive correctness
    Pc = _p_correct(p_know, p_S, p_G)
    Pw = 1 - Pc

    # Posterior after a correct/incorrect observation
    params = BKTParams(
        p_L0=p_know, p_T=base.p_T, p_S=p_S, p_G=p_G, decay_wrong=decay_wrong,
        min_floor=base.min_floor, max_ceiling=base.max_ceiling,
    )
    p_after_c = bkt_update_once(p_know, True, params)
    p_after_w = bkt_update_once(p_know, False, params)

    # Expected posterior entropy
    H_post = Pc * _binary_entropy(p_after_c) + Pw * _binary_entropy(p_after_w)

    return max(0.0, H_prior - H_post)


# ──────────────────────────────────────────────────────────────────────────────
# Bayesian Weighted Sampling (BWS) over EIG scores
# ──────────────────────────────────────────────────────────────────────────────

def _softmax(xs: List[float], temperature: float) -> List[float]:
    if not xs:
        return []
    t = max(1e-6, float(temperature))
    m = max(xs)
    exps = [math.exp((x - m) / t) for x in xs]
    s = sum(exps)
    if s <= 0:
        n = len(xs)
        return [1.0 / n] * n
    return [e / s for e in exps]


def _bws_pick_ids_by_eig(
    user,
    qs: QuerySet,
    take: int,
    mastery_by_sub: Dict[int, float],
    temperature: float = SOFTMAX_TEMPERATURE,
    eval_cap: int = EVAL_CANDIDATES_PER_BUCKET,
) -> List[int]:
    """
    Evaluate up to `eval_cap` random candidates with EIG, then draw `take` ids
    proportionally to softmax(EIG/temperature). If EIG all zero, fall back to random.
    """
    if take <= 0:
        return []

    # Pre-sample a candidate set for evaluation
    cand_ids = _sample_random_by_offsets(qs.only('id'), min(eval_cap, take * 8))
    if not cand_ids:
        return []

    # Fetch needed fields once
    fields = ['id', 'subtopic_id', 'estimated_difficulty']
    objs = list(GeneratedQuestion.objects.filter(id__in=cand_ids).only(*fields))

    base = BKTParams()  # shared baseline

    eig_scores: List[float] = []
    ordered_ids: List[int] = []

    for o in objs:
        sid = getattr(o, 'subtopic_id', None)
        if sid is None:
            continue
        p_know = (mastery_by_sub.get(sid, 0.0) or 0.0) / 100.0
        if p_know <= 0.0:
            p_know = base.p_L0  # cold start
        dlevel = _diff_level(getattr(o, 'estimated_difficulty', None))
        eig = _eig_for_question(p_know, dlevel, base)
        eig_scores.append(float(eig))
        ordered_ids.append(int(o.id))

    if not ordered_ids:
        return []

    # If all zero/near-zero, random fallback
    if max(eig_scores) <= 1e-9:
        k = min(take, len(ordered_ids))
        return random.sample(ordered_ids, k)

    probs = _softmax(eig_scores, temperature)

    chosen: List[int] = []
    pool: List[Tuple[int, float]] = list(zip(ordered_ids, probs))

    # Multinomial draws without replacement (approximate by renormalizing each draw)
    for _ in range(min(take, len(pool))):
        # draw
        r = random.random()
        cum = 0.0
        pick_idx = 0
        for i, (_id, p) in enumerate(pool):
            cum += p
            if r <= cum:
                pick_idx = i
                break
        chosen_id = pool[pick_idx][0]
        chosen.append(chosen_id)
        # remove and renormalize
        del pool[pick_idx]
        s = sum(p for _, p in pool)
        if s > 0:
            pool = [(i, p / s) for (i, p) in pool]
        else:
            break

    return chosen


# ──────────────────────────────────────────────────────────────────────────────
# Public API (Current-zone only, with maintenance)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_questions_for_game(
    user,
    game_type: str,                 # 'crossword' | 'wordsearch' | 'hangman' | 'debugging'
    limit: int = 10,
    exclude_ids: Optional[Iterable[int]] = None,  # avoid repeats in a session
) -> List[GeneratedQuestion]:
    """
    Current-zone question selection with EIG‑BKT + BWS:
      • Focus on weak subtopics in the current zone.
      • Mix in review (>=90) and occasional maintenance (=100) from the same zone.
      • Compute Expected Information Gain per candidate via BKT (difficulty‑aware).
      • Use Bayesian Weighted Sampling (softmax over EIG) to *sample* items.
      • Regex gating for grid‑compatible answers in non‑coding games.
      • All backfills restricted to the current zone.
    """
    zone = _current_zone(user)
    if not zone:
        return []

    zone_sub_ids = _zone_subtopics(zone).values_list('id', flat=True)

    gtype = _game_type_of(game_type)
    exclude_ids = set(exclude_ids or [])

    # ── Pools of subtopics (current zone ONLY)
    weak_subs   = _weak_subtopics_in_zone(user, zone)
    review_subs = _review_subtopics_in_zone(user, zone)
    maint_subs  = _maintenance_subtopics_in_zone(user, zone)

    # Mastery map (for EIG and difficulty targeting)
    all_subs_for_map = Subtopic.objects.filter(
        id__in=weak_subs.values_list('id', flat=True)
             .union(review_subs.values_list('id', flat=True))
             .union(maint_subs.values_list('id', flat=True))
    )
    mastery_by_sub: Dict[int, float] = _mastery_map(user, all_subs_for_map)

    # Base queryset by game type, restricted to current zone
    base_qs: QuerySet = GeneratedQuestion.objects.filter(
        game_type=gtype,
        subtopic_id__in=zone_sub_ids
    )
    if exclude_ids:
        base_qs = base_qs.exclude(id__in=list(exclude_ids))

    # ── CODING: exactly 1 item (current zone only) using EIG‑BKT + BWS
    if gtype == 'coding':
        weak_qs  = base_qs.filter(subtopic_id__in=weak_subs.values_list('id', flat=True)).only('id')
        maint_qs = base_qs.filter(subtopic_id__in=maint_subs.values_list('id', flat=True)).only('id')

        # pick_maint = (random.random() < MAINT_PROB_CODING) and maint_qs.count() > 0
        # choice_qs = maint_qs if pick_maint else weak_qs

        pick_maint = (random.random() < MAINT_PROB_CODING) and maint_qs.count() > 0
        choice_qs = maint_qs if pick_maint else weak_qs
        # NEW: if maintenance was chosen but turns out empty, fall back
        if choice_qs.count() == 0:
            choice_qs = weak_qs


        chosen_ids = _bws_pick_ids_by_eig(user, choice_qs, take=1, mastery_by_sub=mastery_by_sub)
        if not chosen_ids:
            # fallbacks
            fallback_qs = weak_qs if weak_qs.count() > 0 else base_qs.only('id')
            one = _pick_one_random(fallback_qs)
            if not one:
                return []
            chosen_ids = [one.id]

        # Fallback correct_answer from game_data (for coding games that omit it)
        full_one = GeneratedQuestion.objects.get(id=chosen_ids[0])
        if not full_one.correct_answer:
            fn = (full_one.game_data or {}).get('function_name') or ''
            if fn:
                full_one.correct_answer = fn
                full_one.save(update_fields=['correct_answer'])
        return [full_one]

    # ── NON‑CODING: stratified weak/review/maintenance with EIG‑BKT + BWS
    base_nc = base_qs.filter(correct_answer__regex=GRID_REGEX)

    def qs_for_subtopics(subs: QuerySet) -> QuerySet:
        return base_nc.filter(subtopic_id__in=subs.values_list('id', flat=True))

    weak_qs   = qs_for_subtopics(weak_subs)
    review_qs = qs_for_subtopics(review_subs)
    maint_qs  = qs_for_subtopics(maint_subs)

    # Split weak by mastery bands → difficulty targeting
    weak_low_ids, weak_mid_ids, weak_high_ids = [], [], []
    for sid in weak_subs.values_list('id', flat=True):
        m = mastery_by_sub.get(sid, 0.0)
        if m < 50:
            weak_low_ids.append(sid)
        elif m < 85:
            weak_mid_ids.append(sid)
        else:
            weak_high_ids.append(sid)

    weak_low_qs  = base_nc.filter(subtopic_id__in=weak_low_ids,  estimated_difficulty__in=DIFF_LOW)
    weak_mid_qs  = base_nc.filter(subtopic_id__in=weak_mid_ids,  estimated_difficulty__in=DIFF_ALL)
    weak_high_qs = base_nc.filter(subtopic_id__in=weak_high_ids, estimated_difficulty__in=DIFF_HIGH)
    
    # ============================================================================
# OPTIONAL THETA TARGETING (ADAPTIVE DIFFICULTY)
# These lines DO NOT replace the EIG-BKT logic. They simply bias the sampling
# toward a difficulty near the user's theta, WITHOUT breaking compatibility.
# ============================================================================

    try:
        from analytics.models import UserAbility
        theta = UserAbility.objects.get(user=user).theta
    except Exception:
        theta = 0.0

    # Map difficulty levels (0..3) toward a target difficulty based on theta
    if theta < -0.5:
        target_levels = ["beginner"]
    elif theta < 0.5:
        target_levels = ["beginner", "intermediate"]
    elif theta < 1.5:
        target_levels = ["intermediate", "advanced"]
    else:
        target_levels = ["advanced", "master"]

    # Filter weak pools to prioritize difficulty near theta
    weak_low_qs  = weak_low_qs.filter(estimated_difficulty__in=target_levels) or weak_low_qs
    weak_mid_qs  = weak_mid_qs.filter(estimated_difficulty__in=target_levels) or weak_mid_qs
    weak_high_qs = weak_high_qs.filter(estimated_difficulty__in=target_levels) or weak_high_qs


    # Review: allow anything; Maintenance: prefer hard items to truly test mastery
    review_all_qs = review_qs.filter(estimated_difficulty__in=DIFF_ALL)
    maint_high_qs = maint_qs.filter(estimated_difficulty__in=DIFF_HIGH)

    # How many to take
    k1 = max(1, int(round(limit * MIX_WEAK)))
    k2 = max(0, int(round(limit * MIX_REVIEW)))
    k3 = max(0, limit - k1 - k2)  # maintenance gets the remainder

    # Within weak, allocate across bands (more low→mid)
    k1_low  = int(round(k1 * 0.55))
    k1_mid  = int(round(k1 * 0.35))
    k1_high = max(0, k1 - k1_low - k1_mid)

    chosen_ids: List[int] = []

    def extend_from_bws(qs: QuerySet, take: int):
        if take <= 0:
            return
        ids = _bws_pick_ids_by_eig(user, qs.exclude(id__in=chosen_ids), take, mastery_by_sub)
        for i in ids:
            if i not in chosen_ids and i not in exclude_ids:
                chosen_ids.append(i)

    extend_from_bws(weak_low_qs,  k1_low)
    extend_from_bws(weak_mid_qs,  k1_mid)
    extend_from_bws(weak_high_qs, k1_high)

    extend_from_bws(review_all_qs, k2)
    extend_from_bws(maint_high_qs, k3)

    # Backfill if short (still current zone only) — use BWS over the remainder
    if len(chosen_ids) < limit:
        need = limit - len(chosen_ids)
        backfill_qs = base_nc.exclude(id__in=chosen_ids).only('id')  # already restricted to zone
        extend_from_bws(backfill_qs, need)

    return _fetch_objects_preserve_order_by_id(GeneratedQuestion, chosen_ids[:limit])
