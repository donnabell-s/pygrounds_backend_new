from django.urls import path
from .views import (
    # Shared
    StartGameSession, SubmitAnswers, exit_session, GetSessionResponses, GetSessionInfo,

    # Crossword
    StartCrosswordGame, GetCrosswordGrid,

    # WordSearch
    StartWordSearchGame, GetWordSearchMatrix,

    # Hangman
    StartHangmanGame, SubmitHangmanCode,

    StartDebugGame, SubmitDebugGame,
)


urlpatterns = [
    # ──────────────── Generic ────────────────
    path("session/<str:session_id>/submit/", SubmitAnswers.as_view(), name="submit-answers"),
    path("start-session/", StartGameSession.as_view(), name="start-session"),
    path("session/<str:session_id>/", GetSessionInfo.as_view(), name="get-session-info"),
    path("session/<str:session_id>/exit/", exit_session, name="exit-session"),
    path("session/<str:session_id>/responses/", GetSessionResponses.as_view(), name="session-responses"),

    # ──────────────── Crossword ────────────────
    path("crossword/start/", StartCrosswordGame.as_view(), name="start-crossword"),
    path("crossword/<str:session_id>/grid/", GetCrosswordGrid.as_view(), name="crossword-grid"),

    # ──────────────── WordSearch ────────────────
    path("wordsearch/start/", StartWordSearchGame.as_view(), name="start-wordsearch"),
    path("wordsearch/<str:session_id>/matrix/", GetWordSearchMatrix.as_view(), name="wordsearch-matrix"),
    
    # ──────────────── Hangman ────────────────
    path("hangman/start/", StartHangmanGame.as_view(), name="start-hangman"),
    path("hangman/<str:session_id>/submit-code/", SubmitHangmanCode.as_view(), name="submit-hangman-code"),

    path("debugging/start/", StartDebugGame.as_view(), name="start-debug"),
    path("debugging/<str:session_id>/submit-code/", SubmitDebugGame.as_view(), name="submit-debug"),
 
]
