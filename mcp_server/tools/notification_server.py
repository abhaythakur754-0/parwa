"""
PARWA MCP — Notification Server

Provides notification delivery tools.
Supports in-app, email, SMS, push, and webhook notifications
for agents, customers, and admins.
"""

from __future__ import annotations

from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.models import (
    NotificationSendRequest,
    NotificationSendResponse,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.notification_server")


class NotificationServer(MCPServerBase):
    """MCP sub-server for notification delivery."""

    name = "notification_server"
    description = "Multi-channel notification delivery (in-app, email, SMS, push, webhook)"
    category = ToolCategory.TOOL
    version = "1.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register notification tools."""
        registry.register_tool(
            ToolDefinition(
                name="notification_send",
                description="Send a notification to a recipient via the specified channel. "
                            "Supports in-app, email, SMS, push, and webhook delivery.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "recipient_type": {
                            "type": "string",
                            "enum": ["agent", "customer", "admin", "channel"],
                        },
                        "recipient_id": {"type": "string"},
                        "title": {"type": "string"},
                        "message": {"type": "string"},
                        "channel": {
                            "type": "string",
                            "enum": ["in_app", "email", "sms", "push", "webhook"],
                            "default": "in_app",
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "normal", "high", "urgent"],
                            "default": "normal",
                        },
                        "data": {"type": "object"},
                    },
                    "required": ["recipient_type", "recipient_id", "title", "message"],
                },
                tags=["notification", "send", "alert", "delivery"],
            ),
            handler=self._invoke_send,
        )

        registry.register_tool(
            ToolDefinition(
                name="notification_get_preferences",
                description="Get notification preferences for a user.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"},
                    },
                    "required": ["user_id"],
                },
                tags=["notification", "preferences", "settings"],
            ),
            handler=self._invoke_get_preferences,
        )

    def get_router(self) -> APIRouter:
        """Return the notification REST router."""
        router = APIRouter(prefix="/tools/notification", tags=["Tool — Notification"])

        @router.post("/send", response_model=NotificationSendResponse)
        async def send_notification(request: NotificationSendRequest) -> NotificationSendResponse:
            """Send a notification via REST."""
            result = await self._invoke_send(request.model_dump())
            if result.success and result.data:
                return NotificationSendResponse(**result.data)
            return NotificationSendResponse(notification_id="", status="failed")

        return router

    async def _invoke_send(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle notification_send tool invocation."""
        params = parameters or {}
        recipient_type = params.get("recipient_type", "")
        recipient_id = params.get("recipient_id", "")
        channel = params.get("channel", "in_app")
        priority = params.get("priority", "normal")

        logger.info(
            "notification_sent",
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            channel=channel,
            priority=priority,
        )

        return ToolInvokeResponse(
            success=True,
            tool_name="notification_send",
            data={
                "notification_id": f"notif_placeholder_{id(parameters) % 100000}",
                "status": "sent",
                "channel": channel,
            },
            metadata={"channel": channel, "priority": priority, "status": "placeholder"},
        )

    async def _invoke_get_preferences(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle notification_get_preferences tool invocation."""
        params = parameters or {}
        user_id = params.get("user_id", "")

        logger.info("notification_preferences", user_id=user_id)

        return ToolInvokeResponse(
            success=True,
            tool_name="notification_get_preferences",
            data={
                "user_id": user_id,
                "preferences": {
                    "in_app": {"enabled": True, "ticket_assigned": True, "sla_warning": True},
                    "email": {"enabled": True, "ticket_assigned": True, "sla_warning": True, "daily_digest": False},
                    "sms": {"enabled": False, "urgent_only": True},
                    "push": {"enabled": True, "ticket_assigned": True},
                },
            },
            metadata={"status": "placeholder"},
        )


# Singleton instance
notification_server = NotificationServer()
