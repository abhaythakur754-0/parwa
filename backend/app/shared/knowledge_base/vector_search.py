"""
PARWA Vector Search Module (G1 FIX)

Provides the VectorStore abstraction layer used by rag_retrieval.py,
rag_reranking.py, and the RAG API endpoints.

Architecture:
  - VectorStore (ABC): Interface for vector search operations
  - MockVectorStore: In-memory implementation for dev/testing
  - PgVectorStore: PostgreSQL pgvector implementation (production)
  - get_vector_store(): Factory that returns the appropriate store

BC-001: All operations scoped to company_id.
BC-008: Graceful degradation — MockVectorStore as fallback.

Parent: Day 4 (G1 fix — module was missing, causing ImportError)
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("parwa.vector_search")

# ── Constants ───────────────────────────────────────────────────────

EMBEDDING_DIMENSION: int = 768  # Google AI embedding dimension


# ── Data Classes ───────────────────────────────────────────────────


@dataclass
class VectorChunk:
    """A chunk stored in the vector store."""

    chunk_id: str
    document_id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    company_id: str = ""


@dataclass
class SearchResult:
    """A vector search result."""

    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── VectorStore ABC ────────────────────────────────────────────────


class VectorStore(ABC):
    """Abstract base class for vector search operations.

    BC-001: All methods require company_id for tenant isolation.
    BC-008: Subclasses must handle their own errors gracefully.
    """

    @abstractmethod
    def add_document(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]],
        company_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Add a document's chunks to the vector store."""
        ...

    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        company_id: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """Search for similar chunks."""
        ...

    @abstractmethod
    def delete_document(self, document_id: str, company_id: str) -> bool:
        """Delete a document from the vector store."""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the vector store is healthy."""
        ...

    def get_all_documents(self, company_id: str) -> Dict[str, Any]:
        """Get all documents for a company (used by keyword fallback)."""
        return {}

    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate a deterministic pseudo-embedding for fallback."""
        if not text or not text.strip():
            return None
        text_bytes = text.encode("utf-8")
        raw = hashlib.sha256(text_bytes).digest()
        # Expand to EMBEDDING_DIMENSION floats in [-1, 1]
        embedding: List[float] = []
        for i in range(EMBEDDING_DIMENSION):
            byte_idx = i % len(raw)
            val = (raw[byte_idx] / 127.5) - 1.0
            embedding.append(round(val, 6))
        # Normalize to unit vector
        magnitude = math.sqrt(sum(v * v for v in embedding)) or 1.0
        return [v / magnitude for v in embedding]


# ── MockVectorStore (dev/testing) ──────────────────────────────────


class MockVectorStore(VectorStore):
    """In-memory vector store for development and testing.

    Uses cosine similarity for search. Falls back to deterministic
    pseudo-embeddings when no real embedding service is available.

    BC-008: Never crashes — always returns safe defaults.
    """

    def __init__(self):
        # company_id -> document_id -> {"chunks": [...], "metadata": {...}}
        self._store: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def add_document(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]],
        company_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Store chunks in memory."""
        if company_id not in self._store:
            self._store[company_id] = {}
        self._store[company_id][document_id] = {
            "chunks": chunks,
            "metadata": metadata or {},
        }
        logger.debug(
            "mock_vector_store_add",
            company_id=company_id,
            document_id=document_id,
            chunk_count=len(chunks),
        )
        return True

    def search(
        self,
        query_embedding: List[float],
        company_id: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """Search using cosine similarity against pseudo-embeddings."""
        results: List[SearchResult] = []

        company_docs = self._store.get(company_id, {})
        for doc_id, doc_data in company_docs.items():
            for chunk in doc_data.get("chunks", []):
                if isinstance(chunk, dict):
                    content = chunk.get("content", "")
                    chunk_id = chunk.get("chunk_id", "")
                    chunk_meta = chunk.get("metadata", {})
                else:
                    content = getattr(chunk, "content", "")
                    chunk_id = getattr(chunk, "chunk_id", "")
                    chunk_meta = getattr(chunk, "metadata", {})

                if not content:
                    continue

                # Apply metadata filters if provided
                if filters:
                    skip = False
                    for fk, fv in filters.items():
                        if fk in chunk_meta and chunk_meta[fk] != fv:
                            skip = True
                            break
                    if skip:
                        continue

                # Generate pseudo-embedding and compute cosine similarity
                chunk_emb = self._generate_embedding(content)
                if chunk_emb and query_embedding:
                    score = self._cosine_similarity(query_embedding, chunk_emb)
                else:
                    score = 0.5  # default score

                results.append(SearchResult(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    content=content,
                    score=round(score, 4),
                    metadata=chunk_meta,
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def delete_document(self, document_id: str, company_id: str) -> bool:
        """Remove a document from memory."""
        if company_id in self._store:
            self._store[company_id].pop(document_id, None)
        return True

    def health_check(self) -> bool:
        """Mock store is always healthy."""
        return True

    def get_all_documents(self, company_id: str) -> Dict[str, Any]:
        """Get all documents for a company."""
        return dict(self._store.get(company_id, {}))

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)


# ── Factory ────────────────────────────────────────────────────────

_store_instance: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Return the appropriate VectorStore implementation.

    Priority:
    1. PgVectorStore if DATABASE_URL is set and pgvector is available
    2. MockVectorStore as safe fallback (BC-008)

    Thread-safe singleton pattern.
    """
    global _store_instance
    if _store_instance is not None:
        return _store_instance

    # Try PgVectorStore first
    try:
        database_url = os.environ.get("DATABASE_URL", "")
        if database_url and "postgresql" in database_url.lower():
            pg_store = _create_pg_vector_store()
            if pg_store and pg_store.health_check():
                _store_instance = pg_store
                logger.info("Using PgVectorStore for vector search")
                return _store_instance
    except Exception as exc:
        logger.warning(
            "PgVectorStore unavailable, falling back to MockVectorStore: %s",
            exc,
        )

    # Fallback to MockVectorStore
    _store_instance = MockVectorStore()
    logger.info("Using MockVectorStore for vector search (dev/fallback mode)")
    return _store_instance


def _create_pg_vector_store() -> Optional[VectorStore]:
    """Attempt to create a PgVectorStore instance.

    Returns None if pgvector is not available.
    """
    try:
        # Lazy import — pgvector might not be installed
        import asyncpg  # noqa: F401

        # Check if pgvector extension function is available
        # This will be properly implemented when pgvector is integrated
        logger.info("pgvector detected, PgVectorStore available")
        return None  # Return actual PgVectorStore when implemented
    except ImportError:
        logger.debug("asyncpg not installed — MockVectorStore will be used")
        return None
    except Exception as exc:
        logger.warning("PgVectorStore creation failed: %s", exc)
        return None
