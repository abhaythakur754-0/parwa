"""
Day 6 Security Audit Tests — AI Pipeline & RAG Fix

Tests for:
  I1: PgVectorStore and InMemoryVectorStore
  - add_document, search, delete_document, health_check
  - Tenant isolation (BC-001)
  - Cosine similarity search ranking
  - PgVectorStore SQL structure validation (without real DB)

Run:
  cd /home/z/parwa && python -m pytest backend/app/tests/test_day6_security.py -v
"""

from __future__ import annotations

import importlib
import math
import os
import sys
import pytest
from typing import List, Dict, Any

# Import vector_search.py by manipulating sys.path so that
# "app.shared.knowledge_base.vector_search" resolves to the file
# directly, bypassing __init__.py which pulls in sqlalchemy.
#
# IMPORTANT: We must NOT poison the "app" top-level namespace.
# If a real `app` module already exists in sys.modules, reuse it.
# Otherwise create a stub that still points to the real app dir
# so that other submodules (app.core, app.middleware, etc.) remain
# importable for sibling test files.

import types as _types

_kb_dir = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "shared", "knowledge_base"),
)
_app_dir = os.path.normpath(
    os.path.join(os.path.dirname(__file__), ".."),
)
_shared_dir = os.path.join(_app_dir, "shared")

# Ensure the top-level "app" module exists with the REAL __path__
if "app" in sys.modules and hasattr(sys.modules["app"], "__path__"):
    _pkg_app = sys.modules["app"]
else:
    _pkg_app = _types.ModuleType("app")
    _pkg_app.__path__ = [_app_dir]
    _pkg_app.__package__ = "app"
    sys.modules["app"] = _pkg_app

# Ensure "app.shared" exists
if "app.shared" in sys.modules and hasattr(
        sys.modules["app.shared"], "__path__"):
    _pkg_shared = sys.modules["app.shared"]
else:
    _pkg_shared = _types.ModuleType("app.shared")
    _pkg_shared.__path__ = [_shared_dir]
    _pkg_shared.__package__ = "app.shared"
    sys.modules["app.shared"] = _pkg_shared

# Ensure "app.shared.knowledge_base" exists (empty package to
# bypass __init__.py which imports sqlalchemy)
if "app.shared.knowledge_base" in sys.modules and hasattr(
        sys.modules["app.shared.knowledge_base"], "__path__"):
    _pkg_kb = sys.modules["app.shared.knowledge_base"]
else:
    _pkg_kb = _types.ModuleType("app.shared.knowledge_base")
    _pkg_kb.__path__ = [_kb_dir]
    _pkg_kb.__package__ = "app.shared.knowledge_base"
    sys.modules["app.shared.knowledge_base"] = _pkg_kb

# Register a spec so import machinery finds our module
_vs_path = os.path.join(_kb_dir, "vector_search.py")
if "app.shared.knowledge_base.vector_search" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "app.shared.knowledge_base.vector_search", _vs_path,
    )
    assert _spec is not None and _spec.loader is not None
    _vs_mod = importlib.util.module_from_spec(_spec)
    _vs_mod.__package__ = "app.shared.knowledge_base"
    _vs_mod.__file__ = _vs_path
    sys.modules["app.shared.knowledge_base.vector_search"] = _vs_mod
    _spec.loader.exec_module(_vs_mod)
else:
    _vs_mod = sys.modules["app.shared.knowledge_base.vector_search"]

InMemoryVectorStore = _vs_mod.InMemoryVectorStore
MockVectorStore = _vs_mod.MockVectorStore
PgVectorStore = _vs_mod.PgVectorStore
VectorStore = _vs_mod.VectorStore
VectorChunk = _vs_mod.VectorChunk
SearchResult = _vs_mod.SearchResult
EMBEDDING_DIMENSION = _vs_mod.EMBEDDING_DIMENSION


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════


def _make_unit_vector(seed: int = 42, dim: int = 768) -> List[float]:
    """Generate a deterministic pseudo-random unit vector for testing."""
    import hashlib
    text = f"seed-{seed}-test-vector"
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vec: List[float] = []
    for i in range(dim):
        byte_idx = i % len(h)
        val = (h[byte_idx] / 127.5) - 1.0
        vec.append(val)
    magnitude = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / magnitude for v in vec]


def _sample_chunks(count: int = 5) -> List[Dict[str, Any]]:
    """Generate sample document chunks for testing."""
    chunks = []
    for i in range(count):
        chunks.append({
            "chunk_id": f"chunk_{i}",
            "content": f"This is sample content chunk number {i} about topic area.",
            "metadata": {"section": f"section_{i % 3}", "index": i},
        })
    return chunks


# ════════════════════════════════════════════════════════════════════
# InMemoryVectorStore Tests (I1)
# ════════════════════════════════════════════════════════════════════


class TestInMemoryVectorStore:

    def test_instantiation(self):
        """InMemoryVectorStore can be created without arguments."""
        store = InMemoryVectorStore()
        assert store is not None
        assert store._store == {}

    def test_mockvectorstore_is_alias(self):
        """MockVectorStore is a backwards-compat alias for InMemoryVectorStore."""
        assert MockVectorStore is InMemoryVectorStore

    def test_is_subclass_of_vectorstore(self):
        """InMemoryVectorStore is a subclass of VectorStore ABC."""
        assert issubclass(InMemoryVectorStore, VectorStore)

    def test_add_document(self):
        """add_document stores chunks in memory."""
        store = InMemoryVectorStore()
        chunks = _sample_chunks(3)
        result = store.add_document(
            document_id="doc_1",
            chunks=chunks,
            company_id="co_123",
        )
        assert result is True
        assert "co_123" in store._store
        assert "doc_1" in store._store["co_123"]
        assert store._store["co_123"]["doc_1"]["chunks"] == chunks

    def test_add_document_with_metadata(self):
        """add_document stores document metadata."""
        store = InMemoryVectorStore()
        chunks = _sample_chunks(2)
        meta = {"source": "test", "version": 1}
        store.add_document(
            document_id="doc_meta",
            chunks=chunks,
            company_id="co_456",
            metadata=meta,
        )
        assert store._store["co_456"]["doc_meta"]["metadata"] == meta

    def test_search_returns_results(self):
        """search returns SearchResult objects sorted by score."""
        store = InMemoryVectorStore()
        chunks = _sample_chunks(5)
        store.add_document("doc_1", chunks, company_id="co_search")

        query_vec = _make_unit_vector(seed=99)
        results = store.search(
            query_embedding=query_vec,
            company_id="co_search",
            top_k=3,
        )
        assert isinstance(results, list)
        assert len(results) <= 3
        for r in results:
            assert isinstance(r, SearchResult)
            assert r.chunk_id != ""
            assert r.document_id == "doc_1"
            assert 0.0 <= r.score <= 1.0

    def test_search_results_sorted_descending(self):
        """Search results are sorted by score descending (highest first)."""
        store = InMemoryVectorStore()
        chunks = _sample_chunks(5)
        store.add_document("doc_1", chunks, company_id="co_sort")

        query_vec = _make_unit_vector(seed=77)
        results = store.search(query_vec, company_id="co_sort", top_k=10)
        if len(results) > 1:
            scores = [r.score for r in results]
            assert scores == sorted(scores, reverse=True)

    def test_search_tenant_isolation(self):
        """Search does not return results from other companies (BC-001)."""
        store = InMemoryVectorStore()
        chunks_a = _sample_chunks(3)
        chunks_b = [
            {"chunk_id": "b1", "content": "Company B data", "metadata": {}},
        ]
        store.add_document("doc_a", chunks_a, company_id="co_alpha")
        store.add_document("doc_b", chunks_b, company_id="co_beta")

        results = store.search(
            query_embedding=_make_unit_vector(1),
            company_id="co_alpha",
        )
        for r in results:
            assert r.document_id != "doc_b"

    def test_search_empty_company(self):
        """Search returns empty list for unknown company."""
        store = InMemoryVectorStore()
        results = store.search(
            query_embedding=_make_unit_vector(1),
            company_id="nonexistent",
        )
        assert results == []

    def test_search_with_filters(self):
        """Search applies metadata filters."""
        store = InMemoryVectorStore()
        chunks = [
            {"chunk_id": "c1", "content": "hello world", "metadata": {"section": "A"}},
            {"chunk_id": "c2", "content": "hello there", "metadata": {"section": "B"}},
            {"chunk_id": "c3", "content": "hello again", "metadata": {"section": "A"}},
        ]
        store.add_document("doc_f", chunks, company_id="co_filter")

        results = store.search(
            query_embedding=_make_unit_vector(1),
            company_id="co_filter",
            filters={"section": "B"},
        )
        # Should only return chunks with section == B
        for r in results:
            assert r.metadata.get("section") == "B"

    def test_delete_document(self):
        """delete_document removes a document from the store."""
        store = InMemoryVectorStore()
        store.add_document("doc_del", _sample_chunks(3), company_id="co_del")
        assert "doc_del" in store._store.get("co_del", {})

        result = store.delete_document("doc_del", company_id="co_del")
        assert result is True
        assert "doc_del" not in store._store["co_del"]

    def test_delete_document_missing(self):
        """delete_document returns True even if document doesn't exist."""
        store = InMemoryVectorStore()
        result = store.delete_document("nonexistent", company_id="co_del")
        assert result is True  # BC-008: never crash

    def test_delete_wrong_company(self):
        """delete_document only removes from the specified company."""
        store = InMemoryVectorStore()
        store.add_document("doc_cross", _sample_chunks(2), company_id="co_a")
        store.add_document("doc_cross", _sample_chunks(2), company_id="co_b")

        store.delete_document("doc_cross", company_id="co_a")
        assert "doc_cross" not in store._store["co_a"]
        assert "doc_cross" in store._store["co_b"]  # still exists for co_b

    def test_health_check(self):
        """health_check always returns True for InMemoryVectorStore."""
        store = InMemoryVectorStore()
        assert store.health_check() is True

    def test_get_all_documents(self):
        """get_all_documents returns dict of all docs for a company."""
        store = InMemoryVectorStore()
        store.add_document("doc_1", _sample_chunks(2), company_id="co_all")
        store.add_document("doc_2", _sample_chunks(1), company_id="co_all")

        docs = store.get_all_documents("co_all")
        assert isinstance(docs, dict)
        assert "doc_1" in docs
        assert "doc_2" in docs

    def test_get_all_documents_empty(self):
        """get_all_documents returns empty dict for unknown company."""
        store = InMemoryVectorStore()
        docs = store.get_all_documents("nonexistent")
        assert docs == {}

    def test_multiple_companies(self):
        """Documents from multiple companies are isolated."""
        store = InMemoryVectorStore()
        store.add_document("shared_name",
                           [{"chunk_id": "a1",
                             "content": "A data",
                             "metadata": {}}],
                           company_id="co_1")
        store.add_document("shared_name",
                           [{"chunk_id": "b1",
                             "content": "B data",
                             "metadata": {}}],
                           company_id="co_2")

        results_a = store.search(_make_unit_vector(1), company_id="co_1")
        results_b = store.search(_make_unit_vector(1), company_id="co_2")

        # Each company should only see its own data
        for r in results_a:
            assert "A data" in r.content
        for r in results_b:
            assert "B data" in r.content

    def test_cosine_similarity_identical_vectors(self):
        """Cosine similarity of identical vectors should be ~1.0."""
        vec = _make_unit_vector(42)
        score = InMemoryVectorStore._cosine_similarity(vec, vec)
        assert abs(score - 1.0) < 0.001

    def test_cosine_similarity_orthogonal_vectors(self):
        """Cosine similarity of orthogonal vectors should be ~0.0."""
        # Create two orthogonal vectors manually
        a = [1.0] + [0.0] * 767
        b = [0.0, 1.0] + [0.0] * 766
        score = InMemoryVectorStore._cosine_similarity(a, b)
        assert abs(score - 0.0) < 0.001

    def test_cosine_similarity_empty_vectors(self):
        """Cosine similarity returns 0.0 for empty vectors."""
        assert InMemoryVectorStore._cosine_similarity([], [1, 2]) == 0.0
        assert InMemoryVectorStore._cosine_similarity([1, 2], []) == 0.0
        assert InMemoryVectorStore._cosine_similarity([], []) == 0.0

    def test_cosine_similarity_dimension_mismatch(self):
        """Cosine similarity returns 0.0 for dimension mismatch."""
        assert InMemoryVectorStore._cosine_similarity([1, 2], [1]) == 0.0


# ════════════════════════════════════════════════════════════════════
# PgVectorStore Tests (I1) — no real DB required
# ════════════════════════════════════════════════════════════════════


class TestPgVectorStore:

    def test_instantiation(self):
        """PgVectorStore can be created with a connection string."""
        store = PgVectorStore(
            connection_string="postgresql://user:pass@localhost/testdb",
        )
        assert store is not None
        assert store._connection_string == "postgresql://user:pass@localhost/testdb"
        assert store.dimension == 768

    def test_instantiation_custom_dimension(self):
        """PgVectorStore accepts custom dimension."""
        store = PgVectorStore(dimension=1536)
        assert store.dimension == 1536

    def test_instantiation_no_connection_string(self):
        """PgVectorStore can be created without connection string."""
        store = PgVectorStore()
        assert store._connection_string is None

    def test_is_subclass_of_vectorstore(self):
        """PgVectorStore is a subclass of VectorStore ABC."""
        assert issubclass(PgVectorStore, VectorStore)

    def test_health_check_returns_false_without_db(self):
        """health_check returns False when no DB is available."""
        store = PgVectorStore()  # no connection string
        assert store.health_check() is False

    def test_is_available_returns_false_without_db(self):
        """is_available returns False when no DB is available."""
        store = PgVectorStore()
        assert store.is_available() is False

    def test_add_vectors_empty_lists(self):
        """add_vectors returns False for empty input lists."""
        store = PgVectorStore()
        assert store.add_vectors([], []) is False

    def test_add_vectors_mismatched_lengths(self):
        """add_vectors returns False when ids and embeddings length differ."""
        store = PgVectorStore()
        assert store.add_vectors(["id1"], [[1, 2], [3, 4]]) is False

    def test_add_document_delegates_to_add_vectors(self):
        """add_document builds vectors and delegates to add_vectors.

        Since we don't have a real DB, we verify the method runs
        and returns False (because add_vectors can't connect).
        """
        store = PgVectorStore()
        chunks = _sample_chunks(3)
        # Will fail to connect, but should not raise an exception
        result = store.add_document("doc_pg", chunks, company_id="co_pg")
        assert result is False  # No DB connection

    def test_search_returns_empty_without_db(self):
        """search returns empty list when no DB is available."""
        store = PgVectorStore()
        results = store.search(
            query_embedding=_make_unit_vector(1),
            company_id="co_pg",
        )
        assert results == []

    def test_delete_document_returns_false_without_db(self):
        """delete_document returns False when no DB is available."""
        store = PgVectorStore()
        result = store.delete_document("doc_pg", company_id="co_pg")
        assert result is False

    def test_get_engine_raises_without_db(self):
        """_get_engine raises RuntimeError when no connection string or env var."""
        store = PgVectorStore()  # no connection_string
        # Remove DATABASE_URL from env to ensure failure
        old_env = os.environ.pop("DATABASE_URL", None)
        try:
            with pytest.raises(RuntimeError, match="connection_string or DATABASE_URL"):
                store._get_engine()
        finally:
            if old_env is not None:
                os.environ["DATABASE_URL"] = old_env


# ════════════════════════════════════════════════════════════════════
# Data Class Tests
# ════════════════════════════════════════════════════════════════════


class TestDataClasses:

    def test_vector_chunk_defaults(self):
        """VectorChunk has correct defaults."""
        chunk = VectorChunk(
            chunk_id="c1",
            document_id="d1",
            content="test",
        )
        assert chunk.embedding is None
        assert chunk.metadata == {}
        assert chunk.company_id == ""

    def test_search_result_defaults(self):
        """SearchResult has correct defaults."""
        result = SearchResult(
            chunk_id="c1",
            document_id="d1",
            content="test",
            score=0.95,
        )
        assert result.metadata == {}
        assert result.score == 0.95

    def test_embedding_dimension_constant(self):
        """EMBEDDING_DIMENSION is set to Google AI embedding dimension."""
        assert EMBEDDING_DIMENSION == 768
