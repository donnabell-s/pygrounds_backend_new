"""
Embedding generator with multi-model support and parallel processing.
"""

import os
import threading
import time
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from django.utils import timezone

from .models import (
    EmbeddingModelType, EmbeddingConfig, MODEL_CONFIGS, CHUNK_TYPE_TO_MODEL
)

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Creates embeddings for different kinds of text (code vs. concepts).
    - Picks a model per chunk type.
    - Loads models on demand and caches them.
    - Can run work in parallel for batches.
    """

    def __init__(self, max_workers: int = 4, use_gpu: bool = False):
        # Initialize generator with worker count and GPU settings
        self.max_workers = max_workers
        self.use_gpu = use_gpu
        self.models: Dict[EmbeddingModelType, dict] = {}  # Cache loaded models
        self._model_lock = threading.Lock()

        logger.info(f"Initialized EmbeddingGenerator with {max_workers} workers, GPU: {use_gpu}")

    # ==================== MAIN ENTRY POINTS ====================

    def embed_and_save_batch(self, chunks: List[Any]) -> Dict[str, Any]:
        # Run batch embedding and write results to the database
        embedding_results = self.generate_batch_embeddings(chunks)

        if embedding_results['embeddings']:
            save_results = self.save_embeddings_to_db(embedding_results['embeddings'])

            return {
                'total_chunks': embedding_results['total'],
                'embeddings_generated': embedding_results['success'],
                'embeddings_failed': embedding_results['failed'],
                'database_saves': save_results.get('success', 0),
                'database_errors': save_results.get('failed', 0),
                'models_used': embedding_results['models_used'],
                'processing_time': embedding_results['processing_time']
            }

        return {
            'total_chunks': embedding_results['total'],
            'embeddings_generated': 0,
            'embeddings_failed': embedding_results['failed'],
            'database_saves': 0,
            'database_errors': 0,
            'models_used': embedding_results['models_used'],
            'processing_time': embedding_results['processing_time']
        }

    # ==================== BATCH PROCESSING & WORKER LOGIC ====================

    def generate_batch_embeddings(self, chunks: List[Any]) -> Dict[str, Any]:
        # Create embeddings for many chunks, skipping any that already exist
        from content_ingestion.models import Embedding  # Import here to avoid circular dependency

        if not chunks:
            return {
                'success': 0, 'failed': 0, 'total': 0, 'skipped': 0,
                'models_used': {}, 'processing_time': 0.0, 'embeddings': []
            }

        logger.info(f"Starting batch embedding for {len(chunks)} chunks with {self.max_workers} workers")

        # Identify chunks that already have embeddings
        existing_chunk_ids = set(
            Embedding.objects.filter(
                document_chunk_id__in=[c.id for c in chunks]
            ).values_list('document_chunk_id', flat=True)
        )
        
        chunks_to_process = [c for c in chunks if c.id not in existing_chunk_ids]
        skipped_count = len(chunks) - len(chunks_to_process)

        if not chunks_to_process:
            logger.info(f"All {len(chunks)} chunks already have embeddings. Nothing to do.")
            return {
                'success': 0, 'failed': 0, 'total': len(chunks), 'skipped': skipped_count,
                'models_used': {}, 'processing_time': 0.0, 'embeddings': []
            }
        
        logger.info(f"Skipping {skipped_count} existing embeddings, processing {len(chunks_to_process)} new chunks.")

        # Group chunks by model type for efficient batch processing
        chunks_by_model: Dict[EmbeddingModelType, List[Any]] = {}
        for chunk in chunks_to_process:
            model_type = self._get_model_type_for_chunk(getattr(chunk, 'chunk_type', ''))
            chunks_by_model.setdefault(model_type, []).append(chunk)

        logger.info(f"New chunks grouped by model: {[(mt.value, len(chs)) for mt, chs in chunks_by_model.items()]}")

        results = {
            'success': 0,
            'failed': 0,
            'total': len(chunks),
            'skipped': skipped_count,
            'models_used': {},
            'processing_time': 0.0,
            'embeddings': []
        }

        start_time = time.time()

        # Process each model group separately
        for model_type, model_chunks in chunks_by_model.items():
            logger.info(f"Processing {len(model_chunks)} chunks with {model_type.value}")
            try:
                # Ensure model is loaded once per type
                if self._load_model(model_type) is None:
                    logger.error(f"Skipping {model_type.value}: model failed to load")
                    results['failed'] += len(model_chunks)
                    continue

                batch_results = self.embed_chunks_batch(model_chunks)

                results['success'] += batch_results.get('success', 0)
                results['failed'] += batch_results.get('failed', 0)
                results['models_used'][model_type.value] = len(model_chunks)
                results['embeddings'].extend(batch_results.get('embeddings', []))

            except Exception as e:
                logger.error(f"Batch processing failed for model {model_type}: {e}")
                results['failed'] += len(model_chunks)

        results['processing_time'] = time.time() - start_time
        logger.info(
            f"Batch embedding completed: "
            f"{results['success']} success, {results['failed']} failed, {results['skipped']} skipped"
        )

        return results

    def embed_chunks_batch(self, model_chunks: List[Any]) -> Dict[str, Any]:
        # Encode a list of chunks that share the same model type
        success, failed, items = 0, 0, []

        def _work(chunk: Any) -> Dict[str, Any]:
            # Expect chunk to have: .text, .chunk_type, .id (and optional .subtopic_id)
            res = self.generate_embedding(getattr(chunk, 'text', ''), getattr(chunk, 'chunk_type', ''))
            if res['vector'] is None:
                raise RuntimeError(res.get('error') or 'embedding failed')
            model_type_str = res['model_type'].value if hasattr(res['model_type'], 'value') else str(res['model_type'])
            return {
                'chunk': chunk,
                'embedding': res['vector'],
                'model_type': model_type_str,
                'model_name': res['model_name'],
                'dimension': res['dimension'],
            }

        # Fan out in threads
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = [ex.submit(_work, c) for c in model_chunks]
            for f in futures:
                try:
                    items.append(f.result())
                    success += 1
                except Exception as e:
                    logger.error(f"Chunk embedding failed: {e}")
                    failed += 1

        return {'success': success, 'failed': failed, 'total': success + failed, 'embeddings': items}

    # ==================== SINGLE EMBEDDING GENERATION ====================

    def generate_embedding(self, text: str, chunk_type: str) -> Dict[str, Any]:
        # Create an embedding for one piece of text
        try:
            model_type = self._get_model_type_for_chunk(chunk_type)
            model_data = self._load_model(model_type)
            if model_data is None:
                return {
                    'vector': None,
                    'model_name': MODEL_CONFIGS[model_type].model_name,
                    'model_type': model_type,
                    'dimension': 0,
                    'error': f"Failed to load {model_type.value} model"
                }

            clean_text = self._prepare_text_for_embedding(text, model_data['config'])

            if model_type == EmbeddingModelType.CODE_BERT:
                embedding = self._generate_codebert_embedding(clean_text, model_data)
            else:
                embedding = self._generate_sentence_embedding(clean_text, model_data)

            if embedding is None:
                return {
                    'vector': None,
                    'model_name': model_data['config'].model_name,
                    'model_type': model_type,
                    'dimension': 0,
                    'error': f"Embedding generation failed for {model_type.value}"
                }

            logger.debug(f"Generated {len(embedding)}-dim embedding using {model_type.value}")

            return {
                'vector': embedding,
                'model_name': model_data['config'].model_name,
                'model_type': model_type,
                'dimension': len(embedding),
                'error': None
            }

        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            return {
                'vector': None,
                'model_name': 'unknown',
                'model_type': None,
                'dimension': 0,
                'error': str(e)
            }

    # ==================== MODEL LOADING & MANAGEMENT ====================

    def _get_model_type_for_chunk(self, chunk_type: str) -> EmbeddingModelType:
        # Pick the model family to use for a given chunk type
        return CHUNK_TYPE_TO_MODEL.get(chunk_type, EmbeddingModelType.SENTENCE_TRANSFORMER)

    def _load_model(self, model_type: EmbeddingModelType) -> Optional[dict]:
        # Load a model once and cache it
        with self._model_lock:
            if model_type in self.models:
                return self.models[model_type]

            config: EmbeddingConfig = MODEL_CONFIGS[model_type]
            logger.info(f"Loading {model_type.value} model: {config.model_name}")

            try:
                if model_type == EmbeddingModelType.CODE_BERT:
                    # Load CodeBERT model
                    from transformers import AutoModel, AutoTokenizer
                    import torch

                    model = AutoModel.from_pretrained(config.model_name)
                    tokenizer = AutoTokenizer.from_pretrained(config.model_name)

                    if self.use_gpu and torch.cuda.is_available():
                        model = model.cuda()
                        logger.info(f"Moved {config.model_name} to GPU")

                    self.models[model_type] = {
                        'model': model,
                        'tokenizer': tokenizer,
                        'config': config
                    }

                elif model_type == EmbeddingModelType.SENTENCE_TRANSFORMER:
                    # Load Sentence Transformer model
                    from sentence_transformers import SentenceTransformer
                    import torch

                    device = 'cuda' if (self.use_gpu and torch.cuda.is_available()) else 'cpu'
                    model = SentenceTransformer(config.model_name, device=device)

                    self.models[model_type] = {
                        'model': model,
                        'config': config
                    }

                logger.info(f"Successfully loaded {model_type.value} model")
                return self.models[model_type]

            except ImportError as e:
                logger.error(f"Missing dependencies for {model_type.value}: {e}")
                logger.info("Install with: pip install transformers sentence-transformers torch")
                return None
            except Exception as e:
                logger.error(f"Failed to load {model_type.value} model: {e}")
                return None

    # ==================== LOW-LEVEL EMBEDDING GENERATION ====================

    def _generate_codebert_embedding(self, text: str, model_data: dict) -> Optional[List[float]]:
        # Generate embedding for code-like text using CodeBERT
        try:
            import torch

            model = model_data['model']
            tokenizer = model_data['tokenizer']
            config: EmbeddingConfig = model_data['config']

            inputs = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=config.max_length
            )

            if self.use_gpu and torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            with torch.no_grad():
                outputs = model(**inputs)
                # Use [CLS] token embedding (first token)
                embedding = outputs.last_hidden_state[:, 0, :].detach().cpu().numpy()[0]

            return embedding.tolist()

        except Exception as e:
            logger.error(f"CodeBERT embedding failed: {e}")
            return None

    def _generate_sentence_embedding(self, text: str, model_data: dict) -> Optional[List[float]]:
        # Generate embedding for natural-language text using SentenceTransformer
        try:
            model = model_data['model']
            embedding = model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Sentence transformer embedding failed: {e}")
            return None

    # ==================== TEXT PREPARATION ====================

    def _prepare_text_for_embedding(self, text: str, config: 'EmbeddingConfig') -> str:
        # Light cleanup and length control for the text
        if not text:
            return ""

        # Basic cleaning
        clean_text = text.strip()
        clean_text = ' '.join(clean_text.split())

        # Model-specific preparation
        if getattr(config, 'model_type', None) == EmbeddingModelType.CODE_BERT:
            # For code, preserve structure better; keep non-empty lines
            lines = text.split('\n')
            clean_lines = [line.rstrip() for line in lines if line.strip()]
            clean_text = '\n'.join(clean_lines)

        # Truncate based on model's max length (rough 4 chars per token)
        max_chars = int(getattr(config, 'max_length', 512)) * 4
        if len(clean_text) > max_chars:
            clean_text = clean_text[:max_chars]
            logger.debug(f"Text truncated to {len(clean_text)} chars for {getattr(config, 'model_type', 'unknown')}")

        return clean_text

    # ==================== DATABASE OPERATIONS ====================

    def save_embeddings_to_db(self, embeddings: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Persist embeddings to the DB using appropriate vector fields
        from content_ingestion.models import Embedding  # your Embedding model
        from traceback import format_exc

        success = 0
        failed = 0
        start_time = time.time()

        logger.info(f"save_embeddings_to_db: saving {len(embeddings)} embeddings to DB")

        for embedding_data in embeddings:
            try:
                chunk = embedding_data['chunk']
                vector = embedding_data['embedding']
                model_type = embedding_data.get('model_type', 'sentence')
                model_name = embedding_data.get('model_name', 'all-MiniLM-L6-v2')
                dimension = embedding_data.get('dimension', len(vector))

                logger.debug(f"Saving embedding for chunk_id={getattr(chunk, 'id', 'unknown')} model_type={model_type} model_name={model_name} dim={dimension}")

                # Prepare the appropriate vector field and defaults
                defaults = {
                    'model_name': model_name,
                    'dimension': dimension,
                    'embedded_at': timezone.now()
                }
                
                # Set the appropriate vector field based on model type
                if model_type == 'sentence' or 'minilm' in model_name.lower():
                    defaults['minilm_vector'] = vector
                elif model_type == 'code_bert' or 'codebert' in model_name.lower():
                    defaults['codebert_vector'] = vector
                else:
                    logger.error(f"Unsupported model type for embedding: {model_type} (model_name={model_name})")
                    failed += 1
                    continue

                # Create or update embedding with correct vector field
                try:
                    embedding_obj, created = Embedding.objects.get_or_create(
                        document_chunk=chunk,
                        model_type=model_type,
                        content_type='chunk',
                        defaults=defaults
                    )
                except Exception as e:
                    # Log full stack for DB get_or_create failures
                    logger.error(f"get_or_create failed for chunk {getattr(chunk, 'id', 'unknown')}: {e}\n{format_exc()}")
                    failed += 1
                    continue

                if created:
                    logger.debug(f"Created new Embedding id={embedding_obj.id} for chunk_id={getattr(chunk, 'id', 'unknown')}")
                else:
                    # Update existing embedding
                    logger.debug(f"Updating existing Embedding id={embedding_obj.id} for chunk_id={getattr(chunk, 'id', 'unknown')}")
                    if model_type == 'sentence' or 'minilm' in model_name.lower():
                        embedding_obj.minilm_vector = vector
                    elif model_type == 'code_bert' or 'codebert' in model_name.lower():
                        embedding_obj.codebert_vector = vector
                    
                    embedding_obj.model_name = model_name
                    embedding_obj.dimension = dimension
                    embedding_obj.embedded_at = timezone.now()
                    try:
                        embedding_obj.save()
                    except Exception as e:
                        logger.error(f"Failed to save updated embedding {embedding_obj.id} for chunk {getattr(chunk, 'id', 'unknown')}: {e}\n{format_exc()}")
                        failed += 1
                        continue

                # Sanity check: confirm vector field exists after save
                try:
                    refreshed = Embedding.objects.get(id=embedding_obj.id)
                    has_vector = bool(refreshed.minilm_vector or refreshed.codebert_vector)
                    if not has_vector:
                        logger.warning(f"Embedding saved but vector missing for id={embedding_obj.id} chunk_id={getattr(chunk, 'id', 'unknown')}")
                    else:
                        logger.debug(f"Embedding id={embedding_obj.id} contains vector(s) after save")
                except Exception as e:
                    logger.error(f"Failed to refresh embedding {getattr(embedding_obj, 'id', 'unknown')}: {e}\n{format_exc()}")

                success += 1

            except Exception as e:
                failed += 1
                try:
                    cid = getattr(embedding_data.get('chunk', None), 'id', 'unknown')
                except Exception:
                    cid = 'unknown'
                logger.error(f"DB save failed for chunk {cid}: {e}\n{format_exc()}")

        return {
            'success': success,
            'failed': failed,
            'processing_time': time.time() - start_time
        }

    # ==================== OTHER PUBLIC METHODS ====================

    def generate_subtopic_embedding(self, subtopic_name: str, topic_name: str = "") -> Dict[str, Any]:
        # Create an embedding for a subtopic name (optionally with its topic)
        text = f"{topic_name} - {subtopic_name}" if topic_name else subtopic_name
        return self.generate_embedding(text, chunk_type='Concept')

    def generate_subtopic_dual_embeddings(self, subtopic) -> Dict[str, Any]:
        # Generate dual embeddings for a subtopic using intent-based content
        from content_ingestion.models import Embedding
        
        results = {
            'subtopic_id': subtopic.id,
            'subtopic_name': subtopic.name,
            'concept_embedding': None,
            'code_embedding': None,
            'embeddings_created': 0,
            'errors': []
        }
        
        try:
            # Remove existing subtopic embeddings to replace them
            Embedding.objects.filter(
                subtopic=subtopic,
                content_type='subtopic'
            ).delete()
            
            # Generate concept embedding (MiniLM) if concept_intent exists
            if subtopic.concept_intent:
                concept_text = f"{subtopic.topic.name} - {subtopic.name}: {subtopic.concept_intent}"
                concept_result = self.generate_embedding(concept_text, chunk_type='Concept')
                
                if concept_result['vector'] is not None:
                    # Save concept embedding
                    concept_embedding = Embedding.objects.create(
                        subtopic=subtopic,
                        content_type='subtopic',
                        model_type='sentence',
                        model_name=concept_result['model_name'],
                        dimension=concept_result['dimension'],
                        minilm_vector=concept_result['vector']
                    )
                    results['concept_embedding'] = concept_embedding.id
                    results['embeddings_created'] += 1
                else:
                    results['errors'].append(f"Failed to generate concept embedding: {concept_result.get('error', 'Unknown error')}")
            
            # Generate code embedding (CodeBERT) if code_intent exists
            if subtopic.code_intent:
                code_text = f"{subtopic.topic.name} - {subtopic.name}: {subtopic.code_intent}"
                code_result = self.generate_embedding(code_text, chunk_type='Code')
                
                if code_result['vector'] is not None:
                    # Save code embedding (update existing or create new)
                    if results['concept_embedding']:
                        # Update existing embedding with CodeBERT vector
                        concept_embedding = Embedding.objects.get(id=results['concept_embedding'])
                        concept_embedding.codebert_vector = code_result['vector']
                        concept_embedding.save()
                    else:
                        # Create new embedding with only CodeBERT vector
                        code_embedding = Embedding.objects.create(
                            subtopic=subtopic,
                            content_type='subtopic',
                            model_type='code_bert',
                            model_name=code_result['model_name'],
                            dimension=code_result['dimension'],
                            codebert_vector=code_result['vector']
                        )
                        results['code_embedding'] = code_embedding.id
                        results['embeddings_created'] += 1
                else:
                    results['errors'].append(f"Failed to generate code embedding: {code_result.get('error', 'Unknown error')}")
            
            results['success'] = results['embeddings_created'] > 0
            logger.info(f"Generated {results['embeddings_created']} embeddings for subtopic '{subtopic.name}'")
            
        except Exception as e:
            logger.error(f"Error generating dual embeddings for subtopic {subtopic.id}: {e}")
            results['success'] = False
            results['errors'].append(str(e))
        
        return results


# Convenience functions for easy usage
def get_embedding_generator(max_workers: int = 4, use_gpu: bool = False) -> EmbeddingGenerator:
    """
    Shortcut for a configured EmbeddingGenerator.
    """
    return EmbeddingGenerator(max_workers=max_workers, use_gpu=use_gpu)


def embed_chunks_with_models(chunks: List[Any], max_workers: int = 4, use_gpu: bool = False) -> Dict[str, Any]:
    """
    Quick way to embed a list of chunks using default settings.
    """
    generator = EmbeddingGenerator(max_workers=max_workers, use_gpu=use_gpu)
    return generator.generate_batch_embeddings(chunks)
