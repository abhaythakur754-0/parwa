"""
PARWA MCP — Monitoring Server

Provides system health monitoring and alerting tools.
Tracks service health, performance metrics, and
infrastructure status.
"""

from __future__ import annotations

from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.models import (
    MonitoringStatusRequest,
    MonitoringStatusResponse,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.monitoring_server")


class MonitoringServer(MCPServerBase):
    """MCP sub-server for system monitoring and alerting."""

    name = "monitoring_server"
    description = "System health monitoring, performance metrics, and alerting"
    category = ToolCategory.TOOL
    version = "1.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register monitoring tools."""
        registry.register_tool(
            ToolDefinition(
                name="monitoring_get_status",
                description="Get the health status of PARWA system components "
                            "(backend, database, Redis, AI pipeline, etc.).",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "component": {
                            "type": "string",
                            "description": "Specific component to check (null = all)",
                        },
                        "include_metrics": {
                            "type": "boolean",
                            "default": True,
                        },
                    },
                },
                tags=["monitoring", "health", "status", "metrics"],
            ),
            handler=self._invoke_get_status,
        )

        registry.register_tool(
            ToolDefinition(
                name="monitoring_get_alerts",
                description="Get current active alerts and recent alert history.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "warning", "info"],
                            "description": "Filter by severity",
                        },
                        "limit": {"type": "integer", "default": 20},
                    },
                },
                tags=["monitoring", "alerts", "incidents"],
            ),
            handler=self._invoke_get_alerts,
        )

        registry.register_tool(
            ToolDefinition(
                name="monitoring_get_performance",
                description="Get performance metrics (latency, throughput, error rates) "
                            "for the AI pipeline and system components.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "string",
                            "enum": ["1h", "6h", "24h", "7d"],
                            "default": "1h",
                        },
                    },
                },
                tags=["monitoring", "performance", "latency", "throughput"],
            ),
            handler=self._invoke_get_performance,
        )

    def get_router(self) -> APIRouter:
        """Return the monitoring REST router."""
        router = APIRouter(prefix="/tools/monitoring", tags=["Tool — Monitoring"])

        @router.post("/status", response_model=MonitoringStatusResponse)
        async def get_status(request: MonitoringStatusRequest) -> MonitoringStatusResponse:
            """Get monitoring status via REST."""
            result = await self._invoke_get_status(request.model_dump())
            if result.success and result.data:
                return MonitoringStatusResponse(**result.data)
            return MonitoringStatusResponse()

        return router

    async def _invoke_get_status(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle monitoring_get_status tool invocation."""
        params = parameters or {}
        component = params.get("component")
        include_metrics = params.get("include_metrics", True)

        logger.info("monitoring_status", component=component)

        components = [
            {
                "name": "backend",
                "status": "healthy",
                "uptime_seconds": 86400,
                "response_time_ms": 45,
            },
            {
                "name": "database",
                "status": "healthy",
                "connections_active": 12,
                "connections_max": 100,
            },
            {
                "name": "redis",
                "status": "healthy",
                "memory_used_mb": 128,
                "memory_max_mb": 512,
            },
            {
                "name": "ai_pipeline",
                "status": "healthy",
                "avg_latency_ms": 320,
                "error_rate_percent": 0.5,
            },
        ]

        if component:
            components = [c for c in components if c["name"] == component]

        if not include_metrics:
            components = [{"name": c["name"], "status": c["status"]} for c in components]

        return ToolInvokeResponse(
            success=True,
            tool_name="monitoring_get_status",
            data={
                "components": components,
                "overall_status": "healthy",
                "alerts": [],
            },
            metadata={"status": "placeholder"},
        )

    async def _invoke_get_alerts(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle monitoring_get_alerts tool invocation."""
        params = parameters or {}

        logger.info("monitoring_alerts_queried", severity=params.get("severity"))

        return ToolInvokeResponse(
            success=True,
            tool_name="monitoring_get_alerts",
            data={"alerts": [], "total": 0},
            metadata={"status": "placeholder"},
        )

    async def _invoke_get_performance(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle monitoring_get_performance tool invocation."""
        params = parameters or {}
        period = params.get("period", "1h")

        logger.info("monitoring_performance", period=period)

        return ToolInvokeResponse(
            success=True,
            tool_name="monitoring_get_performance",
            data={
                "period": period,
                "ai_pipeline": {
                    "avg_latency_ms": 320,
                    "p50_latency_ms": 280,
                    "p95_latency_ms": 650,
                    "p99_latency_ms": 1200,
                    "throughput_rps": 21.5,
                    "error_rate_percent": 0.5,
                },
                "api": {
                    "avg_latency_ms": 45,
                    "throughput_rps": 150,
                    "error_rate_percent": 0.1,
                },
            },
            metadata={"status": "placeholder"},
        )


# Singleton instance
monitoring_server = MonitoringServer()
