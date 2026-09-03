"""
PARWA MCP — Analytics Server (v2.0.0 — Wired to Real Backend)

Provides analytics and reporting tools.
Wired to real backend analytics API via httpx.

Backend routes: /analytics/tickets/*, analytics_service
"""

from __future__ import annotations

import os

import httpx
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

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


class AnalyticsServer(MCPServerBase):
    """MCP sub-server for analytics and reporting — wired to real backend."""

    name = "analytics_server"
    description = "Customer support analytics, metrics, and reporting — wired to backend"
    category = ToolCategory.TOOL
    version = "2.0.0"

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
                        "start_date": {"type": "string", "description": "ISO date string"},
                        "end_date": {"type": "string", "description": "ISO date string"},
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

    async def _backend_call(
        self, method: str, path: str, json_data: dict | None = None, params: dict | None = None,
    ) -> dict | None:
        """Make an httpx call to the backend analytics API."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{BACKEND_URL}{path}"
                resp = await client.request(method, url, json=json_data, params=params)
                if resp.status_code in (200, 201):
                    return resp.json()
                logger.warning(
                    "analytics_backend_error",
                    path=path,
                    status=resp.status_code,
                    body=resp.text[:200],
                )
        except Exception as exc:
            logger.warning("analytics_backend_failed", path=path, error=str(exc)[:200])
        return None

    async def _invoke_analytics_query(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle analytics_query tool invocation — wired to backend."""
        params = parameters or {}
        metric = params.get("metric", "")
        period = params.get("period", "24h")
        granularity = params.get("granularity", "hour")

        logger.info("analytics_query_invoked", metric=metric, period=period, granularity=granularity)

        # Map metric to backend endpoint
        metric_endpoint_map = {
            "ticket_volume": "/analytics/tickets/summary",
            "resolution_time": "/analytics/tickets/sla",
            "csat": "/analytics/tickets/summary",
            "first_response_time": "/analytics/tickets/sla",
            "escalation_rate": "/analytics/tickets/summary",
            "category_distribution": "/analytics/tickets/category",
            "trends": "/analytics/tickets/trends",
            "agent_performance": "/analytics/tickets/agents",
        }

        endpoint = metric_endpoint_map.get(metric, "/analytics/tickets/dashboard")
        query_params = {}
        if params.get("start_date"):
            query_params["start_date"] = params["start_date"]
        if params.get("end_date"):
            query_params["end_date"] = params["end_date"]

        data = await self._backend_call("GET", endpoint, params=query_params)
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="analytics_query",
                data={
                    "metric": metric,
                    "period": period,
                    **data,
                },
                metadata={"granularity": granularity, "source": "backend"},
            )

        # Fallback
        return ToolInvokeResponse(
            success=True,
            tool_name="analytics_query",
            data={
                "metric": metric,
                "period": period,
                "data_points": [],
                "summary": {"message": "Analytics data unavailable — backend unreachable"},
            },
            metadata={"granularity": granularity, "source": "fallback", "reason": "backend_unreachable"},
        )

    async def _invoke_get_dashboard(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle analytics_get_dashboard tool invocation — wired to backend."""
        params = parameters or {}
        period = params.get("period", "24h")

        logger.info("analytics_dashboard_invoked", period=period)

        query_params = {}
        if params.get("start_date"):
            query_params["start_date"] = params["start_date"]
        if params.get("end_date"):
            query_params["end_date"] = params["end_date"]

        data = await self._backend_call("GET", "/analytics/tickets/dashboard", params=query_params)
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="analytics_get_dashboard",
                data={"period": period, **data},
                metadata={"source": "backend"},
            )

        # Fallback
        return ToolInvokeResponse(
            success=True,
            tool_name="analytics_get_dashboard",
            data={
                "period": period,
                "metrics": {},
                "message": "Dashboard data unavailable — backend unreachable",
            },
            metadata={"source": "fallback", "reason": "backend_unreachable"},
        )


# Singleton instance
analytics_server = AnalyticsServer()
