# Worker entrypoints for subprocess-safe embedding generation.

import os
import logging
import django


logger = logging.getLogger(__name__)
_DJANGO_READY = False


def setup_django() -> None:
    # Initialize Django once per worker process.
    global _DJANGO_READY
    if _DJANGO_READY:
        return
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pygrounds_backend_new.settings')
    django.setup()
    _DJANGO_READY = True


def generate_embedding_task(args):
    # Generate a subtopic embedding inside a worker process.
    setup_django()

    subtopic_id, model_type = args
    logger.info("Worker generating %s embedding for subtopic %s", model_type, subtopic_id)

    try:
        from content_ingestion.models import Subtopic
        from content_ingestion.helpers.embedding.generator import EmbeddingGenerator

        subtopic = Subtopic.objects.get(id=subtopic_id)
        generator = EmbeddingGenerator()

        if model_type == 'concept':
            text = f"{subtopic.topic.name} - {subtopic.name}: {subtopic.concept_intent}"
            result = generator.generate_embedding(text, chunk_type='Concept')
        else:
            text = f"Python task: {subtopic.topic.name} - {subtopic.name}. Use: {subtopic.code_intent}"
            result = generator.generate_embedding(text, chunk_type='Code')

        success = bool(result.get('vector'))
        logger.info("%s embedding %s for subtopic %s", model_type, "generated" if success else "failed", subtopic_id)
        return model_type, result.get('vector')

    except Exception as e:
        logger.exception("Error generating %s embedding for subtopic %s", model_type, subtopic_id)
        return model_type, None
