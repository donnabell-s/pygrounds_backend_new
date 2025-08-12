"""
Page chunking and CRUD operations for document chunks.
"""

from .imports import *
from content_ingestion.helpers.utils.stubs import log_chunk_processing
import PyPDF2
import io
from django.utils import timezone

# === COMPLETE PIPELINE ===

class UploadAndProcessPipelineView(APIView):
    """
    Complete pipeline that accepts PDF upload with difficulty field and processes it:
    1. Upload PDF with automatic title extraction
    2. Generate TOC  
    3. Chunk document
    4. Generate embeddings (automatic)
    5. Return complete processing summary
    
    Required fields:
    - file: PDF file
    - difficulty: 'beginner' | 'intermediate' | 'advanced' | 'master'
    """
    def post(self, request):
        try:
            # Step 1: Handle PDF upload with difficulty validation
            file = request.FILES.get('file')
            if not file:
                return Response({'status': 'error', 'message': 'No file provided.'},
                                status=status.HTTP_400_BAD_REQUEST)

            if not file.name.lower().endswith('.pdf'):
                return Response({'status': 'error', 'message': 'Only PDF files allowed.'},
                                status=status.HTTP_400_BAD_REQUEST)

            max_size_mb = 20
            if file.size > max_size_mb * 1024 * 1024:
                return Response({'status': 'error', 'message': f'Max size: {max_size_mb} MB.'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Auto-extract title from filename
            title = file.name.replace('.pdf', '').replace('_', ' ').title()
            difficulty = request.data.get('difficulty', 'intermediate')
            
            # Validate difficulty level
            valid_difficulties = ['beginner', 'intermediate', 'advanced', 'master']
            if difficulty not in valid_difficulties:
                return Response({
                    'status': 'error', 
                    'message': f'Invalid difficulty. Must be one of: {", ".join(valid_difficulties)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate PDF
            file_content = file.read()
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
                total_pages = len(pdf_reader.pages)
                file.seek(0)
                if total_pages == 0:
                    return Response({'status': 'error', 'message': 'PDF contains no pages.'},
                                    status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({'status': 'error', 'message': f'PDF read error: {str(e)}'},
                                status=status.HTTP_400_BAD_REQUEST)

            if UploadedDocument.objects.filter(title=title).exists():
                existing_doc = UploadedDocument.objects.get(title=title)
                return Response({
                    'status': 'error',
                    'message': f'Document "{title}" already exists.',
                    'existing_document': {
                        'id': existing_doc.id,
                        'title': existing_doc.title,
                        'difficulty': existing_doc.difficulty,
                        'uploaded_at': existing_doc.uploaded_at.isoformat()
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

            # Create document with difficulty
            document = UploadedDocument.objects.create(
                title=title,
                file=file,
                total_pages=total_pages,
                processing_status='PROCESSING',
                difficulty=difficulty
            )

            print(f"\n{'='*80}")
            print(f"UPLOAD & PROCESS PIPELINE - {document.title}")
            print(f"Difficulty: {difficulty} | Embeddings: Always enabled")
            print(f"{'='*80}")

            pipeline_results = {
                'document_id': document.id,
                'document_title': document.title,
                'total_pages': document.total_pages,
                'difficulty': document.difficulty,
                'pipeline_steps': {}
            }

            # Step 2: TOC Generation
            print("\n🔍 STEP 2: TOC GENERATION")
            try:
                from content_ingestion.helpers.toc_parser.toc_apply import generate_toc_entries_for_document
                toc_entries = generate_toc_entries_for_document(document)
                toc_count = len(toc_entries) if toc_entries else 0
                pipeline_results['pipeline_steps']['toc_generation'] = {
                    'status': 'success',
                    'entries_created': toc_count,
                    'toc_source': 'metadata' if toc_count > 0 else 'fallback'
                }
                print(f"✅ TOC generated ({toc_count} entries)")
            except Exception as e:
                pipeline_results['pipeline_steps']['toc_generation'] = {'status': 'error', 'error': str(e)}
                print(f"❌ TOC generation failed: {e}")

            # Step 3: Document chunking
            print("\n📄 STEP 3: DOCUMENT CHUNKING")
            try:
                from content_ingestion.helpers.page_chunking.toc_chunk_processor import GranularChunkProcessor
                processor = GranularChunkProcessor(enable_embeddings=False)
                chunk_results = processor.process_entire_document(document)
                chunk_count = chunk_results['total_chunks_created']
                pipeline_results['pipeline_steps']['chunking'] = {
                    'status': 'success',
                    'chunks_created': chunk_count,
                    'pages_processed': chunk_results['total_pages_processed'],
                    'chunk_types': list(chunk_results['chunk_types_distribution'].keys())
                }
                print(f"✅ Document chunked ({chunk_count} chunks)")
            except Exception as e:
                pipeline_results['pipeline_steps']['chunking'] = {'status': 'error', 'error': str(e)}
                print(f"❌ Chunking failed: {e}")

            # Step 4: Embedding generation (automatic)
            print("\n🔗 STEP 4: EMBEDDING GENERATION")
            try:
                from content_ingestion.helpers.embedding import EmbeddingGenerator
                from content_ingestion.models import Embedding
                
                embedding_generator = EmbeddingGenerator()
                
                # Find chunks without embeddings (check via Embedding model)
                chunks_with_embeddings = Embedding.objects.filter(
                    document_chunk__document=document
                ).values_list('document_chunk_id', flat=True)
                
                chunks = DocumentChunk.objects.filter(document=document).exclude(
                    id__in=chunks_with_embeddings
                )
                
                embedded_count = 0
                for chunk in chunks:
                    try:
                        embedding_vector = embedding_generator.generate_embedding(chunk.text)
                        
                        # Save to Embedding model only
                        Embedding.objects.create(
                            document_chunk=chunk,
                            vector=embedding_vector,
                            model_name=embedding_generator.model_name
                        )
                        
                        embedded_count += 1
                    except Exception as e:
                        print(f"⚠️ Failed to embed chunk {chunk.id}: {e}")
                
                pipeline_results['pipeline_steps']['embedding'] = {
                    'status': 'success',
                    'chunks_embedded': embedded_count,
                    'total_chunks': chunks.count()
                }
                print(f"✅ Embeddings generated ({embedded_count} chunks)")
            except Exception as e:
                pipeline_results['pipeline_steps']['embedding'] = {'status': 'error', 'error': str(e)}
                print(f"❌ Embedding generation failed: {e}")

            # Update document status
            document.processing_status = 'COMPLETED'
            document.parsed = True
            document.save(update_fields=['processing_status', 'parsed'])

            print(f"\n✅ PIPELINE COMPLETED for {document.title}")

            return Response({
                'status': 'success',
                'message': f'Document "{document.title}" uploaded and processed successfully',
                'document': {
                    'id': document.id,
                    'title': document.title,
                    'difficulty': document.difficulty,
                    'total_pages': document.total_pages,
                    'processing_status': document.processing_status,
                    'uploaded_at': document.uploaded_at.isoformat(),
                    'file_url': document.file.url if document.file else None
                },
                'pipeline_results': pipeline_results,
                'next_steps': {
                    'view_chunks': f'/api/content_ingestion/chunks/{document.id}/',
                    'view_toc': f'/api/content_ingestion/toc/document/{document.id}/',
                    'generate_questions': f'/api/question_generation/generate/',
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Upload and process pipeline failed: {str(e)}")
            return Response({'status': 'error', 'message': f'Pipeline failed: {str(e)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
                from content_ingestion.helpers.toc_parser.toc_apply import generate_toc_entries_for_document
                toc_entries = generate_toc_entries_for_document(document)
                toc_count = len(toc_entries) if toc_entries else 0
                pipeline_results['pipeline_steps']['toc_generation'] = {
                    'status': 'success',
                    'entries_created': toc_count,
                    'toc_source': 'metadata' if toc_count > 0 else 'fallback'
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
                    from content_ingestion.helpers.embedding import EmbeddingGenerator
                    embedding_generator = EmbeddingGenerator()
                    chunks = DocumentChunk.objects.filter(document=document)
                    to_embed = chunks.filter(embeddings__isnull=True)
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
            chunks_data = []
            for chunk in chunks:
                # Check if chunk has embedding via Embedding model
                try:
                    from content_ingestion.models import Embedding
                    embedding_obj = Embedding.objects.get(document_chunk=chunk)
                    has_embedding = True
                    embedding_vector = embedding_obj.vector
                    embedding_dimensions = len(embedding_obj.vector)
                except Embedding.DoesNotExist:
                    has_embedding = False
                    embedding_vector = None
                    embedding_dimensions = 0
                
                chunks_data.append({
                    'id': chunk.id,
                    'text': chunk.text[:200] + '...' if len(chunk.text) > 200 else chunk.text,
                    'chunk_type': chunk.chunk_type,
                    'page_number': chunk.page_number,
                    'order_in_doc': chunk.order_in_doc,
                    'token_count': chunk.token_count,
                    'topic_title': chunk.subtopic_title,
                    'has_embedding': has_embedding,
                    'embedding_vector': embedding_vector,
                    'embedding_dimensions': embedding_dimensions
                })

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
        # No need to exclude types since chunker only detects the 5 valid types
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
            book_title = chunk.parser_metadata.get('book_title', '')
            chunks_data.append({
                'id': chunk.id,
                'text': chunk.text,
                'chunk_type': chunk.chunk_type,
                'topic_title': chunk.subtopic_title,
                'book_title': book_title,
                'difficulty': '',
                'page_number': chunk.page_number,
                'order_in_doc': chunk.order_in_doc,
                'token_count': tokens,
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
        
        # Check if chunk has embedding via Embedding model
        try:
            from content_ingestion.models import Embedding
            embedding_obj = Embedding.objects.get(document_chunk=chunk)
            has_embedding = True
            embedding_model = embedding_obj.model_name
            embedded_at = embedding_obj.embedded_at
        except Embedding.DoesNotExist:
            has_embedding = False
            embedding_model = None
            embedded_at = None
        
        chunk_data = {
            'id': chunk.id,
            'document_id': chunk.document.id,
            'document_title': chunk.document.title,
            'chunk_type': chunk.chunk_type,
            'text': chunk.text,
            'page_number': chunk.page_number,
            'order_in_doc': chunk.order_in_doc,
            'topic_title': chunk.subtopic_title,
            'token_count': chunk.token_count,
                        'confidence_score': chunk.confidence_score,
            'parser_metadata': chunk.parser_metadata,
            'has_embedding': has_embedding,
            'embedding_model': embedding_model,
            'embedded_at': embedded_at.isoformat() if embedded_at else None
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
        valid_types = ['Concept', 'Exercise', 'Example', 'Try_It', 'Code']
        if chunk_type not in valid_types:
            return Response({
                'status': 'error',
                'message': f'Invalid chunk type. Valid types: {", ".join(valid_types)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        chunks = DocumentChunk.objects.filter(document=document, chunk_type=chunk_type).order_by('page_number', 'order_in_doc')
        
        chunks_data = []
        for chunk in chunks:
            # Check if chunk has embedding via Embedding model
            try:
                from content_ingestion.models import Embedding
                embedding_obj = Embedding.objects.get(document_chunk=chunk)
                has_embedding = True
            except Embedding.DoesNotExist:
                has_embedding = False
                
            chunks_data.append({
                'id': chunk.id,
                'text': chunk.text,
                'chunk_type': chunk.chunk_type,
                'page_number': chunk.page_number,
                'order_in_doc': chunk.order_in_doc,
                'topic_title': chunk.subtopic_title,
                'has_embedding': has_embedding,
                'text_length': len(chunk.text)
            })
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
                'topic_title': chunk.subtopic_title,
                'has_embedding': bool(chunk.embeddings.first()),
                'text_length': len(chunk.text),
                'token_count': getattr(chunk, 'token_count', 0)
            }
            if semantic_context:
                try:
                    from content_ingestion.helpers.utils.stubs import create_coding_context_for_embedding, extract_programming_concepts
                    chunk_data['enhanced_context'] = create_coding_context_for_embedding(
                        chunk.text, chunk.chunk_type, chunk.subtopic_title or ""
                    )
                    chunk_data['programming_concepts'] = extract_programming_concepts(chunk.text)
                    chunk_data['semantic_ready'] = True
                    chunk_data['context_type'] = 'enhanced_with_domain_detection'
                except ImportError:
                    chunk_data['semantic_ready'] = False
                    chunk_data['enhanced_context'] = f"{chunk.chunk_type}: {chunk.text}"
            if include_context and chunk.subtopic_title:
                ctx = []
                if chunk.subtopic_title: ctx.append(f"Topic: {chunk.subtopic_title}")
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


class CompleteSemanticPipelineView(APIView):
    """
    Complete end-to-end pipeline from upload to semantic similarity analysis:
    1. Upload PDF with automatic title extraction
    2. Generate TOC  
    3. Chunk document with fine-grained processing
    4. Generate embeddings for all chunks
    5. Generate subtopic embeddings
    6. Compute semantic similarity between subtopics and chunks
    7. Return comprehensive processing summary
    
    Required fields:
    - file: PDF file
    - difficulty: 'beginner' | 'intermediate' | 'advanced' | 'master'
    """
    def post(self, request):
        try:
            # Step 1: Handle PDF upload with validation
            file = request.FILES.get('file')
            if not file:
                return Response({'status': 'error', 'message': 'No file provided.'},
                                status=status.HTTP_400_BAD_REQUEST)

            if not file.name.lower().endswith('.pdf'):
                return Response({'status': 'error', 'message': 'Only PDF files allowed.'},
                                status=status.HTTP_400_BAD_REQUEST)

            max_size_mb = 20
            if file.size > max_size_mb * 1024 * 1024:
                return Response({'status': 'error', 'message': f'Max size: {max_size_mb} MB.'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Auto-extract title from filename
            title = file.name.replace('.pdf', '').replace('_', ' ').title()
            difficulty = request.data.get('difficulty', 'intermediate')
            
            # Validate difficulty level
            valid_difficulties = ['beginner', 'intermediate', 'advanced', 'master']
            if difficulty not in valid_difficulties:
                return Response({
                    'status': 'error', 
                    'message': f'Invalid difficulty. Must be one of: {", ".join(valid_difficulties)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate PDF
            file_content = file.read()
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
                total_pages = len(pdf_reader.pages)
                file.seek(0)
                if total_pages == 0:
                    return Response({'status': 'error', 'message': 'PDF contains no pages.'},
                                    status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({'status': 'error', 'message': f'PDF read error: {str(e)}'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Check for existing document
            if UploadedDocument.objects.filter(title=title).exists():
                existing_doc = UploadedDocument.objects.get(title=title)
                return Response({
                    'status': 'error',
                    'message': f'Document "{title}" already exists.',
                    'existing_document': {
                        'id': existing_doc.id,
                        'title': existing_doc.title,
                        'difficulty': existing_doc.difficulty,
                        'uploaded_at': existing_doc.uploaded_at.isoformat()
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

            # Create document
            document = UploadedDocument.objects.create(
                title=title,
                file=file,
                total_pages=total_pages,
                processing_status='PROCESSING',
                difficulty=difficulty
            )

            print(f"\n{'='*80}")
            print(f"COMPLETE SEMANTIC PIPELINE - {document.title}")
            print(f"Difficulty: {difficulty} | Full semantic analysis enabled")
            print(f"{'='*80}")

            pipeline_results = {
                'document_id': document.id,
                'document_title': document.title,
                'total_pages': document.total_pages,
                'difficulty': document.difficulty,
                'pipeline_steps': {}
            }

            # Step 2: TOC Generation
            print("\n🔍 STEP 2: TOC GENERATION")
            try:
                from content_ingestion.helpers.toc_parser.toc_apply import generate_toc_entries_for_document
                toc_entries = generate_toc_entries_for_document(document)
                toc_count = len(toc_entries) if toc_entries else 0
                pipeline_results['pipeline_steps']['toc_generation'] = {
                    'status': 'success',
                    'entries_created': toc_count,
                    'toc_source': 'metadata' if toc_count > 0 else 'fallback'
                }
                print(f"✅ TOC generated ({toc_count} entries)")
            except Exception as e:
                pipeline_results['pipeline_steps']['toc_generation'] = {'status': 'error', 'error': str(e)}
                print(f"❌ TOC generation failed: {e}")

            # Step 3: Document chunking with embeddings and semantic analysis
            print("\n📄 STEP 3: COMPLETE DOCUMENT PROCESSING")
            try:
                from content_ingestion.helpers.page_chunking.toc_chunk_processor import GranularChunkProcessor
                
                # Enable embeddings in the processor - this triggers semantic analysis automatically
                processor = GranularChunkProcessor(enable_embeddings=True)
                chunk_results = processor.process_entire_document(document)
                
                chunk_count = chunk_results['total_chunks_created']
                pipeline_results['pipeline_steps']['chunking_and_embeddings'] = {
                    'status': 'success',
                    'chunks_created': chunk_count,
                    'pages_processed': chunk_results['total_pages_processed'],
                    'chunk_types': list(chunk_results['chunk_types_distribution'].keys()),
                    'embeddings_generated': chunk_results.get('embeddings_generated', 0),
                    'semantic_analysis': chunk_results.get('semantic_analysis', {})
                }
                print(f"✅ Document processing complete ({chunk_count} chunks with embeddings)")
                
                # Display semantic analysis results if available
                if 'semantic_analysis' in chunk_results:
                    semantic_info = chunk_results['semantic_analysis']
                    print(f"🧠 Semantic analysis: {semantic_info.get('subtopics_analyzed', 0)} subtopics analyzed")
                    
            except Exception as e:
                pipeline_results['pipeline_steps']['chunking_and_embeddings'] = {'status': 'error', 'error': str(e)}
                print(f"❌ Document processing failed: {e}")

            # Step 4: Ensure subtopic embeddings exist (prerequisite for semantic analysis)
            print("\n🎯 STEP 4: SUBTOPIC EMBEDDINGS")
            try:
                from content_ingestion.views.embeddingViews import generate_subtopic_embeddings
                from content_ingestion.models import Subtopic
                
                # Count subtopics without embeddings
                subtopics_without_embeddings = Subtopic.objects.filter(embeddings__isnull=True).count()
                total_subtopics = Subtopic.objects.count()
                
                if subtopics_without_embeddings > 0:
                    # Generate missing subtopic embeddings
                    embedding_result = generate_subtopic_embeddings(request)
                    if hasattr(embedding_result, 'data') and embedding_result.data.get('status') == 'success':
                        pipeline_results['pipeline_steps']['subtopic_embeddings'] = {
                            'status': 'success',
                            'embeddings_generated': embedding_result.data.get('generated_count', 0),
                            'total_subtopics': total_subtopics
                        }
                        print(f"✅ Subtopic embeddings generated ({embedding_result.data.get('generated_count', 0)} new)")
                    else:
                        pipeline_results['pipeline_steps']['subtopic_embeddings'] = {
                            'status': 'error', 
                            'error': 'Failed to generate subtopic embeddings'
                        }
                        print("❌ Failed to generate subtopic embeddings")
                else:
                    pipeline_results['pipeline_steps']['subtopic_embeddings'] = {
                        'status': 'success',
                        'embeddings_generated': 0,
                        'total_subtopics': total_subtopics,
                        'message': 'All subtopics already have embeddings'
                    }
                    print(f"✅ Subtopic embeddings already exist ({total_subtopics} subtopics)")
                    
            except Exception as e:
                pipeline_results['pipeline_steps']['subtopic_embeddings'] = {'status': 'error', 'error': str(e)}
                print(f"❌ Subtopic embedding check failed: {e}")

            # Step 5: Semantic Analysis - Compare chunks with subtopics
            print("\n🔍 STEP 5: SEMANTIC ANALYSIS")
            try:
                from question_generation.helpers.semantic_analyzer import SemanticAnalyzer
                
                analyzer = SemanticAnalyzer()
                semantic_result = analyzer.populate_semantic_subtopics(reanalyze=True)
                
                pipeline_results['pipeline_steps']['semantic_analysis'] = {
                    'status': 'success',
                    'subtopics_analyzed': semantic_result.get('processed', 0),
                    'subtopics_created': semantic_result.get('created', 0),
                    'subtopics_updated': semantic_result.get('updated', 0)
                }
                print(f"✅ Semantic analysis complete ({semantic_result.get('processed', 0)} subtopics analyzed)")
                
            except Exception as e:
                pipeline_results['pipeline_steps']['semantic_analysis'] = {'status': 'error', 'error': str(e)}
                print(f"❌ Semantic analysis failed: {e}")

            # Update document status
            document.processing_status = 'COMPLETED'
            document.parsed = True
            document.save(update_fields=['processing_status', 'parsed'])

            print(f"\n✅ COMPLETE SEMANTIC PIPELINE FINISHED for {document.title}")

            return Response({
                'status': 'success',
                'message': f'Document "{document.title}" processed with complete semantic analysis',
                'document': {
                    'id': document.id,
                    'title': document.title,
                    'difficulty': document.difficulty,
                    'total_pages': document.total_pages,
                    'processing_status': document.processing_status,
                    'uploaded_at': document.uploaded_at.isoformat(),
                    'file_url': document.file.url if document.file else None
                },
                'pipeline_results': pipeline_results,
                'next_steps': {
                    'view_chunks': f'/api/content_ingestion/chunks/{document.id}/',
                    'view_toc': f'/api/content_ingestion/toc/{document.id}/view/',
                    'generate_questions': f'/api/question_generation/generate/',
                    'test_questions': f'/api/question_generation/test/',
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Complete semantic pipeline failed: {str(e)}")
            return Response({'status': 'error', 'message': f'Pipeline failed: {str(e)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
