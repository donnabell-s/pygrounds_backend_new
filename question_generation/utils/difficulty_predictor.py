import joblib
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.normpath(os.path.join(BASE_DIR, '..', 'ml_models', 'difficulty_model.pkl'))
ENCODER_PATH = os.path.normpath(os.path.join(BASE_DIR, '..', 'ml_models', 'difficulty_label_encoder.pkl'))
VECTORIZER_PATH = os.path.normpath(os.path.join(BASE_DIR, '..', 'ml_models', 'difficulty_vectorizer.pkl'))

model = joblib.load(MODEL_PATH)
label_encoder = joblib.load(ENCODER_PATH)
vectorizer = joblib.load(VECTORIZER_PATH)

def clean_text(text):
    return re.sub(r'\W+', ' ', text.lower())

def predict_difficulty(question_text):
    cleaned = clean_text(question_text)
    features = vectorizer.transform([cleaned])
    prediction = model.predict(features)
    label = label_encoder.inverse_transform(prediction)[0]
    return label
