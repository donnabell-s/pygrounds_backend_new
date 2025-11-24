from dataclasses import dataclass
from enum import Enum
from typing import Dict
import os


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


# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MODELS_DIR = os.path.join(PROJECT_ROOT, 'models')

# Check if local models exist, otherwise use online models
def get_model_path(model_name: str, local_folder: str) -> str:
    local_path = os.path.join(MODELS_DIR, local_folder)
    if os.path.exists(local_path):
        print(f"🔗 Using local model: {local_path}")
        return local_path
    else:
        print(f"🌐 Using online model: {model_name}")
        return model_name

# Model configurations for different content types
MODEL_CONFIGS = {
    EmbeddingModelType.CODE_BERT: EmbeddingConfig(
        model_name=get_model_path("microsoft/codebert-base", "codebert-base"),
        model_type=EmbeddingModelType.CODE_BERT,
        dimension=768,
        max_length=512,
        batch_size=16
    ),
    EmbeddingModelType.SENTENCE_TRANSFORMER: EmbeddingConfig(
        model_name=get_model_path("sentence-transformers/all-MiniLM-L6-v2", "all-MiniLM-L6-v2"),
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
