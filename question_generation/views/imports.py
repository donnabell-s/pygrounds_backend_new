"""
Shared imports for question generation views.

This module provides common imports used across question generation views,
including Django REST framework components, models, and utilities.
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
from question_generation.models import GeneratedQuestion, PreAssessmentQuestion
# SemanticSubtopic is now in content_ingestion.models
from content_ingestion.models import SemanticSubtopic

# Standard library imports
import logging
import json
import os
import random
from datetime import datetime

# Initialize logger
logger = logging.getLogger(__name__)
