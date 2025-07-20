import json

data = {
    "python_snippets": {
        "input_output": {
            "description": "Code snippets for input and output operations",
            "snippets": [
                {
                    "id": "multiple_inputs",
                    "topic": "Multiple inputs",
                    "code": "name = input(\"Name: \")\nage = int(input(\"Age: \"))\ncity = input(\"City: \")\nprint(f\"{name} is {age} years old and lives in {city}\")",
                    "difficulty": "beginner",
                    "concepts": ["input", "int", "print", "f-strings", "variables"],
                    "buggy_version": "name = input(\"Name: \")\nage = int(input(\"Age: \"))\ncity = input(\"City: \")\nprint(f\"{name} is {age} years old and lives in {city}\")",
                    "bug_type": "none",
                    "bug_description": "Clean code for reference"
                },
                {
                    "id": "age_check",
                    "topic": "Age validation",
                    "code": "age = int(input(\"Enter your age: \"))\nif age >= 18:\n    print(\"You are an adult\")\nelse:\n    print(\"You are a minor\")",
                    "difficulty": "beginner",
                    "concepts": ["input", "int", "if-else", "comparison"],
                    "buggy_version": "age = input(\"Enter your age: \")\nif age >= 18:\n    print(\"You are an adult\")\nelse:\n    print(\"You are a minor\")",
                    "bug_type": "type_error",
                    "bug_description": "Comparing string to integer without conversion"
                }
            ]
        }
    }
}

with open('python_code_snippets.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)

print("JSON file created successfully")
