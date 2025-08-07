"""
DeepSeek Prompt Templates for Question Gen⚠️ RULES:
- ❌ Do NOT use vague phrases like "Write a function that…"
- ❌ No external libraries, randomness, or file I/O
- ❌ No multi-function or multi-step problems
- ✅ `buggy_question_text` must NEVER be empty - always describe what's wrong
- ✅ All questions involve debugging buggy code
- ✅ `buggy_question_text` should describe symptoms/behavior, not solutions

✅ REQUIRED FIELDS (ALL 6):

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
      """Generate creative, real-world, and testable Python coding challenges."""
      return f"""
You are a senior Python challenge architect. Use the RAG context below to generate compact, real-world-inspired Python tasks that develop **precise programming logic**.

📚 CONTEXT:
{context['rag_context']}

TOPIC: {context['subtopic_name']}
DIFFICULTY: {context['difficulty']}

🎯 OBJECTIVE:
Generate exactly {context['num_questions']} Python coding problems in strict **JSON format**.

Each challenge must:
- Reflect a single logical task or small bug fix
- Be realistic, focused, and clearly testable
- Include **all required fields** — no missing or null values
- Use a concise `question_text` (≤ 12 words) with action verbs like: Build, Format, Extract, Fix, Sort, Assemble, Transform in real world context

⚠️ RULES:
- Do NOT use vague phrases like “Write a function that…”
- Avoid external libraries, file I/O, randomness, or multi-part tasks
- `buggy_code` must ALWAYS be present AND THE SOLUTION MUST BE THE field `sample_output` and `sample_input`
- `buggy_question_text` must ALWAYS describe **observable behavior** (e.g., “The result is always reversed”, “Only the first name prints”) — never reveal the fix.


📦 REQUIRED FIELDS (all must be filled):
```json
[
  {{
    "question_text": "Count down from n to 1",
    "buggy_question_text": "The numbers keep getting bigger instead of smaller",
    "function_name": "countdown",
    "sample_input": "(3,)",
    "sample_output": "3\\n2\\n1",
    "hidden_tests": ["(2,),output:'2\\n1'", "(1,),output:'1'"],
    "buggy_code": "def countdown(n):\\n    while n > 0:\\n        print(n)\\n        n = n + 1",
    "difficulty": "{context['difficulty']}"
  }},
  {{
    "question_text": "Extract initials from a full name",
    "buggy_question_text": "Only the first letter shows up instead of the full name",
    "function_name": "get_initials",
    "sample_input": "('John Doe',)",
    "sample_output": "'JD'",
    "hidden_tests": ["('Alice Smith',),output:'AS'", "('Bob Marley',),output:'BM'"],
    "buggy_code": "def get_initials(name):\\n    parts = name.split()\\n    return parts[0][0]",
    "difficulty": "{context['difficulty']}"
  }},
  {{
    "question_text": "Calculate sum of positive numbers only",
    "buggy_question_text": "Negative numbers are being included in the total instead of positive numbers only",
    "function_name": "sum_positives",
    "sample_input": "([1, -2, 3, -4, 5],)",
    "sample_output": "9",
    "hidden_tests": ["([-1, -2],),output:0", "([10, -5, 15],),output:25"],
    "buggy_code": "def sum_positives(nums):\\n    total = 0\\n    for num in nums:\\n        total += num\\n    return total",
    "difficulty": "{context['difficulty']}"
  }}
]

```"""

    def get_non_coding_prompt(self, context):
          """Generate concise,unique, creative, concept-focused Python quiz prompts."""
          return f"""
      You are a Python quiz creator. Use the RAG context below to generate creative and compact concept-based questions.

      CONTEXT: {context['rag_context']}
      SUBTOPIC: {context['subtopic_name']}  # May include multiple subtopics
      DIFFICULTY: {context['difficulty']}

      TASK:
      Generate {context['num_questions']} concise quiz questions for concept recall.

      🚫 RESTRICTIONS:
      - No True/False questions (unless about `True`, `False`, or `bool`)
      - No code blocks, full code, or symbols (e.g., `==`, `+`, `:`)
      - No vague, subjective, or overly theoretical prompts

      ✅ REQUIREMENTS:
          Answers must use only letters (a–z, A–Z); no symbols or numbers
          Spaces are allowed, but total length including spaces must be ≤13 characters
          Use concept keywords or compound terms (e.g., "list comprehension", "global variable")
          If multiple subtopics are involved, combine them into an integrated concept
          Use clear action verbs in questions: Identify, Spot, Predict, Choose, Select, etc.
      🎯 GOAL:
      Test conceptual understanding across syntax and behavior — make it game-friendly (crossword/word search).

      📦 FORMAT (JSON):
      ```json
      [
        {{
          "question_text": "Which keyword exits a loop early?",
          "answer": "break",
          "difficulty": "{context['difficulty']}"
        }},
        {{
          "question_text": "What keyword sends a value from a function?",
          "answer": "return",
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
