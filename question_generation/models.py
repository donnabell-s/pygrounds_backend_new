from django.db import models
from question_generation.utils.difficulty_predictor import predict_difficulty

DIFFICULTY_LEVELS = (
    (0, "Beginner"),
    (1, "Intermediate"),
    (2, "Advanced"),
    (3, "Master"),
)

DIFFICULTY_MAPPING = {
    "Beginner": 0,
    "Intermediate": 1,
    "Advanced": 2,
    "Master": 3,
}

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

    def save(self, *args, **kwargs):
        if self.difficulty is None:
            label = predict_difficulty(self.text)  
            self.difficulty = DIFFICULTY_MAPPING.get(label, None)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.text[:50]

# dummy midel rani
class GeneratedQuestion(models.Model):
    text = models.TextField()
    difficulty = models.IntegerField(choices=DIFFICULTY_LEVELS)

    def __str__(self):
        return self.text[:50]
