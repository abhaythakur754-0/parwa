"""
PARWA Universal Provider Base Classes

Defines abstract base classes for all provider types.
Each provider type (Email, SMS, Voice, Chat) extends these base classes.

This design ensures PARWA is NOT locked into any specific provider.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ProviderType(str, Enum):
    """Type of provider service."""
    EMAIL = "email"
    SMS = "sms"
    VOICE = "voice"
    CHAT = "chat"
    HELPDESK = "helpdesk"
    CRM = "crm"
    ECOMMERCE = "ecommerce"
    PAYMENT = "payment"
    STORAGE = "storage"
    AI = "ai"


class ProviderCapability(str, Enum):
    """Capabilities that a provider may support."""
    # Email capabilities
    SEND_EMAIL = "send_email"
    SEND_TEMPLATE_EMAIL = "send_template_email"
    TRACK_OPENS = "track_opens"
    TRACK_CLICKS = "track_clicks"
    WEBHOOK_EVENTS = "webhook_events"
    
    # SMS capabilities
    SEND_SMS = "send_sms"
    RECEIVE_SMS = "receive_sms"
    SCHEDULE_SMS = "schedule_sms"
    SHORTCODE = "shortcode"
    ALPHANUMERIC_SENDER = "alphanumeric_sender"
    
    # Voice capabilities
    MAKE_CALL = "make_call"
    RECEIVE_CALL = "receive_call"
    VOICEMAIL = "voicemail"
    TRANSCRIPTION = "transcription"
    TEXT_TO_SPEECH = "text_to_speech"
    
    # Chat capabilities
    SEND_MESSAGE = "send_message"
    RECEIVE_MESSAGE = "receive_message"
    RICH_MESSAGES = "rich_messages"
    FILE_SHARING = "file_sharing"
    
    # General capabilities
    BATCH_OPERATIONS = "batch_operations"
    WEBHOOKS = "webhooks"
    ANALYTICS = "analytics"
    RATE_LIMITS = "rate_limits"


class ProviderStatus(str, Enum):
    """Health status of a provider connection."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    PENDING = "pending"
    TESTING = "testing"


@dataclass
class ProviderResult:
    """Result from a provider operation."""
    success: bool
    provider_name: str
    operation: str
    message_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "provider_name": self.provider_name,
            "operation": self.operation,
            "message_id": self.message_id,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class EmailMessage:
    """Email message data."""
    to: str
    subject: str
    html_content: str
    text_content: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    cc: List[str] = field(default_factory=list)
    bcc: List[str] = field(default_factory=list)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    template_id: Optional[str] = None
    template_variables: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class SMSMessage:
    """SMS message data."""
    to: str
    body: str
    from_number: Optional[str] = None
    media_urls: List[str] = field(default_factory=list)
    scheduled_at: Optional[datetime] = None
    status_callback: Optional[str] = None
    validity_period: Optional[int] = None  # seconds


@dataclass
class VoiceCall:
    """Voice call data."""
    to: str
    from_number: str
    url: Optional[str] = None  # TwiML URL
    application_sid: Optional[str] = None
    status_callback: Optional[str] = None
    status_callback_event: List[str] = field(default_factory=list)
    timeout: int = 30
    record: bool = False
    machine_detection: Optional[str] = None


@dataclass
class ChatMessage:
    """Chat message data."""
    channel: str
    channel_id: str
    text: str
    blocks: Optional[List[Dict]] = None
    attachments: Optional[List[Dict]] = None
    thread_ts: Optional[str] = None
    reply_to: Optional[str] = None


class BaseProvider(ABC):
    """Abstract base class for all providers.
    
    All provider implementations must extend this class and implement
    the required methods. This ensures consistency across all providers.
    """
    
    # Provider identification
    provider_type: ProviderType
    provider_name: str
    display_name: str
    description: str = ""
    website: str = ""
    
    # Configuration schema
    required_config_fields: List[str] = []
    optional_config_fields: List[str] = []
    
    # Capabilities
    capabilities: List[ProviderCapability] = []
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize provider with configuration.
        
        Args:
            config: Provider-specific configuration dict.
        """
        self.config = config
        self._status = ProviderStatus.PENDING
        self._last_error: Optional[str] = None
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate that all required config fields are present.
        
        Raises:
            ValueError: If required fields are missing.
        """
        missing = [
            field for field in self.required_config_fields
            if not self.config.get(field)
        ]
        if missing:
            raise ValueError(
                f"Missing required config fields for {self.provider_name}: "
                f"{', '.join(missing)}"
            )
    
    @property
    def status(self) -> ProviderStatus:
        """Get current provider status."""
        return self._status
    
    @property
    def last_error(self) -> Optional[str]:
        """Get last error message."""
        return self._last_error
    
    @abstractmethod
    def test_connection(self) -> ProviderResult:
        """Test the connection to the provider.
        
        Returns:
            ProviderResult with success status.
        """
        pass
    
    @abstractmethod
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get provider rate limits.
        
        Returns:
            Dict with rate limit information.
        """
        pass
    
    def supports(self, capability: ProviderCapability) -> bool:
        """Check if provider supports a capability.
        
        Args:
            capability: Capability to check.
            
        Returns:
            True if supported, False otherwise.
        """
        return capability in self.capabilities
    
    def mask_config(self) -> Dict[str, Any]:
        """Return config with sensitive values masked.
        
        Returns:
            Config dict with sensitive values masked.
        """
        sensitive_keys = {
            "api_key", "secret_key", "auth_token", "password",
            "secret", "token", "private_key", "access_token",
        }
        masked = {}
        for key, value in self.config.items():
            if any(s in key.lower() for s in sensitive_keys):
                if isinstance(value, str) and len(value) > 4:
                    masked[key] = value[:4] + "****"
                else:
                    masked[key] = "****"
            else:
                masked[key] = value
        return masked


class EmailProvider(BaseProvider):
    """Base class for email providers.
    
    Supports: Brevo, SendGrid, Mailgun, AWS SES, Postmark, etc.
    """
    
    provider_type = ProviderType.EMAIL
    capabilities = [
        ProviderCapability.SEND_EMAIL,
        ProviderCapability.WEBHOOKS,
    ]
    
    @abstractmethod
    def send_email(self, message: EmailMessage) -> ProviderResult:
        """Send an email.
        
        Args:
            message: EmailMessage with email details.
            
        Returns:
            ProviderResult with success status and message ID.
        """
        pass
    
    @abstractmethod
    def send_template_email(
        self,
        template_id: str,
        to: str,
        variables: Dict[str, Any],
    ) -> ProviderResult:
        """Send an email using a provider template.
        
        Args:
            template_id: Provider's template ID.
            to: Recipient email address.
            variables: Template variables.
            
        Returns:
            ProviderResult with success status.
        """
        pass
    
    def send_batch_emails(
        self,
        messages: List[EmailMessage],
    ) -> List[ProviderResult]:
        """Send multiple emails in batch.
        
        Default implementation sends individually.
        Override for providers with batch API.
        
        Args:
            messages: List of EmailMessage objects.
            
        Returns:
            List of ProviderResult objects.
        """
        if not self.supports(ProviderCapability.BATCH_OPERATIONS):
            return [self.send_email(msg) for msg in messages]
        
        # Override in subclasses for actual batch support
        return [self.send_email(msg) for msg in messages]


class SMSProvider(BaseProvider):
    """Base class for SMS providers.
    
    Supports: Twilio, MessageBird, Vonage, Plivo, Sinch, etc.
    """
    
    provider_type = ProviderType.SMS
    capabilities = [
        ProviderCapability.SEND_SMS,
        ProviderCapability.WEBHOOKS,
    ]
    
    @abstractmethod
    def send_sms(self, message: SMSMessage) -> ProviderResult:
        """Send an SMS.
        
        Args:
            message: SMSMessage with SMS details.
            
        Returns:
            ProviderResult with success status and message ID.
        """
        pass
    
    @abstractmethod
    def get_message_status(self, message_id: str) -> Dict[str, Any]:
        """Get delivery status of a message.
        
        Args:
            message_id: Provider's message ID.
            
        Returns:
            Dict with status information.
        """
        pass
    
    def send_batch_sms(
        self,
        messages: List[SMSMessage],
    ) -> List[ProviderResult]:
        """Send multiple SMS in batch.
        
        Default implementation sends individually.
        
        Args:
            messages: List of SMSMessage objects.
            
        Returns:
            List of ProviderResult objects.
        """
        return [self.send_sms(msg) for msg in messages]
    
    def parse_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse incoming SMS webhook data.
        
        Args:
            data: Webhook payload from provider.
            
        Returns:
            Normalized dict with: from, to, body, message_id, etc.
        """
        raise NotImplementedError("Subclass must implement parse_webhook")


class VoiceProvider(BaseProvider):
    """Base class for voice providers.
    
    Supports: Twilio Voice, Vonage Voice, Sinch Voice, etc.
    """
    
    provider_type = ProviderType.VOICE
    capabilities = [
        ProviderCapability.MAKE_CALL,
        ProviderCapability.WEBHOOKS,
    ]
    
    @abstractmethod
    def make_call(self, call: VoiceCall) -> ProviderResult:
        """Make an outbound voice call.
        
        Args:
            call: VoiceCall with call details.
            
        Returns:
            ProviderResult with success status and call ID.
        """
        pass
    
    @abstractmethod
    def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """Get status of a call.
        
        Args:
            call_id: Provider's call ID.
            
        Returns:
            Dict with call status information.
        """
        pass
    
    @abstractmethod
    def hangup_call(self, call_id: str) -> ProviderResult:
        """Hang up an ongoing call.
        
        Args:
            call_id: Provider's call ID.
            
        Returns:
            ProviderResult with success status.
        """
        pass


class ChatProvider(BaseProvider):
    """Base class for chat providers.
    
    Supports: Slack, Discord, Microsoft Teams, etc.
    """
    
    provider_type = ProviderType.CHAT
    capabilities = [
        ProviderCapability.SEND_MESSAGE,
        ProviderCapability.WEBHOOKS,
    ]
    
    @abstractmethod
    def send_message(self, message: ChatMessage) -> ProviderResult:
        """Send a chat message.
        
        Args:
            message: ChatMessage with message details.
            
        Returns:
            ProviderResult with success status.
        """
        pass
    
    @abstractmethod
    def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Get information about a channel.
        
        Args:
            channel_id: Channel identifier.
            
        Returns:
            Dict with channel information.
        """
        pass
