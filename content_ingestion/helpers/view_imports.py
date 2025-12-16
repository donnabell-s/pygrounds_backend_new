## compatibility shim for legacy wildcard imports
# views were refactored to explicit imports; keep this for any external code still relying on `import *`

from __future__ import annotations

import warnings

warnings.warn(
    "`content_ingestion.helpers.view_imports` is deprecated; use explicit imports instead.",
    DeprecationWarning,
    stacklevel=2,
)

# re-export the previously provided names
from django.http import FileResponse, Http404, JsonResponse  # noqa: F401
from django.shortcuts import get_object_or_404  # noqa: F401
from django.db import transaction  # noqa: F401
from django.db.models import Count, Q  # noqa: F401
from django.core.files.storage import default_storage  # noqa: F401
from django.utils import timezone  # noqa: F401

from rest_framework import generics, status  # noqa: F401
from rest_framework.decorators import api_view, permission_classes  # noqa: F401
from rest_framework.permissions import IsAuthenticated  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from rest_framework.views import APIView  # noqa: F401

import json  # noqa: F401
import logging  # noqa: F401
import os  # noqa: F401
from datetime import datetime  # noqa: F401

from ..models import (  # noqa: F401
    DocumentChunk,
    GameZone,
    Subtopic,
    TOCEntry,
    Topic,
    UploadedDocument,
)
from ..serializers import (  # noqa: F401
    DocumentChunkSerializer,
    DocumentSerializer,
    GameZoneSerializer,
    SubtopicSerializer,
    TopicSerializer,
)

logger = logging.getLogger(__name__)  # noqa: F401

__all__ = [
    "APIView",
    "Count",
    "DocumentChunk",
    "DocumentChunkSerializer",
    "DocumentSerializer",
    "FileResponse",
    "GameZone",
    "GameZoneSerializer",
    "Http404",
    "IsAuthenticated",
    "JsonResponse",
    "Q",
    "Response",
    "Subtopic",
    "SubtopicSerializer",
    "TOCEntry",
    "Topic",
    "TopicSerializer",
    "UploadedDocument",
    "api_view",
    "datetime",
    "default_storage",
    "generics",
    "get_object_or_404",
    "json",
    "logger",
    "logging",
    "os",
    "permission_classes",
    "status",
    "timezone",
    "transaction",
]
