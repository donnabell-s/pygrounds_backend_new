# db save + json export helpers

import json
import os
from datetime import datetime
from django.db import transaction
from typing import List, Dict, Any, Optional, Tuple
from .question_processing import generate_question_hash, check_question_similarity

# cross-platform file locking
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    # windows doesn't have fcntl; use an alternative approach
    import msvcrt
    HAS_FCNTL = False


def write_json_safely(filepath: str, data: list, question_type: str = "question"):
    # cross-platform json append with disk sync
    try:
        if HAS_FCNTL:
            # unix/linux/mac: use fcntl
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
            # windows: use simple file ops with retry
            for attempt in range(3):
                try:
                    # read existing data
                    if os.path.exists(filepath):
                        with open(filepath, 'r', encoding='utf-8') as f:
                            try:
                                existing_data = json.load(f)
                            except (json.JSONDecodeError, ValueError):
                                existing_data = []
                    else:
                        existing_data = []
                    
                    # append new data
                    existing_data.extend(data if isinstance(data, list) else [data])
                    
                    # write atomically using a temp file
                    import tempfile
                    temp_path = filepath + '.tmp'
                    with open(temp_path, 'w', encoding='utf-8') as f:
                        json.dump(existing_data, f, indent=2, ensure_ascii=False)
                        f.flush()
                        os.fsync(f.fileno())
                    
                    # atomic move (windows)
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
        print(f"Error in write_json_safely: {e}")
        raise


def export_question_to_json(question_obj, game_type: str):
    # append a saved question to question_outputs/*.json
    try:
        # create question_outputs directory if it doesn't exist
        output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'question_outputs')
        os.makedirs(output_dir, exist_ok=True)
        
        # create session-based filename that persists during generation
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{game_type}_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        # for session continuity, check for a recent file (within last hour)
        import glob
        import time
        pattern = f"{game_type}_*.json"
        existing_files = glob.glob(os.path.join(output_dir, pattern))
        
        # find the most recent file that's less than 1 hour old
        current_time = time.time()
        recent_file = None
        for existing_file in existing_files:
            file_time = os.path.getctime(existing_file)
            if (current_time - file_time) < 3600:  # 1 hour
                if not recent_file or file_time > os.path.getctime(recent_file):
                    recent_file = existing_file
        
        if recent_file:
            filepath = recent_file
        
        # prepare enhanced question data for json export with different structures for coding vs non-coding
        if game_type == 'non_coding':
            # for non-coding questions, only include essential game_data to reduce redundancy
            minimal_game_data = {
                'explanation': question_obj.game_data.get('explanation', '') if question_obj.game_data else '',
                'generation_timestamp': question_obj.game_data.get('generation_timestamp', '') if question_obj.game_data else datetime.now().isoformat()
            }
        else:
            # for coding questions, organize into grouped structure and remove redundant fields
            game_data = question_obj.game_data if question_obj.game_data else {}
            
            # group normal coding fields together
            normal_version = {
                'question_text': question_obj.question_text,
                'function_name': game_data.get('function_name', ''),
                'sample_input': game_data.get('sample_input', ''),
                'sample_output': game_data.get('sample_output', ''),
                'hidden_tests': game_data.get('hidden_tests', []),
                'correct_code': game_data.get('correct_code', ''),
                'explanation': game_data.get('explanation', '')
            }
            
            # group buggy version fields together
            buggy_version = {
                'buggy_question_text': game_data.get('buggy_question_text', ''),
                'buggy_code': game_data.get('buggy_code', ''),
                'buggy_correct_code': game_data.get('buggy_correct_code', ''),
                'buggy_code_explanation': game_data.get('buggy_code_explanation', '')
            }
            
            # clean game_data with organized structure
            minimal_game_data = {
                'normal': normal_version,
                'buggy': buggy_version,
                'generation_timestamp': game_data.get('generation_timestamp', datetime.now().isoformat())
            }
        
        # create different structures for coding vs non-coding questions
        if game_type == 'coding':
            # for coding questions, use organized structure without redundant fields
            question_data = {
                'game_type': question_obj.game_type,
                'difficulty': question_obj.estimated_difficulty,
                'subtopic': question_obj.subtopic.name if question_obj.subtopic else None,
                'game_data': minimal_game_data,
                'created_at': question_obj.created_at.isoformat() if hasattr(question_obj, 'created_at') and question_obj.created_at else datetime.now().isoformat(),
                'exported_at': datetime.now().isoformat()
            }
        else:
            # for non-coding questions, keep the simple structure
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
        
        # initialize file if it doesn't exist
        if not os.path.exists(filepath):
            print(f"Creating new {game_type} questions file: {os.path.basename(filepath)}")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=2)
        
        # use cross-platform safe json writing
        total_questions = write_json_safely(filepath, question_data, game_type)
        print(f"{game_type.upper()} question exported (#{total_questions}): {question_obj.question_text[:50]}...")
            
    except Exception as e:
        print(f"Failed to export {game_type} question to JSON: {e}")
        import traceback
        print(traceback.format_exc())


def export_preassessment_question_to_json(question_obj):
    # append a pre-assessment question to question_outputs/*.json
    try:
        # create question_outputs directory if it doesn't exist
        output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'question_outputs')
        os.makedirs(output_dir, exist_ok=True)
        
        # use a simple filename format for pre-assessment questions
        date_str = datetime.now().strftime("%Y%m%d")
        
        # find the most recent pre-assessment file for this date, or create a new one
        pattern = f"pre_assessment_{date_str}_*.json"
        import glob
        existing_files = glob.glob(os.path.join(output_dir, pattern))
        
        if existing_files:
            # use the most recent file
            filepath = max(existing_files, key=os.path.getctime)
        else:
            # create a new file with current timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pre_assessment_{timestamp}.json"
            filepath = os.path.join(output_dir, filename)
        
        # prepare question data for json export
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
        
        # create file if it doesn't exist
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=2)
        
        # read existing data
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            existing_data = []
        
        # append new question
        existing_data.append(question_data)
        
        # write back to file
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
                                         thread_manager=None,
                                         max_to_save: Optional[int] = None) -> Tuple[List, List]:
    # persist questions with dedupe + json export
    from question_generation.models import GeneratedQuestion
    
    # extract subtopic names and ids for deduplication
    subtopic_names = [s.name for s in subtopic_combination]
    subtopic_ids = [s.id for s in subtopic_combination]
    
    saved_questions = []
    duplicate_questions = []
    primary_subtopic = subtopic_combination[0]  # use first subtopic as primary for db relations
    
    with transaction.atomic():
        # if max_to_save is provided, only persist up to that many items
        to_save_iter = questions_json[:max_to_save] if max_to_save is not None else questions_json

        for q in to_save_iter:
            try:
                # extract core question data
                question_text = q.get('question_text') or q.get('question', '')

                # generate question hash for deduplication
                question_hash = generate_question_hash(question_text, subtopic_combination, game_type)

                # check for existing question with same hash
                existing_question = GeneratedQuestion.objects.filter(
                    game_data__question_hash=question_hash
                ).first()

                if existing_question:
                    print(f"Duplicate question detected (hash: {question_hash[:8]}...), skipping")
                    duplicate_questions.append({
                        'question_text': question_text[:100] + "...",
                        'hash': question_hash,
                        'existing_id': existing_question.id,
                        'subtopic_combination': subtopic_names,
                        'difficulty': difficulty,
                        'reason': 'duplicate_hash'
                    })
                    continue

                # similarity check: look for very similar questions in the same subtopic/difficulty
                similar_questions = GeneratedQuestion.objects.filter(
                    subtopic__in=subtopic_combination,
                    estimated_difficulty=difficulty,
                    game_type=game_type
                ).exclude(id__in=[q.id for q in saved_questions])  # Don't check against questions we just saved

                for similar_q in similar_questions:
                    # simple similarity check for near-duplicates
                    if check_question_similarity(question_text, similar_q.question_text):
                        print(f"Similar question detected, skipping (similar to ID: {similar_q.id})")
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
                    # prepare data based on game type
                    if game_type == 'coding':
                        # for coding questions, extract the correct answer and coding-specific fields
                        # `GeneratedQuestion.correct_answer` is legacy; for coding it should mirror `correct_code`.
                        correct_answer = (q.get('correct_code') or q.get('correct_answer', ''))
                        
                        # extract coding-specific fields for game_data
                        function_name = q.get('function_name', '')
                        sample_input = q.get('sample_input', '')
                        sample_output = q.get('sample_output', '')
                        hidden_tests = q.get('hidden_tests', [])
                        buggy_code = q.get('buggy_code', '')
                        
                        # extract all required coding fields from prompt
                        buggy_question_text = q.get('buggy_question_text', '')
                        correct_code = q.get('correct_code', '')
                        buggy_correct_code = q.get('buggy_correct_code', '')
                        buggy_code_explanation = q.get('buggy_code_explanation') or q.get('buggy_explanation', '')
                        
                        # extract explanation fields
                        explanation = q.get('explanation', '')
                        buggy_explanation = q.get('buggy_explanation', '')
                        
                    else:  # non_coding
                        # for non-coding, use simple answer format
                        correct_answer = q.get('answer', '')
                        
                        # extract explanation field for non-coding questions
                        explanation = q.get('explanation', '')
                        
                        # set empty coding fields for consistency
                        function_name = ''
                        sample_input = ''
                        sample_output = ''
                        hidden_tests = []
                        buggy_code = ''
                        buggy_question_text = ''  # Only for coding questions
                        correct_code = ''
                        buggy_correct_code = ''
                        buggy_code_explanation = ''
                        buggy_explanation = ''  # Only for coding questions
                    
                    # create GeneratedQuestion object
                    question_obj = GeneratedQuestion.objects.create(
                        question_text=question_text,
                        correct_answer=correct_answer,
                        subtopic=primary_subtopic,  # primary subtopic for db relation
                        topic=primary_subtopic.topic,  # add topic field
                        estimated_difficulty=difficulty,  # use correct field name
                        game_type=game_type,
                        game_data={
                            # core game data
                            'question_hash': question_hash,  # add hash for deduplication
                            'function_name': function_name,
                            'sample_input': sample_input,
                            'sample_output': sample_output,
                            'hidden_tests': hidden_tests,
                            'buggy_code': buggy_code,
                            'buggy_question_text': buggy_question_text,
                            'correct_code': correct_code,
                            'buggy_correct_code': buggy_correct_code,
                            'buggy_code_explanation': buggy_code_explanation,
                            
                            # explanation fields
                            'explanation': explanation,
                            'buggy_explanation': buggy_explanation,
                            
                            'subtopic_names': subtopic_names,
                            'subtopic_ids': subtopic_ids,
                            'zone_name': zone.name,
                            'zone_order': zone.order,
                            'rag_context': rag_context[:2000] if rag_context else ''  # store rag context in game_data
                        }
                    )
                    
                    saved_questions.append(question_obj)
                
                # generate json output for question_outputs folder
                try:
                    export_question_to_json(question_obj, game_type)
                except Exception as json_error:
                    print(f"Warning: Failed to export question to JSON: {json_error}")
                
            except Exception as e:
                print(f"Error saving question: {str(e)}")
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
    # simplified batch save
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
                print(f"Error saving question in batch: {str(e)}")
    
    return saved_questions


def get_existing_questions_count(subtopic=None, game_type: str = None, difficulty: str = None) -> int:
    # count existing questions with optional filters
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
    # delete questions matching criteria
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
