# document management and admin views
from .admin_views import (
    upload_pdf, list_documents, get_document_detail, get_document_status, delete_document,
    ZoneList, ZoneDetail, TopicList, TopicDetail, 
    SubtopicList, SubtopicDetail, DocumentList, DocumentDetail,
    ZoneTopicsView, TopicSubtopicsView
)

# toc parsing views
from .tocParserView import (
    generate_document_toc, get_section_content, get_document_toc
)

# document chunking and pipeline views
from .chunkPagesView import (
    process_document_pipeline, cancel_document_pipeline, chunk_document_pages, generate_document_embeddings,
    get_document_chunks, get_single_chunk, get_document_chunks_full,
    get_chunks_by_type, get_coding_chunks_for_minigames
)

# embedding views
from .embeddingViews import (
    embed_document_chunks, get_chunk_embeddings, get_chunk_embeddings_detailed,
    generate_subtopic_embeddings, get_topic_subtopic_embeddings_detailed
)

# semantic similarity views
from .semantic_views import (
    process_semantic_similarities, process_all_semantic_similarities,
    get_subtopic_similar_chunks, get_semantic_overview
)

__all__ = [
    # admin and document management
    'upload_pdf', 'list_documents', 'get_document_detail', 'get_document_status', 'delete_document',
    'ZoneList', 'ZoneDetail', 'TopicList', 'TopicDetail',
    'SubtopicList', 'SubtopicDetail', 'DocumentList', 'DocumentDetail',
    'ZoneTopicsView', 'TopicSubtopicsView',
    # toc parsing
    'generate_document_toc', 'get_section_content', 'get_document_toc',
    # chunking and pipeline
    'process_document_pipeline', 'chunk_document_pages', 'generate_document_embeddings',
    'get_document_chunks', 'get_single_chunk', 'get_document_chunks_full',
    'get_chunks_by_type', 'get_coding_chunks_for_minigames',
    # embeddings
    'embed_document_chunks', 'get_chunk_embeddings', 'get_chunk_embeddings_detailed',
    'generate_subtopic_embeddings', 'get_topic_subtopic_embeddings_detailed',
    # semantic similarity
    'process_semantic_similarities', 'process_all_semantic_similarities',
    'get_subtopic_similar_chunks', 'get_semantic_overview'
]