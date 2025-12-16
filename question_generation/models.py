from django.db import models
from django.db.models import JSONField
from content_ingestion.models import Topic, Subtopic, DocumentChunk


class GeneratedQuestion(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='generated_questions')
    subtopic = models.ForeignKey(Subtopic, on_delete=models.CASCADE, related_name='generated_questions')

    question_text = models.TextField(blank=True)  # Could be clue, prompt, description, etc.
    correct_answer = models.TextField(blank=True)

    estimated_difficulty = models.CharField(
        max_length=20,
        choices=[('beginner','Beginner'), ('intermediate','Intermediate'), ('advanced','Advanced'), ('master','Master')],
        default='beginner',
        blank=True,
    )
    
    game_type = models.CharField(max_length=20, choices=[('coding','Coding'), ('non_coding','Non-Coding')], default='non_coding')

    # Flexible field for storing game-specific data:
    game_data = JSONField(default=dict, blank=True)

    # Metadata & tracking
    validation_status = models.CharField(
    max_length=20,
    choices=[
        ('pending', 'Pending'),
        ('processed', 'Processed'),
    ],
    default='pending'
)

    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
   
    class Meta:
        ordering = ['subtopic__name']
        indexes = [
            models.Index(fields=['subtopic', 'estimated_difficulty']),
            models.Index(fields=['validation_status']),
            models.Index(fields=['topic']),
        ]

    def __str__(self):
        return f"{self.subtopic.name}: {self.question_text[:50]}... ({self.estimated_difficulty})"


class PreAssessmentQuestion(models.Model):
    # Store multiple topic and subtopic IDs that this question covers
    topic_ids = JSONField(default=list, blank=True, help_text="List of topic IDs this question covers")
    subtopic_ids = JSONField(default=list, blank=True, help_text="List of subtopic IDs this question covers")

    question_text = models.TextField()
    # No question_type field

    answer_options = JSONField(default=list, blank=True)
    correct_answer = models.TextField()
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
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        # Get first topic name if available, otherwise show question text
        try:
            if self.topic_ids:
                first_topic = Topic.objects.get(id=self.topic_ids[0])
                return f"[Pre] {first_topic.name} - {self.question_text[:40]}..."
            else:
                return f"[Pre] No topics - {self.question_text[:40]}..."
        except Topic.DoesNotExist:
            return f"[Pre] Invalid topic - {self.question_text[:40]}..."

