"""
Content ingestion views package - Final consolidated version.
All views organized by functionality for better maintainability.
"""

# ==================== ADMIN VIEWS ====================
# Administrative operations and enhanced management features
from .admin_views import (
    # Admin CRUD operations
    AdminGameZoneListView, AdminGameZoneDetailView,
    AdminTopicListView, AdminTopicDetailView,
    AdminSubtopicListView, AdminSubtopicDetailView,
    AdminDocumentListView, AdminDocumentDetailView,
    
    # Admin statistics and analytics
    zone_statistics, topic_statistics, subtopic_statistics,
    
    # Bulk operations
    bulk_create_subtopics, bulk_unlock_zones,
    
    # Advanced document management
    pdf_management_overview, delete_document_with_chunks, reprocess_document,
    
    # Document CRUD operations
    upload_pdf, list_documents, get_document_detail, delete_document,
    
    # Document testing and validation
    test_pdf_analysis, test_pdf_chunking,
    
    # Public CRUD operations for zones, topics, subtopics
    GameZoneListCreateView, GameZoneDetailView, ZoneTopicsView,
    TopicListCreateView, TopicDetailView, TopicSubtopicsView,
    SubtopicListCreateView, SubtopicDetailView
)

# ==================== SPECIALIZED VIEWS ====================
# Embedding operations
from .embeddingViews import (
    embed_document_chunks, get_chunk_embeddings,
    get_chunk_embeddings_detailed, get_topic_subtopic_embeddings_detailed,
    generate_subtopic_embeddings
)

# TOC parser views
from .tocParserView import (
    TOCGenerationView, get_section_content, get_document_toc
)

# Chunk processing views
from .chunkPagesView import (
    UploadAndProcessPipelineView, CompleteDocumentPipelineView,
    CompleteSemanticPipelineView, ChunkAllPagesView,
    get_document_chunks, get_single_chunk, get_chunks_by_type,
    get_coding_chunks_for_minigames
)

__all__ = [
    # Document management
    'upload_pdf', 'list_documents', 'get_document_detail', 'delete_document',
    'test_pdf_analysis', 'test_pdf_chunking',
    
    # Embedding operations
    'embed_document_chunks', 'get_chunk_embeddings', 'get_chunk_embeddings_detailed',
    'get_topic_subtopic_embeddings_detailed', 'generate_subtopic_embeddings',
    
    # Standard CRUD operations
    'GameZoneListCreateView', 'GameZoneDetailView', 'TopicListCreateView',
    'TopicDetailView', 'ZoneTopicsView', 'SubtopicListCreateView',
    'SubtopicDetailView', 'TopicSubtopicsView',
    
    # Admin operations
    'AdminGameZoneListView', 'AdminGameZoneDetailView', 'AdminTopicListView',
    'AdminTopicDetailView', 'AdminSubtopicListView', 'AdminSubtopicDetailView',
    'AdminDocumentListView', 'AdminDocumentDetailView',
    'zone_statistics', 'topic_statistics', 'subtopic_statistics',
    'bulk_create_subtopics', 'bulk_unlock_zones', 'pdf_management_overview',
    'delete_document_with_chunks', 'reprocess_document',
    
    # TOC parser views
    'TOCGenerationView', 'get_section_content', 'get_document_toc',
    
    # Chunk processing views
    'UploadAndProcessPipelineView', 'CompleteDocumentPipelineView',
    'CompleteSemanticPipelineView', 'ChunkAllPagesView', 'get_document_chunks',
    'get_single_chunk', 'get_chunks_by_type', 'get_coding_chunks_for_minigames'
]
