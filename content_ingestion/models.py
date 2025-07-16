from django.db import models
from django.db.models import JSONField
from django.contrib.postgres.fields import ArrayField

class UploadedDocument(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="pdfs/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    parsed = models.BooleanField(default=False)
    
    # Track which pages have been processed
    parsed_pages = ArrayField(
        base_field=models.IntegerField(), 
        blank=True, 
        default=list
    )
    
    # Store document metadata
    total_pages = models.IntegerField(default=0)
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('PROCESSING', 'Processing'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed')
        ],
        default='PENDING'
    )
    
    # Store parsing metadata
    parse_metadata = JSONField(
        default=dict,
        blank=True,
        help_text="Stores parsing configuration and metrics"
    )

    def __str__(self):
        return f"{self.title} ({self.processing_status})"

class DocumentChunk(models.Model):
    document = models.ForeignKey(UploadedDocument, on_delete=models.CASCADE, related_name="chunks")
    
    chunk_type = models.CharField(max_length=50, choices=[
        ("Header", "Header"),
        ("Module", "Module"),
        ("Lesson", "Lesson"),
        ("Section", "Section"),
        ("Subsection", "Subsection"),
        ("Text", "Text"),
        ("Table", "Table"),
        ("Figure", "Figure"),
        ("Code", "Code"),
        ("Caption", "Caption"),
        ("Exercise", "Exercise"),
        ("Example", "Example"),
    ])
    
    text = models.TextField()
    page_number = models.IntegerField()  # Exact page number
    position_on_page = JSONField(
        default=dict,
        help_text="Coordinates of chunk on the page {x1, y1, x2, y2}"
    )
    order_in_doc = models.IntegerField()
    
    # Content classification
    topic_title = models.CharField(max_length=255, null=True, blank=True)
    subtopic_title = models.CharField(max_length=255, null=True, blank=True)
    
    # Parsing metadata
    confidence_score = models.FloatField(
        null=True, 
        blank=True,
        help_text="Confidence score from the parser"
    )
    parser_metadata = JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata from the parser"
    )

    class Meta:
        ordering = ['page_number', 'order_in_doc']

    def __str__(self):
        return f"{self.chunk_type}: {self.text[:50]}..."

class TOCEntry(models.Model):
    document = models.ForeignKey(UploadedDocument, on_delete=models.CASCADE)
    parent = models.ForeignKey(
        'self', 
        null=True, 
        blank=True, 
        on_delete=models.CASCADE,
        related_name='children'
    )
    
    title = models.CharField(max_length=255)
    level = models.IntegerField(
        default=0,
        help_text="Hierarchy level (0 for top-level entries)"
    )
    
    start_page = models.IntegerField()
    end_page = models.IntegerField(null=True, blank=True)
    order = models.IntegerField()
    
    # Content tracking
    chunked = models.BooleanField(
        default=False,
        help_text="Set to True once this TOC entry has been parsed and linked to chunks"
    )
    chunk_count = models.IntegerField(default=0)
    
    # Navigation helpers
    next_entry = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='previous_entry_set'
    )

    class Meta:
        ordering = ['order']
        unique_together = [['document', 'order']]

    def __str__(self):
        return f"{self.title} (Pages {self.start_page}-{self.end_page or '?'})"
