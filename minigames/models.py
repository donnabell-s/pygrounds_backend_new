from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class GameSession(models.Model):
    GAME_CHOICES = [
        ('crossword', 'Crossword'),
        ('hangman', 'Hangman'),
        ('wordsearch', 'WordSearch'), 
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
    ]

    session_id = models.CharField(max_length=100, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="game_sessions")
    game_type = models.CharField(max_length=50, choices=GAME_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    total_score = models.IntegerField(default=0)
    time_limit = models.IntegerField(help_text="Seconds", default=300)

    def __str__(self):
        return f"{self.user.username} - {self.game_type} - {self.session_id}"


class Question(models.Model):
    """
    Master question bank. Questions are fetched from here into sessions.
    """
    text = models.TextField()
    answer = models.CharField(max_length=100)

    difficulty = models.CharField(
        max_length=10,
        choices=[
            ('easy', 'Easy'),
            ('medium', 'Medium'),
            ('hard', 'Hard')
        ]
    )
    source_type = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"[{self.difficulty}] {self.text[:40]}"


class GameQuestion(models.Model):
    """
    Links a master question to a specific game session.
    """
    session = models.ForeignKey(GameSession, on_delete=models.CASCADE, related_name="session_questions")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="used_in_sessions")

    def __str__(self):
        return f"Session {self.session.session_id} → Q{self.question.id}"


class QuestionResponse(models.Model):
    """
    Stores the user's answer to a question during a session.
    """
    question = models.ForeignKey(GameQuestion, on_delete=models.CASCADE, related_name="responses")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    user_answer = models.CharField(max_length=100, blank=True, null=True)
    is_correct = models.BooleanField(default=False)
    time_taken = models.IntegerField(default=0, help_text="Time taken in seconds")
    answered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} → Q:{self.question.id} | Correct: {self.is_correct}"

class WordSearchData(models.Model):
    session = models.OneToOneField(GameSession, on_delete=models.CASCADE, related_name="wordsearch_data")
    matrix = models.JSONField()
    placements = models.JSONField()

    def __str__(self):
        return f"WordSearch for Session {self.session.session_id}"