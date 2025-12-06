import os
import json
import re
import joblib
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report

from sklearn.naive_bayes import ComplementNB
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import nltk
nltk.download("stopwords")
nltk.download("wordnet")

lemmatizer = WordNetLemmatizer()
stop_words = set(stopwords.words("english"))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "question_outputs")

coding_files = [f for f in os.listdir(DATA_DIR) if f.startswith("coding") and f.endswith(".json")]

dataset = []

def clean_text(text):
    text = text.lower()
    text = re.sub(r"[^a-zA-Z\s]", " ", text)
    words = text.split()
    words = [w for w in words if w not in stop_words]
    lemma_words = [lemmatizer.lemmatize(w) for w in words]
    return " ".join(lemma_words)


for filename in coding_files:
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r") as f:
        data = json.load(f)

    for item in data:
        try:
            text = item["game_data"]["normal"]["question_text"]
            diff = item["difficulty"]
            dataset.append({"text": clean_text(text), "difficulty": diff})
        except:
            continue

df = pd.DataFrame(dataset)

label_encoder = LabelEncoder()
y = label_encoder.fit_transform(df["difficulty"])
X = df["text"]

vectorizer = TfidfVectorizer(max_features=4000)
X_vec = vectorizer.fit_transform(X)

X_train, X_test, y_train, y_test = train_test_split(
    X_vec, y, test_size=0.2, random_state=42
)

models = {
    "Naive Bayes": ComplementNB(),
    "SVM": LinearSVC(),
    "Random Forest": RandomForestClassifier(n_estimators=250, random_state=42),
    "XGBoost": XGBClassifier(
        max_depth=6, learning_rate=0.1, n_estimators=300,
        subsample=0.7, eval_metric="mlogloss"
    )
}

results = {}

print("\n===== TRAINING CODING MINIGAME MODELS =====")
for model_name, model in models.items():
    print(f"\nTraining {model_name}...")
    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    acc = accuracy_score(y_test, preds)
    print(f"Accuracy: {acc:.4f}")
    print(classification_report(y_test, preds, target_names=label_encoder.classes_))

    results[model_name] = acc

best_model_name = max(results, key=results.get)
best_model = models[best_model_name]

print("\n==================================")
print(f"BEST CODING MODEL: {best_model_name}")
print("==================================")

OUTPUT_PATH = os.path.join(
    BASE_DIR, "question_generation", "models", "minigame_coding_model.pkl"
)

joblib.dump({
    "model": best_model,
    "vectorizer": vectorizer,
    "label_encoder": label_encoder
}, OUTPUT_PATH)

print(f"\nModel saved to {OUTPUT_PATH}")
