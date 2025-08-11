from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView, TokenRefreshView, TokenVerifyView,
)
from rest_framework.routers import DefaultRouter
from rest_framework.schemas import get_schema_view
from rest_framework.renderers import JSONOpenAPIRenderer

from reading.views import (
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
    path("admin/", admin.site.urls),

    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    path("api/", include(router.urls)),

    # Reading endpoints
    path("api/reading/topics/", TopicListView.as_view(), name="topics-list"),
    path(
        "api/reading/topics/<slug:topic_key>/subtopics/",
        SubtopicListByTopicView.as_view(),
        name="subtopics-by-topic",
    ),
    path(
        "api/reading/topics/<slug:topic_slug>/subtopics/<slug:subtopic_slug>/materials/",
        MaterialsByTopicSubtopicView.as_view(),
        name="materials-by-topic-subtopic",
    ),
    path("api/topics/<str:topic_name>/toc/", TopicTOC.as_view(), name="topic-toc"),

    #calibration routes (question_generation)

    path("api/", include("question_generation.urls")),

    path(
        "api/schema/",
        get_schema_view(
            title="PyGrounds API",
            description="Reading materials public API",
            version="1.0.0",
            renderer_classes=[JSONOpenAPIRenderer],
        ),
        name="openapi-schema",
    ),
]
