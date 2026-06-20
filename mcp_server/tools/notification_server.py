"""
PARWA MCP — Notification Server (v2.0.0 — Wired to Real Backend)

Provides notification delivery tools.
Wired to real backend notification API via httpx.

Backend routes: /api/v1/notifications/*
"""

from __future__ import annotations

import os

import httpx
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

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5100")


class NotificationServer(MCPServerBase):
    """MCP sub-server for notification delivery — wired to real backend."""

    name = "notification_server"
    description = "Multi-channel notification delivery — wired to backend"
    category = ToolCategory.TOOL
    version = "2.0.0"

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

    async def _backend_call(
        self, method: str, path: str, json_data: dict | None = None, params: dict | None = None,
    ) -> dict | None:
        """Make an httpx call to the backend notification API."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{BACKEND_URL}{path}"
                resp = await client.request(method, url, json=json_data, params=params)
                if resp.status_code in (200, 201):
                    return resp.json()
                logger.warning(
                    "notification_backend_error",
                    path=path,
                    status=resp.status_code,
                    body=resp.text[:200],
                )
        except Exception as exc:
            logger.warning("notification_backend_failed", path=path, error=str(exc)[:200])
        return None

    async def _invoke_send(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle notification_send tool invocation — wired to backend."""
        params = parameters or {}
        recipient_type = params.get("recipient_type", "")
        recipient_id = params.get("recipient_id", "")
        channel = params.get("channel", "in_app")
        priority = params.get("priority", "normal")

        logger.info(
            "notification_send_invoked",
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            channel=channel,
            priority=priority,
        )

        payload = {
            "event_type": params.get("title", "custom_notification"),
            "recipient_ids": [recipient_id],
            "data": {
                "title": params.get("title", ""),
                "message": params.get("message", ""),
                "channel": channel,
                "priority": priority,
                "recipient_type": recipient_type,
                **(params.get("data", {}) or {}),
            },
            "channels": [channel],
            "priority": priority,
        }

        data = await self._backend_call("POST", "/api/v1/notifications/send", json_data=payload)
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="notification_send",
                data={
                    "notification_id": data.get("notification_id", data.get("id", "")),
                    "status": data.get("status", "sent"),
                    "channel": channel,
                    **data,
                },
                metadata={"channel": channel, "priority": priority, "source": "backend"},
            )

        # Fallback
        return ToolInvokeResponse(
            success=False,
            tool_name="notification_send",
            error="Notification delivery failed — backend unreachable",
            metadata={"channel": channel, "priority": priority, "source": "fallback"},
        )

    async def _invoke_get_preferences(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle notification_get_preferences tool invocation — wired to backend."""
        params = parameters or {}
        user_id = params.get("user_id", "")

        logger.info("notification_get_preferences_invoked", user_id=user_id)

        data = await self._backend_call("GET", "/api/v1/notifications/preferences")
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="notification_get_preferences",
                data={"user_id": user_id, **data},
                metadata={"source": "backend"},
            )

        # Fallback
        return ToolInvokeResponse(
            success=True,
            tool_name="notification_get_preferences",
            data={
                "user_id": user_id,
                "preferences": {},
                "message": "Notification preferences unavailable — backend unreachable",
            },
            metadata={"source": "fallback"},
        )


# Singleton instance
notification_server = NotificationServer()
