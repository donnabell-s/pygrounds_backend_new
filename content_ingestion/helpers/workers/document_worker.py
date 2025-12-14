# Worker entrypoints for subprocess-safe document processing.

import os
import django


_DJANGO_READY = False


def setup_django() -> None:
    # Initialize Django once per worker process.
    global _DJANGO_READY
    if _DJANGO_READY:
        return

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pygrounds_backend_new.settings')
    django.setup()
    _DJANGO_READY = True


def process_document_task(task_data):
    # Process one pipeline step for a document.
    try:
        setup_django()

        document_id, reprocess, step = task_data

        from content_ingestion.models import UploadedDocument, DocumentChunk

        document = UploadedDocument.objects.get(id=document_id)

        if step == 'cleanup' and reprocess:
            try:
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
