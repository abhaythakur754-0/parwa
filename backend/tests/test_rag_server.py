"""
Comprehensive unit and integration tests for the PARWA MCP RAG Server.

Tests cover:
  - rag_query tool: backend POST /api/rag/search, request body, response parsing
  - rag_rerank tool: BM25 reranking logic with sample chunks
  - semantic_search tool: parwa_high variant, response format
  - Error handling: backend unreachable, graceful error with success=False
  - Tenant isolation: tenant_id passed to backend and in metadata
  - Tool registration: all 3 tools registered with correct schemas
  - REST endpoints: FastAPI router endpoints
  - _bm25_rerank pure function: scoring, ordering, edge cases
  - _BackendClient: post/get error handling

All tests mock external dependencies — no database, Redis, or network access.
"""

from __future__ import annotations

import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server.base_server import MCPRegistry
from mcp_server.knowledge.rag_server import RAGServer, _BackendClient, _bm25_rerank, _STOP_WORDS
from mcp_server.models import ToolCategory, ToolInvokeResponse


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def rag_server():
    """Create a RAGServer instance with a mocked _BackendClient."""
    server = RAGServer()
    server._backend = MagicMock(spec=_BackendClient)
    server._backend.post = AsyncMock()
    server._backend.get = AsyncMock()
    return server


@pytest.fixture
def registry():
    """Create a fresh MCPRegistry for tool registration tests."""
    return MCPRegistry()


MOCK_RAG_SEARCH_RESPONSE = {
    "status": "ok",
    "data": {
        "chunks": [
            {
                "chunk_id": "chunk-1",
                "document_id": "doc-1",
                "content": "Our refund policy allows returns within 30 days of purchase.",
                "score": 0.95,
                "metadata": {"source": "faq.md"},
                "citation": None,
            },
            {
                "chunk_id": "chunk-2",
                "document_id": "doc-2",
                "content": "Shipping typically takes 3-5 business days.",
                "score": 0.82,
                "metadata": {"source": "shipping.md"},
                "citation": None,
            },
        ],
        "total_found": 2,
        "retrieval_time_ms": 45.2,
        "variant_tier_used": "parwa",
        "cached": False,
        "degradation_used": False,
    },
}

MOCK_ERROR_RESPONSE = {
    "status": "error",
    "data": {"message": "Connection refused"},
}


# ═══════════════════════════════════════════════════════════════════
# 1. Tool Registration Tests
# ═══════════════════════════════════════════════════════════════════


class TestRAGToolRegistration:
    """Verify that all 3 RAG tools are registered with correct schemas."""

    def test_three_tools_registered(self, rag_server, registry):
        rag_server.register_tools(registry)
        tools = registry.list_tools(server="rag_server")
        assert len(tools) == 3

    def test_rag_query_tool_registered(self, rag_server, registry):
        rag_server.register_tools(registry)
        tool = registry.get_tool("rag_query")
        assert tool is not None
        assert tool.name == "rag_query"
        assert tool.category == ToolCategory.KNOWLEDGE
        assert tool.server == "rag_server"
        assert "query" in tool.input_schema.get("required", [])

    def test_rag_rerank_tool_registered(self, rag_server, registry):
        rag_server.register_tools(registry)
        tool = registry.get_tool("rag_rerank")
        assert tool is not None
        assert tool.name == "rag_rerank"
        required = tool.input_schema.get("required", [])
        assert "query" in required
        assert "chunks" in required

    def test_semantic_search_tool_registered(self, rag_server, registry):
        rag_server.register_tools(registry)
        tool = registry.get_tool("semantic_search")
        assert tool is not None
        assert tool.name == "semantic_search"
        assert tool.tags == ["rag", "semantic", "search", "knowledge"]

    def test_rag_query_schema_has_variant_type_enum(self, rag_server, registry):
        rag_server.register_tools(registry)
        tool = registry.get_tool("rag_query")
        variant_prop = tool.input_schema["properties"]["variant_type"]
        assert "enum" in variant_prop
        assert set(variant_prop["enum"]) == {"mini_parwa", "parwa", "parwa_high"}

    def test_handlers_registered(self, rag_server, registry):
        rag_server.register_tools(registry)
        for name in ["rag_query", "rag_rerank", "semantic_search"]:
            handler = registry.get_handler(name)
            assert handler is not None
            assert callable(handler)

    def test_server_info(self, rag_server):
        info = rag_server.get_server_info()
        assert info.name == "rag_server"
        assert info.version == "2.0.0"
        assert info.category == ToolCategory.KNOWLEDGE


# ═══════════════════════════════════════════════════════════════════
# 2. rag_query Tool Tests
# ═══════════════════════════════════════════════════════════════════


class TestRAGQueryTool:
    """Test the rag_query tool handler."""

    @pytest.mark.asyncio
    async def test_rag_query_success(self, rag_server):
        rag_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        result = await rag_server._invoke_rag_query(
            parameters={"query": "What is the refund policy?", "top_k": 5},
            context={"tenant_id": "tenant-abc"},
        )

        assert result.success is True
        assert result.tool_name == "rag_query"
        assert len(result.data) == 2
        assert result.data[0]["content"] == "Our refund policy allows returns within 30 days of purchase."
        assert result.data[0]["source"] == "doc-1"
        assert result.data[0]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_rag_query_sends_correct_request_body(self, rag_server):
        rag_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        await rag_server._invoke_rag_query(
            parameters={
                "query": "refund policy",
                "variant_type": "parwa_high",
                "top_k": 10,
                "filters": {"source": "faq"},
            },
            context={"tenant_id": "tenant-xyz"},
        )

        rag_server._backend.post.assert_awaited_once()
        call_args = rag_server._backend.post.call_args
        path = call_args[0][0]
        body = call_args[0][1]
        assert path == "/api/rag/search"
        assert body["query"] == "refund policy"
        assert body["variant_type"] == "parwa_high"
        assert body["top_k"] == 10
        assert body["filters"] == {"source": "faq"}

    @pytest.mark.asyncio
    async def test_rag_query_default_variant_type(self, rag_server):
        rag_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        await rag_server._invoke_rag_query(
            parameters={"query": "test"},
        )

        body = rag_server._backend.post.call_args[0][1]
        assert body["variant_type"] == "parwa"

    @pytest.mark.asyncio
    async def test_rag_query_empty_query_rejected(self, rag_server):
        result = await rag_server._invoke_rag_query(
            parameters={"query": "   "},
        )

        assert result.success is False
        assert "required" in result.error.lower() or "empty" in result.error.lower()
        rag_server._backend.post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rag_query_backend_error(self, rag_server):
        rag_server._backend.post.return_value = MOCK_ERROR_RESPONSE

        result = await rag_server._invoke_rag_query(
            parameters={"query": "test"},
            context={"tenant_id": "tenant-abc"},
        )

        assert result.success is False
        assert "unavailable" in result.error.lower() or "backend" in result.error.lower()
        assert result.metadata["backend_status"] == "error"

    @pytest.mark.asyncio
    async def test_rag_query_tenant_isolation(self, rag_server):
        rag_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        result = await rag_server._invoke_rag_query(
            parameters={"query": "test"},
            context={"tenant_id": "tenant-isolated"},
        )

        # Verify tenant_id appears in response metadata
        assert result.metadata["tenant_id"] == "tenant-isolated"
        # Verify tenant_id is set in each chunk's metadata
        for chunk in result.data:
            assert chunk["metadata"]["tenant_id"] == "tenant-isolated"

    @pytest.mark.asyncio
    async def test_rag_query_no_filters_omits_key(self, rag_server):
        rag_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        await rag_server._invoke_rag_query(
            parameters={"query": "test", "top_k": 3},
        )

        body = rag_server._backend.post.call_args[0][1]
        assert "filters" not in body

    @pytest.mark.asyncio
    async def test_rag_query_metadata_fields(self, rag_server):
        rag_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        result = await rag_server._invoke_rag_query(
            parameters={"query": "test", "variant_type": "parwa", "top_k": 5},
        )

        assert result.metadata["query"] == "test"
        assert result.metadata["variant_type"] == "parwa"
        assert result.metadata["top_k"] == 5
        assert result.metadata["retrieved_count"] == 2
        assert result.metadata["total_found"] == 2
        assert "elapsed_ms" in result.metadata

    @pytest.mark.asyncio
    async def test_rag_query_query_stripped(self, rag_server):
        rag_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        await rag_server._invoke_rag_query(
            parameters={"query": "  padded query  "},
        )

        body = rag_server._backend.post.call_args[0][1]
        assert body["query"] == "padded query"


# ═══════════════════════════════════════════════════════════════════
# 3. rag_rerank Tool Tests
# ═══════════════════════════════════════════════════════════════════


class TestRAGRerankTool:
    """Test the rag_rerank tool handler."""

    @pytest.mark.asyncio
    async def test_rerank_basic(self, rag_server):
        chunks = [
            {"content": "Refund policy for electronics", "score": 0.7},
            {"content": "Shipping details and delivery times", "score": 0.8},
            {"content": "Full refund process explained step by step", "score": 0.6},
        ]

        result = await rag_server._invoke_rag_rerank(
            parameters={"query": "refund process", "chunks": chunks, "top_k": 2},
        )

        assert result.success is True
        assert len(result.data) == 2
        # Each reranked chunk should have a rerank_score
        for chunk in result.data:
            assert "rerank_score" in chunk

    @pytest.mark.asyncio
    async def test_rerank_empty_chunks(self, rag_server):
        result = await rag_server._invoke_rag_rerank(
            parameters={"query": "test", "chunks": []},
        )

        assert result.success is True
        assert result.data == []
        assert result.metadata["original_count"] == 0

    @pytest.mark.asyncio
    async def test_rerank_empty_query_rejected(self, rag_server):
        result = await rag_server._invoke_rag_rerank(
            parameters={"query": "  ", "chunks": [{"content": "test", "score": 0.5}]},
        )

        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_rerank_respects_top_k(self, rag_server):
        chunks = [
            {"content": f"chunk {i}", "score": 0.5} for i in range(10)
        ]

        result = await rag_server._invoke_rag_rerank(
            parameters={"query": "chunk", "chunks": chunks, "top_k": 3},
        )

        assert len(result.data) == 3

    @pytest.mark.asyncio
    async def test_rerank_tenant_isolation(self, rag_server):
        result = await rag_server._invoke_rag_rerank(
            parameters={"query": "test", "chunks": [{"content": "hello world", "score": 0.5}]},
            context={"tenant_id": "tenant-999"},
        )

        assert result.metadata["tenant_id"] == "tenant-999"

    @pytest.mark.asyncio
    async def test_rerank_metadata_fields(self, rag_server):
        chunks = [{"content": "test content", "score": 0.5}]

        result = await rag_server._invoke_rag_rerank(
            parameters={"query": "test", "chunks": chunks, "top_k": 5},
        )

        assert result.metadata["original_count"] == 1
        assert result.metadata["method"] == "bm25_cross_encoder"
        assert "elapsed_ms" in result.metadata

    @pytest.mark.asyncio
    async def test_rerank_no_backend_call(self, rag_server):
        """Rerank is a local operation — no backend API call should be made."""
        chunks = [{"content": "test", "score": 0.5}]
        await rag_server._invoke_rag_rerank(
            parameters={"query": "test", "chunks": chunks},
        )
        rag_server._backend.post.assert_not_awaited()


# ═══════════════════════════════════════════════════════════════════
# 4. semantic_search Tool Tests
# ═══════════════════════════════════════════════════════════════════


class TestSemanticSearchTool:
    """Test the semantic_search tool handler."""

    @pytest.mark.asyncio
    async def test_semantic_search_uses_parwa_high(self, rag_server):
        rag_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        await rag_server._invoke_semantic_search(
            parameters={"query": "detailed explanation of refunds"},
        )

        body = rag_server._backend.post.call_args[0][1]
        assert body["variant_type"] == "parwa_high"

    @pytest.mark.asyncio
    async def test_semantic_search_response_format(self, rag_server):
        rag_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        result = await rag_server._invoke_semantic_search(
            parameters={"query": "test query", "top_k": 10},
        )

        assert result.success is True
        assert result.tool_name == "semantic_search"
        # Check confidence fields exist
        for item in result.data:
            assert "confidence_score" in item
            assert "confidence_level" in item
            assert item["confidence_level"] in ("high", "medium", "low")

    @pytest.mark.asyncio
    async def test_semantic_search_confidence_levels(self, rag_server):
        """Verify confidence level mapping: high >= 0.85, medium >= 0.60, low < 0.60."""
        response = {
            "status": "ok",
            "data": {
                "chunks": [
                    {"chunk_id": "c1", "document_id": "d1", "content": "high", "score": 0.92, "metadata": {}, "citation": None},
                    {"chunk_id": "c2", "document_id": "d2", "content": "medium", "score": 0.70, "metadata": {}, "citation": None},
                    {"chunk_id": "c3", "document_id": "d3", "content": "low", "score": 0.40, "metadata": {}, "citation": None},
                ],
                "total_found": 3,
                "variant_tier_used": "parwa_high",
            },
        }
        rag_server._backend.post.return_value = response

        result = await rag_server._invoke_semantic_search(
            parameters={"query": "test"},
        )

        levels = [item["confidence_level"] for item in result.data]
        assert levels == ["high", "medium", "low"]

    @pytest.mark.asyncio
    async def test_semantic_search_empty_query(self, rag_server):
        result = await rag_server._invoke_semantic_search(
            parameters={"query": ""},
        )

        assert result.success is False
        rag_server._backend.post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_semantic_search_backend_error(self, rag_server):
        rag_server._backend.post.return_value = MOCK_ERROR_RESPONSE

        result = await rag_server._invoke_semantic_search(
            parameters={"query": "test"},
        )

        assert result.success is False
        assert "unavailable" in result.error.lower() or "backend" in result.error.lower()

    @pytest.mark.asyncio
    async def test_semantic_search_tenant_isolation(self, rag_server):
        rag_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        result = await rag_server._invoke_semantic_search(
            parameters={"query": "test"},
            context={"tenant_id": "tenant-sem"},
        )

        assert result.metadata["tenant_id"] == "tenant-sem"
        assert result.metadata["variant_type"] == "parwa_high"

    @pytest.mark.asyncio
    async def test_semantic_search_default_top_k(self, rag_server):
        rag_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        await rag_server._invoke_semantic_search(
            parameters={"query": "test"},
        )

        body = rag_server._backend.post.call_args[0][1]
        assert body["top_k"] == 10  # default for semantic_search

    @pytest.mark.asyncio
    async def test_semantic_search_with_filters(self, rag_server):
        rag_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        await rag_server._invoke_semantic_search(
            parameters={"query": "test", "filters": {"source": "kb"}},
        )

        body = rag_server._backend.post.call_args[0][1]
        assert body["filters"] == {"source": "kb"}


# ═══════════════════════════════════════════════════════════════════
# 5. _bm25_rerank Pure Function Tests
# ═══════════════════════════════════════════════════════════════════


class TestBM25RerankFunction:
    """Test the BM25-inspired reranker as a pure function."""

    def test_empty_chunks_returns_empty(self):
        result = _bm25_rerank("test query", [], top_k=5)
        assert result == []

    def test_empty_query_returns_first_k(self):
        chunks = [{"content": "hello", "score": 0.9}]
        result = _bm25_rerank("", chunks, top_k=5)
        assert result == chunks[:5]

    def test_rerank_adds_rerank_score(self):
        chunks = [{"content": "refund policy details", "score": 0.5}]
        result = _bm25_rerank("refund policy", chunks, top_k=5)
        assert "rerank_score" in result[0]
        assert isinstance(result[0]["rerank_score"], float)

    def test_rerank_score_capped_at_one(self):
        chunks = [{"content": "exact match exact match", "score": 1.0}]
        result = _bm25_rerank("exact match", chunks, top_k=5)
        assert result[0]["rerank_score"] <= 1.0

    def test_rerank_preserves_original_fields(self):
        chunks = [{"content": "hello world", "score": 0.5, "document_id": "doc-1"}]
        result = _bm25_rerank("hello", chunks, top_k=5)
        assert result[0]["document_id"] == "doc-1"
        assert result[0]["content"] == "hello world"

    def test_rerank_exact_phrase_match_gets_bonus(self):
        chunks = [
            {"content": "word1 unrelated stuff", "score": 0.5},
            {"content": "this has the exact phrase match here", "score": 0.5},
        ]
        result = _bm25_rerank("exact phrase match", chunks, top_k=2)
        # The chunk with the exact phrase should rank higher
        assert result[0]["content"] == "this has the exact phrase match here"

    def test_rerank_top_k_limits_output(self):
        chunks = [{"content": f"chunk {i}", "score": 0.5} for i in range(20)]
        result = _bm25_rerank("chunk", chunks, top_k=3)
        assert len(result) == 3

    def test_rerank_stop_words_ignored(self):
        """Stop words should not contribute to scoring."""
        # "the is at" are all stop words — should return original order
        chunks = [{"content": "hello world", "score": 0.5}]
        result = _bm25_rerank("the is at", chunks, top_k=5)
        # With only stop words, query_terms is empty -> returns original
        assert len(result) == 1

    def test_rerank_keyword_overlap_improves_ranking(self):
        chunks = [
            {"content": "completely unrelated content here", "score": 0.5},
            {"content": "refund policy for customers refund process", "score": 0.5},
        ]
        result = _bm25_rerank("refund policy", chunks, top_k=2)
        # Chunk with keyword overlap should rank higher
        assert result[0]["content"] == "refund policy for customers refund process"


# ═══════════════════════════════════════════════════════════════════
# 6. _BackendClient Tests
# ═══════════════════════════════════════════════════════════════════


class TestBackendClient:
    """Test the _BackendClient helper."""

    @pytest.mark.asyncio
    async def test_post_returns_error_on_exception(self):
        client = _BackendClient()
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=Exception("Connection refused"))
        mock_http_client.is_closed = False
        client._get_client = AsyncMock(return_value=mock_http_client)

        result = await client.post("/api/rag/search", {"query": "test"})
        assert result["status"] == "error"
        assert "Connection refused" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_get_returns_error_on_exception(self):
        client = _BackendClient()
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(side_effect=Exception("Timeout"))
        mock_http_client.is_closed = False
        client._get_client = AsyncMock(return_value=mock_http_client)

        result = await client.get("/api/kb/stats")
        assert result["status"] == "error"
        assert "Timeout" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_post_returns_json_on_success(self):
        client = _BackendClient()
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "data": {"key": "value"}}
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        client._get_client = AsyncMock(return_value=mock_http_client)

        result = await client.post("/api/test", {"q": "test"})
        assert result["status"] == "ok"
        assert result["data"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_get_returns_json_on_success(self):
        client = _BackendClient()
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "data": {"total": 5}}
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        client._get_client = AsyncMock(return_value=mock_http_client)

        result = await client.get("/api/test")
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_close_closes_client(self):
        client = _BackendClient()
        mock_http_client = MagicMock()
        mock_http_client.is_closed = False
        mock_http_client.aclose = AsyncMock()
        client._client = mock_http_client

        await client.close()
        mock_http_client.aclose.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════
# 7. REST Router Tests
# ═══════════════════════════════════════════════════════════════════


class TestRAGRouter:
    """Test the FastAPI router endpoints."""

    def test_router_has_correct_prefix(self, rag_server):
        router = rag_server.get_router()
        assert router.prefix == "/knowledge/rag"

    def test_router_has_routes(self, rag_server):
        router = rag_server.get_router()
        route_paths = [r.path for r in router.routes]
        assert "/knowledge/rag/query" in route_paths
        assert "/knowledge/rag/rerank" in route_paths
        assert "/knowledge/rag/semantic-search" in route_paths

    def test_router_route_methods(self, rag_server):
        router = rag_server.get_router()
        route_methods = {}
        for r in router.routes:
            route_methods[r.path] = r.methods
        assert "POST" in route_methods.get("/knowledge/rag/query", set())
        assert "POST" in route_methods.get("/knowledge/rag/rerank", set())
        assert "POST" in route_methods.get("/knowledge/rag/semantic-search", set())


# ═══════════════════════════════════════════════════════════════════
# 8. Edge Cases and Additional Tests
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_rag_query_none_parameters(self, rag_server):
        """Test with parameters=None (should default to empty dict)."""
        rag_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        result = await rag_server._invoke_rag_query(parameters=None)
        # Empty query should be rejected
        assert result.success is False

    @pytest.mark.asyncio
    async def test_rag_query_none_context(self, rag_server):
        """Test with context=None (should default to empty dict)."""
        rag_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        result = await rag_server._invoke_rag_query(
            parameters={"query": "test"},
            context=None,
        )
        assert result.success is True
        assert result.metadata["tenant_id"] == ""

    @pytest.mark.asyncio
    async def test_rag_query_empty_chunks_in_response(self, rag_server):
        response = {"status": "ok", "data": {"chunks": [], "total_found": 0}}
        rag_server._backend.post.return_value = response

        result = await rag_server._invoke_rag_query(
            parameters={"query": "test"},
        )
        assert result.success is True
        assert result.data == []
        assert result.metadata["retrieved_count"] == 0

    @pytest.mark.asyncio
    async def test_rerank_with_none_parameters(self, rag_server):
        result = await rag_server._invoke_rag_rerank(parameters=None)
        assert result.success is False

    def test_stop_words_set_not_empty(self):
        """Verify the stop words list is populated."""
        assert len(_STOP_WORDS) > 50
        assert "the" in _STOP_WORDS
        assert "is" in _STOP_WORDS
        assert "refurbished" not in _STOP_WORDS  # not a stop word

    def test_bm25_rerank_single_chunk(self):
        chunks = [{"content": "refund policy", "score": 0.5}]
        result = _bm25_rerank("refund", chunks, top_k=5)
        assert len(result) == 1
        assert result[0]["rerank_score"] > 0

    def test_bm25_rerank_chunk_missing_content_key(self):
        """Chunks without 'content' should not crash."""
        chunks = [{"score": 0.5}]  # missing 'content'
        result = _bm25_rerank("test", chunks, top_k=5)
        assert len(result) == 1

    def test_bm25_rerank_chunk_missing_score_key(self):
        """Chunks without 'score' should default to 0.0."""
        chunks = [{"content": "some text"}]  # missing 'score'
        result = _bm25_rerank("some", chunks, top_k=5)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_rag_query_backend_httpx_error(self, rag_server):
        """Simulate httpx.ConnectError by having backend.post return an error dict."""
        error_resp = {
            "status": "error",
            "data": {"message": "ConnectError: [Errno 111] Connection refused"},
        }
        rag_server._backend.post.return_value = error_resp

        result = await rag_server._invoke_rag_query(
            parameters={"query": "test"},
        )
        assert result.success is False
        assert "Connection refused" in result.error
