from django.db.models import Avg
from django.apps import apps
from django.db import models
from question_generation.models import GeneratedQuestion, PreAssessmentQuestion
from analytics.models import QuestionResponse, QuestionRecalibration
import math

LEVELS = ["beginner", "intermediate", "advanced", "master"]


def _get_question_model():
    return GeneratedQuestion


def _get_question_response_model():
    try:
        return apps.get_model("analytics", "QuestionResponse")
    except LookupError:
        return None



def assign_initial_difficulty(question_text: str, author_tag: str = None) -> str:
    text = (question_text or "").lower().strip()
    word_count = len(text.split())

    recursion_keywords = ["recursion", "recursive", "nested function", "nested call", "nested loop"]
    loop_keywords = ["for", "while", "loop", "iteration"]

    if any(k in text for k in recursion_keywords):
        return "advanced"
    elif any(k in text for k in loop_keywords):
        return "intermediate"
    elif word_count < 10:
        return "beginner"
    else:
        return "intermediate"




# ------------------------------
# Algorithm 2 – Analytics-based recalibration
# ------------------------------
def recalibrate_difficulty_with_analytics(question_id: int):
    try:
        question = GeneratedQuestion.objects.get(id=question_id)
    except GeneratedQuestion.DoesNotExist:
        return f"Question {question_id} not found."

    responses = QuestionResponse.objects.filter(question=question)

    # Not enough analytics data
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

    old_difficulty = question.recalibrated_difficulty or question.estimated_difficulty
    if new_difficulty != old_difficulty:
        QuestionRecalibration.objects.create(
            question=question,
            old_difficulty=old_difficulty,
            new_difficulty=new_difficulty
        )
        question.recalibrated_difficulty = new_difficulty
        question.validation_status = "processed"
        question.save(update_fields=["recalibrated_difficulty", "validation_status"])
        return f"Recalibrated to {new_difficulty}."
    else:
        question.validation_status = "processed"
        question.save(update_fields=["validation_status"])
        return "No recalibration needed (already optimal)."


# ------------------------------
# Algorithm 3 – Bayesian Probabilistic Recalibration
# ------------------------------
def bayesian_recalibration(question_id: int):
    """
    Adaptive recalibration using Bayesian inference.
    Updates difficulty probabilities based on user performance history.
    """

    try:
        question = GeneratedQuestion.objects.get(id=question_id)
    except GeneratedQuestion.DoesNotExist:
        return f"Question {question_id} not found."

    responses = QuestionResponse.objects.filter(question=question)
    n = responses.count()

    if n < 5:
        return "Not enough responses for Bayesian recalibration (need ≥5)."

    # --- Initialize priors for each difficulty ---
    priors = {
        "beginner": 0.25,
        "intermediate": 0.25,
        "advanced": 0.25,
        "master": 0.25,
    }

    # --- Likelihoods (how probable a good score is for each difficulty) ---
    likelihoods = {
        "beginner": 0.9,
        "intermediate": 0.7,
        "advanced": 0.5,
        "master": 0.3,
    }

    # --- Process each response as evidence ---
    for r in responses:
        score = r.score or 0
        correct_prob = score  # interpret score as confidence level

        for lvl in LEVELS:
            # P(E|D) using score influence (higher score = easier)
            likelihood = (correct_prob * likelihoods[lvl]) + (1 - correct_prob) * (1 - likelihoods[lvl])
            priors[lvl] *= likelihood

        # Normalize after each response (Bayes normalization)
        total = sum(priors.values())
        for lvl in LEVELS:
            priors[lvl] /= total

    # --- Select difficulty with highest posterior probability ---
    new_difficulty = max(priors, key=priors.get)
    old_difficulty = question.recalibrated_difficulty or question.estimated_difficulty

    # --- Update if changed ---
    if new_difficulty != old_difficulty:
        QuestionRecalibration.objects.create(
            question=question,
            old_difficulty=old_difficulty,
            new_difficulty=new_difficulty
        )
        question.recalibrated_difficulty = new_difficulty
        question.validation_status = "processed"
        question.save(update_fields=["recalibrated_difficulty", "validation_status"])
        return f"[Bayesian] Recalibrated to {new_difficulty}."
    else:
        question.validation_status = "processed"
        question.save(update_fields=["validation_status"])
        return "[Bayesian] No change (posterior stable)."


# ------------------------------
# Combined entrypoint (Algorithm 1 + 2)
# ------------------------------
def get_or_recalibrate_difficulty(sender=None, instance=None, created=False, **kwargs):
    if instance is None:
        return "No instance provided."

    question = getattr(instance, "question", None)
    if question is None:
        return "Invalid instance: no question attached."

    responses = QuestionResponse.objects.filter(question=question)

    if responses.count() < 5:
        new_difficulty = assign_initial_difficulty(
            getattr(question, "question_text", ""),
            getattr(question, "estimated_difficulty", None)
        )

        if question.recalibrated_difficulty != new_difficulty:
            old_difficulty = question.recalibrated_difficulty or question.estimated_difficulty
            question.recalibrated_difficulty = new_difficulty
            QuestionRecalibration.objects.create(
                question=question,
                old_difficulty=old_difficulty,
                new_difficulty=new_difficulty
            )

        question.validation_status = "processed"
        question.save(update_fields=["recalibrated_difficulty", "validation_status"])
        return f"Assigned initial difficulty ({new_difficulty})."

    # Switch to Bayesian recalibration if enough data
    return bayesian_recalibration(question.id)


# ------------------------------
# Manual trigger for a specific question
# ------------------------------
def recalibrate_difficulty_for_question(question_id: int) -> str:
    Question = _get_question_model()
    try:
        q = Question.objects.get(pk=question_id)
    except Question.DoesNotExist:
        return "Question not found."

    # Use Bayesian recalibration as the default
    msg = bayesian_recalibration(q.id)
    q.validation_status = "processed"
    q.save(update_fields=["validation_status"])
    return msg


# ------------------------------
# Recalibrate by question type (bulk)
# ------------------------------
def recalibrate_difficulty_by_type(question_type: str) -> str:
    """
    Handles recalibration for different question categories:
    - coding / non_coding / minigame → GeneratedQuestion
    - preassessment → PreAssessmentQuestion
    """
    mapped_type = question_type.replace("_", " ").title()

    # 🔹 For pre-assessment
    if question_type == "preassessment":
        questions = PreAssessmentQuestion.objects.all()
        updated_count = 0

        for q in questions:
            new_difficulty = assign_initial_difficulty(q.question_text, q.estimated_difficulty)
            if q.estimated_difficulty != new_difficulty:
                q.estimated_difficulty = new_difficulty
                q.save(update_fields=["estimated_difficulty"])
                updated_count += 1

        if updated_count == 0:
            return "All pre-assessment questions are already up-to-date (no changes made)."
        else:
            return f"Successfully recalibrated {updated_count} pre-assessment question(s)."

    # 🔹 For minigame (coding/non_coding)
    elif question_type in ["minigame", "coding", "non_coding"]:
        questions = GeneratedQuestion.objects.filter(game_type__in=["coding", "non_coding"])
        updated_count = 0

        for q in questions:
            new_difficulty = assign_initial_difficulty(q.question_text, q.estimated_difficulty)
            if q.estimated_difficulty != new_difficulty or q.validation_status != "processed":
                q.estimated_difficulty = new_difficulty
                q.validation_status = "processed"  # ✅ mark as processed after recalibration
                q.save(update_fields=["estimated_difficulty", "validation_status"])
                updated_count += 1

        if updated_count == 0:
            return "All minigame questions are already up-to-date (no changes made)."
        else:
            return f"Successfully recalibrated {updated_count} minigame question(s)."

    # 🔹 If unknown type
    else:
        return f"Unsupported question type: {question_type}"
