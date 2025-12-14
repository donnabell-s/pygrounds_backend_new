import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from unstructured.partition.pdf import partition_pdf
from unstructured.chunking.title import chunk_by_title
from unstructured.cleaners.core import clean_extra_whitespace

from .chunk_classifier import infer_chunk_type
from .text_cleaner import clean_raw_text, clean_chunk_text
from .cross_page_merger import enhance_cross_page_chunking

logger = logging.getLogger(__name__)


def extract_unstructured_chunks(file_path):
    # Extract chunks via `unstructured` and classify for coding vs conceptual content.
    import tempfile
    import os
    
    # Use context manager for better temp file handling
    temp_dir = None
    try:
        print(f"Starting unstructured processing for {file_path}")
        print("📋 Analyzing PDF structure and extracting content elements...")
        
        # Create a temporary directory for unstructured library to use
        temp_dir = tempfile.mkdtemp(prefix='unstructured_')
        
        # Set environment variable for unstructured to use our temp directory
        old_tmpdir = os.environ.get('TMPDIR')
        os.environ['TMPDIR'] = temp_dir
        
        try:
            # Partition the PDF
            elements = partition_pdf(
                filename=file_path,
                extract_images_in_pdf=False,
                infer_table_structure=True,
                chunking_strategy="by_title",
                max_characters=1000,  # Increased for better context
                new_after_n_chars=800,  # Adaptive chunking
                combine_text_under_n_chars=200,  # Combine small fragments
                overlap=50
            )
        finally:
            # Restore original TMPDIR
            if old_tmpdir:
                os.environ['TMPDIR'] = old_tmpdir
            elif 'TMPDIR' in os.environ:
                del os.environ['TMPDIR']
        
        print(f"✅ Successfully extracted {len(elements)} elements from PDF")
        print("📝 Note: Any 'skipping bad link/annot' messages above are normal - corrupted PDF links are automatically handled")
        
        # Process elements into chunks
        processed_chunks = []
        
        for i, element in enumerate(elements):
            text = str(element)
            
            if not text or len(text.strip()) < 10:  # Skip very short chunks
                continue
            
            # Clean the raw text first
            cleaned_text = clean_raw_text(text)
            
            if not cleaned_text or len(cleaned_text.strip()) < 10:
                continue
            
            # Infer the chunk type using our enhanced classifier
            chunk_type = infer_chunk_type(cleaned_text)
            
            # Determine adaptive max_characters based on content type
            if chunk_type in ['Code', 'Try_It', 'Exercise', 'Example']:
                # Coding content needs more context
                target_length = 600
                context_preservation = True
            else:  # Concept
                # Conceptual content can be more concise
                target_length = 400
                context_preservation = True
            
            # Further clean the text with context preservation
            final_cleaned_text = clean_chunk_text(cleaned_text)
            
            if not final_cleaned_text or len(final_cleaned_text.strip()) < 10:
                continue
            
            # Create contextual chunk based on type
            # For now, we'll use basic context since we don't have subtopic info in this function
            # This could be enhanced when integrated with document structure parsing
            contextual_text = _create_basic_context(final_cleaned_text, chunk_type)
            
            # Store the processed chunk with page information for cross-page merging
            chunk_data = {
                'text': contextual_text,
                'chunk_type': chunk_type,
                'element_type': str(type(element).__name__),
                'sequence_number': i,
                'page_number': getattr(element.metadata, 'page_number', i // 10) if hasattr(element, 'metadata') else i // 10,  # Estimate page if not available
                'original_length': len(text),
                'processed_length': len(contextual_text),
                'target_length': target_length
            }
            
            processed_chunks.append(chunk_data)
        
        print(f"Processed {len(processed_chunks)} initial chunks")
        
        # Apply cross-page merging to handle split content
        final_chunks = enhance_cross_page_chunking(processed_chunks)
        
        # Log final chunk type distribution
        chunk_types = {}
        for chunk in final_chunks:
            chunk_type = chunk['chunk_type']
            chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
        
        print(f"Final chunk type distribution: {chunk_types}")
        
        return final_chunks
        
    except Exception as e:
        logger.error(f"Error in extract_unstructured_chunks: {str(e)}")
        print(f"Error processing {file_path}: {str(e)}")
        return []
    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                import shutil
                shutil.rmtree(temp_dir)
                print(f"🧹 Cleaned up temporary directory: {temp_dir}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup temp directory {temp_dir}: {cleanup_error}")
                print(f"⚠️  Warning: Failed to cleanup temp directory: {cleanup_error}")


def _create_basic_context(text: str, chunk_type: str) -> str:
    # Basic context hook (no-op): chunk_type already carries type info.
    return text


def get_chunk_statistics(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Stats for analysis/debugging.
    if not chunks:
        return {}
    
    chunk_types = {}
    total_original_length = 0
    total_processed_length = 0
    
    for chunk in chunks:
        chunk_type = chunk.get('chunk_type', 'Unknown')
        chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
        total_original_length += chunk.get('original_length', 0)
        total_processed_length += chunk.get('processed_length', 0)
    
    return {
        'total_chunks': len(chunks),
        'chunk_type_distribution': chunk_types,
        'total_original_length': total_original_length,
        'total_processed_length': total_processed_length,
        'compression_ratio': total_processed_length / total_original_length if total_original_length > 0 else 0,
        'average_chunk_length': total_processed_length / len(chunks) if chunks else 0
    }
