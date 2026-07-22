"""
Week 2 Tests — CLARA RAG Advanced Retrieval (HyDE, Multi-Query, LLM Reranking)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


# ─── HyDE Tests ──────────────────────────────────────────────────


class TestHyDEGenerator:
    """Tests for HyDE (Hypothetical Document Embedding) generation."""

    @pytest.mark.asyncio
    async def test_generate_hypothetical_answer_success(self):
        """LLM returns a valid hypothetical answer."""
        mock_router = MagicMock()
        mock_decision = MagicMock()
        mock_decision.model_config.model_id = "llama-3.1-8b"
        mock_router.route.return_value = mock_decision
        mock_router.execute_llm_call.return_value = {
            "content": '{"answer": "To reset your password, go to Settings > Security > Reset Password."}'
        }

        with patch("app.core.rag.hyde.SmartRouter", return_value=mock_router):
            from app.core.rag.hyde import HyDEGenerator
            gen = HyDEGenerator()
            result = await gen.generate_hypothetical_answer(
                "How do I reset my password?", "company_123"
            )
        assert "password" in result.lower() or len(result) > 10

    @pytest.mark.asyncio
    async def test_generate_hypothetical_answer_fallback(self):
        """When LLM fails, returns original query as fallback (BC-008)."""
        mock_router = MagicMock()
        mock_router.route.side_effect = Exception("LLM unavailable")

        with patch("app.core.rag.hyde.SmartRouter", return_value=mock_router):
            from app.core.rag.hyde import HyDEGenerator
            gen = HyDEGenerator()
            result = await gen.generate_hypothetical_answer(
                "How do I reset my password?", "company_123"
            )
        assert "password" in result.lower()

    @pytest.mark.asyncio
    async def test_get_hyde_embedding_returns_list(self):
        """Embedding service returns a list of floats."""
        mock_router = MagicMock()
        mock_decision = MagicMock()
        mock_router.route.return_value = mock_decision
        mock_router.execute_llm_call.return_value = {
            "content": '{"answer": "Password reset via settings page."}'
        }
        mock_embed_svc = MagicMock()
        mock_embed_svc.generate_embedding.return_value = [0.1] * 384

        with patch("app.core.rag.hyde.SmartRouter", return_value=mock_router), \
             patch("app.core.rag.hyde.EmbeddingService", return_value=mock_embed_svc):
            from app.core.rag.hyde import HyDEGenerator
            gen = HyDEGenerator()
            result = await gen.get_hyde_embedding("test query", "co_1")
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_hyde_embedding_fallback(self):
        """When embedding fails, returns None (BC-008)."""
        mock_router = MagicMock()
        mock_router.route.side_effect = Exception("down")

        with patch("app.core.rag.hyde.SmartRouter", return_value=mock_router), \
             patch("app.core.rag.hyde.EmbeddingService", side_effect=Exception("no embed")):
            from app.core.rag.hyde import HyDEGenerator
            gen = HyDEGenerator()
            result = await gen.get_hyde_embedding("test", "co_1")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self):
        """Empty query returns empty string without LLM call."""
        with patch("app.core.rag.hyde.SmartRouter") as mock_cls:
            from app.core.rag.hyde import HyDEGenerator
            gen = HyDEGenerator()
            result = await gen.generate_hypothetical_answer("", "co_1")
        assert result == ""
        mock_cls.assert_not_called()


# ─── Multi-Query Tests ──────────────────────────────────────────


class TestMultiQueryRetriever:
    """Tests for Multi-Query Retrieval system."""

    @pytest.mark.asyncio
    async def test_generate_alternative_queries_success(self):
        """LLM returns 3 alternative query phrasings."""
        mock_router = MagicMock()
        mock_decision = MagicMock()
        mock_router.route.return_value = mock_decision
        mock_router.execute_llm_call.return_value = {
            "content": '["how to change my plan?", "plan upgrade options", "switch subscription tier"]'
        }

        with patch("app.core.rag.multi_query.SmartRouter", return_value=mock_router):
            from app.core.rag.multi_query import MultiQueryRetriever
            rq = MultiQueryRetriever()
            result = await rq.generate_alternative_queries(
                "I want to change my plan", "co_1"
            )
        assert isinstance(result, list)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_generate_alternative_queries_fallback(self):
        """When LLM fails, returns only original query (BC-008)."""
        mock_router = MagicMock()
        mock_router.route.side_effect = Exception("LLM down")

        with patch("app.core.rag.multi_query.SmartRouter", return_value=mock_router):
            from app.core.rag.multi_query import MultiQueryRetriever
            rq = MultiQueryRetriever()
            result = await rq.generate_alternative_queries(
                "I want a refund", "co_1"
            )
        assert result == ["I want a refund"]

    def test_merge_and_deduplicate_removes_dupes(self):
        """Duplicate chunk_ids are removed, keeping higher score."""
        from app.core.rag.multi_query import MultiQueryRetriever
        from app.core.rag_retrieval import RAGResult, RAGChunk

        rq = MultiQueryRetriever()
        chunk_a = RAGChunk(chunk_id="c1", document_id="d1", content="hello", score=0.8)
        chunk_b = RAGChunk(chunk_id="c1", document_id="d1", content="hello", score=0.9)
        chunk_c = RAGChunk(chunk_id="c2", document_id="d2", content="world", score=0.7)
        r1 = RAGResult(chunks=[chunk_a, chunk_c])
        r2 = RAGResult(chunks=[chunk_b])

        merged = rq._merge_and_deduplicate([r1, r2])
        ids = [c.chunk_id for c in merged]
        assert ids.count("c1") == 1  # deduplicated
        assert "c2" in ids

    def test_rank_by_aggregate_score(self):
        """Chunks in more queries rank higher."""
        from app.core.rag.multi_query import MultiQueryRetriever

        rq = MultiQueryRetriever()
        scores = {
            "c1": [0.9, 0.8, 0.85],  # 3 queries, avg 0.85
            "c2": [0.7],              # 1 query, avg 0.7
        }
        ranked = rq._rank_by_aggregate_score(scores)
        assert ranked[0][0] == "c1"  # higher aggregate score


# ─── LLM Reranker Tests ──────────────────────────────────────────


class TestLLMReranker:
    """Tests for LLM-based reranking."""

    @pytest.mark.asyncio
    async def test_rerank_success(self):
        """LLM scores chunks, results reordered by score."""
        from app.core.rag_retrieval import RAGChunk

        chunks = [
            RAGChunk(chunk_id="c1", document_id="d1", content="low relevance", score=0.5),
            RAGChunk(chunk_id="c2", document_id="d2", content="high relevance password reset", score=0.6),
        ]

        mock_router = MagicMock()
        mock_decision = MagicMock()
        mock_router.route.return_value = mock_decision
        mock_router.execute_llm_call.return_value = {
            "content": '{"scores": [{"chunk_id": "c1", "score": 3}, {"chunk_id": "c2", "score": 8}]}'
        }

        with patch("app.core.rag.llm_reranker.SmartRouter", return_value=mock_router):
            from app.core.rag.llm_reranker import LLMReranker
            reranker = LLMReranker()
            result = await reranker.rerank("password reset", chunks, "co_1")

        assert len(result) == 2
        assert result[0].chunk_id == "c2"  # higher score first

    @pytest.mark.asyncio
    async def test_rerank_fallback_to_bm25(self):
        """When LLM fails, falls back to BM25 scoring (BC-008)."""
        from app.core.rag_retrieval import RAGChunk

        chunks = [
            RAGChunk(chunk_id="c1", document_id="d1", content="password reset your account", score=0.5),
            RAGChunk(chunk_id="c2", document_id="d2", content="unrelated content", score=0.4),
        ]

        mock_router = MagicMock()
        mock_router.route.side_effect = Exception("LLM down")

        with patch("app.core.rag.llm_reranker.SmartRouter", return_value=mock_router):
            from app.core.rag.llm_reranker import LLMReranker
            reranker = LLMReranker()
            result = await reranker.rerank("password reset", chunks, "co_1")

        assert len(result) == 2
        # BM25 should rank c1 higher (word overlap with query)
        assert result[0].chunk_id == "c1"

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty(self):
        """Empty chunk list returns empty without crash."""
        mock_router = MagicMock()
        with patch("app.core.rag.llm_reranker.SmartRouter", return_value=mock_router):
            from app.core.rag.llm_reranker import LLMReranker
            reranker = LLMReranker()
            result = await reranker.rerank("test", [], "co_1")
        assert result == []

    @pytest.mark.asyncio
    async def test_batch_scoring(self):
        """Verify chunks are batched (max 5 per call)."""
        from app.core.rag_retrieval import RAGChunk

        chunks = [RAGChunk(chunk_id=f"c{i}", document_id=f"d{i}", content=f"chunk {i}", score=0.5) for i in range(8)]

        mock_router = MagicMock()
        mock_decision = MagicMock()
        mock_router.route.return_value = mock_decision
        mock_router.execute_llm_call.return_value = {
            "content": '{"scores": [{"chunk_id": "c0", "score": 5}]}'
        }

        with patch("app.core.rag.llm_reranker.SmartRouter", return_value=mock_router):
            from app.core.rag.llm_reranker import LLMReranker
            reranker = LLMReranker()
            await reranker.rerank("test", chunks, "co_1")

        # 8 chunks / 5 per batch = 2 LLM calls
        assert mock_router.execute_llm_call.call_count == 2
