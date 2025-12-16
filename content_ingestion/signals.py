# content ingestion signals
# automatic processing when models are saved

import logging
from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from .models import Subtopic, SemanticSubtopic

logger = logging.getLogger(__name__)

# global dictionary to track field changes
_subtopic_field_tracker = {}

@receiver(pre_delete, sender=Subtopic)
def handle_subtopic_deletion(sender, instance, **kwargs):
    # log cascade-deleted related objects for a subtopic
    logger.info(f" Deleting subtopic '{instance.name}' (ID: {instance.pk})")
    
    # log what will be deleted via cascade
    try:
        from content_ingestion.models import Embedding
        from question_generation.models import GeneratedQuestion
        
        # count related objects that will be cascade deleted
        embeddings_count = Embedding.objects.filter(subtopic=instance).count()
        questions_count = GeneratedQuestion.objects.filter(subtopic=instance).count()
        
        logger.info(f"  - Will cascade delete {embeddings_count} embeddings")
        logger.info(f"  - Will cascade delete {questions_count} generated questions")
        
        # check for semantic subtopic
        try:
            semantic_subtopic = SemanticSubtopic.objects.get(subtopic=instance)
            logger.info(f"  - Will cascade delete SemanticSubtopic record")
        except SemanticSubtopic.DoesNotExist:
            logger.info(f"  - No SemanticSubtopic record to delete")
            
        # check user learning data
        try:
            from user_learning.models import SubtopicMastery
            mastery_count = SubtopicMastery.objects.filter(subtopic=instance).count()
            logger.info(f"  - Will cascade delete {mastery_count} user mastery records")
        except ImportError:
            pass  # user_learning app might not be available
            
        # check reading materials
        try:
            from reading.models import ReadingMaterial
            reading_count = ReadingMaterial.objects.filter(subtopic_ref=instance).count()
            logger.info(f"  - Will cascade delete {reading_count} reading materials")
        except ImportError:
            pass  # reading app might not be available
            
    except Exception as e:
        logger.warning(f"Error counting related objects for subtopic deletion: {e}")
    
    logger.info(f" All related objects will be automatically cascade deleted by Django")


@receiver(pre_save, sender=Subtopic)
def track_subtopic_changes(sender, instance, **kwargs):
    # track field changes to decide whether to regenerate embeddings
    if instance.pk:  # only track for existing objects (updates)
        try:
            old_instance = Subtopic.objects.get(pk=instance.pk)
            _subtopic_field_tracker[instance.pk] = {
                'name_changed': old_instance.name != instance.name,
                'concept_intent_changed': old_instance.concept_intent != instance.concept_intent,
                'code_intent_changed': old_instance.code_intent != instance.code_intent,
                'old_concept_intent': old_instance.concept_intent,
                'old_code_intent': old_instance.code_intent,
            }
            logger.info(f"Tracking changes for subtopic '{instance.name}' (ID: {instance.pk})")
            logger.info(f"  - Name changed: {_subtopic_field_tracker[instance.pk]['name_changed']}")
            logger.info(f"  - Concept intent changed: {_subtopic_field_tracker[instance.pk]['concept_intent_changed']}")
            logger.info(f"  - Code intent changed: {_subtopic_field_tracker[instance.pk]['code_intent_changed']}")
        except Subtopic.DoesNotExist:
            # object doesn't exist yet, this is a creation
            _subtopic_field_tracker[instance.pk] = None


@receiver(post_save, sender=Subtopic)
def handle_subtopic_save(sender, instance, created, **kwargs):
    # regenerate embeddings on create or relevant field changes
    try:
        logger.info(f"Signal triggered for subtopic '{instance.name}' (created: {created})")
        logger.info(f"Intent fields - concept: {bool(instance.concept_intent)}, code: {bool(instance.code_intent)}")

        # determine whether to regenerate embeddings
        should_generate = False
        
        if created:
            # always generate for new subtopics (name is always descriptive)
            should_generate = True
            logger.info(f"Processing newly created subtopic '{instance.name}' - will generate embeddings from name")
        else:
            # for updates, check whether relevant fields changed
            changes = _subtopic_field_tracker.get(instance.pk)
            if changes:
                field_changed = (
                    changes['name_changed'] or 
                    changes['concept_intent_changed'] or 
                    changes['code_intent_changed']
                )
                should_generate = field_changed
                
                if field_changed:
                    logger.info(f"Relevant fields changed for subtopic '{instance.name}' - will regenerate embeddings")
                    logger.info(f"  - Name: {changes['name_changed']}")
                    logger.info(f"  - Concept intent: {changes['concept_intent_changed']}")
                    logger.info(f"  - Code intent: {changes['code_intent_changed']}")
                else:
                    logger.info(f"No relevant field changes for subtopic '{instance.name}' - skipping embedding regeneration")
            else:
                # no tracking data, assume we should generate (safe fallback)
                should_generate = True
                logger.info(f"No change tracking data for subtopic '{instance.name}' - will generate embeddings")

        # clean up tracker
        if instance.pk in _subtopic_field_tracker:
            del _subtopic_field_tracker[instance.pk]

        if not should_generate:
            logger.info(f"Skipping embedding generation for subtopic '{instance.name}'")
            return

        logger.info(f"Processing embeddings and semantic similarities for subtopic '{instance.name}'")

        # check if subtopic has embeddings
        from content_ingestion.models import Embedding
        has_embeddings = Embedding.objects.filter(subtopic=instance).exists()
        
        # always generate dual embeddings (minilm + codebert)
        logger.info(f"Generating dual embeddings for subtopic '{instance.name}'")
        
        # determine what content we're using for embedding messages
        embedding_sources = ['name']  # Always include name
        if instance.concept_intent:
            embedding_sources.append('concept_intent')
        if instance.code_intent:
            embedding_sources.append('code_intent')
        
        source_description = ' + '.join(embedding_sources)
        
        # update status to processing with descriptive message
        Subtopic.objects.filter(pk=instance.pk).update(
            embedding_status='processing',
            embedding_error=f'Generating dual embeddings (MiniLM + CodeBERT) from {source_description} for: {instance.name}'
        )
        logger.info(f" Status updated: Processing dual embeddings from {source_description}")
        
        # generate and save embeddings using the proper database-saving method
        from content_ingestion.helpers.embedding.generator import EmbeddingGenerator
        
        # clean up old embeddings if they exist
        if has_embeddings:
            from content_ingestion.models import Embedding
            Embedding.objects.filter(subtopic=instance).delete()
            logger.info(f" Cleaned up old embeddings for subtopic '{instance.name}'")
        
        try:
            logger.info(f" Starting dual embedding generation from: {source_description}")
            
            # small delay to ensure status is visible in frontend
            import time
            time.sleep(0.5)  # 500ms delay to make processing status visible
            
            generator = EmbeddingGenerator()
            result = generator.generate_subtopic_dual_embeddings(instance)
            
            if result['embeddings_created'] > 0:
                success_msg = f"Generated {result['embeddings_created']} dual embeddings from {source_description}"
                Subtopic.objects.filter(pk=instance.pk).update(
                    embedding_status='completed',
                    embedding_error=None
                )
                logger.info(f" {success_msg} for subtopic '{instance.name}'")
                # continue to semantic processing below
            else:
                error_msg = '; '.join(result['errors']) if result['errors'] else 'No embeddings were created'
                Subtopic.objects.filter(pk=instance.pk).update(
                    embedding_status='failed',
                    embedding_error=f"Failed: {error_msg}"
                )
                logger.error(f" Failed to generate embeddings for subtopic '{instance.name}': {error_msg}")
                return
                    
        except Exception as e:
            error_msg = f"Exception during embedding generation: {str(e)}"
            logger.error(f" Error generating embeddings for subtopic '{instance.name}': {e}")
            Subtopic.objects.filter(pk=instance.pk).update(
                embedding_status='failed',
                embedding_error=error_msg
            )
            return

        # ensure semantic subtopic record exists (even without chunks)
        semantic_subtopic, semantic_created = SemanticSubtopic.objects.get_or_create(
            subtopic=instance,
            defaults={
                'ranked_concept_chunks': [],
                'ranked_code_chunks': []
            }
        )
        
        if semantic_created:
            logger.info(f"Created SemanticSubtopic record for '{instance.name}'")

        # check if there are any document chunks with embeddings before processing
        from .models import DocumentChunk
        chunks_with_embeddings = DocumentChunk.objects.filter(embeddings__isnull=False).exists()
        if not chunks_with_embeddings:
            logger.info(f" No document chunks with embeddings yet - SemanticSubtopic record exists but rankings remain empty for '{instance.name}'")
            # update status to completed since embedding generation is done and semantic record exists
            Subtopic.objects.filter(pk=instance.pk).update(
                embedding_status='completed',
                embedding_error=None
            )
            logger.info(f" Subtopic '{instance.name}' processing completed (no chunks to rank)")
            return

        # update status for semantic processing
        Subtopic.objects.filter(pk=instance.pk).update(
            embedding_status='processing',
            embedding_error='Processing semantic similarities with document chunks'
        )
        logger.info(f" Starting semantic similarity processing for '{instance.name}'")

        # lazy import to avoid sklearn loading during django setup
        from .helpers.semantic_similarity import process_single_subtopic

        # process semantic similarities for this subtopic
        result = process_single_subtopic(
            subtopic_id=instance.id,
            similarity_threshold=0.1,
            top_k_results=15  # Match the RAG system's top_k
        )

        logger.info(f" Semantic processing result for subtopic '{instance.name}': {result}")

        if result.get('status') == 'success':
            # update status to completed with success message
            similar_chunks = result.get('similar_chunks', 0)
            Subtopic.objects.filter(pk=instance.pk).update(
                embedding_status='completed',
                embedding_error=None
            )
            logger.info(f" Successfully processed semantic similarities for subtopic '{instance.name}' - found {similar_chunks} related chunks")
        else:
            # update status to failed with error message
            error_msg = f"Semantic processing failed: {result.get('message', 'Unknown error')}"
            Subtopic.objects.filter(pk=instance.pk).update(
                embedding_status='failed',
                embedding_error=error_msg
            )
            logger.error(f" Failed to process semantic similarities for subtopic '{instance.name}': {result.get('message')}")

    except Exception as e:
        logger.error(f" Error in subtopic save signal for '{instance.name}': {str(e)}")
        # update status to failed with exception message
        Subtopic.objects.filter(pk=instance.pk).update(
            embedding_status='failed',
            embedding_error=f"Signal processing error: {str(e)}"
        )