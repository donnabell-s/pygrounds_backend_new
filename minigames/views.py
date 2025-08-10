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
    CrosswordData
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



# class SubmitAnswers(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, session_id):
#         # local sanitizer for crossword/wordsearch
#         def _san(s: str) -> str:
#             # letters-only; strips spaces/symbols and uppercases
#             return re.sub(r'[^A-Za-z]', '', (s or '')).upper()
#             # If you want to allow digits too, use:
#             # return re.sub(r'[^A-Za-z0-9]', '', (s or '')).upper()

#         answers = request.data.get("answers", []) or []
#         session = GameSession.objects.filter(session_id=session_id, status="active").first()
#         if not session:
#             return Response({"error": "Invalid or inactive session"}, status=400)

#         # Build a map: submitted question_id -> payload
#         submitted_map = {int(a.get("question_id")): a for a in answers if "question_id" in a}

#         # Grab ALL questions in this session (placed-only for crossword/wordsearch)
#         session_gqs = list(GameQuestion.objects.filter(session=session).select_related("question"))

#         results = []
#         correct_count = 0

#         for game_q in session_gqs:
#             qid = game_q.id  # GameQuestion PK used by client
#             qobj = game_q.question

#             payload = submitted_map.get(qid)
#             if payload is None:
#                 # ❌ Not submitted → count as WRONG with empty answer
#                 user_answer_raw = ""
#                 is_correct = False
#                 time_taken = 0
#             else:
#                 user_answer_raw = payload.get("user_answer", "")
#                 time_taken = payload.get("time_taken", 0)

#                 # ✅ Normalize like the grid for crossword/wordsearch
#                 if session.game_type in ("crossword", "wordsearch"):
#                     user_norm = _san(user_answer_raw)
#                     correct_norm = _san(qobj.correct_answer or "")
#                 else:
#                     # other games keep simple text compare
#                     user_norm = (user_answer_raw or "").strip().lower()
#                     correct_norm = (qobj.correct_answer or "").strip().lower()

#                 is_correct = (user_norm == correct_norm)

#             if is_correct:
#                 correct_count += 1

#             # Persist the response (including unanswered-as-wrong)
#             QuestionResponse.objects.create(
#                 question=game_q,
#                 user=request.user,
#                 user_answer=user_answer_raw,
#                 is_correct=is_correct,
#                 time_taken=time_taken,
#             )

#             # Subtopic/topic mapping (from game_data)
#             gd = getattr(qobj, "game_data", {}) or {}
#             subtopic_ids = [s.get("id") for s in gd.get("subtopic_combination", []) if "id" in s]

#             from content_ingestion.models import Subtopic
#             topic_ids = list(
#                 Subtopic.objects.filter(id__in=subtopic_ids).values_list("topic_id", flat=True)
#             )

#             results.append({
#                 "question_id": qobj.id,
#                 "question_text": qobj.question_text,
#                 "user_answer": user_answer_raw,
#                 "correct_answer": qobj.correct_answer or "",
#                 "is_correct": bool(is_correct),
#                 "topic_ids": topic_ids,
#                 "subtopic_ids": subtopic_ids,
#                 "estimated_difficulty": (getattr(qobj, "estimated_difficulty", None) or None),
#                 "game_type": getattr(qobj, "game_type", None),
#                 "minigame_type": getattr(qobj, "minigame_type", None),
#             })

#         # Finish session
#         session.status = "completed"
#         session.total_score = correct_count
#         session.end_time = timezone.now()
#         session.save()

#         # Recalibrate with both answered and unanswered (as wrong)
#         try:
#             recalibrate_topic_proficiency(request.user, results)
#         except Exception as e:
#             print("Recalibration error:", e)

#         return Response({
#             "total": len(session_gqs),        # all placed questions
#             "answered": len(submitted_map),   # how many the user attempted
#             "correct": correct_count,
#             "results": results,
#             "score": correct_count
#         })

class SubmitAnswers(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        def _san(s: str) -> str:
            return re.sub(r'[^A-Za-z]', '', (s or '')).upper()

        answers = request.data.get("answers", []) or []
        session = GameSession.objects.filter(session_id=session_id, status="active").first()
        if not session:
            return Response({"error": "Invalid or inactive session"}, status=400)

        # Submitted map: GameQuestion.id -> payload
        submitted_map = {int(a.get("question_id")): a for a in answers if "question_id" in a}

        # All GQs for the session (we'll filter to eligible/placed)
        session_gqs = list(GameQuestion.objects.filter(session=session).select_related("question"))

        # Build eligible GameQuestion IDs from persisted placements
        eligible_ids = set()

        if session.game_type == "crossword":
            try:
                placements = session.crossword_data.placements
            except CrosswordData.DoesNotExist:
                placements = []
            # Prefer authoritative IDs saved at start
            ids = [p.get("game_question_id") for p in placements if p.get("game_question_id")]
            eligible_ids = set(int(i) for i in ids)

            # Fallback: if any placement lacks id (shouldn't happen), map by word
            if not eligible_ids and placements:
                word_to_gqid = {}
                for gq in session_gqs:
                    w = _san(gq.question.correct_answer or "")
                    if w and w not in word_to_gqid:
                        word_to_gqid[w] = gq.id
                for p in placements:
                    w = _san(p.get("word") or "")
                    if w in word_to_gqid:
                        eligible_ids.add(word_to_gqid[w])

        elif session.game_type == "wordsearch":
            try:
                data = session.wordsearch_data
                ws_placements = data.placements
            except WordSearchData.DoesNotExist:
                ws_placements = []

            word_to_gqid = {}
            for gq in session_gqs:
                w = _san(gq.question.correct_answer or "")
                if w and w not in word_to_gqid:
                    word_to_gqid[w] = gq.id

            for p in ws_placements:
                w = _san(p.get("word") or "")
                if w in word_to_gqid:
                    eligible_ids.add(word_to_gqid[w])

        else:
            # coding games: all questions are inherently placed
            eligible_ids = {gq.id for gq in session_gqs}

        # Evaluate ONLY eligible/placed questions
        results = []
        correct_count = 0

        for gq in session_gqs:
            if gq.id not in eligible_ids:
                continue

            q = gq.question
            payload = submitted_map.get(gq.id)

            if payload is None:
                ua, ok, t = "", False, 0
            else:
                ua, t = payload.get("user_answer", ""), payload.get("time_taken", 0)
                if session.game_type in ("crossword", "wordsearch"):
                    ok = _san(ua) == _san(q.correct_answer or "")
                else:
                    ok = (ua or "").strip().lower() == (q.correct_answer or "").strip().lower()

            if ok:
                correct_count += 1

            QuestionResponse.objects.create(
                question=gq,
                user=request.user,
                user_answer=ua,
                is_correct=ok,
                time_taken=t,
            )

            gd = getattr(q, "game_data", {}) or {}
            subtopic_ids = [s.get("id") for s in gd.get("subtopic_combination", []) if "id" in s]
            from content_ingestion.models import Subtopic
            topic_ids = list(Subtopic.objects.filter(id__in=subtopic_ids).values_list("topic_id", flat=True))

            results.append({
                "question_id": q.id,
                "question_text": q.question_text,
                "user_answer": ua,
                "correct_answer": q.correct_answer or "",
                "is_correct": bool(ok),
                "topic_ids": topic_ids,
                "subtopic_ids": subtopic_ids,
                "estimated_difficulty": getattr(q, "estimated_difficulty", None),
                "game_type": getattr(q, "game_type", None),
                "minigame_type": getattr(q, "minigame_type", None),
            })

        # Close session with placed-only totals
        session.status = "completed"
        session.total_score = correct_count
        session.end_time = timezone.now()
        session.save()

        try:
            recalibrate_topic_proficiency(request.user, results)
        except Exception as e:
            print("Recalibration error:", e)

        return Response({
            "total": len(eligible_ids),
            "answered": len({k for k in submitted_map.keys() if k in eligible_ids}),
            "correct": correct_count,
            "results": results,
            "score": correct_count
        })


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

# class StartCrosswordGame(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         user = request.user
#         question_count = int(request.data.get("question_count", 10))

#         session = GameSession.objects.create(
#             session_id=str(uuid.uuid4()),
#             user=user,
#             game_type="crossword",
#             status="active",
#             time_limit=300,
#         )

#         # 1️⃣ Fetch questions
#         questions = fetch_questions_for_game(user, "crossword", limit=question_count)

#         # 2️⃣ Prepare sanitized words
#         sanitized_map = {q.id: sanitize_word_for_grid(q.correct_answer) for q in questions}
#         words = [w for w in sanitized_map.values() if w]

#         # 3️⃣ Generate crossword
#         generator = CrosswordGenerator()
#         grid, placements = generator.generate(words)
#         grid_display = ["".join(row) for row in grid]

#         # 4️⃣ Determine which questions were actually placed
#         placed_words = {p.word for p in placements}
#         placed_questions = [q for q in questions if sanitized_map[q.id] in placed_words]

#         # 5️⃣ Only create GameQuestions for placed questions
#         GameQuestion.objects.bulk_create([
#             GameQuestion(session=session, question_id=q.id) for q in placed_questions
#         ])

#         # 6️⃣ Prepare placements with clues
#         placements_payload = []
#         for p in placements:
#             clue = next((q.question_text for q in placed_questions if sanitize_word_for_grid(q.correct_answer) == p.word), "")
#             placements_payload.append({
#                 "word":      p.word,
#                 "clue":      clue,
#                 "row":       p.row,
#                 "col":       p.col,
#                 "direction": p.direction,
#             })

#         return Response({
#             "session_id":    session.session_id,
#             "grid":          grid_display,
#             "placements":    placements_payload,
#             "questions":     LightweightQuestionSerializer(placed_questions, many=True).data,
#             "timer_seconds": session.time_limit,
#             "started_at":    session.start_time,
#         }, status=201)

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

        # 1) Fetch questions
        questions = fetch_questions_for_game(user, "crossword", limit=question_count)

        # 2) Sanitize words
        sanitized_map = {q.id: sanitize_word_for_grid(q.correct_answer) for q in questions}
        words = [w for w in sanitized_map.values() if w]

        # 3) Generate crossword once
        generator = CrosswordGenerator()
        grid, placements = generator.generate(words)
        grid_display = ["".join(row) for row in grid]

        # 4) Keep only placed questions
        placed_words = {p.word for p in placements}
        placed_questions = [q for q in questions if sanitized_map[q.id] in placed_words]

        # 5) Create GameQuestions only for placed questions
        GameQuestion.objects.bulk_create([
            GameQuestion(session=session, question_id=q.id) for q in placed_questions
        ])

        # 6) Map placed word -> GameQuestion.id (first match wins)
        word_to_gqid = {}
        for gq in session.session_questions.select_related("question").all():
            w = sanitize_word_for_grid(gq.question.correct_answer)
            if w and w not in word_to_gqid:
                word_to_gqid[w] = gq.id

        # 7) Persist placements with clue + game_question_id
        stored_placements = []
        for p in placements:
            clue = next((q.question_text for q in placed_questions
                         if sanitize_word_for_grid(q.correct_answer) == p.word), "")
            stored_placements.append({
                "word": p.word,
                "clue": clue,
                "row": p.row,
                "col": p.col,
                "direction": p.direction,
                "game_question_id": word_to_gqid.get(p.word)
            })

        CrosswordData.objects.create(
            session=session,
            grid=grid_display,
            placements=stored_placements
        )

        return Response({
            "session_id":    session.session_id,
            "grid":          grid_display,
            "placements":    stored_placements,
            "questions":     LightweightQuestionSerializer(placed_questions, many=True).data,
            "timer_seconds": session.time_limit,
            "started_at":    session.start_time,
        }, status=201)


# class GetCrosswordGrid(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, session_id):
#         session = GameSession.objects.filter(
#             session_id=session_id, game_type="crossword"
#         ).first()
#         if not session:
#             return Response({"error": "Session not found"}, status=404)

#         # Only questions that were actually saved for this session (i.e., placed at start)
#         gqs = list(session.session_questions.select_related("question").all())
#         questions = [gq.question for gq in gqs]

#         # Prepare sanitized words from these questions
#         words = [sanitize_word_for_grid(q.correct_answer) for q in questions]
#         words = [w for w in words if w]  # drop blanks

#         # Re-generate board for these words
#         generator = CrosswordGenerator()
#         grid, placements = generator.generate(words)
#         grid_display = ["".join(row) for row in grid]

#         # Build mapping from sanitized word -> GameQuestion.id (first match wins)
#         word_to_gqid = {}
#         for gq in gqs:
#             w = sanitize_word_for_grid(gq.question.correct_answer)
#             if w and w not in word_to_gqid:
#                 word_to_gqid[w] = gq.id

#         # Build response: each placement carries its clue and game_question_id
#         payload_placements = []
#         for p in placements:
#             clue = next(
#                 (q.question_text for q in questions if sanitize_word_for_grid(q.correct_answer) == p.word),
#                 ""
#             )
#             payload_placements.append({
#                 "word": p.word,
#                 "clue": clue,
#                 "row": p.row,
#                 "col": p.col,
#                 "direction": p.direction,
#                 "game_question_id": word_to_gqid.get(p.word),
#             })

#         return Response({
#             "grid": grid_display,
#             "placements": payload_placements
#         })

class GetCrosswordGrid(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = GameSession.objects.filter(
            session_id=session_id, game_type="crossword"
        ).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)

        try:
            data = session.crossword_data
        except CrosswordData.DoesNotExist:
            return Response({"error": "Grid not generated yet."}, status=400)

        return Response({
            "grid": data.grid,
            "placements": data.placements
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


# class SubmitHangmanCode(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, session_id):
#         session = GameSession.objects.filter(
#             session_id=session_id, user=request.user, status="active"
#         ).first()
#         if not session:
#             return Response({"error": "Invalid or ended session."}, status=400)

#         game_q = session.session_questions.first()
#         question = game_q.question
#         user_code = request.data.get("code")
#         if not user_code:
#             return Response({"error": "No code submitted."}, status=400)

#         wrong = QuestionResponse.objects.filter(
#             question=game_q, user=request.user, is_correct=False
#         ).count()
#         remaining_lives = 3 - wrong

#         passed, message, trace = run_user_code(
#             user_code,
#             question.game_data.get("function_name", ""),
#             question.game_data.get("hidden_tests", [])
#         )

#         QuestionResponse.objects.create(
#             question=game_q,
#             user=request.user,
#             user_answer=user_code,
#             is_correct=passed,
#             time_taken=0,
#         )

#         # ✅ Build results for recalibration
#         gd = getattr(question, "game_data", {}) or {}
#         subtopic_ids = [s["id"] for s in gd.get("subtopic_combination", [])]
#         from content_ingestion.models import Subtopic
#         topic_ids = list(
#             Subtopic.objects.filter(id__in=subtopic_ids).values_list("topic_id", flat=True)
#         )
#         results = [{
#             "question_id": question.id,
#             "question_text": question.question_text,
#             "user_answer": "<code-submission>",
#             "correct_answer": question.correct_answer or "",
#             "is_correct": passed,
#             "topic_ids": topic_ids,
#             "subtopic_ids": subtopic_ids,
#         }]

#         if passed or remaining_lives <= 1:
#             session.status = "completed"
#             session.total_score = 1 if passed else 0
#             session.end_time = timezone.now()
#             session.save()

#             # ✅ Trigger recalibration on game over
#             recalibrate_topic_proficiency(request.user, results)

#             return Response({
#                 "success": passed,
#                 "game_over": True,
#                 "remaining_lives": max(0, remaining_lives - (0 if passed else 1)),
#                 "message": message,
#                 **({"traceback": trace} if not passed else {})
#             })

#         return Response({
#             "success": False,
#             "game_over": False,
#             "remaining_lives": remaining_lives - 1,
#             "message": message,
#             "traceback": trace,
#         })

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

        # Lives BEFORE this submission
        wrong_before = QuestionResponse.objects.filter(
            question=game_q, user=request.user, is_correct=False
        ).count()
        remaining_lives_before = 3 - wrong_before

        passed, message, trace = run_user_code(
            user_code,
            question.game_data.get("function_name", ""),
            question.game_data.get("hidden_tests", [])
        )

        # Save this attempt
        QuestionResponse.objects.create(
            question=game_q,
            user=request.user,
            user_answer=user_code,
            is_correct=passed,
            time_taken=0,
        )

        # Recompute lives AFTER recording this attempt
        wrong_after = QuestionResponse.objects.filter(
            question=game_q, user=request.user, is_correct=False
        ).count()
        remaining_lives_after = max(0, 3 - wrong_after)

        game_over = passed or remaining_lives_after == 0

        if game_over:
            session.status = "completed"
            session.total_score = 1 if passed else 0
            session.end_time = timezone.now()
            session.save()

            # Build FULL history of attempts for this session (all tries)
            attempts = list(
                QuestionResponse.objects
                .filter(question=game_q, user=request.user)
                .order_by('answered_at')
                .values('is_correct', 'user_answer')
            )

            # Map subtopics/topics (from game_data)
            gd = getattr(question, "game_data", {}) or {}
            subtopic_ids = [s.get("id") for s in gd.get("subtopic_combination", []) if "id" in s]
            from content_ingestion.models import Subtopic
            topic_ids = list(Subtopic.objects.filter(id__in=subtopic_ids).values_list("topic_id", flat=True))

            # Convert every attempt into an engine event (coding game_type for weighting)
            results = []
            for att in attempts:
                results.append({
                    "question_id": question.id,
                    "question_text": question.question_text,
                    "user_answer": "<code-submission>",
                    "correct_answer": question.correct_answer or "",
                    "is_correct": bool(att["is_correct"]),
                    "topic_ids": topic_ids,
                    "subtopic_ids": subtopic_ids,
                    "estimated_difficulty": getattr(question, "estimated_difficulty", None),
                    "game_type": "coding",
                    "minigame_type": "hangman",
                })

            # Recalibrate with ALL attempts (so fails are fully counted)
            try:
                recalibrate_topic_proficiency(request.user, results)
            except Exception as e:
                print("Recalibration error (hangman):", e)

        return Response({
            "success": passed,
            "game_over": game_over,
            "remaining_lives": remaining_lives_after,
            "message": message,
            **({"traceback": trace} if not passed else {})
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


# class SubmitDebugGame(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, session_id):
#         session = GameSession.objects.filter(
#             session_id=session_id, user=request.user, status="active"
#         ).first()
#         if not session:
#             return Response({"error": "Invalid or ended session."}, status=400)

#         game_q = session.session_questions.first()
#         question = game_q.question
#         user_code = request.data.get("code")
#         if not user_code:
#             return Response({"error": "No code submitted."}, status=400)

#         wrong = QuestionResponse.objects.filter(
#             question=game_q, user=request.user, is_correct=False
#         ).count()
#         remaining_lives = 3 - wrong

#         passed, message, traceback_str = run_user_code(
#             user_code,
#             question.game_data.get("function_name", ""),
#             question.game_data.get("hidden_tests", [])
#         )

#         QuestionResponse.objects.create(
#             question=game_q,
#             user=request.user,
#             user_answer=user_code,
#             is_correct=passed,
#             time_taken=0,
#         )

#         # ✅ Prepare results for recalibration
#         gd = getattr(question, "game_data", {}) or {}
#         subtopic_ids = [s["id"] for s in gd.get("subtopic_combination", [])]

#         from content_ingestion.models import Subtopic
#         topic_ids = list(
#             Subtopic.objects.filter(id__in=subtopic_ids).values_list("topic_id", flat=True)
#         )

#         results = [{
#             "question_id": question.id,
#             "question_text": question.question_text,
#             "user_answer": "<code-submission>",
#             "correct_answer": question.correct_answer or "",
#             "is_correct": passed,
#             "topic_ids": topic_ids,
#             "subtopic_ids": subtopic_ids,
#         }]

#         # ✅ Handle game over
#         if passed or remaining_lives <= 1:
#             session.status = "completed"
#             session.total_score = 1 if passed else 0
#             session.end_time = timezone.now()
#             session.save()

#             # ✅ Trigger recalibration on game over
#             try:
#                 recalibrate_topic_proficiency(request.user, results)
#             except Exception as e:
#                 print("Recalibration error:", e)

#             return Response({
#                 "success": passed,
#                 "game_over": True,
#                 "remaining_lives": max(0, remaining_lives - (0 if passed else 1)),
#                 "message": message,
#                 **({"traceback": traceback_str} if not passed else {})
#             })

#         # ✅ Not game over yet
#         return Response({
#             "success": False,
#             "game_over": False,
#             "remaining_lives": remaining_lives - 1,
#             "message": message,
#             "traceback": traceback_str,
#         })

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

        wrong_before = QuestionResponse.objects.filter(
            question=game_q, user=request.user, is_correct=False
        ).count()
        remaining_lives_before = 3 - wrong_before

        passed, message, traceback_str = run_user_code(
            user_code,
            question.game_data.get("function_name", ""),
            question.game_data.get("hidden_tests", [])
        )

        # Save this attempt
        QuestionResponse.objects.create(
            question=game_q,
            user=request.user,
            user_answer=user_code,
            is_correct=passed,
            time_taken=0,
        )

        # Lives AFTER this attempt
        wrong_after = QuestionResponse.objects.filter(
            question=game_q, user=request.user, is_correct=False
        ).count()
        remaining_lives_after = max(0, 3 - wrong_after)

        game_over = passed or remaining_lives_after == 0

        if game_over:
            session.status = "completed"
            session.total_score = 1 if passed else 0
            session.end_time = timezone.now()
            session.save()

            # Build FULL history
            attempts = list(
                QuestionResponse.objects
                .filter(question=game_q, user=request.user)
                .order_by('answered_at')
                .values('is_correct', 'user_answer')
            )

            gd = getattr(question, "game_data", {}) or {}
            subtopic_ids = [s.get("id") for s in gd.get("subtopic_combination", []) if "id" in s]
            from content_ingestion.models import Subtopic
            topic_ids = list(Subtopic.objects.filter(id__in=subtopic_ids).values_list("topic_id", flat=True))

            results = []
            for att in attempts:
                results.append({
                    "question_id": question.id,
                    "question_text": question.question_text,
                    "user_answer": "<code-submission>",
                    "correct_answer": question.correct_answer or "",
                    "is_correct": bool(att["is_correct"]),
                    "topic_ids": topic_ids,
                    "subtopic_ids": subtopic_ids,
                    "estimated_difficulty": getattr(question, "estimated_difficulty", None),
                    "game_type": "coding",
                    "minigame_type": "debugging",
                })

            try:
                recalibrate_topic_proficiency(request.user, results)
            except Exception as e:
                print("Recalibration error (debugging):", e)

        return Response({
            "success": passed,
            "game_over": game_over,
            "remaining_lives": remaining_lives_after,
            "message": message,
            **({"traceback": traceback_str} if not passed else {})
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
