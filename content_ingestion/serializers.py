from rest_framework import serializers
from .models import GameZone, Topic, Subtopic, ContentMapping, TOCEntry

class GameZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameZone
        fields = ['id', 'name', 'description', 'order', 'is_active', 
                 'required_exp', 'max_exp', 'is_unlocked']

class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ['id', 'zone', 'name', 'description', 'order', 
                 'min_zone_exp', 'is_unlocked']

class SubtopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtopic
        fields = ['id', 'topic', 'name', 'description', 'order',
                 'learning_objectives', 'difficulty_levels', 
                 'min_zone_exp', 'is_unlocked']

class ContentMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentMapping
        fields = ['id', 'toc_entry', 'zone', 'topic', 'subtopic',
                 'confidence_score', 'mapping_metadata']
        
    def validate(self, data):
        """
        Check that at least one of zone, topic, or subtopic is provided
        """
        if not any([data.get('zone'), data.get('topic'), data.get('subtopic')]):
            raise serializers.ValidationError(
                "At least one of zone, topic, or subtopic must be provided"
            )
        return data

class TOCEntryMappingSerializer(serializers.ModelSerializer):
    """
    Serializer for viewing TOC entries with their content mappings
    """
    content_mappings = ContentMappingSerializer(many=True, read_only=True)
    
    class Meta:
        model = TOCEntry
        fields = ['id', 'title', 'level', 'start_page', 'end_page',
                 'order', 'content_mappings']
