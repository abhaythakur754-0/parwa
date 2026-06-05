"""
Comprehensive unit and integration tests for the PARWA MCP FAQ Server.

Tests cover:
  - faq_search tool: backend POST /api/rag/search, FAQ-style response formatting
  - faq_get_categories tool: backend GET /api/kb/stats, category list extraction
  - faq_ingest tool: uploading Q&A pairs, backend POST /api/rag/documents
  - Error handling: backend unreachable, graceful error with success=False
  - Tenant isolation: tenant_id in all calls
  - Tool registration: 3 tools registered with correct schemas
  - _extract_qa_pair helper: Q:/A: format parsing, fallback logic
  - REST endpoints: FastAPI router endpoints

All tests mock external dependencies — no database, Redis, or network access.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_server.base_server import MCPRegistry
from mcp_server.knowledge.faq_server import FAQServer, _BackendClient
from mcp_server.models import ToolCategory, ToolInvokeResponse


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def faq_server():
    """Create a FAQServer instance with a mocked _BackendClient."""
    server = FAQServer()
    server._backend = MagicMock(spec=_BackendClient)
    server._backend.post = AsyncMock()
    server._backend.get = AsyncMock()
    return server


@pytest.fixture
def registry():
    """Create a fresh MCPRegistry for tool registration tests."""
    return MCPRegistry()


MOCK_FAQ_SEARCH_RESPONSE = {
    "status": "ok",
    "data": {
        "chunks": [
            {
                "chunk_id": "faq-chunk-1",
                "document_id": "faq-doc-1",
                "content": "Q: What is the refund policy?\nA: You can return items within 30 days of purchase for a full refund.",
                "score": 0.93,
                "metadata": {"source": "faq.md", "category": "billing"},
                "citation": None,
            },
            {
                "chunk_id": "faq-chunk-2",
                "document_id": "faq-doc-2",
                "content": "Shipping takes 3-5 business days for domestic orders.",
                "score": 0.78,
                "metadata": {"source": "faq.md", "category": "shipping"},
                "citation": None,
            },
        ],
        "total_found": 2,
        "retrieval_time_ms": 30.0,
    },
}

MOCK_KB_STATS_RESPONSE = {
    "status": "ok",
    "data": {
        "total_documents": 25,
        "total_chunks": 320,
        "completed": 23,
        "processing": 1,
        "failed": 1,
        "pending": 0,
    },
}

MOCK_KB_STATS_EMPTY_RESPONSE = {
    "status": "ok",
    "data": {
        "total_documents": 0,
        "total_chunks": 0,
        "completed": 0,
        "processing": 0,
        "failed": 0,
        "pending": 0,
    },
}

MOCK_ERROR_RESPONSE = {
    "status": "error",
    "data": {"message": "Connection refused"},
}

MOCK_INGEST_SUCCESS_RESPONSE = {
    "status": "ok",
    "data": {
        "message": "Document ingested successfully",
    },
}


# ═══════════════════════════════════════════════════════════════════
# 1. Tool Registration Tests
# ═══════════════════════════════════════════════════════════════════


class TestFAQToolRegistration:
    """Verify that all 3 FAQ tools are registered with correct schemas."""

    def test_three_tools_registered(self, faq_server, registry):
        faq_server.register_tools(registry)
        tools = registry.list_tools(server="faq_server")
        assert len(tools) == 3

    def test_faq_search_tool_registered(self, faq_server, registry):
        faq_server.register_tools(registry)
        tool = registry.get_tool("faq_search")
        assert tool is not None
        assert tool.name == "faq_search"
        assert tool.category == ToolCategory.KNOWLEDGE
        assert tool.server == "faq_server"
        assert "query" in tool.input_schema.get("required", [])
        assert "faq" in tool.tags

    def test_faq_get_categories_tool_registered(self, faq_server, registry):
        faq_server.register_tools(registry)
        tool = registry.get_tool("faq_get_categories")
        assert tool is not None
        assert tool.name == "faq_get_categories"
        # No required fields for this tool
        assert tool.input_schema.get("required", []) == []

    def test_faq_ingest_tool_registered(self, faq_server, registry):
        faq_server.register_tools(registry)
        tool = registry.get_tool("faq_ingest")
        assert tool is not None
        assert tool.name == "faq_ingest"
        required = tool.input_schema.get("required", [])
        assert "document_id" in required
        assert "faqs" in required

    def test_all_handlers_registered(self, faq_server, registry):
        faq_server.register_tools(registry)
        for name in ["faq_search", "faq_get_categories", "faq_ingest"]:
            handler = registry.get_handler(name)
            assert handler is not None
            assert callable(handler)

    def test_server_info(self, faq_server):
        info = faq_server.get_server_info()
        assert info.name == "faq_server"
        assert info.version == "2.0.0"
        assert info.category == ToolCategory.KNOWLEDGE


# ═══════════════════════════════════════════════════════════════════
# 2. faq_search Tool Tests
# ═══════════════════════════════════════════════════════════════════


class TestFAQSearchTool:
    """Test the faq_search tool handler."""

    @pytest.mark.asyncio
    async def test_faq_search_success(self, faq_server):
        faq_server._backend.post.return_value = MOCK_FAQ_SEARCH_RESPONSE

        result = await faq_server._invoke_faq_search(
            parameters={"query": "refund policy"},
        )

        assert result.success is True
        assert result.tool_name == "faq_search"
        assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_faq_search_formats_as_qa_pairs(self, faq_server):
        faq_server._backend.post.return_value = MOCK_FAQ_SEARCH_RESPONSE

        result = await faq_server._invoke_faq_search(
            parameters={"query": "refund policy"},
        )

        # First chunk has Q:/A: format — should be parsed
        first = result.data[0]
        assert "question" in first
        assert "answer" in first
        assert first["question"] == "What is the refund policy?"
        assert "30 days" in first["answer"]

    @pytest.mark.asyncio
    async def test_faq_search_non_qa_content_uses_query_as_question(self, faq_server):
        faq_server._backend.post.return_value = MOCK_FAQ_SEARCH_RESPONSE

        result = await faq_server._invoke_faq_search(
            parameters={"query": "How long does shipping take?"},
        )

        # Second chunk doesn't have Q:/A: format
        second = result.data[1]
        assert second["question"] == "How long does shipping take?"
        assert "3-5 business days" in second["answer"]

    @pytest.mark.asyncio
    async def test_faq_search_sends_correct_request_body(self, faq_server):
        faq_server._backend.post.return_value = MOCK_FAQ_SEARCH_RESPONSE

        await faq_server._invoke_faq_search(
            parameters={"query": "billing", "category": "billing", "limit": 3},
            context={"tenant_id": "tenant-xyz"},
        )

        call_args = faq_server._backend.post.call_args
        path = call_args[0][0]
        body = call_args[0][1]
        assert path == "/api/rag/search"
        assert body["query"] == "billing"
        assert body["top_k"] == 3
        assert body["filters"]["source_type"] == "faq"
        assert body["filters"]["category"] == "billing"

    @pytest.mark.asyncio
    async def test_faq_search_includes_source_type_filter(self, faq_server):
        faq_server._backend.post.return_value = MOCK_FAQ_SEARCH_RESPONSE

        await faq_server._invoke_faq_search(
            parameters={"query": "test"},
        )

        body = faq_server._backend.post.call_args[0][1]
        assert body["filters"]["source_type"] == "faq"

    @pytest.mark.asyncio
    async def test_faq_search_no_category_omits_filter(self, faq_server):
        faq_server._backend.post.return_value = MOCK_FAQ_SEARCH_RESPONSE

        await faq_server._invoke_faq_search(
            parameters={"query": "test"},
        )

        body = faq_server._backend.post.call_args[0][1]
        assert "category" not in body["filters"]

    @pytest.mark.asyncio
    async def test_faq_search_empty_query_rejected(self, faq_server):
        result = await faq_server._invoke_faq_search(
            parameters={"query": "   "},
        )

        assert result.success is False
        faq_server._backend.post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_faq_search_backend_error(self, faq_server):
        faq_server._backend.post.return_value = MOCK_ERROR_RESPONSE

        result = await faq_server._invoke_faq_search(
            parameters={"query": "test"},
        )

        assert result.success is False
        assert "unavailable" in result.error.lower() or "backend" in result.error.lower()

    @pytest.mark.asyncio
    async def test_faq_search_tenant_isolation(self, faq_server):
        faq_server._backend.post.return_value = MOCK_FAQ_SEARCH_RESPONSE

        result = await faq_server._invoke_faq_search(
            parameters={"query": "test"},
            context={"tenant_id": "tenant-abc"},
        )

        assert result.metadata["tenant_id"] == "tenant-abc"

    @pytest.mark.asyncio
    async def test_faq_search_metadata_fields(self, faq_server):
        faq_server._backend.post.return_value = MOCK_FAQ_SEARCH_RESPONSE

        result = await faq_server._invoke_faq_search(
            parameters={"query": "test", "category": "billing"},
        )

        assert result.metadata["source"] == "faq_knowledge_base"
        assert result.metadata["category_filter"] == "billing"
        assert "elapsed_ms" in result.metadata

    @pytest.mark.asyncio
    async def test_faq_search_confidence_rounded(self, faq_server):
        faq_server._backend.post.return_value = MOCK_FAQ_SEARCH_RESPONSE

        result = await faq_server._invoke_faq_search(
            parameters={"query": "test"},
        )

        for item in result.data:
            # Confidence should be rounded to 4 decimal places
            assert item["confidence"] == round(item["confidence"], 4)

    @pytest.mark.asyncio
    async def test_faq_search_default_limit(self, faq_server):
        faq_server._backend.post.return_value = MOCK_FAQ_SEARCH_RESPONSE

        await faq_server._invoke_faq_search(
            parameters={"query": "test"},
        )

        body = faq_server._backend.post.call_args[0][1]
        assert body["top_k"] == 5  # default limit


# ═══════════════════════════════════════════════════════════════════
# 3. faq_get_categories Tool Tests
# ═══════════════════════════════════════════════════════════════════


class TestFAQCategoriesTool:
    """Test the faq_get_categories tool handler."""

    @pytest.mark.asyncio
    async def test_categories_with_data(self, faq_server):
        faq_server._backend.get.return_value = MOCK_KB_STATS_RESPONSE

        result = await faq_server._invoke_faq_categories(
            context={"tenant_id": "tenant-abc"},
        )

        assert result.success is True
        assert result.tool_name == "faq_get_categories"
        assert isinstance(result.data, list)
        assert len(result.data) > 0
        # Should include standard categories
        assert "billing" in result.data
        assert "shipping" in result.data
        assert "general" in result.data

    @pytest.mark.asyncio
    async def test_categories_empty_kb(self, faq_server):
        faq_server._backend.get.return_value = MOCK_KB_STATS_EMPTY_RESPONSE

        result = await faq_server._invoke_faq_categories()

        assert result.success is True
        assert result.data == []

    @pytest.mark.asyncio
    async def test_categories_calls_kb_stats(self, faq_server):
        faq_server._backend.get.return_value = MOCK_KB_STATS_RESPONSE

        await faq_server._invoke_faq_categories()

        faq_server._backend.get.assert_awaited_once_with("/api/kb/stats")

    @pytest.mark.asyncio
    async def test_categories_backend_error(self, faq_server):
        faq_server._backend.get.return_value = MOCK_ERROR_RESPONSE

        result = await faq_server._invoke_faq_categories()

        assert result.success is False
        assert "unavailable" in result.error.lower() or "backend" in result.error.lower()

    @pytest.mark.asyncio
    async def test_categories_tenant_isolation(self, faq_server):
        faq_server._backend.get.return_value = MOCK_KB_STATS_RESPONSE

        result = await faq_server._invoke_faq_categories(
            context={"tenant_id": "tenant-999"},
        )

        assert result.metadata["tenant_id"] == "tenant-999"

    @pytest.mark.asyncio
    async def test_categories_metadata_includes_stats(self, faq_server):
        faq_server._backend.get.return_value = MOCK_KB_STATS_RESPONSE

        result = await faq_server._invoke_faq_categories()

        assert result.metadata["total_documents"] == 25
        assert result.metadata["total_chunks"] == 320
        assert result.metadata["count"] == len(result.data)


# ═══════════════════════════════════════════════════════════════════
# 4. faq_ingest Tool Tests
# ═══════════════════════════════════════════════════════════════════


class TestFAQIngestTool:
    """Test the faq_ingest tool handler."""

    @pytest.mark.asyncio
    async def test_ingest_success(self, faq_server):
        faq_server._backend.post.return_value = MOCK_INGEST_SUCCESS_RESPONSE

        result = await faq_server._invoke_faq_ingest(
            parameters={
                "document_id": "faq-doc-1",
                "faqs": [
                    {"question": "What is the refund policy?", "answer": "30 days", "category": "billing"},
                    {"question": "How to contact support?", "answer": "Email us", "category": "support"},
                ],
            },
        )

        assert result.success is True
        assert result.tool_name == "faq_ingest"
        assert result.data["document_id"] == "faq-doc-1"
        assert result.data["chunks_ingested"] == 2
        assert result.data["faq_count"] == 2

    @pytest.mark.asyncio
    async def test_ingest_sends_correct_request_body(self, faq_server):
        faq_server._backend.post.return_value = MOCK_INGEST_SUCCESS_RESPONSE

        await faq_server._invoke_faq_ingest(
            parameters={
                "document_id": "faq-doc-1",
                "faqs": [
                    {"question": "Q1?", "answer": "A1", "category": "billing"},
                ],
                "metadata": {"source": "upload"},
            },
            context={"tenant_id": "tenant-xyz"},
        )

        call_args = faq_server._backend.post.call_args
        path = call_args[0][0]
        body = call_args[0][1]

        assert path == "/api/rag/documents"
        assert body["document_id"] == "faq-doc-1"
        assert len(body["chunks"]) == 1
        # Each chunk should be in "Q: ...\nA: ..." format
        assert body["chunks"][0]["content"] == "Q: Q1?\nA: A1"
        assert body["chunks"][0]["metadata"]["source_type"] == "faq"
        assert body["chunks"][0]["metadata"]["category"] == "billing"

    @pytest.mark.asyncio
    async def test_ingest_no_document_id_rejected(self, faq_server):
        result = await faq_server._invoke_faq_ingest(
            parameters={
                "document_id": "",
                "faqs": [{"question": "Q?", "answer": "A"}],
            },
        )

        assert result.success is False
        assert "document_id" in result.error.lower()

    @pytest.mark.asyncio
    async def test_ingest_empty_faqs_rejected(self, faq_server):
        result = await faq_server._invoke_faq_ingest(
            parameters={"document_id": "doc-1", "faqs": []},
        )

        assert result.success is False
        assert "faqs" in result.error.lower() or "non-empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_ingest_none_faqs_rejected(self, faq_server):
        result = await faq_server._invoke_faq_ingest(
            parameters={"document_id": "doc-1"},  # faqs key omitted -> defaults to []
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_ingest_skips_invalid_qa_pairs(self, faq_server):
        """FAQ entries without question or answer should be skipped."""
        faq_server._backend.post.return_value = MOCK_INGEST_SUCCESS_RESPONSE

        result = await faq_server._invoke_faq_ingest(
            parameters={
                "document_id": "doc-1",
                "faqs": [
                    {"question": "Valid Q?", "answer": "Valid A"},
                    {"question": "", "answer": "No question"},
                    {"question": "No answer?", "answer": ""},
                    {"question": "Also valid", "answer": "Also valid answer"},
                ],
            },
        )

        assert result.success is True
        assert result.data["chunks_ingested"] == 2  # only the 2 valid ones

    @pytest.mark.asyncio
    async def test_ingest_all_invalid_returns_error(self, faq_server):
        """If all FAQ entries are invalid, return an error."""
        result = await faq_server._invoke_faq_ingest(
            parameters={
                "document_id": "doc-1",
                "faqs": [
                    {"question": "", "answer": "No question"},
                    {"question": "No answer?", "answer": ""},
                ],
            },
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_ingest_backend_error(self, faq_server):
        faq_server._backend.post.return_value = MOCK_ERROR_RESPONSE

        result = await faq_server._invoke_faq_ingest(
            parameters={
                "document_id": "doc-1",
                "faqs": [{"question": "Q?", "answer": "A"}],
            },
        )

        assert result.success is False
        assert "unavailable" in result.error.lower() or "backend" in result.error.lower()

    @pytest.mark.asyncio
    async def test_ingest_tenant_isolation(self, faq_server):
        faq_server._backend.post.return_value = MOCK_INGEST_SUCCESS_RESPONSE

        result = await faq_server._invoke_faq_ingest(
            parameters={
                "document_id": "doc-1",
                "faqs": [{"question": "Q?", "answer": "A"}],
            },
            context={"tenant_id": "tenant-ingest"},
        )

        assert result.metadata["tenant_id"] == "tenant-ingest"

    @pytest.mark.asyncio
    async def test_ingest_default_category(self, faq_server):
        """FAQs without a category should default to 'general'."""
        faq_server._backend.post.return_value = MOCK_INGEST_SUCCESS_RESPONSE

        await faq_server._invoke_faq_ingest(
            parameters={
                "document_id": "doc-1",
                "faqs": [{"question": "Q?", "answer": "A"}],  # no category
            },
        )

        body = faq_server._backend.post.call_args[0][1]
        assert body["chunks"][0]["metadata"]["category"] == "general"


# ═══════════════════════════════════════════════════════════════════
# 5. _extract_qa_pair Helper Tests
# ═══════════════════════════════════════════════════════════════════


class TestExtractQAPair:
    """Test the static _extract_qa_pair helper method."""

    def test_extract_qa_with_prefix(self):
        content = "Q: What is the refund policy?\nA: You can return items within 30 days."
        question, answer = FAQServer._extract_qa_pair(content, "refund?")
        assert question == "What is the refund policy?"
        assert "30 days" in answer

    def test_extract_qa_lowercase_prefix(self):
        content = "q: How to reset password?\na: Click the reset link."
        question, answer = FAQServer._extract_qa_pair(content, "reset?")
        assert question == "How to reset password?"
        assert "reset link" in answer

    def test_extract_qa_multiline_answer(self):
        content = "Q: How to return?\nA: Step 1: Package the item\nStep 2: Ship it back\nStep 3: Get refund"
        question, answer = FAQServer._extract_qa_pair(content, "return?")
        assert "Step 1" in answer
        assert "Step 3" in answer

    def test_extract_qa_no_format_uses_query(self):
        content = "Our refund policy allows returns within 30 days."
        question, answer = FAQServer._extract_qa_pair(content, "What is the refund policy?")
        assert question == "What is the refund policy?"
        assert answer == content

    def test_extract_qa_empty_content(self):
        question, answer = FAQServer._extract_qa_pair("", "my query")
        assert question == "my query"
        assert answer == ""

    def test_extract_qa_single_line_no_q_prefix(self):
        content = "Just some plain text without Q or A markers"
        question, answer = FAQServer._extract_qa_pair(content, "my query")
        assert question == "my query"
        assert answer == content


# ═══════════════════════════════════════════════════════════════════
# 6. REST Router Tests
# ═══════════════════════════════════════════════════════════════════


class TestFAQRouter:
    """Test the FastAPI router endpoints."""

    def test_router_has_correct_prefix(self, faq_server):
        router = faq_server.get_router()
        assert router.prefix == "/knowledge/faq"

    def test_router_has_search_route(self, faq_server):
        router = faq_server.get_router()
        route_paths = [r.path for r in router.routes]
        assert "/knowledge/faq/search" in route_paths

    def test_router_has_categories_route(self, faq_server):
        router = faq_server.get_router()
        route_paths = [r.path for r in router.routes]
        assert "/knowledge/faq/categories" in route_paths

    def test_router_has_ingest_route(self, faq_server):
        router = faq_server.get_router()
        route_paths = [r.path for r in router.routes]
        assert "/knowledge/faq/ingest" in route_paths

    def test_router_search_is_post(self, faq_server):
        router = faq_server.get_router()
        for route in router.routes:
            if route.path == "/knowledge/faq/search":
                assert "POST" in route.methods

    def test_router_categories_is_get(self, faq_server):
        router = faq_server.get_router()
        for route in router.routes:
            if route.path == "/knowledge/faq/categories":
                assert "GET" in route.methods

    def test_router_ingest_is_post(self, faq_server):
        router = faq_server.get_router()
        for route in router.routes:
            if route.path == "/knowledge/faq/ingest":
                assert "POST" in route.methods


# ═══════════════════════════════════════════════════════════════════
# 7. Edge Cases and Additional Tests
# ═══════════════════════════════════════════════════════════════════


class TestFAQEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_faq_search_none_parameters(self, faq_server):
        result = await faq_server._invoke_faq_search(parameters=None)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_faq_search_none_context(self, faq_server):
        faq_server._backend.post.return_value = MOCK_FAQ_SEARCH_RESPONSE

        result = await faq_server._invoke_faq_search(
            parameters={"query": "test"},
            context=None,
        )
        assert result.success is True
        assert result.metadata["tenant_id"] == ""

    @pytest.mark.asyncio
    async def test_faq_categories_none_context(self, faq_server):
        faq_server._backend.get.return_value = MOCK_KB_STATS_RESPONSE

        result = await faq_server._invoke_faq_categories(context=None)
        assert result.success is True
        assert result.metadata["tenant_id"] == ""

    @pytest.mark.asyncio
    async def test_faq_ingest_none_parameters(self, faq_server):
        result = await faq_server._invoke_faq_ingest(parameters=None)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_faq_search_result_has_all_fields(self, faq_server):
        faq_server._backend.post.return_value = MOCK_FAQ_SEARCH_RESPONSE

        result = await faq_server._invoke_faq_search(
            parameters={"query": "test"},
        )

        for item in result.data:
            assert "id" in item
            assert "question" in item
            assert "answer" in item
            assert "category" in item
            assert "confidence" in item
            assert "source" in item

    @pytest.mark.asyncio
    async def test_faq_ingest_with_metadata(self, faq_server):
        faq_server._backend.post.return_value = MOCK_INGEST_SUCCESS_RESPONSE

        await faq_server._invoke_faq_ingest(
            parameters={
                "document_id": "doc-1",
                "faqs": [{"question": "Q?", "answer": "A"}],
                "metadata": {"uploaded_by": "admin", "version": "2"},
            },
        )

        body = faq_server._backend.post.call_args[0][1]
        # Document-level metadata should include source_type
        assert body["metadata"]["source_type"] == "faq"
        assert body["metadata"]["uploaded_by"] == "admin"

    @pytest.mark.asyncio
    async def test_faq_search_query_stripped(self, faq_server):
        faq_server._backend.post.return_value = MOCK_FAQ_SEARCH_RESPONSE

        await faq_server._invoke_faq_search(
            parameters={"query": "  padded query  "},
        )

        body = faq_server._backend.post.call_args[0][1]
        assert body["query"] == "padded query"
