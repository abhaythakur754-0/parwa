"""
PARWA MCP — Chat Server

Provides live chat messaging tools.
Supports multi-channel chat (widget, SMS, WhatsApp)
with AI-powered response generation.
"""

from __future__ import annotations

from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.models import (
    ChatMessageRequest,
    ChatMessageResponse,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.chat_server")


class ChatServer(MCPServerBase):
    """MCP sub-server for chat communication channels."""

    name = "chat_server"
    description = "Live chat messaging across channels (widget, web, mobile)"
    category = ToolCategory.INTEGRATION
    version = "1.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register chat tools."""
        registry.register_tool(
            ToolDefinition(
                name="chat_send_message",
                description="Send a chat message and receive an AI-generated response. "
                            "Supports multiple channels (chat_widget, web, mobile).",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "conversation_id": {
                            "type": "string",
                            "description": "Existing conversation ID (new if omitted)",
                        },
                        "message": {"type": "string"},
                        "channel": {
                            "type": "string",
                            "default": "chat_widget",
                        },
                        "customer_id": {"type": "string"},
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
                        "limit": {"type": "integer", "default": 50},
                    },
                    "required": ["conversation_id"],
                },
                tags=["chat", "history", "conversation"],
            ),
            handler=self._invoke_get_conversation,
        )

    def get_router(self) -> APIRouter:
        """Return the chat REST router."""
        router = APIRouter(prefix="/integrations/chat", tags=["Integration — Chat"])

        @router.post("/message", response_model=ChatMessageResponse)
        async def send_message(request: ChatMessageRequest) -> ChatMessageResponse:
            """Send a chat message via REST."""
            result = await self._invoke_send_message(request.model_dump())
            if result.success and result.data:
                return ChatMessageResponse(**result.data)
            return ChatMessageResponse(
                conversation_id="", message_id="", reply="Error processing message"
            )

        return router

    async def _invoke_send_message(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle chat_send_message tool invocation."""
        params = parameters or {}
        message = params.get("message", "")
        conversation_id = params.get("conversation_id")
        channel = params.get("channel", "chat_widget")

        logger.info(
            "chat_message_sent",
            channel=channel,
            conversation_id=conversation_id,
            message_len=len(message),
        )

        # Placeholder — connects to AI pipeline in production
        return ToolInvokeResponse(
            success=True,
            tool_name="chat_send_message",
            data={
                "conversation_id": conversation_id or f"conv_placeholder_{id(parameters) % 100000}",
                "message_id": f"msg_placeholder_{id(parameters) % 100000}",
                "reply": (
                    f"Thank you for your message. In production, this would be an "
                    f"AI-generated response based on the PARWA pipeline (Mini/Pro/High "
                    f"variant routing). Your message was: '{message[:100]}...'"
                ),
                "is_ai_generated": True,
                "confidence": 0.85,
            },
            metadata={
                "channel": channel,
                "ai_variant": "placeholder",
                "status": "placeholder",
            },
        )

    async def _invoke_get_conversation(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle chat_get_conversation tool invocation."""
        params = parameters or {}
        conversation_id = params.get("conversation_id", "")

        logger.info("chat_conversation_retrieved", conversation_id=conversation_id)

        return ToolInvokeResponse(
            success=True,
            tool_name="chat_get_conversation",
            data={
                "conversation_id": conversation_id,
                "messages": [
                    {
                        "id": "msg-1",
                        "role": "customer",
                        "content": "I need help with my order.",
                        "timestamp": "2025-01-15T10:00:00Z",
                    },
                    {
                        "id": "msg-2",
                        "role": "ai_agent",
                        "content": "I'd be happy to help with your order. Could you provide your order number?",
                        "timestamp": "2025-01-15T10:00:02Z",
                    },
                ],
            },
            metadata={"message_count": 2, "status": "placeholder"},
        )


# Singleton instance
chat_server = ChatServer()
