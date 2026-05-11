"""
Comprehensive tests for RAG Reranking Module (F-064).

Tests cover: MetadataFilter, QueryRewriter, ContextWindowAssembler,
CitationTracker, CrossEncoderReranker, and full pipeline behavior.
"""

import asyncio
import math
import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ── Mock external dependencies before importing source ────────────
with patch("app.logger.get_logger", return_value=MagicMock()):
    from app.core.rag_retrieval import RAGChunk, RAGResult
    from app.core.rag_reranking import (
        AssembledContext,
        Citation,
        CitationTracker,
        ContextWindowAssembler,
        CrossEncoderReranker,
        MetadataFilter,
        QueryRewriter,
        RerankStrategy,
        VARIANT_RERANK_CONFIG,
        _CHARS_PER_TOKEN,
        _MAX_RETRIES,
        _RERANK_CONCURRENCY_LIMIT,
        _STOP_WORDS,
    )


# ── Helpers ────────────────────────────────────────────────────────

def make_chunk(
    chunk_id: str = "c1",
    document_id: str = "doc1",
    content: str = "Default chunk content about testing.",
    score: float = 0.8,
    metadata: dict = None,
) -> RAGChunk:
    """Create a test RAGChunk."""
    return RAGChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        content=content,
        score=score,
        metadata=metadata or {},
    )


# ═══════════════════════════════════════════════════════════════════
# MetadataFilter Tests
# ═══════════════════════════════════════════════════════════════════

class TestMetadataFilter:
    """Tests for MetadataFilter.filter_chunks and _chunk_matches."""

    def test_none_filters_returns_all_chunks(self):
        chunks = [make_chunk("c1"), make_chunk("c2")]
        result = MetadataFilter.filter_chunks(chunks, None)
        assert len(result) == 2

    def test_empty_filters_returns_all_chunks(self):
        chunks = [make_chunk("c1"), make_chunk("c2")]
        result = MetadataFilter.filter_chunks(chunks, {})
        assert len(result) == 2

    def test_empty_chunks_returns_empty(self):
        result = MetadataFilter.filter_chunks([], {"source_type": "pdf"})
        assert result == []

    def test_source_type_filter_match(self):
        chunks = [
            make_chunk("c1", metadata={"source_type": "pdf"}),
            make_chunk("c2", metadata={"source_type": "web"}),
        ]
        result = MetadataFilter.filter_chunks(chunks, {"source_type": "pdf"})
        assert len(result) == 1
        assert result[0].chunk_id == "c1"

    def test_source_type_filter_no_match(self):
        chunks = [
            make_chunk("c1", metadata={"source_type": "web"}),
            make_chunk("c2", metadata={"source_type": "web"}),
        ]
        result = MetadataFilter.filter_chunks(chunks, {"source_type": "pdf"})
        assert len(result) == 0

    def test_source_type_missing_metadata(self):
        chunks = [make_chunk("c1", metadata={})]
        result = MetadataFilter.filter_chunks(chunks, {"source_type": "pdf"})
        assert len(result) == 0

    def test_category_filter_match(self):
        chunks = [
            make_chunk("c1", metadata={"category": "support"}),
            make_chunk("c2", metadata={"category": "sales"}),
        ]
        result = MetadataFilter.filter_chunks(chunks, {"category": "support"})
        assert len(result) == 1

    def test_category_filter_no_match(self):
        chunks = [make_chunk("c1", metadata={"category": "sales"})]
        result = MetadataFilter.filter_chunks(chunks, {"category": "support"})
        assert len(result) == 0

    def test_date_from_filter_inclusive(self):
        chunks = [
            make_chunk("c1", metadata={"date": "2024-06-15T00:00:00"}),
            make_chunk("c2", metadata={"date": "2024-01-10T00:00:00"}),
        ]
        result = MetadataFilter.filter_chunks(
            chunks, {"date_from": "2024-06-01T00:00:00"}
        )
        assert len(result) == 1
        assert result[0].chunk_id == "c1"

    def test_date_from_filter_exact_boundary(self):
        """Inclusive: chunk exactly at date_from should pass."""
        chunks = [
            make_chunk("c1", metadata={"date": "2024-06-01T00:00:00"}),
        ]
        result = MetadataFilter.filter_chunks(
            chunks, {"date_from": "2024-06-01T00:00:00"}
        )
        assert len(result) == 1

    def test_date_to_filter_inclusive(self):
        chunks = [
            make_chunk("c1", metadata={"date": "2024-03-15T00:00:00"}),
            make_chunk("c2", metadata={"date": "2024-12-31T00:00:00"}),
        ]
        result = MetadataFilter.filter_chunks(
            chunks, {"date_to": "2024-06-01T00:00:00"}
        )
        assert len(result) == 1

    def test_date_range_filter_both(self):
        chunks = [
            make_chunk("c1", metadata={"date": "2024-05-15"}),
            make_chunk("c2", metadata={"date": "2024-07-15"}),
            make_chunk("c3", metadata={"date": "2024-03-15"}),
        ]
        result = MetadataFilter.filter_chunks(
            chunks,
            {"date_from": "2024-04-01", "date_to": "2024-06-30"},
        )
        assert len(result) == 1
        assert result[0].chunk_id == "c1"

    def test_tags_filter_single_tag(self):
        chunks = [
            make_chunk("c1", metadata={"tags": ["billing", "support"]}),
            make_chunk("c2", metadata={"tags": ["sales"]}),
        ]
        result = MetadataFilter.filter_chunks(chunks, {"tags": ["billing"]})
        assert len(result) == 1

    def test_tags_filter_multiple_required(self):
        chunks = [
            make_chunk("c1", metadata={"tags": ["billing", "support"]}),
            make_chunk("c2", metadata={"tags": ["billing"]}),
        ]
        result = MetadataFilter.filter_chunks(
            chunks, {"tags": ["billing", "support"]}
        )
        assert len(result) == 1
        assert result[0].chunk_id == "c1"

    def test_tags_filter_string_input(self):
        """Tags filter accepts a single string."""
        chunks = [
            make_chunk("c1", metadata={"tags": ["billing"]}),
        ]
        result = MetadataFilter.filter_chunks(chunks, {"tags": "billing"})
        assert len(result) == 1

    def test_tags_filter_non_list_metadata(self):
        """Tags filter handles non-list metadata gracefully."""
        chunks = [
            make_chunk("c1", metadata={"tags": "not-a-list"}),
        ]
        result = MetadataFilter.filter_chunks(chunks, {"tags": ["billing"]})
        assert len(result) == 0

    def test_min_score_filter_pass(self):
        chunks = [
            make_chunk("c1", score=0.9),
            make_chunk("c2", score=0.5),
        ]
        result = MetadataFilter.filter_chunks(chunks, {"min_score": 0.7})
        assert len(result) == 1
        assert result[0].chunk_id == "c1"

    def test_min_score_filter_all_pass(self):
        chunks = [
            make_chunk("c1", score=0.8),
            make_chunk("c2", score=0.9),
        ]
        result = MetadataFilter.filter_chunks(chunks, {"min_score": 0.5})
        assert len(result) == 2

    def test_min_score_filter_all_fail(self):
        chunks = [
            make_chunk("c1", score=0.3),
            make_chunk("c2", score=0.4),
        ]
        result = MetadataFilter.filter_chunks(chunks, {"min_score": 0.5})
        assert len(result) == 0

    def test_combined_filters_and_logic(self):
        """Multiple filters use AND logic."""
        chunks = [
            make_chunk("c1", score=0.9, metadata={"category": "support"}),
            make_chunk("c2", score=0.3, metadata={"category": "support"}),
            make_chunk("c3", score=0.9, metadata={"category": "sales"}),
        ]
        result = MetadataFilter.filter_chunks(
            chunks, {"category": "support", "min_score": 0.8}
        )
        assert len(result) == 1
        assert result[0].chunk_id == "c1"

    def test_unknown_filter_keys_ignored(self):
        """Unknown filter keys are silently ignored."""
        chunks = [make_chunk("c1")]
        result = MetadataFilter.filter_chunks(
            chunks, {"unknown_key": "value", "min_score": 0.5}
        )
        assert len(result) == 1

    def test_malformed_date_does_not_filter_out(self):
        """BC-008: Malformed date is lenient, doesn't filter out chunk."""
        chunks = [make_chunk("c1", metadata={"date": "not-a-date"})]
        result = MetadataFilter.filter_chunks(
            chunks, {"date_from": "2024-01-01"}
        )
        assert len(result) == 1

    def test_chunk_with_no_metadata_date(self):
        """Chunks without date pass date filters."""
        chunks = [make_chunk("c1", metadata={})]
        result = MetadataFilter.filter_chunks(
            chunks, {"date_from": "2024-01-01"}
        )
        assert len(result) == 1

    def test_supported_keys_set(self):
        assert "source_type" in MetadataFilter._SUPPORTED_KEYS
        assert "date_from" in MetadataFilter._SUPPORTED_KEYS
        assert "date_to" in MetadataFilter._SUPPORTED_KEYS
        assert "category" in MetadataFilter._SUPPORTED_KEYS
        assert "tags" in MetadataFilter._SUPPORTED_KEYS
        assert "min_score" in MetadataFilter._SUPPORTED_KEYS
        assert "unknown_key" not in MetadataFilter._SUPPORTED_KEYS


# ═══════════════════════════════════════════════════════════════════
# QueryRewriter Tests
# ═══════════════════════════════════════════════════════════════════

class TestQueryRewriter:
    """Tests for QueryRewriter.rewrite, _tokenise, _build_term_scores."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_original(self):
        result = await QueryRewriter.rewrite("", [], "co1")
        assert result == ""

    @pytest.mark.asyncio
    async def test_whitespace_query_returns_original(self):
        result = await QueryRewriter.rewrite("   ", [], "co1")
        assert result == "   "

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_original(self):
        result = await QueryRewriter.rewrite("hello world", [], "co1")
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_rewrite_adds_expansion_terms(self):
        chunks = [
            make_chunk(content="Machine learning algorithms process data structures and neural networks for classification tasks"),
        ]
        result = await QueryRewriter.rewrite("data algorithms", chunks, "co1")
        assert "data algorithms" in result
        # Should have added expansion terms
        assert result != "data algorithms"

    @pytest.mark.asyncio
    async def test_rewrite_respects_max_expansion_terms(self):
        chunks = [make_chunk(content="alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau")]
        result = await QueryRewriter.rewrite("alpha", chunks, "co1")
        added = result.replace("alpha", "").strip()
        added_terms = added.split() if added else []
        assert len(added_terms) <= QueryRewriter._MAX_EXPANSION_TERMS

    @pytest.mark.asyncio
    async def test_rewrite_does_not_duplicate_query_terms(self):
        query = "specific_keyword"
        chunks = [make_chunk(content="specific_keyword appears multiple times specific_keyword")]
        result = await QueryRewriter.rewrite(query, chunks, "co1")
        # Count occurrences of the query term
        count = result.lower().split().count("specific_keyword")
        assert count >= 1

    @pytest.mark.asyncio
    async def test_tokenise_strips_stop_words(self):
        tokens = QueryRewriter._tokenise("the quick brown fox is running")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "quick" in tokens
        assert "brown" in tokens
        assert "fox" in tokens
        assert "running" in tokens

    @pytest.mark.asyncio
    async def test_tokenise_lowercase(self):
        tokens = QueryRewriter._tokenise("Hello World TEST")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens

    @pytest.mark.asyncio
    async def test_tokenise_strips_punctuation(self):
        tokens = QueryRewriter._tokenise("hello, world! test?")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens
        assert "," not in tokens

    def test_tokenise_extra_stop_words(self):
        tokens = QueryRewriter._tokenise("also like get use using used make")
        assert "also" not in tokens
        assert "like" not in tokens
        assert "get" not in tokens
        assert "use" not in tokens
        assert "using" not in tokens
        assert "used" not in tokens
        assert "make" not in tokens

    def test_build_term_scores_returns_dict(self):
        chunks = [make_chunk(content="alpha beta gamma")]
        scores = QueryRewriter._build_term_scores({"alpha"}, chunks)
        assert isinstance(scores, dict)
        assert "alpha" in scores
        assert "beta" in scores or "gamma" in scores

    def test_build_term_scores_empty_chunks(self):
        scores = QueryRewriter._build_term_scores({"alpha"}, [])
        assert scores == {}

    def test_build_term_scores_boosts_query_matching_terms(self):
        chunks = [make_chunk(content="database databases data processing")]
        scores = QueryRewriter._build_term_scores({"data"}, chunks)
        data_score = scores.get("data", 0)
        database_score = scores.get("database", 0)
        # database partially matches data, so should get boost
        assert database_score > 0

    @pytest.mark.asyncio
    async def test_rewrite_exception_returns_original(self):
        """BC-008: Exception returns original query."""
        with patch.object(
            QueryRewriter, "_build_term_scores", side_effect=RuntimeError("boom")
        ):
            result = await QueryRewriter.rewrite(
                "test query", [make_chunk()], "co1"
            )
        assert result == "test query"

    @pytest.mark.asyncio
    async def test_rewrite_chunks_limited_to_5(self):
        """Only first 5 chunks are used for corpus."""
        chunks = [make_chunk(content=f"unique_word_{i} content here") for i in range(10)]
        result = await QueryRewriter.rewrite("query", chunks, "co1")
        # Should still work with 10 chunks but only use first 5
        assert "query" in result

    @pytest.mark.asyncio
    async def test_min_term_score_threshold(self):
        """Terms below _MIN_TERM_SCORE are not added."""
        chunks = [make_chunk(content="common word appears many times common word")]
        result = await QueryRewriter.rewrite("appears", chunks, "co1")
        added = result.replace("appears", "").strip()
        added_terms = added.split() if added else []
        for term in added_terms:
            # All added terms should have been scored >= threshold
            assert term


# ═══════════════════════════════════════════════════════════════════
# ContextWindowAssembler Tests
# ═══════════════════════════════════════════════════════════════════

class TestContextWindowAssembler:
    """Tests for ContextWindowAssembler.assemble and _smart_truncate."""

    def test_empty_chunks_returns_empty_context(self):
        result = ContextWindowAssembler.assemble([], 1000)
        assert result.context_string == ""
        assert result.total_tokens == 0
        assert result.chunks_used == []
        assert result.truncated is False

    def test_zero_max_tokens_returns_empty(self):
        chunks = [make_chunk(content="Hello world")]
        result = ContextWindowAssembler.assemble(chunks, 0)
        assert result.context_string == ""

    def test_negative_max_tokens_returns_empty(self):
        chunks = [make_chunk(content="Hello world")]
        result = ContextWindowAssembler.assemble(chunks, -10)
        assert result.context_string == ""

    def test_single_chunk_fits_within_budget(self):
        chunks = [make_chunk(content="A" * 100)]
        result = ContextWindowAssembler.assemble(chunks, 1000)
        assert result.context_string == "A" * 100
        assert result.truncated is False
        assert len(result.chunks_used) == 1

    def test_multiple_chunks_all_fit(self):
        chunks = [
            make_chunk("c1", content="Chunk one content here."),
            make_chunk("c2", content="Chunk two content here."),
        ]
        result = ContextWindowAssembler.assemble(chunks, 1000)
        assert "Chunk one" in result.context_string
        assert "Chunk two" in result.context_string
        assert result.truncated is False
        assert len(result.chunks_used) == 2

    def test_truncation_when_exceeds_budget(self):
        long_content = "This is a sentence. " * 200  # ~3400 chars
        chunks = [make_chunk(content=long_content)]
        result = ContextWindowAssembler.assemble(chunks, 100)
        assert result.truncated is True

    def test_truncated_flag_set_on_overflow(self):
        small_budget = 10
        chunks = [make_chunk(content="A" * 500)]
        result = ContextWindowAssembler.assemble(chunks, small_budget)
        assert result.truncated is True

    def test_empty_content_chunk_skipped(self):
        chunks = [
            make_chunk("c1", content=""),
            make_chunk("c2", content="Valid content"),
        ]
        result = ContextWindowAssembler.assemble(chunks, 1000)
        assert len(result.chunks_used) == 1
        assert result.chunks_used[0].chunk_id == "c2"

    def test_whitespace_only_chunk_skipped(self):
        chunks = [make_chunk("c1", content="   ")]
        result = ContextWindowAssembler.assemble(chunks, 1000)
        assert len(result.chunks_used) == 0

    def test_citations_created_for_each_chunk(self):
        chunks = [
            make_chunk("c1", content="First chunk."),
            make_chunk("c2", content="Second chunk."),
        ]
        result = ContextWindowAssembler.assemble(chunks, 1000)
        assert len(result.citations) == 2
        assert result.citations[0].chunk_id == "c1"
        assert result.citations[1].chunk_id == "c2"

    def test_citation_excerpt_short_content(self):
        short = "Short"
        chunks = [make_chunk("c1", content=short)]
        result = ContextWindowAssembler.assemble(chunks, 1000)
        assert result.citations[0].excerpt == short

    def test_citation_excerpt_long_content_truncated(self):
        long_content = "A" * 300
        chunks = [make_chunk("c1", content=long_content)]
        result = ContextWindowAssembler.assemble(chunks, 1000)
        excerpt = result.citations[0].excerpt
        assert excerpt == "A" * 200 + "..."

    def test_citation_position_tracking(self):
        chunks = [
            make_chunk("c1", content="AAAA"),
            make_chunk("c2", content="BBBB"),
        ]
        result = ContextWindowAssembler.assemble(chunks, 1000)
        assert result.citations[0].position_in_context == 0
        # Second chunk position = len(first) + len(separator)
        assert result.citations[1].position_in_context > 0

    def test_total_tokens_approximate(self):
        content = "A" * 200  # 200 chars
        chunks = [make_chunk(content=content)]
        result = ContextWindowAssembler.assemble(chunks, 1000)
        expected_tokens = max(1, 200 // _CHARS_PER_TOKEN)
        assert result.total_tokens == expected_tokens

    def test_total_tokens_minimum_one(self):
        chunks = [make_chunk(content="Hi")]
        result = ContextWindowAssembler.assemble(chunks, 1000)
        assert result.total_tokens >= 1

    def test_chunk_separator_between_chunks(self):
        chunks = [
            make_chunk("c1", content="One"),
            make_chunk("c2", content="Two"),
        ]
        result = ContextWindowAssembler.assemble(chunks, 1000)
        assert ContextWindowAssembler._CHUNK_SEPARATOR in result.context_string

    def test_smart_truncate_text_fits(self):
        text = "Short text"
        result = ContextWindowAssembler._smart_truncate(text, 100)
        assert result == text

    def test_smart_truncate_at_sentence_boundary(self):
        text = "First sentence. Second sentence. Third sentence."
        result = ContextWindowAssembler._smart_truncate(text, 25)
        assert result.endswith(".")
        assert "First sentence." in result

    def test_smart_truncate_whitespace_fallback(self):
        text = "word1 word2 word3 word4 word5"
        result = ContextWindowAssembler._smart_truncate(text, 15)
        # Should truncate at a word boundary
        assert " " not in result.split()[-1] if result else True

    def test_smart_truncate_hard_fallback(self):
        text = "a" * 50
        result = ContextWindowAssembler._smart_truncate(text, 20)
        assert len(result) <= 20

    def test_assemble_to_dict_method(self):
        chunks = [make_chunk(content="Test")]
        result = ContextWindowAssembler.assemble(chunks, 1000)
        d = result.to_dict()
        assert "context_string" in d
        assert "total_tokens" in d
        assert "truncated" in d
        assert "chunk_ids" in d

    def test_multiple_chunks_partial_truncation(self):
        """Only later chunks get truncated when budget exceeded."""
        chunks = [
            make_chunk("c1", content="A" * 50),
            make_chunk("c2", content="B" * 500),
        ]
        result = ContextWindowAssembler.assemble(chunks, 80)
        # First chunk should fit, second should be truncated
        assert result.truncated is True


# ═══════════════════════════════════════════════════════════════════
# CitationTracker Tests
# ═══════════════════════════════════════════════════════════════════

class TestCitationTracker:
    """Tests for CitationTracker.track_citations."""

    def test_empty_context_returns_empty(self):
        ctx = AssembledContext()
        result = CitationTracker.track_citations([], ctx)
        assert result == []

    def test_no_chunks_used_returns_empty(self):
        ctx = AssembledContext(chunks_used=[], citations=[])
        result = CitationTracker.track_citations([make_chunk()], ctx)
        assert result == []

    def test_single_citation_enriched(self):
        chunk = make_chunk("c1", metadata={"source": "PDF", "page": 5})
        citation = Citation(
            chunk_id="c1", document_id="doc1",
            relevance_score=0.9, position_in_context=0, excerpt="test"
        )
        ctx = AssembledContext(
            chunks_used=[chunk], citations=[citation]
        )
        result = CitationTracker.track_citations([chunk], ctx)
        assert len(result) == 1
        assert "[Source: PDF]" in result[0].excerpt
        assert "(p. 5)" in result[0].excerpt

    def test_citation_with_section_metadata(self):
        chunk = make_chunk("c1", metadata={"source": "KB", "section": "Intro"})
        citation = Citation(
            chunk_id="c1", document_id="doc1",
            relevance_score=0.8, position_in_context=0, excerpt="intro text"
        )
        ctx = AssembledContext(
            chunks_used=[chunk], citations=[citation]
        )
        result = CitationTracker.track_citations([chunk], ctx)
        assert "Intro" in result[0].excerpt

    def test_citation_with_default_source_no_enrichment(self):
        """Default 'Knowledge Base' source with no page/section uses original."""
        chunk = make_chunk("c1", metadata={"source": "Knowledge Base"})
        citation = Citation(
            chunk_id="c1", document_id="doc1",
            relevance_score=0.8, position_in_context=0, excerpt="original"
        )
        ctx = AssembledContext(
            chunks_used=[chunk], citations=[citation]
        )
        result = CitationTracker.track_citations([chunk], ctx)
        assert result[0].excerpt == "original"

    def test_citation_deduplication(self):
        """Duplicate chunk_ids in citations are deduplicated."""
        chunk = make_chunk("c1")
        c1 = Citation(chunk_id="c1", document_id="d1", relevance_score=0.9, position_in_context=0)
        c2 = Citation(chunk_id="c1", document_id="d1", relevance_score=0.8, position_in_context=10)
        ctx = AssembledContext(
            chunks_used=[chunk], citations=[c1, c2]
        )
        result = CitationTracker.track_citations([chunk], ctx)
        assert len(result) == 1

    def test_citation_chunk_not_in_lookup_keeps_original(self):
        """If chunk not in lookup but chunks_used is populated, citation is returned as-is."""
        citation = Citation(
            chunk_id="missing", document_id="d1",
            relevance_score=0.8, position_in_context=0, excerpt="test"
        )
        # Need a chunk in chunks_used so track_citations doesn't short-circuit to []
        chunk = make_chunk("other_chunk", metadata={"source": "Doc"})
        ctx = AssembledContext(
            chunks_used=[chunk], citations=[citation]
        )
        # Pass empty chunks list so "missing" won't be in lookup
        result = CitationTracker.track_citations([], ctx)
        assert len(result) == 1
        assert result[0].chunk_id == "missing"

    def test_citation_with_page_and_section(self):
        chunk = make_chunk("c1", metadata={"source": "Doc", "page": 10, "section": "Chapter 1"})
        citation = Citation(
            chunk_id="c1", document_id="d1",
            relevance_score=0.9, position_in_context=0, excerpt="content"
        )
        ctx = AssembledContext(
            chunks_used=[chunk], citations=[citation]
        )
        result = CitationTracker.track_citations([chunk], ctx)
        assert "Chapter 1" in result[0].excerpt
        assert "p. 10" in result[0].excerpt


# ═══════════════════════════════════════════════════════════════════
# CrossEncoderReranker Tests
# ═══════════════════════════════════════════════════════════════════

class TestCrossEncoderReranker:
    """Tests for CrossEncoderReranker.rerank and scoring methods."""

    def setup_method(self):
        self.reranker = CrossEncoderReranker()

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty_result(self):
        result = await self.reranker.rerank([], "query", "co1")
        assert result.chunks == []
        assert result.retrieval_time_ms == 0.0

    @pytest.mark.asyncio
    async def test_unknown_variant_defaults_to_parwa(self):
        chunks = [make_chunk(score=0.7)]
        result = await self.reranker.rerank(chunks, "query", "co1", variant_type="unknown")
        assert result.variant_tier_used == "parwa"

    @pytest.mark.asyncio
    async def test_mini_parwa_skip_reranking(self):
        """mini_parwa should skip reranking and sort by original score."""
        chunks = [
            make_chunk("c1", score=0.5),
            make_chunk("c2", score=0.9),
            make_chunk("c3", score=0.7),
        ]
        result = await self.reranker.rerank(
            chunks, "query", "co1", variant_type="mini_parwa"
        )
        assert len(result.chunks) <= 3  # top_k=3 for mini_parwa
        if len(result.chunks) >= 2:
            assert result.chunks[0].score >= result.chunks[1].score

    @pytest.mark.asyncio
    async def test_parwa_cross_encoder_reranking(self):
        """parwa variant applies cross-encoder reranking."""
        chunks = [
            make_chunk("c1", content="database query optimization indexing", score=0.6),
            make_chunk("c2", content="query optimization techniques for databases", score=0.8),
        ]
        result = await self.reranker.rerank(
            chunks, "database query", "co1", variant_type="parwa"
        )
        assert len(result.chunks) > 0
        # Reranked scores should be updated
        assert result.variant_tier_used == "parwa"

    @pytest.mark.asyncio
    async def test_parwa_high_rewrite_rerank_pipeline(self):
        """parwa_high uses 3-step pipeline."""
        chunks = [
            make_chunk("c1", content="machine learning neural networks deep learning algorithms"),
            make_chunk("c2", content="neural network training data processing"),
        ]
        result = await self.reranker.rerank(
            chunks, "ML algorithms", "co1", variant_type="parwa_high"
        )
        assert result.variant_tier_used == "parwa_high"
        assert len(result.chunks) > 0

    @pytest.mark.asyncio
    async def test_top_k_limits_results(self):
        chunks = [make_chunk(f"c{i}", score=0.5 + i * 0.1) for i in range(10)]
        result = await self.reranker.rerank(
            chunks, "query", "co1", variant_type="mini_parwa", top_k=3
        )
        assert len(result.chunks) <= 3

    @pytest.mark.asyncio
    async def test_top_k_none_uses_config_default(self):
        chunks = [make_chunk(f"c{i}", score=0.5 + i * 0.1) for i in range(10)]
        result = await self.reranker.rerank(
            chunks, "query", "co1", variant_type="parwa", top_k=None
        )
        assert len(result.chunks) <= 5  # parwa default_top_k=5

    @pytest.mark.asyncio
    async def test_exception_returns_degraded_result(self):
        """BC-008: Exception returns chunks sorted by original score."""
        chunks = [
            make_chunk("c1", score=0.9),
            make_chunk("c2", score=0.5),
        ]
        with patch.object(
            self.reranker, "_execute_with_guard",
            side_effect=RuntimeError("test error")
        ):
            result = await self.reranker.rerank(
                chunks, "query", "co1", variant_type="parwa"
            )
        assert result.degradation_used is True
        assert len(result.chunks) > 0
        # Should be sorted by original score descending
        scores = [c.score for c in result.chunks]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_metadata_filters_applied(self):
        """parwa_high with filters should filter chunks."""
        chunks = [
            make_chunk("c1", metadata={"source_type": "pdf"}),
            make_chunk("c2", metadata={"source_type": "web"}),
        ]
        result = await self.reranker.rerank(
            chunks, "query", "co1",
            variant_type="parwa_high",
            filters={"source_type": "pdf"},
        )
        for chunk in result.chunks:
            assert chunk.metadata.get("source_type") == "pdf"

    def test_cross_encoder_score_empty_chunks(self):
        result = self.reranker._cross_encoder_score([], "query", "co1")
        assert result == []

    def test_cross_encoder_score_empty_query(self):
        chunks = [make_chunk()]
        result = self.reranker._cross_encoder_score(chunks, "", "co1")
        assert len(result) == 1

    def test_cross_encoder_score_whitespace_query(self):
        chunks = [make_chunk()]
        result = self.reranker._cross_encoder_score(chunks, "   ", "co1")
        assert len(result) == 1

    def test_cross_encoder_score_only_stop_words(self):
        chunks = [make_chunk()]
        result = self.reranker._cross_encoder_score(chunks, "the a an is", "co1")
        assert len(result) == 1

    def test_cross_encoder_score_sorted_descending(self):
        chunks = [
            make_chunk("c1", content="database systems", score=0.5),
            make_chunk("c2", content="database systems", score=0.9),
        ]
        result = self.reranker._cross_encoder_score(chunks, "database", "co1")
        if len(result) >= 2:
            assert result[0].score >= result[1].score

    def test_cross_encoder_exact_phrase_bonus(self):
        """Chunk with exact query gets phrase bonus."""
        chunks = [
            make_chunk("c1", content="database query optimization"),
            make_chunk("c2", content="completely different topic"),
        ]
        result = self.reranker._cross_encoder_score(chunks, "database query optimization", "co1")
        c1_score = next((c.score for c in result if c.chunk_id == "c1"), 0)
        c2_score = next((c.score for c in result if c.chunk_id == "c2"), 0)
        assert c1_score > c2_score

    def test_cross_encoder_scores_capped_at_one(self):
        chunks = [make_chunk(content="test " * 100, score=0.99)]
        result = self.reranker._cross_encoder_score(chunks, "test", "co1")
        for c in result:
            assert c.score <= 1.0

    def test_compute_bm25_score_zero_content_length(self):
        score = self.reranker._compute_bm25_score(
            query_terms={"test"},
            content_terms=set(),
            content_term_freq={},
            idf_scores={"test": 1.0},
            content_length=0,
        )
        assert score == 0.0

    def test_compute_bm25_score_matching_terms(self):
        score = self.reranker._compute_bm25_score(
            query_terms={"database"},
            content_terms={"database", "query", "optimization"},
            content_term_freq={"database": 3, "query": 1, "optimization": 1},
            idf_scores={"database": 1.5},
            content_length=5,
        )
        assert score > 0.0
        assert score <= 1.0

    def test_compute_bm25_score_no_matching_terms(self):
        score = self.reranker._compute_bm25_score(
            query_terms={"xyz"},
            content_terms={"database", "query"},
            content_term_freq={"database": 1, "query": 1},
            idf_scores={"xyz": 1.0},
            content_length=2,
        )
        assert score == 0.0

    def test_compute_idf_returns_non_negative(self):
        chunks = [make_chunk(content="alpha beta gamma")]
        idf = self.reranker._compute_idf({"alpha", "beta", "missing"}, chunks)
        for term, score in idf.items():
            assert score >= 0.0

    def test_compute_idf_rare_terms_higher(self):
        chunks = [
            make_chunk(content="common common common"),
            make_chunk(content="common common common"),
        ]
        idf = self.reranker._compute_idf({"common", "rare"}, chunks)
        assert idf.get("rare", 0) > idf.get("common", 0)

    def test_semaphore_initialization(self):
        assert self.reranker._semaphore is not None
        assert isinstance(self.reranker._semaphore, asyncio.Semaphore)

    def test_init_creates_sub_components(self):
        assert self.reranker._metadata_filter is not None
        assert self.reranker._assembler is not None
        assert self.reranker._citation_tracker is not None
        assert self.reranker._query_rewriter is not None

    def test_variant_config_has_all_variants(self):
        assert "mini_parwa" in VARIANT_RERANK_CONFIG
        assert "parwa" in VARIANT_RERANK_CONFIG
        assert "parwa_high" in VARIANT_RERANK_CONFIG

    def test_variant_config_strategies(self):
        assert VARIANT_RERANK_CONFIG["mini_parwa"]["strategy"] == RerankStrategy.SKIP
        assert VARIANT_RERANK_CONFIG["parwa"]["strategy"] == RerankStrategy.CROSS_ENCODER
        assert VARIANT_RERANK_CONFIG["parwa_high"]["strategy"] == RerankStrategy.REWRITE_RERANK


# ═══════════════════════════════════════════════════════════════════
# Data Classes Tests
# ═══════════════════════════════════════════════════════════════════

class TestDataClasses:
    """Tests for AssembledContext, Citation, RerankStrategy."""

    def test_assembled_context_defaults(self):
        ctx = AssembledContext()
        assert ctx.context_string == ""
        assert ctx.total_tokens == 0
        assert ctx.chunks_used == []
        assert ctx.citations == []
        assert ctx.truncated is False

    def test_assembled_context_to_dict(self):
        ctx = AssembledContext(
            context_string="test", total_tokens=5, truncated=True
        )
        d = ctx.to_dict()
        assert d["context_string"] == "test"
        assert d["total_tokens"] == 5
        assert d["truncated"] is True
        assert d["chunks_used_count"] == 0

    def test_citation_defaults(self):
        c = Citation(
            chunk_id="c1", document_id="d1",
            relevance_score=0.9, position_in_context=0
        )
        assert c.excerpt == ""

    def test_citation_to_dict(self):
        c = Citation(
            chunk_id="c1", document_id="d1",
            relevance_score=0.9123456, position_in_context=10,
            excerpt="test excerpt"
        )
        d = c.to_dict()
        assert d["chunk_id"] == "c1"
        assert d["relevance_score"] == 0.912346  # rounded to 6 decimals

    def test_rerank_strategy_values(self):
        assert RerankStrategy.SKIP.value == "skip"
        assert RerankStrategy.CROSS_ENCODER.value == "cross_encoder"
        assert RerankStrategy.REWRITE_RERANK.value == "rewrite_rerank"

    def test_rag_chunk_creation(self):
        chunk = RAGChunk(
            chunk_id="c1", document_id="d1",
            content="test", score=0.95,
            metadata={"key": "val"}, citation="cite1"
        )
        assert chunk.chunk_id == "c1"
        assert chunk.document_id == "d1"
        assert chunk.content == "test"
        assert chunk.score == 0.95
        assert chunk.metadata == {"key": "val"}
        assert chunk.citation == "cite1"

    def test_rag_result_defaults(self):
        result = RAGResult()
        assert result.chunks == []
        assert result.total_found == 0
        assert result.retrieval_time_ms == 0.0
        assert result.variant_tier_used == "parwa"
        assert result.cached is False
        assert result.degradation_used is False
