"""
PDF Table of Contents (TOC) extraction API views.
"""

from .imports import *
from content_ingestion.helpers.utils.stubs import log_toc_generation
import json
from pathlib import Path
from django.utils import timezone

# You might already have a config like this
LOGS_DIR = Path(__file__).resolve().parent.parent / "json_exports"
LOGS_DIR.mkdir(exist_ok=True)

def log_toc_generation(document_id, toc_data, meta):
    log_file = LOGS_DIR / "toc_generation_log.json"
    logs = []
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = []
    # Compose log entry
    log_entry = {
        "timestamp": timezone.now().isoformat(),
        "document_id": document_id,
        "toc_entries": toc_data,
        "metadata": meta,
    }
    logs.append(log_entry)
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)
    return {
        "status": "logged",
        "entry_count": len(logs),
        "last_entry": log_entry,
        "log_file": str(log_file)
    }

class TOCGenerationView(APIView):
    """
    API endpoint for extracting and saving TOC entries from an uploaded PDF.
    """
    def post(self, request, document_id=None):
        """
        Generate TOC for a PDF from UploadedDocument.
        Query parameters:
        - skip_nlp: 'true' to skip NLP matching (for faster processing)
        """
        try:
            skip_nlp = request.query_params.get('skip_nlp', 'false').lower() == 'true'
            if not document_id:
                return Response({'error': 'document_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
            document = get_object_or_404(UploadedDocument, id=document_id)
            logger.info(f"Processing document: {document.title}")

            print("=" * 80)
            print(f"TOC GENERATION API - Document: {document.title}")
            print("=" * 80)

            # Extract and save TOC entries
            generate_toc_entries_for_document(document, skip_nlp=skip_nlp)
            all_entries = TOCEntry.objects.filter(document=document).order_by('order')

            response_data = list(
                all_entries.values('id', 'title', 'level', 'start_page', 'end_page', 'order')
            )

            print(f"API Response: {len(response_data)} TOC entries returned for chunking\n")

            # Mark as completed
            document.processing_status = 'COMPLETED'
            document.save(update_fields=['processing_status'])

            # Log metadata
            log_metadata = {
                'document_title': document.title,
                'total_pages': document.total_pages,
                'skip_nlp': skip_nlp,
                'processing_summary': {
                    'total_entries_parsed': all_entries.count(),
                    'entries_for_chunking': len(response_data)
                }
            }
            log_result = log_toc_generation(document_id, response_data, log_metadata)

            return Response({
                'status': 'success',
                'document_title': document.title,
                'total_pages': document.total_pages,
                'processing_summary': log_metadata['processing_summary'],
                'toc_entries': response_data,
                'json_log': log_result
            })

        except Exception as e:
            logger.error(f"[TOC Extraction Error] {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_section_content(request, entry_id):
    """
    Get the content text for a specific TOC section (if implemented).
    """
    try:
        entry = get_object_or_404(TOCEntry, id=entry_id)
        content = entry.get_content()  # You must have this implemented on your model

        return Response({
            'status': 'success',
            'entry': {
                'id': entry.id,
                'title': entry.title,
                'content': content,
                'start_page': entry.start_page,
                'end_page': entry.end_page
            }
        })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_document_toc(request, document_id):
    """
    Get the flat TOC entry list for a given document.
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        entries = TOCEntry.objects.filter(document=document).order_by('order')

        response_data = [
            {
                'id': entry.id,
                'title': entry.title,
                'level': entry.level,
                'start_page': entry.start_page,
                'end_page': entry.end_page,
                'order': entry.order,
                'parent_id': entry.parent_id
            }
            for entry in entries
        ]

        return Response({
            'status': 'success',
            'document_title': document.title,
            'total_pages': document.total_pages,
            'entries': response_data
        })

    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
