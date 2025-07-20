import os
import sys
import django

# Add the project directory to Python path
sys.path.append('c:\\Users\\Ju\\Documents\\PYGROUNDS\\pygrounds_backend_new')

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pygrounds_backend_new.settings')
django.setup()

import requests
import json

def test_hangman_function_format():
    """Test the new function format for hangman coding"""
    
    url = "http://127.0.0.1:8000/questions/compare/subtopic/2/"
    
    # Test data
    data = {
        "minigame_type": "hangman_coding",
        "force_regenerate": True
    }
    
    print("Testing hangman coding with function format...")
    print(f"Request data: {data}")
    print("-" * 50)
    
    try:
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            result = response.json()
            print("SUCCESS!")
            print(f"Status: {response.status_code}")
            print(f"Response keys: {list(result.keys())}")
            
            # Check if we have generated questions
            if 'generated_questions' in result and result['generated_questions']:
                question = result['generated_questions'][0]  # Get first question
                print(f"\nFirst Generated Question:")
                print(f"Question keys: {list(question.keys())}")
                
                if 'question_text' in question:
                    print(f"\nQuestion Text:")
                    print(question['question_text'])
                    
                if 'game_data' in question:
                    print(f"\nGame Data:")
                    game_data = question['game_data']
                    
                    if 'hangman_version' in game_data:
                        print(f"\nHangman Version:")
                        print(game_data['hangman_version'])
                        
                    if 'complete_function' in game_data:
                        print(f"\nComplete Function:")
                        print(game_data['complete_function'])
                        
                    if 'function_name' in game_data:
                        print(f"\nFunction Name: {game_data['function_name']}")
                        
                    if 'parameters' in game_data:
                        print(f"Parameters: {game_data['parameters']}")
                        
                if 'correct_answer' in question:
                    print(f"\nCorrect Answer:")
                    print(question['correct_answer'])
            else:
                print("\nNo generated questions found in response!")
                print(f"Full response: {json.dumps(result, indent=2)}")
            
        else:
            print(f"ERROR: Status {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"Exception occurred: {e}")

if __name__ == "__main__":
    test_hangman_function_format()
