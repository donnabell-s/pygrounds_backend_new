from django.urls import path
from . import views

app_name = 'content_ingestion'

urlpatterns = [
    # PDF Upload endpoint
    path('upload/', views.PDFUploadView.as_view(), name='upload_pdf'),
    
    # TOC Generation endpoints
    path('toc/generate/', views.TOCGenerationView.as_view(), name='generate_toc_upload'),  # For direct PDF upload
    path('toc/generate/<int:document_id>/', views.TOCGenerationView.as_view(), name='generate_toc'),  # For existing document
    
    # Complete Document Processing with Chunking
    path('process/<int:document_id>/', views.DocumentChunkingView.as_view(), name='process_document'),
    
    # Chunks endpoint
    path('chunks/<int:document_id>/', views.get_document_chunks, name='get_document_chunks'),
    path('chunks/full/<int:document_id>/', views.get_document_chunks_full, name='get_document_chunks_full'),
    path('chunks/<int:document_id>/embed/', views.embed_document_chunks, name='embed_document_chunks'),
    path('chunks/<int:document_id>/embeddings/', views.get_chunk_embeddings, name='get_chunk_embeddings'),
    
    # TOC Content endpoints
    path('toc/document/<int:document_id>/', 
         views.get_document_toc, 
         name='get_document_toc'),
    path('toc/section/<int:entry_id>/', 
         views.get_section_content, 
         name='get_section_content'),
         
    # Game Zone endpoints
    path('zones/', views.GameZoneListCreateView.as_view(), name='zone-list'),
    path('zones/<int:pk>/', views.GameZoneDetailView.as_view(), name='zone-detail'),
    
    # Topic endpoints
    path('topics/', views.TopicListCreateView.as_view(), name='topic-list'),
    path('topics/<int:pk>/', views.TopicDetailView.as_view(), name='topic-detail'),
    path('zones/<int:zone_id>/topics/', views.ZoneTopicsView.as_view(), name='zone-topics'),
    
    # Subtopic endpoints
    path('subtopics/', views.SubtopicListCreateView.as_view(), name='subtopic-list'),
    path('subtopics/<int:pk>/', views.SubtopicDetailView.as_view(), name='subtopic-detail'),
    path('topics/<int:topic_id>/subtopics/', views.TopicSubtopicsView.as_view(), name='topic-subtopics'),
    
    # Content Mapping endpoints
    path('mappings/', views.ContentMappingListCreateView.as_view(), name='mapping-list'),
    path('mappings/<int:pk>/', views.ContentMappingDetailView.as_view(), name='mapping-detail'),
    path('toc/<int:toc_id>/map/', views.MapTOCEntryView.as_view(), name='map-toc-entry'),
]
