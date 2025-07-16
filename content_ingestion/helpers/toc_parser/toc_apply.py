from question_generation.models import TOCEntry as DBTOCEntry, UploadedDocument
from .toc_utils import extract_toc, fallback_toc_text, parse_toc_text, assign_end_pages
import fitz
from typing import List
from question_generation.models import *

def generate_toc_entries_for_document(document):
    print(f"\n[DEBUG] Starting TOC generation for {document.title}")
    try:
        # Try metadata-based TOC first
        toc_data = extract_toc(document.file.path)
        print(f"[DEBUG] Metadata TOC extraction result: {toc_data}")
        
        if not toc_data:
            print("[DEBUG] No metadata TOC found, trying fallback method")
            # Try fallback method
            doc = fitz.open(document.file.path)
            toc_pages = fallback_toc_text(doc)
            print(f"[DEBUG] Fallback TOC pages found: {len(toc_pages)}")
            
            if toc_pages:
                toc_text = toc_pages[0]  # Use first page with TOC-like content
                print(f"[DEBUG] TOC text sample: {toc_text[:200]}...")  # Print first 200 chars
                toc_data = parse_toc_text(toc_text)
                print(f"[DEBUG] Parsed TOC entries: {len(toc_data)}")

        # Create TOC entries
        entries = []
        for idx, entry_data in enumerate(toc_data):
            print(f"[DEBUG] Processing entry: {entry_data}")
            entry = TOCEntry.objects.create(
                document=document,
                title=entry_data['title'],
                start_page=entry_data['start_page'],
                level=entry_data.get('level', 0),
                order=idx
            )
            entries.append(entry)
            
        # Assign end pages
        if entries:
            assign_end_pages(entries)
            
        print(f"[DEBUG] Final entries count: {len(entries)}")
        return entries
        
    except Exception as e:
        print(f"[DEBUG] Error in TOC generation: {str(e)}")
        raise
 