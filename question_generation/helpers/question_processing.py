import hashlib
import json
import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def _fix_invalid_json_escapes(text: str) -> str:
    """
    Replace bare backslashes that aren't valid JSON escape sequences.
    Valid JSON escapes: \\\\  \\"  \\/  \\b  \\f  \\n  \\r  \\t  \\uXXXX
    The LLM often emits Python code containing \\e, \\s, \\p, \\', etc.
    inside JSON string values, which makes json.loads reject the whole response.
    """
    return re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)


def generate_question_hash(question_text, subtopic_combination, game_type, difficulty=''):
    common_words = {
        'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
    }
    words = question_text.lower().split()
    meaningful = [w.strip('.,!?()[]{}";:') for w in words
                  if w.strip('.,!?()[]{}";:') not in common_words and len(w) > 2]
    question_essence = ' '.join(sorted(meaningful[:5]))
    subtopic_ids = tuple(sorted([s.id for s in subtopic_combination]))
    return hashlib.md5(f"{question_essence}|{subtopic_ids}|{game_type}|{difficulty}".encode()).hexdigest()[:12]


def check_question_similarity(question_text1: str, question_text2: str, threshold: float = 0.8) -> bool:
    if not question_text1 or not question_text2:
        return False
    text1, text2 = question_text1.lower().strip(), question_text2.lower().strip()
    if text1 == text2:
        return True
    len1, len2 = len(text1), len(text2)
    if min(len1, len2) / max(len1, len2) < 0.7:
        return False
    words1, words2 = set(text1.split()), set(text2.split())
    union = len(words1 | words2)
    if union == 0:
        return False
    return (len(words1 & words2) / union) >= threshold


def _extract_json_array(text: str):
    """Extract and parse the first complete JSON array found in text."""
    start = text.find('[')
    if start == -1:
        return None
    bracket_count = end = 0
    for i, char in enumerate(text[start:], start):
        if char == '[':
            bracket_count += 1
        elif char == ']':
            bracket_count -= 1
            if bracket_count == 0:
                end = i + 1
                break
    if not end:
        return None
    questions = json.loads(text[start:end])
    return questions if isinstance(questions, list) else [questions]


def _try_parse(text: str):
    """Parse JSON and normalise to a list."""
    parsed = json.loads(text)
    questions = parsed.get('questions', parsed) if isinstance(parsed, dict) else parsed
    if isinstance(questions, dict):
        return [questions]
    if isinstance(questions, list):
        return questions
    return None


def parse_llm_json_response(llm_response: str, game_type: str = 'coding') -> Optional[List[Dict[str, Any]]]:
    clean = llm_response.strip()
    if "```json" in clean:
        start = clean.find("```json") + 7
        end = clean.find("```", start)
        if end != -1:
            clean = clean[start:end].strip()

    # 1. Try as-is
    try:
        return _try_parse(clean)
    except json.JSONDecodeError:
        pass

    # 2. Try with invalid escape sequences fixed
    try:
        return _try_parse(_fix_invalid_json_escapes(clean))
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error at position {e.pos}: {e} — preview: {llm_response[:300]}")

    # 3. Bracket extraction (as-is, then escape-fixed)
    try:
        return _extract_json_array(clean)
    except Exception:
        pass

    try:
        return _extract_json_array(_fix_invalid_json_escapes(clean))
    except Exception:
        pass

    logger.error("All parse attempts failed")
    return None


def format_question_for_game_type(question_data: Dict[str, Any], game_type: str) -> Dict[str, Any]:
    if game_type == 'coding':
        return {
            'question_text':         question_data.get('question_text', ''),
            'buggy_question_text':   question_data.get('buggy_question_text', ''),
            'function_name':         question_data.get('function_name', ''),
            'sample_input':          question_data.get('sample_input', ''),
            'sample_output':         question_data.get('sample_output', ''),
            'hidden_tests':          question_data.get('hidden_tests', []),
            'clean_solution':        question_data.get('clean_solution') or question_data.get('correct_code', ''),
            'code_shown_to_student': question_data.get('code_shown_to_student') or question_data.get('buggy_code', ''),
            'code_with_bug_fixed':   question_data.get('code_with_bug_fixed') or question_data.get('buggy_correct_code', ''),
            'difficulty':            question_data.get('difficulty', ''),
            'explanation':           question_data.get('explanation', ''),
            'buggy_explanation':     question_data.get('buggy_explanation', ''),
        }
    else:
        return {
            'question_text': question_data.get('question_text', ''),
            'answer':        question_data.get('answer', question_data.get('correct_answer', '')),
            'difficulty':    question_data.get('difficulty', ''),
            'explanation':   question_data.get('explanation', ''),
        }


def validate_question_data(question_data: Dict[str, Any], game_type: str,
                            seen_function_names: set = None) -> bool:
    required_fields = ['question_text', 'difficulty']
    if game_type == 'coding':
        required_fields.extend([
            'buggy_question_text', 'function_name', 'sample_input', 'sample_output',
            'hidden_tests', 'clean_solution', 'code_shown_to_student', 'code_with_bug_fixed',
            'explanation', 'buggy_explanation',
        ])
        if seen_function_names is not None:
            fn = question_data.get('function_name')
            if fn in seen_function_names:
                logger.warning(f"Duplicate function name: {fn}")
                return False
            seen_function_names.add(fn)
    else:
        required_fields.extend(['answer', 'explanation'])

    for field in required_fields:
        if field not in question_data:
            logger.warning(f"Missing required field: {field}")
            return False
        value = question_data[field]
        if field == 'hidden_tests':
            if not isinstance(value, list) or not value:
                logger.warning("Invalid hidden_tests: must be a non-empty list")
                return False
            continue
        if isinstance(value, str):
            if not value.strip():
                logger.warning(f"Empty required field: {field}")
                return False
        elif value is None:
            logger.warning(f"Null required field: {field}")
            return False
    return True


def validate_question_batch(questions: List[Dict[str, Any]], game_type: str) -> bool:
    if not questions:
        return False
    seen_function_names = set() if game_type == 'coding' else None
    return all(validate_question_data(q, game_type, seen_function_names) for q in questions)


def extract_subtopic_names(subtopic_combination) -> List[str]:
    try:
        return [subtopic.name for subtopic in subtopic_combination]
    except AttributeError:
        return list(subtopic_combination) if isinstance(subtopic_combination, (list, tuple)) else []


def create_generation_context(subtopic_combination, difficulty: str, num_questions: int,
                               rag_context: str = None) -> Dict[str, Any]:
    subtopic_names = extract_subtopic_names(subtopic_combination)
    safe_name = (' + '.join(subtopic_names) if len(subtopic_names) > 1
                 else subtopic_names[0] if subtopic_names else '')
    return {
        'subtopic_name': safe_name,
        'difficulty':    difficulty,
        'num_questions': num_questions,
        'rag_context':   rag_context or 'No specific content context available. Generate questions based on general Python knowledge.',
    }
