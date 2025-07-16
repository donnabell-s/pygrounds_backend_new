from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.shortcuts import get_object_or_404
from content_ingestion.models import GameZone, Topic, Subtopic, ContentMapping, TOCEntry, UploadedDocument
from .serializers import (
    GameZoneSerializer, TopicSerializer, SubtopicSerializer,
    ContentMappingSerializer, TOCEntryMappingSerializer
)
from .helpers.toc_parser.toc_apply import generate_toc_entries_for_document
import os
import logging

logger = logging.getLogger(__name__)

class PDFUploadView(APIView):
    def post(self, request):
        uploaded_file = request.FILES.get('file') # KEY NAME in postman

        if not uploaded_file or not uploaded_file.name.lower().endswith('.pdf'):
            return Response({'error': 'A PDF file is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Strip ".pdf" from file name if no title was given
        filename = uploaded_file.name
        default_title = os.path.splitext(filename)[0]  # removes .pdf
        title = request.POST.get('title', default_title)

        doc = UploadedDocument.objects.create(title=title, file=uploaded_file)
        return Response({
            'id': doc.id,
            'title': doc.title,
            'file_url': doc.file.url,
            'uploaded_at': doc.uploaded_at
        }, status=status.HTTP_201_CREATED)

class TOCGenerationView(APIView):
    """
    Handles TOC generation for uploaded PDFs.
    """
    def post(self, request, document_id=None):
        """
        Generate TOC for a PDF. Can either:
        1. Send document_id of already uploaded PDF
        2. Send a new PDF file directly
        
        Query parameters:
        - skip_nlp: Set to 'true' to skip NLP matching for faster processing
        """
        try:
            # Check if we should skip NLP processing
            skip_nlp = request.query_params.get('skip_nlp', 'false').lower() == 'true'
            if skip_nlp:
                print("[DEBUG] Skipping NLP processing for faster execution")
            
            # Case 1: Process existing document
            if document_id:
                document = get_object_or_404(UploadedDocument, id=document_id)
                logger.info(f"Processing existing document: {document.title}")
            
            # Case 2: Process new PDF upload
            else:
                uploaded_file = request.FILES.get('file')
                if not uploaded_file or not uploaded_file.name.lower().endswith('.pdf'):
                    return Response({
                        'error': 'A PDF file is required.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Create new document
                filename = uploaded_file.name
                default_title = os.path.splitext(filename)[0]
                title = request.POST.get('title', default_title)
                document = UploadedDocument.objects.create(
                    title=title, 
                    file=uploaded_file,
                    processing_status='PROCESSING'
                )
                logger.info(f"Processing new upload: {title}")
            
            # Extract and save TOC
            print(f"\n[TOC Extraction] Starting for document: {document.title}")
            entries = generate_toc_entries_for_document(document, skip_nlp=skip_nlp)
            print(f"\n[TOC Extraction] Found {len(entries)} entries:")
            
            response_data = []
            for entry in entries:
                entry_data = {
                    'id': entry.id,
                    'title': entry.title,
                    'level': entry.level,
                    'start_page': entry.start_page,
                    'end_page': entry.end_page,
                    'order': entry.order
                }
                response_data.append(entry_data)
                print(f"\n[TOC Entry] {'-' * entry.level}> {entry.title}")
                print(f"    Pages: {entry.start_page + 1}-{entry.end_page + 1 if entry.end_page else '?'}")
                print(f"    Level: {entry.level}")
                
            # Update document status
            document.processing_status = 'COMPLETED'
            document.save()
            
            print(f"\n[TOC Extraction] Complete! Total entries: {len(entries)}\n")
                
            return Response({
                'status': 'success',
                'document_title': document.title,
                'total_pages': document.total_pages,
                'entries': response_data
            })
            
        except Exception as e:
            error_msg = str(e)
            print(f"\n[TOC Extraction Error] {error_msg}\n")
            return Response({
                'status': 'error',
                'message': error_msg
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_section_content(request, entry_id):
    """
    Get the content of a specific TOC section.
    """
    try:
        entry = get_object_or_404(TOCEntry, id=entry_id)
        content = entry.get_content()
        
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
    Get the full TOC structure for a document.
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        entries = TOCEntry.objects.filter(document=document).order_by('order')
        
        response_data = []
        for entry in entries:
            response_data.append({
                'id': entry.id,
                'title': entry.title,
                'level': entry.level,
                'start_page': entry.start_page,
                'end_page': entry.end_page,
                'order': entry.order,
                'parent_id': entry.parent_id
            })
            
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

class GameZoneListCreateView(generics.ListCreateAPIView):
    """
    List all game zones or create a new zone
    """
    queryset = GameZone.objects.all()
    serializer_class = GameZoneSerializer

class GameZoneDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a game zone
    """
    queryset = GameZone.objects.all()
    serializer_class = GameZoneSerializer

class TopicListCreateView(generics.ListCreateAPIView):
    """
    List all topics or create a new topic
    """
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer

class TopicDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a topic
    """
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer

class ZoneTopicsView(generics.ListAPIView):
    """
    List all topics for a specific zone
    """
    serializer_class = TopicSerializer

    def get_queryset(self):
        zone_id = self.kwargs['zone_id']
        return Topic.objects.filter(zone_id=zone_id)

class SubtopicListCreateView(generics.ListCreateAPIView):
    """
    List all subtopics or create a new subtopic
    """
    queryset = Subtopic.objects.all()
    serializer_class = SubtopicSerializer

class SubtopicDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a subtopic
    """
    queryset = Subtopic.objects.all()
    serializer_class = SubtopicSerializer

class TopicSubtopicsView(generics.ListAPIView):
    """
    List all subtopics for a specific topic
    """
    serializer_class = SubtopicSerializer

    def get_queryset(self):
        topic_id = self.kwargs['topic_id']
        return Subtopic.objects.filter(topic_id=topic_id)

class ContentMappingListCreateView(generics.ListCreateAPIView):
    """
    List all content mappings or create a new mapping
    """
    queryset = ContentMapping.objects.all()
    serializer_class = ContentMappingSerializer

class ContentMappingDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a content mapping
    """
    queryset = ContentMapping.objects.all()
    serializer_class = ContentMappingSerializer

class MapTOCEntryView(APIView):
    """
    Map a TOC entry to game content (zone, topic, subtopic)
    """
    def post(self, request, toc_id):
        toc_entry = get_object_or_404(TOCEntry, id=toc_id)
        
        # Get mapping data from request
        zone_id = request.data.get('zone_id')
        topic_id = request.data.get('topic_id')
        subtopic_id = request.data.get('subtopic_id')
        
        try:
            # Create or update mapping
            mapping, created = ContentMapping.objects.update_or_create(
                toc_entry=toc_entry,
                defaults={
                    'zone_id': zone_id,
                    'topic_id': topic_id,
                    'subtopic_id': subtopic_id,
                    'confidence_score': request.data.get('confidence_score', 0.0),
                    'mapping_metadata': request.data.get('metadata', {})
                }
            )
            
            return Response({
                'status': 'success',
                'message': 'TOC entry mapped successfully',
                'mapping_id': mapping.id
            })
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
