from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ReadingMaterialViewSet,
    TopicViewSet,
    TopicTOC,
    TopicListView,
    SubtopicListByTopicView,
    MaterialsByTopicSubtopicView,
)

router = DefaultRouter()
router.register(r"reading-materials", ReadingMaterialViewSet, basename="reading-material")
router.register(r"topics", TopicViewSet, basename="topic")

urlpatterns = [
    path("", include(router.urls)),

    path("reading/topics/", TopicListView.as_view(), name="topics-list"),
    path(
        "reading/topics/<slug:topic_key>/subtopics/",
        SubtopicListByTopicView.as_view(),
        name="subtopics-by-topic",
    ),
    path(
        "reading/topics/<slug:topic_slug>/subtopics/<slug:subtopic_slug>/materials/",
        MaterialsByTopicSubtopicView.as_view(),
        name="materials-by-topic-subtopic",
    ),
    path("topics/<str:topic_name>/toc/", TopicTOC.as_view(), name="topic-toc"),
]
