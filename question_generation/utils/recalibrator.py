from django.db.models import Avg
from minigames.models import Question
from analytics.models import QuestionResponse

LEVELS = ['beginner', 'intermediate', 'advanced', 'master']

def recalibrate_difficulty_for_question(question_id: int) -> str:
    """
    Score-based recalibration (uses analytics.QuestionResponse.score ∈ [0,1]):
      avg_score < 0.30  -> 'master'
      avg_score < 0.60  -> 'advanced'
      avg_score < 0.80  -> 'intermediate'
      else              -> 'beginner'
    Requires at least 5 responses.
    """
    try:
        q = Question.objects.get(id=question_id)
    except Question.DoesNotExist:
        return "Question not found."

    qs = QuestionResponse.objects.filter(question=q)
    total = qs.count()
    if total < 5:
        return "Not enough responses to recalibrate."

    avg_score = qs.aggregate(val=Avg('score'))['val'] or 0.0

    if avg_score < 0.30:
        new_diff = 'master'
    elif avg_score < 0.60:
        new_diff = 'advanced'
    elif avg_score < 0.80:
        new_diff = 'intermediate'
    else:
        new_diff = 'beginner'

    if q.difficulty != new_diff:
        q.difficulty = new_diff
        q.save(update_fields=['difficulty'])
        return f"Recalibrated to {new_diff.capitalize()}."
    return "No recalibration needed."
