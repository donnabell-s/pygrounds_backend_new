# user_learning/serializers.py
from rest_framework import serializers
from .models import UserZoneProgress, UserTopicProficiency, UserSubtopicMastery
from content_ingestion.models import Zone, Topic, Subtopic


class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Zone
        fields = ['id', 'name', 'description', 'order']


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ['id', 'name', 'description', 'order', 'zone']


class SubtopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtopic
        fields = ['id', 'name', 'order', 'topic']


class UserZoneProgressSerializer(serializers.ModelSerializer):
    zone = ZoneSerializer()

    class Meta:
        model = UserZoneProgress
        fields = ['zone', 'unlocked_at', 'completion_percent']  # ← updated



class UserTopicProficiencySerializer(serializers.ModelSerializer):
    topic = TopicSerializer()

    class Meta:
        model = UserTopicProficiency
        fields = ['topic', 'proficiency_percent']


class UserSubtopicMasterySerializer(serializers.ModelSerializer):
    subtopic = SubtopicSerializer()

    class Meta:
        model = UserSubtopicMastery
        fields = ['subtopic', 'attempts', 'correct']
