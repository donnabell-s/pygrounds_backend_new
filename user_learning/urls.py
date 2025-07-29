from django.urls import path
from .views import (
    MyZoneProgressView,
    MyTopicProgressView,
    MySubtopicStatsView,
    MyCurrentZoneView,
)

urlpatterns = [
    path('progress/zones/', MyZoneProgressView.as_view(), name='my-zone-progress'),
    path('progress/topics/', MyTopicProgressView.as_view(), name='my-topic-progress'),
    path('progress/subtopics/', MySubtopicStatsView.as_view(), name='my-subtopic-progress'),
    path('progress/current-zone/', MyCurrentZoneView.as_view(), name='my-current-zone'),
]
