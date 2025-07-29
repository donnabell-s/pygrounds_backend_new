# user_learning/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Max

from .models import UserZoneProgress
from .serializers import UserZoneProgressSerializer
from content_ingestion.models import GameZone


class MyZoneProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        progress = UserZoneProgress.objects.filter(user=request.user).order_by('zone__order')
        return Response(UserZoneProgressSerializer(progress, many=True).data)


class MyTopicProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import UserTopicProficiency
        from .serializers import UserTopicProficiencySerializer
        progress = UserTopicProficiency.objects.filter(user=request.user)
        return Response(UserTopicProficiencySerializer(progress, many=True).data)


class MySubtopicStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import UserSubtopicMastery
        from .serializers import UserSubtopicMasterySerializer
        mastery = UserSubtopicMastery.objects.filter(user=request.user)
        return Response(UserSubtopicMasterySerializer(mastery, many=True).data)


class MyCurrentZoneView(APIView):
    """
    Returns the user's current active zone for gameplay.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Get all progress ordered by zone order
        progresses = (
            UserZoneProgress.objects
            .filter(user=user)
            .select_related('zone')
            .order_by('zone__order')
        )

        if not progresses.exists():
            # If no progress yet, start with the first zone
            first_zone = GameZone.objects.order_by('order').first()
            return Response({
                "current_zone_id": first_zone.id if first_zone else None,
                "current_zone_name": first_zone.name if first_zone else None,
                "completion_percent": 0,
            })

        # Determine current zone: highest unlocked
        current_zone = None
        for progress in progresses:
            if progress.completion_percent > 0:
                current_zone = progress

        # If all zones are 0%, stay at the first one
        if not current_zone:
            current_zone = progresses.first()

        return Response({
            "current_zone_id": current_zone.zone.id,
            "current_zone_name": current_zone.zone.name,
            "completion_percent": current_zone.completion_percent,
        })
