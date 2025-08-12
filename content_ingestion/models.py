from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.db.models import JSONField

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

PROCESSING_STATUS = [
    ('PENDING', 'Pending'),
    ('PROCESSING', 'Processing'),
    ('COMPLETED', 'Completed'),
    ('FAILED', 'Failed'),
]


class UploadedDocument(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='pdfs/')

    processing_status = models.CharField(
        max_length=20,
        choices=PROCESSING_STATUS,
        default='PENDING',
    )
    parsed_pages = ArrayField(
        base_field=models.IntegerField(),
        default=list,
        blank=True,
        help_text='Pages already parsed'
    )
    total_pages = models.IntegerField(default=0)

    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='beginner',
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

    # Classification - keeping the hierarchy structure but removing redundant topic_title
    subtopic_title = models.CharField(max_length=255, blank=True, null=True)

    # Token info for LLM optimization - simplified to just count
    token_count = models.IntegerField(blank=True, null=True)
    parser_metadata = JSONField(default=dict, blank=True, help_text='Stores book title, extraction method, and other processing metadata')

    # Note: Embeddings are now stored in separate Embedding model for better organization

    class Meta:
        ordering = ['page_number', 'order_in_doc']

    def __str__(self):
        preview = (self.text[:50] + '...') if len(self.text) > 50 else self.text
        return f"{self.chunk_type}: {preview}"


class TOCEntry(models.Model):
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

    name = models.CharField(max_length=100)
    description = models.TextField()
    order = models.IntegerField(unique=True)
    is_unlocked = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Zone {self.order}: {self.name}"


class Topic(models.Model):

    zone = models.ForeignKey(GameZone, on_delete=models.CASCADE, related_name='topics')
    name = models.CharField(max_length=100)
    description = models.TextField()

    class Meta:
        ordering = ['zone__order', 'name']

    def __str__(self):
        return f"{self.zone.name} - {self.name}"


class Subtopic(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='subtopics')
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ['topic__zone__order', 'topic__name', 'name']

    def __str__(self):
        return f"{self.topic.name} - {self.name}"


class Embedding(models.Model):

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
        size=768,  # Increased to support CodeBERT (768) and Sentence Transformers (384)
        help_text='Embedding vector - dimension depends on model used'
    )
    model_name = models.CharField(
        max_length=100,
        default='all-MiniLM-L6-v2',
        help_text='Name of the embedding model used (e.g., codebert-base, all-MiniLM-L6-v2)'
    )
    model_type = models.CharField(
        max_length=50,
        default='sentence',
        help_text='Type of model: code_bert, sentence, general'
    )
    dimension = models.IntegerField(
        default=384,
        help_text='Actual dimension of the embedding vector'
    )
    embedded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ('document_chunk', 'model_type'),  # Allow multiple models per chunk
            ('subtopic', 'model_type'),
        ]

    def __str__(self):
        target = self.document_chunk or self.subtopic
        return f"Embedding for {target} ({self.model_type}, {self.dimension}d)"
