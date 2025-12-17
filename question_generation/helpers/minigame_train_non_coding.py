import os
import json
import re
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report, f1_score

from sklearn.naive_bayes import ComplementNB
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.utils.class_weight import compute_sample_weight

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

noncoding_files = [
    f for f in os.listdir(DATA_DIR)
    if f.startswith("non_coding") and f.endswith(".json")
]

dataset = []

def clean_text(text):
    text = (text or "").lower()
    text = re.sub(r"[^a-zA-Z\s]", " ", text)
    words = text.split()
    words = [w for w in words if w and w not in stop_words]
    lemma_words = [lemmatizer.lemmatize(w) for w in words]
    return " ".join(lemma_words)

def norm_label(x):
    return str(x).strip().lower()

# =========================
# LOAD DATASET
# =========================
for filename in noncoding_files:
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r") as f:
        data = json.load(f)

    for item in data:
        try:
            text = item.get("question_text", "")
            diff = item.get("difficulty", "")
            dataset.append({"text": clean_text(text), "difficulty": norm_label(diff)})
        except Exception:
            continue

df = pd.DataFrame(dataset)

# drop empty + invalid labels
df = df[df["text"].str.len() > 0].copy()
df = df[df["difficulty"].isin(["beginner", "intermediate", "advanced", "master"])].copy()

print("\nNON-CODING LABEL DISTRIBUTION")
print(df["difficulty"].value_counts(dropna=False))

# =========================
# ENCODE + VECTORIZER
# =========================
label_encoder = LabelEncoder()
y = label_encoder.fit_transform(df["difficulty"])
X = df["text"]

vectorizer = TfidfVectorizer(
    max_features=4000,
    ngram_range=(1, 2),
    sublinear_tf=True
)
X_vec = vectorizer.fit_transform(X)

X_train, X_test, y_train, y_test = train_test_split(
    X_vec, y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# ✅ imbalance weights (recommended)
train_weights = compute_sample_weight(class_weight="balanced", y=y_train)

num_classes = len(label_encoder.classes_)

# =========================
# MODELS
# =========================
models = {
    "Naive Bayes": ComplementNB(),
    "SVM": LinearSVC(class_weight="balanced", random_state=42),
    "Random Forest": RandomForestClassifier(
        n_estimators=250,
        random_state=42,
        class_weight="balanced_subsample"
    ),
    "XGBoost": XGBClassifier(
        max_depth=6,
        learning_rate=0.1,
        n_estimators=300,
        subsample=0.7,
        colsample_bytree=0.8,
        eval_metric="mlogloss",
        objective="multi:softprob",
        num_class=num_classes
    )
}

results = {}

print("\nTRAINING NON-CODING MINIGAME MODELS")
for model_name, model in models.items():
    print(f"\nTraining {model_name}...")

    # ✅ try sample_weight (works for most)
    try:
        model.fit(X_train, y_train, sample_weight=train_weights)
    except TypeError:
        model.fit(X_train, y_train)

    preds = model.predict(X_test)

    acc = accuracy_score(y_test, preds)
    f1m = f1_score(y_test, preds, average="macro")

    print(f"Accuracy: {acc:.4f} | Macro-F1: {f1m:.4f}")
    print(classification_report(y_test, preds, target_names=label_encoder.classes_))

    # choose best by macro-f1
    results[model_name] = f1m

best_model_name = max(results, key=results.get)
best_model = models[best_model_name]

print(f"\nBEST NON-CODING MODEL (Macro-F1): {best_model_name}")

OUTPUT_PATH = os.path.join(
    BASE_DIR, "question_generation", "models", "minigame_non_coding_model.pkl"
)

joblib.dump({
    "model": best_model,
    "vectorizer": vectorizer,
    "label_encoder": label_encoder
}, OUTPUT_PATH)

print(f"\nModel saved to {OUTPUT_PATH}")
