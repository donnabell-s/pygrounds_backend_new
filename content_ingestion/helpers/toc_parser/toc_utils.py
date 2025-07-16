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
    Parses a block of text to extract TOC-style entries using a regex pattern.

    Expected format:
        Section Title ......... PageNumber

    Args:
        toc_text_block: Block of text containing TOC entries

    Returns:
        List of dictionaries with 'title', 'start_page', 'level' and 'order'.
    """
    entries = []
    lines = toc_text_block.split('\n')
    for i, line in enumerate(lines):
        match = re.match(r"(.+?)\s+\.{2,}\s+(\d+)$", line.strip())
        if match:
            title = match.group(1).strip()
            page = int(match.group(2)) - 1  # Convert to 0-based index
            level = detect_level(line)
            entries.append({
                "title": title,
                "start_page": page,
                "level": level,
                "order": i
            })
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
