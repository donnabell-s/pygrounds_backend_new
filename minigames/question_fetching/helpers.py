# Helper functions for question fetching
import random
from typing import List, Sequence, Optional, Dict
from django.db.models import Q, QuerySet
from content_ingestion.models import Subtopic, GameZone
from user_learning.models import UserZoneProgress, UserSubtopicMastery

def game_type_of(minigame: str) -> str:
    from .constants import CODING_MINIGAMES, NONCODING_MINIGAMES
    m = (minigame or '').strip().lower()
    if m in CODING_MINIGAMES:
        return 'coding'
    if m in NONCODING_MINIGAMES:
        return 'non_coding'
    return 'non_coding'

def pick_one_random(qs: QuerySet):
    n = qs.count()
    if n == 0:
        return None
    return qs[random.randrange(n)]

def sample_random_by_offsets(qs: QuerySet, k: int) -> List[int]:
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

def fetch_objects_preserve_order_by_id(qmodel, ids: Sequence[int]) -> List[object]:
    if not ids:
        return []
    objs = list(qmodel.objects.filter(id__in=ids))
    by_id = {o.id: o for o in objs}
    return [by_id[i] for i in ids if i in by_id]

def current_zone(user) -> Optional[GameZone]:
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

def zone_subtopics(zone: GameZone) -> QuerySet:
    return Subtopic.objects.filter(topic__zone=zone)

def weak_subtopics_in_zone(user, zone: GameZone) -> QuerySet:
    return (
        Subtopic.objects
        .filter(topic__zone=zone)
        .filter(
            Q(usersubtopicmastery__user=user, usersubtopicmastery__mastery_level__lt=90)
            | ~Q(usersubtopicmastery__user=user)
        )
        .distinct()
    )

def review_subtopics_in_zone(user, zone: GameZone) -> QuerySet:
    return (
        Subtopic.objects
        .filter(topic__zone=zone,
                usersubtopicmastery__user=user,
                usersubtopicmastery__mastery_level__gte=90,
                usersubtopicmastery__mastery_level__lt=100)
        .distinct()
    )

def maintenance_subtopics_in_zone(user, zone: GameZone) -> QuerySet:
    return (
        Subtopic.objects
        .filter(topic__zone=zone,
                usersubtopicmastery__user=user,
                usersubtopicmastery__mastery_level__gte=100)
        .distinct()
    )

def mastery_map(user, subtopics: QuerySet) -> Dict[int, float]:
    ms = list(
        UserSubtopicMastery.objects
        .filter(user=user, subtopic__in=subtopics.values_list('id', flat=True))
        .values('subtopic_id', 'mastery_level')
    )
    return {m['subtopic_id']: float(m['mastery_level'] or 0.0) for m in ms}
