from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Avg


from minigames.models import Question
from analytics.models import QuestionResponse
from question_generation.utils.recalibrator import recalibrate_difficulty_for_question


@api_view(['POST'])
@permission_classes([IsAdminUser]) 
def recalibrate_question(request, question_id: int):
    """
    Trigger recalibration for a specific Minigame Question (by ID).
    Returns before/after difficulty ug basic stats.
    """
    try:
        q = Question.objects.get(id=question_id)
    except Question.DoesNotExist:
        return Response({"detail": "Question not found."}, status=status.HTTP_404_NOT_FOUND)

    prev = q.difficulty

    msg = recalibrate_difficulty_for_question(question_id)

    q.refresh_from_db()

    responses = QuestionResponse.objects.filter(question=q)
    total = responses.count()
    avg_score = responses.aggregate(val=Avg('score'))['val'] if total else None

    payload = {
        "id": q.id,
        "message": msg,
        "prev_difficulty": prev,
        "new_difficulty": q.difficulty,
        "changed": prev != q.difficulty,
        "stats": {
            "total_responses": total,
            "average_score": avg_score,
        },
    }
    return Response(payload, status=status.HTTP_200_OK)
