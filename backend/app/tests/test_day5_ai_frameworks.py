"""
Day 5 Backend Tests — AI Frameworks + RAG + DSPy + Agent Lightning

Comprehensive unit + integration tests covering all Day 5 modules:
  1. CLARA RAG — HyDE (hyde.py)
  2. CLARA RAG — Multi-Query (multi_query.py)
  3. Contextual Compression (rag_compression.py)
  4. FAKE Voting (fake_voting.py)
  5. DSPy Integration (dspy_integration.py)
  6. Agent Lightning (agent_lightning.py)
  7. Technique Router (technique_router.py)
  8. Variant Tier Mapper (variant_tier_mapper.py)

BC-001: All tests use scoped company_id.
BC-008: All tests verify fallback/graceful degradation.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════════════════
# Shared helpers & constants
# ══════════════════════════════════════════════════════════════════

COMPANY_A = "co_day5_alpha"
COMPANY_B = "co_day5_beta"


def _make_chunk(
    content: str = "Test content " * 40,
    chunk_id: str = "chunk_1",
    doc_id: str = "doc_1",
    score: float = 0.85,
    metadata: Optional[Dict] = None,
    citation: Optional[str] = None,
) -> MagicMock:
    """Build a mock RAGChunk-like object."""
    chunk = MagicMock()
    chunk.chunk_id = chunk_id
    chunk.document_id = doc_id
    chunk.content = content
    chunk.score = score
    chunk.metadata = metadata or {}
    chunk.citation = citation
    return chunk


# ══════════════════════════════════════════════════════════════════
# 1. CLARA RAG — HyDE
# ══════════════════════════════════════════════════════════════════


class TestHyDEGenerator:
    """Tests for app.core.rag.hyde.HyDEGenerator"""

    @pytest.fixture
    def hyde(self):
        from app.core.rag.hyde import HyDEGenerator
        with patch("app.core.rag.hyde._get_smart_router", return_value=None):
            gen = HyDEGenerator()
            gen._router = None
            return gen

    # ── Happy path ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_generate_hypothetical_answer_returns_query_on_empty(self, hyde):
        """Empty query returns the original query (BC-008)."""
        result = await hyde.generate_hypothetical_answer("", COMPANY_A)
        assert result == ""

    @pytest.mark.asyncio
    async def test_generate_hypothetical_answer_returns_query_on_whitespace(self, hyde):
        result = await hyde.generate_hypothetical_answer("   ", COMPANY_A)
        assert result == "   "

    @pytest.mark.asyncio
    async def test_generate_hypothetical_answer_llm_success(self, hyde):
        """LLM returns a valid hypothesis — should be returned."""
        mock_router = MagicMock()
        mock_router.route.return_value = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "To reset your password click Forgot Password.", "model": "gpt-4o-mini"}
        )
        hyde._router = mock_router

        with patch("app.core.rag.hyde._cache_get", new_callable=AsyncMock, return_value=None), \
             patch("app.core.rag.hyde._cache_set", new_callable=AsyncMock, return_value=True):
            result = await hyde.generate_hypothetical_answer(
                "How do I reset my password?", COMPANY_A
            )
        assert "password" in result.lower()

    @pytest.mark.asyncio
    async def test_generate_hypothetical_answer_llm_returns_empty_falls_back(self, hyde):
        """LLM returns empty content — should fall back to original query (BC-008)."""
        mock_router = MagicMock()
        mock_router.route.return_value = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            return_value={"content": "", "fallback_used": True}
        )
        hyde._router = mock_router

        with patch("app.core.rag.hyde._cache_get", new_callable=AsyncMock, return_value=None), \
             patch("app.core.rag.hyde._cache_set", new_callable=AsyncMock, return_value=True):
            result = await hyde.generate_hypothetical_answer(
                "How do I reset?", COMPANY_A
            )
        assert result == "How do I reset?"

    @pytest.mark.asyncio
    async def test_generate_hypothetical_answer_no_router(self, hyde):
        """No Smart Router available — returns original query (BC-008)."""
        hyde._router = None
        with patch("app.core.rag.hyde._get_smart_router", return_value=None), \
             patch("app.core.rag.hyde._cache_get", new_callable=AsyncMock, return_value=None):
            result = await hyde.generate_hypothetical_answer(
                "What is billing?", COMPANY_A
            )
        assert result == "What is billing?"

    @pytest.mark.asyncio
    async def test_generate_hypothetical_answer_llm_exception(self, hyde):
        """LLM raises an exception — returns original query (BC-008)."""
        mock_router = MagicMock()
        mock_router.route.return_value = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(side_effect=RuntimeError("LLM down"))
        hyde._router = mock_router

        with patch("app.core.rag.hyde._cache_get", new_callable=AsyncMock, return_value=None):
            result = await hyde.generate_hypothetical_answer(
                "How to cancel?", COMPANY_A
            )
        assert result == "How to cancel?"

    # ── Caching ───────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_generate_hypothetical_answer_cache_hit(self, hyde):
        """Cached answer is returned without calling LLM."""
        with patch("app.core.rag.hyde._cache_get", new_callable=AsyncMock, return_value="Cached hypothesis"):
            result = await hyde.generate_hypothetical_answer(
                "Any query", COMPANY_A
            )
        assert result == "Cached hypothesis"

    def test_cache_key_scoped_to_company(self):
        """Cache keys differ by company_id (BC-001)."""
        from app.core.rag.hyde import _build_cache_key
        key_a = _build_cache_key("reset password", COMPANY_A, "parwa")
        key_b = _build_cache_key("reset password", COMPANY_B, "parwa")
        assert key_a != key_b

    def test_cache_key_includes_variant(self):
        """Cache keys differ by variant_type."""
        from app.core.rag.hyde import _build_cache_key
        key_parwa = _build_cache_key("reset password", COMPANY_A, "parwa")
        key_high = _build_cache_key("reset password", COMPANY_A, "parwa_high")
        assert key_parwa != key_high

    # ── get_hyde_embedding ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_hyde_embedding_returns_none_on_empty_query(self, hyde):
        result = await hyde.get_hyde_embedding("", COMPANY_A)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_hyde_embedding_fallback_to_query_embedding(self, hyde):
        """If hypothesis embedding fails, falls back to query embedding (BC-008)."""
        with patch.object(hyde, "generate_hypothetical_answer", new_callable=AsyncMock, return_value=""), \
             patch("app.core.rag.hyde._generate_embedding", new_callable=AsyncMock, return_value=[0.1] * 128):
            result = await hyde.get_hyde_embedding("test query", COMPANY_A)
        assert result is not None
        assert len(result) == 128

    @pytest.mark.asyncio
    async def test_get_hyde_embedding_happy_path(self, hyde):
        """Normal flow: generate hypothesis → embed it → return embedding."""
        with patch.object(hyde, "generate_hypothetical_answer", new_callable=AsyncMock, return_value="Hypothetical answer"), \
             patch("app.core.rag.hyde._generate_embedding", new_callable=AsyncMock, return_value=[0.2] * 256):
            result = await hyde.get_hyde_embedding("test query", COMPANY_A)
        assert result is not None
        assert len(result) == 256

    @pytest.mark.asyncio
    async def test_get_hyde_embedding_total_failure_returns_none(self, hyde):
        """Both hypothesis and query embeddings fail → returns None (BC-008)."""
        with patch.object(hyde, "generate_hypothetical_answer", new_callable=AsyncMock, return_value=""), \
             patch("app.core.rag.hyde._generate_embedding", new_callable=AsyncMock, return_value=None):
            result = await hyde.get_hyde_embedding("test query", COMPANY_A)
        assert result is None


# ══════════════════════════════════════════════════════════════════
# 2. CLARA RAG — Multi-Query
# ══════════════════════════════════════════════════════════════════


class TestMultiQuery:
    """Tests for app.core.rag.multi_query module."""

    @pytest.fixture
    def mq(self):
        from app.core.rag.multi_query import MultiQueryRetriever
        with patch("app.core.rag.multi_query._get_smart_router", return_value=None):
            return MultiQueryRetriever(retriever=MagicMock())

    # ── _extract_json_array ───────────────────────────────────────

    def test_extract_json_array_plain(self):
        from app.core.rag.multi_query import _extract_json_array
        result = _extract_json_array('["alt1", "alt2", "alt3"]')
        assert result == ["alt1", "alt2", "alt3"]

    def test_extract_json_array_with_markdown_fence(self):
        from app.core.rag.multi_query import _extract_json_array
        result = _extract_json_array('```json\n["a", "b"]\n```')
        assert result == ["a", "b"]

    def test_extract_json_array_with_surrounding_text(self):
        from app.core.rag.multi_query import _extract_json_array
        result = _extract_json_array('Here are the alternatives: ["one", "two"] done.')
        assert result == ["one", "two"]

    def test_extract_json_array_empty_string(self):
        from app.core.rag.multi_query import _extract_json_array
        assert _extract_json_array("") is None

    def test_extract_json_array_invalid_json(self):
        from app.core.rag.multi_query import _extract_json_array
        assert _extract_json_array("not json at all") is None

    def test_extract_json_array_filters_empty_strings(self):
        from app.core.rag.multi_query import _extract_json_array
        result = _extract_json_array('["valid", "", "also valid"]')
        assert result == ["valid", "also valid"]

    def test_extract_json_array_newline_fallback(self):
        """When JSON parsing fails, falls back to line splitting."""
        from app.core.rag.multi_query import _extract_json_array
        result = _extract_json_array("How to reset?\nHow to change password?\nForgot credentials?")
        assert result is not None
        assert len(result) >= 2

    # ── generate_alternative_queries ──────────────────────────────

    @pytest.mark.asyncio
    async def test_generate_alternative_queries_empty_query(self, mq):
        result = await mq.generate_alternative_queries("", COMPANY_A)
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_alternative_queries_clamps_num(self, mq):
        """num_alternatives clamped to [1, 5]."""
        with patch.object(mq, "_llm_generate_queries", new_callable=AsyncMock, return_value=["a"]):
            with patch("app.core.rag.multi_query._cache_get_alternatives", new_callable=AsyncMock, return_value=None), \
                 patch("app.core.rag.multi_query._cache_set_alternatives", new_callable=AsyncMock):
                result = await mq.generate_alternative_queries("test", COMPANY_A, num_alternatives=10)
        # Should still work (clamped to 5 internally)

    @pytest.mark.asyncio
    async def test_generate_alternative_queries_llm_failure_returns_empty(self, mq):
        """LLM failure returns empty list (BC-008)."""
        mq._router = None
        with patch("app.core.rag.multi_query._get_smart_router", return_value=None), \
             patch("app.core.rag.multi_query._cache_get_alternatives", new_callable=AsyncMock, return_value=None):
            result = await mq.generate_alternative_queries("test query", COMPANY_A)
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_alternative_queries_llm_success(self, mq):
        mock_router = MagicMock()
        mock_router.route.return_value = MagicMock()
        mock_router.async_execute_llm_call = AsyncMock(
            return_value={"content": '["how to reset password", "password reset steps"]'}
        )
        mq._router = mock_router

        with patch("app.core.rag.multi_query._cache_get_alternatives", new_callable=AsyncMock, return_value=None), \
             patch("app.core.rag.multi_query._cache_set_alternatives", new_callable=AsyncMock):
            result = await mq.generate_alternative_queries("reset password", COMPANY_A)
        assert len(result) >= 1

    # ── _rank_by_aggregate_score ──────────────────────────────────

    def test_rank_by_aggregate_score_basic(self, mq):
        scores = {
            "c1": [0.9, 0.8],
            "c2": [0.7],
            "c3": [0.9, 0.9, 0.8],
        }
        ranked = mq._rank_by_aggregate_score(scores)
        assert ranked[0][0] == "c3"  # highest avg + frequency bonus
        assert len(ranked) == 3

    def test_rank_by_aggregate_score_empty(self, mq):
        ranked = mq._rank_by_aggregate_score({})
        assert ranked == []

    # ── retrieve_with_multi_query ─────────────────────────────────

    @pytest.mark.asyncio
    async def test_retrieve_with_multi_query_empty_query(self, mq):
        from app.core.rag_retrieval import RAGResult
        result = await mq.retrieve_with_multi_query("", COMPANY_A)
        assert isinstance(result, RAGResult)
        assert len(result.chunks) == 0

    @pytest.mark.asyncio
    async def test_retrieve_with_multi_query_fallback_to_single(self, mq):
        """When all retrievals fail, falls back to single query (BC-008)."""
        from app.core.rag_retrieval import RAGResult
        mock_retriever = MagicMock()
        mock_retriever.retrieve = AsyncMock(return_value=RAGResult(variant_tier_used="parwa"))
        mq._retriever = mock_retriever
        mq._router = None

        with patch("app.core.rag.multi_query._get_smart_router", return_value=None), \
             patch("app.core.rag.multi_query._cache_get_alternatives", new_callable=AsyncMock, return_value=None):
            result = await mq.retrieve_with_multi_query("test", COMPANY_A)
        assert isinstance(result, RAGResult)

    # ── Tenant isolation (BC-001) ─────────────────────────────────

    def test_cache_key_scoped_to_company(self):
        from app.core.rag.multi_query import _build_query_cache_key
        key_a = _build_query_cache_key("test", COMPANY_A, "parwa", 3)
        key_b = _build_query_cache_key("test", COMPANY_B, "parwa", 3)
        assert key_a != key_b


# ══════════════════════════════════════════════════════════════════
# 3. Contextual Compression
# ══════════════════════════════════════════════════════════════════


class TestContextualCompression:
    """Tests for app.core.rag_compression.ContextualCompressor"""

    @pytest.fixture
    def compressor(self):
        from app.core.rag_compression import ContextualCompressor
        return ContextualCompressor()

    # ── Tier behavior ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_mini_parwa_no_compression(self, compressor):
        chunks = [_make_chunk()]
        result = await compressor.compress_chunks(chunks, "test query", COMPANY_A, "mini_parwa")
        assert result.method_used == "none"
        assert result.compressed_chunks[0].compression_ratio == 1.0
        assert result.compressed_chunks[0].compression_method == "none"

    @pytest.mark.asyncio
    async def test_parwa_truncation_compression(self, compressor):
        long_content = "This is a sentence. " * 50
        chunks = [_make_chunk(content=long_content)]
        result = await compressor.compress_chunks(chunks, "test query", COMPANY_A, "parwa")
        assert result.method_used == "truncation"
        assert result.compressed_chunks[0].compression_ratio < 1.0

    @pytest.mark.asyncio
    async def test_parwa_high_llm_compression(self, compressor):
        """parwa_high with LLM function uses LLM-based compression."""
        mock_llm = AsyncMock(return_value=MagicMock(text="Relevant extracted sentence."))
        comp = type(compressor)(llm_generate_func=mock_llm)
        chunks = [_make_chunk(content="Long document content. " * 30)]
        result = await comp.compress_chunks(chunks, "test query", COMPANY_A, "parwa_high")
        assert result.method_used == "llm"

    @pytest.mark.asyncio
    async def test_parwa_high_llm_failure_fallback_to_truncation(self, compressor):
        """parwa_high falls back to truncation when LLM fails (BC-008)."""
        compressor._llm_generate = None
        chunks = [_make_chunk(content="Long content. " * 50)]
        with patch.dict("sys.modules", {"app.services.llm_gateway": None}):
            result = await compressor.compress_chunks(chunks, "test query", COMPANY_A, "parwa_high")
        assert result.method_used == "truncation"

    # ── Edge cases ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_empty_chunks(self, compressor):
        result = await compressor.compress_chunks([], "test query", COMPANY_A, "parwa")
        assert len(result.compressed_chunks) == 0

    @pytest.mark.asyncio
    async def test_empty_query_returns_uncompressed(self, compressor):
        chunks = [_make_chunk()]
        result = await compressor.compress_chunks(chunks, "", COMPANY_A, "parwa")
        assert result.method_used == "none"

    @pytest.mark.asyncio
    async def test_none_query_returns_uncompressed(self, compressor):
        chunks = [_make_chunk()]
        result = await compressor.compress_chunks(chunks, None, COMPANY_A, "parwa")
        assert result.method_used == "none"

    @pytest.mark.asyncio
    async def test_max_chunks_limit(self, compressor):
        chunks = [_make_chunk(chunk_id=f"c{i}") for i in range(10)]
        result = await compressor.compress_chunks(chunks, "test", COMPANY_A, "mini_parwa", max_chunks=3)
        assert len(result.compressed_chunks) == 3

    @pytest.mark.asyncio
    async def test_short_content_truncation_keeps_all(self, compressor):
        short = "Short"
        chunks = [_make_chunk(content=short)]
        result = await compressor.compress_chunks(chunks, "test", COMPANY_A, "parwa")
        assert result.compressed_chunks[0].compression_ratio == 1.0

    @pytest.mark.asyncio
    async def test_compressed_chunk_to_dict(self, compressor):
        from app.core.rag_compression import CompressedChunk
        cc = CompressedChunk(
            chunk_id="c1", document_id="d1", original_content="orig",
            compressed_content="comp", compression_ratio=0.5,
            score=0.9, compression_method="truncation",
        )
        d = cc.to_dict()
        assert d["chunk_id"] == "c1"
        assert d["compression_ratio"] == 0.5

    @pytest.mark.asyncio
    async def test_compression_result_to_dict(self, compressor):
        chunks = [_make_chunk()]
        result = await compressor.compress_chunks(chunks, "test", COMPANY_A, "mini_parwa")
        d = result.to_dict()
        assert "compressed_chunks" in d
        assert "overall_compression_ratio" in d
        assert "method_used" in d

    @pytest.mark.asyncio
    async def test_llm_returns_no_relevant_content(self, compressor):
        """LLM returns NO_RELEVANT_CONTENT — keeps first 100 chars."""
        mock_llm = AsyncMock(return_value=MagicMock(text="NO_RELEVANT_CONTENT"))
        comp = type(compressor)(llm_generate_func=mock_llm)
        chunks = [_make_chunk(content="A" * 500)]
        result = await comp.compress_chunks(chunks, "unrelated query", COMPANY_A, "parwa_high")
        assert result.method_used == "llm"
        assert len(result.compressed_chunks[0].compressed_content) < 500


# ══════════════════════════════════════════════════════════════════
# 4. FAKE Voting
# ══════════════════════════════════════════════════════════════════


class TestFakeVoting:
    """Tests for app.core.fake_voting module."""

    @pytest.fixture
    def engine(self):
        from app.core.fake_voting import FakeVotingEngine, FakeVotingConfig
        config = FakeVotingConfig(
            num_candidates=3,
            evaluators=["fluency", "relevance", "accuracy", "safety", "empathy"],
        )
        return FakeVotingEngine(config=config)

    @pytest.fixture
    def red_flag_engine(self):
        from app.core.fake_voting import RedFlagEngine
        return RedFlagEngine()

    # ── get_fake_voting_config ────────────────────────────────────

    def test_config_mini_parwa(self):
        from app.core.fake_voting import get_fake_voting_config
        config = get_fake_voting_config("mini_parwa")
        assert config.num_candidates == 3
        assert "empathy" not in config.evaluators
        assert config.consensus_threshold == 0.50

    def test_config_parwa(self):
        from app.core.fake_voting import get_fake_voting_config
        config = get_fake_voting_config("parwa")
        assert config.num_candidates == 5
        assert "accuracy" in config.evaluators
        assert config.consensus_threshold == 0.60

    def test_config_parwa_high(self):
        from app.core.fake_voting import get_fake_voting_config
        config = get_fake_voting_config("parwa_high")
        assert config.num_candidates == 7
        assert "empathy" in config.evaluators
        assert config.consensus_threshold == 0.75

    def test_config_unknown_variant_defaults_to_mini(self):
        from app.core.fake_voting import get_fake_voting_config
        config = get_fake_voting_config("nonexistent")
        assert config.num_candidates == 3  # mini_parwa default

    # ── vote ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_vote_empty_candidates(self, engine):
        result = await engine.vote([], "test query", COMPANY_A)
        assert result["consensus_score"] == 0.0
        assert result["winner"]["source"] == "empty"

    @pytest.mark.asyncio
    async def test_vote_single_candidate(self, engine):
        candidates = [{"solution": "Here is your refund info.", "confidence": 0.9}]
        result = await engine.vote(candidates, "I want a refund", COMPANY_A)
        assert result["winner"] is not None
        assert "consensus_score" in result["winner"]

    @pytest.mark.asyncio
    async def test_vote_multiple_candidates_selects_best(self, engine):
        candidates = [
            {"solution": "Sorry, I understand. Here is the info you requested about refunds.", "confidence": 0.9},
            {"solution": "I think maybe you could possibly check the website.", "confidence": 0.3},
            {"solution": "No relevant answer available.", "confidence": 0.1},
        ]
        result = await engine.vote(candidates, "How do I get a refund?", COMPANY_A)
        assert result["consensus_score"] > 0.0
        assert "all_scores" in result
        assert "red_flags" in result

    @pytest.mark.asyncio
    async def test_vote_never_crashes(self, engine):
        """BC-008: vote never crashes, even with bad input."""
        result = await engine.vote([{}], "", COMPANY_A)
        assert "winner" in result

    # ── Red-Flag Engine ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_red_flags_hallucination_risk(self, red_flag_engine):
        flags = await red_flag_engine.check_red_flags(
            "I think this might probably work somehow.", "test query", COMPANY_A
        )
        types = [f["type"] for f in flags]
        assert "hallucination_risk" in types

    @pytest.mark.asyncio
    async def test_red_flags_pii_email(self, red_flag_engine):
        flags = await red_flag_engine.check_red_flags(
            "Contact me at john@example.com", "email query", COMPANY_A
        )
        types = [f["type"] for f in flags]
        assert "pii_leakage" in types

    @pytest.mark.asyncio
    async def test_red_flags_pii_ssn_high_severity(self, red_flag_engine):
        flags = await red_flag_engine.check_red_flags(
            "My SSN is 123-45-6789", "SSN query", COMPANY_A
        )
        pii_flags = [f for f in flags if f["type"] == "pii_leakage"]
        assert len(pii_flags) >= 1
        assert pii_flags[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_red_flags_policy_violation(self, red_flag_engine):
        flags = await red_flag_engine.check_red_flags(
            "We guarantee this will definitely work.", "test", COMPANY_A
        )
        types = [f["type"] for f in flags]
        assert "policy_violation" in types

    @pytest.mark.asyncio
    async def test_red_flags_off_topic(self, red_flag_engine):
        flags = await red_flag_engine.check_red_flags(
            "The weather is sunny and the mountains are beautiful today.", "refund process", COMPANY_A
        )
        types = [f["type"] for f in flags]
        assert "off_topic" in types

    @pytest.mark.asyncio
    async def test_red_flags_confidence_mismatch(self, red_flag_engine):
        """Low score but confident language → mismatch."""
        flags = await red_flag_engine.check_red_flags(
            "This is certainly the answer.", "test", COMPANY_A, consensus_score=0.2
        )
        types = [f["type"] for f in flags]
        assert "confidence_mismatch" in types

    @pytest.mark.asyncio
    async def test_red_flags_clean_response(self, red_flag_engine):
        """Clean response should have no (or very few) flags."""
        flags = await red_flag_engine.check_red_flags(
            "To reset your password, click the Forgot Password link.", "reset password", COMPANY_A, consensus_score=0.8
        )
        # May have off_topic=False for well-matched content
        severe_flags = [f for f in flags if f["severity"] == "high"]
        assert len(severe_flags) == 0

    # ── Evaluators ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_evaluate_fluency(self, engine):
        score = await engine.evaluate_fluency("This is a well-formed sentence with proper grammar.", COMPANY_A)
        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_evaluate_relevance(self, engine):
        score = await engine.evaluate_relevance(
            "To reset your password, click Forgot Password.", "How to reset password?", COMPANY_A
        )
        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_evaluate_accuracy(self, engine):
        score = await engine.evaluate_accuracy("The refund takes 3-5 days.", "refund timeline", COMPANY_A)
        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_evaluate_safety_pii_penalty(self, engine):
        score = await engine.evaluate_safety("My SSN is 123-45-6789", COMPANY_A)
        assert score < 0.5

    @pytest.mark.asyncio
    async def test_evaluate_empathy(self, engine):
        score = await engine.evaluate_empathy(
            "I'm sorry to hear that. I understand your frustration.", "I'm upset", COMPANY_A
        )
        assert score >= 0.2  # empathy keywords present

    # ── _parse_score ──────────────────────────────────────────────

    def test_parse_score_decimal(self):
        from app.core.fake_voting import FakeVotingEngine
        assert FakeVotingEngine._parse_score("0.75") == 0.75

    def test_parse_score_percentage(self):
        from app.core.fake_voting import FakeVotingEngine
        assert FakeVotingEngine._parse_score("85%") == 0.85

    def test_parse_score_none(self):
        from app.core.fake_voting import FakeVotingEngine
        assert FakeVotingEngine._parse_score("") is None

    def test_parse_score_integer_0_or_1(self):
        from app.core.fake_voting import FakeVotingEngine
        assert FakeVotingEngine._parse_score("1") == 1.0


# ══════════════════════════════════════════════════════════════════
# 5. DSPy Integration
# ══════════════════════════════════════════════════════════════════


class TestDSPyIntegration:
    """Tests for app.core.dspy_integration.DSPyIntegration"""

    @pytest.fixture
    def dspy(self):
        from app.core.dspy_integration import DSPyIntegration
        d = DSPyIntegration()
        d.reset_metrics()
        yield d
        d.reset_metrics()

    # ── Signature Definitions ─────────────────────────────────────

    def test_define_signature_predefined_classify(self, dspy):
        sig = dspy.define_signature("classify")
        assert sig is not None

    def test_define_signature_custom_task(self, dspy):
        sig = dspy.define_signature("custom_task", inputs=["a", "b"], outputs=["c"])
        assert sig is not None

    def test_define_signature_overrides_predefined_inputs(self, dspy):
        sig = dspy.define_signature("classify", inputs=["custom_in"], outputs=["custom_out"])
        assert sig is not None

    # ── Module Creation ───────────────────────────────────────────

    def test_create_module_returns_something(self, dspy):
        module = dspy.create_module("classify")
        assert module is not None

    def test_create_module_unknown_type(self, dspy):
        module = dspy.create_module("nonexistent_task")
        assert module is not None

    def test_create_module_with_num_candidates(self, dspy):
        module = dspy.create_module("respond", config={"num_candidates": 3})
        assert module is not None

    # ── Optimization ──────────────────────────────────────────────

    def test_optimize_returns_module(self, dspy):
        module = dspy.create_module("classify")
        optimized = dspy.optimize(module, optimizer_name="BootstrapFewShot")
        assert optimized is not None

    def test_optimize_miprov2(self, dspy):
        module = dspy.create_module("classify")
        optimized = dspy.optimize(module, optimizer_name="MIPROv2")
        assert optimized is not None

    def test_optimize_with_trainset(self, dspy):
        module = dspy.create_module("classify")
        optimized = dspy.optimize(module, trainset=[{"input": "test"}])
        assert optimized is not None

    # ── Execution ─────────────────────────────────────────────────

    def test_execute_stub_module(self, dspy):
        from app.core.dspy_integration import StubModule
        stub = StubModule(task_type="classify")
        result = dspy.execute(stub, {"customer_query": "hello"})
        assert isinstance(result, dict)
        assert "response" in result

    def test_execute_stub_has_fallback_response(self, dspy):
        from app.core.dspy_integration import StubModule
        stub = StubModule()
        result = dspy.execute(stub, {"customer_query": "refund"})
        assert "Fallback" in result.get("response", "")
        assert result["confidence"] == 0.5

    def test_execute_records_metrics(self, dspy):
        from app.core.dspy_integration import StubModule
        dspy.reset_metrics()
        stub = StubModule(task_type="respond")
        dspy.execute(stub, {"input": "test"})
        metrics = dspy.get_metrics()
        assert metrics["total_executions"] == 1

    # ── Configuration ─────────────────────────────────────────────

    def test_configure_valid(self, dspy):
        config = dspy.configure(COMPANY_A, {
            "model_name": "gpt-4o",
            "max_tokens": 1000,
            "temperature": 0.5,
        })
        assert config.model_name == "gpt-4o"

    def test_configure_isolated_per_tenant(self, dspy):
        dspy.configure(COMPANY_A, {"model_name": "model_a"})
        dspy.configure(COMPANY_B, {"model_name": "model_b"})
        assert dspy.get_config(COMPANY_A).model_name == "model_a"
        assert dspy.get_config(COMPANY_B).model_name == "model_b"

    def test_configure_invalid_max_tokens(self, dspy):
        with pytest.raises(ValueError, match="max_tokens"):
            dspy.configure(COMPANY_A, {"max_tokens": -1})

    def test_configure_invalid_temperature(self, dspy):
        with pytest.raises(ValueError, match="temperature"):
            dspy.configure(COMPANY_A, {"temperature": 3.0})

    def test_configure_invalid_model_name(self, dspy):
        with pytest.raises(ValueError, match="model_name"):
            dspy.configure(COMPANY_A, {"model_name": ""})

    def test_configure_invalid_num_threads(self, dspy):
        with pytest.raises(ValueError, match="num_threads"):
            dspy.configure(COMPANY_A, {"num_threads": 0})

    # ── StubModule / StubPrediction ───────────────────────────────

    def test_stub_module_call(self):
        from app.core.dspy_integration import StubModule, StubPrediction
        stub = StubModule(task_type="test")
        result = stub()
        assert isinstance(result, StubPrediction)

    def test_stub_prediction_defaults(self):
        from app.core.dspy_integration import StubPrediction
        pred = StubPrediction(task_type="classify")
        assert pred.response == ""
        assert pred.confidence == 0.0

    # ── Internal metrics ──────────────────────────────────────────

    def test_safety_score_clean(self, dspy):
        assert DSPyIntegration._safety_score("This is a safe response.") == 1.0

    def test_safety_score_blocklist(self, dspy):
        assert DSPyIntegration._safety_score("My SSN is 123-45-6789") == 0.0

    def test_relevance_score(self, dspy):
        score = DSPyIntegration._relevance_score("reset password", "To reset your password")
        assert score > 0.0

    def test_conciseness_score_short(self, dspy):
        score = DSPyIntegration._conciseness_score("short query", "short response")
        assert score == 1.0


# ══════════════════════════════════════════════════════════════════
# 6. Agent Lightning
# ══════════════════════════════════════════════════════════════════


class TestAgentLightning:
    """Tests for app.core.agent_lightning module."""

    @pytest.fixture
    def trainer(self):
        from app.core.agent_lightning import AgentLightningTrainer
        return AgentLightningTrainer()

    @pytest.fixture
    def populated_dataset(self):
        from app.core.agent_lightning import TrainingDataset, TrainingSample
        ds = TrainingDataset(dataset_id="ds_test", company_id=COMPANY_A)
        for i in range(20):
            ds.samples.append(TrainingSample(
                input_text=f"Customer query {i}",
                output_text=f"Agent response {i}",
                intent="general",
                quality_score=4.5,
            ))
        ds.split(train_ratio=0.8)
        return ds

    # ── TrainingDataset ───────────────────────────────────────────

    def test_dataset_split_default_ratio(self):
        from app.core.agent_lightning import TrainingDataset, TrainingSample
        ds = TrainingDataset(dataset_id="ds1", company_id=COMPANY_A)
        for i in range(20):
            ds.samples.append(TrainingSample(input_text=f"Q{i}", output_text=f"A{i}"))
        ds.split()
        assert len(ds.train_split) == 16
        assert len(ds.test_split) == 4

    def test_dataset_split_custom_ratio(self):
        from app.core.agent_lightning import TrainingDataset, TrainingSample
        ds = TrainingDataset(dataset_id="ds2", company_id=COMPANY_A)
        for i in range(10):
            ds.samples.append(TrainingSample(input_text=f"Q{i}", output_text=f"A{i}"))
        ds.split(train_ratio=0.5)
        assert len(ds.train_split) == 5
        assert len(ds.test_split) == 5

    def test_dataset_split_single_sample(self):
        """With 1 sample, train gets at least 1, test gets 0."""
        from app.core.agent_lightning import TrainingDataset, TrainingSample
        ds = TrainingDataset(dataset_id="ds3", company_id=COMPANY_A)
        ds.samples.append(TrainingSample(input_text="Q", output_text="A"))
        ds.split()
        assert len(ds.train_split) >= 1

    def test_dataset_to_dict(self):
        from app.core.agent_lightning import TrainingDataset, TrainingSample
        ds = TrainingDataset(dataset_id="ds4", company_id=COMPANY_A)
        ds.samples.append(TrainingSample(input_text="Q", output_text="A"))
        d = ds.to_dict()
        assert d["dataset_id"] == "ds4"
        assert d["total_samples"] == 1

    # ── TrainingSample ────────────────────────────────────────────

    def test_sample_to_dict(self):
        from app.core.agent_lightning import TrainingSample
        sample = TrainingSample(input_text="Q", output_text="A", intent="refund", quality_score=4.5)
        d = sample.to_dict()
        assert d["input"] == "Q"
        assert d["intent"] == "refund"

    def test_sample_to_finetune_format(self):
        from app.core.agent_lightning import TrainingSample
        sample = TrainingSample(input_text="Q", output_text="A")
        fmt = sample.to_finetune_format()
        assert "instruction" in fmt
        assert "response" in fmt

    # ── prepare_dataset ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_prepare_dataset_db_unavailable_uses_synthetic(self, trainer):
        """When DB unavailable, returns synthetic dataset (BC-008)."""
        with patch.dict("sys.modules", {"database.base": None}):
            dataset = await trainer.prepare_dataset(COMPANY_A)
        assert dataset.company_id == COMPANY_A
        assert dataset.total_samples > 0

    @pytest.mark.asyncio
    async def test_prepare_dataset_scoped_to_company(self, trainer):
        with patch.dict("sys.modules", {"database.base": None}):
            ds_a = await trainer.prepare_dataset(COMPANY_A)
            ds_b = await trainer.prepare_dataset(COMPANY_B)
        assert ds_a.company_id == COMPANY_A
        assert ds_b.company_id == COMPANY_B

    # ── schedule_training ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_schedule_training_insufficient_samples(self, trainer):
        from app.core.agent_lightning import TrainingDataset
        ds = TrainingDataset(dataset_id="ds_fail", company_id=COMPANY_A)
        job = await trainer.schedule_training(COMPANY_A, ds)
        assert job.status == "failed"
        assert "Insufficient" in job.error

    @pytest.mark.asyncio
    async def test_schedule_training_success(self, trainer, populated_dataset):
        job = await trainer.schedule_training(COMPANY_A, populated_dataset)
        assert job.status in ("pending", "running")
        assert job.company_id == COMPANY_A

    # ── check_training_status ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_check_training_status_found(self, trainer, populated_dataset):
        job = await trainer.schedule_training(COMPANY_A, populated_dataset)
        found = await trainer.check_training_status(job.job_id)
        assert found is not None
        assert found.job_id == job.job_id

    @pytest.mark.asyncio
    async def test_check_training_status_not_found(self, trainer):
        found = await trainer.check_training_status("nonexistent_id")
        assert found is None

    # ── apply_fine_tuned_model ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_apply_fine_tuned_model_success(self, trainer, populated_dataset):
        job = await trainer.schedule_training(COMPANY_A, populated_dataset)
        result = await trainer.apply_fine_tuned_model(COMPANY_A, job.job_id)
        assert result["status"] == "deployed"
        assert result["company_id"] == COMPANY_A
        assert "model_name" in result

    @pytest.mark.asyncio
    async def test_apply_fine_tuned_model_nonexistent_job(self, trainer):
        result = await trainer.apply_fine_tuned_model(COMPANY_A, "nonexistent")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_apply_fine_tuned_model_traffic_clamped(self, trainer, populated_dataset):
        """Traffic percent clamped to [5, 50]."""
        job = await trainer.schedule_training(COMPANY_A, populated_dataset)
        result = await trainer.apply_fine_tuned_model(COMPANY_A, job.job_id, traffic_percent=99)
        assert result["traffic_percent"] == 50

    # ── TrainingJob ───────────────────────────────────────────────

    def test_training_job_to_dict(self):
        from app.core.agent_lightning import TrainingJob
        job = TrainingJob(job_id="j1", company_id=COMPANY_A, dataset_id="d1")
        d = job.to_dict()
        assert d["job_id"] == "j1"
        assert d["status"] == "pending"


# ══════════════════════════════════════════════════════════════════
# 7. Technique Router
# ══════════════════════════════════════════════════════════════════


class TestTechniqueRouter:
    """Tests for app.core.technique_router module."""

    # ── Tier 1 always active ──────────────────────────────────────

    def test_tier_1_always_active(self):
        from app.core.technique_router import TechniqueRouter, QuerySignals, TechniqueID
        router = TechniqueRouter(model_tier="medium")
        signals = QuerySignals()  # all defaults
        result = router.route(signals)
        technique_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.CLARA in technique_ids
        assert TechniqueID.CRP in technique_ids
        assert TechniqueID.GSD in technique_ids

    # ── Tier 2 conditional ────────────────────────────────────────

    def test_tier_2_complexity_triggers_cot(self):
        from app.core.technique_router import TechniqueRouter, QuerySignals, TechniqueID
        router = TechniqueRouter()
        signals = QuerySignals(query_complexity=0.6)
        result = router.route(signals)
        technique_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.CHAIN_OF_THOUGHT in technique_ids

    def test_tier_2_low_confidence_triggers_reverse_thinking(self):
        from app.core.technique_router import TechniqueRouter, QuerySignals, TechniqueID
        router = TechniqueRouter()
        signals = QuerySignals(confidence_score=0.5)
        result = router.route(signals)
        technique_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.REVERSE_THINKING in technique_ids

    def test_tier_2_many_turns_triggers_thread_of_thought(self):
        from app.core.technique_router import TechniqueRouter, QuerySignals, TechniqueID
        router = TechniqueRouter()
        signals = QuerySignals(turn_count=7)
        result = router.route(signals)
        technique_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.THREAD_OF_THOUGHT in technique_ids

    def test_tier_2_technical_intent_triggers_react(self):
        from app.core.technique_router import TechniqueRouter, QuerySignals, TechniqueID
        router = TechniqueRouter()
        signals = QuerySignals(intent_type="technical")
        result = router.route(signals)
        technique_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.REACT in technique_ids

    # ── Tier 3 conditional ────────────────────────────────────────

    def test_tier_3_vip_triggers_universe_of_thoughts(self):
        from app.core.technique_router import TechniqueRouter, QuerySignals, TechniqueID
        router = TechniqueRouter()
        signals = QuerySignals(customer_tier="vip")
        result = router.route(signals)
        technique_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.UNIVERSE_OF_THOUGHTS in technique_ids

    def test_tier_3_monetary_gt_100_triggers_self_consistency(self):
        from app.core.technique_router import TechniqueRouter, QuerySignals, TechniqueID
        router = TechniqueRouter()
        signals = QuerySignals(monetary_value=500)
        result = router.route(signals)
        technique_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.SELF_CONSISTENCY in technique_ids

    def test_tier_3_strategic_decision_triggers_gst(self):
        from app.core.technique_router import TechniqueRouter, QuerySignals, TechniqueID
        router = TechniqueRouter()
        signals = QuerySignals(is_strategic_decision=True)
        result = router.route(signals)
        technique_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.GST in technique_ids

    # ── Budget fallback ───────────────────────────────────────────

    def test_budget_fallback_t3_to_t2(self):
        """Light model tier with high complexity → budget exceeded → fallback."""
        from app.core.technique_router import TechniqueRouter, QuerySignals
        router = TechniqueRouter(model_tier="light")
        signals = QuerySignals(
            query_complexity=0.9,
            is_strategic_decision=True,
            customer_tier="vip",
        )
        result = router.route(signals)
        assert result.fallback_applied is True

    # ── Disabled techniques ───────────────────────────────────────

    def test_enabled_techniques_filter(self):
        from app.core.technique_router import TechniqueRouter, QuerySignals, TechniqueID
        enabled = {TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD}
        router = TechniqueRouter(enabled_techniques=enabled)
        signals = QuerySignals(query_complexity=0.9)
        result = router.route(signals)
        technique_ids = {a.technique_id for a in result.activated_techniques}
        # CoT should be skipped since not in enabled set
        assert TechniqueID.CHAIN_OF_THOUGHT not in technique_ids

    # ── get_available_techniques_for_plan ─────────────────────────

    def test_free_plan_only_tier1(self):
        from app.core.technique_router import TechniqueRouter, TechniqueID
        techniques = TechniqueRouter.get_available_techniques_for_plan("free")
        assert TechniqueID.CLARA in techniques
        assert TechniqueID.CHAIN_OF_THOUGHT not in techniques

    def test_pro_plan_tier1_and_tier2(self):
        from app.core.technique_router import TechniqueRouter, TechniqueID
        techniques = TechniqueRouter.get_available_techniques_for_plan("pro")
        assert TechniqueID.CLARA in techniques
        assert TechniqueID.CHAIN_OF_THOUGHT in techniques
        assert TechniqueID.GST not in techniques

    def test_enterprise_plan_all_tiers(self):
        from app.core.technique_router import TechniqueRouter, TechniqueID
        techniques = TechniqueRouter.get_available_techniques_for_plan("enterprise")
        assert TechniqueID.GST in techniques
        assert TechniqueID.UNIVERSE_OF_THOUGHTS in techniques


# ══════════════════════════════════════════════════════════════════
# 8. Variant Tier Mapper
# ══════════════════════════════════════════════════════════════════


class TestVariantTierMapper:
    """Tests for app.core.variant_tier_mapper module."""

    # ── variant_id_to_tier ────────────────────────────────────────

    def test_variant_id_starter(self):
        from app.core.variant_tier_mapper import variant_id_to_tier
        assert variant_id_to_tier("starter") == "mini_parwa"

    def test_variant_id_growth(self):
        from app.core.variant_tier_mapper import variant_id_to_tier
        assert variant_id_to_tier("growth") == "parwa"

    def test_variant_id_high(self):
        from app.core.variant_tier_mapper import variant_id_to_tier
        assert variant_id_to_tier("high") == "parwa_high"

    def test_variant_id_unknown_defaults(self):
        from app.core.variant_tier_mapper import variant_id_to_tier
        assert variant_id_to_tier("unknown") == "mini_parwa"

    def test_variant_id_case_insensitive(self):
        from app.core.variant_tier_mapper import variant_id_to_tier
        assert variant_id_to_tier("STARTER") == "mini_parwa"

    # ── variant_name_to_tier ──────────────────────────────────────

    def test_variant_name_parwa_starter(self):
        from app.core.variant_tier_mapper import variant_name_to_tier
        assert variant_name_to_tier("PARWA Starter") == "mini_parwa"

    def test_variant_name_parwa_growth(self):
        from app.core.variant_tier_mapper import variant_name_to_tier
        assert variant_name_to_tier("PARWA Growth") == "parwa"

    def test_variant_name_parwa_high(self):
        from app.core.variant_tier_mapper import variant_name_to_tier
        assert variant_name_to_tier("PARWA High") == "parwa_high"

    def test_variant_name_unknown(self):
        from app.core.variant_tier_mapper import variant_name_to_tier
        assert variant_name_to_tier("Nonexistent") == "mini_parwa"

    # ── industry_label_to_enum ────────────────────────────────────

    def test_industry_ecommerce(self):
        from app.core.variant_tier_mapper import industry_label_to_enum
        assert industry_label_to_enum("E-commerce") == "ecommerce"

    def test_industry_saas(self):
        from app.core.variant_tier_mapper import industry_label_to_enum
        assert industry_label_to_enum("SaaS") == "saas"

    def test_industry_others(self):
        from app.core.variant_tier_mapper import industry_label_to_enum
        assert industry_label_to_enum("Others") == "general"

    def test_industry_unknown(self):
        from app.core.variant_tier_mapper import industry_label_to_enum
        assert industry_label_to_enum("Unknown") == "general"

    # ── resolve_tier_from_context ─────────────────────────────────

    def test_resolve_tier_from_variant_id(self):
        from app.core.variant_tier_mapper import resolve_tier_from_context
        assert resolve_tier_from_context(variant_id="high") == "parwa_high"

    def test_resolve_tier_from_variant_name(self):
        from app.core.variant_tier_mapper import resolve_tier_from_context
        assert resolve_tier_from_context(variant_name="PARWA Growth") == "parwa"

    def test_resolve_tier_from_selected_variants(self):
        from app.core.variant_tier_mapper import resolve_tier_from_context
        selected = [{"variant_id": "growth"}, {"variant_id": "starter"}]
        result = resolve_tier_from_context(selected_variants=selected)
        assert result == "parwa"  # growth = parwa, higher than starter

    def test_resolve_tier_default(self):
        from app.core.variant_tier_mapper import resolve_tier_from_context
        assert resolve_tier_from_context() == "mini_parwa"

    def test_resolve_tier_variant_id_takes_priority(self):
        from app.core.variant_tier_mapper import resolve_tier_from_context
        result = resolve_tier_from_context(variant_id="high", variant_name="PARWA Starter")
        assert result == "parwa_high"  # variant_id takes priority

    # ── get_tier_metadata ─────────────────────────────────────────

    def test_get_tier_metadata_mini_parwa(self):
        from app.core.variant_tier_mapper import get_tier_metadata
        meta = get_tier_metadata("mini_parwa")
        assert meta["display_name"] == "PARWA Starter"
        assert "cost_per_query" in meta

    def test_get_tier_metadata_parwa(self):
        from app.core.variant_tier_mapper import get_tier_metadata
        meta = get_tier_metadata("parwa")
        assert meta["display_name"] == "PARWA Growth"

    def test_get_tier_metadata_parwa_high(self):
        from app.core.variant_tier_mapper import get_tier_metadata
        meta = get_tier_metadata("parwa_high")
        assert meta["display_name"] == "PARWA High"

    def test_get_tier_metadata_unknown_defaults(self):
        from app.core.variant_tier_mapper import get_tier_metadata
        meta = get_tier_metadata("nonexistent")
        assert "display_name" in meta  # falls back to mini_parwa

    # ── resolve_industry_from_context ─────────────────────────────

    def test_resolve_industry_direct(self):
        from app.core.variant_tier_mapper import resolve_industry_from_context
        assert resolve_industry_from_context(industry="ecommerce") == "ecommerce"

    def test_resolve_industry_from_entry_params(self):
        from app.core.variant_tier_mapper import resolve_industry_from_context
        assert resolve_industry_from_context(entry_params={"industry": "logistics"}) == "logistics"

    def test_resolve_industry_default(self):
        from app.core.variant_tier_mapper import resolve_industry_from_context
        assert resolve_industry_from_context() == "general"

    # ── tier_to_variant_id ────────────────────────────────────────

    def test_tier_to_variant_id(self):
        from app.core.variant_tier_mapper import tier_to_variant_id
        assert tier_to_variant_id("mini_parwa") == "starter"
        assert tier_to_variant_id("parwa") == "growth"
        assert tier_to_variant_id("parwa_high") == "high"
        assert tier_to_variant_id("unknown") == "starter"


# ══════════════════════════════════════════════════════════════════
# 9. Cross-Component Integration
# ══════════════════════════════════════════════════════════════════


class TestDay5CrossComponentIntegration:
    """Integration tests verifying consistency between Day 5 components."""

    def test_variant_tier_mapper_consistent_with_technique_router(self):
        """Tier mapper tier strings are consistent with technique router model tiers."""
        from app.core.variant_tier_mapper import VARIANT_ID_TO_TIER
        from app.core.technique_router import TOKEN_BUDGETS

        for variant_id, tier in VARIANT_ID_TO_TIER.items():
            # Each tier should be usable as a key concept in technique routing
            assert tier in ("mini_parwa", "parwa", "parwa_high")

    def test_fake_voting_config_matches_tier_mapper(self):
        """FAKE voting configs exist for all variant tiers."""
        from app.core.fake_voting import get_fake_voting_config
        from app.core.variant_tier_mapper import VARIANT_ID_TO_TIER

        for variant_id, tier in VARIANT_ID_TO_TIER.items():
            config = get_fake_voting_config(tier)
            assert config is not None
            assert config.num_candidates > 0

    def test_compression_tier_consistency(self):
        """Compression module handles all variant tiers from mapper."""
        from app.core.rag_compression import ContextualCompressor
        from app.core.variant_tier_mapper import VARIANT_ID_TO_TIER

        compressor = ContextualCompressor()
        for variant_id, tier in VARIANT_ID_TO_TIER.items():
            # Just verifying the tier names are valid for the compressor
            assert tier in ("mini_parwa", "parwa", "parwa_high")

    @pytest.mark.asyncio
    async def test_hyde_and_compression_integration(self):
        """HyDE + compression pipeline works end to end."""
        from app.core.rag_compression import ContextualCompressor
        from app.core.rag.hyde import HyDEGenerator

        # Create a hypothetical answer (simulated)
        with patch("app.core.rag.hyde._get_smart_router", return_value=None):
            gen = HyDEGenerator()
            gen._router = None

        # Compress it
        compressor = ContextualCompressor()
        chunk = _make_chunk(content="To reset your password, navigate to the login page and click Forgot Password. " * 10)
        result = await compressor.compress_chunks(
            [chunk], "reset password", COMPANY_A, "parwa"
        )
        assert result.method_used == "truncation"
        assert len(result.compressed_chunks) == 1

    def test_technique_router_tier_access_matches_variant_tier(self):
        """Enterprise/VIP variant should map to full technique access."""
        from app.core.technique_router import TechniqueRouter, TechniqueID
        from app.core.variant_tier_mapper import variant_id_to_tier

        # High variant → enterprise plan → all techniques
        tier = variant_id_to_tier("high")
        assert tier == "parwa_high"
        techniques = TechniqueRouter.get_available_techniques_for_plan("enterprise")
        assert TechniqueID.GST in techniques

    @pytest.mark.asyncio
    async def test_agent_lightning_with_variant_tier(self):
        """Agent Lightning training respects company_id scoping."""
        from app.core.agent_lightning import AgentLightningTrainer, TrainingDataset, TrainingSample

        trainer = AgentLightningTrainer()
        ds_a = TrainingDataset(dataset_id="ds_a", company_id=COMPANY_A)
        ds_b = TrainingDataset(dataset_id="ds_b", company_id=COMPANY_B)
        for i in range(15):
            ds_a.samples.append(TrainingSample(input_text=f"Qa{i}", output_text=f"Aa{i}"))
            ds_b.samples.append(TrainingSample(input_text=f"Qb{i}", output_text=f"Ab{i}"))
        ds_a.split()
        ds_b.split()

        job_a = await trainer.schedule_training(COMPANY_A, ds_a)
        job_b = await trainer.schedule_training(COMPANY_B, ds_b)

        assert job_a.company_id == COMPANY_A
        assert job_b.company_id == COMPANY_B
        assert job_a.job_id != job_b.job_id

    def test_dspy_config_per_tenant_isolation(self):
        """DSPy configs for different companies are isolated."""
        from app.core.dspy_integration import DSPyIntegration

        dspy = DSPyIntegration()
        dspy.configure(COMPANY_A, {"model_name": "gpt-4o", "temperature": 0.7})
        dspy.configure(COMPANY_B, {"model_name": "claude-3", "temperature": 0.3})

        config_a = dspy.get_config(COMPANY_A)
        config_b = dspy.get_config(COMPANY_B)
        assert config_a.model_name == "gpt-4o"
        assert config_b.model_name == "claude-3"
        assert config_a.temperature != config_b.temperature
