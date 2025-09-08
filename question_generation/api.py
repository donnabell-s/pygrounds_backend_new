from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Avg
from django.apps import apps

def _get_question_response_model():
    try:
        return apps.get_model("analytics", "QuestionResponse")
    except LookupError:
        return None

def _get_question_model():
    for app_label, model_name in [
        ("question_generation", "GeneratedQuestion"),
        ("question_generation", "Question"),
        ("minigames", "Question"),
    ]:
        try:
            model = apps.get_model(app_label, model_name)
            if model is not None:
                return model
        except LookupError:
            continue
    raise LookupError(
        "No suitable Question model found (looked for "
        "question_generation.GeneratedQuestion / Question / minigames.Question)."
    )

from question_generation.utils.recalibrator import recalibrate_difficulty_for_question


@api_view(["POST"])
@permission_classes([IsAdminUser])
def recalibrate_question(request, question_id: int):
    """
    Trigger difficulty recalibration for a specific question by ID.
    Works whether you're using question_generation.*Question or minigames.Question.
    If analytics app is missing, stats will be None.
    """
    QuestionModel = _get_question_model()
    try:
        q = QuestionModel.objects.get(pk=question_id)
    except QuestionModel.DoesNotExist:
        return Response({"detail": "Question not found."}, status=status.HTTP_404_NOT_FOUND)

    prev = getattr(q, "difficulty", None)

    # Run recalibration (function should update the record in DB)
    msg = recalibrate_difficulty_for_question(question_id)

    try:
        q.refresh_from_db()
    except Exception:
        pass

    total = None
    avg_score = None
    QuestionResponse = _get_question_response_model()
    if QuestionResponse is not None:
        try:
            responses = QuestionResponse.objects.filter(question=q)
            total = responses.count()
            avg_score = responses.aggregate(val=Avg("score"))["val"] if total else None
        except Exception:
            total = None
            avg_score = None

    payload = {
        "id": getattr(q, "id", question_id),
        "message": msg,
        "prev_difficulty": prev,
        "new_difficulty": getattr(q, "difficulty", None),
        "changed": (prev != getattr(q, "difficulty", None)),
        "stats": {
            "total_responses": total,
            "average_score": avg_score,
        },
    }
    return Response(payload, status=status.HTTP_200_OK)
