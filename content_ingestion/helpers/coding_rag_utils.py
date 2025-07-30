"""
Enhanced embedding strategies for coding content in RAG system.
Optimized for contextual chunks created by unstructured library.
"""

def create_coding_context_for_embedding(chunk_text, chunk_type, topic_title="", subtopic_title=""):
    """
    Create rich context for coding chunks to improve semantic similarity matching.
    
    Args:
        chunk_text: The text content of the chunk
        chunk_type: Type of the chunk (Exercise, Code, Try_It, etc.)
        topic_title: Topic title for context
        subtopic_title: Subtopic title for context
        
    Returns:
        str: Enhanced text for better embedding representation
    """
    
    context_parts = []
    
    # Add topic/subtopic context for better semantic matching
    if topic_title:
        context_parts.append(f"Learning Topic: {topic_title}")
    if subtopic_title:
        context_parts.append(f"Specific Area: {subtopic_title}")
    
    # Enhance based on chunk type with coding-specific context
    if chunk_type == "Exercise":
        context_parts.append("Programming exercise and practice problem")
        context_parts.append("Coding challenge for skill development and learning")
        
        # Extract difficulty indicators from exercise text
        if any(word in chunk_text.lower() for word in ["advanced", "complex", "challenging"]):
            context_parts.append("Advanced programming exercise")
        elif any(word in chunk_text.lower() for word in ["basic", "simple", "beginner", "introduction"]):
            context_parts.append("Beginner-friendly programming exercise")
        
    elif chunk_type == "Try_It":
        context_parts.append("Interactive hands-on coding practice section")
        context_parts.append("Learn by doing programming activity")
        
    elif chunk_type == "Code":
        context_parts.append("Programming code example and implementation")
        context_parts.append("Code snippet demonstration for learning")
        
        # Try to extract programming concepts from code
        code_concepts = extract_programming_concepts(chunk_text)
        if code_concepts:
            context_parts.append(f"Programming concepts demonstrated: {', '.join(code_concepts)}")
        
        # Check if it's contextual code (has explanatory text)
        if any(indicator in chunk_text.lower() for indicator in [
            "example", "shows", "demonstrates", "following", "above", "code"
        ]):
            context_parts.append("Explained code example with context")
            
    elif chunk_type == "Example":
        context_parts.append("Programming example demonstration and illustration")
        context_parts.append("Real-world coding example for understanding")
        
    elif chunk_type == "Concept":
        context_parts.append("Programming concept explanation and theory")
        context_parts.append("Fundamental programming knowledge and understanding")
        
    # Add programming domain indicators based on content
    programming_domains = detect_programming_domain(chunk_text)
    if programming_domains:
        context_parts.append(f"Programming domains: {', '.join(programming_domains)}")
    
    # Combine context with original text for enhanced embedding
    if context_parts:
        enhanced_text = f"{' | '.join(context_parts)}. CONTENT: {chunk_text}"
    else:
        enhanced_text = chunk_text
        
    return enhanced_text

def detect_programming_domain(text):
    """
    Detect programming domains/areas from text content.
    
    Args:
        text: Text content to analyze
        
    Returns:
        list: Programming domains detected
    """
    domains = []
    text_lower = text.lower()
    
    domain_keywords = {
        'data_types': ['string', 'integer', 'float', 'boolean', 'list', 'dictionary', 'tuple'],
        'control_flow': ['if', 'else', 'elif', 'for', 'while', 'loop', 'condition'],
        'functions': ['def', 'function', 'return', 'parameter', 'argument', 'call'],
        'input_output': ['print', 'input', 'output', 'display', 'user input', 'console'],
        'string_manipulation': ['split', 'join', 'replace', 'upper', 'lower', 'strip'],
        'error_handling': ['try', 'except', 'error', 'exception', 'debugging'],
        'file_operations': ['file', 'read', 'write', 'open', 'close'],
        'object_oriented': ['class', 'object', 'method', 'inheritance', 'attribute'],
        'data_structures': ['array', 'stack', 'queue', 'tree', 'graph']
    }
    
    for domain, keywords in domain_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            domains.append(domain.replace('_', ' '))
    
    return domains

def extract_programming_concepts(code_text):
    """
    Extract programming concepts from code text for better embedding context.
    
    Args:
        code_text: String containing code
        
    Returns:
        list: Programming concepts found in the code
    """
    concepts = []
    
    # Python keywords and concepts
    python_concepts = {
        'def ': 'function definition',
        'class ': 'class definition', 
        'for ': 'for loop',
        'while ': 'while loop',
        'if ': 'conditional statement',
        'try:': 'error handling',
        'except': 'exception handling',
        'import ': 'module import',
        'return ': 'function return',
        'print(': 'output operation',
        'input(': 'input operation',
        'len(': 'length function',
        'range(': 'range function',
        'list(': 'list creation',
        'dict(': 'dictionary creation',
        'str(': 'string conversion',
        'int(': 'integer conversion',
        'float(': 'float conversion',
        '[]': 'list operations',
        '{}': 'dictionary operations',
        'append(': 'list append',
        'split(': 'string split',
        'join(': 'string join',
        '==': 'equality comparison',
        '!=': 'inequality comparison',
        '+=': 'compound assignment',
        'and ': 'logical AND',
        'or ': 'logical OR',
        'not ': 'logical NOT'
    }
    
    for pattern, concept in python_concepts.items():
        if pattern in code_text:
            concepts.append(concept)
    
    return list(set(concepts))  # Remove duplicates

def get_coding_chunks_for_minigame(document_id, learning_topics=None):
    """
    Retrieve and rank coding chunks for minigame generation with enhanced context.
    
    Args:
        document_id: ID of the document
        learning_topics: List of Topic/Subtopic objects for context matching
        
    Returns:
        dict: Structured coding content for minigame generation
    """
    from content_ingestion.models import DocumentChunk
    
    # Get coding-specific chunk types
    coding_types = ['Exercise', 'Try_It', 'Code', 'Example', 'Concept']
    
    chunks = DocumentChunk.objects.filter(
        document_id=document_id,
        chunk_type__in=coding_types,
        embeddings__isnull=False  # Only chunks with embeddings
    ).order_by('page_number', 'order_in_doc')
    
    # Organize by type with enhanced context
    coding_content = {
        'exercises': [],
        'examples': [],
        'concepts': [],
        'try_it_activities': [],
        'code_snippets': []
    }
    
    for chunk in chunks:
        enhanced_context = create_coding_context_for_embedding(chunk)
        
        chunk_data = {
            'id': chunk.id,
            'text': chunk.text,
            'enhanced_context': enhanced_context,
            'topic': chunk.topic_title,
            'subtopic': chunk.subtopic_title,
            'page': chunk.page_number,
            'programming_concepts': extract_programming_concepts(chunk.text)
        }
        
        # Categorize for minigame use
        if chunk.chunk_type == 'Exercise':
            coding_content['exercises'].append(chunk_data)
        elif chunk.chunk_type == 'Example':
            coding_content['examples'].append(chunk_data)
        elif chunk.chunk_type == 'Concept':
            coding_content['concepts'].append(chunk_data)
        elif chunk.chunk_type == 'Try_It':
            coding_content['try_it_activities'].append(chunk_data)
        elif chunk.chunk_type == 'Code':
            coding_content['code_snippets'].append(chunk_data)
    
    return coding_content

# Example usage for semantic similarity with topics
def match_chunks_to_learning_topics(chunks, topics, similarity_threshold=0.7):
    """
    DEPRECATED: Topic embeddings have been removed.
    This function is no longer functional.
    
    Use subtopic-based matching instead via the Embedding model.
    """
    return {}
