"""
Document processing worker module for ProcessPool.
Separate module to avoid Django initialization issues in worker processes.
"""

import os
import sys
import django

def setup_django():
    """Setup Django in worker process"""
    # Add the parent directory to the Python path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    # Setup Django environment
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pygrounds_backend_new.settings')
    django.setup()

def process_document_task(task_data):
    """
    Worker function to process a document in a separate process.
    
    Args:
        task_data: tuple (document_id, reprocess_flag, step_name)
        
    Returns:
        tuple (step_name, result_dict)
    """
    try:
        setup_django()
        
        document_id, reprocess, step = task_data
        
        # Import Django models after setup
        from content_ingestion.models import UploadedDocument, DocumentChunk
        
        document = UploadedDocument.objects.get(id=document_id)
        
        if step == 'cleanup' and reprocess:
            try:
                # Delete existing TOC entries and chunks
                document.toc_entry_set.all().delete()
                document.documentchunk_set.all().delete()
                
                return ('cleanup', {
                    'status': 'success',
                    'message': 'Previous processing artifacts cleaned up successfully'
                })
            except Exception as e:
                return ('cleanup', {
                    'status': 'error',
                    'message': f'Cleanup failed: {str(e)}',
                    'error': str(e)
                })
        
        elif step == 'toc':
            try:
                from content_ingestion.helpers.toc_parser import generate_toc_entries_for_document
                toc_entries = generate_toc_entries_for_document(document)
                entries_count = len(toc_entries) if toc_entries else 0
                
                if entries_count > 0:
                    return ('toc', {
                        'status': 'success',
                        'message': f'Table of contents generated with {entries_count} entries',
                        'entries_count': entries_count
                    })
                else:
                    return ('toc', {
                        'status': 'error',
                        'message': 'TOC generation completed but no entries were found',
                        'entries_count': 0,
                        'error': 'No TOC entries generated'
                    })
                    
            except Exception as e:
                return ('toc', {
                    'status': 'error',
                    'message': f'TOC generation failed: {str(e)}',
                    'error': str(e),
                    'entries_count': 0
                })
        
        elif step == 'chunking':
            try:
                from content_ingestion.helpers.page_chunking.toc_chunk_processor import GranularChunkProcessor
                processor = GranularChunkProcessor()
                chunk_result = processor.process_entire_document(document)
                chunks_created = chunk_result.get('total_chunks_created', 0)
                
                if chunks_created > 0:
                    return ('chunking', {
                        'status': 'success',
                        'message': f'Document chunked successfully into {chunks_created} chunks',
                        'chunks_created': chunks_created
                    })
                else:
                    return ('chunking', {
                        'status': 'error',
                        'message': 'Chunking completed but no chunks were created',
                        'chunks_created': 0,
                        'error': 'No chunks generated'
                    })
                    
            except Exception as e:
                return ('chunking', {
                    'status': 'error',
                    'message': f'Chunking failed: {str(e)}',
                    'error': str(e),
                    'chunks_created': 0
                })
        
        elif step == 'embedding':
            try:
                from content_ingestion.helpers.embedding.generator import EmbeddingGenerator
                embedding_gen = EmbeddingGenerator()
                chunks = DocumentChunk.objects.filter(document=document)
                
                if chunks.exists():
                    embedding_result = embedding_gen.embed_and_save_batch(chunks)
                    embeddings_created = embedding_result.get('embeddings_generated', 0)
                    
                    return ('embedding', {
                        'status': 'success',
                        'message': f'Generated {embeddings_created} embeddings for {chunks.count()} chunks',
                        'embeddings_created': embeddings_created,
                        'database_saves': embedding_result.get('database_saves', 0),
                        'chunks_processed': chunks.count()
                    })
                else:
                    return ('embedding', {
                        'status': 'error',
                        'message': 'No chunks found for embedding generation',
                        'embeddings_created': 0,
                        'chunks_processed': 0,
                        'error': 'No chunks available'
                    })
                    
            except Exception as e:
                return ('embedding', {
                    'status': 'error',
                    'message': f'Embedding generation failed: {str(e)}',
                    'error': str(e),
                    'embeddings_created': 0
                })
        
        elif step == 'semantic':
            try:
                from content_ingestion.helpers.semantic_similarity import compute_semantic_similarities_for_document
                semantic_result = compute_semantic_similarities_for_document(
                    document_id=document_id, 
                    similarity_threshold=0.1,
                    top_k_results=10
                )
                
                return ('semantic', {
                    'status': semantic_result['status'],
                    'message': f'Processed {semantic_result.get("processed_subtopics", 0)} subtopics with {semantic_result.get("total_similarities", 0)} similarities',
                    'processed_subtopics': semantic_result.get('processed_subtopics', 0),
                    'total_similarities': semantic_result.get('total_similarities', 0)
                })
                
            except Exception as e:
                return ('semantic', {
                    'status': 'error',
                    'message': f'Semantic similarity computation failed: {str(e)}',
                    'error': str(e)
                })
        
        else:
            return (step, {
                'status': 'error',
                'message': f'Unknown processing step: {step}',
                'error': 'Unknown step'
            })
    
    except Exception as e:
        return (step if 'step' in locals() else 'unknown', {
            'status': 'error',
            'message': f'Worker process error: {str(e)}',
            'error': str(e)
        })
