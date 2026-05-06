from django.urls import path
from .views import (
    MyZoneProgressView,
    MyTopicProgressView,
    MySubtopicStatsView,
    MyCurrentZoneView,
    AllLearnersZoneProgressView,
    TopicProficiencyHistoryView,
)

urlpatterns = [
    path('progress/zones/', MyZoneProgressView.as_view(), name='my-zone-progress'),
    path('progress/topics/', MyTopicProgressView.as_view(), name='my-topic-progress'),
    path('progress/topics/history/', TopicProficiencyHistoryView.as_view(), name='topic-proficiency-history'),
    path('progress/subtopics/', MySubtopicStatsView.as_view(), name='my-subtopic-progress'),
    path('progress/current-zone/', MyCurrentZoneView.as_view(), name='my-current-zone'),
    path('progress/zones/all/', AllLearnersZoneProgressView.as_view(), name='all-learners-zone-progress'),
]
