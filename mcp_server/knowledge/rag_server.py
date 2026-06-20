"""
PARWA MCP — RAG Server (v2.0.0 — Wired to Real Backend)

Provides Retrieval-Augmented Generation query tools.
Wired to real backend RAG API via httpx.

Backend routes: /api/rag/*
"""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.models import (
    RAGQueryRequest,
    RAGQueryResult,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.rag_server")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5100")


class RAGServer(MCPServerBase):
    """MCP sub-server for RAG queries — wired to real backend."""

    name = "rag_server"
    description = "RAG pipeline queries for contextual document retrieval — wired to backend"
    category = ToolCategory.KNOWLEDGE
    version = "2.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register RAG tools."""
        registry.register_tool(
            ToolDefinition(
                name="rag_query",
                description="Query the RAG pipeline to retrieve relevant document chunks. "
                            "Returns top-k chunks with relevance scores for AI context enrichment.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query for retrieval",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of chunks to retrieve (1-20)",
                            "default": 5,
                        },
                        "knowledge_base_id": {
                            "type": "string",
                            "description": "Optional specific KB to query",
                        },
                        "filters": {
                            "type": "object",
                            "description": "Metadata filters for retrieval",
                        },
                    },
                    "required": ["query"],
                },
                tags=["rag", "retrieval", "knowledge", "vector"],
            ),
            handler=self._invoke_rag_query,
        )

        registry.register_tool(
            ToolDefinition(
                name="rag_rerank",
                description="Re-rank a set of retrieved chunks for better relevance ordering.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "chunks": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Chunks to re-rank",
                        },
                        "top_k": {
                            "type": "integer",
                            "default": 5,
                        },
                    },
                    "required": ["query", "chunks"],
                },
                tags=["rag", "reranking", "relevance"],
            ),
            handler=self._invoke_rag_rerank,
        )

        registry.register_tool(
            ToolDefinition(
                name="rag_health",
                description="Check the health status of the RAG pipeline and vector store.",
                category=self.category,
                server=self.name,
                tags=["rag", "health", "status"],
            ),
            handler=self._invoke_rag_health,
        )

    def get_router(self) -> APIRouter:
        """Return the RAG REST router."""
        router = APIRouter(prefix="/knowledge/rag", tags=["Knowledge — RAG"])

        @router.post("/query", response_model=list[RAGQueryResult])
        async def rag_query(request: RAGQueryRequest) -> list[RAGQueryResult]:
            """Query the RAG pipeline via REST."""
            result = await self._invoke_rag_query(request.model_dump())
            if result.success and result.data:
                return [RAGQueryResult(**r) for r in result.data]
            return []

        return router

    async def _backend_call(
        self, method: str, path: str, json_data: dict | None = None, params: dict | None = None,
    ) -> dict | None:
        """Make an httpx call to the backend RAG API."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{BACKEND_URL}{path}"
                resp = await client.request(method, url, json=json_data, params=params)
                if resp.status_code in (200, 201):
                    return resp.json()
                logger.warning(
                    "rag_backend_error",
                    path=path,
                    status=resp.status_code,
                    body=resp.text[:200],
                )
        except Exception as exc:
            logger.warning("rag_backend_failed", path=path, error=str(exc)[:200])
        return None

    async def _invoke_rag_query(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle rag_query tool invocation — wired to backend."""
        params = parameters or {}
        query = params.get("query", "")
        top_k = params.get("top_k", 5)
        kb_id = params.get("knowledge_base_id")

        logger.info("rag_query_invoked", query=query, top_k=top_k, knowledge_base_id=kb_id)

        payload: dict = {"query": query, "top_k": top_k}
        if kb_id:
            payload["knowledge_base_id"] = kb_id
        if params.get("filters"):
            payload["filters"] = params["filters"]
        if params.get("variant_type"):
            payload["variant_type"] = params["variant_type"]

        data = await self._backend_call("POST", "/api/rag/search", json_data=payload)
        if data:
            # Backend returns results in various formats, normalize
            results = data.get("results", data.get("chunks", []))
            if isinstance(data, list):
                results = data
            return ToolInvokeResponse(
                success=True,
                tool_name="rag_query",
                data=results,
                metadata={
                    "query": query,
                    "top_k": top_k,
                    "retrieved_count": len(results) if isinstance(results, list) else 1,
                    "source": "backend",
                },
            )

        # Fallback: no mock data — return honest empty response
        return ToolInvokeResponse(
            success=True,
            tool_name="rag_query",
            data=[],
            metadata={
                "query": query,
                "retrieved_count": 0,
                "source": "fallback",
                "reason": "backend_unreachable",
            },
        )

    async def _invoke_rag_rerank(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle rag_rerank tool invocation.

        Reranking is done client-side since backend doesn't have a dedicated rerank endpoint.
        Simple score-based sorting as fallback.
        """
        params = parameters or {}
        query = params.get("query", "")
        chunks = params.get("chunks", [])
        top_k = params.get("top_k", 5)

        logger.info("rag_rerank_invoked", query=query, chunk_count=len(chunks))

        # Sort chunks by score if available (descending)
        if chunks and isinstance(chunks, list):
            try:
                sorted_chunks = sorted(
                    chunks,
                    key=lambda c: float(c.get("score", c.get("relevance_score", 0))),
                    reverse=True,
                )
                reranked = sorted_chunks[:top_k]
            except (TypeError, ValueError):
                reranked = chunks[:top_k]
        else:
            reranked = chunks[:top_k] if isinstance(chunks, list) else []

        return ToolInvokeResponse(
            success=True,
            tool_name="rag_rerank",
            data=reranked,
            metadata={
                "original_count": len(chunks),
                "reranked_count": len(reranked),
                "source": "local_rerank",
            },
        )

    async def _invoke_rag_health(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle rag_health tool invocation — wired to backend."""
        data = await self._backend_call("GET", "/api/rag/health")
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="rag_health",
                data=data,
                metadata={"source": "backend"},
            )

        return ToolInvokeResponse(
            success=False,
            tool_name="rag_health",
            error="RAG health check failed — backend unreachable",
            metadata={"source": "fallback"},
        )


# Singleton instance
rag_server = RAGServer()
