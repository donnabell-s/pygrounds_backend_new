from django.db import models
from django.conf import settings

class QuestionResponse(models.Model):
    question = models.ForeignKey(
        "question_generation.GeneratedQuestion", 
        on_delete=models.CASCADE,
        related_name="analytics_responses"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="analytics_responses"
    )
    score = models.FloatField()  
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Resp({self.user}, {self.question}, {self.score})"

class QuestionRecalibration(models.Model):
    question = models.ForeignKey(
        "question_generation.GeneratedQuestion",
        on_delete=models.CASCADE,
        related_name="recalibration_history"
    )
    old_difficulty = models.CharField(max_length=20)
    new_difficulty = models.CharField(max_length=20)
    triggered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Q{self.question.id}: {self.old_difficulty} → {self.new_difficulty} @ {self.triggered_at}"
