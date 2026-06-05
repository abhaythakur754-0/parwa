"""
PARWA MCP — Email Server

Provides email send/receive/query tools for customer communication.
Integrates with Brevo (Sendinblue) for outbound email delivery.

V2: Wired to ExternalToolBus for:
- Variant-aware channel permissions
- Real Brevo API delivery (no more placeholders)
- Graceful degradation when Brevo not configured
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.integrations.external_tool_bus import external_tool_bus
from mcp_server.models import (
    EmailSendRequest,
    EmailSendResponse,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.email_server")


class EmailServer(MCPServerBase):
    """MCP sub-server for email communication via Brevo.

    Uses ExternalToolBus for real Brevo API delivery with
    variant permission enforcement and fallback handling.
    """

    name = "email_server"
    description = "Email send, receive, and query integration (Brevo) — variant-aware"
    category = ToolCategory.INTEGRATION
    version = "2.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register email tools."""
        registry.register_tool(
            ToolDefinition(
                name="email_send",
                description="Send an email to one or more recipients. Supports HTML body, "
                            "templates, CC/BCC, and attachments. "
                            "Available for ALL variant tiers (mini_parwa, parwa, parwa_high). "
                            "Uses Brevo (Sendinblue) for delivery.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Recipient email addresses",
                        },
                        "subject": {"type": "string"},
                        "body": {"type": "string", "description": "Plain text body"},
                        "html_body": {"type": "string", "description": "HTML body (optional, overrides plain text)"},
                        "cc": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "bcc": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "template_id": {"type": "string"},
                        "template_data": {"type": "object"},
                        "company_id": {
                            "type": "string",
                            "description": "Tenant company ID (required for multi-tenant isolation)",
                        },
                        "variant": {
                            "type": "string",
                            "enum": ["mini_parwa", "parwa", "parwa_high"],
                            "default": "mini_parwa",
                        },
                    },
                    "required": ["to", "subject", "body", "company_id"],
                },
                tags=["email", "send", "communication", "brevo"],
            ),
            handler=self._invoke_email_send,
        )

        registry.register_tool(
            ToolDefinition(
                name="email_send_ticket_update",
                description="Send a ticket status update email notification. "
                            "Builds the email HTML automatically from ticket info. "
                            "Available for ALL variant tiers.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "Customer email address"},
                        "ticket_number": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["created", "in_progress", "resolved", "escalated", "closed"],
                        },
                        "customer_name": {"type": "string"},
                        "subject_line": {"type": "string"},
                        "company_id": {"type": "string"},
                        "variant": {
                            "type": "string",
                            "enum": ["mini_parwa", "parwa", "parwa_high"],
                            "default": "mini_parwa",
                        },
                    },
                    "required": ["to", "ticket_number", "status", "customer_name", "company_id"],
                },
                tags=["email", "ticket", "notification", "status"],
            ),
            handler=self._invoke_ticket_update_email,
        )

        registry.register_tool(
            ToolDefinition(
                name="email_get_history",
                description="Retrieve email conversation history for a customer.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "email_address": {"type": "string"},
                        "limit": {"type": "integer", "default": 20},
                    },
                },
                tags=["email", "history", "conversation"],
            ),
            handler=self._invoke_email_history,
        )

    def get_router(self) -> APIRouter:
        """Return the email REST router."""
        router = APIRouter(prefix="/integrations/email", tags=["Integration — Email"])

        @router.post("/send", response_model=EmailSendResponse)
        async def send_email(request: EmailSendRequest) -> EmailSendResponse:
            """Send an email via REST."""
            result = await self._invoke_email_send(request.model_dump())
            if result.success and result.data:
                return EmailSendResponse(
                    message_id=result.data.get("message_id", ""),
                    status="sent",
                    recipients=result.data.get("recipients", request.to),
                )
            return EmailSendResponse(message_id="", status="failed")

        return router

    async def _invoke_email_send(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle email_send tool invocation via ExternalToolBus."""
        params = parameters or {}
        to = params.get("to", [])
        subject = params.get("subject", "")
        body = params.get("body", "")
        html_body = params.get("html_body", "")
        cc = params.get("cc", [])
        bcc = params.get("bcc", [])
        company_id = params.get("company_id", "")
        variant = params.get("variant", "mini_parwa")
        template_id = params.get("template_id")

        logger.info(
            "email_send_via_mcp",
            recipients=len(to) if isinstance(to, list) else 1,
            subject=subject[:80],
            variant=variant,
            company_id=company_id,
            template_id=template_id,
        )

        if not to or not subject or not body:
            return ToolInvokeResponse(
                success=False,
                tool_name="email_send",
                error="Missing required parameters: to, subject, body",
            )

        result = await external_tool_bus.send_email(
            variant=variant,
            company_id=company_id,
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
            cc=cc or None,
            bcc=bcc or None,
        )

        return ToolInvokeResponse(
            success=result.success,
            tool_name="email_send",
            data=result.to_dict() if result.success else None,
            error=result.error if not result.success else None,
            metadata={"provider": result.provider, "channel": "email"},
        )

    async def _invoke_ticket_update_email(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle email_send_ticket_update tool invocation."""
        params = parameters or {}
        to_email = params.get("to", "")
        ticket_number = params.get("ticket_number", "")
        status = params.get("status", "")
        customer_name = params.get("customer_name", "")
        subject_line = params.get("subject_line", "")
        company_id = params.get("company_id", "")
        variant = params.get("variant", "mini_parwa")

        # Build email content
        subject = subject_line or f"[PARWA] {ticket_number}: Ticket Update — {status.replace('_', ' ').title()}"

        status_messages = {
            "created": f"Hi {customer_name}, your support ticket {ticket_number} has been created. We'll respond shortly.",
            "in_progress": f"Hi {customer_name}, we're working on your ticket {ticket_number} now.",
            "resolved": f"Hi {customer_name}, your ticket {ticket_number} has been resolved. Thank you for contacting us!",
            "escalated": f"Hi {customer_name}, your ticket {ticket_number} has been escalated to a specialist. We'll update you soon.",
            "closed": f"Hi {customer_name}, your ticket {ticket_number} has been closed.",
        }

        body = status_messages.get(status, f"Your ticket {ticket_number} status has been updated to {status}.")

        html_body = (
            f"<div style='font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;'>"
            f"<h2 style='color: #2563eb;'>Ticket Update: {ticket_number}</h2>"
            f"<p>{body}</p>"
            f"<hr style='border: none; border-top: 1px solid #eee; margin: 20px 0;' />"
            f"<p style='color: #888; font-size: 12px;'>Powered by PARWA AI Workforce Platform</p>"
            f"</div>"
        )

        result = await external_tool_bus.send_email(
            variant=variant,
            company_id=company_id,
            to=to_email,
            subject=subject,
            body=body,
            html_body=html_body,
        )

        return ToolInvokeResponse(
            success=result.success,
            tool_name="email_send_ticket_update",
            data=result.to_dict() if result.success else None,
            error=result.error if not result.success else None,
            metadata={"provider": result.provider, "ticket_number": ticket_number},
        )

    async def _invoke_email_history(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle email_get_history tool invocation."""
        params = parameters or {}
        customer_id = params.get("customer_id")
        email_address = params.get("email_address")

        logger.info(
            "email_history_invoked",
            customer_id=customer_id,
            email=email_address,
        )

        # Try to get from backend
        try:
            import httpx
            import os

            backend_url = os.environ.get("BACKEND_URL", "http://localhost:5100")
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{backend_url}/api/v1/email/history",
                    params={"customer_id": customer_id, "email": email_address},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return ToolInvokeResponse(
                        success=True,
                        tool_name="email_get_history",
                        data=data,
                    )
        except Exception as exc:
            logger.warning("email_history_backend_failed", error=str(exc)[:200])

        return ToolInvokeResponse(
            success=True,
            tool_name="email_get_history",
            data={
                "emails": [],
                "total": 0,
                "message": "Email history not available — backend unreachable or no data",
            },
            metadata={"status": "fallback"},
        )


# Singleton instance
email_server = EmailServer()
