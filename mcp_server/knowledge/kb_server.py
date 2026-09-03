"""
PARWA MCP — Knowledge Base Server (v2.0.0 — Wired to Real Backend)

Provides knowledge base document query tools.
Wired to real backend KB API via httpx.

Backend routes: /api/kb/*
"""

from __future__ import annotations

import os

import httpx
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

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


class KBServer(MCPServerBase):
    """MCP sub-server for knowledge base document queries — wired to real backend."""

    name = "kb_server"
    description = "Knowledge base document search and retrieval — wired to backend"
    category = ToolCategory.KNOWLEDGE
    version = "2.0.0"

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

        registry.register_tool(
            ToolDefinition(
                name="kb_stats",
                description="Get knowledge base statistics (document counts, processing status, etc.).",
                category=self.category,
                server=self.name,
                tags=["knowledge_base", "stats", "metrics"],
            ),
            handler=self._invoke_kb_stats,
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

    async def _backend_call(
        self, method: str, path: str, json_data: dict | None = None, params: dict | None = None,
    ) -> dict | None:
        """Make an httpx call to the backend KB API."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{BACKEND_URL}{path}"
                resp = await client.request(method, url, json=json_data, params=params)
                if resp.status_code in (200, 201):
                    return resp.json()
                logger.warning(
                    "kb_backend_error",
                    path=path,
                    status=resp.status_code,
                    body=resp.text[:200],
                )
        except Exception as exc:
            logger.warning("kb_backend_failed", path=path, error=str(exc)[:200])
        return None

    async def _invoke_kb_search(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle kb_search tool invocation — wired to backend RAG search."""
        params = parameters or {}
        query = params.get("query", "")
        search_type = params.get("search_type", "hybrid")
        limit = params.get("limit", 10)

        logger.info("kb_search_invoked", query=query, search_type=search_type, limit=limit)

        # Use RAG search as the backend KB search endpoint
        payload = {"query": query, "top_k": limit}
        data = await self._backend_call("POST", "/api/rag/search", json_data=payload)
        if data:
            results = data.get("results", data.get("chunks", []))
            if isinstance(data, list):
                results = data
            # Convert RAG results to KB document format
            kb_docs = []
            for i, r in enumerate(results):
                if isinstance(r, dict):
                    kb_docs.append({
                        "id": r.get("document_id", r.get("id", f"doc-{i + 1}")),
                        "title": r.get("title", r.get("source", f"Document {i + 1}")),
                        "content": r.get("content", r.get("text", "")),
                        "knowledge_base_id": r.get("knowledge_base_id", params.get("knowledge_base_ids", ["default"])[0] if params.get("knowledge_base_ids") else "default"),
                        "relevance_score": r.get("score", r.get("relevance_score", 0.0)),
                        "metadata": r.get("metadata", {}),
                    })
            return ToolInvokeResponse(
                success=True,
                tool_name="kb_search",
                data=kb_docs,
                metadata={
                    "query": query,
                    "search_type": search_type,
                    "result_count": len(kb_docs),
                    "source": "backend",
                },
            )

        # Fallback: no mock — honest empty response
        return ToolInvokeResponse(
            success=True,
            tool_name="kb_search",
            data=[],
            metadata={
                "query": query,
                "result_count": 0,
                "source": "fallback",
                "reason": "backend_unreachable",
            },
        )

    async def _invoke_kb_get_document(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle kb_get_document tool invocation — wired to backend."""
        params = parameters or {}
        doc_id = params.get("document_id", "")

        logger.info("kb_get_document_invoked", document_id=doc_id)

        data = await self._backend_call("GET", f"/api/kb/documents/{doc_id}")
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="kb_get_document",
                data=data,
                metadata={"source": "backend"},
            )

        return ToolInvokeResponse(
            success=False,
            tool_name="kb_get_document",
            error=f"Document '{doc_id}' not found or backend unreachable",
            metadata={"source": "fallback"},
        )

    async def _invoke_kb_list_bases(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle kb_list_bases tool invocation — wired to backend."""
        logger.info("kb_list_bases_invoked")

        data = await self._backend_call("GET", "/api/kb/documents")
        if data is not None:
            # Backend returns list of documents; extract unique KB IDs
            docs = data if isinstance(data, list) else data.get("documents", [])
            kb_ids = set()
            for doc in docs:
                if isinstance(doc, dict) and doc.get("knowledge_base_id"):
                    kb_ids.add(doc["knowledge_base_id"])

            bases = []
            if kb_ids:
                for kb_id in kb_ids:
                    bases.append({"id": kb_id, "name": kb_id, "doc_count": 0})
            else:
                # If no documents, still return a default base
                bases = [{"id": "default", "name": "Default Knowledge Base", "doc_count": 0}]

            return ToolInvokeResponse(
                success=True,
                tool_name="kb_list_bases",
                data=bases,
                metadata={"count": len(bases), "source": "backend"},
            )

        # Fallback
        return ToolInvokeResponse(
            success=True,
            tool_name="kb_list_bases",
            data=[{"id": "default", "name": "Default Knowledge Base", "doc_count": 0}],
            metadata={"count": 1, "source": "fallback", "reason": "backend_unreachable"},
        )

    async def _invoke_kb_stats(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle kb_stats tool invocation — wired to backend."""
        logger.info("kb_stats_invoked")

        data = await self._backend_call("GET", "/api/kb/stats")
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="kb_stats",
                data=data,
                metadata={"source": "backend"},
            )

        return ToolInvokeResponse(
            success=True,
            tool_name="kb_stats",
            data={"total_documents": 0, "total_chunks": 0, "status": "unknown"},
            metadata={"source": "fallback", "reason": "backend_unreachable"},
        )


# Singleton instance
kb_server = KBServer()
