from collections import defaultdict
from django.db.models import Avg
from question_generation.models import PreAssessmentQuestion
from user_learning.models import (
    UserZoneProgress,
    UserTopicProficiency,
    UserSubtopicMastery
)
from content_ingestion.models import Topic, Subtopic, GameZone

def recalibrate_topic_proficiency(user, results: list):
    """
    Recalibrate user topic proficiency and zone progression.
    Works for both pre-assessment and minigame results.
    """

    topic_scores = defaultdict(lambda: {"correct": 0, "total": 0})
    subtopic_scores = defaultdict(lambda: {"correct": 0, "total": 0})

    # --- 1️⃣ Aggregate scores ---
    for entry in results:
        is_correct = entry.get("is_correct", False)

        topic_ids = entry.get("topic_ids") or []
        subtopic_ids = entry.get("subtopic_ids") or []

        # Fallback: Load from PreAssessmentQuestion if missing
        if not topic_ids and not subtopic_ids:
            q_id = entry.get("question_id")
            try:
                question = PreAssessmentQuestion.objects.get(id=q_id)
                topic_ids = getattr(question, "topic_ids", [])
                subtopic_ids = getattr(question, "subtopic_ids", [])
            except PreAssessmentQuestion.DoesNotExist:
                continue

        for t_id in topic_ids:
            topic_scores[t_id]["total"] += 1
            if is_correct:
                topic_scores[t_id]["correct"] += 1

        for s_id in subtopic_ids:
            subtopic_scores[s_id]["total"] += 1
            if is_correct:
                subtopic_scores[s_id]["correct"] += 1

    # --- 2️⃣ Save topic proficiency ---
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

    # --- 3️⃣ Save subtopic mastery ---
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

    # --- 4️⃣ Update zone progression ---
    zones = GameZone.objects.all().order_by("order")
    user_progress_map = {
        up.zone_id: up for up in UserZoneProgress.objects.filter(user=user)
    }

    # Compute completion percent per zone
    zone_avgs = []
    for idx, zone in enumerate(zones):
        zone_topics = Topic.objects.filter(zone=zone)
        avg_proficiency = (
            UserTopicProficiency.objects
            .filter(user=user, topic__in=zone_topics)
            .aggregate(avg=Avg('proficiency_percent'))['avg'] or 0
        )
        progress, _ = UserZoneProgress.objects.update_or_create(
            user=user,
            zone=zone,
            defaults={"completion_percent": avg_proficiency},
        )
        progress.completion_percent = avg_proficiency
        user_progress_map[zone.id] = progress
        zone_avgs.append(avg_proficiency)

    # --- 5️⃣ Determine current zone ---
    # Rule:
    # - If this is first recalibration -> force start at zone 1
    # - Otherwise, current zone = first zone not 100% complete
    current_zone_index = 0
    if UserZoneProgress.objects.filter(user=user).count() > 0:
        for idx, avg in enumerate(zone_avgs):
            if avg < 100:
                current_zone_index = idx
                break
            else:
                current_zone_index = idx  # keep advancing if fully mastered

    # --- 6️⃣ Apply is_current & locked and save ---
    for idx, zone in enumerate(zones):
        progress = user_progress_map[zone.id]
        progress.is_current = (idx == current_zone_index)
        progress.locked = idx > current_zone_index
        progress.save(update_fields=["completion_percent", "is_current", "locked"])

    return current_zone_index
