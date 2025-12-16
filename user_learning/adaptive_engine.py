from typing import Dict, List
from django.db import transaction
from django.db.models import Avg
from user_learning.models import UserZoneProgress, UserTopicProficiency, UserSubtopicMastery, UserAbility
from content_ingestion.models import Topic, Subtopic, GameZone
from .adaptive_weights import compute_effective_correctness


def clamp(x: float, min_val: float, max_val: float) -> float:

    return max(min_val, min(max_val, x))


def extract_subtopic_ids(entry: dict) -> List[int]:

    # Direct subtopic_id
    if "subtopic_id" in entry and entry["subtopic_id"]:
        return [int(entry["subtopic_id"])]
    
    # Direct subtopic_ids list
    if "subtopic_ids" in entry and entry["subtopic_ids"]:
        return [int(sid) for sid in entry["subtopic_ids"]]
    
    # subtopics array of dicts
    if "subtopics" in entry and isinstance(entry["subtopics"], list):
        ids = []
        for s in entry["subtopics"]:
            if isinstance(s, dict) and "id" in s:
                ids.append(int(s["id"]))
        if ids:
            return ids
    
    # mapping.subtopic_ids
    if "mapping" in entry and isinstance(entry["mapping"], dict):
        if "subtopic_ids" in entry["mapping"]:
            return [int(sid) for sid in entry["mapping"]["subtopic_ids"]]
    
    return []


def aggregate_by_subtopic(results: List[dict]) -> Dict[int, Dict[str, float]]:

    agg = {}
    for entry in results:
        # Compute effective correctness incorporating difficulty, time, lives
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
    
    # Compute weighted accuracy
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
    
    # 1. Load or create UserAbility
    ability, _ = UserAbility.objects.get_or_create(
        user=user,
        defaults={"ability_score": 0.5}
    )
    ability_old = float(ability.ability_score)
    
    # 2. Aggregate by subtopic
    subtopic_agg = aggregate_by_subtopic(results)
    
    # Compute overall session accuracy
    total_attempts = sum(entry.get("is_correct") is not None for entry in results)
    total_correct = sum(1 for entry in results if entry.get("is_correct", False))
    session_accuracy = total_correct / total_attempts if total_attempts > 0 else 0.0
    
    # EMA parameters
    alpha = 0.45  # subtopic mastery update rate
    beta = 0.20   # ability update rate
    
    updated_subtopics = []
    touched_topic_ids = set()
    
    # 3. Update each touched subtopic
    for subtopic_id, stats in subtopic_agg.items():
        subtopic_obj = Subtopic.objects.filter(id=subtopic_id).first()
        if not subtopic_obj:
            continue
        
        touched_topic_ids.add(subtopic_obj.topic_id)
        
        # Load or create mastery
        mastery_obj, _ = UserSubtopicMastery.objects.get_or_create(
            user=user,
            subtopic=subtopic_obj,
            defaults={"mastery_level": 0.0}
        )
        
        K_old = mastery_obj.mastery_level / 100.0  # convert percent to 0-1
        K_old = clamp(K_old, 0.0, 1.0)
        
        # Personalized prior (from paper)
        prior = 0.7 * K_old + 0.3 * ability_old
        
        # EMA update with subtopic accuracy
        subtopic_accuracy = stats["accuracy"]
        K_new = (1 - alpha) * prior + alpha * subtopic_accuracy
        K_new = clamp(K_new, 0.0, 1.0)
        
        # Save mastery
        mastery_obj.mastery_level = K_new * 100.0
        mastery_obj.save(update_fields=["mastery_level"])
        
        updated_subtopics.append({
            "subtopic_id": subtopic_id,
            "subtopic_name": subtopic_obj.name,
            "old_mastery": K_old,
            "new_mastery": K_new,
            "accuracy": subtopic_accuracy,
            "attempts": stats["attempts"],
        })
    
    # 4. Update global ability
    ability_new = (1 - beta) * ability_old + beta * session_accuracy
    ability_new = clamp(ability_new, 0.05, 0.95)
    
    ability.ability_score = ability_new
    ability.save(update_fields=["ability_score"])
    
    # 5. Rollup to topics
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
    
    # 6. Rollup to zones
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
