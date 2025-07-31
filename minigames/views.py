import uuid
import re
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from question_generation.models import PreAssessmentQuestion
from user_learning.adaptive_engine import recalibrate_topic_proficiency

from .game_logic.crossword import CrosswordGenerator
from .game_logic.wordsearch import WordSearchGenerator
from .game_logic.hangman import run_user_code
from .models import (
    GameSession,
    GameQuestion,
    QuestionResponse,
    WordSearchData,
)
from .serializers import GameSessionSerializer, QuestionResponseSerializer, LightweightQuestionSerializer
from .question_fetching import fetch_questions_for_game


# =============================
# Helper
# =============================

def sanitize_word_for_grid(word: str) -> str:
    """
    Converts a word to uppercase and removes non-alphabetic characters
    for crossword/wordsearch compatibility.
    """
    if not word:
        return ""
    return re.sub(r'[^A-Za-z]', '', word).upper()


# =============================
# Generic Session Views
# =============================

class StartGameSession(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        game_type = request.data.get("game_type")
        question_count = int(request.data.get("question_count", 5))

        session = GameSession.objects.create(
            session_id=str(uuid.uuid4()),
            user=user,
            game_type=game_type,
            status="active",
        )

        questions = fetch_questions_for_game(user, game_type, limit=question_count)
        GameQuestion.objects.bulk_create([
            GameQuestion(session=session, question_id=q.id)
            for q in questions
        ])

        return Response(GameSessionSerializer(session).data, status=201)


class GetSessionInfo(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = GameSession.objects.filter(session_id=session_id).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        return Response(GameSessionSerializer(session).data)


class SubmitAnswers(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        answers = request.data.get("answers", [])
        session = GameSession.objects.filter(session_id=session_id, status="active").first()
        if not session:
            return Response({"error": "Invalid or inactive session"}, status=400)

        score = 0
        for ans in answers:
            try:
                game_q = GameQuestion.objects.get(id=ans["question_id"], session=session)
            except GameQuestion.DoesNotExist:
                continue

            correct = (
                str(game_q.question.correct_answer).strip().lower()
                == ans["user_answer"].strip().lower()
            )
            if correct:
                score += 1

            QuestionResponse.objects.create(
                question=game_q,
                user=request.user,
                user_answer=ans["user_answer"],
                is_correct=correct,
                time_taken=ans.get("time_taken", 0),
            )

        session.status = "completed"
        session.total_score = score
        session.end_time = timezone.now()
        session.save()

        return Response({"message": "Answers submitted", "score": score})


@api_view(["POST"])
def exit_session(request, session_id):
    session = GameSession.objects.filter(session_id=session_id, status="active").first()
    if not session:
        return Response({"error": "Session not found or already ended."}, status=400)

    session.status = "expired"
    session.end_time = timezone.now()
    session.save()
    return Response({"message": "Session marked as expired."})


class GetSessionResponses(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = GameSession.objects.filter(session_id=session_id).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)

        responses = QuestionResponse.objects.filter(
            question__session=session, user=request.user
        )
        return Response(QuestionResponseSerializer(responses, many=True).data)


# =============================
# Crossword Game
# =============================

class StartCrosswordGame(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        question_count = int(request.data.get("question_count", 10))

        session = GameSession.objects.create(
            session_id=str(uuid.uuid4()),
            user=user,
            game_type="crossword",
            status="active",
            time_limit=300,
        )

        questions = fetch_questions_for_game(user, "crossword", limit=question_count)
        GameQuestion.objects.bulk_create([
            GameQuestion(session=session, question_id=q.id) for q in questions
        ])

        # Sanitize answers for grid
        words = [sanitize_word_for_grid(q.correct_answer) for q in questions]
        words = [w for w in words if w]
        print("DEBUG WORDS:", words)

        generator = CrosswordGenerator()
        grid, placements = generator.generate(words)
        grid_display = ["".join(row) for row in grid]

        placements_payload = []
        for p in placements:
            clue = next((q.question_text for q in questions if sanitize_word_for_grid(q.correct_answer) == p.word), "")
            placements_payload.append({
                "word":      p.word,
                "clue":      clue,
                "row":       p.row,
                "col":       p.col,
                "direction": p.direction,
            })

        return Response({
            "session_id":    session.session_id,
            "grid":          grid_display,
            "placements":    placements_payload,
            "timer_seconds": session.time_limit,
            "started_at":    session.start_time,
        }, status=201)


class GetCrosswordGrid(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = GameSession.objects.filter(
            session_id=session_id, game_type="crossword"
        ).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)

        questions = [gq.question for gq in session.session_questions.all()]
        words = [sanitize_word_for_grid(q.correct_answer) for q in questions]
        words = [w for w in words if w]

        generator = CrosswordGenerator()
        grid, placements = generator.generate(words)
        grid_display = ["".join(row) for row in grid]

        return Response({
            "grid":       grid_display,
            "placements": [
                {
                    "word":      p.word,
                    "clue":      next((q.question_text for q in questions if sanitize_word_for_grid(q.correct_answer) == p.word), ""),
                    "row":       p.row,
                    "col":       p.col,
                    "direction": p.direction,
                } for p in placements
            ]
        })


# =============================
# WordSearch Game
# =============================

class StartWordSearchGame(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        question_count = int(request.data.get("question_count", 10))

        session = GameSession.objects.create(
            session_id=str(uuid.uuid4()),
            user=user,
            game_type="wordsearch",
            status="active",
            time_limit=300,
        )

        # 1) Fetch questions
        questions = fetch_questions_for_game(user, "wordsearch", limit=question_count)

        # 2) Prepare sanitized words
        sanitized_map = {q.id: sanitize_word_for_grid(q.correct_answer) for q in questions}
        words = [w for w in sanitized_map.values() if w]

        # 3) Generate the matrix
        generator = WordSearchGenerator()
        matrix, placements = generator.generate(words)

        # 4) Determine which questions were actually placed
        placed_words = {p.word for p in placements}
        placed_questions = [q for q in questions if sanitized_map[q.id] in placed_words]

        # 5) Only create GameQuestions for placed questions
        GameQuestion.objects.bulk_create([
            GameQuestion(session=session, question_id=q.id) for q in placed_questions
        ])

        # 6) Save matrix & placements
        WordSearchData.objects.create(
            session=session,
            matrix=["".join(row) for row in matrix],
            placements=[{
                "word":      p.word,
                "row":       p.row,
                "col":       p.col,
                "direction": p.direction
            } for p in placements]
        )

        return Response({
            "session_id":    session.session_id,
            "matrix":        ["".join(row) for row in matrix],
            "placements":    [{
                "word":      p.word,
                "row":       p.row,
                "col":       p.col,
                "direction": p.direction
            } for p in placements],
            "questions":     LightweightQuestionSerializer(placed_questions, many=True).data,
            "timer_seconds": session.time_limit,
            "started_at":    session.start_time,
        }, status=201)




class GetWordSearchMatrix(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = GameSession.objects.filter(
            session_id=session_id, game_type="wordsearch"
        ).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)

        try:
            data = session.wordsearch_data
        except WordSearchData.DoesNotExist:
            return Response({"error": "Matrix not generated yet."}, status=400)

        questions = [gq.question for gq in session.session_questions.all()]
        placed_words = {p["word"] for p in data.placements}
        placed_questions = [
            q for q in questions
            if sanitize_word_for_grid(q.correct_answer) in placed_words
        ]

        return Response({
            "matrix":     data.matrix,
            "placements": data.placements,
            "questions":  LightweightQuestionSerializer(placed_questions, many=True).data
        })



# =============================
# Hangman Game
# =============================

class StartHangmanGame(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        session = GameSession.objects.create(
            session_id=str(uuid.uuid4()),
            user=user,
            game_type="hangman",
            status="active",
            time_limit=300,
        )

        questions = fetch_questions_for_game(user, "hangman", limit=1)
        if not questions:
            return Response({"error": "No questions available"}, status=400)

        question = questions[0]
        GameQuestion.objects.create(session=session, question=question)

        return Response({
            "session_id":    session.session_id,
            "prompt":        question.question_text,
            "function_name": question.game_data.get("function_name", ""),
            "sample_input":  question.game_data.get("sample_input", ""),
            "sample_output": question.game_data.get("sample_output", ""),
            "timer_seconds": session.time_limit,
        }, status=201)


class SubmitHangmanCode(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = GameSession.objects.filter(
            session_id=session_id, user=request.user, status="active"
        ).first()
        if not session:
            return Response({"error": "Invalid or ended session."}, status=400)

        game_q = session.session_questions.first()
        question = game_q.question
        user_code = request.data.get("code")
        if not user_code:
            return Response({"error": "No code submitted."}, status=400)

        wrong = QuestionResponse.objects.filter(
            question=game_q, user=request.user, is_correct=False
        ).count()
        remaining_lives = 3 - wrong

        passed, message, trace = run_user_code(
            user_code,
            question.game_data.get("function_name", ""),
            question.game_data.get("hidden_tests", [])
        )

        QuestionResponse.objects.create(
            question=game_q,
            user=request.user,
            user_answer=user_code,
            is_correct=passed,
            time_taken=0,
        )

        if passed or remaining_lives <= 1:
            session.status = "completed"
            session.total_score = 1 if passed else 0
            session.end_time = timezone.now()
            session.save()
            return Response({
                "success":       passed,
                "game_over":     True,
                "remaining_lives": max(0, remaining_lives - (0 if passed else 1)),
                "message":       message,
                **({"traceback": trace} if not passed else {})
            })

        return Response({
            "success":       False,
            "game_over":     False,
            "remaining_lives": remaining_lives - 1,
            "message":       message,
            "traceback":     trace,
        })


# =============================
# Debugging Game
# =============================

class StartDebugGame(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        session = GameSession.objects.create(
            session_id=str(uuid.uuid4()),
            user=user,
            game_type="debugging",
            status="active",
            time_limit=300,
        )

        questions = fetch_questions_for_game(user, "debugging", limit=1)
        if not questions:
            return Response({"error": "No questions available"}, status=400)

        question = questions[0]
        GameQuestion.objects.create(session=session, question=question)

        return Response({
            "session_id":    session.session_id,
            "prompt":        question.question_text,
            "function_name": question.game_data.get("function_name", ""),
            "sample_input":  question.game_data.get("sample_input", ""),
            "sample_output": question.game_data.get("sample_output", ""),
            "broken_code":   question.game_data.get("buggy_code", ""),
            "timer_seconds": session.time_limit,
        }, status=201)


class SubmitDebugGame(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = GameSession.objects.filter(
            session_id=session_id, user=request.user, status="active"
        ).first()
        if not session:
            return Response({"error": "Invalid or ended session."}, status=400)

        game_q = session.session_questions.first()
        question = game_q.question
        user_code = request.data.get("code")
        if not user_code:
            return Response({"error": "No code submitted."}, status=400)

        wrong = QuestionResponse.objects.filter(
            question=game_q, user=request.user, is_correct=False
        ).count()
        remaining_lives = 3 - wrong

        passed, message, traceback_str = run_user_code(
            user_code,
            question.game_data.get("function_name", ""),
            question.game_data.get("hidden_tests", [])
        )

        QuestionResponse.objects.create(
            question=game_q,
            user=request.user,
            user_answer=user_code,
            is_correct=passed,
            time_taken=0,
        )

        if passed or remaining_lives <= 1:
            session.status = "completed"
            session.total_score = 1 if passed else 0
            session.end_time = timezone.now()
            session.save()
            return Response({
                "success":       passed,
                "game_over":     True,
                "remaining_lives": max(0, remaining_lives - (0 if passed else 1)),
                "message":       message,
                **({"traceback": traceback_str} if not passed else {})
            })

        return Response({
            "success":       False,
            "game_over":     False,
            "remaining_lives": remaining_lives - 1,
            "message":       message,
            "traceback":     traceback_str,
        })


# =============================
# PreAssessment Submission
# =============================

class SubmitPreAssessmentAnswers(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        answers = data if isinstance(data, list) else data.get("answers", [])

        results = []
        correct_count = 0

        for ans in answers:
            try:
                q = PreAssessmentQuestion.objects.get(id=ans["question_id"])
                is_correct = q.correct_answer.strip().lower() == ans["user_answer"].strip().lower()
                results.append({
                    "question_id": q.id,
                    "question_text": q.question_text,
                    "user_answer": ans["user_answer"],
                    "correct_answer": q.correct_answer,
                    "is_correct": is_correct
                })
                if is_correct:
                    correct_count += 1
            except PreAssessmentQuestion.DoesNotExist:
                continue

        if request.user.is_authenticated:
            recalibrate_topic_proficiency(request.user, results)

        return Response({
            "total": len(answers),
            "correct": correct_count,
            "results": results
        })
