import fitz  # PyMuPDF
import re
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

@dataclass
class TOCEntry:
    """A single entry in the Table of Contents."""
    title: str
    start_page: int
    end_page: Optional[int] = None
    level: int = 0
    children: List['TOCEntry'] = field(default_factory=list)

def find_content_boundaries(pdf_path: str) -> Tuple[int, int]:
    """
    Returns (first_content_page, last_content_page) in 0-based indexing.
    Skips preface, TOC, and appendices by keyword.
    More strict detection prioritizing "Chapter 1" as content start.
    """
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
    """
    Extracts TOC from PDF metadata if available.
    Returns list of [level, title, page].
    """
    try:
        doc = fitz.open(pdf_path)
        return doc.get_toc()
    except FileNotFoundError:
        raise FileNotFoundError(f"PDF file not found at {pdf_path}")
    except Exception as e:
        raise Exception(f"Error reading PDF: {e}")

def fallback_toc_text(doc: fitz.Document, page_limit: int = 15) -> List[str]:
    """
    Scans the first few pages for 'Contents' or TOC patterns.
    Returns list of page texts likely containing TOC.
    """
    toc_pages = []
    found_toc_start = False

    for page_num in range(min(page_limit, len(doc))):
        text = doc.load_page(page_num).get_text()
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

    return toc_pages

def detect_level(line: str) -> int:
    """Detects hierarchy based on indentation (4 spaces per level)."""
    return (len(line) - len(line.lstrip())) // 4

def parse_toc_text(toc_text_block: str) -> List[Dict[str, Any]]:
    """
    Flexible TOC parser for text blocks with multi-line, hierarchical entries.
    Returns list of dicts: title, start_page, level, order.
    """
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
    """Advanced detection of TOC entry hierarchy."""
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
    """
    Sorts by page, prevents level jumps >1, updates order.
    Supports up to 4 levels (0-3).
    """
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
    """
    Adds 'end_page' to each TOC entry.
    """
    for i in range(len(toc_entries)):
        if i < len(toc_entries) - 1:
            toc_entries[i]['end_page'] = toc_entries[i + 1]['start_page'] - 1
        else:
            toc_entries[i]['end_page'] = total_pages - 1
    return toc_entries

def validate_toc_structure(entries: List[TOCEntry]) -> bool:
    """
    Recursively checks TOC structure: page order, children validity.
    """
    if not entries: return False
    for entry in entries:
        if entry.start_page < 0 or (entry.end_page is not None and entry.end_page < entry.start_page):
            return False
        if entry.children and not validate_toc_structure(entry.children):
            return False
    return True
