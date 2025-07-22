from django.urls import path
from .views import StartCrosswordGame, SubmitCrosswordResult

urlpatterns = [
    path("start-crossword/", StartCrosswordGame.as_view(), name="start-crossword"),
    path("submit-crossword/", SubmitCrosswordResult.as_view(), name="submit-crossword"),
]
