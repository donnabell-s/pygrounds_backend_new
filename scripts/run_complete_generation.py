#!/usr/bin/env python
"""
Complete Question Generation Pipeline

This script runs question generation for all combinations of:
- Difficulties: beginner, intermediate, advanced, master  
- Game types: coding, non_coding
- Topics: configurable (currently set to topic 8)

Features:
- Uses the simplified question generation system with direct SemanticSubtopic integration
- Overwrites output files for each difficulty/game_type combination 
- Provides detailed progress tracking and error reporting
- Saves results to single JSON files (no timestamps) for easy access

Output files are saved as: generated_questions_{difficulty}_{game_type}.json
Example: generated_questions_beginner_coding.json

The JSON files contain:
- Generation metadata (difficulty, game_type, timestamps)
- All generated questions with full details
- Statistics (successful/failed generations, RAG contexts found)
- Error details for debugging
"""

import requests
import json
import time

def run_complete_generation():
    """
    Run question generation for all difficulty/game_type combinations.
    
    This function:
    1. Iterates through all difficulty levels and game types
    2. Sends requests to the Django test endpoint
    3. Tracks success/failure rates and saves results to JSON files
    4. Provides detailed console output for monitoring progress
    
    Each combination generates a separate JSON file that overwrites previous runs,
    making it easy to track the latest generation results.
    """
    
    base_url = "http://localhost:8000"
    endpoint = f"{base_url}/questions/test/generate/"
    
    # Configuration - modify these as needed
    difficulties = ["beginner", "intermediate", "advanced", "master"]
    game_types = ["coding", "non_coding"]
    topic_ids = [8]  # Basic Input and Output - can be extended to multiple topics
    num_questions = 1  # Keep small for testing, increase for production
    
    print("🚀 Starting Complete Question Generation Pipeline")
    print("=" * 60)
    print(f"📊 Difficulties: {difficulties}")
    print(f"🎮 Game Types: {game_types}")
    print(f"📚 Topic IDs: {topic_ids}")
    print(f"❓ Questions per subtopic: {num_questions}")
    print("=" * 60)
    
    results = []
    
    for difficulty in difficulties:
        for game_type in game_types:
            print(f"\n🎯 Running: {difficulty.upper()} + {game_type.upper()}")
            print("-" * 40)
            
            payload = {
                "difficulty": difficulty,
                "game_type": game_type,
                "num_questions": num_questions,
                "topic_ids": topic_ids
            }
            
            try:
                response = requests.post(endpoint, json=payload, timeout=300)  # 5 min timeout
                
                if response.status_code == 200:
                    data = response.json()
                    stats = data.get('stats', {})
                    output_file = data.get('output_file', 'Unknown')
                    
                    print(f"✅ Success!")
                    print(f"   📊 Successful: {stats.get('successful_generations', 0)}")
                    print(f"   ❌ Failed: {stats.get('failed_generations', 0)}")
                    print(f"   🎯 RAG Contexts: {stats.get('rag_contexts_found', 0)}")
                    print(f"   📁 Output: {output_file}")
                    
                    results.append({
                        'difficulty': difficulty,
                        'game_type': game_type,
                        'status': 'success',
                        'stats': stats,
                        'output_file': output_file
                    })
                    
                else:
                    print(f"❌ Error {response.status_code}: {response.text[:200]}")
                    results.append({
                        'difficulty': difficulty,
                        'game_type': game_type,
                        'status': 'error',
                        'error': response.text[:200]
                    })
                
                # Brief pause between requests
                time.sleep(2)
                
            except Exception as e:
                print(f"❌ Request failed: {e}")
                results.append({
                    'difficulty': difficulty,
                    'game_type': game_type,
                    'status': 'exception',
                    'error': str(e)
                })
    
    print("\n🎉 Complete Generation Summary")
    print("=" * 60)
    
    successful = len([r for r in results if r['status'] == 'success'])
    total = len(results)
    
    print(f"✅ Successful: {successful}/{total}")
    print(f"📁 Output files generated:")
    
    for result in results:
        if result['status'] == 'success':
            print(f"   - {result['difficulty']}_{result['game_type']}: {result.get('output_file', 'Unknown')}")
    
    print(f"\n📍 Check the 'question_outputs' directory for all generated files!")

if __name__ == "__main__":
    print("Make sure Django server is running: python manage.py runserver")
    input("Press Enter to continue or Ctrl+C to cancel...")
    run_complete_generation()
