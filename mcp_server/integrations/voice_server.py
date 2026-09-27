"""
PARWA MCP — Voice Server

Provides voice call tools via Twilio integration.
Supports outbound calls, call status tracking, and TTS configuration.

CONNECTED to the real VoiceChannelService — no more placeholder SIDs.
When Jarvis says "call this customer", this server actually makes the call
via Twilio and returns the real CallSid.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

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


def _get_voice_service(company_id: str):
    """Get a VoiceChannelService instance connected to the DB.

    Returns:
        Tuple of (service, db_session) or (None, None) on failure.
    """
    try:
        from database.base import SessionLocal
        from app.services.voice_channel_service import VoiceChannelService

        db = SessionLocal()
        service = VoiceChannelService(db)
        return service, db
    except Exception as exc:
        logger.error("voice_service_init_failed", error=str(exc)[:200])
        return None, None


class VoiceServer(MCPServerBase):
    """MCP sub-server for voice/telephony integration (Twilio).

    Connected to the real VoiceChannelService so Jarvis can actually
    make calls. When a tool is invoked:
    1. Look up the company's voice channel config
    2. Call VoiceChannelService.initiate_outbound_call()
    3. Emit Socket.io event call:outgoing to the tenant room
    4. Return the real Twilio CallSid
    """

    name = "voice_server"
    description = "Voice call management via Twilio (outbound, status, IVR)"
    category = ToolCategory.INTEGRATION
    version = "2.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register voice tools."""
        registry.register_tool(
            ToolDefinition(
                name="voice_initiate_call",
                description="Initiate an outbound voice call to a phone number. "
                            "Supports TTS message and language configuration. "
                            "This is used by Jarvis when you say 'call this customer'.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Phone number (E.164 format, e.g. +919652852014)",
                        },
                        "from_number": {
                            "type": "string",
                            "description": "Caller ID number (optional, uses config default)",
                        },
                        "message": {
                            "type": "string",
                            "description": "Initial TTS message to play when call connects",
                        },
                        "language": {
                            "type": "string",
                            "default": "en-US",
                        },
                        "company_id": {
                            "type": "string",
                            "description": "Tenant company ID (required for multi-tenant isolation)",
                        },
                        "ticket_id": {
                            "type": "string",
                            "description": "Optional ticket ID to link the call to",
                        },
                    },
                    "required": ["to", "company_id"],
                },
                tags=["voice", "call", "twilio", "phone", "jarvis"],
            ),
            handler=self._invoke_initiate_call,
        )

        registry.register_tool(
            ToolDefinition(
                name="voice_get_call_status",
                description="Get the status of an existing voice call by Twilio CallSid.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "call_sid": {"type": "string", "description": "Twilio Call SID"},
                        "company_id": {
                            "type": "string",
                            "description": "Tenant company ID",
                        },
                    },
                    "required": ["call_sid", "company_id"],
                },
                tags=["voice", "status", "twilio"],
            ),
            handler=self._invoke_call_status,
        )

        registry.register_tool(
            ToolDefinition(
                name="voice_end_call",
                description="End an active voice call. Used by Jarvis to hang up a call.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "call_sid": {"type": "string", "description": "Twilio Call SID"},
                        "company_id": {
                            "type": "string",
                            "description": "Tenant company ID",
                        },
                    },
                    "required": ["call_sid", "company_id"],
                },
                tags=["voice", "end", "hangup", "twilio"],
            ),
            handler=self._invoke_end_call,
        )

        registry.register_tool(
            ToolDefinition(
                name="voice_list_active_calls",
                description="List currently active (in-progress, ringing, queued) calls for a tenant.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "company_id": {
                            "type": "string",
                            "description": "Tenant company ID",
                        },
                    },
                    "required": ["company_id"],
                },
                tags=["voice", "list", "active", "calls"],
            ),
            handler=self._invoke_list_active_calls,
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
        """Handle voice_initiate_call tool invocation.

        Wires directly to VoiceChannelService.initiate_outbound_call()
        and emits Socket.io call:outgoing event to the dashboard.
        """
        params = parameters or {}
        to = params.get("to", "")
        message = params.get("message", "")
        company_id = params.get("company_id", "")
        ticket_id = params.get("ticket_id")
        sender_role = params.get("sender_role", "bot")

        logger.info("voice_call_initiated_via_mcp", to=to, company_id=company_id, message_len=len(message))

        if not to:
            return ToolInvokeResponse(
                success=False,
                tool_name="voice_initiate_call",
                error="Missing required parameter: to (phone number)",
            )

        if not company_id:
            return ToolInvokeResponse(
                success=False,
                tool_name="voice_initiate_call",
                error="Missing required parameter: company_id",
            )

        service, db = _get_voice_service(company_id)
        if not service:
            return ToolInvokeResponse(
                success=False,
                tool_name="voice_initiate_call",
                error="Failed to initialize voice service — check DB connection",
            )

        try:
            result = service.initiate_outbound_call(
                company_id=company_id,
                to_number=to,
                variant_tier="parwa",
                message=message or None,
                sender_id="jarvis",
                sender_role=sender_role,
                ticket_id=ticket_id,
            )

            if result.get("status") == "error":
                return ToolInvokeResponse(
                    success=False,
                    tool_name="voice_initiate_call",
                    error=result.get("error", "Unknown error"),
                )

            # Emit Socket.io event to dashboard
            try:
                from app.core.socketio import emit_to_tenant
                asyncio.create_task(emit_to_tenant(
                    company_id=company_id,
                    event_type="call:outgoing",
                    payload={
                        "call_id": result.get("call_id"),
                        "twilio_call_sid": result.get("twilio_call_sid"),
                        "direction": "outbound",
                        "from_number": result.get("from_number"),
                        "to_number": result.get("to_number"),
                        "status": "queued",
                        "variant_tier": result.get("variant_tier"),
                        "sender_role": sender_role,
                        "message": message,
                    },
                ))
            except Exception as sio_exc:
                logger.warning("voice_socket_emit_failed", error=str(sio_exc)[:200])

            return ToolInvokeResponse(
                success=True,
                tool_name="voice_initiate_call",
                data={
                    "call_sid": result.get("twilio_call_sid", ""),
                    "call_id": result.get("call_id", ""),
                    "status": "initiated",
                    "to": to,
                    "from_number": result.get("from_number", ""),
                    "direction": "outbound",
                },
                metadata={"provider": "twilio", "source": "mcp_jarvis"},
            )
        except Exception as exc:
            logger.error("voice_call_mcp_error", error=str(exc)[:300])
            return ToolInvokeResponse(
                success=False,
                tool_name="voice_initiate_call",
                error=f"Call initiation failed: {str(exc)[:200]}",
            )
        finally:
            if db:
                db.close()

    async def _invoke_call_status(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle voice_get_call_status tool invocation."""
        params = parameters or {}
        call_sid = params.get("call_sid", "")
        company_id = params.get("company_id", "")

        logger.info("voice_call_status_via_mcp", call_sid=call_sid, company_id=company_id)

        if not call_sid or not company_id:
            return ToolInvokeResponse(
                success=False,
                tool_name="voice_get_call_status",
                error="Missing required parameters: call_sid and company_id",
            )

        service, db = _get_voice_service(company_id)
        if not service:
            return ToolInvokeResponse(
                success=False,
                tool_name="voice_get_call_status",
                error="Failed to initialize voice service",
            )

        try:
            from database.models.voice_channel import VoiceCall
            call = (
                db.query(VoiceCall)
                .filter(
                    VoiceCall.twilio_call_sid == call_sid,
                    VoiceCall.company_id == company_id,
                )
                .first()
            )

            if not call:
                return ToolInvokeResponse(
                    success=False,
                    tool_name="voice_get_call_status",
                    error=f"Call not found: {call_sid}",
                )

            return ToolInvokeResponse(
                success=True,
                tool_name="voice_get_call_status",
                data=call.to_dict(),
                metadata={"source": "mcp_jarvis"},
            )
        except Exception as exc:
            logger.error("voice_status_mcp_error", error=str(exc)[:200])
            return ToolInvokeResponse(
                success=False,
                tool_name="voice_get_call_status",
                error=f"Status lookup failed: {str(exc)[:200]}",
            )
        finally:
            if db:
                db.close()

    async def _invoke_end_call(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle voice_end_call tool invocation."""
        params = parameters or {}
        call_sid = params.get("call_sid", "")
        company_id = params.get("company_id", "")

        logger.info("voice_end_call_via_mcp", call_sid=call_sid, company_id=company_id)

        if not call_sid or not company_id:
            return ToolInvokeResponse(
                success=False,
                tool_name="voice_end_call",
                error="Missing required parameters: call_sid and company_id",
            )

        service, db = _get_voice_service(company_id)
        if not service:
            return ToolInvokeResponse(
                success=False,
                tool_name="voice_end_call",
                error="Failed to initialize voice service",
            )

        try:
            result = service.end_call(company_id, call_sid)

            if result.get("status") == "error":
                return ToolInvokeResponse(
                    success=False,
                    tool_name="voice_end_call",
                    error=result.get("error", "Unknown error"),
                )

            # Emit Socket.io event
            try:
                from app.core.socketio import emit_to_tenant
                asyncio.create_task(emit_to_tenant(
                    company_id=company_id,
                    event_type="call:ended",
                    payload={
                        "call_sid": call_sid,
                        "call_id": result.get("call_id"),
                        "status": "completed",
                        "ended_by": "jarvis",
                    },
                ))
            except Exception as sio_exc:
                logger.warning("voice_end_socket_emit_failed", error=str(sio_exc)[:200])

            return ToolInvokeResponse(
                success=True,
                tool_name="voice_end_call",
                data=result,
                metadata={"source": "mcp_jarvis"},
            )
        except Exception as exc:
            logger.error("voice_end_mcp_error", error=str(exc)[:200])
            return ToolInvokeResponse(
                success=False,
                tool_name="voice_end_call",
                error=f"End call failed: {str(exc)[:200]}",
            )
        finally:
            if db:
                db.close()

    async def _invoke_list_active_calls(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle voice_list_active_calls tool invocation."""
        params = parameters or {}
        company_id = params.get("company_id", "")

        if not company_id:
            return ToolInvokeResponse(
                success=False,
                tool_name="voice_list_active_calls",
                error="Missing required parameter: company_id",
            )

        service, db = _get_voice_service(company_id)
        if not service:
            return ToolInvokeResponse(
                success=False,
                tool_name="voice_list_active_calls",
                error="Failed to initialize voice service",
            )

        try:
            active_calls = []
            for status in ["queued", "ringing", "in-progress"]:
                result = service.list_calls(
                    company_id=company_id,
                    page=1,
                    page_size=50,
                    status=status,
                )
                active_calls.extend(result.get("items", []))

            return ToolInvokeResponse(
                success=True,
                tool_name="voice_list_active_calls",
                data={
                    "active_calls": active_calls,
                    "total": len(active_calls),
                },
                metadata={"source": "mcp_jarvis"},
            )
        except Exception as exc:
            logger.error("voice_list_active_mcp_error", error=str(exc)[:200])
            return ToolInvokeResponse(
                success=False,
                tool_name="voice_list_active_calls",
                error=f"List active calls failed: {str(exc)[:200]}",
            )
        finally:
            if db:
                db.close()


# Singleton instance
voice_server = VoiceServer()
