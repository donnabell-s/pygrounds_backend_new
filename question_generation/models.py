from django.db import models

from django.db import models

DIFFICULTY_LEVELS = (
    (1, "Easy"),
    (2, "Intermediate"),
    (3, "Hard"),
)

class Topic(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Subtopic(models.Model):
    name = models.CharField(max_length=100)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.topic.name} - {self.name}"

class Question(models.Model):
    text = models.TextField()
    topic = models.ForeignKey(Topic, null=True, blank=True, on_delete=models.SET_NULL)
    subtopic = models.ForeignKey(Subtopic, null=True, blank=True, on_delete=models.SET_NULL)
    difficulty = models.IntegerField(choices=DIFFICULTY_LEVELS, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text[:50]
