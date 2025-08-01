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
    Only recalibrates subtopic mastery directly from results.
    Topic proficiency = avg(subtopic mastery)
    Zone completion = avg(topic proficiency)
    """
    subtopic_scores = defaultdict(lambda: {"correct": 0, "total": 0})

    # --- 1️⃣ Aggregate results for subtopics ---
    for entry in results:
        is_correct = entry.get("is_correct", False)
        subtopic_ids = entry.get("subtopic_ids") or []
        topic_ids = entry.get("topic_ids") or []

        # Fallback to PreAssessmentQuestion mapping
        if not topic_ids and not subtopic_ids:
            q_id = entry.get("question_id")
            try:
                question = PreAssessmentQuestion.objects.get(id=q_id)
                topic_ids = getattr(question, "topic_ids", [])
                subtopic_ids = getattr(question, "subtopic_ids", [])
            except PreAssessmentQuestion.DoesNotExist:
                continue

        for s_id in subtopic_ids:
            subtopic_scores[s_id]["total"] += 1
            if is_correct:
                subtopic_scores[s_id]["correct"] += 1

    # --- 2️⃣ Update subtopic mastery ---
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

    # --- 3️⃣ Recalculate topic proficiency from subtopics ---
    for topic in Topic.objects.all():
        topic_subtopics = Subtopic.objects.filter(topic=topic)
        avg_mastery = (
            UserSubtopicMastery.objects
            .filter(user=user, subtopic__in=topic_subtopics)
            .aggregate(avg=Avg('mastery_level'))['avg'] or 0
        )
        UserTopicProficiency.objects.update_or_create(
            user=user,
            topic=topic,
            defaults={"proficiency_percent": avg_mastery},
        )

    # --- 4️⃣ Recalculate zone completion from topics ---
    for zone in GameZone.objects.all().order_by("order"):
        zone_topics = Topic.objects.filter(zone=zone)
        avg_proficiency = (
            UserTopicProficiency.objects
            .filter(user=user, topic__in=zone_topics)
            .aggregate(avg=Avg('proficiency_percent'))['avg'] or 0
        )
        UserZoneProgress.objects.update_or_create(
            user=user,
            zone=zone,
            defaults={"completion_percent": avg_proficiency},
        )

    # ✅ Returns nothing, since recalibration is fully data-driven
