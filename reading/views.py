<<<<<<< HEAD
from django.db.models.functions import Coalesce
from django.db.models import IntegerField, Value
from rest_framework import viewsets, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

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

    @action(detail=True, methods=["get"])
    def next(self, request, pk=None):
        """
        Next reading material within the same topic.
        """
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
        """
        Previous reading material within the same topic.
        """
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


class TopicViewSet(viewsets.ViewSet):
    """
    GET /api/topics/
    Returns a simple array of unique topic strings (sorted).
    """
    def list(self, request):
        topics = (
            ReadingMaterial.objects
            .values_list("topic", flat=True)
            .distinct()
            .order_by("topic")
        )
        return Response(list(topics))
=======
from django.shortcuts import render

# Create your views here.
>>>>>>> origin/reading-material
