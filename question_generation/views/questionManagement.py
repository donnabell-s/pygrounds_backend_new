"""
Question management and CRUD operations for retrieval, filtering, and statistics for generated questions.
"""

from .imports import *
from django.db.models import Count

@api_view(['GET'])
def get_subtopic_questions(request, subtopic_id):
    """
    Get all generated questions for a specific subtopic, with filters.
    Query params:
        - difficulty: filter by difficulty (estimated_difficulty)
        - minigame_type: filter by minigame type
        - game_type: filter by coding/non-coding
    """
    try:
        subtopic = get_object_or_404(Subtopic, id=subtopic_id)
        questions_query = GeneratedQuestion.objects.filter(subtopic=subtopic)
        
        # Filtering
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
        questions = list(questions_query)
        
        # Prepare response data
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
        } for q in questions]

        # Statistics
        stats = {
            'total_questions': len(questions),
            'by_difficulty': dict(questions_query.values('estimated_difficulty').annotate(count=Count('estimated_difficulty')).values_list('estimated_difficulty', 'count')),
            'by_game_type': dict(questions_query.values('game_type').annotate(count=Count('game_type')).values_list('game_type', 'count')),
        }

        return Response({
            'status': 'success',
            'subtopic': {
                'id': subtopic.id,
                'name': subtopic.name,
                'topic': subtopic.topic.name,
                'zone': subtopic.topic.zone.name
            },
            'filters_applied': {
                'difficulty': difficulty,
                'minigame_type': minigame_type,
                'game_type': game_type,
            },
            'statistics': stats,
            'questions': questions_data
        })

    except Exception as e:
        logger.error(f"Failed to retrieve questions for subtopic {subtopic_id}: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_topic_questions_summary(request, topic_id):
    """
    Get a summary of generated questions for a topic across all its subtopics.
    """
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
                difficulty_dist = dict(questions.values('estimated_difficulty').annotate(count=Count('estimated_difficulty')).values_list('estimated_difficulty', 'count'))
                minigame_type_dist = dict(questions.values('minigame_type').annotate(count=Count('minigame_type')).values_list('minigame_type', 'count'))
                game_type_dist = dict(questions.values('game_type').annotate(count=Count('game_type')).values_list('game_type', 'count'))
                latest = questions.order_by('-created_at').first()

                subtopic_summaries.append({
                    'subtopic_id': subtopic.id,
                    'subtopic_name': subtopic.name,
                    'question_count': question_count,
                    'difficulty_distribution': difficulty_dist,
                    'minigame_type_distribution': minigame_type_dist,
                    'game_type_distribution': game_type_dist,
                    'latest_generated': latest.created_at.isoformat() if latest else None,
                    'has_questions': True
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
                    'has_questions': False
                })

        all_questions = GeneratedQuestion.objects.filter(subtopic__topic=topic)
        overall_stats = {
            'total_questions': total_questions,
            'subtopics_with_questions': sum(1 for s in subtopic_summaries if s['has_questions']),
            'subtopics_without_questions': sum(1 for s in subtopic_summaries if not s['has_questions']),
            'coverage_percentage': (sum(1 for s in subtopic_summaries if s['has_questions']) / len(subtopic_summaries) * 100) if subtopic_summaries else 0,
            'overall_difficulty_distribution': dict(all_questions.values('estimated_difficulty').annotate(count=Count('estimated_difficulty')).values_list('estimated_difficulty', 'count')),
            'overall_minigame_type_distribution': dict(all_questions.values('minigame_type').annotate(count=Count('minigame_type')).values_list('minigame_type', 'count')),
            'overall_game_type_distribution': dict(all_questions.values('game_type').annotate(count=Count('game_type')).values_list('game_type', 'count')),
        }

        return Response({
            'status': 'success',
            'topic': {
                'id': topic.id,
                'name': topic.name,
                'zone': topic.zone.id,
                'zone_name': topic.zone.name,  # Explicit zone_name field
                'total_subtopics': subtopics.count(),
                'subtopics_count': subtopics.count()  # Explicit subtopics_count field as int
            },
            'overall_statistics': overall_stats,
            'subtopic_summaries': subtopic_summaries
        })

    except Exception as e:
        logger.error(f"Failed to get topic questions summary for topic {topic_id}: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_question_by_id(request, question_id):
    """
    Get a specific generated question by ID with complete game data.
    Query params:
        - full_context: if 'true', includes full RAG context (default: false for cleaner response)
    """
    try:
        question = get_object_or_404(GeneratedQuestion, id=question_id)
        
        # Check if full context is requested
        include_full_game_data = request.query_params.get('full_context', 'false').lower() == 'true'
        
        question_data = format_question_response(question, include_full_game_data)
        
        # Add extra fields for single question view
        question_data.update({
            'subtopic': {
                'id': question.subtopic.id,
                'name': question.subtopic.name,
                'topic': {
                    'id': question.topic.id,
                    'name': question.topic.name,
                    'zone': question.topic.zone.name if hasattr(question.topic, 'zone') else None
                }
            }
        })

        return Response({
            'status': 'success',
            'question': question_data
        })

    except Exception as e:
        logger.error(f"Failed to retrieve question {question_id}: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_questions_batch(request):
    """
    Get multiple questions by IDs or filter criteria. 
    Useful for frontend to fetch a batch of questions efficiently.
    
    Query params:
        - ids: comma-separated question IDs (e.g., "1,2,3")
        - subtopic_id: filter by subtopic
        - difficulty: filter by difficulty
        - game_type: filter by coding/non-coding
        - limit: max number of questions to return (default: 10)
    """
    try:
        questions_query = GeneratedQuestion.objects.all()
        
        # Filter by IDs if provided
        question_ids = request.query_params.get('ids')
        if question_ids:
            id_list = [int(id.strip()) for id in question_ids.split(',') if id.strip().isdigit()]
            questions_query = questions_query.filter(id__in=id_list)
        
        # Additional filters
        subtopic_id = request.query_params.get('subtopic_id')
        if subtopic_id:
            questions_query = questions_query.filter(subtopic_id=subtopic_id)
            
        difficulty = request.query_params.get('difficulty')
        if difficulty:
            questions_query = questions_query.filter(estimated_difficulty=difficulty)
            
        game_type = request.query_params.get('game_type')
        if game_type:
            questions_query = questions_query.filter(game_type=game_type)
        
        # Limit results
        limit = int(request.query_params.get('limit', 10))
        questions_query = questions_query.order_by('-id')[:limit]
        
        # Format response
        questions_data = []
        for question in questions_query:
            questions_data.append({
                'id': question.id,
                'question_text': question.question_text,
                'correct_answer': question.correct_answer,
                'estimated_difficulty': question.estimated_difficulty,
                'game_type': question.game_type,
                'validation_status': question.validation_status,
                'game_data': question.game_data,  # Complete game data
                'subtopic': {
                    'id': question.subtopic.id,
                    'name': question.subtopic.name,
                    'topic_name': question.topic.name
                },
                'created_at': question.created_at.isoformat() if hasattr(question, 'created_at') else None
            })

        return Response({
            'status': 'success',
            'count': len(questions_data),
            'questions': questions_data
        })

    except Exception as e:
        logger.error(f"Failed to retrieve questions batch: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_questions_by_filters(request):
    """
    Get questions filtered by game_type and difficulty.
    Query params:
        - game_type: 'coding' or 'non_coding' (required)
        - difficulty: 'beginner', 'intermediate', 'advanced', 'master' (optional)
        - limit: max number of questions to return (optional, default 20)
        - offset: pagination offset (optional, default 0)
    """
    try:
        # Required parameter
        game_type = request.query_params.get('game_type')
        if not game_type:
            return Response({
                'status': 'error', 
                'message': 'game_type parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if game_type not in ['coding', 'non_coding']:
            return Response({
                'status': 'error', 
                'message': 'game_type must be either "coding" or "non_coding"'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Start with base query
        questions_query = GeneratedQuestion.objects.filter(game_type=game_type)
        
        # Optional filters
        difficulty = request.query_params.get('difficulty')
        if difficulty:
            if difficulty not in ['beginner', 'intermediate', 'advanced', 'master']:
                return Response({
                    'status': 'error', 
                    'message': 'difficulty must be one of: beginner, intermediate, advanced, master'
                }, status=status.HTTP_400_BAD_REQUEST)
            questions_query = questions_query.filter(estimated_difficulty=difficulty)
        
        # Pagination
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))
        
        # Order by creation date (newest first)
        questions_query = questions_query.order_by('-id')
        
        # Get total count before pagination
        total_count = questions_query.count()
        
        # Apply pagination
        questions = questions_query[offset:offset + limit]
        
        # Prepare response data
        questions_data = []
        for question in questions:
            questions_data.append({
                'id': question.id,
                'question_text': question.question_text,
                'correct_answer': question.correct_answer,
                'estimated_difficulty': question.estimated_difficulty,
                'game_type': question.game_type,
                'validation_status': question.validation_status,
                'game_data': question.game_data,  # Complete game data including buggy_code, etc.
                'subtopic': {
                    'id': question.subtopic.id,
                    'name': question.subtopic.name,
                    'topic_name': question.topic.name,
                    'zone_name': question.topic.zone.name
                },
            })

        return Response({
            'status': 'success',
            'filters_applied': {
                'game_type': game_type,
                'difficulty': difficulty,
                'limit': limit,
                'offset': offset
            },
            'pagination': {
                'total_count': total_count,
                'returned_count': len(questions_data),
                'has_more': offset + limit < total_count
            },
            'questions': questions_data
        })

    except ValueError as e:
        return Response({
            'status': 'error', 
            'message': 'Invalid limit or offset parameter'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Failed to retrieve questions by filters: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_all_questions(request):
    """
    Get all generated questions with optional pagination.
    Returns all questions in the database with complete game data.
    
    Query params:
        - limit: max number of questions to return (optional, default 50)
        - offset: pagination offset (optional, default 0)
        - order_by: sort field - 'id', 'created_at', 'difficulty', 'game_type' (optional, default 'id')
        - order: 'asc' or 'desc' (optional, default 'desc' for newest first)
    
    Example: GET /questions/all/?limit=100&offset=0&order_by=created_at&order=desc
    """
    try:
        # Pagination parameters
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        
        # Ordering parameters
        order_by = request.query_params.get('order_by', 'id')
        order = request.query_params.get('order', 'desc')
        
        # Validate order_by field
        valid_order_fields = ['id', 'created_at', 'estimated_difficulty', 'game_type']
        if order_by not in valid_order_fields:
            return Response({
                'status': 'error', 
                'message': f'order_by must be one of: {", ".join(valid_order_fields)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate order direction
        if order not in ['asc', 'desc']:
            return Response({
                'status': 'error', 
                'message': 'order must be either "asc" or "desc"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Build order string
        order_field = f"-{order_by}" if order == 'desc' else order_by
        
        # Get all questions with ordering
        questions_query = GeneratedQuestion.objects.all().order_by(order_field)
        
        # Get total count before pagination
        total_count = questions_query.count()
        
        # Apply pagination
        questions = questions_query[offset:offset + limit]
        
        # Prepare response data using the helper function
        questions_data = [format_question_response(q) for q in questions]

        return Response({
            'status': 'success',
            'pagination': {
                'total_count': total_count,
                'returned_count': len(questions_data),
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total_count
            },
            'ordering': {
                'order_by': order_by,
                'order': order
            },
            'questions': questions_data
        })

    except ValueError as e:
        return Response({
            'status': 'error', 
            'message': 'Invalid limit, offset, or ordering parameter'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Failed to retrieve all questions: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def get_questions_batch_filtered(request):
    """
    Get multiple questions by batch criteria (game_type, difficulty, etc.).
    More flexible than get_questions_batch - instead of specific IDs, filter by criteria.
    
    Request body:
    {
        "game_type": "coding",           // optional: "coding" or "non_coding"
        "difficulty": "beginner",        // optional: "beginner", "intermediate", "advanced", "master"
        "minigame_type": "hangman_coding", // optional: specific minigame type
        "limit": 20,                     // optional: max results (default 20)
        "random": true                   // optional: randomize results (default false)
    }
    
    Example: POST /questions/batch/filtered/
    {
        "game_type": "coding",
        "difficulty": "beginner", 
        "limit": 10,
        "random": true
    }
    """
    try:
        # Get filter criteria from request body
        game_type = request.data.get('game_type')
        difficulty = request.data.get('difficulty')
        minigame_type = request.data.get('minigame_type')
        limit = int(request.data.get('limit', 20))
        random_order = request.data.get('random', False)
        
        # Validate parameters
        if game_type and game_type not in ['coding', 'non_coding']:
            return Response({
                'status': 'error', 
                'message': 'game_type must be either "coding" or "non_coding"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if difficulty and difficulty not in ['beginner', 'intermediate', 'advanced', 'master']:
            return Response({
                'status': 'error', 
                'message': 'difficulty must be one of: beginner, intermediate, advanced, master'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Start with base query
        questions_query = GeneratedQuestion.objects.all()
        
        # Apply filters
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
        
        # Apply ordering
        if random_order:
            questions_query = questions_query.order_by('?')  # Random ordering
        else:
            questions_query = questions_query.order_by('-id')  # Newest first
        
        # Apply limit
        questions = questions_query[:limit]
        
        # Prepare response data
        questions_data = []
        for question in questions:
            questions_data.append({
                'id': question.id,
                'question_text': question.question_text,
                'correct_answer': question.correct_answer,
                'estimated_difficulty': question.estimated_difficulty,
                'game_type': question.game_type,
                'validation_status': question.validation_status,
                'game_data': question.game_data,  # Complete game data including buggy_code, etc.
                'subtopic': {
                    'id': question.subtopic.id,
                    'name': question.subtopic.name,
                    'topic_name': question.topic.name,
                    'zone_name': question.topic.zone.name
                },
            })

        return Response({
            'status': 'success',
            'filters_applied': filters_applied,
            'settings': {
                'limit': limit,
                'random_order': random_order
            },
            'count': len(questions_data),
            'questions': questions_data
        })

    except ValueError as e:
        return Response({
            'status': 'error', 
            'message': 'Invalid limit parameter'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Failed to retrieve filtered batch: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def clean_game_data_for_frontend(game_data):
    """
    Clean game_data by removing or truncating long fields.
    Keeps essential game information while reducing response size.
    """
    if not game_data:
        return game_data

    # Create a copy to avoid modifying the original
    cleaned_data = game_data.copy()

    # Remove deprecated/unused fields from game_data
    # Keep CRUD-essential fields like is_cross_subtopic for frontend editing
    fields_to_remove = ['used', 'context', 'auto_generated', 'pipeline_version']
    for field in fields_to_remove:
        cleaned_data.pop(field, None)

    # Remove deprecated fields from nested rag_context if it exists
    if 'rag_context' in cleaned_data and isinstance(cleaned_data['rag_context'], dict):
        rag_context_fields_to_remove = ['used', 'context']
        for field in rag_context_fields_to_remove:
            cleaned_data['rag_context'].pop(field, None)

        # Remove rag_context entirely if it's empty
        if not cleaned_data['rag_context']:
            cleaned_data.pop('rag_context', None)

    return cleaned_data


def format_question_response(question, include_full_game_data=False):
    """
    Format a question object for API response with optional game_data cleaning.
    """
    game_data = question.game_data if include_full_game_data else clean_game_data_for_frontend(question.game_data)

    response = {
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
            'topic_name': question.topic.name,
            'zone_name': question.topic.zone.name
        },
        'created_at': question.created_at.isoformat() if hasattr(question, 'created_at') else None
    }

    # Add coding-specific fields at top level for CRUD operations
    if question.game_type == 'coding' and game_data:
        response.update({
            'correct_code': game_data.get('correct_code', ''),
            'hidden_tests': game_data.get('hidden_tests', []),
            'sample_input': game_data.get('sample_input', ''),
            'function_name': game_data.get('function_name', ''),
            'sample_output': game_data.get('sample_output', ''),
            'buggy_explanation': game_data.get('buggy_explanation', ''),
            'buggy_correct_code': game_data.get('buggy_correct_code', ''),
            'buggy_question_text': game_data.get('buggy_question_text', ''),
            'subtopic_ids': game_data.get('subtopic_ids', []),
            'subtopic_names': game_data.get('subtopic_names', []),
            'subtopic_count': game_data.get('subtopic_count', 1),
            'is_cross_subtopic': game_data.get('is_cross_subtopic', False)
        })

    return response


@api_view(['GET'])
def get_all_coding_questions(request):
    """
    Get all coding questions with pagination.
    Query params: limit, offset, order_by, order
    """
    try:
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        order_by = request.query_params.get('order_by', 'id')
        order = request.query_params.get('order', 'desc')
        
        # Validate parameters
        valid_order_fields = ['id', 'created_at', 'estimated_difficulty']
        if order_by not in valid_order_fields:
            return Response({
                'status': 'error', 
                'message': f'order_by must be one of: {", ".join(valid_order_fields)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if order not in ['asc', 'desc']:
            return Response({
                'status': 'error', 
                'message': 'order must be either "asc" or "desc"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Build query
        order_field = f"-{order_by}" if order == 'desc' else order_by
        questions_query = GeneratedQuestion.objects.filter(game_type='coding').order_by(order_field)
        
        total_count = questions_query.count()
        questions = questions_query[offset:offset + limit]
        
        questions_data = [format_question_response(q) for q in questions]

        return Response({
            'status': 'success',
            'game_type': 'coding',
            'pagination': {
                'total_count': total_count,
                'returned_count': len(questions_data),
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total_count
            },
            'questions': questions_data
        })

    except ValueError as e:
        return Response({'status': 'error', 'message': 'Invalid pagination parameters'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Failed to retrieve coding questions: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_all_non_coding_questions(request):
    """
    Get all non-coding questions with pagination.
    Query params: limit, offset, order_by, order
    """
    try:
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        order_by = request.query_params.get('order_by', 'id')
        order = request.query_params.get('order', 'desc')
        
        # Validate parameters
        valid_order_fields = ['id', 'created_at', 'estimated_difficulty']
        if order_by not in valid_order_fields:
            return Response({
                'status': 'error', 
                'message': f'order_by must be one of: {", ".join(valid_order_fields)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if order not in ['asc', 'desc']:
            return Response({
                'status': 'error', 
                'message': 'order must be either "asc" or "desc"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Build query
        order_field = f"-{order_by}" if order == 'desc' else order_by
        questions_query = GeneratedQuestion.objects.filter(game_type='non_coding').order_by(order_field)
        
        total_count = questions_query.count()
        questions = questions_query[offset:offset + limit]
        
        questions_data = [format_question_response(q) for q in questions]

        return Response({
            'status': 'success',
            'game_type': 'non_coding',
            'pagination': {
                'total_count': total_count,
                'returned_count': len(questions_data),
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total_count
            },
            'questions': questions_data
        })

    except ValueError as e:
        return Response({'status': 'error', 'message': 'Invalid pagination parameters'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Failed to retrieve non-coding questions: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_all_beginner_questions(request):
    """
    Get all beginner difficulty questions with pagination.
    Query params: limit, offset, order_by, order
    """
    try:
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        order_by = request.query_params.get('order_by', 'id')
        order = request.query_params.get('order', 'desc')
        
        # Validate parameters
        valid_order_fields = ['id', 'created_at', 'game_type']
        if order_by not in valid_order_fields:
            return Response({
                'status': 'error', 
                'message': f'order_by must be one of: {", ".join(valid_order_fields)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if order not in ['asc', 'desc']:
            return Response({
                'status': 'error', 
                'message': 'order must be either "asc" or "desc"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Build query
        order_field = f"-{order_by}" if order == 'desc' else order_by
        questions_query = GeneratedQuestion.objects.filter(estimated_difficulty='beginner').order_by(order_field)
        
        total_count = questions_query.count()
        questions = questions_query[offset:offset + limit]
        
        questions_data = [format_question_response(q) for q in questions]

        return Response({
            'status': 'success',
            'difficulty': 'beginner',
            'pagination': {
                'total_count': total_count,
                'returned_count': len(questions_data),
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total_count
            },
            'questions': questions_data
        })

    except ValueError as e:
        return Response({'status': 'error', 'message': 'Invalid pagination parameters'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Failed to retrieve beginner questions: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_all_intermediate_questions(request):
    """
    Get all intermediate difficulty questions with pagination.
    Query params: limit, offset, order_by, order
    """
    try:
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        order_by = request.query_params.get('order_by', 'id')
        order = request.query_params.get('order', 'desc')
        
        # Validate parameters
        valid_order_fields = ['id', 'created_at', 'game_type']
        if order_by not in valid_order_fields:
            return Response({
                'status': 'error', 
                'message': f'order_by must be one of: {", ".join(valid_order_fields)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if order not in ['asc', 'desc']:
            return Response({
                'status': 'error', 
                'message': 'order must be either "asc" or "desc"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Build query
        order_field = f"-{order_by}" if order == 'desc' else order_by
        questions_query = GeneratedQuestion.objects.filter(estimated_difficulty='intermediate').order_by(order_field)
        
        total_count = questions_query.count()
        questions = questions_query[offset:offset + limit]
        
        questions_data = [format_question_response(q) for q in questions]

        return Response({
            'status': 'success',
            'difficulty': 'intermediate',
            'pagination': {
                'total_count': total_count,
                'returned_count': len(questions_data),
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total_count
            },
            'questions': questions_data
        })

    except ValueError as e:
        return Response({'status': 'error', 'message': 'Invalid pagination parameters'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Failed to retrieve intermediate questions: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_all_advanced_questions(request):
    """
    Get all advanced difficulty questions with pagination.
    Query params: limit, offset, order_by, order
    """
    try:
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        order_by = request.query_params.get('order_by', 'id')
        order = request.query_params.get('order', 'desc')
        
        # Validate parameters
        valid_order_fields = ['id', 'created_at', 'game_type']
        if order_by not in valid_order_fields:
            return Response({
                'status': 'error', 
                'message': f'order_by must be one of: {", ".join(valid_order_fields)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if order not in ['asc', 'desc']:
            return Response({
                'status': 'error', 
                'message': 'order must be either "asc" or "desc"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Build query
        order_field = f"-{order_by}" if order == 'desc' else order_by
        questions_query = GeneratedQuestion.objects.filter(estimated_difficulty='advanced').order_by(order_field)
        
        total_count = questions_query.count()
        questions = questions_query[offset:offset + limit]
        
        questions_data = [format_question_response(q) for q in questions]

        return Response({
            'status': 'success',
            'difficulty': 'advanced',
            'pagination': {
                'total_count': total_count,
                'returned_count': len(questions_data),
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total_count
            },
            'questions': questions_data
        })

    except ValueError as e:
        return Response({'status': 'error', 'message': 'Invalid pagination parameters'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Failed to retrieve advanced questions: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_all_master_questions(request):
    """
    Get all master difficulty questions with pagination.
    Query params: limit, offset, order_by, order
    """
    try:
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        order_by = request.query_params.get('order_by', 'id')
        order = request.query_params.get('order', 'desc')
        
        # Validate parameters
        valid_order_fields = ['id', 'created_at', 'game_type']
        if order_by not in valid_order_fields:
            return Response({
                'status': 'error', 
                'message': f'order_by must be one of: {", ".join(valid_order_fields)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if order not in ['asc', 'desc']:
            return Response({
                'status': 'error', 
                'message': 'order must be either "asc" or "desc"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Build query
        order_field = f"-{order_by}" if order == 'desc' else order_by
        questions_query = GeneratedQuestion.objects.filter(estimated_difficulty='master').order_by(order_field)
        
        total_count = questions_query.count()
        questions = questions_query[offset:offset + limit]
        
        questions_data = [format_question_response(q) for q in questions]

        return Response({
            'status': 'success',
            'difficulty': 'master',
            'pagination': {
                'total_count': total_count,
                'returned_count': len(questions_data),
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total_count
            },
            'questions': questions_data
        })

    except ValueError as e:
        return Response({'status': 'error', 'message': 'Invalid pagination parameters'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Failed to retrieve master questions: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
