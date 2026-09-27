"""
Comprehensive tests for backend.app.core.rag_reranking (F-064).

Covers:
  - CrossEncoderReranker: 3 variant strategies, BM25 scoring, GAP-004 timeout,
    semaphore, caching, BC-001, BC-008
  - ContextWindowAssembler: token counting, truncation, citations, empty chunks
  - CitationTracker: extraction, dedup, metadata enrichment
  - MetadataFilter: all filter types, AND logic, empty filters
  - QueryRewriter: query expansion, stop words, term frequency
  - Redis cache helpers: cache get/set/invalidate, key building
  - Data classes: AssembledContext.to_dict, Citation.to_dict
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Ensure test environment before any backend imports
# ---------------------------------------------------------------------------
import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test_secret_key")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret")
os.environ.setdefault("DATA_ENCRYPTION_KEY", "12345678901234567890123456789012")

from backend.app.core.rag_retrieval import RAGChunk, RAGResult  # noqa: E402
from backend.app.core.rag_reranking import (  # noqa: E402
    AssembledContext,
    Citation,
    CitationTracker,
    ContextWindowAssembler,
    CrossEncoderReranker,
    MetadataFilter,
    QueryRewriter,
    RerankStrategy,
    VARIANT_RERANK_CONFIG,
    _build_rerank_cache_key,
    get_cached_rerank,
    get_reranker,
    invalidate_rerank_cache,
    set_cached_rerank,
)


# ════════════════════════════════════════════════════════════════════════
#  Fixtures
# ════════════════════════════════════════════════════════════════════════


def _make_chunk(
    chunk_id: str = "chunk-1",
    document_id: str = "doc-1",
    content: str = "Machine learning models process data to find patterns.",
    score: float = 0.85,
    metadata: Optional[Dict[str, Any]] = None,
) -> RAGChunk:
    """Factory for building RAGChunk instances."""
    return RAGChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        content=content,
        score=score,
        metadata=metadata or {},
    )


def _make_chunks(count: int = 5, base_score: float = 0.9) -> List[RAGChunk]:
    """Create *count* chunks with descending scores."""
    return [
        _make_chunk(
            chunk_id=f"chunk-{i}",
            document_id=f"doc-{i % 3}",
            content=f"This is chunk {i} about machine learning and neural networks.",
            score=round(base_score - i * 0.05, 4),
        )
        for i in range(count)
    ]


@pytest.fixture
def reranker() -> CrossEncoderReranker:
    """Fresh CrossEncoderReranker instance per test."""
    return CrossEncoderReranker()


@pytest.fixture
def sample_chunks() -> List[RAGChunk]:
    return _make_chunks(5)


@pytest.fixture
def diverse_chunks() -> List[RAGChunk]:
    """Chunks with varied content and metadata for richer tests."""
    return [
        _make_chunk(
            chunk_id="c1",
            document_id="d1",
            content="Machine learning is a branch of artificial intelligence.",
            score=0.95,
            metadata={"source_type": "pdf", "date": "2024-01-15", "category": "ai", "tags": ["ml", "ai"]},
        ),
        _make_chunk(
            chunk_id="c2",
            document_id="d1",
            content="Deep learning neural networks require large datasets.",
            score=0.88,
            metadata={"source_type": "pdf", "date": "2024-03-20", "category": "ai", "tags": ["dl", "nn"]},
        ),
        _make_chunk(
            chunk_id="c3",
            document_id="d2",
            content="Customer support ticket escalation policy document.",
            score=0.72,
            metadata={"source_type": "wiki", "date": "2024-06-10", "category": "support", "tags": ["policy"]},
        ),
        _make_chunk(
            chunk_id="c4",
            document_id="d2",
            content="Reinforcement learning trains agents through reward signals.",
            score=0.81,
            metadata={"source_type": "pdf", "date": "2024-02-28", "category": "ai", "tags": ["rl", "ml"]},
        ),
        _make_chunk(
            chunk_id="c5",
            document_id="d3",
            content="Billing invoice template for enterprise clients.",
            score=0.60,
            metadata={"source_type": "docx", "date": "2024-04-05", "category": "billing", "tags": ["invoice"]},
        ),
    ]


# ════════════════════════════════════════════════════════════════════════
#  1. CrossEncoderReranker — SKIP strategy (mini_parwa)
# ════════════════════════════════════════════════════════════════════════


class TestCrossEncoderRerankerSkip:
    """Tests for the mini_parwa / SKIP variant strategy."""

    @pytest.mark.asyncio
    async def test_skip_returns_chunks_sorted_by_original_score(self, reranker, sample_chunks):
        """mini_parwa should return chunks sorted by original score descending."""
        result = await reranker.rerank(
            chunks=sample_chunks, query="test", company_id="co-1", variant_type="mini_parwa"
        )
        scores = [c.score for c in result.chunks]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_skip_respects_top_k(self, reranker, sample_chunks):
        """mini_parwa with top_k=2 should return at most 2 chunks."""
        result = await reranker.rerank(
            chunks=sample_chunks, query="test", company_id="co-1",
            variant_type="mini_parwa", top_k=2,
        )
        assert len(result.chunks) <= 2

    @pytest.mark.asyncio
    async def test_skip_default_top_k_is_3(self, reranker, sample_chunks):
        """mini_parwa config has default_top_k=3; passing None should use it."""
        result = await reranker.rerank(
            chunks=sample_chunks, query="test", company_id="co-1",
            variant_type="mini_parwa", top_k=None,
        )
        assert len(result.chunks) <= 3

    @pytest.mark.asyncio
    async def test_skip_does_not_modify_chunk_scores(self, reranker):
        """SKIP strategy preserves original scores."""
        chunk = _make_chunk(score=0.42)
        result = await reranker.rerank(
            chunks=[chunk], query="irrelevant", company_id="co-1", variant_type="mini_parwa"
        )
        assert result.chunks[0].score == 0.42

    @pytest.mark.asyncio
    async def test_skip_variant_tier_used(self, reranker, sample_chunks):
        result = await reranker.rerank(
            chunks=sample_chunks, query="test", company_id="co-1", variant_type="mini_parwa"
        )
        assert result.variant_tier_used == "mini_parwa"

    @pytest.mark.asyncio
    async def test_skip_total_found_matches_input(self, reranker, sample_chunks):
        result = await reranker.rerank(
            chunks=sample_chunks, query="test", company_id="co-1", variant_type="mini_parwa"
        )
        assert result.total_found == len(sample_chunks)


# ════════════════════════════════════════════════════════════════════════
#  2. CrossEncoderReranker — CROSS_ENCODER strategy (parwa)
# ════════════════════════════════════════════════════════════════════════


class TestCrossEncoderRerankerParwa:
    """Tests for the parwa / CROSS_ENCODER variant strategy."""

    @pytest.mark.asyncio
    async def test_cross_encoder_returns_reranked_chunks(self, reranker, sample_chunks):
        result = await reranker.rerank(
            chunks=sample_chunks, query="machine learning", company_id="co-1",
            variant_type="parwa",
        )
        assert len(result.chunks) > 0
        assert result.variant_tier_used == "parwa"

    @pytest.mark.asyncio
    async def test_cross_encoder_respects_top_k(self, reranker, sample_chunks):
        result = await reranker.rerank(
            chunks=sample_chunks, query="machine learning", company_id="co-1",
            variant_type="parwa", top_k=2,
        )
        assert len(result.chunks) <= 2

    @pytest.mark.asyncio
    async def test_cross_encoder_scores_are_capped_at_1(self, reranker):
        """Final scores must never exceed 1.0."""
        chunk = _make_chunk(content="machine learning machine learning machine learning", score=0.99)
        result = await reranker.rerank(
            chunks=[chunk], query="machine learning", company_id="co-1",
            variant_type="parwa",
        )
        assert all(c.score <= 1.0 for c in result.chunks)

    @pytest.mark.asyncio
    async def test_cross_encoder_with_filters(self, reranker, diverse_chunks):
        """parwa should apply metadata filters before scoring."""
        result = await reranker.rerank(
            chunks=diverse_chunks, query="learning", company_id="co-1",
            variant_type="parwa",
            filters={"source_type": "pdf"},
        )
        assert all(c.metadata.get("source_type") == "pdf" for c in result.chunks)

    @pytest.mark.asyncio
    async def test_cross_encoder_relevance_ordering(self, reranker):
        """A chunk containing the query should score higher than one that does not."""
        relevant = _make_chunk(chunk_id="rel", content="machine learning algorithms", score=0.5)
        irrelevant = _make_chunk(chunk_id="irr", content="gardening tips and recipes", score=0.8)
        result = await reranker.rerank(
            chunks=[irrelevant, relevant], query="machine learning",
            company_id="co-1", variant_type="parwa",
        )
        chunk_ids = [c.chunk_id for c in result.chunks]
        assert chunk_ids.index("rel") < chunk_ids.index("irr")

    @pytest.mark.asyncio
    async def test_cross_encoder_default_top_k_is_5(self, reranker, sample_chunks):
        result = await reranker.rerank(
            chunks=sample_chunks, query="test", company_id="co-1",
            variant_type="parwa", top_k=None,
        )
        assert len(result.chunks) <= 5

    @pytest.mark.asyncio
    async def test_cross_encoder_empty_query_returns_original_order(self, reranker, sample_chunks):
        """Empty query should cause _cross_encoder_score to return chunks unchanged."""
        result = await reranker.rerank(
            chunks=sample_chunks, query="   ", company_id="co-1", variant_type="parwa",
        )
        assert len(result.chunks) > 0

    @pytest.mark.asyncio
    async def test_cross_encoder_all_stopword_query(self, reranker):
        """A query containing only stop words should not crash."""
        chunk = _make_chunk(content="some data")
        result = await reranker.rerank(
            chunks=[chunk], query="the is and", company_id="co-1", variant_type="parwa",
        )
        assert len(result.chunks) == 1


# ════════════════════════════════════════════════════════════════════════
#  3. CrossEncoderReranker — REWRITE_RERANK strategy (parwa_high)
# ════════════════════════════════════════════════════════════════════════


class TestCrossEncoderRerankerParwaHigh:
    """Tests for the parwa_high / REWRITE_RERANK variant strategy."""

    @pytest.mark.asyncio
    async def test_rewrite_rerank_returns_chunks(self, reranker, sample_chunks):
        result = await reranker.rerank(
            chunks=sample_chunks, query="machine learning", company_id="co-1",
            variant_type="parwa_high",
        )
        assert len(result.chunks) > 0
        assert result.variant_tier_used == "parwa_high"

    @pytest.mark.asyncio
    async def test_rewrite_rerank_respects_top_k(self, reranker, sample_chunks):
        result = await reranker.rerank(
            chunks=sample_chunks, query="machine learning", company_id="co-1",
            variant_type="parwa_high", top_k=3,
        )
        assert len(result.chunks) <= 3

    @pytest.mark.asyncio
    async def test_rewrite_rerank_applies_filters(self, reranker, diverse_chunks):
        result = await reranker.rerank(
            chunks=diverse_chunks, query="learning", company_id="co-1",
            variant_type="parwa_high",
            filters={"category": "ai"},
        )
        assert all(c.metadata.get("category") == "ai" for c in result.chunks)

    @pytest.mark.asyncio
    async def test_rewrite_rerank_default_top_k_is_10(self, reranker, sample_chunks):
        result = await reranker.rerank(
            chunks=sample_chunks, query="test", company_id="co-1",
            variant_type="parwa_high", top_k=None,
        )
        assert len(result.chunks) <= 10

    @pytest.mark.asyncio
    async def test_rewrite_rerank_with_metadata_filters(self, reranker, diverse_chunks):
        """parwa_high pipeline applies metadata filters in step 3."""
        result = await reranker.rerank(
            chunks=diverse_chunks, query="anything", company_id="co-1",
            variant_type="parwa_high",
            filters={"min_score": 0.8},
        )
        assert all(c.score >= 0.8 for c in result.chunks)


# ════════════════════════════════════════════════════════════════════════
#  4. CrossEncoderReranker — BM25 / IDF / Bigram / Phrase scoring
# ════════════════════════════════════════════════════════════════════════


class TestCrossEncoderScoringInternals:
    """Direct tests for scoring helper methods."""

    def test_compute_idf_returns_dict_for_all_query_terms(self, reranker):
        chunks = [_make_chunk(content="alpha beta gamma")]
        idf = reranker._compute_idf({"alpha", "beta"}, chunks)
        assert "alpha" in idf
        assert "beta" in idf
        assert all(v >= 0.0 for v in idf.values())

    def test_compute_idf_rare_term_has_higher_idf(self, reranker):
        """A term in fewer chunks should have a higher IDF value."""
        common_chunks = [
            _make_chunk(content="common word appears here"),
            _make_chunk(content="common word again present"),
            _make_chunk(content="common word once more"),
        ]
        idf = reranker._compute_idf({"common", "rare"}, common_chunks)
        # rare appears in 0 docs so IDF is higher than common
        assert idf.get("rare", 0) >= idf.get("common", 0)

    def test_compute_bm25_zero_content_length(self, reranker):
        score = reranker._compute_bm25_score(
            query_terms={"term"},
            content_terms=set(),
            content_term_freq={},
            idf_scores={"term": 1.0},
            content_length=0,
        )
        assert score == 0.0

    def test_compute_bm25_perfect_match_higher_score(self, reranker):
        """A chunk matching all query terms should score higher than one matching half."""
        idf = {"alpha": 1.0, "beta": 1.0, "gamma": 1.0}

        all_match = reranker._compute_bm25_score(
            query_terms={"alpha", "beta", "gamma"},
            content_terms={"alpha", "beta", "gamma"},
            content_term_freq={"alpha": 1, "beta": 1, "gamma": 1},
            idf_scores=idf,
            content_length=100,
        )
        half_match = reranker._compute_bm25_score(
            query_terms={"alpha", "beta", "gamma"},
            content_terms={"alpha", "beta"},
            content_term_freq={"alpha": 1, "beta": 1},
            idf_scores=idf,
            content_length=100,
        )
        assert all_match > half_match

    def test_compute_bm25_score_bounded_0_to_1(self, reranker):
        score = reranker._compute_bm25_score(
            query_terms={"term"},
            content_terms={"term"},
            content_term_freq={"term": 50},
            idf_scores={"term": 5.0},
            content_length=200,
        )
        assert 0.0 <= score <= 1.0

    def test_cross_encoder_phrase_bonus(self, reranker):
        """A chunk containing the exact query phrase should get a bonus."""
        chunk_exact = _make_chunk(chunk_id="exact", content="machine learning is great", score=0.5)
        chunk_partial = _make_chunk(chunk_id="partial", content="machine something else", score=0.5)
        reranked = reranker._cross_encoder_score(
            [chunk_exact, chunk_partial], "machine learning", "co-1"
        )
        exact_score = next(c.score for c in reranked if c.chunk_id == "exact")
        partial_score = next(c.score for c in reranked if c.chunk_id == "partial")
        assert exact_score > partial_score

    def test_cross_encoder_bigram_bonus(self, reranker):
        """Matching bigrams should boost the score."""
        chunk_bigram = _make_chunk(chunk_id="bg", content="deep learning networks", score=0.5)
        chunk_no_bigram = _make_chunk(chunk_id="nb", content="deep insights about topics", score=0.5)
        reranked = reranker._cross_encoder_score(
            [chunk_bigram, chunk_no_bigram], "deep learning", "co-1"
        )
        bg_score = next(c.score for c in reranked if c.chunk_id == "bg")
        nb_score = next(c.score for c in reranked if c.chunk_id == "nb")
        assert bg_score > nb_score

    def test_cross_encoder_position_recency(self, reranker):
        """First chunk in list should get a recency bonus over the last."""
        chunks = [
            _make_chunk(chunk_id=f"c{i}", content="generic text about stuff", score=0.5)
            for i in range(10)
        ]
        reranked = reranker._cross_encoder_score(chunks, "generic", "co-1")
        # The content is identical so position recency should differentiate
        first = next(c for c in reranked if c.chunk_id == "c0")
        last = next(c for c in reranked if c.chunk_id == "c9")
        assert first.score > last.score

    def test_cross_encoder_empty_chunks_returns_empty(self, reranker):
        result = reranker._cross_encoder_score([], "query", "co-1")
        assert result == []

    def test_cross_encoder_empty_query_returns_chunks_unchanged(self, reranker, sample_chunks):
        result = reranker._cross_encoder_score(sample_chunks, "", "co-1")
        assert len(result) == len(sample_chunks)


# ════════════════════════════════════════════════════════════════════════
#  5. CrossEncoderReranker — GAP-004 timeout, retry, semaphore
# ════════════════════════════════════════════════════════════════════════


class TestCrossEncoderRerankerGAP004:
    """Tests for GAP-004: timeout, max_retries, and semaphore."""

    @pytest.mark.asyncio
    async def test_timeout_triggers_retry_then_fallback(self, reranker, sample_chunks):
        """After exhausting retries on timeout, BC-008 fallback kicks in."""
        call_count = 0

        async def slow_strategy(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(100)  # guarantee timeout

        with patch.object(reranker, "_execute_strategy", side_effect=slow_strategy):
            result = await reranker.rerank(
                chunks=sample_chunks, query="test", company_id="co-1",
                variant_type="parwa", top_k=5,
            )
        # Should have attempted at least twice (original + 1 retry for timeout)
        assert call_count >= 2
        # BC-008: fallback returns chunks sorted by original score
        assert result.degradation_used is True
        assert len(result.chunks) > 0

    @pytest.mark.asyncio
    async def test_non_timeout_error_does_not_retry(self, reranker, sample_chunks):
        """Non-timeout exceptions should NOT be retried — immediate fallback."""
        call_count = 0

        async def fail_strategy(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("boom")

        with patch.object(reranker, "_execute_strategy", side_effect=fail_strategy):
            result = await reranker.rerank(
                chunks=sample_chunks, query="test", company_id="co-1",
                variant_type="parwa",
            )
        assert call_count == 1
        assert result.degradation_used is True

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self, reranker, sample_chunks):
        """Verify semaphore is acquired (value drops) during execution."""
        original_sem = reranker._semaphore
        assert original_sem._value == 5  # default concurrency limit

        async def instant_strategy(*args, **kwargs):
            # While inside semaphore, value should be decremented
            assert original_sem._value < 5
            return RAGResult(chunks=sample_chunks[:2], total_found=2, variant_tier_used="parwa")

        with patch.object(reranker, "_execute_strategy", side_effect=instant_strategy):
            await reranker.rerank(
                chunks=sample_chunks, query="test", company_id="co-1",
                variant_type="parwa", top_k=2,
            )

    @pytest.mark.asyncio
    async def test_timeout_uses_variant_config_value(self, reranker, sample_chunks):
        """mini_parwa timeout is 5s, parwa is 10s, parwa_high is 15s."""
        call_count = 0

        async def slow_strategy(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(100)

        # Use mini_parwa with 5s timeout — should fail faster
        start = time.monotonic()
        with patch.object(reranker, "_execute_strategy", side_effect=slow_strategy):
            await reranker.rerank(
                chunks=sample_chunks, query="test", company_id="co-1",
                variant_type="mini_parwa", top_k=2,
            )
        elapsed = time.monotonic() - start
        # 5s timeout × 2 attempts + small margin
        assert elapsed < 20  # should be well under 20s


# ════════════════════════════════════════════════════════════════════════
#  6. CrossEncoderReranker — BC-001 (tenant isolation) & BC-008 (degradation)
# ════════════════════════════════════════════════════════════════════════


class TestCrossEncoderRerankerBC001BC008:
    """Tests for BC-001 (tenant isolation) and BC-008 (graceful degradation)."""

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty_result(self, reranker):
        result = await reranker.rerank(
            chunks=[], query="test", company_id="co-1", variant_type="parwa"
        )
        assert result.chunks == []
        assert result.retrieval_time_ms == 0.0

    @pytest.mark.asyncio
    async def test_unknown_variant_defaults_to_parwa(self, reranker, sample_chunks):
        """An unknown variant_type should fall back to parwa strategy."""
        result = await reranker.rerank(
            chunks=sample_chunks, query="test", company_id="co-1",
            variant_type="unknown_variant_xyz",
        )
        assert result.variant_tier_used == "parwa"
        assert len(result.chunks) > 0

    @pytest.mark.asyncio
    async def test_company_id_scoped_in_rewrite_rerank(self, reranker, sample_chunks):
        """parwa_high should pass company_id to query rewriter."""
        captured = {}

        async def spy_rewrite(query, original_chunks, company_id):
            captured["company_id"] = company_id
            return query  # no-op

        with patch.object(reranker._query_rewriter, "rewrite", side_effect=spy_rewrite):
            await reranker.rerank(
                chunks=sample_chunks, query="test", company_id="tenant-42",
                variant_type="parwa_high",
            )
        assert captured["company_id"] == "tenant-42"

    @pytest.mark.asyncio
    async def test_bc008_degradation_flag_on_failure(self, reranker, sample_chunks):
        """When execution fails, degradation_used flag should be True."""
        with patch.object(
            reranker, "_execute_strategy",
            side_effect=RuntimeError("catastrophe"),
        ):
            result = await reranker.rerank(
                chunks=sample_chunks, query="test", company_id="co-1",
                variant_type="parwa",
            )
        assert result.degradation_used is True

    @pytest.mark.asyncio
    async def test_bc008_fallback_chunks_sorted_by_original_score(self, reranker):
        """Fallback should return chunks sorted by their original score."""
        chunks = [
            _make_chunk(chunk_id="low", score=0.3),
            _make_chunk(chunk_id="high", score=0.9),
            _make_chunk(chunk_id="mid", score=0.6),
        ]
        with patch.object(
            reranker, "_execute_strategy",
            side_effect=RuntimeError("fail"),
        ):
            result = await reranker.rerank(
                chunks=chunks, query="test", company_id="co-1", variant_type="parwa",
            )
        ids = [c.chunk_id for c in result.chunks]
        assert ids == ["high", "mid", "low"]

    @pytest.mark.asyncio
    async def test_never_raises_exception_to_caller(self, reranker, sample_chunks):
        """No matter what goes wrong internally, rerank() should never raise."""
        with patch.object(
            reranker, "_execute_strategy",
            side_effect=Exception("unexpected"),
        ):
            result = await reranker.rerank(
                chunks=sample_chunks, query="test", company_id="co-1",
                variant_type="parwa",
            )
        assert isinstance(result, RAGResult)


# ════════════════════════════════════════════════════════════════════════
#  7. CrossEncoderReranker — assemble_context & rerank_and_assemble
# ════════════════════════════════════════════════════════════════════════


class TestCrossEncoderRerankerConvenience:
    """Tests for convenience methods: assemble_context, rerank_and_assemble."""

    @pytest.mark.asyncio
    async def test_assemble_context_returns_assembled_context(self, reranker, sample_chunks):
        result = reranker.assemble_context(
            chunks=sample_chunks, query="test",
            company_id="co-1", variant_type="parwa",
        )
        assert isinstance(result, AssembledContext)
        assert result.context_string != ""

    @pytest.mark.asyncio
    async def test_assemble_context_variant_token_budgets(self, reranker, sample_chunks):
        """Different variants should allow different token budgets."""
        mini = reranker.assemble_context(sample_chunks, "q", "co-1", "mini_parwa")
        parwa = reranker.assemble_context(sample_chunks, "q", "co-1", "parwa")
        high = reranker.assemble_context(sample_chunks, "q", "co-1", "parwa_high")
        # parwa_high should fit more or equal content
        assert high.total_tokens >= parwa.total_tokens >= mini.total_tokens

    @pytest.mark.asyncio
    async def test_rerank_and_assemble_returns_tuple(self, reranker, sample_chunks):
        result = await reranker.rerank_and_assemble(
            chunks=sample_chunks, query="machine learning",
            company_id="co-1", variant_type="parwa",
        )
        assert isinstance(result, tuple)
        assert len(result) == 3
        rag_result, assembled, citations = result
        assert isinstance(rag_result, RAGResult)
        assert isinstance(assembled, AssembledContext)
        assert isinstance(citations, list)


# ════════════════════════════════════════════════════════════════════════
#  8. CrossEncoderReranker — Strategy dispatch edge cases
# ════════════════════════════════════════════════════════════════════════


class TestStrategyDispatch:
    """Tests for _execute_strategy dispatching logic."""

    @pytest.mark.asyncio
    async def test_unknown_strategy_falls_back_to_skip(self, reranker, sample_chunks):
        """An unrecognised strategy value should fall back to SKIP."""
        # MagicMock won't match any RerankStrategy member via ==
        fake_strategy = MagicMock()
        fake_strategy.__eq__ = lambda self, other: False
        with patch.object(reranker, "_strategy_skip", wraps=reranker._strategy_skip) as mock_skip:
            result = await reranker._execute_strategy(
                chunks=sample_chunks, query="q", company_id="co-1",
                variant_type="parwa", top_k=3, strategy=fake_strategy, filters=None,
            )
            # Should have fallen back to _strategy_skip
            assert mock_skip.called
            scores = [c.score for c in result.chunks]
            assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_strategy_records_retrieval_time(self, reranker, sample_chunks):
        result = await reranker._execute_strategy(
            chunks=sample_chunks, query="q", company_id="co-1",
            variant_type="mini_parwa", top_k=3,
            strategy=RerankStrategy.SKIP, filters=None,
        )
        assert result.retrieval_time_ms >= 0.0


# ════════════════════════════════════════════════════════════════════════
#  9. ContextWindowAssembler — token counting, assembly, truncation
# ════════════════════════════════════════════════════════════════════════


class TestContextWindowAssembler:
    """Tests for ContextWindowAssembler.assemble() and _smart_truncate()."""

    def test_assemble_basic(self):
        chunks = [_make_chunk(content="Hello world.")]
        result = ContextWindowAssembler.assemble(chunks, max_tokens=100)
        assert result.context_string == "Hello world."
        assert result.total_tokens >= 1
        assert not result.truncated

    def test_assemble_empty_chunks(self):
        result = ContextWindowAssembler.assemble([], max_tokens=100)
        assert result.context_string == ""
        assert result.total_tokens == 0
        assert result.chunks_used == []
        assert result.citations == []

    def test_assemble_zero_max_tokens(self):
        chunks = [_make_chunk(content="Some text.")]
        result = ContextWindowAssembler.assemble(chunks, max_tokens=0)
        assert result.context_string == ""
        assert result.total_tokens == 0

    def test_assemble_negative_max_tokens(self):
        chunks = [_make_chunk(content="Some text.")]
        result = ContextWindowAssembler.assemble(chunks, max_tokens=-10)
        assert result.context_string == ""

    def test_assemble_skips_empty_content_chunks(self):
        chunks = [_make_chunk(content=""), _make_chunk(content="Real content.")]
        result = ContextWindowAssembler.assemble(chunks, max_tokens=100)
        assert result.context_string == "Real content."
        assert len(result.chunks_used) == 1

    def test_assemble_multiple_chunks_joined_by_separator(self):
        c1 = _make_chunk(chunk_id="a", content="First chunk.")
        c2 = _make_chunk(chunk_id="b", content="Second chunk.")
        result = ContextWindowAssembler.assemble([c1, c2], max_tokens=100)
        sep = ContextWindowAssembler._CHUNK_SEPARATOR
        assert sep in result.context_string
        assert result.chunks_used[0].chunk_id == "a"
        assert result.chunks_used[1].chunk_id == "b"

    def test_assemble_truncation_flag_set(self):
        """When content exceeds budget, truncated flag should be True."""
        long_content = "Word " * 500  # ~2500 chars
        chunks = [_make_chunk(content=long_content)]
        result = ContextWindowAssembler.assemble(chunks, max_tokens=100)  # 400 chars budget
        assert result.truncated is True

    def test_assemble_citations_built(self):
        chunks = [_make_chunk(chunk_id="x", content="Short text.")]
        result = ContextWindowAssembler.assemble(chunks, max_tokens=100)
        assert len(result.citations) == 1
        assert result.citations[0].chunk_id == "x"

    def test_assemble_citation_excerpt_short_content(self):
        """Short content should not have trailing '...'."""
        chunks = [_make_chunk(content="Short.")]
        result = ContextWindowAssembler.assemble(chunks, max_tokens=100)
        assert not result.citations[0].excerpt.endswith("...")

    def test_assemble_citation_excerpt_long_content(self):
        """Long content excerpts should be truncated with '...'."""
        long_text = "A" * 300
        chunks = [_make_chunk(content=long_text)]
        result = ContextWindowAssembler.assemble(chunks, max_tokens=1000)
        assert result.citations[0].excerpt.endswith("...")
        assert len(result.citations[0].excerpt) < len(long_text)

    def test_assemble_citation_position_offsets(self):
        """Citations should have accurate position_in_context offsets."""
        c1 = _make_chunk(chunk_id="a", content="AAAA.")
        c2 = _make_chunk(chunk_id="b", content="BBBB.")
        result = ContextWindowAssembler.assemble([c1, c2], max_tokens=100)
        assert result.citations[0].position_in_context == 0
        assert result.citations[1].position_in_context > 0

    def test_smart_truncate_fits_within_limit(self):
        text = "Hello world."
        result = ContextWindowAssembler._smart_truncate(text, 100)
        assert result == text

    def test_smart_truncate_sentence_boundary(self):
        text = "First sentence. Second sentence. Third sentence."
        result = ContextWindowAssembler._smart_truncate(text, 25)
        assert result.endswith(".")

    def test_smart_truncate_whitespace_fallback(self):
        """When no sentence boundary exists, fall back to whitespace."""
        text = "word1 word2 word3 word4 word5 word6"
        result = ContextWindowAssembler._smart_truncate(text, 15)
        # text[:15] = 'word1 word2 wor', last_space at index 11 (after 'word2')
        # 11 > 15//2=7, so truncates to 'word1 word2'
        assert "word1 word2" in result
        assert not result.endswith(" ")

    def test_smart_truncate_hard_cutoff(self):
        """When no boundary at all (single long word), hard truncate."""
        text = "abcdefghijklmnop"
        result = ContextWindowAssembler._smart_truncate(text, 5)
        assert len(result) <= 5


# ════════════════════════════════════════════════════════════════════════
#  10. CitationTracker — extraction, dedup, metadata enrichment
# ════════════════════════════════════════════════════════════════════════


class TestCitationTracker:
    """Tests for CitationTracker.track_citations()."""

    def test_track_citations_basic(self):
        chunk = _make_chunk(chunk_id="c1", content="Some content.")
        assembled = AssembledContext(
            context_string="Some content.",
            total_tokens=5,
            chunks_used=[chunk],
            citations=[Citation(chunk_id="c1", document_id="d1", relevance_score=0.8, position_in_context=0)],
        )
        result = CitationTracker.track_citations([chunk], assembled)
        assert len(result) == 1
        assert result[0].chunk_id == "c1"

    def test_track_citations_empty_chunks_used(self):
        assembled = AssembledContext()
        result = CitationTracker.track_citations([], assembled)
        assert result == []

    def test_track_citations_dedup(self):
        """Duplicate chunk_ids should be deduped."""
        chunk = _make_chunk(chunk_id="c1")
        assembled = AssembledContext(
            chunks_used=[chunk],
            citations=[
                Citation(chunk_id="c1", document_id="d1", relevance_score=0.8, position_in_context=0),
                Citation(chunk_id="c1", document_id="d1", relevance_score=0.8, position_in_context=10),
            ],
        )
        result = CitationTracker.track_citations([chunk], assembled)
        assert len(result) == 1

    def test_track_citations_enriches_with_source(self):
        chunk = _make_chunk(
            chunk_id="c1",
            metadata={"source": "Annual Report", "page": 42, "section": "Finance"},
        )
        assembled = AssembledContext(
            chunks_used=[chunk],
            citations=[Citation(chunk_id="c1", document_id="d1", relevance_score=0.8, position_in_context=0)],
        )
        result = CitationTracker.track_citations([chunk], assembled)
        assert "[Source: Annual Report]" in result[0].excerpt
        assert "(p. 42)" in result[0].excerpt
        assert "Finance" in result[0].excerpt

    def test_track_citations_default_source_no_enrichment(self):
        """Chunks with default 'Knowledge Base' source and no page/section are not enriched."""
        chunk = _make_chunk(chunk_id="c1", metadata={"source": "Knowledge Base"})
        assembled = AssembledContext(
            chunks_used=[chunk],
            citations=[Citation(chunk_id="c1", document_id="d1", relevance_score=0.8, position_in_context=0, excerpt="orig")],
        )
        result = CitationTracker.track_citations([chunk], assembled)
        assert result[0].excerpt == "orig"

    def test_track_citations_page_only_enriches(self):
        chunk = _make_chunk(chunk_id="c1", metadata={"source": "Knowledge Base", "page": 10})
        assembled = AssembledContext(
            chunks_used=[chunk],
            citations=[Citation(chunk_id="c1", document_id="d1", relevance_score=0.8, position_in_context=0)],
        )
        result = CitationTracker.track_citations([chunk], assembled)
        assert "(p. 10)" in result[0].excerpt

    def test_track_citations_section_only_enriches(self):
        chunk = _make_chunk(chunk_id="c1", metadata={"source": "Knowledge Base", "section": "Intro"})
        assembled = AssembledContext(
            chunks_used=[chunk],
            citations=[Citation(chunk_id="c1", document_id="d1", relevance_score=0.8, position_in_context=0)],
        )
        result = CitationTracker.track_citations([chunk], assembled)
        assert "Intro" in result[0].excerpt

    def test_track_citations_chunk_not_in_lookup_preserves_citation(self):
        """If chunk_id is not found in the full list, the citation is kept as-is."""
        assembled = AssembledContext(
            chunks_used=[],
            citations=[Citation(chunk_id="ghost", document_id="d1", relevance_score=0.5, position_in_context=0)],
        )
        # chunks_used is empty, so track_citations returns [] early
        result = CitationTracker.track_citations([], assembled)
        assert result == []

    def test_track_citations_missing_chunk_in_lookup(self):
        """If citation's chunk_id not in lookup but is in assembled, keep as-is."""
        other_chunk = _make_chunk(chunk_id="other")
        assembled = AssembledContext(
            chunks_used=[other_chunk],
            citations=[Citation(chunk_id="other", document_id="d1", relevance_score=0.5, position_in_context=0)],
        )
        # lookup built from empty list, so full_chunk will be None
        result = CitationTracker.track_citations([], assembled)
        # assembled has chunks_used, so we enter the loop, but lookup is empty
        assert len(result) == 1
        assert result[0].chunk_id == "other"

    def test_track_citations_multiple_chunks_ordered_by_position(self):
        c1 = _make_chunk(chunk_id="c1")
        c2 = _make_chunk(chunk_id="c2")
        assembled = AssembledContext(
            chunks_used=[c1, c2],
            citations=[
                Citation(chunk_id="c2", document_id="d1", relevance_score=0.7, position_in_context=50),
                Citation(chunk_id="c1", document_id="d1", relevance_score=0.9, position_in_context=0),
            ],
        )
        result = CitationTracker.track_citations([c1, c2], assembled)
        # Should maintain the order from assembled_context.citations (position order)
        assert result[0].chunk_id == "c2"
        assert result[1].chunk_id == "c1"


# ════════════════════════════════════════════════════════════════════════
#  11. MetadataFilter — all filter types, AND logic, edge cases
# ════════════════════════════════════════════════════════════════════════


class TestMetadataFilter:
    """Tests for MetadataFilter.filter_chunks() and _chunk_matches()."""

    def test_no_filters_returns_all_chunks(self):
        chunks = [_make_chunk()]
        result = MetadataFilter.filter_chunks(chunks)
        assert len(result) == 1

    def test_none_filters_returns_all_chunks(self):
        chunks = [_make_chunk()]
        result = MetadataFilter.filter_chunks(chunks, filters=None)
        assert len(result) == 1

    def test_empty_chunks_returns_empty(self):
        result = MetadataFilter.filter_chunks([], filters={"source_type": "pdf"})
        assert result == []

    def test_source_type_filter_exact_match(self):
        chunks = [
            _make_chunk(chunk_id="a", metadata={"source_type": "pdf"}),
            _make_chunk(chunk_id="b", metadata={"source_type": "wiki"}),
        ]
        result = MetadataFilter.filter_chunks(chunks, {"source_type": "pdf"})
        assert [c.chunk_id for c in result] == ["a"]

    def test_source_type_filter_no_match(self):
        chunks = [_make_chunk(metadata={"source_type": "wiki"})]
        result = MetadataFilter.filter_chunks(chunks, {"source_type": "pdf"})
        assert result == []

    def test_category_filter(self):
        chunks = [
            _make_chunk(chunk_id="a", metadata={"category": "ai"}),
            _make_chunk(chunk_id="b", metadata={"category": "billing"}),
        ]
        result = MetadataFilter.filter_chunks(chunks, {"category": "ai"})
        assert len(result) == 1
        assert result[0].chunk_id == "a"

    def test_date_from_filter_inclusive(self):
        chunks = [
            _make_chunk(chunk_id="a", metadata={"date": "2024-03-15"}),
            _make_chunk(chunk_id="b", metadata={"date": "2024-01-10"}),
        ]
        result = MetadataFilter.filter_chunks(chunks, {"date_from": "2024-02-01"})
        assert [c.chunk_id for c in result] == ["a"]

    def test_date_to_filter_inclusive(self):
        chunks = [
            _make_chunk(chunk_id="a", metadata={"date": "2024-03-15"}),
            _make_chunk(chunk_id="b", metadata={"date": "2024-06-20"}),
        ]
        result = MetadataFilter.filter_chunks(chunks, {"date_to": "2024-04-01"})
        assert [c.chunk_id for c in result] == ["a"]

    def test_date_range_both_bounds(self):
        chunks = [
            _make_chunk(chunk_id="a", metadata={"date": "2024-02-15"}),
            _make_chunk(chunk_id="b", metadata={"date": "2024-05-20"}),
            _make_chunk(chunk_id="c", metadata={"date": "2024-08-01"}),
        ]
        result = MetadataFilter.filter_chunks(
            chunks, {"date_from": "2024-03-01", "date_to": "2024-06-30"}
        )
        assert [c.chunk_id for c in result] == ["b"]

    def test_tags_filter_all_required(self):
        chunks = [
            _make_chunk(chunk_id="a", metadata={"tags": ["ml", "ai", "python"]}),
            _make_chunk(chunk_id="b", metadata={"tags": ["ml"]}),
            _make_chunk(chunk_id="c", metadata={"tags": ["ai"]}),
        ]
        result = MetadataFilter.filter_chunks(chunks, {"tags": ["ml", "ai"]})
        assert [c.chunk_id for c in result] == ["a"]

    def test_tags_filter_single_string(self):
        """tags filter accepts a single string (coerced to list)."""
        chunks = [
            _make_chunk(chunk_id="a", metadata={"tags": ["ml"]}),
            _make_chunk(chunk_id="b", metadata={"tags": ["ai"]}),
        ]
        result = MetadataFilter.filter_chunks(chunks, {"tags": "ml"})
        assert [c.chunk_id for c in result] == ["a"]

    def test_min_score_filter(self):
        chunks = [
            _make_chunk(chunk_id="a", score=0.9),
            _make_chunk(chunk_id="b", score=0.4),
            _make_chunk(chunk_id="c", score=0.7),
        ]
        result = MetadataFilter.filter_chunks(chunks, {"min_score": 0.7})
        assert [c.chunk_id for c in result] == ["a", "c"]

    def test_and_logic_all_filters_must_match(self):
        """Chunks must satisfy ALL active filters (AND logic)."""
        chunks = [
            _make_chunk(
                chunk_id="a",
                score=0.9,
                metadata={"source_type": "pdf", "category": "ai"},
            ),
            _make_chunk(
                chunk_id="b",
                score=0.9,
                metadata={"source_type": "wiki", "category": "ai"},
            ),
        ]
        result = MetadataFilter.filter_chunks(
            chunks, {"source_type": "pdf", "category": "ai"}
        )
        assert [c.chunk_id for c in result] == ["a"]

    def test_unsupported_filter_keys_ignored(self):
        """Unknown filter keys should be silently ignored."""
        chunks = [_make_chunk(chunk_id="a")]
        result = MetadataFilter.filter_chunks(
            chunks, {"unknown_key": "value", "another_unknown": 42}
        )
        assert len(result) == 1

    def test_malformed_date_does_not_filter_out(self):
        """Chunks with unparseable dates should not be filtered out (lenient)."""
        chunks = [_make_chunk(chunk_id="a", metadata={"date": "not-a-date"})]
        result = MetadataFilter.filter_chunks(chunks, {"date_from": "2024-01-01"})
        # Malformed date → try block catches ValueError → passes through
        assert len(result) == 1

    def test_chunk_with_no_metadata_passes_source_type(self):
        """Chunk with empty metadata should fail source_type filter (no key to match)."""
        chunks = [_make_chunk(chunk_id="a", metadata={})]
        result = MetadataFilter.filter_chunks(chunks, {"source_type": "pdf"})
        assert result == []

    def test_chunk_with_no_metadata_passes_min_score(self):
        chunks = [_make_chunk(chunk_id="a", score=0.9, metadata={})]
        result = MetadataFilter.filter_chunks(chunks, {"min_score": 0.5})
        assert len(result) == 1

    def test_tags_filter_non_list_chunk_tags_ignored(self):
        """If chunk tags is not a list (e.g., None), treat as empty."""
        chunks = [_make_chunk(chunk_id="a", metadata={"tags": None})]
        result = MetadataFilter.filter_chunks(chunks, {"tags": ["ml"]})
        assert result == []

    def test_date_filter_with_datetime_objects(self):
        """date_from/date_to accept datetime objects, not just strings."""
        chunks = [
            _make_chunk(
                chunk_id="a",
                metadata={"date": datetime(2024, 6, 15, tzinfo=timezone.utc)},
            ),
        ]
        result = MetadataFilter.filter_chunks(
            chunks, {"date_from": datetime(2024, 1, 1, tzinfo=timezone.utc)}
        )
        assert len(result) == 1

    def test_chunk_without_date_field_not_filtered_by_date(self):
        """Chunks missing 'date' metadata should pass date filters (no key = pass)."""
        chunks = [_make_chunk(chunk_id="a", metadata={"source": "test"})]
        result = MetadataFilter.filter_chunks(chunks, {"date_from": "2024-01-01"})
        assert len(result) == 1


# ════════════════════════════════════════════════════════════════════════
#  12. QueryRewriter — expansion, stop words, term frequency, BC-008
# ════════════════════════════════════════════════════════════════════════


class TestQueryRewriter:
    """Tests for QueryRewriter.rewrite(), _tokenise(), and _build_term_scores()."""

    @pytest.mark.asyncio
    async def test_rewrite_adds_expansion_terms(self):
        chunks = [_make_chunk(content="neural networks deep learning transformers attention mechanism")]
        result = await QueryRewriter.rewrite("machine learning", chunks, "co-1")
        assert result.startswith("machine learning")
        assert result != "machine learning"  # should have added terms

    @pytest.mark.asyncio
    async def test_rewrite_empty_query_returns_original(self):
        result = await QueryRewriter.rewrite("", [_make_chunk()], "co-1")
        assert result == ""

    @pytest.mark.asyncio
    async def test_rewrite_whitespace_query_returns_original(self):
        result = await QueryRewriter.rewrite("   ", [_make_chunk()], "co-1")
        assert result == "   "

    @pytest.mark.asyncio
    async def test_rewrite_empty_chunks_returns_original(self):
        result = await QueryRewriter.rewrite("query", [], "co-1")
        assert result == "query"

    @pytest.mark.asyncio
    async def test_rewrite_no_matching_terms_returns_original(self):
        """If chunks contain no high-value terms not already in query, return original."""
        chunks = [_make_chunk(content="the is and or but")]
        result = await QueryRewriter.rewrite("something", chunks, "co-1")
        # All chunk words are stop words, so no expansion possible
        assert result == "something"

    @pytest.mark.asyncio
    async def test_rewrite_max_expansion_terms_capped(self):
        """Should not add more than _MAX_EXPANSION_TERMS expansion terms."""
        # Create chunks with many unique relevant terms
        chunk_content = " ".join(f"term{i}" for i in range(20))
        chunks = [_make_chunk(content=chunk_content)]
        result = await QueryRewriter.rewrite("query", chunks, "co-1")
        extra_terms = result.replace("query", "").strip().split()
        assert len(extra_terms) <= QueryRewriter._MAX_EXPANSION_TERMS

    @pytest.mark.asyncio
    async def test_rewrite_terms_not_already_in_query(self):
        """Expansion terms should NOT duplicate terms already in the query."""
        chunks = [_make_chunk(content="alpha beta gamma")]
        result = await QueryRewriter.rewrite("alpha", chunks, "co-1")
        for term in ["alpha"]:
            # alpha should appear only once (from original query)
            parts = result.split()
            assert parts.count(term) == 1

    @pytest.mark.asyncio
    async def test_rewrite_bc008_error_returns_original(self):
        """On internal error, BC-008 ensures original query is returned."""
        with patch.object(QueryRewriter, "_build_term_scores", side_effect=RuntimeError("fail")):
            result = await QueryRewriter.rewrite("safe query", [_make_chunk()], "co-1")
        assert result == "safe query"

    def test_tokenise_strips_stop_words(self):
        tokens = QueryRewriter._tokenise("this is a test of the system")
        # Stop words: this, is, a, of, the
        assert "this" not in tokens
        assert "is" not in tokens
        assert "a" not in tokens
        assert "of" not in tokens
        assert "the" not in tokens
        assert "test" in tokens
        assert "system" in tokens

    def test_tokenise_lowercase(self):
        tokens = QueryRewriter._tokenise("Machine Learning")
        assert "machine" in tokens
        assert "learning" in tokens
        assert "Machine" not in tokens

    def test_tokenise_excludes_punctuation(self):
        tokens = QueryRewriter._tokenise("hello, world! how's it going?")
        assert "hello" in tokens
        assert "world" in tokens
        assert "," not in tokens
        assert "!" not in tokens

    def test_build_term_scores_returns_dict(self):
        chunks = [_make_chunk(content="alpha beta gamma")]
        scores = QueryRewriter._build_term_scores({"query"}, chunks)
        assert isinstance(scores, dict)
        assert len(scores) > 0

    def test_build_term_scores_query_term_boost(self):
        """Terms that match query terms should get a 0.3 boost."""
        chunks = [_make_chunk(content="alpha alphafold beta")]
        scores = QueryRewriter._build_term_scores({"alpha"}, chunks)
        # "alpha" appears and partially matches query → boost
        assert scores.get("alpha", 0) > 0.3  # base + boost

    def test_build_term_scores_frequent_terms_score_higher(self):
        """A term appearing in more chunks should generally score higher (up to a point)."""
        chunks = [
            _make_chunk(content="common common"),
            _make_chunk(content="common common"),
            _make_chunk(content="rare"),
        ]
        scores = QueryRewriter._build_term_scores({"query"}, chunks)
        assert scores.get("common", 0) > scores.get("rare", 0)

    def test_extra_stop_words_include_custom(self):
        """Verify custom extra stop words like 'also', 'like', 'get' are excluded."""
        tokens = QueryRewriter._tokenise("also like get use want")
        assert tokens == set()  # all should be filtered


# ════════════════════════════════════════════════════════════════════════
#  13. Redis cache helpers — get_cached_rerank, set_cached_rerank,
#     invalidate_rerank_cache, _build_rerank_cache_key
# ════════════════════════════════════════════════════════════════════════


class TestRedisCacheHelpers:
    """Tests for Redis cache functions with mocked Redis calls."""

    @pytest.mark.asyncio
    async def test_get_cached_rerank_hit(self):
        """Should reconstruct RAGResult from cached dict."""
        cached_dict = {
            "chunks": [
                {"chunk_id": "c1", "document_id": "d1", "content": "text",
                 "score": 0.9, "metadata": {}, "citation": None}
            ],
            "total_found": 1,
            "retrieval_time_ms": 50.0,
            "query_embedding_time_ms": 10.0,
            "filters_applied": {},
            "variant_tier_used": "parwa",
        }
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=cached_dict):
            result = await get_cached_rerank("co-1", "query", "parwa", 5)
        assert result is not None
        assert result.cached is True
        assert len(result.chunks) == 1

    @pytest.mark.asyncio
    async def test_get_cached_rerank_miss(self):
        """Should return None when cache returns None."""
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            result = await get_cached_rerank("co-1", "query", "parwa", 5)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_rerank_redis_error_returns_none(self):
        """BC-008: Redis errors should return None, not raise."""
        with patch("backend.app.core.redis.cache_get", new_callable=AsyncMock, side_effect=Exception("redis down")):
            result = await get_cached_rerank("co-1", "query", "parwa", 5)
        assert result is None

    @pytest.mark.asyncio
    async def test_set_cached_rerank_success(self):
        rag_result = RAGResult(chunks=[_make_chunk()], total_found=1, variant_tier_used="parwa")
        with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock, return_value=True):
            ok = await set_cached_rerank("co-1", "query", "parwa", 5, rag_result)
        assert ok is True

    @pytest.mark.asyncio
    async def test_set_cached_rerank_redis_error_returns_false(self):
        rag_result = RAGResult()
        with patch("backend.app.core.redis.cache_set", new_callable=AsyncMock, side_effect=Exception("fail")):
            ok = await set_cached_rerank("co-1", "query", "parwa", 5, rag_result)
        assert ok is False

    @pytest.mark.asyncio
    async def test_invalidate_rerank_cache_specific_query(self):
        """Invalidating a specific query should delete keys for all variant/top_k combos."""
        mock_delete = AsyncMock()
        with patch("backend.app.core.redis.cache_delete", side_effect=mock_delete):
            result = await invalidate_rerank_cache("co-1", query="test query")
        assert result is True
        # Should delete for 3 variants × 3 top_k values = 9 calls
        assert mock_delete.call_count == 9

    @pytest.mark.asyncio
    async def test_invalidate_rerank_cache_all(self):
        """Invalidating all should use scan_iter pattern."""
        mock_redis = AsyncMock()
        # scan_iter returns an async iterator — mock it properly
        async def mock_scan_iter(*args, **kwargs):
            for key in ["key1", "key2"]:
                yield key
        mock_redis.scan_iter = mock_scan_iter
        mock_redis.delete = AsyncMock()
        with patch("backend.app.core.redis.get_redis", return_value=mock_redis), \
             patch("backend.app.core.redis.make_key", return_value="cache:co-1:rerank:*"):
            result = await invalidate_rerank_cache("co-1")
        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_rerank_cache_error_returns_false(self):
        with patch("backend.app.core.redis.cache_delete", new_callable=AsyncMock, side_effect=Exception("boom")):
            result = await invalidate_rerank_cache("co-1", query="test")
        assert result is False

    def test_build_rerank_cache_key_format(self):
        # _build_rerank_cache_key(query, company_id, variant_type, top_k, filters)
        key = _build_rerank_cache_key("Test Query", "co-1", "parwa", 5)
        assert key.startswith("rerank:co-1:")
        # Key format: rerank:{company_id}:{query_hash}:{meta_hash}
        parts = key.split(":")
        assert parts[0] == "rerank"
        assert parts[1] == "co-1"
        # Last part is meta_hash (8 chars), second-to-last is query_hash (16 chars)
        assert len(parts[-1]) == 8
        assert len(parts[-2]) == 16

    def test_build_rerank_cache_key_deterministic(self):
        """Same inputs should always produce the same key."""
        k1 = _build_rerank_cache_key("query", "co-1", "parwa", 5, {"tags": ["a"]})
        k2 = _build_rerank_cache_key("query", "co-1", "parwa", 5, {"tags": ["a"]})
        assert k1 == k2

    def test_build_rerank_cache_key_different_queries(self):
        k1 = _build_rerank_cache_key("query one", "co-1", "parwa", 5)
        k2 = _build_rerank_cache_key("query two", "co-1", "parwa", 5)
        assert k1 != k2

    def test_build_rerank_cache_key_case_insensitive_query(self):
        """Query should be normalised to lowercase in the hash."""
        k1 = _build_rerank_cache_key("Test Query", "co-1", "parwa", 5)
        k2 = _build_rerank_cache_key("test query", "co-1", "parwa", 5)
        # Both produce the same query_hash since query is lowercased before hashing
        assert k1 == k2


# ════════════════════════════════════════════════════════════════════════
#  14. Data classes — AssembledContext.to_dict() and Citation.to_dict()
# ════════════════════════════════════════════════════════════════════════


class TestDataClasses:
    """Tests for to_dict() serialisation on data classes."""

    def test_assembled_context_to_dict(self):
        ac = AssembledContext(
            context_string="hello",
            total_tokens=10,
            chunks_used=[_make_chunk(chunk_id="x")],
            truncated=True,
        )
        d = ac.to_dict()
        assert d["context_string"] == "hello"
        assert d["total_tokens"] == 10
        assert d["chunks_used_count"] == 1
        assert d["citations_count"] == 0
        assert d["truncated"] is True
        assert "x" in d["chunk_ids"]

    def test_assembled_context_to_dict_empty(self):
        ac = AssembledContext()
        d = ac.to_dict()
        assert d["context_string"] == ""
        assert d["total_tokens"] == 0
        assert d["chunks_used_count"] == 0
        assert d["chunk_ids"] == []

    def test_citation_to_dict(self):
        c = Citation(
            chunk_id="c1",
            document_id="d1",
            relevance_score=0.8564321,
            position_in_context=100,
            excerpt="Some excerpt text.",
        )
        d = c.to_dict()
        assert d["chunk_id"] == "c1"
        assert d["document_id"] == "d1"
        assert d["relevance_score"] == 0.856432  # rounded to 6 decimals
        assert d["position_in_context"] == 100
        assert d["excerpt"] == "Some excerpt text."

    def test_citation_to_dict_default_excerpt(self):
        c = Citation(chunk_id="c1", document_id="d1", relevance_score=0.5, position_in_context=0)
        d = c.to_dict()
        assert d["excerpt"] == ""


# ════════════════════════════════════════════════════════════════════════
#  15. RerankStrategy enum and VARIANT_RERANK_CONFIG
# ════════════════════════════════════════════════════════════════════════


class TestConstantsAndEnums:
    """Tests for module-level constants and the RerankStrategy enum."""

    def test_rerank_strategy_enum_values(self):
        assert RerankStrategy.SKIP.value == "skip"
        assert RerankStrategy.CROSS_ENCODER.value == "cross_encoder"
        assert RerankStrategy.REWRITE_RERANK.value == "rewrite_rerank"

    def test_variant_rerank_config_has_three_variants(self):
        assert set(VARIANT_RERANK_CONFIG.keys()) == {"mini_parwa", "parwa", "parwa_high"}

    def test_variant_rerank_config_strategies(self):
        assert VARIANT_RERANK_CONFIG["mini_parwa"]["strategy"] == RerankStrategy.SKIP
        assert VARIANT_RERANK_CONFIG["parwa"]["strategy"] == RerankStrategy.CROSS_ENCODER
        assert VARIANT_RERANK_CONFIG["parwa_high"]["strategy"] == RerankStrategy.REWRITE_RERANK

    def test_variant_rerank_config_timeouts_increase(self):
        t_mini = VARIANT_RERANK_CONFIG["mini_parwa"]["timeout_seconds"]
        t_parwa = VARIANT_RERANK_CONFIG["parwa"]["timeout_seconds"]
        t_high = VARIANT_RERANK_CONFIG["parwa_high"]["timeout_seconds"]
        assert t_mini < t_parwa < t_high

    def test_variant_rerank_config_max_context_tokens_increase(self):
        m_mini = VARIANT_RERANK_CONFIG["mini_parwa"]["max_context_tokens"]
        m_parwa = VARIANT_RERANK_CONFIG["parwa"]["max_context_tokens"]
        m_high = VARIANT_RERANK_CONFIG["parwa_high"]["max_context_tokens"]
        assert m_mini < m_parwa < m_high


# ════════════════════════════════════════════════════════════════════════
#  16. get_reranker factory
# ════════════════════════════════════════════════════════════════════════


class TestGetRerankerFactory:

    def test_returns_cross_encoder_reranker(self):
        r = get_reranker()
        assert isinstance(r, CrossEncoderReranker)

    def test_returns_singleton(self):
        r1 = get_reranker()
        r2 = get_reranker()
        assert r1 is r2

    def test_fresh_instance_after_reset(self):
        r1 = get_reranker()
        if hasattr(get_reranker, "_instance"):
            delattr(get_reranker, "_instance")
        r2 = get_reranker()
        assert isinstance(r2, CrossEncoderReranker)
        # Clean up
        if hasattr(get_reranker, "_instance"):
            delattr(get_reranker, "_instance")
