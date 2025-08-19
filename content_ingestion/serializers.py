from rest_framework import serializers
from .models import GameZone, Topic, Subtopic, TOCEntry, DocumentChunk

class DocumentChunkSerializer(serializers.ModelSerializer):
    """
    Serializer for document chunks with token information
    """
    class Meta:
        model = DocumentChunk
        fields = [
            'id', 'chunk_type', 'text', 'page_number', 'order_in_doc',
            'topic_title', 'subtopic_title', 'token_count', 'token_encoding',
            'confidence_score', 'parser_metadata', 'embedded_at'
        ]

class DocumentChunkSummarySerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for chunk summaries (without full text)
    """
    text_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = DocumentChunk
        fields = [
            'id', 'chunk_type', 'page_number', 'order_in_doc',
            'topic_title', 'subtopic_title', 'token_count', 'token_encoding',
            'text_preview'
        ]
    
    def get_text_preview(self, obj):
        """Return first 100 characters of text"""
        return obj.text[:100] + "..." if len(obj.text) > 100 else obj.text

class GameZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameZone
        fields = ['id', 'name', 'description', 'order']

class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ['id', 'zone', 'name', 'description']

class SubtopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtopic
        fields = ['id', 'topic', 'name', 'order']

class TOCEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TOCEntry
        fields = ['id', 'title', 'level', 'start_page', 'end_page',
                 'order', 'topic_title', 'subtopic_title']
