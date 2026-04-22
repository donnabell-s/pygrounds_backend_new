import uuid
import time
import threading
import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction

from content_ingestion.models import GameZone, Topic, Subtopic
from ..helpers.generation_core import run_multithreaded_generation
from ..helpers.rag_context import get_rag_context_for_subtopic
from ..helpers.question_processing import parse_llm_json_response
from ..helpers.llm_utils import invoke_deepseek, NON_CODING_TEMPERATURE
from ..helpers.deepseek_prompts import deepseek_prompt_manager
from ..helpers.generation_status import generation_status_tracker

logger = logging.getLogger(__name__)


# ============================================================
# BULK GENERATION
# ============================================================

@api_view(['POST'])
def generate_questions_bulk(request):
    """
    Start async bulk question generation.

    Request body:
        game_type                - coding | non_coding (default: non_coding)
        difficulty_levels        - list of levels (default: all four)
        num_questions_per_subtopic - int (default: 2)
        zone_ids                 - optional list of zone IDs
        topic_ids                - optional list of topic IDs
        subtopic_ids             - optional list of subtopic IDs
        max_total_questions      - optional cap (pre-assessment only)

    Returns session_id for status polling.
    """
    try:
        game_type                  = request.data.get('game_type', 'non_coding')
        difficulty_levels          = request.data.get('difficulty_levels', ['beginner', 'intermediate', 'advanced', 'master'])
        num_questions_per_subtopic = int(request.data.get('num_questions_per_subtopic', 2))
        max_total_questions        = request.data.get('max_total_questions')
        zone_ids                   = request.data.get('zone_ids')
        topic_ids                  = request.data.get('topic_ids')
        subtopic_ids               = request.data.get('subtopic_ids')

        valid_game_types  = ['coding', 'non_coding']
        valid_difficulties = ['beginner', 'intermediate', 'advanced', 'master']

        if game_type not in valid_game_types:
            return Response({'error': f'game_type must be one of: {valid_game_types}'}, status=status.HTTP_400_BAD_REQUEST)
        if not all(d in valid_difficulties for d in difficulty_levels):
            return Response({'error': f'difficulty_levels must be from: {valid_difficulties}'}, status=status.HTTP_400_BAD_REQUEST)

        # ── Specific subtopics ──────────────────────────────────
        if subtopic_ids:
            from ..helpers.parallel_workers import run_subtopic_specific_generation
            session_id    = str(uuid.uuid4())
            total_workers = len(subtopic_ids) * len(difficulty_levels)

            generation_status_tracker.create_session(
                session_id=session_id, total_workers=total_workers,
                zones=["Specific Subtopics"], difficulties=difficulty_levels,
            )

            def _run():
                try:
                    run_subtopic_specific_generation(
                        subtopic_ids=subtopic_ids, difficulty_levels=difficulty_levels,
                        num_questions_per_subtopic=num_questions_per_subtopic,
                        game_type=game_type, session_id=session_id,
                    )
                except Exception as e:
                    logger.error(f"Specific generation failed [{session_id}]: {e}")
                    generation_status_tracker.update_status(session_id, {'status': 'error', 'error': str(e)})

            threading.Thread(target=_run, daemon=True).start()
            return Response({
                'status': 'initializing', 'session_id': session_id,
                'mode': 'specific_subtopics', 'total_workers': total_workers,
                'subtopic_count': len(subtopic_ids), 'difficulties': difficulty_levels,
                'message': 'Subtopic generation started. Poll /generate/status/{session_id}/ for progress.',
            })

        # ── Specific topics ────────────────────────────────────
        if topic_ids:
            topic_subtopics = list(Subtopic.objects.filter(topic_id__in=topic_ids).select_related('topic__zone'))
            if not topic_subtopics:
                return Response({'error': 'No subtopics found for the specified topics'}, status=status.HTTP_404_NOT_FOUND)

            session_id    = str(uuid.uuid4())
            total_workers = len(topic_subtopics) * len(difficulty_levels)

            generation_status_tracker.create_session(
                session_id=session_id, total_workers=total_workers,
                zones=["Specific Topics"], difficulties=difficulty_levels,
            )

            def _run():
                try:
                    from ..helpers.parallel_workers import run_subtopic_specific_generation
                    run_subtopic_specific_generation(
                        subtopic_ids=[s.id for s in topic_subtopics],
                        difficulty_levels=difficulty_levels,
                        num_questions_per_subtopic=num_questions_per_subtopic,
                        game_type=game_type, session_id=session_id,
                    )
                except Exception as e:
                    logger.error(f"Topic generation failed [{session_id}]: {e}")
                    generation_status_tracker.update_status(session_id, {'status': 'error', 'error': str(e)})

            threading.Thread(target=_run, daemon=True).start()
            return Response({
                'status': 'initializing', 'session_id': session_id,
                'mode': 'specific_topics', 'total_workers': total_workers,
                'topic_count': len(topic_ids), 'subtopic_count': len(topic_subtopics),
                'difficulties': difficulty_levels,
                'message': 'Topic generation started. Poll /generate/status/{session_id}/ for progress.',
            })

        # ── Zone-wide generation ───────────────────────────────
        zones = GameZone.objects.filter(id__in=zone_ids).order_by('order') if zone_ids else GameZone.objects.all().order_by('order')
        if not zones.exists():
            return Response({'error': 'No zones found for processing'}, status=status.HTTP_404_NOT_FOUND)

        session_id    = str(uuid.uuid4())
        total_workers = len(zones) * len(difficulty_levels)

        generation_status_tracker.create_session(
            session_id=session_id, total_workers=total_workers,
            zones=[z.name for z in zones], difficulties=difficulty_levels,
        )

        def _run():
            try:
                run_multithreaded_generation(
                    zones=zones, difficulty_levels=difficulty_levels,
                    num_questions_per_subtopic=num_questions_per_subtopic,
                    game_type=game_type, session_id=session_id,
                    max_total_questions=max_total_questions,
                )
            except Exception as e:
                logger.error(f"Bulk generation failed [{session_id}]: {e}")
                generation_status_tracker.update_status(session_id, {'status': 'error', 'error': str(e)})

        threading.Thread(target=_run, daemon=True).start()
        return Response({
            'status': 'initializing', 'session_id': session_id,
            'total_workers': total_workers, 'zones': [z.name for z in zones],
            'difficulties': difficulty_levels,
            'message': 'Bulk generation started. Poll /generate/status/{session_id}/ for progress.',
        })

    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# PRE-ASSESSMENT GENERATION
# ============================================================

@api_view(['POST'])
def generate_pre_assessment(request):
    """
    Start async pre-assessment generation.

    Request body:
        topic_ids       - optional list (defaults to all topics)
        total_questions - int (default: 20)

    Returns session_id for status polling.
    """
    try:
        topic_ids       = request.data.get('topic_ids')
        total_questions = 30  # Hardcoded max questions to 30

        topics = Topic.objects.filter(id__in=topic_ids) if topic_ids else Topic.objects.all()
        if not topics.exists():
            return Response({'error': 'No topics found'}, status=status.HTTP_404_NOT_FOUND)

        from ..models import PreAssessmentQuestion

        session_id = str(uuid.uuid4())
        generation_status_tracker.start_session(session_id, {
            'type': 'pre_assessment',
            'total_questions': total_questions,
            'topic_count': len(topics),
            'topics': [{'id': t.id, 'name': t.name} for t in topics],
        })

        def _generate():
            try:
                generation_status_tracker.update_status(session_id, {
                    'status': 'processing', 'step': 'Building topic context',
                })

                topics_str = "\n\n".join(
                    f"**{t.name}**: {', '.join(s.name for s in t.subtopics.all())}"
                    for t in topics if t.subtopics.exists()
                )

                generation_status_tracker.update_status(session_id, {
                    'status': 'processing', 'step': 'Calling LLM',
                })

                prompt = deepseek_prompt_manager.get_prompt_for_minigame(
                    "pre_assessment", {'topics_and_subtopics': topics_str, 'num_questions': total_questions}
                )
                # Calculate difficulty distribution: 1 master, rest split roughly 40/40/20
                rem = total_questions - 1
                beginner_count     = round(rem * 0.45)
                intermediate_count = round(rem * 0.35)
                advanced_count     = rem - beginner_count - intermediate_count
                master_count       = 1

                system_prompt = (
                    f"You are a Python assessment expert. "
                    f"Generate exactly {total_questions} questions covering all listed topics and subtopics. "
                    f"Mix questions that span multiple subtopics. Use exact subtopic names from the list.\n"
                    f"CRITICAL INSTRUCTION - You MUST generate exactly this distribution of difficulties:\n"
                    f"- {beginner_count} beginner questions\n"
                    f"- {intermediate_count} intermediate questions\n"
                    f"- {advanced_count} advanced questions\n"
                    f"- {master_count} master question"
                )
                llm_response = invoke_deepseek(
                    prompt, system_prompt=system_prompt, model="deepseek-chat",
                    temperature=NON_CODING_TEMPERATURE, max_tokens=8000,
                )

                questions = parse_llm_json_response(llm_response, 'non_coding')
                if not questions:
                    generation_status_tracker.complete_session(session_id, {
                        'status': 'error',
                        'message': 'Failed to parse LLM response',
                        'questions': [], 'questions_generated': 0,
                        'total_questions_requested': total_questions,
                    })
                    return

                # Generation succeeded — now safe to clear old questions
                deleted_count = PreAssessmentQuestion.objects.all().delete()[0]
                logger.info(f"Cleared {deleted_count} existing pre-assessment questions after successful generation")

                generation_status_tracker.update_status(session_id, {
                    'status': 'processing',
                    'step': f'Saving {len(questions)} questions to database',
                    'questions_generated': len(questions),
                    'total_questions_requested': total_questions,
                })

                # Build a flat lookup map once: normalised_name → (subtopic, topic)
                subtopic_lookup = {}
                for topic in topics:
                    for sub in topic.subtopics.all():
                        subtopic_lookup[sub.name.strip().lower()] = (sub, topic)

                def find_subtopic_by_name(name: str):
                    """Exact → case-insensitive → starts-with fuzzy fallback."""
                    key = name.strip().lower()
                    if key in subtopic_lookup:
                        return subtopic_lookup[key]
                    # Fuzzy: find the closest key that contains/starts with this name
                    for k, v in subtopic_lookup.items():
                        if k.startswith(key) or key.startswith(k):
                            return v
                    return None, None

                saved, errors = [], 0
                for idx, q in enumerate(questions):
                    try:
                        subtopic_ids_found, topic_ids_found = [], []
                        for name in q.get('subtopics_covered', []):
                            sub, topic = find_subtopic_by_name(name)
                            if sub:
                                if sub.id not in subtopic_ids_found:
                                    subtopic_ids_found.append(sub.id)
                                if topic.id not in topic_ids_found:
                                    topic_ids_found.append(topic.id)

                        obj = PreAssessmentQuestion.objects.create(
                            topic_ids=topic_ids_found,
                            subtopic_ids=subtopic_ids_found,
                            question_text=q.get('question_text', ''),
                            answer_options=q.get('choices', []),
                            correct_answer=q.get('correct_answer', ''),
                            estimated_difficulty=q.get('difficulty', 'beginner'),
                            order=idx,
                        )
                        try:
                            from ..helpers.db_operations import export_preassessment_question_to_json
                            export_preassessment_question_to_json(obj)
                        except Exception:
                            pass
                        saved.append({'id': obj.id, 'question_text': obj.question_text, 'saved': True})
                    except Exception as e:
                        logger.error(f"Failed to save pre-assessment question {idx}: {e}")
                        errors += 1
                        saved.append({'question_text': q.get('question_text', ''), 'saved': False, 'error': str(e)})

                generation_status_tracker.complete_session(session_id, {
                    'status': 'completed',
                    'step': 'Generation completed successfully',
                    'questions_generated': len(questions),
                    'questions_saved': len(questions) - errors,
                    'save_errors': errors,
                    'total_questions_requested': total_questions,
                    'assessment_info': {
                        'total_questions_requested': total_questions,
                        'questions_generated': len(questions),
                        'questions_saved': len(questions) - errors,
                        'topics_covered': len(topics),
                        'subtopics_total': sum(t.subtopics.count() for t in topics),
                    },
                    'questions': questions,
                    'saved_questions': saved,
                    'topics_covered': [
                        {'id': t.id, 'name': t.name, 'subtopics': [s.name for s in t.subtopics.all()]}
                        for t in topics
                    ],
                })

            except Exception as e:
                generation_status_tracker.complete_session(session_id, {
                    'status': 'error', 'message': str(e), 'questions': [],
                })

        threading.Thread(target=_generate, daemon=True).start()
        return Response({
            'status': 'started', 'session_id': session_id,
            'message': f'Pre-assessment generation started for {total_questions} questions',
            'topics_count': len(topics),
        })

    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# SESSION STATUS & CONTROL
# ============================================================

@api_view(['GET'])
def get_generation_status(request, session_id):
    """Poll the status of any generation session."""
    try:
        session = generation_status_tracker.get_session_status(session_id)
        if not session:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

        # Pre-assessment sessions
        if session.get('type') == 'pre_assessment':
            return Response({
                'session_id': session_id,
                'status': session['status'],
                'type': session['type'],
                'start_time': session['start_time'],
                'last_updated': session['last_updated'],
                'step': session.get('step', ''),
                'total_questions': session.get('total_questions', 0),
                'questions_generated': session.get('questions_generated', 0),
                'total_questions_requested': session.get('total_questions_requested', 0),
                'questions_preview': session.get('questions_preview', []),
                'topic_count': session.get('topic_count', 0),
                'topics': session.get('topics', []),
                'assessment_info': session.get('assessment_info', {}),
                'questions': session.get('questions', []),
                'topics_covered': session.get('topics_covered', []),
                'message': session.get('message', ''),
            })

        # Task-counter-based sessions (subtopic/topic specific)
        if 'total_tasks' in session:
            total     = int(session.get('total_tasks') or 0)
            completed = int(session.get('completed_tasks') or 0)
            successful = int(session.get('successful_tasks') or 0)
            failed    = max(0, completed - successful)
            active    = max(0, total - completed) if session.get('status') in ['processing', 'starting', 'initializing'] else 0
            return Response({
                'session_id': session_id,
                'status': session['status'],
                'start_time': session['start_time'],
                'last_updated': session['last_updated'],
                'overall_progress': session.get('overall_progress', {}),
                'worker_summary': {
                    'total_workers': total, 'active_workers': active,
                    'completed_workers': completed, 'failed_workers': failed,
                },
                'zones': session.get('zones', []),
                'difficulties': session.get('difficulties', []),
            })

        # Standard per-worker sessions
        workers = session.get('workers', {}).values()
        return Response({
            'session_id': session_id,
            'status': session['status'],
            'start_time': session['start_time'],
            'last_updated': session['last_updated'],
            'overall_progress': session.get('overall_progress', {}),
            'worker_summary': {
                'total_workers':     session.get('total_workers', 0),
                'active_workers':    sum(1 for w in workers if w['status'] == 'processing'),
                'completed_workers': sum(1 for w in workers if w['status'] == 'completed'),
                'failed_workers':    sum(1 for w in workers if w['status'] in ['error', 'failed']),
            },
            'zones': session.get('zones', []),
            'difficulties': session.get('difficulties', []),
        })

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_worker_details(request, session_id):
    """Get per-worker breakdown for a generation session."""
    try:
        session = generation_status_tracker.get_session_status(session_id)
        if not session:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

        worker_details = sorted([
            {
                'worker_id':           worker_id,
                'status':              w['status'],
                'zone_name':           w['zone_name'],
                'difficulty':          w['difficulty'],
                'current_step':        w['current_step'],
                'progress':            w['progress'],
                'start_time':          w['start_time'],
                'last_activity':       w['last_activity'],
                'estimated_completion': w.get('estimated_completion'),
                'duration':            (time.time() - w['start_time']) if w['start_time'] else 0,
            }
            for worker_id, w in session['workers'].items()
        ], key=lambda x: x['worker_id'])

        return Response({
            'session_id': session_id,
            'workers': worker_details,
            'summary': {
                'total_workers':     len(worker_details),
                'active_workers':    sum(1 for w in worker_details if w['status'] == 'processing'),
                'completed_workers': sum(1 for w in worker_details if w['status'] == 'completed'),
                'failed_workers':    sum(1 for w in worker_details if w['status'] in ['error', 'failed']),
                'pending_workers':   sum(1 for w in worker_details if w['status'] == 'pending'),
            },
        })

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def cancel_generation(request, session_id):
    """Cancel an active generation session and clean up malformed questions."""
    try:
        from ..models import GeneratedQuestion

        session = generation_status_tracker.get_session_status(session_id)
        if not session:
            return Response({'error': f'Session {session_id} not found'}, status=status.HTTP_404_NOT_FOUND)

        if session['status'] in ['completed', 'failed', 'cancelled']:
            return Response(
                {'error': f'Cannot cancel a session with status: {session["status"]}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not generation_status_tracker.cancel_session(session_id, 'Cancelled by user'):
            return Response({'error': 'Failed to cancel session'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Clean up malformed questions created during this session
        latest = GeneratedQuestion.objects.order_by('-id').first()
        recent_qs = (
            GeneratedQuestion.objects.filter(id__gte=latest.id - 1000).select_related('topic', 'subtopic')
            if latest else GeneratedQuestion.objects.none()
        )

        to_remove = [
            q.id for q in recent_qs
            if (not q.question_text or len(q.question_text.strip()) < 10)
            or (not q.correct_answer or len(q.correct_answer.strip()) < 1)
            or (not q.topic or not q.subtopic)
            or q.validation_status == 'processing'
        ]

        removed = 0
        if to_remove:
            with transaction.atomic():
                removed = GeneratedQuestion.objects.filter(id__in=to_remove).delete()[0]

        session_start = session.get('start_time', time.time())
        questions_checked = recent_qs.count()
        valid_kept = questions_checked - removed
        return Response({
            'success': True,
            'session_id': session_id,
            'message': 'Generation session cancelled successfully',
            'cancellation_stats': {
                'cancel_time': time.time(),
                'session_duration': time.time() - session_start,
                'questions_removed': removed,
                'questions_checked': questions_checked,
                'cleanup_stats': {
                    'valid_questions_kept': max(0, valid_kept),
                    'invalid_questions_removed': removed,
                },
            },
        })

    except Exception as e:
        logger.error(f"Error cancelling session {session_id}: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# RAG CONTEXT (debug/testing)
# ============================================================

@api_view(['GET'])
def get_rag_context(request, subtopic_id):
    """
    Query params:
        difficulty - default: beginner
        game_type  - default: non_coding
    """
    try:
        subtopic   = get_object_or_404(Subtopic, id=subtopic_id)
        difficulty = request.GET.get('difficulty', 'beginner')
        game_type  = request.GET.get('game_type', 'non_coding')
        rag_context = get_rag_context_for_subtopic(subtopic, difficulty, game_type)

        return Response({
            'subtopic': {
                'id': subtopic.id, 'name': subtopic.name,
                'topic': subtopic.topic.name, 'zone': subtopic.topic.zone.name,
            },
            'difficulty': difficulty,
            'rag_context': rag_context,
        })

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
