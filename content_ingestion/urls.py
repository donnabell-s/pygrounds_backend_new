from django.urls import path
from .views import (
    # Document management (unified)
    upload_pdf, list_documents, get_document_detail, delete_document, test_pdf_analysis, test_pdf_chunking,
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

app_name = 'content_ingestion'

urlpatterns = [
    # ========== DOCUMENTS ==========
    path('upload/', upload_pdf, name='upload'),
    path('test-analysis/', test_pdf_analysis, name='test-analysis'),
    path('test-chunking/', test_pdf_chunking, name='test-chunking'),
    path('documents/', list_documents, name='documents'),
    path('documents/<int:document_id>/', get_document_detail, name='document-detail'),
    path('documents/<int:document_id>/delete/', delete_document, name='document-delete'),

    # ========== PIPELINE (FUNCTIONAL) ==========
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

    # ========== RESOURCES ==========
    path('zones/', ZoneList.as_view(), name='zones'),
    path('zones/<int:pk>/', ZoneDetail.as_view(), name='zone-detail'),
    path('topics/', TopicList.as_view(), name='topics'),
    path('topics/<int:pk>/', TopicDetail.as_view(), name='topic-detail'),
    path('zones/<int:zone_id>/topics/', ZoneTopicsView, name='zone-topics'),
    path('subtopics/', SubtopicList.as_view(), name='subtopics'),
    path('subtopics/<int:pk>/', SubtopicDetail.as_view(), name='subtopic-detail'),
    path('topics/<int:topic_id>/subtopics/', TopicSubtopicsView, name='topic-subtopics'),

    # ========== ADMIN RESOURCES ==========
    path('admin/zones/', ZoneList.as_view(), name='admin-zones'),
    path('admin/zones/<int:pk>/', ZoneDetail.as_view(), name='admin-zone-detail'),
    path('admin/topics/', TopicList.as_view(), name='admin-topics'),
    path('admin/topics/<int:pk>/', TopicDetail.as_view(), name='admin-topic-detail'),
    path('admin/subtopics/', SubtopicList.as_view(), name='admin-subtopics'),
    path('admin/subtopics/<int:pk>/', SubtopicDetail.as_view(), name='admin-subtopic-detail'),
]
