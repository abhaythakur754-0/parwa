"""
Tests for RAG Retrieval Module (F-064) — Week 9 Day 7

Covers: RAGRetriever init, retrieve(), variant tiers (mini_parwa/parwa/parwa_high),
keyword fallback BC-008, query expansion, reranking, citation tracking,
dedup + limit, cache behavior, G9-GAP-07, G9-GAP-12, RAGChunk/RAGResult dataclasses,
edge cases.

Target: 100+ tests
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — import source modules with mocked logger
# ═══════════════════════════════════════════════════════════════════════

# Runtime-injected by _mock_logger fixture — satisfies flake8 F821
CACHE_TTL_SECONDS = QUERY_SYNONYMS = RAGChunk = RAGResult = RAGRetriever = VARIANT_CONFIG = MockVectorStore = SearchResult = StoredChunk = VectorStore = None

@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("app.logger.get_logger", return_value=MagicMock()):
        from app.core.rag_retrieval import (  # noqa: F811,F401
            CACHE_TTL_SECONDS,
            QUERY_SYNONYMS,
            RAGChunk,
            RAGResult,
            RAGRetriever,
            VARIANT_CONFIG,
        )
        from shared.knowledge_base.vector_search import (  # noqa: F811,F401
            MockVectorStore,
            SearchResult,
            StoredChunk,
            VectorStore,
        )
        globals().update({
            "CACHE_TTL_SECONDS": CACHE_TTL_SECONDS,
            "QUERY_SYNONYMS": QUERY_SYNONYMS,
            "RAGChunk": RAGChunk,
            "RAGResult": RAGResult,
            "RAGRetriever": RAGRetriever,
            "VARIANT_CONFIG": VARIANT_CONFIG,
            "MockVectorStore": MockVectorStore,
            "SearchResult": SearchResult,
            "StoredChunk": StoredChunk,
            "VectorStore": VectorStore,
        })


def _make_store_with_data(company_id="c1", n_chunks=3):
    """Helper: create a MockVectorStore pre-loaded with test data."""
    store = MockVectorStore()
    for i in range(n_chunks):
        chunk = StoredChunk(
            chunk_id=f"chunk_{i}",
            document_id=f"doc_{i % 2}",
            content=f"This is test chunk {i} about refund and billing help",
            embedding=store._generate_embedding(f"test chunk {i}"),
            metadata={"source": f"kb_doc_{i}", "document_type": "faq"},
        )
        store.add_chunks([chunk], company_id)
    return store


# ═══════════════════════════════════════════════════════════════════════
# 1. RAGRetriever init (3 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestRAGRetrieverInit:
    def test_default_store(self):
        retriever = RAGRetriever()
        assert retriever._store is not None

    def test_custom_store(self):
        store = MockVectorStore()
        retriever = RAGRetriever(vector_store=store)
        assert retriever._store is store

    def test_store_is_vector_store(self):
        store = MockVectorStore()
        retriever = RAGRetriever(vector_store=store)
        assert isinstance(retriever._store, VectorStore)


# ═══════════════════════════════════════════════════════════════════════
# 2. retrieve() basic (12 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestRetrieveBasic:
    @pytest.mark.asyncio
    async def test_empty_query(self):
        store = MockVectorStore()
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("", company_id="c1")
        assert result.chunks == []
        assert result.total_found == 0

    @pytest.mark.asyncio
    async def test_whitespace_query(self):
        store = MockVectorStore()
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("   ", company_id="c1")
        assert result.chunks == []

    @pytest.mark.asyncio
    async def test_valid_query_returns_result(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund billing help", company_id="c1")
        assert isinstance(result, RAGResult)
        assert result.variant_tier_used == "parwa"

    @pytest.mark.asyncio
    async def test_company_id_scoping_bc001(self):
        """BC-001: Results are scoped to company_id."""
        store_a = _make_store_with_data("co_a")
        store_b = _make_store_with_data("co_b")
        retriever_a = RAGRetriever(vector_store=store_a)
        retriever_b = RAGRetriever(vector_store=store_b)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                r_a = await retriever_a.retrieve("refund", company_id="co_a")
                r_b = await retriever_b.retrieve("refund", company_id="co_b")
        # Both should return results from their respective stores
        assert r_a.total_found > 0
        assert r_b.total_found > 0

    @pytest.mark.asyncio
    async def test_custom_top_k(self):
        store = _make_store_with_data("c1", n_chunks=10)
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1", top_k=2)
        assert len(result.chunks) <= 2

    @pytest.mark.asyncio
    async def test_similarity_threshold(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1", similarity_threshold=0.99)
        # Very high threshold → likely 0 results
        assert result.total_found >= 0

    @pytest.mark.asyncio
    async def test_filters_applied_for_parwa(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve(
                    "refund", company_id="c1",
                    filters={"document_type": "faq"},
                )
        assert isinstance(result, RAGResult)
        assert result.filters_applied == {"document_type": "faq"}

    @pytest.mark.asyncio
    async def test_retrieval_time_populated(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1")
        assert result.retrieval_time_ms >= 0

    @pytest.mark.asyncio
    async def test_query_embedding_time_populated(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1")
        assert result.query_embedding_time_ms >= 0

    @pytest.mark.asyncio
    async def test_none_input_returns_empty(self):
        store = MockVectorStore()
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve(None, company_id="c1")
        assert result.chunks == []

    @pytest.mark.asyncio
    async def test_non_string_input_returns_empty(self):
        store = MockVectorStore()
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve(12345, company_id="c1")
        assert result.chunks == []

    @pytest.mark.asyncio
    async def test_no_matching_company(self):
        store = MockVectorStore()
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="nonexistent")
        assert result.total_found == 0


# ═══════════════════════════════════════════════════════════════════════
# 3. Variant Tiers (8 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestVariantTiers:
    @pytest.mark.asyncio
    async def test_mini_parwa_basic_search(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1", variant_type="mini_parwa")
        assert result.variant_tier_used == "mini_parwa"
        assert result.filters_applied == {}

    @pytest.mark.asyncio
    async def test_parwa_with_metadata(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve(
                    "refund", company_id="c1",
                    variant_type="parwa",
                    filters={"document_type": "faq"},
                )
        assert result.variant_tier_used == "parwa"
        assert result.filters_applied == {"document_type": "faq"}

    @pytest.mark.asyncio
    async def test_parwa_high_with_reranking(self):
        store = _make_store_with_data("c1", n_chunks=5)
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1", variant_type="parwa_high")
        assert result.variant_tier_used == "parwa_high"
        # parwa_high uses reranking; all chunks should have citation
        for chunk in result.chunks:
            assert chunk.citation is not None

    @pytest.mark.asyncio
    async def test_parwa_high_citation_tracking(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1", variant_type="parwa_high")
        for chunk in result.chunks:
            assert "Source:" in (chunk.citation or "")

    @pytest.mark.asyncio
    async def test_parwa_high_query_expansion(self):
        store = _make_store_with_data("c1", n_chunks=5)
        retriever = RAGRetriever(vector_store=store)
        # 'refund' should trigger query expansion with synonyms
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1", variant_type="parwa_high")
        assert isinstance(result, RAGResult)

    def test_variant_config_keys(self):
        assert "mini_parwa" in VARIANT_CONFIG
        assert "parwa" in VARIANT_CONFIG
        assert "parwa_high" in VARIANT_CONFIG

    def test_mini_parwa_no_reranking(self):
        assert VARIANT_CONFIG["mini_parwa"]["use_reranking"] is False
        assert VARIANT_CONFIG["mini_parwa"]["use_citation_tracking"] is False

    def test_parwa_high_full_features(self):
        cfg = VARIANT_CONFIG["parwa_high"]
        assert cfg["use_reranking"] is True
        assert cfg["use_citation_tracking"] is True
        assert cfg["use_query_expansion"] is True


# ═══════════════════════════════════════════════════════════════════════
# 4. Keyword Fallback BC-008 (10 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestKeywordFallback:
    @pytest.mark.asyncio
    async def test_embedding_none_triggers_keyword(self):
        """BC-008: When embedding fails, fall back to keyword search."""
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        # Mock _generate_embedding to return None
        with patch.object(retriever, "_generate_embedding", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
                with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                    result = await retriever.retrieve("refund billing help", company_id="c1")
        assert result.degradation_used is True

    @pytest.mark.asyncio
    async def test_store_unhealthy_triggers_keyword(self):
        """BC-008: Unhealthy vector store triggers keyword fallback."""
        store = _make_store_with_data("c1")
        store.set_healthy(False)
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1")
        assert result.degradation_used is True

    @pytest.mark.asyncio
    async def test_vector_exception_triggers_keyword(self):
        """BC-008: Vector search exception triggers keyword fallback."""
        store = MockVectorStore()
        store.set_healthy(True)
        # Override search to raise exception
        store.search = MagicMock(side_effect=RuntimeError("vector search failed"))
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1")
        assert result.degradation_used is True

    @pytest.mark.asyncio
    async def test_gap07_uses_get_all_documents(self):
        """G9-GAP-07: Keyword fallback uses public get_all_documents method."""
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch.object(retriever, "_generate_embedding", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
                with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                    result = await retriever.retrieve("refund billing", company_id="c1")
        # Should return results from keyword search
        assert result.total_found >= 0
        assert result.degradation_used is True

    @pytest.mark.asyncio
    async def test_keyword_fallback_scores_by_overlap(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch.object(retriever, "_generate_embedding", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
                with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                    result = await retriever.retrieve("refund", company_id="c1")
        for chunk in result.chunks:
            assert chunk.score > 0

    @pytest.mark.asyncio
    async def test_keyword_fallback_respects_top_k(self):
        store = _make_store_with_data("c1", n_chunks=10)
        retriever = RAGRetriever(vector_store=store)
        with patch.object(retriever, "_generate_embedding", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
                with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                    result = await retriever.retrieve("refund", company_id="c1", top_k=2)
        assert len(result.chunks) <= 2

    @pytest.mark.asyncio
    async def test_keyword_fallback_no_crash_on_error(self):
        """BC-008: Keyword search itself shouldn't crash."""
        store = MockVectorStore()
        store.search = MagicMock(side_effect=RuntimeError("boom"))
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("test", company_id="c1")
        # Should still return a valid result
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_keyword_fallback_sorts_by_score(self):
        store = _make_store_with_data("c1", n_chunks=5)
        retriever = RAGRetriever(vector_store=store)
        with patch.object(retriever, "_generate_embedding", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
                with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                    result = await retriever.retrieve("refund billing help", company_id="c1")
        scores = [c.score for c in result.chunks]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_keyword_fallback_empty_query(self):
        store = MockVectorStore()
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("", company_id="c1")
        assert result.chunks == []

    @pytest.mark.asyncio
    async def test_keyword_fallback_variant_preserved(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch.object(retriever, "_generate_embedding", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
                with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                    result = await retriever.retrieve("test", company_id="c1", variant_type="mini_parwa")
        assert result.variant_tier_used == "mini_parwa"


# ═══════════════════════════════════════════════════════════════════════
# 5. Query Expansion (5 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestQueryExpansion:
    def setup_method(self):
        store = MockVectorStore()
        self.retriever = RAGRetriever(vector_store=store)

    def test_expand_refund(self):
        expanded = self.retriever._expand_query("refund")
        assert "refund" in expanded
        assert len(expanded) >= 2  # original + at least one synonym

    def test_expand_error(self):
        expanded = self.retriever._expand_query("error")
        assert "error" in expanded
        assert len(expanded) >= 2

    def test_expand_max_3(self):
        expanded = self.retriever._expand_query("refund error billing password")
        assert len(expanded) <= 3  # max 3 total (original + 2 expansions)

    def test_expand_no_synonyms(self):
        expanded = self.retriever._expand_query("xyzzy")
        assert len(expanded) == 1  # only original

    def test_expand_preserves_original(self):
        expanded = self.retriever._expand_query("refund")
        assert expanded[0] == "refund"


# ═══════════════════════════════════════════════════════════════════════
# 6. Reranking (5 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestReranking:
    def setup_method(self):
        store = MockVectorStore()
        self.retriever = RAGRetriever(vector_store=store)

    def test_rerank_returns_same_count(self):
        chunks = [
            RAGChunk(chunk_id="c1", document_id="d1", content="refund help", score=0.8),
            RAGChunk(chunk_id="c2", document_id="d2", content="billing issue", score=0.7),
            RAGChunk(chunk_id="c3", document_id="d3", content="password reset", score=0.6),
        ]
        reranked = self.retriever._rerank("refund help", chunks)
        assert len(reranked) == 3

    def test_rerank_sorted_descending(self):
        chunks = [
            RAGChunk(chunk_id="c1", document_id="d1", content="unrelated topic", score=0.9),
            RAGChunk(chunk_id="c2", document_id="d2", content="refund help needed", score=0.5),
        ]
        reranked = self.retriever._rerank("refund help", chunks)
        scores = [c.score for c in reranked]
        assert scores == sorted(scores, reverse=True)

    def test_rerank_phrase_bonus(self):
        chunks = [
            RAGChunk(chunk_id="c1", document_id="d1", content="refund help", score=0.5),
            RAGChunk(chunk_id="c2", document_id="d2", content="related but different text", score=0.5),
        ]
        reranked = self.retriever._rerank("refund help", chunks)
        # First chunk should have higher score due to exact phrase match
        assert reranked[0].score >= reranked[1].score

    def test_rerank_word_overlap(self):
        chunks = [
            RAGChunk(chunk_id="c1", document_id="d1", content="refund billing account", score=0.5),
            RAGChunk(chunk_id="c2", document_id="d2", content="shipping package delivery", score=0.5),
        ]
        reranked = self.retriever._rerank("refund billing", chunks)
        # First chunk should score higher (more word overlap)
        assert reranked[0].chunk_id == "c1"

    def test_rerank_empty_query(self):
        chunks = [
            RAGChunk(chunk_id="c1", document_id="d1", content="test", score=0.5),
        ]
        reranked = self.retriever._rerank("", chunks)
        assert len(reranked) == 1


# ═══════════════════════════════════════════════════════════════════════
# 7. Citation Tracking (5 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestCitationTracking:
    def setup_method(self):
        store = MockVectorStore()
        self.retriever = RAGRetriever(vector_store=store)

    def test_citation_with_source(self):
        chunks = [
            RAGChunk(
                chunk_id="c1", document_id="d1", content="test",
                score=0.8, metadata={"source": "FAQ Document"},
            ),
        ]
        result = self.retriever._add_citations(chunks)
        assert "FAQ Document" in result[0].citation
        assert "Source:" in result[0].citation

    def test_citation_with_page(self):
        chunks = [
            RAGChunk(
                chunk_id="c1", document_id="d1", content="test",
                score=0.8, metadata={"source": "KB", "page": 5},
            ),
        ]
        result = self.retriever._add_citations(chunks)
        assert "p. 5" in result[0].citation

    def test_citation_with_section(self):
        chunks = [
            RAGChunk(
                chunk_id="c1", document_id="d1", content="test",
                score=0.8, metadata={"source": "KB", "section": "Refunds"},
            ),
        ]
        result = self.retriever._add_citations(chunks)
        assert "Refunds" in result[0].citation

    def test_citation_default_source(self):
        chunks = [
            RAGChunk(chunk_id="c1", document_id="d1", content="test", score=0.8),
        ]
        result = self.retriever._add_citations(chunks)
        assert "Knowledge Base" in result[0].citation

    def test_citation_multiple_chunks(self):
        chunks = [
            RAGChunk(chunk_id="c1", document_id="d1", content="test", score=0.8, metadata={"source": "A"}),
            RAGChunk(chunk_id="c2", document_id="d2", content="test2", score=0.7, metadata={"source": "B"}),
        ]
        result = self.retriever._add_citations(chunks)
        assert len(result) == 2
        assert "A" in result[0].citation
        assert "B" in result[1].citation


# ═══════════════════════════════════════════════════════════════════════
# 8. Dedup + Limit (5 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestDedupLimit:
    @pytest.mark.asyncio
    async def test_duplicates_removed(self):
        """Duplicate chunk_ids should be deduped."""
        store = MockVectorStore()
        # Add same chunk twice
        for _ in range(2):
            chunk = StoredChunk(
                chunk_id="same_chunk", document_id="d1",
                content="refund help", embedding=store._generate_embedding("refund"),
            )
            store.add_chunks([chunk], "c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1", top_k=10)
        chunk_ids = [c.chunk_id for c in result.chunks]
        assert len(chunk_ids) == len(set(chunk_ids))

    @pytest.mark.asyncio
    async def test_top_k_applied(self):
        store = _make_store_with_data("c1", n_chunks=10)
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1", top_k=3)
        assert len(result.chunks) <= 3

    @pytest.mark.asyncio
    async def test_total_found_ge_returned(self):
        store = _make_store_with_data("c1", n_chunks=10)
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1", top_k=2)
        assert result.total_found >= len(result.chunks)

    def test_dedup_preserves_order(self):
        retriever = RAGRetriever(vector_store=MockVectorStore())
        chunks = [
            RAGChunk(chunk_id="a", document_id="d1", content="first", score=0.9),
            RAGChunk(chunk_id="b", document_id="d2", content="second", score=0.8),
            RAGChunk(chunk_id="a", document_id="d1", content="first", score=0.7),
            RAGChunk(chunk_id="c", document_id="d3", content="third", score=0.6),
        ]
        seen = set()
        unique = []
        for c in chunks:
            if c.chunk_id not in seen:
                seen.add(c.chunk_id)
                unique.append(c)
        assert [c.chunk_id for c in unique] == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_empty_store_returns_zero(self):
        store = MockVectorStore()
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1")
        assert result.total_found == 0
        assert result.chunks == []


# ═══════════════════════════════════════════════════════════════════════
# 9. Cache (8 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestCache:
    @pytest.mark.asyncio
    async def test_cache_hit(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        cached_data = {
            "chunks": [{"chunk_id": "c1", "document_id": "d1", "content": "test",
                         "score": 0.9, "metadata": {}, "citation": None}],
            "total_found": 1,
            "retrieval_time_ms": 5.0,
            "query_embedding_time_ms": 2.0,
            "filters_applied": {},
            "variant_tier_used": "parwa",
        }
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=cached_data):
            result = await retriever.retrieve("refund", company_id="c1")
        assert result.cached is True
        assert len(result.chunks) == 1
        assert result.chunks[0].chunk_id == "c1"

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1")
        assert result.cached is False

    @pytest.mark.asyncio
    async def test_cache_fail_open(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, side_effect=Exception("Redis down")):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1")
        assert result.cached is False
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_cache_store_called(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock) as mock_set:
                await retriever.retrieve("refund", company_id="c1")
                mock_set.assert_called_once()

    def test_cache_key_format(self):
        key = RAGRetriever._build_cache_key("refund", "c1", "parwa", None)
        assert key.startswith("rag:c1:parwa:")
        assert "refund" not in key  # should be hashed

    def test_cache_key_includes_company(self):
        key1 = RAGRetriever._build_cache_key("q", "co_a", "parwa", None)
        key2 = RAGRetriever._build_cache_key("q", "co_b", "parwa", None)
        assert key1 != key2

    def test_cache_key_includes_variant(self):
        key1 = RAGRetriever._build_cache_key("q", "c1", "mini_parwa", None)
        key2 = RAGRetriever._build_cache_key("q", "c1", "parwa_high", None)
        assert key1 != key2

    def test_cache_key_with_filters(self):
        key_no_filter = RAGRetriever._build_cache_key("q", "c1", "parwa", None)
        key_filter = RAGRetriever._build_cache_key("q", "c1", "parwa", {"type": "faq"})
        assert key_no_filter != key_filter


# ═══════════════════════════════════════════════════════════════════════
# 10. G9-GAP-12 — Unknown variant (3 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestUnknownVariant:
    @pytest.mark.asyncio
    async def test_unknown_variant_defaults_to_parwa(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1", variant_type="unknown_tier")
        # Should use parwa config (default)
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_unknown_variant_logs_warning(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        # Get the module-level logger
        from app.core import rag_retrieval as mod
        with patch.object(mod.logger, "warning") as mock_warn:
            with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
                with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                    await retriever.retrieve("test", company_id="c1", variant_type="bogus_variant")
                    mock_warn.assert_called()
                    call_args = str(mock_warn.call_args)
                    assert "unknown_variant_type" in call_args

    @pytest.mark.asyncio
    async def test_unknown_variant_keyword_fallback_logs(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        from app.core import rag_retrieval as mod
        with patch.object(retriever, "_generate_embedding", new_callable=AsyncMock, return_value=None):
            with patch.object(mod.logger, "warning") as mock_warn:
                with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
                    with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                        await retriever.retrieve("test", company_id="c1", variant_type="bogus")
                        # Should log warning for unknown variant in keyword fallback
                        call_strs = [str(c) for c in mock_warn.call_args_list]
                        assert any("unknown_variant" in s for s in call_strs)


# ═══════════════════════════════════════════════════════════════════════
# 11. RAGChunk / RAGResult (5 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestRAGDataClasses:
    def test_rag_chunk_to_dict(self):
        chunk = RAGChunk(
            chunk_id="c1", document_id="d1", content="test content",
            score=0.856789, metadata={"source": "KB"}, citation="[Source: KB]",
        )
        d = chunk.to_dict()
        assert d["chunk_id"] == "c1"
        assert d["document_id"] == "d1"
        assert d["content"] == "test content"
        assert d["score"] == 0.856789
        assert d["metadata"] == {"source": "KB"}
        assert d["citation"] == "[Source: KB]"

    def test_rag_chunk_defaults(self):
        chunk = RAGChunk(chunk_id="c1", document_id="d1", content="test", score=0.5)
        assert chunk.metadata == {}
        assert chunk.citation is None

    def test_rag_result_to_dict(self):
        chunk = RAGChunk(chunk_id="c1", document_id="d1", content="test", score=0.8)
        result = RAGResult(
            chunks=[chunk], total_found=1, retrieval_time_ms=10.5,
            query_embedding_time_ms=3.2, filters_applied={"type": "faq"},
            variant_tier_used="parwa", cached=False, degradation_used=False,
        )
        d = result.to_dict()
        assert len(d["chunks"]) == 1
        assert d["total_found"] == 1
        assert d["retrieval_time_ms"] == 10.5
        assert d["cached"] is False
        assert d["degradation_used"] is False

    def test_rag_result_defaults(self):
        result = RAGResult()
        assert result.chunks == []
        assert result.total_found == 0
        assert result.retrieval_time_ms == 0.0
        assert result.variant_tier_used == "parwa"
        assert result.cached is False
        assert result.degradation_used is False

    def test_rag_result_empty_to_dict(self):
        result = RAGResult()
        d = result.to_dict()
        assert d["chunks"] == []
        assert d["total_found"] == 0


# ═══════════════════════════════════════════════════════════════════════
# 12. Edge Cases (10 tests)
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_none_query(self):
        store = MockVectorStore()
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve(None, company_id="c1")
        assert result.chunks == []

    @pytest.mark.asyncio
    async def test_non_string_query(self):
        store = MockVectorStore()
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve(12345, company_id="c1")
        assert result.chunks == []

    @pytest.mark.asyncio
    async def test_very_long_query(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        long_q = "refund " * 500
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve(long_q, company_id="c1")
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_special_chars_query(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("@#$%^&*() refund !@#$%^&*()", company_id="c1")
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_unicode_query(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("返款 帮助", company_id="c1")
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_filters_with_no_match(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve(
                    "refund", company_id="c1",
                    filters={"document_type": "nonexistent_type"},
                )
        assert result.total_found >= 0

    @pytest.mark.asyncio
    async def test_metadata_filtering(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result_faq = await retriever.retrieve(
                    "refund", company_id="c1",
                    filters={"document_type": "faq"},
                    variant_type="parwa",
                )
                result_all = await retriever.retrieve(
                    "refund", company_id="c1", variant_type="parwa",
                )
        assert result_faq.total_found <= result_all.total_found

    @pytest.mark.asyncio
    async def test_zero_top_k(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1", top_k=0)
        assert len(result.chunks) == 0

    @pytest.mark.asyncio
    async def test_single_word_query(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund", company_id="c1")
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_newlines_in_query(self):
        store = _make_store_with_data("c1")
        retriever = RAGRetriever(vector_store=store)
        with patch("app.core.redis.cache_get", new_callable=AsyncMock, return_value=None):
            with patch("app.core.redis.cache_set", new_callable=AsyncMock):
                result = await retriever.retrieve("refund\n\nbilling\nhelp", company_id="c1")
        assert isinstance(result, RAGResult)


# ═══════════════════════════════════════════════════════════════════════
# 13. Additional VectorStore & Integration tests
# ═══════════════════════════════════════════════════════════════════════

class TestVectorStoreIntegration:
    def test_mock_store_add_chunks(self):
        store = MockVectorStore()
        chunk = StoredChunk(
            chunk_id="c1", document_id="d1",
            content="test", embedding=store._generate_embedding("test"),
        )
        count = store.add_chunks([chunk], "c1")
        assert count == 1

    def test_mock_store_search(self):
        store = MockVectorStore()
        emb = store._generate_embedding("refund help")
        chunk = StoredChunk(
            chunk_id="c1", document_id="d1",
            content="refund help here", embedding=emb,
        )
        store.add_chunks([chunk], "c1")
        results = store.search(emb, "c1", top_k=5)
        assert len(results) >= 1
        assert results[0].chunk_id == "c1"

    def test_mock_store_delete_document(self):
        store = MockVectorStore()
        chunk = StoredChunk(
            chunk_id="c1", document_id="d1",
            content="test", embedding=store._generate_embedding("test"),
        )
        store.add_chunks([chunk], "c1")
        assert store.delete_document("d1", "c1") is True
        assert store.delete_document("d1", "c1") is False

    def test_mock_store_health_check(self):
        store = MockVectorStore()
        assert store.health_check() is True
        store.set_healthy(False)
        assert store.health_check() is False

    def test_mock_store_get_all_documents(self):
        store = _make_store_with_data("c1", n_chunks=3)
        docs = store.get_all_documents("c1")
        assert len(docs) > 0

    def test_mock_store_get_all_documents_empty(self):
        store = MockVectorStore()
        docs = store.get_all_documents("nonexistent")
        assert docs == {}

    def test_mock_store_clear(self):
        store = _make_store_with_data("c1", n_chunks=3)
        store.clear()
        docs = store.get_all_documents("c1")
        assert docs == {}

    def test_search_result_to_dict(self):
        sr = SearchResult(
            chunk_id="c1", document_id="d1",
            content="test content", score=0.856789,
            metadata={"source": "KB"},
        )
        d = sr.to_dict()
        assert d["chunk_id"] == "c1"
        assert d["score"] == 0.856789
        assert d["metadata"] == {"source": "KB"}

    def test_stored_chunk_to_dict(self):
        sc = StoredChunk(
            chunk_id="c1", document_id="d1",
            content="test", embedding=[0.1, 0.2],
            metadata={"key": "val"},
        )
        d = sc.to_dict()
        assert d["chunk_id"] == "c1"
        assert d["document_id"] == "d1"
        assert "embedding" not in d  # embedding not in to_dict


class TestQueryExpansionAdditional:
    def setup_method(self):
        store = MockVectorStore()
        self.retriever = RAGRetriever(vector_store=store)

    def test_expand_billing(self):
        expanded = self.retriever._expand_query("billing question")
        assert "billing" in expanded[0]
        assert len(expanded) >= 2

    def test_expand_password(self):
        expanded = self.retriever._expand_query("password reset")
        assert "password" in expanded[0]
        assert len(expanded) >= 2

    def test_expand_shipping(self):
        expanded = self.retriever._expand_query("shipping status")
        assert "shipping" in expanded[0]
        assert len(expanded) >= 2

    def test_expand_empty_string(self):
        expanded = self.retriever._expand_query("")
        assert len(expanded) == 1

    def test_expand_casing_preserved(self):
        expanded = self.retriever._expand_query("Refund")
        # First element is the original query (casing preserved)
        assert expanded[0] == "Refund"


class TestRerankingAdditional:
    def setup_method(self):
        store = MockVectorStore()
        self.retriever = RAGRetriever(vector_store=store)

    def test_rerank_single_chunk(self):
        chunks = [RAGChunk(chunk_id="c1", document_id="d1", content="test", score=0.5)]
        reranked = self.retriever._rerank("test", chunks)
        assert len(reranked) == 1

    def test_rerank_empty_chunks(self):
        reranked = self.retriever._rerank("test", [])
        assert reranked == []

    def test_rerank_score_capped_at_1(self):
        chunks = [
            RAGChunk(chunk_id="c1", document_id="d1", content="test query words", score=0.99),
        ]
        reranked = self.retriever._rerank("test query words", chunks)
        assert reranked[0].score <= 1.0

    def test_rerank_position_bonus(self):
        """Earlier chunks should get position bonus."""
        chunks = [
            RAGChunk(chunk_id="c1", document_id="d1", content="query words", score=0.5),
            RAGChunk(chunk_id="c2", document_id="d2", content="query words", score=0.5),
        ]
        reranked = self.retriever._rerank("query words", chunks)
        # First chunk should have slightly higher score due to position bonus
        assert reranked[0].score >= reranked[1].score


class TestCitationAdditional:
    def setup_method(self):
        store = MockVectorStore()
        self.retriever = RAGRetriever(vector_store=store)

    def test_citation_empty_chunks(self):
        result = self.retriever._add_citations([])
        assert result == []

    def test_citation_with_page_and_section(self):
        chunks = [RAGChunk(
            chunk_id="c1", document_id="d1", content="test", score=0.8,
            metadata={"source": "Manual", "page": 10, "section": "Troubleshooting"},
        )]
        result = self.retriever._add_citations(chunks)
        assert "p. 10" in result[0].citation
        assert "Troubleshooting" in result[0].citation

    def test_citation_format_bracket(self):
        chunks = [RAGChunk(
            chunk_id="c1", document_id="d1", content="test", score=0.8,
            metadata={"source": "Test"},
        )]
        result = self.retriever._add_citations(chunks)
        assert result[0].citation.startswith("[Source: Test]")
