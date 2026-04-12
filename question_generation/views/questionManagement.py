from .imports import *
from django.db.models import Count


# ============================================================
# HELPERS
# ============================================================

def get_user_level(user):
    """Map user IRT theta to a difficulty level string."""
    try:
        from analytics.models import UserAbility
        theta = UserAbility.objects.get(user=user).theta
    except Exception:
        theta = -1.0  # no record → beginner

    if theta < -0.5:   return 'beginner'
    elif theta < 0.5:  return 'intermediate'
    elif theta < 1.5:  return 'advanced'
    else:              return 'master'


def clean_game_data_for_frontend(game_data):
    """Strip deprecated/internal fields from game_data before sending to client."""
    if not game_data:
        return game_data

    cleaned = game_data.copy()
    for field in ['used', 'context', 'auto_generated', 'pipeline_version', 'is_cross_subtopic']:
        cleaned.pop(field, None)

    if 'rag_context' in cleaned and isinstance(cleaned['rag_context'], dict):
        for field in ['used', 'context']:
            cleaned['rag_context'].pop(field, None)
        if not cleaned['rag_context']:
            cleaned.pop('rag_context', None)

    return cleaned


def format_question_response(question, include_full_game_data=False):
    """Serialize a GeneratedQuestion for API responses."""
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
    Query params:
        page       - page number (default: 1)
        page_size  - items per page (default: 10)
        reason     - partial match on flag_reason
        game_type  - coding | non_coding
        level      - beginner | intermediate | advanced | master
        min_count  - minimum flag count for that level (default: >0)
    """
    VALID_LEVELS = ['beginner', 'intermediate', 'advanced', 'master']
    try:
        page      = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))

        qs = GeneratedQuestion.objects.filter(flagged=True)

        reason = request.query_params.get('reason')
        if reason:
            qs = qs.filter(flag_reason__icontains=reason)

        game_type = request.query_params.get('game_type')
        if game_type:
            qs = qs.filter(game_type=game_type)

        qs = qs.order_by('-flag_created_at')

        level           = request.query_params.get('level')
        min_count_param = request.query_params.get('min_count')

        if level:
            if level not in VALID_LEVELS:
                return Response(
                    {'status': 'error', 'message': f'level must be one of: {", ".join(VALID_LEVELS)}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if min_count_param is not None:
                min_count     = int(min_count_param)
                questions_list = [q for q in qs if (q.flag_count_by_level or {}).get(level, 0) >= min_count]
            else:
                questions_list = [
                    q for q in qs
                    if not q.flag_count_by_level  # legacy: no level data → include anyway
                    or (q.flag_count_by_level or {}).get(level, 0) > 0
                ]
            total_count = len(questions_list)
            offset      = (page - 1) * page_size
            questions   = questions_list[offset:offset + page_size]
        else:
            total_count = qs.count()
            offset      = (page - 1) * page_size
            questions   = qs[offset:offset + page_size]

        results = [
            {
                'id': q.id,
                'question_text': q.question_text,
                'flagged': q.flagged,
                'flag_reason': q.flag_reason,
                'flag_notes': q.flag_notes,
                'flagged_by': q.flagged_by,
                'flag_created_at': q.flag_created_at.isoformat() if q.flag_created_at else None,
                'flag_count_by_level': q.flag_count_by_level or {},
                'game_type': q.game_type,
                'estimated_difficulty': q.estimated_difficulty,
                'correct_answer': q.correct_answer,
                'answer_options': q.game_data.get('answer_options') if q.game_data else None,
                'game_data': clean_game_data_for_frontend(q.game_data),
                'subtopic': {
                    'id': q.subtopic.id,
                    'name': q.subtopic.name,
                    'topic_name': q.subtopic.topic.name,
                },
            }
            for q in questions
        ]

        next_page = page + 1 if offset + page_size < total_count else None
        prev_page = page - 1 if page > 1 else None

        return Response({
            'status': 'success',
            'count': total_count,
            'next':     f"?page={next_page}&page_size={page_size}" if next_page else None,
            'previous': f"?page={prev_page}&page_size={page_size}" if prev_page else None,
            'results': results,
        })

    except ValueError:
        return Response({'status': 'error', 'message': 'Invalid page or page_size'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"get_flagged_questions failed: {e}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def toggle_question_flag(request, question_id):
    """
    Toggle flagged status. When flagging, accepts:
        reason     - flag reason
        note       - additional notes
        flagged_by - username override
    """
    try:
        try:
            question = GeneratedQuestion.objects.get(id=question_id)
        except GeneratedQuestion.DoesNotExist:
            return Response({
                'status': 'error',
                'message': f'Question {question_id} not found.',
                'type': 'QUESTION_NOT_FOUND',
            }, status=status.HTTP_404_NOT_FOUND)

        question.flagged = not question.flagged
        counts     = question.flag_count_by_level if isinstance(question.flag_count_by_level, dict) else {}
        user_level = get_user_level(request.user)

        if question.flagged:
            question.flag_reason    = request.data.get('reason') or None
            question.flag_notes     = request.data.get('note') or None
            question.flagged_by     = request.data.get('flagged_by') or getattr(request.user, 'username', 'anonymous')
            question.flag_created_at = timezone.now()
            counts[user_level]      = counts.get(user_level, 0) + 1
        else:
            question.flag_reason    = None
            question.flag_notes     = None
            question.flagged_by     = None
            question.flag_created_at = None
            counts[user_level]      = max(counts.get(user_level, 0) - 1, 0)

        question.flag_count_by_level = counts
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
            'flag_count_by_level': question.flag_count_by_level,
        })

    except Exception as e:
        logger.error(f"toggle_question_flag failed for {question_id}: {e}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def regenerate_flagged_question(request, question_id):
    """
    Two-step regeneration:

    Step 1 — Preview (no accepted_fields):
        POST { llm_prompt: "..." }
        Returns the full LLM-generated question for the admin to review.
        Nothing is saved to the database.

    Step 2 — Apply (with accepted_fields):
        POST { llm_prompt: "...", regenerated: {...}, accepted_fields: ["question_text", ...] }
        Writes only the accepted fields back to the question.
        If accepted_fields is omitted, all fields are applied (backwards-compatible).

    Coding accepted_fields:
        question_text, buggy_question_text, explanation, buggy_explanation,
        function_name, sample_input, sample_output, hidden_tests,
        buggy_code, correct_code, buggy_correct_code, difficulty

    Non-coding accepted_fields:
        question_text, answer, explanation, difficulty
    """
    from question_generation.helpers.llm_utils import invoke_deepseek, CODING_TEMPERATURE, NON_CODING_TEMPERATURE
    from question_generation.helpers.question_processing import (
        parse_llm_json_response, validate_question_data, format_question_for_game_type,
    )
    try:
        try:
            question = GeneratedQuestion.objects.get(id=question_id)
        except GeneratedQuestion.DoesNotExist:
            return Response({'status': 'error', 'message': f'Question {question_id} not found'}, status=status.HTTP_404_NOT_FOUND)

        llm_prompt = (request.data.get('llm_prompt', '') or '').strip()
        if not llm_prompt:
            return Response({'status': 'error', 'message': 'llm_prompt is required'}, status=status.HTTP_400_BAD_REQUEST)

        game_type   = question.game_type
        temperature = CODING_TEMPERATURE if game_type == 'coding' else NON_CODING_TEMPERATURE

        # ── Step 2: apply a previously previewed result ───────────────────────
        regenerated_data = request.data.get('regenerated')
        accepted_fields  = request.data.get('accepted_fields')  # None = apply all

        if regenerated_data is not None:
            q = format_question_for_game_type(regenerated_data, game_type)
            return _apply_regenerated_question(
                request, question, q, game_type, llm_prompt, accepted_fields
            )

        # ── Step 1: call the LLM and return a preview ─────────────────────────
        if game_type == 'coding':
            system_prompt = (
            "You are a Python question generator. Regenerate the given question based on the instructions.\n"
            "OUTPUT ONLY VALID JSON ARRAY. NO prose, NO markdown, NO backticks.\n\n"
            "RULES:\n"
            "- Simple real-world tasks, no external libs, under 20 lines per code block.\n"
            "- snake_case function names.\n"
            "- All hidden_tests must use 'expected_output' as the key.\n"
            "- Function signature must be IDENTICAL across all code fields.\n\n"
            "CODE FIELDS:\n"
            "'clean_solution': correct implementation from scratch. Must pass all hidden_tests.\n"
            "'code_shown_to_student': broken version with EXACTLY ONE bug causing wrong output, not a crash.\n"
            "'code_with_bug_fixed': code_shown_to_student with only the bug corrected. Must pass all hidden_tests.\n\n"
            "VERIFY BEFORE OUTPUTTING:\n"
            "- code_shown_to_student produces WRONG output on sample_input\n"
            "- code_with_bug_fixed produces CORRECT output on sample_input\n"
            "- clean_solution produces CORRECT output on sample_input\n\n"
            "RETURN a JSON array with exactly 1 item:\n"
            "[\n"
            "  {\n"
            '    "question_text":         "brief task (12 words max)",\n'
            '    "buggy_question_text":   "visible symptom in Debugging (8-20 words)",\n'
            '    "explanation":           "post-Hangman explanation (30-40 words, friendly tone)",\n'
            '    "buggy_explanation":     "post-Debugging explanation (30-40 words, friendly tone)",\n'
            '    "function_name":         "snake_case",\n'
            '    "sample_input":          "(example,)",\n'
            '    "sample_output":         "expected correct output",\n'
            '    "hidden_tests":          [{"input": "(test,)", "expected_output": "result"}],\n'
            '    "clean_solution":        "def name(...):\\n    ...",\n'
            '    "code_shown_to_student": "def name(...):\\n    ...",\n'
            '    "code_with_bug_fixed":   "def name(...):\\n    ...",\n'
            '    "difficulty":            "beginner|intermediate|advanced|master"\n'
            "  }\n"
            "]\n"
            "RETURN: JSON array ONLY."
        )
        else:
            system_prompt = (
            "You are a Python concept quiz creator. Regenerate the given question based on the instructions.\n"
            "OUTPUT ONLY VALID JSON ARRAY. NO prose, NO markdown, NO backticks.\n\n"
            "RULES:\n"
            "- Answer must be a single term, 4-13 letters only, domain-specific.\n"
            "- No code blocks or symbols in question_text, letters and spaces only.\n"
            "- Frame as a crossword-style clue, not a textbook question.\n\n"
            "RETURN a JSON array with exactly 1 item:\n"
            "[\n"
            "  {\n"
            '    "question_text": "short unambiguous clue (18 words max)",\n'
            '    "answer":        "singleterm",\n'
            '    "explanation":   "brief concept note (30-40 words, friendly tone)",\n'
            '    "difficulty":    "beginner|intermediate|advanced|master"\n'
            "  }\n"
            "]\n"
            "RETURN: JSON array ONLY."
        )

        llm_response   = invoke_deepseek(llm_prompt, system_prompt=system_prompt, temperature=temperature, max_tokens=4000)
        questions_json = parse_llm_json_response(llm_response, game_type)

        if not questions_json:
            return Response({'status': 'error', 'message': 'LLM returned an unparseable response'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if not validate_question_data(questions_json[0], game_type):
            return Response({'status': 'error', 'message': 'Regenerated question failed validation'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        q = format_question_for_game_type(questions_json[0], game_type)

        if game_type == 'coding':
            accepted_fields_available = [
        'question_text', 'buggy_question_text', 'explanation', 'buggy_explanation',
        'function_name', 'sample_input', 'sample_output', 'hidden_tests',
        'clean_solution', 'code_shown_to_student', 'code_with_bug_fixed', 'difficulty',
    ]
        else:
            accepted_fields_available = ['question_text', 'answer', 'explanation', 'difficulty']

        return Response({
            'status': 'preview',
            'message': 'Review the regenerated question and choose which fields to apply.',
            'question_id': question_id,
            'game_type': game_type,
            'accepted_fields_available': accepted_fields_available,
            'current': _serialize_current(question, game_type),
            'regenerated': q,
        })

    except Exception as e:
        logger.error(f"regenerate_flagged_question failed for {question_id}: {e}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _serialize_current(question, game_type):
    gd = question.game_data or {}
    if game_type == 'coding':
        return {
            'question_text':         question.question_text,
            'buggy_question_text':   gd.get('buggy_question_text', ''),
            'explanation':           gd.get('explanation', ''),
            'buggy_explanation':     gd.get('buggy_explanation', ''),
            'function_name':         gd.get('function_name', ''),
            'sample_input':          gd.get('sample_input', ''),
            'sample_output':         gd.get('sample_output', ''),
            'hidden_tests':          gd.get('hidden_tests', []),
            # new field names with fallback for old questions
            'clean_solution':        gd.get('clean_solution') or gd.get('correct_code', ''),
            'code_shown_to_student': gd.get('code_shown_to_student') or gd.get('buggy_code', ''),
            'code_with_bug_fixed':   gd.get('code_with_bug_fixed') or gd.get('buggy_correct_code', ''),
            'difficulty':            question.estimated_difficulty,
        }
    else:
        return {
            'question_text': question.question_text,
            'answer':        question.correct_answer,
            'explanation':   gd.get('explanation', ''),
            'difficulty':    question.estimated_difficulty,
        }


def _apply_regenerated_question(request, question, q, game_type, llm_prompt, accepted_fields):
    """Write accepted fields from a regenerated question back to the DB."""
    game_data = question.game_data or {}

    if game_type == 'coding':
        all_fields = {
        'question_text':         ('model',     'question_text'),
        'buggy_question_text':   ('game_data', 'buggy_question_text'),
        'explanation':           ('game_data', 'explanation'),
        'buggy_explanation':     ('game_data', 'buggy_explanation'),
        'function_name':         ('game_data', 'function_name'),
        'sample_input':          ('game_data', 'sample_input'),
        'sample_output':         ('game_data', 'sample_output'),
        'hidden_tests':          ('game_data', 'hidden_tests'),
        'clean_solution':        ('both',      'clean_solution'),   # correct_answer + game_data
        'code_shown_to_student': ('game_data', 'code_shown_to_student'),
        'code_with_bug_fixed':   ('game_data', 'code_with_bug_fixed'),
        'difficulty':            ('model',     'estimated_difficulty'),
    }
    else:
        all_fields = {
            'question_text': ('model',    'question_text'),
            'answer':        ('model',    'correct_answer'),
            'explanation':   ('game_data', 'explanation'),
            'difficulty':    ('model',    'estimated_difficulty'),
        }

    fields_to_apply = set(accepted_fields) if accepted_fields is not None else set(all_fields.keys())
    invalid = fields_to_apply - set(all_fields.keys())
    if invalid:
        return Response(
            {'status': 'error', 'message': f'Unknown accepted_fields: {sorted(invalid)}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    applied = []
    for field in fields_to_apply:
        destination, db_key = all_fields[field]
        value = q.get(field)
        if value is None:
            continue
        if destination == 'model':
            setattr(question, db_key, value)
        elif destination == 'game_data':
            game_data[db_key] = value
        elif destination == 'both':
            question.correct_answer = value
            game_data[db_key] = value
        applied.append(field)

    regen_context = {
        'flag_reason':            question.flag_reason,
        'flag_notes':             question.flag_notes,
        'llm_regeneration_prompt': llm_prompt,
        'regenerated_at':         timezone.now().isoformat(),
        'regenerated_by':         getattr(request.user, 'username', 'system'),
        'accepted_fields':        sorted(applied),
    }
    game_data['_regeneration_context'] = regen_context

    question.game_data         = game_data
    question.validation_status = 'pending'
    question.flagged           = False
    question.flag_reason       = None
    question.flag_notes        = None
    question.flagged_by        = None
    question.flag_created_at   = None
    question.save()

    return Response({
        'status':           'success',
        'message':          'Question updated successfully',
        'question_id':      question.id,
        'applied_fields':   sorted(applied),
        'regeneration_context': regen_context,
    })


# ============================================================
# SINGLE QUESTION RETRIEVAL
# ============================================================

@api_view(['GET'])
def get_question_by_id(request, question_id):
    """
    Query params:
        full_context - include full RAG context if 'true' (default: false)
    """
    try:
        question              = get_object_or_404(GeneratedQuestion, id=question_id)
        include_full_game_data = request.query_params.get('full_context', 'false').lower() == 'true'
        return Response({'status': 'success', 'question': format_question_response(question, include_full_game_data)})

    except Exception as e:
        logger.error(f"get_question_by_id failed for {question_id}: {e}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# BULK / FILTERED RETRIEVAL
# ============================================================

@api_view(['GET'])
def get_all_questions(request):
    """
    Query params:
        limit    - max results (default: 50)
        offset   - pagination offset (default: 0)
        order_by - id | created_at | estimated_difficulty | game_type (default: created_at)
        order    - asc | desc (default: desc)
    """
    VALID_ORDER_FIELDS = ['id', 'created_at', 'estimated_difficulty', 'game_type']
    try:
        limit    = int(request.query_params.get('limit', 50))
        offset   = int(request.query_params.get('offset', 0))
        order_by = request.query_params.get('order_by', 'created_at')
        order    = request.query_params.get('order', 'desc')

        if order_by not in VALID_ORDER_FIELDS:
            return Response({'status': 'error', 'message': f'order_by must be one of: {", ".join(VALID_ORDER_FIELDS)}'}, status=status.HTTP_400_BAD_REQUEST)
        if order not in ['asc', 'desc']:
            return Response({'status': 'error', 'message': 'order must be "asc" or "desc"'}, status=status.HTTP_400_BAD_REQUEST)

        order_field = f"-{order_by}" if order == 'desc' else order_by
        qs          = GeneratedQuestion.objects.all().order_by(order_field)
        total_count = qs.count()
        questions   = [format_question_response(q) for q in qs[offset:offset + limit]]

        return Response({
            'status': 'success',
            'pagination': {
                'total_count': total_count, 'returned_count': len(questions),
                'limit': limit, 'offset': offset, 'has_more': offset + limit < total_count,
            },
            'ordering': {'order_by': order_by, 'order': order},
            'questions': questions,
        })

    except ValueError:
        return Response({'status': 'error', 'message': 'Invalid limit, offset, or ordering parameter'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"get_all_questions failed: {e}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_questions_by_filters(request):
    """
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

        limit  = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))

        qs = GeneratedQuestion.objects.filter(game_type=game_type)
        if difficulty:
            qs = qs.filter(estimated_difficulty=difficulty)
        qs = qs.order_by('-id')

        total_count = qs.count()
        questions   = [format_question_response(q) for q in qs[offset:offset + limit]]

        return Response({
            'status': 'success',
            'filters_applied': {'game_type': game_type, 'difficulty': difficulty, 'limit': limit, 'offset': offset},
            'pagination': {'total_count': total_count, 'returned_count': len(questions), 'has_more': offset + limit < total_count},
            'questions': questions,
        })

    except ValueError:
        return Response({'status': 'error', 'message': 'Invalid limit or offset'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"get_questions_by_filters failed: {e}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_questions_batch(request):
    """
    Query params:
        ids         - comma-separated question IDs
        subtopic_id - filter by subtopic
        difficulty  - filter by difficulty
        game_type   - filter by coding/non_coding
        limit       - max results (default: 10)
    """
    try:
        qs = GeneratedQuestion.objects.all()

        ids = request.query_params.get('ids')
        if ids:
            id_list = [int(i.strip()) for i in ids.split(',') if i.strip().isdigit()]
            qs = qs.filter(id__in=id_list)

        subtopic_id = request.query_params.get('subtopic_id')
        if subtopic_id:
            qs = qs.filter(subtopic_id=subtopic_id)

        difficulty = request.query_params.get('difficulty')
        if difficulty:
            qs = qs.filter(estimated_difficulty=difficulty)

        game_type = request.query_params.get('game_type')
        if game_type:
            qs = qs.filter(game_type=game_type)

        limit     = int(request.query_params.get('limit', 10))
        questions = [format_question_response(q) for q in qs.order_by('-id')[:limit]]

        return Response({'status': 'success', 'count': len(questions), 'questions': questions})

    except Exception as e:
        logger.error(f"get_questions_batch failed: {e}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def get_questions_batch_filtered(request):
    """
    Request body:
        game_type     - coding | non_coding (optional)
        difficulty    - beginner | intermediate | advanced | master (optional)
        minigame_type - specific minigame type (optional)
        limit         - max results (default: 20)
        random        - randomize results (default: false)
    """
    VALID_DIFFICULTIES = ['beginner', 'intermediate', 'advanced', 'master']
    try:
        game_type     = request.data.get('game_type')
        difficulty    = request.data.get('difficulty')
        minigame_type = request.data.get('minigame_type')
        limit         = int(request.data.get('limit', 20))
        random_order  = request.data.get('random', False)

        if game_type and game_type not in ['coding', 'non_coding']:
            return Response({'status': 'error', 'message': 'game_type must be "coding" or "non_coding"'}, status=status.HTTP_400_BAD_REQUEST)
        if difficulty and difficulty not in VALID_DIFFICULTIES:
            return Response({'status': 'error', 'message': f'difficulty must be one of: {", ".join(VALID_DIFFICULTIES)}'}, status=status.HTTP_400_BAD_REQUEST)

        qs              = GeneratedQuestion.objects.all()
        filters_applied = {}

        if game_type:
            qs = qs.filter(game_type=game_type)
            filters_applied['game_type'] = game_type
        if difficulty:
            qs = qs.filter(estimated_difficulty=difficulty)
            filters_applied['difficulty'] = difficulty
        if minigame_type:
            qs = qs.filter(minigame_type=minigame_type)
            filters_applied['minigame_type'] = minigame_type

        qs        = qs.order_by('?') if random_order else qs.order_by('-id')
        questions = [format_question_response(q) for q in qs[:limit]]

        return Response({
            'status': 'success',
            'filters_applied': filters_applied,
            'settings': {'limit': limit, 'random_order': random_order},
            'count': len(questions),
            'questions': questions,
        })

    except ValueError:
        return Response({'status': 'error', 'message': 'Invalid limit parameter'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"get_questions_batch_filtered failed: {e}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# SUBTOPIC / TOPIC VIEWS
# ============================================================

@api_view(['GET'])
def get_subtopic_questions(request, subtopic_id):
    """
    Query params:
        difficulty    - filter by estimated_difficulty
        minigame_type - filter by minigame type
        game_type     - filter by coding/non_coding
    """
    try:
        subtopic = get_object_or_404(Subtopic, id=subtopic_id)
        qs       = GeneratedQuestion.objects.filter(subtopic=subtopic)

        difficulty = request.query_params.get('difficulty')
        if difficulty:
            qs = qs.filter(estimated_difficulty=difficulty)

        minigame_type = request.query_params.get('minigame_type')
        if minigame_type:
            qs = qs.filter(minigame_type=minigame_type)

        game_type = request.query_params.get('game_type')
        if game_type:
            qs = qs.filter(game_type=game_type)

        qs = qs.order_by('-created_at')

        questions = [
            {
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
            }
            for q in qs
        ]

        stats = {
            'total_questions': len(questions),
            'by_difficulty': dict(qs.values('estimated_difficulty').annotate(count=Count('estimated_difficulty')).values_list('estimated_difficulty', 'count')),
            'by_game_type':  dict(qs.values('game_type').annotate(count=Count('game_type')).values_list('game_type', 'count')),
        }

        return Response({
            'status': 'success',
            'subtopic': {'id': subtopic.id, 'name': subtopic.name, 'topic': subtopic.topic.name, 'zone': subtopic.topic.zone.name},
            'filters_applied': {'difficulty': difficulty, 'minigame_type': minigame_type, 'game_type': game_type},
            'statistics': stats,
            'questions': questions,
        })

    except Exception as e:
        logger.error(f"get_subtopic_questions failed for subtopic {subtopic_id}: {e}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_topic_questions_summary(request, topic_id):
    """Summary of question counts and distributions for all subtopics in a topic."""
    try:
        topic     = get_object_or_404(Topic, id=topic_id)
        subtopics = topic.subtopics.all()
        summaries = []
        total     = 0

        for subtopic in subtopics:
            qs    = GeneratedQuestion.objects.filter(subtopic=subtopic)
            count = qs.count()
            total += count

            summaries.append({
                'subtopic_id':   subtopic.id,
                'subtopic_name': subtopic.name,
                'question_count': count,
                'has_questions': count > 0,
                'difficulty_distribution':   dict(qs.values('estimated_difficulty').annotate(c=Count('estimated_difficulty')).values_list('estimated_difficulty', 'c')) if count else {},
                'minigame_type_distribution': dict(qs.values('minigame_type').annotate(c=Count('minigame_type')).values_list('minigame_type', 'c')) if count else {},
                'game_type_distribution':    dict(qs.values('game_type').annotate(c=Count('game_type')).values_list('game_type', 'c')) if count else {},
                'latest_generated': qs.order_by('-created_at').first().created_at.isoformat() if count else None,
            })

        all_qs        = GeneratedQuestion.objects.filter(subtopic__topic=topic)
        with_questions = sum(1 for s in summaries if s['has_questions'])

        return Response({
            'status': 'success',
            'topic': {'id': topic.id, 'name': topic.name, 'zone': topic.zone.name, 'total_subtopics': subtopics.count()},
            'overall_statistics': {
                'total_questions': total,
                'subtopics_with_questions':    with_questions,
                'subtopics_without_questions': len(summaries) - with_questions,
                'coverage_percentage': (with_questions / len(summaries) * 100) if summaries else 0,
                'overall_difficulty_distribution':    dict(all_qs.values('estimated_difficulty').annotate(c=Count('estimated_difficulty')).values_list('estimated_difficulty', 'c')),
                'overall_minigame_type_distribution': dict(all_qs.values('minigame_type').annotate(c=Count('minigame_type')).values_list('minigame_type', 'c')),
                'overall_game_type_distribution':     dict(all_qs.values('game_type').annotate(c=Count('game_type')).values_list('game_type', 'c')),
            },
            'subtopic_summaries': summaries,
        })

    except Exception as e:
        logger.error(f"get_topic_questions_summary failed for topic {topic_id}: {e}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
