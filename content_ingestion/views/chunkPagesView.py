from ..helpers.view_imports import *
from ..helpers.helper_imports import *
from content_ingestion.models import CHUNK_TYPE_CHOICES
from multiprocessing import Pool
import psutil
import threading
import queue
import time
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

# Global processing queue management
_processing_queue = queue.Queue()
_active_processing = set()
_max_concurrent_documents = None
_queue_lock = threading.Lock()

def _get_max_concurrent_documents():
    """Determine maximum number of documents that can be processed concurrently."""
    global _max_concurrent_documents
    if _max_concurrent_documents is None:
        cpu_count = psutil.cpu_count(logical=True)

        # Balanced approach: consider that some processing steps use parallel workers
        # Use 1 document per 3 CPU cores, minimum 2, maximum 6
        # This accounts for parallel processing within documents (like 16 workers for question generation)
        _max_concurrent_documents = max(2, min(6, cpu_count // 3))

        logger.info(f"Setting max concurrent document processing to {_max_concurrent_documents} (CPU cores: {cpu_count})")
        logger.info(f"This allows parallel processing within documents while preventing resource exhaustion")
    return _max_concurrent_documents

def _start_queued_processing():
    """Start processing queued documents if slots are available."""
    global _processing_queue, _active_processing, _queue_lock

    with _queue_lock:
        max_concurrent = _get_max_concurrent_documents()
        available_slots = max_concurrent - len(_active_processing)

        if available_slots > 0 and not _processing_queue.empty():
            # Start processing queued documents
            for _ in range(min(available_slots, _processing_queue.qsize())):
                try:
                    document_id, reprocess = _processing_queue.get_nowait()
                    _active_processing.add(document_id)

                    # Start processing in background thread
                    thread = threading.Thread(
                        target=_run_document_pipeline_background,
                        args=(document_id, reprocess),
                        daemon=True
                    )
                    thread.start()
                    logger.info(f"Started queued processing for document {document_id}")

                except queue.Empty:
                    break

def _queue_document_for_processing(document_id, reprocess=False):
    """Queue a document for processing or start immediately if slots available."""
    global _processing_queue, _active_processing, _queue_lock

    with _queue_lock:
        max_concurrent = _get_max_concurrent_documents()

        if len(_active_processing) < max_concurrent:
            # Start processing immediately
            _active_processing.add(document_id)
            thread = threading.Thread(
                target=_run_document_pipeline_background,
                args=(document_id, reprocess),
                daemon=True
            )
            thread.start()
            logger.info(f"Started immediate processing for document {document_id}")
        else:
            # Queue for later processing
            _processing_queue.put((document_id, reprocess))
            logger.info(f"Queued document {document_id} for processing (queue size: {_processing_queue.qsize()})")

def _finish_document_processing(document_id):
    """Mark document processing as complete and start next queued document."""
    global _active_processing, _queue_lock

    with _queue_lock:
        _active_processing.discard(document_id)
        logger.info(f"Finished processing document {document_id}, active processing: {len(_active_processing)}")

        # Start next queued document if available
        _start_queued_processing()

def _run_document_pipeline_background(document_id, reprocess=False):
    """
    Background function to run the complete document processing pipeline using ProcessPool.
    This runs in a separate thread to manage the ProcessPool without blocking HTTP response.
    """
    try:
        document = UploadedDocument.objects.get(id=document_id)

        # Status already set by the main view, just update the message
        document.processing_message = 'Starting document processing pipeline...'
        document.save()

        # Determine optimal number of processes (use fewer since each step is sequential)
        cpu_count = psutil.cpu_count(logical=True)
        max_workers = min(2, max(1, cpu_count - 2))  # Use up to 2 processes for document pipeline

        # Prepare processing tasks in order
        processing_steps = []

        if reprocess:
            processing_steps.append((document_id, reprocess, 'cleanup'))

        # Add the main processing steps
        processing_steps.extend([
            (document_id, reprocess, 'toc'),
            (document_id, reprocess, 'chunking'),
            (document_id, reprocess, 'embedding'),
            (document_id, reprocess, 'semantic')
        ])

        pipeline_results = {
            'document_id': document_id,
            'document_title': document.title,
            'pipeline_steps': {}
        }

        try:
            # Import the worker function from our separate module
            from content_ingestion.document_worker import process_document_task

            # Process steps sequentially (since they depend on each other)
            for step_data in processing_steps:
                step_name = step_data[2]

                # Check if processing was cancelled before each step
                document.refresh_from_db()
                if document.processing_status == 'PENDING':
                    logger.info(f"Processing cancelled for document {document_id} before step {step_name}")
                    return  # Exit early if cancelled

                # Update status message
                status_messages = {
                    'cleanup': 'Cleaning up previous processing artifacts...',
                    'toc': 'Parsing document structure and generating table of contents...',
                    'chunking': 'Chunking document content into semantic units...',
                    'embedding': 'Generating embeddings for content chunks...',
                    'semantic': 'Computing semantic similarities between content chunks...'
                }

                document.processing_message = status_messages.get(step_name, f'Processing {step_name}...')
                document.save()

                # Execute single step in process pool
                with Pool(processes=1) as pool:  # Use single process for sequential steps
                    result = pool.apply(process_document_task, (step_data,))

                step_result_name, step_result = result
                pipeline_results['pipeline_steps'][step_result_name] = step_result

                # Stop if any step fails critically
                if step_result['status'] == 'error' and step_name in ['toc', 'chunking']:
                    logger.error(f"Critical step {step_name} failed for document {document_id}: {step_result['message']}")
                    break

        except Exception as e:
            logger.error(f"ProcessPool error for document {document_id}: {str(e)}")
            pipeline_results['pipeline_steps']['process_error'] = {
                'status': 'error',
                'message': f'Process pool error: {str(e)}',
                'error': str(e)
            }

        # Update final status based on pipeline results
        failed_steps = [step for step, result in pipeline_results['pipeline_steps'].items()
                       if result.get('status') == 'error']

        if failed_steps:
            document.processing_status = 'FAILED'
            document.processing_message = f'Processing failed at steps: {", ".join(failed_steps)}'
        else:
            # Check critical steps completed successfully and produced results
            toc_result = pipeline_results['pipeline_steps'].get('toc', {})
            chunking_result = pipeline_results['pipeline_steps'].get('chunking', {})

            if (toc_result.get('status') == 'success' and toc_result.get('entries_count', 0) > 0 and
                chunking_result.get('status') == 'success' and chunking_result.get('chunks_created', 0) > 0):
                document.processing_status = 'COMPLETED'
                document.processing_message = 'Document processing completed successfully'
            else:
                document.processing_status = 'COMPLETED_WITH_WARNINGS'
                document.processing_message = 'Document processing completed but with potential issues'

        document.save()
        logger.info(f"Document {document_id} processing completed with status: {document.processing_status}")

    except Exception as e:
        logger.error(f"Critical error in document pipeline for {document_id}: {str(e)}")
        try:
            document = UploadedDocument.objects.get(id=document_id)
            document.processing_status = 'FAILED'
            document.processing_message = f'Critical processing error: {str(e)}'
            document.save()
        except Exception:
            pass
    finally:
        # Always mark processing as finished to free up the slot
        _finish_document_processing(document_id)

@csrf_exempt
@api_view(['POST'])
def process_document_pipeline(request, document_id):
    """
    Start processing an uploaded document through the full pipeline using ProcessPool.

    This endpoint queues the document for processing and returns immediately.
    Processing is managed globally to prevent resource contention.
    Use GET /docs/<document_id>/ to check the processing status.
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)

        if document.processing_status == 'PROCESSING':
            return Response({
                'status': 'error',
                'message': 'Document is already being processed',
                'document_id': document_id,
                'current_status': document.processing_status,
                'current_message': document.processing_message
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get reprocess flag from request
        reprocess = request.data.get('reprocess', False)

        # Auto-detect if reprocessing is needed based on existing data
        if not reprocess:
            # Check if document already has chunks or TOC entries
            has_chunks = document.chunks.exists()
            has_toc = document.tocentry_set.exists()
            if has_chunks or has_toc:
                logger.info(f"Document {document_id} has existing data (chunks: {has_chunks}, toc: {has_toc}), enabling reprocess mode")
                reprocess = True

        # Queue document for processing (will start immediately if slots available)
        _queue_document_for_processing(document_id, reprocess)

        # Check if processing started immediately or is queued
        max_concurrent = _get_max_concurrent_documents()
        queue_size = _processing_queue.qsize()

        # Update document status immediately based on queue state
        if queue_size == 0:
            document.processing_status = 'PROCESSING'
            document.processing_message = f'Starting document processing pipeline...'
        else:
            document.processing_status = 'QUEUED'
            document.processing_message = f'Document queued for processing (position {queue_size} in queue)'
        document.save()

        if queue_size == 0:
            message = f'Document processing started immediately for "{document.title}"'
            processing_status = 'PROCESSING'
        else:
            message = f'Document queued for processing (position {queue_size} in queue) for "{document.title}"'
            processing_status = 'QUEUED'

        # Return immediately while processing continues in background
        return Response({
            'status': 'success',
            'message': message,
            'document_id': document_id,
            'processing_status': processing_status,
            'max_concurrent_documents': max_concurrent,
            'queue_position': queue_size if queue_size > 0 else 0,
            'note': 'Use GET /api/content_ingestion/docs/{document_id}/ to check processing status'
        }, status=status.HTTP_202_ACCEPTED)

    except Exception as e:
        logger.error(f"Error queuing document {document_id} for processing: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Failed to queue processing: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def cancel_document_pipeline(request, document_id):
    """
    Cancel the document processing pipeline and clean up any partially created objects.
    
    This will:
    1. Mark the document as cancelled
    2. Delete any partially created chunks, embeddings, etc.
    3. Reset the document to PENDING status
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        if document.processing_status not in ['PROCESSING', 'FAILED']:
            return Response({
                'status': 'error',
                'message': f'Cannot cancel document with status: {document.processing_status}',
                'current_status': document.processing_status
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"Cancelling pipeline for document {document_id}: {document.title}")
        
        # Clean up any partially created objects
        cleanup_count = _cleanup_document_objects(document)
        
        # Reset document status
        document.processing_status = 'PENDING'
        document.processing_message = 'Processing cancelled by user. Ready to restart.'
        document.save()
        
        logger.info(f"Pipeline cancelled for document {document_id}. Cleaned up {cleanup_count} objects.")
        
        return Response({
            'status': 'success',
            'message': f'Document processing cancelled for "{document.title}"',
            'document_id': document_id,
            'processing_status': 'PENDING',
            'cleaned_objects': cleanup_count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error cancelling pipeline for document {document_id}: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Failed to cancel processing: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _cleanup_document_objects(document):
    """
    Clean up all objects created during document processing.
    Returns the count of objects cleaned up.
    """
    cleanup_count = 0
    
    try:
        # Delete document chunks
        chunks = document.chunks.all()
        chunk_count = chunks.count()
        if chunk_count > 0:
            chunks.delete()
            cleanup_count += chunk_count
            logger.info(f"Deleted {chunk_count} document chunks")
        
        # Delete TOC entries
        toc_entries = document.tocentry_set.all()
        toc_count = toc_entries.count()
        if toc_count > 0:
            toc_entries.delete()
            cleanup_count += toc_count
            logger.info(f"Deleted {toc_count} TOC entries")
        
        # Delete any document-related embeddings
        from content_ingestion.models import Embedding
        embeddings = Embedding.objects.filter(document_chunk__document=document)
        embedding_count = embeddings.count()
        if embedding_count > 0:
            embeddings.delete()
            cleanup_count += embedding_count
            logger.info(f"Deleted {embedding_count} embeddings")
        
        # Clear parsed pages tracking
        document.parsed_pages = []
        document.save()
        
        logger.info(f"Total cleanup: {cleanup_count} objects removed")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
    
    return cleanup_count


@api_view(['POST'])
def chunk_document_pages(request, document_id):
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        if not document.file:
            return Response({
                'status': 'error',
                'message': 'Document has no file attached'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        processor = GranularChunkProcessor()
        chunk_result = processor.process_entire_document(document_id)
        
        chunks = DocumentChunk.objects.filter(document=document)
        chunks_data = []
        for chunk in chunks:
            chunks_data.append({
                'id': chunk.id,
                'chunk_type': chunk.chunk_type,
                'page_number': chunk.page_number,
                'text_preview': chunk.text[:100] + '...' if len(chunk.text) > 100 else chunk.text
            })
        
        return Response({
            'status': 'success',
            'message': f'Document chunked successfully',
            'document': {
                'id': document.id,
                'title': document.title,
                'total_chunks': len(chunks_data)
            },
            'chunks_created': len(chunk_result.get('chunks_created', [])),
            'chunks': chunks_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Chunking error for document {document_id}: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Chunking failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def generate_document_embeddings(request, document_id):
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        chunk_count = DocumentChunk.objects.filter(document=document).count()
        if chunk_count == 0:
            return Response({
                'status': 'error',
                'message': 'Document has no chunks. Run chunking first.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        embedding_gen = EmbeddingGenerator()
        chunks = DocumentChunk.objects.filter(document=document)
        embedding_result = embedding_gen.embed_and_save_batch(chunks)
        
        return Response({
            'status': 'success',
            'message': f'Embeddings generated and saved successfully',
            'document': {
                'id': document.id,
                'title': document.title,
                'chunk_count': chunk_count
            },
            'embeddings_generated': embedding_result.get('embeddings_generated', 0),
            'database_saves': embedding_result.get('database_saves', 0)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Embedding generation error for document {document_id}: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Embedding generation failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_document_chunks(request, document_id):
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        chunks = DocumentChunk.objects.filter(document=document).order_by(
            'page_number', 'order_in_doc'
        )
        
        if not chunks.exists():
            return Response({
                'status': 'warning',
                'message': 'No chunks found for this document',
                'document': {'id': document.id, 'title': document.title},
                'chunks': []
            }, status=status.HTTP_200_OK)
        
        chunks_by_page = _group_optimized_chunks_by_page(chunks)
        difficulty_stats = _get_difficulty_distribution(chunks)
        
        return Response({
            'status': 'success',
            'document': {
                'id': document.id,
                'title': document.title,
                'total_chunks': chunks.count(),
                'total_pages': chunks.values('page_number').distinct().count()
            },
            'difficulty_distribution': difficulty_stats,
            'chunks_by_page': chunks_by_page
        })
        
    except Exception as e:
        logger.error(f"Error getting chunks for document {document_id}: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Failed to retrieve chunks: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_single_chunk(request, chunk_id):
    try:
        chunk = get_object_or_404(DocumentChunk, id=chunk_id)
        
        chunk_data = {
            'id': chunk.id,
            'document': {
                'id': chunk.document.id,
                'title': chunk.document.title
            },
            'chunk_type': chunk.chunk_type,
            'text': chunk.text,
            'page_number': chunk.page_number,
            'order_in_doc': chunk.order_in_doc,
            'token_count': chunk.token_count,
            'has_embedding': hasattr(chunk, 'embeddings') and chunk.embeddings.exists()
        }
        
        return Response({
            'status': 'success',
            'chunk': chunk_data
        })
        
    except Exception as e:
        logger.error(f"Error getting chunk {chunk_id}: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Failed to retrieve chunk: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_document_chunks_full(request, document_id):
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        chunks = DocumentChunk.objects.filter(document=document).order_by(
            'page_number', 'order_in_doc'
        )
        
        chunks_data = []
        for chunk in chunks:
            chunks_data.append({
                'id': chunk.id,
                'chunk_type': chunk.chunk_type,
                'text': chunk.text,
                'page_number': chunk.page_number,
                'order_in_doc': chunk.order_in_doc,
                'token_count': chunk.token_count,
            })
        
        return Response({
            'status': 'success',
            'document': {
                'id': document.id,
                'title': document.title,
                'total_chunks': len(chunks_data)
            },
            'chunks': chunks_data
        })
        
    except Exception as e:
        logger.error(f"Error getting full chunks for document {document_id}: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Failed to retrieve full chunks: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_chunks_by_type(request, document_id, chunk_type):
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        valid_types = [choice[0] for choice in CHUNK_TYPE_CHOICES]
        if chunk_type not in valid_types:
            return Response({
                'status': 'error',
                'message': f'Invalid chunk type. Valid types: {valid_types}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        chunks = DocumentChunk.objects.filter(
            document=document,
            chunk_type=chunk_type
        ).order_by('page_number', 'order_in_doc')
        
        chunks_data = []
        for chunk in chunks:
            chunks_data.append({
                'id': chunk.id,
                'chunk_type': chunk.chunk_type,
                'page_number': chunk.page_number,
                'text_preview': chunk.text[:200] + '...' if len(chunk.text) > 200 else chunk.text,
                'token_count': chunk.token_count
            })
        
        return Response({
            'status': 'success',
            'document': {
                'id': document.id,
                'title': document.title
            },
            'chunk_type': chunk_type,
            'total_chunks': len(chunks_data),
            'chunks': chunks_data
        })
        
    except Exception as e:
        logger.error(f"Error getting {chunk_type} chunks for document {document_id}: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Failed to retrieve {chunk_type} chunks: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_coding_chunks_for_minigames(request, document_id):
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        coding_chunks = DocumentChunk.objects.filter(
            document=document,
            chunk_type__in=['Code', 'Try_It']
        ).order_by('page_number', 'order_in_doc')
        
        minigame_chunks = []
        for chunk in coding_chunks:
            code_lines = chunk.text.count('\n') + 1
            has_functions = 'def ' in chunk.text
            has_classes = 'class ' in chunk.text
            has_imports = 'import ' in chunk.text or 'from ' in chunk.text
            
            complexity_score = 0
            complexity_score += min(code_lines // 5, 3)
            if has_functions: complexity_score += 2
            if has_classes: complexity_score += 3
            if has_imports: complexity_score += 1
            
            minigame_difficulty = 'easy' if complexity_score <= 2 else 'medium' if complexity_score <= 5 else 'hard'
            
            minigame_chunks.append({
                'id': chunk.id,
                'chunk_type': chunk.chunk_type,
                'page_number': chunk.page_number,
                'text': chunk.text,
                'token_count': chunk.token_count,
                'minigame_metadata': {
                    'difficulty': minigame_difficulty,
                    'complexity_score': complexity_score,
                    'code_lines': code_lines,
                    'has_functions': has_functions,
                    'has_classes': has_classes,
                    'has_imports': has_imports
                }
            })
        
        return Response({
            'status': 'success',
            'document': {
                'id': document.id,
                'title': document.title
            },
            'total_coding_chunks': len(minigame_chunks),
            'difficulty_breakdown': {
                'easy': len([c for c in minigame_chunks if c['minigame_metadata']['difficulty'] == 'easy']),
                'medium': len([c for c in minigame_chunks if c['minigame_metadata']['difficulty'] == 'medium']),
                'hard': len([c for c in minigame_chunks if c['minigame_metadata']['difficulty'] == 'hard'])
            },
            'chunks': minigame_chunks
        })
        
    except Exception as e:
        logger.error(f"Error getting coding chunks for document {document_id}: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Failed to retrieve coding chunks: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def _group_optimized_chunks_by_page(chunks_data):
    chunks_by_page = {}
    for chunk in chunks_data:
        page_num = chunk.page_number
        if page_num not in chunks_by_page:
            chunks_by_page[page_num] = []
        
        chunks_by_page[page_num].append({
            'id': chunk.id,
            'chunk_type': chunk.chunk_type,
            'order_in_doc': chunk.order_in_doc,
            'text_preview': chunk.text[:100] + '...' if len(chunk.text) > 100 else chunk.text,
            'token_count': chunk.token_count
        })
    
    return chunks_by_page

def _get_difficulty_distribution(chunks_data):
    type_counts = {}
    for chunk in chunks_data:
        chunk_type = chunk.chunk_type
        type_counts[chunk_type] = type_counts.get(chunk_type, 0) + 1
    
    return type_counts


@api_view(['POST'])
def upload_and_process_pipeline(request):
    """
    Complete pipeline endpoint: Upload file + run full processing pipeline.
    
    Expected form data:
    - file: PDF file to upload (required)
    - difficulty: Document difficulty level (optional, defaults to 'intermediate')
    
    Processing steps:
    1. Upload and save document (title auto-extracted from filename)
    2. Generate TOC
    3. Chunk pages according to TOC
    4. Generate embeddings
    5. Compute semantic similarities
    """
    try:
        # Check if file is provided
        if 'file' not in request.FILES:
            return Response({
                'status': 'error',
                'message': 'No file provided. Please upload a PDF file.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Import necessary modules
        from content_ingestion.serializers import DocumentSerializer
        from content_ingestion.helpers.toc_parser import generate_toc_entries_for_document
        from content_ingestion.helpers.page_chunking.toc_chunk_processor import GranularChunkProcessor
        from content_ingestion.helpers.embedding.generator import EmbeddingGenerator
        from content_ingestion.helpers.semantic_similarity import compute_semantic_similarities_for_document
        import os
        
        # Prepare document data
        uploaded_file = request.FILES['file']
        difficulty = request.data.get('difficulty', 'intermediate')
        
        # Auto-extract title from filename (remove extension)
        title = os.path.splitext(uploaded_file.name)[0]
        
        document_data = {
            'file': uploaded_file,
            'title': title,
            'difficulty': difficulty
        }
        
        # Validate and save uploaded document
        serializer = DocumentSerializer(data=document_data)
        if not serializer.is_valid():
            return Response({
                'status': 'error',
                'message': 'Invalid document data',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save document and set processing status
        document = serializer.save()
        document.processing_status = 'PROCESSING'
        document.save()
        
        # Initialize pipeline results
        pipeline_results = {
            'document_id': document.id,
            'document_title': document.title,
            'difficulty': document.difficulty,
            'pipeline_steps': {},
            'status': 'success'
        }
        
        try:
            # Step 1: Generate TOC
            toc_result = generate_toc_entries_for_document(document)
            pipeline_results['pipeline_steps']['toc'] = {
                'status': 'success',
                'entries_count': len(toc_result) if toc_result else 0
            }
        except Exception as e:
            pipeline_results['pipeline_steps']['toc'] = {'status': 'error', 'error': str(e)}
        
        try:
            # Step 2: Chunk document pages according to TOC
            chunk_processor = GranularChunkProcessor()
            chunking_result = chunk_processor.process_entire_document(document)
            pipeline_results['pipeline_steps']['chunking'] = {
                'status': 'success',
                'chunks_created': chunking_result.get('total_chunks_created', 0)
            }
        except Exception as e:
            pipeline_results['pipeline_steps']['chunking'] = {'status': 'error', 'error': str(e)}
        
        try:
            # Step 3: Generate embeddings
            embedding_generator = EmbeddingGenerator()
            chunks = DocumentChunk.objects.filter(document=document)
            embedding_result = embedding_generator.embed_and_save_batch(chunks)
            pipeline_results['pipeline_steps']['embeddings'] = {
                'status': 'success',
                'embeddings_generated': embedding_result.get('embeddings_generated', 0),
                'database_saves': embedding_result.get('database_saves', 0)
            }
        except Exception as e:
            pipeline_results['pipeline_steps']['embeddings'] = {'status': 'error', 'error': str(e)}
        
        try:
            # Step 4: Semantic Similarity Processing
            semantic_result = compute_semantic_similarities_for_document(
                document_id=document.id, 
                similarity_threshold=0.1,  # Store similarities above 0.1
                top_k_results=10  # Store top 10 similar chunks per subtopic
            )
            pipeline_results['pipeline_steps']['semantic_similarity'] = {
                'status': semantic_result['status'],
                'processed_subtopics': semantic_result.get('processed_subtopics', 0),
                'total_similarities': semantic_result.get('total_similarities', 0)
            }
        except Exception as e:
            pipeline_results['pipeline_steps']['semantic_similarity'] = {'status': 'error', 'error': str(e)}
        
        # Update document status
        document.processing_status = 'COMPLETED'
        document.save()
        
        # Check if any steps failed
        failed_steps = [step for step, data in pipeline_results['pipeline_steps'].items() 
                       if data.get('status') == 'error']
        
        if failed_steps:
            pipeline_results['status'] = 'partial_success'
            pipeline_results['failed_steps'] = failed_steps
            return Response(pipeline_results, status=status.HTTP_207_MULTI_STATUS)
        
        return Response(pipeline_results, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        # Update document status if it was created
        if 'document' in locals():
            document.processing_status = 'ERROR'
            document.save()
        
        return Response({
            'status': 'error',
            'message': f'Pipeline processing failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_processing_queue_status(request):
    """
    Get the current status of the document processing queue.

    Returns information about:
    - Currently active processing documents
    - Queue size and waiting documents
    - Maximum concurrent processing limit
    """
    with _queue_lock:
        active_count = len(_active_processing)
        queue_size = _processing_queue.qsize()
        max_concurrent = _get_max_concurrent_documents()

        # Get active document details
        active_documents = []
        for doc_id in _active_processing:
            try:
                doc = UploadedDocument.objects.get(id=doc_id)
                active_documents.append({
                    'id': doc.id,
                    'title': doc.title,
                    'status': doc.processing_status,
                    'message': doc.processing_message
                })
            except UploadedDocument.DoesNotExist:
                active_documents.append({
                    'id': doc_id,
                    'title': f'Unknown Document {doc_id}',
                    'status': 'UNKNOWN',
                    'message': 'Document not found'
                })

        return Response({
            'status': 'success',
            'queue_status': {
                'active_processing': active_count,
                'queued_documents': queue_size,
                'max_concurrent': max_concurrent,
                'available_slots': max(0, max_concurrent - active_count)
            },
            'active_documents': active_documents,
            'system_info': {
                'cpu_cores': psutil.cpu_count(logical=True),
                'cpu_physical': psutil.cpu_count(logical=False)
            }
        })
