from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.db.models import JSONField
from django.utils import timezone

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
    uploaded_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

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
    token_count = models.IntegerField(blank=True, null=True)

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
    
    # Intent descriptions for better semantic embedding
    concept_intent = models.TextField(
        blank=True, null=True,
        help_text="Conceptual description for MiniLM embedding - explains what to understand"
    )
    code_intent = models.TextField(
        blank=True, null=True, 
        help_text="Code-focused description for CodeBERT embedding - explains what to implement"
    )

    class Meta:
        ordering = ['topic__zone__order', 'topic__name', 'name']

    def __str__(self):
        return f"{self.topic.name} - {self.name}"


class Embedding(models.Model):
    CONTENT_TYPE_CHOICES = [
        ('chunk', 'Document Chunk'),
        ('subtopic', 'Subtopic'),
    ]

    document_chunk = models.ForeignKey(
        DocumentChunk, null=True, blank=True,
        on_delete=models.CASCADE, related_name='embeddings'
    )
    subtopic = models.ForeignKey(
        Subtopic, null=True, blank=True,
        on_delete=models.CASCADE, related_name='embeddings'
    )
    content_type = models.CharField(
        max_length=20,
        choices=CONTENT_TYPE_CHOICES,
        help_text='Type of content being embedded (chunk or subtopic)'
    )
    minilm_vector = ArrayField(
        base_field=models.FloatField(),
        size=384,  # MiniLM dimension
        help_text='MiniLM embedding vector (384 dimensions)',
        null=True, blank=True
    )
    codebert_vector = ArrayField(
        base_field=models.FloatField(),
        size=768,  # CodeBERT dimension
        help_text='CodeBERT embedding vector (768 dimensions)', 
        null=True, blank=True
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
            ('document_chunk', 'model_type'),  # Allow one embedding per model type per chunk
            ('subtopic', 'model_type'),        # Allow one embedding per model type per subtopic
        ]

    def clean(self):
        """Validate that content_type matches the related object and vectors are properly set."""
        from django.core.exceptions import ValidationError
        
        if self.content_type == 'chunk' and not self.document_chunk:
            raise ValidationError("Content type 'chunk' requires a document_chunk")
        if self.content_type == 'subtopic' and not self.subtopic:
            raise ValidationError("Content type 'subtopic' requires a subtopic")
        if self.document_chunk and self.subtopic:
            raise ValidationError("Cannot have both document_chunk and subtopic")
        
        # Validate that at least one vector is provided
        if not self.minilm_vector and not self.codebert_vector:
            raise ValidationError("At least one embedding vector must be provided")

    def get_vector_for_model(self, model_type):
        """Get the appropriate vector based on model type."""
        if model_type == 'sentence' or 'minilm' in model_type.lower():
            return self.minilm_vector
        elif model_type == 'code_bert' or 'codebert' in model_type.lower():
            return self.codebert_vector
        else:
            # No fallback - require specific model types
            return None
    
    def set_vector_for_model(self, model_type, vector):
        """Set the appropriate vector based on model type."""
        if model_type == 'sentence' or 'minilm' in model_type.lower():
            self.minilm_vector = vector
            self.dimension = 384
        elif model_type == 'code_bert' or 'codebert' in model_type.lower():
            self.codebert_vector = vector
            self.dimension = 768
        else:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Unsupported model type: {model_type}")

    def save(self, *args, **kwargs):
        # Auto-set content_type based on related objects
        if not self.content_type:
            if self.document_chunk:
                self.content_type = 'chunk'
            elif self.subtopic:
                self.content_type = 'subtopic'
        
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        target = self.document_chunk or self.subtopic
        return f"Embedding for {target} ({self.content_type}, {self.model_type}, {self.dimension}d)"


class SemanticSubtopic(models.Model):
    """
    Stores semantic similarity between subtopics and chunk embeddings for RAG retrieval.
    
    This model stores the semantic similarity scores between a subtopic and document chunks:
    - Each subtopic gets analyzed against available chunks using dual embeddings
    - Concept chunks (MiniLM) are ranked separately from code chunks (CodeBERT)
    - Question generation uses these for targeted context retrieval
    
    The ranked fields contain lists of dictionaries:
    [{"chunk_id": 123, "similarity": 0.85, "chunk_type": "Concept"}, ...]
    Ordered by similarity score (highest first) for efficient top-k retrieval.
    """
    # One-to-one relationship with Subtopic
    subtopic = models.OneToOneField(
        Subtopic, 
        on_delete=models.CASCADE, 
        related_name='semantic_data',
        help_text="The subtopic this semantic analysis belongs to"
    )
    
    # Separate rankings for concept and code chunks
    ranked_concept_chunks = JSONField(
        default=list, 
        blank=True, 
        help_text="Ranked list of top concept chunks (MiniLM similarities), ordered by similarity (highest first)"
    )
    
    ranked_code_chunks = JSONField(
        default=list, 
        blank=True, 
        help_text="Ranked list of top code/example/exercise chunks (CodeBERT similarities), ordered by similarity (highest first)"
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['subtopic__name']
        indexes = [
            models.Index(fields=['subtopic']),
        ]
    
    def __str__(self):
        concept_count = len(self.ranked_concept_chunks) if self.ranked_concept_chunks else 0
        code_count = len(self.ranked_code_chunks) if self.ranked_code_chunks else 0
        return f"{self.subtopic.name} - {concept_count} concept, {code_count} code chunks"
    
    def get_concept_chunk_ids(self, limit=5, min_similarity=0.5):
        """
        Get ranked concept chunk IDs for RAG retrieval.
        """
        if not self.ranked_concept_chunks:
            return []
        
        filtered_chunks = [
            chunk for chunk in self.ranked_concept_chunks 
            if chunk.get('similarity', 0) >= min_similarity
        ]
        
        return [chunk['chunk_id'] for chunk in filtered_chunks[:limit]]
    
    def get_code_chunk_ids(self, limit=5, min_similarity=0.5):
        """
        Get ranked code chunk IDs for RAG retrieval.
        """
        if not self.ranked_code_chunks:
            return []
        
        filtered_chunks = [
            chunk for chunk in self.ranked_code_chunks 
            if chunk.get('similarity', 0) >= min_similarity
        ]
        
        return [chunk['chunk_id'] for chunk in filtered_chunks[:limit]]
    
    def get_top_chunk_ids(self, limit=5, chunk_type=None, min_similarity=0.5):
        """
        Get ranked chunk IDs for RAG retrieval based on semantic similarity.
        Legacy method - use get_concept_chunk_ids() or get_code_chunk_ids() for better performance.
        """
        if chunk_type == 'Concept':
            return self.get_concept_chunk_ids(limit=limit, min_similarity=min_similarity)
        elif chunk_type in ['Code', 'Example', 'Exercise', 'Try_It']:
            return self.get_code_chunk_ids(limit=limit, min_similarity=min_similarity)
        
        # If no specific type, combine both (legacy behavior)
        concept_chunks = self.get_concept_chunk_ids(limit=limit//2, min_similarity=min_similarity)
        code_chunks = self.get_code_chunk_ids(limit=limit//2, min_similarity=min_similarity)
        
        return concept_chunks + code_chunks
    
    def add_concept_ranking(self, chunk_id, similarity_score, chunk_type):
        """Add or update a concept chunk in the ranked list, maintaining sort order by similarity."""
        if not self.ranked_concept_chunks:
            self.ranked_concept_chunks = []
        
        # Remove existing entry for this chunk if it exists
        self.ranked_concept_chunks = [c for c in self.ranked_concept_chunks if c.get('chunk_id') != chunk_id]
        
        # Add new entry
        new_chunk = {
            'chunk_id': chunk_id,
            'similarity': similarity_score,
            'chunk_type': chunk_type,
            'model_type': 'sentence'  # MiniLM model
        }
        self.ranked_concept_chunks.append(new_chunk)
        
        # Re-sort by similarity (highest first) and keep only top 10
        self.ranked_concept_chunks.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        self.ranked_concept_chunks = self.ranked_concept_chunks[:10]
    
    def add_code_ranking(self, chunk_id, similarity_score, chunk_type):
        """Add or update a code chunk in the ranked list, maintaining sort order by similarity."""
        if not self.ranked_code_chunks:
            self.ranked_code_chunks = []
        
        # Remove existing entry for this chunk if it exists
        self.ranked_code_chunks = [c for c in self.ranked_code_chunks if c.get('chunk_id') != chunk_id]
        
        # Add new entry
        new_chunk = {
            'chunk_id': chunk_id,
            'similarity': similarity_score,
            'chunk_type': chunk_type,
            'model_type': 'code_bert'  # CodeBERT model
        }
        self.ranked_code_chunks.append(new_chunk)
        
        # Re-sort by similarity (highest first) and keep only top 10
        self.ranked_code_chunks.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        self.ranked_code_chunks = self.ranked_code_chunks[:10]
    
    def add_chunk_ranking(self, chunk_id, similarity_score, chunk_type):
        """Add or update a chunk in the appropriate ranked list based on chunk type."""
        if chunk_type == 'Concept':
            self.add_concept_ranking(chunk_id, similarity_score, chunk_type)
        elif chunk_type in ['Code', 'Example', 'Exercise', 'Try_It']:
            self.add_code_ranking(chunk_id, similarity_score, chunk_type)
        else:
            # Unknown chunk type - treat as concept by default
            self.add_concept_ranking(chunk_id, similarity_score, chunk_type)
    
    def get_chunks_by_type(self, chunk_type, limit=None):
        """Get chunk IDs of a specific type for this subtopic."""
        if chunk_type == 'Concept':
            chunks = self.ranked_concept_chunks
        elif chunk_type in ['Code', 'Example', 'Exercise', 'Try_It']:
            chunks = self.ranked_code_chunks
        else:
            # Unknown type - return empty list
            return []
        
        if not chunks:
            return []
        
        chunk_ids = [
            chunk['chunk_id'] for chunk in chunks 
            if chunk.get('chunk_type') == chunk_type
        ]
        
        return chunk_ids[:limit] if limit else chunk_ids
    
    def get_similarity_for_chunk_type(self, chunk_type):
        """Get highest similarity score for a specific chunk type."""
        if chunk_type == 'Concept':
            chunks = self.ranked_concept_chunks
        elif chunk_type in ['Code', 'Example', 'Exercise', 'Try_It']:
            chunks = self.ranked_code_chunks
        else:
            # Unknown type - return 0
            return 0.0
        
        if not chunks:
            return 0.0
        
        type_chunks = [c for c in chunks if c.get('chunk_type') == chunk_type]
        if not type_chunks:
            return 0.0
        
        # Return the highest similarity for this chunk type
        return max(c.get('similarity', 0) for c in type_chunks)
