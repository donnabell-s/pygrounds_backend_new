"""
Embedding-related views for RAG functionality.
"""

from .imports import *
from content_ingestion.helpers.json_export_utils import log_embedding_generation

@api_view(['POST'])
def embed_document_chunks(request, document_id):
    """
    Generate embeddings for all document chunks for RAG retrieval.
    """
    try:
        from content_ingestion.helpers.embedding_utils import EmbeddingGenerator
        from content_ingestion.models import DocumentChunk

        document = get_object_or_404(UploadedDocument, id=document_id)

        print("\n🔮 EMBEDDING DOCUMENT CHUNKS")
        print("=" * 50)
        print(f"Document: {document.title}")

        all_chunks = DocumentChunk.objects.filter(document=document)
        chunks_to_embed = all_chunks.filter(embedding__isnull=True)
        already_embedded = all_chunks.filter(embedding__isnull=False)

        print(f"Total chunks: {all_chunks.count()}")
        print(f"Already embedded: {already_embedded.count()}")
        print(f"Need embedding: {chunks_to_embed.count()}")

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

        print("\n📊 EMBEDDING RESULTS")
        print("─" * 30)
        print(f"Success: {embedding_results['success']}")
        print(f"Failed: {embedding_results['failed']}")
        print(f"Model: {embedding_results['model']}")

        # Detailed chunk embedding data (for logging, not full API output)
        chunk_logs = []
        for chunk in all_chunks:
            chunk_logs.append({
                'chunk_id': chunk.id,
                'chunk_type': chunk.chunk_type,
                'content_preview': chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                'has_embedding': chunk.embedding is not None,
                'embedding_dimensions': len(chunk.embedding) if chunk.embedding else 0,
                'topic_title': chunk.topic_title,
                'subtopic_title': chunk.subtopic_title,
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
        log_result = log_embedding_generation('document_chunks', document.id, embedding_log_data)

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
            },
            'json_log': log_result
        })

    except Exception as e:
        print(f"❌ Embedding failed: {str(e)}")
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
            has_embedding = bool(chunk.embedding)
            if has_embedding:
                embedded_count += 1

            embedding_data.append({
                'id': chunk.id,
                'topic_title': chunk.topic_title,
                'page_number': chunk.page_number,
                'text_preview': chunk.text[:100] + "..." if len(chunk.text) > 100 else chunk.text,
                'has_embedding': has_embedding,
                'embedding_dimension': len(chunk.embedding) if has_embedding else 0,
                'embedding_model': chunk.embedding_model,
                'embedded_at': chunk.embedded_at.isoformat() if chunk.embedded_at else None
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
