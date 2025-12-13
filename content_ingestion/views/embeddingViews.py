import logging
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import UploadedDocument

logger = logging.getLogger(__name__)

@api_view(['POST'])
def embed_document_chunks(request, document_id):
    # Generate embeddings for all document chunks for RAG retrieval
    # Uses dual embedding system: Concept chunks -> MiniLM, others -> CodeBERT
    try:
        from content_ingestion.helpers.embedding import EmbeddingGenerator
        from content_ingestion.models import DocumentChunk, Embedding

        document = get_object_or_404(UploadedDocument, id=document_id)

        all_chunks = DocumentChunk.objects.filter(document=document)
        
        # Check for existing embeddings in the new vector fields
        chunks_with_embeddings = []
        chunks_to_embed = []
        
        for chunk in all_chunks:
            has_minilm = Embedding.objects.filter(
                document_chunk=chunk, 
                content_type='chunk',
                minilm_vector__isnull=False
            ).exists()
            has_codebert = Embedding.objects.filter(
                document_chunk=chunk, 
                content_type='chunk',
                codebert_vector__isnull=False
            ).exists()
            
            # Chunk needs embedding if it doesn't have the appropriate vector for its type
            if chunk.chunk_type == 'Concept':
                if not has_minilm:
                    chunks_to_embed.append(chunk)
                else:
                    chunks_with_embeddings.append(chunk)
            else:
                if not has_codebert:
                    chunks_to_embed.append(chunk)
                else:
                    chunks_with_embeddings.append(chunk)

        if not chunks_to_embed:
            return Response({
                'status': 'success',
                'message': 'All chunks already have appropriate embeddings',
                'document_id': document.id,
                'document_title': document.title,
                'embedding_stats': {
                    'total_chunks': all_chunks.count(),
                    'already_embedded': len(chunks_with_embeddings),
                    'newly_embedded': 0,
                    'failed': 0
                }
            })

        print(f"📝 Found {len(chunks_to_embed)} chunks to embed")
        
        # Generate embeddings using the updated generator
        embedding_generator = EmbeddingGenerator()
        embedding_results = embedding_generator.embed_and_save_batch(chunks_to_embed)

        # Log chunk embedding status with new vector fields
        chunk_logs = []
        for chunk in all_chunks:
            # Check both vector types for this chunk
            minilm_embedding = Embedding.objects.filter(
                document_chunk=chunk, 
                content_type='chunk',
                minilm_vector__isnull=False
            ).first()
            codebert_embedding = Embedding.objects.filter(
                document_chunk=chunk, 
                content_type='chunk',
                codebert_vector__isnull=False
            ).first()
            
            has_appropriate_embedding = False
            embedding_info = {}
            
            if chunk.chunk_type == 'Concept' and minilm_embedding:
                has_appropriate_embedding = True
                embedding_info = {
                    'model_type': 'MiniLM',
                    'dimensions': len(minilm_embedding.minilm_vector),
                    'model_name': minilm_embedding.model_name
                }
            elif chunk.chunk_type != 'Concept' and codebert_embedding:
                has_appropriate_embedding = True
                embedding_info = {
                    'model_type': 'CodeBERT', 
                    'dimensions': len(codebert_embedding.codebert_vector),
                    'model_name': codebert_embedding.model_name
                }
            
            chunk_logs.append({
                'chunk_id': chunk.id,
                'chunk_type': chunk.chunk_type,
                'content_preview': chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text,
                'has_appropriate_embedding': has_appropriate_embedding,
                'embedding_info': embedding_info,
                'page_number': chunk.page_number
            })

        return Response({
            'status': 'success',
            'message': f"Generated embeddings for {embedding_results['embeddings_generated']} chunks",
            'document_id': document.id,
            'document_title': document.title,
            'embedding_stats': {
                'total_chunks': all_chunks.count(),
                'already_embedded': len(chunks_with_embeddings),
                'newly_embedded': embedding_results['embeddings_generated'],
                'failed': embedding_results['embeddings_failed'],
                'database_saves': embedding_results['database_saves'], 
                'database_errors': embedding_results['database_errors'],
                'models_used': embedding_results['models_used']
            },
            'chunk_details': chunk_logs
        })

    except Exception as e:
        import traceback
        print(f"❌ Error in embed_document_chunks: {str(e)}")
        print(traceback.format_exc())
        return Response({
            'status': 'error',
            'message': f"Failed to generate embeddings: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_chunk_embeddings(request, document_id):
    # Return embedding coverage + metadata per chunk.
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        from content_ingestion.models import DocumentChunk, Embedding

        chunks = DocumentChunk.objects.filter(document=document).order_by('page_number', 'order_in_doc')

        embedding_data = []
        embedded_count = 0

        for chunk in chunks:
            # Check for appropriate embedding based on chunk type
            minilm_embedding = Embedding.objects.filter(
                document_chunk=chunk,
                content_type='chunk',
                minilm_vector__isnull=False
            ).first()
            
            codebert_embedding = Embedding.objects.filter(
                document_chunk=chunk,
                content_type='chunk', 
                codebert_vector__isnull=False
            ).first()
            
            # Determine if chunk has appropriate embedding for its type
            has_embedding = False
            embedding_info = {}
            
            if chunk.chunk_type == 'Concept' and minilm_embedding:
                has_embedding = True
                embedding_info = {
                    'model_type': 'MiniLM',
                    'model_name': minilm_embedding.model_name,
                    'dimension': len(minilm_embedding.minilm_vector),
                    'embedded_at': minilm_embedding.embedded_at.isoformat()
                }
                embedded_count += 1
            elif chunk.chunk_type != 'Concept' and codebert_embedding:
                has_embedding = True
                embedding_info = {
                    'model_type': 'CodeBERT',
                    'model_name': codebert_embedding.model_name, 
                    'dimension': len(codebert_embedding.codebert_vector),
                    'embedded_at': codebert_embedding.embedded_at.isoformat()
                }
                embedded_count += 1

            embedding_data.append({
                'id': chunk.id,
                'chunk_type': chunk.chunk_type,
                'page_number': chunk.page_number,
                'text_preview': chunk.text[:100] + "..." if len(chunk.text) > 100 else chunk.text,
                'has_embedding': has_embedding,
                'embedding_info': embedding_info,
                'expected_model': 'MiniLM' if chunk.chunk_type == 'Concept' else 'CodeBERT'
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
    # Return embeddings including vectors (large payload).
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
                'content_preview': chunk.text[:300] + "..." if len(chunk.text) > 300 else chunk.text,
                'full_content_length': len(chunk.text),
                'page_number': chunk.page_number,
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
    # Generate dual embeddings (MiniLM + CodeBERT) for all subtopics
    try:
        from content_ingestion.helpers.embedding import EmbeddingGenerator
        from content_ingestion.models import Embedding, Subtopic

        # Get subtopics that don't have both embeddings
        subtopics_needing_embeddings = []
        total = Subtopic.objects.count()
        
        for subtopic in Subtopic.objects.all():
            has_minilm = Embedding.objects.filter(
                subtopic=subtopic,
                content_type='subtopic',
                minilm_vector__isnull=False
            ).exists()
            has_codebert = Embedding.objects.filter(
                subtopic=subtopic,
                content_type='subtopic',
                codebert_vector__isnull=False
            ).exists()
            
            if not (has_minilm and has_codebert):
                subtopics_needing_embeddings.append(subtopic)

        already_embedded = total - len(subtopics_needing_embeddings)

        if not subtopics_needing_embeddings:
            return Response({
                'status': 'success',
                'message': 'All subtopics already have dual embeddings',
                'embedding_stats': {
                    'total_subtopics': total,
                    'already_embedded': already_embedded,
                    'newly_embedded': 0,
                    'failed': 0
                }
            })

        generator = EmbeddingGenerator()
        success = 0
        failed = 0
        details = []

        for subtopic in subtopics_needing_embeddings:
            try:
                subtopic_text = f"{subtopic.topic.name} - {subtopic.name}"
                
                # Generate MiniLM embedding
                minilm_result = generator.generate_embedding(subtopic_text, chunk_type='Concept')
                if minilm_result['vector']:
                    minilm_embedding, created = Embedding.objects.get_or_create(
                        subtopic=subtopic,
                        model_type='sentence',
                        content_type='subtopic',
                        defaults={
                            'minilm_vector': minilm_result['vector'],
                            'model_name': minilm_result['model_name'],
                            'dimension': minilm_result['dimension']
                        }
                    )
                    if not created:
                        minilm_embedding.minilm_vector = minilm_result['vector']
                        minilm_embedding.model_name = minilm_result['model_name']
                        minilm_embedding.dimension = minilm_result['dimension']
                        minilm_embedding.save()

                # Generate CodeBERT embedding  
                codebert_result = generator.generate_embedding(subtopic_text, chunk_type='Code')
                if codebert_result['vector']:
                    codebert_embedding, created = Embedding.objects.get_or_create(
                        subtopic=subtopic,
                        model_type='code_bert',
                        content_type='subtopic',
                        defaults={
                            'codebert_vector': codebert_result['vector'],
                            'model_name': codebert_result['model_name'],
                            'dimension': codebert_result['dimension']
                        }
                    )
                    if not created:
                        codebert_embedding.codebert_vector = codebert_result['vector']
                        codebert_embedding.model_name = codebert_result['model_name']
                        codebert_embedding.dimension = codebert_result['dimension']
                        codebert_embedding.save()

                if minilm_result['vector'] and codebert_result['vector']:
                    details.append({
                        'subtopic_id': subtopic.id,
                        'subtopic_name': subtopic.name,
                        'topic_name': subtopic.topic.name,
                        'minilm_status': 'success',
                        'codebert_status': 'success',
                        'status': 'success'
                    })
                    success += 1
                else:
                    details.append({
                        'subtopic_id': subtopic.id,
                        'subtopic_name': subtopic.name,
                        'topic_name': subtopic.topic.name,
                        'minilm_status': 'success' if minilm_result['vector'] else 'failed',
                        'codebert_status': 'success' if codebert_result['vector'] else 'failed',
                        'status': 'partial_failure',
                        'error': 'One or both embedding generations failed'
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

        return Response({
            'status': 'success',
            'message': f"Generated dual embeddings for {success} subtopics",
            'embedding_stats': {
                'total_subtopics': total,
                'already_embedded': already_embedded,
                'newly_embedded': success,
                'failed': failed,
                'models_used': ['all-MiniLM-L6-v2', 'microsoft/codebert-base']
            },
            'details': details
        })

    except Exception as e:
        import traceback
        print(f"❌ Error in generate_subtopic_embeddings: {str(e)}")
        print(traceback.format_exc())
        return Response({
            'status': 'error',
            'message': f"Failed to generate subtopic embeddings: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_topic_subtopic_embeddings_detailed(request):
    # Retrieve topic/subtopic embeddings (including vectors).
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
