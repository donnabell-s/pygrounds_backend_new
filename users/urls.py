# users/urls.py

from django.urls import path
from .views import (RegisterView, UserProfileView,)
from users.jwt_views import EmailTokenObtainPairView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='user-register'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('api/token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
]
