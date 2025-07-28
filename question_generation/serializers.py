# serializers.py
from rest_framework import serializers
from .models import PreAssessmentQuestion

class PreAssessmentQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreAssessmentQuestion
        fields = '__all__'
