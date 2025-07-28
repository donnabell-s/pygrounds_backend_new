# views.py

import uuid
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from question_generation.models import PreAssessmentQuestion
from question_generation.serializers import PreAssessmentQuestionSerializer

from question_generation.models import PreAssessmentQuestion
from user_learning.adaptive_engine import recalibrate_topic_proficiency

from .game_logic.crossword import CrosswordGenerator
from .game_logic.wordsearch import WordSearchGenerator
from .game_logic.hangman import run_user_code
from .models import (
    GameSession,
    Question,
    GameQuestion,
    QuestionResponse,
    WordSearchData,
)
from .serializers import GameSessionSerializer, QuestionResponseSerializer


# =============================
# Generic Session Views (shared across games)
# =============================

class StartGameSession(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        game_type = request.data.get("game_type")
        question_count = int(request.data.get("question_count", 5))

        # 1) create session
        session = GameSession.objects.create(
            session_id=str(uuid.uuid4()),
            user=user,
            game_type=game_type,
            status="active",
        )

        # 2) pick pre-seeded questions for that game
        questions = Question.objects.filter(game_type=game_type).order_by("?")[:question_count]
        GameQuestion.objects.bulk_create([
            GameQuestion(session=session, question=q)
            for q in questions
        ])

        # 3) return session info
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
                game_q.question.answer.strip().lower()
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
# Crossword Game-Specific Views
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

        # pull from seeded questions
        questions = list(
            Question.objects.filter(game_type="crossword")
            .order_by("?")[:question_count]
        )
        GameQuestion.objects.bulk_create([
            GameQuestion(session=session, question=q) for q in questions
        ])

        # generate grid
        generator = CrosswordGenerator()
        words = [q.answer.upper() for q in questions]
        grid, placements = generator.generate(words)
        grid_display = ["".join(row) for row in grid]

        # build placements payload
        placements_payload = []
        for p in placements:
            clue = next((q.text for q in questions if q.answer.upper() == p.word), "")
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
        generator = CrosswordGenerator()
        words = [q.answer.upper() for q in questions]
        grid, placements = generator.generate(words)
        grid_display = ["".join(row) for row in grid]

        return Response({
            "grid":       grid_display,
            "placements": [
                {
                    "word":      p.word,
                    "clue":      next((q.text for q in questions if q.answer.upper() == p.word), ""),
                    "row":       p.row,
                    "col":       p.col,
                    "direction": p.direction,
                } for p in placements
            ]
        })


# =============================
# WordSearch Game-Specific Views
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

        questions = list(
            Question.objects.filter(game_type="wordsearch")
            .order_by("?")[:question_count]
        )
        GameQuestion.objects.bulk_create([
            GameQuestion(session=session, question=q) for q in questions
        ])

        words = [q.answer.upper() for q in questions]
        generator = WordSearchGenerator()
        matrix, placements = generator.generate(words)

        # persist matrix & placements
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

        return Response({
            "matrix":     data.matrix,
            "placements": data.placements
        })


# =============================
# Hangman Game-Specific Views
# =============================

class StartHangmanGame(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        # pick one pre-seeded hangman question
        question = Question.objects.filter(game_type="hangman").order_by("?").first()
        session = GameSession.objects.create(
            session_id=str(uuid.uuid4()),
            user=user,
            game_type="hangman",
            status="active",
            time_limit=300,
        )
        GameQuestion.objects.create(session=session, question=question)

        return Response({
            "session_id":    session.session_id,
            "prompt":        question.text,
            "function_name": question.function_name,
            "sample_input":  question.sample_input,
            "sample_output": question.sample_output,
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

        # track lives
        wrong = QuestionResponse.objects.filter(
            question=game_q, user=request.user, is_correct=False
        ).count()
        remaining_lives = 3 - wrong

        # run and record
        passed, message, trace = run_user_code(user_code, question.function_name, question.hidden_tests)
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
# Debugging Game-Specific Views
# =============================

class StartDebugGame(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        # pick one pre-seeded debugging question
        question = Question.objects.filter(game_type="debugging").order_by("?").first()
        session = GameSession.objects.create(
            session_id=str(uuid.uuid4()),
            user=user,
            game_type="debugging",
            status="active",
            time_limit=300,
        )
        GameQuestion.objects.create(session=session, question=question)

        return Response({
            "session_id":    session.session_id,
            "prompt":        question.text,
            "function_name": question.function_name,
            "sample_input":  question.sample_input,
            "sample_output": question.sample_output,
            "broken_code":   question.broken_code,
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

        passed, message, traceback = run_user_code(user_code, question.function_name, question.hidden_tests)
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
                **({"traceback": traceback} if not passed else {})
            })

        return Response({
            "success":       False,
            "game_over":     False,
            "remaining_lives": remaining_lives - 1,
            "message":       message,
            "traceback":     traceback,
        })


# =============================
# PreAssessment Views
# =============================

class SubmitPreAssessmentAnswers(APIView):
    permission_classes = [AllowAny]  # if unauthenticated users can submit

    def post(self, request):
        data = request.data
        if isinstance(data, list):
            answers = data
        else:
            answers = data.get("answers", [])

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

        recalibrate_topic_proficiency(request.user, results)

        return Response({
            "total": len(answers),
            "correct": correct_count,
            "results": results
        })