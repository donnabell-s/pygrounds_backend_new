from django.urls import path
from .api import recalibrate_question_difficulty 
urlpatterns = [
    path('recalibrate-question/<int:id>/', recalibrate_question_difficulty),
]
