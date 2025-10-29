"""
Database operations for saving generated questions to the Django ORM.
Handles question creation, validation, and batch operations with JSON export.
"""

import json
import os
from datetime import datetime
from django.db import transaction
from typing import List, Dict, Any, Optional, Tuple


def export_question_to_json(question_obj, game_type: str):
    """
    Export a single question to the appropriate JSON file in question_outputs folder.
    Uses a single file per game type with session timestamp.
    
    Args:
        question_obj: GeneratedQuestion instance
        game_type: 'coding' or 'non_coding'
    """
    try:
        # Create question_outputs directory if it doesn't exist
        output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'question_outputs')
        os.makedirs(output_dir, exist_ok=True)
        
        # Use a simple filename format - one file per game type per session
        # We'll create/reuse files with today's date
        date_str = datetime.now().strftime("%Y%m%d")
        
        # Find the most recent file for this game type and date, or create a new one
        pattern = f"{game_type}_{date_str}_*.json"
        import glob
        existing_files = glob.glob(os.path.join(output_dir, pattern))
        
        if existing_files:
            # Use the most recent file
            filepath = max(existing_files, key=os.path.getctime)
        else:
            # Create a new file with current timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{game_type}_{timestamp}.json"
            filepath = os.path.join(output_dir, filename)
        
        # Prepare question data for JSON export
        question_data = {
            'id': question_obj.id,
            'question_text': question_obj.question_text,
            'correct_answer': question_obj.correct_answer,
            'game_type': question_obj.game_type,
            'difficulty': question_obj.estimated_difficulty,
            'topic': question_obj.topic.name if question_obj.topic else None,
            'subtopic': question_obj.subtopic.name if question_obj.subtopic else None,
            'game_data': question_obj.game_data,
            'created_at': question_obj.created_at.isoformat() if hasattr(question_obj, 'created_at') else None
        }
        
        # Check if file exists, if not create with empty array
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=2)
        
        # Read existing data
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            existing_data = []
        
        # Append new question
        existing_data.append(question_data)
        
        # Write back to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        print(f"Failed to export question to JSON: {e}")


def export_preassessment_question_to_json(question_obj):
    """
    Export a single pre-assessment question to the JSON file in question_outputs folder.
    
    Args:
        question_obj: PreAssessmentQuestion instance
    """
    try:
        # Create question_outputs directory if it doesn't exist
        output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'question_outputs')
        os.makedirs(output_dir, exist_ok=True)
        
        # Use a simple filename format for pre-assessment questions
        date_str = datetime.now().strftime("%Y%m%d")
        
        # Find the most recent pre-assessment file for this date, or create a new one
        pattern = f"pre_assessment_{date_str}_*.json"
        import glob
        existing_files = glob.glob(os.path.join(output_dir, pattern))
        
        if existing_files:
            # Use the most recent file
            filepath = max(existing_files, key=os.path.getctime)
        else:
            # Create a new file with current timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pre_assessment_{timestamp}.json"
            filepath = os.path.join(output_dir, filename)
        
        # Prepare question data for JSON export
        question_data = {
            'id': question_obj.id,
            'question_text': question_obj.question_text,
            'answer_options': question_obj.answer_options,
            'correct_answer': question_obj.correct_answer,
            'estimated_difficulty': question_obj.estimated_difficulty,
            'topic_ids': question_obj.topic_ids,
            'subtopic_ids': question_obj.subtopic_ids,
            'order': question_obj.order,
            'created_at': question_obj.created_at.isoformat() if hasattr(question_obj, 'created_at') else None
        }
        
        # Check if file exists, if not create with empty array
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=2)
        
        # Read existing data
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            existing_data = []
        
        # Append new question
        existing_data.append(question_data)
        
        # Write back to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        print(f"Failed to export pre-assessment question to JSON: {e}")


def save_minigame_questions_to_db_enhanced(questions_json: List[Dict[str, Any]], 
                                         subtopic_combination, 
                                         difficulty: str, 
                                         game_type: str, 
                                         rag_context: str, 
                                         zone, 
                                         thread_manager=None) -> Tuple[List, List]:
    """
    Enhanced save function that handles both coding and non-coding questions with proper field mapping.
    Includes deduplication and JSON export functionality.
    
    Args:
        questions_json: List of question dictionaries from LLM
        subtopic_combination: List/queryset of subtopics
        difficulty: Difficulty level
        game_type: 'coding' or 'non_coding'
        rag_context: RAG context used for generation
        zone: GameZone instance
        thread_manager: Optional thread manager for deduplication
        
    Returns:
        Tuple of (saved_questions, duplicate_questions)
    """
    from question_generation.models import GeneratedQuestion
    
    saved_questions = []
    duplicate_questions = []
    primary_subtopic = subtopic_combination[0]  # Use first subtopic as primary for DB relations
    
    with transaction.atomic():
        for q in questions_json:
            try:
                # Extract core question data
                question_text = q.get('question_text') or q.get('question', '')
                
                # Skip deduplication for now since we removed the threading manager
                # TODO: Implement simple deduplication if needed
                
                # Prepare data based on game type
                if game_type == 'coding':
                    # For coding questions, extract the correct answer and coding-specific fields
                    correct_answer = q.get('correct_answer', '')  # The working code solution
                    
                    # Extract coding-specific fields for game_data
                    function_name = q.get('function_name', '')
                    sample_input = q.get('sample_input', '')
                    sample_output = q.get('sample_output', '')
                    hidden_tests = q.get('hidden_tests', [])
                    buggy_code = q.get('buggy_code', '')
                    
                    # NEW: Extract buggy question text
                    buggy_question_text = q.get('buggy_question_text', '')
                    
                else:  # non_coding
                    # For non-coding, use simple answer format
                    correct_answer = q.get('answer', '')
                    
                    # Set empty coding fields for consistency
                    function_name = ''
                    sample_input = ''
                    sample_output = ''
                    hidden_tests = []
                    buggy_code = ''
                    buggy_question_text = ''  # Only for coding questions
                
                # Create GeneratedQuestion object
                question_obj = GeneratedQuestion.objects.create(
                    question_text=question_text,
                    correct_answer=correct_answer,
                    subtopic=primary_subtopic,  # Primary subtopic for DB relation
                    topic=primary_subtopic.topic,  # Add topic field
                    estimated_difficulty=difficulty,  # Use correct field name
                    game_type=game_type,
                    game_data={
                        'function_name': function_name,
                        'sample_input': sample_input,
                        'sample_output': sample_output,
                        'hidden_tests': hidden_tests,
                        'buggy_code': buggy_code,
                        'buggy_question_text': buggy_question_text,
                        'subtopic_names': [s.name for s in subtopic_combination],
                        'zone_name': zone.name,
                        'zone_order': zone.order,
                        'rag_context': rag_context[:2000] if rag_context else ''  # Store RAG context in game_data
                    }
                )
                
                saved_questions.append(question_obj)
                
                # Generate JSON output for question_outputs folder
                try:
                    export_question_to_json(question_obj, game_type)
                except Exception as json_error:
                    print(f"Warning: Failed to export question to JSON: {json_error}")
                
            except Exception as e:
                print(f"❌ Error saving question: {str(e)}")
                print(f"   Question text: {q.get('question_text', 'N/A')[:100]}...")
                duplicate_questions.append({
                    'question_text': q.get('question_text', 'N/A')[:100] + "...",
                    'error': str(e),
                    'subtopic_combination': [s.name for s in subtopic_combination],
                    'difficulty': difficulty,
                    'reason': 'save_error'
                })
    
    return saved_questions, duplicate_questions


def save_questions_batch(questions_data: List[Dict[str, Any]], 
                        subtopic, 
                        game_type: str, 
                        difficulty: str) -> List:
    """
    Save a batch of questions to the database (simplified version).
    
    Args:
        questions_data: List of question dictionaries
        subtopic: Subtopic instance
        game_type: 'coding' or 'non_coding'
        difficulty: Difficulty level
        
    Returns:
        List of saved GeneratedQuestion objects
    """
    from question_generation.models import GeneratedQuestion
    
    saved_questions = []
    
    with transaction.atomic():
        for q_data in questions_data:
            try:
                question_obj = GeneratedQuestion.objects.create(
                    question_text=q_data.get('question_text', ''),
                    correct_answer=q_data.get('correct_answer', ''),
                    subtopic=subtopic,
                    difficulty=difficulty,
                    game_type=game_type,
                    rag_context=q_data.get('rag_context', ''),
                    game_data=q_data.get('game_data', {})
                )
                saved_questions.append(question_obj)
                
            except Exception as e:
                print(f"❌ Error saving question in batch: {str(e)}")
    
    return saved_questions


def get_existing_questions_count(subtopic=None, game_type: str = None, difficulty: str = None) -> int:
    """
    Get count of existing questions with optional filters.
    
    Args:
        subtopic: Optional subtopic filter
        game_type: Optional game type filter
        difficulty: Optional difficulty filter
        
    Returns:
        Count of matching questions
    """
    from question_generation.models import GeneratedQuestion
    
    queryset = GeneratedQuestion.objects.all()
    
    if subtopic:
        queryset = queryset.filter(subtopic=subtopic)
    if game_type:
        queryset = queryset.filter(game_type=game_type)
    if difficulty:
        queryset = queryset.filter(difficulty=difficulty)
        
    return queryset.count()


def delete_questions_by_criteria(subtopic=None, game_type: str = None, difficulty: str = None) -> int:
    """
    Delete questions matching given criteria.
    
    Args:
        subtopic: Optional subtopic filter
        game_type: Optional game type filter
        difficulty: Optional difficulty filter
        
    Returns:
        Number of deleted questions
    """
    from question_generation.models import GeneratedQuestion
    
    queryset = GeneratedQuestion.objects.all()
    
    if subtopic:
        queryset = queryset.filter(subtopic=subtopic)
    if game_type:
        queryset = queryset.filter(game_type=game_type)
    if difficulty:
        queryset = queryset.filter(difficulty=difficulty)
    
    count = queryset.count()
    queryset.delete()
    
    return count
