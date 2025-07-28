from django.db import models
from content_ingestion.models import GameZone, Topic, Subtopic
from django.contrib.auth import get_user_model

User = get_user_model()

class UserZoneProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='unlocked_zones')
    zone = models.ForeignKey(GameZone, on_delete=models.CASCADE)
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'zone')
        ordering = ['zone__order']

    def __str__(self):
        return f"{self.user.username} → {self.zone.name}"

class UserTopicProficiency(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='topic_proficiencies')
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    proficiency_percent = models.FloatField(default=0.0)

    class Meta:
        unique_together = ('user', 'topic')
        ordering = ['topic__order']

    def __str__(self):
        return f"{self.user.username} → {self.topic.name}: {self.proficiency_percent}%"

class UserSubtopicMastery(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subtopic_mastery')
    subtopic = models.ForeignKey(Subtopic, on_delete=models.CASCADE)
    attempts = models.IntegerField(default=0)
    correct = models.IntegerField(default=0)

    class Meta:
        unique_together = ('user', 'subtopic')

    def __str__(self):
        return f"{self.user.username} → {self.subtopic.name}: {self.correct}/{self.attempts}"
