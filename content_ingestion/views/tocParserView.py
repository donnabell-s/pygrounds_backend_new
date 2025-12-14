import json
import logging
from pathlib import Path

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import DocumentChunk, TOCEntry, UploadedDocument
from ..helpers.toc_parser import generate_toc_entries_for_document

logger = logging.getLogger(__name__)

LOGS_DIR = Path(__file__).resolve().parent.parent / "json_exports"
LOGS_DIR.mkdir(exist_ok=True)

@api_view(['POST'])
def generate_document_toc(request, document_id):
    try:
        skip_nlp = request.query_params.get('skip_nlp', 'false').lower() == 'true'
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        toc_result = generate_toc_entries_for_document(document, skip_nlp=skip_nlp)
        
        log_toc_generation(document_id, toc_result, {"skip_nlp": skip_nlp})
        
        return Response({
            'status': 'success',
            'document_id': document_id,
            'entries_created': len(toc_result.get('entries', [])),
            'toc_entries': toc_result.get('entries', [])
        })
    except Exception as e:
        logger.error(f"TOC generation error for document {document_id}: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_section_content(request, entry_id):
    try:
        entry = get_object_or_404(TOCEntry, id=entry_id)
        
        content_data = {
            'id': entry.id,
            'title': entry.title,
            'level': entry.level,
            'start_page': entry.start_page,
            'end_page': entry.end_page,
            'topic_title': entry.topic_title,
            'subtopic_title': entry.subtopic_title,
            'chunked': entry.chunked,
            'chunk_count': entry.chunk_count
        }
        
        if entry.chunked:
            chunks = DocumentChunk.objects.filter(
                document=entry.document,
                page_number__gte=entry.start_page,
                page_number__lte=entry.end_page or entry.start_page
            )
            content_data['chunks'] = [
                {
                    'id': chunk.id,
                    'chunk_type': chunk.chunk_type,
                    'text': chunk.text[:200] + '...' if len(chunk.text) > 200 else chunk.text,
                    'page_number': chunk.page_number
                } for chunk in chunks
            ]
        
        return Response({
            'status': 'success',
            'section': content_data
        })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_document_toc(request, document_id):
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        entries = TOCEntry.objects.filter(document=document).order_by('order')
        
        toc_data = []
        for entry in entries:
            toc_data.append({
                'id': entry.id,
                'title': entry.title,
                'level': entry.level,
                'start_page': entry.start_page,
                'end_page': entry.end_page,
                'order': entry.order,
                'topic_title': entry.topic_title,
                'subtopic_title': entry.subtopic_title,
                'chunked': entry.chunked,
                'chunk_count': entry.chunk_count
            })
        
        return Response({
            'status': 'success',
            'document': {
                'id': document.id,
                'title': document.title
            },
            'total_entries': len(toc_data),
            'toc_entries': toc_data
        })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def log_toc_generation(document_id, toc_data, meta):
    log_file = LOGS_DIR / "toc_generation_log.json"
    logs = []
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = []
    
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
