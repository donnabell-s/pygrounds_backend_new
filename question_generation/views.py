from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from content_ingestion.models import Topic, Subtopic, DocumentChunk
from .models import GeneratedQuestion, RAGSession, QuestionGenerationTask, ChunkRetrievalScore
from .helpers.rag_utils import QuestionRAG, SmartRAGRetriever
# from .helpers.llm_utils import DeepSeekQuestionGenerator, MockDeepSeekGenerator  # Temporarily disabled
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SubtopicRAGView(APIView):
    """
    RAG retrieval and context preparation for a specific subtopic.
    """
    
    def get(self, request, subtopic_id):
        """
        Retrieve relevant chunks and prepare context for a subtopic.
        Query parameters:
        - top_k: Number of chunks to retrieve (default: 10)
        - similarity_threshold: Minimum similarity score (default: 0.3)
        - include_topic_chunks: Include parent topic chunks (default: true)
        - include_related_chunks: Include related topic chunks (default: true)
        """
        try:
            subtopic = get_object_or_404(Subtopic, id=subtopic_id)
            
            # Parse query parameters
            config = {
                'top_k': int(request.query_params.get('top_k', 10)),
                'similarity_threshold': float(request.query_params.get('similarity_threshold', 0.3)),
                'include_topic_chunks': request.query_params.get('include_topic_chunks', 'true').lower() == 'true',
                'include_related_chunks': request.query_params.get('include_related_chunks', 'true').lower() == 'true',
                'max_tokens': int(request.query_params.get('max_tokens', 4000))
            }
            
            print(f"\n🎯 RAG RETRIEVAL FOR SUBTOPIC")
            print(f"{'='*50}")
            print(f"Subtopic: {subtopic.name}")
            print(f"Topic: {subtopic.topic.name}")
            print(f"Zone: {subtopic.topic.zone.name}")
            print(f"Config: {config}")
            
            # Initialize RAG system
            question_rag = QuestionRAG()
            
            # Prepare context
            rag_context = question_rag.prepare_subtopic_context(subtopic, config)
            
            print(f"\n📊 RAG RESULTS")
            print(f"{'─'*30}")
            print(f"Chunks retrieved: {rag_context['metadata']['chunks_retrieved']}")
            print(f"Avg similarity: {rag_context['metadata']['avg_similarity']:.3f}")
            print(f"Context length: {rag_context['metadata']['context_length']} chars")
            
            # Prepare response
            response_data = {
                'status': 'success',
                'subtopic': {
                    'id': subtopic.id,
                    'name': subtopic.name,
                    'description': subtopic.description,
                    'topic': subtopic.topic.name,
                    'zone': subtopic.topic.zone.name,
                    'learning_objectives': subtopic.learning_objectives
                },
                'retrieval_metadata': rag_context['metadata'],
                'retrieved_chunks': [
                    {
                        'chunk_id': chunk['chunk_id'],
                        'similarity_score': chunk['similarity_score'],
                        'topic_title': chunk['topic_title'],
                        'subtopic_title': chunk['subtopic_title'],
                        'page_number': chunk['page_number'],
                        'chunk_type': chunk['chunk_type'],
                        'text_preview': chunk['text_preview']
                    }
                    for chunk in rag_context['retrieved_chunks']
                ],
                'context_window': rag_context['context_window'],
                'ready_for_question_generation': len(rag_context['retrieved_chunks']) > 0
            }
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"RAG retrieval failed for subtopic {subtopic_id}: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BatchSubtopicRAGView(APIView):
    """
    Batch RAG retrieval for multiple subtopics.
    """
    
    def post(self, request):
        """
        Prepare RAG contexts for multiple subtopics.
        Request body: {
            "subtopic_ids": [1, 2, 3],
            "config": {...}  // optional RAG config
        }
        """
        try:
            subtopic_ids = request.data.get('subtopic_ids', [])
            config = request.data.get('config', {})
            
            if not subtopic_ids:
                return Response({
                    'status': 'error',
                    'message': 'subtopic_ids is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get subtopics
            subtopics = Subtopic.objects.filter(id__in=subtopic_ids)
            found_ids = set(subtopics.values_list('id', flat=True))
            missing_ids = set(subtopic_ids) - found_ids
            
            print(f"\n🎯 BATCH RAG RETRIEVAL")
            print(f"{'='*50}")
            print(f"Requested subtopics: {len(subtopic_ids)}")
            print(f"Found subtopics: {len(found_ids)}")
            if missing_ids:
                print(f"Missing subtopics: {missing_ids}")
            
            # Initialize RAG system
            question_rag = QuestionRAG()
            
            # Prepare contexts
            contexts = question_rag.batch_prepare_contexts(list(subtopics), config)
            
            # Prepare response
            results = {}
            summary_stats = {
                'total_requested': len(subtopic_ids),
                'total_processed': len(contexts),
                'total_chunks_retrieved': 0,
                'successful': 0,
                'failed': 0
            }
            
            for subtopic_id, context in contexts.items():
                if 'error' in context:
                    summary_stats['failed'] += 1
                    results[subtopic_id] = {
                        'status': 'error',
                        'error': context['error'],
                        'subtopic_name': context['subtopic'].name
                    }
                else:
                    summary_stats['successful'] += 1
                    summary_stats['total_chunks_retrieved'] += context['metadata']['chunks_retrieved']
                    results[subtopic_id] = {
                        'status': 'success',
                        'subtopic_name': context['subtopic'].name,
                        'chunks_retrieved': context['metadata']['chunks_retrieved'],
                        'avg_similarity': context['metadata']['avg_similarity'],
                        'context_length': context['metadata']['context_length'],
                        'ready_for_generation': len(context['retrieved_chunks']) > 0
                    }
            
            print(f"\n📊 BATCH RESULTS")
            print(f"{'─'*30}")
            print(f"Successful: {summary_stats['successful']}")
            print(f"Failed: {summary_stats['failed']}")
            print(f"Total chunks: {summary_stats['total_chunks_retrieved']}")
            
            return Response({
                'status': 'success',
                'summary': summary_stats,
                'missing_subtopic_ids': list(missing_ids),
                'results': results
            })
            
        except Exception as e:
            logger.error(f"Batch RAG retrieval failed: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SemanticSearchView(APIView):
    """
    General semantic search over document chunks.
    """
    
    def get(self, request):
        """
        Search chunks using semantic similarity.
        Query parameters:
        - q: Search query (required)
        - top_k: Number of results (default: 10)
        - similarity_threshold: Minimum similarity (default: 0.3)
        - topic: Filter by topic name (optional)
        - subtopic: Filter by subtopic name (optional)
        """
        try:
            query = request.query_params.get('q')
            if not query:
                return Response({
                    'status': 'error',
                    'message': 'Query parameter "q" is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Parse parameters
            top_k = int(request.query_params.get('top_k', 10))
            similarity_threshold = float(request.query_params.get('similarity_threshold', 0.3))
            topic_filter = request.query_params.get('topic')
            subtopic_filter = request.query_params.get('subtopic')
            
            print(f"\n🔍 SEMANTIC SEARCH")
            print(f"{'='*50}")
            print(f"Query: {query}")
            print(f"Top K: {top_k}")
            print(f"Threshold: {similarity_threshold}")
            
            # Initialize retriever
            retriever = SmartRAGRetriever()
            
            # Perform search
            results = retriever.search_chunks(
                query=query,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                filter_by_topic=topic_filter,
                filter_by_subtopic=subtopic_filter
            )
            
            print(f"Found {len(results)} matching chunks")
            
            # Format results
            search_results = []
            for result in results:
                search_results.append({
                    'chunk_id': result['chunk_id'],
                    'similarity_score': result['similarity_score'],
                    'topic_title': result['topic_title'],
                    'subtopic_title': result['subtopic_title'],
                    'page_number': result['page_number'],
                    'chunk_type': result['chunk_type'],
                    'text_preview': result['text_preview']
                })
            
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
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_subtopic_questions(request, subtopic_id):
    """
    Get all generated questions for a specific subtopic.
    """
    try:
        subtopic = get_object_or_404(Subtopic, id=subtopic_id)
        
        # Get questions with filtering options
        questions_query = GeneratedQuestion.objects.filter(subtopic=subtopic)
        
        # Apply filters from query parameters
        difficulty = request.query_params.get('difficulty')
        if difficulty:
            questions_query = questions_query.filter(estimated_difficulty=difficulty)
        
        question_type = request.query_params.get('type')
        if question_type:
            questions_query = questions_query.filter(question_type=question_type)
        
        validation_status = request.query_params.get('status', 'approved')
        if validation_status != 'all':
            questions_query = questions_query.filter(validation_status=validation_status)
        
        questions = questions_query.order_by('-created_at')
        
        # Format response
        questions_data = []
        for question in questions:
            questions_data.append({
                'id': question.id,
                'question_text': question.question_text,
                'question_type': question.question_type,
                'answer_options': question.answer_options,
                'correct_answer': question.correct_answer,
                'explanation': question.explanation,
                'estimated_difficulty': question.estimated_difficulty,
                'validation_status': question.validation_status,
                'quality_score': question.quality_score,
                'times_used': question.times_used,
                'success_rate': question.success_rate,
                'created_at': question.created_at.isoformat(),
                'source_chunks_count': question.source_chunks.count()
            })
        
        return Response({
            'status': 'success',
            'subtopic': {
                'id': subtopic.id,
                'name': subtopic.name,
                'topic': subtopic.topic.name,
                'zone': subtopic.topic.zone.name
            },
            'total_questions': len(questions_data),
            'filters_applied': {
                'difficulty': difficulty,
                'question_type': question_type,
                'validation_status': validation_status
            },
            'questions': questions_data
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_topic_questions_summary(request, topic_id):
    """
    Get a summary of questions generated for all subtopics in a topic.
    """
    try:
        topic = get_object_or_404(Topic, id=topic_id)
        
        # Get subtopics with question counts
        subtopics_data = []
        for subtopic in topic.subtopics.all():
            question_counts = GeneratedQuestion.objects.filter(subtopic=subtopic).aggregate(
                total=Count('id'),
                pending=Count('id', filter=Q(validation_status='pending')),
                approved=Count('id', filter=Q(validation_status='approved')),
                rejected=Count('id', filter=Q(validation_status='rejected')),
                by_difficulty=Count('id', filter=Q(estimated_difficulty__isnull=False))
            )
            
            subtopics_data.append({
                'id': subtopic.id,
                'name': subtopic.name,
                'description': subtopic.description,
                'learning_objectives': subtopic.learning_objectives,
                'question_counts': question_counts
            })
        
        # Overall topic statistics
        total_questions = GeneratedQuestion.objects.filter(topic=topic).count()
        
        return Response({
            'status': 'success',
            'topic': {
                'id': topic.id,
                'name': topic.name,
                'zone': topic.zone.name,
                'total_subtopics': topic.subtopics.count()
            },
            'total_questions': total_questions,
            'subtopics': subtopics_data
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def create_question_generation_task(request):
    """
    Create a new question generation task for multiple subtopics.
    Request body: {
        "subtopic_ids": [1, 2, 3],
        "questions_per_subtopic": 5,
        "generation_config": {...}
    }
    """
    try:
        subtopic_ids = request.data.get('subtopic_ids', [])
        questions_per_subtopic = request.data.get('questions_per_subtopic', 5)
        generation_config = request.data.get('generation_config', {})
        
        if not subtopic_ids:
            return Response({
                'status': 'error',
                'message': 'subtopic_ids is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate subtopics exist
        subtopics = Subtopic.objects.filter(id__in=subtopic_ids)
        if subtopics.count() != len(subtopic_ids):
            missing_ids = set(subtopic_ids) - set(subtopics.values_list('id', flat=True))
            return Response({
                'status': 'error',
                'message': f'Subtopics not found: {list(missing_ids)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create task
        task = QuestionGenerationTask.objects.create(
            questions_per_subtopic=questions_per_subtopic,
            generation_config=generation_config,
            total_subtopics=len(subtopic_ids)
        )
        
        # Add subtopics to task
        task.subtopics.set(subtopics)
        
        print(f"\n📝 QUESTION GENERATION TASK CREATED")
        print(f"{'='*50}")
        print(f"Task ID: {task.id}")
        print(f"Subtopics: {len(subtopic_ids)}")
        print(f"Questions per subtopic: {questions_per_subtopic}")
        
        return Response({
            'status': 'success',
            'task': {
                'id': task.id,
                'status': task.status,
                'total_subtopics': task.total_subtopics,
                'questions_per_subtopic': task.questions_per_subtopic,
                'created_at': task.created_at.isoformat()
            },
            'subtopics': [
                {
                    'id': subtopic.id,
                    'name': subtopic.name,
                    'topic': subtopic.topic.name
                }
                for subtopic in subtopics
            ]
        })
        
    except Exception as e:
        logger.error(f"Failed to create question generation task: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_generation_task_status(request, task_id):
    """
    Get the status and progress of a question generation task.
    """
    try:
        task = get_object_or_404(QuestionGenerationTask, id=task_id)
        
        return Response({
            'status': 'success',
            'task': {
                'id': task.id,
                'status': task.status,
                'progress_percentage': task.progress_percentage,
                'total_subtopics': task.total_subtopics,
                'completed_subtopics': task.completed_subtopics,
                'total_questions_generated': task.total_questions_generated,
                'failed_subtopics': task.failed_subtopics,
                'created_at': task.created_at.isoformat(),
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'task_results': task.task_results,
                'error_log': task.error_log
            }
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RAGSessionListView(generics.ListAPIView):
    """
    List all RAG sessions with filtering options.
    """
    
    def get(self, request):
        """
        Get RAG sessions with optional filtering.
        Query parameters:
        - subtopic_id: Filter by subtopic
        - success_only: Show only successful sessions
        - limit: Limit number of results
        """
        try:
            sessions_query = RAGSession.objects.all()
            
            # Apply filters
            subtopic_id = request.query_params.get('subtopic_id')
            if subtopic_id:
                sessions_query = sessions_query.filter(subtopic_id=subtopic_id)
            
            success_only = request.query_params.get('success_only', 'false').lower() == 'true'
            if success_only:
                sessions_query = sessions_query.filter(generation_success=True)
            
            limit = request.query_params.get('limit')
            if limit:
                sessions_query = sessions_query[:int(limit)]
            
            # Format response
            sessions_data = []
            for session in sessions_query.order_by('-started_at'):
                sessions_data.append({
                    'id': session.id,
                    'subtopic': {
                        'id': session.subtopic.id,
                        'name': session.subtopic.name,
                        'topic': session.subtopic.topic.name
                    },
                    'questions_generated': session.questions_generated,
                    'generation_success': session.generation_success,
                    'chunks_retrieved': session.retrieved_chunks.count(),
                    'started_at': session.started_at.isoformat(),
                    'completed_at': session.completed_at.isoformat() if session.completed_at else None,
                    'error_message': session.error_message
                })
            
            return Response({
                'status': 'success',
                'total_sessions': len(sessions_data),
                'sessions': sessions_data
            })
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CodingRAGView(APIView):
    """
    RAG retrieval specifically for coding question generation.
    """
    
    def get(self, request, subtopic_id):
        """
        Retrieve coding-specific chunks for a subtopic.
        Query parameters:
        - top_k: Number of chunks to retrieve (default: 8)
        - similarity_threshold: Minimum similarity score (default: 0.25)
        """
        try:
            subtopic = get_object_or_404(Subtopic, id=subtopic_id)
            
            # Parse query parameters
            config = {
                'top_k': int(request.query_params.get('top_k', 8)),
                'similarity_threshold': float(request.query_params.get('similarity_threshold', 0.25)),
                'max_tokens': int(request.query_params.get('max_tokens', 3000))
            }
            
            print(f"\n🧑‍💻 CODING RAG RETRIEVAL")
            print(f"{'='*50}")
            print(f"Subtopic: {subtopic.name}")
            print(f"Config: {config}")
            
            # Initialize RAG system
            question_rag = QuestionRAG()
            
            # Prepare coding context
            coding_context = question_rag.prepare_coding_context(subtopic, config)
            
            print(f"\n📊 CODING RAG RESULTS")
            print(f"{'─'*30}")
            print(f"Chunks retrieved: {coding_context['metadata']['chunks_retrieved']}")
            print(f"Avg similarity: {coding_context['metadata']['avg_similarity']:.3f}")
            print(f"Chunk types: {', '.join(set(coding_context['metadata']['chunk_types']))}")
            
            # Prepare response
            response_data = {
                'status': 'success',
                'subtopic': {
                    'id': subtopic.id,
                    'name': subtopic.name,
                    'description': subtopic.description,
                    'topic': subtopic.topic.name,
                    'zone': subtopic.topic.zone.name
                },
                'content_category': 'coding',
                'retrieval_metadata': coding_context['metadata'],
                'retrieved_chunks': [
                    {
                        'chunk_id': chunk['chunk_id'],
                        'similarity_score': chunk['similarity_score'],
                        'chunk_type': chunk['chunk_type'],
                        'topic_title': chunk['topic_title'],
                        'page_number': chunk['page_number'],
                        'text_preview': chunk['text_preview']
                    }
                    for chunk in coding_context['retrieved_chunks']
                ],
                'context_window': coding_context['context_window'],
                'ready_for_question_generation': len(coding_context['retrieved_chunks']) > 0
            }
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Coding RAG retrieval failed for subtopic {subtopic_id}: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ExplanationRAGView(APIView):
    """
    RAG retrieval specifically for explanation question generation.
    """
    
    def get(self, request, subtopic_id):
        """
        Retrieve explanation-specific chunks for a subtopic.
        Query parameters:
        - top_k: Number of chunks to retrieve (default: 10)
        - similarity_threshold: Minimum similarity score (default: 0.3)
        """
        try:
            subtopic = get_object_or_404(Subtopic, id=subtopic_id)
            
            # Parse query parameters
            config = {
                'top_k': int(request.query_params.get('top_k', 10)),
                'similarity_threshold': float(request.query_params.get('similarity_threshold', 0.3)),
                'max_tokens': int(request.query_params.get('max_tokens', 3000))
            }
            
            print(f"\n📚 EXPLANATION RAG RETRIEVAL")
            print(f"{'='*50}")
            print(f"Subtopic: {subtopic.name}")
            print(f"Config: {config}")
            
            # Initialize RAG system
            question_rag = QuestionRAG()
            
            # Prepare explanation context
            explanation_context = question_rag.prepare_explanation_context(subtopic, config)
            
            print(f"\n📊 EXPLANATION RAG RESULTS")
            print(f"{'─'*30}")
            print(f"Chunks retrieved: {explanation_context['metadata']['chunks_retrieved']}")
            print(f"Avg similarity: {explanation_context['metadata']['avg_similarity']:.3f}")
            print(f"Chunk types: {', '.join(set(explanation_context['metadata']['chunk_types']))}")
            
            # Prepare response
            response_data = {
                'status': 'success',
                'subtopic': {
                    'id': subtopic.id,
                    'name': subtopic.name,
                    'description': subtopic.description,
                    'topic': subtopic.topic.name,
                    'zone': subtopic.topic.zone.name
                },
                'content_category': 'explanation',
                'retrieval_metadata': explanation_context['metadata'],
                'retrieved_chunks': [
                    {
                        'chunk_id': chunk['chunk_id'],
                        'similarity_score': chunk['similarity_score'],
                        'chunk_type': chunk['chunk_type'],
                        'topic_title': chunk['topic_title'],
                        'page_number': chunk['page_number'],
                        'text_preview': chunk['text_preview']
                    }
                    for chunk in explanation_context['retrieved_chunks']
                ],
                'context_window': explanation_context['context_window'],
                'ready_for_question_generation': len(explanation_context['retrieved_chunks']) > 0
            }
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Explanation RAG retrieval failed for subtopic {subtopic_id}: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Temporarily disabled - LLM utils need fixing
"""
@api_view(['POST'])
def generate_questions_with_deepseek(request, subtopic_id):
    # Generate questions using DeepSeek Reasoner with smart RAG.
    # Request body: {
    #     "question_category": "coding|explanation",
    #     "num_questions": 5,
    #     "question_types": ["multiple_choice", "coding_exercise"],
    #     "use_mock": false
    # }
    try:
        subtopic = get_object_or_404(Subtopic, id=subtopic_id)
        
        # Parse request data
        question_category = request.data.get('question_category', 'explanation')
        num_questions = request.data.get('num_questions', 5)
        question_types = request.data.get('question_types', ['multiple_choice'])
        use_mock = request.data.get('use_mock', False)
        rag_config = request.data.get('rag_config', {})
        
        print(f"\\n🧠 QUESTION GENERATION WITH DEEPSEEK")
        print(f"{'='*50}")
        print(f"Subtopic: {subtopic.name}")
        print(f"Category: {question_category}")
        print(f"Questions: {num_questions}")
        print(f"Types: {question_types}")
        print(f"Mock mode: {use_mock}")
        
        # Initialize question generator
        if use_mock:
            generator = MockDeepSeekGenerator()
        else:
            generator = DeepSeekQuestionGenerator()
        
        # Prepare RAG context based on category
        question_rag = QuestionRAG()
        
        if question_category == 'coding':
            rag_context = question_rag.prepare_coding_context(subtopic, rag_config)
        else:
            rag_context = question_rag.prepare_explanation_context(subtopic, rag_config)
        
        # Check if we have relevant content
        if not rag_context['retrieved_chunks']:
            return Response({
                'status': 'error',
                'message': f'No relevant {question_category} content found for {subtopic.name}',
                'subtopic_id': subtopic.id
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate questions
        if use_mock:
            # For mock, use the general method
            generation_result = generator.generate_questions_for_subtopic(
                subtopic=subtopic,
                num_questions=num_questions,
                question_types=question_types
            )
        else:
            # For real DeepSeek, use the context directly
            generation_result = generator.generate_questions_for_subtopic(
                subtopic=subtopic,
                num_questions=num_questions,
                question_types=question_types,
                rag_config=rag_config
            )
        
        if generation_result['success']:
            print(f"\\n✅ Generated {len(generation_result['questions'])} questions successfully")
            
            # Enhance response with RAG metadata
            generation_result['rag_metadata'] = rag_context['metadata']
            generation_result['question_category'] = question_category
            
            return Response(generation_result)
        else:
            print(f"\\n❌ Question generation failed: {generation_result['error']}")
            return Response(generation_result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"Question generation failed for subtopic {subtopic_id}: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e),
            'subtopic_id': subtopic_id
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
"""
