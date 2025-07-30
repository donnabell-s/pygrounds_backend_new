#!/usr/bin/env python
"""
Simple Question Generation Test

Quick test script for single question generation configuration.
Uses the cleaned up system with single JSON output files.
"""

import requests
import json

def test_single_generation():
    """Test a single question generation configuration."""
    
    url = "http://localhost:8000/questions/test/generate/"
    
    # Test configuration - modify as needed
    payload = {
        "difficulty": "beginner",
        "game_type": "non_coding",
        "num_questions": 1,
        "topic_ids": [8]  # Basic Input and Output
    }
    
    print("🧪 Testing Single Question Generation")
    print(f"📊 Config: {payload}")
    print("-" * 40)
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Success!")
            print(f"📊 Stats: {data.get('stats', {})}")
            print(f"📁 Output: {data.get('output_file', 'Unknown')}")
            
            # Show first question preview
            questions = data.get('questions', [])
            if questions:
                print(f"\n📝 Sample Question Preview:")
                question = questions[0]
                print(f"   Subtopic: {question.get('subtopic_name', 'Unknown')}")
                print(f"   Question: {question.get('question', 'Unknown')[:100]}...")
                print(f"   Difficulty: {question.get('difficulty', 'Unknown')}")
                print(f"   Game Type: {question.get('game_type', 'Unknown')}")
            
        else:
            print(f"❌ Error {response.status_code}")
            print(response.text[:500])
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_single_generation()
