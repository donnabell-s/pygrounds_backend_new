from django.db import models
from django.utils.text import slugify

class Topic(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Subtopic(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="subtopics")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    order_in_topic = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["topic", "name"], name="uniq_topic_subtopic")
        ]
        ordering = ["topic__name", "order_in_topic", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.topic.name} / {self.name}"


class ReadingMaterial(models.Model):
    # ...
    topic_ref = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name="materials",
        null=True,    # TEMP: allow nulls aron makabackfill ta
        blank=True,   # TEMP
    )
    subtopic_ref = models.ForeignKey(
        Subtopic,
        on_delete=models.CASCADE,
        related_name="materials",
        null=True,
        blank=True,
    )
    # ...


    title = models.CharField(max_length=255)
    content = models.TextField()
    order_in_topic = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["topic_ref", "subtopic_ref", "title"],
                name="uniq_topic_subtopic_title"
            )
        ]
        ordering = ["topic_ref__name", "subtopic_ref__order_in_topic", "title"]

    def __str__(self):
        sub = self.subtopic_ref.name if self.subtopic_ref_id else (self.subtopic or "—")
        return f"{self.topic_ref.name} - {sub} - {self.title}"
