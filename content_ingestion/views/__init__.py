# Document management and admin views
from .admin_views import (
    upload_pdf, list_documents, get_document_detail, delete_document,
    delete_document_with_chunks, reprocess_document,
    test_pdf_analysis, test_pdf_chunking,
    ZoneList, ZoneDetail, TopicList, TopicDetail, 
    SubtopicList, SubtopicDetail, DocumentList, DocumentDetail,
    ZoneTopicsView, TopicSubtopicsView
)

# TOC parsing views
from .tocParserView import (
    generate_document_toc, get_section_content, get_document_toc
)

# Document chunking and pipeline views
from .chunkPagesView import (
    process_document_pipeline, chunk_document_pages, generate_document_embeddings,
    get_document_chunks, get_single_chunk, get_document_chunks_full,
    get_chunks_by_type, get_coding_chunks_for_minigames,
    upload_and_process_pipeline
)

# Embedding views
from .embeddingViews import (
    embed_document_chunks, get_chunk_embeddings, get_chunk_embeddings_detailed,
    generate_subtopic_embeddings, get_topic_subtopic_embeddings_detailed
)

# Semantic similarity views
from .semantic_views import (
    process_semantic_similarities, process_all_semantic_similarities,
    get_subtopic_similar_chunks, get_semantic_overview
)

__all__ = [
    # Admin and document management
    'upload_pdf', 'list_documents', 'get_document_detail', 'delete_document',
    'delete_document_with_chunks', 'reprocess_document', 
    'test_pdf_analysis', 'test_pdf_chunking',
    'ZoneList', 'ZoneDetail', 'TopicList', 'TopicDetail',
    'SubtopicList', 'SubtopicDetail', 'DocumentList', 'DocumentDetail',
    'ZoneTopicsView', 'TopicSubtopicsView',
    # TOC parsing
    'generate_document_toc', 'get_section_content', 'get_document_toc',
    # Chunking and pipeline
    'process_document_pipeline', 'chunk_document_pages', 'generate_document_embeddings',
    'get_document_chunks', 'get_single_chunk', 'get_document_chunks_full',
    'get_chunks_by_type', 'get_coding_chunks_for_minigames',
    'upload_and_process_pipeline',
    # Embeddings
    'embed_document_chunks', 'get_chunk_embeddings', 'get_chunk_embeddings_detailed',
    'generate_subtopic_embeddings', 'get_topic_subtopic_embeddings_detailed',
    # Semantic similarity
    'process_semantic_similarities', 'process_all_semantic_similarities',
    'get_subtopic_similar_chunks', 'get_semantic_overview'
]