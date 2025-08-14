from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView, TokenRefreshView, TokenVerifyView,
)
from rest_framework.routers import DefaultRouter

from reading.views import ReadingMaterialViewSet, TopicViewSet, TopicTOC

router = DefaultRouter()
router.register(r"reading-materials", ReadingMaterialViewSet, basename="reading-material")
router.register(r"topics", TopicViewSet, basename="topic")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # path("api/question_generation/", include("question_generation.urls")),  # keep disabled if not needed right now
    path("api/", include(router.urls)),
    path("api/topics/<str:topic_name>/toc/", TopicTOC.as_view(), name="topic-toc"),
]
