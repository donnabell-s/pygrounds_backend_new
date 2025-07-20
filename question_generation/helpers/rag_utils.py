"""
Smart RAG (Retrieval-Augmented Generation) utilities for question generation.
Intelligently retrieves chunks based on question type:
- Coding questions: Focus on "Exercise", "Example", "Code" chunks  
- Non-coding questions: Focus on "Text", "Section", "Subsection" chunks
"""

import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from django.db.models import Q
from sentence_transformers import SentenceTransformer
from content_ingestion.models import DocumentChunk, Subtopic, Topic
import logging

logger = logging.getLogger(__name__)


class SmartRAGRetriever:
    """
    Smart retrieval system that filters chunks based on question type and content needs.
    """
    
    def __init__(self, embedding_model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the smart RAG retriever.
        
        Args:
            embedding_model_name: Name of the sentence transformer model to use
        """
        self.embedding_model_name = embedding_model_name
        self.model = None
        
        # Define chunk types for different question categories
        self.coding_chunk_types = ["Exercise", "Example", "Code"]
        self.explanation_chunk_types = ["Text", "Section", "Subsection", "Header"]
        
    def _load_model(self):
        """Load the sentence transformer model if not already loaded."""
        if self.model is None:
            logger.info(f"Loading embedding model: {self.embedding_model_name}")
            self.model = SentenceTransformer(self.embedding_model_name)
    
    
    def cosine_similarity(self, vector1: List[float], vector2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vector1: First vector
            vector2: Second vector
            
        Returns:
            Cosine similarity score between 0 and 1
        """
        v1 = np.array(vector1)
        v2 = np.array(vector2)
        
        # Handle zero vectors
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return np.dot(v1, v2) / (norm1 * norm2)
    
    def retrieve_for_coding_questions(
        self,
        subtopic: Subtopic,
        top_k: int = 10,
        similarity_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve chunks specifically for coding question generation.
        Focuses on "Exercise", "Example", "Code" chunks.
        
        Args:
            subtopic: The subtopic to generate questions for
            top_k: Maximum number of chunks to retrieve
            similarity_threshold: Minimum similarity score to include chunk
            
        Returns:
            List of coding-relevant chunk data with similarity scores
        """
        logger.info(f"🔍 CODING RAG Retrieval for subtopic: {subtopic.name}")
        
        # Create query focused on coding aspects
        query_parts = [
            subtopic.name,
            "coding exercise example implementation",
            subtopic.topic.name,
            " ".join(subtopic.learning_objectives) if subtopic.learning_objectives else ""
        ]
        query_text = " ".join(part for part in query_parts if part.strip())
        
        logger.info(f"Coding query: {query_text[:100]}...")
        
        # Generate query embedding
        self._load_model()
        query_embedding = self.model.encode([query_text])[0].tolist()
        
        # Get coding-specific candidate chunks
        coding_chunks = self._get_coding_chunks(subtopic)
        
        logger.info(f"Found {len(coding_chunks)} coding chunks")
        
        # Calculate similarities and rank
        chunk_scores = []
        for chunk in coding_chunks:
            if chunk.embedding is None or len(chunk.embedding) == 0:
                continue
                
            similarity = self.cosine_similarity(query_embedding, chunk.embedding)
            
            if similarity >= similarity_threshold:
                chunk_scores.append({
                    'chunk': chunk,
                    'similarity_score': similarity,
                    'chunk_id': chunk.id,
                    'topic_title': chunk.topic_title,
                    'subtopic_title': chunk.subtopic_title,
                    'page_number': chunk.page_number,
                    'text_preview': chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text,
                    'text': chunk.text,
                    'chunk_type': chunk.chunk_type,
                    'content_category': 'coding'
                })
        
        # Sort by similarity score and take top_k
        chunk_scores.sort(key=lambda x: x['similarity_score'], reverse=True)
        top_chunks = chunk_scores[:top_k]
        
        logger.info(f"Retrieved {len(top_chunks)} coding chunks above threshold {similarity_threshold}")
        for i, chunk_data in enumerate(top_chunks[:3], 1):
            logger.info(f"  {i}. [{chunk_data['chunk_type']}] Score: {chunk_data['similarity_score']:.3f} - Page {chunk_data['page_number']}")
        
        return top_chunks
    
    def retrieve_for_explanation_questions(
        self,
        subtopic: Subtopic,
        top_k: int = 10,
        similarity_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve chunks specifically for explanation/theory question generation.
        Focuses on "Text", "Section", "Subsection" chunks.
        
        Args:
            subtopic: The subtopic to generate questions for
            top_k: Maximum number of chunks to retrieve
            similarity_threshold: Minimum similarity score to include chunk
            
        Returns:
            List of explanation-relevant chunk data with similarity scores
        """
        logger.info(f"🔍 EXPLANATION RAG Retrieval for subtopic: {subtopic.name}")
        
        # Create query focused on explanatory content
        query_parts = [
            subtopic.name,
            "explanation definition concept theory",
            subtopic.description,
            subtopic.topic.name,
            " ".join(subtopic.learning_objectives) if subtopic.learning_objectives else ""
        ]
        query_text = " ".join(part for part in query_parts if part.strip())
        
        logger.info(f"Explanation query: {query_text[:100]}...")
        
        # Generate query embedding
        self._load_model()
        query_embedding = self.model.encode([query_text])[0].tolist()
        
        # Get explanation-specific candidate chunks
        explanation_chunks = self._get_explanation_chunks(subtopic)
        
        logger.info(f"Found {len(explanation_chunks)} explanation chunks")
        
        # Calculate similarities and rank
        chunk_scores = []
        for chunk in explanation_chunks:
            if chunk.embedding is None or len(chunk.embedding) == 0:
                continue
                
            similarity = self.cosine_similarity(query_embedding, chunk.embedding)
            
            if similarity >= similarity_threshold:
                chunk_scores.append({
                    'chunk': chunk,
                    'similarity_score': similarity,
                    'chunk_id': chunk.id,
                    'topic_title': chunk.topic_title,
                    'subtopic_title': chunk.subtopic_title,
                    'page_number': chunk.page_number,
                    'text_preview': chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text,
                    'text': chunk.text,
                    'chunk_type': chunk.chunk_type,
                    'content_category': 'explanation'
                })
        
        # Sort by similarity score and take top_k
        chunk_scores.sort(key=lambda x: x['similarity_score'], reverse=True)
        top_chunks = chunk_scores[:top_k]
        
        logger.info(f"Retrieved {len(top_chunks)} explanation chunks above threshold {similarity_threshold}")
        for i, chunk_data in enumerate(top_chunks[:3], 1):
            logger.info(f"  {i}. [{chunk_data['chunk_type']}] Score: {chunk_data['similarity_score']:.3f} - Page {chunk_data['page_number']}")
        
        return top_chunks
    
    def _get_coding_chunks(self, subtopic: Subtopic) -> List[DocumentChunk]:
        """
        Get chunks suitable for coding question generation.
        
        Args:
            subtopic: Target subtopic
            
        Returns:
            List of coding-relevant chunks
        """
        # Start with chunks that have embeddings
        base_query = DocumentChunk.objects.filter(
            embedding__isnull=False
        ).exclude(
            embedding=[]
        )
        
        # Filter for coding chunk types
        coding_filter = Q(chunk_type__in=self.coding_chunk_types)
        
        # Also include chunks with coding keywords in text
        coding_keywords = ['def ', 'import ', 'print(', 'input(', '>>>', 'try:', 'if ', 'for ', 'while ']
        text_filter = Q()
        for keyword in coding_keywords:
            text_filter |= Q(text__icontains=keyword)
        
        # Combine filters
        filters = coding_filter | text_filter
        
        # Add subtopic/topic relevance - more lenient for granular chunks
        relevance_filter = Q()
        relevance_filter |= Q(subtopic_title__icontains=subtopic.name)
        relevance_filter |= Q(topic_title__icontains=subtopic.topic.name)
        
        # Get related topics in same zone
        related_topics = Topic.objects.filter(zone=subtopic.topic.zone)
        for topic in related_topics:
            relevance_filter |= Q(topic_title__icontains=topic.name)
        
        # For granular chunks that may not have topic mapping, include chunks with empty topic/subtopic titles
        relevance_filter |= Q(topic_title="") | Q(subtopic_title="")
        
        # Apply all filters
        coding_chunks = base_query.filter(filters & relevance_filter).distinct()
        
        return list(coding_chunks)
    
    def _get_explanation_chunks(self, subtopic: Subtopic) -> List[DocumentChunk]:
        """
        Get chunks suitable for explanation question generation.
        
        Args:
            subtopic: Target subtopic
            
        Returns:
            List of explanation-relevant chunks
        """
        # Start with chunks that have embeddings
        base_query = DocumentChunk.objects.filter(
            embedding__isnull=False
        ).exclude(
            embedding=[]
        )
        
        # Filter for explanation chunk types
        explanation_filter = Q(chunk_type__in=self.explanation_chunk_types)
        
        # Exclude coding-heavy chunks
        exclude_coding = Q()
        coding_keywords = ['def ', 'import ', '>>>', 'print(', 'input(']
        for keyword in coding_keywords:
            exclude_coding |= Q(text__icontains=keyword)
        
        # Add subtopic/topic relevance - more lenient for granular chunks
        relevance_filter = Q()
        relevance_filter |= Q(subtopic_title__icontains=subtopic.name)
        relevance_filter |= Q(topic_title__icontains=subtopic.topic.name)
        
        # Get related topics in same zone
        related_topics = Topic.objects.filter(zone=subtopic.topic.zone)
        for topic in related_topics:
            relevance_filter |= Q(topic_title__icontains=topic.name)
        
        # For granular chunks that may not have topic mapping, include chunks with empty topic/subtopic titles
        relevance_filter |= Q(topic_title="") | Q(subtopic_title="")
        
        # Apply filters: explanation types, not too coding-heavy, and relevant
        explanation_chunks = base_query.filter(
            explanation_filter & relevance_filter
        ).exclude(exclude_coding).distinct()
        
        return list(explanation_chunks)
    
    def create_coding_context_window(
        self,
        retrieved_chunks: List[Dict[str, Any]],
        subtopic: Subtopic,
        max_tokens: int = 3000
    ) -> str:
        """
        Create a context window optimized for coding question generation.
        
        Args:
            retrieved_chunks: List of coding chunk data from retrieval
            subtopic: Target subtopic for context
            max_tokens: Approximate maximum tokens for context window
            
        Returns:
            Formatted context string for coding question generation
        """
        context_parts = []
        
        # Add subtopic information
        context_parts.append(f"SUBTOPIC: {subtopic.name}")
        context_parts.append(f"DESCRIPTION: {subtopic.description}")
        context_parts.append(f"TOPIC: {subtopic.topic.name}")
        
        if subtopic.learning_objectives:
            context_parts.append(f"LEARNING OBJECTIVES: {', '.join(subtopic.learning_objectives)}")
        
        context_parts.append("\n" + "="*80 + "\n")
        context_parts.append("CODING EXAMPLES AND EXERCISES:")
        context_parts.append("="*80)
        
        # Add retrieved coding chunks
        current_length = len(" ".join(context_parts))
        
        for i, chunk_data in enumerate(retrieved_chunks, 1):
            chunk_text = chunk_data['text']
            chunk_header = f"\n[{chunk_data['chunk_type'].upper()} {i} - Score: {chunk_data['similarity_score']:.3f}]\n"
            chunk_section = chunk_header + chunk_text + "\n" + "-"*40
            
            # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
            estimated_tokens = (current_length + len(chunk_section)) / 4
            
            if estimated_tokens > max_tokens:
                logger.info(f"Coding context window limit reached. Including {i-1} chunks.")
                break
            
            context_parts.append(chunk_section)
            current_length += len(chunk_section)
        
        return "\n".join(context_parts)
    
    def create_explanation_context_window(
        self,
        retrieved_chunks: List[Dict[str, Any]],
        subtopic: Subtopic,
        max_tokens: int = 3000
    ) -> str:
        """
        Create a context window optimized for explanation question generation.
        
        Args:
            retrieved_chunks: List of explanation chunk data from retrieval
            subtopic: Target subtopic for context
            max_tokens: Approximate maximum tokens for context window
            
        Returns:
            Formatted context string for explanation question generation
        """
        context_parts = []
        
        # Add subtopic information
        context_parts.append(f"SUBTOPIC: {subtopic.name}")
        context_parts.append(f"DESCRIPTION: {subtopic.description}")
        context_parts.append(f"TOPIC: {subtopic.topic.name}")
        
        if subtopic.learning_objectives:
            context_parts.append(f"LEARNING OBJECTIVES: {', '.join(subtopic.learning_objectives)}")
        
        context_parts.append("\n" + "="*80 + "\n")
        context_parts.append("EXPLANATORY CONTENT:")
        context_parts.append("="*80)
        
        # Add retrieved explanation chunks
        current_length = len(" ".join(context_parts))
        
        for i, chunk_data in enumerate(retrieved_chunks, 1):
            chunk_text = chunk_data['text']
            chunk_header = f"\n[{chunk_data['chunk_type'].upper()} {i} - Score: {chunk_data['similarity_score']:.3f}]\n"
            chunk_section = chunk_header + chunk_text + "\n" + "-"*40
            
            # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
            estimated_tokens = (current_length + len(chunk_section)) / 4
            
            if estimated_tokens > max_tokens:
                logger.info(f"Explanation context window limit reached. Including {i-1} chunks.")
                break
            
            context_parts.append(chunk_section)
            current_length += len(chunk_section)
        
        return "\n".join(context_parts)


class QuestionRAG:
    """
    High-level smart RAG interface for question generation.
    """
    
    def __init__(self):
        self.retriever = SmartRAGRetriever()
    
    def prepare_coding_context(
        self,
        subtopic: Subtopic,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Prepare RAG context specifically for coding question generation.
        
        Args:
            subtopic: Target subtopic
            config: Optional configuration for retrieval parameters
            
        Returns:
            Dictionary with coding context window, retrieved chunks, and metadata
        """
        # Default config for coding questions
        default_config = {
            'top_k': 8,
            'similarity_threshold': 0.25,
            'max_tokens': 3000
        }
        
        if config:
            default_config.update(config)
        
        logger.info(f"🎯 Preparing CODING context for: {subtopic.name}")
        
        # Retrieve coding-relevant chunks
        retrieved_chunks = self.retriever.retrieve_for_coding_questions(
            subtopic=subtopic,
            top_k=default_config['top_k'],
            similarity_threshold=default_config['similarity_threshold']
        )
        
        # Create coding context window
        context_window = self.retriever.create_coding_context_window(
            retrieved_chunks=retrieved_chunks,
            subtopic=subtopic,
            max_tokens=default_config['max_tokens']
        )
        
        # Prepare metadata
        retrieval_metadata = {
            'subtopic_id': subtopic.id,
            'subtopic_name': subtopic.name,
            'topic_name': subtopic.topic.name,
            'zone_name': subtopic.topic.zone.name,
            'chunks_retrieved': len(retrieved_chunks),
            'content_category': 'coding',
            'config_used': default_config,
            'similarity_scores': [chunk['similarity_score'] for chunk in retrieved_chunks],
            'avg_similarity': sum(chunk['similarity_score'] for chunk in retrieved_chunks) / len(retrieved_chunks) if retrieved_chunks else 0,
            'context_length': len(context_window),
            'chunk_types': [chunk['chunk_type'] for chunk in retrieved_chunks],
            'embedding_model': self.retriever.embedding_model_name
        }
        
        return {
            'context_window': context_window,
            'retrieved_chunks': retrieved_chunks,
            'metadata': retrieval_metadata,
            'subtopic': subtopic,
            'question_category': 'coding'
        }
    
    def prepare_explanation_context(
        self,
        subtopic: Subtopic,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Prepare RAG context specifically for explanation question generation.
        
        Args:
            subtopic: Target subtopic
            config: Optional configuration for retrieval parameters
            
        Returns:
            Dictionary with explanation context window, retrieved chunks, and metadata
        """
        # Default config for explanation questions
        default_config = {
            'top_k': 10,
            'similarity_threshold': 0.3,
            'max_tokens': 3000
        }
        
        if config:
            default_config.update(config)
        
        logger.info(f"🎯 Preparing EXPLANATION context for: {subtopic.name}")
        
        # Retrieve explanation-relevant chunks
        retrieved_chunks = self.retriever.retrieve_for_explanation_questions(
            subtopic=subtopic,
            top_k=default_config['top_k'],
            similarity_threshold=default_config['similarity_threshold']
        )
        
        # Create explanation context window
        context_window = self.retriever.create_explanation_context_window(
            retrieved_chunks=retrieved_chunks,
            subtopic=subtopic,
            max_tokens=default_config['max_tokens']
        )
        
        # Prepare metadata
        retrieval_metadata = {
            'subtopic_id': subtopic.id,
            'subtopic_name': subtopic.name,
            'topic_name': subtopic.topic.name,
            'zone_name': subtopic.topic.zone.name,
            'chunks_retrieved': len(retrieved_chunks),
            'content_category': 'explanation',
            'config_used': default_config,
            'similarity_scores': [chunk['similarity_score'] for chunk in retrieved_chunks],
            'avg_similarity': sum(chunk['similarity_score'] for chunk in retrieved_chunks) / len(retrieved_chunks) if retrieved_chunks else 0,
            'context_length': len(context_window),
            'chunk_types': [chunk['chunk_type'] for chunk in retrieved_chunks],
            'embedding_model': self.retriever.embedding_model_name
        }
        
        return {
            'context_window': context_window,
            'retrieved_chunks': retrieved_chunks,
            'metadata': retrieval_metadata,
            'subtopic': subtopic,
            'question_category': 'explanation'
        }
