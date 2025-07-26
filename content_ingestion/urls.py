from django.urls import path
from .views import (
    # Upload
    PDFUploadView, DocumentDetailView,
    # Main pipeline (all-in-one)
    CompleteDocumentPipelineView, ChunkAllPagesView,
    # Core steps
    TOCGenerationView, get_section_content, get_document_toc,
    embed_document_chunks, get_chunk_embeddings,
    generate_topic_embeddings, generate_subtopic_embeddings,
    # Chunks
    get_document_chunks, get_single_chunk, get_chunks_by_type, get_coding_chunks_for_minigames,
    get_chunk_embeddings_detailed, get_topic_subtopic_embeddings_detailed,
    # Zone/topic/subtopic CRUD
    GameZoneListCreateView, GameZoneDetailView, TopicListCreateView, TopicDetailView,
    ZoneTopicsView, SubtopicListCreateView, SubtopicDetailView, TopicSubtopicsView,
    # JSON Export/logging
    get_export_summary, download_export_file, view_export_file, create_system_snapshot,
    get_recent_logs, clear_export_logs, get_log_statistics
)

app_name = 'content_ingestion'

urlpatterns = [
    # ========== UPLOAD & DOCUMENT MANAGEMENT ==========
    path('upload/', PDFUploadView.as_view(), name='upload_pdf'),
    path('documents/', PDFUploadView.as_view(), name='list_documents'),  # GET only
    path('documents/<int:document_id>/', DocumentDetailView.as_view(), name='document_detail'),

    # ========== PIPELINE OPERATIONS ==========
    path('process/complete/<int:document_id>/', CompleteDocumentPipelineView.as_view(), name='complete_document_pipeline'),
    path('process/chunk-all-pages/<int:document_id>/', ChunkAllPagesView.as_view(), name='chunk_all_pages'),

    # ========== TOC OPERATIONS ==========
    path('toc/generate/', TOCGenerationView.as_view(), name='generate_toc_upload'),  # For direct upload
    path('toc/generate/<int:document_id>/', TOCGenerationView.as_view(), name='generate_toc'),
    path('toc/document/<int:document_id>/', get_document_toc, name='get_document_toc'),
    path('toc/section/<int:entry_id>/', get_section_content, name='get_section_content'),

    # ========== CHUNK OPERATIONS ==========
    path('chunks/<int:document_id>/', get_document_chunks, name='get_document_chunks'),
    path('chunks/single/<int:chunk_id>/', get_single_chunk, name='get_single_chunk'),
    path('chunks/<int:document_id>/type/<str:chunk_type>/', get_chunks_by_type, name='get_chunks_by_type'),
    path('chunks/<int:document_id>/for-coding/', get_coding_chunks_for_minigames, name='get_coding_chunks_for_minigames'),

    # ========== EMBEDDING ==========
    path('chunks/<int:document_id>/embed/', embed_document_chunks, name='embed_document_chunks'),
    path('chunks/<int:document_id>/embeddings/', get_chunk_embeddings, name='get_chunk_embeddings'),
    path('chunks/<int:document_id>/embeddings/detailed/', get_chunk_embeddings_detailed, name='get_chunk_embeddings_detailed'),
    path('topics/embed/', generate_topic_embeddings, name='generate_topic_embeddings'),
    path('subtopics/embed/', generate_subtopic_embeddings, name='generate_subtopic_embeddings'),
    path('topics-subtopics/embeddings/detailed/', get_topic_subtopic_embeddings_detailed, name='get_topic_subtopic_embeddings_detailed'),

    # ========== ZONE, TOPIC, SUBTOPIC CRUD ==========
    path('zones/', GameZoneListCreateView.as_view(), name='zone-list'),
    path('zones/<int:pk>/', GameZoneDetailView.as_view(), name='zone-detail'),
    path('topics/', TopicListCreateView.as_view(), name='topic-list'),
    path('topics/<int:pk>/', TopicDetailView.as_view(), name='topic-detail'),
    path('zones/<int:zone_id>/topics/', ZoneTopicsView.as_view(), name='zone-topics'),
    path('subtopics/', SubtopicListCreateView.as_view(), name='subtopic-list'),
    path('subtopics/<int:pk>/', SubtopicDetailView.as_view(), name='subtopic-detail'),
    path('topics/<int:topic_id>/subtopics/', TopicSubtopicsView.as_view(), name='topic-subtopics'),

    # ========== JSON EXPORT & LOGGING ==========
    path('exports/summary/', get_export_summary, name='export-summary'),
    path('exports/download/<str:filename>/', download_export_file, name='download-export'),
    path('exports/view/<str:filename>/', view_export_file, name='view-export'),
    path('exports/snapshot/', create_system_snapshot, name='create-snapshot'),
    path('logs/<str:log_type>/recent/', get_recent_logs, name='recent-logs'),
    path('logs/<str:log_type>/recent/<int:count>/', get_recent_logs, name='recent-logs-count'),
    path('logs/statistics/', get_log_statistics, name='log-statistics'),
    path('logs/clear/', clear_export_logs, name='clear-logs'),
]
