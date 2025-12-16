# question_generation/utils/ml_classifier.py

import os
import re
import joblib
import numpy as np

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

from .non_coding_rule_engine import refined_non_coding_rule_engine
from .coding_rule_engine import refined_coding_rule_engine
from .pre_assessment_rule_engine import pre_assessment_rule_engine


# =========================
# PATHS + LOAD MODELS
# =========================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "models")

coding_model_path = os.path.join(MODEL_DIR, "minigame_coding_model.pkl")
noncoding_model_path = os.path.join(MODEL_DIR, "minigame_non_coding_model.pkl")

coding_bundle = joblib.load(coding_model_path)
noncoding_bundle = joblib.load(noncoding_model_path)

coding_model = coding_bundle["model"]
coding_vectorizer = coding_bundle["vectorizer"]
coding_encoder = coding_bundle["label_encoder"]

noncoding_model = noncoding_bundle["model"]
noncoding_vectorizer = noncoding_bundle["vectorizer"]
noncoding_encoder = noncoding_bundle["label_encoder"]


# =========================
# PREPROCESSING (match training)
# =========================
_lemmatizer = WordNetLemmatizer()
_stop_words = set(stopwords.words("english"))


def _clean_text(text: str) -> str:
    """
    IMPORTANT: this should match your training preprocessing.
    Lowercase -> remove non letters -> remove stopwords -> lemmatize
    """
    t = (text or "").lower()
    t = re.sub(r"[^a-zA-Z\s]", " ", t)
    words = [w for w in t.split() if w and w not in _stop_words]
    words = [_lemmatizer.lemmatize(w) for w in words]
    return " ".join(words)


# =========================
# INTERNAL HELPERS
# =========================
def _get_model_bundle(game_type: str):
    """
    Returns: (model, vectorizer, encoder)

    Note: preassessment does NOT use ML.
    """
    if game_type == "coding":
        return coding_model, coding_vectorizer, coding_encoder

    # default to non_coding
    return noncoding_model, noncoding_vectorizer, noncoding_encoder


def _ml_predict_with_conf(text: str, game_type: str):
    """
    Returns: (label, confidence)

    confidence meaning:
    - If model has predict_proba -> max probability (0..1)
    - Else if decision_function (LinearSVC) -> margin between top2 scores (bigger = more confident)
    - Else -> None

    NOTE: confidence is for debugging only. It does NOT change final output.
    """
    cleaned = _clean_text(text)
    model, veczr, enc = _get_model_bundle(game_type)

    X = veczr.transform([cleaned])
    pred = model.predict(X)[0]
    label = enc.inverse_transform([pred])[0]

    conf = None

    # Probabilistic models
    if hasattr(model, "predict_proba"):
        try:
            proba = model.predict_proba(X)[0]
            conf = float(np.max(proba))
        except Exception:
            conf = None

    # Margin-based confidence (e.g., LinearSVC)
    elif hasattr(model, "decision_function"):
        try:
            scores = model.decision_function(X)
            scores = scores[0] if getattr(scores, "ndim", 1) > 1 else scores
            if len(scores) >= 2:
                top2 = np.sort(scores)[-2:]
                conf = float(top2[1] - top2[0])  # margin
            else:
                conf = float(scores[0])
        except Exception:
            conf = None

    return label, conf


def _rule_predict(text: str, game_type: str):
    """
    Returns rule label or None
    """
    if game_type == "coding":
        return refined_coding_rule_engine(text)
    if game_type == "non_coding":
        return refined_non_coding_rule_engine(text)
    return None


# =========================
# FINAL PREDICTOR
# =========================
def predict_difficulty(text: str, game_type: str) -> str:
    """
    Unified hybrid difficulty classifier:

    - PREASSESSMENT -> rule only (NO ML)
    - CODING/NON_CODING -> ML baseline + rule override (rule wins)

    No guardrails here (as requested).
    """
    text = (text or "").strip()

    # PREASSESSMENT = rule only
    if game_type == "preassessment":
        return pre_assessment_rule_engine(text) or "beginner"

    if not text:
        return "beginner"

    # ML baseline
    ml_output, _ml_conf = _ml_predict_with_conf(text, game_type)

    # Rule override
    rule_output = _rule_predict(text, game_type)
    if rule_output:
        return rule_output

    # If no rule matched, trust ML
    return ml_output


# =========================
# DEBUG VERSION
# =========================
def predict_difficulty_debug(text: str, game_type: str):
    """
    Debug helper: returns detailed info (ml output + confidence, rule output, final output).
    """
    text = (text or "").strip()

    info = {
        "game_type": game_type,
        "text_preview": text[:120],
        "ml_output": None,
        "ml_confidence": None,
        "rule_output": None,
        "final_output": None,
        "note": "",
    }

    # PREASSESSMENT (rule only)
    if game_type == "preassessment":
        rule = pre_assessment_rule_engine(text) or "beginner"
        info["rule_output"] = rule
        info["final_output"] = rule
        info["note"] = "preassessment -> rule only"
        return info

    if not text:
        info["final_output"] = "beginner"
        info["note"] = "empty text -> beginner"
        return info

    # ML baseline
    ml_output, ml_conf = _ml_predict_with_conf(text, game_type)
    info["ml_output"] = ml_output
    info["ml_confidence"] = ml_conf

    # Rule override
    rule_output = _rule_predict(text, game_type)
    info["rule_output"] = rule_output

    if rule_output:
        info["final_output"] = rule_output
        info["note"] = "rule override applied"
        return info

    # Otherwise ML decides
    info["final_output"] = ml_output
    info["note"] = "ml used (no rule match)"
    return info
