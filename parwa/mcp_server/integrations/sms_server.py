"""
PARWA MCP — SMS Server

Provides SMS messaging tools via Twilio integration.
Wired to the ExternalToolBus for variant-aware channel permissions.

mini_parwa  → SMS NOT allowed
parwa       → SMS allowed
parwa_high  → SMS allowed
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.integrations.external_tool_bus import external_tool_bus, Channel
from mcp_server.models import (
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.sms_server")


class SMSServer(MCPServerBase):
    """MCP sub-server for SMS messaging via Twilio.

    Uses ExternalToolBus for:
    - Variant permission enforcement
    - Provider fallback (backend → direct Twilio)
    - Graceful degradation when Twilio not configured
    """

    name = "sms_server"
    description = "SMS messaging via Twilio (variant-aware: parwa & parwa_high only)"
    category = ToolCategory.INTEGRATION
    version = "2.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register SMS tools."""
        registry.register_tool(
            ToolDefinition(
                name="sms_send",
                description="Send an SMS message to a phone number. "
                            "Available for parwa and parwa_high variants only. "
                            "mini_parwa does not have SMS access. "
                            "Uses Twilio API for delivery.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Phone number (E.164 format, e.g. +919652852014)",
                        },
                        "body": {
                            "type": "string",
                            "description": "SMS message body (max 1600 characters)",
                        },
                        "company_id": {
                            "type": "string",
                            "description": "Tenant company ID (required for multi-tenant isolation)",
                        },
                        "variant": {
                            "type": "string",
                            "enum": ["mini_parwa", "parwa", "parwa_high"],
                            "default": "parwa",
                            "description": "Variant tier — determines channel permissions",
                        },
                        "ticket_id": {
                            "type": "string",
                            "description": "Optional ticket ID to link the SMS to",
                        },
                    },
                    "required": ["to", "body", "company_id"],
                },
                tags=["sms", "text", "twilio", "phone", "message"],
            ),
            handler=self._invoke_send_sms,
        )

        registry.register_tool(
            ToolDefinition(
                name="sms_send_ticket_update",
                description="Send a ticket status update SMS notification. "
                            "Builds the SMS body automatically from ticket info. "
                            "Available for parwa and parwa_high only.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "Customer phone number"},
                        "ticket_number": {"type": "string", "description": "Ticket number (e.g. TKT-1234)"},
                        "status": {
                            "type": "string",
                            "enum": ["created", "in_progress", "resolved", "escalated", "closed"],
                        },
                        "customer_name": {"type": "string"},
                        "company_id": {"type": "string"},
                        "variant": {
                            "type": "string",
                            "enum": ["mini_parwa", "parwa", "parwa_high"],
                            "default": "parwa",
                        },
                        "extra_message": {"type": "string"},
                    },
                    "required": ["to", "ticket_number", "status", "customer_name", "company_id"],
                },
                tags=["sms", "ticket", "notification", "status"],
            ),
            handler=self._invoke_ticket_update_sms,
        )

        registry.register_tool(
            ToolDefinition(
                name="sms_status",
                description="Check if SMS service is configured and which variants can use it.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "variant": {
                            "type": "string",
                            "enum": ["mini_parwa", "parwa", "parwa_high"],
                            "default": "parwa",
                        },
                    },
                },
                tags=["sms", "status", "configuration"],
            ),
            handler=self._invoke_sms_status,
        )

    def get_router(self) -> APIRouter:
        """Return the SMS REST router."""
        router = APIRouter(prefix="/integrations/sms", tags=["Integration — SMS"])

        @router.post("/send")
        async def send_sms(request: dict) -> dict:
            """Send an SMS via REST."""
            result = await self._invoke_send_sms(request)
            return result.model_dump()

        return router

    async def _invoke_send_sms(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle sms_send tool invocation via ExternalToolBus."""
        params = parameters or {}
        to = params.get("to", "")
        body = params.get("body", "")
        company_id = params.get("company_id", "")
        variant = params.get("variant", "parwa")

        logger.info(
            "sms_send_via_mcp",
            to=to[:15] + "..." if len(to) > 15 else to,
            company_id=company_id,
            variant=variant,
            body_len=len(body),
        )

        if not to or not body or not company_id:
            return ToolInvokeResponse(
                success=False,
                tool_name="sms_send",
                error="Missing required parameters: to, body, company_id",
            )

        result = await external_tool_bus.send_sms(
            variant=variant,
            company_id=company_id,
            to=to,
            body=body[:1600],
        )

        return ToolInvokeResponse(
            success=result.success,
            tool_name="sms_send",
            data=result.to_dict() if result.success else None,
            error=result.error if not result.success else None,
            metadata={"provider": result.provider, "channel": "sms"},
        )

    async def _invoke_ticket_update_sms(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle sms_send_ticket_update tool invocation."""
        params = parameters or {}
        to = params.get("to", "")
        ticket_number = params.get("ticket_number", "")
        status = params.get("status", "")
        customer_name = params.get("customer_name", "")
        company_id = params.get("company_id", "")
        variant = params.get("variant", "parwa")
        extra = params.get("extra_message", "")

        # Build SMS body
        prefix = f"[PARWA] {ticket_number}"
        status_messages = {
            "created": f"Hi {customer_name}, your ticket has been created. We'll respond shortly.",
            "in_progress": f"Hi {customer_name}, we're working on your ticket now.",
            "resolved": f"Hi {customer_name}, your ticket has been resolved. Thank you!",
            "escalated": f"Hi {customer_name}, your ticket has been escalated to a specialist.",
            "closed": f"Hi {customer_name}, your ticket has been closed.",
        }

        body = f"{prefix}: {status_messages.get(status, f'Status updated to {status}.')}"
        if extra and len(body) + len(extra) + 3 < 160:
            body += f" {extra}"

        result = await external_tool_bus.send_sms(
            variant=variant,
            company_id=company_id,
            to=to,
            body=body[:160],
        )

        return ToolInvokeResponse(
            success=result.success,
            tool_name="sms_send_ticket_update",
            data=result.to_dict() if result.success else None,
            error=result.error if not result.success else None,
            metadata={"provider": result.provider, "ticket_number": ticket_number},
        )

    async def _invoke_sms_status(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle sms_status tool invocation."""
        params = parameters or {}
        variant = params.get("variant", "parwa")

        allowed = external_tool_bus.is_channel_allowed(variant, Channel.SMS)
        configured = external_tool_bus.is_channel_configured(Channel.SMS)

        return ToolInvokeResponse(
            success=True,
            tool_name="sms_status",
            data={
                "variant": variant,
                "sms_allowed": allowed,
                "sms_configured": configured,
                "allowed_channels": external_tool_bus.get_allowed_channels(variant),
                "provider_status": external_tool_bus.get_provider_status(),
            },
        )


# Singleton instance
sms_server = SMSServer()
