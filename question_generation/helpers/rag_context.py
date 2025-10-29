# RAG (Retrieval Augmented Generation) context manager
# Gets relevant content chunks based on semantic similarity

from typing import Optional
from django.db import models
import logging
logger = logging.getLogger(__name__)

def get_rag_context_for_subtopic(subtopic, difficulty: str, game_type: str = 'non_coding') -> str:
    # Get relevant content chunks for question generation
    # Uses semantic similarity to fetch best matching content based on game type
    #
    # Process:
    # 1. Get semantic subtopic data
    # 2. Select chunks based on game_type (coding prioritizes code chunks, non_coding prioritizes concept chunks)
    # 3. Format context for LLM
    try:
        from content_ingestion.models import SemanticSubtopic  # Moved to content_ingestion
        from content_ingestion.models import DocumentChunk
        
        # Try to get pre-computed semantic analysis for this subtopic
        try:
            semantic_subtopic = SemanticSubtopic.objects.get(subtopic=subtopic)
        except SemanticSubtopic.DoesNotExist:
            # Fallback: Generate basic context from subtopic metadata
            return f"""
Topic: {subtopic.topic.name}
Subtopic: {subtopic.name}
Game Type: {game_type}

No semantic analysis available for this subtopic.
Please generate {game_type} questions based on the subtopic name.
Focus on {game_type}-appropriate content related to {subtopic.name}.
"""
        
        # Chunk retrieval configuration
        config = {
            'top_k': 15,                    # Retrieve at most 15 chunks
            'min_similarity': 0.5,          # 50% minimum similarity threshold
        }
        
        # Get ranked chunk IDs based on game type
        if game_type == 'coding':
            # For coding questions, prioritize code chunks (CodeBERT rankings)
            chunk_ids = semantic_subtopic.get_code_chunk_ids(
                limit=config['top_k'],
                min_similarity=config['min_similarity']
            )
            # If no code chunks found, fallback to concept chunks
            if not chunk_ids:
                chunk_ids = semantic_subtopic.get_concept_chunk_ids(
                    limit=config['top_k']//2,
                    min_similarity=config['min_similarity']
                )
        else:  # non_coding
            # For non-coding questions, prioritize concept chunks (MiniLM rankings)
            chunk_ids = semantic_subtopic.get_concept_chunk_ids(
                limit=config['top_k'],
                min_similarity=config['min_similarity']
            )
            # If no concept chunks found, fallback to code chunks
            if not chunk_ids:
                chunk_ids = semantic_subtopic.get_code_chunk_ids(
                    limit=config['top_k']//2,
                    min_similarity=config['min_similarity']
                )
        
        if not chunk_ids:
            return f"""
Topic: {subtopic.topic.name}
Subtopic: {subtopic.name}
Game Type: {game_type}

No relevant {game_type} chunks found above similarity threshold (50%).
Please generate {game_type} questions based on the subtopic name.
Focus on {game_type}-appropriate content related to {subtopic.name}.
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
Game Type: {game_type}
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
Game Type: {game_type}

Error retrieving context: {str(e)}
Please generate {game_type} questions based on the subtopic name.
"""


def get_combined_rag_context(subtopic_combination, difficulty: str, game_type: str = 'non_coding') -> str:
    """
    Get combined RAG context for multiple subtopics.
    
    Args:
        subtopic_combination: List/queryset of subtopics
        difficulty: Difficulty level (kept for backward compatibility in prompts)
        game_type: 'coding' or 'non_coding' to determine chunk type selection
        
    Returns:
        str: Combined context for all subtopics
    """
    try:
        combined_contexts = []
        subtopic_names = []
        
        for subtopic in subtopic_combination:
            subtopic_names.append(subtopic.name)
            context = get_rag_context_for_subtopic(subtopic, difficulty, game_type)
            
            # Extract just the learning content part
            if "LEARNING CONTENT:" in context:
                content_part = context.split("LEARNING CONTENT:")[1].strip()
                combined_contexts.append(f"=== {subtopic.name} ===\n{content_part}")
            else:
                combined_contexts.append(f"=== {subtopic.name} ===\n{context}")
        
        if not combined_contexts:
            return f"""
FALLBACK MODE: No semantic content chunks were found for these subtopics.
Please generate {game_type} questions based on general Python knowledge for these topics:
{chr(10).join([f"- {name}: Focus on {game_type}-appropriate content" for name in subtopic_names])}

LEARNING CONTEXT:
These subtopics are from learning progression.
Create {game_type} questions that would be appropriate for learners.
"""
        
        combined_context = f"""
GAME TYPE: {game_type.upper()}
DIFFICULTY LEVEL: {difficulty.upper()}
SUBTOPIC COMBINATION: {' + '.join(subtopic_names)}

""" + "\n\n".join(combined_contexts)
        
        return combined_context
        
    except Exception as e:
        print(f"⚠️ Error combining RAG contexts: {str(e)}")
        return f"""
Error retrieving combined context: {str(e)}
Please generate {game_type} questions for: {', '.join([s.name for s in subtopic_combination])}
Focus on {game_type}-appropriate content.
"""


def format_rag_context_for_prompt(rag_context: str, subtopic_names: list, difficulty: str, game_type: str = 'non_coding') -> str:
    """
    Format RAG context specifically for prompt consumption.
    
    Args:
        rag_context: Raw RAG context
        subtopic_names: List of subtopic names
        difficulty: Difficulty level (kept for backward compatibility)
        game_type: 'coding' or 'non_coding' for content type focus
        
    Returns:
        str: Formatted context ready for LLM prompts
    """
    if "No semantic analysis available" in rag_context or "No relevant chunks found" in rag_context:
        return f"""
FALLBACK MODE: No semantic content chunks were found for these subtopics.
Please generate {game_type} questions based on general Python knowledge for these topics:
{chr(10).join([f"- {name}: Focus on {game_type}-appropriate content" for name in subtopic_names])}

LEARNING CONTEXT:
These subtopics are from the learning progression.
Create {game_type} questions that would be appropriate for learners.
"""
    
    return rag_context
