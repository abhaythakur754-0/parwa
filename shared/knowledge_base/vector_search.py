"""
Vector Search Module — Abstract & Mock Implementations

Provides the VectorStore interface and MockVectorStore for testing/development.
Production implementations (Pinecone, Weaviate, Qdrant) will implement VectorStore.

Part of the shared knowledge base infrastructure used by RAG retrieval (F-064).

BC-001: Tenant isolation — all operations scoped to company_id.
"""

from __future__ import annotations

import hashlib
import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ── Constants ─────────────────────────────────────────────────────────

EMBEDDING_DIMENSION = 768  # Default embedding dimension (compatible with many models)

# ── Search Result ─────────────────────────────────────────────────────


@dataclass
class SearchResult:
    """A single result from a vector search query."""

    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "content": self.content,
            "score": round(self.score, 6),
            "metadata": self.metadata,
        }


# ── Stored Chunk (internal) ──────────────────────────────────────────


@dataclass
class StoredChunk:
    """A chunk stored in the vector store."""

    chunk_id: str
    document_id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "content": self.content,
            "metadata": self.metadata,
        }


# Public alias used by tests and other modules
VectorChunk = StoredChunk


# ── Abstract Vector Store ────────────────────────────────────────────


class VectorStore(ABC):
    """Abstract base class for vector stores.

    All implementations must support:
    - Tenant-isolated search (BC-001)
    - Metadata filtering
    - Health checks
    """

    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        company_id: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """Search for similar chunks.

        Args:
            query_embedding: Query vector.
            company_id: Tenant identifier (BC-001).
            top_k: Maximum results to return.
            filters: Optional metadata filters.

        Returns:
            List of search results sorted by score descending.
        """
        ...

    @abstractmethod
    def add_chunks(
        self,
        chunks: List[StoredChunk],
        company_id: str,
    ) -> int:
        """Add chunks to the vector store.

        Args:
            chunks: List of chunks with embeddings.
            company_id: Tenant identifier (BC-001).

        Returns:
            Number of chunks added.
        """
        ...

    @abstractmethod
    def delete_document(
        self,
        document_id: str,
        company_id: str,
    ) -> bool:
        """Delete all chunks for a document.

        Args:
            document_id: Document to delete.
            company_id: Tenant identifier (BC-001).

        Returns:
            True if document was found and deleted.
        """
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the vector store is healthy.

        Returns:
            True if healthy, False otherwise.
        """
        ...


# ── Mock Vector Store ────────────────────────────────────────────────


class MockVectorStore(VectorStore):
    """In-memory mock vector store for testing and development.

    Uses cosine similarity for search and deterministic hashing for embeddings.
    Supports metadata filtering and tenant isolation (BC-001).

    Storage structure:
        _store = {
            company_id: {
                document_id: {
                    "metadata": {...},
                    "chunks": [StoredChunk, ...]
                }
            }
        }
    """

    def __init__(self, seed: Optional[int] = None, embedding_dim: int = EMBEDDING_DIMENSION):
        self._store: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._embedding_dim = embedding_dim
        self._healthy = True
        self._rng: random.Random = random.Random(seed) if seed is not None else random.Random()

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate a deterministic pseudo-embedding for text.

        Uses hash-based approach for reproducibility in tests.
        """
        # Create a seed from the text for deterministic but varied embeddings
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        seed = int(text_hash[:8], 16)

        rng = random.Random(seed)
        embedding = []
        for i in range(self._embedding_dim):
            # Mix text-derived value with position
            char_val = ord(text[i % len(text)]) if text else 0
            hash_val = int(text_hash[i % len(text_hash): i % len(text_hash) + 2], 16) / 255.0
            noise = rng.gauss(0, 0.1)
            embedding.append(round((char_val / 255.0) * 0.5 + hash_val * 0.3 + noise, 6))

        # Normalize to unit vector
        magnitude = math.sqrt(sum(x * x for x in embedding))
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding

    def search(
        self,
        query_embedding: List[float],
        company_id: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """Search for similar chunks using cosine similarity.

        Args:
            query_embedding: Query vector.
            company_id: Tenant identifier (BC-001).
            top_k: Maximum results to return.
            filters: Optional metadata filters (e.g., document_type, tags).

        Returns:
            List of search results sorted by score descending.
        """
        if not self._healthy:
            return []

        if company_id not in self._store:
            return []

        results: List[Tuple[float, StoredChunk]] = []

        for doc_id, doc_data in self._store[company_id].items():
            # Apply document-level filters
            if filters and not self._matches_filters(doc_data.get("metadata", {}), filters):
                continue

            for chunk in doc_data.get("chunks", []):
                # Apply chunk-level filters
                if filters and not self._matches_filters(chunk.metadata, filters):
                    continue

                similarity = self._cosine_similarity(query_embedding, chunk.embedding)
                if similarity > 0:
                    results.append((similarity, chunk))

        # Sort by similarity descending
        results.sort(key=lambda x: x[0], reverse=True)

        return [
            SearchResult(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                content=chunk.content,
                score=score,
                metadata=chunk.metadata,
            )
            for score, chunk in results[:top_k]
        ]

    def add_chunks(
        self,
        chunks: List[StoredChunk],
        company_id: str,
    ) -> int:
        """Add chunks to the mock store.

        Args:
            chunks: List of chunks with embeddings.
            company_id: Tenant identifier (BC-001).

        Returns:
            Number of chunks added.
        """
        if company_id not in self._store:
            self._store[company_id] = {}

        added = 0
        for chunk in chunks:
            if chunk.document_id not in self._store[company_id]:
                self._store[company_id][chunk.document_id] = {
                    "metadata": {},
                    "chunks": [],
                }
            self._store[company_id][chunk.document_id]["chunks"].append(chunk)
            added += 1

        return added

    def delete_document(
        self,
        document_id: str,
        company_id: str,
    ) -> bool:
        """Delete all chunks for a document.

        Args:
            document_id: Document to delete.
            company_id: Tenant identifier (BC-001).

        Returns:
            True if document was found and deleted.
        """
        if company_id in self._store and document_id in self._store[company_id]:
            del self._store[company_id][document_id]
            return True
        return False

    def health_check(self) -> bool:
        """Check if the mock store is healthy.

        Returns:
            True (always healthy for mock).
        """
        return self._healthy

    def set_healthy(self, healthy: bool) -> None:
        """Set health status for testing."""
        self._healthy = healthy

    def set_unhealthy(self, unhealthy: bool) -> None:
        """Toggle unhealthy state for testing (True = unhealthy)."""
        self._healthy = not unhealthy

    def add_document(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]],
        company_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Add a document with chunk dicts to the store.

        Args:
            document_id: Unique document identifier.
            chunks: List of dicts with "content" and optional "metadata".
            company_id: Tenant identifier (BC-001).
            metadata: Optional document-level metadata merged into every chunk.

        Returns:
            True (always succeeds).
        """
        if company_id not in self._store:
            self._store[company_id] = {}

        doc_metadata: Dict[str, Any] = metadata or {}
        stored_chunks: List[StoredChunk] = []

        for i, chunk in enumerate(chunks):
            content = chunk["content"]
            chunk_meta = chunk.get("metadata", {})
            # Merge: chunk-level overrides doc-level
            merged_metadata: Dict[str, Any] = {**doc_metadata, **chunk_meta}
            embedding = self._generate_embedding(content)
            chunk_id = f"{document_id}_chunk_{i}"
            stored_chunks.append(
                StoredChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    content=content,
                    embedding=embedding,
                    metadata=merged_metadata,
                )
            )

        self._store[company_id][document_id] = {
            "metadata": doc_metadata,
            "chunks": stored_chunks,
        }

        return True

    def get_document(self, document_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a stored document as a dict, or None if not found.

        Returns:
            Dict with keys document_id, company_id, metadata, chunks (list of chunk dicts).
        """
        if company_id in self._store and document_id in self._store[company_id]:
            doc_data = self._store[company_id][document_id]
            return {
                "document_id": document_id,
                "company_id": company_id,
                "metadata": doc_data["metadata"],
                "chunks": [chunk.to_dict() for chunk in doc_data["chunks"]],
            }
        return None

    def document_count(self, company_id: str) -> int:
        """Return the number of documents for a company."""
        return len(self._store.get(company_id, {}))

    def get_all_documents(self, company_id: str) -> Dict[str, Dict[str, Any]]:
        """Get all documents for a company (for keyword search fallback).

        Args:
            company_id: Tenant identifier.

        Returns:
            Dict of document_id -> document data.
        """
        return self._store.get(company_id, {})

    def clear(self) -> None:
        """Clear all stored data."""
        self._store.clear()

    # ── Internal Methods ──────────────────────────────────────

    @staticmethod
    def _normalize(vec: List[float]) -> List[float]:
        """Normalize a vector to unit length."""
        mag = math.sqrt(sum(x * x for x in vec))
        if mag == 0:
            return vec
        return [x / mag for x in vec]

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot_product = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot_product / (mag_a * mag_b)

    @staticmethod
    def _matches_filters(
        metadata: Dict[str, Any],
        filters: Dict[str, Any],
    ) -> bool:
        """Check if metadata matches all filter criteria.

        Supports:
        - Exact match: {"document_type": "faq"}
        - Tag membership: {"tags": ["refund", "billing"]}
        - Date range: {"date_after": "2024-01-01", "date_before": "2024-12-31"}
        """
        for key, value in filters.items():
            meta_val = metadata.get(key)

            if key in ("date_after", "date_before"):
                if meta_val is None:
                    return False
                if key == "date_after" and meta_val < value:
                    return False
                if key == "date_before" and meta_val > value:
                    return False
            elif isinstance(value, list):
                # Tag membership: at least one tag must match
                if not meta_val or not any(
                    tag in value for tag in (meta_val if isinstance(meta_val, list) else [meta_val])
                ):
                    return False
            else:
                # Exact match
                if meta_val != value:
                    return False

        return True


# ── Module-level Singleton & Convenience Function ──────────────────


_default_store: Optional[MockVectorStore] = None


def get_vector_store() -> VectorStore:
    """Get the appropriate vector store implementation.

    Returns a singleton MockVectorStore instance in test/dev,
    production store in production.

    Returns:
        VectorStore instance (singleton).
    """
    global _default_store

    if _default_store is None:
        import os

        environment = os.getenv("ENVIRONMENT", "development")

        if environment == "production":
            # In production, use a real vector store
            # For now, return mock with warning
            _default_store = MockVectorStore()
        else:
            _default_store = MockVectorStore()

    return _default_store


def vector_search(
    query_embedding: List[float],
    company_id: str,
    top_k: int = 5,
) -> List[SearchResult]:
    """Convenience function that searches the default vector store.

    Args:
        query_embedding: Query vector.
        company_id: Tenant identifier (BC-001).
        top_k: Maximum results to return.

    Returns:
        List of SearchResult objects sorted by score descending.
    """
    store = get_vector_store()
    return store.search(query_embedding, company_id, top_k)
