"""
PARWA MCP — Analytics Server

Provides analytics and reporting tools.
Exposes customer support metrics, trends, and
custom analytics queries.
"""

from __future__ import annotations

from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.models import (
    AnalyticsQueryRequest,
    AnalyticsQueryResponse,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.analytics_server")


class AnalyticsServer(MCPServerBase):
    """MCP sub-server for analytics and reporting."""

    name = "analytics_server"
    description = "Customer support analytics, metrics, and reporting"
    category = ToolCategory.TOOL
    version = "1.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register analytics tools."""
        registry.register_tool(
            ToolDefinition(
                name="analytics_query",
                description="Query customer support analytics metrics (CSAT, resolution time, "
                            "ticket volume, etc.) over configurable time periods and granularity.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "metric": {
                            "type": "string",
                            "description": "Metric name (csat, resolution_time, ticket_volume, "
                                          "first_response_time, escalation_rate, etc.)",
                        },
                        "period": {
                            "type": "string",
                            "enum": ["1h", "6h", "24h", "7d", "30d", "90d"],
                            "default": "24h",
                        },
                        "granularity": {
                            "type": "string",
                            "enum": ["minute", "hour", "day"],
                            "default": "hour",
                        },
                        "filters": {
                            "type": "object",
                            "description": "Additional filters (channel, priority, etc.)",
                        },
                    },
                    "required": ["metric"],
                },
                tags=["analytics", "metrics", "reporting", "kpi"],
            ),
            handler=self._invoke_analytics_query,
        )

        registry.register_tool(
            ToolDefinition(
                name="analytics_get_dashboard",
                description="Get a summary of all key metrics for the dashboard view.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "string",
                            "default": "24h",
                        },
                    },
                },
                tags=["analytics", "dashboard", "overview", "kpi"],
            ),
            handler=self._invoke_get_dashboard,
        )

    def get_router(self) -> APIRouter:
        """Return the analytics REST router."""
        router = APIRouter(prefix="/tools/analytics", tags=["Tool — Analytics"])

        @router.post("/query", response_model=AnalyticsQueryResponse)
        async def query_analytics(request: AnalyticsQueryRequest) -> AnalyticsQueryResponse:
            """Query analytics via REST."""
            result = await self._invoke_analytics_query(request.model_dump())
            if result.success and result.data:
                return AnalyticsQueryResponse(**result.data)
            return AnalyticsQueryResponse(metric=request.metric, period=request.period)

        return router

    async def _invoke_analytics_query(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle analytics_query tool invocation."""
        params = parameters or {}
        metric = params.get("metric", "")
        period = params.get("period", "24h")
        granularity = params.get("granularity", "hour")

        logger.info("analytics_query", metric=metric, period=period, granularity=granularity)

        return ToolInvokeResponse(
            success=True,
            tool_name="analytics_query",
            data={
                "metric": metric,
                "period": period,
                "data_points": [
                    {"timestamp": "2025-01-15T10:00:00Z", "value": 42.5},
                    {"timestamp": "2025-01-15T11:00:00Z", "value": 38.2},
                    {"timestamp": "2025-01-15T12:00:00Z", "value": 45.1},
                ],
                "summary": {
                    "avg": 41.9,
                    "min": 38.2,
                    "max": 45.1,
                    "trend": "stable",
                },
            },
            metadata={"granularity": granularity, "status": "placeholder"},
        )

    async def _invoke_get_dashboard(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle analytics_get_dashboard tool invocation."""
        params = parameters or {}
        period = params.get("period", "24h")

        logger.info("analytics_dashboard", period=period)

        return ToolInvokeResponse(
            success=True,
            tool_name="analytics_get_dashboard",
            data={
                "period": period,
                "metrics": {
                    "ticket_volume": {"value": 142, "trend": "+5%"},
                    "avg_csat": {"value": 4.3, "trend": "+0.2"},
                    "avg_resolution_time_hours": {"value": 4.2, "trend": "-12%"},
                    "first_response_time_minutes": {"value": 8.5, "trend": "-8%"},
                    "escalation_rate_percent": {"value": 6.2, "trend": "-2%"},
                    "ai_resolution_rate_percent": {"value": 68, "trend": "+3%"},
                },
            },
            metadata={"status": "placeholder"},
        )


# Singleton instance
analytics_server = AnalyticsServer()
