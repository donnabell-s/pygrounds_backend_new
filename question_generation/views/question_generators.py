from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count
from django.db import transaction
from django.shortcuts import get_object_or_404
from content_ingestion.models import Subtopic, Topic
from .question_api import generate_pre_assessment

from ..models import PreAssessmentQuestion, GeneratedQuestion
from ..serializers import PreAssessmentQuestionSerializer, GeneratedQuestionSerializer
from ..helpers.generation_core import generate_questions_for_subtopic_combination

import logging
logger = logging.getLogger(__name__)

@api_view(['POST'])
def generate_preassessment_only(request):
    # Preassessment generation
    # Parameters:
    # - topic_id (int): array of topic ids ,set name REQ
    # - count (int): num of questions to ratio according to list of topics
    try:
        topic_id = request.data.get('topic_id')
        count = request.data.get('count', 5)

        if not topic_id:
            return Response(
                {'error': 'topic_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        topic = get_object_or_404(Topic, id=topic_id)
        result = generate_pre_assessment({'topic_ids': [topic_id], 'total_questions': count})
        questions = result.get('questions', [])
        
        return Response({
            'message': f'Successfully generated {len(questions)} preassessment questions',
            'questions': questions
        })
    except Exception as e:
        logger.error(f"Error generating preassessment questions: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def generate_coding_questions_only(request):
    # Minigames coding questions
    # Parameters:
    # - subtopic_id (int): array of subtopici ids   
    # - count (int): num of questions per subtopic: 
    try:
        subtopic_id = request.data.get('subtopic_id')
        count = request.data.get('count', 3)

        if not subtopic_id:
            return Response(
                {'error': 'subtopic_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        subtopic = get_object_or_404(Subtopic, id=subtopic_id)
        questions = generate_questions_for_subtopic_combination(
            subtopic_combination=[subtopic],
            difficulty='beginner',  # Default difficulty for now
            num_questions=count,
            game_type='coding',
            zone=subtopic.topic.zone
        )
        serializer = GeneratedQuestionSerializer(questions, many=True)
        
        return Response({
            'message': f'Successfully generated {len(questions)} coding questions',
            'questions': serializer.data
        })
    except Exception as e:
        logger.error(f"Error generating coding questions: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def generate_noncoding_questions_only(request):
    # Minigames Non coding
    # Parameters:
    # - subtopic_id (int):array of subtopic ids
    # - count (int): num of questions
    try:
        subtopic_id = request.data.get('subtopic_id')
        count = request.data.get('count', 3)

        if not subtopic_id:
            return Response(
                {'error': 'subtopic_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        subtopic = get_object_or_404(Subtopic, id=subtopic_id)
        questions = generate_questions_for_subtopic_combination(
            subtopic_combination=[subtopic],
            difficulty='beginner',  # Default difficulty for now
            num_questions=count,
            game_type='non_coding',
            zone=subtopic.topic.zone
        )
        serializer = GeneratedQuestionSerializer(questions, many=True)
        
        return Response({
            'message': f'Successfully generated {len(questions)} non-coding questions',
            'questions': serializer.data
        })
    except Exception as e:
        logger.error(f"Error generating non-coding questions: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
