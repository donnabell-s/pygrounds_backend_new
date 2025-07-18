import fitz
from typing import List, Dict, Any
from django.db import transaction
from content_ingestion.models import UploadedDocument, DocumentChunk, TOCEntry
from .chunk_extractor_utils import extract_unstructured_chunks, infer_chunk_type, clean_chunk_text
from content_ingestion.helpers.embedding_utils import EmbeddingGenerator
import tempfile
import os

class TOCBasedChunkProcessor:
    """
    Processes matched TOC entries and creates consolidated page chunks for optimal RAG performance.
    """
    
    def __init__(self, enable_embeddings: bool = True):
        self.batch_size = 50
        self.enable_embeddings = enable_embeddings
        self.embedding_generator = EmbeddingGenerator() if enable_embeddings else None
        
        # Sample content detection patterns
        self.sample_content_indicators = [
            "This is a sample from",
            "With the full version of the book you get",
            "purchase a full version",
            "If you enjoyed the sample chapters",
            "Python Basics: A Practical Introduction to Python 3"
        ]
    
    def process_matched_entries(self, document: UploadedDocument, matched_entries: List[TOCEntry]) -> Dict[str, Any]:
        """
        Process only the matched TOC entries and create consolidated page chunks.
        
        Args:
            document: The UploadedDocument instance
            matched_entries: List of TOCEntry objects that matched topics/subtopics
        
        Returns:
            Dictionary with processing results and statistics
        """
        results = {
            'total_entries_processed': 0,
            'total_chunks_created': 0,
            'total_pages_processed': 0,
            'entries_details': [],
            'consolidated_pages': set(),
            'sample_content_filtered': 0,
            'entries_skipped_sample_only': 0
        }
        
        print(f"\n🔄 STARTING CHUNK PROCESSING")
        print(f"{'─'*60}")
        print(f"Document: {document.title}")
        print(f"Document total pages: {document.total_pages}")
        print(f"Matched entries to process: {len(matched_entries)}")
        
        # Clear all existing chunks for this document to avoid duplicates
        existing_chunks_count = DocumentChunk.objects.filter(document=document).count()
        if existing_chunks_count > 0:
            print(f"🗑️  Clearing {existing_chunks_count} existing chunks for clean reprocessing...")
            DocumentChunk.objects.filter(document=document).delete()
            print(f"✅ Cleared all existing chunks")
        
        # Pre-filter valid entries
        valid_entries = []
        for entry in matched_entries:
            if entry.start_page < 0:
                print(f"⚠️  Skipping '{entry.title[:30]}...': negative start_page ({entry.start_page})")
                continue
            if entry.start_page >= document.total_pages:
                print(f"⚠️  Skipping '{entry.title[:30]}...': start_page ({entry.start_page+1}) > total_pages ({document.total_pages})")
                continue
            if entry.end_page and entry.end_page < entry.start_page:
                print(f"⚠️  Skipping '{entry.title[:30]}...': invalid page range ({entry.start_page+1}-{entry.end_page+1})")
                continue
            valid_entries.append(entry)
        
        print(f"Valid entries after filtering: {len(valid_entries)}/{len(matched_entries)}")
        
        if not valid_entries:
            print(f"❌ No valid entries to process")
            return results
        
        # Process each valid TOC entry
        for i, toc_entry in enumerate(valid_entries, 1):
            print(f"\n📄 Processing Entry {i}/{len(valid_entries)}: {toc_entry.title[:50]}...")
            print(f"   Pages: {toc_entry.start_page+1}-{toc_entry.end_page+1 if toc_entry.end_page else 'end'}")
            
            # Validate entry before processing
            if toc_entry.start_page < 0:
                print(f"   ⚠️  Invalid start_page ({toc_entry.start_page}), skipping entry")
                results['entries_details'].append({
                    'id': toc_entry.id,
                    'title': toc_entry.title,
                    'pages': f"{toc_entry.start_page+1}-{toc_entry.end_page+1 if toc_entry.end_page else 'end'}",
                    'chunks_created': 0,
                    'status': 'error',
                    'error': 'Invalid page range: negative start_page'
                })
                continue
            
            if toc_entry.end_page and toc_entry.end_page < toc_entry.start_page:
                print(f"   ⚠️  Invalid page range (end < start), will fix automatically")
            
            try:
                # Extract chunks for this specific TOC section
                entry_chunks = self._extract_chunks_for_toc_entry(document, toc_entry)
                
                if not entry_chunks:
                    print(f"   ⚠️  No chunks extracted - likely sample-only content, skipping")
                    results['entries_skipped_sample_only'] += 1
                    results['entries_details'].append({
                        'id': toc_entry.id,
                        'title': toc_entry.title,
                        'pages': f"{toc_entry.start_page+1}-{toc_entry.end_page+1 if toc_entry.end_page else 'end'}",
                        'chunks_created': 0,
                        'status': 'skipped_sample_content',
                        'reason': 'Entry contains only sample placeholder content'
                    })
                    continue
                
                # Save chunks to database
                chunk_count = self._save_chunks_for_entry(toc_entry, entry_chunks)
                
                # Update TOC entry status
                toc_entry.chunked = True
                toc_entry.chunk_count = chunk_count
                toc_entry.save(update_fields=['chunked', 'chunk_count'])
                
                # Track results
                start_page = max(0, toc_entry.start_page)
                end_page = toc_entry.end_page if toc_entry.end_page and toc_entry.end_page >= start_page else start_page
                pages_in_entry = range(start_page, end_page + 1)
                results['consolidated_pages'].update(pages_in_entry)
                results['total_entries_processed'] += 1
                results['total_chunks_created'] += chunk_count
                
                results['entries_details'].append({
                    'id': toc_entry.id,
                    'title': toc_entry.title,
                    'pages': f"{toc_entry.start_page+1}-{toc_entry.end_page+1 if toc_entry.end_page else 'end'}",
                    'chunks_created': chunk_count,
                    'status': 'success'
                })
                
                print(f"   ✅ Created {chunk_count} chunks")
                
            except Exception as e:
                print(f"   ❌ Error processing entry: {str(e)}")
                results['entries_details'].append({
                    'id': toc_entry.id,
                    'title': toc_entry.title,
                    'pages': f"{toc_entry.start_page+1}-{toc_entry.end_page+1 if toc_entry.end_page else 'end'}",
                    'chunks_created': 0,
                    'status': 'error',
                    'error': str(e)
                })
        
        # Consolidate chunks by page for better RAG performance
        results['total_pages_processed'] = len(results['consolidated_pages'])
        self._consolidate_chunks_by_page(document, list(results['consolidated_pages']))
        
        # Generate embeddings for all chunks
        embedding_results = self._generate_embeddings_for_document(document)
        results['embedding_stats'] = embedding_results
        
        print(f"\n📊 PROCESSING COMPLETE")
        print(f"{'─'*60}")
        print(f"Entries processed: {results['total_entries_processed']}")
        print(f"Entries skipped (sample-only): {results['entries_skipped_sample_only']}")
        print(f"Total chunks created: {results['total_chunks_created']}")
        print(f"Pages with consolidated chunks: {results['total_pages_processed']}")
        if results['sample_content_filtered'] > 0:
            print(f"Sample content chunks filtered: {results['sample_content_filtered']}")
        if embedding_results['total'] > 0:
            print(f"Embeddings generated: {embedding_results['success']}/{embedding_results['total']}")
        
        return results
    
    def _generate_embeddings_for_document(self, document: UploadedDocument) -> Dict[str, Any]:
        """
        Generate embeddings for all chunks in the document.
        
        Args:
            document: The UploadedDocument instance
            
        Returns:
            Dictionary with embedding statistics
        """
        if not self.enable_embeddings or not self.embedding_generator:
            return {'success': 0, 'failed': 0, 'total': 0, 'status': 'disabled'}
        
        print(f"\n🔮 GENERATING EMBEDDINGS")
        print(f"{'─'*40}")
        
        # Get all chunks for this document that don't have embeddings
        chunks_to_embed = DocumentChunk.objects.filter(
            document=document,
            embedding__isnull=True
        )
        
        if not chunks_to_embed.exists():
            print(f"✅ All chunks already have embeddings")
            return {'success': 0, 'failed': 0, 'total': 0, 'status': 'already_embedded'}
        
        print(f"📝 Found {chunks_to_embed.count()} chunks to embed")
        
        # Generate embeddings in batch
        embedding_results = self.embedding_generator.embed_chunks_batch(chunks_to_embed)
        
        print(f"✅ Embedding complete: {embedding_results['success']}/{embedding_results['total']} successful")
        
        return embedding_results
    
    def _is_sample_placeholder_content(self, text: str) -> bool:
        """
        Check if the content is just a sample placeholder (not actual book content).
        
        Args:
            text: The text content to check
            
        Returns:
            True if this appears to be sample placeholder content
        """
        if not text or len(text.strip()) < 50:
            return False
            
        # Check for multiple sample indicators
        indicator_count = 0
        text_lower = text.lower()
        
        for indicator in self.sample_content_indicators:
            if indicator.lower() in text_lower:
                indicator_count += 1
        
        # If we find 2+ indicators, it's likely a sample placeholder
        if indicator_count >= 2:
            return True
            
        # Additional heuristic: if the content is very short and contains sample text
        if len(text.strip()) < 800 and any(indicator.lower() in text_lower for indicator in self.sample_content_indicators[:3]):
            return True
            
        return False
    
    def _extract_chunks_for_toc_entry(self, document: UploadedDocument, toc_entry: TOCEntry) -> List[Dict[str, Any]]:
        """
        Extract chunks for a specific TOC entry's page range.
        """
        doc = None
        temp_pdf = None
        temp_path = None
        
        try:
            # Open the PDF and validate page range
            doc = fitz.open(document.file.path)
            total_pages = len(doc)
            
            start_page = max(0, toc_entry.start_page)
            end_page = toc_entry.end_page
            
            # Fix invalid page ranges
            if end_page is None or end_page < start_page:
                end_page = start_page
            
            # Ensure pages are within document bounds
            start_page = min(start_page, total_pages - 1)
            end_page = min(end_page, total_pages - 1)
            
            print(f"   📄 Extracting pages {start_page+1}-{end_page+1} from {total_pages} total pages")
            
            # Validate we have valid pages to process
            if start_page >= total_pages:
                print(f"   ⚠️  Start page {start_page+1} exceeds document length ({total_pages}), skipping")
                return []
            
            # Create a temporary PDF with just the pages we need
            temp_pdf = fitz.open()
            for page_num in range(start_page, end_page + 1):
                if page_num < total_pages:
                    temp_pdf.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            # Check if we have any pages to save
            if len(temp_pdf) == 0:
                print(f"   ⚠️  No valid pages to process for range {start_page+1}-{end_page+1}")
                return []
            
            # Create temporary file with proper cleanup
            temp_fd, temp_path = tempfile.mkstemp(suffix='.pdf')
            try:
                os.close(temp_fd)  # Close file descriptor immediately
                temp_pdf.save(temp_path)
                
                print(f"   🔧 Created temp PDF with {len(temp_pdf)} pages at {temp_path}")
                
                # Extract chunks using unstructured with fallback
                try:
                    raw_chunks = extract_unstructured_chunks(temp_path)
                    print(f"   📝 Extracted {len(raw_chunks)} raw chunks using unstructured")
                except Exception as extract_error:
                    print(f"   ⚠️  Unstructured extraction failed: {str(extract_error)}")
                    print(f"   🔄 Falling back to basic PyMuPDF text extraction")
                    raw_chunks = self._fallback_text_extraction(temp_pdf, start_page, end_page)
                    print(f"   📝 Extracted {len(raw_chunks)} chunks using fallback method")
                
                if not raw_chunks:
                    print(f"   ⚠️  No content extracted from any method")
                    return []
                
                # Filter out sample placeholder content
                valid_chunks = []
                sample_chunks_filtered = 0
                
                for chunk in raw_chunks:
                    if self._is_sample_placeholder_content(chunk['content']):
                        sample_chunks_filtered += 1
                        print(f"   🚫 Filtered sample placeholder content (chunk {len(valid_chunks) + sample_chunks_filtered})")
                    else:
                        valid_chunks.append(chunk)
                
                if sample_chunks_filtered > 0:
                    print(f"   📊 Filtered {sample_chunks_filtered} sample placeholder chunks, kept {len(valid_chunks)} valid chunks")
                
                if not valid_chunks:
                    print(f"   ⚠️  All extracted content appears to be sample placeholders - skipping entry")
                    return []
                
                # Enhance chunks with TOC context and page mapping
                enhanced_chunks = []
                pages_per_chunk = max(1, (end_page - start_page + 1) / max(1, len(valid_chunks)))
                
                for chunk_idx, chunk in enumerate(valid_chunks):
                    # Better page mapping based on chunk position
                    estimated_page = start_page + int(chunk_idx * pages_per_chunk)
                    chunk_page = min(estimated_page, end_page)
                    
                    enhanced_chunk = {
                        'text': chunk['content'],
                        'chunk_type': chunk['chunk_type'],
                        'page_number': chunk_page,
                        'toc_entry': toc_entry,
                        'order_in_doc': chunk_idx,
                        'topic_title': toc_entry.title,
                        'parser_metadata': {
                            'source': chunk['source'],
                            'toc_entry_id': toc_entry.id,
                            'original_chunk_type': chunk['chunk_type'],
                            'page_range': f"{start_page+1}-{end_page+1}",
                            'estimated_page': chunk_page + 1
                        }
                    }
                    enhanced_chunks.append(enhanced_chunk)
                
                print(f"   ✅ Enhanced {len(enhanced_chunks)} chunks with metadata")
                return enhanced_chunks
                
            except Exception as e:
                print(f"   ❌ Error during chunk extraction: {str(e)}")
                return []
        
        except Exception as e:
            print(f"   ❌ Error opening/processing PDF: {str(e)}")
            return []
        
        finally:
            # Ensure proper cleanup in all cases
            try:
                if doc:
                    doc.close()
                if temp_pdf:
                    temp_pdf.close()
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
                    print(f"   🗑️  Cleaned up temporary file")
            except Exception as cleanup_error:
                    print(f"   ⚠️  Cleanup warning: {str(cleanup_error)}")
    
    def _fallback_text_extraction(self, temp_pdf, start_page, end_page) -> List[Dict[str, Any]]:
        """
        Fallback text extraction using PyMuPDF when unstructured fails.
        """
        chunks = []
        try:
            for page_idx in range(len(temp_pdf)):
                page = temp_pdf[page_idx]
                text = page.get_text()
                
                if text.strip():  # Only add non-empty text
                    # Check if this page is sample content before processing
                    if self._is_sample_placeholder_content(text):
                        print(f"   🚫 Skipping sample placeholder content on page {page_idx + 1}")
                        continue
                    
                    # Split long text into smaller chunks
                    max_chunk_size = 2000
                    if len(text) > max_chunk_size:
                        # Split by paragraphs first, then by sentences
                        paragraphs = text.split('\n\n')
                        current_chunk = ""
                        
                        for para in paragraphs:
                            if len(current_chunk + para) > max_chunk_size:
                                if current_chunk.strip():
                                    chunks.append({
                                        'content': current_chunk.strip(),
                                        'chunk_type': 'Text',
                                        'source': 'pymupdf_fallback'
                                    })
                                current_chunk = para
                            else:
                                current_chunk += "\n\n" + para if current_chunk else para
                        
                        # Add remaining chunk
                        if current_chunk.strip():
                            chunks.append({
                                'content': current_chunk.strip(),
                                'chunk_type': 'Text',
                                'source': 'pymupdf_fallback'
                            })
                    else:
                        chunks.append({
                            'content': text.strip(),
                            'chunk_type': 'Text',
                            'source': 'pymupdf_fallback'
                        })
            
            return chunks
            
        except Exception as e:
            print(f"   ❌ Fallback extraction also failed: {str(e)}")
            return []    @transaction.atomic
    def _save_chunks_for_entry(self, toc_entry: TOCEntry, chunks: List[Dict[str, Any]]) -> int:
        """
        Save chunks for a TOC entry to the database.
        """
        # Note: Document-level chunk clearing is done upfront in process_matched_entries()
        # No need to delete individual TOC entry chunks here
        
        chunk_objects = []
        for chunk_data in chunks:
            chunk = DocumentChunk(
                document=toc_entry.document,
                chunk_type=chunk_data['chunk_type'],
                text=chunk_data['text'],
                page_number=chunk_data['page_number'],
                order_in_doc=chunk_data['order_in_doc'],
                topic_title=chunk_data['topic_title'],
                parser_metadata=chunk_data['parser_metadata']
            )
            chunk_objects.append(chunk)
        
        # Bulk create chunks
        if chunk_objects:
            DocumentChunk.objects.bulk_create(chunk_objects)
        
        return len(chunk_objects)
    
    def _consolidate_chunks_by_page(self, document: UploadedDocument, processed_pages: List[int]):
        """
        Consolidate chunks by title across multiple pages for better RAG performance.
        This groups related content with the same title into single unified chunks.
        """
        print(f"\n🔄 CONSOLIDATING CHUNKS BY TITLE ACROSS PAGES")
        print(f"{'─'*40}")
        
        # Get all chunks for processed pages
        all_chunks = DocumentChunk.objects.filter(
            document=document,
            page_number__in=processed_pages
        ).order_by('page_number', 'order_in_doc')
        
        if not all_chunks.exists():
            print(f"   ⚠️  No chunks found for consolidation")
            return
        
        # Group chunks by topic title
        chunks_by_title = {}
        for chunk in all_chunks:
            title = chunk.topic_title or "untitled_content"
            if title not in chunks_by_title:
                chunks_by_title[title] = []
            chunks_by_title[title].append(chunk)
        
        print(f"   📊 Found {len(chunks_by_title)} unique titles to consolidate")
        
        # Process each title group
        for title, title_chunks in chunks_by_title.items():
            if len(title_chunks) == 1:
                # Single chunk - just update its type for consistency
                chunk = title_chunks[0]
                chunk.chunk_type = "consolidated_content"
                chunk.parser_metadata = chunk.parser_metadata or {}
                chunk.parser_metadata.update({
                    'consolidated': True,
                    'original_chunk_count': 1,
                    'original_types': [chunk.chunk_type],
                    'consolidation_reason': 'single_chunk_standardization',
                    'title_unified': True
                })
                chunk.save()
                print(f"   📄 Title '{title}': Standardized 1 chunk")
            else:
                # Multiple chunks - consolidate into one
                combined_text_parts = []
                combined_types = set()
                page_numbers = set()
                
                for chunk in title_chunks:
                    combined_text_parts.append(chunk.text.strip())
                    combined_types.add(chunk.chunk_type)
                    page_numbers.add(chunk.page_number)
                
                # Use the first page as primary page
                primary_page = min(page_numbers)
                
                # Create consolidated chunk with combined content
                consolidated_text = "\n\n".join(combined_text_parts)
                
                # Delete all original chunks
                chunk_ids = [chunk.id for chunk in title_chunks]
                DocumentChunk.objects.filter(id__in=chunk_ids).delete()
                
                # Create single consolidated chunk
                DocumentChunk.objects.create(
                    document=document,
                    chunk_type="consolidated_content",
                    text=consolidated_text,
                    page_number=primary_page,
                    order_in_doc=0,  # Single chunk per title
                    topic_title=title,
                    parser_metadata={
                        'consolidated': True,
                        'original_chunk_count': len(title_chunks),
                        'original_types': list(combined_types),
                        'page_range': f"{min(page_numbers)}-{max(page_numbers)}",
                        'consolidation_reason': 'title_based_unification',
                        'title_unified': True,
                        'pages_spanned': list(sorted(page_numbers))
                    }
                )
                
                page_range = f"{min(page_numbers)+1}-{max(page_numbers)+1}" if len(page_numbers) > 1 else str(primary_page+1)
                print(f"   📄 Title '{title}': Consolidated {len(title_chunks)} chunks from pages {page_range} → 1 unified chunk")
        
        print(f"✅ Title-based consolidation complete - One chunk per title achieved")
