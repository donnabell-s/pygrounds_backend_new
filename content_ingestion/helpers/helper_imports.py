## Compatibility shim for legacy wildcard imports.
# Views were refactored to explicit imports; keep this for any external code still relying on `import *`.

from __future__ import annotations

import warnings

warnings.warn(
	"`content_ingestion.helpers.helper_imports` is deprecated; use explicit imports instead.",
	DeprecationWarning,
	stacklevel=2,
)

from ..helpers.embedding.generator import EmbeddingGenerator  # noqa: F401
from ..helpers.page_chunking.toc_chunk_processor import GranularChunkProcessor  # noqa: F401
from ..helpers.toc_parser import generate_toc_entries_for_document  # noqa: F401

__all__ = [
	"EmbeddingGenerator",
	"GranularChunkProcessor",
	"generate_toc_entries_for_document",
]
