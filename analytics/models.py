from django.db import models
from django.contrib.auth import get_user_model
from minigames.models import Question

User = get_user_model()

class QuestionResponse(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analytics_responses')
    score = models.FloatField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.question.text[:30]} - {self.score}"
