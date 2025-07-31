from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.db.models import JSONField

# Difficulty choices for documents and subtopics
DIFFICULTY_CHOICES = [
    ('beginner', 'Beginner'),
    ('intermediate', 'Intermediate'),
    ('advanced', 'Advanced'),
    ('master', 'Master'),
]

CHUNK_TYPE_CHOICES = [
    ('Concept', 'Concept'),
    ('Exercise', 'Exercise'), 
    ('Code', 'Code'),
    ('Try_It', 'Try It'),
    ('Example', 'Example'),
]

MATCH_STATUS_CHOICES = [
    ('unmatched', 'Unmatched'),
    ('matched', 'Matched'),
    ('ignored', 'Ignored'),
]

PROCESSING_STATUS = [
    ('PENDING', 'Pending'),
    ('PROCESSING', 'Processing'),
    ('COMPLETED', 'Completed'),
    ('FAILED', 'Failed'),
]


class UploadedDocument(models.Model):
    """
    Represents an uploaded PDF with parsing metadata and difficulty level.
    """
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='pdfs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Parsing state
    processing_status = models.CharField(
        max_length=20,
        choices=PROCESSING_STATUS,
        default='PENDING',
    )
    parsed = models.BooleanField(default=False)
    parsed_pages = ArrayField(
        base_field=models.IntegerField(),
        default=list,
        blank=True,
        help_text='Pages already parsed'
    )
    total_pages = models.IntegerField(default=0)
    parse_metadata = JSONField(default=dict, blank=True)

    # Document difficulty
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='intermediate',
        help_text='Content difficulty level'
    )

    def __str__(self):
        return f"{self.title} ({self.processing_status})"


class DocumentChunk(models.Model):
    """
    Individual content segments extracted from an UploadedDocument.
    Supports RAG embedding and token counting.
    """
    document = models.ForeignKey(
        UploadedDocument, on_delete=models.CASCADE, related_name='chunks'
    )
    chunk_type = models.CharField(
        max_length=50,
        choices=CHUNK_TYPE_CHOICES,
    )
    text = models.TextField()
    page_number = models.IntegerField()
    order_in_doc = models.IntegerField()

    # Classification
    topic_title = models.CharField(max_length=255, blank=True, null=True)
    subtopic_title = models.CharField(max_length=255, blank=True, null=True)
    sub_subtopic_title = models.CharField(max_length=255, blank=True, null=True, help_text='Third level nesting (optional, only when detected in TOC)')
    sub_sub_subtopic_title = models.CharField(max_length=255, blank=True, null=True, help_text='Fourth level nesting (optional, for expert-level PDFs with deep hierarchy)')

    # Token info for LLM optimization
    token_count = models.IntegerField(blank=True, null=True)
    token_encoding = models.CharField(
        max_length=50,
        default='cl100k_base',
        blank=True,
    )
    parser_metadata = JSONField(default=dict, blank=True)
    
    # Semantic matching status
    match_status = models.CharField(
        max_length=20,
        choices=MATCH_STATUS_CHOICES,
        default='unmatched',
        help_text='Status for semantic similarity matching - can be used to ignore already processed chunks'
    )

    # Note: Embeddings are now stored in separate Embedding model for better organization

    class Meta:
        ordering = ['page_number', 'order_in_doc']

    def __str__(self):
        preview = (self.text[:50] + '...') if len(self.text) > 50 else self.text
        return f"{self.chunk_type}: {preview}"


class TOCEntry(models.Model):
    """
    Table of Contents entries that map to ranges of pages and chunk status.
    """
    document = models.ForeignKey(UploadedDocument, on_delete=models.CASCADE)
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='children'
    )
    title = models.CharField(max_length=255)
    level = models.IntegerField(default=0)
    start_page = models.IntegerField()
    end_page = models.IntegerField(blank=True, null=True)
    order = models.IntegerField()

    # Parsing and mapping state
    chunked = models.BooleanField(default=False)
    chunk_count = models.IntegerField(default=0)
    topic_title = models.CharField(max_length=255, blank=True, null=True)
    subtopic_title = models.CharField(max_length=255, blank=True, null=True)
    sub_subtopic_title = models.CharField(max_length=255, blank=True, null=True, help_text='Third level nesting (optional)')
    sub_sub_subtopic_title = models.CharField(max_length=255, blank=True, null=True, help_text='Fourth level nesting (optional, for expert PDFs)')

    class Meta:
        ordering = ['order']
        unique_together = [['document', 'order']]

    def __str__(self):
        pages = f"{self.start_page}-{self.end_page or '?'}"
        return f"{self.title} (Pages {pages})"



class GameZone(models.Model):
    """A zone in PyGrounds (e.g. Python Basics)"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    order = models.IntegerField(unique=True)
    # is_unlocked = models.BooleanField(default=False) 

    def __str__(self):
        return f"Zone {self.order}: {self.name}"

    class Meta:
        ordering = ['order']


class Topic(models.Model):
    zone = models.ForeignKey(GameZone, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)  # ✅ non-nullable with default
    embedding = ArrayField(models.FloatField(), size=384, null=True, blank=True)

    class Meta:
        unique_together = ('zone', 'order')
        ordering = ['zone__order', 'order']


class Subtopic(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)  # ✅ non-nullable with default

    class Meta:
        unique_together = ('topic', 'order')
        ordering = ['topic__zone__order', 'topic__order', 'order']


class Embedding(models.Model):
    """
    Stores high‑dimensional embeddings for DocumentChunks or Subtopics, 
    allowing multiple versions/models per entity.
    """
    document_chunk = models.ForeignKey(
        DocumentChunk, null=True, blank=True,
        on_delete=models.CASCADE, related_name='embeddings'
    )
    subtopic = models.ForeignKey(
        Subtopic, null=True, blank=True,
        on_delete=models.CASCADE, related_name='embeddings'
    )
    vector = ArrayField(
        base_field=models.FloatField(),
        size=384,
        help_text='Embedding vector'
    )
    model_name = models.CharField(
        max_length=100,
        default='all-MiniLM-L6-v2',
        help_text='Model used to produce this embedding'
    )
    embedded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ('document_chunk', 'model_name'),
            ('subtopic', 'model_name'),
        ]

    def __str__(self):
        target = self.document_chunk or self.subtopic
        return f"Embedding ({self.model_name}) for {target}"
