from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import GameSession, Question, GameQuestion, QuestionResponse
from .serializers import GameSessionSerializer, QuestionResponseSerializer
from .game_logic.crossword import CrosswordGenerator
from .game_logic.wordsearch import WordSearchGenerator
import uuid


# =============================
# Generic Session Views (shared across games)
# =============================

class StartGameSession(APIView):
    def post(self, request):
        user = request.user
        game_type = request.data.get("game_type")
        question_count = int(request.data.get("question_count", 5))

        session = GameSession.objects.create(
            session_id=str(uuid.uuid4()),
            user=user,
            game_type=game_type,
            status='active',
        )

        questions = Question.objects.order_by('?')[:question_count]
        for q in questions:
            GameQuestion.objects.create(session=session, question=q)

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

    # Accept session_id from the URL
    def post(self, request, session_id):
        answers = request.data.get("answers", [])

        # Look up the active session by its session_id
        session = GameSession.objects.filter(
            session_id=session_id,
            status="active"
        ).first()
        if not session:
            return Response(
                {"error": "Invalid or inactive session"},
                status=400
            )

        score = 0
        for ans in answers:
            try:
                game_q = GameQuestion.objects.get(
                    id=ans["question_id"],
                    session=session
                )
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
                    time_taken=ans.get("time_taken", 0)
                )
            except GameQuestion.DoesNotExist:
                continue

        # Mark session completed & save score
        session.status = "completed"
        session.total_score = score
        session.end_time = timezone.now()
        session.save()

        return Response(
            {"message": "Answers submitted", "score": score}
        )

@api_view(['POST'])
def exit_session(request, session_id):  # ✅ receive it from URL
    session = GameSession.objects.filter(session_id=session_id, status='active').first()

    if session:
        session.status = 'expired'
        session.end_time = timezone.now()
        session.save()
        return Response({"message": "Session marked as expired."})
    
    return Response({"error": "Session not found or already ended."}, status=400)


class GetSessionResponses(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = GameSession.objects.filter(session_id=session_id).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)

        responses = QuestionResponse.objects.filter(question__session=session, user=request.user)
        return Response(QuestionResponseSerializer(responses, many=True).data)


# =============================
# Crossword Game-Specific Views
# =============================

STATIC_CROSSWORD_QUESTIONS = [
    {"text": "A popular programming language.", "answer": "python", "difficulty": "easy"},
    {"text": "Immutable sequence in Python.", "answer": "tuple", "difficulty": "medium"},
    {"text": "A sequence of characters.", "answer": "string", "difficulty": "easy"},
    {"text": "Used to define a block of code.", "answer": "indentation", "difficulty": "medium"},
    {"text": "Structure that holds key-value pairs.", "answer": "dictionary", "difficulty": "medium"},
    {"text": "Loop that repeats while a condition is true.", "answer": "while", "difficulty": "easy"},
    {"text": "Keyword to define a function.", "answer": "def", "difficulty": "easy"},
    {"text": "Error found during execution.", "answer": "exception", "difficulty": "medium"},
    {"text": "Code block used to test and handle errors.", "answer": "try", "difficulty": "medium"},
    {"text": "Built-in function to get length of a list.", "answer": "len", "difficulty": "easy"},
]


class StartCrosswordGame(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        session = GameSession.objects.create(
            session_id=str(uuid.uuid4()),
            user=user,
            game_type='crossword',
            status='active',
            time_limit=300
        )

        question_objs = []
        for q in STATIC_CROSSWORD_QUESTIONS:
            question = Question.objects.create(
                text=q["text"],
                answer=q["answer"].upper(),
                difficulty=q["difficulty"]
            )
            GameQuestion.objects.create(session=session, question=question)
            question_objs.append(question)

        generator = CrosswordGenerator()
        words = [q.answer.upper() for q in question_objs]
        grid, placements = generator.generate(words)
        grid_display = [''.join(row) for row in grid]

        return Response({
            "session_id": session.session_id,
            "grid": grid_display,
            "placements": [
                {
                    "word": p.word,
                    "clue": next((q.text for q in question_objs if q.answer.upper() == p.word), ""),
                    "row": p.row,
                    "col": p.col,
                    "direction": p.direction
                } for p in placements
            ],
            "timer_seconds": session.time_limit,
            "started_at": session.start_time
        }, status=201)


class GetCrosswordGrid(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = GameSession.objects.filter(session_id=session_id, game_type="crossword").first()
        if not session:
            return Response({"error": "Session not found"}, status=404)

        questions = [gq.question for gq in session.session_questions.all()]
        generator = CrosswordGenerator()
        words = [q.answer.upper() for q in questions]
        grid, placements = generator.generate(words)
        grid_display = [''.join(row) for row in grid]

        return Response({
            "grid": grid_display,
            "placements": [
                {
                    "word": p.word,
                    "clue": next((q.text for q in questions if q.answer.upper() == p.word), ""),
                    "row": p.row,
                    "col": p.col,
                    "direction": p.direction
                } for p in placements
            ]
        })


# =============================
# WordSearch Game-Specific Views
# =============================

dummy_questions = [
    {"text": "A popular programming language.", "answer": "python", "difficulty": "easy"},
    {"text": "A sequence of characters.", "answer": "string", "difficulty": "easy"},
    {"text": "Immutable list in Python.", "answer": "tuple", "difficulty": "medium"},
]


class StartWordSearchGame(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        session = GameSession.objects.create(
            session_id=str(uuid.uuid4()),
            user=user,
            game_type='wordsearch',
            status='active',
            time_limit=300
        )

        question_objs = []
        for q in dummy_questions:
            question = Question.objects.create(
                text=q["text"],
                answer=q["answer"].upper(),
                difficulty=q["difficulty"]
            )
            GameQuestion.objects.create(session=session, question=question)
            question_objs.append(question)

        words = [q.answer.upper() for q in question_objs]
        generator = WordSearchGenerator()
        matrix, placements = generator.generate(words)

        return Response({
            "session_id": session.session_id,
            "matrix": ["".join(row) for row in matrix],
            "placements": [
                {
                    "word": p.word,
                    "row": p.row,
                    "col": p.col,
                    "direction": p.direction
                } for p in placements
            ],
            "timer_seconds": session.time_limit,
            "started_at": session.start_time
        }, status=201)


class GetWordSearchMatrix(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = GameSession.objects.filter(session_id=session_id, game_type="wordsearch").first()
        if not session:
            return Response({"error": "Session not found"}, status=404)

        questions = [gq.question for gq in session.session_questions.all()]
        words = [q.answer.upper() for q in questions]
        generator = WordSearchGenerator()
        matrix, placements = generator.generate(words)

        return Response({
            "matrix": ["".join(row) for row in matrix],
            "placements": [
                {
                    "word": p.word,
                    "row": p.row,
                    "col": p.col,
                    "direction": p.direction
                } for p in placements
            ]
        })
