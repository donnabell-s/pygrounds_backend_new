from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from content_ingestion.models import GameZone, Topic, Subtopic
from .models import GeneratedQuestion


# ---------------------------------------------------------------------------
# Shared fixture helper
# ---------------------------------------------------------------------------

def make_question(**kwargs):
    """Create a minimal GeneratedQuestion with all required relations."""
    zone     = GameZone.objects.create(name="Zone 1", description="z", order=1)
    topic    = Topic.objects.create(zone=zone, name="Variables", description="t")
    subtopic = Subtopic.objects.create(topic=topic, name="Assignment")
    defaults = dict(
        topic=topic,
        subtopic=subtopic,
        question_text="What does x = 5 do?",
        correct_answer="Assigns 5 to x",
        estimated_difficulty="beginner",
        game_type="non_coding",
    )
    defaults.update(kwargs)
    return GeneratedQuestion.objects.create(**defaults)


# ---------------------------------------------------------------------------
# get_question_by_id  GET /api/question/<id>/
# ---------------------------------------------------------------------------

class GetQuestionByIdTests(APITestCase):

    def test_returns_question_data(self):
        q = make_question()
        url = reverse("get-question-by-id", args=[q.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["question"]["id"], q.id)
        self.assertEqual(data["question"]["question_text"], q.question_text)

    def test_returns_404_for_missing_question(self):
        url = reverse("get-question-by-id", args=[99999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# toggle_question_flag  POST /api/question/<id>/toggle-flag/
# ---------------------------------------------------------------------------

class ToggleQuestionFlagTests(APITestCase):

    def test_flags_an_unflagged_question(self):
        q = make_question(flagged=False)
        url = reverse("toggle-question-flag", args=[q.id])
        response = self.client.post(url, {"reason": "wrong answer", "note": "double checked"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["flagged"])
        self.assertEqual(data["flag_reason"], "wrong answer")

        q.refresh_from_db()
        self.assertTrue(q.flagged)

    def test_unflags_a_flagged_question(self):
        q = make_question(flagged=True, flag_reason="bad question")
        url = reverse("toggle-question-flag", args=[q.id])
        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertFalse(data["flagged"])
        self.assertIsNone(data["flag_reason"])

        q.refresh_from_db()
        self.assertFalse(q.flagged)

    def test_increments_flag_count_by_level_on_flag(self):
        q = make_question(flagged=False, flag_count_by_level={})
        url = reverse("toggle-question-flag", args=[q.id])
        self.client.post(url, {}, format="json")

        q.refresh_from_db()
        # One level should have count 1 (anonymous user maps to beginner)
        total = sum(q.flag_count_by_level.values())
        self.assertEqual(total, 1)

    def test_returns_404_for_missing_question(self):
        url = reverse("toggle-question-flag", args=[99999])
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()["type"], "QUESTION_NOT_FOUND")


# ---------------------------------------------------------------------------
# get_flagged_questions  GET /api/question/flagged/
# ---------------------------------------------------------------------------

class GetFlaggedQuestionsTests(APITestCase):

    def setUp(self):
        self.url = reverse("get-flagged-questions")

    def test_only_returns_flagged_questions(self):
        flagged  = make_question(flagged=True, flag_reason="unclear")
        # A second question sharing the same relations
        topic    = Topic.objects.first()
        subtopic = Subtopic.objects.first()
        GeneratedQuestion.objects.create(
            topic=topic, subtopic=subtopic,
            question_text="Another question", correct_answer="ans",
            estimated_difficulty="beginner", game_type="non_coding",
            flagged=False,
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["id"], flagged.id)

    def test_returns_empty_when_no_flagged_questions(self):
        make_question(flagged=False)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 0)

    def test_filter_by_invalid_level_returns_400(self):
        response = self.client.get(self.url, {"level": "expert"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pagination_respects_page_size(self):
        # Create 3 flagged questions using same existing relations if any
        zone    = GameZone.objects.create(name="Zone Pag", description="z", order=99)
        topic   = Topic.objects.create(zone=zone, name="Pag Topic", description="t")
        sub     = Subtopic.objects.create(topic=topic, name="Pag Sub")
        for i in range(3):
            GeneratedQuestion.objects.create(
                topic=topic, subtopic=sub,
                question_text=f"Q{i}", correct_answer="a",
                estimated_difficulty="beginner", game_type="non_coding",
                flagged=True,
            )

        response = self.client.get(self.url, {"page_size": 2, "page": 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 2)
        self.assertIsNotNone(data["next"])


# ---------------------------------------------------------------------------
# get_all_questions  GET /api/all/
# ---------------------------------------------------------------------------

class GetAllQuestionsTests(APITestCase):

    def setUp(self):
        self.url = reverse("get-all-questions")

    def test_returns_all_questions(self):
        make_question()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertGreaterEqual(data["pagination"]["total_count"], 1)
        self.assertIn("questions", data)

    def test_invalid_order_by_returns_400(self):
        response = self.client.get(self.url, {"order_by": "nonexistent_field"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_order_direction_returns_400(self):
        response = self.client.get(self.url, {"order": "sideways"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_limit_is_respected(self):
        zone    = GameZone.objects.create(name="Zone Lim", description="z", order=88)
        topic   = Topic.objects.create(zone=zone, name="Lim Topic", description="t")
        sub     = Subtopic.objects.create(topic=topic, name="Lim Sub")
        for i in range(5):
            GeneratedQuestion.objects.create(
                topic=topic, subtopic=sub,
                question_text=f"Q{i}", correct_answer="a",
                estimated_difficulty="beginner", game_type="non_coding",
            )

        response = self.client.get(self.url, {"limit": 2, "offset": 0})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["questions"]), 2)
        self.assertTrue(data["pagination"]["has_more"])


# ---------------------------------------------------------------------------
# get_generation_status  GET /api/generate/status/<session_id>/
# ---------------------------------------------------------------------------

class GetGenerationStatusTests(APITestCase):

    def test_unknown_session_returns_404(self):
        url = reverse("get-generation-status", args=["nonexistent-session-id"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
