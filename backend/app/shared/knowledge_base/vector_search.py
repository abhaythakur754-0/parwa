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

    def get_document(
        self, document_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a single document and its chunks.

        SECURITY (BC-001): Must be scoped to company_id.

        Args:
            document_id: Document identifier.
            company_id: Tenant identifier.

        Returns:
            Dict with document data, or None if not found.
        """
        return None

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
        # ── SAFETY ASSERTION: prevent unscoped writes ──────────────
        if not company_id or not isinstance(company_id, str) or not company_id.strip():
            raise ValueError(
                "SECURITY: MockVectorStore.add_document() requires a non-empty "
                "company_id to prevent cross-tenant data leakage. "
                f"Received: {company_id!r}"
            )
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
        # ── SAFETY ASSERTION: prevent unscoped queries ─────────────
        if not company_id or not isinstance(company_id, str) or not company_id.strip():
            raise ValueError(
                "SECURITY: MockVectorStore.search() requires a non-empty "
                "company_id to prevent cross-tenant data leakage. "
                f"Received: {company_id!r}"
            )
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
        # ── SAFETY ASSERTION: prevent unscoped deletes ─────────────
        if not company_id or not isinstance(company_id, str) or not company_id.strip():
            raise ValueError(
                "SECURITY: MockVectorStore.delete_document() requires a non-empty "
                "company_id to prevent cross-tenant data deletion. "
                f"Received: {company_id!r}"
            )
        if company_id in self._store:
            self._store[company_id].pop(document_id, None)
        return True

    def health_check(self) -> bool:
        """Mock store is always healthy."""
        return True

    def get_all_documents(self, company_id: str) -> Dict[str, Any]:
        """Get all documents for a company."""
        return dict(self._store.get(company_id, {}))

    def get_document(
        self, document_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a single document and its chunks (BC-001: scoped to company_id)."""
        company_docs = self._store.get(company_id, {})
        doc_data = company_docs.get(document_id)
        if doc_data is None:
            return None
        return {
            "document_id": document_id,
            "company_id": company_id,
            "chunks": doc_data.get("chunks", []),
            "metadata": doc_data.get("metadata", {}),
        }

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


# ── PgVectorStore (production — PostgreSQL + pgvector) ──────────


class PgVectorStore(VectorStore):
    """PostgreSQL + pgvector vector store implementation.

    Uses the document_chunks table which already has an embedding
    column with pgvector vector(768) type.
    """

    def __init__(self, dimension: int = 768):
        self.dimension = dimension

    def add_document(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]],
        company_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Store document chunks and their embeddings in the database.

        SECURITY (BC-001): company_id is stored as a first-class column
        on every INSERT to enforce tenant isolation.
        """
        # ── SAFETY ASSERTION: prevent unscoped writes ──────────────
        if not company_id or not isinstance(company_id, str) or not company_id.strip():
            raise ValueError(
                "SECURITY: PgVectorStore.add_document() requires a non-empty "
                "company_id to prevent cross-tenant data leakage. "
                f"Received: {company_id!r}"
            )

        from sqlalchemy import create_engine, text
        from app.core.config import get_settings

        settings = get_settings()
        engine = create_engine(settings.DATABASE_URL)

        try:
            with engine.begin() as conn:
                for i, chunk in enumerate(chunks):
                    chunk_id = chunk.get("chunk_id", f"{document_id}_{i}")
                    embedding = chunk.get("embedding")
                    conn.execute(
                        text("""
                            INSERT INTO document_chunks
                                (id, document_id, chunk_index, content, embedding, company_id)
                            VALUES
                                (:id, :document_id, :chunk_index, :content, :embedding, :company_id)
                            ON CONFLICT (id) DO UPDATE SET
                                embedding = EXCLUDED.embedding,
                                content = EXCLUDED.content,
                                company_id = EXCLUDED.company_id
                        """),
                        {
                            "id": chunk_id,
                            "document_id": document_id,
                            "chunk_index": chunk.get("chunk_index", i),
                            "content": chunk.get("content", ""),
                            "embedding": str(embedding) if embedding else None,
                            "company_id": company_id,  # BC-001: first-class column
                        },
                    )
            return True
        except Exception as exc:
            logger.warning("PgVectorStore add_document failed: %s", exc)
            return False
        finally:
            engine.dispose()

    def search(
        self,
        query_embedding: List[float],
        company_id: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """Find similar documents using cosine similarity.

        SECURITY (BC-001): Results are strictly scoped to *company_id*
        via a proper column filter.  A safety assertion raises if
        company_id is None or empty, preventing accidental unscoped queries.
        """
        # ── SAFETY ASSERTION: prevent unscoped queries ─────────────
        if not company_id or not isinstance(company_id, str) or not company_id.strip():
            raise ValueError(
                "SECURITY: PgVectorStore.search() requires a non-empty "
                "company_id to prevent cross-tenant data leakage. "
                f"Received: {company_id!r}"
            )

        from sqlalchemy import create_engine, text
        from app.core.config import get_settings

        settings = get_settings()
        engine = create_engine(settings.DATABASE_URL)

        query_sql = """
            SELECT id, document_id, chunk_index, content,
                   1 - (embedding <=> :query_embedding::vector) AS similarity
            FROM document_chunks
            WHERE embedding IS NOT NULL
              AND company_id = :company_id
        """
        params: Dict[str, Any] = {
            "query_embedding": str(query_embedding),
            "company_id": company_id,  # BC-001: proper column filter
            "limit": top_k,
        }

        query_sql += " ORDER BY embedding <=> :query_embedding::vector LIMIT :limit"

        results: List[SearchResult] = []
        try:
            with engine.connect() as conn:
                rows = conn.execute(text(query_sql), params).fetchall()
                for row in rows:
                    results.append(SearchResult(
                        chunk_id=str(row[0]),
                        document_id=str(row[1]) if row[1] else "",
                        content=row[3] or "",
                        score=float(row[4]),
                        metadata={},
                    ))
        except Exception as exc:
            logger.warning("PgVectorStore search failed: %s", exc)
        finally:
            engine.dispose()

        return results

    def delete_document(self, document_id: str, company_id: str) -> bool:
        """Delete all chunks for a document.

        SECURITY (BC-001): Deletion is scoped to both *document_id* AND
        *company_id* to prevent cross-tenant deletion.  A safety assertion
        raises if company_id is None or empty.
        """
        # ── SAFETY ASSERTION: prevent unscoped deletes ─────────────
        if not company_id or not isinstance(company_id, str) or not company_id.strip():
            raise ValueError(
                "SECURITY: PgVectorStore.delete_document() requires a non-empty "
                "company_id to prevent cross-tenant data deletion. "
                f"Received: {company_id!r}"
            )

        from sqlalchemy import create_engine, text
        from app.core.config import get_settings

        settings = get_settings()
        engine = create_engine(settings.DATABASE_URL)

        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "DELETE FROM document_chunks "
                        "WHERE document_id = :document_id "
                        "AND company_id = :company_id"  # BC-001: tenant-scoped delete
                    ),
                    {
                        "document_id": document_id,
                        "company_id": company_id,  # BC-001: prevents cross-tenant deletion
                    },
                )
            return True
        except Exception as exc:
            logger.warning("PgVectorStore delete_document failed: %s", exc)
            return False
        finally:
            engine.dispose()

    def get_all_documents(self, company_id: str) -> Dict[str, Any]:
        """Get all documents for a company from the vector store.

        SECURITY (BC-001): Strictly scoped to company_id.
        """
        if not company_id or not company_id.strip():
            return {}

        from sqlalchemy import create_engine, text
        from app.core.config import get_settings

        settings = get_settings()
        engine = create_engine(settings.DATABASE_URL)

        result: Dict[str, Any] = {}
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT document_id, id, chunk_index, content "
                        "FROM document_chunks "
                        "WHERE company_id = :company_id "
                        "ORDER BY document_id, chunk_index"
                    ),
                    {"company_id": company_id},
                ).fetchall()

                for row in rows:
                    doc_id = str(row[0])
                    if doc_id not in result:
                        result[doc_id] = {
                            "chunks": [],
                            "metadata": {},
                        }
                    result[doc_id]["chunks"].append({
                        "chunk_id": str(row[1]),
                        "chunk_index": row[2],
                        "content": row[3] or "",
                    })
        except Exception as exc:
            logger.warning("PgVectorStore get_all_documents failed: %s", exc)
        finally:
            engine.dispose()

        return result

    def get_document(
        self, document_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a single document and its chunks.

        SECURITY (BC-001): Strictly scoped to company_id.
        """
        if not company_id or not company_id.strip():
            return None

        from sqlalchemy import create_engine, text
        from app.core.config import get_settings

        settings = get_settings()
        engine = create_engine(settings.DATABASE_URL)

        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT id, chunk_index, content "
                        "FROM document_chunks "
                        "WHERE document_id = :document_id "
                        "AND company_id = :company_id "
                        "ORDER BY chunk_index"
                    ),
                    {"document_id": document_id, "company_id": company_id},
                ).fetchall()

                if not rows:
                    return None

                chunks = []
                for row in rows:
                    chunks.append({
                        "chunk_id": str(row[0]),
                        "chunk_index": row[1],
                        "content": row[2] or "",
                    })

                return {
                    "document_id": document_id,
                    "company_id": company_id,
                    "chunks": chunks,
                    "metadata": {},
                }
        except Exception as exc:
            logger.warning("PgVectorStore get_document failed: %s", exc)
            return None
        finally:
            engine.dispose()

    def health_check(self) -> bool:
        """Check if pgvector extension is available."""
        return self.is_available()

    def is_available(self) -> bool:
        """Check if pgvector extension is available."""
        try:
            from sqlalchemy import create_engine, text
            from app.core.config import get_settings

            settings = get_settings()
            engine = create_engine(settings.DATABASE_URL)

            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
                ).fetchone()

            engine.dispose()
            return result is not None
        except Exception:
            return False


# ── Factory ────────────────────────────────────────────────────────

_store_instance: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Return the appropriate VectorStore implementation.

    Priority:
    1. PgVectorStore if DATABASE_URL is set and pgvector is available
    2. MockVectorStore as safe fallback (BC-008)

    Thread-safe singleton pattern.

    NOTE: DATABASE_URL is resolved from ``app.config.get_settings()`` first
    (which reads ``.env`` files via pydantic-settings), then from
    ``os.environ`` as a secondary source.  This ensures that a PostgreSQL
    URL defined in ``.env`` is correctly detected even when it is not
    present in the raw environment.
    """
    global _store_instance
    if _store_instance is not None:
        return _store_instance

    # ── Resolve DATABASE_URL from settings first (covers .env file) ──
    database_url = ""
    try:
        from app.config import get_settings
        settings = get_settings()
        database_url = getattr(settings, "DATABASE_URL", "") or ""
    except Exception:
        # Settings unavailable — fall back to raw env var
        database_url = os.environ.get("DATABASE_URL", "")

    if not database_url:
        logger.info(
            "DATABASE_URL not configured — using MockVectorStore "
            "(no connection string available)"
        )
        _store_instance = MockVectorStore()
        logger.info("Using MockVectorStore for vector search (dev/fallback mode)")
        return _store_instance

    # ── Prefer PgVectorStore when a PostgreSQL URL is configured ────
    if "postgresql" in database_url.lower():
        try:
            pg_store = _create_pg_vector_store()
            if pg_store and pg_store.health_check():
                _store_instance = pg_store
                logger.info(
                    "Using PgVectorStore for vector search "
                    "(DATABASE_URL=%s)",
                    database_url.split("@")[-1] if "@" in database_url else "redacted",
                )
                return _store_instance
            else:
                logger.warning(
                    "PgVectorStore created but health_check failed — "
                    "falling back to MockVectorStore. "
                    "Ensure the pgvector extension is installed: "
                    "CREATE EXTENSION IF NOT EXISTS vector;"
                )
        except Exception as exc:
            logger.warning(
                "PgVectorStore unavailable, falling back to MockVectorStore: %s",
                exc,
            )
    else:
        logger.info(
            "DATABASE_URL is not PostgreSQL (%s) — using MockVectorStore",
            database_url.split("://")[0] if "://" in database_url else "unknown",
        )

    # ── Fallback: MockVectorStore (BC-008) ────────────────────────────
    _store_instance = MockVectorStore()
    logger.info("Using MockVectorStore for vector search (dev/fallback mode)")
    return _store_instance


def _create_pg_vector_store() -> Optional[VectorStore]:
    """Try to create a real PgVectorStore if pgvector is available."""
    try:
        store = PgVectorStore()
        if store.is_available():
            logger.info("PgVectorStore created — using real pgvector search")
            return store
        else:
            logger.warning("pgvector extension not found in database — MockVectorStore will be used")
            return None
    except Exception as exc:
        logger.warning("PgVectorStore creation failed: %s", exc)
        return None
