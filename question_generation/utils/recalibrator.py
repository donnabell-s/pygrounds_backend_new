from django.db.models import Avg
from django.apps import apps

LEVELS = ["beginner", "intermediate", "advanced", "master"]


def _get_question_model():
    """
    Resolve a Question-like model in this order:
      1) question_generation.GeneratedQuestion
      2) question_generation.Question
      3) minigames.Question
    """
    candidates = [
        ("question_generation", "GeneratedQuestion"),
        ("question_generation", "Question"),
        ("minigames", "Question"),
    ]
    for app_label, model_name in candidates:
        try:
            model = apps.get_model(app_label, model_name)
            if model:
                return model
        except LookupError:
            continue
    raise LookupError(
        "No suitable Question model found "
        "(tried question_generation.GeneratedQuestion / Question / minigames.Question)."
    )


def _get_question_response_model():
    """
    Try to load analytics.QuestionResponse (optional app).
    Returns None if analytics is not installed.
    """
    try:
        return apps.get_model("analytics", "QuestionResponse")
    except LookupError:
        return None


def recalibrate_difficulty_for_question(question_id: int) -> str:
    """
    Score-based recalibration (expects analytics.QuestionResponse.score in [0,1]):

      avg_score < 0.30  -> 'master'
      avg_score < 0.60  -> 'advanced'
      avg_score < 0.80  -> 'intermediate'
      else              -> 'beginner'

    Requires at least 5 responses. If the analytics app is not present,
    we skip recalibration gracefully.
    """
    Question = _get_question_model()

    try:
        q = Question.objects.get(pk=question_id)
    except Question.DoesNotExist:
        return "Question not found."

    QuestionResponse = _get_question_response_model()
    if QuestionResponse is None:
        return "Analytics app not installed; cannot recalibrate."

    qs = QuestionResponse.objects.filter(question=q)
    total = qs.count()
    if total < 5:
        return "Not enough responses to recalibrate (need ≥5)."

    avg_score = qs.aggregate(val=Avg("score"))["val"] or 0.0

    if avg_score < 0.30:
        new_diff = "master"
    elif avg_score < 0.60:
        new_diff = "advanced"
    elif avg_score < 0.80:
        new_diff = "intermediate"
    else:
        new_diff = "beginner"

    prev = getattr(q, "difficulty", None)
    if prev != new_diff:
        q.difficulty = new_diff
        try:
            q.save(update_fields=["difficulty"])
        except Exception:
            q.save()
        return f"Recalibrated to {new_diff.capitalize()}."
    return "No recalibration needed."
