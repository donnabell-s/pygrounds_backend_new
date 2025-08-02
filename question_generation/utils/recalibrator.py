from minigames.models import QuestionResponse, GameQuestion
from question_generation.models import GeneratedQuestion
from django.db.models import Count

def recalibrate_difficulty():
    questions = GeneratedQuestion.objects.all()
    updated = 0

    for question in questions:
        responses = QuestionResponse.objects.filter(question__question=question)
        total = responses.count()
        wrong = responses.filter(is_correct=False).count()

        if total >= 5:
            error_rate = wrong / total

            if question.difficulty == 1 and error_rate > 0.5:
                question.difficulty = 2  # easy to intermediate
                question.save()
                updated += 1
            elif question.difficulty == 2 and error_rate > 0.5:
                question.difficulty = 3  # intermediate to ard
                question.save()
                updated += 1

    return f"Recalibrated {updated} questions."
