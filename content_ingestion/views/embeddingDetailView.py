"""
Specialized views for retrieving detailed embedding information including vectors.
"""

from .imports import *
from content_ingestion.helpers.json_export_utils import json_exporter

@api_view(['GET'])
def get_chunk_embeddings_detailed(request, document_id):
    """
    Retrieve all chunk embeddings for a document, including actual vectors.
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        print("\n🔍 RETRIEVING DETAILED CHUNK EMBEDDINGS")
        print("=" * 50)
        print(f"Document: {document.title}")

        # Query all chunks for the document
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
                'topic_title': chunk.topic_title,
                'subtopic_title': chunk.subtopic_title,
                'has_embedding': has_embedding,
                'embedding_vector': chunk.embedding if has_embedding else None,
                'embedding_dimensions': len(chunk.embedding) if has_embedding else 0
            }
            if has_embedding:
                chunks_with_embeddings.append(chunk_data)
                embedding_dimensions = len(chunk.embedding)
            else:
                chunks_without_embeddings.append(chunk_data)

        print(f"Total chunks: {chunks.count()}")
        print(f"With embeddings: {len(chunks_with_embeddings)}")
        print(f"Without embeddings: {len(chunks_without_embeddings)}")
        print(f"Embedding dimensions: {embedding_dimensions}")

        # Prepare exportable data
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
        export_filename = f"document_{document_id}_chunk_embeddings_detailed"
        export_result = json_exporter.export_snapshot(export_filename, export_data)

        return Response({
            'status': 'success',
            'document': export_data['document_info'],
            'embedding_summary': export_data['embedding_summary'],
            'chunks_with_embeddings': chunks_with_embeddings,
            'chunks_without_embeddings': chunks_without_embeddings,
            'json_export': export_result
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
        print("\n🔍 RETRIEVING DETAILED TOPIC/SUBTOPIC EMBEDDINGS")
        print("=" * 50)

        # Topics
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

        # Subtopics
        subtopics = Subtopic.objects.all()
        subtopics_with_embeddings = []
        subtopics_without_embeddings = []

        for subtopic in subtopics:
            # Check if subtopic has an embedding via the Embedding model
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

        print(f"Topics with embeddings: {len(topics_with_embeddings)}/{topics.count()}")
        print(f"Subtopics with embeddings: {len(subtopics_with_embeddings)}/{subtopics.count()}")

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
        export_result = json_exporter.export_snapshot("topic_subtopic_embeddings_detailed", export_data)

        return Response({
            'status': 'success',
            'embedding_summary': export_data['embedding_summary'],
            'topics_with_embeddings': topics_with_embeddings,
            'topics_without_embeddings': topics_without_embeddings,
            'subtopics_with_embeddings': subtopics_with_embeddings,
            'subtopics_without_embeddings': subtopics_without_embeddings,
            'json_export': export_result
        })

    except Exception as e:
        return Response({
            'status': 'error',
            'message': f"Failed to retrieve detailed topic/subtopic embeddings: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
