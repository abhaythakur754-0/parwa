"""
Vector Search Module — Abstract & Mock Implementations

Provides the VectorStore interface and MockVectorStore for testing/development.
Production implementations (Pinecone, Weaviate, Qdrant) will implement VectorStore.

Part of the shared knowledge base infrastructure used by RAG retrieval (F-064).

BC-001: Tenant isolation — all operations scoped to company_id.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ── Optional PgVector dependencies (graceful degradation) ─────────
try:
    from sqlalchemy import text
    _HAS_SQLALCHEMY = True
except ImportError:
    _HAS_SQLALCHEMY = False
    text = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

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


# ── PgVector Store ───────────────────────────────────────────────


class PgVectorStore(VectorStore):
    """PostgreSQL pgvector-backed vector store.

    Uses real semantic embeddings stored in PostgreSQL with the pgvector
    extension for fast approximate nearest-neighbour cosine-similarity
    search.

    Every query is scoped to ``company_id`` (BC-001).  All database
    operations are wrapped in ``try/except`` so that transient failures
    are reported but never bubble up (BC-008).
    """

    def __init__(self, connection_string: Optional[str] = None) -> None:
        """Initialise the PgVectorStore.

        Args:
            connection_string: Optional PostgreSQL URL.  When *None*,
                the connection is obtained from
                :func:`database.base.get_db` or the ``DATABASE_URL``
                environment variable.
        """
        self._connection_string = connection_string
        self._engine = None
        self._session_factory = None
        self._init_db()

    # ── Internal: engine / session setup ───────────────────────────

    def _init_db(self) -> None:
        """Create a SQLAlchemy engine and session factory."""
        try:
            if not _HAS_SQLALCHEMY:
                logger.warning(
                    "PgVectorStore: sqlalchemy not available — "
                    "operations will fail gracefully"
                )
                return

            if self._connection_string:
                url = self._connection_string
            else:
                # Try the shared database module first
                try:
                    from database.base import SessionLocal  # type: ignore[import-untyped]
                    self._session_factory = SessionLocal
                    logger.debug("PgVectorStore: using database.base.SessionLocal")
                    return
                except Exception:
                    pass

                url = os.environ.get(
                    "DATABASE_URL",
                    "postgresql://localhost:5432/parwa",
                )

            from sqlalchemy import create_engine  # type: ignore[import-untyped]
            self._engine = create_engine(url, pool_pre_ping=True)
            from sqlalchemy.orm import sessionmaker  # type: ignore[import-untyped]
            self._session_factory = sessionmaker(
                bind=self._engine,
                autocommit=False,
                autoflush=False,
            )
            logger.debug("PgVectorStore: engine created from connection string")
        except Exception as exc:
            logger.error(
                "PgVectorStore._init_db failed: %s", exc,
            )

    def _get_session(self):
        """Return a new DB session, or *None* on failure."""
        if self._session_factory is None:
            return None
        try:
            return self._session_factory()
        except Exception as exc:
            logger.error("PgVectorStore: cannot create session: %s", exc)
            return None

    # ── VectorStore interface ──────────────────────────────────────

    def search(
        self,
        query_embedding: List[float],
        company_id: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        similarity_threshold: float = 0.3,
    ) -> List[SearchResult]:
        """Search for similar chunks via pgvector cosine similarity.

        Uses the ``<=>`` (cosine distance) operator provided by the
        ``pgvector`` extension and converts it to a similarity score
        (``1 - distance``).  Results are filtered by ``company_id``
        (BC-001) and optionally by ``similarity_threshold``.

        Args:
            query_embedding: Query vector.
            company_id: Tenant identifier (BC-001).
            top_k: Maximum results to return.
            filters: Optional metadata filters (JSONB containment).
            similarity_threshold: Minimum cosine similarity (default 0.3).

        Returns:
            List of search results sorted by score descending.
        """
        session = self._get_session()
        if session is None:
            return []

        try:
            embedding_str = _embedding_to_pgvector_str(query_embedding)

            stmt = text(
                "SELECT chunk_id, document_id, content, "
                "       1 - (embedding <=> :embedding::vector) AS score, "
                "       metadata "
                "FROM document_chunks "
                "WHERE company_id = :company_id "
                "ORDER BY embedding <=> :embedding::vector "
                "LIMIT :limit"
            )
            params: Dict[str, Any] = {
                "embedding": embedding_str,
                "company_id": company_id,
                "limit": top_k,
            }

            row = session.execute(stmt, params).fetchall()

            results: List[SearchResult] = []
            for r in row:
                chunk_id = r[0]
                document_id = r[1]
                content = r[2]
                score = float(r[3]) if r[3] is not None else 0.0
                metadata_raw = r[4]

                if score < similarity_threshold:
                    continue

                # Parse metadata from JSONB / text
                metadata: Dict[str, Any] = {}
                if metadata_raw is not None:
                    if isinstance(metadata_raw, dict):
                        metadata = metadata_raw
                    elif isinstance(metadata_raw, str):
                        try:
                            metadata = json.loads(metadata_raw)
                        except (json.JSONDecodeError, TypeError):
                            metadata = {}

                # Apply optional Python-level metadata filters
                if filters and not self._matches_filters(metadata, filters):
                    continue

                results.append(
                    SearchResult(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        content=content,
                        score=round(score, 6),
                        metadata=metadata,
                    )
                )

            return results

        except Exception as exc:
            logger.error(
                "PgVectorStore.search failed [company_id=%s]: %s",
                company_id, exc,
            )
            return []
        finally:
            self._close_session(session)

    def add_chunks(
        self,
        chunks: List[StoredChunk],
        company_id: str,
    ) -> int:
        """Insert chunks into ``document_chunks`` with pgvector embeddings.

        Each chunk's ``embedding`` list is serialised as a pgvector literal.

        Args:
            chunks: List of chunks with embeddings.
            company_id: Tenant identifier (BC-001).

        Returns:
            Number of chunks successfully added.
        """
        session = self._get_session()
        if session is None:
            return 0

        try:
            added = 0
            for chunk in chunks:
                embedding_str = _embedding_to_pgvector_str(chunk.embedding)
                metadata_json = json.dumps(chunk.metadata) if chunk.metadata else None

                stmt = text(
                    "INSERT INTO document_chunks "
                    "  (id, document_id, company_id, content, embedding, "
                    "   metadata, chunk_index) "
                    "VALUES "
                    "  (:id, :document_id, :company_id, :content, "
                    "   :embedding::vector, :metadata::jsonb, :chunk_index) "
                    "ON CONFLICT (id) DO UPDATE SET "
                    "  content = EXCLUDED.content, "
                    "  embedding = EXCLUDED.embedding, "
                    "  metadata = EXCLUDED.metadata"
                )
                session.execute(stmt, {
                    "id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "company_id": company_id,
                    "content": chunk.content,
                    "embedding": embedding_str,
                    "metadata": metadata_json,
                    "chunk_index": 0,
                })
                added += 1

            session.commit()
            return added

        except Exception as exc:
            logger.error(
                "PgVectorStore.add_chunks failed [company_id=%s]: %s",
                company_id, exc,
            )
            try:
                session.rollback()
            except Exception:
                pass
            return 0
        finally:
            self._close_session(session)

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
            True if rows were deleted, False otherwise.
        """
        session = self._get_session()
        if session is None:
            return False

        try:
            stmt = text(
                "DELETE FROM document_chunks "
                "WHERE document_id = :document_id "
                "  AND company_id = :company_id"
            )
            result = session.execute(stmt, {
                "document_id": document_id,
                "company_id": company_id,
            })
            session.commit()
            return result.rowcount > 0

        except Exception as exc:
            logger.error(
                "PgVectorStore.delete_document failed "
                "[document_id=%s, company_id=%s]: %s",
                document_id, company_id, exc,
            )
            try:
                session.rollback()
            except Exception:
                pass
            return False
        finally:
            self._close_session(session)

    def add_document(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]],
        company_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Add a document with chunk dicts — generates embeddings via EmbeddingService."""
        doc_metadata = metadata or {}
        stored_chunks: List[StoredChunk] = []
        for i, chunk in enumerate(chunks):
            content = chunk["content"]
            chunk_meta = chunk.get("metadata", {})
            merged_metadata: Dict[str, Any] = {**doc_metadata, **chunk_meta}
            # Generate real embedding via EmbeddingService
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
        added = self.add_chunks(stored_chunks, company_id)
        return added > 0

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text via EmbeddingService."""
        try:
            from app.services.embedding_service import EmbeddingService
            svc = EmbeddingService(company_id="system")
            result = svc.generate_embedding(text)
            if result:
                return result
        except Exception as exc:
            logger.warning("PgVectorStore._generate_embedding failed: %s", exc)
        # Fallback: return zero vector of correct dimension
        return [0.0] * EMBEDDING_DIMENSION

    def get_document(self, document_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a stored document as a dict."""
        session = self._get_session()
        if session is None:
            return None
        try:
            stmt = text(
                "SELECT chunk_id, document_id, content, metadata "
                "FROM document_chunks "
                "WHERE document_id = :document_id AND company_id = :company_id "
                "ORDER BY chunk_index"
            )
            rows = session.execute(stmt, {"document_id": document_id, "company_id": company_id}).fetchall()
            if not rows:
                return None
            chunks = []
            for r in rows:
                meta = r[3]
                if isinstance(meta, str):
                    try: meta = json.loads(meta)
                    except: meta = {}
                chunks.append({"chunk_id": r[0], "document_id": r[1], "content": r[2], "metadata": meta or {}})
            return {
                "document_id": document_id,
                "company_id": company_id,
                "metadata": {},
                "chunks": chunks,
            }
        except Exception as exc:
            logger.error("PgVectorStore.get_document failed: %s", exc)
            return None
        finally:
            self._close_session(session)

    def document_count(self, company_id: str) -> int:
        """Return the number of documents for a company."""
        session = self._get_session()
        if session is None:
            return 0
        try:
            stmt = text("SELECT COUNT(DISTINCT document_id) FROM document_chunks WHERE company_id = :company_id")
            row = session.execute(stmt, {"company_id": company_id}).fetchone()
            return row[0] if row else 0
        except Exception:
            return 0
        finally:
            self._close_session(session)

    def get_all_documents(self, company_id: str) -> Dict[str, Dict[str, Any]]:
        """Get all documents for a company (for keyword search fallback)."""
        session = self._get_session()
        if session is None:
            return {}
        try:
            stmt = text(
                "SELECT document_id, chunk_id, content, metadata "
                "FROM document_chunks WHERE company_id = :company_id"
            )
            rows = session.execute(stmt, {"company_id": company_id}).fetchall()
            result: Dict[str, Dict[str, Any]] = {}
            for r in rows:
                doc_id = r[0]
                if doc_id not in result:
                    result[doc_id] = {"metadata": {}, "chunks": []}
                meta = r[3]
                if isinstance(meta, str):
                    try: meta = json.loads(meta)
                    except: meta = {}
                result[doc_id]["chunks"].append({
                    "chunk_id": r[1], "content": r[2], "metadata": meta or {},
                })
            return result
        except Exception:
            return {}
        finally:
            self._close_session(session)

    def health_check(self) -> bool:
        """Verify pgvector extension is available and DB is reachable.

        Returns:
            True if the ``vector`` extension is installed and a test
            query succeeds, False otherwise.
        """
        session = self._get_session()
        if session is None:
            return False

        try:
            row = session.execute(
                text(
                    "SELECT extversion FROM pg_extension "
                    "WHERE extname = 'vector'"
                )
            ).fetchone()

            if row is None:
                logger.warning(
                    "PgVectorStore.health_check: pgvector extension not found"
                )
                return False

            logger.debug(
                "PgVectorStore.health_check: pgvector %s", row[0]
            )
            return True

        except Exception as exc:
            logger.error(
                "PgVectorStore.health_check failed: %s", exc
            )
            return False
        finally:
            self._close_session(session)

    # ── Internal helpers ───────────────────────────────────────────

    @staticmethod
    def _close_session(session: Any) -> None:
        """Safely close a DB session."""
        try:
            session.close()
        except Exception:
            pass

    @staticmethod
    def _matches_filters(
        metadata: Dict[str, Any],
        filters: Dict[str, Any],
    ) -> bool:
        """Check if *metadata* matches all *filters*.

        Supports:
        - Exact match: ``{"document_type": "faq"}``
        - Tag membership: ``{"tags": ["refund", "billing"]}``
        - Date range: ``{"date_after": "2024-01-01"}``
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
                if not meta_val or not any(
                    tag in value
                    for tag in (
                        meta_val if isinstance(meta_val, list)
                        else [meta_val]
                    )
                ):
                    return False
            else:
                if meta_val != value:
                    return False
        return True


# ── Helpers ───────────────────────────────────────────────────────


def _embedding_to_pgvector_str(embedding: List[float]) -> str:
    """Convert a list of floats to a pgvector literal string.

    Example:  ``[0.1, 0.2]`` -> ``'[0.1,0.2]'``
    """
    return "[" + ",".join(f"{x:.8g}" for x in embedding) + "]"


# ── Module-level Singleton & Convenience Function ──────────────────


_default_store: Optional[VectorStore] = None


def get_vector_store(force_mock: bool = False) -> VectorStore:
    """Get the appropriate vector store implementation.

    Resolution order:

    1. If ``force_mock`` is *True*, return a :class:`MockVectorStore`.
    2. In ``production`` or ``test`` environments, attempt to create a
       :class:`PgVectorStore` backed by PostgreSQL + pgvector.
    3. If PgVectorStore creation or its health-check fails, fall back
       to :class:`MockVectorStore` (BC-008).

    Returns:
        VectorStore instance (singleton).
    """
    global _default_store

    if _default_store is not None:
        return _default_store

    # Force mock mode — useful in tests or when no DB is available
    if force_mock:
        _default_store = MockVectorStore()
        return _default_store

    environment = os.getenv("ENVIRONMENT", "development")

    # In all environments, try PgVectorStore first
    if environment in ("production", "test", "development", "staging"):
        try:
            pg_store = PgVectorStore()
            if pg_store.health_check():
                logger.info(
                    "get_vector_store: using PgVectorStore (env=%s)",
                    environment,
                )
                _default_store = pg_store
                return _default_store
            else:
                logger.warning(
                    "get_vector_store: PgVectorStore health_check failed, "
                    "falling back to MockVectorStore (BC-008)"
                )
        except Exception as exc:
            logger.warning(
                "get_vector_store: PgVectorStore init failed (%s), "
                "falling back to MockVectorStore (BC-008)",
                exc,
            )

    # Default / fallback
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
