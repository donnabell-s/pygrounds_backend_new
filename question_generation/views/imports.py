from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from content_ingestion.models import Topic, Subtopic, DocumentChunk
from question_generation.models import GeneratedQuestion, PreAssessmentQuestion
from content_ingestion.models import SemanticSubtopic
import logging
import json
import os
import random
from datetime import datetime
logger = logging.getLogger(__name__)
