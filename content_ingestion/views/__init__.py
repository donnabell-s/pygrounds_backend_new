"""
Content ingestion views package.
Modular organization of views by functional responsibility.
"""

# Embedding-related views
from .embeddingView import (
    embed_document_chunks,
    get_chunk_embeddings
)

# TOC parsing and mapping views  
from .tocParserView import (
    TOCGenerationView,
    get_section_content,
    get_document_toc
    # MapTOCEntryView removed
)

# Page chunking and chunk CRUD views
from .chunkPagesView import (
    UploadAndProcessPipelineView,
    CompleteDocumentPipelineView,
    CompleteSemanticPipelineView,
    ChunkAllPagesView,
    get_document_chunks,
    get_single_chunk,
    get_chunks_by_type,
    get_coding_chunks_for_minigames
)

# Zone, topic, and subtopic CRUD views
from .zoneCrudViews import (
    GameZoneListCreateView,
    GameZoneDetailView,
    TopicListCreateView,
    TopicDetailView,
    ZoneTopicsView,
    SubtopicListCreateView,
    SubtopicDetailView,
    TopicSubtopicsView
)

# Upload views
from .uploadViews import (
    PDFUploadView,
    DocumentDetailView,
    PDFTestAnalysisView,
    PDFTestChunkingView
)

# JSON Export views
from .json_export_views import (
    get_export_summary,
    download_export_file,
    view_export_file,
    create_system_snapshot,
    get_recent_logs,
    clear_export_logs,
    get_log_statistics
)

# Topic Embedding views
from .topicEmbeddingView import (
    generate_subtopic_embeddings
)

# Embedding Detail views
from .embeddingDetailView import (
    get_chunk_embeddings_detailed,
    get_topic_subtopic_embeddings_detailed
)

__all__ = [
    # Upload views
    'PDFUploadView',
    'DocumentDetailView',
    'PDFTestAnalysisView',
    'PDFTestChunkingView',
    
    # Embedding views
    'embed_document_chunks',
    'get_chunk_embeddings',
    
    # TOC parser views
    'TOCGenerationView',
    'get_section_content', 
    'get_document_toc',
    # 'MapTOCEntryView',  # <-- REMOVED
    
    # Chunk processing views
    'UploadAndProcessPipelineView',
    'CompleteDocumentPipelineView',
    'CompleteSemanticPipelineView',
    'ChunkAllPagesView',
    'get_document_chunks',
    'get_single_chunk',
    'get_chunks_by_type',
    'get_coding_chunks_for_minigames',
    
    # CRUD views
    'GameZoneListCreateView',
    'GameZoneDetailView',
    'TopicListCreateView',
    'TopicDetailView',
    'ZoneTopicsView',
    'SubtopicListCreateView',
    'SubtopicDetailView',
    'TopicSubtopicsView',
    
    # JSON Export views
    'get_export_summary',
    'download_export_file',
    'view_export_file',
    'create_system_snapshot',
    'get_recent_logs',
    'clear_export_logs',
    'get_log_statistics',
    
    # Topic Embedding views
    'generate_subtopic_embeddings',
    
    # Embedding Detail views
    'get_chunk_embeddings_detailed',
    'get_topic_subtopic_embeddings_detailed'
]
