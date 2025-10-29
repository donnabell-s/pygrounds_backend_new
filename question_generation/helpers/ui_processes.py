# UI processes and status management for question generation
# Handles status tracking, cancellation, and UI-specific operations

import time
import logging
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.conf import settings
from rest_framework import status

from ..helpers.generation_status import generation_status_tracker
from .parallel_workers import get_worker_details as get_worker_details_data
from .common_utils import format_duration_human, calculate_percentage, create_error_response, create_success_response

logger = logging.getLogger(__name__)


@api_view(['GET'])
def get_generation_status(request, session_id):
    """
    Get real-time status for a generation session (bulk or pre-assessment).
    
    GET /api/questions/generate/status/{session_id}/
    """
    try:
        session_status = generation_status_tracker.get_session_status(session_id)
        
        if not session_status:
            # Return default status information for testing/API discovery
            return Response({
                'session_id': session_id,
                'status': 'not_found',
                'start_time': None,
                'last_updated': None,
                'overall_progress': {},
                'worker_summary': {
                    'total_tasks': 0,
                    'active_tasks': 0,
                    'completed_tasks': 0,
                    'failed_tasks': 0,
                    'calculated_pending_tasks': 0
                },
                'zones': [],
                'difficulties': [],
                'total_tasks': 0,
                'completed_tasks': 0,
                'successful_tasks': 0,
                'total_questions': 0,
                'current_combination': [],
                'current_difficulty': '',
                'progress_percentage': 0,
                'success_rate': 0,
                'thread_pool_info': {
                    'max_threads': settings.QUESTION_GENERATION_WORKERS,
                    'thread_scaling_type': 'subtopic-level (high parallelism)'
                },
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
        total_tasks = session_status.get('total_tasks', 0)
        completed_tasks = session_status.get('completed_tasks', 0)
        successful_tasks = session_status.get('successful_tasks', 0)
        
        worker_summary = {
            'total_tasks': total_tasks,  # Renamed from total_workers for clarity
            'active_tasks': len([w for w in session_status.get('workers', {}).values() if w['status'] == 'processing']),
            'completed_tasks': completed_tasks,  # Use consistent value
            'failed_tasks': len([w for w in session_status.get('workers', {}).values() if w['status'] in ['error', 'failed']]),
            'calculated_pending_tasks': total_tasks - completed_tasks - len([w for w in session_status.get('workers', {}).values() if w['status'] in ['error', 'failed']])
        }
        
        # Debug logging to see what the backend is actually returning
        print('🔍 DEBUG: Full status response:', {
            'session_id': session_id,
            'status': session_status['status'],
            'overall_progress': session_status.get('overall_progress', {}),
            'worker_summary': worker_summary,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
        })
        print('🔍 DEBUG: Task/Thread breakdown:', {
            'total_tasks': total_tasks,
            'active_tasks': worker_summary['active_tasks'],
            'completed_tasks': completed_tasks,
            'failed_tasks': worker_summary['failed_tasks'],
            'thread_pool_size': f'{settings.QUESTION_GENERATION_WORKERS} (from QUESTION_GENERATION_WORKERS setting)',
            'calculated_pending_tasks': worker_summary['calculated_pending_tasks']
        })
        
        return Response({
            'session_id': session_id,
            'status': session_status['status'],
            'start_time': session_status['start_time'],
            'last_updated': session_status['last_updated'],
            'overall_progress': session_status.get('overall_progress', {}),
            'worker_summary': worker_summary,  # Now uses task terminology
            'zones': session_status.get('zones', []),
            'difficulties': session_status.get('difficulties', []),
            # Add subtopic-specific generation fields (now consistent)
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'successful_tasks': successful_tasks,
            'total_questions': session_status.get('total_questions', 0),
            'current_combination': session_status.get('current_combination', []),
            'current_difficulty': session_status.get('current_difficulty', ''),
            'progress_percentage': session_status.get('progress_percentage', 0),
            'success_rate': session_status.get('success_rate', 0),
            # Add thread pool information for clarity
            'thread_pool_info': {
                'max_threads': settings.QUESTION_GENERATION_WORKERS,
                'thread_scaling_type': 'subtopic-level (high parallelism)'
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting generation status for session {session_id}: {str(e)}")
        return Response({
            'error': f'Failed to get generation status: {str(e)}'
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


@api_view(['GET'])
def get_worker_details(request, session_id):
    """
    Get detailed worker information for a generation session.
    
    GET /api/questions/generate/workers/{session_id}/
    """
    try:
        worker_data = get_worker_details_data(session_id)
        
        if 'error' in worker_data:
            return Response({
                'error': worker_data['error']
            }, status=status.HTTP_404_NOT_FOUND if 'not found' in worker_data['error'].lower() else status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(worker_data)
        
    except Exception as e:
        logger.error(f"Error in get_worker_details API endpoint for session {session_id}: {str(e)}")
        return Response({
            'error': f'Failed to get worker details: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_session_summary(session_id: str) -> dict:
    """
    Get a comprehensive summary of a generation session.
    
    Args:
        session_id: Session ID to get summary for
        
    Returns:
        Dictionary with session summary or error
    """
    try:
        session_status = generation_status_tracker.get_session_status(session_id)
        
        if not session_status:
            return {'error': 'Session not found'}
        
        # Calculate session duration
        start_time = session_status.get('start_time', time.time())
        current_time = time.time()
        duration = current_time - start_time
        
        # Build summary based on session type
        if session_status.get('type') == 'pre_assessment':
            return {
                'session_id': session_id,
                'type': 'pre_assessment',
                'status': session_status['status'],
                'duration_seconds': duration,
                'duration_human': format_duration_human(duration),
                'questions_requested': session_status.get('total_questions', 0),
                'questions_generated': session_status.get('questions_generated', 0),
                'topics_covered': len(session_status.get('topics', [])),
                'current_step': session_status.get('step', ''),
                'completion_percentage': calculate_preassessment_progress(session_status)
            }
        else:
            # Bulk generation session
            total_tasks = session_status.get('total_tasks', 0)
            completed_tasks = session_status.get('completed_tasks', 0)
            
            return {
                'session_id': session_id,
                'type': 'bulk_generation',
                'status': session_status['status'],
                'duration_seconds': duration,
                'duration_human': format_duration_human(duration),
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'successful_tasks': session_status.get('successful_tasks', 0),
                'total_questions': session_status.get('total_questions', 0),
                'zones': session_status.get('zones', []),
                'difficulties': session_status.get('difficulties', []),
                'completion_percentage': calculate_percentage(completed_tasks, total_tasks),
                'success_rate': session_status.get('success_rate', 0)
            }
            
    except Exception as e:
        logger.error(f"Error getting session summary for {session_id}: {str(e)}")
        return {'error': str(e)}


def calculate_preassessment_progress(session_status: dict) -> float:
    """Calculate progress percentage for preassessment generation."""
    step = session_status.get('step', '')
    status_value = session_status.get('status', '')
    
    if status_value == 'completed':
        return 100.0
    elif status_value == 'error' or status_value == 'cancelled':
        return 0.0
    elif 'Building topic context' in step:
        return 20.0
    elif 'Generating questions' in step:
        return 50.0
    elif 'Parsing AI response' in step:
        return 70.0
    elif 'Processing' in step and 'generated questions' in step:
        return 80.0
    elif 'Saving questions' in step:
        return 90.0
    else:
        return 10.0


# format_duration function moved to common_utils.py as format_duration_human