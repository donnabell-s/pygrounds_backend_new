# user_learning/adaptive_engine.py

from question_generation.models import PreAssessmentQuestion
from user_learning.models import UserTopicProficiency, UserSubtopicMastery
from content_ingestion.models import Topic, Subtopic

from collections import defaultdict

def recalibrate_topic_proficiency(user, results: list):
    """
    Called after user registers and submits pre-assessment.
    Recalculates initial topic and subtopic scores.
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

        # Track per-topic
        for topic_id in question.topic_ids:
            topic_scores[topic_id]["total"] += 1
            if is_correct:
                topic_scores[topic_id]["correct"] += 1

        # Track per-subtopic (optional)
        for sub_id in question.subtopic_ids:
            subtopic_scores[sub_id]["total"] += 1
            if is_correct:
                subtopic_scores[sub_id]["correct"] += 1

    # Save topic proficiency
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

    # Save subtopic mastery (optional but useful for adaptive pathing)
    for sub_id, data in subtopic_scores.items():
        try:
            subtopic = Subtopic.objects.get(id=sub_id)
            UserSubtopicMastery.objects.update_or_create(
                user=user,
                subtopic=subtopic,
                defaults={
                    "correct": data["correct"],
                    "attempts": data["total"],
                },
            )
        except Subtopic.DoesNotExist:
            continue
