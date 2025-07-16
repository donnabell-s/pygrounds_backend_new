from .toc_utils import extract_toc, fallback_toc_text, parse_toc_text, assign_end_pages
import fitz
from typing import List
from content_ingestion.models import *

def generate_toc_entries_for_document(document, skip_nlp=False):
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
            # Try fallback method
            toc_pages = fallback_toc_text(doc)
            print(f"[DEBUG] Fallback TOC pages found: {len(toc_pages)}")
            
            if toc_pages:
                toc_text = toc_pages[0]  # Use first page with TOC-like content
                print(f"[DEBUG] TOC text sample: {toc_text[:200]}...")
                toc_data = parse_toc_text(toc_text)
                print(f"[DEBUG] Parsed TOC entries: {len(toc_data)}")
        
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

        # Initialize topic matcher (only if we have game content and NLP is enabled)
        matcher = None
        if not skip_nlp:
            try:
                from ..topic_matching import TopicMatcher
                from content_ingestion.models import Subtopic, Topic
                
                # Check if we have any game content to match against
                has_game_content = Subtopic.objects.exists() or Topic.objects.exists()
                if has_game_content:
                    matcher = TopicMatcher()
                    print("[DEBUG] NLP matcher initialized")
                else:
                    print("[DEBUG] No game content found, skipping NLP matching")
            except Exception as e:
                print(f"[DEBUG] Failed to initialize NLP matcher: {str(e)}")
        else:
            print("[DEBUG] NLP matching disabled by request")
        
        # Create TOC entries with optional topic mapping
        entries = []
        batch_size = 20  # Process in batches to avoid timeouts
        
        for idx, entry_data in enumerate(toc_data):
            print(f"\n[DEBUG] Processing entry {idx + 1}/{len(toc_data)}: {entry_data['title']}")
            
            # Create TOC entry
            entry = TOCEntry.objects.create(
                document=document,
                title=entry_data['title'],
                start_page=entry_data['start_page'],
                end_page=entry_data.get('end_page'),
                level=entry_data.get('level', 0),
                order=idx
            )
            
            # Try to map to topics/subtopics (only if matcher is available)
            if matcher:
                try:
                    mapping_data = matcher.create_content_mapping(entry)
                    if mapping_data['confidence_score'] >= 0.3:
                        ContentMapping.objects.create(**mapping_data)
                        print(f"[DEBUG] Mapped with confidence: {mapping_data['confidence_score']:.2f}")
                    else:
                        print(f"[DEBUG] No confident mapping (best: {mapping_data['confidence_score']:.2f})")
                except Exception as e:
                    print(f"[DEBUG] NLP mapping error: {str(e)}")
            else:
                print("[DEBUG] Skipping NLP mapping")
            
            entries.append(entry)
            
            # Process in batches to avoid memory issues
            if (idx + 1) % batch_size == 0:
                print(f"[DEBUG] Processed batch {idx + 1}/{len(toc_data)}")
                # Clear any cached NLP data
                if matcher and hasattr(matcher, '_text_cache'):
                    matcher._text_cache.clear()
            
        # Update document with total pages and status
        document.total_pages = total_pages
        document.processing_status = 'COMPLETED'
        document.save()
            
        print(f"\n[DEBUG] Final entries count: {len(entries)}")
        return entries
        
    except Exception as e:
        print(f"[DEBUG] Error in TOC generation: {str(e)}")
        raise
 