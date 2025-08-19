"""
CRUD operations for admin frontend.
Handles document, zones, topics, and subtopics management.
"""

from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Count
from django.http import FileResponse

from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import (
    UploadedDocument, DocumentChunk, TOCEntry, GameZone,
    Topic, Subtopic
)
from ..serializers import (
    GameZoneSerializer, TopicSerializer, SubtopicSerializer,
    DocumentSerializer, DocumentChunkSerializer
)

import logging
logger = logging.getLogger(__name__)

# ==================== ADMIN CRUD VIEWS ====================

class ZoneList(generics.ListCreateAPIView):
    queryset = GameZone.objects.all()
    serializer_class = GameZoneSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.annotate(
            topic_count=Count('topics'),
            subtopic_count=Count('topics__subtopics')
        )
    
    def create(self, request, *args, **kwargs):
        try:
            # Check required fields
            required_fields = ['name', 'description', 'order']
            missing_fields = [field for field in required_fields if not request.data.get(field)]
            if missing_fields:
                return Response(
                    {'error': f'Missing required fields: {", ".join(missing_fields)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check for duplicate zone name
            name = request.data.get('name')
            if GameZone.objects.filter(name=name).exists():
                return Response(
                    {'error': f'A zone named "{name}" already exists. Zone names must be unique.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if order is already taken
            order = request.data.get('order')
            if GameZone.objects.filter(order=order).exists():
                return Response(
                    {'error': f'A zone with order number {order} already exists. Order numbers must be unique.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return super().create(request, *args, **kwargs)

        except Exception as e:
            logger.error(f"Error creating zone: {str(e)}")
            return Response(
                {'error': 'Failed to create zone. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            # Check required fields
            required_fields = ['name', 'description', 'order']
            missing_fields = [field for field in required_fields if not request.data.get(field)]
            if missing_fields:
                return Response(
                    {'error': f'Missing required fields: {", ".join(missing_fields)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return super().create(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error creating zone: {str(e)}")
            return Response(
                {'error': 'Failed to create zone. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ZoneDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = GameZone.objects.all()
    serializer_class = GameZoneSerializer

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()

            # Check for duplicate zone name if name is being changed
            name = request.data.get('name')
            if name and name != instance.name:
                if GameZone.objects.filter(name=name).exists():
                    return Response(
                        {'error': f'A zone named "{name}" already exists. Zone names must be unique.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Check for duplicate order if order is being changed
            order = request.data.get('order')
            if order and order != instance.order:
                if GameZone.objects.filter(order=order).exists():
                    return Response(
                        {'error': f'A zone with order number {order} already exists. Order numbers must be unique.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Check if anything is being changed
            changed_fields = []
            for field in ['name', 'description', 'order']:
                new_value = request.data.get(field)
                if new_value and new_value != getattr(instance, field):
                    changed_fields.append(field)
            
            if not changed_fields:
                return Response(
                    {'message': 'No changes were made to the zone'},
                    status=status.HTTP_200_OK
                )
            
            response = super().update(request, *args, **kwargs)
            response.data['message'] = f'Zone updated successfully. Changed fields: {", ".join(changed_fields)}'
            return response
            
        except Exception as e:
            logger.error(f"Error updating zone: {str(e)}")
            return Response(
                {'error': 'Failed to update zone. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            
            # Check if zone has any topics
            if instance.topics.exists():
                return Response(
                    {'error': 'Cannot delete zone that contains topics. Delete all topics in this zone first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            instance.delete()
            return Response(
                {'message': f'Zone "{instance.name}" was successfully deleted'},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error deleting zone: {str(e)}")
            return Response(
                {'error': 'Failed to delete zone. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    


class TopicList(generics.ListCreateAPIView):
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        zone_id = self.request.query_params.get('zone_id')
        if zone_id:
            queryset = queryset.filter(zone_id=zone_id)
        return queryset.annotate(subtopic_count=Count('subtopics'))
    
    def create(self, request, *args, **kwargs):
        try:
            # Check required fields
            required_fields = ['name', 'description', 'zone']
            missing_fields = [field for field in required_fields if not request.data.get(field)]
            if missing_fields:
                return Response(
                    {'error': f'Missing required fields: {", ".join(missing_fields)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify zone exists
            zone_id = request.data.get('zone')
            try:
                GameZone.objects.get(pk=zone_id)
            except GameZone.DoesNotExist:
                return Response(
                    {'error': f'Zone with id {zone_id} does not exist'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check for duplicate topic name in zone
            zone_id = request.data.get('zone')
            name = request.data.get('name')
            if Topic.objects.filter(zone_id=zone_id, name=name).exists():
                return Response(
                    {'error': f'A topic named "{name}" already exists in this zone'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return super().create(request, *args, **kwargs)
            
        except Exception as e:
            logger.error(f"Error creating topic: {str(e)}")
            return Response(
                {'error': 'Failed to create topic. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TopicDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            
            # Verify zone exists if zone is being updated
            zone_id = request.data.get('zone')
            if zone_id:
                try:
                    GameZone.objects.get(pk=zone_id)
                except GameZone.DoesNotExist:
                    return Response(
                        {'error': f'Zone with id {zone_id} does not exist'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Check for duplicate topic name in zone if name is being updated
            name = request.data.get('name')
            if name and name != instance.name:
                zone_id = zone_id or instance.zone.id
                if Topic.objects.filter(zone_id=zone_id, name=name).exists():
                    return Response(
                        {'error': f'A topic named "{name}" already exists in this zone'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            return super().update(request, *args, **kwargs)

        except Exception as e:
            logger.error(f"Error updating topic: {str(e)}")
            return Response(
                {'error': 'Failed to update topic. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            
            # Check if topic has any subtopics
            if instance.subtopics.exists():
                return Response(
                    {'error': 'Cannot delete topic with existing subtopics. Delete subtopics first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return super().destroy(request, *args, **kwargs)

        except Exception as e:
            logger.error(f"Error deleting topic: {str(e)}")
            return Response(
                {'error': 'Failed to delete topic. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    


class SubtopicList(generics.ListCreateAPIView):
    queryset = Subtopic.objects.all()
    serializer_class = SubtopicSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        topic_id = self.request.query_params.get('topic_id')
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)
        return queryset

    def create(self, request, *args, **kwargs):
        try:
            # Check required fields
            required_fields = ['name', 'topic']
            missing_fields = [field for field in required_fields if not request.data.get(field)]
            if missing_fields:
                return Response(
                    {'error': f'Missing required fields: {", ".join(missing_fields)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify topic exists
            topic_id = request.data.get('topic')
            try:
                Topic.objects.get(pk=topic_id)
            except Topic.DoesNotExist:
                return Response(
                    {'error': f'Topic with id {topic_id} does not exist'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check for duplicate subtopic name in topic
            topic_id = request.data.get('topic')
            name = request.data.get('name')
            if Subtopic.objects.filter(topic_id=topic_id, name=name).exists():
                return Response(
                    {'error': f'A subtopic named "{name}" already exists in this topic'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return super().create(request, *args, **kwargs)
            
        except Exception as e:
            logger.error(f"Error creating subtopic: {str(e)}")
            return Response(
                {'error': 'Failed to create subtopic. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
   
class SubtopicDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Subtopic.objects.all()
    serializer_class = SubtopicSerializer

    def perform_destroy(self, instance):
        try:
            # Delete related embeddings first
            from content_ingestion.models import Embedding
            Embedding.objects.filter(subtopic=instance).delete()
            
            # Then delete the subtopic
            instance.delete()
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error deleting subtopic {instance.id}: {e}")
            raise

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            
            # Verify topic exists if topic is being updated
            topic_id = request.data.get('topic')
            if topic_id:
                try:
                    Topic.objects.get(pk=topic_id)
                except Topic.DoesNotExist:
                    return Response(
                        {'error': f'Topic with id {topic_id} does not exist'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Check for duplicate subtopic name in topic if name is being updated
            name = request.data.get('name')
            if name and name != instance.name:
                topic_id = topic_id or instance.topic.id
                if Subtopic.objects.filter(topic_id=topic_id, name=name).exists():
                    return Response(
                        {'error': f'A subtopic named "{name}" already exists in this topic'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            return super().update(request, *args, **kwargs)

        except Exception as e:
            logger.error(f"Error updating subtopic: {str(e)}")
            return Response(
                {'error': 'Failed to update subtopic. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            
            # Check if subtopic has any document chunks
            if instance.document_chunks.exists():
                return Response(
                    {
                        'status': 'error',
                        'message': 'Cannot delete subtopic that contains document chunks. Delete chunks first.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Proceed with deletion
            instance.delete()
            
            return Response(
                {
                    'status': 'success',
                    'message': f'Subtopic "{instance.name}" deleted successfully'
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error deleting subtopic: {str(e)}")
            return Response(
                {
                    'status': 'error',
                    'message': f'Failed to delete subtopic: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    


class DocumentList(generics.ListCreateAPIView):
    queryset = UploadedDocument.objects.all()
    serializer_class = DocumentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.annotate(
            chunk_count=Count('chunks')
        )

class DocumentDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = UploadedDocument.objects.all()
    serializer_class = DocumentSerializer

# ==================== GETTER BY OBJECT ====================

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
    """
    Upload a PDF document - only saves the document, processing is handled separately.
    Document starts with PENDING status.
    """
    try:
        serializer = DocumentSerializer(data=request.data)
        if serializer.is_valid():
            document = serializer.save()
            # Set initial status - processing will be handled by separate endpoint
            document.processing_status = 'PENDING'
            document.processing_message = 'Document uploaded successfully. Ready for processing.'
            document.save()
            
            response_data = DocumentSerializer(document).data
            
            logger.info(f"Document uploaded with PENDING status: {document.title} (ID: {document.id})")
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        return Response(
            {'error': f'Failed to upload document: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def list_documents(request):
    """List all non-deleted uploaded documents"""
    try:
        documents = UploadedDocument.objects.filter(is_deleted=False).order_by('-uploaded_at').annotate(
            chunk_count=Count('chunks')
        )
        serializer = DocumentSerializer(documents, many=True)
        
        # Structure the response for frontend
        return Response({
            'status': 'success',
            'message': 'Documents retrieved successfully',
            'count': len(documents),
            'documents': serializer.data,
            'statuses': {
                'pending': documents.filter(processing_status='PENDING').count(),
                'processing': documents.filter(processing_status='PROCESSING').count(),
                'completed': documents.filter(processing_status='COMPLETED').count(),
                'failed': documents.filter(processing_status='FAILED').count(),
            }
        })
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        return Response({
            'status': 'error',
            'message': 'Failed to retrieve documents',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

@api_view(['GET'])
def download_document(request, document_id):
    """Download a document's PDF file"""
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        if not document.pdf_file:
            return Response(
                {'error': 'No PDF file associated with this document'},
                status=status.HTTP_404_NOT_FOUND
            )
            
        try:
            response = FileResponse(
                document.pdf_file.open('rb'),
                content_type='application/pdf'
            )
            response['Content-Disposition'] = f'attachment; filename="{document.title}.pdf"'
            return response
        except Exception as e:
            logger.error(f"Error opening PDF file: {str(e)}")
            return Response(
                {'error': 'Failed to open PDF file'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        logger.error(f"Error downloading document: {str(e)}")
        return Response(
            {'error': 'Failed to download document'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST', 'DELETE'])
def delete_document(request, document_id):
    """
    Delete a document with comprehensive cleanup of all related data.
    Supports both soft delete (POST) and hard delete (DELETE).
    Query parameter 'hard_delete=true' forces hard deletion.
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        # Check if hard delete is requested
        hard_delete = (
            request.method == 'DELETE' or 
            request.query_params.get('hard_delete', '').lower() == 'true' or
            request.data.get('hard_delete', False)
        )
        
        # Always hard delete failed documents for cleanup
        if document.processing_status == 'FAILED':
            hard_delete = True
            logger.info(f"Forcing hard delete for failed document: {document.title}")
        
        if hard_delete:
            # Hard delete - permanently remove document and all related data
            document_title = document.title
            document_status = document.processing_status
            
            # Count related objects before deletion for logging
            chunk_count = document.chunks.count() if hasattr(document, 'chunks') else 0
            toc_count = document.tocentry_set.count() if hasattr(document, 'tocentry_set') else 0
            
            try:
                # Count embeddings
                from content_ingestion.models import Embedding
                embedding_count = Embedding.objects.filter(
                    document_chunk__document=document,
                    content_type='chunk'
                ).count()
            except Exception:
                embedding_count = 0
            
            logger.info(f"Hard deleting document: {document_title}")
            logger.info(f"  Status: {document_status}")
            logger.info(f"  Related data: {chunk_count} chunks, {toc_count} TOC entries, {embedding_count} embeddings")
            
            # Use our custom delete method which handles all cleanup
            document.delete()
            
            logger.info(f"Document hard deleted successfully: {document_title}")
            return Response({
                'status': 'success',
                'message': f'Document "{document_title}" permanently deleted',
                'deletion_type': 'hard',
                'cleaned_up': {
                    'chunks': chunk_count,
                    'toc_entries': toc_count,
                    'embeddings': embedding_count
                }
            }, status=status.HTTP_200_OK)
        else:
            # Soft delete - mark as deleted but keep data
            document.is_deleted = True
            document.save()
            
            logger.info(f"Document soft deleted: {document.title}")
            return Response({
                'status': 'success',
                'message': f'Document "{document.title}" marked as deleted',
                'deletion_type': 'soft',
                'note': 'Use hard_delete=true to permanently remove'
            }, status=status.HTTP_200_OK)
            
    except UploadedDocument.DoesNotExist:
        return Response(
            {'error': 'Document not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {str(e)}")
        return Response(
            {
                'error': 'Failed to delete document', 
                'detail': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def cleanup_failed_documents(request):
    """
    Bulk cleanup of all failed documents and their related data.
    This is useful for cleaning up documents that failed during processing.
    """
    try:
        # Find all failed documents
        failed_documents = UploadedDocument.objects.filter(
            processing_status='FAILED'
        )
        
        if failed_documents.count() == 0:
            return Response({
                'status': 'success',
                'message': 'No failed documents found to clean up',
                'deleted_count': 0
            }, status=status.HTTP_200_OK)
        
        # Count related data before deletion
        total_chunks = 0
        total_toc_entries = 0
        total_embeddings = 0
        
        document_titles = []
        
        for doc in failed_documents:
            document_titles.append(doc.title)
            total_chunks += doc.chunks.count() if hasattr(doc, 'chunks') else 0
            total_toc_entries += doc.tocentry_set.count() if hasattr(doc, 'tocentry_set') else 0
            
            try:
                from content_ingestion.models import Embedding
                total_embeddings += Embedding.objects.filter(
                    document_chunk__document=doc,
                    content_type='chunk'
                ).count()
            except Exception:
                pass
        
        failed_count = failed_documents.count()
        
        logger.info(f"Starting bulk cleanup of {failed_count} failed documents")
        logger.info(f"Related data to clean: {total_chunks} chunks, {total_toc_entries} TOC entries, {total_embeddings} embeddings")
        
        # Delete all failed documents (this will trigger our custom delete method)
        deleted_titles = list(document_titles)  # Copy before deletion
        failed_documents.delete()
        
        logger.info(f"Bulk cleanup completed: {failed_count} failed documents deleted")
        
        return Response({
            'status': 'success',
            'message': f'Successfully cleaned up {failed_count} failed documents',
            'deleted_count': failed_count,
            'deleted_documents': deleted_titles,
            'cleaned_up': {
                'chunks': total_chunks,
                'toc_entries': total_toc_entries,
                'embeddings': total_embeddings
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error during bulk cleanup of failed documents: {str(e)}")
        return Response(
            {
                'error': 'Failed to cleanup failed documents',
                'detail': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
