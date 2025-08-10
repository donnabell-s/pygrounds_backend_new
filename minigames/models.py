from django.db import models
from question_generation.models import GeneratedQuestion
from django.contrib.auth import get_user_model

User = get_user_model()


class Question(models.Model):
    GAME_CHOICES = [
        ('crossword', 'Crossword'),
        ('hangman', 'Hangman'),
        ('wordsearch', 'WordSearch'),
        ('debugging', 'Debugging'),
    ]
    question = models.ForeignKey(GeneratedQuestion, on_delete=models.CASCADE, null=True)  #para dummy checker rani
    text = models.TextField()
    answer = models.CharField(max_length=100, blank=True, null=True)
    difficulty = models.CharField(max_length=12, choices=[
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('master', 'Master')
    ])
    game_type = models.CharField(max_length=50, choices=GAME_CHOICES, null=True, blank=True, help_text="Game this question is for")

    # Code-related fields
    function_name = models.CharField(max_length=50, blank=True, null=True)
    sample_input = models.TextField(blank=True, null=True)
    sample_output = models.TextField(blank=True, null=True)
    hidden_tests = models.JSONField(blank=True, null=True)
    broken_code = models.TextField(blank=True, null=True)


    def __str__(self):
        return f"[{self.game_type}] [{self.difficulty}] {self.text[:40]}"


class GameSession(models.Model):
    # mostly fine as-is
    session_id = models.CharField(max_length=100, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="game_sessions")
    game_type = models.CharField(max_length=50, choices=Question.GAME_CHOICES, null=True, blank=True)
    status = models.CharField(max_length=20, choices=[('active', 'Active'), ('completed', 'Completed'), ('expired', 'Expired')], default='active')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    total_score = models.IntegerField(default=0)
    time_limit = models.IntegerField(help_text="Seconds", default=300)

    def __str__(self):
        return f"{self.user.username} - {self.game_type} - {self.session_id}"


# minigames/models.py


class GameQuestion(models.Model):
    session = models.ForeignKey(GameSession, on_delete=models.CASCADE, related_name="session_questions")
    question = models.ForeignKey(GeneratedQuestion, on_delete=models.CASCADE, related_name="used_in_sessions")

    class Meta:
        unique_together = ('session', 'question')



class QuestionResponse(models.Model):
    question = models.ForeignKey(GameQuestion, on_delete=models.CASCADE, related_name="responses")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    user_answer = models.TextField(blank=True, null=True)
    is_correct = models.BooleanField(default=False)
    time_taken = models.IntegerField(default=0)
    answered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} | Q:{self.question.id} | Correct: {self.is_correct}"


class WordSearchData(models.Model):
    session = models.OneToOneField(GameSession, on_delete=models.CASCADE, related_name="wordsearch_data")
    matrix = models.JSONField()
    placements = models.JSONField()

    def __str__(self):
        return f"WordSearch for Session {self.session.session_id}"
    
class HangmanData(models.Model):
    session = models.OneToOneField(GameSession, on_delete=models.CASCADE, related_name="hangman_data")
    prompt = models.TextField()
    function_name = models.CharField(max_length=50)
    sample_input = models.TextField()
    sample_output = models.TextField()
    hidden_tests = models.JSONField()  # e.g., [{"input": "abc", "output": "cba"}, ...]

    def __str__(self):
        return f"Hangman for {self.session.session_id}"

