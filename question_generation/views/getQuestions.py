# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..models import PreAssessmentQuestion
from ..serializers import PreAssessmentQuestionSerializer

class PreAssessmentQuestionListView(APIView):
    def get(self, request):
        questions = PreAssessmentQuestion.objects.all()
        serializer = PreAssessmentQuestionSerializer(questions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
