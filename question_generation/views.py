from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser

from question_generation.utils.recalibrator import recalibrate_difficulty_for_question


@api_view(['POST'])
@permission_classes([IsAdminUser])
def recalibrate_question(request, id):
    """
    POST endpoint to trigger difficulty recalibration for a specific question by ID.
    Only accessible to admin users.
    """
    result = recalibrate_difficulty_for_question(id)
    return Response({"message": result})
