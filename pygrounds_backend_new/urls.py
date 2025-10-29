from django.contrib import admin
from django.urls import path, include
from rest_framework.renderers import JSONOpenAPIRenderer
from rest_framework.schemas import get_schema_view
from rest_framework_simplejwt.views import (
    TokenObtainPairView, TokenRefreshView, TokenVerifyView
)

urlpatterns = [
    path("admin/", admin.site.urls),

    # JWT Authentication
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    

    # App APIs
    path("api/", include("reading.urls")),
    path("api/user/", include("users.urls")),

    # reading + users 
    path("api/", include("reading.urls")),
    path("api/user/", include("users.urls")),
   
    path("api/", include("content_ingestion.urls")),
    path("api/", include("question_generation.urls")),
    path("api/", include("user_learning.urls")),
    path("api/", include("minigames.urls")),


    # OpenAPI Documentation
    path(
        "api/schema/",
        get_schema_view(
            title="PyGrounds API",
            description="Reading + Admin CRUD",
            version="1.0.0",
            renderer_classes=[JSONOpenAPIRenderer],
        ),
        name="openapi-schema",
    ),
    # reading + users 
    path("api/", include("reading.urls")),
    path("api/user/", include("users.urls")),

    
    # OpenAPI (optional)
    path(
        "api/schema/",
        get_schema_view(
            title="PyGrounds API",
            description="Reading + Admin CRUD",
            version="1.0.0",
            renderer_classes=[JSONOpenAPIRenderer],
        ),
        name="openapi-schema",
    ),
]
