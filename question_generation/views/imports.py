"""
Shared imports for question generation views modules.
"""

# Django REST Framework imports
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view

# Django core imports
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q

# Local model imports
from content_ingestion.models import Topic, Subtopic, DocumentChunk
from question_generation.models import GeneratedQuestion,PreAssessmentQuestion

# Helper imports
from question_generation.helpers.rag_utils import QuestionRAG, SmartRAGRetriever
# from question_generation.helpers.llm_utils import DeepSeekQuestionGenerator, MockDeepSeekGenerator  # Temporarily disabled

# Standard library imports
import logging
import json
import os
import random
from datetime import datetime

# Initialize logger
logger = logging.getLogger(__name__)

def load_code_snippets():
    """Load Python code snippets from JSON file"""
    try:
        json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'python_code_snippets.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load code snippets: {e}")
        return None
