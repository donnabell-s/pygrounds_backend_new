"""
Page chunking and CRUD operations for document chunks.
"""

from .imports import *
from content_ingestion.helpers.json_export_utils import log_chunk_processing

# === COMPLETE PIPELINE ===

class CompleteDocumentPipelineView(APIView):
    """
    End-to-end document processing:
    1. Generate TOC
    2. Chunk document (fine-grained, not just TOC-based)
    3. Generate embeddings (optional)
    4. Return overall summary
    """
    def post(self, request, document_id=None):
        try:
            if not document_id:
                return Response({'error': 'document_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
            include_embeddings = request.query_params.get('include_embeddings', 'true').lower() == 'true'
            document = get_object_or_404(UploadedDocument, id=document_id)

            print(f"\n{'='*80}")
            print(f"COMPLETE PIPELINE - {document.title} (Include embeddings: {include_embeddings})")
            print(f"{'='*80}")

            pipeline_results = {
                'document_id': document.id,
                'document_title': document.title,
                'total_pages': document.total_pages,
                'pipeline_steps': {}
            }

            # 1. TOC
            print("\n🔍 STEP 1: TOC GENERATION")
            try:
                from content_ingestion.helpers.toc_parser.toc_apply import apply_toc_to_document
                toc_results = apply_toc_to_document(document)
                toc_count = TOCEntry.objects.filter(document=document).count()
                pipeline_results['pipeline_steps']['toc_generation'] = {
                    'status': 'success',
                    'entries_created': toc_count,
                    'toc_source': toc_results.get('toc_source', 'unknown')
                }
                print(f"✅ TOC generated ({toc_count} entries)")
            except Exception as e:
                pipeline_results['pipeline_steps']['toc_generation'] = {'status': 'error', 'error': str(e)}
                print(f"❌ TOC generation failed: {e}")

            # 2. Chunking
            print("\n🧩 STEP 2: CHUNKING")
            try:
                from content_ingestion.helpers.page_chunking.toc_chunk_processor import GranularChunkProcessor
                processor = GranularChunkProcessor(enable_embeddings=False)
                chunk_results = processor.process_entire_document(document)
                pipeline_results['pipeline_steps']['chunking'] = {
                    'status': 'success',
                    'total_chunks_created': chunk_results['total_chunks_created'],
                    'pages_processed': chunk_results['total_pages_processed'],
                    'chunk_types_distribution': chunk_results['chunk_types_distribution']
                }
                print(f"✅ Chunking complete ({chunk_results['total_chunks_created']} chunks)")
            except Exception as e:
                pipeline_results['pipeline_steps']['chunking'] = {'status': 'error', 'error': str(e)}
                print(f"❌ Chunking failed: {e}")
                return Response({
                    'status': 'error',
                    'message': f'Chunking failed: {e}',
                    'pipeline_results': pipeline_results
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 3. Embeddings (optional)
            if include_embeddings:
                print("\n🔮 STEP 3: EMBEDDINGS")
                try:
                    from content_ingestion.helpers.embedding_utils import EmbeddingGenerator
                    embedding_generator = EmbeddingGenerator()
                    chunks = DocumentChunk.objects.filter(document=document)
                    to_embed = chunks.filter(embedding__isnull=True)
                    if to_embed.exists():
                        embedding_results = embedding_generator.embed_chunks_batch(to_embed)
                        pipeline_results['pipeline_steps']['embeddings'] = {
                            'status': 'success',
                            'total_chunks': chunks.count(),
                            'newly_embedded': embedding_results.get('successful', 0),
                            'failed_embeddings': embedding_results.get('failed', 0)
                        }
                        print(f"✅ Embeddings generated ({embedding_results.get('successful', 0)})")
                    else:
                        pipeline_results['pipeline_steps']['embeddings'] = {
                            'status': 'success',
                            'total_chunks': chunks.count(),
                            'newly_embedded': 0,
                            'message': 'All chunks already have embeddings'
                        }
                        print("✅ All chunks already embedded")
                except Exception as e:
                    pipeline_results['pipeline_steps']['embeddings'] = {'status': 'error', 'error': str(e)}
                    print(f"❌ Embedding generation failed: {e}")
            else:
                pipeline_results['pipeline_steps']['embeddings'] = {'status': 'skipped', 'reason': 'include_embeddings=false'}
                print("⏭️  Embeddings skipped")

            # Finalize
            document.processing_status = 'COMPLETED'
            document.parsed = True
            document.save()

            total_chunks = DocumentChunk.objects.filter(document=document).count()
            print("\n🎉 COMPLETE PIPELINE FINISHED")
            print(f"Document Status: {document.processing_status} | Chunks: {total_chunks}")
            print(f"{'='*80}\n")

            return Response({
                'status': 'success',
                'message': 'Complete pipeline processing finished',
                'document_status': document.processing_status,
                'total_chunks_ready': total_chunks,
                'pipeline_results': pipeline_results
            })
        except Exception as e:
            logger.error(f"[Complete Pipeline Error] {e}")
            return Response({
                'status': 'error',
                'message': str(e),
                'document_id': document_id,
                'pipeline_results': pipeline_results if 'pipeline_results' in locals() else {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# === GRANULAR CHUNKING ===

class ChunkAllPagesView(APIView):
    """
    Chunk all pages of a document using semantic classification (not just TOC).
    """
    def post(self, request, document_id=None):
        try:
            if not document_id:
                return Response({'error': 'document_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
            include_embeddings = request.query_params.get('include_embeddings', 'true').lower() == 'true'
            document = get_object_or_404(UploadedDocument, id=document_id)
            print(f"\n{'='*80}")
            print(f"CHUNK ALL PAGES - {document.title} (Include embeddings: {include_embeddings})")
            print(f"{'='*80}")

            from content_ingestion.helpers.page_chunking.toc_chunk_processor import GranularChunkProcessor
            processor = GranularChunkProcessor(enable_embeddings=include_embeddings)
            results = processor.process_entire_document(document)

            # Update document status
            if results['total_chunks_created'] > 0:
                document.processing_status = 'COMPLETED'
                document.parsed = True
                document.save()

            # Prepare log
            chunks = DocumentChunk.objects.filter(document=document)
            chunks_data = [{
                'id': chunk.id,
                'chunk_type': chunk.chunk_type,
                'content': chunk.content,
                'page_number': chunk.page_number,
                'start_page': chunk.start_page,
                'end_page': chunk.end_page,
                'topic_title': chunk.topic_title,
                'subtopic_title': chunk.subtopic_title,
                'has_embedding': chunk.embedding is not None,
                'embedding_vector': chunk.embedding if chunk.embedding else None,
                'embedding_dimensions': len(chunk.embedding) if chunk.embedding else 0
            } for chunk in chunks]

            log_metadata = {
                'document_title': document.title,
                'document_status': document.processing_status,
                'total_pages': document.total_pages,
                'processing_summary': results,
                'include_embeddings': include_embeddings
            }
            log_result = log_chunk_processing(document.id, chunks_data, log_metadata)

            return Response({
                'status': 'success',
                'document_id': document.id,
                'document_title': document.title,
                'document_status': document.processing_status,
                'total_pages': document.total_pages,
                'processing_summary': results,
                'embedding_stats': results.get('embedding_stats', {}),
                'chunks_ready_for_rag': results['total_chunks_created'],
                'json_log': log_result
            })
        except Exception as e:
            logger.error(f"[Chunk All Pages Error] {e}")
            return Response({
                'status': 'error',
                'message': str(e),
                'document_id': document_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# === CHUNK CRUD ===

@api_view(['GET'])
def get_document_chunks(request, document_id):
    """
    List all document chunks. Optionally include meta chunks or filter by type.
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        include_meta = request.query_params.get('include_meta', 'false').lower() == 'true'
        filter_type = request.query_params.get('chunk_type', None)

        chunks = DocumentChunk.objects.filter(document=document)
        if not include_meta:
            chunks = chunks.exclude(chunk_type__in=['TOC', 'Header', 'Meta', 'Index', 'Acknowledgement'])
        if filter_type:
            chunks = chunks.filter(chunk_type=filter_type)
        chunks = chunks.order_by('page_number', 'order_in_doc')

        chunk_type_counts = {}
        total_tokens = 0
        chunks_data = []
        for chunk in chunks:
            tokens = chunk.token_count or 0
            total_tokens += tokens
            chunk_type_counts[chunk.chunk_type] = chunk_type_counts.get(chunk.chunk_type, 0) + 1
            chunks_data.append({
                'id': chunk.id,
                'text': chunk.text,
                'chunk_type': chunk.chunk_type,
                'topic_title': chunk.topic_title,
                'subtopic_title': chunk.subtopic_title,
                'difficulty': '',
                'page_number': chunk.page_number,
                'order_in_doc': chunk.order_in_doc,
                'token_count': tokens,
                'token_encoding': chunk.token_encoding
            })
        return Response({
            'status': 'success',
            'document_title': document.title,
            'total_chunks': len(chunks_data),
            'total_tokens': total_tokens,
            'avg_tokens_per_chunk': round(total_tokens / len(chunks_data), 2) if chunks_data else 0,
            'chunk_type_distribution': chunk_type_counts,
            'filtering': {
                'include_meta': include_meta,
                'filter_type': filter_type,
                'excluded_types': ['TOC', 'Header', 'Meta', 'Index', 'Acknowledgement'] if not include_meta else []
            },
            'chunks': chunks_data
        })
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_single_chunk(request, chunk_id):
    """Retrieve full details for a single chunk."""
    try:
        chunk = get_object_or_404(DocumentChunk, id=chunk_id)
        chunk_data = {
            'id': chunk.id,
            'document_id': chunk.document.id,
            'document_title': chunk.document.title,
            'chunk_type': chunk.chunk_type,
            'text': chunk.text,
            'page_number': chunk.page_number,
            'order_in_doc': chunk.order_in_doc,
            'topic_title': chunk.topic_title,
            'subtopic_title': chunk.subtopic_title,
            'token_count': chunk.token_count,
            'token_encoding': chunk.token_encoding,
            'confidence_score': chunk.confidence_score,
            'parser_metadata': chunk.parser_metadata,
            'has_embedding': bool(chunk.embedding),
            'embedding_model': chunk.embedding_model,
            'embedded_at': chunk.embedded_at.isoformat() if chunk.embedded_at else None
        }
        return Response({'status': 'success', 'chunk': chunk_data})
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_document_chunks_full(request, document_id):
    """
    Retrieve all chunks for a document, optimized for LLM consumption.
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        print(f"\n🚀 RETRIEVING OPTIMIZED CHUNKS for {document.title}")

        optimizer = ChunkOptimizer()
        optimization_result = optimizer.optimize_chunks(document_id)
        optimized_chunks = optimization_result['optimized_chunks']
        stats = optimization_result['optimization_stats']
        llm_format = optimization_result['llm_ready_format']

        print(f"\n📊 OPTIMIZATION RESULTS")
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
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def _group_optimized_chunks_by_page(chunks_data):
    pages = {}
    for chunk in chunks_data:
        page_num = chunk['page_number']
        pages.setdefault(page_num, []).append({
            'id': chunk['id'],
            'clean_title': chunk['clean_title'],
            'content_type': chunk['content_type'],
            'concepts': chunk['concepts'],
            'code_examples_count': chunk['code_examples_count'],
            'exercises_count': chunk['exercises_count'],
            'llm_context': chunk['llm_context']
        })
    return pages

def _get_difficulty_distribution(chunks_data):
    distribution = {}
    for chunk in chunks_data:
        t = chunk['content_type']
        distribution[t] = distribution.get(t, 0) + 1
    return distribution

@api_view(['GET'])
def get_chunks_by_type(request, document_id, chunk_type):
    """
    Get all chunks of a specific type for a document.
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        valid_types = [
            'Concept', 'Exercise', 'Example', 'Try_It', 'Text', 'Code', 'Table', 'Figure',
            'Introduction', 'Acknowledgement', 'TOC', 'Index', 'Header', 'Meta'
        ]
        if chunk_type not in valid_types:
            return Response({
                'status': 'error',
                'message': f'Invalid chunk type. Valid types: {", ".join(valid_types)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        chunks = DocumentChunk.objects.filter(document=document, chunk_type=chunk_type).order_by('page_number', 'order_in_doc')
        chunks_data = [{
            'id': chunk.id,
            'text': chunk.text,
            'chunk_type': chunk.chunk_type,
            'page_number': chunk.page_number,
            'order_in_doc': chunk.order_in_doc,
            'topic_title': chunk.topic_title,
            'subtopic_title': chunk.subtopic_title,
            'has_embedding': bool(chunk.embedding),
            'text_length': len(chunk.text)
        } for chunk in chunks]
        return Response({
            'status': 'success',
            'document_title': document.title,
            'chunk_type': chunk_type,
            'total_chunks': len(chunks_data),
            'chunks': chunks_data
        })
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_coding_chunks_for_minigames(request, document_id):
    """
    Get coding-related chunks for minigame generation.
    Types: Exercise, Try_It, Code, Example, Concept
    Query params:
      - include_context (bool, default true)
      - min_length (int, default 50)
      - semantic_context (bool, default true)
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        include_context = request.GET.get('include_context', 'true').lower() == 'true'
        min_length = int(request.GET.get('min_length', '50'))
        semantic_context = request.GET.get('semantic_context', 'true').lower() == 'true'
        coding_chunk_types = ['Exercise', 'Try_It', 'Code', 'Example', 'Concept']

        # Initial queryset (filter out empty text)
        chunks = DocumentChunk.objects.filter(
            document=document, chunk_type__in=coding_chunk_types
        ).exclude(text__isnull=True).exclude(text='').order_by('page_number', 'order_in_doc')
        # Further filter by min_length if set
        if min_length > 0:
            chunks = [chunk for chunk in chunks if len(chunk.text.strip()) >= min_length]

        coding_chunks = []
        for chunk in chunks:
            chunk_data = {
                'id': chunk.id,
                'text': chunk.text,
                'chunk_type': chunk.chunk_type,
                'page_number': chunk.page_number,
                'order_in_doc': chunk.order_in_doc,
                'topic_title': chunk.topic_title,
                'subtopic_title': chunk.subtopic_title,
                'has_embedding': bool(chunk.embedding),
                'text_length': len(chunk.text),
                'token_count': getattr(chunk, 'token_count', 0)
            }
            if semantic_context:
                try:
                    from content_ingestion.helpers.coding_rag_utils import create_coding_context_for_embedding, extract_programming_concepts
                    chunk_data['enhanced_context'] = create_coding_context_for_embedding(
                        chunk.text, chunk.chunk_type, chunk.topic_title or "", chunk.subtopic_title or ""
                    )
                    chunk_data['programming_concepts'] = extract_programming_concepts(chunk.text)
                    chunk_data['semantic_ready'] = True
                    chunk_data['context_type'] = 'enhanced_with_domain_detection'
                except ImportError:
                    chunk_data['semantic_ready'] = False
                    chunk_data['enhanced_context'] = f"{chunk.chunk_type}: {chunk.text}"
            if include_context and (chunk.topic_title or chunk.subtopic_title):
                ctx = []
                if chunk.topic_title: ctx.append(f"Topic: {chunk.topic_title}")
                if chunk.subtopic_title: ctx.append(f"Subtopic: {chunk.subtopic_title}")
                chunk_data['learning_context'] = " | ".join(ctx)
            coding_chunks.append(chunk_data)

        # Group by type for reporting
        chunks_by_type = {}
        for c in coding_chunks:
            chunks_by_type.setdefault(c['chunk_type'], []).append(c)

        return Response({
            'status': 'success',
            'document_id': document.id,
            'document_title': document.title,
            'total_coding_chunks': len(coding_chunks),
            'coding_chunk_types': list(chunks_by_type.keys()),
            'chunks_by_type_count': {k: len(v) for k, v in chunks_by_type.items()},
            'filters_applied': {
                'include_context': include_context,
                'min_length': min_length,
                'semantic_context': semantic_context
            },
            'chunks': coding_chunks,
            'chunks_by_type': chunks_by_type
        })
    except UploadedDocument.DoesNotExist:
        return Response({'status': 'error', 'message': f'Document with id {document_id} not found.'}, status=status.HTTP_404_NOT_FOUND)
    except ValueError as e:
        return Response({'status': 'error', 'message': f'Invalid parameter: {e}'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'status': 'error', 'message': f'Unexpected error: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
