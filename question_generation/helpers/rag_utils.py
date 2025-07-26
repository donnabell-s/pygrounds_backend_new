"""
Smart RAG (Retrieval-Augmented Generation) utilities for question generation.
Intelligently retrieves document chunks based on question type:
- Coding: Focus on "Exercise", "Example", "Code"
- Non-coding: Focus on "Text", "Section", "Subsection"
"""

import numpy as np
from typing import List, Dict, Any, Optional
from django.db.models import Q
from sentence_transformers import SentenceTransformer
from content_ingestion.models import DocumentChunk, Subtopic, Topic
import logging

logger = logging.getLogger(__name__)


class SmartRAGRetriever:
    """Smart retrieval/filtering for document chunks based on question type."""
    
    CODING_CHUNK_TYPES = ["Exercise", "Example", "Code"]
    EXPLANATION_CHUNK_TYPES = ["Text", "Section", "Subsection", "Header"]
    CODING_KEYWORDS = ['def ', 'import ', 'print(', 'input(', '>>>', 'try:', 'if ', 'for ', 'while ']

    def __init__(self, embedding_model_name: str = "all-MiniLM-L6-v2"):
        self.embedding_model_name = embedding_model_name
        self.model = None

    def _load_model(self):
        if self.model is None:
            logger.info(f"Loading embedding model: {self.embedding_model_name}")
            self.model = SentenceTransformer(self.embedding_model_name)

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        v1, v2 = np.array(v1), np.array(v2)
        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        return float(np.dot(v1, v2) / (n1 * n2)) if n1 and n2 else 0.0

    def _build_query(self, subtopic: Subtopic, extra_terms: str = "") -> str:
        terms = [
            subtopic.name,
            subtopic.topic.name,
            extra_terms,
            " ".join(subtopic.learning_objectives) if getattr(subtopic, "learning_objectives", None) else ""
        ]
        return " ".join([t for t in terms if t.strip()])

    def _filter_chunks(
        self, subtopic: Subtopic, chunk_types: List[str], include_keywords: bool = False
    ) -> List[DocumentChunk]:
        """Query chunks by types, optionally including text keyword matching."""
        query = DocumentChunk.objects.filter(embedding__isnull=False).exclude(embedding=[])
        chunk_type_q = Q(chunk_type__in=chunk_types)

        text_q = Q()
        if include_keywords:
            for k in self.CODING_KEYWORDS:
                text_q |= Q(text__icontains=k)

        relevance_q = Q(subtopic_title__icontains=subtopic.name) | Q(topic_title__icontains=subtopic.topic.name)
        for topic in Topic.objects.filter(zone=subtopic.topic.zone):
            relevance_q |= Q(topic_title__icontains=topic.name)
        relevance_q |= Q(topic_title="") | Q(subtopic_title="")

        # Coding: types OR keywords, Explanation: only types
        final_filter = (chunk_type_q | text_q) if include_keywords else chunk_type_q
        return list(query.filter(final_filter & relevance_q).distinct())

    def retrieve_chunks(
        self, subtopic: Subtopic, top_k: int, similarity_threshold: float, chunk_types: List[str], extra_terms: str = "", include_keywords=False
    ) -> List[Dict[str, Any]]:
        self._load_model()
        query_text = self._build_query(subtopic, extra_terms)
        query_embedding = self.model.encode([query_text])[0].tolist()
        candidates = self._filter_chunks(subtopic, chunk_types, include_keywords=include_keywords)

        scored = []
        for chunk in candidates:
            if not chunk.embedding: continue
            sim = self.cosine_similarity(query_embedding, chunk.embedding)
            if sim >= similarity_threshold:
                scored.append({
                    'chunk': chunk,
                    'similarity_score': sim,
                    'chunk_id': chunk.id,
                    'topic_title': chunk.topic_title,
                    'subtopic_title': chunk.subtopic_title,
                    'page_number': chunk.page_number,
                    'text_preview': chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text,
                    'text': chunk.text,
                    'chunk_type': chunk.chunk_type,
                })
        scored.sort(key=lambda x: x['similarity_score'], reverse=True)
        return scored[:top_k]

    def retrieve_for_coding_questions(self, subtopic, top_k=10, similarity_threshold=0.3):
        logger.info(f"🔍 Coding RAG for: {subtopic.name}")
        return self.retrieve_chunks(
            subtopic=subtopic,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            chunk_types=self.CODING_CHUNK_TYPES,
            extra_terms="coding exercise example implementation",
            include_keywords=True,
        )

    def retrieve_for_explanation_questions(self, subtopic, top_k=10, similarity_threshold=0.3):
        logger.info(f"🔍 Explanation RAG for: {subtopic.name}")
        return self.retrieve_chunks(
            subtopic=subtopic,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            chunk_types=self.EXPLANATION_CHUNK_TYPES,
            extra_terms="explanation definition concept theory",
            include_keywords=False,
        )

    def create_context_window(self, retrieved_chunks, subtopic, header, max_tokens=3000):
        """
        Create a formatted context window from retrieved chunks.
        """
        context = [
            f"SUBTOPIC: {subtopic.name}",
            f"DESCRIPTION: {subtopic.description}",
            f"TOPIC: {subtopic.topic.name}",
        ]
        if getattr(subtopic, "learning_objectives", None):
            context.append(f"LEARNING OBJECTIVES: {', '.join(subtopic.learning_objectives)}")
        context += ["\n" + "="*80, header, "="*80]
        current_length = len(" ".join(context))
        for i, chunk in enumerate(retrieved_chunks, 1):
            text = chunk['text']
            chunk_header = f"\n[{chunk['chunk_type'].upper()} {i} - Score: {chunk['similarity_score']:.3f}]\n"
            chunk_section = chunk_header + text + "\n" + "-"*40
            estimated_tokens = (current_length + len(chunk_section)) / 4
            if estimated_tokens > max_tokens:
                logger.info(f"Context window token limit reached at {i-1} chunks.")
                break
            context.append(chunk_section)
            current_length += len(chunk_section)
        return "\n".join(context)

    def create_coding_context_window(self, retrieved_chunks, subtopic, max_tokens=3000):
        return self.create_context_window(retrieved_chunks, subtopic, "CODING EXAMPLES AND EXERCISES:", max_tokens)

    def create_explanation_context_window(self, retrieved_chunks, subtopic, max_tokens=3000):
        return self.create_context_window(retrieved_chunks, subtopic, "EXPLANATORY CONTENT:", max_tokens)


class QuestionRAG:
    """
    High-level RAG interface for question generation.
    """

    def __init__(self):
        self.retriever = SmartRAGRetriever()

    def prepare_context(
        self,
        subtopic: Subtopic,
        category: str = "coding",
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Prepare RAG context for a given subtopic/category ('coding' or 'explanation').
        """
        configs = {
            "coding": {"top_k": 8, "similarity_threshold": 0.25, "max_tokens": 3000},
            "explanation": {"top_k": 10, "similarity_threshold": 0.3, "max_tokens": 3000}
        }
        if config:
            configs[category].update(config)
        params = configs[category]

        if category == "coding":
            chunks = self.retriever.retrieve_for_coding_questions(
                subtopic=subtopic,
                top_k=params['top_k'],
                similarity_threshold=params['similarity_threshold']
            )
            context_window = self.retriever.create_coding_context_window(chunks, subtopic, params['max_tokens'])
        else:
            chunks = self.retriever.retrieve_for_explanation_questions(
                subtopic=subtopic,
                top_k=params['top_k'],
                similarity_threshold=params['similarity_threshold']
            )
            context_window = self.retriever.create_explanation_context_window(chunks, subtopic, params['max_tokens'])

        meta = {
            'subtopic_id': subtopic.id,
            'subtopic_name': subtopic.name,
            'topic_name': subtopic.topic.name,
            'zone_name': subtopic.topic.zone.name,
            'chunks_retrieved': len(chunks),
            'content_category': category,
            'config_used': params,
            'similarity_scores': [c['similarity_score'] for c in chunks],
            'avg_similarity': np.mean([c['similarity_score'] for c in chunks]) if chunks else 0,
            'context_length': len(context_window),
            'chunk_types': [c['chunk_type'] for c in chunks],
            'embedding_model': self.retriever.embedding_model_name
        }
        return {
            'context_window': context_window,
            'retrieved_chunks': chunks,
            'metadata': meta,
            'subtopic': subtopic,
            'question_category': category
        }

    def prepare_coding_context(self, subtopic, config=None):
        return self.prepare_context(subtopic, category="coding", config=config)

    def prepare_explanation_context(self, subtopic, config=None):
        return self.prepare_context(subtopic, category="explanation", config=config)
