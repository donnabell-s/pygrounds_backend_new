import os
from typing import List, Dict, Any
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class EmbeddingGenerator:
    """
    Handles embedding generation for document chunks using sentence-transformers.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedding generator with sentence-transformers.
        
        Args:
            model_name: Sentence transformer model to use
        """
        self.model_name = model_name
        self.dimension = 384  # all-MiniLM-L6-v2 dimension
        self.model = None
        
        # Lazy load the model
        self._load_model()
    
    def _load_model(self):
        """Load the sentence transformer model."""
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Loaded sentence transformer model: {self.model_name}")
        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
            self.model = None
        except Exception as e:
            logger.error(f"Failed to load model {self.model_name}: {str(e)}")
            self.model = None
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            if self.model is None:
                logger.error("Model not loaded")
                return None
                
            # Clean and prepare text
            clean_text = self._prepare_text_for_embedding(text)
            
            # Generate embedding using sentence-transformers
            embedding = self.model.encode(clean_text)
            
            # Convert numpy array to list
            embedding_list = embedding.tolist()
            
            logger.info(f"Generated embedding for text (length: {len(clean_text)}) -> vector dim: {len(embedding_list)}")
            return embedding_list
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            return None
    
    def generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        try:
            if self.model is None:
                logger.error("Model not loaded")
                return [None] * len(texts)
                
            # Clean texts
            clean_texts = [self._prepare_text_for_embedding(text) for text in texts]
            
            # Generate embeddings in batch (much faster)
            embeddings = self.model.encode(clean_texts)
            
            # Convert numpy arrays to lists
            embeddings_list = [embedding.tolist() for embedding in embeddings]
            
            logger.info(f"Generated {len(embeddings_list)} embeddings in batch")
            return embeddings_list
            
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {str(e)}")
            return [None] * len(texts)
    
    def _prepare_text_for_embedding(self, text: str) -> str:
        """
        Clean and prepare text for embedding generation.
        
        Args:
            text: Raw text from chunk
            
        Returns:
            Cleaned text ready for embedding
        """
        if not text:
            return ""
        
        # Basic cleaning
        clean_text = text.strip()
        
        # Remove excessive whitespace
        clean_text = ' '.join(clean_text.split())
        
        # Truncate if too long (OpenAI has token limits)
        max_chars = 8000  # Conservative limit
        if len(clean_text) > max_chars:
            clean_text = clean_text[:max_chars]
            logger.warning(f"Text truncated from {len(text)} to {len(clean_text)} chars")
        
        return clean_text
    
    def embed_chunk(self, chunk) -> bool:
        """
        Generate and save embedding for a DocumentChunk instance.
        
        Args:
            chunk: DocumentChunk instance
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate embedding
            embedding = self.generate_embedding(chunk.text)
            
            if embedding is None:
                return False
            
            # Save to chunk
            chunk.embedding = embedding
            chunk.embedding_model = self.model_name
            chunk.embedded_at = timezone.now()
            chunk.save(update_fields=['embedding', 'embedding_model', 'embedded_at'])
            
            logger.info(f"Embedded chunk {chunk.id} with {len(embedding)}-dim vector")
            return True
            
        except Exception as e:
            logger.error(f"Failed to embed chunk {chunk.id}: {str(e)}")
            return False
    
    def embed_chunks_batch(self, chunks) -> Dict[str, Any]:
        """
        Generate embeddings for multiple chunks in batch.
        
        Args:
            chunks: QuerySet or list of DocumentChunk instances
            
        Returns:
            Dictionary with embedding results and statistics
        """
        if not chunks:
            return {'success': 0, 'failed': 0, 'total': 0}
        
        chunk_list = list(chunks)
        texts = [chunk.text for chunk in chunk_list]
        
        logger.info(f"Starting batch embedding for {len(chunk_list)} chunks")
        
        # Generate embeddings in batch
        embeddings = self.generate_batch_embeddings(texts)
        
        success_count = 0
        failed_count = 0
        
        # Save embeddings to chunks
        for chunk, embedding in zip(chunk_list, embeddings):
            try:
                if embedding is not None:
                    chunk.embedding = embedding
                    chunk.embedding_model = self.model_name
                    chunk.embedded_at = timezone.now()
                    chunk.save(update_fields=['embedding', 'embedding_model', 'embedded_at'])
                    success_count += 1
                else:
                    failed_count += 1
                    logger.warning(f"No embedding generated for chunk {chunk.id}")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to save embedding for chunk {chunk.id}: {str(e)}")
        
        results = {
            'success': success_count,
            'failed': failed_count,
            'total': len(chunk_list),
            'model': self.model_name
        }
        
        logger.info(f"Batch embedding complete: {success_count}/{len(chunk_list)} successful")
        return results
