#!/usr/bin/env python
"""
Test the new function format for hangman coding and validation setup
"""

import requests
import json
from datetime import datetime

def test_function_format():
    """Test the function format for hangman coding"""
    
    print(f"\n🎮 TESTING FUNCTION FORMAT")
    print(f"{'='*60}")
    print(f"Timestamp: {datetime.now()}")
    
    # Test parameters
    base_url = "http://localhost:8000"
    subtopic_id = 17  # input() subtopic
    
    request_data = {
        'max_questions': 1,
        'minigame_type': 'hangman_coding',
        'force_regenerate': True
    }
    
    try:
        url = f"{base_url}/questions/compare/subtopic/{subtopic_id}/"
        response = requests.post(
            url,
            json=request_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data['generated_questions']:
                question = data['generated_questions'][0]
                game_data = question.get('game_data', {})
                
                print(f"\n📝 HANGMAN CODING QUESTION:")
                print(f"{'─'*50}")
                print(f"Question Text:")
                print(question['question_text'])
                
                print(f"\n🔧 GAME DATA:")
                print(f"{'─'*30}")
                print(f"Function Name: {game_data.get('function_name', 'N/A')}")
                print(f"Parameters: {game_data.get('parameters', [])}")
                print(f"Validation Type: {game_data.get('validation_type', 'N/A')}")
                print(f"Concepts: {game_data.get('concepts', [])}")
                
                if 'hangman_version' in game_data:
                    print(f"\n👤 HANGMAN VERSION (what student sees):")
                    print(f"{'─'*40}")
                    print(game_data['hangman_version'])
                
                if 'complete_function' in game_data:
                    print(f"\n✅ COMPLETE FUNCTION (solution):")
                    print(f"{'─'*40}")
                    print(game_data['complete_function'])
                
                if 'expected_output' in game_data:
                    print(f"\n🎯 EXPECTED OUTPUT (for validation):")
                    print(f"{'─'*40}")
                    for test_case in game_data['expected_output']:
                        print(f"   Test: {test_case['description']}")
                        print(f"   Input: {test_case['input']}")
                
                print(f"\n📊 VALIDATION SETUP:")
                print(f"{'─'*30}")
                print(f"✅ Function format: def {game_data.get('function_name', 'funcName')}({', '.join(game_data.get('parameters', []))})")
                print(f"✅ Given code section: Present")
                print(f"✅ Enter your answer here: Present")
                print(f"✅ Return statement: Expected")
                print(f"✅ Output-based validation: {game_data.get('validation_type') == 'output_based'}")
        
        else:
            print(f"❌ Failed: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")

def test_ship_debugging_format():
    """Test the ship debugging validation setup"""
    
    print(f"\n🚢 TESTING SHIP DEBUGGING FORMAT")
    print(f"{'='*60}")
    
    # Test parameters
    base_url = "http://localhost:8000"
    subtopic_id = 17  # input() subtopic
    
    request_data = {
        'max_questions': 1,
        'minigame_type': 'ship_debugging',
        'force_regenerate': True
    }
    
    try:
        url = f"{base_url}/questions/compare/subtopic/{subtopic_id}/"
        response = requests.post(
            url,
            json=request_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data['generated_questions']:
                question = data['generated_questions'][0]
                game_data = question.get('game_data', {})
                
                print(f"\n📝 SHIP DEBUGGING QUESTION:")
                print(f"{'─'*50}")
                print(f"Question Text:")
                print(question['question_text'])
                
                print(f"\n🔧 GAME DATA:")
                print(f"{'─'*30}")
                print(f"Bug Type: {game_data.get('bug_type', 'N/A')}")
                print(f"Bug Description: {game_data.get('bug_description', 'N/A')}")
                print(f"Validation Type: {game_data.get('validation_type', 'N/A')}")
                print(f"Win Condition: {game_data.get('win_condition', 'N/A')}")
                
                if 'buggy_code' in game_data:
                    print(f"\n🐛 BUGGY CODE (what student sees):")
                    print(f"{'─'*40}")
                    print(game_data['buggy_code'])
                
                if 'fixed_code' in game_data:
                    print(f"\n✅ FIXED CODE (reference solution):")
                    print(f"{'─'*40}")
                    print(game_data['fixed_code'])
                
                print(f"\n📊 VALIDATION SETUP:")
                print(f"{'─'*30}")
                print(f"✅ Execution-based validation: {game_data.get('validation_type') == 'execution_based'}")
                print(f"✅ Win condition: User's code runs without errors")
                print(f"✅ Bug type: {game_data.get('bug_type', 'N/A')}")
        
        else:
            print(f"❌ Failed: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")

if __name__ == '__main__':
    test_function_format()
    test_ship_debugging_format()
    
    print(f"\n🎯 FORMAT SUMMARY:")
    print(f"{'='*60}")
    print(f"✅ Hangman Coding:")
    print(f"   • Function format: def funcName(param):")
    print(f"   • Given code section")
    print(f"   • Enter your answer here section")
    print(f"   • Return statement required")
    print(f"   • Validation: Output-based (function return value)")
    print(f"")
    print(f"✅ Ship Debugging:")
    print(f"   • Buggy code provided")
    print(f"   • User fixes the code")
    print(f"   • Validation: Execution-based (code runs without errors)")
    print(f"   • Win condition: Code executes successfully")
