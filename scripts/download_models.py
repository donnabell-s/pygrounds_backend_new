#!/usr/bin/env python
"""
Download embedding models to local folder to avoid rate limits during populate_zones.py
"""
import os
import time

# Get the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
models_dir = os.path.join(project_root, 'models')

print("🔄 Downloading embedding models to local folder...")
print(f"📁 Models will be saved to: {models_dir}")

# Create models directory if it doesn't exist
os.makedirs(models_dir, exist_ok=True)

try:
    print("\n1. Downloading MiniLM model...")
    from sentence_transformers import SentenceTransformer
    
    minilm_path = os.path.join(models_dir, 'all-MiniLM-L6-v2')
    minilm = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    minilm.save(minilm_path)
    print(f"   ✅ MiniLM model saved to: {minilm_path}")
except Exception as e:
    print(f"   ❌ Failed to download MiniLM: {e}")

# Wait between downloads to avoid rate limits
print("⏳ Waiting 5 seconds before downloading CodeBERT...")
time.sleep(5)

try:
    print("2. Downloading CodeBERT model...")
    from transformers import AutoTokenizer, AutoModel
    
    codebert_path = os.path.join(models_dir, 'codebert-base')
    tokenizer = AutoTokenizer.from_pretrained('microsoft/codebert-base')
    model = AutoModel.from_pretrained('microsoft/codebert-base')
    
    # Save tokenizer and model to local folder
    tokenizer.save_pretrained(codebert_path)
    model.save_pretrained(codebert_path)
    print(f"   ✅ CodeBERT model saved to: {codebert_path}")
except Exception as e:
    print(f"   ❌ Failed to download CodeBERT: {e}")

print(f"\n🎉 Model download complete!")
print(f"📂 Models are stored in: {models_dir}")
print("   You can now run populate_zones.py with local models!")
