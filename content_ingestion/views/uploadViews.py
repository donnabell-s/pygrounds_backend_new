"""
PDF upload and document management API.
"""

from .imports import *
from django.db.models import Count
import PyPDF2
import io
import re

class PDFUploadView(APIView):
    """
    POST: Upload PDF and create UploadedDocument.
    GET: List documents (with filters).
    """

    def post(self, request):
        """Upload a PDF and create UploadedDocument."""
        try:
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

            title = request.data.get('title') or file.name.replace('.pdf', '').replace('_', ' ').title()
            difficulty = request.data.get('difficulty', 'intermediate')
            
            # Validate difficulty level
            valid_difficulties = ['beginner', 'intermediate', 'advanced', 'master']
            if difficulty not in valid_difficulties:
                return Response({
                    'status': 'error', 
                    'message': f'Invalid difficulty. Must be one of: {", ".join(valid_difficulties)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
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
                    'message': f'Document "{title}" exists.',
                    'existing_document': {
                        'id': existing_doc.id,
                        'title': existing_doc.title,
                        'uploaded_at': existing_doc.uploaded_at.isoformat()
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

            doc = UploadedDocument.objects.create(
                title=title,
                file=file,
                total_pages=total_pages,
                processing_status='PENDING',
                difficulty=difficulty
            )

            return Response({
                'status': 'success',
                'message': 'PDF uploaded.',
                'document': {
                    'id': doc.id,
                    'title': doc.title,
                    'filename': file.name,
                    'total_pages': total_pages,
                    'file_size_bytes': file.size,
                    'processing_status': doc.processing_status,
                    'difficulty': doc.difficulty,
                    'uploaded_at': doc.uploaded_at.isoformat(),
                    'file_url': doc.file.url if doc.file else None
                },
                'next_steps': {
                    'toc_generation': f'/api/content_ingestion/toc/generate/{doc.id}/',
                    'granular_processing': f'/api/content_ingestion/process/granular/{doc.id}/',
                    'chunk_retrieval': f'/api/content_ingestion/chunks/{doc.id}/'
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"PDF upload failed: {str(e)}")
            return Response({'status': 'error', 'message': f'Upload failed: {str(e)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        """
        List uploaded documents.
        Query: status, limit, search.
        """
        try:
            status_filter = request.query_params.get('status')
            limit = int(request.query_params.get('limit', 20))
            search = request.query_params.get('search')

            query = UploadedDocument.objects.all()
            if status_filter:
                query = query.filter(processing_status=status_filter)
            if search:
                query = query.filter(title__icontains=search)

            docs = query.order_by('-uploaded_at')[:limit]
            docs_data = []
            for doc in docs:
                chunk_count = DocumentChunk.objects.filter(document=doc).count()
                docs_data.append({
                    'id': doc.id,
                    'title': doc.title,
                    'filename': doc.file.name.split('/')[-1] if doc.file else None,
                    'total_pages': doc.total_pages,
                    'processing_status': doc.processing_status,
                    'difficulty': doc.difficulty,
                    'parsed': doc.parsed,
                    'chunks_created': chunk_count,
                    'uploaded_at': doc.uploaded_at.isoformat(),
                    'file_url': doc.file.url if doc.file else None,
                    'file_size_mb': round(doc.file.size / (1024 * 1024), 2) if doc.file else 0
                })

            status_counts = {
                st.lower(): query.filter(processing_status=st).count()
                for st in ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']
            }

            return Response({
                'status': 'success',
                'summary': {
                    'total_documents': query.count(),
                    'showing_count': len(docs),
                    'status_distribution': status_counts
                },
                'filters_applied': {
                    'status': status_filter,
                    'search': search,
                    'limit': limit
                },
                'documents': docs_data
            })

        except Exception as e:
            logger.error(f"Failed to list documents: {str(e)}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DocumentDetailView(APIView):
    """
    GET: Document detail.
    DELETE: Remove document and related data.
    """

    def get(self, request, document_id):
        """Get info for one document."""
        try:
            doc = get_object_or_404(UploadedDocument, id=document_id)
            chunk_count = DocumentChunk.objects.filter(document=doc).count()
            toc_count = TOCEntry.objects.filter(document=doc).count()
            chunk_types = DocumentChunk.objects.filter(document=doc).values('chunk_type').annotate(
                count=Count('chunk_type')).order_by('chunk_type')
            chunk_dist = {c['chunk_type']: c['count'] for c in chunk_types}

            return Response({
                'status': 'success',
                'document': {
                    'id': doc.id,
                    'title': doc.title,
                    'filename': doc.file.name.split('/')[-1] if doc.file else None,
                    'total_pages': doc.total_pages,
                    'processing_status': doc.processing_status,
                    'difficulty': doc.difficulty,
                    'parsed': doc.parsed,
                    'uploaded_at': doc.uploaded_at.isoformat(),
                    'file_url': doc.file.url if doc.file else None,
                    'file_size_mb': round(doc.file.size / (1024 * 1024), 2) if doc.file else 0
                },
                'processing_info': {
                    'chunks_created': chunk_count,
                    'toc_entries_created': toc_count,
                    'chunk_type_distribution': chunk_dist,
                },
                'available_actions': {
                    'generate_toc': f'/api/content_ingestion/toc/generate/{doc.id}/',
                    'process_granular': f'/api/content_ingestion/process/granular/{doc.id}/',
                    'get_chunks': f'/api/content_ingestion/chunks/{doc.id}/',
                    'embed_chunks': f'/api/content_ingestion/chunks/{doc.id}/embed/'
                }
            })
        except Exception as e:
            logger.error(f"Failed to get document details for {document_id}: {str(e)}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, document_id):
        """Delete document and all its data."""
        try:
            doc = get_object_or_404(UploadedDocument, id=document_id)
            chunk_count = DocumentChunk.objects.filter(document=doc).count()
            toc_count = TOCEntry.objects.filter(document=doc).count()

            if doc.file:
                try:
                    doc.file.delete(save=False)
                except Exception as e:
                    logger.warning(f"Could not delete file from storage: {e}")

            doc.delete()

            return Response({
                'status': 'success',
                'message': f'Document "{doc.title}" deleted.',
                'deleted_data': {
                    'document_id': document_id,
                    'chunks_deleted': chunk_count,
                    'toc_entries_deleted': toc_count
                }
            })
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {str(e)}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            try:
                # Test TOC parsing (without saving to DB)
                import fitz
                from content_ingestion.helpers.toc_parser.toc_utils import extract_toc, fallback_toc_text, parse_toc_text, assign_end_pages
                
                # Open PDF with PyMuPDF for TOC analysis - with error handling for color issues
                try:
                    doc = fitz.open(temp_file_path)
                    total_pages = len(doc)
                except Exception as pdf_error:
                    if "gray non-stroke color" in str(pdf_error) or "invalid float value" in str(pdf_error):
                        print(f"⚠️ PDF color space issue detected: {pdf_error}")
                        # Try to continue with basic analysis
                        doc = fitz.open(temp_file_path)
                        total_pages = len(doc)
                    else:
                        raise pdf_error
                
                # Try metadata-based TOC extraction first
                try:
                    toc_data = extract_toc(temp_file_path)
                    toc_source = "metadata"
                except Exception as toc_error:
                    print(f"⚠️ TOC extraction error: {toc_error}")
                    toc_data = []
                    toc_source = "metadata_failed"
                
                if toc_data and isinstance(toc_data[0], list):
                    # Convert [level, title, page] to dicts
                    toc_data = [
                        {
                            'title': item[1],
                            'start_page': item[2] - 1,
                            'level': item[0],
                            'order': idx
                        }
                        for idx, item in enumerate(toc_data) if len(item) >= 3
                    ]
                else:
                    # Fallback: Manual TOC parsing from first pages
                    toc_source = "text_extraction"
                    try:
                        toc_pages = fallback_toc_text(doc)
                        combined_toc_text = "\n".join(toc_pages)
                        toc_data = parse_toc_text(combined_toc_text)
                    except Exception as fallback_error:
                        print(f"⚠️ Fallback TOC parsing error: {fallback_error}")
                        toc_data = []
                        toc_source = "text_extraction_failed"
                
                doc.close()
                
                # Assign end pages (this doesn't save to DB)
                if toc_data:
                    toc_data = assign_end_pages(toc_data, total_pages)
                
                # Format TOC analysis
                toc_analysis = {
                    'total_entries': len(toc_data),
                    'source': toc_source,
                    'levels': {},
                    'entries': []
                }
                
                for entry in toc_data[:20]:  # Limit to first 20 for response size
                    level = entry.get('level', 0)
                    if level not in toc_analysis['levels']:
                        toc_analysis['levels'][level] = 0
                    toc_analysis['levels'][level] += 1
                    
                    toc_analysis['entries'].append({
                        'title': entry.get('title', ''),
                        'level': level,
                        'start_page': entry.get('start_page', 0),
                        'end_page': entry.get('end_page', 0),
                        'order': entry.get('order', 0)
                    })

                # Test chunk extraction (follow granular process format)
                from content_ingestion.helpers.page_chunking.toc_chunk_processor import GranularChunkProcessor
                from content_ingestion.helpers.page_chunking.chunk_extractor_utils import clean_chunk_text, infer_chunk_type, extract_unstructured_chunks
                
                chunk_processor = GranularChunkProcessor()
                
                # Initialize results in granular process format
                results = {
                    'total_chunks_created': 0,
                    'total_pages_processed': 0,
                    'content_boundaries': None,
                    'chunk_types_distribution': {},
                    'chunks': []  # Add chunks array for analysis
                }
                
                # Find content boundaries (simplified for test)
                first_page = 0
                last_page = min(4, total_pages - 1)  # Process first 5 pages for test
                results['content_boundaries'] = (first_page + 1, last_page + 1)
                results['total_pages_processed'] = last_page - first_page + 1
                
                # Create temporary PDF for chunk extraction
                import tempfile
                try:
                    temp_pdf = fitz.open()
                    for page_num in range(first_page, last_page + 1):
                        if page_num < total_pages:
                            try:
                                temp_pdf.insert_pdf(fitz.open(temp_file_path), from_page=page_num, to_page=page_num)
                            except Exception as page_error:
                                print(f"⚠️ Error processing page {page_num + 1}: {page_error}")
                                continue
                except Exception as pdf_creation_error:
                    print(f"⚠️ Error creating temporary PDF: {pdf_creation_error}")
                    temp_pdf = fitz.open()  # Create empty PDF as fallback
                
                if len(temp_pdf) > 0:
                    # Create temporary file for chunk extraction
                    temp_fd, temp_chunk_path = tempfile.mkstemp(suffix='.pdf')
                    try:
                        os.close(temp_fd)
                        temp_pdf.save(temp_chunk_path)
                        
                        # Extract chunks using the same method as granular processor
                        try:
                            raw_chunks = extract_unstructured_chunks(temp_chunk_path)
                        except Exception as chunk_error:
                            print(f"⚠️ Unstructured chunk extraction failed: {chunk_error}")
                            # Enhanced fallback extraction with color space error handling
                            raw_chunks = []
                            for page_idx in range(len(temp_pdf)):
                                try:
                                    page = temp_pdf.load_page(page_idx)
                                    text = page.get_text()
                                    if text.strip() and len(text.strip()) > 50:
                                        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip() and len(p.strip()) > 30]
                                        for para in paragraphs:
                                            if len(para) >= 30:
                                                raw_chunks.append({
                                                    'content': para,
                                                    'chunk_type': infer_chunk_type(para),
                                                    'source': 'fallback_granular'
                                                })
                                except Exception as page_text_error:
                                    print(f"⚠️ Error extracting text from page {page_idx + 1}: {page_text_error}")
                                    # Skip this page and continue
                                    continue
                        
                        # Process chunks following granular format
                        valid_chunks = []
                        pages_per_chunk = max(1, (last_page - first_page + 1) / max(1, len(raw_chunks)))
                        
                        for chunk_idx, chunk in enumerate(raw_chunks):
                            # Map chunk to page
                            estimated_page = first_page + int(chunk_idx * pages_per_chunk)
                            chunk_page = min(estimated_page, last_page)
                            
                            # Get TOC titles for this page (simplified)
                            topic_title = ""
                            subtopic_title = ""
                            sub_subtopic_title = ""
                            sub_sub_subtopic_title = ""
                            for entry in toc_data:
                                if entry.get('start_page', 0) <= chunk_page + 1 <= entry.get('end_page', 999):
                                    if entry.get('level') == 1:
                                        topic_title = entry.get('title', '')
                                    elif entry.get('level') == 2:
                                        subtopic_title = entry.get('title', '')
                                    elif entry.get('level') == 3:
                                        sub_subtopic_title = entry.get('title', '')
                                    elif entry.get('level') >= 4:
                                        sub_sub_subtopic_title = entry.get('title', '')
                            
                            # Enhanced non-content filtering - be more strict
                            non_content_keywords = [
                                'contents', 'foreword', 'introduction', 'preface', 'acknowledgements', 
                                'table of contents', 'index', 'bibliography', 'references', 'glossary',
                                'appendix', 'about the author', 'about this book', 'dedication',
                                'copyright', 'isbn', 'overview', 'getting started', 'toc'
                            ]
                            
                            # Skip if topic title matches non-content keywords
                            if any(keyword in topic_title.lower() for keyword in non_content_keywords):
                                continue
                                
                            # Skip if this appears to be a TOC page (page 2 is often TOC)
                            if chunk_page + 1 <= 3 and any(keyword in topic_title.lower() for keyword in ['contents', 'table']):
                                continue
                                
                            # Skip pages that don't have substantial educational content
                            if len(chunk['content'].strip()) < 200:  # Too short to be meaningful content
                                continue
                            
                            # Clean chunk text
                            cleaned_text = clean_chunk_text(chunk['content'], subtopic_title, topic_title, sub_subtopic_title, sub_sub_subtopic_title)
                            
                            # Create enhanced chunk in granular format
                            enhanced_chunk = {
                                'text': cleaned_text,
                                'chunk_type': chunk['chunk_type'],
                                'page_number': chunk_page,
                                'order_in_doc': chunk_idx,
                                'topic_title': topic_title,
                                'subtopic_title': subtopic_title,
                                'sub_subtopic_title': sub_subtopic_title,
                                'sub_sub_subtopic_title': sub_sub_subtopic_title,
                                'parser_metadata': {
                                    'source': chunk.get('source', 'test_analysis'),
                                    'extraction_type': 'granular_document_processing',
                                    'original_chunk_type': chunk['chunk_type'],
                                    'page_range': f"{first_page+1}-{last_page+1}",
                                    'estimated_page': chunk_page + 1,
                                    'chunk_index': chunk_idx
                                }
                            }
                            valid_chunks.append(enhanced_chunk)
                            
                            # Track chunk type distribution
                            chunk_type = chunk['chunk_type']
                            results['chunk_types_distribution'][chunk_type] = results['chunk_types_distribution'].get(chunk_type, 0) + 1
                        
                        results['total_chunks_created'] = len(valid_chunks)
                        results['chunks'] = valid_chunks
                        
                    finally:
                        if os.path.exists(temp_chunk_path):
                            os.unlink(temp_chunk_path)
                
                temp_pdf.close()

                return Response({
                    'status': 'success',
                    'message': 'PDF granular analysis completed (no data saved)',
                    'document': {
                        'title': temp_doc.title,
                        'total_pages': total_pages,
                        'file_size_mb': round(len(file_content) / (1024*1024), 2)
                    },
                    'toc_info': {
                        'total_entries': len(toc_data),
                        'source': toc_source,
                        'levels': toc_analysis['levels'] if 'toc_analysis' in locals() else {}
                    },
                    'processing_results': results
                })

            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"PDF test analysis failed: {str(e)}")
            return Response({'status': 'error', 'message': f'Analysis failed: {str(e)}'},
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
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            try:
                # Full chunking pipeline test (without saving to DB)
                import fitz
                from content_ingestion.helpers.toc_parser.toc_utils import extract_toc, fallback_toc_text, parse_toc_text, assign_end_pages
                from content_ingestion.helpers.page_chunking.toc_chunk_processor import GranularChunkProcessor
                from content_ingestion.helpers.page_chunking.chunk_extractor_utils import clean_chunk_text, infer_chunk_type, extract_unstructured_chunks
                
                # Initialize chunk processor
                chunk_processor = GranularChunkProcessor()
                
                # Open PDF with error handling
                try:
                    doc = fitz.open(temp_file_path)
                    total_pages = len(doc)
                except Exception as pdf_error:
                    if "gray non-stroke color" in str(pdf_error) or "invalid float value" in str(pdf_error):
                        print(f"⚠️ PDF color space issue detected: {pdf_error}")
                        doc = fitz.open(temp_file_path)
                        total_pages = len(doc)
                    else:
                        raise pdf_error

                # Get TOC data
                try:
                    toc_data = extract_toc(temp_file_path)
                    toc_source = "metadata"
                except Exception as toc_error:
                    print(f"⚠️ TOC extraction error: {toc_error}")
                    toc_data = []
                    toc_source = "metadata_failed"
                
                if toc_data and isinstance(toc_data[0], list):
                    # Convert [level, title, page] to dicts
                    toc_data = [
                        {
                            'title': item[1],
                            'start_page': item[2] - 1,
                            'level': item[0],
                            'order': idx
                        }
                        for idx, item in enumerate(toc_data) if len(item) >= 3
                    ]
                else:
                    # Fallback: Manual TOC parsing
                    toc_source = "text_extraction"
                    try:
                        toc_pages = fallback_toc_text(doc)
                        combined_toc_text = "\n".join(toc_pages)
                        toc_data = parse_toc_text(combined_toc_text)
                    except Exception as fallback_error:
                        print(f"⚠️ Fallback TOC parsing error: {fallback_error}")
                        toc_data = []
                        toc_source = "text_extraction_failed"
                
                doc.close()
                
                # Assign end pages
                if toc_data:
                    toc_data = assign_end_pages(toc_data, total_pages)
                
                # Determine content boundaries - use TOC data if available
                from content_ingestion.helpers.toc_parser.toc_utils import find_content_boundaries
                
                if toc_data and len(toc_data) > 5:  # We have substantial TOC data
                    print(f"📖 Using TOC-based content boundaries with {len(toc_data)} entries")
                    
                    # Filter out non-content TOC entries
                    non_content_keywords = [
                        'cover', 'title page', 'copyright', 'dedication', 'about packt',
                        'contents', 'foreword', 'preface', 'acknowledgements', 
                        'table of contents', 'index', 'bibliography', 'references', 'glossary',
                        'appendix', 'about the author', 'about this book'
                    ]
                    
                    # Find first content entry (preferably Chapter 1)
                    first_content_entry = None
                    for entry in toc_data:
                        title_lower = entry.get('title', '').lower()
                        
                        # Skip non-content entries
                        if any(keyword in title_lower for keyword in non_content_keywords):
                            continue
                            
                        # Look for Chapter 1 or similar
                        if any(pattern in title_lower for pattern in ['chapter 1', 'chapter one', 'lesson 1', 'unit 1']):
                            first_content_entry = entry
                            print(f"📚 Found Chapter 1 in TOC: '{entry.get('title')}' at page {entry.get('start_page', 0) + 1}")
                            break
                            
                        # Look for numbered sections
                        if re.match(r'^\d+\.?\s+', title_lower) or 'introduction' in title_lower:
                            if not first_content_entry:  # Only set if we haven't found a better one
                                first_content_entry = entry
                    
                    if first_content_entry:
                        first_page = first_content_entry.get('start_page', 0)
                        # Find a reasonable end page (limit to ~20 pages for testing)
                        last_page = min(first_page + 20, total_pages - 1)
                        content_boundaries_source = "toc_analysis"
                        print(f"📖 TOC-based boundaries: pages {first_page + 1}-{last_page + 1}")
                    else:
                        # Fallback to content detection
                        first_page, last_page = find_content_boundaries(temp_file_path)
                        last_page = min(first_page + 20, last_page)  # Limit for testing
                        content_boundaries_source = "content_detection_fallback"
                else:
                    # Use content boundary detection
                    try:
                        first_page, last_page = find_content_boundaries(temp_file_path)
                        last_page = min(first_page + 20, last_page)  # Limit for testing
                        content_boundaries_source = "content_detection"
                    except Exception as boundary_error:
                        print(f"⚠️ Content boundary detection failed: {boundary_error}")
                        first_page, last_page = 10, min(30, total_pages - 1)  # Skip first 10 pages as fallback
                        content_boundaries_source = "fallback_skip_first_pages"
                
                # Process chunks using the enhanced granular processor
                results = {
                    'total_chunks_created': 0,
                    'total_pages_processed': 0,
                    'content_boundaries': (first_page + 1, last_page + 1),  # Convert to 1-based for display
                    'content_boundaries_source': content_boundaries_source,
                    'toc_source': toc_source,
                    'chunk_types_distribution': {},
                    'chunks': []  # Actual chunks for quality inspection
                }
                
                # Extract and process chunks from content pages
                pages_per_chunk = max(1, (last_page - first_page + 1) / 20)  # Target ~20 chunks max for testing
                
                try:
                    # Extract chunks using unstructured
                    temp_pdf = fitz.open()
                    for page_num in range(first_page, min(first_page + 10, last_page + 1)):  # Limit to 10 pages for testing
                        if page_num < total_pages:
                            try:
                                temp_pdf.insert_pdf(fitz.open(temp_file_path), from_page=page_num, to_page=page_num)
                            except Exception as page_error:
                                print(f"⚠️ Error processing page {page_num + 1}: {page_error}")
                                continue
                    
                    if len(temp_pdf) > 0:
                        # Create temporary file for chunk extraction
                        temp_fd, temp_chunk_path = tempfile.mkstemp(suffix='.pdf')
                        try:
                            os.close(temp_fd)
                            temp_pdf.save(temp_chunk_path)
                            
                            # Extract chunks
                            try:
                                raw_chunks = extract_unstructured_chunks(temp_chunk_path)
                            except Exception as chunk_error:
                                print(f"⚠️ Unstructured chunk extraction failed: {chunk_error}")
                                # Enhanced fallback extraction
                                raw_chunks = []
                                for page_idx in range(len(temp_pdf)):
                                    try:
                                        page = temp_pdf.load_page(page_idx)
                                        text = page.get_text()
                                        if text.strip() and len(text.strip()) > 100:
                                            # Split into meaningful paragraphs
                                            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip() and len(p.strip()) > 50]
                                            for para_idx, para in enumerate(paragraphs):
                                                if len(para) >= 50:
                                                    raw_chunks.append({
                                                        'content': para,
                                                        'chunk_type': infer_chunk_type(para),
                                                        'source': f'fallback_page_{page_idx + first_page + 1}_para_{para_idx + 1}'
                                                    })
                                    except Exception as page_text_error:
                                        print(f"⚠️ Error extracting text from page {page_idx + 1}: {page_text_error}")
                                        continue
                            
                            # Process chunks with proper 4-level TOC mapping
                            for chunk_idx, chunk in enumerate(raw_chunks):
                                # Map chunk to page
                                estimated_page = first_page + int(chunk_idx * pages_per_chunk)
                                chunk_page = min(estimated_page, last_page)
                                
                                # Initialize hierarchy titles
                                topic_title = ""
                                subtopic_title = ""
                                sub_subtopic_title = ""
                                sub_sub_subtopic_title = ""
                                
                                # Find the most specific TOC entry for this page (4-level hierarchy)
                                best_match_entries = {1: None, 2: None, 3: None, 4: None}
                                
                                for entry in toc_data:
                                    entry_start = entry.get('start_page', 0)
                                    entry_end = entry.get('end_page', entry_start)
                                    entry_level = entry.get('level', 0)
                                    
                                    # Check if this page falls within this TOC entry's range
                                    if entry_start <= chunk_page + 1 <= entry_end:
                                        # Store the best match for each level
                                        if entry_level in [1, 2, 3, 4]:
                                            best_match_entries[entry_level] = entry
                                
                                # If no exact matches, find the nearest parent entries before this page
                                for level in [1, 2, 3, 4]:
                                    if not best_match_entries[level]:
                                        for entry in reversed(toc_data):
                                            if (entry.get('level') == level and 
                                                entry.get('start_page', 0) <= chunk_page + 1):
                                                best_match_entries[level] = entry
                                                break
                                
                                # Assign titles based on hierarchy (Level 1=Topic, 2=Subtopic, 3=Sub-subtopic, 4=Sub-sub-subtopic)
                                if best_match_entries[1]:
                                    topic_title = best_match_entries[1].get('title', '')
                                if best_match_entries[2]:
                                    subtopic_title = best_match_entries[2].get('title', '')
                                if best_match_entries[3]:
                                    sub_subtopic_title = best_match_entries[3].get('title', '')
                                if best_match_entries[4]:
                                    sub_sub_subtopic_title = best_match_entries[4].get('title', '')
                                
                                # Ensure hierarchy consistency - if we have Level 4, we should have Level 3
                                if sub_sub_subtopic_title and not sub_subtopic_title:
                                    # Look for a Level 3 entry that could be the parent
                                    for entry in reversed(toc_data):
                                        if (entry.get('level') == 3 and 
                                            entry.get('start_page', 0) <= chunk_page + 1):
                                            sub_subtopic_title = entry.get('title', '')
                                            break
                                    
                                    # If still no Level 3, but we have Level 4, something might be mislabeled
                                    # Check if the Level 4 entry should actually be Level 3
                                    if not sub_subtopic_title and best_match_entries[4]:
                                        # Check if there are any more specific entries after this one
                                        has_deeper_entries = any(
                                            entry.get('level', 0) > 4 and entry.get('start_page', 0) >= chunk_page + 1
                                            for entry in toc_data
                                        )
                                        if not has_deeper_entries:
                                            # Move Level 4 to Level 3 if no deeper hierarchy exists
                                            sub_subtopic_title = sub_sub_subtopic_title
                                            sub_sub_subtopic_title = ""
                                
                                # Enhanced content filtering
                                non_content_keywords = [
                                    'contents', 'foreword', 'introduction', 'preface', 'acknowledgements', 
                                    'table of contents', 'index', 'bibliography', 'references', 'glossary',
                                    'appendix', 'about the author', 'about this book', 'dedication',
                                    'copyright', 'isbn', 'overview', 'getting started', 'toc'
                                ]
                                
                                # Skip if topic title matches non-content keywords
                                if any(keyword in topic_title.lower() for keyword in non_content_keywords):
                                    continue
                                    
                                # Skip if this appears to be a TOC page
                                if chunk_page + 1 <= 3 and any(keyword in topic_title.lower() for keyword in ['contents', 'table']):
                                    continue
                                    
                                # Skip chunks that are too short to be meaningful content after cleaning
                                if len(cleaned_text.strip()) < 20:
                                    print(f"   📝 Skipping minimal chunk after cleaning: {len(cleaned_text.strip())} chars")
                                    continue
                                
                                # Clean chunk text with all 4 levels
                                cleaned_text = clean_chunk_text(
                                    chunk['content'], 
                                    subtopic_title, 
                                    topic_title, 
                                    sub_subtopic_title, 
                                    sub_sub_subtopic_title
                                )
                                
                                # Create enhanced chunk with full hierarchy
                                enhanced_chunk = {
                                    'chunk_id': chunk_idx + 1,
                                    'text': cleaned_text,
                                    'original_text': chunk['content'],  # Include original for comparison
                                    'chunk_type': chunk['chunk_type'],
                                    'page_number': chunk_page + 1,  # 1-based page number
                                    'estimated_page': chunk_page + 1,
                                    'word_count': len(cleaned_text.split()),
                                    'character_count': len(cleaned_text),
                                    'topic_title': topic_title,
                                    'subtopic_title': subtopic_title,
                                    'sub_subtopic_title': sub_subtopic_title,
                                    'sub_sub_subtopic_title': sub_sub_subtopic_title,
                                    'source': chunk.get('source', 'unstructured'),
                                    'quality_metrics': {
                                        'has_topic': bool(topic_title),
                                        'has_subtopic': bool(subtopic_title),
                                        'has_sub_subtopic': bool(sub_subtopic_title),
                                        'has_sub_sub_subtopic': bool(sub_sub_subtopic_title),
                                        'hierarchy_depth': sum([bool(topic_title), bool(subtopic_title), bool(sub_subtopic_title), bool(sub_sub_subtopic_title)]),
                                        'text_cleaned': len(cleaned_text) < len(chunk['content']),
                                        'substantial_content': len(cleaned_text) >= 200
                                    }
                                }
                                
                                results['chunks'].append(enhanced_chunk)
                                
                                # Track chunk type distribution
                                chunk_type = chunk['chunk_type']
                                results['chunk_types_distribution'][chunk_type] = results['chunk_types_distribution'].get(chunk_type, 0) + 1
                            
                            results['total_chunks_created'] = len(results['chunks'])
                            results['total_pages_processed'] = min(10, last_page - first_page + 1)
                            
                        finally:
                            # Clean up temporary chunk file
                            if os.path.exists(temp_chunk_path):
                                os.unlink(temp_chunk_path)
                    
                    temp_pdf.close()
                    
                except Exception as processing_error:
                    print(f"⚠️ Chunk processing error: {processing_error}")
                    results['error'] = str(processing_error)
                
                # Return comprehensive chunking analysis
                return Response({
                    'status': 'success',
                    'message': 'PDF chunking analysis completed',
                    'document_info': {
                        'title': temp_doc.title,
                        'total_pages': total_pages,
                        'difficulty': difficulty,
                        'file_size_mb': round(len(file_content) / (1024*1024), 2)
                    },
                    'toc_info': {
                        'total_entries': len(toc_data),
                        'source': toc_source,
                        'entries_sample': toc_data[:5] if toc_data else []  # First 5 entries for reference
                    },
                    'chunking_results': results,
                    'quality_summary': {
                        'chunks_with_topics': sum(1 for chunk in results['chunks'] if chunk['quality_metrics']['has_topic']),
                        'chunks_with_subtopics': sum(1 for chunk in results['chunks'] if chunk['quality_metrics']['has_subtopic']),
                        'chunks_with_sub_subtopics': sum(1 for chunk in results['chunks'] if chunk['quality_metrics']['has_sub_subtopic']),
                        'chunks_with_sub_sub_subtopics': sum(1 for chunk in results['chunks'] if chunk['quality_metrics']['has_sub_sub_subtopic']),
                        'average_chunk_length': sum(chunk['word_count'] for chunk in results['chunks']) / max(1, len(results['chunks'])),
                        'text_cleaning_applied': sum(1 for chunk in results['chunks'] if chunk['quality_metrics']['text_cleaned']),
                        'substantial_content_chunks': sum(1 for chunk in results['chunks'] if chunk['quality_metrics']['substantial_content'])
                    }
                })

            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"PDF test chunking failed: {str(e)}")
            return Response({'status': 'error', 'message': f'Chunking analysis failed: {str(e)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
