"""
Embedding system with multi-model support and batch processing.
"""

from .models import EmbeddingModelType, EmbeddingConfig, MODEL_CONFIGS, CHUNK_TYPE_TO_MODEL
from .generator import EmbeddingGenerator, embed_chunks_with_models

# Main exports
__all__ = [
    'EmbeddingModelType',
    'EmbeddingConfig', 
    'MODEL_CONFIGS',
    'CHUNK_TYPE_TO_MODEL',
    'EmbeddingGenerator',
    'embed_chunks_with_models',
]
