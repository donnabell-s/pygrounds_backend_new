from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import GameSession, Question, GameQuestion, QuestionResponse, WordSearchData, HangmanData
from .serializers import GameSessionSerializer, QuestionResponseSerializer
from .game_logic.crossword import CrosswordGenerator
from .game_logic.wordsearch import WordSearchGenerator
from .game_logic.hangman import run_user_code
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

        # Save the matrix and placements
        WordSearchData.objects.create(
            session=session,
            matrix=["".join(row) for row in matrix],
            placements=[
                {"word": p.word, "row": p.row, "col": p.col, "direction": p.direction}
                for p in placements
            ]
        )

        return Response({
            "session_id": session.session_id,
            "matrix": ["".join(row) for row in matrix],
            "placements": [
                {"word": p.word, "row": p.row, "col": p.col, "direction": p.direction}
                for p in placements
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

        try:
            data = session.wordsearch_data  # from OneToOneField
        except WordSearchData.DoesNotExist:
            return Response({"error": "Matrix not generated yet."}, status=400)

        return Response({
            "matrix": data.matrix,
            "placements": data.placements
        })

# =============================
# Hangman Game-Specific Views
# =============================

STATIC_HANGMAN_QUESTIONS = [
    {
        "text": "Write a function `reverse_string(s)` that returns the reversed string.",
        "function_name": "reverse_string",
        "sample_input": "('hello',)",
        "sample_output": "'olleh'",
        "hidden_tests": [
            {"input": "('hello',)", "output": "olleh"},
            {"input": "('world',)", "output": "dlrow"},
            {"input": "('Python',)", "output": "nohtyP"},
        ],
        "difficulty": "easy",
    },
    {
        "text": "Write a function `is_even(n)` that returns True if a number is even.",
        "function_name": "is_even",
        "sample_input": "(4,)",
        "sample_output": "True",
        "hidden_tests": [
            {"input": "(4,)", "output": True},
            {"input": "(5,)", "output": False},
            {"input": "(0,)", "output": True},
        ],
        "difficulty": "easy",
    },
]


class StartHangmanGame(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import random
        user = request.user
        data = random.choice(STATIC_HANGMAN_QUESTIONS)

        # Create Question instance dynamically
        question = Question.objects.create(
            text=data["text"],
            function_name=data["function_name"],
            sample_input=data["sample_input"],
            sample_output=data["sample_output"],
            hidden_tests=data["hidden_tests"],
            difficulty=data["difficulty"],
            source_type="hangman",
        )

        # Create session and link question
        session = GameSession.objects.create(
            session_id=str(uuid.uuid4()),
            user=user,
            game_type='hangman',
            status='active',
            time_limit=300
        )
        GameQuestion.objects.create(session=session, question=question)

        return Response({
            "session_id": session.session_id,
            "prompt": question.text,
            "function_name": question.function_name,
            "sample_input": question.sample_input,
            "sample_output": question.sample_output,
            "timer_seconds": session.time_limit
        }, status=201)


class SubmitHangmanCode(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        from .game_logic.hangman import run_user_code

        session = GameSession.objects.filter(session_id=session_id, user=request.user).first()
        if not session or session.status != "active":
            return Response({"error": "Invalid or ended session."}, status=400)

        game_question = session.session_questions.first()
        if not game_question:
            return Response({"error": "No question linked to session."}, status=400)
        question = game_question.question

        user_code = request.data.get("code")
        if not user_code:
            return Response({"error": "No code submitted."}, status=400)

        # Count previous incorrect attempts
        incorrect_attempts = QuestionResponse.objects.filter(
            question=game_question,
            user=request.user,
            is_correct=False
        ).count()
        remaining_lives = 3 - incorrect_attempts

        # Run user code
        passed, message, trace = run_user_code(user_code, question.function_name, question.hidden_tests)

        # Record this attempt
        QuestionResponse.objects.create(
            question=game_question,
            user=request.user,
            user_answer=user_code,
            is_correct=passed,
            time_taken=0
        )

        if passed:
            session.status = "completed"
            session.total_score = 1
            session.end_time = timezone.now()
            session.save()
            return Response({
                "success": True,
                "game_over": True,
                "remaining_lives": remaining_lives,
                "message": message
            })

        if remaining_lives <= 1:
            session.status = "completed"
            session.end_time = timezone.now()
            session.save()
            return Response({
                "success": False,
                "game_over": True,
                "remaining_lives": 0,
                "message": message,
                "traceback": trace
            })

        return Response({
            "success": False,
            "game_over": False,
            "remaining_lives": remaining_lives - 1,
            "message": message,
            "traceback": trace
        })
