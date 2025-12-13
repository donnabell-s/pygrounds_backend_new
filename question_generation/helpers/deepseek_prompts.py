# Manages prompts for different question types in DeepSeek LLM


class DeepSeekPromptManager:
    # Core prompt templates for different game types

    def get_prompt_for_minigame(self, game_type, context):
        # Route to appropriate prompt based on game type
        prompts = {
            'coding': self.get_coding_prompt,
            'non_coding': self.get_non_coding_prompt,
            'pre_assessment': self.get_pre_assessment_prompt
        }

        if game_type not in prompts:
            raise ValueError(f"Unknown game_type: {game_type}")

        return prompts[game_type](context)

    def get_coding_prompt(self, context):
        return f"""
OUTPUT ONLY VALID JSON ARRAY. NO prose, NO markdown, NO backticks.

TASK: Generate {context['num_questions']} Python DEBUGGING questions for {context['subtopic_name']} ({context['difficulty']}).

RAG_CONTEXT:
<<<
{context['rag_context']}
>>>

RULES (MUST):
- Simple, real-world tasks; no external libs; < 20 lines/code.
- snake_case function names.
- Keep texts short and specific.

ITEM SCHEMA (ALL FIELDS REQUIRED):
{{
  "question_text": "brief task (≤12 words)",
  "buggy_question_text": "visible symptom (8–20 words)",
  "explanation": "clear explanation of the main task/problem (20–40 words)",
  "buggy_explanation": "explanation of the bug and debugging approach (20–40 words)",
  "function_name": "snake_case",
  "sample_input": "(example,)",
  "sample_output": "expected",
  "hidden_tests": [{{"input": "(test,)", "expected_output": "result"}}],
  "buggy_code": "def name():\\n    # buggy version",
  "correct_code": "def name():\\n    # working solution",
  "buggy_correct_code": "def name():\\n    # fixed buggy version",
  "difficulty": "{context['difficulty']}"
}}

RETURN: JSON array ONLY.
"""

    def get_non_coding_prompt(self, context):
        return f"""
OUTPUT ONLY VALID JSON. DO NOT add explanations, markdown, or backticks.

ROLE: Python concept quiz creator.

RAG_CONTEXT (use only salient facts; ignore noise):
<<<
{context['rag_context']}
>>>

SUBTOPIC(S): {context['subtopic_name']}
DIFFICULTY: {context['difficulty']}
NUM_QUESTIONS: {context['num_questions']}

TASK:
Create {context['num_questions']} concise concept-recall items for a crossword/word-search game.

QUALITY RULES:
- Each question must target ONE **specific Python concept term** that appears or is strictly implied in RAG_CONTEXT.
- Avoid trivial universals (e.g., “write clean code”, “use comments wisely”).
- No True/False (unless concept is literally True/False/bool).
- No code blocks or symbols anywhere (letters/spaces only).
- Answers must be a **single term** (one token when split on spaces), 4–13 characters, letters only.
- Answers must be **domain-specific** (e.g., “docstring”, “idempotent”, “immutability”, “generator”), not generic (“code”, “variable”, “python”, “function”).
- Frame questions as clever, crossword-style clues.
- If multiple subtopics are present, integrate meaningfully (but still one-term answer).

AVOID THESE STEM PATTERNS:
- “What is the term for…”
- “Identify the concept that…”
- “Which keyword is used to…”

INSTEAD USE (EXAMPLES):
- “A special variable that holds multiple items.” (Answer: list)
- “The Pythonic way of iterating through a sequence.” (Answer: forloop)
- “A reusable block of code that performs a specific action.” (Answer: function)
- “The process of finding and fixing errors in code.” (Answer: debugging)

OUTPUT SCHEMA (array length = NUM_QUESTIONS):
[
  {{
    "question_text": "<short, unambiguous question (≤18 words, letters/spaces only)>",
    "answer": "<single domain term, 4–13 letters>",
    "explanation": "<brief concept note, 20–40 words, friendly and clear>",
    "difficulty": "{context['difficulty']}",
    }}
]
VALIDATION HINTS:
- If the best possible answer is too generic, choose a more specific, technical term from RAG_CONTEXT.
- Prefer concrete glossary-like targets (e.g., “docstring”, “sentinel”, “ducktyping”, “mutability”, “shortcircuit”).
- Keep JSON compact. Return only the JSON array.
"""

    def get_pre_assessment_prompt(self, context):
        return f"""
OUTPUT ONLY VALID JSON. DO NOT add explanations, markdown, or backticks.

ROLE: You are a Python Master and Educational Game Designer creating a welcoming pre-assessment for complete beginners with ZERO programming experience.

COMPREHENSIVE COVERAGE REQUIRED - ALL THESE SUBTOPICS (99 total):
<<<
{context['topics_and_subtopics']}
>>>

ASSESSMENT PURPOSE:
This is a PRE-ASSESSMENT GAME for absolute beginners to determine their starting point in Python learning. Students taking this have likely NEVER programmed before and need a friendly, non-intimidating introduction to gauge their readiness level.

TOTAL QUESTIONS: {context['num_questions']} (typically 20 for comprehensive beginner assessment)

BEGINNER-FIRST DESIGN PHILOSOPHY:
As a Python Master designing for beginners, you understand that effective pre-assessment requires:

1. **GENTLE DIFFICULTY PROGRESSION**:
   - 50% Beginner: Fundamental concepts, simple syntax recognition, basic terminology
   - 40% Intermediate: Basic application of concepts, simple problem recognition  
   - 10% Advanced: Identify students with some prior experience
   - ONLY 1 MASTER LEVEL QUESTION FOR INSPIRATION AND MOTIVATION
2. **ACCESSIBLE LANGUAGE & CONCEPTS**:
   - Use simple, clear explanations
   - Relate to everyday concepts when possible
   - Avoid jargon unless explaining it
   - Make questions feel like puzzles, not tests

3. **STRATEGIC SUBTOPIC COVERAGE**:
   - Bundle 2-4 related foundational subtopics per question
   - Focus on concepts that indicate learning readiness
   - Cover basics that determine appropriate starting difficulty


ABSOLUTE REQUIREMENTS:
- Use EXACT subtopic names from the provided list in `subtopics_covered` - DO NOT paraphrase or shorten them
- COPY the subtopic names EXACTLY as they appear in the topic list above - character for character
- Example: Use "Basic Text Output with print()" NOT "Basic Output" or "Print Statements"
- Example: Use "Using input() to Read User Data" NOT "Input Functions" or "User Input"
- Make all questions welcoming and game-like, never intimidating
- Ensure someone with zero experience can still engage meaningfully
- Cover foundational concepts that predict learning success
- All answer choices should be clearly distinct and logical

CRITICAL: The `subtopics_covered` array must contain EXACT MATCHES to the subtopic names listed in the COMPREHENSIVE COVERAGE section above. Any paraphrasing will cause database mapping failures.

OUTPUT SCHEMA:
[
  {{
    "question_text": "<clear, beginner-friendly question with simple language and relatable examples>",
    "choices": ["<simple, clear option A>", "<simple, clear option B>", "<simple, clear option C>", "<simple, clear option D>"],
    "correct_answer": "<must exactly match one choice>",
    "subtopics_covered": ["<exact subtopic name 1>", "<exact subtopic name 2>", "<exact subtopic name 3>"],
    "difficulty": "beginner|intermediate|advanced|master"
  }}
]

MANDATE: Create {context['num_questions']} welcoming, game-like questions that help complete beginners discover their Python learning readiness while efficiently covering ALL 99 subtopics.

RETURN: Only the JSON array.
"""


# Global instance
deepseek_prompt_manager = DeepSeekPromptManager()
