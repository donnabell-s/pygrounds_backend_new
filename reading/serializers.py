from django.utils.text import slugify
from rest_framework import serializers

from content_ingestion.models import Topic as CITopic, Subtopic as CISubtopic
from reading.models import ReadingMaterial



class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = CITopic
        fields = ["id", "name", "slug"]


class SubtopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = CISubtopic
        fields = ["id", "name", "slug", "order_in_topic"]

class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ["id", "name", "slug"]


class SubtopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtopic
        fields = ["id", "name", "slug", "order_in_topic"]
<<<<<<< Updated upstream

class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ["id", "name", "slug"]


class SubtopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtopic
        fields = ["id", "name", "slug", "order_in_topic"]
=======
>>>>>>> Stashed changes


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
            "id", "created_at", "updated_at",
            "topic", "topic_slug", "subtopic", "subtopic_slug",
            "estimated_read_time",
        ]

    def get_estimated_read_time(self, obj):
        words = len((obj.content or "").split())
        return max(1, round(words / 200))

    def validate_title(self, v):
        if not v or not v.strip():
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

class TopicAdminSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(required=False, allow_blank=True, default="")

<<<<<<< Updated upstream
<<<<<<< Updated upstream
=======
=======
>>>>>>> Stashed changes
<<<<<<< HEAD


class TopicAdminSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(required=False, allow_blank=True)

=======
>>>>>>> origin/merge-read/recalib-wip
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
    class Meta:
        model = CITopic
        fields = ["id", "name", "slug"]

    def validate(self, attrs):
        name = (attrs.get("name") or getattr(self.instance, "name", "") or "").strip()
        if not name:
            raise serializers.ValidationError({"name": "Name is required."})
<<<<<<< Updated upstream
<<<<<<< Updated upstream
=======
=======
>>>>>>> Stashed changes
<<<<<<< HEAD

        s = slugify(attrs.get("slug") or name)

        qs = CITopic.objects.all()
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

=======
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
        s = slugify(attrs.get("slug") or name)

        qs = Topic.objects.all()
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
<<<<<<< Updated upstream
<<<<<<< Updated upstream
=======
>>>>>>> origin/merge-read/recalib-wip
>>>>>>> Stashed changes
=======
>>>>>>> origin/merge-read/recalib-wip
>>>>>>> Stashed changes
        if qs.filter(name__iexact=name).exists():
            raise serializers.ValidationError({"name": "A topic with this name already exists."})
        if qs.filter(slug__iexact=s).exists():
            raise serializers.ValidationError({"slug": "Slug already exists."})

        attrs["name"] = name
        attrs["slug"] = s
        return attrs


class SubtopicAdminSerializer(serializers.ModelSerializer):
<<<<<<< Updated upstream
<<<<<<< Updated upstream
=======
=======
>>>>>>> Stashed changes
<<<<<<< HEAD
    topic = serializers.PrimaryKeyRelatedField(queryset=CITopic.objects.all())
    slug = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = CISubtopic
        fields = ["id", "name", "slug", "order_in_topic", "topic"]
        extra_kwargs = { "slug": {"required": False, "allow_blank": True} }
=======
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
    topic = serializers.PrimaryKeyRelatedField(queryset=Topic.objects.all())
    slug = serializers.CharField(required=False, allow_blank=True, default="")

    class Meta:
        model = Subtopic
        fields = ["id", "name", "slug", "order_in_topic", "topic"]
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True, "default": ""},
        }
<<<<<<< Updated upstream
<<<<<<< Updated upstream
=======
>>>>>>> origin/merge-read/recalib-wip
>>>>>>> Stashed changes
=======
>>>>>>> origin/merge-read/recalib-wip
>>>>>>> Stashed changes

    def validate(self, attrs):
        topic = attrs.get("topic") or getattr(self.instance, "topic", None)
        name = (attrs.get("name") or getattr(self.instance, "name", "") or "").strip()
        if not name:
            raise serializers.ValidationError({"name": "Name is required."})
        if topic is None:
            raise serializers.ValidationError({"topic": "Topic is required."})

        s = slugify(attrs.get("slug") or name)

<<<<<<< Updated upstream
<<<<<<< Updated upstream
        qs = Subtopic.objects.filter(topic=topic, slug__iexact=s)
=======
=======
>>>>>>> Stashed changes
<<<<<<< HEAD
        qs = CISubtopic.objects.filter(topic=topic, slug__iexact=s)
=======
        qs = Subtopic.objects.filter(topic=topic, slug__iexact=s)
>>>>>>> origin/merge-read/recalib-wip
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({
                "slug": "A subtopic with this slug already exists for the selected topic."
            })

        attrs["name"] = name
        attrs["slug"] = s
        return attrs


class AdminReadingMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingMaterial
        fields = [
            "id", "title", "content",
            "topic_ref", "subtopic_ref", "order_in_topic",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        topic = attrs.get("topic_ref") or (self.instance.topic_ref if self.instance else None)
        subtopic = attrs.get("subtopic_ref") or (self.instance.subtopic_ref if self.instance else None)
        if subtopic and topic and subtopic.topic_id != topic.id:
            raise serializers.ValidationError({"subtopic_ref": "Subtopic does not belong to the selected topic."})
        return attrs
