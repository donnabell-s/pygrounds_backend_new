from django.db import models
from question_generation.utils.difficulty_predictor import predict_difficulty
from question_generation.utils.topic_predictor import predict_topic

DIFFICULTY_LEVELS = (
    (1, "Easy"),
    (2, "Intermediate"),
    (3, "Hard"),
)

DIFFICULTY_MAPPING = {
    "Easy": 1,
    "Intermediate": 2,
    "Hard": 3,
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
        if not self.difficulty:
            label = predict_difficulty(self.text)  # returns "Easy", "Intermediate", "Hard"
            self.difficulty = DIFFICULTY_MAPPING.get(label, None)

        if not self.topic:
            topic_name = predict_topic(self.text)  # returns string like "Loops", "Variables", etc.
            if topic_name and topic_name != "Uncategorized":
                topic_obj, _ = Topic.objects.get_or_create(name=topic_name)
                self.topic = topic_obj

        super().save(*args, **kwargs)

    def __str__(self):
        return self.text[:50]
