from rest_framework import viewsets, filters, generics
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from django.db.models.functions import Coalesce
from django.db.models import IntegerField, Value, Count, Q
from rest_framework.permissions import AllowAny

from reading.models import ReadingMaterial
from content_ingestion.models import Topic, Subtopic
from .serializers import ReadingMaterialSerializer
from .serializers import TopicAdminSerializer, SubtopicAdminSerializer
from .pagination import StandardResultsSetPagination


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
            .annotate(
                _ord=Coalesce("order_in_topic", Value(10_000_000, output_field=IntegerField()))
            )
            .order_by("subtopic_ref__order_in_topic", "_ord", "title", "id")
            .values("id", "title", subtopic_name=Coalesce("subtopic_ref__name", Value("")))
        )
        return Response(list(qs))


class TopicViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public endpoint to list topics with subtopic counts.
    """
    queryset = Topic.objects.all().order_by("zone__order", "id")
    serializer_class = TopicAdminSerializer

    def get_queryset(self):
        return (
            Topic.objects
            .annotate(subtopics_count=Count("subtopics"))
            .order_by("zone__order", "id")
        )


class SubtopicViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public endpoint to list subtopics by topic (with reading material count).
    """
    queryset = Subtopic.objects.select_related("topic").order_by("topic__id", "order_in_topic")
    serializer_class = SubtopicAdminSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        topic_param = self.request.query_params.get("topic")  
        if topic_param:
            qs = qs.filter(Q(topic__slug=topic_param) | Q(topic__name=topic_param))
        return (
            qs.annotate(materials_count=Count("materials"))
            .order_by("topic__id", "order_in_topic", "name")
        )



class ReadingMaterialViewSet(viewsets.ReadOnlyModelViewSet):
    """Public read-only endpoint for Reading Materials."""
    permission_classes = [AllowAny]
    pagination_class = None

    queryset = (
        ReadingMaterial.objects
        .select_related("topic_ref", "subtopic_ref")
        .order_by("topic_ref__name", "subtopic_ref__order_in_topic", "order_in_topic", "title")
    )
    serializer_class = ReadingMaterialSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

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


class TopicListView(APIView):
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
    permission_classes = [AllowAny]
    def get(self, request, topic_key):
        qs = (
            Subtopic.objects
            .filter(Q(topic_ref__slug=topic_key) | Q(topic_ref__name=topic_key))
            .annotate(materials_count=Count("readingmaterial"))
            .order_by("order_in_topic", "name")
            .values("id", "name", "slug", "order_in_topic", "materials_count")
        )
        return Response(list(qs))


class MaterialsByTopicSubtopicView(generics.ListAPIView):
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
