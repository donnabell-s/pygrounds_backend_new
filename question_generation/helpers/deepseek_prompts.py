class DeepSeekPromptManager:

    def get_prompt_for_minigame(self, game_type: str, context: dict) -> str:
        prompts = {
            'coding':         self.get_coding_prompt,
            'non_coding':     self.get_non_coding_prompt,
            'pre_assessment': self.get_pre_assessment_prompt,
        }
        if game_type not in prompts:
            raise ValueError(f"Unknown game_type: {game_type}")
        return prompts[game_type](context)

    def get_coding_prompt(self, context: dict) -> str:
        return f"""
OUTPUT ONLY VALID JSON ARRAY. NO prose, NO markdown, NO backticks.

TASK: Generate {context['num_questions']} Python coding questions for {context['subtopic_name']} ({context['difficulty']}).
Each question serves TWO games: Hangman (write from scratch) and Debugging (fix a bug).

RAG_CONTEXT:
{context['rag_context']}

RULES:
- Simple real-world tasks, no external libs, under 20 lines per code block.
- snake_case function names.
- All hidden_tests must use "expected_output" as the key.
- Function signature must be IDENTICAL across all code fields.

CODE FIELDS:
"clean_solution": correct implementation from scratch. Must pass all hidden_tests.
"code_shown_to_student": broken version for Debugging. Contains EXACTLY ONE bug that causes wrong output, not a crash.
"code_with_bug_fixed": code_shown_to_student with only the bug corrected. Must pass all hidden_tests.

BEFORE OUTPUTTING VERIFY:
- code_shown_to_student produces WRONG output on sample_input
- code_with_bug_fixed produces CORRECT output on sample_input
- clean_solution produces CORRECT output on sample_input
- code_with_bug_fixed and clean_solution agree on all hidden_tests outputs

EXPLANATION FIELDS:
"explanation": shown after Hangman ends. Cover what the function does, a common beginner mistake, and the key concept. 30-40 words, friendly tone.
"buggy_explanation": shown after Debugging ends. Cover what the bug was, why it caused wrong output, and what to remember. 30-40 words, friendly tone.

SCHEMA:
{{
  "question_text":         "brief task (12 words max)",
  "buggy_question_text":   "visible symptom in Debugging (8-20 words)",
  "explanation":           "post-Hangman explanation (30-40 words)",
  "buggy_explanation":     "post-Debugging explanation (30-40 words)",
  "function_name":         "snake_case",
  "sample_input":          "(example,)",
  "sample_output":         "expected correct output",
  "hidden_tests":          [{{"input": "(test,)", "expected_output": "result"}}],
  "clean_solution":        "def name(...):\\n    ...",
  "code_shown_to_student": "def name(...):\\n    ...",
  "code_with_bug_fixed":   "def name(...):\\n    ...",
  "difficulty":            "{context['difficulty']}"
}}

EXAMPLE:
{{
  "question_text":         "Sum all numbers in a list",
  "buggy_question_text":   "Function returns wrong total when summing a list",
  "explanation":           "This function totals a list using sum(). A common mistake is starting the accumulator at 1 instead of 0. Remember: neutral starting values matter — 0 for addition, 1 for multiplication.",
  "buggy_explanation":     "The bug was initializing total to 1 instead of 0, making every sum off by 1. Always initialize accumulators to a neutral value — 0 for addition.",
  "function_name":         "sum_list",
  "sample_input":          "([1, 2, 3],)",
  "sample_output":         "6",
  "hidden_tests":          [{{"input": "([4, 5, 6],)", "expected_output": "15"}}, {{"input": "([0, 0, 0],)", "expected_output": "0"}}],
  "clean_solution":        "def sum_list(numbers):\\n    return sum(numbers)",
  "code_shown_to_student": "def sum_list(numbers):\\n    total = 1\\n    for n in numbers:\\n        total += n\\n    return total",
  "code_with_bug_fixed":   "def sum_list(numbers):\\n    total = 0\\n    for n in numbers:\\n        total += n\\n    return total",
  "difficulty":            "{context['difficulty']}"
}}

RETURN: JSON array only. {context['num_questions']} items.
"""

    def get_non_coding_prompt(self, context: dict) -> str:
      return f"""
OUTPUT ONLY VALID JSON ARRAY. NO prose, NO markdown, NO backticks.

TASK: Generate {context['num_questions']} Python concept-recall questions for a crossword/wordsearch game.
SUBTOPIC: {context['subtopic_name']}
DIFFICULTY: {context['difficulty']}

RAG_CONTEXT:
{context['rag_context']}

RULES:
- Each question targets ONE specific Python concept term from RAG_CONTEXT.
- Answer must be a single term, 4-13 letters only, domain-specific (e.g. docstring, immutability, generator).
- No True/False, no code blocks, no symbols — letters and spaces only.
- Avoid generic answers like "code", "variable", "python", "function".
- Frame as clever crossword-style clues, not textbook questions.

AVOID: "What is the term for...", "Which keyword is used to...", "Identify the concept that..."
USE INSTEAD: "A reusable block of code that performs a specific action." (function)

SCHEMA:
[
  {{
    "question_text": "short unambiguous clue (18 words max, letters and spaces only)",
    "answer":        "singleterm",
    "explanation":   "brief concept note (30-40 words, friendly tone)",
    "difficulty":    "{context['difficulty']}"
  }}
]

RETURN: JSON array only. {context['num_questions']} items.
"""

    def get_pre_assessment_prompt(self, context: dict) -> str:
        return f"""
OUTPUT ONLY VALID JSON ARRAY. NO prose, NO markdown, NO backticks.

TASK: Generate {context['num_questions']} placement assessment questions to determine a beginner's starting Python learning zone.
Zone 1 = Python Basics | Zone 2 = Control Structures | Zone 3 = Loops & Iteration | Zone 4 = Data Structures & Modularity

ZONES, TOPICS, AND SUBTOPICS:
{context['topics_and_subtopics']}

ZONE DISTRIBUTION:
- Zone 1: {context['num_questions'] // 4} questions
- Zone 2: {context['num_questions'] // 4} questions
- Zone 3: {context['num_questions'] // 4} questions
- Zone 4: {context['num_questions'] // 4} questions

DIFFICULTY DISTRIBUTION:
- 50% beginner: recognize a concept, basic terminology, simple syntax
- 40% intermediate: apply a concept in a simple real scenario
- 10% advanced: identify students with prior experience
- EXACTLY 1 master question total

CROSS-TOPIC PAIRING REQUIRED:
Every question combines subtopics from 2 DIFFERENT topics. Use these natural pairings:
Loops+Lists, Loops+Dictionaries, Loops+Strings, Conditionals+Variables,
Conditionals+Dictionaries, Conditionals+Lists, Functions+ErrorHandling,
Functions+Lists, Functions+Dictionaries, Strings+Conditionals,
Sets+Loops, Variables+InputOutput, Operators+Conditionals, ErrorHandling+InputOutput

RULES:
- subtopics_covered must use EXACT subtopic names from the list above, character for character.
- correct_answer must be copied exactly from one of the 4 choices.
- All 4 choices must be plausible, no silly distractors.
- Frame as real scenarios: "You want to...", "You have a...", "You are building..."
- Beginner questions must be approachable with zero experience.

SCHEMA:
[
  {{
    "question_text":    "scenario-based question",
    "choices":          ["A", "B", "C", "D"],
    "correct_answer":   "copied exactly from choices",
    "subtopics_covered": ["exact subtopic from Topic A", "exact subtopic from Topic B"],
    "primary_topic":    "topic this question mainly tests",
    "secondary_topic":  "cross-paired topic",
    "difficulty":       "beginner|intermediate|advanced|master",
    "zone":             1
  }}
]

EXAMPLE:
{{
  "question_text":    "You have a dictionary of student scores and want to print only scores above 50. What should your code do?",
  "choices":          ["Loop through the dictionary and use an if statement to check each score", "Use print() directly on the dictionary", "Sort the dictionary first then print", "Convert the dictionary to a list first"],
  "correct_answer":   "Loop through the dictionary and use an if statement to check each score",
  "subtopics_covered": ["Looping Through Keys, Values, and Items", "if Statement Syntax and Structure"],
  "primary_topic":    "Dictionaries",
  "secondary_topic":  "Conditional Statements",
  "difficulty":       "intermediate",
  "zone":             4
}}

RETURN: JSON array only. {context['num_questions']} items. Distribute evenly across all 4 zones.
"""


deepseek_prompt_manager = DeepSeekPromptManager()
