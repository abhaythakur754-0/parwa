"""
PARWA MCP — Knowledge Base Server

Provides knowledge base document query tools.
Supports semantic, keyword, and hybrid search across
one or more knowledge bases.
"""

from __future__ import annotations

from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.models import (
    KBDocument,
    KBQueryRequest,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.kb_server")


class KBServer(MCPServerBase):
    """MCP sub-server for knowledge base document queries."""

    name = "kb_server"
    description = "Knowledge base document search and retrieval"
    category = ToolCategory.KNOWLEDGE
    version = "1.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register KB tools."""
        registry.register_tool(
            ToolDefinition(
                name="kb_search",
                description="Search knowledge base documents using semantic, keyword, or hybrid search. "
                            "Returns ranked documents with relevance scores.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "knowledge_base_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific KB IDs to search (empty = all)",
                        },
                        "search_type": {
                            "type": "string",
                            "enum": ["semantic", "keyword", "hybrid"],
                            "default": "hybrid",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
                tags=["knowledge_base", "search", "documents"],
            ),
            handler=self._invoke_kb_search,
        )

        registry.register_tool(
            ToolDefinition(
                name="kb_get_document",
                description="Retrieve a specific document from a knowledge base by ID.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "document_id": {
                            "type": "string",
                            "description": "Document ID to retrieve",
                        },
                        "knowledge_base_id": {
                            "type": "string",
                            "description": "Knowledge base containing the document",
                        },
                    },
                    "required": ["document_id"],
                },
                tags=["knowledge_base", "document", "retrieve"],
            ),
            handler=self._invoke_kb_get_document,
        )

        registry.register_tool(
            ToolDefinition(
                name="kb_list_bases",
                description="List all available knowledge bases.",
                category=self.category,
                server=self.name,
                tags=["knowledge_base", "list"],
            ),
            handler=self._invoke_kb_list_bases,
        )

    def get_router(self) -> APIRouter:
        """Return the KB REST router."""
        router = APIRouter(prefix="/knowledge/kb", tags=["Knowledge — KB"])

        @router.post("/search", response_model=list[KBDocument])
        async def search_kb(request: KBQueryRequest) -> list[KBDocument]:
            """Search knowledge bases via REST."""
            result = await self._invoke_kb_search(request.model_dump())
            if result.success and result.data:
                return [KBDocument(**d) for d in result.data]
            return []

        @router.get("/bases")
        async def list_bases() -> list[dict]:
            """List available knowledge bases."""
            result = await self._invoke_kb_list_bases({})
            if result.success:
                return result.data or []
            return []

        return router

    # ── Tool Handlers (placeholder implementations) ─────────────

    async def _invoke_kb_search(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle kb_search tool invocation."""
        params = parameters or {}
        query = params.get("query", "")
        kb_ids = params.get("knowledge_base_ids", [])
        search_type = params.get("search_type", "hybrid")
        limit = params.get("limit", 10)

        logger.info(
            "kb_search_invoked",
            query=query,
            search_type=search_type,
            kb_ids=kb_ids,
            limit=limit,
        )

        mock_docs = [
            KBDocument(
                id=f"doc-{i + 1}",
                title=f"Sample Document {i + 1}: {query}",
                content=(
                    f"Placeholder document content relevant to '{query}'. "
                    f"This would be retrieved from the knowledge base using "
                    f"{search_type} search in production."
                ),
                knowledge_base_id=kb_ids[0] if kb_ids else "default_kb",
                relevance_score=max(0.4, 0.95 - (i * 0.15)),
                metadata={
                    "search_type": search_type,
                    "chunk_index": i,
                },
            )
            for i in range(min(limit, 3))
        ]

        return ToolInvokeResponse(
            success=True,
            tool_name="kb_search",
            data=[d.model_dump() for d in mock_docs],
            metadata={
                "query": query,
                "search_type": search_type,
                "result_count": len(mock_docs),
                "status": "placeholder",
            },
        )

    async def _invoke_kb_get_document(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle kb_get_document tool invocation."""
        params = parameters or {}
        doc_id = params.get("document_id", "")
        kb_id = params.get("knowledge_base_id", "")

        logger.info("kb_get_document_invoked", document_id=doc_id, kb_id=kb_id)

        return ToolInvokeResponse(
            success=True,
            tool_name="kb_get_document",
            data={
                "id": doc_id,
                "title": f"Document {doc_id}",
                "content": "Placeholder document content. In production, "
                           "this would be fetched from the knowledge base.",
                "knowledge_base_id": kb_id,
                "metadata": {},
            },
            metadata={"status": "placeholder"},
        )

    async def _invoke_kb_list_bases(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle kb_list_bases tool invocation."""
        logger.info("kb_list_bases_invoked")

        mock_bases = [
            {"id": "kb_default", "name": "Default Knowledge Base", "doc_count": 150},
            {"id": "kb_product", "name": "Product Documentation", "doc_count": 89},
            {"id": "kb_policies", "name": "Company Policies", "doc_count": 42},
        ]

        return ToolInvokeResponse(
            success=True,
            tool_name="kb_list_bases",
            data=mock_bases,
            metadata={"count": len(mock_bases), "status": "placeholder"},
        )


# Singleton instance
kb_server = KBServer()
