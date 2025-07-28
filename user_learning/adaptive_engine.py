# user_learning/adaptive_engine.py
from django.db import models


from question_generation.models import PreAssessmentQuestion
from user_learning.models import UserTopicProficiency, UserSubtopicMastery, UserZoneProgress
from content_ingestion.models import Topic, Subtopic, GameZone
from collections import defaultdict

def recalibrate_topic_proficiency(user, results: list):
    """
    Called after user registers and submits pre-assessment.
    Calculates simplified topic proficiency (percentage-based) for frontend display,
    detailed subtopic mastery for backend adaptive use,
    and recalibrates zone progress based on topic proficiency.
    """

    topic_scores = defaultdict(lambda: {"correct": 0, "total": 0})
    subtopic_scores = defaultdict(lambda: {"correct": 0, "total": 0})

    for entry in results:
        q_id = entry.get("question_id")
        is_correct = entry.get("is_correct", False)

        try:
            question = PreAssessmentQuestion.objects.get(id=q_id)
        except PreAssessmentQuestion.DoesNotExist:
            continue

        for topic_id in question.topic_ids:
            topic_scores[topic_id]["total"] += 1
            if is_correct:
                topic_scores[topic_id]["correct"] += 1

        for sub_id in question.subtopic_ids:
            subtopic_scores[sub_id]["total"] += 1
            if is_correct:
                subtopic_scores[sub_id]["correct"] += 1

    # Save simplified topic proficiency
    for topic_id, data in topic_scores.items():
        try:
            topic = Topic.objects.get(id=topic_id)
            pct = (data["correct"] / data["total"]) * 100
            UserTopicProficiency.objects.update_or_create(
                user=user,
                topic=topic,
                defaults={"proficiency_percent": pct},
            )
        except Topic.DoesNotExist:
            continue

    # Save detailed subtopic mastery
    for sub_id, data in subtopic_scores.items():
        try:
            subtopic = Subtopic.objects.get(id=sub_id)
            pct = (data["correct"] / data["total"]) * 100
            UserSubtopicMastery.objects.update_or_create(
                user=user,
                subtopic=subtopic,
                defaults={"mastery_level": pct},
            )
        except Subtopic.DoesNotExist:
            continue

    # Recalibrate zone progress and completion percent
    zones = GameZone.objects.all().order_by('order')

    for idx, zone in enumerate(zones):
        zone_topics = Topic.objects.filter(zone=zone)
        if not zone_topics.exists():
            continue

        avg_proficiency = (
            UserTopicProficiency.objects
            .filter(user=user, topic__in=zone_topics)
            .aggregate(avg_pct=models.Avg('proficiency_percent'))['avg_pct'] or 0
        )

        # Always unlock the first zone
        if idx == 0:
            UserZoneProgress.objects.update_or_create(
                user=user,
                zone=zone,
                defaults={'completion_percent': avg_proficiency}
            )
            continue

        if avg_proficiency >= 70:  # Threshold for unlocking subsequent zones
            UserZoneProgress.objects.update_or_create(
                user=user,
                zone=zone,
                defaults={'completion_percent': avg_proficiency}
            )


