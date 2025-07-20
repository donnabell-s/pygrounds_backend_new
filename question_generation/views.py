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
import json
import os
import random
from datetime import datetime

logger = logging.getLogger(__name__)

def load_code_snippets():
    """Load Python code snippets from JSON file"""
    try:
        json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'python_code_snippets.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load code snippets: {e}")
        return None


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


class CompareSubtopicAndGenerateView(APIView):
    """
    Compare subtopic metadata with embeddings and generate questions via RAG.
    This endpoint will:
    1. Compare subtopic name and description against stored content
    2. Use RAG to find relevant content chunks
    3. Determine if the content is coding or non-coding
    4. Generate questions with LLM using the embeddings
    5. Save questions with default difficulty 'beginner'
    """
    
    def post(self, request, subtopic_id):
        """
        Generate questions for a subtopic using RAG and embeddings.
        
        Request body:
        {
            "max_questions": 5,
            "question_types": ["multiple_choice", "coding_exercise"],
            "difficulty": "beginner",  // optional, defaults to beginner
            "force_regenerate": false,  // optional, regenerate existing questions
            "minigame_type": "hangman_coding"  // optional, specific minigame type
        }
        """
        try:
            subtopic = get_object_or_404(Subtopic, id=subtopic_id)
            
            # Parse request parameters
            max_questions = request.data.get('max_questions', 5)
            num_questions = request.data.get('num_questions', max_questions)  # Support both parameter names
            minigame_type = request.data.get('minigame_type', 'generic')  # Specific minigame type
            force_regenerate = request.data.get('force_regenerate', False)
            
            print(f"\n🔍 SUBTOPIC COMPARISON & QUESTION GENERATION")
            print(f"{'='*60}")
            print(f"Subtopic: {subtopic.name}")
            print(f"Description: {subtopic.description}")
            print(f"Topic: {subtopic.topic.name}")
            print(f"Zone: {subtopic.topic.zone.name}")
            print(f"Max Questions: {num_questions}")
            print(f"Minigame Type: {minigame_type}")
            
            # Validate minigame type
            valid_minigame_types = ['hangman_coding', 'ship_debugging', 'word_search', 'crossword', 'generic']
            if minigame_type not in valid_minigame_types:
                return Response({
                    'status': 'error',
                    'message': f'Invalid minigame_type. Must be one of: {valid_minigame_types}',
                    'subtopic_id': subtopic_id
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Auto-determine if minigame is coding or non-coding based on type
            if minigame_type in ['hangman_coding', 'ship_debugging']:
                determined_game_type = 'coding'
            elif minigame_type in ['word_search', 'crossword']:
                determined_game_type = 'non_coding'
            else:
                # For generic, auto-detect from content
                determined_game_type = 'auto'
            
            # Step 1: Compare subtopic metadata with existing content
            print(f"\n📊 STEP 1: Analyzing subtopic metadata")
            subtopic_metadata = {
                'name': subtopic.name,
                'description': subtopic.description,
                'learning_objectives': subtopic.learning_objectives,
                'topic_context': {
                    'name': subtopic.topic.name,
                    'description': subtopic.topic.description,
                    'zone': subtopic.topic.zone.name
                }
            }
            
            # Step 2: Use RAG to find relevant content chunks
            print(f"\n🎯 STEP 2: RAG retrieval for relevant content")
            
            # Initialize RAG system
            rag_system = QuestionRAG()
            
            # Determine context type based on minigame type
            if determined_game_type == 'coding':
                rag_result = rag_system.prepare_coding_context(subtopic)
            elif determined_game_type == 'non_coding':
                rag_result = rag_system.prepare_explanation_context(subtopic)
            else:
                # Auto-detect based on content for generic minigame
                # First try coding context to analyze content
                coding_result = rag_system.prepare_coding_context(subtopic)
                
                if not coding_result['retrieved_chunks']:
                    # No coding content found, use explanation context
                    rag_result = rag_system.prepare_explanation_context(subtopic)
                    determined_game_type = 'non_coding'
                else:
                    # Analyze content to determine type
                    coding_indicators = [
                        'def ', 'class ', 'import ', 'from ', 'print(', 'input(', 
                        'if __name__', 'python', 'code', 'script', 'function',
                        'variable', 'loop', 'syntax', '>>>', 'python.org'
                    ]
                    
                    total_chunks = len(coding_result['retrieved_chunks'])
                    coding_chunks = 0
                    
                    for chunk in coding_result['retrieved_chunks']:
                        chunk_text = chunk['text'].lower()
                        if any(indicator in chunk_text for indicator in coding_indicators):
                            coding_chunks += 1
                    
                    coding_ratio = coding_chunks / total_chunks if total_chunks > 0 else 0
                    
                    if coding_ratio >= 0.3:  # 30% threshold for coding content
                        rag_result = coding_result
                        determined_game_type = 'coding'
                    else:
                        rag_result = rag_system.prepare_explanation_context(subtopic)
                        determined_game_type = 'non_coding'
            
            if not rag_result['retrieved_chunks']:
                return Response({
                    'status': 'error',
                    'message': 'No relevant content found for this subtopic',
                    'subtopic_id': subtopic_id
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Step 3: Content type already determined
            print(f"\n🔍 STEP 3: Content type determined as: {determined_game_type}")
            
            # Step 4: Check for existing questions (unless force regenerate)
            existing_questions = GeneratedQuestion.objects.filter(subtopic=subtopic)
            
            if existing_questions.exists() and not force_regenerate:
                print(f"\n📚 Found {existing_questions.count()} existing questions")
                return Response({
                    'status': 'success',
                    'message': 'Questions already exist. Use force_regenerate=true to regenerate.',
                    'subtopic_id': subtopic_id,
                    'existing_questions_count': existing_questions.count(),
                    'generated_questions': []
                })
            
            # Step 5: Generate questions using LLM with embeddings
            print(f"\n🤖 STEP 4: Generating questions with LLM")
            
            generated_questions = []
            
            # Prepare context for LLM
            context_text = "\n\n".join([chunk['text'] for chunk in rag_result['retrieved_chunks'][:5]])
            
            # Mock LLM generation (replace with actual LLM call)
            for i in range(max_questions):
                # Generate based on minigame type
                if minigame_type == 'hangman_coding':
                    question_data = self._generate_hangman_coding_question(
                        subtopic, context_text
                    )
                elif minigame_type == 'ship_debugging':
                    question_data = self._generate_ship_debugging_question(
                        subtopic, context_text
                    )
                elif minigame_type == 'word_search':
                    question_data = self._generate_word_search_question(
                        subtopic, context_text
                    )
                elif minigame_type == 'crossword':
                    question_data = self._generate_crossword_question(
                        subtopic, context_text
                    )
                else:
                    # Generate based on content type (legacy logic)
                    if determined_game_type == 'coding':
                        question_data = self._generate_coding_question(
                            subtopic, context_text, 'coding_exercise'
                        )
                    else:
                        question_data = self._generate_non_coding_question(
                            subtopic, context_text, 'multiple_choice'
                        )
                
                # Create GeneratedQuestion instance (leave fields empty as requested)
                question = GeneratedQuestion.objects.create(
                    topic=subtopic.topic,
                    subtopic=subtopic,
                    question_text=question_data['question_text'],
                    question_type=question_data.get('question_type', 'multiple_choice'),
                    answer_options=question_data.get('answer_options', []),
                    correct_answer=question_data['correct_answer'],
                    explanation=question_data.get('explanation', ''),
                    estimated_difficulty='',  # Leave empty as requested
                    game_type=determined_game_type,
                    minigame_type=minigame_type,
                    game_data=question_data.get('game_data', {}),  # Save minigame-specific data
                    rag_context={
                        'chunks_used': len(rag_result['retrieved_chunks']),
                        'similarity_scores': [chunk['similarity_score'] for chunk in rag_result['retrieved_chunks'][:3]],
                        'content_analysis': {
                            'game_type_method': determined_game_type,
                            'total_tokens': sum(chunk.get('token_count', 0) for chunk in rag_result['retrieved_chunks'])
                        }
                    },
                    generation_model='mock-llm-v1',
                    generation_metadata={
                        'subtopic_metadata': subtopic_metadata,
                        'rag_method': f'{determined_game_type}_context',
                        'minigame_type': minigame_type,
                        'generation_timestamp': datetime.now().isoformat()
                    }
                )
                
                # Add source chunks
                for chunk in rag_result['retrieved_chunks'][:3]:  # Link top 3 chunks
                    if 'chunk_id' in chunk:
                        try:
                            chunk_obj = DocumentChunk.objects.get(id=chunk['chunk_id'])
                            question.source_chunks.add(chunk_obj)
                        except DocumentChunk.DoesNotExist:
                            pass
                
                generated_questions.append({
                    'id': question.id,
                    'question_text': question.question_text,
                    'question_type': question.question_type,
                    'game_type': question.game_type,
                    'minigame_type': question.minigame_type,
                    'difficulty': question.estimated_difficulty,
                    'answer_options': question.answer_options,
                    'correct_answer': question.correct_answer,
                    'game_data': question.game_data
                })
                
                print(f"   Generated {question.question_type} question {i+1}")
            
            print(f"\n✅ GENERATION COMPLETE")
            print(f"   Questions created: {len(generated_questions)}")
            print(f"   Game type: {determined_game_type}")
            print(f"   RAG chunks used: {len(rag_result['retrieved_chunks'])}")
            
            return Response({
                'status': 'success',
                'message': f'Successfully generated {len(generated_questions)} questions',
                'subtopic_id': subtopic_id,
                'subtopic_analysis': {
                    'name': subtopic.name,
                    'description': subtopic.description,
                    'content_type': determined_game_type,
                    'game_type_method': f'minigame_{minigame_type}' if minigame_type != 'generic' else f'auto_detected_{determined_game_type}'
                },
                'rag_analysis': {
                    'chunks_found': len(rag_result['retrieved_chunks']),
                    'avg_similarity': sum(chunk['similarity_score'] for chunk in rag_result['retrieved_chunks']) / len(rag_result['retrieved_chunks']) if rag_result['retrieved_chunks'] else 0,
                    'total_tokens': sum(chunk.get('token_count', 0) for chunk in rag_result['retrieved_chunks'])
                },
                'generated_questions': generated_questions
            })
            
        except Exception as e:
            logger.error(f"Subtopic comparison and generation failed for {subtopic_id}: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e),
                'subtopic_id': subtopic_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _generate_coding_question(self, subtopic, context, question_type):
        """Generate a coding-related question"""
        if question_type == 'coding_exercise':
            return {
                'question_text': f"Write a Python function that demonstrates the concept of {subtopic.name}. "
                               f"Use the following context as a guide:\n\n{context[:200]}...",
                'question_type': 'coding_exercise',
                'correct_answer': f"# Example solution for {subtopic.name}\ndef example_function():\n    # Implementation here\n    pass",
                'explanation': f"This exercise tests understanding of {subtopic.name} concepts."
            }
        elif question_type == 'code_completion':
            return {
                'question_text': f"Complete the following Python code related to {subtopic.name}:\n\n"
                               f"def incomplete_function():\n    # Complete this function\n    ___",
                'question_type': 'code_completion',
                'correct_answer': "# Completed function implementation",
                'explanation': f"This tests practical application of {subtopic.name}."
            }
        else:
            return {
                'question_text': f"What is the main concept behind {subtopic.name} in Python programming?",
                'question_type': 'multiple_choice',
                'answer_options': [
                    f"Primary concept of {subtopic.name}",
                    "Incorrect option 1",
                    "Incorrect option 2",
                    "Incorrect option 3"
                ],
                'correct_answer': f"Primary concept of {subtopic.name}",
                'explanation': f"Understanding {subtopic.name} is essential for Python programming."
            }
    
    def _generate_non_coding_question(self, subtopic, context, question_type):
        """Generate a non-coding question"""
        if question_type == 'multiple_choice':
            return {
                'question_text': f"Which of the following best describes {subtopic.name}?",
                'question_type': 'multiple_choice',
                'answer_options': [
                    f"Correct description of {subtopic.name}",
                    "Incorrect option 1",
                    "Incorrect option 2", 
                    "Incorrect option 3"
                ],
                'correct_answer': f"Correct description of {subtopic.name}",
                'explanation': f"This definition captures the essence of {subtopic.name}."
            }
        elif question_type == 'short_answer':
            return {
                'question_text': f"Explain the importance of {subtopic.name} in programming.",
                'question_type': 'short_answer',
                'correct_answer': f"{subtopic.name} is important because it provides fundamental concepts needed for programming.",
                'explanation': f"Understanding {subtopic.name} helps build a strong foundation."
            }
        else:
            return {
                'question_text': f"True or False: {subtopic.name} is a fundamental concept in programming.",
                'question_type': 'true_false',
                'answer_options': ["True", "False"],
                'correct_answer': "True",
                'explanation': f"{subtopic.name} is indeed a fundamental programming concept."
            }
    
    def _generate_hangman_coding_question(self, subtopic, context):
        """Generate a hangman-style coding question using real Python snippets in function format"""
        snippets_data = load_code_snippets()
        
        if snippets_data:
            # Find relevant snippets based on subtopic name
            relevant_category = self._find_relevant_snippet_category(subtopic.name, snippets_data)
            if relevant_category and snippets_data['python_snippets'][relevant_category]['snippets']:
                snippet = random.choice(snippets_data['python_snippets'][relevant_category]['snippets'])
                
                # Create function-based hangman question
                function_data = self._create_function_hangman_version(snippet, subtopic)
                
                return {
                    'question_text': f"Complete the function for {subtopic.name}:\n\n{function_data['hangman_code']}",
                    'question_type': 'code_completion',
                    'answer_options': snippet.get('concepts', ['input', 'print', 'variable']),
                    'correct_answer': function_data['complete_code'],
                    'explanation': f"This function demonstrates {', '.join(snippet.get('concepts', []))}.",
                    'game_data': {
                        'original_code': snippet['code'],
                        'hangman_version': function_data['hangman_code'],
                        'complete_function': function_data['complete_code'],
                        'function_name': function_data['function_name'],
                        'parameters': function_data['parameters'],
                        'expected_output': function_data['expected_output'],
                        'validation_type': 'output_based',  # User wins if output matches, not code
                        'concepts': snippet.get('concepts', []),
                        'difficulty_level': snippet.get('difficulty', 'auto'),
                        'snippet_id': snippet['id']
                    }
                }
        
        # Fallback to generic version
        return self._generate_hangman_fallback(subtopic)
    
    def _generate_ship_debugging_question(self, subtopic, context):
        """Generate a ship debugging game question using real Python snippets"""
        snippets_data = load_code_snippets()
        
        if snippets_data:
            # Find relevant snippets with bugs
            relevant_category = self._find_relevant_snippet_category(subtopic.name, snippets_data)
            if relevant_category and snippets_data['python_snippets'][relevant_category]['snippets']:
                snippets = snippets_data['python_snippets'][relevant_category]['snippets']
                # Prefer snippets with bugs
                buggy_snippets = [s for s in snippets if s.get('bug_type') != 'none']
                if buggy_snippets:
                    snippet = random.choice(buggy_snippets)
                else:
                    snippet = random.choice(snippets)
                
                buggy_code = snippet.get('buggy_version', snippet['code'])
                fixed_code = snippet['code']
                
                return {
                    'question_text': f"Debug the spaceship's code! Find and fix the errors in this {subtopic.name} implementation:\n\n{buggy_code}",
                    'question_type': 'coding_exercise',
                    'answer_options': [],
                    'correct_answer': fixed_code,
                    'explanation': f"Bug fixed: {snippet.get('bug_description', 'Code corrected')}",
                    'game_data': {
                        'buggy_code': buggy_code,
                        'fixed_code': fixed_code,
                        'bug_type': snippet.get('bug_type', 'unknown'),
                        'bug_description': snippet.get('bug_description', ''),
                        'validation_type': 'execution_based',  # User wins if code runs without errors
                        'win_condition': 'code_executes_successfully',
                        'concepts': snippet.get('concepts', []),
                        'difficulty_level': snippet.get('difficulty', 'auto'),
                        'snippet_id': snippet['id']
                    }
                }
        
        # Fallback to generic version
        return self._generate_debugging_fallback(subtopic)
    
    def _find_relevant_snippet_category(self, subtopic_name, snippets_data):
        """Find the most relevant snippet category based on subtopic name"""
        subtopic_lower = subtopic_name.lower()
        
        # Direct mapping of subtopic keywords to categories
        category_keywords = {
            'input_output': ['input', 'print', 'output', 'console'],
            'variables_datatypes': ['variable', 'data type', 'string', 'number', 'boolean'],
            'operators': ['operator', 'arithmetic', 'comparison', 'logical'],
            'conditionals': ['if', 'else', 'condition', 'decision'],
            'loops': ['loop', 'for', 'while', 'iteration', 'repeat'],
            'functions': ['function', 'def', 'return', 'parameter'],
            'data_structures': ['list', 'dictionary', 'tuple', 'set', 'data structure']
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in subtopic_lower for keyword in keywords):
                return category
        
        # Default to input_output for most basic questions
        return 'input_output'
    
    def _create_function_hangman_version(self, snippet, subtopic):
        """Create a function-based hangman version with the format: def funcName(param): // given code // enter your answer here return"""
        
        # Dynamically choose function name based on snippet topic and concepts
        function_names = {
            'input': ['get_user_input', 'collect_data', 'read_value', 'prompt_user'],
            'print': ['display_info', 'show_output', 'print_result', 'output_data'],
            'variable': ['store_value', 'assign_data', 'set_variable', 'save_info'],
            'loop': ['iterate_data', 'repeat_action', 'process_list', 'count_items'],
            'function': ['calculate_result', 'process_data', 'compute_value', 'execute_task'],
            'list': ['manage_list', 'process_items', 'handle_data', 'organize_values'],
            'string': ['format_text', 'process_string', 'handle_text', 'format_message'],
            'if-else': ['check_condition', 'validate_input', 'test_value', 'evaluate_data'],
            'arithmetic': ['calculate_math', 'compute_result', 'do_math', 'process_numbers']
        }
        
        # Choose function name based on snippet concepts
        concepts = snippet.get('concepts', ['process'])
        func_name = 'process_data'  # default
        for concept in concepts:
            if concept in function_names:
                func_name = random.choice(function_names[concept])
                break
        
        # Determine parameters based on the original code
        original_code = snippet['code']
        parameters = []
        
        # Analyze code to determine appropriate parameters
        if 'input(' in original_code:
            # Convert input() calls to parameters instead
            if 'age' in original_code.lower() and 'name' in original_code.lower():
                parameters = ['name', 'age']
            elif 'age' in original_code.lower():
                parameters = ['age']
            elif 'name' in original_code.lower():
                parameters = ['name']
            else:
                parameters = ['user_input']
        elif any(var in original_code for var in ['x =', 'y =', 'a =', 'b =']):
            # For math operations, provide variables as parameters
            if 'x =' in original_code and 'y =' in original_code:
                parameters = ['x', 'y']
            else:
                parameters = ['num1', 'num2']
        elif 'for ' in original_code and 'in ' in original_code:
            if 'range(' in original_code:
                parameters = ['n']
            else:
                parameters = ['items']
        elif 'def ' in original_code:
            # Extract existing parameters if it's already a function
            import re
            match = re.search(r'def\s+\w+\((.*?)\):', original_code)
            if match:
                existing_params = [p.strip() for p in match.group(1).split(',') if p.strip()]
                parameters = existing_params[:2]  # Take first 2 parameters max
        
        # Default parameter if none determined
        if not parameters:
            parameters = ['data']
        
        # Create the function structure
        param_str = ', '.join(parameters)
        
        # Process the original code to remove input() calls and convert to function logic
        code_lines = original_code.split('\n')
        processed_lines = []
        
        for line in code_lines:
            if line.strip():
                # Skip existing function definitions
                if line.strip().startswith('def '):
                    continue
                # Replace input() calls with parameter usage
                modified_line = line
                if 'input(' in line:
                    # Replace input() calls with parameter references
                    if 'name' in parameters:
                        modified_line = modified_line.replace('input("Enter your name: ")', 'name')
                        modified_line = modified_line.replace('input("Name: ")', 'name')
                    if 'age' in parameters:
                        modified_line = modified_line.replace('int(input("Enter your age: "))', 'age')
                        modified_line = modified_line.replace('int(input("Age: "))', 'age')
                    if 'user_input' in parameters:
                        modified_line = modified_line.replace('input(', 'user_input  # Replace with: input(')
                
                # Add indentation for function body
                if not modified_line.startswith('    '):
                    processed_lines.append('    ' + modified_line)
                else:
                    processed_lines.append(modified_line)
        
        # Create given code section and answer section
        given_lines = []
        answer_section_lines = []
        
        # Split code intelligently - show setup, hide main logic
        split_point = max(1, len(processed_lines) // 2)
        for i, line in enumerate(processed_lines):
            if i < split_point:  # First part as given
                given_lines.append(line)
            else:  # Second part as answer section
                answer_section_lines.append(line)
        
        # Ensure we have a return statement and determine expected output
        expected_output = self._determine_expected_output(snippet, parameters)
        
        # Ensure the function returns the result instead of printing
        if answer_section_lines:
            last_line = answer_section_lines[-1].strip()
            if 'print(' in last_line:
                # Convert print to return
                return_value = last_line.replace('print(', '').replace(')', '').strip()
                answer_section_lines[-1] = f"    return {return_value}"
        
        # If no return statement, add one
        if not any('return' in line for line in answer_section_lines):
            answer_section_lines.append("    return result")
        
        # Build the hangman version
        hangman_parts = [
            f"def {func_name}({param_str}):",
            "    # Given code"
        ]
        
        if given_lines:
            hangman_parts.extend(given_lines)
        else:
            hangman_parts.append("    # Setup code here")
        
        hangman_parts.extend([
            "",
            "    # Enter your answer here",
            "",
        ])
        
        # Show blanks for the answer section
        if answer_section_lines:
            for line in answer_section_lines:
                if line.strip():
                    hangman_parts.append("    # _____")
        else:
            hangman_parts.append("    # _____")
        
        hangman_code = '\n'.join(hangman_parts)
        
        # Build the complete function
        complete_parts = [f"def {func_name}({param_str}):"]
        complete_parts.extend(given_lines if given_lines else ["    # Setup code"])
        complete_parts.extend(answer_section_lines if answer_section_lines else ["    return result"])
        
        complete_code = '\n'.join(complete_parts)
        
        return {
            'hangman_code': hangman_code,
            'complete_code': complete_code,
            'function_name': func_name,
            'parameters': parameters,
            'expected_output': expected_output
        }
    
    def _determine_expected_output(self, snippet, parameters):
        """Determine what output the function should produce for validation"""
        # Create test cases based on the snippet and parameters
        test_cases = []
        
        if 'input' in snippet.get('concepts', []):
            if 'name' in parameters and 'age' in parameters:
                test_cases = [
                    {'input': ['Alice', 25], 'description': 'name="Alice", age=25'},
                    {'input': ['Bob', 30], 'description': 'name="Bob", age=30'}
                ]
            elif 'name' in parameters:
                test_cases = [
                    {'input': ['Alice'], 'description': 'name="Alice"'},
                    {'input': ['Bob'], 'description': 'name="Bob"'}
                ]
            elif 'age' in parameters:
                test_cases = [
                    {'input': [25], 'description': 'age=25'},
                    {'input': [18], 'description': 'age=18'}
                ]
        elif any(concept in snippet.get('concepts', []) for concept in ['arithmetic', 'comparison']):
            if len(parameters) >= 2:
                test_cases = [
                    {'input': [10, 3], 'description': f'{parameters[0]}=10, {parameters[1]}=3'},
                    {'input': [5, 2], 'description': f'{parameters[0]}=5, {parameters[1]}=2'}
                ]
            else:
                test_cases = [
                    {'input': [10], 'description': f'{parameters[0]}=10'},
                    {'input': [5], 'description': f'{parameters[0]}=5'}
                ]
        
        if not test_cases:
            # Default test case
            test_cases = [{'input': ['test'], 'description': 'data="test"'}]
        
        return test_cases
    
    def _generate_hangman_fallback(self, subtopic):
        """Fallback hangman question if JSON loading fails"""
        hangman_code = f"""def process_user_data(name):
    # Given code
    user_input = input(f'Enter your {{name}}: ')
    
    # Enter your answer here
    
    # _____"""
        
        complete_code = f"""def process_user_data(name):
    # Given code
    user_input = input(f'Enter your {{name}}: ')
    
    # Complete the function
    result = f'You entered: {{user_input}}'
    return result"""
        
        return {
            'question_text': f"Complete the function for {subtopic.name}:\n\n{hangman_code}",
            'question_type': 'code_completion',
            'answer_options': ['result', 'output', 'data', 'response'],
            'correct_answer': complete_code,
            'explanation': f"This function demonstrates basic input/output concepts in {subtopic.name}.",
            'game_data': {
                'difficulty_level': 'auto',
                'fallback': True,
                'function_name': 'process_user_data',
                'parameters': ['name'],
                'validation_type': 'output_based',
                'expected_output': [
                    {'input': ['Alice'], 'description': 'name="Alice"'},
                    {'input': ['Bob'], 'description': 'name="Bob"'}
                ]
            }
        }
    
    def _generate_debugging_fallback(self, subtopic):
        """Fallback debugging question if JSON loading fails"""
        buggy_code = f"# {subtopic.name} example\nuser_input = input('Enter name: '\nprint(f'Hello {{user_input}}!')"
        fixed_code = f"# {subtopic.name} example\nuser_input = input('Enter name: ')\nprint(f'Hello {{user_input}}!')"
        
        return {
            'question_text': f"Debug the code for {subtopic.name}:\n\n{buggy_code}",
            'question_type': 'coding_exercise',
            'answer_options': [],
            'correct_answer': fixed_code,
            'explanation': "Missing closing parenthesis in input() function call.",
            'game_data': {
                'buggy_code': buggy_code,
                'fixed_code': fixed_code,
                'bug_type': 'syntax_error',
                'bug_description': 'Missing closing parenthesis',
                'validation_type': 'execution_based',
                'win_condition': 'code_executes_successfully',
                'difficulty_level': 'auto',
                'fallback': True
            }
        }
    
    def _generate_word_search_question(self, subtopic, context):
        """Generate a word search puzzle question using JSON data"""
        snippets_data = load_code_snippets()
        
        if snippets_data and 'word_search_terms' in snippets_data:
            # Find relevant word category
            category = self._find_word_search_category(subtopic.name)
            words = snippets_data['word_search_terms'].get(category, [])
            
            if not words:
                # Use a default set if category not found
                words = snippets_data['word_search_terms']['input_output']
            
            # Select 6-8 words for the puzzle
            selected_words = random.sample(words, min(8, len(words)))
            
            return {
                'question_text': f"Find all the {subtopic.name} related terms hidden in the word search puzzle:",
                'question_type': 'multiple_choice',
                'answer_options': selected_words,
                'correct_answer': ', '.join(selected_words),
                'explanation': f"These terms are fundamental to understanding {subtopic.name}.",
                'game_data': {
                    'words_to_find': selected_words,
                    'grid_size': 12,
                    'category': category,
                    'theme': subtopic.name,
                    'difficulty_level': 'auto'
                }
            }
        
        # Fallback version
        return self._generate_word_search_fallback(subtopic)
    
    def _generate_crossword_question(self, subtopic, context):
        """Generate a crossword puzzle question using JSON data"""
        snippets_data = load_code_snippets()
        
        if snippets_data and 'crossword_clues' in snippets_data:
            across_clues = snippets_data['crossword_clues']['across']
            down_clues = snippets_data['crossword_clues']['down']
            
            # Select 3-4 clues for a smaller crossword
            selected_across = random.sample(across_clues, min(3, len(across_clues)))
            selected_down = random.sample(down_clues, min(2, len(down_clues)))
            
            all_answers = [clue['answer'] for clue in selected_across + selected_down]
            
            return {
                'question_text': f"Complete the {subtopic.name} crossword puzzle using the clues provided:",
                'question_type': 'short_answer',
                'answer_options': [],
                'correct_answer': ', '.join(all_answers),
                'explanation': f"This crossword tests your knowledge of {subtopic.name} terminology.",
                'game_data': {
                    'across_clues': selected_across,
                    'down_clues': selected_down,
                    'grid_size': 10,
                    'solution_words': all_answers,
                    'theme': subtopic.name,
                    'difficulty_level': 'auto'
                }
            }
        
        # Fallback version
        return self._generate_crossword_fallback(subtopic)
    
    def _find_word_search_category(self, subtopic_name):
        """Find appropriate word search category based on subtopic"""
        subtopic_lower = subtopic_name.lower()
        
        if any(word in subtopic_lower for word in ['input', 'output', 'print']):
            return 'input_output'
        elif any(word in subtopic_lower for word in ['variable', 'data', 'type']):
            return 'variables'
        elif any(word in subtopic_lower for word in ['operator', 'arithmetic', 'math']):
            return 'operators'
        elif any(word in subtopic_lower for word in ['if', 'else', 'condition']):
            return 'conditionals'
        elif any(word in subtopic_lower for word in ['loop', 'for', 'while']):
            return 'loops'
        elif any(word in subtopic_lower for word in ['int', 'float', 'string', 'bool']):
            return 'datatypes'
        else:
            return 'input_output'  # Default
    
    def _generate_word_search_fallback(self, subtopic):
        """Fallback word search if JSON fails"""
        default_words = ['python', 'code', 'program', 'variable', 'function', 'input', 'print', 'data']
        
        return {
            'question_text': f"Find all the {subtopic.name} related programming terms:",
            'question_type': 'multiple_choice',
            'answer_options': default_words,
            'correct_answer': ', '.join(default_words),
            'explanation': f"These are basic programming terms related to {subtopic.name}.",
            'game_data': {
                'words_to_find': default_words,
                'grid_size': 10,
                'theme': subtopic.name,
                'difficulty_level': 'auto',
                'fallback': True
            }
        }
    
    def _generate_crossword_fallback(self, subtopic):
        """Fallback crossword if JSON fails"""
        simple_clues = [
            {'number': 1, 'clue': 'Get user input', 'answer': 'input', 'direction': 'across'},
            {'number': 2, 'clue': 'Display output', 'answer': 'print', 'direction': 'down'},
            {'number': 3, 'clue': 'Store data', 'answer': 'variable', 'direction': 'across'}
        ]
        
        return {
            'question_text': f"Solve this {subtopic.name} crossword puzzle:",
            'question_type': 'short_answer',
            'answer_options': [],
            'correct_answer': 'input, print, variable',
            'explanation': f"Basic programming concepts for {subtopic.name}.",
            'game_data': {
                'clues': simple_clues,
                'grid_size': 8,
                'theme': subtopic.name,
                'difficulty_level': 'auto',
                'fallback': True
            }
        }
    
    def _extract_code_keywords(self, context, subtopic_name):
        """Extract code-related keywords for hangman game"""
        # Simple keyword extraction - in production, use NLP
        code_indicators = ['def ', 'class ', 'import ', 'from ', 'print(', 'input(']
        found_keywords = []
        
        for indicator in code_indicators:
            if indicator in context.lower():
                found_keywords.append(indicator.strip('( '))
        
        return {
            'words_to_guess': found_keywords or ['function', 'variable', 'loop', 'condition'],
            'target_word': subtopic_name.lower().replace(' ', '_'),
            'hints': [f"Used in {subtopic_name}", "Programming concept"],
            'code_template': f"# Template for {subtopic_name}\n# Fill in the blanks"
        }
    
    def _create_buggy_code(self, context, subtopic_name):
        """Create buggy code for debugging game"""
        # Template buggy code - simplified without difficulty levels
        buggy_code = f"""# {subtopic_name} example with bugs
def example_function()
    x = 5
    y = "hello world"
    print(x + y)  # Bug: mixing types
    return x"""
        
        fixed_code = f"""# {subtopic_name} example - fixed
def example_function():
    x = 5
    y = "hello world"
    print(f"x = {{x}}, y = {{y}}")  # Fixed: proper string formatting
    return x"""
        
        return {
            'buggy_code': buggy_code,
            'fixed_code': fixed_code,
            'bug_locations': [1, 4],  # Line numbers
            'bug_types': ['syntax_error', 'type_error'],
            'bug_explanations': ['Missing colon after function definition', 'Cannot add int and string'],
            'hints': ['Check the function definition', 'Look at the data types being combined'],
            'lines_to_debug': [1, 4]
        }
    
    def _extract_key_terms(self, context, subtopic_name):
        """Extract key terms for word search"""
        # Simple term extraction - in production, use NLP
        common_terms = ['python', 'code', 'function', 'variable', 'loop', 'condition', 'data', 'input', 'output']
        subtopic_words = subtopic_name.lower().split()
        
        words_to_find = subtopic_words + [term for term in common_terms if term in context.lower()][:8]
        
        return {
            'words_to_find': list(set(words_to_find))[:10],  # Limit to 10 unique words
            'definitions': {word: f"Programming concept related to {subtopic_name}" for word in words_to_find},
            'bonus_words': ['programming', 'coding', 'syntax']
        }
    
    def _extract_crossword_clues(self, context, subtopic_name):
        """Extract clues and answers for crossword"""
        # Generate clues based on subtopic
        base_words = subtopic_name.lower().split()
        
        across_clues = [
            {'number': 1, 'clue': f'Main concept in {subtopic_name}', 'answer': base_words[0] if base_words else 'python', 'length': len(base_words[0]) if base_words else 6},
            {'number': 3, 'clue': 'Programming language we use', 'answer': 'python', 'length': 6},
            {'number': 5, 'clue': 'Block of reusable code', 'answer': 'function', 'length': 8}
        ]
        
        down_clues = [
            {'number': 2, 'clue': 'Store data in programming', 'answer': 'variable', 'length': 8},
            {'number': 4, 'clue': 'Repeat code multiple times', 'answer': 'loop', 'length': 4}
        ]
        
        return {
            'across_clues': across_clues,
            'down_clues': down_clues,
            'solution_words': [clue['answer'] for clue in across_clues + down_clues],
            'solution_grid': f"Grid for {subtopic_name} crossword"
        }
