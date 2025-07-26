"""
PDF upload and document management API.
"""

from .imports import *
from django.db.models import Count
import PyPDF2
import io

class PDFUploadView(APIView):
    """
    POST: Upload PDF and create UploadedDocument.
    GET: List documents (with filters).
    """

    def post(self, request):
        """Upload a PDF and create UploadedDocument."""
        try:
            file = request.FILES.get('file')
            if not file:
                return Response({'status': 'error', 'message': 'No file provided.'},
                                status=status.HTTP_400_BAD_REQUEST)

            if not file.name.lower().endswith('.pdf'):
                return Response({'status': 'error', 'message': 'Only PDF files allowed.'},
                                status=status.HTTP_400_BAD_REQUEST)

            max_size_mb = 10
            if file.size > max_size_mb * 1024 * 1024:
                return Response({'status': 'error', 'message': f'Max size: {max_size_mb} MB.'},
                                status=status.HTTP_400_BAD_REQUEST)

            title = request.data.get('title') or file.name.replace('.pdf', '').replace('_', ' ').title()
            file_content = file.read()
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
                total_pages = len(pdf_reader.pages)
                file.seek(0)
                if total_pages == 0:
                    return Response({'status': 'error', 'message': 'PDF contains no pages.'},
                                    status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({'status': 'error', 'message': f'PDF read error: {str(e)}'},
                                status=status.HTTP_400_BAD_REQUEST)

            if UploadedDocument.objects.filter(title=title).exists():
                existing_doc = UploadedDocument.objects.get(title=title)
                return Response({
                    'status': 'error',
                    'message': f'Document "{title}" exists.',
                    'existing_document': {
                        'id': existing_doc.id,
                        'title': existing_doc.title,
                        'uploaded_at': existing_doc.uploaded_at.isoformat()
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

            doc = UploadedDocument.objects.create(
                title=title,
                file=file,
                total_pages=total_pages,
                processing_status='PENDING'
            )

            return Response({
                'status': 'success',
                'message': 'PDF uploaded.',
                'document': {
                    'id': doc.id,
                    'title': doc.title,
                    'filename': file.name,
                    'total_pages': total_pages,
                    'file_size_bytes': file.size,
                    'processing_status': doc.processing_status,
                    'uploaded_at': doc.uploaded_at.isoformat(),
                    'file_url': doc.file.url if doc.file else None
                },
                'next_steps': {
                    'toc_generation': f'/api/content_ingestion/toc/generate/{doc.id}/',
                    'granular_processing': f'/api/content_ingestion/process/granular/{doc.id}/',
                    'chunk_retrieval': f'/api/content_ingestion/chunks/{doc.id}/'
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"PDF upload failed: {str(e)}")
            return Response({'status': 'error', 'message': f'Upload failed: {str(e)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        """
        List uploaded documents.
        Query: status, limit, search.
        """
        try:
            status_filter = request.query_params.get('status')
            limit = int(request.query_params.get('limit', 20))
            search = request.query_params.get('search')

            query = UploadedDocument.objects.all()
            if status_filter:
                query = query.filter(processing_status=status_filter)
            if search:
                query = query.filter(title__icontains=search)

            docs = query.order_by('-uploaded_at')[:limit]
            docs_data = []
            for doc in docs:
                chunk_count = DocumentChunk.objects.filter(document=doc).count()
                docs_data.append({
                    'id': doc.id,
                    'title': doc.title,
                    'filename': doc.file.name.split('/')[-1] if doc.file else None,
                    'total_pages': doc.total_pages,
                    'processing_status': doc.processing_status,
                    'parsed': doc.parsed,
                    'chunks_created': chunk_count,
                    'uploaded_at': doc.uploaded_at.isoformat(),
                    'file_url': doc.file.url if doc.file else None,
                    'file_size_mb': round(doc.file.size / (1024 * 1024), 2) if doc.file else 0
                })

            status_counts = {
                st.lower(): query.filter(processing_status=st).count()
                for st in ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']
            }

            return Response({
                'status': 'success',
                'summary': {
                    'total_documents': query.count(),
                    'showing_count': len(docs),
                    'status_distribution': status_counts
                },
                'filters_applied': {
                    'status': status_filter,
                    'search': search,
                    'limit': limit
                },
                'documents': docs_data
            })

        except Exception as e:
            logger.error(f"Failed to list documents: {str(e)}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DocumentDetailView(APIView):
    """
    GET: Document detail.
    DELETE: Remove document and related data.
    """

    def get(self, request, document_id):
        """Get info for one document."""
        try:
            doc = get_object_or_404(UploadedDocument, id=document_id)
            chunk_count = DocumentChunk.objects.filter(document=doc).count()
            toc_count = TOCEntry.objects.filter(document=doc).count()
            chunk_types = DocumentChunk.objects.filter(document=doc).values('chunk_type').annotate(
                count=Count('chunk_type')).order_by('chunk_type')
            chunk_dist = {c['chunk_type']: c['count'] for c in chunk_types}

            return Response({
                'status': 'success',
                'document': {
                    'id': doc.id,
                    'title': doc.title,
                    'filename': doc.file.name.split('/')[-1] if doc.file else None,
                    'total_pages': doc.total_pages,
                    'processing_status': doc.processing_status,
                    'parsed': doc.parsed,
                    'uploaded_at': doc.uploaded_at.isoformat(),
                    'file_url': doc.file.url if doc.file else None,
                    'file_size_mb': round(doc.file.size / (1024 * 1024), 2) if doc.file else 0
                },
                'processing_info': {
                    'chunks_created': chunk_count,
                    'toc_entries_created': toc_count,
                    'chunk_type_distribution': chunk_dist,
                },
                'available_actions': {
                    'generate_toc': f'/api/content_ingestion/toc/generate/{doc.id}/',
                    'process_granular': f'/api/content_ingestion/process/granular/{doc.id}/',
                    'get_chunks': f'/api/content_ingestion/chunks/{doc.id}/',
                    'embed_chunks': f'/api/content_ingestion/chunks/{doc.id}/embed/'
                }
            })
        except Exception as e:
            logger.error(f"Failed to get document details for {document_id}: {str(e)}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, document_id):
        """Delete document and all its data."""
        try:
            doc = get_object_or_404(UploadedDocument, id=document_id)
            chunk_count = DocumentChunk.objects.filter(document=doc).count()
            toc_count = TOCEntry.objects.filter(document=doc).count()

            if doc.file:
                try:
                    doc.file.delete(save=False)
                except Exception as e:
                    logger.warning(f"Could not delete file from storage: {e}")

            doc.delete()

            return Response({
                'status': 'success',
                'message': f'Document "{doc.title}" deleted.',
                'deleted_data': {
                    'document_id': document_id,
                    'chunks_deleted': chunk_count,
                    'toc_entries_deleted': toc_count
                }
            })
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {str(e)}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
