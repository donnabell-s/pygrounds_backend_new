# user_learning/adaptive_engine.py
from django.db.models import Avg
from collections import defaultdict

from question_generation.models import PreAssessmentQuestion
from user_learning.models import (
    UserZoneProgress,
    UserTopicProficiency,
    UserSubtopicMastery
)
from content_ingestion.models import Topic, Subtopic, GameZone


def recalibrate_topic_proficiency(user, results: list):
    """
    Called after user pre-assessment or gameplay update.
    Updates:
      1. Topic proficiency (percentage)
      2. Subtopic mastery (percentage)
      3. Zone progression (unlock, advance, or revert)
    """

    # --- 1. Compute temporary score tracking ---
    topic_scores = defaultdict(lambda: {"correct": 0, "total": 0})
    subtopic_scores = defaultdict(lambda: {"correct": 0, "total": 0})

    for entry in results:
        q_id = entry.get("question_id")
        is_correct = entry.get("is_correct", False)

        try:
            question = PreAssessmentQuestion.objects.get(id=q_id)
        except PreAssessmentQuestion.DoesNotExist:
            continue

        # Aggregate topic scores
        for topic_id in question.topic_ids:
            topic_scores[topic_id]["total"] += 1
            if is_correct:
                topic_scores[topic_id]["correct"] += 1

        # Aggregate subtopic scores
        for sub_id in question.subtopic_ids:
            subtopic_scores[sub_id]["total"] += 1
            if is_correct:
                subtopic_scores[sub_id]["correct"] += 1

    # --- 2. Save topic proficiency ---
    for topic_id, data in topic_scores.items():
        if data["total"] == 0:
            continue

        pct = (data["correct"] / data["total"]) * 100
        topic = Topic.objects.filter(id=topic_id).first()
        if topic:
            UserTopicProficiency.objects.update_or_create(
                user=user,
                topic=topic,
                defaults={"proficiency_percent": pct},
            )

    # --- 3. Save subtopic mastery ---
    for sub_id, data in subtopic_scores.items():
        if data["total"] == 0:
            continue

        pct = (data["correct"] / data["total"]) * 100
        subtopic = Subtopic.objects.filter(id=sub_id).first()
        if subtopic:
            UserSubtopicMastery.objects.update_or_create(
                user=user,
                subtopic=subtopic,
                defaults={"mastery_level": pct},
            )

    # --- 4. Recalculate zone progress ---
    zones = GameZone.objects.all().order_by("order")
    user_progress_map = {
        up.zone_id: up for up in UserZoneProgress.objects.filter(user=user)
    }

    highest_unlocked_index = 0  # Always at least Zone 0
    for idx, zone in enumerate(zones):
        zone_topics = Topic.objects.filter(zone=zone)

        avg_proficiency = (
            UserTopicProficiency.objects
            .filter(user=user, topic__in=zone_topics)
            .aggregate(avg=Avg('proficiency_percent'))['avg'] or 0
        )

        # Update or create zone progress
        progress, _ = UserZoneProgress.objects.update_or_create(
            user=user,
            zone=zone,
            defaults={"completion_percent": avg_proficiency},
        )
        user_progress_map[zone.id] = progress

        # Only mark as "fully complete" if >= 100%
        if avg_proficiency >= 100:
            highest_unlocked_index = idx

    # --- 5. Determine current zone ---
    current_zone_index = highest_unlocked_index

    # Revert if current zone drops to 0% or below
    while current_zone_index > 0:
        current_zone = zones[current_zone_index]
        if user_progress_map[current_zone.id].completion_percent <= 0:
            current_zone_index -= 1
        else:
            break

    # --- 6. Lock info for frontend (optional) ---
    # You can annotate UserZoneProgress with `is_current` or `locked`
    for idx, zone in enumerate(zones):
        progress = user_progress_map[zone.id]
        progress.is_current = (idx == current_zone_index)  # For frontend use
        progress.locked = idx > current_zone_index          # For frontend use

    return current_zone_index  # Return index of current active zone
