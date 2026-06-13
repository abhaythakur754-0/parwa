"""
PARWA MCP — FAQ Server (v2.0.0 — Wired to Real Backend)

Provides FAQ search and retrieval tools.
Wired to real backend FAQ data via RAG search endpoint.

Backend routes: /api/rag/search (for semantic FAQ retrieval)
FAQ data source: backend/app/data/jarvis_knowledge/08_faq.json
"""

from __future__ import annotations

import json
import os

import httpx
from fastapi import APIRouter, Query

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.models import (
    FAQSearchRequest,
    FAQSearchResult,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
    ToolStatus,
)

logger = get_logger("mcp.faq_server")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5100")


class FAQServer(MCPServerBase):
    """MCP sub-server for FAQ knowledge queries — wired to real backend."""

    name = "faq_server"
    description = "FAQ search and retrieval from the knowledge base — wired to backend"
    category = ToolCategory.KNOWLEDGE
    version = "2.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register FAQ tools."""
        registry.register_tool(
            ToolDefinition(
                name="faq_search",
                description="Search FAQs by natural language query. Returns matching question-answer pairs.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language search query",
                        },
                        "category": {
                            "type": "string",
                            "description": "Optional FAQ category filter",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (1-50)",
                            "default": 5,
                        },
                        "language": {
                            "type": "string",
                            "description": "Response language code",
                            "default": "en",
                        },
                    },
                    "required": ["query"],
                },
                tags=["faq", "knowledge", "search"],
            ),
            handler=self._invoke_faq_search,
        )

        registry.register_tool(
            ToolDefinition(
                name="faq_get_categories",
                description="List all available FAQ categories.",
                category=self.category,
                server=self.name,
                tags=["faq", "categories", "knowledge"],
            ),
            handler=self._invoke_faq_categories,
        )

    def get_router(self) -> APIRouter:
        """Return the FAQ REST router."""
        router = APIRouter(prefix="/knowledge/faq", tags=["Knowledge — FAQ"])

        @router.post("/search", response_model=list[FAQSearchResult])
        async def search_faqs(request: FAQSearchRequest) -> list[FAQSearchResult]:
            """Search FAQs via REST endpoint."""
            result = await self._invoke_faq_search(request.model_dump())
            if result.success:
                return result.data or []
            logger.error("faq_search_failed", error=result.error)
            return []

        @router.get("/categories")
        async def list_categories() -> list[str]:
            """List FAQ categories."""
            result = await self._invoke_faq_categories({})
            if result.success:
                return result.data or []
            return []

        return router

    async def _backend_call(
        self, method: str, path: str, json_data: dict | None = None, params: dict | None = None,
    ) -> dict | None:
        """Make an httpx call to the backend API."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{BACKEND_URL}{path}"
                resp = await client.request(method, url, json=json_data, params=params)
                if resp.status_code in (200, 201):
                    return resp.json()
                logger.warning(
                    "faq_backend_error",
                    path=path,
                    status=resp.status_code,
                    body=resp.text[:200],
                )
        except Exception as exc:
            logger.warning("faq_backend_failed", path=path, error=str(exc)[:200])
        return None

    def _load_local_faq_data(self) -> list[dict]:
        """Load FAQ data from local JSON file as fallback."""
        try:
            faq_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "backend", "app", "data", "jarvis_knowledge", "08_faq.json",
            )
            if os.path.exists(faq_path):
                with open(faq_path, "r") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return data.get("faqs", data.get("items", []))
        except Exception as exc:
            logger.warning("faq_local_load_failed", error=str(exc)[:200])
        return []

    async def _invoke_faq_search(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle faq_search tool invocation — wired to backend RAG search."""
        params = parameters or {}
        query = params.get("query", "")
        category = params.get("category")
        limit = params.get("limit", 5)
        language = params.get("language", "en")

        logger.info("faq_search_invoked", query=query, category=category, limit=limit)

        # Try backend RAG search for FAQ content
        payload = {"query": query, "top_k": limit, "filters": {"source": "faq"}}
        if category:
            payload["filters"]["category"] = category

        data = await self._backend_call("POST", "/api/rag/search", json_data=payload)
        if data:
            results = data.get("results", data.get("chunks", []))
            if isinstance(data, list):
                results = data

            faq_results = []
            for i, r in enumerate(results):
                if isinstance(r, dict):
                    faq_results.append({
                        "id": r.get("id", f"faq-{i}"),
                        "question": r.get("title", r.get("question", query)),
                        "answer": r.get("content", r.get("text", r.get("answer", ""))),
                        "category": r.get("category", category or "general"),
                        "confidence": r.get("score", r.get("relevance_score", 0.5)),
                        "source": "faq",
                    })

            if faq_results:
                return ToolInvokeResponse(
                    success=True,
                    tool_name="faq_search",
                    data=faq_results,
                    metadata={
                        "query": query,
                        "result_count": len(faq_results),
                        "source": "backend",
                    },
                )

        # Fallback: try local FAQ file
        local_faqs = self._load_local_faq_data()
        if local_faqs:
            # Simple keyword matching on local data
            matched = []
            query_lower = query.lower()
            for faq in local_faqs[:limit]:
                q = faq.get("question", faq.get("title", ""))
                a = faq.get("answer", faq.get("content", ""))
                if query_lower in q.lower() or query_lower in a.lower() or not query:
                    matched.append({
                        "id": faq.get("id", f"faq-local-{len(matched)}"),
                        "question": q,
                        "answer": a,
                        "category": faq.get("category", category or "general"),
                        "confidence": 0.7,
                        "source": "faq",
                    })
                if len(matched) >= limit:
                    break

            if matched:
                return ToolInvokeResponse(
                    success=True,
                    tool_name="faq_search",
                    data=matched,
                    metadata={
                        "query": query,
                        "result_count": len(matched),
                        "source": "local_faq_file",
                    },
                )

        # No results found anywhere
        return ToolInvokeResponse(
            success=True,
            tool_name="faq_search",
            data=[],
            metadata={
                "query": query,
                "result_count": 0,
                "source": "none",
                "reason": "no_matching_faqs_found",
            },
        )

    async def _invoke_faq_categories(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle faq_get_categories tool invocation — from local FAQ data."""
        logger.info("faq_categories_invoked")

        local_faqs = self._load_local_faq_data()
        if local_faqs:
            categories = sorted(set(
                faq.get("category", "general")
                for faq in local_faqs
                if faq.get("category")
            ))
            if not categories:
                categories = ["general"]
        else:
            categories = [
                "billing",
                "account_management",
                "shipping",
                "returns",
                "product_information",
                "technical_support",
                "general",
            ]

        return ToolInvokeResponse(
            success=True,
            tool_name="faq_get_categories",
            data=categories,
            metadata={"count": len(categories), "source": "local_faq_data" if local_faqs else "default"},
        )


# Singleton instance for import and registration
faq_server = FAQServer()
