"""
RAG context operations for retrieving and formatting semantic content.
Handles semantic similarity retrieval and context formatting for question generation.
"""

from typing import Optional
from django.db import models


def get_rag_context_for_subtopic(subtopic, difficulty: str) -> str:
    """
    Retrieve RAG context using SemanticSubtopic ranked chunks.
    
    This function is the core of our RAG system:
    1. Gets pre-computed semantic similarity scores from SemanticSubtopic
    2. Retrieves top-ranked chunk IDs based on difficulty requirements
    3. Fetches actual chunk content from database
    4. Formats context for LLM consumption
    
    Args:
        subtopic: Subtopic instance to generate context for
        difficulty: One of ['beginner', 'intermediate', 'advanced', 'master']
        
    Returns:
        str: Formatted context string for LLM, including chunks and metadata
    """
    try:
        from question_generation.models import SemanticSubtopic
        from content_ingestion.models import DocumentChunk
        
        # Try to get pre-computed semantic analysis for this subtopic
        try:
            semantic_subtopic = SemanticSubtopic.objects.get(subtopic=subtopic)
        except SemanticSubtopic.DoesNotExist:
            # Fallback: Generate basic context from subtopic metadata
            return f"""
Topic: {subtopic.topic.name}
Subtopic: {subtopic.name}
Difficulty: {difficulty}

No semantic analysis available for this subtopic.
Please generate questions based on the subtopic name and difficulty level.
Focus on {difficulty}-level concepts related to {subtopic.name}.
"""
        
        # Unified retrieval configuration for all difficulty levels
        config = {
            'top_k': 15,                    # Retrieve at most 15 chunks
            'min_similarity': 0.5,          # 50% minimum similarity threshold
        }
        
        # Get ranked chunk IDs
        chunk_ids = semantic_subtopic.get_top_chunk_ids(
            limit=config['top_k'],
            min_similarity=config['min_similarity']
        )
        
        if not chunk_ids:
            return f"""
Topic: {subtopic.topic.name}
Subtopic: {subtopic.name}
Difficulty: {difficulty}

No relevant chunks found above similarity threshold (50%).
Please generate questions based on the subtopic name and difficulty level.
Focus on {difficulty}-level concepts related to {subtopic.name}.
"""
        
        # Fetch actual chunks from database
        chunks = DocumentChunk.objects.filter(id__in=chunk_ids).order_by(
            models.Case(*[models.When(id=chunk_id, then=idx) for idx, chunk_id in enumerate(chunk_ids)])
        )
        
        # Build context from chunks
        context_parts = []
        chunk_types_found = set()
        
        for chunk in chunks:
            chunk_types_found.add(chunk.chunk_type or 'Unknown')
            
            # Format chunk with metadata
            chunk_context = f"""
--- {chunk.chunk_type or 'Content'} ---
{chunk.text.strip()}

Document: {chunk.document.title}
"""
            context_parts.append(chunk_context.strip())
        
        # Create final context with metadata
        context = f"""
Topic: {subtopic.topic.name}
Subtopic: {subtopic.name}
Difficulty: {difficulty}
Content Types Found: {', '.join(sorted(chunk_types_found))}
Retrieved Chunks: {len(context_parts)}

LEARNING CONTENT:
{chr(10).join(context_parts)}
"""
        return context.strip()
        
    except Exception as e:
        print(f"⚠️ Error retrieving RAG context for {subtopic.name}: {str(e)}")
        return f"""
Topic: {subtopic.topic.name}
Subtopic: {subtopic.name}
Difficulty: {difficulty}

Error retrieving context: {str(e)}
Please generate questions based on the subtopic name and difficulty level.
"""


def get_combined_rag_context(subtopic_combination, difficulty: str) -> str:
    """
    Get combined RAG context for multiple subtopics.
    
    Args:
        subtopic_combination: List/queryset of subtopics
        difficulty: Difficulty level
        
    Returns:
        str: Combined context for all subtopics
    """
    try:
        combined_contexts = []
        subtopic_names = []
        
        for subtopic in subtopic_combination:
            subtopic_names.append(subtopic.name)
            context = get_rag_context_for_subtopic(subtopic, difficulty)
            
            # Extract just the learning content part
            if "LEARNING CONTENT:" in context:
                content_part = context.split("LEARNING CONTENT:")[1].strip()
                combined_contexts.append(f"=== {subtopic.name} ===\n{content_part}")
            else:
                combined_contexts.append(f"=== {subtopic.name} ===\n{context}")
        
        if not combined_contexts:
            return f"""
FALLBACK MODE: No semantic content chunks were found for these subtopics.
Please generate questions based on general Python knowledge for these topics:
{chr(10).join([f"- {name}: Focus on {difficulty}-level concepts" for name in subtopic_names])}

LEARNING CONTEXT:
These subtopics are from learning progression.
Create questions that would be appropriate for learners at the {difficulty} level.
"""
        
        combined_context = f"""
DIFFICULTY LEVEL: {difficulty.upper()}
SUBTOPIC COMBINATION: {' + '.join(subtopic_names)}

""" + "\n\n".join(combined_contexts)
        
        return combined_context
        
    except Exception as e:
        print(f"⚠️ Error combining RAG contexts: {str(e)}")
        return f"""
Error retrieving combined context: {str(e)}
Please generate questions for: {', '.join([s.name for s in subtopic_combination])}
Focus on {difficulty}-level concepts.
"""


def format_rag_context_for_prompt(rag_context: str, subtopic_names: list, difficulty: str) -> str:
    """
    Format RAG context specifically for prompt consumption.
    
    Args:
        rag_context: Raw RAG context
        subtopic_names: List of subtopic names
        difficulty: Difficulty level
        
    Returns:
        str: Formatted context ready for LLM prompts
    """
    if "No semantic analysis available" in rag_context or "No relevant chunks found" in rag_context:
        return f"""
FALLBACK MODE: No semantic content chunks were found for these subtopics.
Please generate questions based on general Python knowledge for these topics:
{chr(10).join([f"- {name}: Focus on {difficulty}-level concepts" for name in subtopic_names])}

LEARNING CONTEXT:
These subtopics are from the learning progression.
Create questions that would be appropriate for learners at the {difficulty} level.
"""
    
    return rag_context
