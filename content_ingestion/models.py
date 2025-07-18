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
    
    # Embedding fields for RAG
    embedding = ArrayField(
        base_field=models.FloatField(),
        size=384,  # all-MiniLM-L6-v2 dimension
        null=True,
        blank=True,
        help_text="Vector embedding for semantic search and RAG"
    )
    embedding_model = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Model used to generate embedding (e.g., all-MiniLM-L6-v2)"
    )
    embedded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when embedding was generated"
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

class GameZone(models.Model):
    """
    Represents a gameplay zone in PyGrounds (e.g., Python Basics Zone, Advanced Concepts Zone)
    """
    name = models.CharField(max_length=100)
    description = models.TextField()
    order = models.IntegerField(unique=True, help_text="Order in which zones appear")
    is_active = models.BooleanField(default=True)
    
    # Zone progression
    required_exp = models.IntegerField(
        default=0,
        help_text="Experience points required to unlock this zone"
    )
    max_exp = models.IntegerField(
        default=1000,
        help_text="Maximum experience points needed to complete this zone and unlock the next"
    )
    is_unlocked = models.BooleanField(
        default=False,
        help_text="Whether this zone is unlocked for play"
    )
    
    def __str__(self):
        return f"Zone {self.order}: {self.name}"
    
    class Meta:
        ordering = ['order']

class Topic(models.Model):
    """
    Main programming topics within a zone (e.g., Introduction to Python, Control Flow)
    Topics serve as containers for subtopics - proficiency is tracked at subtopic level
    """
    zone = models.ForeignKey(GameZone, on_delete=models.CASCADE, related_name='topics')
    name = models.CharField(max_length=100)
    description = models.TextField()
    order = models.IntegerField(help_text="Order within the zone")
    
    # Basic progression tracking
    min_zone_exp = models.IntegerField(
        default=0,
        help_text="Minimum zone experience required to unlock this topic"
    )
    is_unlocked = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.zone.name} - {self.name}"
    
    class Meta:
        ordering = ['zone__order', 'order']
        unique_together = [['zone', 'order']]

class Subtopic(models.Model):
    """
    Specific concepts within a topic (e.g., Using input(), String Formatting)
    Each subtopic will have 5 difficulty levels generated by LLM after RAG processing
    """
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='subtopics')
    name = models.CharField(max_length=100)
    description = models.TextField()
    order = models.IntegerField(help_text="Order within the topic")
    
    # Learning objectives (for LLM context)
    learning_objectives = JSONField(default=list, blank=True)
    
    # Content structure metadata
    difficulty_levels = models.IntegerField(
        default=5,
        help_text="Number of difficulty levels (exercises will be generated for each)"
    )
    
    # Basic progression - detailed tracking will be in user_learning app
    min_zone_exp = models.IntegerField(
        default=0,
        help_text="Minimum zone experience required to unlock this subtopic"
    )
    is_unlocked = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.topic.name} - {self.name}"
    
    class Meta:
        ordering = ['topic__zone__order', 'topic__order', 'order']
        unique_together = [['topic', 'order']]

class ContentMapping(models.Model):
    """
    Maps TOC entries to game zones, topics, and subtopics
    """
    toc_entry = models.ForeignKey(TOCEntry, on_delete=models.CASCADE, related_name='content_mappings')
    zone = models.ForeignKey(GameZone, null=True, blank=True, on_delete=models.SET_NULL)
    topic = models.ForeignKey(Topic, null=True, blank=True, on_delete=models.SET_NULL)
    subtopic = models.ForeignKey(Subtopic, null=True, blank=True, on_delete=models.SET_NULL)
    
    # Mapping confidence and metadata
    confidence_score = models.FloatField(default=0.0)
    mapping_metadata = JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"{self.toc_entry.title} -> {self.subtopic.name if self.subtopic else 'Unmapped'}"
        
    class Meta:
        unique_together = [['toc_entry', 'zone', 'topic', 'subtopic']]
