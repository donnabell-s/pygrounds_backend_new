"""
File operations for question generation JSON exports.
Handles initialization, writing, and finalization of generation result files.
"""

import json
import os
from datetime import datetime


def initialize_generation_json_file(game_type):
    """
    Initialize JSON file for tracking generated questions.
    
    Args:
        game_type: 'coding' or 'non_coding'
        
    Returns:
        tuple: (filepath, filename) or (None, None) if failed
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{game_type}_{timestamp}.json"
        
        # Ensure question_outputs directory exists
        output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'question_outputs')
        os.makedirs(output_dir, exist_ok=True)
        
        filepath = os.path.join(output_dir, filename)
        
        # Initialize JSON structure
        initial_data = {
            'generation_info': {
                'timestamp': timestamp,
                'game_type': game_type,
                'status': 'in_progress'
            },
            'questions': []
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, indent=2, ensure_ascii=False)
        
        print(f"📁 Initialized JSON file: {filename}")
        return filepath, filename
        
    except Exception as e:
        print(f"⚠️ Failed to initialize JSON file: {str(e)}")
        return None, None


def finalize_generation_json_file(filepath, stats):
    """
    Finalize JSON file with generation statistics.
    
    Args:
        filepath: Path to the JSON file
        stats: Dictionary of generation statistics
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Update generation info with final stats
        data['generation_info'].update({
            'status': 'completed',
            'completion_time': datetime.now().strftime("%Y%m%d_%H%M%S"),
            'statistics': stats
        })
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Finalized JSON file with {stats.get('unique_questions', 0)} unique questions")
        return True
        
    except Exception as e:
        print(f"⚠️ Failed to finalize JSON: {str(e)}")
        return False


def load_generation_results(filepath):
    """
    Load generation results from JSON file.
    
    Args:
        filepath: Path to the JSON file
        
    Returns:
        dict: Generation data or None if failed
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to load JSON: {str(e)}")
        return None


def append_question_batch_to_json(filepath, questions_batch):
    """
    Append a batch of questions to JSON file (thread-safe alternative).
    
    Args:
        filepath: Path to the JSON file
        questions_batch: List of question dictionaries
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        data['questions'].extend(questions_batch)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return True
        
    except Exception as e:
        print(f"⚠️ Failed to append questions batch: {str(e)}")
        return False
