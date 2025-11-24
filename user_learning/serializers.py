# user_learning/serializers.py
from rest_framework import serializers
from .models import UserZoneProgress, UserTopicProficiency, UserSubtopicMastery
from content_ingestion.models import GameZone, Topic, Subtopic


class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameZone
        fields = ['id', 'name', 'description', 'order']


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ['id', 'name', 'description', 'zone']


class SubtopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtopic
        fields = ['id', 'name', 'topic']


# class UserZoneProgressSerializer(serializers.ModelSerializer):
#     zone = ZoneSerializer()

#     class Meta:
#         model = UserZoneProgress
#         fields = ['zone', 'unlocked_at', 'completion_percent']  # ← updated


class UserZoneProgressSerializer(serializers.ModelSerializer):
    zone = ZoneSerializer()
    is_current = serializers.SerializerMethodField()
    locked = serializers.SerializerMethodField()

    class Meta:
        model = UserZoneProgress
        fields = ['zone', 'unlocked_at', 'completion_percent', 'is_current', 'locked']

    def get_is_current(self, obj):
        user = obj.user
        progresses = UserZoneProgress.objects.filter(user=user).order_by('zone__order')

        # Current zone = first zone with <100% completion
        for up in progresses:
            if up.completion_percent < 100:
                return up.id == obj.id

        # If all zones 100%, last zone is current
        return progresses.last().id == obj.id if progresses else False

    def get_locked(self, obj):
        user = obj.user
        progresses = UserZoneProgress.objects.filter(user=user).order_by('zone__order')

        # Find current zone index (first incomplete)
        current_idx = 0
        for idx, up in enumerate(progresses):
            if up.completion_percent < 100:
                current_idx = idx
                break
            else:
                current_idx = idx

        # Lock zones after the current
        return obj.zone.order > progresses[current_idx].zone.order


class UserTopicProficiencySerializer(serializers.ModelSerializer):
    topic = TopicSerializer()
    # ⬅️ Convenience field so each proficiency also has zone at the root
    zone = ZoneSerializer(source="topic.zone", read_only=True)

    class Meta:
        model = UserTopicProficiency
        fields = ["topic", "zone", "proficiency_percent"]


class UserSubtopicMasterySerializer(serializers.ModelSerializer):
    subtopic = SubtopicSerializer()

    class Meta:
        model = UserSubtopicMastery
        fields = ['subtopic', 'mastery_level']

class LeaderboardEntrySerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField(allow_null=True, required=False)
    last_name = serializers.CharField(allow_null=True, required=False)
    overall_completion = serializers.FloatField()
    # Each item: { zone_id, zone_name, zone_order, completion_percent }
    progresses = serializers.ListField(child=serializers.DictField())