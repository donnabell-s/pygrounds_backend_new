from django.test import TestCase
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import PyPDF2
import io
import tempfile
import os


class PDFTestAnalysisView(APIView):
    """
    Test view for analyzing PDF structure, TOC parsing, and embedding generation
    WITHOUT saving anything to the database. Useful for testing new PDF formats.
    """

    def post(self, request):
        """Analyze PDF structure and TOC without saving to database."""
        try:
            file = request.FILES.get('file')
            if not file:
                return Response({'status': 'error', 'message': 'No file provided.'},
                                status=status.HTTP_400_BAD_REQUEST)

            if not file.name.lower().endswith('.pdf'):
                return Response({'status': 'error', 'message': 'Only PDF files allowed.'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Basic PDF validation
            file_content = file.read()
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            total_pages = len(pdf_reader.pages)
            
            if total_pages == 0:
                return Response({'status': 'error', 'message': 'PDF contains no pages.'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Create temporary document object (not saved to DB)
            from content_ingestion.models import UploadedDocument
            difficulty = request.data.get('difficulty', 'intermediate')
            temp_doc = UploadedDocument(
                title=request.data.get('title', file.name.replace('.pdf', '')),
                total_pages=total_pages,
                difficulty=difficulty
            )
            
            # Save file temporarily for processing
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            try:
                # Step 1: TOC Analysis
                from content_ingestion.helpers.toc_parser.toc_utils import extract_toc_with_unstructured
                print("\n ANALYZING TOC STRUCTURE")
                
                toc_entries = extract_toc_with_unstructured(temp_file_path)
                toc_analysis = {
                    'entries_found': len(toc_entries),
                    'max_level': max([entry.get('level', 1) for entry in toc_entries]) if toc_entries else 0,
                    'entries': toc_entries[:10]  # First 10 for preview
                }
                
                # Step 2: Content Structure Analysis  
                print("\n ANALYZING CONTENT STRUCTURE")
                from content_ingestion.helpers.page_chunking.chunk_extractor_utils import process_with_unstructured
                
                try:
                    elements = process_with_unstructured(temp_file_path, temp_doc)
                    structure_analysis = {
                        'total_elements': len(elements),
                        'element_types': {},
                        'sample_elements': []
                    }
                    
                    # Analyze element types
                    for element in elements:
                        element_type = type(element).__name__
                        structure_analysis['element_types'][element_type] = structure_analysis['element_types'].get(element_type, 0) + 1
                    
                    # Sample elements (first 5)
                    for element in elements[:5]:
                        structure_analysis['sample_elements'].append({
                            'type': type(element).__name__,
                            'text_preview': str(element)[:200] + "..." if len(str(element)) > 200 else str(element),
                            'metadata': getattr(element, 'metadata', {})
                        })
                    
                except Exception as e:
                    structure_analysis = {'error': str(e)}

                # Step 3: Test Embeddings (without saving)
                print("\n TESTING EMBEDDING GENERATION")
                try:
                    from content_ingestion.helpers.embedding import EmbeddingGenerator
                    embedding_generator = EmbeddingGenerator()
                    
                    # Test with sample text
                    sample_text = "def hello_world():\n    print('Hello, World!')\n    return True"
                    embedding_result = embedding_generator.generate_embedding(sample_text, 'Code')
                    
                    embedding_analysis = {
                        'model_used': embedding_result.get('model_name'),
                        'dimension': embedding_result.get('dimension'),
                        'success': embedding_result.get('vector') is not None,
                        'error': embedding_result.get('error')
                    }
                except Exception as e:
                    embedding_analysis = {'error': str(e)}
                
                return Response({
                    'status': 'success',
                    'document_info': {
                        'title': temp_doc.title,
                        'total_pages': total_pages,
                        'difficulty': difficulty
                    },
                    'toc_analysis': toc_analysis,
                    'structure_analysis': structure_analysis,
                    'embedding_analysis': embedding_analysis
                })
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        except Exception as e:
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PDFTestChunkingView(APIView):
    """
    Test view for analyzing PDF chunking quality and reviewing actual chunks
    WITHOUT saving anything to the database. Returns actual chunk content for quality inspection.
    """

    def post(self, request):
        """Analyze PDF chunking and return actual chunks for quality review."""
        try:
            file = request.FILES.get('file')
            if not file:
                return Response({'status': 'error', 'message': 'No file provided.'},
                                status=status.HTTP_400_BAD_REQUEST)

            if not file.name.lower().endswith('.pdf'):
                return Response({'status': 'error', 'message': 'Only PDF files allowed.'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Basic PDF validation
            file_content = file.read()
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            total_pages = len(pdf_reader.pages)
            
            if total_pages == 0:
                return Response({'status': 'error', 'message': 'PDF contains no pages.'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Create temporary document object (not saved to DB)
            from content_ingestion.models import UploadedDocument
            difficulty = request.data.get('difficulty', 'intermediate')
            temp_doc = UploadedDocument(
                title=request.data.get('title', file.name.replace('.pdf', '')),
                total_pages=total_pages,
                difficulty=difficulty
            )
            
            # Save file temporarily for processing
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            try:
                # Process the PDF to generate chunks (without saving to DB)
                print("\n ANALYZING PDF CHUNKING QUALITY")
                
                from content_ingestion.helpers.page_chunking.chunk_extractor_utils import process_with_unstructured
                from content_ingestion.helpers.page_chunking.toc_chunk_processor import GranularChunkProcessor
                
                # Step 1: Extract raw elements
                elements = process_with_unstructured(temp_file_path, temp_doc)
                
                # Step 2: Process into chunks
                processor = GranularChunkProcessor(enable_embeddings=False)
                chunks_data = processor.process_elements_to_chunks(elements, temp_doc)
                
                # Step 3: Analyze chunk quality
                chunk_analysis = {
                    'total_chunks': len(chunks_data),
                    'chunk_types': {},
                    'chunks_by_page': {},
                    'token_distribution': {
                        'min': float('inf'),
                        'max': 0,
                        'avg': 0
                    },
                    'sample_chunks': []
                }
                
                total_tokens = 0
                
                for chunk_data in chunks_data:
                    # Chunk type analysis
                    chunk_type = chunk_data.get('chunk_type', 'Unknown')
                    chunk_analysis['chunk_types'][chunk_type] = chunk_analysis['chunk_types'].get(chunk_type, 0) + 1
                    
                    # Page distribution
                    page = chunk_data.get('page_number', 'Unknown')
                    chunk_analysis['chunks_by_page'][str(page)] = chunk_analysis['chunks_by_page'].get(str(page), 0) + 1
                    
                    # Token analysis
                    token_count = chunk_data.get('token_count', 0)
                    if token_count > 0:
                        chunk_analysis['token_distribution']['min'] = min(chunk_analysis['token_distribution']['min'], token_count)
                        chunk_analysis['token_distribution']['max'] = max(chunk_analysis['token_distribution']['max'], token_count)
                        total_tokens += token_count
                
                # Calculate average tokens
                if len(chunks_data) > 0:
                    chunk_analysis['token_distribution']['avg'] = total_tokens / len(chunks_data)
                    
                    # Handle case where no tokens were found
                    if chunk_analysis['token_distribution']['min'] == float('inf'):
                        chunk_analysis['token_distribution']['min'] = 0
                
                # Sample chunks for review (first 5)
                for chunk_data in chunks_data[:5]:
                    chunk_analysis['sample_chunks'].append({
                        'chunk_type': chunk_data.get('chunk_type'),
                        'page_number': chunk_data.get('page_number'),
                        'token_count': chunk_data.get('token_count'),
                        'subtopic_title': chunk_data.get('subtopic_title'),
                        'text_preview': chunk_data.get('text', '')[:300] + "..." if len(chunk_data.get('text', '')) > 300 else chunk_data.get('text', ''),
                        'confidence_score': chunk_data.get('confidence_score'),
                        'metadata': chunk_data.get('parser_metadata', {})
                    })
                
                return Response({
                    'status': 'success',
                    'document_info': {
                        'title': temp_doc.title,
                        'total_pages': total_pages,
                        'difficulty': difficulty
                    },
                    'chunking_analysis': chunk_analysis,
                    'note': 'This is a test analysis - no data was saved to the database.'
                })
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        except Exception as e:
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Create your tests here.
