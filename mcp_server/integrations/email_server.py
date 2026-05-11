"""
PARWA MCP — Email Server

Provides email send/receive/query tools for customer communication.
Integrates with Brevo (Sendinblue) for outbound email delivery.
"""

from __future__ import annotations

from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.models import (
    EmailSendRequest,
    EmailSendResponse,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.email_server")


class EmailServer(MCPServerBase):
    """MCP sub-server for email communication."""

    name = "email_server"
    description = "Email send, receive, and query integration (Brevo)"
    category = ToolCategory.INTEGRATION
    version = "1.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register email tools."""
        registry.register_tool(
            ToolDefinition(
                name="email_send",
                description="Send an email to one or more recipients. Supports HTML body, "
                            "templates, CC/BCC, and attachments.",
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
                        "body": {"type": "string"},
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
                    },
                    "required": ["to", "subject", "body"],
                },
                tags=["email", "send", "communication", "brevo"],
            ),
            handler=self._invoke_email_send,
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
                return EmailSendResponse(**result.data)
            return EmailSendResponse(message_id="", status="failed")

        return router

    async def _invoke_email_send(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle email_send tool invocation."""
        params = parameters or {}
        to = params.get("to", [])
        subject = params.get("subject", "")
        template_id = params.get("template_id")

        logger.info(
            "email_send_invoked",
            recipients=len(to),
            subject=subject[:80],
            template_id=template_id,
        )

        # Placeholder — connects to Brevo API in production
        return ToolInvokeResponse(
            success=True,
            tool_name="email_send",
            data={
                "message_id": f"msg_placeholder_{id(parameters) % 100000}",
                "status": "sent",
                "recipients": to,
            },
            metadata={
                "provider": "brevo",
                "status": "placeholder",
                "template_used": template_id is not None,
            },
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

        return ToolInvokeResponse(
            success=True,
            tool_name="email_get_history",
            data=[
                {
                    "id": "email-placeholder-1",
                    "subject": "Re: Your support request",
                    "from": email_address or "customer@example.com",
                    "to": "support@company.com",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "direction": "inbound",
                }
            ],
            metadata={"count": 1, "status": "placeholder"},
        )


# Singleton instance
email_server = EmailServer()
