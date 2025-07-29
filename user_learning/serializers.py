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
        fields = ['id', 'name', 'description', 'order', 'zone']


class SubtopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtopic
        fields = ['id', 'name', 'order', 'topic']


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
        """
        Mark the highest unlocked zone as current.
        """
        # Get all progresses for this user
        user_progress = (
            UserZoneProgress.objects.filter(user=obj.user)
            .order_by('zone__order')
        )

        # Find the last unlocked zone with >0%
        highest_unlocked = None
        for up in user_progress:
            if up.completion_percent > 0:
                highest_unlocked = up

        return highest_unlocked and highest_unlocked.zone_id == obj.zone_id

    def get_locked(self, obj):
        """
        Lock zones that are after the current highest unlocked zone.
        """
        # Find the highest unlocked zone
        highest_unlocked = (
            UserZoneProgress.objects
            .filter(user=obj.user, completion_percent__gt=0)
            .order_by('zone__order')
            .last()
        )

        if not highest_unlocked:
            return obj.zone.order > 1  # lock everything except first zone

        return obj.zone.order > highest_unlocked.zone.order



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
