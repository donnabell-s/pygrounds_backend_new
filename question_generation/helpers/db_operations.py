"""
Database operations for saving generated questions to the Django ORM.
Handles question creation, validation, and batch operations with proper deduplication.
"""

from django.db import transaction
from typing import List, Dict, Any, Optional, Tuple


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
    from ..helpers.question_processing import generate_question_hash
    
    saved_questions = []
    duplicate_questions = []
    primary_subtopic = subtopic_combination[0]  # Use first subtopic as primary for DB relations
    
    with transaction.atomic():
        for q in questions_json:
            try:
                # Extract core question data
                question_text = q.get('question_text') or q.get('question', '')
                
                # DEDUPLICATION CHECK
                if thread_manager:
                    question_hash = generate_question_hash(question_text, subtopic_combination, game_type)
                    is_unique = thread_manager.check_and_add_question_hash(question_hash)
                    
                    if not is_unique:
                        duplicate_questions.append({
                            'question_text': question_text[:100] + "...",
                            'hash': question_hash,
                            'subtopic_combination': [s.name for s in subtopic_combination],
                            'difficulty': difficulty,
                            'reason': 'duplicate_detected'
                        })
                        continue  # Skip duplicate question
                
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
                    difficulty=difficulty,
                    game_type=game_type,
                    rag_context=rag_context[:2000] if rag_context else '',  # Truncate if too long
                    game_data={
                        'function_name': function_name,
                        'sample_input': sample_input,
                        'sample_output': sample_output,
                        'hidden_tests': hidden_tests,
                        'buggy_code': buggy_code,
                        'buggy_question_text': buggy_question_text,
                        'subtopic_names': [s.name for s in subtopic_combination],
                        'zone_name': zone.name,
                        'zone_order': zone.order
                    }
                )
                
                saved_questions.append(question_obj)
                
                # Append to JSON file if thread manager is available
                if thread_manager:
                    question_data = {
                        'question_text': question_text,
                        'correct_answer': correct_answer,
                        'difficulty': difficulty,
                        'subtopic_names': [s.name for s in subtopic_combination],
                        **({
                            'function_name': function_name,
                            'sample_input': sample_input,
                            'sample_output': sample_output,
                            'hidden_tests': hidden_tests,
                            'buggy_code': buggy_code,
                            'buggy_question_text': buggy_question_text,
                        } if game_type == 'coding' else {
                            'answer': correct_answer
                        })
                    }
                    
                    thread_manager.append_question_to_json(question_data)
                
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
