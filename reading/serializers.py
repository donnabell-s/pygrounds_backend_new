from rest_framework import serializers
from reading.models import Topic, Subtopic, ReadingMaterial


class ReadingMaterialSerializer(serializers.ModelSerializer):
    topic = serializers.CharField(source="topic_ref.name", read_only=True)
    topic_slug = serializers.SlugField(source="topic_ref.slug", read_only=True)
    subtopic = serializers.CharField(source="subtopic_ref.name", read_only=True)
    subtopic_slug = serializers.SlugField(source="subtopic_ref.slug", read_only=True)

    estimated_read_time = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ReadingMaterial
        fields = [
            "id",
            "title",
            "content",
            "topic_ref",
            "subtopic_ref", 
            "order_in_topic",
            "created_at",
            "updated_at",
            "topic",
            "topic_slug",
            "subtopic",
            "subtopic_slug",
            "estimated_read_time",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "topic",
            "topic_slug",
            "subtopic",
            "subtopic_slug",
            "estimated_read_time",
        ]

    def get_estimated_read_time(self, obj):
        text = obj.content or ""
        words = len(text.split())
        minutes = max(1, round(words / 200)) 
        return minutes

    def validate_title(self, v):
        if not v.strip():
            raise serializers.ValidationError("Title cannot be empty.")
        return v

    def validate_content(self, v):
        if not v or not v.strip():
            raise serializers.ValidationError("Content is required.")
        return v


class NeighborIdsSerializer(serializers.Serializer):
    prev_id = serializers.IntegerField(allow_null=True)
    next_id = serializers.IntegerField(allow_null=True)


class IdOnlySerializer(serializers.Serializer):
    id = serializers.IntegerField()


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ["id", "name", "slug"]


class SubtopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtopic
        fields = ["id", "name", "slug", "order_in_topic"]