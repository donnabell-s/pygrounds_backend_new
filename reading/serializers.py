from rest_framework import serializers
from content_ingestion.models import Topic, Subtopic
from reading.models import ReadingMaterial


class TopicAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ["id", "name", "slug", "description", "zone"]


class SubtopicAdminSerializer(serializers.ModelSerializer):
    topic_name = serializers.CharField(source="topic.name", read_only=True)

    class Meta:
        model = Subtopic
        fields = [
            "id",
            "name",
            "slug",
            "order_in_topic",
            "topic_ref",
            "topic_name",
            "concept_intent",
            "code_intent",
            "embedding_status",
            "embedding_error",
            "embedding_updated_at",
        ]


class AdminReadingMaterialSerializer(serializers.ModelSerializer):
    topic_name = serializers.CharField(source="topic_ref.name", read_only=True)
    subtopic_name = serializers.CharField(source="subtopic_ref.name", read_only=True)

    class Meta:
        model = ReadingMaterial
        fields = [
            "id",
            "title",
            "content",
            "topic_ref",       
            "topic_name",      
            "subtopic_ref",    
            "subtopic_name",   
            "order_in_topic",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "topic_ref": {"required": True},
            "subtopic_ref": {"required": True},
        }



class ReadingMaterialSerializer(serializers.ModelSerializer):
    topic_name = serializers.CharField(source="topic.name", read_only=True)
    subtopic_name = serializers.CharField(source="subtopic.name", read_only=True)

    class Meta:
        model = ReadingMaterial
        fields = [
            "id",
            "title",
            "content",
            "topic_ref",
            "topic_name",
            "subtopic_ref",
            "subtopic_name",
            "order_in_topic",
            "created_at",
            "updated_at",
        ]
