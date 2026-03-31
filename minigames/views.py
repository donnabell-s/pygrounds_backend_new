import uuid
import re
from collections import defaultdict
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from question_generation.models import PreAssessmentQuestion
from user_learning.adaptive_engine import recalibrate_topic_proficiency
from user_learning.clustering import assign_learner_cluster, get_cluster_name, get_cluster_mastery_default
from user_learning.models import UserAbility, UserSubtopicMastery, UserTopicProficiency, UserZoneProgress
from content_ingestion.models import Topic, Subtopic, GameZone
from analytics.event_logger import log_question_event


from .game_logic.crossword import CrosswordGenerator
from .game_logic.wordsearch import WordSearchGenerator
from .game_logic.hangman import run_user_code
from .models import (
    GameSession,
    GameQuestion,
    QuestionResponse,
    WordSearchData,
    CrosswordData,
    PreAssessmentResponse,
)
from .serializers import GameSessionSerializer, QuestionResponseSerializer, LightweightQuestionSerializer
from .question_fetching import fetch_questions_for_game
from .serializers import LeaderboardEntrySerializer
from django.db.models import F, Min, Max, Count, Avg, Sum, Q


def extract_topic_subtopic_ids(question):

    if hasattr(question, 'topic_ids') and hasattr(question, 'subtopic_ids'):

        topic_ids = list(question.topic_ids) if question.topic_ids else []
        subtopic_ids = list(question.subtopic_ids) if question.subtopic_ids else []
    elif hasattr(question, 'topic') and hasattr(question, 'subtopic'):

        topic_ids = [question.topic.id] if question.topic else []
        subtopic_ids = [question.subtopic.id] if question.subtopic else []
    else:
 
        gd = getattr(question, "game_data", {}) or {}
        subtopic_ids = [s.get("id") for s in gd.get("subtopic_combination", []) if "id" in s]
        from content_ingestion.models import Subtopic
        topic_ids = list(Subtopic.objects.filter(id__in=subtopic_ids).values_list("topic_id", flat=True))
    
    return topic_ids, subtopic_ids

def sanitize_word_for_grid(word: str) -> str:
    if not word:
        return ""
    return re.sub(r'[^A-Za-z]', '', word).upper()


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
            GameQuestion(session=session, question=q)
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
        print(f"SubmitAnswers called for session {session_id}")
        print(f"User: {request.user}")
        print(f"Request data: {request.data}")
        
        def _san(s: str) -> str:
            return re.sub(r'[^A-Za-z]', '', (s or '')).upper()

        answers = request.data.get("answers", []) or []
        session = GameSession.objects.filter(session_id=session_id, status="active").first()
        if not session:
            return Response({"error": "Invalid or inactive session"}, status=400)

        submitted_map = {int(a.get("question_id")): a for a in answers if "question_id" in a}
        session_gqs = list(GameQuestion.objects.filter(session=session).select_related("question", "question__topic", "question__subtopic"))

        eligible_ids = set()

        if session.game_type == "crossword":
            try:
                placements = session.crossword_data.placements
            except CrosswordData.DoesNotExist:
                placements = []
            ids = [p.get("game_question_id") for p in placements if p.get("game_question_id")]
            eligible_ids = set(int(i) for i in ids)

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
            eligible_ids = {gq.id for gq in session_gqs}

        results = []
        correct_count = 0

        for gq in session_gqs:
            if gq.id not in eligible_ids:
                continue

            q = gq.question
            payload = submitted_map.get(gq.id)

            if payload is None:
                ua, ok = "", False
            else:
                ua = payload.get("user_answer", "")
                if session.game_type in ("crossword", "wordsearch"):
                    ok = _san(ua) == _san(q.correct_answer or "")
                else:
                    ok = (ua or "").strip().lower() == (q.correct_answer or "").strip().lower()

            if ok:
                correct_count += 1

            log_question_event(
                user=request.user,
                game_question=gq,
                user_answer=ua,
                is_correct=ok,
                time_taken=0,
            )
            from analytics.helpers.theta_updater import update_user_theta
            update_user_theta(request.user.id)



            # Extract topic and subtopic IDs
            topic_ids, subtopic_ids = extract_topic_subtopic_ids(q)
            print(f"🔍 Question {q.id}: topic_ids={topic_ids}, subtopic_ids={subtopic_ids}")

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

        session.status = "completed"
        session.total_score = correct_count
        session.end_time = timezone.now()
        session.save()

        total_elapsed = 0.0
        if session.start_time and session.end_time:
            total_elapsed = (session.end_time - session.start_time).total_seconds()

        if results:
            results[0]["minigame_time_taken"] = total_elapsed
            results[0]["time_limit"] = session.time_limit

        try:
            print(f"Attempting to recalibrate topic proficiency for crossword...")
            print(f"User: {request.user}")
            print(f"Results data: {results}")
            recalibrate_topic_proficiency(request.user, results)
            print("Recalibration completed successfully!")
        except Exception as e:
            import traceback
            print(f"Recalibration error (crossword): {e}")
            print(f"Error type: {type(e)}")
            print(f"Traceback:")
            traceback.print_exc()
            print(f"User data: {request.user}")
            print(f"Results data: {results}")

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
        sanitized_map = {q.id: sanitize_word_for_grid(q.correct_answer) for q in questions}
        words = [w for w in sanitized_map.values() if w]

        generator = CrosswordGenerator()
        grid, placements = generator.generate(words)
        grid_display = ["".join(row) for row in grid]

        placed_words = {p.word for p in placements}
        placed_questions = [q for q in questions if sanitized_map[q.id] in placed_words]

        GameQuestion.objects.bulk_create([
            GameQuestion(session=session, question=q) for q in placed_questions
        ])

        word_to_gqid = {}
        for gq in session.session_questions.select_related("question").all():
            w = sanitize_word_for_grid(gq.question.correct_answer)
            if w and w not in word_to_gqid:
                word_to_gqid[w] = gq.id

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

        questions = fetch_questions_for_game(user, "wordsearch", limit=question_count)
        sanitized_map = {q.id: sanitize_word_for_grid(q.correct_answer) for q in questions}
        words = [w for w in sanitized_map.values() if w]

        generator = WordSearchGenerator()
        matrix, placements = generator.generate(words)

        placed_words = {p.word for p in placements}
        placed_questions = [q for q in questions if sanitized_map[q.id] in placed_words]

        GameQuestion.objects.bulk_create([
            GameQuestion(session=session, question=q) for q in placed_questions
        ])

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

        wrong_before = QuestionResponse.objects.filter(
            question=game_q, user=request.user, is_correct=False
        ).count()
        remaining_lives_before = 3 - wrong_before

        passed, message, trace = run_user_code(
            user_code,
            question.game_data.get("function_name", ""),
            question.game_data.get("hidden_tests", [])
        )

        attempt_number = wrong_before + 1
        log_question_event(
            user=request.user,
            game_question=game_q,
            user_answer=user_code,
            is_correct=passed,
            time_taken=0,
            attempt_number=attempt_number,
        )
        from analytics.helpers.theta_updater import update_user_theta
        update_user_theta(request.user.id)




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

            attempts = list(
                QuestionResponse.objects
                .filter(question=game_q, user=request.user)
                .order_by('answered_at')
                .values('is_correct', 'user_answer')
            )

            # Extract topic and subtopic IDs
            topic_ids, subtopic_ids = extract_topic_subtopic_ids(question)
            print(f"🔍 Hangman Question {question.id}: topic_ids={topic_ids}, subtopic_ids={subtopic_ids}")

            results = []
            total_elapsed = 0.0
            if session.start_time and session.end_time:
                total_elapsed = (session.end_time - session.start_time).total_seconds()

            for idx, att in enumerate(attempts):
                # Calculate lives at this attempt
                wrong_at_attempt = sum(1 for i in range(idx + 1) if not attempts[i]["is_correct"])
                lives_at_attempt = max(0, 3 - wrong_at_attempt)
                
                entry = {
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
                    "lives_remaining": lives_at_attempt,
                    "max_lives": 3,
                }
                if idx == len(attempts) - 1:
                    entry["minigame_time_taken"] = total_elapsed
                    entry["time_limit"] = session.time_limit
                results.append(entry)

            try:
                print(f"Attempting to recalibrate topic proficiency for hangman...")
                print(f"User: {request.user}")
                print(f"Results data: {results}")
                recalibrate_topic_proficiency(request.user, results)
                print("Recalibration completed successfully!")
            except Exception as e:
                import traceback
                print(f"Recalibration error (hangman): {e}")
                print(f"Error type: {type(e)}")
                print(f"Traceback:")
                traceback.print_exc()
                print(f"User data: {request.user}")
                print(f"Results data: {results}")

        return Response({
            "success": passed,
            "game_over": game_over,
            "remaining_lives": remaining_lives_after,
            "message": message,
            **({"traceback": trace} if not passed else {})
        })


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

        wrong_before = QuestionResponse.objects.filter(
            question=game_q, user=request.user, is_correct=False
        ).count()
        remaining_lives_before = 3 - wrong_before

        passed, message, traceback_str = run_user_code(
            user_code,
            question.game_data.get("function_name", ""),
            question.game_data.get("hidden_tests", [])
        )

        attempt_number = wrong_before + 1
        log_question_event(
            user=request.user,
            game_question=game_q,
            user_answer=user_code,
            is_correct=passed,
            time_taken=0,
            attempt_number=attempt_number,
        )
        from analytics.helpers.theta_updater import update_user_theta
        update_user_theta(request.user.id)



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

            attempts = list(
                QuestionResponse.objects
                .filter(question=game_q, user=request.user)
                .order_by('answered_at')
                .values('is_correct', 'user_answer')
            )

            # Extract topic and subtopic IDs
            topic_ids, subtopic_ids = extract_topic_subtopic_ids(question)
            print(f"🔍 Debug Question {question.id}: topic_ids={topic_ids}, subtopic_ids={subtopic_ids}")

            results = []
            total_elapsed = 0.0
            if session.start_time and session.end_time:
                total_elapsed = (session.end_time - session.start_time).total_seconds()

            for idx, att in enumerate(attempts):
                # Calculate lives at this attempt
                wrong_at_attempt = sum(1 for i in range(idx + 1) if not attempts[i]["is_correct"])
                lives_at_attempt = max(0, 3 - wrong_at_attempt)
                
                entry = {
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
                    "lives_remaining": lives_at_attempt,
                    "max_lives": 3,
                }
                if idx == len(attempts) - 1:
                    entry["minigame_time_taken"] = total_elapsed
                    entry["time_limit"] = session.time_limit
                results.append(entry)

            try:
                print(f"Attempting to recalibrate topic proficiency for debugging...")
                print(f"User: {request.user}")
                print(f"Results data: {results}")
                recalibrate_topic_proficiency(request.user, results)
                print("Recalibration completed successfully!")
            except Exception as e:
                import traceback
                print(f"Recalibration error (debugging): {e}")
                print(f"Error type: {type(e)}")
                print(f"Traceback:")
                traceback.print_exc()
                print(f"User data: {request.user}")
                print(f"Results data: {results}")

        return Response({
            "success": passed,
            "game_over": game_over,
            "remaining_lives": remaining_lives_after,
            "message": message,
            **({"traceback": traceback_str} if not passed else {})
        })


class SubmitPreAssessmentAnswers(APIView):
    """
    Accepts a bulk pre-assessment submission.

    Request body:
        answers  (list) – [{ question_id, user_answer, time_taken }, ...]

    For each answer:
      - Grades against PreAssessmentQuestion.correct_answer
      - Writes one PreAssessmentResponse row (authenticated users only)
      - Builds a result dict passed to recalibrate_topic_proficiency

    After all answers are processed, aggregates server-side from
    PreAssessmentResponse rows and assigns learner_cluster on UserAbility.
    Minimum threshold: fewer than 3 rows → cluster defaults to 1 (mid).
    event_logger is not used here — PreAssessmentQuestion has no GameQuestion FK.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        answers = request.data.get("answers", [])

        results = []
        correct_count = 0

        for ans in answers:
            try:
                q = PreAssessmentQuestion.objects.get(id=ans["question_id"])
            except PreAssessmentQuestion.DoesNotExist:
                continue

            user_answer = ans.get("user_answer", "")
            time_taken = int(ans.get("time_taken", 0))
            is_correct = q.correct_answer.strip().lower() == user_answer.strip().lower()

            if is_correct:
                correct_count += 1

            if request.user.is_authenticated:
                PreAssessmentResponse.objects.create(
                    user=request.user,
                    question_id=q.id,
                    is_correct=is_correct,
                    time_taken=time_taken,
                )

            results.append({
                "question_id": q.id,
                "question_text": q.question_text,
                "user_answer": user_answer,
                "correct_answer": q.correct_answer,
                "is_correct": is_correct,
                "topic_ids": q.topic_ids or [],
                "subtopic_ids": q.subtopic_ids or [],
                "minigame_time_taken": time_taken,
                "estimated_difficulty": q.estimated_difficulty,
            })

        DIFFICULTY_MULTIPLIER = {
            "beginner": 1.0,
            "intermediate": 1.1,
            "advanced": 1.25,
            "master": 1.4,
        }

        subtopic_stats = defaultdict(lambda: {"correct": 0, "total": 0, "difficulty": "beginner"})
        for r in results:
            for sid in r.get("subtopic_ids", []):
                subtopic_stats[sid]["total"] += 1
                if r["is_correct"]:
                    subtopic_stats[sid]["correct"] += 1
                difficulty = r.get("estimated_difficulty", "beginner")
                if difficulty in ("advanced", "master"):
                    subtopic_stats[sid]["difficulty"] = difficulty
                elif difficulty == "intermediate" and subtopic_stats[sid]["difficulty"] == "beginner":
                    subtopic_stats[sid]["difficulty"] = "intermediate"

        cluster = None
        cluster_name = None

        if request.user.is_authenticated:
            try:
                responses = PreAssessmentResponse.objects.filter(user=request.user)
                count = responses.count()
                if count < 3:
                    cluster = 1
                else:
                    avg_response_time = responses.aggregate(Avg("time_taken"))["time_taken__avg"]
                    accuracy = responses.filter(is_correct=True).count() / count
                    cluster = assign_learner_cluster(avg_response_time, accuracy)

                ability, _ = UserAbility.objects.get_or_create(
                    user=request.user,
                    defaults={"ability_score": 0.5}
                )
                ability.learner_cluster = cluster
                ability.save(update_fields=["learner_cluster"])
                cluster_name = get_cluster_name(cluster)

                # initialise all subtopics — BKT-seeded if covered by pre-assessment, cluster default otherwise
                starting_mastery_default = get_cluster_mastery_default(cluster)  # 0.0–1.0

                from user_learning.bkt import bkt_update
                from user_learning.bkt_params import BKT_PARAMS, DEFAULT_PARAMS
                bkt_params = BKT_PARAMS.get(cluster_name, DEFAULT_PARAMS)

                for subtopic in Subtopic.objects.all():
                    sid = subtopic.id

                    if sid in subtopic_stats and subtopic_stats[sid]["total"] > 0:
                        stats = subtopic_stats[sid]
                        accuracy = stats["correct"] / stats["total"]
                        multiplier = DIFFICULTY_MULTIPLIER.get(stats["difficulty"], 1.0)

                        is_correct_obs = accuracy >= 0.5
                        mastery_0_1 = bkt_update(
                            starting_mastery_default,
                            is_correct_obs,
                            bkt_params["p_slip"],
                            bkt_params["p_guess"],
                        )

                        delta = mastery_0_1 - starting_mastery_default
                        mastery_0_1 = starting_mastery_default + (delta * multiplier)
                        mastery_0_1 = max(0.05, min(0.95, mastery_0_1))
                    else:
                        mastery_0_1 = starting_mastery_default

                    UserSubtopicMastery.objects.get_or_create(
                        user=request.user,
                        subtopic=subtopic,
                        defaults={"mastery_level": mastery_0_1 * 100},
                    )

                # propagate to topic
                for topic in Topic.objects.all():
                    avg = (
                        UserSubtopicMastery.objects
                        .filter(user=request.user, subtopic__topic=topic)
                        .aggregate(avg=Avg("mastery_level"))["avg"] or 0.0
                    )
                    UserTopicProficiency.objects.update_or_create(
                        user=request.user,
                        topic=topic,
                        defaults={"proficiency_percent": avg},
                    )

                # propagate to zone
                for zone in GameZone.objects.all().order_by("order"):
                    avg = (
                        UserTopicProficiency.objects
                        .filter(user=request.user, topic__zone=zone)
                        .aggregate(avg=Avg("proficiency_percent"))["avg"] or 0.0
                    )
                    UserZoneProgress.objects.update_or_create(
                        user=request.user,
                        zone=zone,
                        defaults={"completion_percent": avg},
                    )

            except Exception:
                import traceback
                traceback.print_exc()

        return Response({
            "total": len(answers),
            "correct": correct_count,
            "results": results,
            "cluster": cluster,
            "cluster_name": cluster_name,
        })


class GameLeaderboardView(APIView):
 
    permission_classes = [AllowAny]

    def get(self, request, game_type):
        # Filter completed sessions for the game
        qs = GameSession.objects.filter(game_type=game_type, status='completed').exclude(user__isnull=True)

        # Compute elapsed seconds per session (guard missing end_time)
        sessions = []
        for s in qs.select_related('user'):
            if not s.end_time or not s.start_time:
                elapsed = None
            else:
                elapsed = (s.end_time - s.start_time).total_seconds()
            sessions.append((s, elapsed or 0.0))

        # For each user, select best session according to score desc, elapsed asc
        best_by_user = {}
        for s, elapsed in sessions:
            uid = s.user.id
            cur = best_by_user.get(uid)
            if not cur:
                best_by_user[uid] = (s, elapsed)
                continue
            best_s, best_elapsed = cur
            if s.total_score > best_s.total_score:
                best_by_user[uid] = (s, elapsed)
            elif s.total_score == best_s.total_score and elapsed < best_elapsed:
                best_by_user[uid] = (s, elapsed)

        entries = []
        for uid, (s, elapsed) in best_by_user.items():
            entries.append({
                'user_id': s.user.id,
                'username': s.user.username,
                'first_name': getattr(s.user, 'first_name', '') or '',
                'last_name': getattr(s.user, 'last_name', '') or '',
                'score': s.total_score,
                'time_seconds': float(elapsed),
                'session_id': s.session_id,
                'played_at': s.end_time or s.start_time,
            })

        # sort by score desc, time asc
        entries.sort(key=lambda e: (-e['score'], e['time_seconds']))

        serializer = LeaderboardEntrySerializer(entries, many=True)
        return Response(serializer.data)
