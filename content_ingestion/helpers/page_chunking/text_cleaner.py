"""
Text cleaning utilities for chunk processing.
"""
import re
from typing import Optional


def clean_raw_text(text: str) -> str:
    """
    Clean raw text from PDF before processing to remove titles, links, and noise.
    Enhanced to filter out TOC pages and remove code annotations.
    """
    if not text:
        return ""

    # Filter out Table of Contents pages
    if _is_table_of_contents_page(text):
        return ""

    # Enhanced URL removal with comprehensive patterns
    text = _remove_urls(text)

    # Remove markdown links [text](url)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    # Remove standalone reference numbers [1], [2], etc.
    text = re.sub(r'\[\d+\]', '', text)

    # Remove page numbers and footers
    text = re.sub(r'Page \d+ of \d+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\d+$', '', text, flags=re.MULTILINE)

    # Remove common PDF artifacts
    text = re.sub(r'Copyright.*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'All rights reserved.*', '', text, flags=re.IGNORECASE)

    # Remove code annotations (①, ②, ③, etc.)
    text = re.sub(r'[①②③④⑤⑥⑦⑧⑨⑩]', '', text)

    # Remove repetitive dots and formatting artifacts
    text = re.sub(r'\.\s*\.\s*\.\s*', ' ', text)  # Multiple dots with spaces
    text = re.sub(r'\.{3,}', '', text)  # Three or more consecutive dots

    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def clean_chunk_text(text: str) -> str:
    """
    Clean and normalize chunk text with enhanced preservation for conceptual vs coding content.
    Enhanced to remove code annotations, copyright notices, and headers/footers.

    For Concept chunks: Focus on preserving definitions, keywords, and explanatory text
    For Code/Example/Try_It/Exercise chunks: Preserve code structure and context
    """
    lines = text.strip().split("\n")
    cleaned_lines = []

    # Determine if this looks like conceptual content (for different cleaning strategy)
    is_conceptual = _is_conceptual_content(text)

    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Skip copyright notices and footers
        if _is_copyright_or_footer_line(line):
            continue

        # Skip header/footer patterns
        if _is_header_footer_line(line):
            continue

        # For conceptual content, preserve important definition markers
        if is_conceptual and _has_conceptual_markers(line):
            line = clean_urls_from_line(line)
            if line.strip():
                cleaned_lines.append(line)
            continue

        # Check if this line should be skipped (basic patterns only)
        if _should_skip_basic_line(line, is_conceptual):
            continue

        # Clean URLs and references
        line = clean_urls_from_line(line)
        line = _remove_references_and_numbers(line)

        # Remove code annotations and explanatory text
        line = _remove_code_annotations(line)

        # Remove chapter/section headers that are just numbers and titles
        if re.match(r'^\d+\.?\s*[A-Z][a-z\s]+$', line) and len(line.split()) <= 5:
            continue

        # Clean up the line
        line = re.sub(r'\s+', ' ', line).strip()

        if line:  # Only add non-empty lines
            cleaned_lines.append(line)

    # Handle duplicates carefully
    cleaned_lines = _remove_duplicates(cleaned_lines)

    result = "\n".join(cleaned_lines).strip()

    # Final cleanup - remove excessive whitespace
    result = re.sub(r'\n\s*\n\s*\n', '\n\n', result)  # Max 2 consecutive newlines
    result = re.sub(r'\s+', ' ', result)  # Normalize spaces

    return result


def clean_urls_from_line(line: str) -> str:
    """
    Helper function to clean URLs from a single line while preserving other content.
    """
    return _remove_urls(line)


def _remove_urls(text: str) -> str:
    """Remove various URL patterns from text."""
    # Remove URLs with various protocols and special characters
    text = re.sub(r'https?://[^\s]+', '', text)
    text = re.sub(r'https?:/[^\s]*', '', text)  # Catch partial protocols
    text = re.sub(r'www\.[^\s]+', '', text)
    text = re.sub(r'[a-zA-Z0-9.-]+\.(com|org|net|edu|gov|io)[^\s]*', '', text)
    
    # Remove URLs with Unicode characters like /​/​
    text = re.sub(r'https?:/​/​[^\s]*', '', text)
    text = re.sub(r'[a-zA-Z0-9.-]+\.​[a-zA-Z0-9.-]+[^\s]*', '', text)
    
    # Remove partial URLs and paths that look like URLs
    text = re.sub(r'/​[a-zA-Z0-9._-]+/[^\s]*', '', text)  # Paths with Unicode slash
    text = re.sub(r'/[a-zA-Z0-9._-]+/[a-zA-Z0-9._/-]*', '', text)  # Regular paths
    text = re.sub(r'[a-zA-Z0-9.-]+\.​[a-zA-Z]+', '', text)  # Domains with Unicode dot
    
    # Remove GitHub and repository-specific patterns
    text = re.sub(r'github\.com[^\s]*', '', text)
    text = re.sub(r'PacktPublishing[^\s]*', '', text)
    text = re.sub(r'Expert-​Python[^\s]*', '', text)
    text = re.sub(r'/​tree/​[^\s]*', '', text)
    text = re.sub(r'/​master/​[^\s]*', '', text)
    
    # Remove incomplete URLs that start with protocol but are broken
    text = re.sub(r'https:/​/​\s*for\s+this\s+chapter', 'for this chapter', text)
    text = re.sub(r'https:/​/​\s*', '', text)
    
    # Remove markdown links [text](url)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    return text


def _is_conceptual_content(text: str) -> bool:
    """Check if text appears to be conceptual rather than code."""
    return not any([
        ">>>" in text,
        "def " in text,
        "class " in text,
        "import " in text,
        re.search(r'[a-zA-Z_]\w*\s*=\s*[^=]', text),  # Assignments
    ])


def _has_conceptual_markers(line: str) -> bool:
    """Check if line contains important conceptual markers."""
    conceptual_markers = [
        " is defined as ", " refers to ", " means ", "definition:",
        "in other words", "simply put", "key term", "important to note",
        "terminology", "principle", "concept", "theory"
    ]
    return any(marker in line.lower() for marker in conceptual_markers) and len(line) > 20


def _should_skip_basic_line(line: str, is_conceptual: bool) -> bool:
    """Determine if a line should be skipped during cleaning (simplified version)."""
    line_lower = line.lower()

    # Remove common title patterns (but be more careful with conceptual content)
    if ((line.isupper() and len(line) < 100) or
        (line.startswith('#') and not line.startswith('# ')) or
        (line.endswith(':') and len(line.split()) <= 4 and not is_conceptual and not line.startswith('def '))):
        return True

    return False


def _remove_references_and_numbers(line: str) -> str:
    """Remove references and page numbers from line."""
    # Remove standalone markdown reference links [1], [2], etc.
    line = re.sub(r'\[\d+\]', '', line)
    
    # Remove page numbers and references like "Page 1 of 10"
    line = re.sub(r'Page \d+ of \d+', '', line, flags=re.IGNORECASE)
    line = re.sub(r'^\d+$', '', line)  # Standalone numbers
    
    return line


def _remove_duplicates(cleaned_lines: list) -> list:
    """Remove duplicate lines while preserving important content."""
    if len(cleaned_lines) <= 1:
        return cleaned_lines
    
    # Handle duplicate line detection more carefully for code
    if len(cleaned_lines) > 1 and cleaned_lines[0] == cleaned_lines[1]:
        first_line_lower = cleaned_lines[0].lower()
        is_important = any([
            ">>>" in cleaned_lines[0],
            cleaned_lines[0].strip().startswith(("def ", "class ", "import ", "from ")),
            any(marker in first_line_lower for marker in [" is defined as ", " refers to ", " means "]),
            "definition:" in first_line_lower
        ])
        if not is_important:
            cleaned_lines.pop(0)
    
    # Handle duplicate segments for non-code content
    if len(cleaned_lines) == 1 and cleaned_lines[0]:
        segments = cleaned_lines[0].split()
        mid = len(segments) // 2
        if mid > 0 and segments[:mid] == segments[mid:]:
            line_lower = cleaned_lines[0].lower()
            is_important = any([
                ">>>" in cleaned_lines[0],
                "def " in cleaned_lines[0],
                "import " in cleaned_lines[0],
                "=" in cleaned_lines[0],
                any(marker in line_lower for marker in [" is defined as ", " refers to ", " means ", "definition:"])
            ])
            if not is_important:
                cleaned_lines[0] = " ".join(segments[:mid])
    
    return cleaned_lines


def _is_table_of_contents_page(text: str) -> bool:
    """
    Check if the text appears to be a Table of Contents page that should be filtered out.
    TOC pages contain repetitive dots, page numbers, and section titles.
    """
    if not text or len(text.strip()) < 50:
        return False

    text_lower = text.lower()

    # Check for TOC indicators
    toc_indicators = [
        "table of contents",
        "contents",
        "chapter",
        "section",
        "page"
    ]

    # Count TOC indicators
    indicator_count = sum(1 for indicator in toc_indicators if indicator in text_lower)

    # Check for repetitive dot patterns (common in TOC formatting)
    dot_patterns = re.findall(r'\.\s*\.\s*\.\s*', text)
    if len(dot_patterns) > 3:  # More than 3 instances of " . . . "
        return True

    # Check for page number patterns at end of lines
    page_number_lines = re.findall(r'.*\.\s*\d+\s*$', text, re.MULTILINE)
    if len(page_number_lines) > 5:  # More than 5 lines ending with dots and numbers
        return True

    # If we have multiple TOC indicators AND repetitive formatting, likely a TOC page
    if indicator_count >= 2 and (len(dot_patterns) > 1 or len(page_number_lines) > 2):
        return True

    return False


def _is_copyright_or_footer_line(line: str) -> bool:
    """Check if line contains copyright notices or footer information."""
    line_lower = line.lower()

    copyright_patterns = [
        "copyright",
        "all rights reserved",
        "©",
        "packt publishing",
        "expert-python",
        "(rev",
        "chapter",
        "intermediate python"
    ]

    return any(pattern in line_lower for pattern in copyright_patterns)


def _is_header_footer_line(line: str) -> bool:
    """Check if line appears to be a header or footer."""
    line_lower = line.lower().strip()

    # Skip lines that are just filenames or file extensions
    if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\.(py|txt|md|html|css|js)$', line):
        return True

    # Skip lines with repetitive symbols or short meaningless text
    if len(line) < 20 and (line.isupper() or re.match(r'^[^\w]*$', line)):
        return True

    return False


def _remove_code_annotations(line: str) -> str:
    """Remove code annotations and explanatory text from code examples."""
    # Remove circled numbers and letters (①, ②, ③, etc.)
    line = re.sub(r'[①②③④⑤⑥⑦⑧⑨⑩]', '', line)

    # Remove explanatory text that follows code (patterns like "A list of...", "The for loop...")
    explanatory_patterns = [
        r'\s*A\s+[a-zA-Z\s]+(?:\s+of\s+|\s+that\s+|\s+to\s+)',
        r'\s*The\s+[a-zA-Z\s]+(?:\s+unpacks|\s+prints|\s+creates|\s+defines)',
        r'\s*This\s+[a-zA-Z\s]+(?:\s+is\s+|\s+does\s+)',
    ]
    for pattern in explanatory_patterns:
        try:
            line = re.sub(pattern + r'.*$', '', line, flags=re.IGNORECASE)
        except re.error:
            # If regex fails, continue with original line
            continue

    return line.strip()
