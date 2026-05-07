"""
PARWA MCP — FAQ Server

Provides FAQ search and retrieval tools.
Searches the knowledge base for pre-built FAQ entries
that match customer queries.
"""

from __future__ import annotations

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


class FAQServer(MCPServerBase):
    """MCP sub-server for FAQ knowledge queries."""

    name = "faq_server"
    description = "FAQ search and retrieval from the knowledge base"
    category = ToolCategory.KNOWLEDGE
    version = "1.0.0"

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

    # ── Tool Handlers (placeholder implementations) ─────────────

    async def _invoke_faq_search(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle faq_search tool invocation.

        Placeholder: returns mock results. In production, this would
        query the backend FAQ service at BACKEND_URL/api/knowledge-base/faqs.
        """
        params = parameters or {}
        query = params.get("query", "")
        category = params.get("category")
        limit = params.get("limit", 5)
        language = params.get("language", "en")

        logger.info(
            "faq_search_invoked",
            query=query,
            category=category,
            limit=limit,
            language=language,
        )

        # Placeholder implementation — connects to backend in production
        mock_results = [
            FAQSearchResult(
                id=f"faq-{i}",
                question=f"Sample FAQ question {i}: How do I {query}?",
                answer=f"This is a placeholder answer for '{query}'. "
                       f"In production, this would be retrieved from the FAQ knowledge base "
                       f"via the PARWA backend API.",
                category=category or "general",
                confidence=max(0.5, 0.95 - (i * 0.1)),
                source="faq",
            )
            for i in range(min(limit, 3))
        ]

        return ToolInvokeResponse(
            success=True,
            tool_name="faq_search",
            data=[r.model_dump() for r in mock_results],
            metadata={
                "query": query,
                "result_count": len(mock_results),
                "source": "faq_knowledge_base",
                "status": "placeholder",
            },
        )

    async def _invoke_faq_categories(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle faq_get_categories tool invocation."""
        logger.info("faq_categories_invoked")

        # Placeholder categories
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
            metadata={"count": len(categories)},
        )


# Singleton instance for import and registration
faq_server = FAQServer()
