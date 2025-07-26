from django.db import models
from django.db.models import JSONField
from content_ingestion.models import Topic, Subtopic, DocumentChunk

class GeneratedQuestion(models.Model):
    """
    LLM/RAG-generated questions for minigames and adaptive challenges.
    """
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='generated_questions')
    subtopic = models.ForeignKey(Subtopic, on_delete=models.CASCADE, related_name='generated_questions')

    question_text = models.TextField()
    # No question_type field here

    answer_options = JSONField(default=list, blank=True)
    correct_answer = models.TextField()
    explanation = models.TextField(blank=True)

    estimated_difficulty = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('master', 'Master'),
        ],
        default='beginner',
        blank=True
    )

    # Game/minigame classification
    game_type = models.CharField(
        max_length=20,
        choices=[
            ('coding', 'Coding'),
            ('non_coding', 'Non-Coding'),
        ],
        default='non_coding'
    )
    minigame_type = models.CharField(
        max_length=30,
        choices=[
            ('hangman_coding', 'Hangman-Style Coding Game'),
            ('ship_debugging', 'Ship Debugging Game'),
            ('word_search', 'Word Search Puzzle'),
            ('crossword', 'Crossword Puzzle'),
        ],
        default='generic'
    )

    source_chunks = models.ManyToManyField(DocumentChunk, blank=True)
    rag_context = JSONField(default=dict, blank=True)
    generation_model = models.CharField(max_length=100, blank=True)
    generation_prompt = models.TextField(blank=True)
    generation_metadata = JSONField(default=dict, blank=True)
    game_data = JSONField(default=dict, blank=True)

    quality_score = models.FloatField(null=True, blank=True)
    validation_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Validation'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('needs_review', 'Needs Review'),
        ],
        default='pending'
    )
    times_used = models.IntegerField(default=0)
    success_rate = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subtopic', 'estimated_difficulty']),
            models.Index(fields=['validation_status', 'quality_score']),
            models.Index(fields=['topic']),
        ]

    def __str__(self):
        return f"{self.subtopic.name}: {self.question_text[:50]}... ({self.estimated_difficulty})"


class PreAssessmentQuestion(models.Model):
    """
    Manually-authored pre-assessment questions for onboarding/adaptive profiling.
    """
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True, related_name='pre_questions')
    subtopic = models.ForeignKey(Subtopic, on_delete=models.SET_NULL, null=True, blank=True, related_name='pre_questions')

    question_text = models.TextField()
    # No question_type field

    answer_options = JSONField(default=list, blank=True)
    correct_answer = models.TextField()
    explanation = models.TextField(blank=True)

    estimated_difficulty = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('master', 'Master'),
        ],
        default='beginner',
        blank=True
    )
    game_type = models.CharField(
        max_length=20,
        choices=[
            ('coding', 'Coding'),
            ('non_coding', 'Non-Coding'),
        ],
        default='non_coding'
    )
    minigame_type = models.CharField(
        max_length=30,
        choices=[
            ('hangman_coding', 'Hangman-Style Coding Game'),
            ('ship_debugging', 'Ship Debugging Game'),
            ('word_search', 'Word Search Puzzle'),
            ('crossword', 'Crossword Puzzle'),
        ],
        default='generic'
    )
    order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"[Pre] {self.topic.name if self.topic else ''} - {self.question_text[:40]}..."

