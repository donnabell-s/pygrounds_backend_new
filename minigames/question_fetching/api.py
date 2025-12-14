
# Public API for question fetching
import random
from typing import Iterable, Optional, List, Dict
from django.db.models import QuerySet
from question_generation.models import GeneratedQuestion
from content_ingestion.models import Subtopic
from .constants import MIX_WEAK, MIX_REVIEW, MIX_MAINT, MAINT_PROB_CODING, GRID_REGEX, DIFF_LOW, DIFF_HIGH, DIFF_ALL
from .helpers import (
    game_type_of, pick_one_random, fetch_objects_preserve_order_by_id, current_zone, zone_subtopics,
    weak_subtopics_in_zone, review_subtopics_in_zone, maintenance_subtopics_in_zone, mastery_map
)
from .bws import bws_pick_ids_by_eig

def fetch_questions_for_game(
    user,
    game_type: str,
    limit: int = 10,
    exclude_ids: Optional[Iterable[int]] = None,
) -> List[GeneratedQuestion]:
    zone = current_zone(user)
    if not zone:
        return []
    zone_sub_ids = zone_subtopics(zone).values_list('id', flat=True)
    gtype = game_type_of(game_type)
    exclude_ids = set(exclude_ids or [])
    weak_subs   = weak_subtopics_in_zone(user, zone)
    review_subs = review_subtopics_in_zone(user, zone)
    maint_subs  = maintenance_subtopics_in_zone(user, zone)
    all_subs_for_map = Subtopic.objects.filter(
        id__in=weak_subs.values_list('id', flat=True)
             .union(review_subs.values_list('id', flat=True))
             .union(maint_subs.values_list('id', flat=True))
    )
    mastery_by_sub: Dict[int, float] = mastery_map(user, all_subs_for_map)
    base_qs: QuerySet = GeneratedQuestion.objects.filter(
        game_type=gtype,
        subtopic_id__in=zone_sub_ids
    )
    if exclude_ids:
        base_qs = base_qs.exclude(id__in=list(exclude_ids))
    if gtype == 'coding':
        weak_qs  = base_qs.filter(subtopic_id__in=weak_subs.values_list('id', flat=True)).only('id')
        maint_qs = base_qs.filter(subtopic_id__in=maint_subs.values_list('id', flat=True)).only('id')
        pick_maint = (random.random() < MAINT_PROB_CODING) and maint_qs.count() > 0
        choice_qs = maint_qs if pick_maint else weak_qs
        if choice_qs.count() == 0:
            choice_qs = weak_qs
        chosen_ids = bws_pick_ids_by_eig(user, choice_qs, take=1, mastery_by_sub=mastery_by_sub)
        if not chosen_ids:
            fallback_qs = weak_qs if weak_qs.count() > 0 else base_qs.only('id')
            one = pick_one_random(fallback_qs)
            if not one:
                return []
            chosen_ids = [one.id]
        full_one = GeneratedQuestion.objects.get(id=chosen_ids[0])
        if not full_one.correct_answer:
            fn = (full_one.game_data or {}).get('function_name') or ''
            if fn:
                full_one.correct_answer = fn
                full_one.save(update_fields=['correct_answer'])
        return [full_one]
    base_nc = base_qs.filter(correct_answer__regex=GRID_REGEX)
    def qs_for_subtopics(subs):
        return base_nc.filter(subtopic_id__in=subs.values_list('id', flat=True))
    weak_qs   = qs_for_subtopics(weak_subs)
    review_qs = qs_for_subtopics(review_subs)
    maint_qs  = qs_for_subtopics(maint_subs)
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
    review_all_qs = review_qs.filter(estimated_difficulty__in=DIFF_ALL)
    maint_high_qs = maint_qs.filter(estimated_difficulty__in=DIFF_HIGH)
    k1 = max(1, int(round(limit * MIX_WEAK)))
    k2 = max(0, int(round(limit * MIX_REVIEW)))
    k3 = max(0, limit - k1 - k2)
    k1_low  = int(round(k1 * 0.55))
    k1_mid  = int(round(k1 * 0.35))
    k1_high = max(0, k1 - k1_low - k1_mid)
    chosen_ids: List[int] = []
    def extend_from_bws(qs, take):
        if take <= 0:
            return
        ids = bws_pick_ids_by_eig(user, qs.exclude(id__in=chosen_ids), take, mastery_by_sub)
        for i in ids:
            if i not in chosen_ids and i not in exclude_ids:
                chosen_ids.append(i)
    extend_from_bws(weak_low_qs,  k1_low)
    extend_from_bws(weak_mid_qs,  k1_mid)
    extend_from_bws(weak_high_qs, k1_high)
    extend_from_bws(review_all_qs, k2)
    extend_from_bws(maint_high_qs, k3)
    if len(chosen_ids) < limit:
        need = limit - len(chosen_ids)
        backfill_qs = base_nc.exclude(id__in=chosen_ids).only('id')
        extend_from_bws(backfill_qs, need)
    return fetch_objects_preserve_order_by_id(GeneratedQuestion, chosen_ids[:limit])
