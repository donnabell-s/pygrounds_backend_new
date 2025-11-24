# user_learning/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from collections import defaultdict
from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated
from django.db.models import Max

from .models import UserZoneProgress
from .serializers import UserZoneProgressSerializer, LeaderboardEntrySerializer
from content_ingestion.models import GameZone

User = get_user_model()

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
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            progress = UserTopicProficiency.objects.filter(user=request.user).select_related('topic__zone')
            logger.info(f"Found {progress.count()} topic progress records for user {request.user.username}")
            
            # Check for any broken zone relationships
            valid_progress = []
            for p in progress:
                if p.topic and p.topic.zone:
                    valid_progress.append(p)
                else:
                    logger.warning(f"Skipping topic progress for topic {p.topic.name if p.topic else 'Unknown'} - missing zone")
            
            serializer = UserTopicProficiencySerializer(valid_progress, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error in MyTopicProgressView: {e}")
            return Response([], status=200)  # Return empty list instead of error


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

class AllLearnersZoneProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Pull all progresses for users with role='learner'
        qs = (
            UserZoneProgress.objects
            .select_related("user", "zone")
            .filter(user__role="learner")
            .order_by("user_id", "zone__order")
        )

        by_user = defaultdict(list)
        for up in qs:
            by_user[up.user].append(up)

        payload = []
        for user, progresses in by_user.items():
            prog_items = [{
                "zone_id": p.zone.id,
                "zone_name": getattr(p.zone, "name", str(p.zone)),
                "zone_order": getattr(p.zone, "order", None),
                "completion_percent": round(p.completion_percent, 2),
            } for p in progresses]

            overall = sum(p["completion_percent"] for p in prog_items) / (len(prog_items) or 1)

            payload.append({
                "user_id": user.id,
                "username": user.username,
                "first_name": getattr(user, "first_name", None),
                "last_name": getattr(user, "last_name", None),
                "overall_completion": round(overall, 2),
                "progresses": prog_items,
            })

        # Sort: highest overall first, then username
        payload.sort(key=lambda x: (-x["overall_completion"], x["username"] or ""))

        return Response(LeaderboardEntrySerializer(payload, many=True).data)