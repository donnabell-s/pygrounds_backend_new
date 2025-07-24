from question_generation.models import GeneratedQuestion
from content_ingestion.models import Topic, Subtopic
from question_generation.utils.difficulty_predictor import predict_difficulty

def classify_generated_questions():
    questions = GeneratedQuestion.objects.all()
    updated = 0

    for question in questions:
        question_text = question.question_text.strip()

        predicted_difficulty = predict_difficulty(question_text)

        question.estimated_difficulty = predicted_difficulty.lower()
        question.save()
        updated += 1

    return f"Updated {updated} questions with predicted difficulty levels."
