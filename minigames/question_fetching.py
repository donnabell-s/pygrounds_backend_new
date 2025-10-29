import random
import re
from typing import Iterable, List, Sequence, Optional, Dict

from django.db.models import Q, QuerySet

from content_ingestion.models import Subtopic, GameZone
from user_learning.models import UserZoneProgress, UserSubtopicMastery
from question_generation.models import GeneratedQuestion

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
GRID_REGEX = r'[A-Za-z]+'

# Map minigame string → game_type
CODING_MINIGAMES    = {'hangman', 'debugging'}
NONCODING_MINIGAMES = {'crossword', 'wordsearch'}

# Difficulty targeting by mastery band
DIFF_LOW  = ['beginner', 'intermediate']
DIFF_HIGH = ['advanced', 'master']
DIFF_ALL  = ['beginner', 'intermediate', 'advanced', 'master']


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
    """Subtopics in zone with mastery <100 or no mastery row."""
    return (
        Subtopic.objects
        .filter(topic__zone=zone)
        .filter(
            Q(usersubtopicmastery__user=user, usersubtopicmastery__mastery_level__lt=100)
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
# Public API (Current-zone only, with maintenance)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_questions_for_game(
    user,
    game_type: str,                 # 'crossword' | 'wordsearch' | 'hangman' | 'debugging'
    limit: int = 10,
    exclude_ids: Optional[Iterable[int]] = None,  # avoid repeats in a session
) -> List[GeneratedQuestion]:
    """
    Current-zone question selection:
      • Focus on weak subtopics in the current zone.
      • Mix in review (>=90) and *occasional* maintenance (=100) from the same zone.
      • Target difficulty per subtopic by mastery band.
      • Random sampling without ORDER BY RANDOM().
      • Server‑side regex for grid‑compatible non‑coding answers.
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

    # Mastery map (for difficulty targeting in weak)
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

    # ── CODING: exactly 1 item (current zone only)
    if gtype == 'coding':
        weak_qs  = base_qs.filter(subtopic_id__in=weak_subs.values_list('id', flat=True)).only('id')
        maint_qs = base_qs.filter(subtopic_id__in=maint_subs.values_list('id', flat=True)).only('id')

        pick_maint = (random.random() < MAINT_PROB_CODING)
        choice_qs = maint_qs if pick_maint and maint_qs.count() > 0 else weak_qs

        one = _pick_one_random(choice_qs) or _pick_one_random(weak_qs) or _pick_one_random(base_qs.only('id'))
        if not one:
            return []

        # Fallback correct_answer from game_data (for coding games that omit it)
        full_one = GeneratedQuestion.objects.get(id=one.id)
        if not full_one.correct_answer:
            fn = (full_one.game_data or {}).get('function_name') or ''
            if fn:
                full_one.correct_answer = fn
                full_one.save(update_fields=['correct_answer'])
        return [full_one]

    # ── NON‑CODING: stratified weak/review/maintenance with difficulty targeting
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

    def extend_from(qs: QuerySet, take: int):
        if take <= 0:
            return
        n = qs.count()
        if n == 0:
            return
        ids = _sample_random_by_offsets(qs.only('id'), take)
        for i in ids:
            if i not in exclude_ids and i not in chosen_ids:
                chosen_ids.append(i)

    extend_from(weak_low_qs,  k1_low)
    extend_from(weak_mid_qs,  k1_mid)
    extend_from(weak_high_qs, k1_high)

    extend_from(review_all_qs, k2)
    extend_from(maint_high_qs, k3)

    # Backfill if short (still current zone only)
    if len(chosen_ids) < limit:
        need = limit - len(chosen_ids)
        backfill_qs = base_nc.exclude(id__in=chosen_ids).only('id')  # already restricted to zone
        extend_from(backfill_qs, need)

    return _fetch_objects_preserve_order_by_id(GeneratedQuestion, chosen_ids[:limit])
