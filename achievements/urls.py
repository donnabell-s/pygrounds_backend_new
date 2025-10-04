from django.urls import path
from .views import AchievementListView, AchievementDetailView, UnlockedAchievementListView, UserUnlockedAchievementListView
from .views import AchievementProgressListView

urlpatterns = [
    path('achievements/', AchievementListView.as_view(), name='achievements-list'),
    path('achievements/<int:pk>/', AchievementDetailView.as_view(), name='achievements-detail'),
    path('achievements/unlocked/', UnlockedAchievementListView.as_view(), name='achievements-unlocked'),
    path('achievements/user/<int:user_id>/', UserUnlockedAchievementListView.as_view(), name='achievements-user-unlocked'),
    path('achievements/progress/', AchievementProgressListView.as_view(), name='achievements-progress'),
]
