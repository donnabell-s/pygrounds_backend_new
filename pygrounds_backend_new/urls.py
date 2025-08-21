from django.contrib import admin
from django.urls import path, include
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
    ])),
    path('api/', include('minigames.urls')),
    path('api/user/', include('users.urls')),
]
