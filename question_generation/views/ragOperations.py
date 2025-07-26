"""
RAG operations for question generation.
Handles semantic search, chunk retrieval, and context preparation.
"""

from .imports import *

class SubtopicRAGView(APIView):
    """
    RAG retrieval and context preparation for a specific subtopic.
    """
    def get(self, request, subtopic_id):
        try:
            subtopic = get_object_or_404(Subtopic, id=subtopic_id)
            config = {
                'top_k': int(request.query_params.get('top_k', 10)),
                'similarity_threshold': float(request.query_params.get('similarity_threshold', 0.3)),
                'include_topic_chunks': request.query_params.get('include_topic_chunks', 'true').lower() == 'true',
                'include_related_chunks': request.query_params.get('include_related_chunks', 'true').lower() == 'true',
                'max_tokens': int(request.query_params.get('max_tokens', 4000)),
            }

            question_rag = QuestionRAG()
            rag_context = question_rag.prepare_subtopic_context(subtopic, config)

            return Response({
                'status': 'success',
                'subtopic': {
                    'id': subtopic.id,
                    'name': subtopic.name,
                    'description': subtopic.description,
                    'topic': subtopic.topic.name,
                    'zone': subtopic.topic.zone.name,
                    'learning_objectives': getattr(subtopic, 'learning_objectives', None)
                },
                'retrieval_metadata': rag_context['metadata'],
                'retrieved_chunks': [
                    {
                        'chunk_id': c['chunk_id'],
                        'similarity_score': c['similarity_score'],
                        'topic_title': c['topic_title'],
                        'subtopic_title': c['subtopic_title'],
                        'page_number': c['page_number'],
                        'chunk_type': c['chunk_type'],
                        'text_preview': c['text_preview']
                    }
                    for c in rag_context['retrieved_chunks']
                ],
                'context_window': rag_context['context_window'],
                'ready_for_question_generation': bool(rag_context['retrieved_chunks'])
            })
        except Exception as e:
            logger.error(f"RAG retrieval failed for subtopic {subtopic_id}: {str(e)}")
            return Response({'status': 'error', 'message': str(e)}, status=500)


class BatchSubtopicRAGView(APIView):
    """
    Batch RAG retrieval for multiple subtopics.
    """
    def post(self, request):
        try:
            subtopic_ids = request.data.get('subtopic_ids', [])
            config = request.data.get('config', {})

            if not subtopic_ids:
                return Response({'status': 'error', 'message': 'subtopic_ids is required'}, status=400)

            subtopics = Subtopic.objects.filter(id__in=subtopic_ids)
            found_ids = set(subtopics.values_list('id', flat=True))
            missing_ids = set(subtopic_ids) - found_ids

            question_rag = QuestionRAG()
            contexts = question_rag.batch_prepare_contexts(list(subtopics), config)

            results = {}
            summary = {
                'total_requested': len(subtopic_ids),
                'total_processed': len(contexts),
                'total_chunks_retrieved': sum(c['metadata']['chunks_retrieved'] for c in contexts.values() if 'metadata' in c),
                'successful': sum(1 for c in contexts.values() if 'error' not in c),
                'failed': sum(1 for c in contexts.values() if 'error' in c)
            }

            for subtopic_id, context in contexts.items():
                if 'error' in context:
                    results[subtopic_id] = {
                        'status': 'error',
                        'error': context['error'],
                        'subtopic_name': getattr(context.get('subtopic', None), 'name', None)
                    }
                else:
                    results[subtopic_id] = {
                        'status': 'success',
                        'subtopic_name': context['subtopic'].name,
                        'chunks_retrieved': context['metadata']['chunks_retrieved'],
                        'avg_similarity': context['metadata']['avg_similarity'],
                        'context_length': context['metadata']['context_length'],
                        'ready_for_generation': bool(context['retrieved_chunks'])
                    }

            return Response({
                'status': 'success',
                'summary': summary,
                'missing_subtopic_ids': list(missing_ids),
                'results': results
            })
        except Exception as e:
            logger.error(f"Batch RAG retrieval failed: {str(e)}")
            return Response({'status': 'error', 'message': str(e)}, status=500)


class SemanticSearchView(APIView):
    """
    General semantic search over document chunks.
    """
    def get(self, request):
        try:
            query = request.query_params.get('q')
            if not query:
                return Response({'status': 'error', 'message': 'Query parameter "q" is required'}, status=400)

            top_k = int(request.query_params.get('top_k', 10))
            similarity_threshold = float(request.query_params.get('similarity_threshold', 0.3))
            topic_filter = request.query_params.get('topic')
            subtopic_filter = request.query_params.get('subtopic')

            retriever = SmartRAGRetriever()
            results = retriever.search_chunks(
                query=query,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                filter_by_topic=topic_filter,
                filter_by_subtopic=subtopic_filter
            )

            search_results = [{
                'chunk_id': r['chunk_id'],
                'similarity_score': r['similarity_score'],
                'topic_title': r['topic_title'],
                'subtopic_title': r['subtopic_title'],
                'page_number': r['page_number'],
                'chunk_type': r['chunk_type'],
                'text_preview': r['text_preview']
            } for r in results]

            return Response({
                'status': 'success',
                'query': query,
                'total_results': len(search_results),
                'filters_applied': {
                    'topic': topic_filter,
                    'subtopic': subtopic_filter,
                    'similarity_threshold': similarity_threshold
                },
                'results': search_results
            })
        except Exception as e:
            logger.error(f"Semantic search failed: {str(e)}")
            return Response({'status': 'error', 'message': str(e)}, status=500)


class CodingRAGView(APIView):
    """
    Specialized RAG for coding-related questions and examples.
    """
    def get(self, request):
        try:
            concept = request.query_params.get('concept')
            if not concept:
                return Response({'status': 'error', 'message': 'Query parameter "concept" is required'}, status=400)

            difficulty = request.query_params.get('difficulty', 'Any')
            include_examples = request.query_params.get('include_examples', 'true').lower() == 'true'
            language = request.query_params.get('language', 'python')
            top_k = int(request.query_params.get('top_k', 15))

            retriever = SmartRAGRetriever()
            coding_query = f"{concept} {language} programming"
            if difficulty != 'Any':
                coding_query += f" {difficulty.lower()} difficulty"

            results = retriever.search_chunks(
                query=coding_query,
                top_k=top_k,
                similarity_threshold=0.2,
                filter_chunk_types=['Code', 'Example', 'Exercise'] if include_examples else None
            )

            code_examples = []
            explanations = []
            exercises = []
            for result in results:
                chunk_type = result.get('chunk_type', 'Unknown')
                result_data = {
                    'chunk_id': result['chunk_id'],
                    'similarity_score': result['similarity_score'],
                    'topic_title': result['topic_title'],
                    'subtopic_title': result['subtopic_title'],
                    'content': result.get('content', result['text_preview']),
                    'page_number': result['page_number']
                }
                if chunk_type == 'Code':
                    code_examples.append(result_data)
                elif chunk_type == 'Exercise':
                    exercises.append(result_data)
                else:
                    explanations.append(result_data)

            # Optionally: load_code_snippets() and merge here as before

            return Response({
                'status': 'success',
                'concept': concept,
                'language': language,
                'difficulty_filter': difficulty,
                'results': {
                    'code_examples': code_examples,
                    'explanations': explanations,
                    'exercises': exercises
                },
                'ready_for_coding_questions': bool(code_examples)
            })
        except Exception as e:
            logger.error(f"Coding RAG failed: {str(e)}")
            return Response({'status': 'error', 'message': str(e)}, status=500)


class ExplanationRAGView(APIView):
    """
    RAG for concept explanations and theoretical content.
    """
    def get(self, request):
        try:
            topic = request.query_params.get('topic')
            if not topic:
                return Response({'status': 'error', 'message': 'Query parameter "topic" is required'}, status=400)

            depth = request.query_params.get('depth', 'basic')
            include_examples = request.query_params.get('include_examples', 'true').lower() == 'true'
            top_k = int(request.query_params.get('top_k', 12))

            retriever = SmartRAGRetriever()
            explanation_query = f"{topic} explanation concept definition"
            if depth == 'advanced':
                explanation_query += " advanced detailed complex"
            elif depth == 'intermediate':
                explanation_query += " intermediate practical application"
            else:
                explanation_query += " basic introduction beginner"

            results = retriever.search_chunks(
                query=explanation_query,
                top_k=top_k,
                similarity_threshold=0.25,
                prefer_chunk_types=['Text', 'Concept', 'Introduction']
            )

            definitions = []
            detailed_explanations = []
            practical_examples = []
            for result in results:
                chunk_type = result.get('chunk_type', 'Text')
                content = result.get('content', result['text_preview'])
                result_data = {
                    'chunk_id': result['chunk_id'],
                    'similarity_score': result['similarity_score'],
                    'topic_title': result['topic_title'],
                    'subtopic_title': result['subtopic_title'],
                    'content': content,
                    'content_length': len(content),
                    'page_number': result['page_number'],
                    'chunk_type': chunk_type
                }
                if len(content) < 200 and ('definition' in content.lower() or 'is a' in content.lower()):
                    definitions.append(result_data)
                elif chunk_type in ['Example', 'Code'] and include_examples:
                    practical_examples.append(result_data)
                else:
                    detailed_explanations.append(result_data)

            # Sort by similarity
            definitions.sort(key=lambda x: x['similarity_score'], reverse=True)
            detailed_explanations.sort(key=lambda x: x['similarity_score'], reverse=True)
            practical_examples.sort(key=lambda x: x['similarity_score'], reverse=True)

            return Response({
                'status': 'success',
                'topic': topic,
                'explanation_depth': depth,
                'explanations': {
                    'definitions': definitions,
                    'detailed_explanations': detailed_explanations,
                    'practical_examples': practical_examples
                },
                'best_explanation_chunk': detailed_explanations[0] if detailed_explanations else None,
                'ready_for_explanation_questions': bool(detailed_explanations)
            })
        except Exception as e:
            logger.error(f"Explanation RAG failed: {str(e)}")
            return Response({'status': 'error', 'message': str(e)}, status=500)
