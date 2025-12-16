from django.db.models import Avg
from django.apps import apps

# NEW: import IRT utilities
from analytics.irt_utils import recalibrate_item_irt

LEVELS = ["beginner", "intermediate", "advanced", "master"]


# -----------------------------------------------------------
#  Resolve Question + Response Models
# -----------------------------------------------------------

def _get_question_model():
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
    raise LookupError("No suitable Question model found.")


def _get_question_response_model():
    try:
        return apps.get_model("minigames", "QuestionResponse")
    except LookupError:
        return None



#  OLD METHOD (Score-based recalibration)
#  – still used as fallback

def recalibrate_difficulty_for_question(question_id: int) -> str:
    """
    Simple score-based recalibration. Kept for fallback use.
    """
    Question = _get_question_model()

    try:
        q = Question.objects.get(pk=question_id)
    except Question.DoesNotExist:
        return "Question not found."

    QuestionResponse = _get_question_response_model()
    if QuestionResponse is None:
        return "Analytics app not installed; cannot recalibrate."

    responses = QuestionResponse.objects.filter(question=q)
    total = responses.count()

    if total < 5:
        return "Not enough responses to recalibrate (need ≥5)."

    avg_score = responses.aggregate(val=Avg("score"))["val"] or 0

    if avg_score < 0.30:
        new_diff = "master"
    elif avg_score < 0.60:
        new_diff = "advanced"
    elif avg_score < 0.80:
        new_diff = "intermediate"
    else:
        new_diff = "beginner"

    prev = getattr(q, "estimated_difficulty", None)
    if prev != new_diff:
        q.estimated_difficulty = new_diff
        q.save(update_fields=["estimated_difficulty"])
        return f"[Simple] Recalibrated to {new_diff.capitalize()}."

    return "[Simple] No recalibration needed."


#  ** NEW — IRT RECALIBRATION 

def recalibrate_irt_for_question(question_id: int) -> str:
    """
    Calls the 2PL IRT recalibration logic.
    Returns human-readable result message.
    """
    try:
        msg = recalibrate_item_irt(question_id)
        return f"[IRT] {msg}"
    except Exception as e:
        return f"[IRT ERROR] {str(e)}"


#  ** NEW — Bulk IRT Recalibration for all minigames **

def recalibrate_irt_bulk() -> str:
    """
    Recalibrate ALL GeneratedQuestion items using IRT.
    Only applies to coding/non_coding items.
    """
    Question = _get_question_model()

    questions = Question.objects.filter(game_type__in=["coding", "non_coding"])
    total = questions.count()

    success = 0
    skipped = 0

    for q in questions:
        result = recalibrate_item_irt(q.id)

        if "not enough responses" in result.lower():
            skipped += 1
        elif "done" in result.lower():
            success += 1

    return (
        f"IRT recalibration completed.\n"
        f"Successfully updated: {success}\n"
        f"Skipped (insufficient data): {skipped}\n"
        f"Total items: {total}"
    )
