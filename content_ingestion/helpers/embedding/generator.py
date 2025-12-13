import os
import threading
import time
import logging
import multiprocessing
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from django.utils import timezone
from django.db import transaction

from .models import (
    EmbeddingModelType, EmbeddingConfig, MODEL_CONFIGS, CHUNK_TYPE_TO_MODEL
)

logger = logging.getLogger(__name__)


def _is_in_subprocess() -> bool:
    # Avoid nested multiprocessing when already in a worker process.
    try:
        # Check if current process is not the main process
        return multiprocessing.current_process().name != 'MainProcess'
    except Exception:
        return False


# Worker function for multiprocessing (must be at module level for pickling)
def _embed_chunk_worker(chunk_id: int, text: str, chunk_type: str) -> Dict[str, Any]:
    # Module-level worker function (required for multiprocessing pickling).
    try:
        # Create a fresh generator instance in this process
        # Each process gets its own model cache
        generator = EmbeddingGenerator(max_workers=1, use_gpu=False)
        
        result = generator.generate_embedding(text, chunk_type)
        
        if result['vector'] is None:
            raise RuntimeError(result.get('error', 'Embedding generation failed'))
        
        model_type_str = result['model_type'].value if hasattr(result['model_type'], 'value') else str(result['model_type'])
        
        return {
            'chunk_id': chunk_id,
            'embedding': result['vector'],
            'model_type': model_type_str,
            'model_name': result['model_name'],
            'dimension': result['dimension'],
        }
    except Exception as e:
        logger.error(f"Worker failed for chunk {chunk_id}: {e}")
        raise


class EmbeddingGenerator:
    # Embedding generation for code vs concept chunks (parallel + cached models).

    def __init__(self, max_workers: int = None, use_gpu: bool = False):
        # Configure workers + whether to use GPU.
        self.max_workers = max_workers or multiprocessing.cpu_count()
        self.use_gpu = use_gpu
        self.models: Dict[EmbeddingModelType, dict] = {}  # Cache loaded models
        self._model_lock = threading.Lock()
        
        # Detect if we're in a subprocess to avoid nested multiprocessing
        in_subprocess = _is_in_subprocess()
        
        # Use ProcessPoolExecutor for CPU-bound work (unless GPU is used OR we're in a subprocess)
        if in_subprocess:
            # We're already in a worker process - use ThreadPool or sequential
            self.executor_class = ThreadPoolExecutor
            logger.info(f"Running in subprocess - using ThreadPoolExecutor to avoid nested multiprocessing")
        else:
            # Main process - use ProcessPool for true parallelism (unless GPU)
            self.executor_class = ThreadPoolExecutor if use_gpu else ProcessPoolExecutor

        logger.info(f"Initialized EmbeddingGenerator with {self.max_workers} workers, GPU: {use_gpu}, In subprocess: {in_subprocess}, Executor: {self.executor_class.__name__}")

    def _get_model_type_for_chunk(self, chunk_type: str) -> EmbeddingModelType:
        # Map chunk types to embedding model families.
        return CHUNK_TYPE_TO_MODEL.get(chunk_type, EmbeddingModelType.SENTENCE_TRANSFORMER)

    def _load_model(self, model_type: EmbeddingModelType) -> Optional[dict]:
        # Lazy-load and cache models per model type.
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

    def _generate_codebert_embedding(self, text: str, model_data: dict) -> Optional[List[float]]:
        # Make a vector for code-like text using CodeBERT.
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
        # Make a vector for natural-language text using a SentenceTransformer.
        try:
            model = model_data['model']
            embedding = model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Sentence transformer embedding failed: {e}")
            return None

    def generate_subtopic_embedding(self, subtopic_name: str, topic_name: str = "") -> Dict[str, Any]:
        # Embed a subtopic name (optionally prefixed by topic name).
        text = f"{topic_name} - {subtopic_name}" if topic_name else subtopic_name
        return self.generate_embedding(text, chunk_type='Concept')

    def generate_embedding(self, text: str, chunk_type: str) -> Dict[str, Any]:
                # Embed one piece of text (pick model by chunk_type; load; clean/truncate; encode).
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

    def generate_subtopic_dual_embeddings(self, subtopic) -> Dict[str, Any]:
        # Generate dual embeddings for a subtopic (MiniLM concept + CodeBERT code).
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
            
            # ALWAYS generate concept embedding (MiniLM) from name + optional concept_intent
            if subtopic.concept_intent:
                concept_text = f"{subtopic.topic.name} - {subtopic.name}: {subtopic.concept_intent}"
            else:
                # Use just the name and topic for semantic processing
                concept_text = f"{subtopic.topic.name} - {subtopic.name}"
            
            concept_result = self.generate_embedding(concept_text, chunk_type='Concept')
            
            if concept_result['vector'] is not None:
                # Save concept embedding (always created)
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
            
            # ALWAYS generate code embedding (CodeBERT) from name + optional code_intent
            if subtopic.code_intent:
                code_text = f"Python task: {subtopic.topic.name} - {subtopic.name}. Use: {subtopic.code_intent}"
            else:
                # Use name-based code context for dual embedding
                code_text = f"Python programming topic: {subtopic.topic.name} - {subtopic.name}"
            
            code_result = self.generate_embedding(code_text, chunk_type='Code')
            
            if code_result['vector'] is not None:
                # Always add CodeBERT vector to the existing embedding
                if results['concept_embedding']:
                    # Update existing embedding with CodeBERT vector (dual embedding)
                    concept_embedding = Embedding.objects.get(id=results['concept_embedding'])
                    concept_embedding.codebert_vector = code_result['vector']
                    concept_embedding.save()
                    # Note: embeddings_created count remains the same (it's one dual embedding)
                else:
                    # Fallback: create new embedding with only CodeBERT vector
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
            
            # Verify dual embedding was created
            if results['concept_embedding']:
                final_embedding = Embedding.objects.get(id=results['concept_embedding'])
                has_both = bool(final_embedding.minilm_vector) and bool(final_embedding.codebert_vector)
                logger.info(f"Generated dual embedding for subtopic '{subtopic.name}': MiniLM={bool(final_embedding.minilm_vector)}, CodeBERT={bool(final_embedding.codebert_vector)}")
            
            results['success'] = results['embeddings_created'] > 0
            logger.info(f"Generated {results['embeddings_created']} dual embeddings for subtopic '{subtopic.name}' (name: always, concept_intent: {bool(subtopic.concept_intent)}, code_intent: {bool(subtopic.code_intent)})")
            
        except Exception as e:
            logger.error(f"Error generating dual embeddings for subtopic {subtopic.id}: {e}")
            results['success'] = False
            results['errors'].append(str(e))
        
        return results

    def _prepare_text_for_embedding(self, text: str, config: 'EmbeddingConfig') -> str:
        # Light cleanup + length control (normalize whitespace; preserve code lines; truncate to token budget).
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

    def embed_chunks_batch(self, model_chunks: List[Any]) -> Dict[str, Any]:
        # Encode chunks that share the same model type.
        # Uses processes in main process; threads in subprocess to avoid nested multiprocessing.
        success, failed, items = 0, 0, []
        
        # Extract serializable data from chunks (avoid passing Django ORM objects to processes)
        chunk_data = [
            (c.id, c.text, c.chunk_type, c.subtopic_id if hasattr(c, 'subtopic_id') else None)
            for c in model_chunks
        ]
        
        # Create chunk lookup for results
        chunk_lookup = {c.id: c for c in model_chunks}

        # Fan out in processes (or threads if GPU)
        with self.executor_class(max_workers=self.max_workers) as ex:
            futures = [ex.submit(_embed_chunk_worker, cid, text, chunk_type) for cid, text, chunk_type, _ in chunk_data]
            
            for f in futures:
                try:
                    result = f.result()
                    chunk_id = result['chunk_id']
                    chunk = chunk_lookup[chunk_id]
                    
                    items.append({
                        'chunk': chunk,
                        'embedding': result['embedding'],
                        'model_type': result['model_type'],
                        'model_name': result['model_name'],
                        'dimension': result['dimension'],
                    })
                    success += 1
                except Exception as e:
                    logger.error(f"Chunk embedding failed: {e}")
                    failed += 1

        return {'success': success, 'failed': failed, 'total': success + failed, 'embeddings': items}

    def generate_batch_embeddings(self, chunks: List[Any]) -> Dict[str, Any]:
                # Create embeddings for many chunks by grouping per model type.
        if not chunks:
            return {
                'success': 0,
                'failed': 0,
                'total': 0,
                'models_used': {},
                'processing_time': 0.0,
                'embeddings': []
            }

        logger.info(f"Starting batch embedding for {len(chunks)} chunks with {self.max_workers} workers")

        # Group chunks by model type for efficient batch processing
        chunks_by_model: Dict[EmbeddingModelType, List[Any]] = {}
        for chunk in chunks:
            model_type = self._get_model_type_for_chunk(getattr(chunk, 'chunk_type', ''))
            chunks_by_model.setdefault(model_type, []).append(chunk)

        logger.info(f"Chunks grouped by model: {[(mt.value, len(chs)) for mt, chs in chunks_by_model.items()]}")

        results = {
            'success': 0,
            'failed': 0,
            'total': len(chunks),
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
        logger.info(f"Batch embedding completed: {results['success']} success, {results['failed']} failed")

        return results

    def embed_and_save_batch(self, chunks: List[Any]) -> Dict[str, Any]:
        # Run batch embedding and write results to the database.
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

    def save_embeddings_to_db(self, embeddings: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Persist embeddings to the DB using bulk_create/bulk_update.
        from content_ingestion.models import Embedding
        from traceback import format_exc

        success = 0
        failed = 0
        start_time = time.time()

        logger.info(f"save_embeddings_to_db: saving {len(embeddings)} embeddings to DB using bulk operations")
        
        # Prepare embeddings for bulk operations
        embeddings_to_create = []
        embeddings_to_update = []
        chunk_ids = [e['chunk'].id for e in embeddings]
        
        # Get existing embeddings in one query
        existing_embeddings = {}
        for emb in Embedding.objects.filter(document_chunk_id__in=chunk_ids, content_type='chunk'):
            key = (emb.document_chunk_id, emb.model_type)
            existing_embeddings[key] = emb

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

                # Check if embedding exists
                key = (chunk.id, model_type)
                existing = existing_embeddings.get(key)
                
                if existing:
                    # Update existing
                    if model_type == 'sentence' or 'minilm' in model_name.lower():
                        existing.minilm_vector = vector
                    elif model_type == 'code_bert' or 'codebert' in model_name.lower():
                        existing.codebert_vector = vector
                    
                    existing.model_name = model_name
                    existing.dimension = dimension
                    existing.embedded_at = timezone.now()
                    embeddings_to_update.append(existing)
                else:
                    # Create new
                    embedding_obj = Embedding(
                        document_chunk=chunk,
                        model_type=model_type,
                        content_type='chunk',
                        model_name=model_name,
                        dimension=dimension,
                        embedded_at=timezone.now()
                    )
                    
                    # Set appropriate vector field
                    if model_type == 'sentence' or 'minilm' in model_name.lower():
                        embedding_obj.minilm_vector = vector
                    elif model_type == 'code_bert' or 'codebert' in model_name.lower():
                        embedding_obj.codebert_vector = vector
                    
                    embeddings_to_create.append(embedding_obj)

            except Exception as e:
                failed += 1
                try:
                    cid = getattr(embedding_data.get('chunk', None), 'id', 'unknown')
                except Exception:
                    cid = 'unknown'
                logger.error(f"Embedding preparation failed for chunk {cid}: {e}\n{format_exc()}")
        
        # Bulk insert new embeddings
        try:
            if embeddings_to_create:
                with transaction.atomic():
                    Embedding.objects.bulk_create(embeddings_to_create, batch_size=500)
                    success += len(embeddings_to_create)
                    logger.info(f"Bulk created {len(embeddings_to_create)} embeddings")
        except Exception as e:
            logger.error(f"Bulk create failed: {e}\n{format_exc()}")
            failed += len(embeddings_to_create)
        
        # Bulk update existing embeddings
        try:
            if embeddings_to_update:
                with transaction.atomic():
                    Embedding.objects.bulk_update(
                        embeddings_to_update,
                        ['minilm_vector', 'codebert_vector', 'model_name', 'dimension', 'embedded_at'],
                        batch_size=500
                    )
                    success += len(embeddings_to_update)
                    logger.info(f"Bulk updated {len(embeddings_to_update)} embeddings")
        except Exception as e:
            logger.error(f"Bulk update failed: {e}\n{format_exc()}")
            failed += len(embeddings_to_update)

        return {
            'success': success,
            'failed': failed,
            'processing_time': time.time() - start_time
        }


# Convenience functions for easy usage
def get_embedding_generator(max_workers: int = 4, use_gpu: bool = False) -> EmbeddingGenerator:
    # Shortcut for a configured EmbeddingGenerator.
    return EmbeddingGenerator(max_workers=max_workers, use_gpu=use_gpu)


def embed_chunks_with_models(chunks: List[Any], max_workers: int = 4, use_gpu: bool = False) -> Dict[str, Any]:
    # Quick helper: embed a list of chunks using default settings.
    generator = EmbeddingGenerator(max_workers=max_workers, use_gpu=use_gpu)
    return generator.generate_batch_embeddings(chunks)
