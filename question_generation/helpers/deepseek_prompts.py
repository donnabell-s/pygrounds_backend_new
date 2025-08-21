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
          OUTPUT ONLY VALID JSON. MUST INCLUDE ALL 10 REQUIRED FIELDS FOR EACH QUESTION.

          ROLE: Senior Python challenge architect.

          RAG_CONTEXT:
          <<<
          {context['rag_context']}
          >>>

          TOPIC: {context['subtopic_name']}
          DIFFICULTY: {context['difficulty']}
          NUM_QUESTIONS: {context['num_questions']}

          GOAL:
          Generate {context['num_questions']} compact, real-world Python debugging tasks.

          MANDATORY OUTPUT SCHEMA - MUST INCLUDE ALL 10 FIELDS:
          [
            {{
              "question_text": "<≤12 words>",
              "buggy_question_text": "<symptom-only, 8–20 words>", 
              "function_name": "<snake_case>",
              "sample_input": "<Python-literal tuple>",
              "sample_output": "<expected result>",
              "hidden_tests": [
                {{"input": "(test1,)", "expected_output": "result1"}},
                {{"input": "(test2,)", "expected_output": "result2"}}
              ],
              "buggy_code": "def function_name(...):\\n    # buggy implementation",
              "correct_code": "def function_name(...):\\n    # correct implementation for question_text",
              "buggy_correct_code": "def function_name(...):\\n    # fixed version of buggy_code",
              "difficulty": "{context['difficulty']}"
            }}
          ]

          CRITICAL FAILURE PREVENTION REQUIREMENTS:
          - Every JSON object MUST have exactly these 10 fields, with NO fields missing
          - MANDATORY: "buggy_code": Contains intentional bugs that align with buggy_question_text
          - MANDATORY: "correct_code": Working solution for the main question_text problem  
          - MANDATORY: "buggy_correct_code": Corrected version that fixes the bugs in buggy_code
          - IMPORTANT: If ANY field is missing, the entire batch will be rejected and no questions will be saved

          RULES:
          - Create engaging, simple coding tasks with real-world context
          - No external libraries, randomness, file I/O, or multi-part tasks
          - Use engaging contexts: secret messages, gamer tags, social media, etc.
          - `buggy_question_text` describes symptoms, not solutions
          - Use snake_case for function names
          - Keep code under 20 lines each

          RETURN: Only the JSON array with ALL required fields.
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
- Use action verbs in questions: Identify, Choose, Select, Spot, Predict, Name.
- If multiple subtopics are present, integrate meaningfully (but still one-term answer).

AVOID THESE STEM PATTERNS:
- “What should X avoid?”
- “Best practice for comments?”
- “Why is X important?”

INSTEAD USE:
- “Identify the term for …”
- “Select the keyword that …”
- “Name the concept describing …”
- “Spot the feature that …”

OUTPUT SCHEMA (array length = NUM_QUESTIONS):
[
  {{
    "question_text": "<short, unambiguous question (≤18 words, letters/spaces only)>",
    "answer": "<single domain term, 4–13 letters>",
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
