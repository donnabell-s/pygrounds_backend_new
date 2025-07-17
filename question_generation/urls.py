from django.urls import path
from .views import DocumentChunkClassificationView

urlpatterns = [
    path('classify-document-chunks/', DocumentChunkClassificationView.as_view(), name='classify_document_chunks'),
    path('document-chunks/', DocumentChunkListView.as_view(), name='document_chunks_list'),
]

