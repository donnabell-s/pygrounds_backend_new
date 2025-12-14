from .toc_utils import extract_toc, fallback_toc_text, parse_toc_text, assign_end_pages
import fitz
from typing import List, Dict, Any
from content_ingestion.models import TOCEntry

def generate_toc_entries_for_document(document):
    # Extract TOC entries from a PDF (metadata or fallback) and bulk save them.
    print(f"\n[TOC] Generating TOC entries for: {document.title}")

    try:
        doc = fitz.open(document.file.path)
        total_pages = len(doc)
        print(f"[TOC] PDF has {total_pages} pages")

        # 1. Try metadata-based TOC extraction
        toc_data = extract_toc(document.file.path)
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
            print(f"[TOC] Extracted {len(toc_data)} TOC entries from metadata")
        else:
            # 2. Fallback: Manual TOC parsing from first pages
            print("[TOC] No metadata TOC, using manual extraction")
            toc_pages = fallback_toc_text(doc)
            combined_toc_text = "\n".join(toc_pages)
            toc_data = parse_toc_text(combined_toc_text)
            print(f"[TOC] Parsed {len(toc_data)} TOC entries from fallback text")

        doc.close()

        if not toc_data:
            print("[TOC] No TOC entries found. Marking document complete.")
            document.total_pages = total_pages
            document.status = 'COMPLETED'
            document.save()
            return []

        # 3. Assign end pages for chunking
        toc_data = assign_end_pages(toc_data, total_pages)

        # 4. Remove old TOC entries for this document
        TOCEntry.objects.filter(document=document).delete()

        # 5. Bulk-create new TOC entries
        toc_entries = [
            TOCEntry(
                document=document,
                title=entry['title'],
                start_page=entry['start_page'],
                end_page=entry['end_page'],
                level=entry.get('level', 0),
                order=entry.get('order', idx),
            )
            for idx, entry in enumerate(toc_data)
        ]
        created = TOCEntry.objects.bulk_create(toc_entries)
        print(f"[TOC] Created {len(created)} TOC entries")

        # 6. Update document meta/status
        document.total_pages = total_pages
        document.status = 'COMPLETED'
        document.save()

        print(f"[TOC] All done! Entries ready for chunking: {len(created)}")
        return created

    except Exception as e:
        print(f"[TOC] Error during TOC generation: {str(e)}")
        raise
