"""
PARWA MCP — Chat Server

Provides live chat messaging tools.
Supports multi-channel chat (widget, web, mobile)
with AI-powered response generation.

V2: Wired to ExternalToolBus for:
- Real AI pipeline integration (no more placeholder responses)
- Variant-aware routing
- Graceful template fallback when AI pipeline unavailable
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.integrations.external_tool_bus import external_tool_bus
from mcp_server.models import (
    ChatMessageRequest,
    ChatMessageResponse,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.chat_server")


class ChatServer(MCPServerBase):
    """MCP sub-server for chat communication channels.

    Uses ExternalToolBus for real AI pipeline integration with
    template fallback when the pipeline is unavailable.
    """

    name = "chat_server"
    description = "Live chat messaging across channels (widget, web, mobile) — AI-powered"
    category = ToolCategory.INTEGRATION
    version = "2.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register chat tools."""
        registry.register_tool(
            ToolDefinition(
                name="chat_send_message",
                description="Send a chat message and receive an AI-generated response. "
                            "Supports multiple channels (chat_widget, web, mobile). "
                            "Available for ALL variant tiers. "
                            "Routes through the PARWA AI pipeline for intelligent responses.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "conversation_id": {
                            "type": "string",
                            "description": "Existing conversation ID (new if omitted)",
                        },
                        "message": {"type": "string", "description": "Customer message"},
                        "channel": {
                            "type": "string",
                            "default": "chat_widget",
                            "enum": ["chat_widget", "web", "mobile"],
                        },
                        "customer_id": {"type": "string"},
                        "company_id": {
                            "type": "string",
                            "description": "Tenant company ID",
                        },
                        "variant": {
                            "type": "string",
                            "enum": ["mini_parwa", "parwa", "parwa_high"],
                            "default": "mini_parwa",
                        },
                    },
                    "required": ["message"],
                },
                tags=["chat", "message", "conversation", "ai"],
            ),
            handler=self._invoke_send_message,
        )

        registry.register_tool(
            ToolDefinition(
                name="chat_get_conversation",
                description="Retrieve full conversation history by conversation ID.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "conversation_id": {"type": "string"},
                        "company_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 50},
                    },
                    "required": ["conversation_id"],
                },
                tags=["chat", "history", "conversation"],
            ),
            handler=self._invoke_get_conversation,
        )

        registry.register_tool(
            ToolDefinition(
                name="chat_list_active",
                description="List active chat conversations for a company.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "company_id": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["active", "waiting", "all"],
                            "default": "active",
                        },
                        "limit": {"type": "integer", "default": 20},
                    },
                    "required": ["company_id"],
                },
                tags=["chat", "list", "active"],
            ),
            handler=self._invoke_list_active,
        )

    def get_router(self) -> APIRouter:
        """Return the chat REST router."""
        router = APIRouter(prefix="/integrations/chat", tags=["Integration — Chat"])

        @router.post("/message", response_model=ChatMessageResponse)
        async def send_message(request: ChatMessageRequest) -> ChatMessageResponse:
            """Send a chat message via REST."""
            result = await self._invoke_send_message(request.model_dump())
            if result.success and result.data:
                return ChatMessageResponse(
                    conversation_id=result.data.get("conversation_id", ""),
                    message_id=result.data.get("message_id", ""),
                    reply=result.data.get("reply", ""),
                    is_ai_generated=result.data.get("is_ai_generated", True),
                    confidence=result.data.get("confidence", 0.0),
                )
            return ChatMessageResponse(
                conversation_id="", message_id="", reply="Error processing message"
            )

        return router

    async def _invoke_send_message(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle chat_send_message tool invocation via ExternalToolBus."""
        params = parameters or {}
        message = params.get("message", "")
        conversation_id = params.get("conversation_id", "")
        channel = params.get("channel", "chat_widget")
        customer_id = params.get("customer_id", "")
        company_id = params.get("company_id", "")
        variant = params.get("variant", "mini_parwa")

        logger.info(
            "chat_message_via_mcp",
            channel=channel,
            conversation_id=conversation_id,
            variant=variant,
            company_id=company_id,
            message_len=len(message),
        )

        if not message:
            return ToolInvokeResponse(
                success=False,
                tool_name="chat_send_message",
                error="Missing required parameter: message",
            )

        result = await external_tool_bus.send_chat(
            variant=variant,
            company_id=company_id,
            message=message,
            conversation_id=conversation_id,
            customer_id=customer_id,
            channel=channel,
        )

        return ToolInvokeResponse(
            success=result.success,
            tool_name="chat_send_message",
            data=result.to_dict() if result.success else None,
            error=result.error if not result.success else None,
            metadata={
                "channel": channel,
                "provider": result.provider,
                "variant": variant,
            },
        )

    async def _invoke_get_conversation(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle chat_get_conversation tool invocation."""
        params = parameters or {}
        conversation_id = params.get("conversation_id", "")
        company_id = params.get("company_id", "")
        limit = params.get("limit", 50)

        logger.info("chat_conversation_via_mcp", conversation_id=conversation_id)

        # Try backend
        try:
            import httpx
            import os

            backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000")
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{backend_url}/api/v1/chat/conversations/{conversation_id}",
                    params={"company_id": company_id, "limit": limit},
                )
                if resp.status_code == 200:
                    return ToolInvokeResponse(
                        success=True,
                        tool_name="chat_get_conversation",
                        data=resp.json(),
                    )
        except Exception as exc:
            logger.warning("chat_conversation_backend_failed", error=str(exc)[:200])

        return ToolInvokeResponse(
            success=True,
            tool_name="chat_get_conversation",
            data={
                "conversation_id": conversation_id,
                "messages": [],
                "total": 0,
                "message": "Conversation history not available",
            },
            metadata={"status": "fallback"},
        )

    async def _invoke_list_active(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle chat_list_active tool invocation."""
        params = parameters or {}
        company_id = params.get("company_id", "")
        status = params.get("status", "active")
        limit = params.get("limit", 20)

        logger.info("chat_list_active_via_mcp", company_id=company_id, status=status)

        try:
            import httpx
            import os

            backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000")
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{backend_url}/api/v1/chat/conversations",
                    params={"company_id": company_id, "status": status, "limit": limit},
                )
                if resp.status_code == 200:
                    return ToolInvokeResponse(
                        success=True,
                        tool_name="chat_list_active",
                        data=resp.json(),
                    )
        except Exception as exc:
            logger.warning("chat_list_backend_failed", error=str(exc)[:200])

        return ToolInvokeResponse(
            success=True,
            tool_name="chat_list_active",
            data={"conversations": [], "total": 0},
            metadata={"status": "fallback"},
        )


# Singleton instance
chat_server = ChatServer()
