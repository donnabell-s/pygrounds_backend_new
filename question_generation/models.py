"""
Question Generation Models

This module defines the core models for the question generation system:

1. SemanticSubtopic: Stores semantic similarity analysis results for efficient RAG retrieval
2. GeneratedQuestion: Stores generated questions with metadata and game-specific data
3. PreAssessmentQuestion: Stores manually-authored pre-assessment questions

The semantic system works by:
- Computing semantic similarity between subtopics and content chunks
- Storing ranked chunk IDs with confidence scores in SemanticSubtopic
- Using these pre-computed rankings for fast RAG context retrieval during question generation
"""

from django.db import models
from django.db.models import JSONField
from content_ingestion.models import Topic, Subtopic, DocumentChunk


class SemanticSubtopic(models.Model):
    """
    Stores semantic similarity between subtopics and chunk embeddings for RAG retrieval.
    
    This model stores the semantic similarity scores between a subtopic and document chunks:
    - Each subtopic gets analyzed against available chunks using embeddings
    - Results stored as ranked chunk IDs with similarity scores  
    - Question generation uses these for fast context retrieval
    
    The ranked_chunks field contains a list of dictionaries:
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
    
    # Pre-computed ranked list of similar chunks
    ranked_chunks = JSONField(
        default=list, 
        blank=True, 
        help_text="Ranked list of chunk IDs with similarity scores, ordered by similarity (highest first)"
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['subtopic__name']
        indexes = [
            models.Index(fields=['subtopic']),
        ]
    
    def __str__(self):
        chunk_count = len(self.ranked_chunks) if self.ranked_chunks else 0
        return f"{self.subtopic.name} - {chunk_count} similar chunks"
    
    def get_top_chunk_ids(self, limit=5, chunk_type=None, min_similarity=0.5):
        """
        Get ranked chunk IDs for RAG retrieval based on semantic similarity.
        """
        if not self.ranked_chunks:
            return []
        
        # Filter by chunk type and similarity threshold
        filtered_chunks = self.ranked_chunks
        if chunk_type:
            filtered_chunks = [
                chunk for chunk in filtered_chunks 
                if chunk.get('chunk_type') == chunk_type and chunk.get('similarity', 0) >= min_similarity
            ]
        else:
            filtered_chunks = [
                chunk for chunk in filtered_chunks 
                if chunk.get('similarity', 0) >= min_similarity
            ]
        
        # Return top chunk IDs (already sorted by similarity in ranked_chunks)
        return [chunk['chunk_id'] for chunk in filtered_chunks[:limit]]
    
    def add_chunk_ranking(self, chunk_id, similarity_score, chunk_type):
        """Add or update a chunk in the ranked list, maintaining sort order by similarity."""
        if not self.ranked_chunks:
            self.ranked_chunks = []
        
        # Remove existing entry for this chunk if it exists
        self.ranked_chunks = [c for c in self.ranked_chunks if c.get('chunk_id') != chunk_id]
        
        # Add new entry
        new_chunk = {
            'chunk_id': chunk_id,
            'similarity': similarity_score,
            'chunk_type': chunk_type
        }
        self.ranked_chunks.append(new_chunk)
        
        # Re-sort by similarity (highest first)
        self.ranked_chunks.sort(key=lambda x: x.get('similarity', 0), reverse=True)
    
    def get_chunks_by_type(self, chunk_type, limit=None):
        """Get chunk IDs of a specific type for this subtopic."""
        if not self.ranked_chunks:
            return []
        
        chunk_ids = [
            chunk['chunk_id'] for chunk in self.ranked_chunks 
            if chunk.get('chunk_type') == chunk_type
        ]
        
        return chunk_ids[:limit] if limit else chunk_ids
    
    def get_similarity_for_chunk_type(self, chunk_type):
        """Get highest similarity score for a specific chunk type."""
        if not self.ranked_chunks:
            return 0.0
        
        type_chunks = [c for c in self.ranked_chunks if c.get('chunk_type') == chunk_type]
        if not type_chunks:
            return 0.0
        
        # Return the highest similarity for this chunk type
        return max(c.get('similarity', 0) for c in type_chunks)


class GeneratedQuestion(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='generated_questions')
    subtopic = models.ForeignKey(Subtopic, on_delete=models.CASCADE, related_name='generated_questions')

    question_text = models.TextField(blank=True)  # Could be clue, prompt, description, etc.
    answer_options = JSONField(default=list, blank=True, null=True)  # MCQ options if applicable
    correct_answer = models.TextField(blank=True)
    explanation = models.TextField(blank=True, null=True)

    estimated_difficulty = models.CharField(
        max_length=20,
        choices=[('beginner','Beginner'), ('intermediate','Intermediate'), ('advanced','Advanced'), ('master','Master')],
        default='beginner',
        blank=True,
    )
    
    game_type = models.CharField(max_length=20, choices=[('coding','Coding'), ('non_coding','Non-Coding')], default='non_coding')
    minigame_type = models.CharField(
        max_length=30,
        choices=[
            ('hangman_coding', 'Hangman-Style Coding Game'),
            ('ship_debugging', 'Ship Debugging Game'),
            ('word_search', 'Word Search Puzzle'),
            ('crossword', 'Crossword Puzzle'),
        ],
        default='generic', null=True
    )

    # Flexible field for storing game-specific data:
    game_data = JSONField(default=dict, blank=True)

    # Metadata & tracking
    quality_score = models.FloatField(null=True, blank=True)
    validation_status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending Validation'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('needs_review', 'Needs Review')],
        default='pending'
    )
   
    class Meta:
        ordering = ['subtopic__name']
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

