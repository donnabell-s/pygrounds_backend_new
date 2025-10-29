from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from question_generation.models import GeneratedQuestion  
from analytics.models import QuestionResponse              
import random

User = get_user_model()

class Command(BaseCommand):
    help = "Seed fake responses for testing recalibration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--question_id",
            type=int,
            help="ID of the Question to attach fake responses to",
            default=1
        )
        parser.add_argument(
            "--count",
            type=int,
            help="How many fake responses to generate",
            default=10
        )

    def handle(self, *args, **options):
        question_id = options["question_id"]
        count = options["count"]

        try:
            question = GeneratedQuestion.objects.get(id=question_id)
        except GeneratedQuestion.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"GeneratedQuestion with id={question_id} does not exist"))
            return

        user, _ = User.objects.get_or_create(
            username="test_user",
            defaults={"password": "Test12345!"}
        )

        for i in range(count):
            score = random.choice([0.0, 0.5, 1.0])  
            QuestionResponse.objects.create(
                user=user,
                question=question,
                score=score
            )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully seeded {count} fake responses for Question ID {question_id}")
        )
