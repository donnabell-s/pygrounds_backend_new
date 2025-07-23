import joblib
import os
import re

# Paths to model and encoder
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, 'ml_models', 'difficulty_model.pkl')
ENCODER_PATH = os.path.join(BASE_DIR, 'ml_models', 'difficulty_label_encoder.pkl')

# Load trained pipeline and label encoder
model = joblib.load(MODEL_PATH)
label_encoder = joblib.load(ENCODER_PATH)

def clean_text(text):
    return re.sub(r'\W+', ' ', text.lower())

def predict_difficulty(question_text):
    cleaned = clean_text(question_text)
    prediction = model.predict([cleaned])  # ✅ model already includes vectorizer
    label = label_encoder.inverse_transform(prediction)[0]
    return label
