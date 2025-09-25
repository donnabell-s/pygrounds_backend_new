from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAdminUser  #use AllowAny temporarily if needed
from rest_framework import filters


from content_ingestion.models import Topic as CITopic, Subtopic as CISubtopic
from reading.models import ReadingMaterial

from .serializers import (
    TopicAdminSerializer,
    SubtopicAdminSerializer,
    AdminReadingMaterialSerializer,
)

class TopicAdminViewSet(ModelViewSet):
    
    queryset = CITopic.objects.all().order_by("name", "id")
    
    serializer_class = TopicAdminSerializer
    permission_classes = [IsAdminUser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "slug", "id"]
    ordering = ["name", "id"]



class SubtopicAdminViewSet(ModelViewSet):
    queryset = (
        CISubtopic.objects
        .select_related("topic")
        .all()
        .order_by("topic__name", "order_in_topic", "name", "id")
    )
    serializer_class = SubtopicAdminSerializer
    permission_classes = [IsAdminUser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug", "topic__name", "topic__slug"]
    ordering_fields = ["name", "slug", "order_in_topic", "id", "topic__name"]
    ordering = ["topic__name", "order_in_topic", "name", "id"]


class AdminReadingMaterialViewSet(ModelViewSet):
    queryset = (
        ReadingMaterial.objects
        .select_related("topic_ref", "subtopic_ref")
        .all()
        .order_by(
            "topic_ref__name",
            "subtopic_ref__order_in_topic",
            "order_in_topic",
            "title",
            "id"
        )
    )
    serializer_class = AdminReadingMaterialSerializer
    permission_classes = [IsAdminUser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    
    search_fields = [
        "title", "content",
        "topic_ref__name", "subtopic_ref__name",
        "topic_ref__slug", "subtopic_ref__slug"
    ]
    ordering_fields = [
        "title", "order_in_topic", "id",
        "topic_ref__name", "subtopic_ref__order_in_topic",
        "created_at", "updated_at"
    ]
    ordering = [
        "topic_ref__name",
        "subtopic_ref__order_in_topic",
        "order_in_topic",
        "title",
        "id"
    ]
