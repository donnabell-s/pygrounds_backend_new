from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.shortcuts import get_object_or_404
from content_ingestion.models import GameZone, Topic, Subtopic, ContentMapping, TOCEntry, UploadedDocument, DocumentChunk
from .serializers import (
    GameZoneSerializer, TopicSerializer, SubtopicSerializer,
    ContentMappingSerializer, TOCEntryMappingSerializer
)
from .helpers.toc_parser.toc_apply import generate_toc_entries_for_document, generate_and_chunk_document
from .helpers.page_chunking.chunk_optimizer import ChunkOptimizer
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
        Generate TOC for a PDF by reading from UploadedDocument database only.
        Returns array of saved TOC entries for chunking/testing.
        Query parameters:
        - skip_nlp: Set to 'true' to skip NLP matching for faster processing
        """
        try:
            skip_nlp = request.query_params.get('skip_nlp', 'false').lower() == 'true'
            if not document_id:
                return Response({'error': 'document_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
            document = get_object_or_404(UploadedDocument, id=document_id)
            logger.info(f"Processing document: {document.title}")
            
            print(f"\n{'='*80}")
            print(f"TOC GENERATION API - Document: {document.title}")
            print(f"{'='*80}")
            
            # Extract and save TOC
            matched_entries = generate_toc_entries_for_document(document, skip_nlp=skip_nlp)
            
            # Get all TOC entries for this document
            all_entries = TOCEntry.objects.filter(document=document).order_by('order')
            
            # Get content mappings for matched entries
            content_mappings = ContentMapping.objects.filter(
                toc_entry__document=document
            ).select_related('topic', 'subtopic', 'zone')
            
            print(f"\n📊 PROCESSING RESULTS:")
            print(f"{'─'*60}")
            print(f"Total TOC entries parsed: {all_entries.count()}")
            print(f"Entries with topic mapping: {content_mappings.count()}")
            print(f"Entries returned for chunking: {len(matched_entries)}")
            
            # Prepare detailed matching information for JSON response
            matched_entries_details = []
            skipped_entries_details = []
            
            if content_mappings.exists():
                print(f"\n💾 MATCHED ENTRIES SAVED TO DATABASE:")
                print(f"{'─'*60}")
                for i, mapping in enumerate(content_mappings, 1):
                    entry = mapping.toc_entry
                    match_type = "Subtopic" if mapping.subtopic else "Topic"
                    match_obj = mapping.subtopic or mapping.topic
                    zone = mapping.zone
                    
                    print(f"{i:2d}. TOC: '{entry.title[:45]}...'")
                    print(f"    Pages: {entry.start_page+1}-{entry.end_page+1 if entry.end_page else 'end'}")
                    print(f"    Maps to: {match_type} '{match_obj.name}' (Zone: {zone.name if zone else 'None'})")
                    print(f"    Confidence: {mapping.confidence_score:.3f}")
                    print()
                    
                    # Add to JSON response data
                    matched_entries_details.append({
                        'id': entry.id,
                        'title': entry.title,
                        'level': entry.level,
                        'start_page': entry.start_page,
                        'end_page': entry.end_page,
                        'order': entry.order,
                        'match_type': match_type.lower(),
                        'matched_to': {
                            'id': match_obj.id,
                            'name': match_obj.name,
                            'zone': zone.name if zone else None
                        },
                        'confidence_score': mapping.confidence_score
                    })
            else:
                print(f"\n❌ No entries were matched to topics/subtopics")
            
            # Get entries that were skipped or had low confidence
            all_entry_ids = set(all_entries.values_list('id', flat=True))
            matched_entry_ids = set(content_mappings.values_list('toc_entry_id', flat=True))
            unmatched_entry_ids = all_entry_ids - matched_entry_ids
            
            if unmatched_entry_ids:
                unmatched_entries = TOCEntry.objects.filter(id__in=unmatched_entry_ids)
                for entry in unmatched_entries:
                    skipped_entries_details.append({
                        'id': entry.id,
                        'title': entry.title,
                        'level': entry.level,
                        'start_page': entry.start_page,
                        'end_page': entry.end_page,
                        'order': entry.order,
                        'reason': 'low_confidence_or_meta'
                    })
            
            # Query only relevant TOC entries for chunking
            response_data = list(
                TOCEntry.objects.filter(document=document)
                .order_by('order')
                .values('id', 'title', 'level', 'start_page', 'end_page', 'order')
            )
            
            print(f"🚀 API Response: {len(response_data)} entries returned")
            print(f"{'='*80}\n")
            
            return Response({
                'status': 'success',
                'document_title': document.title,
                'total_pages': document.total_pages,
                'processing_summary': {
                    'total_entries_parsed': all_entries.count(),
                    'matched_entries': content_mappings.count(),
                    'skipped_entries': len(skipped_entries_details),
                    'entries_for_chunking': len(response_data)
                },
                'matched_entries': matched_entries_details,
                'skipped_entries': skipped_entries_details,
                'entries_to_chunk': response_data
            })
            document.processing_status = 'COMPLETED'
            document.save(update_fields=['processing_status'])
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[TOC Extraction Error] {error_msg}")
            return Response({
                'status': 'error',
                'message': error_msg
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DocumentChunkingView(APIView):
    """
    Complete document processing: TOC generation + topic matching + chunking for RAG.
    """
    def post(self, request, document_id=None):
        """
        Process document completely: Generate TOC, match topics, and create chunks.
        Query parameters:
        - include_chunking: Set to 'false' to skip chunking (default: 'true')
        - skip_nlp: Set to 'true' to skip NLP matching for faster processing (default: 'false')
        """
        try:
            if not document_id:
                return Response({'error': 'document_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Parse query parameters
            include_chunking = request.query_params.get('include_chunking', 'true').lower() == 'true'
            skip_nlp = request.query_params.get('skip_nlp', 'false').lower() == 'true'
            
            document = get_object_or_404(UploadedDocument, id=document_id)
            logger.info(f"Complete processing for document: {document.title}")
            
            print(f"\n{'='*80}")
            print(f"COMPLETE DOCUMENT PROCESSING API - Document: {document.title}")
            print(f"Include Chunking: {include_chunking}")
            print(f"Skip NLP: {skip_nlp}")
            print(f"{'='*80}")
            
            # Process document completely
            results = generate_and_chunk_document(
                document=document,
                include_chunking=include_chunking,
                skip_nlp=skip_nlp,
                fast_mode=True
            )
            
            # Prepare response with all processing details
            response_data = {
                'status': 'success',
                'document_id': document.id,
                'document_title': document.title,
                'document_status': document.processing_status,
                'total_pages': document.total_pages,
                'processing_summary': {
                    'toc_processing': results['toc_stats'],
                    'chunking_processing': results['chunking_stats']
                },
                'matched_entries': results['matched_entries'],
                'entries_ready_for_rag': len(results['matched_entries']) if include_chunking else 0
            }
            
            print(f"\n🎉 API RESPONSE READY")
            print(f"{'─'*60}")
            print(f"TOC Entries Found: {results['toc_stats'].get('total_entries_found', 0)}")
            print(f"Matched Entries: {results['toc_stats'].get('matched_entries_count', 0)}")
            if include_chunking and 'chunks_created' in results['chunking_stats']:
                print(f"Chunks Created: {results['chunking_stats']['chunks_created']}")
                print(f"Pages Processed: {results['chunking_stats']['pages_processed']}")
            print(f"Document Status: {document.processing_status}")
            print(f"{'='*80}\n")
            
            return Response(response_data)
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[Document Chunking Error] {error_msg}")
            return Response({
                'status': 'error',
                'message': error_msg,
                'document_id': document_id
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


@api_view(['GET'])
def get_document_chunks(request, document_id):
    """
    Get all chunks created for a document.
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        chunks = DocumentChunk.objects.filter(document=document).order_by('page_number', 'order_in_doc')
        
        chunks_data = []
        for chunk in chunks:
            chunks_data.append({
                'id': chunk.id,
                'text': chunk.text,  # Full text instead of preview
                'topic_title': chunk.topic_title,
                'subtopic_title': chunk.subtopic_title,  # Added subtopic_title
                'difficulty': '',  # Empty as requested - handled at higher level
                'page_number': chunk.page_number,  # 0-based as stored in DB
                'order_in_doc': chunk.order_in_doc
            })
        
        return Response({
            'status': 'success',
            'document_title': document.title,
            'total_chunks': len(chunks_data),
            'chunks': chunks_data
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_document_chunks_full(request, document_id):
    """
    Get all chunks created for a document with FULL optimized content for LLM consumption.
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        print(f"\n🚀 RETRIEVING OPTIMIZED CHUNKS")
        print(f"Document: {document.title}")
        print(f"{'='*50}")
        
        # Initialize optimizer and process chunks
        optimizer = ChunkOptimizer()
        optimization_result = optimizer.optimize_chunks(document_id)
        
        optimized_chunks = optimization_result['optimized_chunks']
        stats = optimization_result['optimization_stats']
        llm_format = optimization_result['llm_ready_format']
        
        print(f"\n📊 OPTIMIZATION RESULTS")
        print(f"{'─'*30}")
        print(f"Total chunks: {stats['total_chunks']}")
        print(f"Title fixes: {stats['title_fixes']}")
        print(f"Content improvements: {stats['content_improvements']}")
        
        return Response({
            'status': 'success',
            'document_title': document.title,
            'document_total_pages': document.total_pages,
            'total_chunks': stats['total_chunks'],
            'optimization_stats': stats,
            'chunks_by_page': _group_optimized_chunks_by_page(optimized_chunks),
            'optimized_chunks': optimized_chunks,
            'llm_ready_format': llm_format,
            'summary': {
                'total_concepts_extracted': sum(len(chunk['concepts'].split()) if isinstance(chunk['concepts'], str) else len(chunk['concepts']) for chunk in optimized_chunks),
                'total_code_examples': sum(chunk['code_examples_count'] for chunk in optimized_chunks),
                'total_exercises': sum(chunk['exercises_count'] for chunk in optimized_chunks),
                'content_type_distribution': _get_difficulty_distribution(optimized_chunks)
            }
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _group_chunks_by_page(chunks_data):
    """Helper to group chunks by page number for easier debugging."""
    pages = {}
    for chunk in chunks_data:
        page_num = chunk['page_number']
        if page_num not in pages:
            pages[page_num] = []
        pages[page_num].append(chunk)
    return pages


def _group_optimized_chunks_by_page(chunks_data):
    """Helper to group optimized chunks by page number."""
    pages = {}
    for chunk in chunks_data:
        page_num = chunk['page_number']
        if page_num not in pages:
            pages[page_num] = []
        pages[page_num].append({
            'id': chunk['id'],
            'clean_title': chunk['clean_title'],
            'content_type': chunk['content_type'],
            'concepts': chunk['concepts'],
            'code_examples_count': chunk['code_examples_count'],
            'exercises_count': chunk['exercises_count'],
            # 'structured_content': chunk['structured_content'],  # REMOVED - too verbose
            'llm_context': chunk['llm_context']
        })
    return pages


def _get_difficulty_distribution(chunks_data):
    """Get content type distribution."""
    distribution = {}
    for chunk in chunks_data:
        content_type = chunk['content_type']
        distribution[content_type] = distribution.get(content_type, 0) + 1
    return distribution
