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
import logging

logger = logging.getLogger(__name__)

class GranularChunkProcessor:
    # create granular, type-classified chunks for rag
    
    def __init__(self, enable_embeddings: bool = True):
        self.batch_size = 50
        self.enable_embeddings = enable_embeddings
        self.embedding_generator = EmbeddingGenerator() if enable_embeddings else None
        self.token_counter = TokenCounter()
        
        self.sample_content_indicators = [
            "This is a sample from",
            "With the full version of the book you get",
            "purchase a full version",
            "If you enjoyed the sample chapters",
            "Python Basics: A Practical Introduction to Python 3"
        ]
    
    def _get_toc_titles_for_page(self, document: UploadedDocument, page_number: int) -> tuple[str, str]:
        try:
            toc_entries = TOCEntry.objects.filter(document=document).order_by('start_page')
            
            current_entry = None
            for entry in toc_entries:
                if entry.start_page <= page_number <= (entry.end_page or entry.start_page):
                    current_entry = entry
                    break
            
            if not current_entry:
                for entry in toc_entries.reverse():
                    if entry.start_page <= page_number:
                        current_entry = entry
                        break
            
            if not current_entry:
                return "", ""
            
            if current_entry.level == 0:
                topic_title = self._clean_toc_title(current_entry.title)
                subtopic_title = ""
            else:
                topic_title = ""
                subtopic_title = self._clean_toc_title(current_entry.title)
                
                parent_entries = toc_entries.filter(
                    level=0, 
                    start_page__lte=current_entry.start_page
                ).order_by('-start_page')
                
                if parent_entries.exists():
                    topic_title = self._clean_toc_title(parent_entries.first().title)
            
            return topic_title, subtopic_title
            
        except Exception as e:
            print(f"   WARN: Error getting TOC titles for page {page_number}: {e}")
            return "", ""
    
    def _clean_toc_title(self, title: str) -> str:
        if not title:
            return ""
        
        title = re.sub(r'^\d+\.?\d*\s*', '', title)
        
        title = re.sub(r'\s*\.+\s*\d*\s*$', '', title)
        title = re.sub(r'\s*\.+\s*$', '', title)
        
        title = re.sub(r'\s+', ' ', title).strip()
        
        return title

    def _analyze_token_distribution(self, document: UploadedDocument) -> Dict[str, Any]:
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
            
            chunk_type = chunk.chunk_type
            if chunk_type not in chunk_types:
                chunk_types[chunk_type] = {'count': 0, 'tokens': 0}
            chunk_types[chunk_type]['count'] += 1
            chunk_types[chunk_type]['tokens'] += token_count
        
        if not token_counts:
            return {"error": "No token data available"}
        
        total_tokens = sum(token_counts)
        avg_tokens = total_tokens / len(token_counts) if token_counts else 0
        
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
        }

    def _get_toc_content_boundaries(self, document: UploadedDocument) -> tuple[int, int]:
        toc_entries = TOCEntry.objects.filter(document=document).order_by('start_page')
        
        if not toc_entries.exists():
            raise ValueError("No TOC entries found for document")
        
        first_toc_page = toc_entries.first().start_page - 1
        last_toc_page = toc_entries.last().end_page - 1 if toc_entries.last().end_page else toc_entries.last().start_page - 1
        
        educational_entries = toc_entries.filter(
            title__iregex=r'^\d+\.?\d*\s+'
        )
        
        if educational_entries.exists():
            first_educational_page = educational_entries.first().start_page - 1
            print(f"Found educational content starting at page {first_educational_page + 1}: '{educational_entries.first().title}'")
            first_content_page = first_educational_page
        else:
            first_content_page = first_toc_page
            print(f"No numbered sections found, using first TOC entry at page {first_content_page + 1}")
        
        last_content_page = last_toc_page
        
        print(f"TOC-based content boundaries: pages {first_content_page + 1}-{last_content_page + 1}")
        return first_content_page, last_content_page

    def process_entire_document(self, document: UploadedDocument) -> Dict[str, Any]:
        results = {
            'total_chunks_created': 0,
            'total_pages_processed': 0,
            'content_boundaries': None,
            'sample_content_filtered': 0,
            'chunk_types_distribution': {},
        }
        
        print(f"Document: {document.title}")
        print(f"Document total pages: {document.total_pages}")
        
        existing_chunks_count = DocumentChunk.objects.filter(document=document).count()
        if existing_chunks_count > 0:
            print(f"Clearing {existing_chunks_count} existing chunks for clean reprocessing...")
            DocumentChunk.objects.filter(document=document).delete()
            print(f"Cleared all existing chunks")
        
        doc = None
        try:
            doc = fitz.open(document.file.path)
            
            try:
                first_page, last_page = self._get_toc_content_boundaries(document)
                results['content_boundaries'] = (first_page + 1, last_page + 1)
                print(f" Processing TOC-defined content pages: {first_page + 1}-{last_page + 1}")
            except Exception as e:
                print(f"Could not determine TOC boundaries, falling back to heuristic: {e}")
                first_page, last_page = find_content_boundaries(document.file.path)
                results['content_boundaries'] = (first_page + 1, last_page + 1)
                print(f"Processing heuristic content pages: {first_page + 1}-{last_page + 1}")
            
            chunks = self._extract_granular_chunks_from_range(doc, document, first_page, last_page)
            
            if not chunks:
                print(f"No chunks extracted from content area")
                return results
            
            chunk_count = self._save_granular_chunks(document, chunks)
            results['total_chunks_created'] = chunk_count
            results['total_pages_processed'] = last_page - first_page + 1
            
            for chunk in chunks:
                chunk_type = chunk['chunk_type']
                results['chunk_types_distribution'][chunk_type] = results['chunk_types_distribution'].get(chunk_type, 0) + 1
            
            print(f"Created {chunk_count} granular chunks")
            print(f"Chunk types: {results['chunk_types_distribution']}")
            
        except Exception as e:
            print(f"ERROR: Error processing document content: {str(e)}")
            logger.error(f"Error in process_entire_document: {str(e)}")
            return results
        finally:
            if doc:
                doc.close()
        
        embedding_results = self._generate_embeddings_for_document(document)
        results['embedding_stats'] = embedding_results
        
        token_analysis = self._analyze_token_distribution(document)
        results['token_analysis'] = token_analysis
        
        print(f"\nPROCESSING COMPLETE")
        print(f"{'-'*60}")
        print(f"Total chunks created: {results['total_chunks_created']}")
        print(f"Pages processed: {results['total_pages_processed']}")
        if results['sample_content_filtered'] > 0:
            print(f"Sample content chunks filtered: {results['sample_content_filtered']}")
        total_processed = embedding_results.get('success', 0) + embedding_results.get('failed', 0)
        if total_processed > 0:
            print(f"Embeddings generated: {embedding_results.get('success', 0)}/{total_processed}")
        if 'total_tokens' in token_analysis:
            print(f"Total tokens: {token_analysis['total_tokens']} (avg: {token_analysis['avg_tokens_per_chunk']} per chunk)")
        
        return results

    def _generate_embeddings_for_document(self, document: UploadedDocument) -> Dict[str, Any]:
        if not self.enable_embeddings or not self.embedding_generator:
            return {'success': 0, 'failed': 0, 'total': 0, 'status': 'disabled'}
        
        print(f"\nGENERATING EMBEDDINGS")
        print(f"{'-'*40}")
        
        chunks_to_embed = DocumentChunk.objects.filter(
            document=document,
            embeddings__isnull=True
        )
        
        if not chunks_to_embed.exists():
            print(f"All chunks already have embeddings")
            return {'success': 0, 'failed': 0, 'total': 0, 'status': 'already_embedded'}
        
        print(f"Found {chunks_to_embed.count()} chunks to embed")
        
        embedding_results = self.embedding_generator.embed_and_save_batch(chunks_to_embed)
        
        total_processed = embedding_results.get('success', 0) + embedding_results.get('failed', 0)
        print(f"Embedding complete: {embedding_results.get('success', 0)}/{total_processed} successful")
        
        return embedding_results
    
    def _is_sample_placeholder_content(self, text: str) -> bool:
        if not text or len(text.strip()) < 50:
            return False
            
        indicator_count = 0
        text_lower = text.lower()
        
        for indicator in self.sample_content_indicators:
            if indicator.lower() in text_lower:
                indicator_count += 1
        
        if indicator_count >= 2:
            return True
            
        if len(text.strip()) < 800 and any(indicator.lower() in text_lower for indicator in self.sample_content_indicators[:3]):
            return True
            
        return False

    def _extract_granular_chunks_from_range(self, doc: fitz.Document, document: UploadedDocument, start_page: int, end_page: int) -> List[Dict[str, Any]]:
        temp_pdf = None
        temp_path = None
        
        try:
            total_pages = len(doc)
            
            start_page = max(0, min(start_page, total_pages - 1))
            end_page = max(start_page, min(end_page, total_pages - 1))
            
            print(f"   Extracting granular chunks from pages {start_page+1}-{end_page+1}")
            
            temp_pdf = fitz.open()
            for page_num in range(start_page, end_page + 1):
                if page_num < total_pages:
                    temp_pdf.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            if len(temp_pdf) == 0:
                print(f"   No valid pages to process")
                return []
            
            temp_fd, temp_path = tempfile.mkstemp(suffix='.pdf')
            try:
                os.close(temp_fd)
                temp_pdf.save(temp_path)
                
                print(f"   Processing {len(temp_pdf)} pages with granular chunking")
                print("   Note: PDF link warnings below are handled automatically - content extraction will proceed normally")
                
                raw_chunks = extract_unstructured_chunks(temp_path)
                print(f"   Extracted {len(raw_chunks)} granular chunks")
                
                if not raw_chunks:
                    print(f"   WARN: No content extracted")
                    return []
                
                valid_chunks = []
                sample_chunks_filtered = 0
                pages_per_chunk = max(1, (end_page - start_page + 1) / max(1, len(raw_chunks)))
                
                for chunk_idx, chunk in enumerate(raw_chunks):
                    if self._is_sample_placeholder_content(chunk['text']):
                        sample_chunks_filtered += 1
                        continue
                    
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
                    print(f"   Filtered {sample_chunks_filtered} sample chunks, kept {len(valid_chunks)} valid chunks")
                
                return valid_chunks
                
            except Exception as e:
                logger.error(f"Error in granular chunking: {str(e)}")
                print(f"   ERROR: Error in granular chunking: {str(e)}")
                return []
            finally:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                        print(f"   Cleaned up temp file: {os.path.basename(temp_path)}")
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup temp file {temp_path}: {cleanup_error}")
                        print(f"   WARN: Failed to cleanup temp file: {cleanup_error}")
                
                if 'temp_pdf' in locals():
                    try:
                        temp_pdf.close()
                    except (OSError, Exception):
                        pass
                        
        except Exception as e:
            print(f"   ERROR: Error extracting granular chunks: {str(e)}")
            return []

    def _save_granular_chunks(self, document: UploadedDocument, chunks: List[Dict[str, Any]]) -> int:
        saved_count = 0
        total_chunks = len(chunks)
        
        print(f"   Saving {total_chunks} chunks to database...")
        
        with transaction.atomic():
            for chunk in chunks:
                try:
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
                    
                    if saved_count % 500 == 0:
                        print(f"   Saved {saved_count}/{total_chunks} chunks...")
                        
                except Exception as e:
                    print(f"   ERROR: Error saving chunk {chunk.get('order_in_doc', 'unknown')}: {str(e)}")
                    logger.error(f"Chunk save error: {str(e)}")
                    raise e
        
        print(f"   Successfully saved {saved_count}/{total_chunks} chunks to database")
        return saved_count
