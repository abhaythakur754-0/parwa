"""
PARWA MCP — Voice Server

Provides voice call tools via Twilio integration.
Supports outbound calls, call status tracking, and TTS configuration.
"""

from __future__ import annotations

from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.models import (
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
    VoiceCallRequest,
    VoiceCallResponse,
)

logger = get_logger("mcp.voice_server")


class VoiceServer(MCPServerBase):
    """MCP sub-server for voice/telephony integration (Twilio)."""

    name = "voice_server"
    description = "Voice call management via Twilio (outbound, status, IVR)"
    category = ToolCategory.INTEGRATION
    version = "1.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register voice tools."""
        registry.register_tool(
            ToolDefinition(
                name="voice_initiate_call",
                description="Initiate an outbound voice call to a phone number. "
                            "Supports TTS message and language configuration.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Phone number (E.164 format)",
                        },
                        "from_number": {
                            "type": "string",
                            "description": "Caller ID number",
                        },
                        "message": {
                            "type": "string",
                            "description": "Initial TTS message to play",
                        },
                        "language": {
                            "type": "string",
                            "default": "en-US",
                        },
                        "webhook_url": {
                            "type": "string",
                            "description": "Status callback URL",
                        },
                    },
                    "required": ["to"],
                },
                tags=["voice", "call", "twilio", "phone"],
            ),
            handler=self._invoke_initiate_call,
        )

        registry.register_tool(
            ToolDefinition(
                name="voice_get_call_status",
                description="Get the status of an existing voice call.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "call_sid": {"type": "string", "description": "Twilio Call SID"},
                    },
                    "required": ["call_sid"],
                },
                tags=["voice", "status", "twilio"],
            ),
            handler=self._invoke_call_status,
        )

    def get_router(self) -> APIRouter:
        """Return the voice REST router."""
        router = APIRouter(prefix="/integrations/voice", tags=["Integration — Voice"])

        @router.post("/call", response_model=VoiceCallResponse)
        async def initiate_call(request: VoiceCallRequest) -> VoiceCallResponse:
            """Initiate an outbound call via REST."""
            result = await self._invoke_initiate_call(request.model_dump())
            if result.success and result.data:
                return VoiceCallResponse(**result.data)
            return VoiceCallResponse(call_sid="", status="failed", to=request.to)

        return router

    async def _invoke_initiate_call(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle voice_initiate_call tool invocation."""
        params = parameters or {}
        to = params.get("to", "")
        message = params.get("message", "")

        logger.info("voice_call_initiated", to=to, message_len=len(message))

        # Placeholder — connects to Twilio in production
        return ToolInvokeResponse(
            success=True,
            tool_name="voice_initiate_call",
            data={
                "call_sid": f"CA_placeholder_{id(parameters) % 100000}",
                "status": "initiated",
                "to": to,
            },
            metadata={"provider": "twilio", "status": "placeholder"},
        )

    async def _invoke_call_status(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle voice_get_call_status tool invocation."""
        params = parameters or {}
        call_sid = params.get("call_sid", "")

        logger.info("voice_call_status", call_sid=call_sid)

        return ToolInvokeResponse(
            success=True,
            tool_name="voice_get_call_status",
            data={
                "call_sid": call_sid,
                "status": "completed",
                "duration": "0:42",
                "direction": "outbound-api",
            },
            metadata={"status": "placeholder"},
        )


# Singleton instance
voice_server = VoiceServer()
