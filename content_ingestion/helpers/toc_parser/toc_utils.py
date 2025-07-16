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

def fallback_toc_text(doc: fitz.Document, page_limit: int = 9) -> List[str]:
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
    for page_num in range(min(page_limit, len(doc))):
        text = doc.load_page(page_num).get_text()
        if "contents" in text.lower():
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
    
    print(f"[DEBUG] Parsing {len(lines)} lines from TOC text")
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines or common headers
        if not line or len(line) < 2 or line.lower() in ['contents', 'table of contents', 'toc', 'index']:
            i += 1
            continue
            
        # Check if current line is just a page number (standalone)
        if line.isdigit() and int(line) > 0:
            # Look back for a title in previous lines
            for j in range(i-1, max(i-4, -1), -1):  # Look back up to 3 lines
                prev_line = lines[j].strip()
                if prev_line and len(prev_line) > 1 and not prev_line.isdigit():
                    # Found potential title
                    title = prev_line
                    page = int(line)
                    
                    # Clean up title more thoroughly
                    title = re.sub(r'\.+$', '', title).strip()  # Remove trailing dots
                    title = re.sub(r'^\.+', '', title).strip()  # Remove leading dots
                    title = re.sub(r'\s*\.{2,}\s*', ' ', title)  # Remove dot leaders (table of contents dots)
                    title = re.sub(r'\s+', ' ', title)          # Normalize spaces
                    title = title.strip()
                    
                    # Skip if title is mostly dots or too short
                    if len(title) < 3 or title.count('.') > len(title) * 0.5:
                        continue
                    
                    # Detect level based on original line indentation and numbering
                    level = _detect_level_advanced(lines[j], title)
                    
                    if len(title) > 2:  # Valid title after cleaning
                        entry = {
                            "title": title,
                            "start_page": page - 1,  # Convert to 0-based
                            "level": level,
                            "order": len(entries)
                        }
                        entries.append(entry)
                        print(f"[DEBUG] Multi-line match: '{title}' -> Page {page} (Level {level})")
                        break
            i += 1
            continue
            
        # Check for single-line entries (title and page on same line)
        page_numbers = re.findall(r'\b(\d+)\b', line)
        if page_numbers:
            potential_page = int(page_numbers[-1])
            
            if potential_page > 0:
                # Remove page number to get title
                title = line
                for pattern in [
                    rf'\s*\.+\s*{potential_page}$',
                    rf'\s+{potential_page}$',
                    rf'\s*{potential_page}$',
                ]:
                    title = re.sub(pattern, '', title).strip()
                
                # Clean up title more thoroughly
                title = re.sub(r'\.+$', '', title).strip()    # Remove trailing dots
                title = re.sub(r'^\.+', '', title).strip()    # Remove leading dots
                title = re.sub(r'\s*\.{2,}\s*', ' ', title)   # Remove dot leaders
                title = re.sub(r'\s+', ' ', title)            # Normalize spaces
                title = title.strip()
                
                # Skip if title is mostly dots or too short
                if len(title) < 3 or title.count('.') > len(title) * 0.5:
                    continue
                    level = _detect_level_advanced(line, title)
                    
                    entry = {
                        "title": title,
                        "start_page": potential_page - 1,
                        "level": level,
                        "order": len(entries)
                    }
                    entries.append(entry)
                    print(f"[DEBUG] Single-line match: '{title}' -> Page {potential_page} (Level {level})")
        
        i += 1
    
    print(f"[DEBUG] Found {len(entries)} entries total")
    
    # Post-process to clean up hierarchy
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
