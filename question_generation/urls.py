from django.urls import path
from .views import DocumentChunkClassificationView

urlpatterns = [
    path('classify-document-chunks/', DocumentChunkClassificationView.as_view(), name='classify_document_chunks'),
]
