import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'question_generation')))

from utils.topic_predictor import predict_topic

test_cases = [
    "How do I use a for loop in Python?",
    "What does the if statement do?",
    "How to define a function with parameters?",
    "What is a variable in Python?",
    "Explain recursion with an example.",
    "Print hello world using Python"
]

for question in test_cases:
    topic = predict_topic(question)
    print(f"Question: {question}\nPredicted Topic: {topic}\n")

