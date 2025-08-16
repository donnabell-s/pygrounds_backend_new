from rest_framework import serializers
from .models import GameZone, Topic, Subtopic, TOCEntry, DocumentChunk, UploadedDocument

class DocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for UploadedDocument with metadata
    """
    chunks_count = serializers.SerializerMethodField()
    
    class Meta:
        model = UploadedDocument
        fields = [
            'id', 'title', 'file', 'processing_status', 
            'total_pages', 'uploaded_at', 'chunks_count'
        ]
        read_only_fields = ['uploaded_at']
    
    def get_chunks_count(self, obj):
        """Get count of associated chunks"""
        return DocumentChunk.objects.filter(document=obj).count()

class DocumentChunkSerializer(serializers.ModelSerializer):
    """
    Serializer for document chunks with token information
    """
    book_title = serializers.SerializerMethodField()
    
    class Meta:
        model = DocumentChunk
        fields = [
            'id', 'chunk_type', 'text', 'page_number', 'order_in_doc',
            'token_count'
        ]

class DocumentChunkSummarySerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for chunk summaries (without full text)
    """
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
        fields = ['id', 'name', 'description', 'order', 'is_unlocked', 'topics_count']
    
    def get_topics_count(self, obj):
        return obj.topics.count()

class TopicSerializer(serializers.ModelSerializer):
    zone_name = serializers.SerializerMethodField()
    subtopics_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Topic
        fields = ['id', 'zone', 'zone_name', 'name', 'description', 'subtopics_count']
    
    def get_zone_name(self, obj):
        return obj.zone.name
    
    def get_subtopics_count(self, obj):
        return obj.subtopics.count()

class SubtopicSerializer(serializers.ModelSerializer):
    topic_name = serializers.SerializerMethodField()
    zone_name = serializers.SerializerMethodField()
    has_embedding = serializers.SerializerMethodField()
    
    class Meta:
        model = Subtopic
        fields = ['id', 'topic', 'topic_name', 'zone_name', 'name', 'has_embedding']
    
    def get_topic_name(self, obj):
        return obj.topic.name
    
    def get_zone_name(self, obj):
        return obj.topic.zone.name
    
    def get_has_embedding(self, obj):
        return hasattr(obj, 'embeddings') and obj.embeddings.exists()

class TOCEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TOCEntry
        fields = ['id', 'title', 'level', 'start_page', 'end_page',
                 'order', 'topic_title', 'subtopic_title']
