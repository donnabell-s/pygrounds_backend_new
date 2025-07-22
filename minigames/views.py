from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .game_logic.crossword import CrosswordGenerator
from .data.crossword_questions import CROSSWORD_QUESTIONS
import time
from datetime import datetime

# Simulate in-memory sessions for demo
SESSION_STATE = {}

class StartCrosswordGame(APIView):
    # permission_classes = [IsAuthenticated]
    def get(self, request):
        session_id = str(time.time())  # Basic session ID

        # Load static questions
        word_clue_pairs = CROSSWORD_QUESTIONS
        words = [pair["word"] for pair in word_clue_pairs]

        generator = CrosswordGenerator()
        grid, placements = generator.generate(words)
        grid_display = [''.join(row) for row in grid]

        # Get the current time in ISO 8601 format
        started_at = datetime.now().isoformat()

        # Save session
        SESSION_STATE[session_id] = {
            "start_time": time.time(),
            "started_at": started_at,  # Store the started_at time
            "questions": word_clue_pairs,
            "answered": [],
            "unanswered": [q["word"].upper() for q in word_clue_pairs],
            "timer": 5 * 60  # 5 minutes
        }

        response = {
            "session_id": session_id,
            "grid": grid_display,
            "placements": [
                {
                    "word": p.word,
                    "clue": next((q["clue"] for q in word_clue_pairs if q["word"].upper() == p.word), ""),
                    "row": p.row,
                    "col": p.col,
                    "direction": p.direction
                } for p in placements
            ],
            "timer_seconds": 300,
            "started_at": started_at  # Include started_at in the response
        }

        return Response(response, status=status.HTTP_200_OK)


class SubmitCrosswordResult(APIView):
    # permission_classes = [IsAuthenticated]
    def post(self, request):
        session_id = request.data.get("session_id")
        answers = request.data.get("answers", [])  # List of answered words

        session = SESSION_STATE.get(session_id)
        if not session:
            return Response({"error": "Invalid session."}, status=status.HTTP_400_BAD_REQUEST)

        end_time = time.time()
        time_taken = end_time - session["start_time"]
        time_limit = session["timer"]

        # No more time-expired check — frontend decides when to submit
        answered_set = set(word.upper() for word in answers)
        correct_answers = [q["word"].upper() for q in session["questions"] if q["word"].upper() in answered_set]
        incorrect_or_unanswered = [q["word"].upper() for q in session["questions"] if q["word"].upper() not in answered_set]

        result = {
            "correct": correct_answers,
            "missed": incorrect_or_unanswered,
            "time_taken_seconds": int(min(time_taken, time_limit)),
            "time_remaining_seconds": max(0, int(time_limit - time_taken)),
            "status": "completed"
        }

        # Clean up session
        del SESSION_STATE[session_id]

        return Response(result, status=status.HTTP_200_OK)
