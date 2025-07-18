from .toc_utils import extract_toc, fallback_toc_text, parse_toc_text, assign_end_pages
import fitz
from typing import List, Dict, Any
from content_ingestion.models import *
from ..page_chunking.toc_chunk_processor import TOCBasedChunkProcessor

def generate_toc_entries_for_document(document, skip_nlp=False, fast_mode=True):
    """
    Generate TOC entries for a document with optional performance optimizations.
    
    Args:
        document: UploadedDocument instance
        skip_nlp: Skip topic matching entirely for fastest processing
        fast_mode: Use fast keyword matching instead of NLP
    """
    print(f"\n[DEBUG] Starting TOC generation for {document.title}")
    if skip_nlp:
        print("[DEBUG] NLP matching disabled for faster processing")
    
    try:
        # Open document to get total pages
        doc = fitz.open(document.file.path)
        total_pages = len(doc)
        print(f"[DEBUG] Document has {total_pages} pages")
        
        # Try metadata-based TOC first
        toc_data = extract_toc(document.file.path)
        print(f"[DEBUG] Metadata TOC extraction result: {toc_data}")
        
        if not toc_data:
            print("[DEBUG] No metadata TOC found, trying fallback method")
            toc_pages = fallback_toc_text(doc)
            print(f"[DEBUG] Fallback TOC pages found: {len(toc_pages)}")
            toc_data = []
            
            # Combine all TOC pages into one text block for cross-page parsing
            combined_toc_text = "\n".join(toc_pages)
            page_entries = parse_toc_text(combined_toc_text)
            print(f"[DEBUG] Parsed TOC entries from combined pages: {len(page_entries)}")
            toc_data.extend(page_entries)
        
        # Close document early to free memory
        doc.close()

        if not toc_data:
            print("[DEBUG] No TOC data found")
            # Update document with total pages even if no TOC
            document.total_pages = total_pages
            document.processing_status = 'COMPLETED'
            document.save()
            return []

        # Assign end pages
        toc_data = assign_end_pages(toc_data, total_pages)
        print(f"[DEBUG] Assigned end pages to {len(toc_data)} entries")

        # Initialize fast topic matcher (only if we have game content)
        matcher = None
        if not skip_nlp:
            try:
                from .topic_matching import FastTopicMatcher
                from content_ingestion.models import Subtopic, Topic
                
                # Check if we have any game content to match against
                has_game_content = Subtopic.objects.exists() or Topic.objects.exists()
                if has_game_content:
                    matcher = FastTopicMatcher()
                    print("[DEBUG] Fast keyword matcher initialized")
                else:
                    print("[DEBUG] No game content found, skipping topic matching")
            except Exception as e:
                print(f"[DEBUG] Failed to initialize fast matcher: {str(e)}")
        else:
            print("[DEBUG] Topic matching disabled by request")
        
        # Create TOC entries with optional topic mapping
        entries = []
        content_mappings = []
        
        print(f"[DEBUG] Creating {len(toc_data)} TOC entries...")
        
        # Overwrite any existing TOC entries for this document
        TOCEntry.objects.filter(document=document).delete()
        toc_entries_to_create = []
        for idx, entry_data in enumerate(toc_data):
            toc_entries_to_create.append(TOCEntry(
                document=document,
                title=entry_data['title'],
                start_page=entry_data['start_page'],
                end_page=entry_data.get('end_page'),
                level=entry_data.get('level', 0),
                order=idx
            ))
        entries = TOCEntry.objects.bulk_create(toc_entries_to_create)
        print(f"[DEBUG] Created {len(entries)} TOC entries in bulk")
        
        # Now do topic matching in batches (if enabled)
        if matcher and entries:
            print(f"[DEBUG] Starting fast topic matching for {len(entries)} entries...")
            
            matched_entries = []
            for idx, entry in enumerate(entries):
                try:
                    mapping_data = matcher.create_content_mapping(entry)
                    if mapping_data['confidence_score'] >= 0.2:  # Lower threshold for fast matching
                        content_mappings.append(ContentMapping(**mapping_data))
                        matched_entries.append(entry)
                        print(f"[FAST] {idx+1}/{len(entries)}: Mapped '{entry.title}' -> {mapping_data['confidence_score']:.3f}")
                    else:
                        print(f"[FAST] {idx+1}/{len(entries)}: No match for '{entry.title}' (best: {mapping_data['confidence_score']:.3f})")
                except Exception as e:
                    print(f"[DEBUG] Fast matching error for '{entry.title}': {str(e)}")
                    
                # Progress indicator
                if (idx + 1) % 10 == 0:
                    print(f"[DEBUG] Topic matching progress: {idx + 1}/{len(entries)}")
            
            # Bulk create content mappings
            if content_mappings:
                ContentMapping.objects.bulk_create(content_mappings)
                print(f"[DEBUG] Created {len(content_mappings)} content mappings in bulk")
            
            # Return only matched entries
            entries = matched_entries
            print(f"[DEBUG] Filtered to {len(entries)} matched entries only")
        else:
            print("[DEBUG] Skipping topic matching")
            # If no matching, return empty list to only get relevant entries
            entries = []
        
        # Update document with total pages and status
        document.total_pages = total_pages
        document.processing_status = 'COMPLETED'
        document.save()
            
        print(f"\n[DEBUG] Final entries count: {len(entries)}")
        return entries
        
    except Exception as e:
        print(f"[DEBUG] Error in TOC generation: {str(e)}")
        raise


def generate_and_chunk_document(document, include_chunking=True, skip_nlp=False, fast_mode=True) -> Dict[str, Any]:
    """
    Complete pipeline: Generate TOC entries, match topics, and create chunks for RAG.
    
    Args:
        document: UploadedDocument instance
        include_chunking: Whether to process matched entries for chunking
        skip_nlp: Skip topic matching entirely
        fast_mode: Use fast keyword matching instead of NLP
    
    Returns:
        Dictionary with processing results including chunking stats
    """
    print(f"\n🚀 STARTING COMPLETE DOCUMENT PROCESSING")
    print(f"{'='*80}")
    print(f"Document: {document.title}")
    print(f"Include Chunking: {include_chunking}")
    print(f"Fast Mode: {fast_mode}")
    
    results = {
        'toc_stats': {},
        'matching_stats': {},
        'chunking_stats': {},
        'matched_entries': [],
        'total_processing_time': 0
    }
    
    try:
        # Step 1: Generate TOC entries and match topics
        print(f"\n📑 STEP 1: TOC Generation & Topic Matching")
        print(f"{'─'*50}")
        
        matched_entries = generate_toc_entries_for_document(
            document=document,
            skip_nlp=skip_nlp,
            fast_mode=fast_mode
        )
        
        results['toc_stats'] = {
            'matched_entries_count': len(matched_entries),
            'total_entries_found': TOCEntry.objects.filter(document=document).count()
        }
        
        results['matched_entries'] = [
            {
                'id': entry.id,
                'title': entry.title,
                'start_page': entry.start_page + 1,  # Human readable (1-based)
                'end_page': (entry.end_page + 1) if entry.end_page else None,
                'level': entry.level
            }
            for entry in matched_entries
        ]
        
        print(f"✅ TOC Processing Complete:")
        print(f"   • Total entries found: {results['toc_stats']['total_entries_found']}")
        print(f"   • Matched entries: {results['toc_stats']['matched_entries_count']}")
        
        # Step 2: Process chunks for matched entries (if enabled)
        if include_chunking and matched_entries:
            print(f"\n🔧 STEP 2: Chunk Processing")
            print(f"{'─'*50}")
            
            chunk_processor = TOCBasedChunkProcessor()
            chunking_results = chunk_processor.process_matched_entries(document, matched_entries)
            
            results['chunking_stats'] = {
                'entries_processed': chunking_results['total_entries_processed'],
                'entries_skipped_sample_only': chunking_results['entries_skipped_sample_only'],
                'chunks_created': chunking_results['total_chunks_created'],
                'pages_processed': chunking_results['total_pages_processed'],
                'sample_content_filtered': chunking_results['sample_content_filtered'],
                'entries_details': chunking_results['entries_details']
            }
            
            print(f"✅ Chunking Complete:")
            print(f"   • Entries processed: {results['chunking_stats']['entries_processed']}")
            if chunking_results['entries_skipped_sample_only'] > 0:
                print(f"   • Entries skipped (sample-only): {results['chunking_stats']['entries_skipped_sample_only']}")
            print(f"   • Total chunks created: {results['chunking_stats']['chunks_created']}")
            print(f"   • Pages with consolidated chunks: {results['chunking_stats']['pages_processed']}")
            if chunking_results['sample_content_filtered'] > 0:
                print(f"   • Sample content chunks filtered: {results['chunking_stats']['sample_content_filtered']}")
            
        elif not include_chunking:
            print(f"\n⏭️  STEP 2: Chunking Skipped (disabled)")
            results['chunking_stats'] = {'status': 'skipped', 'reason': 'chunking_disabled'}
        else:
            print(f"\n⏭️  STEP 2: Chunking Skipped (no matched entries)")
            results['chunking_stats'] = {'status': 'skipped', 'reason': 'no_matched_entries'}
        
        # Step 3: Update document status
        document.processing_status = 'CHUNKED' if include_chunking else 'COMPLETED'
        document.save()
        
        print(f"\n🎉 PROCESSING COMPLETE")
        print(f"{'='*80}")
        print(f"Document Status: {document.processing_status}")
        
        return results
        
    except Exception as e:
        print(f"\n❌ ERROR IN DOCUMENT PROCESSING: {str(e)}")
        document.processing_status = 'ERROR'
        document.save()
        raise

 