
# Place this file at: <your_app>/management/commands/load_static_questions.py
from django.core.management.base import BaseCommand
from django.db import transaction
from minigames.models import Question

class Command(BaseCommand):
    help = 'Load static sample questions into the Question table'

    @transaction.atomic
    def handle(self, *args, **options):
        # Static definitions
        static_crossword = [
            {"text": "A popular programming language.", "answer": "python", "difficulty": "easy"},
            {"text": "Immutable sequence in Python.", "answer": "tuple", "difficulty": "medium"},
            {"text": "A sequence of characters.", "answer": "string", "difficulty": "easy"},
            {"text": "Used to define a block of code.", "answer": "indentation", "difficulty": "medium"},
            {"text": "Structure that holds key-value pairs.", "answer": "dictionary", "difficulty": "medium"},
            {"text": "Loop that repeats while a condition is true.", "answer": "while", "difficulty": "easy"},
            {"text": "Keyword to define a function.", "answer": "def", "difficulty": "easy"},
            {"text": "Error found during execution.", "answer": "exception", "difficulty": "medium"},
            {"text": "Code block used to test and handle errors.", "answer": "try", "difficulty": "medium"},
            {"text": "Built-in function to get length of a list.", "answer": "len", "difficulty": "easy"},
        ]

        static_wordsearch = static_crossword.copy()

        static_hangman = [
            {
                "text": "Write a function `reverse_string(s)` that returns the reversed string.",
                "answer": "",
                "difficulty": "easy",
                "function_name": "reverse_string",
                "sample_input": "('hello',)",
                "sample_output": "'olleh'",
                "hidden_tests": [
                    {"input": "('hello',)", "output": "olleh"},
                    {"input": "('world',)", "output": "dlrow"},
                    {"input": "('Python',)", "output": "nohtyP"},
                ],
            },
            {
                "text": "Write a function `is_even(n)` that returns True if a number is even.",
                "answer": "",
                "difficulty": "easy",
                "function_name": "is_even",
                "sample_input": "(4,)",
                "sample_output": "True",
                "hidden_tests": [
                    {"input": "(4,)", "output": True},
                    {"input": "(5,)", "output": False},
                    {"input": "(0,)", "output": True},
                ],
            },
        ]

        static_debugging = [
            {
                "text": "Fix this function so it returns the factorial of n.",
                "answer": "",
                "difficulty": "easy",
                "function_name": "factorial",
                "sample_input": "(5,)",
                "sample_output": "120",
                "hidden_tests": [
                    {"input": "(0,)", "output": 1},
                    {"input": "(4,)", "output": 24},
                    {"input": "(6,)", "output": 720},
                ],
                "broken_code": "def factorial(n):\n    return n * factorial(n-1)  # infinite recursion!\n",
            },
        ]

        # Load or update crossword questions
        for q in static_crossword:
            obj, created = Question.objects.update_or_create(
                text=q['text'],
                game_type='crossword',
                defaults={
                    'answer': q['answer'].upper(),
                    'difficulty': q['difficulty'],
                }
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f"{action} crossword question: {obj.text}")

        # Load or update wordsearch questions
        for q in static_wordsearch:
            obj, created = Question.objects.update_or_create(
                text=q['text'],
                game_type='wordsearch',
                defaults={
                    'answer': q['answer'].upper(),
                    'difficulty': q['difficulty'],
                }
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f"{action} wordsearch question: {obj.text}")

        # Load or update hangman questions
        for q in static_hangman:
            obj, created = Question.objects.update_or_create(
                text=q['text'],
                game_type='hangman',
                defaults={
                    'answer': q.get('answer', ''),
                    'difficulty': q['difficulty'],
                    'function_name': q['function_name'],
                    'sample_input': q['sample_input'],
                    'sample_output': q['sample_output'],
                    'hidden_tests': q['hidden_tests'],
                }
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f"{action} hangman question: {obj.text}")

        # Load or update debugging questions
        for q in static_debugging:
            obj, created = Question.objects.update_or_create(
                text=q['text'],
                game_type='debugging',
                defaults={
                    'answer': q.get('answer', ''),
                    'difficulty': q['difficulty'],
                    'function_name': q['function_name'],
                    'sample_input': q['sample_input'],
                    'sample_output': q['sample_output'],
                    'hidden_tests': q['hidden_tests'],
                    'broken_code': q['broken_code'],
                }
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f"{action} debugging question: {obj.text}")

        self.stdout.write(self.style.SUCCESS("All static questions loaded."))
