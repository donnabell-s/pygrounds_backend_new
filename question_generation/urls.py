from django.urls import path
from .api import recalibrate_question 
urlpatterns = [
    path('recalibrate-question/<int:question_id>/', recalibrate_question, name='recalibrate_question'),
]
