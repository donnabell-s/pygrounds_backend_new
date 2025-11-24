from django.urls import path, include
from rest_framework.routers import DefaultRouter
from reading.admin_views import TopicAdminViewSet, SubtopicAdminViewSet, AdminReadingMaterialViewSet


from .views import (
    ReadingMaterialViewSet,
    TopicViewSet,
    TopicTOC,
    TopicListView,
    SubtopicViewSet,
    SubtopicListByTopicView,
    MaterialsByTopicSubtopicView,
)


public_router = DefaultRouter()
public_router.register(r"reading-materials", ReadingMaterialViewSet, basename="reading-material")
public_router.register(r"topics", TopicViewSet, basename="topic")
public_router.register(r"subtopics", SubtopicViewSet, basename="subtopic")


public_router = DefaultRouter()
public_router.register(r"reading-materials", ReadingMaterialViewSet, basename="reading-material")
public_router.register(r"topics", TopicViewSet, basename="topic")

admin_router = DefaultRouter()
admin_router.register(r"admin/topics", TopicAdminViewSet, basename="admin-topics")
admin_router.register(r"admin/subtopics", SubtopicAdminViewSet, basename="admin-subtopics")
admin_router.register(r"admin/materials", AdminReadingMaterialViewSet, basename="admin-materials")

urlpatterns = [
    path("", include(public_router.urls)),
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
    path("reading/", include(admin_router.urls)),
]
