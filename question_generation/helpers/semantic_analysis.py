"""
Semantic Analysis Helper

Provides functionality to populate SemanticSubtopic models with semantic similarity analysis.
Converts the management command to a reusable helper function for better organization.
"""

from django.utils import timezone
from content_ingestion.models import Subtopic, DocumentChunk
from question_generation.models import SemanticSubtopic
import re
from typing import Dict, List, Optional


class SemanticAnalyzer:
    """
    Handles semantic similarity analysis between subtopics and document chunks.
    
    Uses lightweight MiniLM model for efficient semantic similarity computation.
    Results are stored in SemanticSubtopic for fast RAG retrieval.
    """
    
    def __init__(self):
        self.model = None
        self.cosine_similarity = None
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the semantic similarity model."""
        try:
            from sentence_transformers import SentenceTransformer
            from sklearn.metrics.pairwise import cosine_similarity
            
            # Use lightweight model that's reliable and fast
            model_name = 'all-MiniLM-L6-v2'
            self.model = SentenceTransformer(model_name)
            self.cosine_similarity = cosine_similarity
            print(f"✅ Lightweight transformer model loaded: {model_name}")
            
        except ImportError:
            print("❌ sentence-transformers not installed. Install with: pip install sentence-transformers scikit-learn")
            raise
        except Exception as e:
            print(f"❌ Could not load model: {e}")
            raise
    
    def populate_semantic_subtopics(self, 
                                  reanalyze: bool = False, 
                                  limit: Optional[int] = None,
                                  min_similarity: float = 0.5,
                                  verbose: bool = True) -> Dict[str, int]:
        """
        Populate SemanticSubtopic models with semantic similarity analysis.
        
        Args:
            reanalyze: Force reanalysis of existing entries
            limit: Limit number of subtopics to process
            min_similarity: Minimum similarity threshold (0.0-1.0)
            verbose: Print progress messages
            
        Returns:
            Dict with statistics: {'created': int, 'updated': int, 'processed': int}
        """
        if verbose:
            print("🚀 Starting SemanticSubtopic population with semantic similarity...")
        
        if not self.model:
            raise RuntimeError("Semantic model not initialized")
        
        # Get subtopics to process
        subtopics_qs = Subtopic.objects.select_related('topic')
        if limit:
            subtopics_qs = subtopics_qs[:limit]
        
        subtopics = list(subtopics_qs)
        if not subtopics:
            if verbose:
                print("❌ No subtopics found")
            return {'created': 0, 'updated': 0, 'processed': 0}
        
        # Get chunks with embeddings for similarity calculation
        chunks = list(DocumentChunk.objects.filter(embeddings__isnull=False))
        if not chunks:
            if verbose:
                print("❌ No chunks with embeddings found")
            return {'created': 0, 'updated': 0, 'processed': 0}
        
        if verbose:
            print(f"📊 Processing {len(subtopics)} subtopics against {len(chunks)} chunks")
            print(f"🎯 Minimum similarity threshold: {min_similarity:.1%}")
        
        stats = {'created': 0, 'updated': 0, 'processed': 0}
        
        for idx, subtopic in enumerate(subtopics, 1):
            if verbose and idx % 10 == 0:
                print(f"Progress: {idx}/{len(subtopics)} subtopics processed")
            
            try:
                result = self._analyze_subtopic_semantic_similarity(
                    subtopic, chunks, min_similarity, reanalyze
                )
                
                if result['created']:
                    stats['created'] += 1
                elif result['updated']:
                    stats['updated'] += 1
                    
                stats['processed'] += 1
                
            except Exception as e:
                if verbose:
                    print(f"❌ Error processing {subtopic.name}: {e}")
                continue
        
        if verbose:
            print(f"\n✅ Semantic analysis complete!")
            print(f"📊 Results: {stats['created']} created, {stats['updated']} updated, {stats['processed']} total processed")
        
        return stats
    
    def _analyze_subtopic_semantic_similarity(self, 
                                            subtopic: Subtopic, 
                                            chunks: List[DocumentChunk],
                                            min_similarity: float,
                                            reanalyze: bool) -> Dict[str, bool]:
        """Analyze semantic similarity for a single subtopic."""
        
        # Get or create SemanticSubtopic
        semantic_subtopic, created = SemanticSubtopic.objects.get_or_create(
            subtopic=subtopic,
            defaults={'ranked_chunks': []}
        )
        
        # Skip if already analyzed and not forcing reanalysis
        if (not created and not reanalyze and semantic_subtopic.ranked_chunks):
            return {'created': False, 'updated': False}
        
        # Generate subtopic embedding
        subtopic_text = f"{subtopic.topic.name} - {subtopic.name}"
        subtopic_embedding = self.model.encode([subtopic_text])[0]
        
        # Calculate similarities with all chunks
        ranked_chunks = []
        
        for chunk in chunks:
            # Get chunk embedding
            chunk_embedding_obj = chunk.embeddings.first()
            if not chunk_embedding_obj or not chunk_embedding_obj.vector:
                continue
            
            # Calculate cosine similarity
            import numpy as np
            chunk_vector = np.array(chunk_embedding_obj.vector)
            similarity = np.dot(subtopic_embedding, chunk_vector) / (
                np.linalg.norm(subtopic_embedding) * np.linalg.norm(chunk_vector)
            )
            
            # Only include chunks above similarity threshold
            if similarity >= min_similarity:
                ranked_chunks.append({
                    'chunk_id': chunk.id,
                    'similarity': float(similarity),
                    'chunk_type': chunk.chunk_type
                })
        
        # Sort by similarity (highest first)
        ranked_chunks.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Update semantic subtopic (removed metadata calculations)
        semantic_subtopic.ranked_chunks = ranked_chunks
        semantic_subtopic.save()
        
        return {'created': created, 'updated': not created}


# Helper function for easy usage
def populate_semantic_subtopics(reanalyze: bool = False, 
                              limit: Optional[int] = None,
                              min_similarity: float = 0.5,
                              verbose: bool = True) -> Dict[str, int]:
    """
    Convenience function to populate semantic subtopics.
    
    Args:
        reanalyze: Force reanalysis of existing entries
        limit: Limit number of subtopics to process  
        min_similarity: Minimum similarity threshold (0.0-1.0)
        verbose: Print progress messages
        
    Returns:
        Dict with statistics: {'created': int, 'updated': int, 'processed': int}
    """
    analyzer = SemanticAnalyzer()
    return analyzer.populate_semantic_subtopics(
        reanalyze=reanalyze,
        limit=limit, 
        min_similarity=min_similarity,
        verbose=verbose
    )
