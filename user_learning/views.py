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
    Returns the user's current active zone with full details, using sequential logic:
    - Current zone = first zone with completion < 100%
    - If all zones 100%, last zone is current
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        progresses = (
            UserZoneProgress.objects
            .filter(user=user)
            .select_related('zone')
            .order_by('zone__order')
        )

        # If no zones exist yet, create first zone progress at 0%
        if not progresses.exists():
            first_zone = GameZone.objects.order_by('order').first()
            if not first_zone:
                return Response([])  # No zones exist

            progress = UserZoneProgress.objects.create(
                user=user,
                zone=first_zone,
                completion_percent=0.0,
            )
            from .serializers import UserZoneProgressSerializer
            return Response([UserZoneProgressSerializer(progress).data])

        # Sequential logic: first incomplete zone is current
        current_progress = None
        for progress in progresses:
            if progress.completion_percent < 100:
                current_progress = progress
                break

        # If all zones 100%, current = last zone
        if current_progress is None:
            current_progress = progresses.last()

        from .serializers import UserZoneProgressSerializer
        data = UserZoneProgressSerializer(current_progress).data
        return Response([data])
