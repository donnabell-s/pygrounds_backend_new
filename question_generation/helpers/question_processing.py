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


def parse_llm_json_response(llm_response: str) -> Optional[List[Dict[str, Any]]]:
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
        questions = json.loads(clean_resp)
        
        # Ensure it's a list
        if isinstance(questions, dict):
            questions = [questions]
        elif not isinstance(questions, list):
            return None
            
        return questions
        
    except json.JSONDecodeError:
        print(f"❌ JSON parse error. Response: {llm_response[:200]}...")
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
            'difficulty': question_data.get('difficulty', ''),
        }
    else:  # non_coding
        return {
            'question_text': question_data.get('question_text', ''),
            'answer': question_data.get('answer', question_data.get('correct_answer', '')),
            'difficulty': question_data.get('difficulty', ''),
        }


def validate_question_data(question_data: Dict[str, Any], game_type: str) -> bool:
    """
    Validate that question data contains required fields.
    
    Args:
        question_data: Question dictionary to validate
        game_type: 'coding' or 'non_coding'
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = ['question_text', 'difficulty']
    
    if game_type == 'coding':
        required_fields.extend(['function_name', 'sample_input', 'sample_output'])
    else:
        required_fields.append('answer')
    
    for field in required_fields:
        if not question_data.get(field):
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
