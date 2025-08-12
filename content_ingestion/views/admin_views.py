"""
CRUD OPERATIONS FOR ADMIN FRONTEND

document
zones
topic
subtopic

"""

from ..helpers.view_imports import *
from ..helpers.helper_imports import *

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

class ZoneDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = GameZone.objects.all()
    serializer_class = GameZoneSerializer

class TopicList(generics.ListCreateAPIView):
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        zone_id = self.request.query_params.get('zone_id')
        if zone_id:
            queryset = queryset.filter(zone_id=zone_id)
        return queryset.annotate(subtopic_count=Count('subtopics'))

class TopicDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer

class SubtopicList(generics.ListCreateAPIView):
    queryset = Subtopic.objects.all()
    serializer_class = SubtopicSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        topic_id = self.request.query_params.get('topic_id')
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)
        return queryset
   
class SubtopicDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Subtopic.objects.all()
    serializer_class = SubtopicSerializer

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
    try:
        from content_ingestion.helpers.toc_parser import generate_toc_entries_for_document
        from content_ingestion.helpers.page_chunking.toc_chunk_processor import GranularChunkProcessor
        from content_ingestion.helpers.embedding.generator import EmbeddingGenerator
        
        serializer = DocumentSerializer(data=request.data)
        if serializer.is_valid():
            document = serializer.save()
            document.processing_status = 'PROCESSING'
            document.save()
            
            pipeline_results = {
                'document_id': document.id,
                'document_title': document.title,
                'pipeline_steps': {}
            }
            
            try:
                toc_result = generate_toc_entries_for_document(document)
                pipeline_results['pipeline_steps']['toc'] = {
                    'status': 'success',
                    'entries_count': len(toc_result.get('entries', []))
                }
            except Exception as e:
                pipeline_results['pipeline_steps']['toc'] = {'status': 'error', 'error': str(e)}
            
            try:
                processor = GranularChunkProcessor()
                chunk_result = processor.process_entire_document(document.id)
                pipeline_results['pipeline_steps']['chunking'] = {
                    'status': 'success',
                    'chunks_created': len(chunk_result.get('chunks_created', []))
                }
            except Exception as e:
                pipeline_results['pipeline_steps']['chunking'] = {'status': 'error', 'error': str(e)}
            
            try:
                embedding_gen = EmbeddingGenerator()
                chunks = DocumentChunk.objects.filter(document=document)
                if chunks.exists():
                    embedding_result = embedding_gen.generate_batch_embeddings(chunks)
                    pipeline_results['pipeline_steps']['embedding'] = {
                        'status': 'success',
                        'embeddings_created': len(embedding_result.get('embeddings', []))
                    }
                else:
                    pipeline_results['pipeline_steps']['embedding'] = {'status': 'skipped', 'reason': 'no_chunks'}
            except Exception as e:
                pipeline_results['pipeline_steps']['embedding'] = {'status': 'error', 'error': str(e)}
            
            document.processing_status = 'COMPLETED'
            document.save()
            
            response_data = DocumentSerializer(document).data
            response_data['pipeline_results'] = pipeline_results
            
            logger.info(f"Document uploaded and processed: {document.title}")
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        if 'document' in locals():
            document.processing_status = 'FAILED'
            document.save()
        
        logger.error(f"Error uploading PDF: {str(e)}")
        return Response(
            {'error': f'Failed to upload and process PDF: {str(e)}'},
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
