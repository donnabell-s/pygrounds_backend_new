from rest_framework import serializers
from .models import GameZone, Topic, Subtopic, TOCEntry, DocumentChunk, UploadedDocument

class DocumentSerializer(serializers.ModelSerializer):
    # serializer for uploaded document with metadata
    chunks_count = serializers.SerializerMethodField()
    
    class Meta:
        model = UploadedDocument
        fields = [
            'id', 'title', 'file', 'processing_status', 
            'processing_message', 'total_pages', 'uploaded_at', 
            'chunks_count', 'difficulty'
        ]
        read_only_fields = ['uploaded_at', 'title']  # title is auto-generated
    
    def create(self, validated_data):
        # auto-generate title from uploaded filename
        import os
        
        # extract title from filename if not provided
        if 'file' in validated_data and validated_data['file']:
            filename = validated_data['file'].name
            # remove extension and clean up the name
            title = os.path.splitext(filename)[0]
            # replace underscores and hyphens with spaces
            title = title.replace('_', ' ').replace('-', ' ').title()
            validated_data['title'] = title
        
        return super().create(validated_data)
    
    def get_chunks_count(self, obj):
        # count associated chunks
        return DocumentChunk.objects.filter(document=obj).count()

class DocumentChunkSerializer(serializers.ModelSerializer):
    # serializer for document chunks with token information
    book_title = serializers.SerializerMethodField()
    text_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = DocumentChunk
        fields = [
            'id', 'chunk_type', 'text', 'page_number', 'order_in_doc',
            'token_count', 'text_preview', 'book_title'
        ]
    
    def get_book_title(self, obj):
        return obj.document.title if obj.document else None
    
    def get_text_preview(self, obj):
        # return first 100 characters
        return obj.text[:100] + "..." if len(obj.text) > 100 else obj.text

class DocumentChunkSummarySerializer(serializers.ModelSerializer):
    # lightweight serializer for chunk summaries (without full text)
    book_title = serializers.SerializerMethodField()
    
    class Meta:
        model = DocumentChunk
        fields = [
            'id', 'chunk_type', 'page_number', 'order_in_doc',
            'token_count', 'text_preview', 'book_title'
        ]
    
    def get_text_preview(self, obj):
        # return first 100 characters
        return obj.text[:100] + "..." if len(obj.text) > 100 else obj.text
    
    def get_book_title(self, obj):
        return obj.document.title if obj.document else None

class GameZoneSerializer(serializers.ModelSerializer):
    topics_count = serializers.SerializerMethodField()
    
    class Meta:
        model = GameZone
        fields = ['id', 'name', 'description', 'order', 'topics_count']
    
    def get_topics_count(self, obj):
        return obj.topics.count()

class TopicSerializer(serializers.ModelSerializer):
    zone_name = serializers.SerializerMethodField()
    subtopics_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Topic
        fields = ['id', 'zone', 'zone_name', 'name', 'slug', 'description', 'subtopics_count']
        read_only_fields = ['zone_name', 'subtopics_count', 'slug']  # slug is auto-generated
    
    def get_zone_name(self, obj):
        return obj.zone.name if obj.zone else None
    
    def get_subtopics_count(self, obj):
        return obj.subtopics.count()
    
    def update(self, instance, validated_data):
        # ensure zone exists if provided
        if 'zone' in validated_data:
            try:
                GameZone.objects.get(pk=validated_data['zone'].id)
            except GameZone.DoesNotExist:
                raise serializers.ValidationError({'zone': 'Invalid zone ID provided.'})
        return super().update(instance, validated_data)


class SubtopicSerializer(serializers.ModelSerializer):
    topic_name = serializers.SerializerMethodField()
    zone_name = serializers.SerializerMethodField()
    has_embedding = serializers.SerializerMethodField()
    
    class Meta:
        model = Subtopic
        fields = [
            'id', 'topic', 'topic_name', 'zone_name', 'name', 'slug', 'order_in_topic',
            'concept_intent', 'code_intent', 'has_embedding',
            'embedding_status', 'embedding_error', 'embedding_updated_at'
        ]
        read_only_fields = [
            'topic_name', 'zone_name', 'has_embedding', 'slug',  # slug is auto-generated
            'embedding_status', 'embedding_error', 'embedding_updated_at'
        ]
    
    def get_topic_name(self, obj):
        return obj.topic.name if obj.topic else None
    
    def get_zone_name(self, obj):
        return obj.topic.zone.name if obj.topic and obj.topic.zone else None
        
    def get_has_embedding(self, obj):
        # Check embedding presence.
        try:
            return hasattr(obj, 'embeddings') and obj.embeddings.exists()
        except Exception:
            return False
        
    def update(self, instance, validated_data):
        # ensure topic exists if provided
        if 'topic' in validated_data:
            try:
                Topic.objects.get(pk=validated_data['topic'].id)
            except Topic.DoesNotExist:
                raise serializers.ValidationError({'topic': 'Invalid topic ID provided.'})
        # track whether intent fields changed
        concept_intent_changed = (
            'concept_intent' in validated_data and 
            validated_data['concept_intent'] != instance.concept_intent
        )
        code_intent_changed = (
            'code_intent' in validated_data and 
            validated_data['code_intent'] != instance.code_intent
        )
        
        # update instance
        instance = super().update(instance, validated_data)
        
        # signal handles embedding regeneration when intent fields change
        
        return instance
    
    def create(self, validated_data):
        print("\n Starting subtopic creation process...")
        print(f"   Topic: {validated_data.get('topic').name}")
        print(f"   Name: {validated_data.get('name')}")
        
        # custom create: generate dual embeddings for new subtopics with intent fields
        instance = super().create(validated_data)
        print(f" Created subtopic with ID: {instance.id}")
        
        # start pool-based embedding generation when intent fields exist
        if instance.concept_intent or instance.code_intent:
            from multiprocessing import Pool
            import psutil
            import logging
            from django.db import transaction
            import threading
            
            logger = logging.getLogger(__name__)
            print("\n Starting embedding generation...")
            print(f"   Concept Intent: {'Yes' if instance.concept_intent else 'No'}")
            print(f"   Code Intent: {'Yes' if instance.code_intent else 'No'}")
            
            with transaction.atomic():
                instance.embedding_status = 'processing'
                instance.embedding_error = None
                instance.save()
                print(" Updated status to 'processing'")
            
            # run embedding generation in a separate thread to avoid blocking the response
            def generate_embeddings_async():
                # determine worker count (cap at 2)
                cpu_count = psutil.cpu_count(logical=True)
                max_workers = min(2, max(1, cpu_count - 1))  # Use up to 2 processes, leave 1 CPU free
                
                try:
                    # run both embeddings in parallel
                    tasks = [
                        (instance.id, 'concept'),
                        (instance.id, 'code')
                    ]
                    
                    print("\n Starting parallel embedding generation...")
                    # execute tasks in parallel using the worker module
                    from content_ingestion.helpers.workers.embedding_worker import generate_embedding_task
                    with Pool(processes=max_workers) as pool:
                        results = pool.map(generate_embedding_task, tasks)
                        
                    print("\n Processing embedding results...")
                    # process results
                    vectors = dict(results)
                    
                    if any(vectors.values()):  # If at least one embedding was generated
                        from content_ingestion.models import Embedding, Subtopic
                        Embedding.objects.create(
                            subtopic=instance,
                            content_type='subtopic',
                            model_type='dual',
                            model_name='dual:minilm+codebert',
                            dimension=384,  # Standard dimension for these models
                            minilm_vector=vectors.get('concept'),
                            codebert_vector=vectors.get('code')
                        )
                        # Update status in a fresh instance to avoid race conditions
                        Subtopic.objects.filter(id=instance.id).update(
                            embedding_status='completed',
                            embedding_error=None
                        )
                        print(" Embeddings generated and saved successfully!")
                    else:
                        Subtopic.objects.filter(id=instance.id).update(
                            embedding_status='failed',
                            embedding_error='No embeddings were generated successfully'
                        )
                        print(" No embeddings were generated")
                        
                except Exception as e:
                    logger.error(f"Failed to generate dual embeddings for subtopic {instance.id}: {e}")
                    Subtopic.objects.filter(id=instance.id).update(
                        embedding_status='failed',
                        embedding_error=str(e)
                    )
                    print(f" Embedding generation failed: {e}")
            
            # start embedding generation in background thread
            threading.Thread(target=generate_embeddings_async, daemon=True).start()
            print(" Embedding generation started in background thread")
        
        return instance
    
    async def _regenerate_dual_embeddings(self, subtopic):
        # generate dual embeddings using intent-based content
        try:
            from content_ingestion.helpers.embedding.generator import EmbeddingGenerator
            
            # create embedding generator
            embedding_gen = EmbeddingGenerator()
            
            # generate embeddings for both intents
            await embedding_gen.generate_subtopic_dual_embeddings(subtopic)
            
        except Exception as e:
            # log error but don't fail the serializer operation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to generate dual embeddings for subtopic {subtopic.id}: {e}")
            raise e

class TOCEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TOCEntry
        fields = ['id', 'title', 'level', 'start_page', 'end_page',
                 'order', 'topic_title', 'subtopic_title']
