"""
Separate worker module for embedding generation to avoid Django import issues.
This module can be safely imported by ProcessPool workers.
"""
import os
import django

def generate_embedding_task(args):
    """
    Generate embedding for a subtopic in a separate process.
    This function is in a separate module to avoid Django import issues.
    """
    # Initialize Django in the worker process
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pygrounds_backend_new.settings')
    django.setup()
    
    subtopic_id, model_type = args
    import logging
    
    logger = logging.getLogger(__name__)
    print(f"\n🔄 Worker process generating {model_type} embedding for subtopic {subtopic_id}...")
    
    try:
        # Import models after Django setup
        from content_ingestion.models import Subtopic
        from content_ingestion.helpers.embedding.generator import EmbeddingGenerator
        
        # Get fresh instance to avoid process sharing issues
        subtopic = Subtopic.objects.get(id=subtopic_id)
        generator = EmbeddingGenerator()
        
        if model_type == 'concept':
            text = f"{subtopic.topic.name} - {subtopic.name}: {subtopic.concept_intent}"
            print(f"   📝 Processing concept text: {text[:100]}...")
            result = generator.generate_embedding(text, chunk_type='Concept')
        else:  # code
            text = f"Python task: {subtopic.topic.name} - {subtopic.name}. Use: {subtopic.code_intent}"
            print(f"   💻 Processing code text: {text[:100]}...")
            result = generator.generate_embedding(text, chunk_type='Code')
        
        success = bool(result.get('vector'))
        print(f"{'✅' if success else '❌'} {model_type.title()} embedding {'generated' if success else 'failed'}")
        return model_type, result.get('vector')
        
    except Exception as e:
        print(f"❌ Error generating {model_type} embedding: {str(e)}")
        logger.error(f"Error generating {model_type} embedding for subtopic {subtopic_id}: {e}")
        return model_type, None
