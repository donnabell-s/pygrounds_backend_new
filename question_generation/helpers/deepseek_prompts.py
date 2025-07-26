from typing import Dict, Any, List

class DeepSeekPromptTemplates:
    """
    Holds prompt templates for all minigame and assessment types.
    Add new minigame/assessment templates as static methods here.
    """

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
    }},
    "explanation": "The missing word 'print' is used to display text output in Python.",
    "learning_objective": "Students learn to identify and use print statements in Python."
}}

IMPORTANT: 
- missing_word must be a single programming term (variable name, function name, keyword, etc.)
- letters_to_guess contains ALL letters including duplicates in order
- unique_letters contains each unique letter only once
- The word should fit naturally in the code context

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
    }},
    "explanation": "input() returns a string, so 'fuel > 50' compares a string to an integer. The fix is to use int().",
    "learning_objective": "Students learn to identify and fix type-related bugs in Python input handling."
}}

IMPORTANT:
- bug_locations provides exact coordinates for IDE highlighting
- Include realistic error messages that Python would actually show
- Focus on one main bug that clearly relates to the subtopic
- Make the space theme engaging but educational

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

IMPORTANT:
- letter_grid must be a valid 2D array where words can actually be found
- Each word in words_to_find must exist in the grid at the specified coordinates
- scrambled_letters should include all letters from the words plus some extras
- start_position and end_position provide exact coordinates for word highlighting

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

IMPORTANT:
- start_position provides exact (row, col) coordinates for word placement
- grid_layout shows the complete filled crossword grid
- word_intersections ensure words properly connect
- All words must fit within the specified grid_size

Generate exactly 1 crossword puzzle based on the context provided.
"""

    @staticmethod
    def get_pre_assessment_prompt() -> str:
        return """
You are a Python assessment expert creating a pre-assessment for a new student.

GOAL: Assess the student's knowledge in key Python topics to recommend a personalized learning path.

TOPICS TO COVER (each with subtopics listed underneath):
{topics_and_subtopics}
- For each topic, the listed subtopics are the *scope* of that topic. Questions should reference subtopics as belonging to their parent topic.

REQUIREMENTS:
- Generate exactly {num_questions} multiple-choice questions.
- For each question:
    * Specify the topic (must be one of the topics above).
    * List the subtopics_covered (choose one or more subtopics relevant to the question, always from the subtopics under the given topic).
    * Write a clear question (avoid ambiguity, be concise).
    * Give four answer choices (A-D), with the correct answer randomly assigned among them (do NOT always use A).
    * Indicate correct_answer as the corresponding letter (A/B/C/D).
    * Specify the difficulty ("beginner", "intermediate", "advanced", "master").
    * Give a brief explanation of the answer.
- Distribute questions across topics and subtopics as evenly as possible.
- Mix question difficulty and ensure a breadth of coverage.
- Format output as a **JSON list** of objects, each with: topic, subtopics_covered, question, choices, correct_answer, difficulty, explanation.

IMPORTANT:
- Each question must clearly state all subtopics it covers (from the relevant topic).
- Do not always place the correct answer as choice A.
- Output ONLY the JSON list, with no extra commentary, markdown, or formatting.

EXAMPLE OUTPUT FORMAT:
[
  {{
    "topic": "Functions",
    "subtopics_covered": ["Defining Functions", "Return Values"],
    "question": "What is the output of: def f(): return 5; print(f())",
    "choices": {{ "A": "5", "B": "None", "C": "f", "D": "Error" }},
    "correct_answer": "A",
    "difficulty": "beginner",
    "explanation": "The function returns 5, so print(f()) prints 5."
  }}
  // ...more questions
]

Generate exactly {num_questions} pre-assessment questions based on the topics and subtopics listed above.
"""


class DeepSeekPromptManager:
    """
    Manages prompt selection, formatting, and validation.
    Add to prompt_mapping and required_context_vars when you add a new mode.
    """

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
        """
        Select and format a prompt for the specified minigame or assessment type.
        """
        if minigame_type not in self.prompt_mapping:
            raise ValueError(f"Unsupported minigame type: {minigame_type}. Supported: {list(self.prompt_mapping.keys())}")

        prompt_template = self.prompt_mapping[minigame_type]()
        try:
            formatted_prompt = prompt_template.format(**context)
            return formatted_prompt
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

# Global instance for easy import everywhere
deepseek_prompt_manager = DeepSeekPromptManager()
