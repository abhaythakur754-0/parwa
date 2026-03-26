"""
PARWA Voice MCP Server.

MCP server for voice/SMS operations via Twilio integration.
Wraps the TwilioClient and exposes it as MCP tools.
"""
from typing import Dict, Any
import asyncio

from mcp_servers.base_server import BaseMCPServer
from shared.integrations.twilio_client import TwilioClient
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class VoiceServer(BaseMCPServer):
    """
    MCP Server for voice and SMS operations.

    Tools provided:
    - make_call: Initiate an automated voice call
    - send_sms: Send an SMS message
    - get_call_status: Get status of a voice call
    - validate_phone_number: Validate a phone number

    This server wraps the TwilioClient and exposes its functionality
    through the MCP protocol.
    """

    def __init__(
        self,
        config: Dict[str, Any] = None,
        twilio_client: TwilioClient = None
    ) -> None:
        """
        Initialize Voice MCP Server.

        Args:
            config: Server configuration
            twilio_client: Optional TwilioClient instance (created if not provided)
        """
        self._twilio_client = twilio_client or TwilioClient()
        super().__init__(name="voice_server", config=config)

    def _register_tools(self) -> None:
        """Register all voice/SMS tools."""
        # Tool: make_call
        self.register_tool(
            name="make_call",
            description=(
                "Initiate an automated voice call to a phone number. "
                "The call will deliver a message using text-to-speech."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient phone number in E.164 format (+1234567890)",
                    },
                    "message": {
                        "type": "string",
                        "description": "Message to deliver via text-to-speech",
                    },
                    "voice": {
                        "type": "string",
                        "description": "Voice to use (default, male, female)",
                        "default": "default",
                    },
                },
                "required": ["to", "message"],
            },
            handler=self._handle_make_call,
        )

        # Tool: send_sms
        self.register_tool(
            name="send_sms",
            description=(
                "Send an SMS message to a phone number. "
                "Maximum message length is 1600 characters."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient phone number in E.164 format (+1234567890)",
                    },
                    "message": {
                        "type": "string",
                        "description": "SMS message content (max 1600 chars)",
                    },
                },
                "required": ["to", "message"],
            },
            handler=self._handle_send_sms,
        )

        # Tool: get_call_status
        self.register_tool(
            name="get_call_status",
            description="Get the status and details of a voice call.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "call_id": {
                        "type": "string",
                        "description": "Call SID from make_call response",
                    },
                },
                "required": ["call_id"],
            },
            handler=self._handle_get_call_status,
        )

        # Tool: validate_phone_number
        self.register_tool(
            name="validate_phone_number",
            description=(
                "Validate a phone number and get carrier information. "
                "Use before making calls or sending SMS."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": "Phone number to validate",
                    },
                },
                "required": ["phone"],
            },
            handler=self._handle_validate_phone_number,
        )

    async def _on_start(self) -> None:
        """Connect to Twilio service on startup."""
        if not self._twilio_client.is_connected:
            success = await self._twilio_client.connect()
            if not success:
                raise RuntimeError("Failed to connect to Twilio service")

    async def _on_stop(self) -> None:
        """Disconnect from Twilio service on shutdown."""
        await self._twilio_client.disconnect()

    async def _handle_make_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle make_call tool call.

        Args:
            params: Tool parameters with to, message, voice (optional)

        Returns:
            Call initiation result with call_sid and status
        """
        to = params.get("to")
        message = params.get("message")
        voice = params.get("voice", "default")

        try:
            # Generate TwiML URL for the message
            # In production, this would be a hosted TwiML endpoint
            twiml_url = f"twiml://say?message={message}&voice={voice}"

            result = await self._twilio_client.make_call(
                to=to,
                url=twiml_url,
            )

            return {
                "call_sid": result.get("sid"),
                "to": result.get("to"),
                "from": result.get("from"),
                "status": result.get("status"),
                "message": message,
                "voice": voice,
            }

        except ValueError as e:
            logger.error({
                "event": "call_validation_error",
                "error": str(e),
            })
            return {"status": "error", "message": str(e)}

        except Exception as e:
            logger.error({
                "event": "call_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to initiate call"}

    async def _handle_send_sms(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle send_sms tool call.

        Args:
            params: Tool parameters with to, message

        Returns:
            SMS send result with message_sid and status
        """
        to = params.get("to")
        message = params.get("message")

        try:
            result = await self._twilio_client.send_sms(
                to=to,
                body=message,
            )

            return {
                "message_sid": result.get("sid"),
                "to": result.get("to"),
                "from": result.get("from"),
                "status": result.get("status"),
                "segments": result.get("num_segments"),
            }

        except ValueError as e:
            logger.error({
                "event": "sms_validation_error",
                "error": str(e),
            })
            return {"status": "error", "message": str(e)}

        except Exception as e:
            logger.error({
                "event": "sms_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to send SMS"}

    async def _handle_get_call_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_call_status tool call.

        Args:
            params: Tool parameters with call_id

        Returns:
            Call status and details
        """
        call_id = params.get("call_id")

        try:
            result = await self._twilio_client.get_call_status(call_id)

            return {
                "call_sid": result.get("sid"),
                "status": result.get("status"),
                "duration": result.get("duration"),
                "error_code": result.get("error_code"),
                "error_message": result.get("error_message"),
            }

        except ValueError as e:
            logger.error({
                "event": "call_status_validation_error",
                "error": str(e),
            })
            return {"status": "error", "message": str(e)}

        except Exception as e:
            logger.error({
                "event": "call_status_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to get call status"}

    async def _handle_validate_phone_number(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle validate_phone_number tool call.

        Args:
            params: Tool parameters with phone

        Returns:
            Phone number validation result with carrier info
        """
        phone = params.get("phone")

        try:
            result = await self._twilio_client.validate_phone_number(phone)

            return {
                "phone_number": result.get("phone_number"),
                "valid": result.get("valid"),
                "carrier": result.get("carrier"),
                "line_type": result.get("line_type"),
                "country_code": result.get("country_code"),
            }

        except ValueError as e:
            logger.error({
                "event": "phone_validation_error",
                "error": str(e),
            })
            return {"status": "error", "message": str(e)}

        except Exception as e:
            logger.error({
                "event": "phone_validation_service_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to validate phone number"}
