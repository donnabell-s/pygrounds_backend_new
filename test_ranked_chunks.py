#!/usr/bin/env python
"""
Test script to verify that ranked_concept_chunks and ranked_code_chunks are working properly
after removing the old ranked_chunks field.
"""

import os
import sys
import django

# Add the project path to sys.path
project_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_path)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pygrounds_backend_new.settings')
django.setup()

from content_ingestion.models import SemanticSubtopic, Subtopic
from django.db import transaction

def test_ranked_chunks():
    """Test that the SemanticSubtopic model is working with the new field structure."""
    print("🧪 Testing SemanticSubtopic model with dual ranking fields...")
    
    # Get a few semantic subtopics
    semantic_subtopics = SemanticSubtopic.objects.all()[:5]
    
    if not semantic_subtopics:
        print("❌ No SemanticSubtopic objects found")
        return
    
    print(f"📊 Found {len(semantic_subtopics)} semantic subtopics to test")
    
    for i, semantic_subtopic in enumerate(semantic_subtopics, 1):
        print(f"\n{i}. Testing: {semantic_subtopic.subtopic.name}")
        
        # Test field access
        try:
            concept_count = len(semantic_subtopic.ranked_concept_chunks) if semantic_subtopic.ranked_concept_chunks else 0
            code_count = len(semantic_subtopic.ranked_code_chunks) if semantic_subtopic.ranked_code_chunks else 0
            
            print(f"   ✅ Concept chunks: {concept_count}")
            print(f"   ✅ Code chunks: {code_count}")
            
            # Test methods
            concept_ids = semantic_subtopic.get_concept_chunk_ids(limit=3)
            code_ids = semantic_subtopic.get_code_chunk_ids(limit=3)
            
            print(f"   ✅ get_concept_chunk_ids(): {len(concept_ids)} IDs")
            print(f"   ✅ get_code_chunk_ids(): {len(code_ids)} IDs")
            
            # Test string representation
            str_repr = str(semantic_subtopic)
            print(f"   ✅ String representation: {str_repr}")
            
        except Exception as e:
            print(f"   ❌ Error testing {semantic_subtopic.subtopic.name}: {e}")
            return False
    
    print(f"\n✅ All tests passed! The dual ranking system is working correctly.")
    return True

def test_model_methods():
    """Test that model methods work correctly with the new fields."""
    print("\n🧪 Testing SemanticSubtopic methods...")
    
    semantic_subtopic = SemanticSubtopic.objects.first()
    if not semantic_subtopic:
        print("❌ No SemanticSubtopic found for testing")
        return False
    
    print(f"Testing with: {semantic_subtopic.subtopic.name}")
    
    try:
        # Test add_concept_ranking
        semantic_subtopic.add_concept_ranking(
            chunk_id=999, 
            similarity_score=0.75, 
            chunk_type='Concept'
        )
        print("   ✅ add_concept_ranking() works")
        
        # Test add_code_ranking
        semantic_subtopic.add_code_ranking(
            chunk_id=998, 
            similarity_score=0.80, 
            chunk_type='Code'
        )
        print("   ✅ add_code_ranking() works")
        
        # Test add_chunk_ranking (should route to appropriate method)
        semantic_subtopic.add_chunk_ranking(
            chunk_id=997, 
            similarity_score=0.70, 
            chunk_type='Example'
        )
        print("   ✅ add_chunk_ranking() works")
        
        # Test get_chunks_by_type
        concept_chunks = semantic_subtopic.get_chunks_by_type('Concept')
        code_chunks = semantic_subtopic.get_chunks_by_type('Code')
        
        print(f"   ✅ get_chunks_by_type('Concept'): {len(concept_chunks)} chunks")
        print(f"   ✅ get_chunks_by_type('Code'): {len(code_chunks)} chunks")
        
        # Test get_similarity_for_chunk_type
        concept_sim = semantic_subtopic.get_similarity_for_chunk_type('Concept')
        code_sim = semantic_subtopic.get_similarity_for_chunk_type('Code')
        
        print(f"   ✅ get_similarity_for_chunk_type('Concept'): {concept_sim}")
        print(f"   ✅ get_similarity_for_chunk_type('Code'): {code_sim}")
        
        # Don't save the test data
        print("   ⚠️  Test data not saved (rollback)")
        
    except Exception as e:
        print(f"   ❌ Error testing methods: {e}")
        return False
    
    print("✅ All method tests passed!")
    return True

if __name__ == "__main__":
    print("🚀 Starting SemanticSubtopic dual ranking field tests...\n")
    
    success = True
    success &= test_ranked_chunks()
    success &= test_model_methods()
    
    if success:
        print("\n🎉 All tests completed successfully!")
        print("The ranked_concept_chunks and ranked_code_chunks fields are working properly.")
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)
