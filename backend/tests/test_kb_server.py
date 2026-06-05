"""
Comprehensive unit and integration tests for the PARWA MCP Knowledge Base Server.

Tests cover:
  - kb_search tool: backend POST /api/rag/search, response format with grouped sections
  - kb_get_document tool: backend GET /api/rag/documents/{company_id}/{document_id}
  - kb_list_bases tool: backend GET /api/kb/stats
  - kb_upload_url tool: URL fetch → chunk → backend POST
  - Error handling: backend unreachable, graceful error with success=False
  - Tenant isolation: tenant_id in all calls
  - Tool registration: 4 tools registered with correct schemas
  - Helper functions: _looks_like_html, _strip_html, _chunk_text, _fetch_url_content

All tests mock external dependencies — no database, Redis, or network access.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server.base_server import MCPRegistry
from mcp_server.knowledge.kb_server import (
    KBServer,
    _BackendClient,
    _chunk_text,
    _looks_like_html,
    _strip_html,
    _fetch_url_content,
)
from mcp_server.models import ToolCategory, ToolInvokeResponse


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def kb_server():
    """Create a KBServer instance with a mocked _BackendClient."""
    server = KBServer()
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
                "content": "Knowledge base article about refunds. Returns within 30 days.",
                "score": 0.91,
                "metadata": {"title": "Refund Policy", "knowledge_base_id": "kb-main"},
                "citation": None,
            },
            {
                "chunk_id": "chunk-2",
                "document_id": "doc-1",
                "content": "To process a refund, contact support.",
                "score": 0.85,
                "metadata": {"title": "Refund Policy", "knowledge_base_id": "kb-main"},
                "citation": None,
            },
            {
                "chunk_id": "chunk-3",
                "document_id": "doc-2",
                "content": "Shipping policy: 3-5 days domestic.",
                "score": 0.78,
                "metadata": {"title": "Shipping Info", "knowledge_base_id": "kb-main"},
                "citation": None,
            },
        ],
        "total_found": 3,
        "retrieval_time_ms": 55.0,
        "variant_tier_used": "parwa",
    },
}

MOCK_KB_STATS_RESPONSE = {
    "status": "ok",
    "data": {
        "total_documents": 50,
        "total_chunks": 800,
        "completed": 48,
        "processing": 1,
        "failed": 1,
        "pending": 0,
    },
}

MOCK_KB_STATS_NO_FAILURES = {
    "status": "ok",
    "data": {
        "total_documents": 30,
        "total_chunks": 400,
        "completed": 30,
        "processing": 0,
        "failed": 0,
        "pending": 0,
    },
}

MOCK_GET_DOCUMENT_RESPONSE = {
    "status": "ok",
    "data": {
        "document_id": "doc-1",
        "content": "Full document content here.",
        "knowledge_base_id": "kb-main",
        "chunk_count": 5,
        "metadata": {"title": "Refund Policy", "author": "admin"},
    },
}

MOCK_ERROR_RESPONSE = {
    "status": "error",
    "data": {"message": "Connection refused"},
}

MOCK_INGEST_SUCCESS_RESPONSE = {
    "status": "ok",
    "data": {
        "message": "URL content imported successfully",
    },
}


# ═══════════════════════════════════════════════════════════════════
# 1. Tool Registration Tests
# ═══════════════════════════════════════════════════════════════════


class TestKBToolRegistration:
    """Verify that all 4 KB tools are registered with correct schemas."""

    def test_four_tools_registered(self, kb_server, registry):
        kb_server.register_tools(registry)
        tools = registry.list_tools(server="kb_server")
        assert len(tools) == 4

    def test_kb_search_tool_registered(self, kb_server, registry):
        kb_server.register_tools(registry)
        tool = registry.get_tool("kb_search")
        assert tool is not None
        assert tool.name == "kb_search"
        assert tool.category == ToolCategory.KNOWLEDGE
        assert tool.server == "kb_server"
        assert "query" in tool.input_schema.get("required", [])

    def test_kb_get_document_tool_registered(self, kb_server, registry):
        kb_server.register_tools(registry)
        tool = registry.get_tool("kb_get_document")
        assert tool is not None
        assert tool.name == "kb_get_document"
        required = tool.input_schema.get("required", [])
        assert "document_id" in required

    def test_kb_list_bases_tool_registered(self, kb_server, registry):
        kb_server.register_tools(registry)
        tool = registry.get_tool("kb_list_bases")
        assert tool is not None
        assert tool.name == "kb_list_bases"
        assert tool.input_schema.get("required", []) == []

    def test_kb_upload_url_tool_registered(self, kb_server, registry):
        kb_server.register_tools(registry)
        tool = registry.get_tool("kb_upload_url")
        assert tool is not None
        assert tool.name == "kb_upload_url"
        required = tool.input_schema.get("required", [])
        assert "url" in required

    def test_all_handlers_registered(self, kb_server, registry):
        kb_server.register_tools(registry)
        for name in ["kb_search", "kb_get_document", "kb_list_bases", "kb_upload_url"]:
            handler = registry.get_handler(name)
            assert handler is not None
            assert callable(handler)

    def test_server_info(self, kb_server):
        info = kb_server.get_server_info()
        assert info.name == "kb_server"
        assert info.version == "2.0.0"
        assert info.category == ToolCategory.KNOWLEDGE


# ═══════════════════════════════════════════════════════════════════
# 2. kb_search Tool Tests
# ═══════════════════════════════════════════════════════════════════


class TestKBSearchTool:
    """Test the kb_search tool handler."""

    @pytest.mark.asyncio
    async def test_kb_search_success(self, kb_server):
        kb_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        result = await kb_server._invoke_kb_search(
            parameters={"query": "refund policy"},
        )

        assert result.success is True
        assert result.tool_name == "kb_search"
        assert len(result.data) == 2  # 2 unique document_ids

    @pytest.mark.asyncio
    async def test_kb_search_groups_by_document(self, kb_server):
        """Chunks from the same document should be grouped into one result."""
        kb_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        result = await kb_server._invoke_kb_search(
            parameters={"query": "refund"},
        )

        # doc-1 should have 2 sections, doc-2 should have 1 section
        doc_ids = {d["id"] for d in result.data}
        assert "doc-1" in doc_ids
        assert "doc-2" in doc_ids

        doc_1 = next(d for d in result.data if d["id"] == "doc-1")
        assert doc_1["metadata"]["section_count"] == 2

    @pytest.mark.asyncio
    async def test_kb_search_sends_correct_request_body(self, kb_server):
        kb_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        await kb_server._invoke_kb_search(
            parameters={
                "query": "test",
                "knowledge_base_ids": ["kb-1", "kb-2"],
                "search_type": "semantic",
                "limit": 5,
            },
            context={"tenant_id": "tenant-abc"},
        )

        call_args = kb_server._backend.post.call_args
        path = call_args[0][0]
        body = call_args[0][1]
        assert path == "/api/rag/search"
        assert body["query"] == "test"
        assert body["variant_type"] == "parwa"
        assert body["top_k"] == 5
        assert body["filters"]["knowledge_base_ids"] == ["kb-1", "kb-2"]

    @pytest.mark.asyncio
    async def test_kb_search_uses_parwa_variant(self, kb_server):
        kb_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        await kb_server._invoke_kb_search(
            parameters={"query": "test"},
        )

        body = kb_server._backend.post.call_args[0][1]
        assert body["variant_type"] == "parwa"

    @pytest.mark.asyncio
    async def test_kb_search_no_kb_ids_omits_filters(self, kb_server):
        kb_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        await kb_server._invoke_kb_search(
            parameters={"query": "test"},
        )

        body = kb_server._backend.post.call_args[0][1]
        assert "filters" not in body

    @pytest.mark.asyncio
    async def test_kb_search_empty_query_rejected(self, kb_server):
        result = await kb_server._invoke_kb_search(
            parameters={"query": "   "},
        )

        assert result.success is False
        kb_server._backend.post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_kb_search_backend_error(self, kb_server):
        kb_server._backend.post.return_value = MOCK_ERROR_RESPONSE

        result = await kb_server._invoke_kb_search(
            parameters={"query": "test"},
        )

        assert result.success is False
        assert "unavailable" in result.error.lower() or "backend" in result.error.lower()

    @pytest.mark.asyncio
    async def test_kb_search_tenant_isolation(self, kb_server):
        kb_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        result = await kb_server._invoke_kb_search(
            parameters={"query": "test"},
            context={"tenant_id": "tenant-isolated"},
        )

        assert result.metadata["tenant_id"] == "tenant-isolated"
        for doc in result.data:
            assert doc["metadata"]["tenant_id"] == "tenant-isolated"

    @pytest.mark.asyncio
    async def test_kb_search_results_sorted_by_relevance(self, kb_server):
        kb_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        result = await kb_server._invoke_kb_search(
            parameters={"query": "test"},
        )

        scores = [d["relevance_score"] for d in result.data]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_kb_search_result_fields(self, kb_server):
        kb_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        result = await kb_server._invoke_kb_search(
            parameters={"query": "test"},
        )

        for doc in result.data:
            assert "id" in doc
            assert "title" in doc
            assert "content" in doc
            assert "knowledge_base_id" in doc
            assert "relevance_score" in doc
            assert "metadata" in doc

    @pytest.mark.asyncio
    async def test_kb_search_metadata_fields(self, kb_server):
        kb_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        result = await kb_server._invoke_kb_search(
            parameters={"query": "test", "search_type": "hybrid"},
        )

        assert result.metadata["query"] == "test"
        assert result.metadata["search_type"] == "hybrid"
        assert result.metadata["result_count"] == 2
        assert "elapsed_ms" in result.metadata


# ═══════════════════════════════════════════════════════════════════
# 3. kb_get_document Tool Tests
# ═══════════════════════════════════════════════════════════════════


class TestKBGetDocumentTool:
    """Test the kb_get_document tool handler."""

    @pytest.mark.asyncio
    async def test_get_document_success(self, kb_server):
        kb_server._backend.get.return_value = MOCK_GET_DOCUMENT_RESPONSE

        result = await kb_server._invoke_kb_get_document(
            parameters={"document_id": "doc-1", "company_id": "comp-1"},
        )

        assert result.success is True
        assert result.tool_name == "kb_get_document"
        assert result.data["id"] == "doc-1"
        assert result.data["title"] == "Refund Policy"
        assert result.data["content"] == "Full document content here."

    @pytest.mark.asyncio
    async def test_get_document_calls_correct_endpoint(self, kb_server):
        kb_server._backend.get.return_value = MOCK_GET_DOCUMENT_RESPONSE

        await kb_server._invoke_kb_get_document(
            parameters={"document_id": "doc-1", "company_id": "comp-1"},
        )

        kb_server._backend.get.assert_awaited_once_with("/api/rag/documents/comp-1/doc-1")

    @pytest.mark.asyncio
    async def test_get_document_no_document_id_rejected(self, kb_server):
        result = await kb_server._invoke_kb_get_document(
            parameters={"document_id": "", "company_id": "comp-1"},
        )

        assert result.success is False
        assert "document_id" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_document_no_company_id_rejected(self, kb_server):
        result = await kb_server._invoke_kb_get_document(
            parameters={"document_id": "doc-1"},
            context={},
        )

        assert result.success is False
        assert "company_id" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_document_uses_tenant_id_as_company_id_fallback(self, kb_server):
        """When company_id is not provided, tenant_id should be used as fallback."""
        kb_server._backend.get.return_value = MOCK_GET_DOCUMENT_RESPONSE

        await kb_server._invoke_kb_get_document(
            parameters={"document_id": "doc-1"},
            context={"tenant_id": "tenant-fallback"},
        )

        kb_server._backend.get.assert_awaited_once_with("/api/rag/documents/tenant-fallback/doc-1")

    @pytest.mark.asyncio
    async def test_get_document_backend_error(self, kb_server):
        kb_server._backend.get.return_value = MOCK_ERROR_RESPONSE

        result = await kb_server._invoke_kb_get_document(
            parameters={"document_id": "doc-1", "company_id": "comp-1"},
        )

        assert result.success is False
        assert "unavailable" in result.error.lower() or "backend" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_document_tenant_isolation(self, kb_server):
        kb_server._backend.get.return_value = MOCK_GET_DOCUMENT_RESPONSE

        result = await kb_server._invoke_kb_get_document(
            parameters={"document_id": "doc-1", "company_id": "comp-1"},
            context={"tenant_id": "tenant-xyz"},
        )

        assert result.metadata["tenant_id"] == "tenant-xyz"
        assert result.data["metadata"]["tenant_id"] == "tenant-xyz"

    @pytest.mark.asyncio
    async def test_get_document_metadata_includes_chunk_count(self, kb_server):
        kb_server._backend.get.return_value = MOCK_GET_DOCUMENT_RESPONSE

        result = await kb_server._invoke_kb_get_document(
            parameters={"document_id": "doc-1", "company_id": "comp-1"},
        )

        assert result.data["metadata"]["chunk_count"] == 5


# ═══════════════════════════════════════════════════════════════════
# 4. kb_list_bases Tool Tests
# ═══════════════════════════════════════════════════════════════════


class TestKBListBasesTool:
    """Test the kb_list_bases tool handler."""

    @pytest.mark.asyncio
    async def test_list_bases_success(self, kb_server):
        kb_server._backend.get.return_value = MOCK_KB_STATS_RESPONSE

        result = await kb_server._invoke_kb_list_bases(
            context={"tenant_id": "tenant-abc"},
        )

        assert result.success is True
        assert result.tool_name == "kb_list_bases"
        assert isinstance(result.data, list)
        assert len(result.data) >= 1

    @pytest.mark.asyncio
    async def test_list_bases_has_default_kb(self, kb_server):
        kb_server._backend.get.return_value = MOCK_KB_STATS_RESPONSE

        result = await kb_server._invoke_kb_list_bases()

        base = result.data[0]
        assert base["id"] == "default"
        assert base["name"] == "Primary Knowledge Base"
        assert base["doc_count"] == 50
        assert base["chunk_count"] == 800

    @pytest.mark.asyncio
    async def test_list_bases_health_status(self, kb_server):
        """Health should be 'healthy' when no failures, 'degraded' when failures exist."""
        # With failures
        kb_server._backend.get.return_value = MOCK_KB_STATS_RESPONSE
        result = await kb_server._invoke_kb_list_bases()
        assert result.data[0]["health"] == "degraded"  # 1 failed

        # Without failures
        kb_server._backend.get.return_value = MOCK_KB_STATS_NO_FAILURES
        result = await kb_server._invoke_kb_list_bases()
        assert result.data[0]["health"] == "healthy"

    @pytest.mark.asyncio
    async def test_list_bases_calls_kb_stats(self, kb_server):
        kb_server._backend.get.return_value = MOCK_KB_STATS_RESPONSE

        await kb_server._invoke_kb_list_bases()

        kb_server._backend.get.assert_awaited_once_with("/api/kb/stats")

    @pytest.mark.asyncio
    async def test_list_bases_backend_error(self, kb_server):
        kb_server._backend.get.return_value = MOCK_ERROR_RESPONSE

        result = await kb_server._invoke_kb_list_bases()

        assert result.success is False
        assert "unavailable" in result.error.lower() or "backend" in result.error.lower()

    @pytest.mark.asyncio
    async def test_list_bases_tenant_isolation(self, kb_server):
        kb_server._backend.get.return_value = MOCK_KB_STATS_RESPONSE

        result = await kb_server._invoke_kb_list_bases(
            context={"tenant_id": "tenant-list"},
        )

        assert result.metadata["tenant_id"] == "tenant-list"

    @pytest.mark.asyncio
    async def test_list_bases_status_summary(self, kb_server):
        kb_server._backend.get.return_value = MOCK_KB_STATS_RESPONSE

        result = await kb_server._invoke_kb_list_bases()

        summary = result.data[0]["status_summary"]
        assert summary["completed"] == 48
        assert summary["processing"] == 1
        assert summary["failed"] == 1
        assert summary["pending"] == 0


# ═══════════════════════════════════════════════════════════════════
# 5. kb_upload_url Tool Tests
# ═══════════════════════════════════════════════════════════════════


class TestKBUploadURLTool:
    """Test the kb_upload_url tool handler."""

    @pytest.mark.asyncio
    async def test_upload_url_success(self, kb_server):
        mock_fetch_result = {
            "status": "ok",
            "text": "This is the fetched URL content. It has enough text for chunking. " * 20,
            "title": "Test Page",
        }

        with patch("mcp_server.knowledge.kb_server._fetch_url_content", return_value=mock_fetch_result):
            kb_server._backend.post.return_value = MOCK_INGEST_SUCCESS_RESPONSE

            result = await kb_server._invoke_kb_upload_url(
                parameters={"url": "https://example.com/docs", "document_id": "doc-url-1"},
                context={"tenant_id": "tenant-abc"},
            )

        assert result.success is True
        assert result.tool_name == "kb_upload_url"
        assert result.data["url"] == "https://example.com/docs"
        assert result.data["document_id"] == "doc-url-1"
        assert result.data["title"] == "Test Page"
        assert result.data["chunks_created"] > 0

    @pytest.mark.asyncio
    async def test_upload_url_sends_to_documents_endpoint(self, kb_server):
        mock_fetch_result = {
            "status": "ok",
            "text": "Content for the document. " * 50,
            "title": "Test Page",
        }

        with patch("mcp_server.knowledge.kb_server._fetch_url_content", return_value=mock_fetch_result):
            kb_server._backend.post.return_value = MOCK_INGEST_SUCCESS_RESPONSE

            await kb_server._invoke_kb_upload_url(
                parameters={"url": "https://example.com", "document_id": "doc-1"},
            )

        call_args = kb_server._backend.post.call_args
        path = call_args[0][0]
        body = call_args[0][1]
        assert path == "/api/rag/documents"
        assert body["document_id"] == "doc-1"
        assert "chunks" in body
        assert body["metadata"]["source_type"] == "url"

    @pytest.mark.asyncio
    async def test_upload_url_empty_url_rejected(self, kb_server):
        result = await kb_server._invoke_kb_upload_url(
            parameters={"url": ""},
        )

        assert result.success is False
        assert "url" in result.error.lower()

    @pytest.mark.asyncio
    async def test_upload_url_fetch_failure(self, kb_server):
        mock_fetch_result = {
            "status": "error",
            "error": "HTTP 404 for https://example.com/missing",
        }

        with patch("mcp_server.knowledge.kb_server._fetch_url_content", return_value=mock_fetch_result):
            result = await kb_server._invoke_kb_upload_url(
                parameters={"url": "https://example.com/missing"},
            )

        assert result.success is False
        assert "404" in result.error or "fetch" in result.error.lower()

    @pytest.mark.asyncio
    async def test_upload_url_empty_text_fails(self, kb_server):
        mock_fetch_result = {
            "status": "ok",
            "text": "",
            "title": "Empty Page",
        }

        with patch("mcp_server.knowledge.kb_server._fetch_url_content", return_value=mock_fetch_result):
            result = await kb_server._invoke_kb_upload_url(
                parameters={"url": "https://example.com/empty"},
            )

        assert result.success is False
        assert "no extractable text" in result.error.lower() or "text" in result.error.lower()

    @pytest.mark.asyncio
    async def test_upload_url_auto_generates_document_id(self, kb_server):
        mock_fetch_result = {
            "status": "ok",
            "text": "Content for auto-ID test. " * 50,
            "title": "Auto ID Page",
        }

        with patch("mcp_server.knowledge.kb_server._fetch_url_content", return_value=mock_fetch_result):
            kb_server._backend.post.return_value = MOCK_INGEST_SUCCESS_RESPONSE

            result = await kb_server._invoke_kb_upload_url(
                parameters={"url": "https://example.com"},  # no document_id
                context={"tenant_id": "tenant-123"},
            )

        assert result.success is True
        assert result.data["document_id"].startswith("doc_url_")

    @pytest.mark.asyncio
    async def test_upload_url_backend_error(self, kb_server):
        mock_fetch_result = {
            "status": "ok",
            "text": "Content for error test. " * 50,
            "title": "Error Test",
        }

        with patch("mcp_server.knowledge.kb_server._fetch_url_content", return_value=mock_fetch_result):
            kb_server._backend.post.return_value = MOCK_ERROR_RESPONSE

            result = await kb_server._invoke_kb_upload_url(
                parameters={"url": "https://example.com", "document_id": "doc-1"},
            )

        assert result.success is False
        assert "unavailable" in result.error.lower() or "backend" in result.error.lower()

    @pytest.mark.asyncio
    async def test_upload_url_tenant_isolation(self, kb_server):
        mock_fetch_result = {
            "status": "ok",
            "text": "Tenant test content. " * 50,
            "title": "Tenant Test",
        }

        with patch("mcp_server.knowledge.kb_server._fetch_url_content", return_value=mock_fetch_result):
            kb_server._backend.post.return_value = MOCK_INGEST_SUCCESS_RESPONSE

            result = await kb_server._invoke_kb_upload_url(
                parameters={"url": "https://example.com", "document_id": "doc-1"},
                context={"tenant_id": "tenant-upload"},
            )

        assert result.metadata["tenant_id"] == "tenant-upload"


# ═══════════════════════════════════════════════════════════════════
# 6. Helper Function Tests
# ═══════════════════════════════════════════════════════════════════


class TestHelperFunctions:
    """Test the pure helper functions: _looks_like_html, _strip_html, _chunk_text."""

    def test_looks_like_html_with_html_tags(self):
        assert _looks_like_html("<html><body>Hello</body></html>") is True
        assert _looks_like_html("<p>Paragraph</p>") is True
        assert _looks_like_html("<div>Content</div>") is True

    def test_looks_like_html_with_plain_text(self):
        assert _looks_like_html("Just plain text") is False
        assert _looks_like_html("") is False

    def test_looks_like_html_with_angle_brackets_only(self):
        """Angle brackets alone without known HTML tags should return False."""
        assert _looks_like_html("5 > 3 and 2 < 4") is False

    def test_strip_html_removes_tags(self):
        html = "<p>Hello <strong>World</strong></p>"
        result = _strip_html(html)
        assert "<" not in result
        assert "Hello" in result
        assert "World" in result

    def test_strip_html_removes_script_and_style(self):
        html = "<script>alert('xss')</script><style>.x{}</style><p>Content</p>"
        result = _strip_html(html)
        assert "alert" not in result
        assert ".x" not in result
        assert "Content" in result

    def test_strip_html_decodes_entities(self):
        html = "Tom &amp; Jerry &lt;cartoon&gt;"
        result = _strip_html(html)
        assert "Tom & Jerry" in result
        assert "<cartoon>" in result

    def test_strip_html_collapses_whitespace(self):
        html = "<p>Hello</p>    <p>World</p>"
        result = _strip_html(html)
        assert "  " not in result  # no double spaces

    def test_chunk_text_basic(self):
        text = "A. " * 500  # ~2000 chars
        chunks = _chunk_text(text)
        assert len(chunks) > 1
        for chunk in chunks:
            assert "content" in chunk
            assert "metadata" in chunk

    def test_chunk_text_empty(self):
        assert _chunk_text("") == []
        assert _chunk_text("   ") == []

    def test_chunk_text_short_text(self):
        text = "Short text."
        chunks = _chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0]["content"] == "Short text."

    def test_chunk_text_metadata_has_chunk_index(self):
        text = "A. " * 500
        chunks = _chunk_text(text)
        for i, chunk in enumerate(chunks):
            assert chunk["metadata"]["chunk_index"] == i


# ═══════════════════════════════════════════════════════════════════
# 7. _fetch_url_content Tests (mocked httpx)
# ═══════════════════════════════════════════════════════════════════


class TestFetchURLContent:
    """Test the _fetch_url_content function with mocked httpx."""

    @pytest.mark.asyncio
    async def test_fetch_url_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"Page content here"
        mock_response.text = "Page content here"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("mcp_server.knowledge.kb_server.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_url_content("https://example.com")

        assert result["status"] == "ok"
        assert result["text"] == "Page content here"

    @pytest.mark.asyncio
    async def test_fetch_url_non_200_status(self):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.content = b"Not found"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("mcp_server.knowledge.kb_server.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_url_content("https://example.com/missing")

        assert result["status"] == "error"
        assert "404" in result["error"]

    @pytest.mark.asyncio
    async def test_fetch_url_timeout(self):
        import httpx as _httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("mcp_server.knowledge.kb_server.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_url_content("https://slow.example.com")

        assert result["status"] == "error"
        assert "timed out" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_fetch_url_http_error(self):
        import httpx as _httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_httpx.HTTPError("connection error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("mcp_server.knowledge.kb_server.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_url_content("https://error.example.com")

        assert result["status"] == "error"
        assert "HTTP error" in result["error"]

    @pytest.mark.asyncio
    async def test_fetch_url_extracts_title(self):
        html = "<html><head><title>My Page</title></head><body><p>Content</p></body></html>"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = html.encode("utf-8")
        mock_response.text = html

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("mcp_server.knowledge.kb_server.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_url_content("https://example.com")

        assert result["status"] == "ok"
        assert result["title"] == "My Page"

    @pytest.mark.asyncio
    async def test_fetch_url_strips_html(self):
        html = "<html><body><p>Content here</p></body></html>"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = html.encode("utf-8")
        mock_response.text = html

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("mcp_server.knowledge.kb_server.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_url_content("https://example.com")

        assert result["status"] == "ok"
        assert "<" not in result["text"]
        assert "Content here" in result["text"]


# ═══════════════════════════════════════════════════════════════════
# 8. REST Router Tests
# ═══════════════════════════════════════════════════════════════════


class TestKBRouter:
    """Test the FastAPI router endpoints."""

    def test_router_has_correct_prefix(self, kb_server):
        router = kb_server.get_router()
        assert router.prefix == "/knowledge/kb"

    def test_router_has_search_route(self, kb_server):
        router = kb_server.get_router()
        route_paths = [r.path for r in router.routes]
        assert "/knowledge/kb/search" in route_paths

    def test_router_has_bases_route(self, kb_server):
        router = kb_server.get_router()
        route_paths = [r.path for r in router.routes]
        assert "/knowledge/kb/bases" in route_paths

    def test_router_has_document_route(self, kb_server):
        router = kb_server.get_router()
        route_paths = [r.path for r in router.routes]
        assert "/knowledge/kb/documents/{document_id}" in route_paths

    def test_router_has_upload_url_route(self, kb_server):
        router = kb_server.get_router()
        route_paths = [r.path for r in router.routes]
        assert "/knowledge/kb/upload-url" in route_paths

    def test_router_search_is_post(self, kb_server):
        router = kb_server.get_router()
        for route in router.routes:
            if route.path == "/knowledge/kb/search":
                assert "POST" in route.methods

    def test_router_bases_is_get(self, kb_server):
        router = kb_server.get_router()
        for route in router.routes:
            if route.path == "/knowledge/kb/bases":
                assert "GET" in route.methods

    def test_router_document_is_get(self, kb_server):
        router = kb_server.get_router()
        for route in router.routes:
            if route.path == "/knowledge/kb/documents/{document_id}":
                assert "GET" in route.methods

    def test_router_upload_url_is_post(self, kb_server):
        router = kb_server.get_router()
        for route in router.routes:
            if route.path == "/knowledge/kb/upload-url":
                assert "POST" in route.methods


# ═══════════════════════════════════════════════════════════════════
# 9. Edge Cases and Additional Tests
# ═══════════════════════════════════════════════════════════════════


class TestKBEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_kb_search_none_parameters(self, kb_server):
        result = await kb_server._invoke_kb_search(parameters=None)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_kb_search_none_context(self, kb_server):
        kb_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        result = await kb_server._invoke_kb_search(
            parameters={"query": "test"},
            context=None,
        )
        assert result.success is True
        assert result.metadata["tenant_id"] == ""

    @pytest.mark.asyncio
    async def test_kb_get_document_none_context(self, kb_server):
        kb_server._backend.get.return_value = MOCK_GET_DOCUMENT_RESPONSE

        result = await kb_server._invoke_kb_get_document(
            parameters={"document_id": "doc-1", "company_id": "comp-1"},
            context=None,
        )
        assert result.success is True
        assert result.metadata["tenant_id"] == ""

    @pytest.mark.asyncio
    async def test_kb_search_empty_chunks_in_response(self, kb_server):
        response = {"status": "ok", "data": {"chunks": [], "total_found": 0}}
        kb_server._backend.post.return_value = response

        result = await kb_server._invoke_kb_search(
            parameters={"query": "test"},
        )
        assert result.success is True
        assert result.data == []

    @pytest.mark.asyncio
    async def test_upload_url_whitespace_url_rejected(self, kb_server):
        result = await kb_server._invoke_kb_upload_url(
            parameters={"url": "   "},
        )
        assert result.success is False

    def test_chunk_text_custom_size(self):
        """Test chunking with custom chunk_size."""
        text = "Word. " * 300  # ~1800 chars
        chunks = _chunk_text(text, chunk_size=500, overlap=100)
        assert len(chunks) > 1

    def test_strip_html_nbsp(self):
        html = "Hello&nbsp;World"
        result = _strip_html(html)
        assert "Hello World" in result

    @pytest.mark.asyncio
    async def test_kb_search_default_search_type(self, kb_server):
        kb_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        await kb_server._invoke_kb_search(
            parameters={"query": "test"},
        )

        # search_type should be in metadata
        # (it's passed through but not sent to backend)

    @pytest.mark.asyncio
    async def test_kb_search_default_limit(self, kb_server):
        kb_server._backend.post.return_value = MOCK_RAG_SEARCH_RESPONSE

        await kb_server._invoke_kb_search(
            parameters={"query": "test"},
        )

        body = kb_server._backend.post.call_args[0][1]
        assert body["top_k"] == 10  # default limit

    @pytest.mark.asyncio
    async def test_kb_list_bases_none_context(self, kb_server):
        kb_server._backend.get.return_value = MOCK_KB_STATS_RESPONSE

        result = await kb_server._invoke_kb_list_bases(context=None)
        assert result.success is True
        assert result.metadata["tenant_id"] == ""

    def test_chunk_text_single_char(self):
        chunks = _chunk_text("X")
        assert len(chunks) == 1
        assert chunks[0]["content"] == "X"
