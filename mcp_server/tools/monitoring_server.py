"""
PARWA MCP — Monitoring Server (v2.0.0 — Wired to Real Backend)

Provides system health monitoring and alerting tools.
Wired to real backend health check API via httpx.

Backend routes: /health, /health/detail, /api/system/health
"""

from __future__ import annotations

import os

import httpx
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

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5100")


class MonitoringServer(MCPServerBase):
    """MCP sub-server for system monitoring and alerting — wired to real backend."""

    name = "monitoring_server"
    description = "System health monitoring, performance metrics, and alerting — wired to backend"
    category = ToolCategory.TOOL
    version = "2.0.0"

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

    async def _backend_call(
        self, method: str, path: str, json_data: dict | None = None, params: dict | None = None,
    ) -> dict | None:
        """Make an httpx call to the backend health API."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{BACKEND_URL}{path}"
                resp = await client.request(method, url, json=json_data, params=params)
                if resp.status_code in (200, 201):
                    return resp.json()
                logger.warning(
                    "monitoring_backend_error",
                    path=path,
                    status=resp.status_code,
                    body=resp.text[:200],
                )
        except Exception as exc:
            logger.warning("monitoring_backend_failed", path=path, error=str(exc)[:200])
        return None

    async def _invoke_get_status(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle monitoring_get_status tool invocation — wired to backend."""
        params = parameters or {}
        component = params.get("component")
        include_metrics = params.get("include_metrics", True)

        logger.info("monitoring_get_status_invoked", component=component)

        # Try detailed health first, fall back to basic health
        data = await self._backend_call("GET", "/health/detail")
        if not data:
            data = await self._backend_call("GET", "/health")

        if data:
            # Extract component data from backend health response
            components = []
            backend_services = data.get("services", data.get("components", {}))

            if isinstance(backend_services, dict):
                for name, info in backend_services.items():
                    comp_data = {"name": name, "status": info.get("status", "unknown") if isinstance(info, dict) else str(info)}
                    if include_metrics and isinstance(info, dict):
                        comp_data.update({k: v for k, v in info.items() if k != "status"})
                    components.append(comp_data)

            if not components:
                # Handle flat health response
                overall = data.get("status", data.get("health", "unknown"))
                components = [{"name": "backend", "status": overall}]

            if component:
                components = [c for c in components if c.get("name") == component]

            if not include_metrics:
                components = [{"name": c.get("name"), "status": c.get("status")} for c in components]

            # Extract alerts if present
            alerts = data.get("alerts", [])

            return ToolInvokeResponse(
                success=True,
                tool_name="monitoring_get_status",
                data={
                    "components": components,
                    "overall_status": data.get("status", data.get("health", "unknown")),
                    "alerts": alerts,
                },
                metadata={"source": "backend"},
            )

        # Fallback: backend unreachable
        return ToolInvokeResponse(
            success=True,
            tool_name="monitoring_get_status",
            data={
                "components": [{"name": "backend", "status": "unreachable"}],
                "overall_status": "degraded",
                "alerts": [{"severity": "critical", "message": "Backend server unreachable"}],
            },
            metadata={"source": "fallback"},
        )

    async def _invoke_get_alerts(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle monitoring_get_alerts tool invocation — wired to backend."""
        params = parameters or {}

        logger.info("monitoring_get_alerts_invoked", severity=params.get("severity"))

        # Try system health for alerts
        data = await self._backend_call("GET", "/api/system/health")
        if data:
            alerts = data.get("alerts", [])
            severity = params.get("severity")
            if severity:
                alerts = [a for a in alerts if isinstance(a, dict) and a.get("severity") == severity]
            limit = params.get("limit", 20)
            alerts = alerts[:limit]

            return ToolInvokeResponse(
                success=True,
                tool_name="monitoring_get_alerts",
                data={"alerts": alerts, "total": len(alerts)},
                metadata={"source": "backend"},
            )

        return ToolInvokeResponse(
            success=True,
            tool_name="monitoring_get_alerts",
            data={"alerts": [], "total": 0},
            metadata={"source": "fallback", "reason": "backend_unreachable"},
        )

    async def _invoke_get_performance(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle monitoring_get_performance tool invocation — wired to backend."""
        params = parameters or {}
        period = params.get("period", "1h")

        logger.info("monitoring_get_performance_invoked", period=period)

        # Try metrics endpoint
        data = await self._backend_call("GET", "/metrics", params={"format": "json"})
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="monitoring_get_performance",
                data={"period": period, **data},
                metadata={"source": "backend"},
            )

        # Fallback: try health detail for performance data
        data = await self._backend_call("GET", "/health/detail")
        if data:
            perf_data = {"period": period}
            services = data.get("services", {})
            for name, info in services.items():
                if isinstance(info, dict):
                    perf_data[name] = {k: v for k, v in info.items() if any(
                        kw in k.lower() for kw in ["latency", "throughput", "error", "time", "rate", "response"]
                    )}
            return ToolInvokeResponse(
                success=True,
                tool_name="monitoring_get_performance",
                data=perf_data,
                metadata={"source": "backend_health_detail"},
            )

        return ToolInvokeResponse(
            success=True,
            tool_name="monitoring_get_performance",
            data={"period": period, "message": "Performance data unavailable — backend unreachable"},
            metadata={"source": "fallback"},
        )


# Singleton instance
monitoring_server = MonitoringServer()
