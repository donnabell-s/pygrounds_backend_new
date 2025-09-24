from django.db import models


class ReadingMaterial(models.Model):
    topic_ref = models.ForeignKey(
        "content_ingestion.Topic",
        on_delete=models.CASCADE,
        related_name="reading_materials",
        null=True,
        blank=True,
    )
    subtopic_ref = models.ForeignKey(
        "content_ingestion.Subtopic",
        on_delete=models.CASCADE,
        related_name="reading_materials",
        null=True,
        blank=True,
    )

    title = models.CharField(max_length=255)
    content = models.TextField()
    order_in_topic = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["topic_ref", "subtopic_ref", "title"],
                name="uniq_topic_subtopic_title",
            )
        ]
        ordering = ["topic_ref__name", "subtopic_ref__order_in_topic", "title"]

    def __str__(self):
        sub = getattr(self.subtopic_ref, "name", "—") if self.subtopic_ref_id else "—"
        topic = getattr(self.topic_ref, "name", "—") if self.topic_ref_id else "—"
        return f"{topic} - {sub} - {self.title}"
