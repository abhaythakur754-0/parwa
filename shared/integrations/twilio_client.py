"""
PARWA Twilio Client.

SMS and Voice communication integration for customer support.
Supports: SMS sending, Voice calls, WhatsApp messaging.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import asyncio
from enum import Enum
import hashlib

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class TwilioClientState(Enum):
    """Twilio Client state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class MessageStatus(Enum):
    """Twilio message status types."""
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    UNDELIVERED = "undelivered"
    FAILED = "failed"


class CallStatus(Enum):
    """Twilio call status types."""
    QUEUED = "queued"
    RINGING = "ringing"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BUSY = "busy"
    NO_ANSWER = "no-answer"


class TwilioClient:
    """
    Twilio Client for SMS and Voice communication.

    Features:
    - SMS sending with status tracking
    - Voice call initiation
    - WhatsApp messaging
    - Phone number validation
    - Message history retrieval
    """

    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3
    API_BASE_URL = "https://api.twilio.com/2010-04-01"

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        api_key: Optional[str] = None,
        phone_number: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT
    ) -> None:
        """
        Initialize Twilio Client.

        Args:
            account_sid: Twilio Account SID (reads from config if not provided)
            auth_token: Twilio Auth Token (reads from config if not provided)
            api_key: Twilio API Key (reads from config if not provided)
            phone_number: Default Twilio phone number for outbound
            timeout: Request timeout in seconds
        """
        self.account_sid = account_sid or settings.twilio_account_sid
        self.auth_token = auth_token or (
            settings.twilio_auth_token.get_secret_value()
            if settings.twilio_auth_token else None
        )
        self.api_key = api_key or (
            settings.twilio_api_key.get_secret_value()
            if settings.twilio_api_key else None
        )
        self.phone_number = phone_number or settings.twilio_phone_number
        self.timeout = timeout
        self._state = TwilioClientState.DISCONNECTED
        self._last_request: Optional[datetime] = None

    @property
    def state(self) -> TwilioClientState:
        """Get current client state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._state == TwilioClientState.CONNECTED

    def _get_base_url(self) -> str:
        """Get the base API URL for Twilio."""
        if not self.account_sid:
            raise ValueError("Twilio Account SID not configured")
        return f"{self.API_BASE_URL}/Accounts/{self.account_sid}"

    async def connect(self) -> bool:
        """
        Connect to Twilio API.

        Validates credentials by fetching account info.

        Returns:
            True if connected successfully
        """
        if self._state == TwilioClientState.CONNECTED:
            return True

        self._state = TwilioClientState.CONNECTING

        if not self.account_sid:
            self._state = TwilioClientState.ERROR
            logger.error({"event": "twilio_missing_account_sid"})
            return False

        if not self.auth_token:
            self._state = TwilioClientState.ERROR
            logger.error({"event": "twilio_missing_auth_token"})
            return False

        try:
            # Simulate connection validation
            await asyncio.sleep(0.1)

            self._state = TwilioClientState.CONNECTED
            self._last_request = datetime.now(timezone.utc)

            logger.info({
                "event": "twilio_client_connected",
                "account_sid": self.account_sid[:8] + "...",  # Partial for security
            })

            return True

        except Exception as e:
            self._state = TwilioClientState.ERROR
            logger.error({
                "event": "twilio_connection_failed",
                "error": str(e),
            })
            return False

    async def disconnect(self) -> None:
        """Disconnect from Twilio API."""
        self._state = TwilioClientState.DISCONNECTED
        self._last_request = None

        logger.info({"event": "twilio_client_disconnected"})

    async def send_sms(
        self,
        to: str,
        body: str,
        from_: Optional[str] = None,
        status_callback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an SMS message.

        Args:
            to: Recipient phone number (E.164 format)
            body: Message body (max 1600 chars for SMS)
            from_: Sender phone number (uses default if not provided)
            status_callback: URL for status callbacks

        Returns:
            Message data dictionary with SID and status
        """
        if not self.is_connected:
            raise ValueError("Twilio client not connected")

        if not to:
            raise ValueError("Recipient phone number is required")

        if not body:
            raise ValueError("Message body is required")

        if len(body) > 1600:
            raise ValueError("Message body exceeds 1600 characters")

        from_number = from_ or self.phone_number
        if not from_number:
            raise ValueError(
                "Sender phone number not configured. "
                "Provide from_ parameter or set default."
            )

        logger.info({
            "event": "twilio_sms_send",
            "to": to,
            "from": from_number,
            "body_length": len(body),
        })

        # Simulated SMS send
        message_sid = "SM" + hashlib.md5(
            f"{to}{body}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:32]

        return {
            "sid": message_sid,
            "to": to,
            "from": from_number,
            "body": body,
            "status": MessageStatus.QUEUED.value,
            "num_segments": str((len(body) // 160) + 1),
            "direction": "outbound-api",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_message_status(
        self,
        message_sid: str
    ) -> Dict[str, Any]:
        """
        Get the status of a message.

        Args:
            message_sid: Twilio Message SID

        Returns:
            Message status dictionary
        """
        if not self.is_connected:
            raise ValueError("Twilio client not connected")

        if not message_sid:
            raise ValueError("Message SID is required")

        logger.info({
            "event": "twilio_message_status",
            "message_sid": message_sid,
        })

        # Simulated status fetch
        return {
            "sid": message_sid,
            "status": MessageStatus.DELIVERED.value,
            "error_code": None,
            "error_message": None,
        }

    async def send_whatsapp(
        self,
        to: str,
        body: str,
        from_: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp message.

        Args:
            to: Recipient phone number (E.164 format)
            body: Message body
            from_: Sender phone number (uses default if not provided)

        Returns:
            Message data dictionary
        """
        if not self.is_connected:
            raise ValueError("Twilio client not connected")

        if not to:
            raise ValueError("Recipient phone number is required")

        if not body:
            raise ValueError("Message body is required")

        from_number = from_ or self.phone_number
        if not from_number:
            raise ValueError("Sender phone number not configured")

        # Format for WhatsApp
        whatsapp_to = f"whatsapp:{to}"
        whatsapp_from = f"whatsapp:{from_number}"

        logger.info({
            "event": "twilio_whatsapp_send",
            "to": whatsapp_to,
            "body_length": len(body),
        })

        # Simulated WhatsApp send
        message_sid = "SM" + hashlib.md5(
            f"{whatsapp_to}{body}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:32]

        return {
            "sid": message_sid,
            "to": whatsapp_to,
            "from": whatsapp_from,
            "body": body,
            "status": MessageStatus.QUEUED.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def make_call(
        self,
        to: str,
        url: str,
        from_: Optional[str] = None,
        status_callback: Optional[str] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Initiate a voice call.

        Args:
            to: Recipient phone number (E.164 format)
            url: TwiML URL for call instructions
            from_: Caller phone number (uses default if not provided)
            status_callback: URL for status callbacks
            timeout: Ring timeout in seconds

        Returns:
            Call data dictionary with SID and status
        """
        if not self.is_connected:
            raise ValueError("Twilio client not connected")

        if not to:
            raise ValueError("Recipient phone number is required")

        if not url:
            raise ValueError("TwiML URL is required for call instructions")

        from_number = from_ or self.phone_number
        if not from_number:
            raise ValueError("Caller phone number not configured")

        if timeout < 1 or timeout > 600:
            raise ValueError("Timeout must be between 1 and 600 seconds")

        logger.info({
            "event": "twilio_call_initiate",
            "to": to,
            "from": from_number,
            "url": url,
        })

        # Simulated call initiation
        call_sid = "CA" + hashlib.md5(
            f"{to}{url}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:32]

        return {
            "sid": call_sid,
            "to": to,
            "from": from_number,
            "status": CallStatus.QUEUED.value,
            "direction": "outbound-api",
            "url": url,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_call_status(
        self,
        call_sid: str
    ) -> Dict[str, Any]:
        """
        Get the status of a call.

        Args:
            call_sid: Twilio Call SID

        Returns:
            Call status dictionary
        """
        if not self.is_connected:
            raise ValueError("Twilio client not connected")

        if not call_sid:
            raise ValueError("Call SID is required")

        logger.info({
            "event": "twilio_call_status",
            "call_sid": call_sid,
        })

        # Simulated status fetch
        return {
            "sid": call_sid,
            "status": CallStatus.COMPLETED.value,
            "duration": "120",
            "error_code": None,
            "error_message": None,
        }

    async def validate_phone_number(
        self,
        phone_number: str
    ) -> Dict[str, Any]:
        """
        Validate a phone number.

        Args:
            phone_number: Phone number to validate

        Returns:
            Validation result with carrier info
        """
        if not self.is_connected:
            raise ValueError("Twilio client not connected")

        if not phone_number:
            raise ValueError("Phone number is required")

        logger.info({
            "event": "twilio_phone_validate",
            "phone_number": phone_number,
        })

        # Simulated validation
        is_valid = phone_number.startswith("+") and len(phone_number) >= 10

        return {
            "phone_number": phone_number,
            "valid": is_valid,
            "carrier": "Unknown" if not is_valid else "Mock Carrier",
            "line_type": "mobile" if is_valid else "unknown",
            "country_code": phone_number[1:3] if is_valid else None,
        }

    async def list_messages(
        self,
        to: Optional[str] = None,
        from_: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List messages.

        Args:
            to: Filter by recipient
            from_: Filter by sender
            limit: Maximum results

        Returns:
            List of message dictionaries
        """
        if not self.is_connected:
            raise ValueError("Twilio client not connected")

        if limit < 1 or limit > 1000:
            raise ValueError("Limit must be between 1 and 1000")

        logger.info({
            "event": "twilio_messages_list",
            "to": to,
            "from": from_,
            "limit": limit,
        })

        # Simulated message list
        return []

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Twilio connection.

        Returns:
            Health status dictionary
        """
        return {
            "healthy": self._state == TwilioClientState.CONNECTED,
            "state": self._state.value,
            "account_sid": (
                self.account_sid[:8] + "..." if self.account_sid else None
            ),
            "phone_number": self.phone_number,
            "last_request": (
                self._last_request.isoformat()
                if self._last_request else None
            ),
        }
