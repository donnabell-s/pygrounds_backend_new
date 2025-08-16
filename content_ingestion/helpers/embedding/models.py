from dataclasses import dataclass
from enum import Enum
from typing import Dict


class EmbeddingModelType(Enum):
    """Types of embedding models for different content types"""
    CODE_BERT = "code_bert"       
    SENTENCE_TRANSFORMER = "sentence"  


@dataclass
class EmbeddingConfig:
    """Configuration for different embedding models"""
    model_name: str
    model_type: EmbeddingModelType
    dimension: int
    max_length: int
    batch_size: int


# Model configurations for different content types
MODEL_CONFIGS = {
    EmbeddingModelType.CODE_BERT: EmbeddingConfig(
        model_name="microsoft/codebert-base",
        model_type=EmbeddingModelType.CODE_BERT,
        dimension=768,
        max_length=512,
        batch_size=16
    ),
    EmbeddingModelType.SENTENCE_TRANSFORMER: EmbeddingConfig(
        model_name="all-MiniLM-L6-v2",
        model_type=EmbeddingModelType.SENTENCE_TRANSFORMER,
        dimension=384,
        max_length=512,
        batch_size=32
    )
}

# Mapping chunk types to embedding models
CHUNK_TYPE_TO_MODEL = {
    'Code': EmbeddingModelType.CODE_BERT,
    'Exercise': EmbeddingModelType.CODE_BERT,
    'Try_It': EmbeddingModelType.CODE_BERT,
    'Example': EmbeddingModelType.CODE_BERT,  # Examples often contain code
    'Concept': EmbeddingModelType.SENTENCE_TRANSFORMER,
}
