"""
PARWA MCP — SLA Server

Provides SLA (Service Level Agreement) management tools.
Tracks SLA policies, breach detection, and response/compliance metrics.
"""

from __future__ import annotations

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


class SLAServer(MCPServerBase):
    """MCP sub-server for SLA management."""

    name = "sla_server"
    description = "SLA policy management, breach detection, and compliance tracking"
    category = ToolCategory.TOOL
    version = "1.0.0"

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

    async def _invoke_sla_check(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle sla_check tool invocation."""
        params = parameters or {}
        ticket_id = params.get("ticket_id")
        policy_id = params.get("policy_id")
        include_breached = params.get("include_breached", False)

        logger.info(
            "sla_check",
            ticket_id=ticket_id,
            policy_id=policy_id,
            include_breached=include_breached,
        )

        if ticket_id:
            return ToolInvokeResponse(
                success=True,
                tool_name="sla_check",
                data={
                    "policy_name": "Default SLA Policy",
                    "current_breaches": 0,
                    "at_risk_count": 0,
                    "tickets": [
                        {
                            "ticket_id": ticket_id,
                            "status": "within_sla",
                            "response_deadline": "2025-01-15T12:00:00Z",
                            "resolution_deadline": "2025-01-16T12:00:00Z",
                            "time_remaining_hours": 18.5,
                        }
                    ],
                    "summary": {"compliance_rate": 96.5},
                },
                metadata={"status": "placeholder"},
            )

        return ToolInvokeResponse(
            success=True,
            tool_name="sla_check",
            data={
                "policy_name": "Default SLA Policy",
                "current_breaches": 0,
                "at_risk_count": 3,
                "tickets": [],
                "summary": {
                    "total_tickets": 142,
                    "compliance_rate": 96.5,
                    "avg_response_time_minutes": 8.5,
                    "avg_resolution_time_hours": 4.2,
                },
            },
            metadata={"status": "placeholder"},
        )

    async def _invoke_get_policies(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle sla_get_policies tool invocation."""
        logger.info("sla_policies_listed")

        return ToolInvokeResponse(
            success=True,
            tool_name="sla_get_policies",
            data={
                "policies": [
                    {
                        "id": "sla_default",
                        "name": "Default SLA Policy",
                        "first_response_minutes": 15,
                        "resolution_hours": 24,
                        "escalation_threshold_minutes": 30,
                    },
                    {
                        "id": "sla_premium",
                        "name": "Premium SLA Policy",
                        "first_response_minutes": 5,
                        "resolution_hours": 8,
                        "escalation_threshold_minutes": 10,
                    },
                ],
                "total": 2,
            },
            metadata={"status": "placeholder"},
        )

    async def _invoke_compliance_report(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle sla_get_compliance_report tool invocation."""
        params = parameters or {}
        period = params.get("period", "7d")

        logger.info("sla_compliance_report", period=period)

        return ToolInvokeResponse(
            success=True,
            tool_name="sla_get_compliance_report",
            data={
                "period": period,
                "overall_compliance_percent": 96.5,
                "total_tickets": 892,
                "breached_tickets": 31,
                "metrics": {
                    "first_response_sla_percent": 97.2,
                    "resolution_sla_percent": 95.8,
                    "customer_satisfaction_impact": -0.3,
                },
            },
            metadata={"status": "placeholder"},
        )


# Singleton instance
sla_server = SLAServer()
