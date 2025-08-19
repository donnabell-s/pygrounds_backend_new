import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from sklearn.metrics.pairwise import cosine_similarity
from django.db import transaction
import logging

from content_ingestion.models import Subtopic, DocumentChunk, Embedding

logger = logging.getLogger(__name__)


# === MAIN PROCESSING FUNCTIONS ===

def process_all_subtopics(document_id: Optional[int] = None, 
                         similarity_threshold: float = 0.1,
                         top_k_results: int = 10,
                         use_intents: bool = True) -> Dict[str, Any]:
    # Process semantic similarity for all subtopics using dual embeddings
    # document_id: optional - limit to specific document
    # similarity_threshold: min score to store (default: 0.1)
    # top_k_results: max chunks per subtopic (default: 10)
    # use_intents: use intent-based embeddings if available
    print(f"🔍 Starting dual-embedding semantic similarity processing...")
    if use_intents:
        print(f"   Using intent-based embeddings when available")
    print(f"   Threshold: {similarity_threshold}")
    print(f"   Top-K results: {top_k_results}")
    
    # Get all subtopics
    subtopics = list(Subtopic.objects.all())
    print(f"   Found {len(subtopics)} total subtopics")
    
    # Get chunks with embeddings for both model types
    minilm_chunks = get_chunks_with_embeddings(document_id, model_type='sentence')
    codebert_chunks = get_chunks_with_embeddings(document_id, model_type='code_bert')
    print(f"   Found {len(minilm_chunks)} chunks with MiniLM embeddings")
    print(f"   Found {len(codebert_chunks)} chunks with CodeBERT embeddings")
    
    if not minilm_chunks and not codebert_chunks:
        return {
            'status': 'warning',
            'message': 'No chunks with embeddings found',
            'processed_subtopics': 0
        }
    
    # Process each subtopic with dual embeddings
    processed_count = 0
    total_similarities_computed = 0
    intent_based_count = 0
    
    for subtopic in subtopics:
        try:
            minilm_subtopic_data = None
            codebert_subtopic_data = None
            
            concept_similarities = []
            code_similarities = []
            
            # Process concept chunks separately with MiniLM embedding
            if minilm_chunks:
                minilm_subtopic_data = get_subtopic_embedding(subtopic, model_type='sentence', use_intents=use_intents)
                if minilm_subtopic_data:
                    if minilm_subtopic_data.get('generated_from_intent'):
                        intent_based_count += 1
                    concept_similarities = compute_subtopic_similarities(
                        minilm_subtopic_data, minilm_chunks, similarity_threshold
                    )
                    concept_similarities.sort(key=lambda x: x['similarity'], reverse=True)
                    concept_similarities = concept_similarities[:top_k_results]  # Top K concept chunks
            
            # Process code chunks separately with CodeBERT embedding  
            if codebert_chunks:
                codebert_subtopic_data = get_subtopic_embedding(subtopic, model_type='code_bert', use_intents=use_intents)
                if codebert_subtopic_data:
                    if codebert_subtopic_data.get('generated_from_intent'):
                        intent_based_count += 1
                    code_similarities = compute_subtopic_similarities(
                        codebert_subtopic_data, codebert_chunks, similarity_threshold
                    )
                    code_similarities.sort(key=lambda x: x['similarity'], reverse=True)
                    code_similarities = code_similarities[:top_k_results]  # Top K code chunks
            
            # Store results separately in their respective fields
            if concept_similarities or code_similarities:
                store_semantic_results_separate(subtopic, concept_similarities, code_similarities)
                processed_count += 1
                total_similarities_computed += len(concept_similarities) + len(code_similarities)
                
                # Count by chunk type for reporting
                concept_count = len(concept_similarities)
                code_count = len(code_similarities)
                
                intent_flag = " 🎯" if (minilm_subtopic_data and minilm_subtopic_data.get('generated_from_intent')) or (codebert_subtopic_data and codebert_subtopic_data.get('generated_from_intent')) else ""
                print(f"   ✅ {subtopic.name}: {concept_count + code_count} chunks (Concept: {concept_count}, Code: {code_count}){intent_flag}")
            else:
                print(f"   ⚠️  {subtopic.name}: No chunks above threshold or no embeddings")
                
        except Exception as e:
            logger.error(f"Error processing subtopic {subtopic.id}: {str(e)}")
            print(f"   ❌ {subtopic.name}: Error - {str(e)}")
    
    print(f"🎯 Semantic similarity processing complete!")
    print(f"   Processed subtopics: {processed_count}")
    print(f"   Total similarities stored: {total_similarities_computed}")
    if use_intents and intent_based_count > 0:
        print(f"   Intent-based embeddings used: {intent_based_count}")
    
    return {
        'status': 'success',
        'processed_subtopics': processed_count,
        'total_similarities': total_similarities_computed,
        'intent_based_embeddings_used': intent_based_count,
        'message': f'Successfully processed {processed_count} subtopics with {"intent-based " if use_intents else ""}dual embeddings'
    }


def process_single_subtopic(subtopic_id: int, 
                           document_id: Optional[int] = None,
                           similarity_threshold: float = 0.1,
                           top_k_results: int = 10) -> Dict[str, Any]:
    # Process semantic similarity for a single subtopic
    try:
        subtopic = Subtopic.objects.get(id=subtopic_id)
    except Subtopic.DoesNotExist:
        return {'status': 'error', 'message': f'Subtopic {subtopic_id} not found'}
    
    # Get subtopic embedding
    subtopic_data = get_subtopic_embedding(subtopic)
    if not subtopic_data:
        return {'status': 'error', 'message': f'No embedding found for subtopic {subtopic.name}'}
    
    # Get chunks with embeddings
    chunks_with_embeddings = get_chunks_with_embeddings(document_id)
    if not chunks_with_embeddings:
        return {'status': 'error', 'message': 'No chunks with embeddings found'}
    
    # Compute similarities
    similarity_results = compute_subtopic_similarities(subtopic_data, chunks_with_embeddings, similarity_threshold)
    
    if similarity_results:
        # Take top results
        similarity_results.sort(key=lambda x: x['similarity'], reverse=True)
        top_similarities = similarity_results[:top_k_results]
        store_semantic_results(subtopic, top_similarities)
        return {
            'status': 'success',
            'subtopic_name': subtopic.name,
            'similar_chunks': len(top_similarities)
        }
    else:
        return {
            'status': 'warning',
            'message': f'No chunks above similarity threshold for {subtopic.name}'
        }


# === EMBEDDING FUNCTIONS ===

def get_subtopic_embedding(subtopic: Subtopic, model_type: str = None, use_intents: bool = True) -> Optional[Dict[str, Any]]:
    # Get embedding data for a subtopic with specific model type
    try:
        # For subtopics, we now have dual embeddings, so don't filter by model_type
        # Just get the subtopic's embedding record (should be dual type with both vectors)
        subtopic_embedding = Embedding.objects.filter(subtopic=subtopic).first()
                
        if subtopic_embedding:
            # Get appropriate vector based on requested model type
            vector = None
            actual_model_type = None
            
            if model_type == 'sentence':
                vector = subtopic_embedding.minilm_vector
                actual_model_type = 'sentence'
            elif model_type == 'code_bert':
                vector = subtopic_embedding.codebert_vector
                actual_model_type = 'code_bert'
            else:
                # Try to get any available vector
                if subtopic_embedding.minilm_vector:
                    vector = subtopic_embedding.minilm_vector
                    actual_model_type = 'sentence'
                elif subtopic_embedding.codebert_vector:
                    vector = subtopic_embedding.codebert_vector
                    actual_model_type = 'code_bert'
                
            if vector:
                return {
                    'subtopic': subtopic,
                    'embedding': np.array(vector),
                    'embedding_id': subtopic_embedding.id,
                    'dimension': len(vector),
                    'model_type': actual_model_type,  # Return the actual model type used
                    'model_name': subtopic_embedding.model_name
                }
        
        # If no embedding found and use_intents is True, generate on-the-fly using intents
        if use_intents and (subtopic.concept_intent or subtopic.code_intent):
            return generate_intent_based_embedding(subtopic, model_type)
            
    except Exception as e:
        logger.error(f"Error getting subtopic embedding: {str(e)}")
        # If no embedding found and use_intents is True, generate on-the-fly using intents
        if use_intents and (subtopic.concept_intent or subtopic.code_intent):
            return generate_intent_based_embedding(subtopic, model_type)
    
    return None


def generate_intent_based_embedding(subtopic: Subtopic, model_type: str = None) -> Optional[Dict[str, Any]]:
    # Generate embedding on-the-fly using subtopic's intent fields
    from content_ingestion.helpers.embedding.generator import get_embedding_generator
    
    try:
        generator = get_embedding_generator()
        
        # Choose intent text based on model type
        intent_text = None
        if model_type == 'sentence' and subtopic.concept_intent:
            intent_text = subtopic.concept_intent
            chunk_type = 'Concept'  # Use concept model (MiniLM)
        elif model_type == 'code_bert' and subtopic.code_intent:
            intent_text = subtopic.code_intent  
            chunk_type = 'Code'  # Use code model (CodeBERT)
        elif subtopic.concept_intent:
            intent_text = subtopic.concept_intent
            chunk_type = 'Concept'
        elif subtopic.code_intent:
            intent_text = subtopic.code_intent
            chunk_type = 'Code'
            
        if not intent_text:
            return None
            
        # Generate embedding using intent text
        result = generator.generate_embedding(intent_text, chunk_type)
        
        if result.get('status') == 'success':
            embedding_data = result['embedding_data']
            return {
                'subtopic': subtopic,
                'embedding': np.array(embedding_data['vector']),
                'embedding_id': None,  # Not saved to DB yet
                'dimension': embedding_data['dimension'],
                'model_type': embedding_data.get('model_type', model_type),
                'model_name': embedding_data.get('model_name', ''),
                'generated_from_intent': True,
                'intent_text': intent_text
            }
            
    except Exception as e:
        logger.error(f"Error generating intent-based embedding for subtopic {subtopic.id}: {str(e)}")
    
    return None


def get_chunks_with_embeddings(document_id: Optional[int] = None, model_type: str = None) -> List[Dict[str, Any]]:
    # Get chunks that have embeddings for the specified model type
    try:
        # Build query to get chunks with embeddings
        embeddings_query = Embedding.objects.filter(document_chunk__isnull=False)
        
        if document_id:
            embeddings_query = embeddings_query.filter(document_chunk__document_id=document_id)
        
        if model_type:
            embeddings_query = embeddings_query.filter(model_type=model_type)
            
        # Get embeddings with non-null vectors based on model type
        if model_type == 'sentence':
            embeddings_query = embeddings_query.exclude(minilm_vector__isnull=True)
        elif model_type == 'code_bert':
            embeddings_query = embeddings_query.exclude(codebert_vector__isnull=True)
        else:
            # Get chunks with any vector
            from django.db.models import Q
            embeddings_query = embeddings_query.filter(
                Q(minilm_vector__isnull=False) | Q(codebert_vector__isnull=False)
            )
        
        chunks_data = []
        for embedding in embeddings_query.select_related('document_chunk'):
            chunk = embedding.document_chunk
            
            # Get appropriate vector
            vector = None
            if model_type == 'sentence' or 'minilm' in (embedding.model_name or '').lower():
                vector = embedding.minilm_vector
            elif model_type == 'code_bert' or 'codebert' in (embedding.model_name or '').lower():
                vector = embedding.codebert_vector
            else:
                vector = embedding.minilm_vector or embedding.codebert_vector
            
            if vector:
                chunks_data.append({
                    'chunk': chunk,
                    'chunk_id': chunk.id,
                    'chunk_type': chunk.chunk_type,
                    'embedding': np.array(vector),
                    'embedding_id': embedding.id,
                    'dimension': len(vector),
                    'model_type': embedding.model_type,
                    'model_name': embedding.model_name
                })
        
        return chunks_data
        
    except Exception as e:
        logger.error(f"Error getting chunks with embeddings: {str(e)}")
        return []


# === SIMILARITY COMPUTATION ===

def compute_subtopic_similarities(subtopic_data: Dict[str, Any], 
                                chunks_data: List[Dict[str, Any]], 
                                similarity_threshold: float) -> List[Dict[str, Any]]:
    # Compute cosine similarities between subtopic and chunks
    if not subtopic_data or not chunks_data:
        return []
    
    subtopic_embedding = subtopic_data['embedding'].reshape(1, -1)
    subtopic = subtopic_data['subtopic']
    
    similarities = []
    
    for chunk_data in chunks_data:
        try:
            chunk_embedding = chunk_data['embedding'].reshape(1, -1)
            
            # Check dimension compatibility
            if subtopic_embedding.shape[1] != chunk_embedding.shape[1]:
                logger.warning(f"Dimension mismatch: subtopic {subtopic_embedding.shape[1]} vs chunk {chunk_embedding.shape[1]}")
                continue
            
            # Compute cosine similarity
            similarity_score = float(cosine_similarity(subtopic_embedding, chunk_embedding)[0][0])
            
            if similarity_score >= similarity_threshold:
                similarities.append({
                    'chunk_id': chunk_data['chunk_id'],
                    'chunk_type': chunk_data['chunk_type'],
                    'similarity': similarity_score,
                    'embedding_id': chunk_data['embedding_id'],
                    'model_type': chunk_data['model_type']
                })
                
        except Exception as e:
            logger.error(f"Error computing similarity for chunk {chunk_data['chunk_id']}: {str(e)}")
    
    return similarities


# === STORAGE FUNCTIONS ===

def store_semantic_results(subtopic: Subtopic, similarity_results: List[Dict[str, Any]]):
    # Store semantic similarity results in the database
    from content_ingestion.models import SemanticSubtopic
    
    try:
        with transaction.atomic():
            # Get or create semantic subtopic record
            semantic_subtopic, created = SemanticSubtopic.objects.get_or_create(
                subtopic=subtopic,
                defaults={
                    'ranked_concept_chunks': [],
                    'ranked_code_chunks': []
                }
            )
            
            # Separate concept and code chunks
            concept_chunks = []
            code_chunks = []
            
            for result in similarity_results:
                chunk_info = {
                    'chunk_id': result['chunk_id'],
                    'similarity': result['similarity'],
                    'model_type': result.get('model_type', 'unknown')
                }
                
                if result['chunk_type'] == 'Concept':
                    concept_chunks.append(chunk_info)
                elif result['chunk_type'] in ['Code', 'Example', 'Exercise', 'Try_It']:
                    code_chunks.append(chunk_info)
            
            # Update the fields
            semantic_subtopic.ranked_concept_chunks = concept_chunks
            semantic_subtopic.ranked_code_chunks = code_chunks
            semantic_subtopic.save()
            
            logger.info(f"Stored {len(concept_chunks)} concept and {len(code_chunks)} code chunks for subtopic '{subtopic.name}'")
            
    except Exception as e:
        logger.error(f"Error storing semantic results for subtopic {subtopic.id}: {str(e)}")


def store_semantic_results_separate(subtopic: Subtopic, concept_similarities: List[Dict[str, Any]], code_similarities: List[Dict[str, Any]]):
    # Store concept and code similarity results separately
    from content_ingestion.models import SemanticSubtopic
    
    try:
        with transaction.atomic():
            # Get or create semantic subtopic record
            semantic_subtopic, created = SemanticSubtopic.objects.get_or_create(
                subtopic=subtopic,
                defaults={
                    'ranked_concept_chunks': [],
                    'ranked_code_chunks': []
                }
            )
            
            # Process concept chunks
            concept_chunks = []
            for result in concept_similarities:
                chunk_info = {
                    'chunk_id': result['chunk_id'],
                    'similarity': result['similarity'],
                    'model_type': result.get('model_type', 'sentence')
                }
                concept_chunks.append(chunk_info)
            
            # Process code chunks
            code_chunks = []
            for result in code_similarities:
                chunk_info = {
                    'chunk_id': result['chunk_id'],
                    'similarity': result['similarity'],
                    'model_type': result.get('model_type', 'code_bert')
                }
                code_chunks.append(chunk_info)
            
            # Update the fields separately
            semantic_subtopic.ranked_concept_chunks = concept_chunks
            semantic_subtopic.ranked_code_chunks = code_chunks
            semantic_subtopic.save()
            
            logger.info(f"Stored {len(concept_chunks)} concept and {len(code_chunks)} code chunks separately for subtopic '{subtopic.name}'")
            
    except Exception as e:
        logger.error(f"Error storing separate semantic results for subtopic {subtopic.id}: {str(e)}")


# === CONVENIENCE FUNCTIONS ===

def compute_semantic_similarities_for_document(document_id: int, 
                                             similarity_threshold: float = 0.1,
                                             top_k_results: int = 10) -> Dict[str, Any]:
    # Compute semantic similarities for a specific document
    return process_all_subtopics(
        document_id=document_id,
        similarity_threshold=similarity_threshold,
        top_k_results=top_k_results
    )


def compute_semantic_similarities_all(similarity_threshold: float = 0.1,
                                    top_k_results: int = 10) -> Dict[str, Any]:
    # Compute semantic similarities for all available content
    return process_all_subtopics(
        similarity_threshold=similarity_threshold,
        top_k_results=top_k_results
    )


def get_similar_chunks_for_subtopic(subtopic_id: int, 
                                  chunk_type: Optional[str] = None,
                                  limit: int = 5,
                                  min_similarity: float = 0.5) -> List[int]:
    # Get ranked chunk IDs for a subtopic based on semantic similarity
    from content_ingestion.models import SemanticSubtopic
    
    try:
        semantic_data = SemanticSubtopic.objects.get(subtopic_id=subtopic_id)
        return semantic_data.get_top_chunk_ids(
            limit=limit, 
            chunk_type=chunk_type, 
            min_similarity=min_similarity
        )
    except SemanticSubtopic.DoesNotExist:
        return []
