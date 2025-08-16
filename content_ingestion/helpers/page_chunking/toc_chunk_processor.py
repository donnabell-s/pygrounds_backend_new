import fitz
import re
from typing import List, Dict, Any
from django.db import transaction
from content_ingestion.models import UploadedDocument, DocumentChunk, TOCEntry
from .chunk_extractor_utils import extract_unstructured_chunks
from .chunk_classifier import infer_chunk_type
from .text_cleaner import clean_chunk_text
from content_ingestion.helpers.embedding import EmbeddingGenerator
from content_ingestion.helpers.toc_parser.toc_utils import find_content_boundaries
from content_ingestion.helpers.utils.token_utils import TokenCounter
import tempfile
import os

class GranularChunkProcessor:
    """
    Processes documents and creates granular chunks with type classification for optimal RAG performance.
    Processes entire content area instead of specific TOC entries.
    """
    
    def __init__(self, enable_embeddings: bool = True):
        self.batch_size = 50
        self.enable_embeddings = enable_embeddings
        self.embedding_generator = EmbeddingGenerator() if enable_embeddings else None
        self.token_counter = TokenCounter()  # Initialize token counter
        
        # Sample content detection patterns
        self.sample_content_indicators = [
            "This is a sample from",
            "With the full version of the book you get",
            "purchase a full version",
            "If you enjoyed the sample chapters",
            "Python Basics: A Practical Introduction to Python 3"
        ]
    
    def _get_toc_titles_for_page(self, document: UploadedDocument, page_number: int) -> tuple[str, str]:
        """
        Get the topic and subtopic titles for a given page based on TOC entries.
        
        Args:
            document: The UploadedDocument instance
            page_number: Page number (1-based)
            
        Returns:
            Tuple of (topic_title, subtopic_title)
        """
        try:
            # Get all TOC entries for this document, ordered by start_page
            toc_entries = TOCEntry.objects.filter(document=document).order_by('start_page')
            
            # Find the TOC entry that contains this page
            current_entry = None
            for entry in toc_entries:
                if entry.start_page <= page_number <= (entry.end_page or entry.start_page):
                    current_entry = entry
                    break
            
            if not current_entry:
                # If no exact match, find the entry that starts before or at this page
                for entry in toc_entries.reverse():
                    if entry.start_page <= page_number:
                        current_entry = entry
                        break
            
            if not current_entry:
                return "", ""
            
            # Determine if this is a chapter (level 0) or section (level 1+)
            if current_entry.level == 0:
                # This is a chapter title
                topic_title = self._clean_toc_title(current_entry.title)
                subtopic_title = ""
            else:
                # This is a section, find the parent chapter
                topic_title = ""
                subtopic_title = self._clean_toc_title(current_entry.title)
                
                # Find the parent chapter (level 0 entry that comes before this one)
                parent_entries = toc_entries.filter(
                    level=0, 
                    start_page__lte=current_entry.start_page
                ).order_by('-start_page')
                
                if parent_entries.exists():
                    topic_title = self._clean_toc_title(parent_entries.first().title)
            
            return topic_title, subtopic_title
            
        except Exception as e:
            print(f"   ⚠️ Error getting TOC titles for page {page_number}: {e}")
            return "", ""
    
    def _clean_toc_title(self, title: str) -> str:
        """
        Clean TOC title by removing dots, page numbers, and formatting artifacts.
        
        Args:
            title: Raw TOC title
            
        Returns:
            Cleaned title string
        """
        if not title:
            return ""
        
        # Remove leading numbers (e.g., "1.1", "2.3")
        title = re.sub(r'^\d+\.?\d*\s*', '', title)
        
        # Remove trailing dots and page references
        title = re.sub(r'\s*\.+\s*\d*\s*$', '', title)
        title = re.sub(r'\s*\.+\s*$', '', title)
        
        # Clean up extra whitespace
        title = re.sub(r'\s+', ' ', title).strip()
        
        return title

    def _analyze_token_distribution(self, document: UploadedDocument) -> Dict[str, Any]:
        """
        Analyze token distribution across all chunks for the document.
        
        Args:
            document: The UploadedDocument instance
            
        Returns:
            Dict with token analysis statistics
        """
        chunks = DocumentChunk.objects.filter(document=document)
        
        if not chunks.exists():
            return {"error": "No chunks found for analysis"}
        
        token_counts = []
        total_characters = 0
        chunk_types = {}
        
        for chunk in chunks:
            token_count = chunk.token_count or 0
            token_counts.append(token_count)
            total_characters += len(chunk.text)
            
            # Track tokens by chunk type
            chunk_type = chunk.chunk_type
            if chunk_type not in chunk_types:
                chunk_types[chunk_type] = {'count': 0, 'tokens': 0}
            chunk_types[chunk_type]['count'] += 1
            chunk_types[chunk_type]['tokens'] += token_count
        
        if not token_counts:
            return {"error": "No token data available"}
        
        # Calculate statistics
        total_tokens = sum(token_counts)
        avg_tokens = total_tokens / len(token_counts) if token_counts else 0
        
        # Cost estimation for common models
        gpt4_cost = self.token_counter.estimate_cost(total_tokens, "gpt-4")
        gpt35_cost = self.token_counter.estimate_cost(total_tokens, "gpt-3.5-turbo")
        
        return {
            "total_chunks": len(token_counts),
            "total_tokens": total_tokens,
            "total_characters": total_characters,
            "avg_tokens_per_chunk": round(avg_tokens, 2),
            "min_tokens": min(token_counts) if token_counts else 0,
            "max_tokens": max(token_counts) if token_counts else 0,
            "encoding_used": self.token_counter.encoding_name,
            "chunks_over_1k_tokens": len([c for c in token_counts if c > 1000]),
            "chunks_over_2k_tokens": len([c for c in token_counts if c > 2000]),
            "chunks_over_4k_tokens": len([c for c in token_counts if c > 4000]),
            "chunk_types_token_distribution": chunk_types,
            "estimated_costs": {
                "gpt_4": gpt4_cost,
                "gpt_3_5_turbo": gpt35_cost
            }
        }

    def _get_toc_content_boundaries(self, document: UploadedDocument) -> tuple[int, int]:
        """
        Determine content boundaries based on existing TOC entries to avoid processing
        copyright pages, title pages, and other non-educational content.
        
        Args:
            document: The UploadedDocument instance
            
        Returns:
            Tuple of (first_content_page, last_content_page) (0-based)
        """
        toc_entries = TOCEntry.objects.filter(document=document).order_by('start_page')
        
        if not toc_entries.exists():
            raise ValueError("No TOC entries found for document")
        
        # Get the first and last page from TOC entries
        first_toc_page = toc_entries.first().start_page - 1  # Convert to 0-based
        last_toc_page = toc_entries.last().end_page - 1 if toc_entries.last().end_page else toc_entries.last().start_page - 1
        
        # Filter out any preliminary pages (usually contain non-educational content)
        # Educational content typically starts with chapter/section numbers
        educational_entries = toc_entries.filter(
            title__iregex=r'^\d+\.?\d*\s+'  # Starts with numbers like "1.1", "2.", etc.
        )
        
        if educational_entries.exists():
            first_educational_page = educational_entries.first().start_page - 1  # Convert to 0-based
            print(f"📚 Found educational content starting at page {first_educational_page + 1}: '{educational_entries.first().title}'")
            first_content_page = first_educational_page
        else:
            # Fallback to first TOC entry if no numbered sections found
            first_content_page = first_toc_page
            print(f"📚 No numbered sections found, using first TOC entry at page {first_content_page + 1}")
        
        # For the end, use the last TOC entry's end_page
        last_content_page = last_toc_page
        
        print(f"📖 TOC-based content boundaries: pages {first_content_page + 1}-{last_content_page + 1}")
        return first_content_page, last_content_page

    def process_entire_document(self, document: UploadedDocument) -> Dict[str, Any]:
        """
        Process the entire document content area with granular chunking,
        avoiding non-informational pages like covers, prefaces, etc.
        
        Args:
            document: The UploadedDocument instance
        
        Returns:
            Dictionary with processing results and statistics
        """
        results = {
            'total_chunks_created': 0,
            'total_pages_processed': 0,
            'content_boundaries': None,
            'sample_content_filtered': 0,
            'chunk_types_distribution': {},
        }
        
        print(f"\n🔄 STARTING GRANULAR DOCUMENT PROCESSING")
        print(f"{'─'*60}")
        print(f"Document: {document.title}")
        print(f"Document total pages: {document.total_pages}")
        
        # Clear all existing chunks for this document to avoid duplicates
        existing_chunks_count = DocumentChunk.objects.filter(document=document).count()
        if existing_chunks_count > 0:
            print(f"🗑️  Clearing {existing_chunks_count} existing chunks for clean reprocessing...")
            DocumentChunk.objects.filter(document=document).delete()
            print(f"✅ Cleared all existing chunks")
        
        # Find content boundaries using TOC data to avoid non-informational pages
        try:
            first_page, last_page = self._get_toc_content_boundaries(document)
            results['content_boundaries'] = (first_page + 1, last_page + 1)  # Convert to 1-based for display
            print(f"📖 Processing TOC-defined content pages: {first_page + 1}-{last_page + 1}")
        except Exception as e:
            print(f"⚠️ Could not determine TOC boundaries, falling back to heuristic: {e}")
            first_page, last_page = find_content_boundaries(document.file.path)
            results['content_boundaries'] = (first_page + 1, last_page + 1)  # Convert to 1-based for display
            print(f"📖 Processing heuristic content pages: {first_page + 1}-{last_page + 1}")
        
        # Process the content area with granular chunking
        try:
            chunks = self._extract_granular_chunks_from_range(document, first_page, last_page)
            
            if not chunks:
                print(f"⚠️ No chunks extracted from content area")
                return results
            
            # Save chunks to database and track statistics
            chunk_count = self._save_granular_chunks(document, chunks)
            results['total_chunks_created'] = chunk_count
            results['total_pages_processed'] = last_page - first_page + 1
            
            # Track chunk type distribution
            for chunk in chunks:
                chunk_type = chunk['chunk_type']
                results['chunk_types_distribution'][chunk_type] = results['chunk_types_distribution'].get(chunk_type, 0) + 1
            
            print(f"✅ Created {chunk_count} granular chunks")
            print(f"📊 Chunk types: {results['chunk_types_distribution']}")
            
        except Exception as e:
            print(f"❌ Error processing document content: {str(e)}")
            return results
        
        # Generate embeddings for all chunks
        embedding_results = self._generate_embeddings_for_document(document)
        results['embedding_stats'] = embedding_results
        
        # Analyze token distribution
        token_analysis = self._analyze_token_distribution(document)
        results['token_analysis'] = token_analysis
        
        print(f"\n📊 PROCESSING COMPLETE")
        print(f"{'─'*60}")
        print(f"Total chunks created: {results['total_chunks_created']}")
        print(f"Pages processed: {results['total_pages_processed']}")
        if results['sample_content_filtered'] > 0:
            print(f"Sample content chunks filtered: {results['sample_content_filtered']}")
        total_processed = embedding_results.get('success', 0) + embedding_results.get('failed', 0)
        if total_processed > 0:
            print(f"Embeddings generated: {embedding_results.get('success', 0)}/{total_processed}")
        if 'total_tokens' in token_analysis:
            print(f"Total tokens: {token_analysis['total_tokens']} (avg: {token_analysis['avg_tokens_per_chunk']} per chunk)")
            print(f"Estimated GPT-4 cost: ${token_analysis['estimated_costs']['gpt_4']['estimated_input_cost_usd']:.4f}")
        
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
            embeddings__isnull=True
        )
        
        if not chunks_to_embed.exists():
            print(f"✅ All chunks already have embeddings")
            return {'success': 0, 'failed': 0, 'total': 0, 'status': 'already_embedded'}
        
        print(f"📝 Found {chunks_to_embed.count()} chunks to embed")
        
        # Generate embeddings in batch
        embedding_results = self.embedding_generator.embed_and_save_batch(chunks_to_embed)
        
        total_processed = embedding_results.get('success', 0) + embedding_results.get('failed', 0)
        print(f"✅ Embedding complete: {embedding_results.get('success', 0)}/{total_processed} successful")
        
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

    def _extract_granular_chunks_from_range(self, document: UploadedDocument, start_page: int, end_page: int) -> List[Dict[str, Any]]:
        """
        Extract granular chunks from a page range of the document.
        Creates smaller, type-classified chunks instead of full-page chunks.
        
        Args:
            document: The UploadedDocument instance
            start_page: Starting page (0-based)
            end_page: Ending page (0-based)
            
        Returns:
            List of enhanced chunk dictionaries with granular content
        """
        doc = None
        temp_pdf = None
        temp_path = None
        
        try:
            # Open the PDF and validate page range
            doc = fitz.open(document.file.path)
            total_pages = len(doc)
            
            # Ensure pages are within document bounds
            start_page = max(0, min(start_page, total_pages - 1))
            end_page = max(start_page, min(end_page, total_pages - 1))
            
            print(f"   📄 Extracting granular chunks from pages {start_page+1}-{end_page+1}")
            
            # Create a temporary PDF with the content pages
            temp_pdf = fitz.open()
            for page_num in range(start_page, end_page + 1):
                if page_num < total_pages:
                    temp_pdf.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            if len(temp_pdf) == 0:
                print(f"   ⚠️  No valid pages to process")
                return []
            
            # Create temporary file with proper cleanup
            temp_fd, temp_path = tempfile.mkstemp(suffix='.pdf')
            try:
                os.close(temp_fd)  # Close file descriptor immediately
                temp_pdf.save(temp_path)
                
                print(f"   🔧 Processing {len(temp_pdf)} pages with granular chunking")
                print("   🔗 Note: PDF link warnings below are handled automatically - content extraction will proceed normally")
                
                # Extract granular chunks using enhanced chunking
                raw_chunks = extract_unstructured_chunks(temp_path)
                print(f"   📝 Extracted {len(raw_chunks)} granular chunks")
                
                if not raw_chunks:
                    print(f"   ⚠️  No content extracted")
                    return []
                
                # Filter out sample placeholder content and enhance chunks
                valid_chunks = []
                sample_chunks_filtered = 0
                pages_per_chunk = max(1, (end_page - start_page + 1) / max(1, len(raw_chunks)))
                
                for chunk_idx, chunk in enumerate(raw_chunks):
                    if self._is_sample_placeholder_content(chunk['text']):
                        sample_chunks_filtered += 1
                        continue
                    
                    # Better page mapping based on chunk position
                    estimated_page = start_page + int(chunk_idx * pages_per_chunk)
                    chunk_page = min(estimated_page, end_page)
                    
                    enhanced_chunk = {
                        'text': chunk['text'],
                        'chunk_type': chunk['chunk_type'],
                        'page_number': chunk_page,
                        'order_in_doc': chunk_idx,
                    }
                    valid_chunks.append(enhanced_chunk)
                
                if sample_chunks_filtered > 0:
                    print(f"   📊 Filtered {sample_chunks_filtered} sample chunks, kept {len(valid_chunks)} valid chunks")
                
                return valid_chunks
                
            finally:
                # Clean up temporary file
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
                        
        except Exception as e:
            print(f"   ❌ Error extracting granular chunks: {str(e)}")
            return []
        finally:
            if temp_pdf:
                temp_pdf.close()
            if doc:
                doc.close()
    
    def _save_granular_chunks(self, document: UploadedDocument, chunks: List[Dict[str, Any]]) -> int:
        """
        Save granular chunks to the database.
        
        Args:
            document: The UploadedDocument instance
            chunks: List of chunk dictionaries to save
            
        Returns:
            Number of chunks saved
        """
        saved_count = 0
        
        with transaction.atomic():
            for chunk in chunks:
                try:
                    # Count tokens in the chunk text
                    token_count = self.token_counter.count_tokens(chunk['text'])
                    
                    DocumentChunk.objects.create(
                        document=document,
                        chunk_type=chunk['chunk_type'],
                        text=chunk['text'],
                        page_number=chunk['page_number'],
                        order_in_doc=chunk['order_in_doc'],
                        token_count=token_count,
                    )
                    saved_count += 1
                except Exception as e:
                    print(f"   ⚠️ Error saving chunk {chunk['order_in_doc']}: {str(e)}")
                    continue
        
        return saved_count
