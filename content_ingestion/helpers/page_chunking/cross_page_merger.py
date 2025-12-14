## Cross-page continuity utilities for content spanning multiple pages.
import re
from typing import List, Dict, Any, Optional, Tuple


def detect_split_content(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Detect and merge content split across pages (code blocks, definitions, sentences, lists, etc.).
    if not chunks:
        return chunks
    
    merged_chunks = []
    i = 0
    
    while i < len(chunks):
        current_chunk = chunks[i]
        
        # Look for split patterns
        if i < len(chunks) - 1:
            next_chunk = chunks[i + 1]
            
            # Check if these chunks should be merged
            should_merge, merge_type = _should_merge_chunks(current_chunk, next_chunk)
            
            if should_merge:
                print(f"🔗 Merging chunks due to {merge_type}: pages {current_chunk.get('page_number', '?')} and {next_chunk.get('page_number', '?')}")
                
                merged_chunk = _merge_chunks(current_chunk, next_chunk, merge_type)
                merged_chunks.append(merged_chunk)
                i += 2  # Skip next chunk as it's been merged
                continue
        
        # No merge needed, add current chunk
        merged_chunks.append(current_chunk)
        i += 1
    
    return merged_chunks


def _should_merge_chunks(chunk1: Dict[str, Any], chunk2: Dict[str, Any]) -> Tuple[bool, str]:
    # Determine if two consecutive chunks should be merged and why.
    text1 = chunk1.get('text', '').strip()
    text2 = chunk2.get('text', '').strip()
    
    if not text1 or not text2:
        return False, ""
    
    # Check for split code blocks
    if _is_split_code_block(text1, text2):
        return True, "split_code_block"
    
    # Check for split class/function definitions
    if _is_split_class_or_function(text1, text2):
        return True, "split_class_function"
    
    # Check for incomplete sentences
    if _is_incomplete_sentence(text1, text2):
        return True, "incomplete_sentence"
    
    # Check for method/descriptor continuation (like your example)
    if _is_method_continuation(text1, text2):
        return True, "method_continuation"
    
    # Check for list/explanation continuation
    if _is_list_continuation(text1, text2):
        return True, "list_continuation"
    
    # Check for same topic continuation based on headers
    if _is_same_topic_continuation(text1, text2):
        return True, "topic_continuation"
    
    return False, ""


def _is_split_code_block(text1: str, text2: str) -> bool:
    # Check if a code block is split across pages.
    # Look for incomplete code structures
    code_indicators = [
        # Incomplete class definition
        (r'class\s+\w+.*:\s*$', r'^\s*(def\s+\w+|@\w+|\w+\s*=)'),
        # Incomplete function definition  
        (r'def\s+\w+.*:\s*$', r'^\s*(""".*?"""|\'\'\'.*?\'\'\'|[a-zA-Z_]\w*)'),
        # Incomplete try/except
        (r'try:\s*$', r'^\s*(except|finally|else)'),
        # Incomplete if/for/while
        (r'(if|for|while)\s+.*:\s*$', r'^\s*[a-zA-Z_]'),
        # Incomplete method with decorator
        (r'@\w+\s*$', r'^\s*def\s+\w+'),
        # Python REPL continuation (>>> at end, content at start)
        (r'>>>\s*[^>]*$', r'^[^>].*'),
    ]
    
    for pattern1, pattern2 in code_indicators:
        if re.search(pattern1, text1, re.MULTILINE) and re.search(pattern2, text2, re.MULTILINE):
            return True
    
    # Check for unmatched brackets/parentheses
    bracket_counts = {
        '(': text1.count('(') - text1.count(')'),
        '[': text1.count('[') - text1.count(']'), 
        '{': text1.count('{') - text1.count('}')
    }
    
    if any(count > 0 for count in bracket_counts.values()):
        # Check if second chunk closes brackets
        for bracket, count in bracket_counts.items():
            closing_bracket = {'(': ')', '[': ']', '{': '}'}[bracket]
            if count > 0 and text2.count(closing_bracket) > text2.count(bracket):
                return True
    
    return False


def _is_split_class_or_function(text1: str, text2: str) -> bool:
    # Check if class or function definition is split.
    # Class definition at end of first chunk, methods/attributes at start of second
    if (re.search(r'class\s+\w+.*:\s*$', text1, re.MULTILINE) and 
        re.search(r'^\s*(def\s+\w+|@\w+|\w+\s*=|""")', text2, re.MULTILINE)):
        return True
    
    # Function definition at end, body at start of next
    if (re.search(r'def\s+\w+.*:\s*$', text1, re.MULTILINE) and
        re.search(r'^\s*[a-zA-Z_"\'@]', text2, re.MULTILINE) and
        not re.search(r'^def\s+', text2, re.MULTILINE)):
        return True
    
    return False


def _is_incomplete_sentence(text1: str, text2: str) -> bool:
    # Check if a sentence is incomplete at a page boundary.
    # First chunk ends without proper punctuation
    if not re.search(r'[.!?:]\s*$', text1.strip()):
        # Second chunk starts with lowercase (continuation)
        if re.match(r'^[a-z]', text2.strip()):
            return True
    
    # Check for incomplete method/descriptor explanations
    if (text1.strip().endswith('method is called') or 
        text1.strip().endswith('is called') or
        text1.strip().endswith('This is called')):
        return True
    
    return False


def _is_method_continuation(text1: str, text2: str) -> bool:
    # Check if method/descriptor description continues on next page.
    # Pattern from your example: "__get__(self, obj, owner=None): This is called whenever"
    # followed by description on next page
    
    # Look for descriptor/method definitions at end of first chunk
    descriptor_patterns = [
        r'__\w+__\s*\([^)]*\):\s*This is called',
        r'def\s+\w+\s*\([^)]*\):\s*This',
        r'__\w+__\s*\([^)]*\):\s*$',  # Method signature with no description
        r':\s*This is called\s*$',     # Incomplete "This is called" description
    ]
    
    for pattern in descriptor_patterns:
        if re.search(pattern, text1, re.MULTILINE | re.IGNORECASE):
            # Check if second chunk continues the description
            if (re.match(r'^(whenever|when|if|to|for)', text2.strip(), re.IGNORECASE) or
                re.match(r'^[a-z]', text2.strip())):  # Lowercase continuation
                return True
    
    # Check for method explanations that continue
    if (re.search(r'(setter|getter|property|descriptor|method)\s*\.?\s*$', text1, re.IGNORECASE) and
        re.match(r'^[A-Z]', text2.strip())):  # Next chunk starts explanation
        return True
    
    return False


def _is_list_continuation(text1: str, text2: str) -> bool:
    # Check if numbered/bulleted list continues on next page.
    # First chunk ends with incomplete list item
    if re.search(r'^\s*[\d\-\*•]\s+.*[^.!?]\s*$', text1.split('\n')[-1].strip()):
        # Second chunk starts with list continuation or next item
        if re.match(r'^\s*[\d\-\*•]', text2.strip()):
            return True
    
    # Descriptor protocol example from your text
    if ('descriptor protocol:' in text1.lower() and 
        re.search(r'__\w+__.*:', text2)):
        return True
    
    return False


def _is_same_topic_continuation(text1: str, text2: str) -> bool:
    # Check if content continues the same topic/section.
    # Extract potential section headers
    headers1 = re.findall(r'^[A-Z][A-Za-z\s]+$', text1, re.MULTILINE)
    headers2 = re.findall(r'^[A-Z][A-Za-z\s]+$', text2, re.MULTILINE)
    
    # If first chunk has a header and second doesn't start with new header,
    # might be continuation
    if headers1 and not headers2:
        last_header = headers1[-1].lower()
        # Check if content relates to the header
        if any(word in text2.lower() for word in last_header.split() if len(word) > 3):
            return True
    
    return False


def _merge_chunks(chunk1: Dict[str, Any], chunk2: Dict[str, Any], merge_type: str) -> Dict[str, Any]:
    # Merge two chunks based on merge_type.
    text1 = chunk1.get('text', '').strip()
    text2 = chunk2.get('text', '').strip()
    
    if merge_type == "split_code_block":
        # For code, maintain proper formatting
        merged_text = f"{text1}\n{text2}"
        chunk_type = "Code"  # Merged code should be Code type
        
    elif merge_type == "split_class_function":
        # Class/function definitions with proper spacing
        merged_text = f"{text1}\n{text2}"
        chunk_type = "Code"
        
    elif merge_type == "incomplete_sentence":
        # For sentences, add space if needed
        if text1.endswith(' ') or text2.startswith(' '):
            merged_text = f"{text1}{text2}"
        else:
            merged_text = f"{text1} {text2}"
        chunk_type = chunk1.get('chunk_type', 'Concept')
        
    elif merge_type == "method_continuation":
        # Method descriptions with proper spacing
        if text1.rstrip().endswith(':'):
            merged_text = f"{text1} {text2}"
        else:
            merged_text = f"{text1} {text2}"
        chunk_type = "Concept"  # Method explanations are conceptual
        
    elif merge_type == "list_continuation":
        # Lists with proper line breaks
        merged_text = f"{text1}\n{text2}"
        chunk_type = chunk1.get('chunk_type', 'Concept')
        
    else:  # topic_continuation and others
        merged_text = f"{text1}\n\n{text2}"
        chunk_type = chunk1.get('chunk_type', 'Concept')
    
    # Create merged chunk with combined metadata
    merged_chunk = chunk1.copy()
    merged_chunk.update({
        'text': merged_text,
        'chunk_type': chunk_type,
        'merged_from_pages': [
            chunk1.get('page_number', 0),
            chunk2.get('page_number', 0)
        ],
        'merge_type': merge_type,
        'original_length': chunk1.get('original_length', 0) + chunk2.get('original_length', 0),
        'processed_length': len(merged_text),
        'is_merged': True
    })
    
    return merged_chunk


def enhance_cross_page_chunking(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Enhance chunking by merging content split by page boundaries.
    print(f"🔄 Processing {len(chunks)} chunks for cross-page continuity...")
    
    # Sort chunks by page and order to ensure proper sequence
    sorted_chunks = sorted(chunks, key=lambda x: (x.get('page_number', 0), x.get('sequence_number', 0)))
    
    # Detect and merge split content
    merged_chunks = detect_split_content(sorted_chunks)
    
    # Log merge statistics
    original_count = len(chunks)
    merged_count = len(merged_chunks)
    merge_count = sum(1 for chunk in merged_chunks if chunk.get('is_merged', False))
    
    print(f"✅ Cross-page processing complete:")
    print(f"   Original chunks: {original_count}")
    print(f"   Final chunks: {merged_count}")
    print(f"   Merges performed: {merge_count}")
    
    return merged_chunks


def merge_cross_page_content(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Alias for `detect_split_content`.
    return detect_split_content(chunks)
