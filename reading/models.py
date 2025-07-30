from django.db import models

class ReadingMaterial(models.Model):
    topic = models.CharField(max_length=200)
    subtopic = models.CharField(max_length=200)
    title = models.CharField(max_length=255)
    content = models.TextField()  
    order_in_topic = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order_in_topic']
        constraints = [
            models.UniqueConstraint(fields=['topic', 'title'], name='unique_topic_title')
        ]

    def __str__(self):
        return f"{self.topic} - {self.subtopic} - {self.title}"
