"""
PARWA Shared Module

Shared utilities and cross-cutting concerns used across
multiple services and modules.

Bug Fix Day 4: Ensures the shared/ directory is importable as both
``app.shared`` (via the app package) and ``shared`` (via PYTHONPATH).
"""

# Re-export knowledge base for backward compatibility
from app.shared.knowledge_base import (  # noqa: F401
    DocumentChunker,
    KnowledgeBaseManager,
    KnowledgeRetriever,
)
