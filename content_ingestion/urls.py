from django.urls import path
from . import views

app_name = 'content_ingestion'

urlpatterns = [
    # PDF Upload endpoint
    path('upload/', views.PDFUploadView.as_view(), name='upload_pdf'),
    
    # TOC Generation endpoints
    # Generate table of contents from PDF metadata or text analysis
    path('toc/generate/', views.TOCGenerationView.as_view(), name='generate_toc_upload'),  # For direct PDF upload
    path('toc/generate/<int:document_id>/', views.TOCGenerationView.as_view(), name='generate_toc'),  # For existing document
    
    # Document Processing
    # Process entire document with granular chunking for optimal RAG performance
    path('process/granular/<int:document_id>/', views.GranularDocumentProcessingView.as_view(), name='granular_process_document'),
    
    # Chunk Retrieval endpoints
    # Get all chunks for a document with basic metadata
    path('chunks/<int:document_id>/', views.get_document_chunks, name='get_document_chunks'),
    # Get single chunk by ID with full details
    path('chunks/single/<int:chunk_id>/', views.get_single_chunk, name='get_single_chunk'),
    # Get chunks filtered by type (Code, Exercise, Example, Text, Concept, etc.)
    path('chunks/<int:document_id>/type/<str:chunk_type>/', views.get_chunks_by_type, name='get_chunks_by_type'),
    # Get all chunks with optimized content for LLM consumption
    path('chunks/full/<int:document_id>/', views.get_document_chunks_full, name='get_document_chunks_full'),
    
    # Chunk Management endpoints
    # Generate embeddings for all chunks in a document
    path('chunks/<int:document_id>/embed/', views.embed_document_chunks, name='embed_document_chunks'),
    # Get embedding status and metadata for all chunks
    path('chunks/<int:document_id>/embeddings/', views.get_chunk_embeddings, name='get_chunk_embeddings'),
    
    # TOC Content endpoints
    # Get table of contents structure for a document
    path('toc/document/<int:document_id>/', 
         views.get_document_toc, 
         name='get_document_toc'),
    # Get content of a specific TOC section
    path('toc/section/<int:entry_id>/', 
         views.get_section_content, 
         name='get_section_content'),
         
    # Game Zone Management endpoints
    # CRUD operations for learning zones (Python Basics, Advanced Concepts, etc.)
    path('zones/', views.GameZoneListCreateView.as_view(), name='zone-list'),
    path('zones/<int:pk>/', views.GameZoneDetailView.as_view(), name='zone-detail'),
    
    # Topic Management endpoints  
    # CRUD operations for topics within zones (Introduction to Python, Control Flow, etc.)
    path('topics/', views.TopicListCreateView.as_view(), name='topic-list'),
    path('topics/<int:pk>/', views.TopicDetailView.as_view(), name='topic-detail'),
    # Get all topics for a specific zone
    path('zones/<int:zone_id>/topics/', views.ZoneTopicsView.as_view(), name='zone-topics'),
    
    # Subtopic Management endpoints
    # CRUD operations for subtopics within topics (Using input(), String Formatting, etc.)
    path('subtopics/', views.SubtopicListCreateView.as_view(), name='subtopic-list'),
    path('subtopics/<int:pk>/', views.SubtopicDetailView.as_view(), name='subtopic-detail'),
    # Get all subtopics for a specific topic
    path('topics/<int:topic_id>/subtopics/', views.TopicSubtopicsView.as_view(), name='topic-subtopics'),
    
    # Content Mapping endpoints
    # Map TOC entries to game zones/topics/subtopics for structured learning paths
    path('mappings/', views.ContentMappingListCreateView.as_view(), name='mapping-list'),
    path('mappings/<int:pk>/', views.ContentMappingDetailView.as_view(), name='mapping-detail'),
    # Create mapping for a specific TOC entry
    path('toc/<int:toc_id>/map/', views.MapTOCEntryView.as_view(), name='map-toc-entry'),
]
