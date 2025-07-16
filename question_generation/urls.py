from django.urls import path
from . import views

app_name = 'question_generation'

urlpatterns = [
    # PDF Upload endpoint
    path('upload/', views.PDFUploadView.as_view(), name='upload_pdf'),
    
    # TOC Generation endpoints
    path('toc/generate/', views.TOCGenerationView.as_view(), name='generate_toc_upload'),  # For direct PDF upload
    path('toc/generate/<int:document_id>/', views.TOCGenerationView.as_view(), name='generate_toc'),  # For existing document
    
    # TOC Content endpoints
    path('toc/document/<int:document_id>/', 
         views.get_document_toc, 
         name='get_document_toc'),
    path('toc/section/<int:entry_id>/', 
         views.get_section_content, 
         name='get_section_content'),
]
