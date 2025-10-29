from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser

from question_generation.utils.recalibrator import (
    recalibrate_difficulty_for_question,
    recalibrate_difficulty_by_type,
    recalibrate_difficulty_with_analytics,
)

@api_view(['POST'])
@permission_classes([IsAdminUser])
def recalibrate_question(request, question_id):
    """
    POST endpoint to trigger difficulty recalibration for a specific question by ID.
    """
    result = recalibrate_difficulty_for_question(question_id)
    return Response({"message": result})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def recalibrate_by_type(request, question_type):
    """
    POST endpoint to trigger recalibration for ALL questions of a given type.
    """
    result = recalibrate_difficulty_by_type(question_type)
    return Response({"message": result})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def recalibrate_with_analytics(request, question_id):
    """
    POST endpoint to trigger difficulty recalibration using performance analytics.
    """
    result = recalibrate_difficulty_with_analytics(question_id)
    return Response({"message": result})
