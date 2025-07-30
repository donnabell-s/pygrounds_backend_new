"""
DeepSeek Prompt Templates for Question Generation

This module contains all prompt templates used for generating different types of questions
through the DeepSeek LLM. It provides game-type specific prompts for coding, non-coding,
and pre-assessment questions with proper JSON formatting and field specifications.
"""


class DeepSeekPromptManager:
    """Manages prompt templates for different question generation types."""
    
    def get_prompt_for_minigame(self, game_type, context):
        """Get appropriate prompt based on game type."""
        if game_type == 'coding':
            return self.get_coding_prompt(context)
        elif game_type == 'non_coding':
            return self.get_non_coding_prompt(context)
        elif game_type == 'pre_assessment':
            return self.get_pre_assessment_prompt(context)
        else:
            raise ValueError(f"Unknown game_type: {game_type}")
    
    def get_coding_prompt(self, context):
        """Generate concise, action‑packed coding challenge prompts."""
        return f"""
You are a coding challenge designer. Use the RAG context to craft tiny, action‑packed Python tasks.

CONTEXT: {context['rag_context']}
SUBTOPIC: {context['subtopic_name']}
DIFFICULTY: {context['difficulty']}

Generate exactly {context['num_questions']} challenges.

GUIDELINES:
- Keep each question_text under 12 words.
- Use verbs like Build, Fix, Transform, Calculate, Decode.
- Avoid “Write a function that…”. Instead, describe the task: e.g. “Reverse string”.
- Each object must include:
  • question_text
  • function_name
  • sample_input / sample_output
  • hidden_tests (format: "('in',),output:'out'")
  • buggy_code with a _____ placeholder
  • difficulty

Format output as a JSON array of {context['num_questions']} objects:
```json
[
  {{
    "question_text": "Reverse string → 'hello' to 'olleh'",
    "function_name": "reverse_string",
    "sample_input": "('hello',)",
    "sample_output": "'olleh'",
    "hidden_tests": ["('world',),output:'dlrow'", "('python',),output:'nohtyp'"],
    "buggy_code": "def reverse_string(s):\\n    return s[_____]",
    "difficulty": "{context['difficulty']}"
  }},
  …
]
```"""

    def get_non_coding_prompt(self, context):
        """Generate concise, concept-focused non-coding quiz prompts."""
        return f"""
You are a quiz creator for Python concepts—use the RAG context.

CONTEXT: {context['rag_context']}
SUBTOPIC: {context['subtopic_name']}
DIFFICULTY: {context['difficulty']}

Generate exactly {context['num_questions']} concept questions.

GUIDELINES:
- Focus on keywords, syntax, or behavior
- Keep answers single words or short phrases
- Use direct questions: Spot, Identify, Predict

Output a JSON array of {context['num_questions']} objects:
```json
[
  {{
    "question_text": "What keyword defines a function in Python?",
    "answer": "def",
    "difficulty": "{context['difficulty']}"
  }},
  {{
    "question_text": "Which operator checks for equality?",
    "answer": "==",
    "difficulty": "{context['difficulty']}"
  }}
]
```"""

    def get_pre_assessment_prompt(self, context):
        """Generate comprehensive pre-assessment prompts covering all topics."""
        return f"""
You are creating a comprehensive pre-assessment for Python learners.

TOPICS AND SUBTOPICS TO COVER:
{context['topics_and_subtopics']}

Generate exactly {context['num_questions']} questions that cover every listed subtopic.

REQUIREMENTS:
- Use exact subtopic names from the list in subtopics_covered
- Mix conceptual and practical questions across difficulty levels
- Ensure integrated understanding by covering multiple subtopics when possible

OUTPUT FORMAT:
Return a JSON array where each question has:
- question_text
- choices: array of 4 strings
- correct_answer: one of the choices
- subtopics_covered: list of exact names
- difficulty

Example:
```json
[
  {{
    "question_text": "What immutable sequence type uses parentheses?",
    "choices": ["list","tuple","set","dict"],
    "correct_answer": "tuple",
    "subtopics_covered": ["Tuples and Their Immutability"],
    "difficulty": "beginner"
  }}
]
```"""

# Global instance
deepseek_prompt_manager = DeepSeekPromptManager()
