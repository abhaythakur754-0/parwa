"""
PARWA AI — Provider Abstraction Layer: Base Classes & Protocols

Defines the core enums, data models, and abstract base classes that every
provider adapter must implement.  All providers inherit from BaseProvider
and one of the category-specific subclasses (EmailProvider, SMSProvider,
PaymentProvider, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ProviderCategory(str, Enum):
    """High-level category a provider belongs to."""

    EMAIL = "email"
    SMS = "sms"
    PAYMENT = "payment"
    CRM = "crm"
    ECOMMERCE = "ecommerce"
    HELPDESK = "helpdesk"
    COMMUNICATION = "communication"
    CUSTOM = "custom"


class ConnectionStatus(str, Enum):
    """Runtime connection state for a provider instance."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class ProviderResult:
    """Standardised return type for every provider operation.

    Attributes:
        success: Whether the operation completed without errors.
        message: Human-readable summary (useful for UI display).
        data: Optional structured payload returned by the provider API.
    """

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = field(default=None)

    # Convenience helpers ---------------------------------------------------

    @classmethod
    def ok(cls, message: str = "Success", data: Optional[Dict[str, Any]] = None) -> "ProviderResult":
        """Create a successful result."""
        return cls(success=True, message=message, data=data)

    @classmethod
    def fail(cls, message: str = "Failed", data: Optional[Dict[str, Any]] = None) -> "ProviderResult":
        """Create a failure result."""
        return cls(success=False, message=message, data=data)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (safe for JSON responses)."""
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
        }


# ---------------------------------------------------------------------------
# Abstract base provider
# ---------------------------------------------------------------------------

class BaseProvider(ABC):
    """Every provider adapter **must** subclass this and implement all
    abstract methods.

    Class-level attributes:
        provider_name:     Human-readable name, e.g. "Brevo", "Twilio".
        provider_category: One of :class:`ProviderCategory`.
        provider_type:     Machine key used in the registry, e.g. "brevo",
                           "sendgrid", "twilio".
    """

    provider_name: str = ""
    provider_category: ProviderCategory = ProviderCategory.CUSTOM
    provider_type: str = ""

    # Connection state (set at runtime) -------------------------------------

    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    _credentials: Dict[str, Any] = {}

    # ----- Abstract methods ------------------------------------------------

    @abstractmethod
    async def test_connection(self, credentials: dict) -> ProviderResult:
        """Verify that the supplied credentials can reach the provider.

        Should set ``self.status`` to ``CONNECTED`` on success or ``ERROR``
        on failure.
        """

    @abstractmethod
    async def validate_credentials(self, credentials: dict) -> ProviderResult:
        """Validate credential dict structure *without* making a network call.

        Checks for the presence and basic format of required fields.
        """

    @abstractmethod
    def get_required_fields(self) -> List[Dict[str, Any]]:
        """Return a list of field specifications for the credential form.

        Each item is a dict with at least:
            ``name``     — field key used in the credentials dict
            ``type``     — one of "text", "password", "select", etc.
            ``label``    — human-readable label
            ``required`` — bool
        """

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Return a list of capability tokens this provider supports.

        Examples: ``"send_email"``, ``"templates"``, ``"webhooks"``.
        """

    # ----- Helpers ---------------------------------------------------------

    def set_credentials(self, credentials: Dict[str, Any]) -> None:
        """Store credentials for subsequent calls."""
        self._credentials = credentials

    def get_credentials(self) -> Dict[str, Any]:
        """Return the currently stored credentials."""
        return self._credentials

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<{self.__class__.__name__} "
            f"name={self.provider_name!r} "
            f"type={self.provider_type!r} "
            f"category={self.provider_category.value!r} "
            f"status={self.status.value!r}>"
        )


# ---------------------------------------------------------------------------
# Category-specific abstract providers
# ---------------------------------------------------------------------------

class EmailProvider(BaseProvider):
    """Base class for all e-mail providers (Brevo, SendGrid, SES, …)."""

    provider_category = ProviderCategory.EMAIL

    @abstractmethod
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        **kwargs: Any,
    ) -> ProviderResult:
        """Send an e-mail.

        Args:
            to:      Recipient e-mail address.
            subject: E-mail subject line.
            body:    HTML or plain-text body.
            **kwargs: Provider-specific options (cc, bcc, reply_to, from_name,
                      template_id, etc.).

        Returns:
            A :class:`ProviderResult` with ``data`` containing at minimum
            ``{"message_id": "..."}`` on success.
        """


class SMSProvider(BaseProvider):
    """Base class for all SMS providers (Twilio, Vonage, …)."""

    provider_category = ProviderCategory.SMS

    @abstractmethod
    async def send_sms(
        self,
        to: str,
        message: str,
        **kwargs: Any,
    ) -> ProviderResult:
        """Send an SMS message.

        Args:
            to:      Recipient phone number in E.164 format.
            message: SMS body text.
            **kwargs: Provider-specific options (from_number, media_urls, etc.).

        Returns:
            A :class:`ProviderResult` with ``data`` containing at minimum
            ``{"message_id": "..."}`` on success.
        """


class PaymentProvider(BaseProvider):
    """Base class for all payment providers (Stripe, Paddle, …)."""

    provider_category = ProviderCategory.PAYMENT

    @abstractmethod
    async def get_subscription(self, subscription_id: str) -> ProviderResult:
        """Retrieve a subscription by its provider-specific ID.

        Returns:
            A :class:`ProviderResult` whose ``data`` contains the normalised
            subscription payload on success.
        """
