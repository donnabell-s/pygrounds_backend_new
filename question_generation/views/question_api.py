# Main API endpoints for question generation 
# Includes bulk generation, single topic/subtopic generation, and preassessment questions

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction

from content_ingestion.models import GameZone, Topic, Subtopic
from ..helpers.generation_core import (
    generate_questions_for_subtopic_combination,
    run_multithreaded_generation
)
from ..helpers.rag_context import get_rag_context_for_subtopic
from ..helpers.question_processing import parse_llm_json_response
from ..helpers.llm_utils import invoke_deepseek, CODING_TEMPERATURE, NON_CODING_TEMPERATURE
from ..helpers.deepseek_prompts import deepseek_prompt_manager

import logging
logger = logging.getLogger(__name__)

@api_view(['POST'])
def generate_questions_bulk(request):
    # Bulk question generation endpoint
    # Parameters:
    # - game_type: 'coding' or 'non_coding' (required)
    # - difficulty_levels: ['beginner', 'intermediate', etc] (required)
    # - num_questions_per_subtopic: int (required)
    # - zone_ids: [int] or null (optional)
    # - topic_ids: [int] or null (optional)
    # - subtopic_ids: [int] or null (optional)
    try:
        # Extract parameters
        game_type = request.data.get('game_type', 'non_coding')
        difficulty_levels = request.data.get('difficulty_levels', ['beginner'])
        num_questions_per_subtopic = int(request.data.get('num_questions_per_subtopic', 2))
        zone_ids = request.data.get('zone_ids')
        
        # Validate parameters
        valid_game_types = ['coding', 'non_coding']
        valid_difficulties = ['beginner', 'intermediate', 'advanced', 'master']
        
        if game_type not in valid_game_types:
            return Response({
                'error': f'Invalid game_type. Must be one of: {valid_game_types}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not all(d in valid_difficulties for d in difficulty_levels):
            return Response({
                'error': f'Invalid difficulty levels. Must be from: {valid_difficulties}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get zones to process
        if zone_ids:
            zones = GameZone.objects.filter(id__in=zone_ids).order_by('order')
        else:
            zones = GameZone.objects.all().order_by('order')
        
        if not zones.exists():
            return Response({
                'error': 'No zones found for processing'
            }, status=status.HTTP_404_NOT_FOUND)
        
        print(f"🚀 Starting bulk generation: {game_type}, {len(zones)} zones, {len(difficulty_levels)} difficulties")
        
        # Run multithreaded generation
        generation_result = run_multithreaded_generation(
            zones=zones,
            difficulty_levels=difficulty_levels,
            num_questions_per_subtopic=num_questions_per_subtopic,
            game_type=game_type
        )
        
        if not generation_result['success']:
            return Response({
                'status': 'error',
                'message': generation_result.get('error', 'Unknown error'),
                'partial_results': generation_result.get('partial_results', [])
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Return success response
        return Response({
            'status': 'success',
            'message': f"Generated {generation_result['total_generated']} questions ({generation_result['duplicates_skipped']} duplicates skipped)",
            'statistics': {
                'total_questions_generated': generation_result['total_generated'],
                'duplicates_skipped': generation_result['duplicates_skipped'],
                'successful_zone_difficulty_pairs': generation_result['successful_results'],
                'failed_zone_difficulty_pairs': generation_result['failed_results'],
                'zones_processed': len(zones),
                'difficulties_processed': difficulty_levels
            },
            'json_filename': generation_result['json_filename'],
            'thread_stats': generation_result['thread_stats']
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Bulk generation failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def generate_questions_single_subtopic(request, subtopic_id=None):
    """
    Generate questions for a single subtopic.
    
    POST {
        "difficulty": "beginner|intermediate|advanced|master",
        "game_type": "coding|non_coding",
        "num_questions": 3
    }
    
    Returns generated questions for the specified subtopic.
    """
    try:
        # Get subtopic
        if subtopic_id:
            subtopic = get_object_or_404(Subtopic, id=subtopic_id)
        else:
            subtopic_id = request.data.get('subtopic_id')
            if not subtopic_id:
                return Response({
                    'error': 'subtopic_id required'
                }, status=status.HTTP_400_BAD_REQUEST)
            subtopic = get_object_or_404(Subtopic, id=subtopic_id)
        
        # Get parameters
        difficulty = request.data.get('difficulty', 'beginner')
        game_type = request.data.get('game_type', 'non_coding')
        num_questions = int(request.data.get('num_questions', 3))
        
        # Validate parameters
        valid_difficulties = ['beginner', 'intermediate', 'advanced', 'master']
        valid_game_types = ['coding', 'non_coding']
        
        if difficulty not in valid_difficulties:
            return Response({
                'error': f'Invalid difficulty. Must be one of: {valid_difficulties}'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if game_type not in valid_game_types:
            return Response({
                'error': f'Invalid game_type. Must be one of: {valid_game_types}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate questions
        generation_result = generate_questions_for_subtopic_combination(
            subtopic_combination=[subtopic],
            difficulty=difficulty,
            num_questions=num_questions,
            game_type=game_type,
            zone=subtopic.topic.zone
        )
        
        if not generation_result['success']:
            return Response({
                'status': 'error',
                'message': generation_result.get('error', 'Generation failed'),
                'subtopic': subtopic.name,
                'difficulty': difficulty,
                'game_type': game_type
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Format questions for response
        questions = []
        for q_obj in generation_result['saved_questions']:
            question_data = {
                'id': q_obj.id,
                'question_text': q_obj.question_text,
                'correct_answer': q_obj.correct_answer,
                'difficulty': q_obj.difficulty,
                'game_type': q_obj.game_type,
                'game_data': q_obj.game_data
            }
            questions.append(question_data)
        
        return Response({
            'status': 'success',
            'subtopic': {
                'id': subtopic.id,
                'name': subtopic.name,
                'topic': subtopic.topic.name,
                'zone': subtopic.topic.zone.name
            },
            'generation_info': {
                'difficulty': difficulty,
                'game_type': game_type,
                'questions_generated': generation_result['questions_generated'],
                'questions_saved': generation_result['questions_saved'],
                'duplicates_skipped': generation_result['duplicates_skipped']
            },
            'questions': questions
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Single subtopic generation failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def generate_pre_assessment(request):
    """
    Generate pre-assessment questions covering multiple topics.
    
    POST {
        "topic_ids": [1, 2, 3] (optional - if not provided, uses all topics),
        "total_questions": 20
    }
    
    Returns comprehensive pre-assessment questions.
    """
    try:
        # Get parameters
        topic_ids = request.data.get('topic_ids')
        total_questions = int(request.data.get('total_questions', 20))
        
        # Get topics
        if topic_ids:
            topics = Topic.objects.filter(id__in=topic_ids)
        else:
            topics = Topic.objects.all()
        
        if not topics.exists():
            return Response({
                'error': 'No topics found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Build topics and subtopics context
        topics_and_subtopics_parts = []
        for topic in topics:
            subtopics = topic.subtopic_set.all()
            if subtopics.exists():
                subtopic_names = [s.name for s in subtopics]
                section = f"**{topic.name}**: {', '.join(subtopic_names)}"
                topics_and_subtopics_parts.append(section)
        
        topics_and_subtopics_str = "\n\n".join(topics_and_subtopics_parts)
        
        # Create context for prompt
        context = {
            'topics_and_subtopics': topics_and_subtopics_str,
            'num_questions': total_questions
        }
        
        # Create system prompt
        system_prompt = (
            f"You are a Python assessment expert creating a concise pre-assessment for users. "
            f"Ensure that all listed topics and their subtopics are comprehensively covered within the total of {total_questions} questions. "
            f"To achieve this, generate many questions that cover multiple subtopics together, testing integrated understanding. "
            f"Cover various difficulty levels and always use the exact subtopic names from the provided list."
        )
        
        # Get prompt and call LLM
        prompt = deepseek_prompt_manager.get_prompt_for_minigame("pre_assessment", context)
        
        llm_response = invoke_deepseek(
            prompt,
            system_prompt=system_prompt,
            model="deepseek-chat",
            temperature=NON_CODING_TEMPERATURE  # Pre-assessments are typically conceptual
        )
        
        # Parse response
        questions = parse_llm_json_response(llm_response)
        
        if not questions:
            return Response({
                'status': 'error',
                'message': 'Failed to parse LLM response for pre-assessment'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Format response
        return Response({
            'status': 'success',
            'assessment_info': {
                'total_questions_requested': total_questions,
                'questions_generated': len(questions),
                'topics_covered': len(topics),
                'subtopics_total': sum(topic.subtopic_set.count() for topic in topics)
            },
            'questions': questions,
            'topics_covered': [
                {
                    'id': topic.id,
                    'name': topic.name,
                    'subtopics': [s.name for s in topic.subtopic_set.all()]
                }
                for topic in topics
            ]
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Pre-assessment generation failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_rag_context(request, subtopic_id):
    """
    Get RAG context for a specific subtopic (for testing/debugging).
    
    GET /api/questions/rag-context/{subtopic_id}/?difficulty=beginner
    """
    try:
        subtopic = get_object_or_404(Subtopic, id=subtopic_id)
        difficulty = request.GET.get('difficulty', 'beginner')
        
        rag_context = get_rag_context_for_subtopic(subtopic, difficulty)
        
        return Response({
            'subtopic': {
                'id': subtopic.id,
                'name': subtopic.name,
                'topic': subtopic.topic.name,
                'zone': subtopic.topic.zone.name
            },
            'difficulty': difficulty,
            'rag_context': rag_context
        })
        
    except Exception as e:
        return Response({
            'error': f'Failed to retrieve RAG context: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
