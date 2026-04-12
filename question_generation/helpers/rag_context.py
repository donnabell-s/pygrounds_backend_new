import logging
from django.db import models

logger = logging.getLogger(__name__)

_TOP_K        = 15
_MIN_SIMILARITY = 0.5

# Which book difficulty levels are appropriate for each generation difficulty.
# Cumulative pools: harder questions can draw from easier books too,
# but not the other way around.
_DIFFICULTY_POOLS = {
    'beginner':     ['beginner'],
    'intermediate': ['beginner', 'intermediate'],
    'advanced':     ['intermediate', 'advanced'],
    'master':       ['advanced', 'master'],
}


# ── Single subtopic ────────────────────────────────────────────────────────────

def get_rag_context_for_subtopic(subtopic, difficulty: str, game_type: str = 'non_coding') -> str:
    """
    Fetch ranked document chunks for a subtopic and format them as an LLM context string.
    Falls back to a minimal stub when no semantic data or matching chunks exist.
    """
    try:
        from content_ingestion.models import DocumentChunk, SemanticSubtopic

        try:
            semantic = SemanticSubtopic.objects.get(subtopic=subtopic)
        except SemanticSubtopic.DoesNotExist:
            return _fallback_context(subtopic, game_type, reason="No semantic analysis available")

        chunk_ids = _get_chunk_ids(semantic, game_type)
        if not chunk_ids:
            return _fallback_context(subtopic, game_type, reason=f"No relevant {game_type} chunks found above similarity threshold")

        allowed_difficulties = _DIFFICULTY_POOLS.get(difficulty, list(_DIFFICULTY_POOLS.keys()))
        chunks = DocumentChunk.objects.filter(
            id__in=chunk_ids,
            document__difficulty__in=allowed_difficulties,
        ).order_by(
            models.Case(*[models.When(id=cid, then=idx) for idx, cid in enumerate(chunk_ids)])
        )

        # If the difficulty filter removed everything, fall back to all matched chunks
        if not chunks.exists():
            chunks = DocumentChunk.objects.filter(id__in=chunk_ids).order_by(
                models.Case(*[models.When(id=cid, then=idx) for idx, cid in enumerate(chunk_ids)])
            )

        chunk_types = set()
        parts = []
        for chunk in chunks:
            chunk_types.add(chunk.chunk_type or 'Unknown')
            parts.append(f"--- {chunk.chunk_type or 'Content'} ---\n{chunk.text.strip()}\nDocument: {chunk.document.title}")

        return (
            f"Topic: {subtopic.topic.name}\n"
            f"Subtopic: {subtopic.name}\n"
            f"Game Type: {game_type}\n"
            f"Content Types Found: {', '.join(sorted(chunk_types))}\n"
            f"Retrieved Chunks: {len(parts)}\n\n"
            f"LEARNING CONTENT:\n" + "\n\n".join(parts)
        )

    except Exception as e:
        logger.error(f"RAG context retrieval failed for {subtopic.name}: {e}")
        return _fallback_context(subtopic, game_type, reason=f"Error: {e}")


# ── Multi-subtopic ─────────────────────────────────────────────────────────────

def get_combined_rag_context(subtopic_combination, difficulty: str, game_type: str = 'non_coding') -> str:
    """Merge individual subtopic contexts into a single combined context string."""
    try:
        parts = []
        names = []
        for subtopic in subtopic_combination:
            names.append(subtopic.name)
            ctx = get_rag_context_for_subtopic(subtopic, difficulty, game_type)
            content = ctx.split("LEARNING CONTENT:")[1].strip() if "LEARNING CONTENT:" in ctx else ctx
            parts.append(f"=== {subtopic.name} ===\n{content}")

        if not parts:
            return _multi_fallback(names, game_type)

        return (
            f"GAME TYPE: {game_type.upper()}\n"
            f"DIFFICULTY LEVEL: {difficulty.upper()}\n"
            f"SUBTOPIC COMBINATION: {' + '.join(names)}\n\n"
            + "\n\n".join(parts)
        )

    except Exception as e:
        logger.error(f"Combined RAG context failed: {e}")
        names = [s.name for s in subtopic_combination]
        return f"Error retrieving combined context: {e}\nPlease generate {game_type} questions for: {', '.join(names)}"


# ── Batch fetch ────────────────────────────────────────────────────────────────

def get_batched_rag_contexts(all_combinations, difficulty: str, game_type: str = 'non_coding') -> dict:
    """Pre-fetch contexts for all combinations keyed by tuple of subtopic objects."""
    contexts = {}
    try:
        for combo in all_combinations:
            key = tuple(combo) if isinstance(combo, (list, tuple)) else (combo,)
            contexts[key] = (
                get_rag_context_for_subtopic(combo[0], difficulty, game_type)
                if len(combo) == 1
                else get_combined_rag_context(combo, difficulty, game_type)
            )
    except Exception as e:
        logger.error(f"Batch RAG context retrieval failed: {e}")
    return contexts


# ── Prompt formatter ───────────────────────────────────────────────────────────

def format_rag_context_for_prompt(rag_context: str, subtopic_names: list,
                                  difficulty: str, game_type: str = 'non_coding') -> str:
    """Return a fallback stub if the context has no useful content."""
    if "No semantic analysis available" in rag_context or "No relevant chunks found" in rag_context:
        return _multi_fallback(subtopic_names, game_type)
    return rag_context


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_chunk_ids(semantic, game_type: str) -> list:
    """Select ranked chunk IDs, preferring the type that matches the game, with fallback."""
    if game_type == 'coding':
        ids = semantic.get_code_chunk_ids(limit=_TOP_K, min_similarity=_MIN_SIMILARITY)
        if not ids:
            ids = semantic.get_concept_chunk_ids(limit=_TOP_K // 2, min_similarity=_MIN_SIMILARITY)
    else:
        ids = semantic.get_concept_chunk_ids(limit=_TOP_K, min_similarity=_MIN_SIMILARITY)
        if not ids:
            ids = semantic.get_code_chunk_ids(limit=_TOP_K // 2, min_similarity=_MIN_SIMILARITY)
    return ids


def _fallback_context(subtopic, game_type: str, reason: str = '') -> str:
    return (
        f"Topic: {subtopic.topic.name}\n"
        f"Subtopic: {subtopic.name}\n"
        f"Game Type: {game_type}\n\n"
        f"{reason}.\n"
        f"Please generate {game_type} questions based on the subtopic name and general Python knowledge."
    )


def _multi_fallback(names: list, game_type: str) -> str:
    lines = "\n".join(f"- {name}" for name in names)
    return (
        f"FALLBACK MODE: No semantic content chunks were found for these subtopics.\n"
        f"Please generate {game_type} questions based on general Python knowledge for:\n{lines}"
    )
