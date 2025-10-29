from rest_framework import viewsets, filters, generics
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from django.db.models.functions import Coalesce
from django.db.models import IntegerField, Value, Count, Q
from rest_framework.permissions import AllowAny

from reading.models import ReadingMaterial, Topic, Subtopic
from .serializers import (
    ReadingMaterialSerializer,
    NeighborIdsSerializer,
    IdOnlySerializer,  
)
from .filters import SafeDjangoFilterBackend
from .pagination import StandardResultsSetPagination


class ReadingMaterialViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public read-only endpoint for Reading Materials.
    Supports filter by topic/subtopic (slug or name), search (title/content), and ordering.
    """
    permission_classes = [AllowAny]
    pagination_class = StandardResultsSetPagination

    queryset = (
        ReadingMaterial.objects
        .select_related("topic_ref", "subtopic_ref")
        .order_by("topic_ref__name", "subtopic_ref__order_in_topic", "order_in_topic", "title")
    )

    serializer_class = ReadingMaterialSerializer
    filter_backends = [SafeDjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    search_fields = ["title", "content"]
    ordering_fields = [
        "title", "created_at", "updated_at",
        "order_in_topic",
        "topic_ref__name",
        "subtopic_ref__name",
        "subtopic_ref__order_in_topic",
    ]
    ordering = ["topic_ref__name", "subtopic_ref__order_in_topic", "order_in_topic", "title"]

    def get_queryset(self):
        qs = super().get_queryset()

        # ?topic=<slug or name>
        # ?subtopic=<slug or name>
        topic_param = self.request.query_params.get("topic")
        subtopic_param = self.request.query_params.get("subtopic")

        if topic_param:
            qs = qs.filter(Q(topic_ref__slug=topic_param) | Q(topic_ref__name=topic_param))

        if subtopic_param:
            qs = qs.filter(Q(subtopic_ref__slug=subtopic_param) | Q(subtopic_ref__name=subtopic_param))

        return qs

    def _topic_ordered_ids(self, current: ReadingMaterial):
        qs = (
            ReadingMaterial.objects
            .filter(topic_ref=current.topic_ref)
            .select_related("subtopic_ref")
            .annotate(_ord_topic=Coalesce("order_in_topic", Value(10_000_000, output_field=IntegerField())))
            .order_by("subtopic_ref__order_in_topic", "_ord_topic", "title", "id")
            .values_list("id", flat=True)
        )
        return list(qs)

    @action(detail=True, methods=["get"])
    def next(self, request, pk=None):
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
        cur = self.get_object()
        ids = self._topic_ordered_ids(cur)
        try:
            idx = ids.index(cur.id)
        except ValueError:
            return Response({"prev_id": None, "next_id": None})
        prev_id = ids[idx - 1] if idx - 1 >= 0 else None
        next_id = ids[idx + 1] if idx + 1 < len(ids) else None
        return Response({"prev_id": prev_id, "next_id": next_id})

    def get_serializer_class(self):
        if getattr(self, "action", None) == "neighbors" and "NeighborIdsSerializer" in globals():
            return NeighborIdsSerializer
        return ReadingMaterialSerializer


class TopicViewSet(viewsets.ViewSet):
    """GET /api/topics/ (existing via router)"""
    permission_classes = [AllowAny]

    def list(self, request):
        topics = (
            Topic.objects
            .annotate(subtopics_count=Count("subtopics"))
            .order_by("name")
            .values("id", "name", "slug", "subtopics_count")
        )
        return Response(list(topics))


# --- New: endpoints to match /api/reading/topics/... ---

class TopicListView(APIView):
    """Alias for topics list at /api/reading/topics/"""
    permission_classes = [AllowAny]
    def get(self, request):
        topics = (
            Topic.objects
            .annotate(subtopics_count=Count("subtopics"))
            .order_by("name")
            .values("id", "name", "slug", "subtopics_count")
        )
        return Response(list(topics))


class SubtopicListByTopicView(APIView):
    """GET /api/reading/topics/<topic_key>/subtopics/  (topic_key = slug or exact name)"""
    permission_classes = [AllowAny]

    def get(self, request, topic_key):
        qs = (
            Subtopic.objects
            .filter(Q(topic__slug=topic_key) | Q(topic__name=topic_key))
            .annotate(materials_count=Count("materials"))
            .order_by("order_in_topic", "name")
            .values("id", "name", "slug", "order_in_topic", "materials_count")
        )
        return Response(list(qs))


class MaterialsByTopicSubtopicView(generics.ListAPIView):
    """
    GET /api/reading/topics/<topic_slug>/subtopics/<subtopic_slug>/materials/
    Paginated list of materials under that (topic, subtopic).
    """
    permission_classes = [AllowAny]
    pagination_class = StandardResultsSetPagination
    serializer_class = ReadingMaterialSerializer

    def get_queryset(self):
        tslug = self.kwargs["topic_slug"]
        sslug = self.kwargs["subtopic_slug"]
        return (
            ReadingMaterial.objects
            .select_related("topic_ref", "subtopic_ref")
            .filter(topic_ref__slug=tslug, subtopic_ref__slug=sslug)
            .order_by("order_in_topic", "title", "id")
        )


class TopicTOC(APIView):
    """
    GET /api/topics/<topic_key>/toc/
    Returns ordered list of pages (id, subtopic name, title) for that topic.
    """
    permission_classes = [AllowAny]

    def get(self, request, topic_key):
        topic = Topic.objects.filter(Q(slug=topic_key) | Q(name=topic_key)).first()
        if not topic:
            return Response({"detail": "Topic not found."}, status=404)

        qs = (
            ReadingMaterial.objects
            .filter(topic_ref=topic)
            .select_related("subtopic_ref")
            .annotate(_ord=Coalesce('order_in_topic', Value(10_000_000, output_field=IntegerField())))
            .order_by('subtopic_ref__order_in_topic', '_ord', 'title', 'id')
            .values('id', 'title', subtopic=Coalesce('subtopic_ref__name', Value('')))
        )
        return Response(list(qs))
