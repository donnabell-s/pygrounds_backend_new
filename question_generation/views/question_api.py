# Main API endpoints for question generation 
# Includes bulk generation, single topic/subtopic generation, and preassessment questions

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction
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

import logging
logger = logging.getLogger(__name__)

@api_view(['POST'])
def generate_questions_bulk(request):
    # Bulk question generation endpoint
    # Parameters:
    # - game_type: 'coding' or 'non_coding' (required)
    # - difficulty_levels: ['beginner', 'intermediate', etc] (required)
    # - num_questions_per_subtopic: int (required) - questions per subtopic
    # - zone_ids: [int] or null (optional) - specific zones to process
    # - topic_ids: [int] or null (optional) - specific topics to process  
    # - subtopic_ids: [int] or null (optional) - specific subtopics to process
    # 
    # Hierarchy: If subtopic_ids provided → use only those subtopics (NO combinations)
    #           If topic_ids provided → use all subtopics from those topics
    #           If zone_ids provided → use all subtopics from those zones (WITH combinations)
    #           If none provided → use all zones (WITH combinations)
    #
    # Note: max_total_questions is NOT used here (it's for pre-assessment generation only)
    try:
        # Extract parameters
        game_type = request.data.get('game_type', 'non_coding')
        difficulty_levels = request.data.get('difficulty_levels', ['beginner', 'intermediate', 'advanced', 'master'])
        num_questions_per_subtopic = int(request.data.get('num_questions_per_subtopic', 2))
        max_total_questions = request.data.get('max_total_questions')  # New parameter
        zone_ids = request.data.get('zone_ids')
        topic_ids = request.data.get('topic_ids')
        subtopic_ids = request.data.get('subtopic_ids')
        
        # Debug logging to understand what parameters are being received
        print(f"🔍 BULK GENERATION REQUEST DEBUG:")
        print(f"   ├── game_type: {game_type}")
        print(f"   ├── difficulty_levels: {difficulty_levels}")
        print(f"   ├── num_questions_per_subtopic: {num_questions_per_subtopic}")
        print(f"   ├── zone_ids: {zone_ids} ({'MISSING - should specify selected zone' if not zone_ids else 'OK'})")
        print(f"   ├── topic_ids: {topic_ids} ({'MISSING - should specify selected topic' if not topic_ids and not subtopic_ids else 'OK' if topic_ids else 'Not needed if subtopic_ids provided'})")
        print(f"   └── subtopic_ids: {subtopic_ids} ({'OK - specific subtopic selected' if subtopic_ids else 'Not provided'})")
        
        # Note: max_total_questions is for pre-assessment only, not regular minigame generation
        if max_total_questions:
            print(f"   ⚠️  max_total_questions: {max_total_questions} (NOTE: This is for pre-assessment only, not minigame generation)")
        
        # Validate hierarchical selection
        if subtopic_ids and not zone_ids and not topic_ids:
            print(f"   ℹ️  INFO: Subtopic selected without zone/topic context (this is OK for specific subtopic generation)")
        
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
        
        # Check if specific subtopics are requested
        if subtopic_ids:
            # SPECIFIC SUBTOPIC GENERATION - NO COMBINATIONS
            from ..helpers.parallel_workers import run_subtopic_specific_generation
            
            print(f"🎯 Specific subtopic generation requested: {len(subtopic_ids)} subtopics")
            print(f"🔍 Subtopic IDs: {subtopic_ids}")
            
            # Create session for tracking
            session_id = str(uuid.uuid4())
            total_workers = len(subtopic_ids) * len(difficulty_levels)
            
            # Initialize status tracking for specific subtopics
            generation_status_tracker.create_session(
                session_id=session_id,
                total_workers=total_workers,
                zones=["Specific Subtopics"],
                difficulties=difficulty_levels
            )
            
            # Start subtopic-specific generation in background thread
            import threading
            def run_specific_generation():
                try:
                    run_subtopic_specific_generation(
                        subtopic_ids=subtopic_ids,
                        difficulty_levels=difficulty_levels,
                        num_questions_per_subtopic=num_questions_per_subtopic,
                        game_type=game_type,
                        session_id=session_id
                    )
                except Exception as e:
                    logger.error(f"Specific generation failed for session {session_id}: {str(e)}")
                    generation_status_tracker.update_status(session_id, {
                        'status': 'error',
                        'error': str(e)
                    })
            
            # Start the background thread
            thread = threading.Thread(target=run_specific_generation)
            thread.daemon = True
            thread.start()
            
            return Response({
                'status': 'initializing',
                'session_id': session_id,
                'message': 'Specific subtopic generation started. Use the status endpoint to track progress.',
                'mode': 'specific_subtopics',
                'total_workers': total_workers,
                'subtopic_count': len(subtopic_ids),
                'difficulties': difficulty_levels
            })
        
        # BULK ZONE/TOPIC GENERATION - WITH COMBINATIONS
        # Handle topic_ids if provided (but no specific subtopics)
        if topic_ids and not subtopic_ids:
            # Get all subtopics from specified topics
            topic_subtopics = list(Subtopic.objects.filter(topic_id__in=topic_ids).select_related('topic__zone'))
            
            if not topic_subtopics:
                return Response({
                    'error': 'No subtopics found for the specified topics'
                }, status=status.HTTP_404_NOT_FOUND)
            
            print(f"🎯 Topic-specific generation requested: {len(topic_ids)} topics, {len(topic_subtopics)} subtopics")
            
            # Use subtopic-specific generation for topic subtopics
            session_id = str(uuid.uuid4())
            total_workers = len(topic_subtopics) * len(difficulty_levels)
            
            generation_status_tracker.create_session(
                session_id=session_id,
                total_workers=total_workers,
                zones=["Specific Topics"],
                difficulties=difficulty_levels
            )
            
            import threading
            def run_topic_generation():
                try:
                    from ..helpers.parallel_workers import run_subtopic_specific_generation
                    run_subtopic_specific_generation(
                        subtopic_ids=[s.id for s in topic_subtopics],
                        difficulty_levels=difficulty_levels,
                        num_questions_per_subtopic=num_questions_per_subtopic,
                        game_type=game_type,
                        session_id=session_id
                    )
                except Exception as e:
                    logger.error(f"Topic generation failed for session {session_id}: {str(e)}")
                    generation_status_tracker.update_status(session_id, {
                        'status': 'error',
                        'error': str(e)
                    })
            
            thread = threading.Thread(target=run_topic_generation)
            thread.daemon = True
            thread.start()
            
            return Response({
                'status': 'initializing',
                'session_id': session_id,
                'message': 'Topic-specific generation started. Use the status endpoint to track progress.',
                'mode': 'specific_topics',
                'total_workers': total_workers,
                'topic_count': len(topic_ids),
                'subtopic_count': len(topic_subtopics),
                'difficulties': difficulty_levels
            })
        
        # Get zones to process
        if zone_ids:
            zones = GameZone.objects.filter(id__in=zone_ids).order_by('order')
        else:
            zones = GameZone.objects.all().order_by('order')
        
        if not zones.exists():
            return Response({
                'error': 'No zones found for processing'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Create a unique session ID for tracking
        session_id = str(uuid.uuid4())
        total_workers = len(zones) * len(difficulty_levels)
        
        # Initialize status tracking
        generation_status_tracker.create_session(
            session_id=session_id,
            total_workers=total_workers,
            zones=[zone.name for zone in zones],
            difficulties=difficulty_levels
        )
        
        print(f"🚀 Starting bulk generation: {game_type}, {len(zones)} zones, {len(difficulty_levels)} difficulties")
        print(f"📊 Session ID: {session_id}, Total workers: {total_workers}")
        
        # Start generation in background thread
        import threading
        def run_generation():
            try:
                run_multithreaded_generation(
                    zones=zones,
                    difficulty_levels=difficulty_levels,
                    num_questions_per_subtopic=num_questions_per_subtopic,
                    game_type=game_type,
                    session_id=session_id,
                    max_total_questions=max_total_questions
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
def generate_pre_assessment(request):
    """
    Generate pre-assessment questions covering multiple topics asynchronously.
    
    POST {
        "topic_ids": [1, 2, 3] (optional - if not provided, uses all topics),
        "total_questions": 20
    }
    
    Returns session_id for tracking progress.
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


@api_view(['GET'])
def get_generation_status(request, session_id):
    """
    Get real-time status for a generation session (bulk or pre-assessment).
    
    GET /api/generate/status/{session_id}/
    """
    try:
        session_status = generation_status_tracker.get_session_status(session_id)
        
        if not session_status:
            return Response({
                'error': 'Session not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Handle pre-assessment sessions (simpler structure)
        if session_status.get('type') == 'pre_assessment':
            return Response({
                'session_id': session_id,
                'status': session_status['status'],
                'start_time': session_status['start_time'],
                'last_updated': session_status['last_updated'],
                'type': session_status['type'],
                'step': session_status.get('step', ''),
                'total_questions': session_status.get('total_questions', 0),
                'questions_generated': session_status.get('questions_generated', 0),
                'total_questions_requested': session_status.get('total_questions_requested', 0),
                'questions_preview': session_status.get('questions_preview', []),
                'topic_count': session_status.get('topic_count', 0),
                'topics': session_status.get('topics', []),
                'assessment_info': session_status.get('assessment_info', {}),
                'questions': session_status.get('questions', []),
                'topics_covered': session_status.get('topics_covered', []),
                'message': session_status.get('message', '')
            })
        
        # Handle bulk generation sessions (original structure)
        return Response({
            'session_id': session_id,
            'status': session_status['status'],
            'start_time': session_status['start_time'],
            'last_updated': session_status['last_updated'],
            'overall_progress': session_status.get('overall_progress', {}),
            'worker_summary': {
                'total_workers': session_status.get('total_workers', 0),
                'active_workers': len([w for w in session_status.get('workers', {}).values() if w['status'] == 'processing']),
                'completed_workers': len([w for w in session_status.get('workers', {}).values() if w['status'] == 'completed']),
                'failed_workers': len([w for w in session_status.get('workers', {}).values() if w['status'] in ['error', 'failed']])
            },
            'zones': session_status.get('zones', []),
            'difficulties': session_status.get('difficulties', [])
        })
        
    except Exception as e:
        return Response({
            'error': f'Failed to get generation status: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_worker_details(request, session_id):
    """
    Get detailed worker information for a generation session.
    
    GET /api/generate/workers/{session_id}/
    """
    try:
        session_status = generation_status_tracker.get_session_status(session_id)
        
        if not session_status:
            return Response({
                'error': 'Session not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Format worker details for frontend consumption
        worker_details = []
        for worker_id, worker in session_status['workers'].items():
            worker_detail = {
                'worker_id': worker_id,
                'status': worker['status'],
                'zone_name': worker['zone_name'],
                'difficulty': worker['difficulty'],
                'current_step': worker['current_step'],
                'progress': worker['progress'],
                'start_time': worker['start_time'],
                'last_activity': worker['last_activity'],
                'estimated_completion': worker.get('estimated_completion'),
                'duration': (time.time() - worker['start_time']) if worker['start_time'] else 0
            }
            worker_details.append(worker_detail)
        
        # Sort by worker_id for consistent ordering
        worker_details.sort(key=lambda x: x['worker_id'])
        
        return Response({
            'session_id': session_id,
            'workers': worker_details,
            'summary': {
                'total_workers': len(worker_details),
                'active_workers': len([w for w in worker_details if w['status'] == 'processing']),
                'completed_workers': len([w for w in worker_details if w['status'] == 'completed']),
                'failed_workers': len([w for w in worker_details if w['status'] in ['error', 'failed']]),
                'pending_workers': len([w for w in worker_details if w['status'] == 'pending'])
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'Failed to get worker details: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def cancel_generation(request, session_id):
    """
    Cancel an active question generation session.
    
    This endpoint:
    1. Marks the session as cancelled in the status tracker
    2. Keeps successfully saved questions intact
    3. Cleans up incomplete/malformed questions from the current session
    4. Returns cancellation statistics
    """
    try:
        from ..models import GeneratedQuestion
        from django.utils import timezone
        from datetime import timedelta
        
        logger.info(f"Cancelling generation session: {session_id}")
        
        # Check if session exists and can be cancelled
        session_status = generation_status_tracker.get_session_status(session_id)
        if not session_status:
            return Response({
                'error': f'Session {session_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if session can be cancelled
        if session_status['status'] in ['completed', 'failed', 'cancelled']:
            return Response({
                'error': f'Cannot cancel session with status: {session_status["status"]}',
                'current_status': session_status['status']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Cancel the session in the status tracker
        cancel_reason = 'Cancelled by user'
        cancelled = generation_status_tracker.cancel_session(session_id, cancel_reason)
        
        if not cancelled:
            return Response({
                'error': 'Failed to cancel session'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Clean up incomplete/malformed questions from this session
        # We'll identify questions created in the last few minutes that might be from this session
        session_start_time = session_status.get('start_time', time.time())
        session_start_datetime = timezone.now() - timedelta(seconds=(time.time() - session_start_time + 300))  # Add 5 minute buffer
        
        cleanup_stats = {
            'questions_before_cleanup': 0,
            'incomplete_questions_removed': 0,
            'malformed_questions_removed': 0,
            'valid_questions_kept': 0
        }
        
        # Find potentially related questions (created since session started)
        latest_question = GeneratedQuestion.objects.filter(
            id__isnull=False
        ).order_by('-id').first()
        
        if latest_question:
            # Look at recent questions (last 1000 max)
            recent_questions = GeneratedQuestion.objects.filter(
                id__gte=latest_question.id - 1000
            ).select_related('topic', 'subtopic')
        else:
            # No questions exist, nothing to clean up
            recent_questions = GeneratedQuestion.objects.none()
        
        cleanup_stats['questions_before_cleanup'] = recent_questions.count()
        
        # Identify incomplete or malformed questions
        questions_to_remove = []
        
        for question in recent_questions:
            is_malformed = False
            
            # Check for malformed/incomplete questions
            if not question.question_text or len(question.question_text.strip()) < 10:
                is_malformed = True
                cleanup_stats['malformed_questions_removed'] += 1
            elif not question.correct_answer or len(question.correct_answer.strip()) < 1:
                is_malformed = True
                cleanup_stats['malformed_questions_removed'] += 1
            elif not question.topic or not question.subtopic:
                is_malformed = True
                cleanup_stats['incomplete_questions_removed'] += 1
            elif question.validation_status == 'processing':
                is_malformed = True
                cleanup_stats['incomplete_questions_removed'] += 1
            
            if is_malformed:
                questions_to_remove.append(question.id)
            else:
                cleanup_stats['valid_questions_kept'] += 1
        
        # Remove malformed questions
        if questions_to_remove:
            with transaction.atomic():
                removed_count = GeneratedQuestion.objects.filter(id__in=questions_to_remove).delete()[0]
                logger.info(f"Removed {removed_count} incomplete/malformed questions for session {session_id}")
        
        # Get final session status
        final_session_status = generation_status_tracker.get_session_status(session_id)
        
        logger.info(f"Successfully cancelled session {session_id}. Cleaned up {len(questions_to_remove)} questions.")
        
        return Response({
            'success': True,
            'session_id': session_id,
            'message': f'Generation session cancelled successfully',
            'cancellation_stats': {
                'cancel_time': time.time(),
                'cancel_reason': cancel_reason,
                'session_duration': time.time() - session_start_time,
                'cleanup_stats': cleanup_stats
            },
            'session_status': final_session_status
        })
        
    except Exception as e:
        logger.error(f"Error cancelling generation session {session_id}: {str(e)}")
        return Response({
            'error': f'Failed to cancel generation: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
