from rest_framework import serializers
from .models import GameSession, GameQuestion, Question, QuestionResponse
from question_generation.models import PreAssessmentQuestion
from question_generation.models import GeneratedQuestion

class LightweightQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedQuestion
        fields = ['id', 'question_text', 'correct_answer']

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedQuestion
        fields = [
            'id',
            'question_text',   # replaces 'text'
            'correct_answer',  # replaces 'answer'
            'game_type',
            # 'minigame_type',
            'game_data',       # contains function_name, sample_input/output, etc
        ]

class GameQuestionSerializer(serializers.ModelSerializer):
    question = QuestionSerializer()

    class Meta:
        model = GameQuestion
        fields = ['id', 'question', 'session']



class GameSessionSerializer(serializers.ModelSerializer):
    session_questions = GameQuestionSerializer(many=True, read_only=True)
    # For Hangman: compute remaining lives
    remaining_lives = serializers.SerializerMethodField()

    class Meta:
        model = GameSession
        fields = [
            'session_id',
            'game_type',
            'status',
            'start_time',
            'end_time',
            'total_score',
            'time_limit',
            'session_questions',
            'remaining_lives',
        ]

    def get_remaining_lives(self, obj):
        if obj.game_type != 'hangman':
            return None
        # Compute lives: 3 minus count of incorrect responses for first question
        # Assuming one GameQuestion per session for hangman
        game_q = obj.session_questions.first()
        if not game_q:
            return 3
        incorrect = QuestionResponse.objects.filter(
            question__session=obj,
            question=game_q,
            is_correct=False
        ).count()
        return max(0, 3 - incorrect)


class QuestionResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionResponse
        fields = [
            'question',
            'user_answer',
            'is_correct',
            'time_taken',
            'answered_at',
        ]

class PreAssessmentQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreAssessmentQuestion
        fields = '__all__'


class LeaderboardEntrySerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField(allow_blank=True, required=False)
    last_name = serializers.CharField(allow_blank=True, required=False)
    score = serializers.IntegerField()
    time_seconds = serializers.FloatField()
    session_id = serializers.CharField()
    played_at = serializers.DateTimeField()