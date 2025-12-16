from django.db import models
from django.contrib.auth import get_user_model
from question_generation.models import GeneratedQuestion

User = get_user_model()


# 1. IRT Parameters per Question (2PL Model)
class ItemIRTParameters(models.Model):
    """
    Stores the 2PL IRT parameters for each question: - a = discrimination - b = difficulty """

    question = models.OneToOneField(
        "question_generation.GeneratedQuestion",
        on_delete=models.CASCADE,
        related_name="irt_params"
    )

    a = models.FloatField(default=1.0)   # discrimination
    b = models.FloatField(default=0.0)   # difficulty

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"IRT Params for Q{self.question_id} (a={self.a:.2f}, b={self.b:.2f})"


# 2. Analytics Responses (ALL logged processed answers)
class QuestionResponse(models.Model):
    """
    Stores analytics responses for IRT recalibration. NOT tied to minigames. Pure analytics-only."""

    question = models.ForeignKey(
        "question_generation.GeneratedQuestion",
        on_delete=models.CASCADE,
        related_name="analytics_responses"
    )

    # binary score: 1 = correct, 0 = wrong
    score = models.FloatField(default=0)

    # optional metadata
    response_time = models.IntegerField(null=True, blank=True)
    user_id = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Response(q={self.question_id}, score={self.score})"



class UserAbility(models.Model):
    """Stores each user's ability level (theta).Theta updates whenever a user answers a question."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="irt_ability")

    # θ (theta) = user ability estimate
    theta = models.FloatField(default=0.0)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} → θ={self.theta:.3f}"
