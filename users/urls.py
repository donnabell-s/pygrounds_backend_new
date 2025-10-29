# users/urls.py

from django.urls import path
from .views import (
    RegisterView,
    UserProfileView,
    UserPublicProfileView,
    UserListView,
    UserAdminDetailView,
    AdminUserListView,
    AdminUserDetailView,
    deactivate_user,
    activate_user,
)
from users.jwt_views import EmailTokenObtainPairView

urlpatterns = [
    # public / user endpoints
    path('register/', RegisterView.as_view(), name='user-register'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('<int:pk>/profile/', UserPublicProfileView.as_view(), name='user-public-profile'),

    # existing user-list/detail endpoints (kept for compatibility)
    path('', UserListView.as_view(), name='user-list'),
    path('<int:pk>/', UserAdminDetailView.as_view(), name='user-admin-detail'),

    # admin-style endpoints introduced on merge-read/recalib-wip
    path('admin/users/', AdminUserListView.as_view(), name='admin-user-list'),
    path('admin/users/<int:pk>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/users/<int:user_id>/deactivate/', deactivate_user, name='deactivate-user'),
    path('admin/users/<int:user_id>/activate/', activate_user, name='activate-user'),

    # token endpoint
    path('api/token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
]
