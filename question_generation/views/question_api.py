# Main API endpoints for question generation 
# Includes bulk generation, single topic/subtopic generation, and preassessment questions

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db import models
from django.conf import settings
import uuid
import time

from content_ingestion.models import GameZone, Topic, Subtopic
from ..helpers.generation_core import (
    generate_questions_for_subtopic_combination,
    run_multithreaded_generation
)
from ..helpers.rag_context import get_rag_context_for_subtopic
from ..helpers.question_processing import parse_llm_json_response
from ..helpers.llm_utils import invoke_deepseek, CODING_TEMPERATURE, NON_CODING_TEMPERATURE
from ..helpers.deepseek_prompts import deepseek_prompt_manager
from ..helpers.generation_status import generation_status_tracker
from ..helpers.parallel_workers import (
    run_subtopic_specific_generation,
    get_subtopic_generation_summary
)

import logging
logger = logging.getLogger(__name__)



@api_view(['POST'])
def generate_questions_bulk(request):
    """
    Generate coding or non-coding questions for specific subtopics.
    
    Expected JSON:
    {
        "game_type": "coding" | "non_coding",
        "difficulty_levels": ["beginner", "intermediate", "advanced", "master"],
        "num_questions_per_subtopic": 5,
        "subtopic_ids": [7, 8, 9, 10, 11] | undefined
    }
    """
    try:
        # Extract parameters matching frontend format
        game_type = request.data.get('game_type')
        difficulty_levels = request.data.get('difficulty_levels')
        num_questions_per_subtopic = int(request.data.get('num_questions_per_subtopic', 5))
        subtopic_ids = request.data.get('subtopic_ids')
        
        # Validate required parameters
        if not game_type:
            return Response({
                'error': 'game_type is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if not difficulty_levels:
            return Response({
                'error': 'difficulty_levels is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
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
        
        # Get subtopics and their zones
        if subtopic_ids:
            subtopics = Subtopic.objects.filter(id__in=subtopic_ids).select_related('topic__zone')
            if not subtopics.exists():
                return Response({
                    'error': 'No subtopics found for the provided IDs'
                }, status=status.HTTP_404_NOT_FOUND)
            # Get unique zones from the selected subtopics
            zones = GameZone.objects.filter(topics__subtopics__in=subtopics).distinct().order_by('order')
        else:
            # If no subtopic_ids provided, process all zones
            zones = GameZone.objects.all().order_by('order')
            
        if not zones.exists():
            return Response({
                'error': 'No zones found for processing'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Create a unique session ID for tracking
        session_id = str(uuid.uuid4())
        
        # For subtopic-specific generation, we'll calculate total_tasks dynamically
        # For zone-based generation, use zone×difficulty combinations
        if subtopic_ids:
            total_workers = len(difficulty_levels)  # Placeholder, will be updated in background thread
        else:
            total_workers = len(zones) * len(difficulty_levels)
        
        # Initialize status tracking
        generation_status_tracker.create_session(
            session_id=session_id,
            total_workers=total_workers,
            zones=[zone.name for zone in zones],
            difficulties=difficulty_levels
        )
        
        print(f"🚀 Starting bulk generation: {game_type}, {len(zones)} zones, {len(difficulty_levels)} difficulties")
        print(f"📊 Session ID: {session_id}, Total TASKS: {total_workers} (zone×difficulty combinations)")
        print(f"⚙️ ThreadPoolExecutor will use: {settings.QUESTION_GENERATION_WORKERS} threads")
        print(f"⚙️ Layered Worker scaling: QuestionGen={settings.QUESTION_GENERATION_WORKERS} (subtopic-level), Embedding={settings.EMBEDDING_WORKERS} (topic-level), Document={settings.DOCUMENT_PROCESSING_WORKERS} (difficulty-level)")
        
        # Start generation in background thread
        import threading
        def run_generation():
            try:
                if subtopic_ids:
                    # Generate questions for specific subtopics
                    run_subtopic_specific_generation(
                        subtopic_ids=subtopic_ids,
                        difficulty_levels=difficulty_levels,
                        num_questions_per_subtopic=num_questions_per_subtopic,
                        game_type=game_type,
                        session_id=session_id
                    )
                else:
                    # Generate questions for all zones (existing behavior)
                    run_multithreaded_generation(
                        zones=zones,
                        difficulty_levels=difficulty_levels,
                        num_questions_per_subtopic=num_questions_per_subtopic,
                        game_type=game_type,
                        session_id=session_id,
                        max_workers=settings.QUESTION_GENERATION_WORKERS  # Dynamic based on CPU cores
                    )
            except Exception as e:
                logger.error(f"Generation failed for session {session_id}: {str(e)}")
                generation_status_tracker.update_status(session_id, {
                    'status': 'error',
                    'error': str(e)
                })
        
        # Start the background thread and return immediately
        thread = threading.Thread(target=run_generation)
        thread.daemon = True
        thread.start()
        
        # Return session ID immediately for polling
        return Response({
            'status': 'initializing',
            'session_id': session_id,
            'message': 'Generation started. Use the status endpoint to track progress.',
            'total_workers': total_workers,
            'zones': [zone.name for zone in zones],
            'difficulties': difficulty_levels
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Bulk generation failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def get_generation_estimate(request):
    """
    Get estimates and summary for question generation without starting the process.
    
    Expected JSON:
    {
        "game_type": "coding" | "non_coding",
        "difficulty_levels": ["beginner", "intermediate", "advanced", "master"],
        "num_questions_per_subtopic": 5,
        "subtopic_ids": [7, 8, 9, 10, 11] | undefined
    }
    """
    try:
        # Extract parameters (same as bulk generation)
        game_type = request.data.get('game_type')
        difficulty_levels = request.data.get('difficulty_levels')
        num_questions_per_subtopic = int(request.data.get('num_questions_per_subtopic', 5))
        subtopic_ids = request.data.get('subtopic_ids')
        
        # Validate required parameters
        if not game_type:
            return Response({
                'error': 'game_type is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if not difficulty_levels:
            return Response({
                'error': 'difficulty_levels is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get generation summary
        if subtopic_ids:
            summary = get_subtopic_generation_summary(
                subtopic_ids=subtopic_ids,
                difficulty_levels=difficulty_levels,
                num_questions_per_subtopic=num_questions_per_subtopic
            )
            
            if 'error' in summary:
                return Response({
                    'error': summary['error']
                }, status=status.HTTP_404_NOT_FOUND)
                
            return Response({
                'game_type': game_type,
                'scope': 'specific_subtopics',
                'generation_summary': summary,
                'recommendation': 'Ready to generate questions for the selected subtopics'
            })
        else:
            # For all zones, provide a different summary
            zones = GameZone.objects.all().order_by('order')
            total_subtopics = sum(zone.topics.aggregate(
                subtopic_count=models.Count('subtopics')
            )['subtopic_count'] for zone in zones)
            
            return Response({
                'game_type': game_type,
                'scope': 'all_zones',
                'generation_summary': {
                    'total_zones': len(zones),
                    'total_subtopics': total_subtopics,
                    'difficulty_levels': difficulty_levels,
                    'zones': [zone.name for zone in zones],
                    'warning': 'This will generate questions for ALL subtopics across ALL zones'
                },
                'recommendation': 'Consider specifying subtopic_ids for more focused generation'
            })
            
    except Exception as e:
        return Response({
            'error': f'Failed to get generation estimate: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def generate_pre_assessment(request):
    """
    Generate pre-assessment questions covering multiple topics asynchronously.
    
    Expected JSON:
    {
        "topic_ids": [1, 2, 3] | undefined,
        "total_questions": 20
    }
    
    Returns session_id for tracking progress.
    """
    try:
        # Get parameters
        topic_ids = request.data.get('topic_ids')
        total_questions = request.data.get('total_questions')
        
        # Validate required parameters
        if not total_questions:
            return Response({
                'error': 'total_questions is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        total_questions = int(total_questions)
        
        # Get topics
        if topic_ids:
            topics = Topic.objects.filter(id__in=topic_ids)
        else:
            topics = Topic.objects.all()
        
        if not topics.exists():
            return Response({
                'error': 'No topics found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Clean up existing pre-assessment questions before generating new ones
        from ..models import PreAssessmentQuestion
        deleted_count = PreAssessmentQuestion.objects.all().delete()[0]
        logger.info(f"Cleaned up {deleted_count} existing pre-assessment questions before generating new ones")
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Initialize status tracker
        generation_status_tracker.start_session(session_id, {
            'type': 'pre_assessment',
            'total_questions': total_questions,
            'topic_count': len(topics),
            'topics': [{'id': t.id, 'name': t.name} for t in topics]
        })
        
        # Start async generation
        import threading
        def generate_async():
            try:
                generation_status_tracker.update_status(session_id, {
                    'status': 'processing',
                    'step': 'Building topic context'
                })
                
                # Build topics and subtopics context
                topics_and_subtopics_parts = []
                for topic in topics:
                    subtopics = topic.subtopics.all()
                    if subtopics.exists():
                        subtopic_names = [s.name for s in subtopics]
                        section = f"**{topic.name}**: {', '.join(subtopic_names)}"
                        topics_and_subtopics_parts.append(section)
                
                topics_and_subtopics_str = "\n\n".join(topics_and_subtopics_parts)
                
                generation_status_tracker.update_status(session_id, {
                    'status': 'processing',
                    'step': 'Generating questions with AI'
                })
                
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
                    temperature=NON_CODING_TEMPERATURE,
                    max_tokens=8000  # High limit for comprehensive pre-assessment
                )
                
                generation_status_tracker.update_status(session_id, {
                    'status': 'processing',
                    'step': 'Parsing AI response',
                    'questions_generated': 0,
                    'total_questions_requested': total_questions
                })
                
                # Parse response
                questions = parse_llm_json_response(llm_response, 'non_coding')
                
                if not questions:
                    generation_status_tracker.complete_session(session_id, {
                        'status': 'error',
                        'message': 'Failed to parse LLM response for pre-assessment',
                        'questions': [],
                        'questions_generated': 0,
                        'total_questions_requested': total_questions,
                        'raw_response': llm_response[:500] if llm_response else 'No response'  # Debug info
                    })
                    return
                
                # Update with real question count as we process them
                generation_status_tracker.update_status(session_id, {
                    'status': 'processing',
                    'step': f'Processing {len(questions)} generated questions',
                    'questions_generated': len(questions),
                    'total_questions_requested': total_questions,
                    'questions_preview': questions[:3] if len(questions) > 3 else questions  # Show first 3 questions as preview
                })
                
                # Save questions to database
                generation_status_tracker.update_status(session_id, {
                    'status': 'processing',
                    'step': 'Saving questions to database',
                    'questions_generated': len(questions),
                    'total_questions_requested': total_questions
                })
                
                saved_questions = []
                from ..models import PreAssessmentQuestion
                
                for idx, question_data in enumerate(questions):
                    try:
                        # Extract subtopic names and find their IDs
                        subtopic_names = question_data.get('subtopics_covered', [])
                        subtopic_ids = []
                        topic_ids = []
                        
                        for subtopic_name in subtopic_names:
                            try:
                                # Find subtopic by name within the selected topics
                                subtopic = None
                                for topic in topics:
                                    subtopic = topic.subtopics.filter(name=subtopic_name).first()
                                    if subtopic:
                                        subtopic_ids.append(subtopic.id)
                                        if topic.id not in topic_ids:
                                            topic_ids.append(topic.id)
                                        break
                            except Exception:
                                continue  # Skip if subtopic not found
                        
                        # Create PreAssessmentQuestion
                        pre_question = PreAssessmentQuestion.objects.create(
                            topic_ids=topic_ids,
                            subtopic_ids=subtopic_ids,
                            question_text=question_data.get('question_text', ''),
                            answer_options=question_data.get('choices', []),
                            correct_answer=question_data.get('correct_answer', ''),
                            estimated_difficulty=question_data.get('difficulty', 'beginner'),
                            order=idx
                        )
                        
                        # Export to JSON
                        try:
                            from ..helpers.db_operations import export_preassessment_question_to_json
                            export_preassessment_question_to_json(pre_question)
                        except Exception as json_error:
                            logger.warning(f"Failed to export pre-assessment question to JSON: {json_error}")
                        
                        saved_questions.append({
                            'id': pre_question.id,
                            'question_text': pre_question.question_text,
                            'saved': True
                        })
                        
                    except Exception as e:
                        logger.error(f"Failed to save question {idx}: {str(e)}")
                        saved_questions.append({
                            'question_text': question_data.get('question_text', 'Unknown'),
                            'saved': False,
                            'error': str(e)
                        })
                
                # Complete successfully
                generation_status_tracker.complete_session(session_id, {
                    'status': 'completed',
                    'step': 'Generation completed successfully',
                    'questions_generated': len(questions),
                    'total_questions_requested': total_questions,
                    'questions_saved': len([q for q in saved_questions if q.get('saved', False)]),
                    'save_errors': len([q for q in saved_questions if not q.get('saved', True)]),
                    'assessment_info': {
                        'total_questions_requested': total_questions,
                        'questions_generated': len(questions),
                        'questions_saved': len([q for q in saved_questions if q.get('saved', False)]),
                        'topics_covered': len(topics),
                        'subtopics_total': sum(topic.subtopics.count() for topic in topics)
                    },
                    'questions': questions,
                    'saved_questions': saved_questions,
                    'topics_covered': [
                        {
                            'id': topic.id,
                            'name': topic.name,
                            'subtopics': [s.name for s in topic.subtopics.all()]
                        }
                        for topic in topics
                    ]
                })
                
            except Exception as e:
                generation_status_tracker.complete_session(session_id, {
                    'status': 'error',
                    'message': f'Pre-assessment generation failed: {str(e)}',
                    'questions': []
                })
        
        # Start the async thread
        thread = threading.Thread(target=generate_async)
        thread.daemon = True
        thread.start()
        
        # Return session ID immediately
        return Response({
            'status': 'started',
            'session_id': session_id,
            'message': f'Pre-assessment generation started for {total_questions} questions',
            'topics_count': len(topics)
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Failed to start pre-assessment generation: {str(e)}'
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
        game_type = request.GET.get('game_type', 'non_coding')
        
        rag_context = get_rag_context_for_subtopic(subtopic, difficulty, game_type)
        
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



