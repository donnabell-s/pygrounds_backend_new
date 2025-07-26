from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.db.models import JSONField

# sets difficulty according to standard pdf docs naming conventions
DIFFICULTY_CHOICES = [
    ('beginner', 'Beginner'),
    ('intermediate', 'Intermediate'),
    ('advanced', 'Advanced'),
    ('expert', 'Expert'),
]

class UploadedDocument(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="pdfs/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    parsed = models.BooleanField(default=False)
    total_pages = models.IntegerField(default=0)
    status = models.CharField(
        max_length=16,
        choices=[('PENDING', 'Pending'), ('PROCESSING', 'Processing'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed')],
        default='PENDING'
    )
    difficulty = models.CharField(
        max_length=16,
        choices=DIFFICULTY_CHOICES,
        default='beginner', 
        help_text="Intended difficulty of the source material."
    )
    parse_metadata = JSONField(default=dict, blank=True)
    def __str__(self):
        return f"{self.title} ({self.status})"

class DocumentChunk(models.Model):
    document = models.ForeignKey(UploadedDocument, on_delete=models.CASCADE, related_name="chunks")
    chunk_type = models.CharField(max_length=16, choices=[
        ("Concept", "Concept"),
        ("Exercise", "Exercise"),
        ("Example", "Example"),
        ("Code", "Code"),
    ])
    text = models.TextField()
    page = models.IntegerField()
    order = models.IntegerField()
    topic_title = models.CharField(max_length=255, null=True, blank=True)
    subtopic_title = models.CharField(max_length=255, null=True, blank=True)
    class Meta:
        ordering = ['page', 'order']
    def __str__(self):
        return f"{self.chunk_type}: {self.text[:40]}..."

class TOCEntry(models.Model):
    document = models.ForeignKey(UploadedDocument, on_delete=models.CASCADE)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')
    title = models.CharField(max_length=255)
    level = models.IntegerField(default=0)
    start_page = models.IntegerField()
    end_page = models.IntegerField(null=True, blank=True)
    order = models.IntegerField()
    class Meta:
        ordering = ['order']
        unique_together = [['document', 'order']]
    def __str__(self):
        return f"{self.title} ({self.start_page}-{self.end_page or '?'})"

class GameZone(models.Model):
    """A zone in PyGrounds (e.g. Python Basics)"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    order = models.IntegerField(unique=True)
    is_unlocked = models.BooleanField(default=False) 

    def __str__(self):
        return f"Zone {self.order}: {self.name}"

    class Meta:
        ordering = ['order']


class Topic(models.Model):
    """A topic inside a GameZone"""
    zone = models.ForeignKey(GameZone, on_delete=models.CASCADE, related_name='topics')
    name = models.CharField(max_length=100)
    description = models.TextField()
    order = models.IntegerField()
    embedding = ArrayField(models.FloatField(), size=384, null=True, blank=True)
    def __str__(self):
        return f"{self.zone.name} - {self.name}"
    class Meta:
        ordering = ['zone__order', 'order']
        unique_together = [['zone', 'order']]

class Subtopic(models.Model):
    """A subtopic inside a Topic"""
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='subtopics')
    name = models.CharField(max_length=100)
    description = models.TextField()
    order = models.IntegerField()
    def __str__(self):
        return f"{self.topic.name} - {self.name}"
    class Meta:
        ordering = ['topic__zone__order', 'topic__order', 'order']
        unique_together = [['topic', 'order']]

class Embedding(models.Model):
    """Links an embedding to either a DocumentChunk or a Subtopic"""
    # Only one of these should be non-null
    document_chunk = models.OneToOneField(DocumentChunk, null=True, blank=True, on_delete=models.CASCADE, related_name='embedding_obj')
    subtopic = models.OneToOneField(Subtopic, null=True, blank=True, on_delete=models.CASCADE, related_name='embedding_obj')
    vector = ArrayField(models.FloatField(), size=384)
    model_name = models.CharField(max_length=100, default="all-MiniLM-L6-v2")
    embedded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        target = self.document_chunk or self.subtopic
        return f"Embedding for {target}"
