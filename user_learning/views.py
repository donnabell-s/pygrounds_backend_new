# user_learning/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import UserZoneProgress, UserTopicProficiency, UserSubtopicMastery
from .serializers import (
    UserZoneProgressSerializer,
    UserTopicProficiencySerializer,
    UserSubtopicMasterySerializer,
)


class MyZoneProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        progress = UserZoneProgress.objects.filter(user=request.user)
        return Response(UserZoneProgressSerializer(progress, many=True).data)


class MyTopicProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        progress = UserTopicProficiency.objects.filter(user=request.user)
        return Response(UserTopicProficiencySerializer(progress, many=True).data)


class MySubtopicStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        mastery = UserSubtopicMastery.objects.filter(user=request.user)
        return Response(UserSubtopicMasterySerializer(mastery, many=True).data)
