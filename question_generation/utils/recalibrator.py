from django.db.models import Avg
from django.apps import apps
from django.db import models
from question_generation.models import GeneratedQuestion
from analytics.models import QuestionResponse, QuestionRecalibration

LEVELS = ["beginner", "intermediate", "advanced", "master"]


def _get_question_model():
    return GeneratedQuestion


def _get_question_response_model():
    try:
        return apps.get_model("analytics", "QuestionResponse")
    except LookupError:
        return None


# ------------------------------
# Initial assignment (Algorithm 1)
# ------------------------------
def assign_initial_difficulty(question_text: str, author_tag: str = None) -> str:
    if author_tag in LEVELS:
        return author_tag

    text = (question_text or "").lower()
    word_count = len(text.split())

    if word_count < 10:
        return "beginner"
    elif "recursion" in text or "nested" in text:
        return "advanced"
    elif "for" in text or "while" in text or "loop" in text:
        return "intermediate"
    else:
        return "intermediate"


# ------------------------------
# Algorithm 2: Analytics-based recalibration
# ------------------------------
def recalibrate_difficulty_with_analytics(question_id: int):
    try:
        question = GeneratedQuestion.objects.get(id=question_id)
    except GeneratedQuestion.DoesNotExist:
        return f"Question {question_id} not found."

    responses = QuestionResponse.objects.filter(question=question)

    if responses.count() < 5:
        return "Not enough responses to recalibrate (need ≥5)."

    avg_score = responses.aggregate(avg=models.Avg("score"))["avg"]

    if avg_score < 0.3:
        new_difficulty = "beginner"
    elif avg_score < 0.6:
        new_difficulty = "intermediate"
    elif avg_score < 0.85:
        new_difficulty = "advanced"
    else:
        new_difficulty = "master"

    # Dual storage + history logging
    old_difficulty = question.recalibrated_difficulty or question.estimated_difficulty
    if new_difficulty != old_difficulty:
        QuestionRecalibration.objects.create(
            question=question,
            old_difficulty=old_difficulty,
            new_difficulty=new_difficulty
        )
        question.recalibrated_difficulty = new_difficulty
        question.save(update_fields=["recalibrated_difficulty"])
        return f"Recalibrated to {new_difficulty}."
    else:
        return "No recalibration needed."


# ------------------------------
# Combined entrypoint (used by signals)
# ------------------------------
def get_or_recalibrate_difficulty(sender=None, instance=None, created=False, **kwargs):
    if instance is None:
        return "No instance provided."

    question = getattr(instance, "question", None)
    if question is None:
        return "Invalid instance: no question attached."

    responses = QuestionResponse.objects.filter(question=question)

    if responses.count() < 5:
        # Algorithm 1: Initial assignment
        new_difficulty = assign_initial_difficulty(
            getattr(question, "question_text", ""),
            getattr(question, "estimated_difficulty", None)
        )
        if question.recalibrated_difficulty != new_difficulty:
            old_difficulty = question.recalibrated_difficulty or question.estimated_difficulty
            question.recalibrated_difficulty = new_difficulty
            question.save(update_fields=["recalibrated_difficulty"])

            QuestionRecalibration.objects.create(
                question=question,
                old_difficulty=old_difficulty,
                new_difficulty=new_difficulty
            )
        return f"Assigned initial difficulty ({new_difficulty})."

    # Algorithm 2
    return recalibrate_difficulty_with_analytics(question.id)


# ------------------------------
# Manual trigger for a specific question
# ------------------------------
def recalibrate_difficulty_for_question(question_id: int) -> str:
    Question = _get_question_model()
    try:
        q = Question.objects.get(pk=question_id)
    except Question.DoesNotExist:
        return "Question not found."
    return recalibrate_difficulty_with_analytics(q.id)


# ------------------------------
# Stub: Recalibrate by type
# ------------------------------
def recalibrate_difficulty_by_type(question_type: str) -> str:
    if question_type not in ["coding", "non_coding", "preassessment"]:
        return f"Invalid question type: {question_type}"
    return f"Recalibration triggered for all {question_type} questions."
