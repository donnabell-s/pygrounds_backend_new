"""
Content ingestion views package - Final consolidated version.
All views organized by functionality for better maintainability.
"""

# ==================== ADMIN VIEWS ====================
# Administrative operations and enhanced management features
from .admin_views import (
    # Admin CRUD operations
    ZoneList, ZoneDetail,
    TopicList, TopicDetail,
    SubtopicList, SubtopicDetail,
    DocumentList, DocumentDetail,
    
    # Document CRUD operations
    upload_pdf, list_documents, get_document_detail, delete_document,
    
    # Document testing and validation
    test_pdf_analysis, test_pdf_chunking,
    
    # Relationship views
    ZoneTopicsView, TopicSubtopicsView
)

# ==================== SPECIALIZED VIEWS ====================
# Embedding operations
from .embeddingViews import (
    embed_document_chunks, get_chunk_embeddings,
    get_chunk_embeddings_detailed, get_topic_subtopic_embeddings_detailed,
    generate_subtopic_embeddings
)

# TOC parser views (functional)
from .tocParserView import (
    generate_document_toc, get_section_content, get_document_toc
)

# Chunk processing views (functional)
from .chunkPagesView import (
    process_document_pipeline, chunk_document_pages, generate_document_embeddings,
    get_document_chunks, get_single_chunk, get_document_chunks_full,
    get_chunks_by_type, get_coding_chunks_for_minigames
)

__all__ = [
    # Document management
    'upload_pdf', 'list_documents', 'get_document_detail', 'delete_document',
    'test_pdf_analysis', 'test_pdf_chunking',
    
    # Embedding operations
    'embed_document_chunks', 'get_chunk_embeddings', 'get_chunk_embeddings_detailed',
    'get_topic_subtopic_embeddings_detailed', 'generate_subtopic_embeddings',
    
    # Relationship views
    'ZoneTopicsView', 'TopicSubtopicsView',
    
    # Admin CRUD operations (concise names)
    'ZoneList', 'ZoneDetail', 'TopicList', 'TopicDetail',
    'SubtopicList', 'SubtopicDetail', 'DocumentList', 'DocumentDetail',
    
    # TOC parser views (functional)
    'generate_document_toc', 'get_section_content', 'get_document_toc',
    
    # Chunk processing views (functional)
    'process_document_pipeline', 'chunk_document_pages', 'generate_document_embeddings',
    'get_document_chunks', 'get_single_chunk', 'get_document_chunks_full',
    'get_chunks_by_type', 'get_coding_chunks_for_minigames'
]
