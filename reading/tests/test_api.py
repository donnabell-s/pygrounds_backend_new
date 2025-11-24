from rest_framework.test import APITestCase
from reading.models import ReadingMaterial
from content_ingestion.models import Topic, Subtopic

class ReadingAPITests(APITestCase):
    def setUp(self):

        self.topic = Topic.objects.create(
            name="Basic Input and Output",
            slug="basic-input-and-output"
        )
        self.st1 = Subtopic.objects.create(
            topic=self.topic, name="Intro", slug="intro", order_in_topic=1
        )
        self.st2 = Subtopic.objects.create(
            topic=self.topic,
            name="Formatting Output with f-Strings",
            slug="formatting-output-with-f-strings",
            order_in_topic=3,
        )

        self.m1 = ReadingMaterial.objects.create(
            topic_ref=self.topic,
            subtopic_ref=self.st1,
            title="Hello Print",
            content="print('hi')",
            order_in_topic=1,
        )
        self.m2 = ReadingMaterial.objects.create(
            topic_ref=self.topic,
            subtopic_ref=self.st2,
            title="Formatting Output with f-Strings",
            content="f'{x}'",
            order_in_topic=3,
        )
        self.m3 = ReadingMaterial.objects.create(
            topic_ref=self.topic,
            subtopic_ref=self.st2,
            title="More f-strings",
            content="...",
            order_in_topic=4,
        )

    def test_topics_list(self):
        res = self.client.get("/api/reading/topics/")
        self.assertEqual(res.status_code, 200)
        slugs = [t["slug"] for t in res.json()]
        self.assertIn("basic-input-and-output", slugs)

    def test_subtopics_by_topic(self):
        res = self.client.get("/api/reading/topics/basic-input-and-output/subtopics/")
        self.assertEqual(res.status_code, 200)
        slugs = [s["slug"] for s in res.json()]
        self.assertIn("formatting-output-with-f-strings", slugs)

    def test_materials_by_topic_and_subtopic(self):
        res = self.client.get(
            "/api/reading-materials/",
            {
                "topic": "basic-input-and-output",
                "subtopic": "formatting-output-with-f-strings",
                "page_size": 50,
            },
        )
        self.assertEqual(res.status_code, 200)
        titles = [x["title"] for x in res.json()["results"]]
        self.assertIn("Formatting Output with f-Strings", titles)

    def test_neighbors_endpoint(self):
        res = self.client.get(f"/api/reading-materials/{self.m2.id}/neighbors/")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIsNotNone(data["prev_id"])
        self.assertIsNotNone(data["next_id"])