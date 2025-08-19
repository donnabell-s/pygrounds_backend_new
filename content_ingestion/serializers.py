from rest_framework import serializers
from .models import GameZone, Topic, Subtopic, TOCEntry, DocumentChunk, UploadedDocument

class DocumentSerializer(serializers.ModelSerializer):
    # Serializer for UploadedDocument with metadata
    chunks_count = serializers.SerializerMethodField()
    
    class Meta:
        model = UploadedDocument
        fields = [
            'id', 'title', 'file', 'processing_status', 
            'processing_message', 'total_pages', 'uploaded_at', 
            'chunks_count', 'difficulty'
        ]
        read_only_fields = ['uploaded_at', 'title']  # Make title read-only since it's auto-generated
    
    def create(self, validated_data):
        """Create document and auto-generate title from filename"""
        import os
        
        # Extract title from filename if not provided
        if 'file' in validated_data and validated_data['file']:
            filename = validated_data['file'].name
            # Remove extension and clean up the name
            title = os.path.splitext(filename)[0]
            # Replace underscores and hyphens with spaces, capitalize
            title = title.replace('_', ' ').replace('-', ' ').title()
            validated_data['title'] = title
        
        return super().create(validated_data)
    
    def get_chunks_count(self, obj):
        # Get count of associated chunks
        return DocumentChunk.objects.filter(document=obj).count()

class DocumentChunkSerializer(serializers.ModelSerializer):
    # Serializer for document chunks with token information
    book_title = serializers.SerializerMethodField()
    
    class Meta:
        model = DocumentChunk
        fields = [
            'id', 'chunk_type', 'text', 'page_number', 'order_in_doc',
            'token_count'
        ]

class DocumentChunkSummarySerializer(serializers.ModelSerializer):
    # Lightweight serializer for chunk summaries (without full text)
    text_preview = serializers.SerializerMethodField()
    book_title = serializers.SerializerMethodField()
    
    class Meta:
        model = DocumentChunk
        fields = [
            'id', 'chunk_type', 'page_number', 'order_in_doc',
            'token_count', 'text_preview'
        ]
    
    def get_text_preview(self, obj):
        """Return first 100 characters of text"""
        return obj.text[:100] + "..." if len(obj.text) > 100 else obj.text

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
        fields = ['id', 'zone', 'zone_name', 'name', 'description', 'subtopics_count']
        read_only_fields = ['zone_name', 'subtopics_count']
    
    def get_zone_name(self, obj):
        return obj.zone.name if obj.zone else None
    
    def get_subtopics_count(self, obj):
        return obj.subtopics.count()
    
    def update(self, instance, validated_data):
        # Ensure zone exists if provided
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
            'id', 'topic', 'topic_name', 'zone_name', 'name',
            'concept_intent', 'code_intent', 'has_embedding',
            'embedding_status', 'embedding_error', 'embedding_updated_at'
        ]
        read_only_fields = [
            'topic_name', 'zone_name', 'has_embedding',
            'embedding_status', 'embedding_error', 'embedding_updated_at'
        ]
    
    def get_topic_name(self, obj):
        return obj.topic.name if obj.topic else None
    
    def get_zone_name(self, obj):
        return obj.topic.zone.name if obj.topic and obj.topic.zone else None
        
    def get_has_embedding(self, obj):
        # Check if either concept_intent or code_intent has an embedding
        return bool(obj.concept_embedding or obj.code_embedding)
        
    def update(self, instance, validated_data):
        # Ensure topic exists if provided
        if 'topic' in validated_data:
            try:
                Topic.objects.get(pk=validated_data['topic'].id)
            except Topic.DoesNotExist:
                raise serializers.ValidationError({'topic': 'Invalid topic ID provided.'})
        return super().update(instance, validated_data)
        return obj.topic.zone.name
    
    def get_has_embedding(self, obj):
        """Check if the object has embeddings, safely handling failed/pending states."""
        try:
            return hasattr(obj, 'embeddings') and obj.embeddings.exists()
        except Exception:
            return False
    
    def update(self, instance, validated_data):
        # Custom update to regenerate embeddings when intent fields change
        # Check if intent fields are being updated
        concept_intent_changed = (
            'concept_intent' in validated_data and 
            validated_data['concept_intent'] != instance.concept_intent
        )
        code_intent_changed = (
            'code_intent' in validated_data and 
            validated_data['code_intent'] != instance.code_intent
        )
        
        # Update the instance
        instance = super().update(instance, validated_data)
        
        # Regenerate embeddings if intent fields changed
        if concept_intent_changed or code_intent_changed:
            from django.core.cache import cache
            from multiprocessing import Pool
            import psutil
            import logging
            
            logger = logging.getLogger(__name__)
            cache_key = f'subtopic_embedding_status_{instance.id}'
            cache.set(cache_key, 'pending', timeout=3600)
            
            # Determine optimal number of processes
            cpu_count = psutil.cpu_count(logical=True)
            max_workers = min(2, max(1, cpu_count - 1))
            
            def generate_embedding(args):
                subtopic_id, model_type = args
                from content_ingestion.models import Subtopic
                from content_ingestion.helpers.embedding.generator import EmbeddingGenerator
                
                print(f"\n🔄 Generating {model_type} embedding for subtopic {subtopic_id}...")
                
                try:
                    # Get fresh instance to avoid process sharing issues
                    subtopic = Subtopic.objects.get(id=subtopic_id)
                    generator = EmbeddingGenerator()
                    
                    if model_type == 'concept':
                        text = f"{subtopic.topic.name} - {subtopic.name}: {subtopic.concept_intent}"
                        print(f"   📝 Processing concept text: {text[:100]}...")
                        result = generator.generate_embedding(text, chunk_type='Concept')
                    else:  # code
                        text = f"Python task: {subtopic.topic.name} - {subtopic.name}. Use: {subtopic.code_intent}"
                        print(f"   💻 Processing code text: {text[:100]}...")
                        result = generator.generate_embedding(text, chunk_type='Code')
                    
                    success = bool(result.get('vector'))
                    print(f"{'✅' if success else '❌'} {model_type.title()} embedding {'generated' if success else 'failed'}")
                    return model_type, result.get('vector')
                except Exception as e:
                    print(f"❌ Error generating {model_type} embedding: {str(e)}")
                    logger.error(f"Error generating {model_type} embedding for subtopic {subtopic_id}: {e}")
                    return model_type, None
            
            try:
                print("\n🧹 Cleaning up old embeddings...")
                # Clean up old embeddings
                from content_ingestion.models import Embedding
                Embedding.objects.filter(subtopic=instance).delete()
                
                # Prepare tasks for both embeddings
                tasks = [
                    (instance.id, 'concept'),
                    (instance.id, 'code')
                ]
                
                print("\n🚀 Starting parallel embedding generation...")
                # Execute tasks in parallel using the separate worker module
                from content_ingestion.embedding_worker import generate_embedding_task
                with Pool(processes=max_workers) as pool:
                    results = pool.map(generate_embedding_task, tasks)
                    
                print("\n📊 Processing embedding results...")
                # Process results
                vectors = dict(results)
                
                if any(vectors.values()):
                    Embedding.objects.create(
                        subtopic=instance,
                        content_type='subtopic',
                        model_type='dual',
                        model_name='dual:minilm+codebert',
                        dimension=384,
                        minilm_vector=vectors.get('concept'),
                        codebert_vector=vectors.get('code')
                    )
                    cache.set(cache_key, 'completed', timeout=3600)
                else:
                    cache.set(cache_key, 'failed: No embeddings generated', timeout=3600)
                    
            except Exception as e:
                logger.error(f"Failed to generate dual embeddings for subtopic {instance.id}: {e}")
                cache.set(cache_key, f'failed: {str(e)}', timeout=3600)
        
        return instance
    
    def create(self, validated_data):
        print("\n🔵 Starting subtopic creation process...")
        print(f"   Topic: {validated_data.get('topic').name}")
        print(f"   Name: {validated_data.get('name')}")
        
        # Custom create to generate dual embeddings for new subtopics with intent fields
        instance = super().create(validated_data)
        print(f"✅ Created subtopic with ID: {instance.id}")
        
        # Start pool-based embedding generation if intent fields are provided
        if instance.concept_intent or instance.code_intent:
            from multiprocessing import Pool
            import psutil
            import logging
            from django.db import transaction
            import threading
            
            logger = logging.getLogger(__name__)
            print("\n🔄 Starting embedding generation...")
            print(f"   Concept Intent: {'Yes' if instance.concept_intent else 'No'}")
            print(f"   Code Intent: {'Yes' if instance.code_intent else 'No'}")
            
            with transaction.atomic():
                instance.embedding_status = 'processing'
                instance.embedding_error = None
                instance.save()
                print("✅ Updated status to 'processing'")
            
            # Run embedding generation in a separate thread to avoid blocking the response
            def generate_embeddings_async():
                # Determine optimal number of processes
                cpu_count = psutil.cpu_count(logical=True)
                max_workers = min(2, max(1, cpu_count - 1))  # Use up to 2 processes, leave 1 CPU free
                
                try:
                    # Prepare tasks for both embeddings
                    tasks = [
                        (instance.id, 'concept'),
                        (instance.id, 'code')
                    ]
                    
                    print("\n🚀 Starting parallel embedding generation...")
                    # Execute tasks in parallel using the separate worker module
                    from content_ingestion.embedding_worker import generate_embedding_task
                    with Pool(processes=max_workers) as pool:
                        results = pool.map(generate_embedding_task, tasks)
                        
                    print("\n📊 Processing embedding results...")
                    # Process results
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
                        print("✅ Embeddings generated and saved successfully!")
                    else:
                        Subtopic.objects.filter(id=instance.id).update(
                            embedding_status='failed',
                            embedding_error='No embeddings were generated successfully'
                        )
                        print("❌ No embeddings were generated")
                        
                except Exception as e:
                    logger.error(f"Failed to generate dual embeddings for subtopic {instance.id}: {e}")
                    Subtopic.objects.filter(id=instance.id).update(
                        embedding_status='failed',
                        embedding_error=str(e)
                    )
                    print(f"❌ Embedding generation failed: {e}")
            
            # Start the embedding generation in a background thread
            threading.Thread(target=generate_embeddings_async, daemon=True).start()
            print("🎯 Embedding generation started in background thread")
        
        return instance
    
    async def _regenerate_dual_embeddings(self, subtopic):
        # Generate dual embeddings for the subtopic using intent-based content
        try:
            from content_ingestion.helpers.embedding.generator import EmbeddingGenerator
            
            # Create embedding generator
            embedding_gen = EmbeddingGenerator()
            
            # Generate embeddings for both intents
            await embedding_gen.generate_subtopic_dual_embeddings(subtopic)
            
        except Exception as e:
            # Log the error but don't fail the serializer operation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to generate dual embeddings for subtopic {subtopic.id}: {e}")
            raise e

class TOCEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TOCEntry
        fields = ['id', 'title', 'level', 'start_page', 'end_page',
                 'order', 'topic_title', 'subtopic_title']
