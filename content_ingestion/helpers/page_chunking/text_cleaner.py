import re
from typing import Optional


def clean_raw_text(text: str) -> str:
    if not text:
        return ""
    
    text = _remove_urls(text)
    
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    text = re.sub(r'\[\d+\]', '', text)
    
    text = re.sub(r'Page \d+ of \d+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\d+$', '', text, flags=re.MULTILINE)
    
    text = re.sub(r'Copyright.*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'All rights reserved.*', '', text, flags=re.IGNORECASE)
    
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def clean_chunk_text(text: str) -> str:
    lines = text.strip().split("\n")
    cleaned_lines = []
    
    is_conceptual = _is_conceptual_content(text)
    
    for line in lines:
        line = line.strip()
        
        if not line:
            continue
        
        if is_conceptual and _has_conceptual_markers(line):
            line = clean_urls_from_line(line)
            if line.strip():
                cleaned_lines.append(line)
            continue
        
        if _should_skip_basic_line(line, is_conceptual):
            continue
        
        line = clean_urls_from_line(line)
        line = _remove_references_and_numbers(line)
        
        if re.match(r'^\d+\.?\s*[A-Z][a-z\s]+$', line) and len(line.split()) <= 5:
            continue
            
        line = re.sub(r'\s+', ' ', line).strip()
        
        if line:
            cleaned_lines.append(line)
    
    cleaned_lines = _remove_duplicates(cleaned_lines)
    
    result = "\n".join(cleaned_lines).strip()
    
    result = re.sub(r'\n\s*\n\s*\n', '\n\n', result)
    result = re.sub(r'\s+', ' ', result)
    
    return result


def clean_urls_from_line(line: str) -> str:
    return _remove_urls(line)


def _remove_urls(text: str) -> str:
    # url cleanup (including common pdf unicode artifacts)
    text = re.sub(r'https?://[^\s]+', '', text)
    text = re.sub(r'https?:/[^\s]*', '', text)  # Catch partial protocols
    text = re.sub(r'www\.[^\s]+', '', text)
    text = re.sub(r'[a-zA-Z0-9.-]+\.(com|org|net|edu|gov|io)[^\s]*', '', text)
    
    text = re.sub(r'https?:/​/​[^\s]*', '', text)
    text = re.sub(r'[a-zA-Z0-9.-]+\.​[a-zA-Z0-9.-]+[^\s]*', '', text)
    
    text = re.sub(r'/​[a-zA-Z0-9._-]+/[^\s]*', '', text)  # Paths with Unicode slash
    text = re.sub(r'/[a-zA-Z0-9._-]+/[a-zA-Z0-9._/-]*', '', text)  # Regular paths
    text = re.sub(r'[a-zA-Z0-9.-]+\.​[a-zA-Z]+', '', text)  # Domains with Unicode dot
    
    text = re.sub(r'github\.com[^\s]*', '', text)
    text = re.sub(r'PacktPublishing[^\s]*', '', text)
    text = re.sub(r'Expert-​Python[^\s]*', '', text)
    text = re.sub(r'/​tree/​[^\s]*', '', text)
    text = re.sub(r'/​master/​[^\s]*', '', text)
    
    text = re.sub(r'https:/​/​\s*for\s+this\s+chapter', 'for this chapter', text)
    text = re.sub(r'https:/​/​\s*', '', text)
    
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    return text


def _is_conceptual_content(text: str) -> bool:
    return not any([
        ">>>" in text,
        "def " in text,
        "class " in text,
        "import " in text,
        re.search(r'[a-zA-Z_]\w*\s*=\s*[^=]', text),
    ])


def _has_conceptual_markers(line: str) -> bool:
    conceptual_markers = [
        " is defined as ", " refers to ", " means ", "definition:",
        "in other words", "simply put", "key term", "important to note",
        "terminology", "principle", "concept", "theory"
    ]
    return any(marker in line.lower() for marker in conceptual_markers) and len(line) > 20


def _should_skip_basic_line(line: str, is_conceptual: bool) -> bool:
    line_lower = line.lower()
    
    if ((line.isupper() and len(line) < 100) or 
        (line.startswith('#') and not line.startswith('# ')) or 
        (line.endswith(':') and len(line.split()) <= 4 and not is_conceptual)):
        return True
    
    return False


def _remove_references_and_numbers(line: str) -> str:
    line = re.sub(r'\[\d+\]', '', line)
    
    line = re.sub(r'Page \d+ of \d+', '', line, flags=re.IGNORECASE)
    line = re.sub(r'^\d+$', '', line)
    
    return line


def _remove_duplicates(cleaned_lines: list) -> list:
    if len(cleaned_lines) <= 1:
        return cleaned_lines
    
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
