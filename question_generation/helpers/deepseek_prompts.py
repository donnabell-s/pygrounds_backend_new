class DeepSeekPromptManager:

    def get_prompt_for_minigame(self, game_type, context):
     
        if game_type == 'coding':
            return self.get_coding_prompt(context)
        elif game_type == 'non_coding':
            return self.get_non_coding_prompt(context)
        elif game_type == 'pre_assessment':
            return self.get_pre_assessment_prompt(context)
        else:
            raise ValueError(f"Unknown game_type: {game_type}")

    def get_coding_prompt(self, context):
      return f"""
          OUTPUT ONLY VALID JSON. DO NOT add explanations, markdown, or backticks.

          ROLE: Senior Python challenge architect.

          RAG_CONTEXT (use only what is relevant; ignore the rest if noisy):
          <<<
          {context['rag_context']}
          >>>

          TOPIC: {context['subtopic_name']}
          DIFFICULTY: {context['difficulty']}
          NUM_QUESTIONS: {context['num_questions']}

          GOAL:
          Generate {context['num_questions']} compact, real-world Python debugging tasks.

          HARD RULES:
          - All questions are about **fixing a single bug** in short code.
          - No external libraries, no randomness, no file I/O, no multi-part tasks.
          - `question_text` ≤ 12 words; start with an action verb (Build, Fix, Sort, Extract, Format, Transform).
          - `buggy_question_text` **must describe symptoms** (observable behavior), not the fix, and must NOT be empty.
          - Always include `buggy_code` (≤ 20 lines).
          - The **intended correct behavior** must be inferable from `sample_input` + `sample_output`.
          - Use **snake_case** for `function_name`.
          - Hidden tests must be structured objects, not free text.

          OUTPUT SCHEMA (array of length = NUM_QUESTIONS):
          [
            {{
              "question_text": "<≤12 words>",
              "buggy_question_text": "<symptom-only, 8–20 words>",
              "function_name": "<snake_case>",
              "sample_input": "<Python-literal tuple, e.g., (3,) or ([1,2], 'x')>",
              "sample_output": "<Python-literal or newline-joined string>",
              "hidden_tests": [
                {{"input": "(2,)", "expected_output": "'2\\n1'"}},
                {{"input": "(1,)", "expected_output": "'1'"}}
              ],
              "buggy_code": "def fn(...):\\n    ...",
              "difficulty": "{context['difficulty']}"
            }}
          ]

          VALIDATION HINTS:
          - Keep total JSON under ~1200 tokens.
          - Prefer small, testable tasks (string ops, loops, indexing, conditionals, formatting).
          - Avoid trick questions and avoid relying on undefined globals.

          RETURN: Only the JSON array.
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

ROLE: Assessment designer.

COVER THESE EXACT SUBTOPICS:
<<<
{context['topics_and_subtopics']}
>>>

NUM_QUESTIONS: {context['num_questions']}

REQUIREMENTS:
- Cover every listed subtopic at least once across the set.
- Mix conceptual and practical items; keep stems clear and brief.
- Choices must be concise; one unambiguous correct answer.
- Use exact subtopic names in `subtopics_covered`.

OUTPUT SCHEMA:
[
  {{
    "question_text": "<≤20 words>",
    "choices": ["<opt1>", "<opt2>", "<opt3>", "<opt4>"],
    "correct_answer": "<must match one of choices>",
    "subtopics_covered": ["<exact subtopic name>", "..."],
    "difficulty": "beginner|intermediate|advanced"
  }}
]

RETURN: Only the JSON array.
"""


# Global instance
deepseek_prompt_manager = DeepSeekPromptManager()
