from rest_framework import viewsets, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models.functions import Coalesce
from django.db.models import IntegerField, Value

from reading.models import ReadingMaterial
from .serializers import ReadingMaterialSerializer


class ReadingMaterialViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public read-only endpoint for Reading Materials.
    Supports filter by topic/subtopic, search (title/content), and ordering.
    """
    queryset = ReadingMaterial.objects.all().order_by("topic", "subtopic", "title")
    serializer_class = ReadingMaterialSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    filterset_fields = ["topic", "subtopic"]
    search_fields = ["title", "content"]
    ordering_fields = ["title", "created_at", "updated_at"]
    ordering = ["topic", "subtopic", "title"]

    # ---------- helper: topic-wide ordering ----------
    def _topic_ordered_ids(self, current):
        """
        Return ordered list of IDs within the same topic.
        Primary: order_in_topic (NULLs last via big fallback),
        Secondary: title, then id.
        """
        qs = (
            ReadingMaterial.objects
            .filter(topic=current.topic)
            .annotate(_ord=Coalesce("order_in_topic", Value(10_000_000, output_field=IntegerField())))
            .order_by("_ord", "title", "id")
            .values_list("id", flat=True)
        )
        return list(qs)

    # ---------- extra actions ----------
    @action(detail=True, methods=["get"])
    def next(self, request, pk=None):
        """Next reading material within the same topic."""
        cur = self.get_object()
        ids = self._topic_ordered_ids(cur)
        try:
            idx = ids.index(cur.id)
        except ValueError:
            return Response({"detail": "Current item not in ordered list."}, status=404)
        if idx + 1 >= len(ids):
            return Response({"detail": "No next reading material in this topic."}, status=404)
        nxt = ReadingMaterial.objects.get(id=ids[idx + 1])
        return Response(self.get_serializer(nxt).data)

    @action(detail=True, methods=["get"])
    def prev(self, request, pk=None):
        """Previous reading material within the same topic."""
        cur = self.get_object()
        ids = self._topic_ordered_ids(cur)
        try:
            idx = ids.index(cur.id)
        except ValueError:
            return Response({"detail": "Current item not in ordered list."}, status=404)
        if idx - 1 < 0:
            return Response({"detail": "No previous reading material in this topic."}, status=404)
        prv = ReadingMaterial.objects.get(id=ids[idx - 1])
        return Response(self.get_serializer(prv).data)

    @action(detail=True, methods=["get"])
    def neighbors(self, request, pk=None):
        """
        One call to fetch prev/next IDs (topic-wide ordering).
        Returns: {"prev_id": <int|null>, "next_id": <int|null>}
        """
        cur = self.get_object()
        ids = self._topic_ordered_ids(cur)
        try:
            idx = ids.index(cur.id)
        except ValueError:
            return Response({"prev_id": None, "next_id": None})
        prev_id = ids[idx - 1] if idx - 1 >= 0 else None
        next_id = ids[idx + 1] if idx + 1 < len(ids) else None
        return Response({"prev_id": prev_id, "next_id": next_id})


class TopicViewSet(viewsets.ViewSet):
    """
    Simple endpoint for listing unique topics (for dropdowns).
    GET /api/topics/
    """
    def list(self, request):
        topics = (
            ReadingMaterial.objects
            .values_list("topic", flat=True)
            .distinct()
            .order_by("topic")
        )
        return Response(list(topics))


class TopicTOC(APIView):
    """
    GET /api/topics/<topic_name>/toc/
    Returns ordered list of pages (id, subtopic, title) for that topic.
    """
    def get(self, request, topic_name):
        qs = (ReadingMaterial.objects
              .filter(topic=topic_name)
              .annotate(_ord=Coalesce('order_in_topic', Value(10_000_000, output_field=IntegerField())))
              .order_by('_ord', 'title', 'id')
              .values('id', 'subtopic', 'title'))
        return Response(list(qs))
