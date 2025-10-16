"""
Database operations for saving generated questions to the Django ORM.
Handles question creation, validation, and batch operations with JSON export.
"""

import json
import os
from datetime import datetime
from django.db import transaction
from typing import List, Dict, Any, Optional, Tuple
from .question_processing import generate_question_hash, check_question_similarity

# Cross-platform file locking
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    # Windows doesn't have fcntl, use alternative approach
    import msvcrt
    HAS_FCNTL = False

def write_json_safely(filepath: str, data: list, question_type: str = "question"):
    """
    Cross-platform safe JSON file writing with immediate disk sync.
    
    Args:
        filepath: Path to JSON file
        data: List of data to write
        question_type: Type of question for logging
    """
    try:
        if HAS_FCNTL:
            # Unix/Linux/Mac - use fcntl
            with open(filepath, 'r+', encoding='utf-8') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                
                try:
                    f.seek(0)
                    existing_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    existing_data = []
                
                existing_data.extend(data if isinstance(data, list) else [data])
                
                f.seek(0)
                f.truncate()
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
                
                return len(existing_data)
        else:
            # Windows - use simple file operations with retry
            for attempt in range(3):
                try:
                    # Read existing data
                    if os.path.exists(filepath):
                        with open(filepath, 'r', encoding='utf-8') as f:
                            try:
                                existing_data = json.load(f)
                            except (json.JSONDecodeError, ValueError):
                                existing_data = []
                    else:
                        existing_data = []
                    
                    # Append new data
                    existing_data.extend(data if isinstance(data, list) else [data])
                    
                    # Write atomically using temp file
                    import tempfile
                    temp_path = filepath + '.tmp'
                    with open(temp_path, 'w', encoding='utf-8') as f:
                        json.dump(existing_data, f, indent=2, ensure_ascii=False)
                        f.flush()
                        os.fsync(f.fileno())
                    
                    # Atomic move (Windows)
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    os.rename(temp_path, filepath)
                    
                    return len(existing_data)
                    
                except (IOError, OSError) as e:
                    if attempt == 2:  # Last attempt
                        raise
                    import time
                    time.sleep(0.1)  # Brief delay before retry
                    
    except Exception as e:
        print(f"❌ Error in write_json_safely: {e}")
        raise


def export_question_to_json(question_obj, game_type: str):
    """
    Export a single question to the appropriate JSON file in question_outputs folder.
    Real-time appending with immediate file updates for live progress tracking.
    
    Args:
        question_obj: GeneratedQuestion instance
        game_type: 'coding' or 'non_coding'
    """
    try:
        # Create question_outputs directory if it doesn't exist
        output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'question_outputs')
        os.makedirs(output_dir, exist_ok=True)
        
        # Create session-based filename that persists during generation
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{game_type}_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        # For session continuity, check if there's a recent file (within last hour)
        import glob
        import time
        pattern = f"{game_type}_*.json"
        existing_files = glob.glob(os.path.join(output_dir, pattern))
        
        # Find the most recent file that's less than 1 hour old
        current_time = time.time()
        recent_file = None
        for existing_file in existing_files:
            file_time = os.path.getctime(existing_file)
            if (current_time - file_time) < 3600:  # 1 hour
                if not recent_file or file_time > os.path.getctime(recent_file):
                    recent_file = existing_file
        
        if recent_file:
            filepath = recent_file
        
        # Prepare enhanced question data for JSON export with different structures for coding vs non-coding
        if game_type == 'non_coding':
            # For non-coding questions, only include essential game_data to reduce redundancy
            minimal_game_data = {
                'explanation': question_obj.game_data.get('explanation', '') if question_obj.game_data else '',
                'generation_timestamp': question_obj.game_data.get('generation_timestamp', '') if question_obj.game_data else datetime.now().isoformat()
            }
        else:
            # For coding questions, organize into grouped structure and remove redundant fields
            game_data = question_obj.game_data if question_obj.game_data else {}
            
            # Group normal coding fields together
            normal_version = {
                'question_text': question_obj.question_text,
                'function_name': game_data.get('function_name', ''),
                'sample_input': game_data.get('sample_input', ''),
                'sample_output': game_data.get('sample_output', ''),
                'hidden_tests': game_data.get('hidden_tests', []),
                'correct_code': game_data.get('correct_code', ''),
                'explanation': game_data.get('explanation', '')
            }
            
            # Group buggy version fields together
            buggy_version = {
                'buggy_question_text': game_data.get('buggy_question_text', ''),
                'buggy_code': game_data.get('buggy_code', ''),
                'buggy_correct_code': game_data.get('buggy_correct_code', ''),
                'buggy_explanation': game_data.get('buggy_explanation', '')
            }
            
            # Clean game_data with organized structure
            minimal_game_data = {
                'normal': normal_version,
                'buggy': buggy_version,
                'generation_timestamp': game_data.get('generation_timestamp', datetime.now().isoformat())
            }
        
        # Create different structures for coding vs non-coding questions
        if game_type == 'coding':
            # For coding questions, use organized structure without redundant fields
            question_data = {
                'game_type': question_obj.game_type,
                'difficulty': question_obj.estimated_difficulty,
                'subtopic': question_obj.subtopic.name if question_obj.subtopic else None,
                'game_data': minimal_game_data,
                'created_at': question_obj.created_at.isoformat() if hasattr(question_obj, 'created_at') and question_obj.created_at else datetime.now().isoformat(),
                'exported_at': datetime.now().isoformat()
            }
        else:
            # For non-coding questions, keep the simple structure
            question_data = {
                'question_text': question_obj.question_text,
                'correct_answer': question_obj.correct_answer,
                'game_type': question_obj.game_type,
                'difficulty': question_obj.estimated_difficulty,
                'subtopic': question_obj.subtopic.name if question_obj.subtopic else None,
                'game_data': minimal_game_data,
                'created_at': question_obj.created_at.isoformat() if hasattr(question_obj, 'created_at') and question_obj.created_at else datetime.now().isoformat(),
                'exported_at': datetime.now().isoformat()
            }
        
        # Initialize file if it doesn't exist
        if not os.path.exists(filepath):
            print(f"📝 Creating new {game_type} questions file: {os.path.basename(filepath)}")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=2)
        
        # Use cross-platform safe JSON writing
        total_questions = write_json_safely(filepath, question_data, game_type)
        print(f"✅ {game_type.upper()} question exported (#{total_questions}): {question_obj.question_text[:50]}...")
            
    except Exception as e:
        print(f"❌ Failed to export {game_type} question to JSON: {e}")
        import traceback
        print(traceback.format_exc())


def export_preassessment_question_to_json(question_obj):
    """
    Export a single pre-assessment question to the JSON file in question_outputs folder.
    Real-time appending for live progress tracking during generation.
    
    Args:
        question_obj: PreAssessmentQuestion instance
    """
    try:
        # Create question_outputs directory if it doesn't exist
        output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'question_outputs')
        os.makedirs(output_dir, exist_ok=True)
        
        # Create session-based filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"pre_assessment_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        # For session continuity, check if there's a recent pre-assessment file (within last hour)
        import glob
        import time
        pattern = f"pre_assessment_*.json"
        existing_files = glob.glob(os.path.join(output_dir, pattern))
        
        # Find the most recent file that's less than 1 hour old
        current_time = time.time()
        recent_file = None
        for existing_file in existing_files:
            file_time = os.path.getctime(existing_file)
            if (current_time - file_time) < 3600:  # 1 hour
                if not recent_file or file_time > os.path.getctime(recent_file):
                    recent_file = existing_file
        
        if recent_file:
            filepath = recent_file
            print(f"📝 Appending to existing pre-assessment file: {os.path.basename(filepath)}")
        else:
            print(f"📝 Creating new pre-assessment file: {os.path.basename(filepath)}")
        
        # Prepare enhanced question data for JSON export  
        question_data = {
            'id': question_obj.id,
            'question_text': question_obj.question_text,
            'answer_options': question_obj.answer_options,
            'correct_answer': question_obj.correct_answer,
            'estimated_difficulty': question_obj.estimated_difficulty,
            'topic_ids': question_obj.topic_ids,
            'subtopic_ids': question_obj.subtopic_ids,
            'order': question_obj.order,
            'created_at': question_obj.created_at.isoformat() if hasattr(question_obj, 'created_at') and question_obj.created_at else datetime.now().isoformat(),
            'exported_at': datetime.now().isoformat()
        }
        
        # Initialize file if it doesn't exist
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=2)
        
        # Use cross-platform safe JSON writing
        total_questions = write_json_safely(filepath, question_data, "pre-assessment")
        print(f"✅ PRE-ASSESSMENT question exported (#{total_questions}): {question_obj.question_text[:50]}...")
            
    except Exception as e:
        print(f"❌ Failed to export pre-assessment question to JSON: {e}")
        import traceback
        print(traceback.format_exc())


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
    
    # Extract all subtopic IDs for dynamic combinations
    subtopic_ids = [subtopic.id for subtopic in subtopic_combination]
    subtopic_names = [subtopic.name for subtopic in subtopic_combination]
    
    with transaction.atomic():
        for q in questions_json:
            try:
                # Extract core question data
                question_text = q.get('question_text') or q.get('question', '')
                
                # Generate question hash for deduplication
                question_hash = generate_question_hash(question_text, subtopic_combination, game_type)
                
                # Check for existing question with same hash
                existing_question = GeneratedQuestion.objects.filter(
                    game_data__question_hash=question_hash
                ).first()
                
                if existing_question:
                    print(f"⚠️ Duplicate question detected (hash: {question_hash[:8]}...), skipping")
                    duplicate_questions.append({
                        'question_text': question_text[:100] + "...",
                        'hash': question_hash,
                        'existing_id': existing_question.id,
                        'subtopic_combination': subtopic_names,
                        'difficulty': difficulty,
                        'reason': 'duplicate_hash'
                    })
                    continue
                
                # Additional similarity check: look for very similar questions in the same subtopic/difficulty
                # This catches questions that are nearly identical but not exact hash matches
                similar_questions = GeneratedQuestion.objects.filter(
                    subtopic__in=subtopic_combination,
                    estimated_difficulty=difficulty,
                    game_type=game_type
                ).exclude(id__in=[q.id for q in saved_questions])  # Don't check against questions we just saved
                
                for similar_q in similar_questions:
                    # Simple similarity check: if question texts are 80% similar in length and contain same key words
                    if check_question_similarity(question_text, similar_q.question_text):
                        print(f"⚠️ Similar question detected, skipping (similar to ID: {similar_q.id})")
                        duplicate_questions.append({
                            'question_text': question_text[:100] + "...",
                            'similar_to_id': similar_q.id,
                            'similar_to_text': similar_q.question_text[:100] + "...",
                            'subtopic_combination': subtopic_names,
                            'difficulty': difficulty,
                            'reason': 'similar_question'
                        })
                        break
                else:  # Only save if no similar questions found
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
                        correct_code = q.get('correct_code', '')
                        buggy_correct_code = q.get('buggy_correct_code', '')
                        
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
                        correct_code = ''  
                        buggy_correct_code = '' 
                        buggy_question_text = '' 
                    
                    # TEMPORARY: Log the question data instead of saving to avoid DB migration issues
                    print(f"🔍 WOULD SAVE QUESTION:")
                    print(f"   Question text: {question_text[:100]}...")
                    print(f"   Game type: {game_type}")
                    print(f"   Difficulty: {difficulty}")
                    print(f"   Primary subtopic: {primary_subtopic.name}")
                    print(f"   Subtopic combination: {subtopic_names}")
                    print(f"   Subtopic IDs: {subtopic_ids}")
                    print(f"   Cross-subtopic: {len(subtopic_combination) > 1}")
                    print(f"   Explanation: {q.get('explanation', 'N/A')[:100]}...")
                    print(f"   Buggy explanation: {q.get('buggy_explanation', 'N/A')[:100]}...")
                
                # Create GeneratedQuestion object WITHOUT subtopic_ids field (temporary)
                question_obj = GeneratedQuestion.objects.create(
                    question_text=question_text,
                    correct_answer=correct_answer,
                    subtopic=primary_subtopic,  # Primary subtopic for DB relation
                    # subtopic_ids=subtopic_ids,  # TEMPORARILY COMMENTED OUT - missing DB column
                    topic=primary_subtopic.topic,  # Add topic field
                    estimated_difficulty=difficulty,  # Use correct field name
                    game_type=game_type,
                    game_data={
                        # Core game data
                        'question_hash': question_hash,  # Add hash for deduplication
                        'function_name': function_name,
                        'sample_input': sample_input,
                        'sample_output': sample_output,
                        'hidden_tests': hidden_tests,
                        'buggy_code': buggy_code,
                        'correct_code': correct_code,
                        'buggy_correct_code': buggy_correct_code,
                        'buggy_question_text': buggy_question_text,
                        
                        # Enhanced explanation fields
                        'explanation': q.get('explanation', ''),
                        'buggy_explanation': q.get('buggy_explanation', ''),
                        
                        # Dynamic subtopic combination data (stored in game_data for now)
                        'subtopic_ids': subtopic_ids,
                        'subtopic_names': subtopic_names,
                        'subtopic_count': len(subtopic_combination),
                        'is_cross_subtopic': len(subtopic_combination) > 1,
                        
                        # Context and metadata
                        'zone_name': zone.name,
                        'zone_order': zone.order,
                        'rag_context': rag_context[:2000] if rag_context else '',
                        'generation_timestamp': datetime.now().isoformat()
                    }
                )
                
                print(f"✅ Question saved with ID: {question_obj.id} (subtopic_ids stored in game_data)")
                
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


def export_all_existing_questions_to_json():
    """
    Export all existing questions in the database to JSON files.
    Useful for regenerating JSON outputs if they weren't created during generation.
    """
    try:
        from question_generation.models import GeneratedQuestion, PreAssessmentQuestion
        
        print("🔄 Exporting all existing questions to JSON files...")
        
        # Export coding questions
        coding_questions = GeneratedQuestion.objects.filter(game_type='coding').order_by('created_at')
        print(f"📝 Found {coding_questions.count()} coding questions to export")
        
        for question in coding_questions:
            try:
                export_question_to_json(question, 'coding')
            except Exception as e:
                print(f"❌ Failed to export coding question {question.id}: {e}")
        
        # Export non-coding questions
        non_coding_questions = GeneratedQuestion.objects.filter(game_type='non_coding').order_by('created_at')
        print(f"📝 Found {non_coding_questions.count()} non-coding questions to export")
        
        for question in non_coding_questions:
            try:
                export_question_to_json(question, 'non_coding')
            except Exception as e:
                print(f"❌ Failed to export non-coding question {question.id}: {e}")
        
        # Export pre-assessment questions
        pre_assessment_questions = PreAssessmentQuestion.objects.all().order_by('created_at')
        print(f"📝 Found {pre_assessment_questions.count()} pre-assessment questions to export")
        
        for question in pre_assessment_questions:
            try:
                export_preassessment_question_to_json(question)
            except Exception as e:
                print(f"❌ Failed to export pre-assessment question {question.id}: {e}")
        
        print("✅ Finished exporting all existing questions to JSON files")
        
    except Exception as e:
        print(f"❌ Error during bulk export: {e}")
        import traceback
        print(traceback.format_exc())


def force_create_json_files():
    """
    Force create empty JSON files for coding, non-coding, and pre-assessment.
    Useful for initializing the file structure.
    """
    try:
        output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'question_outputs')
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create empty files
        for file_type in ['coding', 'non_coding', 'pre_assessment']:
            filename = f"{file_type}_{timestamp}.json"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=2)
            
            print(f"📁 Created empty {file_type} JSON file: {filename}")
        
        print("✅ All JSON files initialized")
        
    except Exception as e:
        print(f"❌ Error creating JSON files: {e}")
