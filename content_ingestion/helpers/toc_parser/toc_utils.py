import fitz  # PyMuPDF
import re
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

@dataclass
class TOCEntry:
    """
    Represents a single entry in the table of contents.
    
    Attributes:
        title: The section title
        start_page: Starting page number (0-based)
        end_page: Ending page number (0-based)
        level: Indentation level (0 for top-level entries)
        children: List of subsections
    """
    title: str
    start_page: int
    end_page: Optional[int] = None
    level: int = 0
    children: List['TOCEntry'] = field(default_factory=list)

def find_content_boundaries(pdf_path: str) -> Tuple[int, int]:
    """
    Find the first and last page containing actual educational content,
    excluding covers, prefaces, indexes, etc.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Tuple of (first_content_page, last_content_page) (0-based)
    """
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        # Keywords that indicate educational content start
        content_start_keywords = [
            'chapter 1', 'module 1', 'lesson 1', 'unit 1',
            'introduction to python', 'getting started',
            'python basics', 'fundamentals', 'variables',
            'data types', 'functions', 'loops'
        ]
        
        # Keywords that indicate non-content pages
        non_content_keywords = [
            'table of contents', 'preface', 'foreword', 'acknowledgments',
            'about the author', 'about this book', 'copyright', 'isbn',
            'index', 'bibliography', 'references', 'glossary',
            'appendix', 'answer key', 'solutions'
        ]
        
        first_content_page = 0
        last_content_page = total_pages - 1
        
        # Find first content page
        for page_num in range(min(20, total_pages)):  # Check first 20 pages
            page = doc.load_page(page_num)
            text = page.get_text().lower()
            
            # Skip if it's clearly non-content
            if any(keyword in text for keyword in non_content_keywords):
                continue
                
            # Look for content indicators
            if any(keyword in text for keyword in content_start_keywords):
                first_content_page = page_num
                break
                
            # Alternative: look for code patterns or exercise patterns
            code_patterns = [
                '>>>', 'print(', 'def ', 'import ', 'from ',
                'python', 'variable', 'function', 'string'
            ]
            if any(pattern in text for pattern in code_patterns):
                # Count how many patterns we find
                pattern_count = sum(1 for pattern in code_patterns if pattern in text)
                if pattern_count >= 3:  # Strong indication of content
                    first_content_page = page_num
                    break
        
        # Find last content page (work backwards from end)
        for page_num in range(total_pages - 1, max(total_pages - 20, first_content_page), -1):
            page = doc.load_page(page_num)
            text = page.get_text().lower()
            
            # Skip if it's clearly non-content (appendix, index, etc.)
            if any(keyword in text for keyword in non_content_keywords):
                continue
                
            # Look for meaningful content (not just "blank" or very short pages)
            if len(text.strip()) > 200:  # Reasonable amount of text
                last_content_page = page_num
                break
        
        print(f"📚 Content boundaries: pages {first_content_page + 1}-{last_content_page + 1} (of {total_pages} total)")
        
        return first_content_page, last_content_page
        
    except Exception as e:
        print(f"⚠️ Error finding content boundaries: {e}")
        # Fallback to reasonable defaults
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        return 5, max(total_pages - 10, 10)  # Skip first 5 and last 10 pages

def extract_toc(pdf_path: str) -> List[List[Any]]:
    """
    Extracts table of contents from PDF metadata if available.
    
    Args:
        pdf_path: Path to the PDF file

    Returns:
        List of [level, title, page] entries from PDF TOC.
        
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        fitz.FileDataError: If PDF is corrupted
    """
    try:
        doc = fitz.open(pdf_path)
        return doc.get_toc()
    except FileNotFoundError:
        raise FileNotFoundError(f"PDF file not found at {pdf_path}")
    except Exception as e:
        raise Exception(f"Error reading PDF: {str(e)}")

def fallback_toc_text(doc: fitz.Document, page_limit: int = 15) -> List[str]:
    """
    Scans the first few pages of the PDF for 'Table of Contents' text 
    if no metadata-based TOC is found.

    Args:
        doc: Open PyMuPDF document
        page_limit: Maximum number of pages to scan

    Returns:
        List of page texts that may contain TOC-like structure.
    """
    toc_pages = []
    found_toc_start = False
    
    for page_num in range(min(page_limit, len(doc))):
        text = doc.load_page(page_num).get_text()
        
        # Check if this is a TOC page
        is_toc_page = False
        
        # Primary check: contains "contents"
        if "contents" in text.lower():
            is_toc_page = True
            found_toc_start = True
        
        # If we found TOC start, continue collecting consecutive pages with TOC-like content
        elif found_toc_start:
            num_count = len(re.findall(r'\b\d{1,3}\b', text))
            dot_leader_count = len(re.findall(r'\.{2,}', text))
            chapter_pattern = len(re.findall(r'^\s*\d+\.?\d*\s+[A-Za-z]', text, re.MULTILINE))
            
            # Continue if page has TOC-like patterns
            if num_count > 8 or dot_leader_count > 3 or chapter_pattern > 2:
                is_toc_page = True
            else:
                # Stop if we hit a page that doesn't look like TOC anymore
                break
        
        # Fallback for pages without "contents" but with strong TOC indicators
        else:
            num_count = len(re.findall(r'\b\d{1,3}\b', text))
            dot_leader_count = len(re.findall(r'\.{2,}', text))
            chapter_pattern = len(re.findall(r'^\s*\d+\.?\d*\s+[A-Za-z]', text, re.MULTILINE))
            
            if num_count > 15 and dot_leader_count > 8 and chapter_pattern > 5:
                is_toc_page = True
                found_toc_start = True
        
        if is_toc_page:
            toc_pages.append(text)
    
    return toc_pages

def detect_level(line: str) -> int:
    """
    Detects the hierarchy level based on indentation or formatting.
    
    Args:
        line: The TOC entry line
        
    Returns:
        Estimated level of the entry (0-based)
    """
    leading_spaces = len(line) - len(line.lstrip())
    return leading_spaces // 4  # Assuming 4-space indentation

def parse_toc_text(toc_text_block: str) -> List[Dict[str, Any]]:
    """
    Extremely flexible TOC parser that handles various formats including multi-line entries.
    
    This parser tries to identify:
    1. Main topics (chapters, sections)
    2. Subtopics (subsections)
    3. Page numbers (even on separate lines)
    4. Hierarchy levels
    
    Args:
        toc_text_block: Block of text containing TOC entries

    Returns:
        List of dictionaries with 'title', 'start_page', 'level' and 'order'.
    """
    entries = []
    lines = toc_text_block.split('\n')
    meta_titles = {'foreword', 'preface', 'introduction', 'why this book', 'about', 'acknowledgments', 'contents', 'table of contents', 'toc', 'index'}
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Skip obvious footer/header patterns and meta content
        if (not line or len(line) < 2 or 
            (line.isdigit() and len(line) <= 2 and int(line) < 50)):  # Skip obvious page footers
            i += 1
            continue
        
        # Check for meta titles (whole words only)
        is_meta = False
        for meta in meta_titles:
            if re.search(r'\b' + re.escape(meta) + r'\b', line.lower()):
                is_meta = True
                break
        if is_meta:
            i += 1
            continue
        
        # If line is not a page number, treat as possible title
        if not line.isdigit():
            title = line
            # Look ahead for page number (up to 10 lines to be safe)
            j = i + 1
            page_found = False
            while j < min(len(lines), i + 11):
                next_line = lines[j].strip()
                if next_line.isdigit() and int(next_line) > 0:
                    page = int(next_line)
                    page_found = True
                    break
                elif next_line and not next_line.isdigit():
                    # Accumulate multi-line titles
                    title += ' ' + next_line
                j += 1
            
            if page_found:
                # Clean up title
                title = re.sub(r'\.+$', '', title).strip()
                title = re.sub(r'^\.+', '', title).strip()
                title = re.sub(r'\s*\.{2,}\s*', ' ', title)
                title = re.sub(r'\s+', ' ', title)
                title = title.strip()
                if len(title) < 3 or title.count('.') > len(title) * 0.5:
                    i = j + 1
                    continue
                if any(re.search(r'\b' + re.escape(meta) + r'\b', title.lower()) for meta in meta_titles):
                    i = j + 1
                    continue
                level = _detect_level_advanced(line, title)
                entry = {
                    "title": title,
                    "start_page": page - 1,
                    "level": level,
                    "order": len(entries)
                }
                entries.append(entry)
                i = j + 1
                continue
            else:
                # No page number found, just move to next line
                i += 1
                continue
        # If line is a page number but previous line is a title, handled above
        i += 1
    entries = _clean_hierarchy(entries)
    return entries

def _detect_level_advanced(original_line: str, title: str) -> int:
    """
    Advanced level detection using multiple heuristics
    """
    level = 0
    
    # Method 1: Check for numbering patterns
    if re.match(r'^\s*\d+\.\d+\.\d+', title):      # 1.2.3 format
        level = 2
    elif re.match(r'^\s*\d+\.\d+', title):         # 1.2 format  
        level = 1
    elif re.match(r'^\s*\d+\.?\s', title):         # 1. or 1 format
        level = 0
    elif re.match(r'^\s*[A-Z]\.\s', title):        # A. format
        level = 0
    elif re.match(r'^\s*[a-z]\.\s', title):        # a. format
        level = 1
    elif re.match(r'^\s*[IVX]+\.\s', title):       # Roman numerals
        level = 0
    else:
        # Method 2: Check indentation
        indent_level = len(original_line) - len(original_line.lstrip())
        if indent_level > 8:
            level = 2
        elif indent_level > 4:
            level = 1
        else:
            level = 0
            
    # Method 3: Check for common keywords to adjust level
    title_lower = title.lower()
    if any(word in title_lower for word in ['chapter', 'part', 'section', 'unit', 'module']):
        level = max(0, level - 1)  # Main topics
    elif any(word in title_lower for word in ['exercise', 'example', 'practice', 'problem']):
        level = min(2, level + 1)  # Subtopics
        
    return level

def _clean_hierarchy(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Clean up the hierarchy to ensure logical nesting
    """
    if not entries:
        return entries
        
    # Sort by page number to ensure proper order
    entries.sort(key=lambda x: x['start_page'])
    
    # Adjust levels to be more logical
    for i in range(1, len(entries)):
        prev_level = entries[i-1]['level']
        curr_level = entries[i]['level']
        
        # Don't allow level jumps of more than 1
        if curr_level > prev_level + 1:
            entries[i]['level'] = prev_level + 1
            
    # Update order after sorting
    for i, entry in enumerate(entries):
        entry['order'] = i
        
    return entries

def assign_end_pages(toc_entries: List[Dict[str, Any]], total_pages: int) -> List[Dict[str, Any]]:
    """
    Adds 'end_page' field to each TOC entry by looking at the start of the next one.

    Args:
        toc_entries: List of dicts with 'start_page' already filled.
        total_pages: Total number of pages in the PDF.

    Returns:
        Same list with added 'end_page' fields.
    """
    for i in range(len(toc_entries)):
        if i < len(toc_entries) - 1:
            toc_entries[i]['end_page'] = toc_entries[i + 1]['start_page'] - 1
        else:
            toc_entries[i]['end_page'] = total_pages - 1  # Last section goes till the end
    return toc_entries

def organize_hierarchy(flat_entries: List[Dict[str, Any]]) -> List[TOCEntry]:
    """
    Converts flat TOC entries into a hierarchical structure.
    
    Args:
        flat_entries: List of dictionaries containing TOC entries
        
    Returns:
        List of TOCEntry objects representing the root level entries,
        with nested children representing the hierarchy
    """
    root = []
    stack = []
    
    for entry in flat_entries:
        curr = TOCEntry(
            title=entry['title'],
            start_page=entry['start_page'],
            end_page=entry.get('end_page'),
            level=entry.get('level', 0)
        )
        
        while stack and stack[-1].level >= curr.level:
            stack.pop()
            
        if not stack:
            root.append(curr)
        else:
            stack[-1].children.append(curr)
            
        stack.append(curr)
        
    return root

def validate_toc_structure(entries: List[TOCEntry]) -> bool:
    """
    Validates the TOC structure for consistency.
    
    Args:
        entries: List of TOCEntry objects
        
    Returns:
        True if structure is valid, False otherwise
    """
    if not entries:
        return False
        
    for entry in entries:
        # Check for valid page numbers
        if entry.start_page < 0 or (entry.end_page and entry.end_page < entry.start_page):
            return False
            
        # Validate children recursively
        if entry.children:
            if not validate_toc_structure(entry.children):
                return False
                
    return True
