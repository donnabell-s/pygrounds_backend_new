from rest_framework import serializers
from .models import GameSession, GameQuestion, Question, QuestionResponse


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'text', 'answer', 'difficulty']


class GameQuestionSerializer(serializers.ModelSerializer):
    question = QuestionSerializer()

    class Meta:
        model = GameQuestion
        fields = ['id', 'question']


class GameSessionSerializer(serializers.ModelSerializer):
    session_questions = GameQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = GameSession
        fields = ['session_id', 'game_type', 'status', 'start_time', 'end_time', 'total_score', 'time_limit', 'session_questions']


class QuestionResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionResponse
        fields = ['question', 'user_answer', 'is_correct', 'time_taken', 'answered_at']
