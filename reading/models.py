from django.db import models
from content_ingestion.models import Topic, Subtopic


class ReadingMaterial(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    topic_ref = models.ForeignKey(
        "content_ingestion.Topic",
        on_delete=models.CASCADE,
        related_name="materials",
        null=True,
        blank=True,
    )
    subtopic_ref = models.ForeignKey(
        "content_ingestion.Subtopic",
        on_delete=models.CASCADE,
        related_name="materials",
        null=True,
        blank=True,
    )
    order_in_topic = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = [
            "topic_ref__zone__order",
            "topic_ref__id",
            "subtopic_ref__order_in_topic",
            "order_in_topic",
            "id",
        ]

    def __str__(self):
        return f"{self.topic_ref} / {self.subtopic_ref}: {self.title}"
