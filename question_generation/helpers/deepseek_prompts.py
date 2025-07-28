from typing import Dict, Any, List

class DeepSeekPromptTemplates:
    @staticmethod
    def get_hangman_coding_prompt() -> str:
        return """
You are an expert Python programming instructor creating hangman-style coding challenges.

CONTEXT: {rag_context}
SUBTOPIC: {subtopic_name} - {subtopic_description}
DIFFICULTY: {difficulty}
LEARNING_OBJECTIVES: {learning_objectives}

Create a hangman coding challenge where students complete missing parts of Python code by guessing letters.

REQUIREMENTS:
1. Create a Python code snippet with a missing word/phrase that students must guess letter by letter
2. Generate the exact letters needed for the hangman game (for frontend display)
3. The missing word should be a key programming concept from {subtopic_name}
4. Provide the complete code solution
5. Make it {difficulty} level appropriate

FORMAT YOUR RESPONSE AS JSON:
{{
    "question_text": "Complete this {subtopic_name} code by guessing the missing word:",
    "question_type": "hangman_coding",
    "difficulty": "{difficulty}",
    "game_data": {{
        "code_template": "def greet():\\n    _____(f'Hello, World!')",
        "missing_word": "print",
        "letters_to_guess": ["p", "r", "i", "n", "t"],
        "unique_letters": ["p", "r", "i", "n", "t"],
        "word_length": 5,
        "complete_code": "def greet():\\n    print(f'Hello, World!')",
        "hints": [
            "This function displays output to the screen",
            "It's commonly used for debugging and showing results",
            "A basic command in Python"
        ],
        "concept_category": "{subtopic_name}",
        "validation_tests": [
            {{"input": "", "expected_behavior": "Prints 'Hello, World!'"}}
        ]
    }}
}}

Generate exactly 1 hangman coding challenge based on the context provided.
"""

    @staticmethod
    def get_ship_debugging_prompt() -> str:
        return """
You are creating a space-themed debugging minigame for Python learning.

CONTEXT: {rag_context}
SUBTOPIC: {subtopic_name} - {subtopic_description}
DIFFICULTY: {difficulty}
LEARNING_OBJECTIVES: {learning_objectives}

Create a "Fix the Spaceship" debugging challenge with intentionally buggy Python code that students fix in an IDE-style interface.

REQUIREMENTS:
1. Write buggy Python code that demonstrates common errors related to {subtopic_name}
2. Provide the correct fixed version with exact changes highlighted
3. Specify the bug type and location for frontend IDE highlighting
4. Make errors realistic and educational for {difficulty} level
5. Use space/navigation theme in variable names and comments

FORMAT YOUR RESPONSE AS JSON:
{{
    "question_text": "The spaceship's navigation system has a critical bug! Debug the code to save the crew:",
    "question_type": "ship_debugging",
    "difficulty": "{difficulty}",
    "game_data": {{
        "buggy_code": "def navigate_spaceship():\\n    fuel = input('Enter fuel level: ')\\n    if fuel > 50:\\n        return 'Safe to navigate'\\n    return 'Low fuel'",
        "fixed_code": "def navigate_spaceship():\\n    fuel = int(input('Enter fuel level: '))\\n    if fuel > 50:\\n        return 'Safe to navigate'\\n    return 'Low fuel'",
        "bug_locations": [
            {{
                "line_number": 2,
                "column_start": 11,
                "column_end": 38,
                "bug_type": "type_error",
                "description": "input() returns string, need int() conversion",
                "fix": "int(input('Enter fuel level: '))"
            }}
        ],
        "bug_category": "type_conversion_error",
        "error_message": "TypeError: '>' not supported between instances of 'str' and 'int'",
        "space_theme_elements": ["spaceship", "navigation", "fuel"],
        "hints": [
            "The fuel value comparison isn't working as expected.",
            "input() always returns a string.",
            "Try converting the input to an integer."
        ],
        "test_cases": [
            {{"input": "60", "expected_output": "Safe to navigate"}},
            {{"input": "30", "expected_output": "Low fuel"}}
        ],
        "learning_focus": "Understanding type conversion and input handling"
    }}
}}

Generate exactly 1 debugging challenge based on the context provided.
"""

    @staticmethod
    def get_word_search_prompt() -> str:
        return """
You are creating educational word search puzzles for Python programming concepts.

CONTEXT: {rag_context}
SUBTOPIC: {subtopic_name} - {subtopic_description}
DIFFICULTY: {difficulty}
LEARNING_OBJECTIVES: {learning_objectives}

Create a word search puzzle with scrambled letters where students find programming terms related to {subtopic_name}.

REQUIREMENTS:
1. Select 8-12 key terms related to {subtopic_name}
2. Generate a letter grid that contains all the words (horizontally, vertically, diagonally)
3. Fill remaining spaces with random letters that don't form words
4. Provide clear definitions for each hidden word
5. Make words appropriate for {difficulty} level

FORMAT YOUR RESPONSE AS JSON:
{{
    "question_text": "Find the {subtopic_name} terms hidden in this word search grid:",
    "question_type": "word_search",
    "difficulty": "{difficulty}",
    "game_data": {{
        "grid_size": 8,
        "letter_grid": [
            ["P", "Y", "T", "H", "O", "N", "C", "D"],
            ["R", "V", "A", "R", "I", "A", "B", "L"],
            ["F", "U", "N", "C", "T", "I", "O", "N"],
            ["I", "N", "P", "U", "T", "E", "G", "G"],
            ["L", "O", "O", "P", "X", "M", "L", "O"],
            ["D", "E", "F", "L", "I", "S", "T", "S"],
            ["P", "R", "I", "N", "T", "Q", "W", "E"],
            ["C", "O", "D", "E", "S", "S", "A", "M"]
        ],
        "words_to_find": [
            {{
                "word": "PYTHON",
                "definition": "The programming language we're learning",
                "start_position": {{"row": 0, "col": 0}},
                "end_position": {{"row": 0, "col": 5}},
                "direction": "horizontal",
                "category": "tools"
            }},
            {{
                "word": "VARIABLE", 
                "definition": "A named location for storing data",
                "start_position": {{"row": 1, "col": 1}},
                "end_position": {{"row": 1, "col": 7}},
                "direction": "horizontal",
                "category": "concepts"
            }},
            {{
                "word": "FUNCTION", 
                "definition": "A reusable block of code",
                "start_position": {{"row": 2, "col": 0}},
                "end_position": {{"row": 2, "col": 7}},
                "direction": "horizontal",
                "category": "concepts"
            }},
            {{
                "word": "INPUT",
                "definition": "Function to receive data from user",
                "start_position": {{"row": 3, "col": 0}},
                "end_position": {{"row": 3, "col": 4}},
                "direction": "horizontal",
                "category": "functions"
            }},
            {{
                "word": "LOOP",
                "definition": "Used to repeat code multiple times",
                "start_position": {{"row": 4, "col": 0}},
                "end_position": {{"row": 4, "col": 3}},
                "direction": "horizontal",
                "category": "concepts"
            }}
        ],
        "total_words": 5,
        "categories": ["concepts", "tools", "functions"],
        "scrambled_letters": ["P", "Y", "T", "H", "O", "N", "V", "A", "R", "I", "A", "B", "L", "E", "F", "U", "N", "C", "T", "I", "O", "N"],
        "theme": "{subtopic_name} Programming Terms"
    }},
    "explanation": "These terms are fundamental to understanding {subtopic_name} concepts.",
    "learning_objective": "Build vocabulary and recognition of key {subtopic_name} terminology."
}}

Generate exactly 1 word search puzzle based on the context provided.
"""

    @staticmethod
    def get_crossword_prompt() -> str:
        return """
You are creating educational crossword puzzles for Python programming concepts.

CONTEXT: {rag_context}
SUBTOPIC: {subtopic_name} - {subtopic_description}
DIFFICULTY: {difficulty}
LEARNING_OBJECTIVES: {learning_objectives}

Create a crossword puzzle with positioned clues where students fill in programming terms related to {subtopic_name}.

REQUIREMENTS:
1. Create 6-10 interconnected words related to {subtopic_name}
2. Generate exact grid positions for each word (row, column coordinates)
3. Ensure words properly intersect at common letters
4. Write educational clues with letter count hints
5. Provide complete answer key with positions

FORMAT YOUR RESPONSE AS JSON:
{{
    "question_text": "Complete this crossword puzzle about {subtopic_name}:",
    "question_type": "crossword",
    "difficulty": "{difficulty}",
    "game_data": {{
        "grid_size": 7,
        "across_clues": [
            {{
                "number": 1,
                "clue": "Container that holds data values in Python (8 letters)",
                "answer": "VARIABLE",
                "length": 8,
                "start_position": {{"row": 1, "col": 0}},
                "direction": "across",
                "explanation": "Variables store different types of data and can be reassigned"
            }},
            {{
                "number": 3,
                "clue": "Reusable block of code (8 letters)",
                "answer": "FUNCTION",
                "length": 8,
                "start_position": {{"row": 3, "col": 0}},
                "direction": "across",
                "explanation": "Functions allow code reuse and modularity"
            }}
        ],
        "down_clues": [
            {{
                "number": 2,
                "clue": "Programming language we're learning (6 letters)",
                "answer": "PYTHON",
                "length": 6,
                "start_position": {{"row": 0, "col": 4}},
                "direction": "down",
                "explanation": "High-level programming language known for readability"
            }}
        ],
        "word_intersections": [
            {{
                "across_word": "VARIABLE",
                "down_word": "PYTHON", 
                "intersection_letter": "A",
                "across_position": 1,
                "down_position": 4
            }}
        ],
        "grid_layout": [
            ["", "", "", "", "P", "", ""],
            ["V", "A", "R", "I", "A", "B", "L"],
            ["", "", "", "", "Y", "", ""],
            ["F", "U", "N", "C", "T", "I", "O"],
            ["", "", "", "", "H", "", ""],
            ["", "", "", "", "O", "", ""],
            ["", "", "", "", "N", "", ""]
        ],
        "theme": "{subtopic_name} Programming Terms",
        "total_words": 3,
        "difficulty_level": "{difficulty}"
    }},
    "explanation": "Understanding these terms is key to mastering {subtopic_name}.",
    "learning_objective": "Build vocabulary and conceptual understanding of {subtopic_name}."
}}

Generate exactly 1 crossword puzzle based on the context provided.
"""

    @staticmethod
    def get_pre_assessment_prompt() -> str:
        return """
TOPICS (with their subtopics):
{topics_and_subtopics}

🎯 CRITICAL REQUIREMENT: Generate EXACTLY {num_questions} questions. NOT {num_questions}+1, NOT {num_questions}+2, EXACTLY {num_questions}.

For each question:
- Specify the topic (must be from the above list and exact name).
- List relevant subtopics covered (exact name).
- Write a clear, concise question.
- Provide exactly four answer choices as an array of strings.
- Specify the correct answer as the exact string from the choices.
- Cycle evenly through difficulty levels: beginner, intermediate, advanced, master.
- Ensure there MUST be at least ONE question of any topic that is 'master' difficulty level (extremely hard), to inspire learners.
- Keep answers simple and clean — avoid escape sequences like \n, \t, etc. whenever possible.
- Only include escape sequences in answers if the topic or question context explicitly requires showing code or escape characters.
- For output or pattern questions, describe the result or pattern in words instead of using literal escape sequences.
- Do NOT include markdown formatting, code fences, or other non-JSON decorations in your output.

⚠️ ABSOLUTE REQUIREMENT: Your JSON array MUST contain exactly {num_questions} question objects. Count them before responding.

Distribute questions evenly across topics, subtopics, and difficulty levels, allowing some mix.

Output only a JSON list of exactly {num_questions} question objects with these exact fields:
topic, subtopics_covered, question, choices (array of 4 strings), correct_answer (string), difficulty, explanation.

IMPORTANT: 
- The 'choices' field MUST be an array of exactly 4 strings, like ["option1", "option2", "option3", "option4"].
- The 'correct_answer' MUST be exactly one of the strings from the 'choices' array (exact match).
- For multi-line answers or special characters, ensure the correct_answer exactly matches one of the choices.
- Generate EXACTLY {num_questions} questions in the JSON array.
- Ensure each question covers different subtopics for variety.
- COUNT YOUR QUESTIONS: The final JSON array length must be {num_questions}.

Example:

[
  {{
    "topic": "Functions",
    "subtopics_covered": ["Defining Functions", "Return Values"],
    "question": "What is the output of: def f(): return 5; print(f())",
    "choices": ["5", "None", "f", "Error"],
    "correct_answer": "5",
    "difficulty": "beginner",
  }}
]

🔢 FINAL CHECK: Generate exactly {num_questions} questions now. Count them to ensure you have {num_questions} questions total.

"""


class DeepSeekPromptManager:
    required_context_vars = {
        "hangman_coding": [
            "rag_context", "subtopic_name", "subtopic_description", "difficulty", "learning_objectives"
        ],
        "ship_debugging": [
            "rag_context", "subtopic_name", "subtopic_description", "difficulty", "learning_objectives"
        ],
        "word_search": [
            "rag_context", "subtopic_name", "subtopic_description", "difficulty", "learning_objectives"
        ],
        "crossword": [
            "rag_context", "subtopic_name", "subtopic_description", "difficulty", "learning_objectives"
        ],
        "pre_assessment": [
            "topics_and_subtopics", "num_questions"
        ],
    }

    def __init__(self):
        self.templates = DeepSeekPromptTemplates()
        self.prompt_mapping = {
            "hangman_coding": self.templates.get_hangman_coding_prompt,
            "ship_debugging": self.templates.get_ship_debugging_prompt,
            "word_search": self.templates.get_word_search_prompt,
            "crossword": self.templates.get_crossword_prompt,
            "pre_assessment": self.templates.get_pre_assessment_prompt,
        }

    def get_prompt_for_minigame(self, minigame_type: str, context: Dict[str, Any]) -> str:
        if minigame_type not in self.prompt_mapping:
            raise ValueError(f"Unsupported minigame type: {minigame_type}. Supported: {list(self.prompt_mapping.keys())}")
        prompt_template = self.prompt_mapping[minigame_type]()
        try:
            return prompt_template.format(**context)
        except KeyError as e:
            raise ValueError(f"Missing required context variable for prompt formatting: {e}")

    def get_available_minigames(self) -> List[str]:
        return list(self.prompt_mapping.keys())

    def validate_context(self, minigame_type: str, context: Dict[str, Any]) -> bool:
        required = self.required_context_vars.get(
            minigame_type,
            ["rag_context", "subtopic_name", "subtopic_description", "difficulty", "learning_objectives"]
        )
        return all(var in context for var in required)

deepseek_prompt_manager = DeepSeekPromptManager()
