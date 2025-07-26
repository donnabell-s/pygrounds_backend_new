"""
Question management and CRUD operations.
Handles retrieval, filtering, and statistics for generated questions.
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
            'by_minigame_type': dict(questions_query.values('minigame_type').annotate(count=Count('minigame_type')).values_list('minigame_type', 'count')),
            'by_game_type': dict(questions_query.values('game_type').annotate(count=Count('game_type')).values_list('game_type', 'count')),
            'latest_generated': questions[0].created_at.isoformat() if questions else None
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
                'zone': topic.zone.name,
                'total_subtopics': subtopics.count()
            },
            'overall_statistics': overall_stats,
            'subtopic_summaries': subtopic_summaries
        })

    except Exception as e:
        logger.error(f"Failed to get topic questions summary for topic {topic_id}: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
