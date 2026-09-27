"""
PARWA MCP — SLA Server (v2.0.0 — Wired to Real Backend)

Provides SLA (Service Level Agreement) management tools.
Wired to real backend SLA API via httpx.

Backend routes: /api/v1/sla/*
"""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.models import (
    SLACheckRequest,
    SLACheckResponse,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.sla_server")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


class SLAServer(MCPServerBase):
    """MCP sub-server for SLA management — wired to real backend."""

    name = "sla_server"
    description = "SLA policy management, breach detection, and compliance tracking — wired to backend"
    category = ToolCategory.TOOL
    version = "2.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register SLA tools."""
        registry.register_tool(
            ToolDefinition(
                name="sla_check",
                description="Check SLA status for a specific ticket, policy, or across all tickets. "
                            "Returns breach status, at-risk tickets, and compliance metrics.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "ticket_id": {
                            "type": "string",
                            "description": "Specific ticket to check SLA for",
                        },
                        "policy_id": {
                            "type": "string",
                            "description": "Specific SLA policy to evaluate",
                        },
                        "include_breached": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include already-breached tickets",
                        },
                    },
                },
                tags=["sla", "breach", "policy", "compliance"],
            ),
            handler=self._invoke_sla_check,
        )

        registry.register_tool(
            ToolDefinition(
                name="sla_get_policies",
                description="List all configured SLA policies with their thresholds and targets.",
                category=self.category,
                server=self.name,
                tags=["sla", "policies", "configuration"],
            ),
            handler=self._invoke_get_policies,
        )

        registry.register_tool(
            ToolDefinition(
                name="sla_get_compliance_report",
                description="Generate an SLA compliance report for a time period.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "string",
                            "enum": ["24h", "7d", "30d", "90d"],
                            "default": "7d",
                        },
                        "start_date": {"type": "string", "description": "ISO date string"},
                        "end_date": {"type": "string", "description": "ISO date string"},
                    },
                },
                tags=["sla", "report", "compliance", "metrics"],
            ),
            handler=self._invoke_compliance_report,
        )

    def get_router(self) -> APIRouter:
        """Return the SLA REST router."""
        router = APIRouter(prefix="/tools/sla", tags=["Tool — SLA"])

        @router.post("/check", response_model=SLACheckResponse)
        async def sla_check(request: SLACheckRequest) -> SLACheckResponse:
            """Check SLA status via REST."""
            result = await self._invoke_sla_check(request.model_dump())
            if result.success and result.data:
                return SLACheckResponse(**result.data)
            return SLACheckResponse()

        return router

    async def _backend_call(
        self, method: str, path: str, json_data: dict | None = None, params: dict | None = None,
    ) -> dict | None:
        """Make an httpx call to the backend SLA API."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{BACKEND_URL}{path}"
                resp = await client.request(method, url, json=json_data, params=params)
                if resp.status_code in (200, 201):
                    return resp.json()
                logger.warning(
                    "sla_backend_error",
                    path=path,
                    status=resp.status_code,
                    body=resp.text[:200],
                )
        except Exception as exc:
            logger.warning("sla_backend_failed", path=path, error=str(exc)[:200])
        return None

    async def _invoke_sla_check(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle sla_check tool invocation — wired to backend."""
        params = parameters or {}
        ticket_id = params.get("ticket_id")
        policy_id = params.get("policy_id")
        include_breached = params.get("include_breached", False)

        logger.info("sla_check_invoked", ticket_id=ticket_id, policy_id=policy_id)

        if ticket_id:
            # Check SLA for specific ticket
            data = await self._backend_call("GET", f"/api/v1/sla/tickets/{ticket_id}")
            if data:
                return ToolInvokeResponse(
                    success=True,
                    tool_name="sla_check",
                    data=data,
                    metadata={"source": "backend"},
                )

        # Get breached tickets
        breached_data = None
        approaching_data = None
        if include_breached:
            breached_data = await self._backend_call("GET", "/api/v1/sla/breached")
        approaching_data = await self._backend_call("GET", "/api/v1/sla/approaching")

        # Get stats
        stats_data = await self._backend_call("GET", "/api/v1/sla/stats")

        if stats_data or breached_data or approaching_data:
            result_data = {
                "policy_name": "SLA Policies",
                "current_breaches": len(breached_data.get("tickets", [])) if breached_data else 0,
                "at_risk_count": len(approaching_data.get("tickets", [])) if approaching_data else 0,
                "tickets": breached_data.get("tickets", []) if breached_data else [],
                "approaching_tickets": approaching_data.get("tickets", []) if approaching_data else [],
            }
            if stats_data:
                result_data["summary"] = stats_data
            return ToolInvokeResponse(
                success=True,
                tool_name="sla_check",
                data=result_data,
                metadata={"source": "backend"},
            )

        # Fallback
        return ToolInvokeResponse(
            success=True,
            tool_name="sla_check",
            data={
                "policy_name": "SLA Policies",
                "current_breaches": 0,
                "at_risk_count": 0,
                "tickets": [],
                "summary": {},
                "message": "SLA data unavailable — backend unreachable",
            },
            metadata={"source": "fallback"},
        )

    async def _invoke_get_policies(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle sla_get_policies tool invocation — wired to backend."""
        logger.info("sla_get_policies_invoked")

        data = await self._backend_call("GET", "/api/v1/sla/policies")
        if data:
            policies = data if isinstance(data, list) else data.get("policies", [])
            return ToolInvokeResponse(
                success=True,
                tool_name="sla_get_policies",
                data={"policies": policies, "total": len(policies)},
                metadata={"source": "backend"},
            )

        # Fallback
        return ToolInvokeResponse(
            success=True,
            tool_name="sla_get_policies",
            data={"policies": [], "total": 0, "message": "SLA policies unavailable — backend unreachable"},
            metadata={"source": "fallback"},
        )

    async def _invoke_compliance_report(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle sla_get_compliance_report tool invocation — wired to backend."""
        params = parameters or {}
        period = params.get("period", "7d")

        logger.info("sla_compliance_report_invoked", period=period)

        query_params = {}
        if params.get("start_date"):
            query_params["start_date"] = params["start_date"]
        if params.get("end_date"):
            query_params["end_date"] = params["end_date"]

        data = await self._backend_call("GET", "/api/v1/sla/stats", params=query_params)
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="sla_get_compliance_report",
                data={"period": period, **data},
                metadata={"source": "backend"},
            )

        # Fallback
        return ToolInvokeResponse(
            success=True,
            tool_name="sla_get_compliance_report",
            data={
                "period": period,
                "overall_compliance_percent": 0,
                "total_tickets": 0,
                "breached_tickets": 0,
                "message": "SLA compliance report unavailable — backend unreachable",
            },
            metadata={"source": "fallback"},
        )


# Singleton instance
sla_server = SLAServer()
