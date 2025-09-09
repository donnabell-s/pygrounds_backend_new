from django.contrib import admin
from django.urls import path, include
from rest_framework.schemas import get_schema_view
from rest_framework.renderers import JSONOpenAPIRenderer

from rest_framework_simplejwt.views import (TokenObtainPairView, TokenRefreshView, TokenVerifyView,)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include([
        path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
        path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
        path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
        path('', include('question_generation.urls')),
        path('', include('content_ingestion.urls')),
        path('', include('user_learning.urls')),
        path('', include("reading.urls")),

    ])),
    path('api/', include('minigames.urls')),
    path('api/user/', include('users.urls')),
    path(
        "api/schema/",
        get_schema_view(
            title="PyGrounds API",
            description="Reading materials + Difficulty recalibration API",
            version="1.0.0",
            renderer_classes=[JSONOpenAPIRenderer],
        ),
        name="openapi-schema",
    ),
]
