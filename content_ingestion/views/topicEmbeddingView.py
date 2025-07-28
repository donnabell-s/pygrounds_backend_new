"""
Topic and Subtopic embedding generation views.
"""

from .imports import *
from content_ingestion.helpers.json_export_utils import log_embedding_generation

@api_view(['POST'])
def generate_topic_embeddings(request):
    """Generate embeddings for all topics."""
    try:
        from content_ingestion.helpers.embedding_utils import EmbeddingGenerator

        topics = Topic.objects.filter(description_embedding__isnull=True)
        total = Topic.objects.count()
        already = total - topics.count()

        if not topics.exists():
            return Response({
                'status': 'success',
                'message': 'All topics already have embeddings',
                'embedding_stats': {
                    'total_topics': total,
                    'already_embedded': already,
                    'newly_embedded': 0,
                    'failed': 0
                }
            })

        generator = EmbeddingGenerator()
        details, success, failed = [], 0, 0

        for topic in topics:
            try:
                text = f"{topic.name}: {topic.description}"
                emb = generator.generate_embedding(text)
                topic.description_embedding = emb.tolist()
                topic.save(update_fields=['description_embedding'])
                details.append({
                    'topic_id': topic.id,
                    'topic_name': topic.name,
                    'status': 'success'
                })
                success += 1
            except Exception as e:
                details.append({
                    'topic_id': topic.id,
                    'topic_name': topic.name,
                    'status': 'failed',
                    'error': str(e)
                })
                failed += 1

        log_data = {
            'total_topics': total,
            'already_embedded': already,
            'newly_embedded': success,
            'failed': failed,
            'model_used': generator.model_name,
            'embedding_details': details
        }
        log_result = log_embedding_generation('topics', 'all', log_data)

        return Response({
            'status': 'success',
            'message': f"Generated embeddings for {success} topics",
            'embedding_stats': {
                'total_topics': total,
                'already_embedded': already,
                'newly_embedded': success,
                'failed': failed,
                'model_used': generator.model_name
            },
            'json_log': log_result
        })
    except Exception as e:
        return Response({'status': 'error', 'message': f"Failed to generate topic embeddings: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def generate_subtopic_embeddings(request):
    """Generate embeddings for all subtopics."""
    try:
        from content_ingestion.helpers.embedding_utils import EmbeddingGenerator

        # Find subtopics without embeddings
        subtopics_with_embeddings = Subtopic.objects.filter(embedding_obj__isnull=False)
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
                text = f"{subtopic.topic.name} - {subtopic.name}"
                emb = generator.generate_embedding(text)
                
                # Create embedding via the Embedding model
                from content_ingestion.models import Embedding
                Embedding.objects.create(
                    subtopic=subtopic,
                    vector=emb.tolist()
                )
                
                details.append({
                    'subtopic_id': subtopic.id,
                    'subtopic_name': subtopic.name,
                    'topic_name': subtopic.topic.name,
                    'status': 'success'
                })
                success += 1
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
            'model_used': generator.model_name,
            'embedding_details': details
        }
        log_result = log_embedding_generation('subtopics', 'all', log_data)

        return Response({
            'status': 'success',
            'message': f"Generated embeddings for {success} subtopics",
            'embedding_stats': {
                'total_subtopics': total,
                'already_embedded': already,
                'newly_embedded': success,
                'failed': failed,
                'model_used': generator.model_name
            },
            'json_log': log_result
        })
    except Exception as e:
        return Response({'status': 'error', 'message': f"Failed to generate subtopic embeddings: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
