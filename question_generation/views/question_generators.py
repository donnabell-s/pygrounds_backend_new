from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from content_ingestion.models import Subtopic, Topic
from ..serializers import GeneratedQuestionSerializer
from ..helpers.generation_core import generate_questions_for_subtopic_combination

import logging
logger = logging.getLogger(__name__)


# ============================================================
# SOLO GENERATORS  (single-subtopic, synchronous)
# ============================================================

@api_view(['POST'])
def generate_preassessment_only(request):
    """
    Request body:
        topic_id - required
        count    - number of questions (default: 5)
    """
    try:
        topic_id = request.data.get('topic_id')
        count = request.data.get('count', 5)

        if not topic_id:
            return Response({'error': 'topic_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        get_object_or_404(Topic, id=topic_id)

        from .question_api import generate_pre_assessment
        result = generate_pre_assessment({'topic_ids': [topic_id], 'total_questions': count})
        questions = result.get('questions', [])

        return Response({
            'message': f'Successfully generated {len(questions)} preassessment questions',
            'questions': questions,
        })

    except Exception as e:
        logger.error(f"Error generating preassessment questions: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def generate_coding_questions_only(request):
    """
    Request body:
        subtopic_id - required
        count       - number of questions (default: 3)
    """
    try:
        subtopic_id = request.data.get('subtopic_id')
        count = request.data.get('count', 3)

        if not subtopic_id:
            return Response({'error': 'subtopic_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        subtopic = get_object_or_404(Subtopic, id=subtopic_id)
        result = generate_questions_for_subtopic_combination(
            subtopic_combination=[subtopic],
            difficulty='beginner',
            num_questions=count,
            game_type='coding',
            zone=subtopic.topic.zone,
        )

        if not result['success']:
            return Response(
                {'error': f"Generation failed: {result.get('error', 'Unknown error')}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = GeneratedQuestionSerializer(result.get('saved_questions', []), many=True)
        return Response({
            'message': f'Successfully generated {result["questions_saved"]} coding questions',
            'questions': serializer.data,
            'generation_stats': {
                'questions_generated': result['questions_generated'],
                'questions_saved':     result['questions_saved'],
                'duplicates_skipped':  result.get('duplicates_skipped', 0),
            },
        })

    except Exception as e:
        logger.error(f"Error generating coding questions: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def generate_noncoding_questions_only(request):
    """
    Request body:
        subtopic_id - required
        count       - number of questions (default: 3)
    """
    try:
        subtopic_id = request.data.get('subtopic_id')
        count = request.data.get('count', 3)

        if not subtopic_id:
            return Response({'error': 'subtopic_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        subtopic = get_object_or_404(Subtopic, id=subtopic_id)
        result = generate_questions_for_subtopic_combination(
            subtopic_combination=[subtopic],
            difficulty='beginner',
            num_questions=count,
            game_type='non_coding',
            zone=subtopic.topic.zone,
        )

        if not result['success']:
            return Response(
                {'error': f"Generation failed: {result.get('error', 'Unknown error')}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = GeneratedQuestionSerializer(result.get('saved_questions', []), many=True)
        return Response({
            'message': f'Successfully generated {result["questions_saved"]} non-coding questions',
            'questions': serializer.data,
            'generation_stats': {
                'questions_generated': result['questions_generated'],
                'questions_saved':     result['questions_saved'],
                'duplicates_skipped':  result.get('duplicates_skipped', 0),
            },
        })

    except Exception as e:
        logger.error(f"Error generating non-coding questions: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
