"""
Tests for the embedding helper + knowledge-base retriever.

Covers:
  1. No hardcoded API keys in source (security regression guard).
  2. Google is the primary embedding provider (per user directive).
  3. Empty / whitespace text returns None without crashing.
  4. Retriever falls back to ILIKE when embeddings are unavailable
     (BC-008 — never crash).
  5. Retriever is tenant-scoped (BC-001 — no cross-tenant leaks).

Run:  cd backend && python3 -m pytest ../tests/test_embedding_and_retriever.py -v --noconftest
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── 1. Security: no hardcoded API keys ─────────────────────────────────────

def test_no_hardcoded_nvidia_key():
    """The leaked NVIDIA key must be gone — env var only."""
    from app.core.parwa_pipeline import nvidia_embedding as emb

    # The module-level NVIDIA_API_KEY must come from os.environ, not a default.
    # In the test env, NVIDIA_API_KEY is unset → should be empty string.
    assert emb.NVIDIA_API_KEY == os.environ.get("NVIDIA_API_KEY", ""), (
        "NVIDIA_API_KEY has a hardcoded default — security leak"
    )
    # The known-leaked key prefix must NOT appear anywhere in the source.
    source = Path(emb.__file__).read_text()
    assert "nvapi-mYdaofMi6jRs" not in source, "Leaked NVIDIA key still in source"


def test_no_hardcoded_google_key():
    """Google API key must also be env-only."""
    from app.core.parwa_pipeline import nvidia_embedding as emb

    # The module should not have a GOOGLE_AI_API_KEY module-level var with a default.
    assert not hasattr(emb, "GOOGLE_AI_API_KEY") or emb.GOOGLE_AI_API_KEY in (
        os.environ.get("GOOGLE_AI_API_KEY", ""),
        os.environ.get("GEMINI_API_KEY", ""),
        "",
    )


# ── 2. Google is primary ───────────────────────────────────────────────────

def test_google_is_primary_embedding_dimension():
    """EMBEDDING_DIMENSION must be 768 (Google), not 1024 (NVIDIA)."""
    from app.core.parwa_pipeline.nvidia_embedding import (
        EMBEDDING_DIMENSION,
        GOOGLE_EMBEDDING_DIMENSION,
    )

    assert GOOGLE_EMBEDDING_DIMENSION == 768
    assert EMBEDDING_DIMENSION == 768, (
        f"Expected Google's 768-dim as primary, got {EMBEDDING_DIMENSION}"
    )


def test_embed_text_sync_tries_google_first(monkeypatch):
    """embed_text_sync must call Google before NVIDIA."""
    from app.core.parwa_pipeline import nvidia_embedding as emb

    call_order = []

    def fake_google(text, input_type):
        call_order.append("google")
        return [0.1] * 768  # success → NVIDIA should never be called

    def fake_nvidia(text, input_type):
        call_order.append("nvidia")
        return [0.2] * 1024

    monkeypatch.setattr(emb, "_embed_google_sync", fake_google)
    monkeypatch.setattr(emb, "_embed_nvidia_sync", fake_nvidia)

    result = emb.embed_text_sync("test query")
    assert result == [0.1] * 768
    assert call_order == ["google"], (
        f"Google must be tried first; got order: {call_order}"
    )


def test_embed_text_sync_falls_back_to_nvidia(monkeypatch):
    """If Google fails, NVIDIA is tried."""
    from app.core.parwa_pipeline import nvidia_embedding as emb

    call_order = []

    monkeypatch.setattr(emb, "_embed_google_sync", lambda t, i: (call_order.append("google") or None))
    monkeypatch.setattr(emb, "_embed_nvidia_sync", lambda t, i: (call_order.append("nvidia") or [0.3] * 1024))

    result = emb.embed_text_sync("test query")
    assert result == [0.3] * 1024
    assert call_order == ["google", "nvidia"]


# ── 3. Empty input handling (BC-008) ───────────────────────────────────────

def test_embed_text_sync_empty_returns_none():
    from app.core.parwa_pipeline.nvidia_embedding import embed_text_sync

    assert embed_text_sync("") is None
    assert embed_text_sync("   ") is None
    assert embed_text_sync(None) is None  # type: ignore[arg-type]


# ── 4. Retriever ILIKE fallback (BC-008) ───────────────────────────────────

def test_retriever_returns_empty_for_empty_query():
    """An empty query must return [] without hitting the DB."""
    from app.shared.knowledge_base.retriever import KnowledgeRetriever

    # Pass a mock session — it should never be used for an empty query.
    retriever = KnowledgeRetriever(db=MagicMock(), company_id="comp-1")
    assert retriever.search("") == []
    assert retriever.search("   ") == []


def test_retriever_falls_back_to_ilike_when_embedding_fails(monkeypatch):
    """When embed_text_sync returns None, the retriever must use ILIKE, not crash."""
    from app.shared.knowledge_base import retriever as retriever_mod
    from app.shared.knowledge_base.retriever import KnowledgeRetriever

    # Force the embedding to fail.
    monkeypatch.setattr(
        "app.core.parwa_pipeline.nvidia_embedding.embed_text_sync",
        lambda text, input_type="query": None,
    )

    # Mock the DB session so the ILIKE path returns a fake chunk.
    fake_chunk = MagicMock()
    fake_chunk.id = "chunk-1"
    fake_chunk.content = "To reset your password, click forgot password."
    fake_chunk.document_id = "doc-1"
    fake_chunk.chunk_index = 0

    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_join = MagicMock()
    mock_filter = MagicMock()
    mock_order = MagicMock()
    mock_limit = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.join.return_value = mock_join
    mock_join.filter.return_value = mock_filter
    mock_filter.filter.return_value = mock_filter
    mock_filter.order_by.return_value = mock_order
    mock_order.limit.return_value = mock_limit
    mock_limit.all.return_value = [(fake_chunk, "faq.md", "general")]

    retriever = KnowledgeRetriever(db=mock_db, company_id="comp-1")
    results = retriever.search("password reset")

    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk-1"
    assert "password" in results[0]["content"].lower()


# ── 5. Tenant scoping (BC-001) ─────────────────────────────────────────────

def test_retriever_search_is_tenant_scoped(monkeypatch):
    """The ILIKE fallback must filter by company_id (no cross-tenant leaks)."""
    from app.shared.knowledge_base.retriever import KnowledgeRetriever

    # Force embedding failure → ILIKE path.
    monkeypatch.setattr(
        "app.core.parwa_pipeline.nvidia_embedding.embed_text_sync",
        lambda text, input_type="query": None,
    )

    captured_filters = []

    class CapturingQuery:
        def __init__(self):
            self._filters = []

        def join(self, *a, **k):
            return self

        def filter(self, *conditions):
            # Record the filter conditions so we can assert company_id is among them.
            for c in conditions:
                captured_filters.append(str(c))
            return self

        def order_by(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

        def all(self):
            return []

    mock_db = MagicMock()
    mock_db.query.return_value = CapturingQuery()

    retriever = KnowledgeRetriever(db=mock_db, company_id="comp-secret-123")
    retriever.search("anything")

    # At least one filter must reference the company_id column.
    assert any("company_id" in f for f in captured_filters), (
        f"No company_id filter found in: {captured_filters}"
    )


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v", "--noconftest"]))
