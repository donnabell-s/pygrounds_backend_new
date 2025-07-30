import re
from unstructured.partition.pdf import partition_pdf
from unstructured.chunking.title import chunk_by_title
from unstructured.cleaners.core import clean_extra_whitespace

def clean_raw_text(text):
    """
    Clean raw text from PDF before processing to remove titles, links, and noise.
    """
    if not text:
        return ""
    
    # Enhanced URL removal with comprehensive patterns
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
    
    # Remove standalone reference numbers [1], [2], etc.
    text = re.sub(r'\[\d+\]', '', text)
    
    # Remove page numbers and footers
    text = re.sub(r'Page \d+ of \d+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\d+$', '', text, flags=re.MULTILINE)
    
    # Remove common PDF artifacts
    text = re.sub(r'Copyright.*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'All rights reserved.*', '', text, flags=re.IGNORECASE)
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

# Enhanced chunk classifier with coding context
def infer_chunk_type(text, default="Concept"):
    """
    Classify chunk type with enhanced detection for coding content.
    Only returns the 5 valid chunk types: Concept, Exercise, Code, Try_It, Example
    """
    text_lower = text.lower()
    
    # Code-specific detection (highest priority)
    if text.strip().startswith(">>>") or ">>>" in text or "..." in text or "import " in text or "def " in text:
        return "Code"
    elif "try it" in text_lower or "try this" in text_lower or "give it a try" in text_lower:
        return "Try_It"
    elif "for example" in text_lower or text_lower.startswith("example:") or "here's an example" in text_lower:
        return "Example"
    elif "exercise" in text_lower or "practice" in text_lower or "challenge" in text_lower:
        return "Exercise"
    else:
        # Everything else is a Concept (includes notes, introductions, definitions, etc.)
        return "Concept"

# Remove visual duplicates and normalize chunk text
def clean_chunk_text(text, subtopic_title=None, topic_title=None, sub_subtopic_title=None, sub_sub_subtopic_title=None):
    """
    Clean and normalize chunk text while preserving code structure.
    Removes titles, links, and other unwanted formatting.
    
    Args:
        text: Raw chunk text
        subtopic_title: Subtopic title to remove from text if present
        topic_title: Topic title to remove from text if present
        sub_subtopic_title: Sub-subtopic title to remove from text if present (3rd level)
        sub_sub_subtopic_title: Sub-sub-subtopic title to remove from text if present (4th level)
    """
    lines = text.strip().split("\n")
    cleaned_lines = []
    
    # Create patterns to match titles
    title_patterns = []
    if subtopic_title:
        # Remove numbering from title (e.g., "17.2. Use matplotlib" -> "Use matplotlib")
        clean_subtopic = re.sub(r'^\d+\.?\d*\.?\s*', '', subtopic_title.strip())
        title_patterns.extend([
            subtopic_title.lower().strip(),
            clean_subtopic.lower().strip(),
            # Also match numbered patterns like "2.2. Windows"
            f"\\d+\\.\\d*\\.?\\s*{re.escape(clean_subtopic.lower().strip())}"
        ])
    if topic_title:
        clean_topic = re.sub(r'^\d+\.?\d*\.?\s*', '', topic_title.strip())
        title_patterns.extend([
            topic_title.lower().strip(),
            clean_topic.lower().strip(),
            # Also match chapter patterns like "Chapter 2 Setting Up Python"
            f"chapter\\s*\\d*\\s*{re.escape(clean_topic.lower().strip())}"
        ])
    if sub_subtopic_title:
        clean_sub_subtopic = re.sub(r'^\d+\.?\d*\.?\d*\.?\s*', '', sub_subtopic_title.strip())
        title_patterns.extend([
            sub_subtopic_title.lower().strip(),
            clean_sub_subtopic.lower().strip(),
            # Also match deep numbered patterns like "2.2.1. Installation Steps"
            f"\\d+\\.\\d+\\.\\d*\\.?\\s*{re.escape(clean_sub_subtopic.lower().strip())}"
        ])
    if sub_sub_subtopic_title:
        clean_sub_sub_subtopic = re.sub(r'^\d+\.?\d*\.?\d*\.?\d*\.?\s*', '', sub_sub_subtopic_title.strip())
        title_patterns.extend([
            sub_sub_subtopic_title.lower().strip(),
            clean_sub_sub_subtopic.lower().strip(),
            # Also match very deep numbered patterns like "2.2.1.3. Advanced Configuration"
            f"\\d+\\.\\d+\\.\\d+\\.\\d*\\.?\\s*{re.escape(clean_sub_sub_subtopic.lower().strip())}"
        ])
    
    for line in lines:
        original_line = line
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
        
        # Check if this line contains title patterns
        line_lower = line.lower()
        should_skip = False
        
        if title_patterns:
            for pattern in title_patterns:
                # Direct substring match
                if isinstance(pattern, str) and not pattern.startswith('\\') and 'chapter' not in pattern:
                    if pattern in line_lower and len(line.split()) <= 12:  # Reasonable line length for titles
                        should_skip = True
                        break
                # Regex pattern match
                elif pattern.startswith('\\') or 'chapter' in pattern:
                    if re.search(pattern, line_lower):
                        should_skip = True
                        break
        
        # Also check for direct "Chapter X Title" pattern
        if topic_title and f"chapter" in line_lower and topic_title.lower() in line_lower:
            should_skip = True
        
        # Also check for sub-subtopic patterns
        if sub_subtopic_title and sub_subtopic_title.lower() in line_lower and len(line.split()) <= 15:
            should_skip = True
        
        # Also check for sub-sub-subtopic patterns
        if sub_sub_subtopic_title and sub_sub_subtopic_title.lower() in line_lower and len(line.split()) <= 15:
            should_skip = True
        
        if should_skip:
            continue
            
        # Remove common title patterns
        if (line.isupper() and len(line) < 100) or \
           (line.startswith('#') and not line.startswith('# ')) or \
           (line.endswith(':') and len(line.split()) <= 4):
            continue
            
        # Enhanced URL and link removal with comprehensive patterns
        # Remove URLs with various protocols and special characters
        line = re.sub(r'https?://[^\s]+', '', line)
        line = re.sub(r'https?:/[^\s]*', '', line)  # Catch partial protocols
        line = re.sub(r'www\.[^\s]+', '', line)
        line = re.sub(r'[a-zA-Z0-9.-]+\.(com|org|net|edu|gov|io)[^\s]*', '', line)
        
        # Remove URLs with Unicode characters like /​/​
        line = re.sub(r'https?:/​/​[^\s]*', '', line)
        line = re.sub(r'[a-zA-Z0-9.-]+\.​[a-zA-Z0-9.-]+[^\s]*', '', line)
        
        # Remove partial URLs and paths that look like URLs
        line = re.sub(r'/​[a-zA-Z0-9._-]+/[^\s]*', '', line)  # Paths with Unicode slash
        line = re.sub(r'/[a-zA-Z0-9._-]+/[a-zA-Z0-9._/-]*', '', line)  # Regular paths
        line = re.sub(r'[a-zA-Z0-9.-]+\.​[a-zA-Z]+', '', line)  # Domains with Unicode dot
        
        # Remove GitHub and repository-specific patterns
        line = re.sub(r'github\.com[^\s]*', '', line)
        line = re.sub(r'PacktPublishing[^\s]*', '', line)
        line = re.sub(r'Expert-​Python[^\s]*', '', line)
        line = re.sub(r'/​tree/​[^\s]*', '', line)
        line = re.sub(r'/​master/​[^\s]*', '', line)
        
        # Remove incomplete URLs that start with protocol but are broken
        line = re.sub(r'https:/​/​\s*for\s+this\s+chapter', 'for this chapter', line)
        line = re.sub(r'https:/​/​\s*', '', line)
        
        # Remove markdown links [text](url)
        line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)
        
        # Remove standalone markdown reference links [1], [2], etc.
        line = re.sub(r'\[\d+\]', '', line)
        
        # Remove page numbers and references like "Page 1 of 10"
        line = re.sub(r'Page \d+ of \d+', '', line, flags=re.IGNORECASE)
        line = re.sub(r'^\d+$', '', line)  # Standalone numbers
        
        # Remove chapter/section headers that are just numbers and titles
        if re.match(r'^\d+\.?\s*[A-Z][a-z\s]+$', line) and len(line.split()) <= 5:
            continue
            
        # Clean up the line
        line = re.sub(r'\s+', ' ', line).strip()
        
        if line:  # Only add non-empty lines
            cleaned_lines.append(line)
    
    # Handle duplicate line detection more carefully for code
    if len(cleaned_lines) > 1 and cleaned_lines[0] == cleaned_lines[1]:
        # Only remove duplicates if they don't look like code
        if not (">>>" in cleaned_lines[0] or cleaned_lines[0].strip().startswith(("def ", "class ", "import ", "from "))):
            cleaned_lines.pop(0)
    
    # Handle duplicate segments for non-code content
    if len(cleaned_lines) == 1 and cleaned_lines[0]:
        segments = cleaned_lines[0].split()
        mid = len(segments) // 2
        if mid > 0 and segments[:mid] == segments[mid:]:
            # Check if this might be code before removing duplicates
            if not any(code_indicator in cleaned_lines[0] for code_indicator in [">>>", "def ", "import ", "="]):
                cleaned_lines[0] = " ".join(segments[:mid])
    
    result = "\n".join(cleaned_lines).strip()
    
    # Final cleanup - remove excessive whitespace
    result = re.sub(r'\n\s*\n\s*\n', '\n\n', result)  # Max 2 consecutive newlines
    result = re.sub(r'\s+', ' ', result)  # Normalize spaces
    
    return result

def create_contextual_code_chunk(code_text, surrounding_elements, element_index):
    """
    Create a code chunk with surrounding context for better RAG understanding.
    
    Args:
        code_text: The raw code content
        surrounding_elements: List of nearby text elements
        element_index: Index of current element in the list
        
    Returns:
        Enhanced code text with context
    """
    context_parts = []
    
    # Look for context before the code (up to 2 elements back)
    context_before = []
    for i in range(max(0, element_index - 2), element_index):
        if i < len(surrounding_elements):
            elem_text = getattr(surrounding_elements[i], 'text', '').strip()
            if elem_text and len(elem_text) > 20:  # Meaningful context
                # Check if it's explanatory text
                if any(indicator in elem_text.lower() for indicator in [
                    "example", "try", "use", "type", "enter", "run", "execute",
                    "following", "shows", "demonstrates", "illustrates"
                ]):
                    context_before.append(elem_text)
    
    # Look for context after the code (up to 1 element forward)
    context_after = []
    for i in range(element_index + 1, min(len(surrounding_elements), element_index + 2)):
        if i < len(surrounding_elements):
            elem_text = getattr(surrounding_elements[i], 'text', '').strip()
            if elem_text and len(elem_text) > 15:  # Meaningful context
                # Check if it's explanatory text
                if any(indicator in elem_text.lower() for indicator in [
                    "output", "result", "returns", "prints", "displays",
                    "this", "notice", "see", "above", "code"
                ]):
                    context_after.append(elem_text)
    
    # Build contextual chunk
    if context_before:
        context_parts.extend(context_before[-1:])  # Take most recent context
    
    context_parts.append(f"CODE:\n{code_text}")
    
    if context_after:
        context_parts.extend(context_after[:1])  # Take immediate following context
    
    return "\n\n".join(context_parts)

def create_contextual_exercise_chunk(exercise_text, surrounding_elements, element_index):
    """
    Create an exercise chunk with surrounding context for better RAG understanding.
    """
    context_parts = []
    
    # Look for instructional context before the exercise
    context_before = []
    for i in range(max(0, element_index - 1), element_index):
        if i < len(surrounding_elements):
            elem_text = getattr(surrounding_elements[i], 'text', '').strip()
            if elem_text and len(elem_text) > 30:
                # Check if it's instructional or explanatory
                if any(indicator in elem_text.lower() for indicator in [
                    "practice", "now", "try", "apply", "use what", "time to",
                    "your turn", "test", "skill", "knowledge"
                ]):
                    context_before.append(elem_text)
    
    # Build contextual exercise chunk
    if context_before:
        context_parts.extend(context_before)
    
    context_parts.append(f"EXERCISE:\n{exercise_text}")
    
    return "\n\n".join(context_parts)

# Enhanced PDF parsing with contextual chunking
def extract_unstructured_chunks(file_path):
    """
    Parse PDF into text chunks with enhanced context preservation for coding content.
    """
    raw_elements = partition_pdf(filename=file_path, strategy="hi_res")
    cleaned_elements = []
    
    for el in raw_elements:
        if hasattr(el, "text") and el.text:
            el.text = clean_extra_whitespace(el.text)
            cleaned_elements.append(el)

    # Use smaller max_characters for better granularity, larger overlap for context
    chunks = chunk_by_title(cleaned_elements, max_characters=400, overlap=75)

    enhanced_chunks = []
    
    for i, chunk in enumerate(chunks):
        chunk_text = chunk.text if hasattr(chunk, "text") else str(chunk)
        chunk_type = infer_chunk_type(chunk_text)
        
        # Create contextual chunks for coding-related content
        if chunk_type in ["Code", "Exercise", "Try_It"]:
            if chunk_type == "Code":
                enhanced_text = create_contextual_code_chunk(
                    chunk_text, cleaned_elements, i
                )
            elif chunk_type in ["Exercise", "Try_It"]:
                enhanced_text = create_contextual_exercise_chunk(
                    chunk_text, cleaned_elements, i
                )
            else:
                enhanced_text = chunk_text
        else:
            enhanced_text = chunk_text
        
        enhanced_chunks.append({
            "content": clean_chunk_text(enhanced_text),
            "chunk_type": chunk_type,
            "source": "unstructured_enhanced",
            "has_context": chunk_type in ["Code", "Exercise", "Try_It"],
            "original_type": chunk_type
        })

    return enhanced_chunks
