"""
Embedding generator with multi-model support and parallel processing.
"""

import os
import threading
import time
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from django.utils import timezone

from .models import (
    EmbeddingModelType, EmbeddingConfig, MODEL_CONFIGS, CHUNK_TYPE_TO_MODEL
)

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Embedding generator that uses different models based on chunk type.
    Supports multi-threading and batch processing for performance.
    """
    
    def __init__(self, max_workers: int = 4, use_gpu: bool = False):
        """
        Initialize embedding generator.
        
        Args:
            max_workers: Number of worker threads for parallel processing
            use_gpu: Whether to use GPU acceleration (if available)
        """
        self.max_workers = max_workers
        self.use_gpu = use_gpu
        self.models = {}  # Cache loaded models
        self._model_lock = threading.Lock()
        
        logger.info(f"Initialized EmbeddingGenerator with {max_workers} workers, GPU: {use_gpu}")
    
    def _get_model_type_for_chunk(self, chunk_type: str) -> EmbeddingModelType:
        """
        Determine the best embedding model for a chunk type.
        
        Args:
            chunk_type: Type of the chunk (Code, Concept, etc.)
            
        Returns:
            EmbeddingModelType to use for this chunk
        """
        return CHUNK_TYPE_TO_MODEL.get(chunk_type, EmbeddingModelType.SENTENCE_TRANSFORMER)
    
    def _load_model(self, model_type: EmbeddingModelType) -> Optional[Any]:
        """
        Load and cache a specific embedding model.
        
        Args:
            model_type: Type of model to load
            
        Returns:
            Loaded model or None if failed
        """
        with self._model_lock:
            if model_type in self.models:
                return self.models[model_type]
            
            config = MODEL_CONFIGS[model_type]
            logger.info(f"Loading {model_type.value} model: {config.model_name}")
            
            try:
                if model_type == EmbeddingModelType.CODE_BERT:
                    # Load CodeBERT model
                    from transformers import AutoModel, AutoTokenizer
                    import torch
                    
                    model = AutoModel.from_pretrained(config.model_name)
                    tokenizer = AutoTokenizer.from_pretrained(config.model_name)
                    
                    if self.use_gpu and torch.cuda.is_available():
                        model = model.cuda()
                        logger.info(f"Moved {config.model_name} to GPU")
                    
                    self.models[model_type] = {
                        'model': model,
                        'tokenizer': tokenizer,
                        'config': config
                    }
                    
                elif model_type == EmbeddingModelType.SENTENCE_TRANSFORMER:
                    # Load Sentence Transformer model
                    from sentence_transformers import SentenceTransformer
                    import torch
                    
                    device = 'cuda' if (self.use_gpu and torch.cuda.is_available()) else 'cpu'
                    model = SentenceTransformer(config.model_name, device=device)
                    
                    self.models[model_type] = {
                        'model': model,
                        'config': config
                    }
                
                logger.info(f"Successfully loaded {model_type.value} model")
                return self.models[model_type]
                
            except ImportError as e:
                logger.error(f"Missing dependencies for {model_type.value}: {e}")
                logger.info("Install with: pip install transformers sentence-transformers torch")
                return None
            except Exception as e:
                logger.error(f"Failed to load {model_type.value} model: {e}")
                return None
    
    def _generate_codebert_embedding(self, text: str, model_data: dict) -> Optional[List[float]]:
        """
        Generate embedding using CodeBERT model.
        
        Args:
            text: Code/exercise text to embed
            model_data: Loaded CodeBERT model and tokenizer
            
        Returns:
            Embedding vector or None if failed
        """
        try:
            import torch
            
            model = model_data['model']
            tokenizer = model_data['tokenizer']
            config = model_data['config']
            
            # Tokenize and truncate
            inputs = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=config.max_length
            )
            
            if self.use_gpu and torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            # Generate embedding
            with torch.no_grad():
                outputs = model(**inputs)
                # Use [CLS] token embedding (first token)
                embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()[0]
            
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"CodeBERT embedding failed: {e}")
            return None
    
    def _generate_sentence_embedding(self, text: str, model_data: dict) -> Optional[List[float]]:
        """
        Generate embedding using Sentence Transformer model.
        
        Args:
            text: Concept text to embed
            model_data: Loaded sentence transformer model
            
        Returns:
            Embedding vector or None if failed
        """
        try:
            model = model_data['model']
            embedding = model.encode(text)
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Sentence transformer embedding failed: {e}")
            return None
    
    def generate_subtopic_embedding(self, subtopic_name: str, topic_name: str = "") -> Dict[str, Any]:
        """
        Generate embedding for subtopic names using Sentence Transformer model.
        Subtopic names are conceptual/semantic content, so always use sentence model.
        
        Args:
            subtopic_name: Name of the subtopic
            topic_name: Optional topic name for additional context
            
        Returns:
            Dictionary containing embedding data
        """
        # Combine topic and subtopic names for better semantic representation
        if topic_name:
            text = f"{topic_name} - {subtopic_name}"
        else:
            text = subtopic_name
        
        # Always use Sentence Transformer for subtopic names (conceptual content)
        return self.generate_embedding(text, chunk_type='Concept')
    
    def generate_embedding(self, text: str, chunk_type: str) -> Dict[str, Any]:
        """
        Generate embedding for text using the appropriate model based on chunk type.
        
        Args:
            text: Text to embed
            chunk_type: Type of chunk (determines model selection)
            
        Returns:
            Dictionary containing embedding data or None if failed
        """
        try:
            # Determine model type
            model_type = self._get_model_type_for_chunk(chunk_type)
            
            # Load model if not cached
            model_data = self._load_model(model_type)
            if model_data is None:
                return {
                    'vector': None,
                    'model_name': MODEL_CONFIGS[model_type].model_name,
                    'model_type': model_type,
                    'dimension': 0,
                    'error': f"Failed to load {model_type.value} model"
                }
            
            # Clean text
            clean_text = self._prepare_text_for_embedding(text, model_data['config'])
            
            # Generate embedding based on model type
            if model_type == EmbeddingModelType.CODE_BERT:
                embedding = self._generate_codebert_embedding(clean_text, model_data)
            else:
                embedding = self._generate_sentence_embedding(clean_text, model_data)
            
            if embedding is None:
                return {
                    'vector': None,
                    'model_name': model_data['config'].model_name,
                    'model_type': model_type,
                    'dimension': 0,
                    'error': f"Embedding generation failed for {model_type.value}"
                }
            
            logger.debug(f"Generated {len(embedding)}-dim embedding using {model_type.value}")
            
            return {
                'vector': embedding,
                'model_name': model_data['config'].model_name,  # Use actual model name from config
                'model_type': model_type,
                'dimension': len(embedding),
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            return {
                'vector': None,
                'model_name': 'unknown',
                'model_type': None,
                'dimension': 0,
                'error': str(e)
            }
    
    def _prepare_text_for_embedding(self, text: str, config: EmbeddingConfig) -> str:
        """
        Prepare text for embedding based on model configuration.
        
        Args:
            text: Raw text
            config: Model configuration
            
        Returns:
            Cleaned and truncated text
        """
        if not text:
            return ""
        
        # Basic cleaning
        clean_text = text.strip()
        clean_text = ' '.join(clean_text.split())
        
        # Model-specific preparation
        if config.model_type == EmbeddingModelType.CODE_BERT:
            # For code, preserve structure better
            # Keep some formatting but normalize excessive whitespace
            lines = text.split('\n')
            clean_lines = [line.strip() for line in lines if line.strip()]
            clean_text = '\n'.join(clean_lines)
        
        # Truncate based on model's max length
        # Rough estimate: 4 characters per token
        max_chars = config.max_length * 4
        if len(clean_text) > max_chars:
            clean_text = clean_text[:max_chars]
            logger.debug(f"Text truncated to {len(clean_text)} chars for {config.model_type.value}")
        
        return clean_text

    def generate_batch_embeddings(self, chunks: List[Any]) -> Dict[str, Any]:
        """
        Generate embeddings for multiple chunks using appropriate models and parallel processing.
        
        Args:
            chunks: List of DocumentChunk instances
            
        Returns:
            Dictionary with results and statistics
        """
        if not chunks:
            return {'success': 0, 'failed': 0, 'total': 0, 'models_used': {}}
        
        logger.info(f"Starting batch embedding for {len(chunks)} chunks with {self.max_workers} workers")
        
        # Group chunks by model type for efficient batch processing
        chunks_by_model = {}
        for chunk in chunks:
            model_type = self._get_model_type_for_chunk(chunk.chunk_type)
            if model_type not in chunks_by_model:
                chunks_by_model[model_type] = []
            chunks_by_model[model_type].append(chunk)
        
        logger.info(f"Chunks grouped by model: {[(mt.value, len(chs)) for mt, chs in chunks_by_model.items()]}")
        
        results = {
            'success': 0,
            'failed': 0, 
            'total': len(chunks),
            'models_used': {},
            'processing_time': 0,
            'embeddings': []
        }
        
        start_time = time.time()
        
        # Process each model group separately for better efficiency
        for model_type, model_chunks in chunks_by_model.items():
            logger.info(f"Processing {len(model_chunks)} chunks with {model_type.value}")
            
            try:
                # Process chunks in batches based on model configuration
                config = MODEL_CONFIGS[model_type]
                batch_results = self.embed_chunks_batch(model_chunks)
                
                results['success'] += batch_results.get('success', 0)
                results['failed'] += batch_results.get('failed', 0)
                results['models_used'][model_type.value] = len(model_chunks)
                results['embeddings'].extend(batch_results.get('embeddings', []))
                
            except Exception as e:
                logger.error(f"Batch processing failed for model {model_type}: {e}")
                results['failed'] += len(model_chunks)
        
        results['processing_time'] = time.time() - start_time
        logger.info(f"Batch embedding completed: {results['success']} success, {results['failed']} failed")
        
        return results

    def embed_and_save_batch(self, chunks: List[Any]) -> Dict[str, Any]:
        """
        Generate embeddings and save to database in one operation.
        
        Args:
            chunks: List of DocumentChunk instances
            
        Returns:
            Dictionary with results and statistics
        """
        embedding_results = self.generate_batch_embeddings(chunks)
        
        if embedding_results['embeddings']:
            save_results = self.save_embeddings_to_db(embedding_results['embeddings'])
            
            return {
                'total_chunks': embedding_results['total'],
                'embeddings_generated': embedding_results['success'],
                'embeddings_failed': embedding_results['failed'],
                'database_saves': save_results.get('success', 0),
                'database_errors': save_results.get('failed', 0),
                'models_used': embedding_results['models_used'],
                'processing_time': embedding_results['processing_time']
            }
        
        return {
            'total_chunks': embedding_results['total'],
            'embeddings_generated': 0,
            'embeddings_failed': embedding_results['failed'],
            'database_saves': 0,
            'database_errors': 0,
            'models_used': embedding_results['models_used'],
            'processing_time': embedding_results['processing_time']
        }

    def save_embeddings_to_db(self, embeddings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Save embeddings to database.
        
        Args:
            embeddings: List of embedding data dictionaries
            
        Returns:
            Dictionary with save results
        """
        from content_ingestion.models import Embedding
        
        success = 0
        failed = 0
        start_time = time.time()
        
        for embedding_data in embeddings:
            try:
                chunk = embedding_data['chunk']
                vector = embedding_data['embedding']
                
                # Create or update embedding
                embedding_obj, created = Embedding.objects.get_or_create(
                    subtopic_id=chunk.subtopic_id if hasattr(chunk, 'subtopic_id') else None,
                    defaults={
                        'vector': vector,
                        'model_used': embedding_data.get('model_type', 'unknown'),
                        'embedded_at': timezone.now()
                    }
                )
                
                if not created:
                    # Update existing embedding
                    embedding_obj.vector = vector
                    embedding_obj.model_used = embedding_data.get('model_type', 'unknown')
                    embedding_obj.embedded_at = timezone.now()
                    embedding_obj.save()
                
                success += 1
                logger.debug(f"Saved embedding for chunk {chunk.id}")
                
            except Exception as e:
                failed += 1
                logger.error(f"DB save failed for chunk {embedding_data.get('chunk', {}).get('id', 'unknown')}: {e}")
        
        return {
            'success': success,
            'failed': failed,
            'processing_time': time.time() - start_time
        }


# Convenience functions for easy usage
def get_embedding_generator(max_workers: int = 4, use_gpu: bool = False) -> EmbeddingGenerator:
    """
    Get an instance of EmbeddingGenerator with optimal settings.
    
    Args:
        max_workers: Number of parallel workers
        use_gpu: Whether to use GPU acceleration
        
    Returns:
        Configured EmbeddingGenerator instance
    """
    return EmbeddingGenerator(max_workers=max_workers, use_gpu=use_gpu)



def embed_chunks_with_models(chunks: List[Any], max_workers: int = 4, use_gpu: bool = False) -> Dict[str, Any]:
    """
    Backward compatibility function for embedding chunks with appropriate models.
    
    Args:
        chunks: List of DocumentChunk instances
        max_workers: Number of parallel workers
        use_gpu: Whether to use GPU acceleration
        
    Returns:
        Dictionary with embedding results
    """
    generator = EmbeddingGenerator(max_workers=max_workers, use_gpu=use_gpu)
    return generator.generate_batch_embeddings(chunks)
