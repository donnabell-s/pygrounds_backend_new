#for testing only and dummy only 
from minigames.models import Question
from analytics.models import QuestionResponse

def recalibrate_difficulty_for_question(gq_id):
    try:
        question = Question.objects.get(question__id=gq_id)
    except Question.DoesNotExist:
        return "Related minigame Question not found for this GeneratedQuestion."

    responses = QuestionResponse.objects.filter(question__question__id=gq_id)

    if not responses.exists():
        return "No responses found to evaluate difficulty."

    average_score = sum([r.score for r in responses]) / len(responses)

    if average_score < 0.3:
        new_diff = 'master'
    elif average_score < 0.6:
        new_diff = 'advanced'
    elif average_score < 0.8:
        new_diff = 'intermediate'
    else:
        new_diff = 'beginner'

    question.difficulty = new_diff
    question.save()

    return f"Updated difficulty to {new_diff}"


#real logic
def recalibrate_difficulty_for_question(question_id):
    from minigames.models import Question
    from analytics.models import QuestionResponse

    try:
        question = Question.objects.get(id=question_id)
    except Question.DoesNotExist:
        return "Question not found."

    responses = QuestionResponse.objects.filter(question=question)
    total = responses.count()

    if total < 5:
        return "Not enough responses to recalibrate."

    wrong = responses.filter(score__lt=0.7).count()

    error_rate = wrong / total

    levels = ['beginner', 'intermediate', 'advanced', 'master']
    current_index = levels.index(question.difficulty)

    if error_rate > 0.6 and current_index < len(levels) - 1:
        question.difficulty = levels[current_index + 1]
        question.save()
        return f"Recalibrated to {question.difficulty.capitalize()}."
    else:
        return "No recalibration needed."




