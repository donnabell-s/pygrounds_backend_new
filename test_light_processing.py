#!/usr/bin/env python
"""
Test script for lightweight TOC processing
"""

import os
import sys
import django
from django.conf import settings

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pygrounds_backend_new.settings')
django.setup()

from content_ingestion.models import UploadedDocument
from content_ingestion.helpers.toc_parser.toc_apply import generate_toc_entries_for_document

def test_light_processing():
    """Test TOC processing with and without NLP"""
    print("Testing light processing for TOC generation...")
    
    # Get the latest document
    try:
        document = UploadedDocument.objects.latest('uploaded_at')
        print(f"Testing with document: {document.title}")
        
        # Test with NLP disabled (should be faster)
        print("\n=== Testing with NLP disabled ===")
        entries_light = generate_toc_entries_for_document(document, skip_nlp=True)
        print(f"Light processing completed: {len(entries_light)} entries")
        
        # Test with NLP enabled (full processing)
        print("\n=== Testing with NLP enabled ===")
        entries_full = generate_toc_entries_for_document(document, skip_nlp=False)
        print(f"Full processing completed: {len(entries_full)} entries")
        
    except UploadedDocument.DoesNotExist:
        print("No documents found. Please upload a PDF first.")
    except Exception as e:
        print(f"Error during testing: {str(e)}")

if __name__ == "__main__":
    test_light_processing()
