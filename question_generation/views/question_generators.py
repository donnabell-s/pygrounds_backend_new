import uuid
import logging
from typing import List, Dict, Any

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from content_ingestion.models import Subtopic, Topic
from ..models import GeneratedQuestion
from ..serializers import GeneratedQuestionSerializer
from ..helpers.parallel_workers import run_subtopic_specific_generation
from ..helpers.common_utils import (
    validate_positive_integer, 
    validate_string_list, 
    create_error_response, 
    create_success_response
)
from .question_api import generate_pre_assessment

logger = logging.getLogger(__name__)


# Utility functions for better code organization and reusability

def validate_difficulty_levels(difficulty_levels: List[str]) -> tuple[bool, str]:
    """
    Validate difficulty levels array.
    
    Returns:
        (is_valid, error_message)
    """
    valid_difficulties = ['beginner', 'intermediate', 'advanced', 'master']
    
    if not isinstance(difficulty_levels, list):
        return False, 'difficulty_levels must be an array'
    
    if not difficulty_levels:
        return False, 'difficulty_levels cannot be empty'
    
    invalid_difficulties = [d for d in difficulty_levels if d not in valid_difficulties]
    if invalid_difficulties:
        return False, f'Invalid difficulty levels: {invalid_difficulties}. Valid options: {valid_difficulties}'
    
    return True, ''


def validate_subtopic_ids(subtopic_ids: List[int]) -> tuple[bool, str, List[Subtopic]]:
    """
    Validate subtopic IDs and return subtopic objects.
    
    Returns:
        (is_valid, error_message, subtopics_list)
    """
    if not subtopic_ids:
        return False, 'subtopic_ids is required', []
    
    if not isinstance(subtopic_ids, list):
        return False, 'subtopic_ids must be an array', []
    
    # Verify subtopics exist
    subtopics = list(Subtopic.objects.filter(id__in=subtopic_ids))
    if len(subtopics) != len(subtopic_ids):
        found_ids = [s.id for s in subtopics]
        missing_ids = [sid for sid in subtopic_ids if sid not in found_ids]
        return False, f'Subtopics not found: {missing_ids}', []
    
    return True, '', subtopics


def create_generation_summary(subtopics: List[Subtopic], 
                            difficulty_levels: List[str], 
                            num_questions_per_subtopic: int) -> Dict[str, Any]:
    """
    Create a generation summary for API response.
    """
    expected_per_difficulty = len(subtopics) * num_questions_per_subtopic
    expected_total = expected_per_difficulty * len(difficulty_levels)
    
    return {
        'subtopic_count': len(subtopics),
        'subtopic_names': [s.name for s in subtopics],
        'difficulty_levels': difficulty_levels,
        'questions_per_subtopic': num_questions_per_subtopic,
        'expected_questions_per_difficulty': expected_per_difficulty,
        'expected_total_questions': expected_total
    }


def get_recent_questions(subtopic_ids: List[int], game_type: str, limit: int = 50) -> List[GeneratedQuestion]:
    """
    Get recently generated questions for the response.
    """
    return GeneratedQuestion.objects.filter(
        subtopic_id__in=subtopic_ids,
        game_type=game_type
    ).order_by('-id')[:limit]


def generate_questions_for_game_type(subtopic_ids: List[int],
                                   difficulty_levels: List[str],
                                   num_questions_per_subtopic: int,
                                   game_type: str) -> Dict[str, Any]:
    """
    Core logic for generating questions for any game type.
    
    Returns:
        Dictionary with generation results
    """
    # Validate inputs
    is_valid_diff, diff_error = validate_difficulty_levels(difficulty_levels)
    if not is_valid_diff:
        return {'success': False, 'error': diff_error}
    
    is_valid_sub, sub_error, subtopics = validate_subtopic_ids(subtopic_ids)
    if not is_valid_sub:
        return {'success': False, 'error': sub_error}
    
    # Generate session ID and start generation
    session_id = str(uuid.uuid4())
    
    logger.info(f"🚀 Starting {game_type} question generation for session {session_id}")
    logger.info(f"   Subtopics: {subtopic_ids}")
    logger.info(f"   Difficulties: {difficulty_levels}")
    logger.info(f"   Questions per subtopic: {num_questions_per_subtopic}")
    
    try:
        # Run the enhanced generation
        run_subtopic_specific_generation(
            subtopic_ids=subtopic_ids,
            difficulty_levels=difficulty_levels,
            num_questions_per_subtopic=num_questions_per_subtopic,
            game_type=game_type,
            session_id=session_id
        )
        
        # Get generated questions for response
        questions = get_recent_questions(subtopic_ids, game_type)
        generation_summary = create_generation_summary(subtopics, difficulty_levels, num_questions_per_subtopic)
        
        return {
            'success': True,
            'session_id': session_id,
            'message': f'Successfully generated {game_type} questions for {len(subtopics)} subtopics across {len(difficulty_levels)} difficulty levels',
            'generation_summary': generation_summary,
            'questions': questions
        }
        
    except Exception as e:
        logger.error(f"Error in {game_type} question generation: {str(e)}")
        return {'success': False, 'error': str(e)}


@api_view(['POST'])
def generate_preassessment_only(request):
    """
    Generate preassessment questions for a specific topic.
    
    Parameters:
    - topic_id (int): Topic ID to generate questions for
    - count (int): Number of questions to generate (default: 5)
    """
    try:
        topic_id = request.data.get('topic_id')
        count = request.data.get('count', 5)

        if not topic_id:
            return Response(
                {'error': 'topic_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify topic exists
        topic = get_object_or_404(Topic, id=topic_id)
        
        # Generate preassessment questions
        result = generate_pre_assessment({
            'topic_ids': [topic_id], 
            'total_questions': count
        })
        
        questions = result.get('questions', [])
        
        return Response({
            'message': f'Successfully generated {len(questions)} preassessment questions for {topic.name}',
            'topic': {
                'id': topic.id,
                'name': topic.name
            },
            'questions_generated': len(questions),
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
    """
    Generate coding questions for minigames.
    
    Parameters:
    - subtopic_ids (list): Array of subtopic IDs
    - difficulty_levels (list): Array of difficulty levels ['beginner', 'intermediate', 'advanced', 'master']
    - num_questions_per_subtopic (int): Number of questions per subtopic per difficulty
    """
    # Extract parameters with defaults
    subtopic_ids = request.data.get('subtopic_ids')
    difficulty_levels = request.data.get('difficulty_levels', ['beginner'])
    num_questions_per_subtopic = request.data.get('num_questions_per_subtopic', 3)
    
    # Use shared generation logic
    result = generate_questions_for_game_type(
        subtopic_ids=subtopic_ids,
        difficulty_levels=difficulty_levels,
        num_questions_per_subtopic=num_questions_per_subtopic,
        game_type='coding'
    )
    
    if not result['success']:
        return Response(
            {'error': result['error']},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Serialize questions for response
    serializer = GeneratedQuestionSerializer(result['questions'], many=True)
    
    return Response({
        'message': result['message'],
        'session_id': result['session_id'],
        'generation_summary': result['generation_summary'],
        'questions': serializer.data[:50]  # Limit response size
    })

@api_view(['POST'])
def generate_noncoding_questions_only(request):
    """
    Generate non-coding questions for minigames.
    
    Parameters:
    - subtopic_ids (list): Array of subtopic IDs
    - difficulty_levels (list): Array of difficulty levels ['beginner', 'intermediate', 'advanced', 'master']
    - num_questions_per_subtopic (int): Number of questions per subtopic per difficulty
    """
    # Extract parameters with defaults
    subtopic_ids = request.data.get('subtopic_ids')
    difficulty_levels = request.data.get('difficulty_levels', ['beginner'])
    num_questions_per_subtopic = request.data.get('num_questions_per_subtopic', 3)
    
    # Use shared generation logic
    result = generate_questions_for_game_type(
        subtopic_ids=subtopic_ids,
        difficulty_levels=difficulty_levels,
        num_questions_per_subtopic=num_questions_per_subtopic,
        game_type='non_coding'
    )
    
    if not result['success']:
        return Response(
            {'error': result['error']},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Serialize questions for response
    serializer = GeneratedQuestionSerializer(result['questions'], many=True)
    
    return Response({
        'message': result['message'],
        'session_id': result['session_id'],
        'generation_summary': result['generation_summary'],
        'questions': serializer.data[:50]  # Limit response size
    })
