import logging
from django.db import models

logger = logging.getLogger(__name__)

_TOP_K        = 15
_MIN_SIMILARITY = 0.5
_MIN_CHUNK_LENGTH = 200

# Substrings that signal a chunk is front-matter / boilerplate, not real content.
# Matched case-insensitively.
_JUNK_MARKERS = (
    'all rights reserved',
    'isbn',
    'copyright ©',
    'first published',
    'library of congress',
    'printed in',
    'packt publishing',
    "o'reilly media",
    'birmingham - mumbai',
    'cover designed',
    'acquisition editor',
    'commissioning editor',
    'content development editor',
    'technical editor',
)

# Which book difficulty levels are appropriate for each generation difficulty.
# `primary` chunks are at-or-below the target level and used as-is.
# `supplementary` chunks are above the target level — kept for relevance, but
# the LLM is instructed to simplify them down to the target level.
_DIFFICULTY_POOLS = {
    'beginner':     {'primary': ['beginner'],                 'supplementary': ['intermediate', 'advanced', 'master']},
    'intermediate': {'primary': ['beginner', 'intermediate'], 'supplementary': ['advanced', 'master']},
    'advanced':     {'primary': ['intermediate', 'advanced'], 'supplementary': ['master']},
    'master':       {'primary': ['advanced', 'master'],       'supplementary': []},
}

_HIGHER_LEVEL_LABELS = {
    'beginner':     ['Intermediate', 'Advanced', 'Master'],
    'intermediate': ['Advanced', 'Master'],
    'advanced':     ['Master'],
    'master':       [],
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

        chunk_entries = _get_chunk_entries(semantic, game_type)
        if not chunk_entries:
            return _fallback_context(subtopic, game_type, reason=f"No relevant {game_type} chunks found above similarity threshold")

        chunk_ids = [cid for cid, _ in chunk_entries]
        similarity_by_id = {cid: sim for cid, sim in chunk_entries}

        pools = _DIFFICULTY_POOLS.get(
            difficulty,
            {'primary': list(_DIFFICULTY_POOLS.keys()), 'supplementary': []},
        )
        primary_difficulties = pools['primary']
        supplementary_difficulties = pools['supplementary']
        allowed_difficulties = primary_difficulties + supplementary_difficulties

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
        primary_parts = []
        supplementary_parts = []
        rejections = []  # [(chunk_id, reason), ...]
        for chunk in chunks:
            sim = similarity_by_id.get(chunk.id, 0.0)
            is_junk, reason = _is_junk_chunk(chunk.text, chunk.document.title)
            if is_junk:
                rejections.append((chunk.id, reason))
                logger.info(
                    f"RAG for '{subtopic.name}': rejected chunk id={chunk.id} "
                    f"doc='{chunk.document.title}' similarity={sim:.3f} reason={reason}"
                )
                continue
            chunk_types.add(chunk.chunk_type or 'Unknown')
            doc_difficulty = (chunk.document.difficulty or '').lower()
            entry = (
                f"--- {chunk.chunk_type or 'Content'} "
                f"[difficulty: {doc_difficulty or 'unknown'}] ---\n"
                f"{chunk.text.strip()}\n"
                f"Document: {chunk.document.title}"
            )
            if doc_difficulty in supplementary_difficulties:
                supplementary_parts.append(entry)
            else:
                primary_parts.append(entry)

        total_kept = len(primary_parts) + len(supplementary_parts)
        if total_kept == 0:
            details = '; '.join(f"id={cid}: {why}" for cid, why in rejections[:5])
            return _fallback_context(
                subtopic, game_type,
                reason=f"All {len(rejections)} retrieved chunks rejected as junk ({details})",
            )

        if rejections:
            logger.info(f"RAG for {subtopic.name}: rejected {len(rejections)} junk chunks, kept {total_kept}")

        sections = []
        if primary_parts:
            sections.append(
                f"PRIMARY REFERENCES (target difficulty — use as-is):\n"
                + "\n\n".join(primary_parts)
            )
        if supplementary_parts:
            sections.append(
                f"SUPPLEMENTARY REFERENCES (above target — SIMPLIFY before using):\n"
                + "\n\n".join(supplementary_parts)
            )

        guidance = _build_difficulty_guidance(difficulty, bool(supplementary_parts))

        return (
            f"Topic: {subtopic.topic.name}\n"
            f"Subtopic: {subtopic.name}\n"
            f"Game Type: {game_type}\n"
            f"Target Difficulty: {difficulty}\n"
            f"Content Types Found: {', '.join(sorted(chunk_types))}\n"
            f"Retrieved Chunks: {total_kept} "
            f"(primary={len(primary_parts)}, supplementary={len(supplementary_parts)})\n\n"
            f"{guidance}\n\n"
            f"LEARNING CONTENT:\n" + "\n\n".join(sections)
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
        any_supplementary = False
        for subtopic in subtopic_combination:
            names.append(subtopic.name)
            ctx = get_rag_context_for_subtopic(subtopic, difficulty, game_type)
            if "SUPPLEMENTARY REFERENCES" in ctx:
                any_supplementary = True
            content = ctx.split("LEARNING CONTENT:")[1].strip() if "LEARNING CONTENT:" in ctx else ctx
            parts.append(f"=== {subtopic.name} ===\n{content}")

        if not parts:
            return _multi_fallback(names, game_type)

        guidance = _build_difficulty_guidance(difficulty, any_supplementary)

        return (
            f"GAME TYPE: {game_type.upper()}\n"
            f"DIFFICULTY LEVEL: {difficulty.upper()}\n"
            f"SUBTOPIC COMBINATION: {' + '.join(names)}\n\n"
            f"{guidance}\n\n"
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

def _build_difficulty_guidance(difficulty: str, has_supplementary: bool) -> str:
    """Instructions to the LLM on how to use chunks of varying difficulty levels."""
    target_lower = (difficulty or '').lower()
    target_label = target_lower.capitalize() or 'Target'
    higher_levels = _HIGHER_LEVEL_LABELS.get(target_lower, [])

    if not has_supplementary or not higher_levels:
        return (
            f"TARGET DIFFICULTY: {target_label}\n\n"
            f"GUIDANCE:\n"
            f"- All references match the target difficulty — use them directly\n"
            f"- Keep questions consistent with the {target_lower} level"
        )

    quoted_higher = ', '.join(f'"{lvl}"' for lvl in higher_levels)
    return (
        f"TARGET DIFFICULTY: {target_label}\n\n"
        f"GUIDANCE:\n"
        f"- Primary references are chunks tagged \"{target_label}\"\n"
        f"- Chunks from {quoted_higher} are supplementary and should be SIMPLIFIED in your output\n"
        f"- Do NOT introduce concepts beyond {target_lower} level\n"
        f"- If a chunk uses advanced terminology, translate it to {target_lower}-friendly language"
    )


def _is_junk_chunk(text: str, document_title: str) -> tuple[bool, str]:
    """Return (is_junk, reason). Reason is empty string when not junk."""
    if not text:
        return True, 'empty text'

    stripped = text.strip()
    if len(stripped) < _MIN_CHUNK_LENGTH:
        return True, f'too short ({len(stripped)} < {_MIN_CHUNK_LENGTH})'

    lowered = stripped.lower()
    for marker in _JUNK_MARKERS:
        if marker in lowered:
            return True, f"matched junk marker: '{marker}'"

    # Cover/title pages repeat the book title many times. Require 3+ occurrences
    # AND a high density (title accounts for >5% of text length) so legitimate
    # chunks that mention the book title once or twice in citations survive.
    title = (document_title or '').strip().lower()
    if len(title) >= 8:
        title_hits = lowered.count(title)
        if title_hits >= 3 and (title_hits * len(title)) / max(len(lowered), 1) > 0.05:
            return True, f"title '{title}' repeated {title_hits}x at high density"

    return False, ''


def _get_chunk_entries(semantic, game_type: str) -> list:
  
    primary_attr = 'ranked_code_chunks' if game_type == 'coding' else 'ranked_concept_chunks'
    fallback_attr = 'ranked_concept_chunks' if game_type == 'coding' else 'ranked_code_chunks'
    primary_limit = _TOP_K
    fallback_limit = _TOP_K // 2

    def _entries_from(attr: str, limit: int) -> list:
        ranked = getattr(semantic, attr, None) or []
        out = []
        for item in ranked:
            sim = item.get('similarity', 0)
            if sim < _MIN_SIMILARITY:
                continue
            out.append((item['chunk_id'], sim))
            if len(out) >= limit:
                break
        return out

    entries = _entries_from(primary_attr, primary_limit)
    if not entries:
        entries = _entries_from(fallback_attr, fallback_limit)
    return entries


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
