from django.urls import path
from .views import (
    # Upload
    PDFUploadView, DocumentDetailView, PDFTestAnalysisView, PDFTestChunkingView,
    # Main pipeline (all-in-one)
    UploadAndProcessPipelineView, CompleteDocumentPipelineView, CompleteSemanticPipelineView, ChunkAllPagesView,
    # Core steps
    TOCGenerationView, get_section_content, get_document_toc,
    get_chunk_embeddings,
    generate_subtopic_embeddings,
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
    # ========== DOCUMENTS ==========
    path('upload/', PDFUploadView.as_view(), name='upload'),
    path('test-analysis/', PDFTestAnalysisView.as_view(), name='test-analysis'),
    path('test-chunking/', PDFTestChunkingView.as_view(), name='test-chunking'),
    path('documents/', PDFUploadView.as_view(), name='documents'),
    path('documents/<int:document_id>/', DocumentDetailView.as_view(), name='document-detail'),

    # ========== PIPELINE ==========
    path('pipeline/', CompleteSemanticPipelineView.as_view(), name='pipeline-complete-semantic'),
    path('pipeline/upload/', UploadAndProcessPipelineView.as_view(), name='pipeline-upload'),
    path('pipeline/<int:document_id>/', CompleteDocumentPipelineView.as_view(), name='pipeline-document'),
    path('pipeline/<int:document_id>/chunks/', ChunkAllPagesView.as_view(), name='pipeline-chunk'),

    # ========== TOC ==========
    path('toc/', TOCGenerationView.as_view(), name='toc-generate'),
    path('toc/<int:document_id>/', TOCGenerationView.as_view(), name='toc-document'),
    path('toc/<int:document_id>/view/', get_document_toc, name='toc-view'),
    path('toc/sections/<int:entry_id>/', get_section_content, name='toc-section'),

    # ========== CHUNKS ==========
    path('chunks/<int:document_id>/', get_document_chunks, name='chunks'),
    path('chunks/<int:chunk_id>/detail/', get_single_chunk, name='chunk-detail'),
    path('chunks/<int:document_id>/<str:chunk_type>/', get_chunks_by_type, name='chunks-by-type'),
    path('chunks/<int:document_id>/coding/', get_coding_chunks_for_minigames, name='chunks-coding'),

    # ========== EMBEDDINGS ==========
    path('embeddings/<int:document_id>/', get_chunk_embeddings, name='embeddings'),
    path('embeddings/<int:document_id>/detailed/', get_chunk_embeddings_detailed, name='embeddings-detailed'),
    path('embeddings/subtopics/', generate_subtopic_embeddings, name='embeddings-subtopics'),
    path('embeddings/topics/detailed/', get_topic_subtopic_embeddings_detailed, name='embeddings-topics'),

    # ========== RESOURCES ==========
    path('zones/', GameZoneListCreateView.as_view(), name='zones'),
    path('zones/<int:pk>/', GameZoneDetailView.as_view(), name='zone-detail'),
    path('topics/', TopicListCreateView.as_view(), name='topics'),
    path('topics/<int:pk>/', TopicDetailView.as_view(), name='topic-detail'),
    path('zones/<int:zone_id>/topics/', ZoneTopicsView.as_view(), name='zone-topics'),
    path('subtopics/', SubtopicListCreateView.as_view(), name='subtopics'),
    path('subtopics/<int:pk>/', SubtopicDetailView.as_view(), name='subtopic-detail'),
    path('topics/<int:topic_id>/subtopics/', TopicSubtopicsView.as_view(), name='topic-subtopics'),

    # ========== EXPORTS & LOGS ==========
    path('exports/', get_export_summary, name='exports'),
    path('exports/<str:filename>/download/', download_export_file, name='export-download'),
    path('exports/<str:filename>/view/', view_export_file, name='export-view'),
    path('exports/snapshot/', create_system_snapshot, name='export-snapshot'),
    path('logs/<str:log_type>/', get_recent_logs, name='logs'),
    path('logs/<str:log_type>/<int:count>/', get_recent_logs, name='logs-count'),
    path('logs/stats/', get_log_statistics, name='logs-stats'),
    path('logs/clear/', clear_export_logs, name='logs-clear'),
]
