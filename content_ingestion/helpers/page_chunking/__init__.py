"""
Page chunking utilities for content ingestion.

This module provides modular tools for processing PDF content into chunks optimized for different question types:
- Conceptual content for non-coding questions  
- Coding content for programming-related questions

Main modules:
- chunk_extractor_utils: Core chunk extraction and processing
- chunk_classifier: Content type classification (Concept, Code, Exercise, Try_It, Example)
- text_cleaner: Text cleaning and URL removal utilities  
- context_creator: Context creation for different chunk types
"""

from .chunk_extractor_utils import (
    extract_unstructured_chunks,
    get_chunk_statistics
)
from .chunk_classifier import infer_chunk_type
from .text_cleaner import clean_raw_text, clean_chunk_text, clean_urls_from_line
from .cross_page_merger import enhance_cross_page_chunking, detect_split_content

# Note: ChunkOptimizer is available directly via chunk_optimizer.py but requires Django

__all__ = [
    'extract_unstructured_chunks',
    'get_chunk_statistics',
    'infer_chunk_type',
    'clean_raw_text',
    'clean_chunk_text', 
    'clean_urls_from_line',
    'enhance_cross_page_chunking',
    'detect_split_content'
]
