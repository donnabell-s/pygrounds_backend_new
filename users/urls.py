# users/urls.py

from django.urls import path
from .views import (
    RegisterView, 
    UserProfileView,
    AdminUserListView,
    AdminUserDetailView,
    deactivate_user,
    activate_user
)
from .views import (RegisterView, UserProfileView, UserPublicProfileView, UserListView, UserAdminDetailView)
from users.jwt_views import EmailTokenObtainPairView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='user-register'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('admin/users/', AdminUserListView.as_view(), name='admin-user-list'),
    path('admin/users/<int:pk>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/users/<int:user_id>/deactivate/', deactivate_user, name='deactivate-user'),
    path('admin/users/<int:user_id>/activate/', activate_user, name='activate-user'),
    path('<int:pk>/profile/', UserPublicProfileView.as_view(), name='user-public-profile'),
]
