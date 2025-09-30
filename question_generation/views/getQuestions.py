# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..models import PreAssessmentQuestion
from ..serializers import PreAssessmentQuestionSerializer

class PreAssessmentQuestionListView(APIView):
    def get(self, request):
        questions = PreAssessmentQuestion.objects.all().order_by('order')  # Sort by order smallest to largest
        serializer = PreAssessmentQuestionSerializer(questions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
