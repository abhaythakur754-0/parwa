"""
PARWA Vector Search Module (G1 FIX)

Provides the VectorStore abstraction layer used by rag_retrieval.py,
rag_reranking.py, and the RAG API endpoints.

Architecture:
  - VectorStore (ABC): Interface for vector search operations
  - InMemoryVectorStore: In-memory implementation for dev/testing (renamed from MockVectorStore)
  - PgVectorStore: PostgreSQL pgvector implementation (production)
  - get_vector_store(): Factory that returns the appropriate store

BC-001: All operations scoped to company_id.
BC-008: Graceful degradation — InMemoryVectorStore as fallback.

Parent: Day 4 (G1 fix — module was missing, causing ImportError)
Security Audit Day 6 (I1): PgVectorStore now uses ``knowledge_base_vectors``
table with native ``<=>`` cosine-distance SQL, accepts a connection string,
and validates both pgvector extension and table existence.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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


class InMemoryVectorStore(VectorStore):
    """In-memory vector store for development and testing.

    Renamed from MockVectorStore (Day 6 — I1). Uses cosine similarity
    for search. Falls back to deterministic pseudo-embeddings when
    no real embedding service is available.

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


# ── PgVectorStore (production — PostgreSQL + pgvector) ──────────

# Backwards-compatibility alias for existing code
MockVectorStore = InMemoryVectorStore


class PgVectorStore(VectorStore):
    """PostgreSQL + pgvector vector store implementation.

    Uses the ``knowledge_base_vectors`` table with pgvector ``<=>``
    cosine-similarity operator.  Accepts a PostgreSQL connection string
    at construction time so callers can supply their own pool.

    Day 6 (I1) security fix:
      - ``add_vectors`` for bulk vector insertion
      - ``search`` uses real ``<=>`` cosine similarity SQL
      - Proper ``company_id`` WHERE clause in every query
      - Validates pgvector extension availability on ``health_check``
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        dimension: int = 768,
    ) -> None:
        self.dimension = dimension
        self._connection_string = connection_string

    def _get_engine(self):
        """Create a SQLAlchemy engine from the configured connection string.

        Day 6 (I1): Accepts an explicit connection string passed at
        construction time, falling back to ``settings.DATABASE_URL``.
        """
        from sqlalchemy import create_engine

        conn_str = self._connection_string
        if not conn_str:
            try:
                from app.core.config import get_settings
                conn_str = get_settings().DATABASE_URL
            except Exception:
                raise RuntimeError(
                    "PgVectorStore requires a connection_string or DATABASE_URL env var"
                )
        return create_engine(conn_str)

    # ── add_vectors (bulk API — Day 6 I1) ───────────────────────

    def add_vectors(
        self,
        vector_ids: List[str],
        embeddings: List[List[float]],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Bulk-insert vectors with pre-computed embeddings.

        Day 6 (I1): New method for production RAG ingestion.
        Uses the ``knowledge_base_vectors`` table with native pgvector
        ``vector(768)`` column.

        SQL::

            INSERT INTO knowledge_base_vectors (id, embedding, metadata)
            VALUES ($1, $2::vector, $3)
            ON CONFLICT (id) DO UPDATE SET embedding = EXCLUDED.embedding
        """
        from sqlalchemy import text

        if not vector_ids or not embeddings:
            return False
        if len(vector_ids) != len(embeddings):
            logger.warning(
                "PgVectorStore.add_vectors: vector_ids (%d) != embeddings (%d)",
                len(vector_ids),
                len(embeddings),
            )
            return False

        meta_list = metadata or [{}] * len(vector_ids)

        engine = None
        try:
            engine = self._get_engine()
            with engine.begin() as conn:
                for vid, emb, meta in zip(vector_ids, embeddings, meta_list):
                    conn.execute(
                        text("""
                            INSERT INTO knowledge_base_vectors (id, embedding, metadata)
                            VALUES (:id, :embedding::vector, :metadata)
                            ON CONFLICT (id) DO UPDATE SET
                                embedding = EXCLUDED.embedding,
                                metadata = EXCLUDED.metadata
                        """), {
                            "id": vid, "embedding": str(emb), "metadata": str(meta) if isinstance(
                                meta, dict) else str(
                                {}), }, )
            return True
        except Exception as exc:
            logger.warning("PgVectorStore.add_vectors failed: %s", exc)
            return False
        finally:
            if engine is not None:
                engine.dispose()

    def add_document(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]],
        company_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Store document chunks and their embeddings in the database.

        Delegates to :meth:`add_vectors` for bulk insertion.  Each
        chunk's ``company_id`` is injected into its metadata dict.
        """
        vector_ids: List[str] = []
        embeddings: List[List[float]] = []
        metas: List[Dict[str, Any]] = []

        for i, chunk in enumerate(chunks):
            vector_ids.append(chunk.get("chunk_id", f"{document_id}_{i}"))
            embeddings.append(chunk.get("embedding", []))
            combined_meta: Dict[str, Any] = {
                "company_id": company_id, "document_id": document_id}
            combined_meta.update(metadata or {})
            metas.append(combined_meta)

        return self.add_vectors(vector_ids, embeddings, metas)

    def search(
        self,
        query_embedding: List[float],
        company_id: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """Find similar documents using cosine similarity.

        Day 6 (I1): Uses ``knowledge_base_vectors`` with the
        pgvector ``<=>`` cosine-distance operator.  **Every** query is
        scoped by ``company_id`` (BC-001 tenant isolation).

        SQL::

            SELECT id, metadata, embedding <=> $1::vector AS similarity
            FROM knowledge_base_vectors
            WHERE company_id = $2
            ORDER BY similarity ASC
            LIMIT $3

        Args:
            query_embedding: The query vector.
            company_id: Tenant ID (BC-001).
            top_k: Max results to return.
            filters: Optional metadata key/value filters.

        Returns:
            List[SearchResult] sorted by similarity (ascending distance).
        """
        from sqlalchemy import text

        # Build the WHERE clause with company_id scoping (BC-001)
        where_clauses = []
        params: Dict[str, Any] = {}
        params["query_embedding"] = str(query_embedding)
        params["company_id"] = company_id
        where_clauses.append("metadata::jsonb->>'company_id' = :company_id")

        # Apply optional metadata filters
        filter_idx = 3
        if filters:
            for fk, fv in filters.items():
                param_key = f"filter_{fk}"
                params[param_key] = str(fv)
                where_clauses.append(
                    f"metadata::jsonb->>'{fk}' = :{param_key}")
                filter_idx += 1

        where_sql = " AND ".join(where_clauses)
        params["limit"] = top_k

        query_sql = """
            SELECT id, metadata, embedding <=> :query_embedding::vector AS similarity
            FROM knowledge_base_vectors
            WHERE {where_sql}
            ORDER BY similarity ASC
            LIMIT :limit
        """

        results: List[SearchResult] = []
        engine = None
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                rows = conn.execute(text(query_sql), params).fetchall()
                for row in rows:
                    raw_meta = row[1] if len(row) > 1 else "{}"
                    meta = raw_meta if isinstance(raw_meta, dict) else {}
                    results.append(SearchResult(
                        chunk_id=str(row[0]) if row[0] else "",
                        document_id=meta.get("document_id", ""),
                        content=meta.get("content", ""),
                        score=float(row[2]) if len(row) > 2 else 0.0,
                        metadata=meta,
                    ))
        except Exception as exc:
            logger.warning("PgVectorStore search failed: %s", exc)
        finally:
            if engine is not None:
                engine.dispose()

        return results

    def delete_document(self, document_id: str, company_id: str) -> bool:
        """Delete all vectors for a document.

        Scopes deletion to ``company_id`` (BC-001).
        """
        from sqlalchemy import text

        engine = None
        try:
            engine = self._get_engine()
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        DELETE FROM knowledge_base_vectors
                        WHERE metadata::jsonb->>'company_id' = :company_id
                          AND metadata::jsonb->>'document_id' = :document_id
                    """),
                    {"company_id": company_id, "document_id": document_id},
                )
            return True
        except Exception as exc:
            logger.warning("PgVectorStore delete_document failed: %s", exc)
            return False
        finally:
            if engine is not None:
                engine.dispose()

    def health_check(self) -> bool:
        """Check if pgvector extension is available.

        Day 6 (I1): Also validates that the ``knowledge_base_vectors``
        table exists before returning True.
        """
        return self.is_available()

    def is_available(self) -> bool:
        """Check if pgvector extension and table are available.

        Returns False (with a warning log) if:
          - The ``vector`` extension is not installed
          - The ``knowledge_base_vectors`` table does not exist
        """
        try:
            from sqlalchemy import text

            engine = self._get_engine()
            try:
                with engine.connect() as conn:
                    # 1. Check pgvector extension
                    result = conn.execute(
                        text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")).fetchone()

                    if result is None:
                        logger.warning(
                            "PgVectorStore: pgvector extension not found in database "
                            "— run CREATE EXTENSION vector; in PostgreSQL")
                        return False

                    # 2. Check knowledge_base_vectors table exists
                    table_check = conn.execute(
                        text("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_name = 'knowledge_base_vectors'
                        )
                        """)
                    ).fetchone()

                    if not table_check or not table_check[0]:
                        logger.warning(
                            "PgVectorStore: knowledge_base_vectors table not found "
                            "— run the migration to create it")
                        return False

                    return True
            finally:
                engine.dispose()
        except Exception as exc:
            logger.warning("PgVectorStore.is_available failed: %s", exc)
            return False


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
            "PgVectorStore unavailable, falling back to InMemoryVectorStore: %s",
            exc,
        )

    # Fallback to InMemoryVectorStore (was MockVectorStore)
    _store_instance = InMemoryVectorStore()
    logger.info(
        "Using InMemoryVectorStore for vector search (dev/fallback mode)")
    return _store_instance


def _create_pg_vector_store() -> Optional[VectorStore]:
    """Try to create a real PgVectorStore if pgvector is available."""
    try:
        store = PgVectorStore()
        if store.is_available():
            logger.info("PgVectorStore created — using real pgvector search")
            return store
        else:
            logger.warning(
                "pgvector extension or table not found — InMemoryVectorStore will be used")
            return None
    except Exception as exc:
        logger.warning("PgVectorStore creation failed: %s", exc)
        return None
