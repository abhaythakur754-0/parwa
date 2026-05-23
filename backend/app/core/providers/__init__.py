"""
PARWA AI — Provider Abstraction Layer

This package provides a provider-agnostic integration architecture for
connecting to external services (email, SMS, payment, CRM, …).

Usage::

    from app.core.providers import ProviderRegistry, ProviderFactory, ApiKeyDetector
    from app.core.providers import BrevoProvider, TwilioProvider, StripeProvider

    # All adapters are auto-registered on import.
    provider_cls = ProviderRegistry.get("email", "brevo")

    # Create an instance with credentials
    provider = await ProviderFactory.create_with_credentials(
        provider_type="brevo",
        category="email",
        credentials={"api_key": "xkeysib-..."},
    )
    result = await provider.send_email(to="user@example.com", subject="Hi", body="<p>Hello</p>")
"""

from .base import (
    BaseProvider,
    ConnectionStatus,
    EmailProvider,
    PaymentProvider,
    ProviderCategory,
    ProviderResult,
    SMSProvider,
)
from .registry import ProviderFactory, ProviderRegistry
from .api_key_detector import ApiKeyDetector, PROVIDER_KEY_PATTERNS

# Provider adapters — imported so they register themselves
from .email_brevo import BrevoProvider
from .email_sendgrid import SendGridProvider
from .email_ses import SESEmailProvider
from .email_mailgun import MailgunProvider
from .email_postmark import PostmarkProvider
from .sms_twilio import TwilioProvider
from .sms_vonage import VonageProvider
from .payment_paddle import PaddleProvider
from .payment_stripe import StripeProvider


# ---------------------------------------------------------------------------
# Auto-registration
# ---------------------------------------------------------------------------

def _auto_register() -> None:
    """Register all imported provider adapters with the ProviderRegistry."""
    adapters: list[tuple[str, str, type[BaseProvider]]] = [
        # Email
        ("email", "brevo", BrevoProvider),
        ("email", "sendgrid", SendGridProvider),
        ("email", "aws_ses", SESEmailProvider),
        ("email", "mailgun", MailgunProvider),
        ("email", "postmark", PostmarkProvider),
        # SMS
        ("sms", "twilio", TwilioProvider),
        ("sms", "vonage", VonageProvider),
        # Payment
        ("payment", "paddle", PaddleProvider),
        ("payment", "stripe", StripeProvider),
    ]

    for category, provider_type, provider_cls in adapters:
        ProviderRegistry.register(category, provider_type, provider_cls)


_auto_register()


# ---------------------------------------------------------------------------
# Public API — explicit re-exports
# ---------------------------------------------------------------------------

__all__ = [
    # Base classes & enums
    "BaseProvider",
    "EmailProvider",
    "SMSProvider",
    "PaymentProvider",
    "ProviderCategory",
    "ConnectionStatus",
    "ProviderResult",
    # Registry & Factory
    "ProviderRegistry",
    "ProviderFactory",
    # API key detection
    "ApiKeyDetector",
    "PROVIDER_KEY_PATTERNS",
    # Email providers
    "BrevoProvider",
    "SendGridProvider",
    "SESEmailProvider",
    "MailgunProvider",
    "PostmarkProvider",
    # SMS providers
    "TwilioProvider",
    "VonageProvider",
    # Payment providers
    "PaddleProvider",
    "StripeProvider",
]
