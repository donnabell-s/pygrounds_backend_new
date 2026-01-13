# question_generation/utils/ml_classifier.py

import os
import re
import joblib
import numpy as np

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

from .coding_rule_engine import refined_coding_rule_engine
from .pre_assessment_rule_engine import pre_assessment_cognitive_engine

# ✅ NON-CODING = cognitive scoring main (no ML)
from .non_coding_rule_engine import predict_non_coding_difficulty, predict_non_coding_difficulty_debug


# =========================
# PREPROCESSING (match training)
# =========================
_lemmatizer = WordNetLemmatizer()
try:
    _stop_words = set(stopwords.words("english"))
except Exception:
    _stop_words = set()


def _clean_text(text: str) -> str:
    """
    IMPORTANT: should match training preprocessing:
    Lowercase -> remove non letters -> remove stopwords -> lemmatize
    """
    t = (text or "").lower()
    t = re.sub(r"[^a-zA-Z\s]", " ", t)
    words = [w for w in t.split() if w and w not in _stop_words]
    words = [_lemmatizer.lemmatize(w) for w in words]
    return " ".join(words)


# =========================
# MODEL LOADING (lazy)
# =========================
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODEL_DIR = os.path.join(_BASE_DIR, "models")

_BUNDLE_CACHE = {}  # game_type -> (model, vectorizer, encoder)


def _load_bundle(game_type: str):
    """
    Lazy-load to avoid unnecessary loads.
    We only need ML bundles for CODING (and optionally future non-coding).
    """
    gt = (game_type or "").strip().lower()

    if gt in _BUNDLE_CACHE:
        return _BUNDLE_CACHE[gt]

    if gt == "coding":
        path = os.path.join(_MODEL_DIR, "minigame_coding_model.pkl")
    else:
        # if you later want to re-enable ML for non-coding, this exists
        path = os.path.join(_MODEL_DIR, "minigame_non_coding_model.pkl")

    bundle = joblib.load(path)
    model = bundle["model"]
    veczr = bundle["vectorizer"]
    enc = bundle["label_encoder"]

    _BUNDLE_CACHE[gt] = (model, veczr, enc)
    return model, veczr, enc


def _ml_predict_with_conf(text: str, game_type: str):
    """
    Returns: (label, confidence)

    confidence meaning:
    - If model has predict_proba -> max probability (0..1)
    - Else if decision_function (LinearSVC) -> margin between top2 scores (bigger = more confident)
    - Else -> None
    """
    cleaned = _clean_text(text)
    model, veczr, enc = _load_bundle(game_type)

    X = veczr.transform([cleaned])  # ✅ TF-IDF applied here
    pred = model.predict(X)[0]
    label = enc.inverse_transform([pred])[0]

    conf = None

    if hasattr(model, "predict_proba"):
        try:
            proba = model.predict_proba(X)[0]
            conf = float(np.max(proba))
        except Exception:
            conf = None

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

    return str(label).strip().lower(), conf


def _rule_predict(text: str, game_type: str):
    gt = (game_type or "").strip().lower()
    if gt == "coding":
        return refined_coding_rule_engine(text)
    return None


# =========================
# FINAL PREDICTOR
# =========================
def predict_difficulty(text: str, game_type: str) -> str:
    """
    ✅ FINAL design:

    - PREASSESSMENT -> cognitive scoring only (NO ML)
    - CODING -> ML + TF-IDF primary + hard guardrails + confidence-gated overrides
    - NON_CODING -> cognitive scoring primary (NO ML)
    """
    gt = (game_type or "").strip().lower()
    text = (text or "").strip()

    if gt == "preassessment":
        return pre_assessment_cognitive_engine(text) or "beginner"

    if not text:
        return "beginner"

    # ✅ NON-CODING main = cognitive scoring (no ML)
    if gt == "non_coding":
        return predict_non_coding_difficulty(text)

    # ✅ CODING main = ML + TF-IDF
    if gt == "coding":
        ml_output, ml_conf = _ml_predict_with_conf(text, gt)
        rule_output = _rule_predict(text, gt)

        # Hard overrides (must-not-miss)
        if rule_output in ("hard_master", "hard_advanced", "hard_intermediate"):
            if rule_output == "hard_master":
                return "master"
            if rule_output == "hard_advanced":
                return "advanced"
            return "intermediate"

        # Confidence-gated override (conservative)
        CONF_THRESHOLD = 0.40
        if rule_output and (ml_conf is None or ml_conf < CONF_THRESHOLD):
            return rule_output

        return ml_output

    # default safety
    return "beginner"


def predict_difficulty_debug(text: str, game_type: str):
    """
    Debug helper:
    - Shows which engine was used (non-coding cognitive vs coding ML)
    """
    gt = (game_type or "").strip().lower()
    text = (text or "").strip()

    info = {
        "game_type": gt,
        "text_preview": text[:120],
        "engine": "",
        "ml_output": None,
        "ml_confidence": None,
        "rule_output": None,
        "final_output": None,
        "note": "",
    }

    if gt == "preassessment":
        out = pre_assessment_cognitive_engine(text) or "beginner"
        info["engine"] = "preassessment_cognitive"
        info["final_output"] = out
        info["note"] = "preassessment -> cognitive scoring (no ML)"
        return info

    if not text:
        info["engine"] = "empty"
        info["final_output"] = "beginner"
        info["note"] = "empty text -> beginner"
        return info

    # ✅ NON-CODING debug
    if gt == "non_coding":
        dbg = predict_non_coding_difficulty_debug(text)
        info["engine"] = "non_coding_cognitive"
        info["final_output"] = dbg["final_label"]
        info["note"] = dbg["note"]
        # attach useful debug fields
        info["cognitive"] = dbg
        return info

    # ✅ CODING debug
    if gt == "coding":
        ml_output, ml_conf = _ml_predict_with_conf(text, gt)
        rule_output = _rule_predict(text, gt)

        info["engine"] = "coding_ml_tfidf"
        info["ml_output"] = ml_output
        info["ml_confidence"] = ml_conf
        info["rule_output"] = rule_output

        if rule_output in ("hard_master", "hard_advanced", "hard_intermediate"):
            if rule_output == "hard_master":
                info["final_output"] = "master"
            elif rule_output == "hard_advanced":
                info["final_output"] = "advanced"
            else:
                info["final_output"] = "intermediate"
            info["note"] = f"coding hard override applied (rule={rule_output})"
            return info

        CONF_THRESHOLD = 0.40
        if rule_output and (ml_conf is None or ml_conf < CONF_THRESHOLD):
            info["final_output"] = rule_output
            info["note"] = f"rule override applied (ml_conf={ml_conf}, threshold={CONF_THRESHOLD})"
            return info

        info["final_output"] = ml_output
        info["note"] = f"ml used (ml_conf={ml_conf}, threshold={CONF_THRESHOLD})"
        return info

    info["engine"] = "fallback"
    info["final_output"] = "beginner"
    info["note"] = "unknown game_type -> fallback beginner"
    return info
