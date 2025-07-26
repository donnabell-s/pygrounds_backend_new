"""
Shared imports for content ingestion views modules.
"""

# Django REST Framework imports
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view

# Django core imports
from django.shortcuts import get_object_or_404
from django.db.models import Count
from django.db import models

# Local model imports
from content_ingestion.models import (
    GameZone, Topic, Subtopic, TOCEntry, 
    UploadedDocument, DocumentChunk
)

# Serializer imports
from content_ingestion.serializers import (
    GameZoneSerializer, TopicSerializer, SubtopicSerializer,
    TOCEntrySerializer
)

# Helper imports
from content_ingestion.helpers.toc_parser.toc_apply import generate_toc_entries_for_document
# Placeholder for ChunkOptimizer - define if the helper exists
try:
    from content_ingestion.helpers.page_chunking.chunk_optimizer import ChunkOptimizer
except ImportError:
    # Create a placeholder if ChunkOptimizer doesn't exist
    class ChunkOptimizer:
        def optimize_chunks(self, document_id):
            return {
                'optimized_chunks': [],
                'optimization_stats': {'total_chunks': 0, 'title_fixes': 0, 'content_improvements': 0},
                'llm_ready_format': ''
            }

# Standard library imports
import os
import logging

# Initialize logger
logger = logging.getLogger(__name__)