"""
Unit tests for PARWA MCP Knowledge Servers.

Tests for:
- BaseMCPServer: Abstract base class functionality
- FAQServer: FAQ lookup and search
- RAGServer: RAG-based document retrieval
- KBServer: Knowledge base operations

CRITICAL: All servers must respond within 2 seconds.
"""
import pytest
import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_servers.base_server import (
    BaseMCPServer,
    MCPServerState,
    ToolDefinition,
    ToolResult,
)
from mcp_servers.knowledge.faq_server import FAQServer
from mcp_servers.knowledge.rag_server import RAGServer
from mcp_servers.knowledge.kb_server import KBServer


# ═══════════════════════════════════════════════════════════════════════════════
# BASE MCP SERVER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBaseMCPServer:
    """Tests for BaseMCPServer abstract class."""

    @pytest.fixture
    def concrete_server(self):
        """Create a concrete implementation for testing."""
        class TestServer(BaseMCPServer):
            def _register_tools(self) -> None:
                self.register_tool(
                    name="test_tool",
                    description="A test tool",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "input": {"type": "string"}
                        },
                        "required": ["input"]
                    },
                    handler=self._handle_test
                )

            async def _handle_test(self, params: dict) -> dict:
                return {"result": params.get("input", "default")}

        return TestServer(name="test_server")

    @pytest.mark.asyncio
    async def test_server_initialization(self, concrete_server):
        """Test server initializes correctly."""
        assert concrete_server.name == "test_server"
        assert concrete_server.state == MCPServerState.STOPPED
        assert concrete_server.is_running is False
        assert "test_tool" in concrete_server.tools

    @pytest.mark.asyncio
    async def test_server_start(self, concrete_server):
        """Test server starts correctly."""
        await concrete_server.start()
        assert concrete_server.state == MCPServerState.RUNNING
        assert concrete_server.is_running is True

    @pytest.mark.asyncio
    async def test_server_stop(self, concrete_server):
        """Test server stops correctly."""
        await concrete_server.start()
        await concrete_server.stop()
        assert concrete_server.state == MCPServerState.STOPPED
        assert concrete_server.is_running is False

    @pytest.mark.asyncio
    async def test_tool_registration(self, concrete_server):
        """Test tool registration."""
        assert len(concrete_server.tools) == 1
        assert "test_tool" in concrete_server.tools

    @pytest.mark.asyncio
    async def test_duplicate_tool_registration_fails(self, concrete_server):
        """Test duplicate tool registration raises error."""
        with pytest.raises(ValueError, match="already registered"):
            concrete_server.register_tool(
                name="test_tool",
                description="Duplicate",
                parameters_schema={},
                handler=lambda x: x
            )

    @pytest.mark.asyncio
    async def test_handle_tool_call_success(self, concrete_server):
        """Test successful tool call handling."""
        await concrete_server.start()
        result = await concrete_server.handle_tool_call(
            "test_tool",
            {"input": "hello"}
        )
        assert result.success is True
        assert result.data["result"] == "hello"

    @pytest.mark.asyncio
    async def test_handle_tool_call_not_running(self, concrete_server):
        """Test tool call fails when server not running."""
        result = await concrete_server.handle_tool_call(
            "test_tool",
            {"input": "test"}
        )
        assert result.success is False
        assert "not running" in result.error.lower()

    @pytest.mark.asyncio
    async def test_handle_tool_call_not_found(self, concrete_server):
        """Test tool call fails for unknown tool."""
        await concrete_server.start()
        result = await concrete_server.handle_tool_call(
            "unknown_tool",
            {}
        )
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_handle_tool_call_missing_required_param(self, concrete_server):
        """Test tool call fails without required parameter."""
        await concrete_server.start()
        result = await concrete_server.handle_tool_call(
            "test_tool",
            {}
        )
        assert result.success is False
        assert "Missing required parameter" in result.error

    @pytest.mark.asyncio
    async def test_health_check(self, concrete_server):
        """Test health check returns valid status."""
        await concrete_server.start()
        health = await concrete_server.health_check()
        assert health["healthy"] is True
        assert health["state"] == MCPServerState.RUNNING.value
        assert health["server"] == "test_server"
        assert "tools" in health

    @pytest.mark.asyncio
    async def test_get_tool_schema(self, concrete_server):
        """Test getting tool schema."""
        schema = concrete_server.get_tool_schema("test_tool")
        assert schema["name"] == "test_tool"
        assert "parameters" in schema

    @pytest.mark.asyncio
    async def test_get_all_tool_schemas(self, concrete_server):
        """Test getting all tool schemas."""
        schemas = concrete_server.get_all_tool_schemas()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "test_tool"

    @pytest.mark.asyncio
    async def test_response_time_within_limit(self, concrete_server):
        """CRITICAL: Server must respond within 2 seconds."""
        await concrete_server.start()
        start = time.time()
        await concrete_server.handle_tool_call("test_tool", {"input": "test"})
        elapsed = (time.time() - start) * 1000
        assert elapsed < 2000, f"Response took {elapsed}ms, exceeds 2000ms limit"


# ═══════════════════════════════════════════════════════════════════════════════
# FAQ SERVER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFAQServer:
    """Tests for FAQ MCP server."""

    @pytest.fixture
    def faq_server(self):
        """Create FAQ server instance."""
        return FAQServer()

    @pytest.mark.asyncio
    async def test_server_starts(self, faq_server):
        """Test FAQ server starts correctly."""
        await faq_server.start()
        assert faq_server.is_running is True

    @pytest.mark.asyncio
    async def test_search_faqs_returns_results(self, faq_server):
        """Test search_faqs returns list of dicts."""
        await faq_server.start()
        result = await faq_server.handle_tool_call(
            "search_faqs",
            {"query": "refund"}
        )
        assert result.success is True
        assert "results" in result.data
        assert isinstance(result.data["results"], list)

    @pytest.mark.asyncio
    async def test_search_faqs_with_category_filter(self, faq_server):
        """Test search with category filter."""
        await faq_server.start()
        result = await faq_server.handle_tool_call(
            "search_faqs",
            {"query": "payment", "category": "Billing"}
        )
        assert result.success is True
        # All results should be in Billing category
        for faq in result.data["results"]:
            assert faq["category"] == "Billing"

    @pytest.mark.asyncio
    async def test_search_faqs_with_limit(self, faq_server):
        """Test search with limit parameter."""
        await faq_server.start()
        result = await faq_server.handle_tool_call(
            "search_faqs",
            {"query": "how", "limit": 2}
        )
        assert result.success is True
        assert len(result.data["results"]) <= 2

    @pytest.mark.asyncio
    async def test_search_faqs_empty_query(self, faq_server):
        """Test search with empty query returns empty results."""
        await faq_server.start()
        result = await faq_server.handle_tool_call(
            "search_faqs",
            {"query": ""}
        )
        assert result.success is True
        assert isinstance(result.data["results"], list)

    @pytest.mark.asyncio
    async def test_get_faq_by_id_success(self, faq_server):
        """Test getting FAQ by ID."""
        await faq_server.start()
        result = await faq_server.handle_tool_call(
            "get_faq_by_id",
            {"faq_id": "faq_001"}
        )
        assert result.success is True
        assert result.data["faq"]["id"] == "faq_001"

    @pytest.mark.asyncio
    async def test_get_faq_by_id_not_found(self, faq_server):
        """Test getting non-existent FAQ."""
        await faq_server.start()
        result = await faq_server.handle_tool_call(
            "get_faq_by_id",
            {"faq_id": "nonexistent"}
        )
        # Tool call succeeds, but data indicates failure
        assert result.success is True
        assert result.data["success"] is False
        assert "not found" in result.data["error"].lower()

    @pytest.mark.asyncio
    async def test_get_faq_categories(self, faq_server):
        """Test getting FAQ categories."""
        await faq_server.start()
        result = await faq_server.handle_tool_call(
            "get_faq_categories",
            {}
        )
        assert result.success is True
        assert "categories" in result.data
        assert len(result.data["categories"]) > 0

    @pytest.mark.asyncio
    async def test_faq_relevance_scoring(self, faq_server):
        """Test that relevance scoring works."""
        await faq_server.start()
        result = await faq_server.handle_tool_call(
            "search_faqs",
            {"query": "password reset"}
        )
        assert result.success is True
        # Results should have relevance_score
        if result.data["results"]:
            assert "relevance_score" in result.data["results"][0]

    @pytest.mark.asyncio
    async def test_faq_response_time(self, faq_server):
        """CRITICAL: FAQ server must respond within 2 seconds."""
        await faq_server.start()
        start = time.time()
        await faq_server.handle_tool_call("search_faqs", {"query": "test"})
        elapsed = (time.time() - start) * 1000
        assert elapsed < 2000


# ═══════════════════════════════════════════════════════════════════════════════
# RAG SERVER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestRAGServer:
    """Tests for RAG MCP server."""

    @pytest.fixture
    def rag_server(self):
        """Create RAG server instance."""
        return RAGServer()

    @pytest.mark.asyncio
    async def test_server_starts(self, rag_server):
        """Test RAG server starts correctly."""
        await rag_server.start()
        assert rag_server.is_running is True

    @pytest.mark.asyncio
    async def test_retrieve_returns_documents(self, rag_server):
        """Test retrieve returns documents with scores."""
        await rag_server.start()
        # First ingest some documents
        await rag_server.handle_tool_call(
            "ingest",
            {
                "documents": [
                    {"content": "This is a test document about Python programming."},
                    {"content": "Another document about machine learning and AI."}
                ]
            }
        )

        result = await rag_server.handle_tool_call(
            "retrieve",
            {"query": "Python programming"}
        )
        assert result.success is True
        assert "results" in result.data

    @pytest.mark.asyncio
    async def test_retrieve_empty_query_fails(self, rag_server):
        """Test retrieve fails with empty query."""
        await rag_server.start()
        result = await rag_server.handle_tool_call(
            "retrieve",
            {"query": ""}
        )
        # Tool call succeeds, but data indicates failure
        assert result.success is True
        assert result.data["success"] is False

    @pytest.mark.asyncio
    async def test_retrieve_with_custom_top_k(self, rag_server):
        """Test retrieve with custom top_k parameter."""
        await rag_server.start()
        result = await rag_server.handle_tool_call(
            "retrieve",
            {"query": "test", "top_k": 3}
        )
        assert result.success is True
        assert result.data["top_k"] == 3

    @pytest.mark.asyncio
    async def test_ingest_documents(self, rag_server):
        """Test document ingestion."""
        await rag_server.start()
        result = await rag_server.handle_tool_call(
            "ingest",
            {
                "documents": [
                    {"content": "Document 1 content", "metadata": {"source": "test"}},
                    {"content": "Document 2 content", "metadata": {"source": "test"}},
                ]
            }
        )
        assert result.success is True
        assert result.data["documents_ingested"] == 2
        assert len(result.data["document_ids"]) == 2

    @pytest.mark.asyncio
    async def test_ingest_empty_documents_fails(self, rag_server):
        """Test ingestion fails with empty documents list."""
        await rag_server.start()
        result = await rag_server.handle_tool_call(
            "ingest",
            {"documents": []}
        )
        # Tool call succeeds, but data indicates failure
        assert result.success is True
        assert result.data["success"] is False

    @pytest.mark.asyncio
    async def test_get_collection_stats(self, rag_server):
        """Test getting collection statistics."""
        await rag_server.start()
        result = await rag_server.handle_tool_call(
            "get_collection_stats",
            {}
        )
        assert result.success is True
        assert "total_documents" in result.data
        assert "total_chunks" in result.data

    @pytest.mark.asyncio
    async def test_rag_response_time(self, rag_server):
        """CRITICAL: RAG server must respond within 2 seconds."""
        await rag_server.start()
        start = time.time()
        await rag_server.handle_tool_call("retrieve", {"query": "test query"})
        elapsed = (time.time() - start) * 1000
        assert elapsed < 2000


# ═══════════════════════════════════════════════════════════════════════════════
# KB SERVER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestKBServer:
    """Tests for Knowledge Base MCP server."""

    @pytest.fixture
    def kb_server(self):
        """Create KB server instance."""
        return KBServer()

    @pytest.mark.asyncio
    async def test_server_starts(self, kb_server):
        """Test KB server starts correctly."""
        await kb_server.start()
        assert kb_server.is_running is True

    @pytest.mark.asyncio
    async def test_search_returns_articles(self, kb_server):
        """Test search returns articles."""
        await kb_server.start()
        result = await kb_server.handle_tool_call(
            "search",
            {"query": "api authentication"}
        )
        assert result.success is True
        assert "results" in result.data
        assert isinstance(result.data["results"], list)

    @pytest.mark.asyncio
    async def test_search_with_category_filter(self, kb_server):
        """Test search with category filter."""
        await kb_server.start()
        result = await kb_server.handle_tool_call(
            "search",
            {"query": "security", "filters": {"category": "Security"}}
        )
        assert result.success is True
        for article in result.data["results"]:
            assert article["category"] == "Security"

    @pytest.mark.asyncio
    async def test_search_with_tag_filter(self, kb_server):
        """Test search with tag filter."""
        await kb_server.start()
        result = await kb_server.handle_tool_call(
            "search",
            {
                "query": "help",
                "filters": {"tags": ["security", "encryption"]}
            }
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_get_article_success(self, kb_server):
        """Test getting article by ID."""
        await kb_server.start()
        result = await kb_server.handle_tool_call(
            "get_article",
            {"article_id": "kb_001"}
        )
        assert result.success is True
        assert result.data["article"]["id"] == "kb_001"

    @pytest.mark.asyncio
    async def test_get_article_not_found(self, kb_server):
        """Test getting non-existent article."""
        await kb_server.start()
        result = await kb_server.handle_tool_call(
            "get_article",
            {"article_id": "nonexistent"}
        )
        # Tool call succeeds, but data indicates failure
        assert result.success is True
        assert result.data["success"] is False

    @pytest.mark.asyncio
    async def test_get_related_articles(self, kb_server):
        """Test getting related articles."""
        await kb_server.start()
        result = await kb_server.handle_tool_call(
            "get_related_articles",
            {"article_id": "kb_001"}
        )
        assert result.success is True
        assert "related_articles" in result.data

    @pytest.mark.asyncio
    async def test_get_related_articles_not_found(self, kb_server):
        """Test getting related articles for non-existent article."""
        await kb_server.start()
        result = await kb_server.handle_tool_call(
            "get_related_articles",
            {"article_id": "nonexistent"}
        )
        # Tool call succeeds, but data indicates failure
        assert result.success is True
        assert result.data["success"] is False

    @pytest.mark.asyncio
    async def test_kb_response_time(self, kb_server):
        """CRITICAL: KB server must respond within 2 seconds."""
        await kb_server.start()
        start = time.time()
        await kb_server.handle_tool_call("search", {"query": "test"})
        elapsed = (time.time() - start) * 1000
        assert elapsed < 2000

    @pytest.mark.asyncio
    async def test_kb_health_check_extended(self, kb_server):
        """Test KB server extended health check."""
        await kb_server.start()
        health = await kb_server.health_check()
        assert "total_articles" in health
        assert "categories" in health


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestKnowledgeServersIntegration:
    """Integration tests for all knowledge servers."""

    @pytest.mark.asyncio
    async def test_all_servers_start(self):
        """Test all knowledge servers can start."""
        servers = [FAQServer(), RAGServer(), KBServer()]

        for server in servers:
            await server.start()
            assert server.is_running is True
            await server.stop()

    @pytest.mark.asyncio
    async def test_all_servers_have_required_tools(self):
        """Test all servers have their required tools."""
        faq = FAQServer()
        rag = RAGServer()
        kb = KBServer()

        assert "search_faqs" in faq.tools
        assert "get_faq_by_id" in faq.tools
        assert "get_faq_categories" in faq.tools

        assert "retrieve" in rag.tools
        assert "ingest" in rag.tools
        assert "get_collection_stats" in rag.tools

        assert "search" in kb.tools
        assert "get_article" in kb.tools
        assert "get_related_articles" in kb.tools

    @pytest.mark.asyncio
    async def test_all_servers_respond_within_2_seconds(self):
        """CRITICAL: All servers must respond within 2 seconds."""
        servers = [
            (FAQServer(), "search_faqs", {"query": "test"}),
            (RAGServer(), "retrieve", {"query": "test"}),
            (KBServer(), "search", {"query": "test"}),
        ]

        for server, tool, params in servers:
            await server.start()
            start = time.time()
            await server.handle_tool_call(tool, params)
            elapsed = (time.time() - start) * 1000
            assert elapsed < 2000, f"{server.name} took {elapsed}ms"
            await server.stop()

    @pytest.mark.asyncio
    async def test_knowledge_workflow(self):
        """Test a complete knowledge retrieval workflow."""
        faq = FAQServer()
        rag = RAGServer()
        kb = KBServer()

        # Start all servers
        await faq.start()
        await rag.start()
        await kb.start()

        # 1. Search FAQs
        faq_result = await faq.handle_tool_call(
            "search_faqs",
            {"query": "password reset"}
        )
        assert faq_result.success is True

        # 2. Ingest and retrieve from RAG
        await rag.handle_tool_call(
            "ingest",
            {"documents": [{"content": "Password reset instructions..."}]}
        )
        rag_result = await rag.handle_tool_call(
            "retrieve",
            {"query": "password reset"}
        )
        assert rag_result.success is True

        # 3. Search KB
        kb_result = await kb.handle_tool_call(
            "search",
            {"query": "security"}
        )
        assert kb_result.success is True

        # Cleanup
        await faq.stop()
        await rag.stop()
        await kb.stop()
