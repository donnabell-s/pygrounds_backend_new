from ..helpers.view_imports import *
from ..helpers.helper_imports import *
from content_ingestion.models import CHUNK_TYPE_CHOICES

@api_view(['POST'])
def process_document_pipeline(request, document_id):
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        if document.processing_status == 'PROCESSING':
            return Response({
                'status': 'error',
                'message': 'Document is already being processed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        document.processing_status = 'PROCESSING'
        document.save()
        
        pipeline_results = {
            'document_id': document_id,
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
            chunk_result = processor.process_entire_document(document)
            pipeline_results['pipeline_steps']['chunking'] = {
                'status': 'success',
                'chunks_created': len(chunk_result.get('chunks_created', []))
            }
        except Exception as e:
            pipeline_results['pipeline_steps']['chunking'] = {'status': 'error', 'error': str(e)}
        
        try:
            embedding_gen = EmbeddingGenerator()
            chunks = DocumentChunk.objects.filter(document=document)
            embedding_result = embedding_gen.generate_batch_embeddings(chunks)
            pipeline_results['pipeline_steps']['embedding'] = {
                'status': 'success',
                'embeddings_created': len(embedding_result.get('embeddings', []))
            }
        except Exception as e:
            pipeline_results['pipeline_steps']['embedding'] = {'status': 'error', 'error': str(e)}
        
        document.processing_status = 'COMPLETED'
        document.save()
        
        return Response({
            'status': 'success',
            'message': f'Document "{document.title}" processed successfully',
            'results': pipeline_results
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        if 'document' in locals():
            document.processing_status = 'FAILED'
            document.save()
        
        logger.error(f"Pipeline error for document {document_id}: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Processing failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
                'subtopic_title': chunk.subtopic_title,
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
        embedding_result = embedding_gen.generate_batch_embeddings(chunks)
        
        return Response({
            'status': 'success',
            'message': f'Embeddings generated successfully',
            'document': {
                'id': document.id,
                'title': document.title,
                'chunk_count': chunk_count
            },
            'embeddings_created': len(embedding_result.get('embeddings', []))
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
            'subtopic_title': chunk.subtopic_title,
            'token_count': chunk.token_count,
            'parser_metadata': chunk.parser_metadata,
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
                'subtopic_title': chunk.subtopic_title,
                'token_count': chunk.token_count,
                'parser_metadata': chunk.parser_metadata
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
                'subtopic_title': chunk.subtopic_title,
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
                'subtopic_title': chunk.subtopic_title,
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
            'subtopic_title': chunk.subtopic_title,
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
