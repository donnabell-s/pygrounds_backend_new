from .imports import *
from django.db.models import Count


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_game_data_for_frontend(game_data):
    """Remove deprecated/unused fields from game_data to reduce response size."""
    if not game_data:
        return game_data

    cleaned_data = game_data.copy()

    fields_to_remove = ['used', 'context', 'auto_generated', 'pipeline_version', 'is_cross_subtopic']
    for field in fields_to_remove:
        cleaned_data.pop(field, None)

    if 'rag_context' in cleaned_data and isinstance(cleaned_data['rag_context'], dict):
        for field in ['used', 'context']:
            cleaned_data['rag_context'].pop(field, None)
        if not cleaned_data['rag_context']:
            cleaned_data.pop('rag_context', None)

    return cleaned_data


def format_question_response(question, include_full_game_data=False):
    """Format a GeneratedQuestion object for API response."""
    game_data = question.game_data if include_full_game_data else clean_game_data_for_frontend(question.game_data)

    return {
        'id': question.id,
        'question_text': question.question_text,
        'correct_answer': question.correct_answer,
        'estimated_difficulty': question.estimated_difficulty,
        'game_type': question.game_type,
        'validation_status': question.validation_status,
        'game_data': game_data,
        'subtopic': {
            'id': question.subtopic.id,
            'name': question.subtopic.name,
            'topic_name': question.subtopic.topic.name,
            'zone_name': question.subtopic.topic.zone.name,
        },
        'created_at': question.created_at.isoformat() if hasattr(question, 'created_at') else None,
    }


# ============================================================
# FLAGGED QUESTIONS
# ============================================================

@api_view(['GET'])
def get_flagged_questions(request):
    """
    Get all flagged questions with pagination and optional filters.

    Query params:
        page       - page number (default: 1)
        page_size  - items per page (default: 10)
        reason     - filter by flag reason (partial match)
        game_type  - filter by game type (coding/non_coding)
    """
    try:
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))

        questions_query = GeneratedQuestion.objects.filter(flagged=True)

        reason = request.query_params.get('reason')
        if reason:
            questions_query = questions_query.filter(flag_reason__icontains=reason)

        game_type = request.query_params.get('game_type')
        if game_type:
            questions_query = questions_query.filter(game_type=game_type)

        questions_query = questions_query.order_by('-flag_created_at')
        total_count = questions_query.count()

        offset = (page - 1) * page_size
        questions = questions_query[offset:offset + page_size]

        questions_data = []
        for question in questions:
            questions_data.append({
                'id': question.id,
                'question_text': question.question_text,
                'flagged': question.flagged,
                'flag_reason': question.flag_reason,
                'flag_notes': question.flag_notes,
                'flagged_by': question.flagged_by,
                'flag_created_at': question.flag_created_at.isoformat() if question.flag_created_at else None,
                'game_type': question.game_type,
                'estimated_difficulty': question.estimated_difficulty,
                'correct_answer': question.correct_answer,
                'answer_options': question.game_data.get('answer_options') if question.game_data else None,
                'game_data': clean_game_data_for_frontend(question.game_data),
                'subtopic': {
                    'id': question.subtopic.id,
                    'name': question.subtopic.name,
                    'topic_name': question.subtopic.topic.name,
                },
            })

        next_page = page + 1 if offset + page_size < total_count else None
        previous_page = page - 1 if page > 1 else None

        return Response({
            'status': 'success',
            'count': total_count,
            'next': f"?page={next_page}&page_size={page_size}" if next_page else None,
            'previous': f"?page={previous_page}&page_size={page_size}" if previous_page else None,
            'results': questions_data,
        })

    except ValueError:
        return Response({'status': 'error', 'message': 'Invalid page or page_size parameter'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Failed to retrieve flagged questions: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def toggle_question_flag(request, question_id):
    """
    Toggle the flagged status of a question.

    Request body (when flagging):
        reason  - reason for flagging
        note    - additional notes
    """
    try:
        try:
            question = GeneratedQuestion.objects.get(id=question_id)
        except GeneratedQuestion.DoesNotExist:
            return Response({
                'status': 'error',
                'message': f'Question {question_id} not found. For multi-question games, use the game ID.',
                'type': 'QUESTION_NOT_FOUND',
            }, status=status.HTTP_404_NOT_FOUND)

        question.flagged = not question.flagged

        if question.flagged:
            question.flag_reason = request.data.get('reason') or None
            question.flag_notes = request.data.get('note') or None
            question.flagged_by = request.data.get('flagged_by') or getattr(request.user, 'username', 'anonymous')
            question.flag_created_at = timezone.now()
        else:
            question.flag_reason = None
            question.flag_notes = None
            question.flagged_by = None
            question.flag_created_at = None

        question.save()

        return Response({
            'status': 'success',
            'message': f"Question {'flagged' if question.flagged else 'unflagged'} successfully",
            'question_id': question.id,
            'flagged': question.flagged,
            'flag_reason': question.flag_reason,
            'flag_notes': question.flag_notes,
            'flagged_by': question.flagged_by,
            'flag_created_at': question.flag_created_at.isoformat() if question.flag_created_at else None,
        })

    except Exception as e:
        logger.error(f"Failed to toggle flag for question {question_id}: {str(e)}")
        return Response({'status': 'error', 'message': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def regenerate_flagged_question(request, question_id):
    """
    Queue a flagged question for regeneration using an admin-provided LLM prompt.
    Stores the context in game_data, sets validation_status to pending_regeneration,
    and clears the flag from the original question.

    Request body:
        llm_prompt - instructions for how to improve the question (required)
    """
    try:
        try:
            original_question = GeneratedQuestion.objects.get(id=question_id)
        except GeneratedQuestion.DoesNotExist:
            return Response({'status': 'error', 'message': f'Question {question_id} not found'}, status=status.HTTP_404_NOT_FOUND)

        llm_prompt = request.data.get('llm_prompt', '').strip() if isinstance(request.data, dict) else ''
        if not llm_prompt:
            return Response({'status': 'error', 'message': 'llm_prompt is required'}, status=status.HTTP_400_BAD_REQUEST)

        regen_context = {
            'flag_reason': original_question.flag_reason,
            'flag_notes': original_question.flag_notes,
            'llm_regeneration_prompt': llm_prompt,
            'regenerated_at': timezone.now().isoformat(),
            'regenerated_by': getattr(request.user, 'username', 'system'),
        }

        game_data = original_question.game_data or {}
        game_data['_regeneration_context'] = regen_context
        original_question.game_data = game_data
        original_question.validation_status = 'pending_regeneration'
        original_question.flagged = False
        original_question.flag_reason = None
        original_question.flag_notes = None
        original_question.flagged_by = None
        original_question.flag_created_at = None
        original_question.save()

        return Response({
            'status': 'success',
            'message': 'Question regeneration queued successfully',
            'question_id': question_id,
            'regenerated_question_id': question_id,
            'regeneration_context': regen_context,
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Failed to regenerate question {question_id}: {str(e)}")
        return Response({'status': 'error', 'message': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# SINGLE QUESTION RETRIEVAL
# ============================================================

@api_view(['GET'])
def get_question_by_id(request, question_id):
    """
    Get a specific question by ID with complete game data.

    Query params:
        full_context - if 'true', includes full RAG context (default: false)
    """
    try:
        question = get_object_or_404(GeneratedQuestion, id=question_id)
        include_full_game_data = request.query_params.get('full_context', 'false').lower() == 'true'
        question_data = format_question_response(question, include_full_game_data)

        return Response({'status': 'success', 'question': question_data})

    except Exception as e:
        logger.error(f"Failed to retrieve question {question_id}: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# BULK / FILTERED RETRIEVAL
# ============================================================

@api_view(['GET'])
def get_all_questions(request):
    """
    Get all questions with pagination and ordering.

    Query params:
        limit    - max results (default: 50)
        offset   - pagination offset (default: 0)
        order_by - id | created_at | estimated_difficulty | game_type (default: id)
        order    - asc | desc (default: desc)
    """
    VALID_ORDER_FIELDS = ['id', 'created_at', 'estimated_difficulty', 'game_type']
    try:
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        order_by = request.query_params.get('order_by', 'id')
        order = request.query_params.get('order', 'desc')

        if order_by not in VALID_ORDER_FIELDS:
            return Response({'status': 'error', 'message': f'order_by must be one of: {", ".join(VALID_ORDER_FIELDS)}'}, status=status.HTTP_400_BAD_REQUEST)
        if order not in ['asc', 'desc']:
            return Response({'status': 'error', 'message': 'order must be "asc" or "desc"'}, status=status.HTTP_400_BAD_REQUEST)

        order_field = f"-{order_by}" if order == 'desc' else order_by
        questions_query = GeneratedQuestion.objects.all().order_by(order_field)
        total_count = questions_query.count()
        questions_data = [format_question_response(q) for q in questions_query[offset:offset + limit]]

        return Response({
            'status': 'success',
            'pagination': {'total_count': total_count, 'returned_count': len(questions_data), 'limit': limit, 'offset': offset, 'has_more': offset + limit < total_count},
            'ordering': {'order_by': order_by, 'order': order},
            'questions': questions_data,
        })

    except ValueError:
        return Response({'status': 'error', 'message': 'Invalid limit, offset, or ordering parameter'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Failed to retrieve all questions: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_questions_by_filters(request):
    """
    Get questions filtered by game_type and difficulty.

    Query params:
        game_type  - coding | non_coding (required)
        difficulty - beginner | intermediate | advanced | master (optional)
        limit      - max results (default: 20)
        offset     - pagination offset (default: 0)
    """
    VALID_DIFFICULTIES = ['beginner', 'intermediate', 'advanced', 'master']
    try:
        game_type = request.query_params.get('game_type')
        if not game_type:
            return Response({'status': 'error', 'message': 'game_type is required'}, status=status.HTTP_400_BAD_REQUEST)
        if game_type not in ['coding', 'non_coding']:
            return Response({'status': 'error', 'message': 'game_type must be "coding" or "non_coding"'}, status=status.HTTP_400_BAD_REQUEST)

        difficulty = request.query_params.get('difficulty')
        if difficulty and difficulty not in VALID_DIFFICULTIES:
            return Response({'status': 'error', 'message': f'difficulty must be one of: {", ".join(VALID_DIFFICULTIES)}'}, status=status.HTTP_400_BAD_REQUEST)

        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))

        questions_query = GeneratedQuestion.objects.filter(game_type=game_type)
        if difficulty:
            questions_query = questions_query.filter(estimated_difficulty=difficulty)
        questions_query = questions_query.order_by('-id')

        total_count = questions_query.count()
        questions_data = [format_question_response(q) for q in questions_query[offset:offset + limit]]

        return Response({
            'status': 'success',
            'filters_applied': {'game_type': game_type, 'difficulty': difficulty, 'limit': limit, 'offset': offset},
            'pagination': {'total_count': total_count, 'returned_count': len(questions_data), 'has_more': offset + limit < total_count},
            'questions': questions_data,
        })

    except ValueError:
        return Response({'status': 'error', 'message': 'Invalid limit or offset'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Failed to retrieve questions by filters: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_questions_batch(request):
    """
    Get multiple questions by IDs or filter criteria.

    Query params:
        ids         - comma-separated question IDs
        subtopic_id - filter by subtopic
        difficulty  - filter by difficulty
        game_type   - filter by coding/non_coding
        limit       - max results (default: 10)
    """
    try:
        questions_query = GeneratedQuestion.objects.all()

        ids = request.query_params.get('ids')
        if ids:
            id_list = [int(i.strip()) for i in ids.split(',') if i.strip().isdigit()]
            questions_query = questions_query.filter(id__in=id_list)

        subtopic_id = request.query_params.get('subtopic_id')
        if subtopic_id:
            questions_query = questions_query.filter(subtopic_id=subtopic_id)

        difficulty = request.query_params.get('difficulty')
        if difficulty:
            questions_query = questions_query.filter(estimated_difficulty=difficulty)

        game_type = request.query_params.get('game_type')
        if game_type:
            questions_query = questions_query.filter(game_type=game_type)

        limit = int(request.query_params.get('limit', 10))
        questions_data = [format_question_response(q) for q in questions_query.order_by('-id')[:limit]]

        return Response({'status': 'success', 'count': len(questions_data), 'questions': questions_data})

    except Exception as e:
        logger.error(f"Failed to retrieve questions batch: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def get_questions_batch_filtered(request):
    """
    Get questions by batch filter criteria.

    Request body:
        game_type    - coding | non_coding (optional)
        difficulty   - beginner | intermediate | advanced | master (optional)
        minigame_type - specific minigame type (optional)
        limit        - max results (default: 20)
        random       - randomize results (default: false)
    """
    VALID_DIFFICULTIES = ['beginner', 'intermediate', 'advanced', 'master']
    try:
        game_type = request.data.get('game_type')
        difficulty = request.data.get('difficulty')
        minigame_type = request.data.get('minigame_type')
        limit = int(request.data.get('limit', 20))
        random_order = request.data.get('random', False)

        if game_type and game_type not in ['coding', 'non_coding']:
            return Response({'status': 'error', 'message': 'game_type must be "coding" or "non_coding"'}, status=status.HTTP_400_BAD_REQUEST)
        if difficulty and difficulty not in VALID_DIFFICULTIES:
            return Response({'status': 'error', 'message': f'difficulty must be one of: {", ".join(VALID_DIFFICULTIES)}'}, status=status.HTTP_400_BAD_REQUEST)

        questions_query = GeneratedQuestion.objects.all()
        filters_applied = {}

        if game_type:
            questions_query = questions_query.filter(game_type=game_type)
            filters_applied['game_type'] = game_type
        if difficulty:
            questions_query = questions_query.filter(estimated_difficulty=difficulty)
            filters_applied['difficulty'] = difficulty
        if minigame_type:
            questions_query = questions_query.filter(minigame_type=minigame_type)
            filters_applied['minigame_type'] = minigame_type

        questions_query = questions_query.order_by('?') if random_order else questions_query.order_by('-id')
        questions_data = [format_question_response(q) for q in questions_query[:limit]]

        return Response({
            'status': 'success',
            'filters_applied': filters_applied,
            'settings': {'limit': limit, 'random_order': random_order},
            'count': len(questions_data),
            'questions': questions_data,
        })

    except ValueError:
        return Response({'status': 'error', 'message': 'Invalid limit parameter'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Failed to retrieve filtered batch: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# SUBTOPIC / TOPIC VIEWS
# ============================================================

@api_view(['GET'])
def get_subtopic_questions(request, subtopic_id):
    """
    Get all questions for a specific subtopic with optional filters.

    Query params:
        difficulty    - filter by estimated_difficulty
        minigame_type - filter by minigame type
        game_type     - filter by coding/non_coding
    """
    try:
        subtopic = get_object_or_404(Subtopic, id=subtopic_id)
        questions_query = GeneratedQuestion.objects.filter(subtopic=subtopic)

        difficulty = request.query_params.get('difficulty')
        if difficulty:
            questions_query = questions_query.filter(estimated_difficulty=difficulty)

        minigame_type = request.query_params.get('minigame_type')
        if minigame_type:
            questions_query = questions_query.filter(minigame_type=minigame_type)

        game_type = request.query_params.get('game_type')
        if game_type:
            questions_query = questions_query.filter(game_type=game_type)

        questions_query = questions_query.order_by('-created_at')

        questions_data = [{
            'id': q.id,
            'question_text': q.question_text,
            'estimated_difficulty': q.estimated_difficulty,
            'minigame_type': q.minigame_type,
            'game_type': q.game_type,
            'answer_options': q.answer_options,
            'correct_answer': q.correct_answer,
            'explanation': q.explanation,
            'created_at': q.created_at.isoformat(),
            'metadata': q.generation_metadata,
            'quality_score': q.quality_score,
            'validation_status': q.validation_status,
        } for q in questions_query]

        stats = {
            'total_questions': len(questions_data),
            'by_difficulty': dict(questions_query.values('estimated_difficulty').annotate(count=Count('estimated_difficulty')).values_list('estimated_difficulty', 'count')),
            'by_game_type': dict(questions_query.values('game_type').annotate(count=Count('game_type')).values_list('game_type', 'count')),
        }

        return Response({
            'status': 'success',
            'subtopic': {'id': subtopic.id, 'name': subtopic.name, 'topic': subtopic.topic.name, 'zone': subtopic.topic.zone.name},
            'filters_applied': {'difficulty': difficulty, 'minigame_type': minigame_type, 'game_type': game_type},
            'statistics': stats,
            'questions': questions_data,
        })

    except Exception as e:
        logger.error(f"Failed to retrieve questions for subtopic {subtopic_id}: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_topic_questions_summary(request, topic_id):
    """Get a summary of generated questions for a topic across all its subtopics."""
    try:
        topic = get_object_or_404(Topic, id=topic_id)
        subtopics = topic.subtopics.all()
        subtopic_summaries = []
        total_questions = 0

        for subtopic in subtopics:
            questions = GeneratedQuestion.objects.filter(subtopic=subtopic)
            question_count = questions.count()
            total_questions += question_count

            if question_count:
                latest = questions.order_by('-created_at').first()
                subtopic_summaries.append({
                    'subtopic_id': subtopic.id,
                    'subtopic_name': subtopic.name,
                    'question_count': question_count,
                    'difficulty_distribution': dict(questions.values('estimated_difficulty').annotate(count=Count('estimated_difficulty')).values_list('estimated_difficulty', 'count')),
                    'minigame_type_distribution': dict(questions.values('minigame_type').annotate(count=Count('minigame_type')).values_list('minigame_type', 'count')),
                    'game_type_distribution': dict(questions.values('game_type').annotate(count=Count('game_type')).values_list('game_type', 'count')),
                    'latest_generated': latest.created_at.isoformat() if latest else None,
                    'has_questions': True,
                })
            else:
                subtopic_summaries.append({
                    'subtopic_id': subtopic.id,
                    'subtopic_name': subtopic.name,
                    'question_count': 0,
                    'difficulty_distribution': {},
                    'minigame_type_distribution': {},
                    'game_type_distribution': {},
                    'latest_generated': None,
                    'has_questions': False,
                })

        all_questions = GeneratedQuestion.objects.filter(subtopic__topic=topic)
        with_questions = sum(1 for s in subtopic_summaries if s['has_questions'])

        return Response({
            'status': 'success',
            'topic': {'id': topic.id, 'name': topic.name, 'zone': topic.zone.name, 'total_subtopics': subtopics.count()},
            'overall_statistics': {
                'total_questions': total_questions,
                'subtopics_with_questions': with_questions,
                'subtopics_without_questions': len(subtopic_summaries) - with_questions,
                'coverage_percentage': (with_questions / len(subtopic_summaries) * 100) if subtopic_summaries else 0,
                'overall_difficulty_distribution': dict(all_questions.values('estimated_difficulty').annotate(count=Count('estimated_difficulty')).values_list('estimated_difficulty', 'count')),
                'overall_minigame_type_distribution': dict(all_questions.values('minigame_type').annotate(count=Count('minigame_type')).values_list('minigame_type', 'count')),
                'overall_game_type_distribution': dict(all_questions.values('game_type').annotate(count=Count('game_type')).values_list('game_type', 'count')),
            },
            'subtopic_summaries': subtopic_summaries,
        })

    except Exception as e:
        logger.error(f"Failed to get topic questions summary for topic {topic_id}: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)