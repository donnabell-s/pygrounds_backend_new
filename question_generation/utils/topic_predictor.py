import re

TOPIC_KEYWORDS = {
    "Loops": [
        "for loop", "while loop", "range", "iteration", "repeat", "looping"
    ],
    "Conditional Statements": [
        "if statement", "if else", "elif", "boolean logic", "condition", "comparison"
    ],
    "Functions": [
        "define function", "def", "return value", "parameters", "arguments", "scope"
    ],
    "Variables & Data Types": [
        "declare variable", "assign", "variable", "string", "integer", "float", "boolean"
    ],
    "Recursion": [
        "recursive", "recursion", "call itself", "base case"
    ],
    "Basic Input and Output": [
        "print", "input", "read user", "output"
    ],
    "Operators": [
        "+", "-", "*", "/", "%", "//", "**", "==", "!=", "and", "or", "not", ">", "<"
    ]
}

def clean_text(text):
    return re.sub(r'\W+', ' ', text.lower())

def predict_topic(text):
    """Predicts the topic of a given question using keyword matching.
    Prioritizes more specific matches by checking topics in order."""
    cleaned = clean_text(text)
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in cleaned:
                return topic
    return "Uncategorized"