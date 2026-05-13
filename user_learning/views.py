# user_learning/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from collections import defaultdict
from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated
from django.db.models import Max

from .models import UserZoneProgress, UserTopicProficiency, UserTopicProficiencyHistory
from .serializers import UserZoneProgressSerializer, LeaderboardEntrySerializer, TopicProficiencyHistorySerializer
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
        from content_ingestion.models import Topic
        import logging
        logger = logging.getLogger(__name__)

        try:
            # All topics that have at least one subtopic, ordered by zone order then topic id
            qualifying_topics = (
                Topic.objects
                .filter(subtopics__isnull=False)
                .select_related('zone')
                .distinct()
                .order_by('zone__order', 'id')
            )

            # Existing proficiency records keyed by topic id
            existing = {
                p.topic_id: p.proficiency_percent
                for p in UserTopicProficiency.objects.filter(user=request.user)
            }

            data = []
            for topic in qualifying_topics:
                if not topic.zone:
                    continue
                zone_data = {
                    "id": topic.zone.id,
                    "name": topic.zone.name,
                    "description": topic.zone.description,
                    "order": topic.zone.order,
                }
                data.append({
                    "topic": {
                        "id": topic.id,
                        "name": topic.name,
                        "description": topic.description,
                        "zone": zone_data,
                    },
                    "zone": zone_data,
                    "proficiency_percent": existing.get(topic.id, 0.0),
                })

            return Response(data)

        except Exception as e:
            logger.error(f"Error in MyTopicProgressView: {e}")
            return Response([], status=200)


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


class TopicProficiencyHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Optional ?user_id= to view another user's history (admin-only)
        user_id = request.query_params.get("user_id")
        if user_id:
            if str(request.user.id) != str(user_id) and getattr(request.user, "role", None) != "admin":
                return Response({"detail": "Not allowed."}, status=403)
            target_user = User.objects.filter(pk=user_id).first()
            if not target_user:
                return Response([], status=200)
        else:
            target_user = request.user

        # Bootstrap: if no history exists yet, seed from current proficiency records
        if not UserTopicProficiencyHistory.objects.filter(user=target_user).exists():
            current = UserTopicProficiency.objects.filter(user=target_user).select_related('topic')
            if current.exists():
                UserTopicProficiencyHistory.objects.bulk_create([
                    UserTopicProficiencyHistory(
                        user=target_user,
                        topic=p.topic,
                        proficiency_percent=p.proficiency_percent,
                    )
                    for p in current
                ])

        history = (
            UserTopicProficiencyHistory.objects
            .filter(user=target_user)
            .select_related('topic')
            .order_by('recorded_at')
        )
        return Response(TopicProficiencyHistorySerializer(history, many=True).data)