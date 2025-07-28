from question_generation.models import GeneratedQuestion
from content_ingestion.models import Topic, Subtopic
from question_generation.utils.difficulty_predictor import predict_difficulty
from question_generation.utils.topic_predictor import predict_topic 

def classify_generated_questions():
    questions = GeneratedQuestion.objects.all()
    updated = 0

    for question in questions:
        question_text = question.question_text.strip()

        predicted_topic = predict_topic(question_text)
        predicted_difficulty = predict_difficulty(question_text)

        question.topic_title = predicted_topic
        question.estimated_difficulty = predicted_difficulty.lower()

        question.save()
        updated += 1

    return f"Updated {updated} questions with predicted topic and difficulty."