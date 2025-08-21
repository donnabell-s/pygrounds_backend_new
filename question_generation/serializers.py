from rest_framework import serializers
from django.contrib.auth.models import User
from .models import GeneratedQuestion, PreAssessmentQuestion
from content_ingestion.models import SemanticSubtopic  # Moved to content_ingestion
from content_ingestion.models import Topic, Subtopic


class TopicNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for Topic with zone information"""
    zone = serializers.SerializerMethodField()
    
    class Meta:
        model = Topic
        fields = ['id', 'name', 'zone']
    
    def get_zone(self, obj):
        return {
            'id': obj.zone.id,
            'name': obj.zone.name,
            'order': obj.zone.order
        }


class SubtopicNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for Subtopic"""
    topic = TopicNestedSerializer(read_only=True)
    
    class Meta:
        model = Subtopic
        fields = ['id', 'name', 'topic']


class GeneratedQuestionSerializer(serializers.ModelSerializer):
    topic = TopicNestedSerializer(read_only=True)
    subtopic = SubtopicNestedSerializer(read_only=True)
    topic_name = serializers.SerializerMethodField()
    subtopic_name = serializers.SerializerMethodField()
    zone_name = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = GeneratedQuestion
        fields = [
            'id', 'topic', 'subtopic', 'topic_name', 'subtopic_name', 'zone_name',
            'question_text', 'correct_answer', 'estimated_difficulty', 'game_type',
            'game_data', 'validation_status', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_topic_name(self, obj):
        return obj.topic.name
    
    def get_subtopic_name(self, obj):
        return obj.subtopic.name
    
    def get_zone_name(self, obj):
        return obj.topic.zone.name


class PreAssessmentQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreAssessmentQuestion
        fields = [
            'id', 'topic_ids', 'subtopic_ids', 'question_text', 'answer_options',
            'correct_answer', 'estimated_difficulty', 'order'
        ]
        read_only_fields = ['id']


class QuestionSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for question lists"""
    topic = TopicNestedSerializer(read_only=True)
    subtopic = SubtopicNestedSerializer(read_only=True)
    topic_name = serializers.SerializerMethodField()
    subtopic_name = serializers.SerializerMethodField()
    question_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = GeneratedQuestion
        fields = [
            'id', 'topic', 'subtopic', 'topic_name', 'subtopic_name', 'question_preview',
            'estimated_difficulty', 'game_type', 'validation_status'
        ]
    
    def get_topic_name(self, obj):
        return obj.topic.name
    
    def get_subtopic_name(self, obj):
        return obj.subtopic.name
    
    def get_question_preview(self, obj):
        return obj.question_text[:100] + "..." if len(obj.question_text) > 100 else obj.question_text


class SemanticSubtopicSerializer(serializers.ModelSerializer):
    subtopic_name = serializers.SerializerMethodField()
    topic_name = serializers.SerializerMethodField()
    chunks_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SemanticSubtopic
        fields = ['id', 'subtopic', 'subtopic_name', 'topic_name', 'ranked_concept_chunks', 'ranked_code_chunks', 'chunks_count', 'updated_at']
        read_only_fields = ['id', 'updated_at']
    
    def get_subtopic_name(self, obj):
        return obj.subtopic.name
    
    def get_topic_name(self, obj):
        return obj.subtopic.topic.name
    
    def get_chunks_count(self, obj):
        concept_count = len(obj.ranked_concept_chunks) if obj.ranked_concept_chunks else 0
        code_count = len(obj.ranked_code_chunks) if obj.ranked_code_chunks else 0
        return concept_count + code_count
