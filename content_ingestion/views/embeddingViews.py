"""
Unified Embedding Views for RAG functionality.
Includes chunk, topic, and subtopic embedding endpoints.
"""

from ..helpers.view_imports import *
from ..helpers.helper_imports import *

@api_view(['POST'])
def embed_document_chunks(request, document_id):
    """
    Generate embeddings for all document chunks for RAG retrieval.
    """
    try:
        from content_ingestion.helpers.embedding import EmbeddingGenerator
        from content_ingestion.models import DocumentChunk

        document = get_object_or_404(UploadedDocument, id=document_id)

        all_chunks = DocumentChunk.objects.filter(document=document)
        chunks_to_embed = all_chunks.filter(embeddings__isnull=True)
        already_embedded = all_chunks.filter(embeddings__isnull=False)

        if not chunks_to_embed.exists():
            return Response({
                'status': 'success',
                'message': 'All chunks already have embeddings',
                'document_id': document.id,
                'document_title': document.title,
                'embedding_stats': {
                    'total_chunks': all_chunks.count(),
                    'already_embedded': already_embedded.count(),
                    'newly_embedded': 0,
                    'failed': 0
                }
            })

        embedding_generator = EmbeddingGenerator()
        embedding_results = embedding_generator.embed_chunks_batch(chunks_to_embed)

        chunk_logs = []
        for chunk in all_chunks:
            embedding_obj = chunk.embeddings.first()
            chunk_logs.append({
                'chunk_id': chunk.id,
                'chunk_type': chunk.chunk_type,
                'content_preview': chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                'has_embedding': embedding_obj is not None,
                'embedding_dimensions': len(embedding_obj.vector) if embedding_obj else 0,
                'topic_title': chunk.subtopic_title,
                'page_number': chunk.page_number
            })

        embedding_log_data = {
            'document_title': document.title,
            'total_chunks': all_chunks.count(),
            'already_embedded': already_embedded.count(),
            'newly_embedded': embedding_results['success'],
            'failed': embedding_results['failed'],
            'model_used': embedding_results['model'],
            'embedding_details': embedding_results,
            'chunks_embedding_data': chunk_logs
        }

        return Response({
            'status': 'success',
            'message': f"Generated embeddings for {embedding_results['success']} chunks",
            'document_id': document.id,
            'document_title': document.title,
            'embedding_stats': {
                'total_chunks': all_chunks.count(),
                'already_embedded': already_embedded.count(),
                'newly_embedded': embedding_results['success'],
                'failed': embedding_results['failed'],
                'model_used': embedding_results['model']
            }
        })

    except Exception as e:
        return Response({
            'status': 'error',
            'message': f"Failed to generate embeddings: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_chunk_embeddings(request, document_id):
    """
    Get embedding status and metadata for all chunks in a document.
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        from content_ingestion.models import DocumentChunk

        chunks = DocumentChunk.objects.filter(document=document).order_by('page_number', 'order_in_doc')

        embedding_data = []
        embedded_count = 0

        for chunk in chunks:
            embedding_obj = chunk.embeddings.first()
            has_embedding = bool(embedding_obj)
            if has_embedding:
                embedded_count += 1

            embedding_data.append({
                'id': chunk.id,
                'topic_title': chunk.subtopic_title,
                'page_number': chunk.page_number,
                'text_preview': chunk.text[:100] + "..." if len(chunk.text) > 100 else chunk.text,
                'has_embedding': has_embedding,
                'embedding_dimension': len(embedding_obj.vector) if has_embedding else 0,
                'embedding_model': embedding_obj.model_name if has_embedding else None,
                'embedded_at': embedding_obj.created_at.isoformat() if has_embedding else None
            })

        total_chunks = chunks.count()
        not_embedded_count = total_chunks - embedded_count

        return Response({
            'status': 'success',
            'document_id': document.id,
            'document_title': document.title,
            'embedding_summary': {
                'total_chunks': total_chunks,
                'embedded_chunks': embedded_count,
                'not_embedded_chunks': not_embedded_count,
                'embedding_coverage': f"{(embedded_count / total_chunks * 100):.1f}%" if total_chunks else "0%"
            },
            'chunks': embedding_data
        })

    except Exception as e:
        return Response({
            'status': 'error',
            'message': f"Failed to retrieve embedding data: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_chunk_embeddings_detailed(request, document_id):
    """
    Retrieve all chunk embeddings for a document, including actual vectors.
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        from content_ingestion.models import DocumentChunk

        chunks = DocumentChunk.objects.filter(document=document)
        chunks_with_embeddings = []
        chunks_without_embeddings = []
        embedding_dimensions = 0

        for chunk in chunks:
            has_embedding = chunk.embedding is not None
            chunk_data = {
                'chunk_id': chunk.id,
                'chunk_type': chunk.chunk_type,
                'content_preview': chunk.content[:300] + "..." if len(chunk.content) > 300 else chunk.content,
                'full_content_length': len(chunk.content),
                'page_number': chunk.page_number,
                'start_page': chunk.start_page,
                'end_page': chunk.end_page,
                'topic_title': chunk.subtopic_title,
                'has_embedding': has_embedding,
                'embedding_vector': chunk.embedding if has_embedding else None,
                'embedding_dimensions': len(chunk.embedding) if has_embedding else 0
            }
            if has_embedding:
                chunks_with_embeddings.append(chunk_data)
                embedding_dimensions = len(chunk.embedding)
            else:
                chunks_without_embeddings.append(chunk_data)

        export_data = {
            'document_info': {
                'id': document.id,
                'title': document.title,
                'total_pages': document.total_pages
            },
            'embedding_summary': {
                'total_chunks': chunks.count(),
                'chunks_with_embeddings': len(chunks_with_embeddings),
                'chunks_without_embeddings': len(chunks_without_embeddings),
                'embedding_dimensions': embedding_dimensions
            },
            'chunks_with_embeddings': chunks_with_embeddings,
            'chunks_without_embeddings': chunks_without_embeddings
        }

        return Response({
            'status': 'success',
            'document': export_data['document_info'],
            'embedding_summary': export_data['embedding_summary'],
            'chunks_with_embeddings': chunks_with_embeddings,
            'chunks_without_embeddings': chunks_without_embeddings
        })

    except Exception as e:
        logger.error(f"Failed to get chunk embeddings for document {document_id}: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, 
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def generate_subtopic_embeddings(request):
    """Generate embeddings for all subtopics using advanced embedding system."""
    try:
        from content_ingestion.helpers.embedding import EmbeddingGenerator

        subtopics_with_embeddings = Subtopic.objects.filter(embeddings__isnull=False)
        subtopics = Subtopic.objects.exclude(id__in=subtopics_with_embeddings.values_list('id', flat=True))
        total = Subtopic.objects.count()
        already = subtopics_with_embeddings.count()

        if not subtopics.exists():
            return Response({
                'status': 'success',
                'message': 'All subtopics already have embeddings',
                'embedding_stats': {
                    'total_subtopics': total,
                    'already_embedded': already,
                    'newly_embedded': 0,
                    'failed': 0
                }
            })

        generator = EmbeddingGenerator()
        details, success, failed = [], 0, 0

        for subtopic in subtopics:
            try:
                embedding_data = generator.generate_subtopic_embedding(
                    subtopic_name=subtopic.name,
                    topic_name=subtopic.topic.name
                )
                
                if embedding_data['vector']:
                    from content_ingestion.models import Embedding
                    Embedding.objects.create(
                        subtopic=subtopic,
                        vector=embedding_data['vector'],
                        model_name=embedding_data['model_name'],
                        model_type=embedding_data['model_type'].value,
                        dimension=embedding_data['dimension']
                    )
                    
                    details.append({
                        'subtopic_id': subtopic.id,
                        'subtopic_name': subtopic.name,
                        'topic_name': subtopic.topic.name,
                        'model_used': embedding_data['model_name'],
                        'model_type': embedding_data['model_type'].value,
                        'dimension': embedding_data['dimension'],
                        'status': 'success'
                    })
                    success += 1
                else:
                    details.append({
                        'subtopic_id': subtopic.id,
                        'subtopic_name': subtopic.name,
                        'topic_name': subtopic.topic.name,
                        'status': 'failed',
                        'error': embedding_data.get('error', 'Unknown error')
                    })
                    failed += 1
            except Exception as e:
                details.append({
                    'subtopic_id': subtopic.id,
                    'subtopic_name': subtopic.name,
                    'topic_name': subtopic.topic.name,
                    'status': 'failed',
                    'error': str(e)
                })
                failed += 1

        log_data = {
            'total_subtopics': total,
            'already_embedded': already,
            'newly_embedded': success,
            'failed': failed,
            'model_used': 'all-MiniLM-L6-v2',
            'model_type': 'sentence',
            'embedding_details': details
        }
        
        return Response({
            'status': 'success',
            'message': f"Generated embeddings for {success} subtopics",
            'embedding_stats': {
                'total_subtopics': total,
                'already_embedded': already,
                'newly_embedded': success,
                'failed': failed,
                'model_used': 'all-MiniLM-L6-v2',
                'model_type': 'sentence'
            }
        })

    except Exception as e:
        return Response({
            'status': 'error',
            'message': f"Failed to retrieve detailed chunk embeddings: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_topic_subtopic_embeddings_detailed(request):
    """
    Retrieve all topic/subtopic embeddings, including vectors.
    """
    try:
        from content_ingestion.models import Topic, Subtopic

        topics = Topic.objects.all()
        topics_with_embeddings = []
        topics_without_embeddings = []

        for topic in topics:
            has_embedding = topic.description_embedding is not None
            topic_data = {
                'topic_id': topic.id,
                'topic_name': topic.name,
                'description': topic.description,
                'zone_name': topic.zone.name,
                'has_embedding': has_embedding,
                'embedding_vector': topic.description_embedding if has_embedding else None,
                'embedding_dimensions': len(topic.description_embedding) if has_embedding else 0
            }
            if has_embedding:
                topics_with_embeddings.append(topic_data)
            else:
                topics_without_embeddings.append(topic_data)

        subtopics = Subtopic.objects.all()
        subtopics_with_embeddings = []
        subtopics_without_embeddings = []

        for subtopic in subtopics:
            has_embedding = hasattr(subtopic, 'embedding_obj') and subtopic.embedding_obj is not None
            subtopic_data = {
                'subtopic_id': subtopic.id,
                'subtopic_name': subtopic.name,
                'topic_name': subtopic.topic.name,
                'zone_name': subtopic.topic.zone.name,
                'has_embedding': has_embedding,
                'embedding_vector': subtopic.embedding_obj.vector if has_embedding else None,
                'embedding_dimensions': len(subtopic.embedding_obj.vector) if has_embedding else 0
            }
            if has_embedding:
                subtopics_with_embeddings.append(subtopic_data)
            else:
                subtopics_without_embeddings.append(subtopic_data)

        export_data = {
            'embedding_summary': {
                'total_topics': topics.count(),
                'topics_with_embeddings': len(topics_with_embeddings),
                'topics_without_embeddings': len(topics_without_embeddings),
                'total_subtopics': subtopics.count(),
                'subtopics_with_embeddings': len(subtopics_with_embeddings),
                'subtopics_without_embeddings': len(subtopics_without_embeddings)
            },
            'topics_with_embeddings': topics_with_embeddings,
            'topics_without_embeddings': topics_without_embeddings,
            'subtopics_with_embeddings': subtopics_with_embeddings,
            'subtopics_without_embeddings': subtopics_without_embeddings
        }

        return Response({
            'status': 'success',
            'embedding_summary': export_data['embedding_summary'],
            'topics_with_embeddings': topics_with_embeddings,
            'topics_without_embeddings': topics_without_embeddings,
            'subtopics_with_embeddings': subtopics_with_embeddings,
            'subtopics_without_embeddings': subtopics_without_embeddings
        })

    except Exception as e:
        return Response({
            'status': 'error',
            'message': f"Failed to retrieve detailed topic/subtopic embeddings: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
