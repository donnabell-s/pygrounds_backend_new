"""
Consolidated admin views for content ingestion.
Contains all CRUD operations, admin functions, and document management.
"""

from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Count, Q
from django.core.files.storage import default_storage
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    GameZone, Topic, Subtopic, UploadedDocument, 
    DocumentChunk, TOCEntry
)
from ..serializers import (
    GameZoneSerializer, TopicSerializer, SubtopicSerializer,
    DocumentSerializer, DocumentChunkSerializer
)

import logging
import os
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# ==================== ADMIN CRUD VIEWS ====================

class AdminGameZoneListView(generics.ListCreateAPIView):
    """Administrative view for GameZone with enhanced functionality"""
    queryset = GameZone.objects.all()
    serializer_class = GameZoneSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        # Add statistics annotations
        return queryset.annotate(
            topic_count=Count('topics'),
            subtopic_count=Count('topics__subtopics')
        )

class AdminGameZoneDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Administrative GameZone detail view"""
    queryset = GameZone.objects.all()
    serializer_class = GameZoneSerializer

class AdminTopicListView(generics.ListCreateAPIView):
    """Administrative Topic view with filtering"""
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        zone_id = self.request.query_params.get('zone_id')
        if zone_id:
            queryset = queryset.filter(zone_id=zone_id)
        return queryset.annotate(subtopic_count=Count('subtopics'))

class AdminTopicDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Administrative Topic detail view"""
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer

class AdminSubtopicListView(generics.ListCreateAPIView):
    """Administrative Subtopic view with filtering"""
    queryset = Subtopic.objects.all()
    serializer_class = SubtopicSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        topic_id = self.request.query_params.get('topic_id')
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)
        return queryset

class AdminSubtopicDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Administrative Subtopic detail view"""
    queryset = Subtopic.objects.all()
    serializer_class = SubtopicSerializer

class AdminDocumentListView(generics.ListCreateAPIView):
    """Administrative Document view with enhanced features"""
    queryset = UploadedDocument.objects.all()
    serializer_class = DocumentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        # Add chunk statistics
        return queryset.annotate(
            chunk_count=Count('chunks')
        )

class AdminDocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Administrative Document detail view"""
    queryset = UploadedDocument.objects.all()
    serializer_class = DocumentSerializer

# ==================== STANDARD CRUD VIEWS ====================

class GameZoneListCreateView(generics.ListCreateAPIView):
    """Public GameZone CRUD operations"""
    queryset = GameZone.objects.all()
    serializer_class = GameZoneSerializer

class GameZoneDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Public GameZone detail operations"""
    queryset = GameZone.objects.all()
    serializer_class = GameZoneSerializer

class TopicListCreateView(generics.ListCreateAPIView):
    """Public Topic CRUD operations"""
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer

class TopicDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Public Topic detail operations"""
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer

class SubtopicListCreateView(generics.ListCreateAPIView):
    """Public Subtopic CRUD operations"""
    queryset = Subtopic.objects.all()
    serializer_class = SubtopicSerializer

class SubtopicDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Public Subtopic detail operations"""
    queryset = Subtopic.objects.all()
    serializer_class = SubtopicSerializer

# ==================== RELATIONSHIP VIEWS ====================

@api_view(['GET'])
def ZoneTopicsView(request, zone_id):
    """Get all topics for a specific zone"""
    try:
        zone = get_object_or_404(GameZone, id=zone_id)
        topics = zone.topics.all()
        serializer = TopicSerializer(topics, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['GET'])
def TopicSubtopicsView(request, topic_id):
    """Get all subtopics for a specific topic"""
    try:
        topic = get_object_or_404(Topic, id=topic_id)
        subtopics = topic.subtopics.all()
        serializer = SubtopicSerializer(subtopics, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

# ==================== DOCUMENT OPERATIONS ====================

@api_view(['POST'])
def upload_pdf(request):
    """Upload and process a PDF document"""
    try:
        serializer = DocumentSerializer(data=request.data)
        if serializer.is_valid():
            document = serializer.save()
            logger.info(f"Document uploaded: {document.title}")
            return Response(
                DocumentSerializer(document).data,
                status=status.HTTP_201_CREATED
            )
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error uploading PDF: {str(e)}")
        return Response(
            {'error': 'Failed to upload PDF'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def list_documents(request):
    """List all uploaded documents"""
    try:
        documents = UploadedDocument.objects.all().annotate(
            chunk_count=Count('chunks')
        )
        serializer = DocumentSerializer(documents, many=True)
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        return Response(
            {'error': 'Failed to retrieve documents'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def get_document_detail(request, document_id):
    """Get detailed information about a document"""
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        chunks = DocumentChunk.objects.filter(document=document)
        
        document_data = DocumentSerializer(document).data
        document_data['chunks'] = DocumentChunkSerializer(chunks, many=True).data
        
        return Response(document_data)
    except Exception as e:
        logger.error(f"Error getting document detail: {str(e)}")
        return Response(
            {'error': 'Failed to retrieve document'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['DELETE'])
def delete_document(request, document_id):
    """Delete a document and its associated data"""
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        # Delete associated chunks
        DocumentChunk.objects.filter(document=document).delete()
        
        # Delete the file if it exists
        if document.file and default_storage.exists(document.file.name):
            default_storage.delete(document.file.name)
        
        # Delete the document
        document.delete()
        
        logger.info(f"Document deleted: {document_id}")
        return Response(
            {'message': 'Document deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        return Response(
            {'error': 'Failed to delete document'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['DELETE'])
def delete_document_with_chunks(request, document_id):
    """Admin function to delete document with all related data"""
    try:
        with transaction.atomic():
            document = get_object_or_404(UploadedDocument, id=document_id)
            
            # Delete all related data
            DocumentChunk.objects.filter(document=document).delete()
            TOCEntry.objects.filter(document=document).delete()
            
            # Delete file
            if document.file and default_storage.exists(document.file.name):
                default_storage.delete(document.file.name)
            
            document.delete()
            
        return Response(
            {'message': 'Document and all related data deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )
    except Exception as e:
        logger.error(f"Error in delete_document_with_chunks: {str(e)}")
        return Response(
            {'error': 'Failed to delete document with chunks'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def reprocess_document(request, document_id):
    """Admin function to reprocess a document"""
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        # Reset processing status
        document.processing_status = 'PENDING'
        document.parsed = False
        document.parsed_pages = []
        document.save()
        
        logger.info(f"Document {document_id} marked for reprocessing")
        return Response(
            {'message': 'Document marked for reprocessing'},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        logger.error(f"Error reprocessing document: {str(e)}")
        return Response(
            {'error': 'Failed to reprocess document'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def test_pdf_analysis(request):
    """Test PDF analysis functionality"""
    try:
        return Response({
            'message': 'PDF analysis test endpoint',
            'status': 'available'
        })
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def test_pdf_chunking(request):
    """Test PDF chunking functionality"""
    try:
        return Response({
            'message': 'PDF chunking test endpoint',
            'status': 'available'
        })
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ==================== STATISTICS ====================

@api_view(['GET'])
def zone_statistics(request):
    """Get comprehensive zone statistics"""
    try:
        zones = GameZone.objects.annotate(
            topic_count=Count('topics'),
            subtopic_count=Count('topics__subtopics')
        )
        
        stats = []
        for zone in zones:
            stats.append({
                'id': zone.id,
                'name': zone.name,
                'topic_count': zone.topic_count,
                'subtopic_count': zone.subtopic_count
            })
        
        return Response({
            'zones': stats,
            'total_zones': zones.count()
        })
    except Exception as e:
        logger.error(f"Error getting zone statistics: {str(e)}")
        return Response(
            {'error': 'Failed to retrieve zone statistics'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def topic_statistics(request):
    """Get comprehensive topic statistics"""
    try:
        topics = Topic.objects.annotate(
            subtopic_count=Count('subtopics')
        )
        
        stats = []
        for topic in topics:
            stats.append({
                'id': topic.id,
                'name': topic.name,
                'zone': topic.zone.name if topic.zone else 'No Zone',
                'subtopic_count': topic.subtopic_count
            })
        
        return Response({
            'topics': stats,
            'total_topics': topics.count()
        })
    except Exception as e:
        logger.error(f"Error getting topic statistics: {str(e)}")
        return Response(
            {'error': 'Failed to retrieve topic statistics'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def subtopic_statistics(request):
    """Get comprehensive subtopic statistics"""
    try:
        subtopics = Subtopic.objects.select_related('topic', 'topic__zone')
        
        stats = []
        for subtopic in subtopics:
            stats.append({
                'id': subtopic.id,
                'name': subtopic.name,
                'topic': subtopic.topic.name if subtopic.topic else 'No Topic',
                'zone': subtopic.topic.zone.name if subtopic.topic and subtopic.topic.zone else 'No Zone'
            })
        
        return Response({
            'subtopics': stats,
            'total_subtopics': subtopics.count()
        })
    except Exception as e:
        logger.error(f"Error getting subtopic statistics: {str(e)}")
        return Response(
            {'error': 'Failed to retrieve subtopic statistics'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ==================== BULK OPERATIONS ====================

@api_view(['POST'])
def bulk_create_subtopics(request):
    """Create multiple subtopics at once"""
    try:
        subtopics_data = request.data.get('subtopics', [])
        if not subtopics_data:
            return Response(
                {'error': 'No subtopics data provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created_subtopics = []
        with transaction.atomic():
            for subtopic_data in subtopics_data:
                serializer = SubtopicSerializer(data=subtopic_data)
                if serializer.is_valid():
                    subtopic = serializer.save()
                    created_subtopics.append(subtopic)
                else:
                    return Response(
                        {'error': f'Invalid subtopic data: {serializer.errors}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        response_data = SubtopicSerializer(created_subtopics, many=True).data
        return Response(
            {
                'message': f'Successfully created {len(created_subtopics)} subtopics',
                'subtopics': response_data
            },
            status=status.HTTP_201_CREATED
        )
    except Exception as e:
        logger.error(f"Error in bulk_create_subtopics: {str(e)}")
        return Response(
            {'error': 'Failed to create subtopics'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def bulk_unlock_zones(request):
    """Unlock multiple zones at once"""
    try:
        zone_ids = request.data.get('zone_ids', [])
        if not zone_ids:
            return Response(
                {'error': 'No zone IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        updated_zones = GameZone.objects.filter(id__in=zone_ids).update(
            unlocked=True
        )
        
        return Response(
            {
                'message': f'Successfully unlocked {updated_zones} zones',
                'unlocked_count': updated_zones
            },
            status=status.HTTP_200_OK
        )
    except Exception as e:
        logger.error(f"Error in bulk_unlock_zones: {str(e)}")
        return Response(
            {'error': 'Failed to unlock zones'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ==================== ADMIN OVERVIEW ====================

@api_view(['GET'])
def pdf_management_overview(request):
    """Get comprehensive PDF management overview"""
    try:
        documents = UploadedDocument.objects.all()
        
        # Calculate statistics
        total_documents = documents.count()
        processed_documents = documents.filter(parsed=True).count()
        pending_documents = documents.filter(processing_status='PENDING').count()
        
        # Get processing status breakdown
        status_breakdown = {}
        for status_choice in ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']:
            count = documents.filter(processing_status=status_choice).count()
            status_breakdown[status_choice.lower()] = count
        
        # Get recent documents
        recent_documents = documents.order_by('-id')[:10]
        recent_docs_data = DocumentSerializer(recent_documents, many=True).data
        
        return Response({
            'overview': {
                'total_documents': total_documents,
                'processed_documents': processed_documents,
                'pending_documents': pending_documents,
                'processing_rate': (processed_documents / total_documents * 100) if total_documents > 0 else 0
            },
            'status_breakdown': status_breakdown,
            'recent_documents': recent_docs_data
        })
    except Exception as e:
        logger.error(f"Error in pdf_management_overview: {str(e)}")
        return Response(
            {'error': 'Failed to retrieve PDF management overview'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
