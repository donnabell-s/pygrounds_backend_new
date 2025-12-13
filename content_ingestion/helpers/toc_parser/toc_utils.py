import fitz  # PyMuPDF
import re
import warnings
import os
import sys
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

# Suppress PyMuPDF warnings about bad annotations/links
warnings.filterwarnings("ignore", message=".*bad link.*")
warnings.filterwarnings("ignore", message=".*annot item.*")

# Try to suppress PyMuPDF C-level warnings by redirecting stderr temporarily
def suppress_stderr():
    # Context manager to suppress stderr output temporarily.
    class DevNull:
        def write(self, msg):
            pass
        def flush(self):
            pass
    
    return DevNull()

# Configure PyMuPDF to be less verbose if possible
try:
    # Some versions of PyMuPDF support setting verbosity
    if hasattr(fitz, 'TOOLS'):
        fitz.TOOLS.mupdf_display_errors(False)
except:
    pass

@dataclass
class TOCEntry:
    # Single entry in the Table of Contents.
    title: str
    start_page: int
    end_page: Optional[int] = None
    level: int = 0
    children: List['TOCEntry'] = field(default_factory=list)

def find_content_boundaries(pdf_path: str) -> Tuple[int, int]:
    # Return (first_content_page, last_content_page) in 0-based indexing.
    # Skips preface/TOC/appendices by keyword; prioritizes "Chapter 1" as content start.
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        # Primary content start indicators (strongest signals)
        primary_start_keywords = [
            'chapter 1', 'chapter one', 'chapter i',
            'lesson 1', 'unit 1', 'module 1'
        ]
        
        # Secondary content indicators
        secondary_start_keywords = [
            'introduction to python', 'getting started',
            'python basics', 'fundamentals', 'variables',
            'data types', 'functions', 'loops', 'programming'
        ]
        
        # Pages to definitely skip
        skip_keywords = [
            'table of contents', 'contents', 'preface', 'foreword', 'acknowledgments',
            'about the author', 'about this book', 'copyright', 'isbn', 'dedication',
            'index', 'bibliography', 'references', 'glossary', 'about packt',
            'appendix', 'answer key', 'solutions', 'toc', 'title page', 'cover'
        ]

        first_content = 0
        last_content = total_pages - 1

        # Detect start - prioritize "Chapter 1" detection
        found_chapter_1 = False
        for page_num in range(min(50, total_pages)):  # Check more pages for chapter 1
            try:
                page = doc.load_page(page_num)
                text = page.get_text().lower()
                
                # Skip pages that are clearly TOC or metadata
                if any(word in text for word in skip_keywords):
                    print(f"   Skipping page {page_num + 1}: contains skip keyword")
                    continue
                
                # Skip pages with very little content (likely formatting pages)
                if len(text.strip()) < 100:
                    continue
                    
                # Look for Chapter 1 first (strongest indicator)
                if any(keyword in text for keyword in primary_start_keywords):
                    first_content = page_num
                    found_chapter_1 = True
                    print(f"📚 Found Chapter 1 indicator on page {page_num + 1}")
                    break
                    
            except Exception as page_error:
                print(f"   ⚠️ Error reading page {page_num + 1}: {page_error}")
                continue
        
        # If no Chapter 1 found, look for secondary indicators but be more strict
        if not found_chapter_1:
            print("   No Chapter 1 found, looking for secondary indicators...")
            for page_num in range(min(50, total_pages)):
                try:
                    page = doc.load_page(page_num)
                    text = page.get_text().lower()
                    
                    # Skip pages that are clearly TOC or metadata
                    if any(word in text for word in skip_keywords):
                        continue
                    
                    # Skip pages with very little content
                    if len(text.strip()) < 200:
                        continue
                        
                    if any(word in text for word in secondary_start_keywords):
                        first_content = page_num
                        print(f"📚 Found secondary content indicator on page {page_num + 1}")
                        break
                        
                    # Fallback: look for substantial programming content
                    code_patterns = ['>>>', 'print(', 'def ', 'import ', 'from ', 'python', 'variable', 'function', 'string']
                    if sum(1 for pat in code_patterns if pat in text) >= 4:
                        first_content = page_num
                        print(f"📚 Found programming content on page {page_num + 1}")
                        break
                        
                except Exception as page_error:
                    print(f"   ⚠️ Error reading page {page_num + 1}: {page_error}")
                    continue

        # Detect end (work backwards)
        for page_num in range(total_pages - 1, max(total_pages - 20, first_content), -1):
            text = doc.load_page(page_num).get_text().lower()
            if any(word in text for word in skip_keywords):
                continue
            if len(text.strip()) > 200:
                last_content = page_num
                break

        print(f"📚 Content: pages {first_content+1}-{last_content+1} of {total_pages}")
        return first_content, last_content

    except Exception as e:
        print(f"⚠️ Error finding content boundaries: {e}")
        doc = fitz.open(pdf_path)
        return 5, max(len(doc) - 10, 10)

def extract_toc(pdf_path: str) -> List[List[Any]]:
    # Extract TOC from PDF metadata if available; fallback to link extraction.
    # Returns list of [level, title, page].
    try:
        doc = fitz.open(pdf_path)
        
        # First try: Standard TOC extraction
        toc = doc.get_toc()
        
        # If TOC is empty or very small, try manual link extraction
        if not toc or len(toc) < 3:
            print("[TOC] Metadata TOC empty or insufficient, trying manual link extraction...")
            toc = _extract_toc_from_links(doc)
        
        doc.close()
        return toc
        
    except FileNotFoundError:
        raise FileNotFoundError(f"PDF file not found at {pdf_path}")
    except Exception as e:
        raise Exception(f"Error reading PDF: {e}")

def _extract_toc_from_links(doc: fitz.Document) -> List[List[Any]]:
    # Manual TOC extraction by scanning PDF links/annotations.
    # Used when standard `get_toc()` fails (e.g., bad annotations).
    toc_entries = []
    
    try:
        # Look through first few pages for TOC with working links
        for page_num in range(min(15, len(doc))):
            page = doc.load_page(page_num)
            
            # Get page text for pattern matching
            try:
                page_text = page.get_text()
            except:
                # If get_text() fails due to bad annotations, try alternative method
                page_text = page.get_text("text", flags=~fitz.TEXT_PRESERVE_LIGATURES)
            
            # Check if this looks like a TOC page
            if not _is_likely_toc_page(page_text):
                continue
            
            # Try to extract links from this page
            try:
                links = page.get_links()
                for link in links:
                    if link.get('kind') == fitz.LINK_GOTO:  # Internal link
                        # Get the text around this link position
                        link_text = _extract_text_at_position(page, link.get('from', {}))
                        if link_text and len(link_text.strip()) > 3:
                            dest_page = link.get('page', 0)
                            level = _guess_level_from_text(link_text)
                            toc_entries.append([level, link_text.strip(), dest_page + 1])
            except Exception as e:
                print(f"[TOC] Warning: Could not extract links from page {page_num + 1}: {e}")
                continue
    
    except Exception as e:
        print(f"[TOC] Manual link extraction failed: {e}")
    
    # Sort by page number and remove duplicates
    toc_entries = _clean_extracted_toc(toc_entries)
    print(f"[TOC] Manual extraction found {len(toc_entries)} entries")
    
    return toc_entries

def _is_likely_toc_page(text: str) -> bool:
    # Heuristic: does this page look like a Table of Contents?
    text_lower = text.lower()
    toc_keywords = ['contents', 'table of contents', 'chapter', 'section']
    
    # Must have TOC keywords and number patterns
    has_toc_keyword = any(keyword in text_lower for keyword in toc_keywords)
    has_page_numbers = len(re.findall(r'\b\d{1,3}\b', text)) > 5
    has_dots = '.' in text and text.count('.') > 10
    
    return has_toc_keyword and (has_page_numbers or has_dots)

def _extract_text_at_position(page: fitz.Page, rect_dict: dict) -> str:
    # Extract nearby text around a link rectangle.
    try:
        if not rect_dict:
            return ""
        
        # Create rectangle from link position
        rect = fitz.Rect(
            rect_dict.get('x0', 0),
            rect_dict.get('y0', 0), 
            rect_dict.get('x1', 100),
            rect_dict.get('y1', 20)
        )
        
        # Expand rectangle slightly to catch nearby text
        rect = rect + (-10, -2, 50, 2)
        
        # Extract text from this area
        text = page.get_text("text", clip=rect)
        return text.strip()
        
    except Exception:
        return ""

def _guess_level_from_text(text: str) -> int:
    # Guess the hierarchical level of a TOC entry from its text.
    # Check for numbering patterns
    if re.match(r'^\s*\d+\.\d+\.\d+', text):
        return 2
    elif re.match(r'^\s*\d+\.\d+', text):
        return 1
    elif re.match(r'^\s*\d+\.?', text):
        return 0
    elif re.match(r'^\s*[A-Z]\.', text):
        return 0
    
    # Check for keywords
    text_lower = text.lower()
    if any(word in text_lower for word in ['chapter', 'part', 'section']):
        return 0
    elif any(word in text_lower for word in ['exercise', 'example', 'problem']):
        return 1
    
    return 0

def _clean_extracted_toc(toc_entries: List[List[Any]]) -> List[List[Any]]:
    # Clean and deduplicate extracted TOC entries.
    if not toc_entries:
        return []
    
    # Remove very short or invalid entries
    cleaned = []
    for entry in toc_entries:
        if len(entry) >= 3 and len(str(entry[1]).strip()) > 3:
            title = str(entry[1]).strip()
            # Remove entries that are just page numbers or dots
            if not title.replace('.', '').replace(' ', '').isdigit():
                cleaned.append(entry)
    
    # Sort by page number and remove duplicates
    cleaned.sort(key=lambda x: x[2])
    unique_entries = []
    seen_titles = set()
    
    for entry in cleaned:
        title_key = str(entry[1]).strip().lower()
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_entries.append(entry)
    
    return unique_entries

def fallback_toc_text(doc: fitz.Document, page_limit: int = 15) -> List[str]:
    # Scan the first few pages for TOC patterns.
    # Returns page texts likely containing TOC; handles bad annotations.
    toc_pages = []
    found_toc_start = False

    for page_num in range(min(page_limit, len(doc))):
        try:
            # Try standard text extraction first
            text = doc.load_page(page_num).get_text()
        except Exception as e:
            print(f"[TOC] Warning: Standard text extraction failed for page {page_num + 1}: {e}")
            try:
                # Fallback: Use alternative text extraction method
                page = doc.load_page(page_num)
                text = page.get_text("text", flags=~fitz.TEXT_PRESERVE_LIGATURES)
            except Exception as e2:
                print(f"[TOC] Warning: Fallback text extraction also failed for page {page_num + 1}: {e2}")
                # Final fallback: Try getting text blocks
                try:
                    text_blocks = page.get_text("dict")
                    text = ""
                    for block in text_blocks.get("blocks", []):
                        if "lines" in block:
                            for line in block["lines"]:
                                for span in line.get("spans", []):
                                    text += span.get("text", "") + " "
                                text += "\n"
                except Exception as e3:
                    print(f"[TOC] Error: All text extraction methods failed for page {page_num + 1}: {e3}")
                    continue
        
        if not text or len(text.strip()) < 10:
            continue
            
        is_toc_page = False

        if "contents" in text.lower():
            is_toc_page = True
            found_toc_start = True
        elif found_toc_start:
            if (
                len(re.findall(r'\b\d{1,3}\b', text)) > 8 or
                len(re.findall(r'\.{2,}', text)) > 3 or
                len(re.findall(r'^\s*\d+\.?\d*\s+[A-Za-z]', text, re.MULTILINE)) > 2
            ):
                is_toc_page = True
            else:
                break
        else:
            if (
                len(re.findall(r'\b\d{1,3}\b', text)) > 15 and
                len(re.findall(r'\.{2,}', text)) > 8 and
                len(re.findall(r'^\s*\d+\.?\d*\s+[A-Za-z]', text, re.MULTILINE)) > 5
            ):
                is_toc_page = True
                found_toc_start = True

        if is_toc_page:
            toc_pages.append(text)
            print(f"[TOC] Found TOC content on page {page_num + 1}")

    return toc_pages

def detect_level(line: str) -> int:
    # Detect hierarchy based on indentation (4 spaces per level).
    return (len(line) - len(line.lstrip())) // 4

def parse_toc_text(toc_text_block: str) -> List[Dict[str, Any]]:
    # Flexible TOC parser for text blocks with multi-line, hierarchical entries.
    # Returns list of dicts: title, start_page, level, order.
    entries = []
    lines = toc_text_block.split('\n')
    meta_titles = {
        'foreword', 'preface', 'introduction', 'why this book', 'about',
        'acknowledgments', 'contents', 'table of contents', 'toc', 'index'
    }
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if (
            not line or len(line) < 2 or
            (line.isdigit() and len(line) <= 2 and int(line) < 50)
        ):
            i += 1
            continue
        if any(re.search(r'\b' + re.escape(meta) + r'\b', line.lower()) for meta in meta_titles):
            i += 1
            continue

        if not line.isdigit():
            title = line
            j = i + 1
            page_found = False
            while j < min(len(lines), i + 11):
                next_line = lines[j].strip()
                if next_line.isdigit() and int(next_line) > 0:
                    page = int(next_line)
                    page_found = True
                    break
                elif next_line and not next_line.isdigit():
                    title += ' ' + next_line
                j += 1

            if page_found:
                # Clean up title
                title = re.sub(r'^\.+|\.+$', '', title).strip()
                title = re.sub(r'\s*\.{2,}\s*', ' ', title)
                title = re.sub(r'\s+', ' ', title)
                if len(title) < 3 or title.count('.') > len(title) * 0.5:
                    i = j + 1
                    continue
                if any(re.search(r'\b' + re.escape(meta) + r'\b', title.lower()) for meta in meta_titles):
                    i = j + 1
                    continue
                level = _detect_level_advanced(line, title)
                entries.append({
                    "title": title,
                    "start_page": page - 1,
                    "level": level,
                    "order": len(entries)
                })
                i = j + 1
                continue
            else:
                i += 1
                continue
        i += 1
    return _clean_hierarchy(entries)

def _detect_level_advanced(original_line: str, title: str) -> int:
    # Advanced detection of TOC entry hierarchy.
    # Numbering patterns (updated for 4 levels)
    if re.match(r'^\s*\d+\.\d+\.\d+\.\d+', title): return 3  # 1.2.3.4 → Level 3 (4th level)
    if re.match(r'^\s*\d+\.\d+\.\d+', title): return 2       # 1.2.3 → Level 2 (3rd level)
    if re.match(r'^\s*\d+\.\d+', title): return 1            # 1.2 → Level 1 (2nd level)
    if re.match(r'^\s*\d+\.?\s', title): return 0            # 1. → Level 0 (1st level)
    if re.match(r'^\s*[A-Z]\.\s', title): return 0
    if re.match(r'^\s*[a-z]\.\s', title): return 1
    if re.match(r'^\s*[IVX]+\.\s', title): return 0
    # Indentation (updated for 4 levels)
    indent_level = len(original_line) - len(original_line.lstrip())
    if indent_level > 12: return 3  # Very deep indentation → Level 3
    if indent_level > 8: return 2   # Deep indentation → Level 2
    if indent_level > 4: return 1   # Medium indentation → Level 1
    # Keywords
    title_lower = title.lower()
    if any(w in title_lower for w in ['chapter', 'part', 'section', 'unit', 'module']):
        return 0
    if any(w in title_lower for w in ['exercise', 'example', 'practice', 'problem']):
        return 1
    return 0

def _clean_hierarchy(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Sort by page, prevent level jumps > 1, update order (levels 0-3).
    if not entries: return entries
    entries.sort(key=lambda x: x['start_page'])
    for i in range(1, len(entries)):
        if entries[i]['level'] > entries[i-1]['level'] + 1:
            entries[i]['level'] = entries[i-1]['level'] + 1
        # Cap at level 3 (4th level) for deep hierarchies
        if entries[i]['level'] > 3:
            entries[i]['level'] = 3
    for i, entry in enumerate(entries):
        entry['order'] = i
    return entries

def assign_end_pages(toc_entries: List[Dict[str, Any]], total_pages: int) -> List[Dict[str, Any]]:
    # Add `end_page` to each TOC entry.
    for i in range(len(toc_entries)):
        if i < len(toc_entries) - 1:
            toc_entries[i]['end_page'] = toc_entries[i + 1]['start_page'] - 1
        else:
            toc_entries[i]['end_page'] = total_pages - 1
    return toc_entries

def validate_toc_structure(entries: List[TOCEntry]) -> bool:
    # Recursively validate TOC structure: page ranges and child validity.
    if not entries: return False
    for entry in entries:
        if entry.start_page < 0 or (entry.end_page is not None and entry.end_page < entry.start_page):
            return False
        if entry.children and not validate_toc_structure(entry.children):
            return False
    return True
