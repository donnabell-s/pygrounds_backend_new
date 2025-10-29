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
        from django.db import connection, transaction
        
        # Force database connection cleanup before starting
        connection.close_if_unneeded_or_obsolete()
        
        # Try to get pre-computed semantic analysis for this subtopic
        try:
            semantic_subtopic = SemanticSubtopic.objects.select_related('subtopic__topic').get(subtopic=subtopic)
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
        
        # Build context from chunks - format each chunk clearly for LLM
        context_parts = []
        chunk_types_found = set()
        
        for i, chunk in enumerate(chunks, 1):
            chunk_types_found.add(chunk.chunk_type or 'Unknown')
            
            # Format each chunk as a clearly separated, numbered section
            chunk_context = f"""
[CHUNK {i}/{len(chunks)} - {chunk.chunk_type or 'Content'}]
Source: {chunk.document.title}
Page: {chunk.page_number}

CONTENT:
{chunk.text.strip()}

[END CHUNK {i}]
"""
            context_parts.append(chunk_context.strip())
        
        # Create final context with clear chunk separation for LLM
        context = f"""
TOPIC: {subtopic.topic.name}
SUBTOPIC: {subtopic.name}
GAME TYPE: {game_type}
CONTENT TYPES FOUND: {', '.join(sorted(chunk_types_found))}
TOTAL CHUNKS RETRIEVED: {len(context_parts)}

IMPORTANT: Each [CHUNK X/Y] section below contains separate, independent content.
Use these chunks individually or in combination to generate {game_type} questions.
Do not treat them as continuous text - they are distinct learning materials.

{'='*80}
RETRIEVED LEARNING CHUNKS:
{'='*80}

{chr(10).join(context_parts)}

{'='*80}
END OF RETRIEVED CHUNKS
{'='*80}
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
            
            # Extract just the learning content part (chunks)
            if "RETRIEVED LEARNING CHUNKS:" in context:
                content_part = context.split("RETRIEVED LEARNING CHUNKS:")[1].split("END OF RETRIEVED CHUNKS")[0].strip()
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

IMPORTANT: Each section below contains separate chunks from different subtopics.
Use these chunks individually or in combination to generate {game_type} questions.
Do not treat them as continuous text - they are distinct learning materials from different topics.

{'='*100}
COMBINED LEARNING CHUNKS FROM MULTIPLE SUBTOPICS:
{'='*100}

""" + "\n\n".join(combined_contexts) + f"""

{'='*100}
END OF COMBINED CHUNKS
{'='*100}
"""
        
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


def get_batched_rag_contexts(subtopic_combinations: list, difficulty: str, game_type: str = 'non_coding') -> dict:
    """
    Batch fetch RAG contexts for multiple subtopic combinations to reduce database connections.
    
    Args:
        subtopic_combinations: List of tuples/lists of Subtopic objects
        difficulty: Difficulty level
        game_type: 'coding' or 'non_coding'
        
    Returns:
        dict: Mapping of subtopic combination tuples to their RAG contexts
    """
    from content_ingestion.models import SemanticSubtopic, DocumentChunk
    from django.db import connection, transaction
    import itertools
    
    # Force database connection cleanup
    connection.close_if_unneeded_or_obsolete()
    
    results = {}
    
    # Flatten all unique subtopics from combinations
    all_subtopics = set()
    for combo in subtopic_combinations:
        if isinstance(combo, (list, tuple)):
            all_subtopics.update(combo)
        else:
            all_subtopics.add(combo)
    
    # Batch fetch all semantic subtopics in one query
    subtopic_ids = [s.id for s in all_subtopics]
    semantic_subtopics = {
        ss.subtopic_id: ss 
        for ss in SemanticSubtopic.objects.select_related('subtopic__topic').filter(subtopic_id__in=subtopic_ids)
    }
    
    # For each combination, get RAG context
    for combo in subtopic_combinations:
        if isinstance(combo, (list, tuple)) and len(combo) == 1:
            # Single subtopic
            subtopic = combo[0]
            results[combo] = get_rag_context_for_subtopic(subtopic, difficulty, game_type)
        elif isinstance(combo, (list, tuple)) and len(combo) > 1:
            # Multiple subtopics - use combined context
            results[combo] = get_combined_rag_context(combo, difficulty, game_type)
        else:
            # Single subtopic (not in tuple)
            results[(combo,)] = get_rag_context_for_subtopic(combo, difficulty, game_type)
    
    return results
