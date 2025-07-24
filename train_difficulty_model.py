import pandas as pd
import joblib
import os
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import LinearSVC

data = {
    "question_text": [
        
        "What is a variable?",
        "Write a Python program to reverse a string.",
        "What does the print() function do?",
        "How do you write a comment in Python?",
        "What is a string in programming?",
        
        "Explain the difference between a list and a tuple in Python.",
        "What is the purpose of the __init__ method in Python classes?",
        "How do you handle exceptions in Python?",
        "What are Python decorators?",
        "What is list comprehension in Python?",

        "Describe recursion with an example.",
        "Explain the concept of multithreading in Python.",
        "How does garbage collection work in Python?",
        "What is the Global Interpreter Lock (GIL) in Python?",
        "Design a class-based system for a library management application."
    ],
    "difficulty": [

        "Easy",
        "Easy",
        "Easy",
        "Easy",
        "Easy",
        
        "Intermediate",
        "Intermediate",
        "Intermediate",
        "Intermediate",
        "Intermediate",
        
        "Hard",
        "Hard",
        "Hard",
        "Hard",
        "Hard"
    ]
}

df = pd.DataFrame(data)

def clean_text(text):
    return re.sub(r'\W+', ' ', text.lower())

df["cleaned_text"] = df["question_text"].apply(clean_text)

label_encoder = LabelEncoder()
y = label_encoder.fit_transform(df["difficulty"])

vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(df["cleaned_text"])

model = LinearSVC()
model.fit(X, y)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "question_generation", "ml_models")
os.makedirs(MODEL_DIR, exist_ok=True)

joblib.dump(model, os.path.join(MODEL_DIR, "difficulty_model.pkl"))
joblib.dump(label_encoder, os.path.join(MODEL_DIR, "difficulty_label_encoder.pkl"))
joblib.dump(vectorizer, os.path.join(MODEL_DIR, "difficulty_vectorizer.pkl"))

print("Model, label encoder, and vectorizer saved successfully.")
