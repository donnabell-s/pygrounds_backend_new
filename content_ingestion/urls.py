from django.urls import path
from .views import (
    # Document management
    upload_pdf, list_documents, get_document_detail, delete_document,
    # Functional processing steps  
    process_document_pipeline, chunk_document_pages, generate_document_embeddings,
    # Core steps
    generate_document_toc, get_section_content, get_document_toc,
    get_chunk_embeddings,
    generate_subtopic_embeddings,
    # Chunks
    get_document_chunks, get_single_chunk, get_document_chunks_full, get_chunks_by_type, get_coding_chunks_for_minigames,
    get_chunk_embeddings_detailed, get_topic_subtopic_embeddings_detailed,
    # Zone/topic/subtopic CRUD
    ZoneTopicsView, TopicSubtopicsView,
    # Admin views
    ZoneList, ZoneDetail, TopicList, TopicDetail,
    SubtopicList, SubtopicDetail
)
# Semantic similarity views
from .views.semantic_views import (
    process_semantic_similarities, process_all_semantic_similarities,
    get_subtopic_similar_chunks, get_semantic_overview
)

urlpatterns = [
    # ========== DOCUMENTS ==========
    # Document management endpoints
    path('docs/', list_documents, name='docs-list'),
    path('docs/upload/', upload_pdf, name='docs-upload'),
    path('docs/<int:document_id>/', get_document_detail, name='docs-detail'),
    path('docs/<int:document_id>/delete/', delete_document, name='docs-delete'),

    # ========== PIPELINE (FUNCTIONAL) ==========
    # Pipeline processing endpoints
    path('pipeline/<int:document_id>/', process_document_pipeline, name='process-document'),
    path('pipeline/<int:document_id>/chunks/', chunk_document_pages, name='chunk-document'),
    path('pipeline/<int:document_id>/embeddings/', generate_document_embeddings, name='embed-document'),

    # ========== TOC ==========
    path('toc/<int:document_id>/generate/', generate_document_toc, name='toc-generate'),
    path('toc/<int:document_id>/', get_document_toc, name='toc-view'),
    path('toc/sections/<int:entry_id>/', get_section_content, name='toc-section'),

    # ========== CHUNKS ==========
    path('chunks/<int:document_id>/', get_document_chunks, name='chunks'),
    path('chunks/<int:document_id>/full/', get_document_chunks_full, name='chunks-full'),
    path('chunks/<int:chunk_id>/detail/', get_single_chunk, name='chunk-detail'),
    path('chunks/<int:document_id>/<str:chunk_type>/', get_chunks_by_type, name='chunks-by-type'),
    path('chunks/<int:document_id>/coding/', get_coding_chunks_for_minigames, name='chunks-coding'),

    # ========== EMBEDDINGS ==========
    path('embeddings/<int:document_id>/', get_chunk_embeddings, name='embeddings'),
    path('embeddings/<int:document_id>/detailed/', get_chunk_embeddings_detailed, name='embeddings-detailed'),
    path('embeddings/subtopics/', generate_subtopic_embeddings, name='embeddings-subtopics'),
    path('embeddings/topics/detailed/', get_topic_subtopic_embeddings_detailed, name='embeddings-topics'),

    # ========== SEMANTIC SIMILARITY ==========
    path('semantic/<int:document_id>/', process_semantic_similarities, name='semantic-process'),
    path('semantic/all/', process_all_semantic_similarities, name='semantic-process-all'),
    path('semantic/subtopic/<int:subtopic_id>/chunks/', get_subtopic_similar_chunks, name='semantic-chunks'),
    path('semantic/overview/', get_semantic_overview, name='semantic-overview'),

    # ========== RESOURCE MANAGEMENT ==========
    # Zones
    path('zones/', ZoneList.as_view(), name='zones'),
    path('zones/<int:pk>/', ZoneDetail.as_view(), name='zone-detail'),
    path('zones/<int:zone_id>/topics/', ZoneTopicsView, name='zone-topics'),
    
    # Topics
    path('topics/', TopicList.as_view(), name='topics'),
    path('topics/<int:pk>/', TopicDetail.as_view(), name='topic-detail'),
    path('topics/<int:topic_id>/subtopics/', TopicSubtopicsView, name='topic-subtopics'),
    
    # Subtopics
    path('subtopics/', SubtopicList.as_view(), name='subtopics'),
    path('subtopics/<int:pk>/', SubtopicDetail.as_view(), name='subtopic-detail'),
]
