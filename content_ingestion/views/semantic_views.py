"""
Semantic Similarity Views for content ingestion.

These views handle semantic similarity processing between subtopics and document chunks.
"""
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import logging

from ..models import UploadedDocument, SemanticSubtopic, Subtopic
from ..helpers.semantic_similarity import (
    compute_semantic_similarities_for_document,
    compute_semantic_similarities_all,
    get_similar_chunks_for_subtopic
)

logger = logging.getLogger(__name__)


@api_view(['POST'])
def process_semantic_similarities(request, document_id):
    """
    Process semantic similarities for a specific document.
    
    POST /content_ingestion/semantic/<document_id>/
    
    Optional parameters:
    - similarity_threshold (float): Minimum similarity score (default: 0.1)
    - top_k_results (int): Maximum results per subtopic (default: 10)
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        # Get parameters from request
        similarity_threshold = float(request.data.get('similarity_threshold', 0.1))
        top_k_results = int(request.data.get('top_k_results', 10))
        
        # Validate parameters
        if not 0.0 <= similarity_threshold <= 1.0:
            return Response({
                'status': 'error',
                'message': 'similarity_threshold must be between 0.0 and 1.0'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not 1 <= top_k_results <= 50:
            return Response({
                'status': 'error', 
                'message': 'top_k_results must be between 1 and 50'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Process semantic similarities
        result = compute_semantic_similarities_for_document(
            document_id=document_id,
            similarity_threshold=similarity_threshold,
            top_k_results=top_k_results
        )
        
        if result['status'] == 'success':
            return Response({
                'status': 'success',
                'message': f'Semantic similarities processed for "{document.title}"',
                'document_id': document_id,
                'document_title': document.title,
                'results': result
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'status': result['status'],
                'message': result.get('message', 'Processing completed with warnings'),
                'results': result
            }, status=status.HTTP_200_OK)
            
    except ValueError as e:
        return Response({
            'status': 'error',
            'message': f'Invalid parameter: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error processing semantic similarities for document {document_id}: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Processing failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def process_all_semantic_similarities(request):
    """
    Process semantic similarities for all available content.
    
    POST /content_ingestion/semantic/all/
    
    Optional parameters:
    - similarity_threshold (float): Minimum similarity score (default: 0.1)  
    - top_k_results (int): Maximum results per subtopic (default: 10)
    """
    try:
        # Get parameters from request
        similarity_threshold = float(request.data.get('similarity_threshold', 0.1))
        top_k_results = int(request.data.get('top_k_results', 10))
        
        # Validate parameters
        if not 0.0 <= similarity_threshold <= 1.0:
            return Response({
                'status': 'error',
                'message': 'similarity_threshold must be between 0.0 and 1.0'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not 1 <= top_k_results <= 50:
            return Response({
                'status': 'error',
                'message': 'top_k_results must be between 1 and 50'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Process semantic similarities for all content
        result = compute_semantic_similarities_all(
            similarity_threshold=similarity_threshold,
            top_k_results=top_k_results
        )
        
        return Response({
            'status': result['status'],
            'message': 'Global semantic similarity processing completed',
            'results': result
        }, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response({
            'status': 'error',
            'message': f'Invalid parameter: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error processing all semantic similarities: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Processing failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_subtopic_similar_chunks(request, subtopic_id):
    """
    Get similar chunks for a specific subtopic based on semantic similarity.
    
    GET /content_ingestion/semantic/subtopic/<subtopic_id>/chunks/
    
    Query parameters:
    - chunk_type: Filter by chunk type (Concept, Code, Exercise, etc.)
    - limit: Maximum number of chunks to return (default: 5)
    - min_similarity: Minimum similarity threshold (default: 0.5)
    """
    try:
        subtopic = get_object_or_404(Subtopic, id=subtopic_id)
        
        # Get query parameters
        chunk_type = request.GET.get('chunk_type')
        limit = int(request.GET.get('limit', 5))
        min_similarity = float(request.GET.get('min_similarity', 0.5))
        
        # Validate parameters
        if not 1 <= limit <= 20:
            return Response({
                'status': 'error',
                'message': 'limit must be between 1 and 20'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not 0.0 <= min_similarity <= 1.0:
            return Response({
                'status': 'error',
                'message': 'min_similarity must be between 0.0 and 1.0'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get similar chunks
        chunk_ids = get_similar_chunks_for_subtopic(
            subtopic_id=subtopic_id,
            chunk_type=chunk_type,
            limit=limit,
            min_similarity=min_similarity
        )
        
        # Get semantic data for additional info
        try:
            semantic_data = SemanticSubtopic.objects.get(subtopic=subtopic)
            
            # Get chunks based on type
            if chunk_type == 'Concept':
                ranked_chunks = semantic_data.ranked_concept_chunks
            elif chunk_type in ['Code', 'Example', 'Exercise', 'Try_It']:
                ranked_chunks = semantic_data.ranked_code_chunks
            else:
                # Combine both lists for general queries
                ranked_chunks = (semantic_data.ranked_concept_chunks or []) + (semantic_data.ranked_code_chunks or [])
            
            # Filter and format results
            filtered_chunks = []
            for chunk_info in ranked_chunks:
                if chunk_info['chunk_id'] in chunk_ids:
                    if not chunk_type or chunk_info.get('chunk_type') == chunk_type:
                        if chunk_info.get('similarity', 0) >= min_similarity:
                            filtered_chunks.append(chunk_info)
            
            # Sort by similarity and limit
            filtered_chunks.sort(key=lambda x: x.get('similarity', 0), reverse=True)
            filtered_chunks = filtered_chunks[:limit]
            
        except SemanticSubtopic.DoesNotExist:
            filtered_chunks = []
        
        return Response({
            'status': 'success',
            'subtopic_id': subtopic_id,
            'subtopic_name': subtopic.name,
            'filters': {
                'chunk_type': chunk_type,
                'limit': limit,
                'min_similarity': min_similarity
            },
            'chunk_ids': chunk_ids,
            'detailed_results': filtered_chunks,
            'total_results': len(filtered_chunks)
        }, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response({
            'status': 'error',
            'message': f'Invalid parameter: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error getting similar chunks for subtopic {subtopic_id}: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Request failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_semantic_overview(request):
    """
    Get overview of semantic similarity data across all subtopics.
    
    GET /content_ingestion/semantic/overview/
    """
    try:
        # Get all semantic subtopics
        semantic_subtopics = SemanticSubtopic.objects.select_related('subtopic').all()
        
        overview_data = []
        total_similarities = 0
        
        for semantic_subtopic in semantic_subtopics:
            concept_count = len(semantic_subtopic.ranked_concept_chunks) if semantic_subtopic.ranked_concept_chunks else 0
            code_count = len(semantic_subtopic.ranked_code_chunks) if semantic_subtopic.ranked_code_chunks else 0
            chunk_count = concept_count + code_count
            total_similarities += chunk_count
            
            # Get chunk type breakdown
            chunk_types = {}
            all_chunks = (semantic_subtopic.ranked_concept_chunks or []) + (semantic_subtopic.ranked_code_chunks or [])
            for chunk in all_chunks:
                chunk_type = chunk.get('chunk_type', 'Unknown')
                chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
            
            # Get highest similarity from both lists
            highest_similarity = 0.0
            if all_chunks:
                highest_similarity = max(
                    chunk.get('similarity', 0) for chunk in all_chunks
                )
            
            overview_data.append({
                'subtopic_id': semantic_subtopic.subtopic.id,
                'subtopic_name': semantic_subtopic.subtopic.name,
                'similar_chunks_count': chunk_count,
                'chunk_types': chunk_types,
                'highest_similarity': highest_similarity,
                'updated_at': semantic_subtopic.updated_at.isoformat()
            })
        
        # Sort by chunk count (most similar chunks first)
        overview_data.sort(key=lambda x: x['similar_chunks_count'], reverse=True)
        
        return Response({
            'status': 'success',
            'total_subtopics': len(semantic_subtopics),
            'total_similarities': total_similarities,
            'average_similarities_per_subtopic': total_similarities / len(semantic_subtopics) if semantic_subtopics else 0,
            'subtopics': overview_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting semantic overview: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Request failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
