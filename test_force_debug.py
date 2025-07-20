#!/usr/bin/env python
"""
Force regeneration and detailed debugging
"""

import requests
import json

def test_force_regenerate():
    """Force regeneration with detailed debugging"""
    
    print("Testing force regeneration...")
    
    try:
        base_url = "http://localhost:8000"
        subtopic_id = 17
        
        request_data = {
            'max_questions': 1,
            'minigame_type': 'hangman_coding',
            'force_regenerate': True,
            'debug': True  # If this exists
        }
        
        url = f"{base_url}/questions/compare/subtopic/{subtopic_id}/"
        response = requests.post(
            url,
            json=request_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            print("📊 FULL RESPONSE:")
            print(json.dumps(data, indent=2))
            
            if data.get('generated_questions'):
                question = data['generated_questions'][0]
                print(f"\n🎯 QUESTION DETAILS:")
                print(f"Question ID: {question.get('id', 'N/A')}")
                print(f"Minigame Type: {question.get('minigame_type', 'N/A')}")
                print(f"Game Type: {question.get('game_type', 'N/A')}")
                print(f"Game Data: {question.get('game_data', 'MISSING')}")
                
        else:
            print(f"❌ Request failed: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == '__main__':
    test_force_regenerate()
