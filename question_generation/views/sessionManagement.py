"""
Session management and task tracking for question generation.
Handles RAG sessions, task monitoring, and user interaction tracking.
"""

from .imports import *

class RAGSessionListView(generics.ListAPIView):
    """
    List all RAG sessions with optional filtering (admin/analytics).
    """
    def get(self, request):
        try:
            limit = int(request.query_params.get('limit', 20))
            sessions = RAGSession.objects.order_by('-started_at')[:limit]
            sessions_data = []
            for session in sessions:
                sessions_data.append({
                    'id': session.id,
                    'subtopic': session.subtopic.name if session.subtopic else None,
                    'questions_generated': session.questions_generated,
                    'generation_success': session.generation_success,
                    'started_at': session.started_at.isoformat(),
                    'completed_at': session.completed_at.isoformat() if session.completed_at else None,
                })
            return Response({
                'status': 'success',
                'showing_count': len(sessions_data),
                'sessions': sessions_data
            })
        except Exception as e:
            logger.error(f"Failed to list RAG sessions: {str(e)}")
            return Response({'status': 'error', 'message': str(e)}, status=500)
class CompareSubtopicAndGenerateView(APIView):
    """
    Compare multiple subtopics and generate comparison questions.
    """
    def post(self, request):
        try:
            subtopic_ids = request.data.get('subtopic_ids', [])
            comparison_type = request.data.get('comparison_type', 'comprehensive')
            if len(subtopic_ids) < 2:
                return Response({'status': 'error', 'message': 'At least 2 subtopics required'}, status=400)
            subtopics = Subtopic.objects.filter(id__in=subtopic_ids)
            if subtopics.count() != len(subtopic_ids):
                return Response({'status': 'error', 'message': 'Some subtopics not found'}, status=400)

            comparison_analysis = []
            generated_questions = []
            for i, s1 in enumerate(subtopics):
                for s2 in subtopics[i+1:]:
                    # For demo: compare by name/desc, but you can add LLM logic here
                    common_words = set(s1.name.lower().split()) & set(s2.name.lower().split())
                    if comparison_type in ['similarity', 'comprehensive'] and common_words:
                        generated_questions.append({
                            'question': f"What do {s1.name} and {s2.name} have in common?",
                            'minigame_type': 'word_search',
                            'subtopics_compared': [s1.name, s2.name]
                        })
                    if comparison_type in ['differences', 'comprehensive'] and not common_words:
                        generated_questions.append({
                            'question': f"What is a key difference between {s1.name} and {s2.name}?",
                            'minigame_type': 'crossword',
                            'subtopics_compared': [s1.name, s2.name]
                        })
            return Response({
                'status': 'success',
                'comparison_type': comparison_type,
                'subtopics': [{'id': s.id, 'name': s.name, 'topic': s.topic.name} for s in subtopics],
                'generated_questions': generated_questions,
                'total_questions': len(generated_questions)
            })
        except Exception as e:
            logger.error(f"Subtopic comparison failed: {str(e)}")
            return Response({'status': 'error', 'message': str(e)}, status=500)
