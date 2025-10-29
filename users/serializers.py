from rest_framework import serializers
from .models import User, LearnerProfile, AdminProfile
from django.contrib.auth.password_validation import validate_password
from user_learning.models import UserZoneProgress, UserTopicProficiency
from content_ingestion.models import GameZone, Topic
from django.db import models

class LearnerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearnerProfile
        fields = ['id']

class AdminProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminProfile
        fields = ['id']

class UserSerializer(serializers.ModelSerializer):
    learner_profile = LearnerProfileSerializer(read_only=True)
    admin_profile = AdminProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'role', 'learner_profile', 'admin_profile']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password', 'password2',)

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn’t match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user

class AdminUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'is_superuser', 'is_active', 'date_joined', 'password']
        read_only_fields = ['id', 'date_joined']

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        
        # Set admin privileges based on role
        if validated_data.get('role') == 'admin':
            user.is_staff = True
            user.is_superuser = True
        
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Set admin privileges based on role
        if validated_data.get('role') == 'admin':
            instance.is_staff = True
            instance.is_superuser = True
        elif validated_data.get('role') == 'learner':
            instance.is_staff = False
            instance.is_superuser = False
        
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameZone
        fields = ['id', 'name', 'description', 'order']


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ['id', 'name', 'description', 'zone']


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
    zone = ZoneSerializer(source="topic.zone", read_only=True)

    class Meta:
        model = UserTopicProficiency
        fields = ["topic", "zone", "proficiency_percent"]


class UserPublicProfileSerializer(serializers.ModelSerializer):
    """Serializer for viewing other users' profiles (public data only)"""
    zone_progresses = serializers.SerializerMethodField()
    topic_proficiencies = serializers.SerializerMethodField()
    overall_completion = serializers.SerializerMethodField()
    current_zone = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'zone_progresses', 'topic_proficiencies', 'overall_completion', 'current_zone']

    def get_zone_progresses(self, obj):
        progresses = UserZoneProgress.objects.filter(user=obj).select_related('zone').order_by('zone__order')
        return UserZoneProgressSerializer(progresses, many=True).data

    def get_topic_proficiencies(self, obj):
        proficiencies = UserTopicProficiency.objects.filter(user=obj).select_related('topic__zone').order_by('topic__zone__order', 'topic__name')
        return UserTopicProficiencySerializer(proficiencies, many=True).data

    def get_overall_completion(self, obj):
        progresses = UserZoneProgress.objects.filter(user=obj)
        if not progresses.exists():
            return 0.0
        return progresses.aggregate(avg_completion=models.Avg('completion_percent'))['avg_completion'] or 0.0

    def get_current_zone(self, obj):
        progresses = UserZoneProgress.objects.filter(user=obj).select_related('zone').order_by('zone__order')
        
        # Find first incomplete zone
        for progress in progresses:
            if progress.completion_percent < 100:
                return ZoneSerializer(progress.zone).data
        
        # If all complete, return last zone
        last_progress = progresses.last()
        return ZoneSerializer(last_progress.zone).data if last_progress else None