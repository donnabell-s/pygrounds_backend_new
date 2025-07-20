#!/usr/bin/env python
"""
Test JSON loading via HTTP request to debug endpoint
"""

import requests
import json

def test_json_debug():
    """Test if JSON is loading properly via the server"""
    
    print("Testing JSON loading through server...")
    
    try:
        # Make a test request to see detailed game_data
        base_url = "http://localhost:8000"
        subtopic_id = 17
        
        request_data = {
            'max_questions': 1,
            'minigame_type': 'hangman_coding',
            'force_regenerate': True
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
            question = data['generated_questions'][0]
            game_data = question.get('game_data', {})
            
            print("📊 DETAILED GAME DATA:")
            print(json.dumps(game_data, indent=2))
            
            # Check if it's using fallback
            is_fallback = game_data.get('fallback', False)
            print(f"\n🔍 Is Fallback: {is_fallback}")
            
            if 'snippet_id' in game_data:
                print(f"✅ Using JSON snippet: {game_data['snippet_id']}")
            else:
                print("❌ Not using JSON snippets - using fallback")
                
            # Check specific validation fields
            validation_type = game_data.get('validation_type')
            expected_output = game_data.get('expected_output')
            print(f"\n🎯 Validation Type: {validation_type}")
            print(f"🎯 Expected Output Present: {expected_output is not None}")
            
        else:
            print(f"❌ Request failed: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == '__main__':
    test_json_debug()
