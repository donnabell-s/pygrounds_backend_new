from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from question_generation.utils.recalibrator import get_or_recalibrate_difficulty
from .models import QuestionResponse


@receiver(post_save, sender=QuestionResponse)
def auto_recalibrate_on_response(sender, instance, created, **kwargs):
    """
    Automatically recalibrate question difficulty when a new QuestionResponse is created.
    - If < 5 responses: Algorithm 1 (initial assignment)
    - If ≥ 5 responses: Algorithm 2 (performance-based recalibration)
    """

    if not created:  
        return

    try:
       
        result = get_or_recalibrate_difficulty(sender=sender, instance=instance, created=created, **kwargs)

        if settings.DEBUG:
            print(f"[AUTO RECALIBRATION] Question {instance.question.id}: {result}")

    except Exception as e:
        if settings.DEBUG:
            print(f"[AUTO RECALIBRATION ERROR] {str(e)}")
