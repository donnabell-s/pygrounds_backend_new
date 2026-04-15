from typing import Dict, List
from django.db import transaction
from django.db.models import Avg
from django.utils import timezone
from user_learning.models import UserZoneProgress, UserTopicProficiency, UserSubtopicMastery, UserAbility
from content_ingestion.models import Topic, Subtopic, GameZone
from .adaptive_weights import compute_effective_correctness
from .bkt_params import BKT_PARAMS, DEFAULT_PARAMS
from .bkt import bkt_update
from .forgetting import apply_forgetting
from .performance_multiplier import apply_coding_multiplier
from .clustering import get_cluster_name


def clamp(x: float, min_val: float, max_val: float) -> float:

    return max(min_val, min(max_val, x))


def extract_subtopic_ids(entry: dict) -> List[int]:

    if "subtopic_id" in entry and entry["subtopic_id"]:
        return [int(entry["subtopic_id"])]
    
    if "subtopic_ids" in entry and entry["subtopic_ids"]:
        return [int(sid) for sid in entry["subtopic_ids"]]

    if "subtopics" in entry and isinstance(entry["subtopics"], list):
        ids = []
        for s in entry["subtopics"]:
            if isinstance(s, dict) and "id" in s:
                ids.append(int(s["id"]))
        if ids:
            return ids
    
    if "mapping" in entry and isinstance(entry["mapping"], dict):
        if "subtopic_ids" in entry["mapping"]:
            return [int(sid) for sid in entry["mapping"]["subtopic_ids"]]
    
    return []


def aggregate_by_subtopic(results: List[dict]) -> Dict[int, Dict[str, float]]:

    agg = {}
    for entry in results:
        effective = compute_effective_correctness(entry)
        
        subtopic_ids = extract_subtopic_ids(entry)
        for sid in subtopic_ids:
            if sid not in agg:
                agg[sid] = {
                    "attempts": 0.0,
                    "weighted_sum": 0.0,
                    "accuracy": 0.0
                }
            agg[sid]["attempts"] += 1.0
            agg[sid]["weighted_sum"] += effective
    
    for sid, stats in agg.items():
        if stats["attempts"] > 0:
            stats["accuracy"] = stats["weighted_sum"] / stats["attempts"]
        else:
            stats["accuracy"] = 0.0
    
    return agg


@transaction.atomic
def recalibrate_topic_proficiency(user, results: list) -> dict:

    if not results:
        return {
            "session": {"total_attempts": 0, "correct": 0, "accuracy": 0.0},
            "ability": {"old": 0.5, "new": 0.5},
            "updated_subtopics": [],
            "touched_topics": [],
        }
    
    ability, _ = UserAbility.objects.get_or_create(
        user=user,
        defaults={"ability_score": 0.5}
    )
    ability_old = float(ability.ability_score)
    
    subtopic_agg = aggregate_by_subtopic(results)
    
    #compute user's performance this session (how accurate, ect)
    total_attempts = sum(entry.get("is_correct") is not None for entry in results)
    total_correct = sum(1 for entry in results if entry.get("is_correct", False))
    session_accuracy = total_correct / total_attempts if total_attempts > 0 else 0.0
    
    beta = 0.20   #userability update rate
    
    updated_subtopics = []
    touched_topic_ids = set()
    
    #resolve BKT params from learner cluster
    try:
        cluster_name = get_cluster_name(ability.learner_cluster)
        params = BKT_PARAMS.get(cluster_name, DEFAULT_PARAMS)
    except Exception:
        params = DEFAULT_PARAMS

    #update each used subtopic's mastery
    for subtopic_id, stats in subtopic_agg.items():
        subtopic_obj = Subtopic.objects.filter(id=subtopic_id).first()
        if not subtopic_obj:
            continue

        touched_topic_ids.add(subtopic_obj.topic_id)

        mastery_obj, _ = UserSubtopicMastery.objects.get_or_create(
            user=user,
            subtopic=subtopic_obj,
            defaults={"mastery_level": 0.0}
        )

        K_old = clamp(mastery_obj.mastery_level / 100.0, 0.0, 1.0)

        # step 1: apply forgetting factor
        K_decayed = apply_forgetting(K_old, mastery_obj.last_practiced_at, params["p_forget"])

        # step 2: BKT posterior — treat accuracy >= 0.5 as a correct observation
        subtopic_accuracy = stats["accuracy"]
        is_correct_obs = subtopic_accuracy >= 0.5
        K_posterior = bkt_update(K_decayed, is_correct_obs, params["p_slip"], params["p_guess"])

        # step 3: apply transit (learning gain)
        K_transited = K_posterior + (1 - K_posterior) * params["p_transit"]

        # step 4: coding multiplier on the delta only
        game_types_in_results = {
            entry.get("game_type", "") for entry in results
            if entry.get("subtopic_id") == subtopic_id
               or subtopic_id in entry.get("subtopic_ids", [])
        }
        is_coding = bool(game_types_in_results & {"coding"})
        if is_coding and subtopic_accuracy >= 0.5:
            delta = K_transited - K_decayed
            K_transited = K_decayed + apply_coding_multiplier(delta)

        K_new = clamp(K_transited, 0.0, 1.0)

        mastery_obj.mastery_level = K_new * 100.0
        mastery_obj.last_practiced_at = timezone.now()
        mastery_obj.save(update_fields=["mastery_level", "last_practiced_at"])

        updated_subtopics.append({
            "subtopic_id": subtopic_id,
            "subtopic_name": subtopic_obj.name,
            "old_mastery": K_old,
            "new_mastery": K_new,
            "accuracy": subtopic_accuracy,
            "attempts": stats["attempts"],
        })
    
    #update userability
    ability_new = (1 - beta) * ability_old + beta * session_accuracy
    ability_new = clamp(ability_new, 0.05, 0.95)
    
    ability.ability_score = ability_new
    ability.save(update_fields=["ability_score"])
    
   #update topic
    for topic in Topic.objects.filter(id__in=touched_topic_ids):
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
    
    #update zone
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
    
    return {
        "session": {
            "total_attempts": total_attempts,
            "correct": total_correct,
            "accuracy": session_accuracy,
        },
        "ability": {
            "old": ability_old,
            "new": ability_new,
        },
        "updated_subtopics": updated_subtopics,
        "touched_topics": list(touched_topic_ids),
    }
