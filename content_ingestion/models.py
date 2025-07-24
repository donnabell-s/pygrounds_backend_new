from django.db import models

class Topic(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Subtopic(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='subtopics')
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.topic.name} - {self.name}"

class DocumentChunk(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True)
    subtopic = models.ForeignKey(Subtopic, on_delete=models.SET_NULL, null=True, blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.content[:50]

