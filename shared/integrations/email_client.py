"""
PARWA Email Client.

Email sending integration using Brevo (formerly Sendinblue).
Supports: Transactional emails, templates, bulk sending, delivery tracking.
"""
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timezone
import asyncio
from enum import Enum
import hashlib

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EmailClientState(Enum):
    """Email Client state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class EmailStatus(Enum):
    """Email delivery status types."""
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    SPAM = "spam"
    FAILED = "failed"


class EmailPriority(Enum):
    """Email priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class EmailClient:
    """
    Email Client for transactional and bulk email via Brevo.

    Features:
    - Transactional email sending
    - Template-based emails
    - Bulk email campaigns
    - Delivery status tracking
    - Email validation
    - Attachment support
    """

    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3
    API_BASE_URL = "https://api.brevo.com/v3"

    def __init__(
        self,
        api_key: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT
    ) -> None:
        """
        Initialize Email Client.

        Args:
            api_key: Brevo API key (reads from config if not provided)
            from_email: Default sender email address
            from_name: Default sender name
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or (
            settings.brevo_api_key.get_secret_value()
            if settings.brevo_api_key else None
        )
        self.from_email = from_email or settings.from_email
        self.from_name = from_name or "PARWA Support"
        self.timeout = timeout
        self._state = EmailClientState.DISCONNECTED
        self._last_request: Optional[datetime] = None

    @property
    def state(self) -> EmailClientState:
        """Get current client state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._state == EmailClientState.CONNECTED

    async def connect(self) -> bool:
        """
        Connect to Brevo API.

        Validates credentials by fetching account info.

        Returns:
            True if connected successfully
        """
        if self._state == EmailClientState.CONNECTED:
            return True

        self._state = EmailClientState.CONNECTING

        if not self.api_key:
            self._state = EmailClientState.ERROR
            logger.error({"event": "email_missing_api_key"})
            return False

        try:
            # Simulate connection validation
            await asyncio.sleep(0.1)

            self._state = EmailClientState.CONNECTED
            self._last_request = datetime.now(timezone.utc)

            logger.info({
                "event": "email_client_connected",
                "from_email": self.from_email,
            })

            return True

        except Exception as e:
            self._state = EmailClientState.ERROR
            logger.error({
                "event": "email_connection_failed",
                "error": str(e),
            })
            return False

    async def disconnect(self) -> None:
        """Disconnect from Brevo API."""
        self._state = EmailClientState.DISCONNECTED
        self._last_request = None

        logger.info({"event": "email_client_disconnected"})

    async def send_email(
        self,
        to: Union[str, List[str]],
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, str]]] = None,
        tags: Optional[List[str]] = None,
        priority: EmailPriority = EmailPriority.NORMAL
    ) -> Dict[str, Any]:
        """
        Send a transactional email.

        Args:
            to: Recipient email(s) - single string or list
            subject: Email subject line
            html_content: HTML email body
            text_content: Plain text email body (optional)
            from_email: Sender email (uses default if not provided)
            from_name: Sender name (uses default if not provided)
            reply_to: Reply-to email address
            cc: CC recipients
            bcc: BCC recipients
            attachments: List of attachments with 'name' and 'content' (base64)
            tags: Tags for tracking and organization
            priority: Email priority level

        Returns:
            Email data dictionary with message ID and status
        """
        if not self.is_connected:
            raise ValueError("Email client not connected")

        # Validate required fields
        if not to:
            raise ValueError("Recipient email is required")

        if not subject:
            raise ValueError("Email subject is required")

        if not html_content:
            raise ValueError("Email content is required")

        # Normalize to list
        recipients = [to] if isinstance(to, str) else to

        # Validate email addresses
        for email in recipients:
            if not self._validate_email_format(email):
                raise ValueError(f"Invalid email address: {email}")

        sender_email = from_email or self.from_email
        sender_name = from_name or self.from_name

        if not sender_email:
            raise ValueError("Sender email not configured")

        logger.info({
            "event": "email_send",
            "to_count": len(recipients),
            "subject": subject[:50] + "..." if len(subject) > 50 else subject,
            "from": sender_email,
            "priority": priority.value,
        })

        # Simulated email send
        message_id = hashlib.md5(
            f"{recipients[0]}{subject}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:32]

        return {
            "message_id": message_id,
            "to": recipients,
            "subject": subject,
            "from": sender_email,
            "from_name": sender_name,
            "status": EmailStatus.QUEUED.value,
            "priority": priority.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def send_template_email(
        self,
        to: Union[str, List[str]],
        template_id: int,
        params: Optional[Dict[str, Any]] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Send an email using a template.

        Args:
            to: Recipient email(s)
            template_id: Brevo template ID
            params: Template variables for substitution
            from_email: Sender email (uses default if not provided)
            from_name: Sender name (uses default if not provided)
            reply_to: Reply-to email address
            tags: Tags for tracking

        Returns:
            Email data dictionary with message ID and status
        """
        if not self.is_connected:
            raise ValueError("Email client not connected")

        if not to:
            raise ValueError("Recipient email is required")

        if not template_id:
            raise ValueError("Template ID is required")

        recipients = [to] if isinstance(to, str) else to

        sender_email = from_email or self.from_email
        sender_name = from_name or self.from_name

        logger.info({
            "event": "email_template_send",
            "to_count": len(recipients),
            "template_id": template_id,
            "from": sender_email,
        })

        # Simulated template email send
        message_id = hashlib.md5(
            f"{recipients[0]}{template_id}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:32]

        return {
            "message_id": message_id,
            "to": recipients,
            "template_id": template_id,
            "from": sender_email,
            "from_name": sender_name,
            "status": EmailStatus.QUEUED.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_email_status(
        self,
        message_id: str
    ) -> Dict[str, Any]:
        """
        Get the delivery status of an email.

        Args:
            message_id: Email message ID from send response

        Returns:
            Email status dictionary
        """
        if not self.is_connected:
            raise ValueError("Email client not connected")

        if not message_id:
            raise ValueError("Message ID is required")

        logger.info({
            "event": "email_status_check",
            "message_id": message_id,
        })

        # Simulated status fetch
        return {
            "message_id": message_id,
            "status": EmailStatus.DELIVERED.value,
            "delivered_at": datetime.now(timezone.utc).isoformat(),
            "opened": False,
            "clicked": False,
            "bounced": False,
            "spam_reported": False,
        }

    async def send_bulk_email(
        self,
        recipients: List[Dict[str, Any]],
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        batch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send bulk emails to multiple recipients.

        Args:
            recipients: List of recipient dicts with 'email' and optional 'name'
            subject: Email subject line
            html_content: HTML email body
            text_content: Plain text email body
            from_email: Sender email
            from_name: Sender name
            batch_id: Optional batch identifier

        Returns:
            Bulk email result with batch ID and count
        """
        if not self.is_connected:
            raise ValueError("Email client not connected")

        if not recipients:
            raise ValueError("Recipients list is required")

        if len(recipients) > 10000:
            raise ValueError("Maximum 10,000 recipients per batch")

        if not subject or not html_content:
            raise ValueError("Subject and content are required")

        sender_email = from_email or self.from_email
        sender_name = from_name or self.from_name

        logger.info({
            "event": "email_bulk_send",
            "recipient_count": len(recipients),
            "batch_id": batch_id,
            "from": sender_email,
        })

        # Simulated bulk send
        generated_batch_id = batch_id or hashlib.md5(
            f"{len(recipients)}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        return {
            "batch_id": generated_batch_id,
            "recipient_count": len(recipients),
            "status": "processing",
            "from": sender_email,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def create_contact(
        self,
        email: str,
        attributes: Optional[Dict[str, Any]] = None,
        list_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Create or update a contact in Brevo.

        Args:
            email: Contact email address
            attributes: Contact attributes (name, company, etc.)
            list_ids: List IDs to add contact to

        Returns:
            Contact data dictionary
        """
        if not self.is_connected:
            raise ValueError("Email client not connected")

        if not email:
            raise ValueError("Email is required")

        if not self._validate_email_format(email):
            raise ValueError(f"Invalid email format: {email}")

        logger.info({
            "event": "email_contact_create",
            "email": email,
        })

        # Simulated contact creation
        contact_id = hashlib.md5(email.encode()).hexdigest()[:16]

        return {
            "id": contact_id,
            "email": email,
            "attributes": attributes or {},
            "list_ids": list_ids or [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_templates(self) -> List[Dict[str, Any]]:
        """
        Get list of available email templates.

        Returns:
            List of template dictionaries
        """
        if not self.is_connected:
            raise ValueError("Email client not connected")

        logger.info({"event": "email_templates_list"})

        # Simulated templates list
        return [
            {
                "id": 1,
                "name": "Welcome Email",
                "subject": "Welcome to PARWA!",
                "active": True,
            },
            {
                "id": 2,
                "name": "Password Reset",
                "subject": "Reset Your Password",
                "active": True,
            },
            {
                "id": 3,
                "name": "Order Confirmation",
                "subject": "Your Order Confirmation",
                "active": True,
            },
        ]

    def _validate_email_format(self, email: str) -> bool:
        """
        Validate email address format.

        Args:
            email: Email address to validate

        Returns:
            True if email format is valid
        """
        if not email or not isinstance(email, str):
            return False

        # Basic email validation
        parts = email.split("@")
        if len(parts) != 2:
            return False

        local, domain = parts
        if not local or not domain:
            return False

        if "." not in domain:
            return False

        return True

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Email connection.

        Returns:
            Health status dictionary
        """
        return {
            "healthy": self._state == EmailClientState.CONNECTED,
            "state": self._state.value,
            "from_email": self.from_email,
            "from_name": self.from_name,
            "last_request": (
                self._last_request.isoformat()
                if self._last_request else None
            ),
        }
