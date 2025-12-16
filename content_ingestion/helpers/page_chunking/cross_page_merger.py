import re
from typing import List, Dict, Any, Tuple


def detect_split_content(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # merge content split across page boundaries
    if not chunks:
        return chunks
    
    merged_chunks = []
    i = 0
    
    while i < len(chunks):
        current_chunk = chunks[i]
        
        if i < len(chunks) - 1:
            next_chunk = chunks[i + 1]
            
            should_merge, merge_type = _should_merge_chunks(current_chunk, next_chunk)
            
            if should_merge:
                print(f"Merging chunks due to {merge_type}: pages {current_chunk.get('page_number', '?')} and {next_chunk.get('page_number', '?')}")
                
                merged_chunk = _merge_chunks(current_chunk, next_chunk, merge_type)
                merged_chunks.append(merged_chunk)
                i += 2
                continue
        
        merged_chunks.append(current_chunk)
        i += 1
    
    return merged_chunks


def _should_merge_chunks(chunk1: Dict[str, Any], chunk2: Dict[str, Any]) -> Tuple[bool, str]:
    text1 = chunk1.get('text', '').strip()
    text2 = chunk2.get('text', '').strip()
    
    if not text1 or not text2:
        return False, ""
    
    if _is_split_code_block(text1, text2):
        return True, "split_code_block"
    
    if _is_split_class_or_function(text1, text2):
        return True, "split_class_function"
    
    if _is_incomplete_sentence(text1, text2):
        return True, "incomplete_sentence"
    
    if _is_method_continuation(text1, text2):
        return True, "method_continuation"
    
    if _is_list_continuation(text1, text2):
        return True, "list_continuation"
    
    if _is_same_topic_continuation(text1, text2):
        return True, "topic_continuation"
    
    return False, ""


def _is_split_code_block(text1: str, text2: str) -> bool:
    # incomplete code structures at end-of-page
    code_indicators = [
        (r'class\s+\w+.*:\s*$', r'^\s*(def\s+\w+|@\w+|\w+\s*=)'),
        (r'def\s+\w+.*:\s*$', r'^\s*(""".*?"""|\'\'\'.*?\'\'\'|[a-zA-Z_]\w*)'),
        (r'try:\s*$', r'^\s*(except|finally|else)'),
        (r'(if|for|while)\s+.*:\s*$', r'^\s*[a-zA-Z_]'),
        (r'@\w+\s*$', r'^\s*def\s+\w+'),
        (r'>>>\s*[^>]*$', r'^[^>].*'),
    ]
    
    for pattern1, pattern2 in code_indicators:
        if re.search(pattern1, text1, re.MULTILINE) and re.search(pattern2, text2, re.MULTILINE):
            return True
    
    bracket_counts = {
        '(': text1.count('(') - text1.count(')'),
        '[': text1.count('[') - text1.count(']'), 
        '{': text1.count('{') - text1.count('}')
    }
    
    if any(count > 0 for count in bracket_counts.values()):
        for bracket, count in bracket_counts.items():
            closing_bracket = {'(': ')', '[': ']', '{': '}'}[bracket]
            if count > 0 and text2.count(closing_bracket) > text2.count(bracket):
                return True
    
    return False


def _is_split_class_or_function(text1: str, text2: str) -> bool:
    if (re.search(r'class\s+\w+.*:\s*$', text1, re.MULTILINE) and 
        re.search(r'^\s*(def\s+\w+|@\w+|\w+\s*=|""")', text2, re.MULTILINE)):
        return True
    
    if (re.search(r'def\s+\w+.*:\s*$', text1, re.MULTILINE) and
        re.search(r'^\s*[a-zA-Z_"\'@]', text2, re.MULTILINE) and
        not re.search(r'^def\s+', text2, re.MULTILINE)):
        return True
    
    return False


def _is_incomplete_sentence(text1: str, text2: str) -> bool:
    if not re.search(r'[.!?:]\s*$', text1.strip()):
        if re.match(r'^[a-z]', text2.strip()):
            return True
    
    if (text1.strip().endswith('method is called') or 
        text1.strip().endswith('is called') or
        text1.strip().endswith('This is called')):
        return True
    
    return False


def _is_method_continuation(text1: str, text2: str) -> bool:
    # method/descriptor explanation split across pages
    descriptor_patterns = [
        r'__\w+__\s*\([^)]*\):\s*This is called',
        r'def\s+\w+\s*\([^)]*\):\s*This',
        r'__\w+__\s*\([^)]*\):\s*$',
        r':\s*This is called\s*$',
    ]
    
    for pattern in descriptor_patterns:
        if re.search(pattern, text1, re.MULTILINE | re.IGNORECASE):
            if (re.match(r'^(whenever|when|if|to|for)', text2.strip(), re.IGNORECASE) or
                re.match(r'^[a-z]', text2.strip())):
                return True
    
    if (re.search(r'(setter|getter|property|descriptor|method)\s*\.?\s*$', text1, re.IGNORECASE) and
        re.match(r'^[A-Z]', text2.strip())):
        return True
    
    return False


def _is_list_continuation(text1: str, text2: str) -> bool:
    if re.search(r'^\s*[\d\-\*•]\s+.*[^.!?]\s*$', text1.split('\n')[-1].strip()):
        if re.match(r'^\s*[\d\-\*•]', text2.strip()):
            return True
    
    if ('descriptor protocol:' in text1.lower() and 
        re.search(r'__\w+__.*:', text2)):
        return True
    
    return False


def _is_same_topic_continuation(text1: str, text2: str) -> bool:
    headers1 = re.findall(r'^[A-Z][A-Za-z\s]+$', text1, re.MULTILINE)
    headers2 = re.findall(r'^[A-Z][A-Za-z\s]+$', text2, re.MULTILINE)
    
    if headers1 and not headers2:
        last_header = headers1[-1].lower()
        if any(word in text2.lower() for word in last_header.split() if len(word) > 3):
            return True
    
    return False


def _merge_chunks(chunk1: Dict[str, Any], chunk2: Dict[str, Any], merge_type: str) -> Dict[str, Any]:
    text1 = chunk1.get('text', '').strip()
    text2 = chunk2.get('text', '').strip()
    
    if merge_type == "split_code_block":
        merged_text = f"{text1}\n{text2}"
        chunk_type = "Code"
        
    elif merge_type == "split_class_function":
        merged_text = f"{text1}\n{text2}"
        chunk_type = "Code"
        
    elif merge_type == "incomplete_sentence":
        if text1.endswith(' ') or text2.startswith(' '):
            merged_text = f"{text1}{text2}"
        else:
            merged_text = f"{text1} {text2}"
        chunk_type = chunk1.get('chunk_type', 'Concept')
        
    elif merge_type == "method_continuation":
        if text1.rstrip().endswith(':'):
            merged_text = f"{text1} {text2}"
        else:
            merged_text = f"{text1} {text2}"
        chunk_type = "Concept"
        
    elif merge_type == "list_continuation":
        merged_text = f"{text1}\n{text2}"
        chunk_type = chunk1.get('chunk_type', 'Concept')
        
    else:
        merged_text = f"{text1}\n\n{text2}"
        chunk_type = chunk1.get('chunk_type', 'Concept')
    
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
    print(f"Processing {len(chunks)} chunks for cross-page continuity...")
    
    sorted_chunks = sorted(chunks, key=lambda x: (x.get('page_number', 0), x.get('sequence_number', 0)))
    
    merged_chunks = detect_split_content(sorted_chunks)
    
    original_count = len(chunks)
    merged_count = len(merged_chunks)
    merge_count = sum(1 for chunk in merged_chunks if chunk.get('is_merged', False))
    
    print(f"Cross-page processing complete:")
    print(f"   Original chunks: {original_count}")
    print(f"   Final chunks: {merged_count}")
    print(f"   Merges performed: {merge_count}")
    
    return merged_chunks


def merge_cross_page_content(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return detect_split_content(chunks)
