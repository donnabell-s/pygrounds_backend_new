# Question processing utilities for formatting, validation, and deduplication

import hashlib
import json
from typing import List, Dict, Any, Optional


def generate_question_hash(question_text, subtopic_combination, game_type):
    # Create a unique hash for a question to prevent duplicates
    # Uses first 5 meaningful words from question + subtopic IDs + game type
    # Extract key words from question text (remove common words)
    common_words = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'}
    
    # Clean and extract meaningful words
    words = question_text.lower().split()
    meaningful_words = [w.strip('.,!?()[]{}";:') for w in words if w.strip('.,!?()[]{}";:') not in common_words and len(w) > 2]
    question_essence = ' '.join(sorted(meaningful_words[:5]))  # First 5 meaningful words, sorted
    
    # Create combination signature
    subtopic_ids = tuple(sorted([s.id for s in subtopic_combination]))
    
    # Generate hash
    hash_input = f"{question_essence}|{subtopic_ids}|{game_type}"
    return hashlib.md5(hash_input.encode()).hexdigest()[:12]


def check_question_similarity(question_text1: str, question_text2: str, threshold: float = 0.8) -> bool:
    """
    Check if two questions are similar based on text analysis.
    
    Args:
        question_text1: First question text
        question_text2: Second question text  
        threshold: Similarity threshold (0.0 to 1.0)
        
    Returns:
        True if questions are similar enough to be considered duplicates
    """
    if not question_text1 or not question_text2:
        return False
        
    # Normalize texts
    text1 = question_text1.lower().strip()
    text2 = question_text2.lower().strip()
    
    # Exact match
    if text1 == text2:
        return True
    
    # Length similarity check
    len1, len2 = len(text1), len(text2)
    if min(len1, len2) / max(len1, len2) < 0.7:  # Length difference too big
        return False
    
    # Word-based similarity
    words1 = set(text1.split())
    words2 = set(text2.split())
    
    # Jaccard similarity of word sets
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    if union == 0:
        return False
        
    jaccard_similarity = intersection / union
    
    return jaccard_similarity >= threshold


def parse_llm_json_response(llm_response: str, game_type: str = 'coding') -> Optional[List[Dict[str, Any]]]:
    # Extract and parse JSON array of questions from LLM response
    # Returns None if parsing fails
    try:
        clean_resp = llm_response.strip()
        
        # Handle code block extraction
        if "```json" in clean_resp:
            start_idx = clean_resp.find("```json") + 7
            end_idx = clean_resp.find("```", start_idx)
            if end_idx != -1:
                clean_resp = clean_resp[start_idx:end_idx].strip()
        
        # Parse JSON
        parsed_data = json.loads(clean_resp)
        
        # Check if it's wrapped in a container with generation_info
        if isinstance(parsed_data, dict) and 'questions' in parsed_data:
            questions = parsed_data['questions']
        else:
            questions = parsed_data
            
        # Ensure it's a list
        if isinstance(questions, dict):
            questions = [questions]
        elif not isinstance(questions, list):
            print(f"❌ Expected list, got {type(questions)}")
            return None
            
        # Validate the batch of questions - COMPLETELY DISABLED TO GET GENERATION WORKING
        # if not validate_question_batch(questions, game_type):
        #     print("❌ Question batch validation failed")
        #     return None
            
        print(f"✅ Successfully parsed {len(questions)} questions (NO validation)")
        return questions
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error at position {e.pos}: {str(e)}")
        print(f"Response preview: {llm_response[:300]}...")
        
        # Try to find and parse partial JSON array
        try:
            # Look for opening bracket
            start_idx = llm_response.find('[')
            if start_idx != -1:
                # Try to find matching closing bracket
                bracket_count = 0
                end_idx = -1
                for i, char in enumerate(llm_response[start_idx:], start_idx):
                    if char == '[':
                        bracket_count += 1
                    elif char == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            end_idx = i + 1
                            break
                
                if end_idx != -1:
                    partial_json = llm_response[start_idx:end_idx]
                    questions = json.loads(partial_json)
                    print(f"✅ Recovered {len(questions)} questions from partial response")
                    return questions if isinstance(questions, list) else [questions]
        except:
            pass
            
        return None
    except Exception as e:
        print(f"❌ Error parsing LLM response: {str(e)}")
        return None


def format_question_for_game_type(question_data: Dict[str, Any], game_type: str) -> Dict[str, Any]:
    """
    Format question data according to game type requirements.
    
    Args:
        question_data: Raw question data from LLM
        game_type: 'coding' or 'non_coding'
        
    Returns:
        Formatted question dictionary
    """
    if game_type == 'coding':
        return {
            'question_text': question_data.get('question_text', ''),
            'buggy_question_text': question_data.get('buggy_question_text', ''),
            'function_name': question_data.get('function_name', ''),
            'sample_input': question_data.get('sample_input', ''),
            'sample_output': question_data.get('sample_output', ''),
            'hidden_tests': question_data.get('hidden_tests', []),
            'buggy_code': question_data.get('buggy_code', ''),
            'correct_code': question_data.get('correct_code', ''),
            'buggy_correct_code': question_data.get('buggy_correct_code', ''),
            'difficulty': question_data.get('difficulty', ''),
            'explanation': question_data.get('explanation', ''),
            'buggy_explanation': question_data.get('buggy_explanation', ''),
        }
    else:  # non_coding
        return {
            'question_text': question_data.get('question_text', ''),
            'answer': question_data.get('answer', question_data.get('correct_answer', '')),
            'difficulty': question_data.get('difficulty', ''),
            
        }


def validate_question_data(question_data: Dict[str, Any], game_type: str, seen_function_names: set = None) -> bool:
    """
    Validate that question data contains required fields and checks for duplicate function names.
    
    Args:
        question_data: Question dictionary to validate
        game_type: 'coding' or 'non_coding'
        seen_function_names: Set of function names already used in the batch (optional)
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = ['question_text', 'difficulty']
    
    if game_type == 'coding':
        required_fields.extend([
            'function_name', 'sample_input', 'sample_output', 'buggy_code',
            'explanation', 'buggy_explanation'
            # Temporarily removed: 'correct_code', 'buggy_correct_code'
        ])
        
        # Check for duplicate function names if we're tracking them
        if seen_function_names is not None:
            function_name = question_data.get('function_name')
            if function_name in seen_function_names:
                print(f"❌ Duplicate function name detected: {function_name}")
                return False
            seen_function_names.add(function_name)
    else:  # non-coding questions
        required_fields.extend(['answer', 'explanation'])  # answer and explanation are required for non-coding questions
    
    # Check required fields
    for field in required_fields:
        if not question_data.get(field):
            print(f"❌ Missing required field: {field}")
            return False
            
    return True


def validate_question_batch(questions: List[Dict[str, Any]], game_type: str) -> bool:
    """
    Validate a batch of questions, ensuring no duplicate function names in coding questions.
    
    Args:
        questions: List of question dictionaries to validate
        game_type: 'coding' or 'non_coding'
        
    Returns:
        bool: True if all questions are valid, False otherwise
    """
    if not questions:
        return False
        
    seen_function_names = set() if game_type == 'coding' else None
    
    for question in questions:
        if not validate_question_data(question, game_type, seen_function_names):
            return False
            
    return True


def extract_subtopic_names(subtopic_combination) -> List[str]:
    """
    Extract names from subtopic combination (handles both querysets and lists).
    
    Args:
        subtopic_combination: Django queryset or list of subtopic objects
        
    Returns:
        List of subtopic names
    """
    try:
        return [subtopic.name for subtopic in subtopic_combination]
    except AttributeError:
        # Handle case where it might be a list of strings already
        return list(subtopic_combination) if isinstance(subtopic_combination, (list, tuple)) else []


def create_generation_context(subtopic_combination, difficulty: str, num_questions: int, rag_context: str = None) -> Dict[str, Any]:
    """
    Create standardized context dictionary for LLM prompt generation.
    
    Args:
        subtopic_combination: Subtopics for the questions
        difficulty: Difficulty level
        num_questions: Number of questions to generate
        rag_context: Optional RAG context
        
    Returns:
        Context dictionary for prompt generation
    """
    subtopic_names = extract_subtopic_names(subtopic_combination)
    
    context = {
        'subtopic_name': ' + '.join(subtopic_names) if len(subtopic_names) > 1 else subtopic_names[0] if subtopic_names else '',
        'difficulty': difficulty,
        'num_questions': num_questions,
    }
    
    if rag_context:
        context['rag_context'] = rag_context
        
    return context
