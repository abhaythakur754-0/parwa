"""
PARWA Universal Provider System

This module provides a universal abstraction layer for all third-party integrations.
The system is NOT locked into any specific provider - it works with ANY provider.

Supported Email Providers:
- Brevo (formerly Sendinblue)
- SendGrid
- Mailgun
- AWS SES
- Postmark
- Mailchimp Transactional
- Custom SMTP

Supported SMS Providers:
- Twilio
- MessageBird
- Vonage (Nexmo)
- Plivo
- Sinch
- Telnyx
- ClickSend

Supported Voice Providers:
- Twilio Voice
- Vonage Voice
- Sinch Voice

Supported Chat Providers:
- Slack
- Discord
- Microsoft Teams
- Custom Webhooks

Usage:
    from app.providers import ProviderFactory, ProviderType

    # Get email provider
    email_provider = ProviderFactory.get_provider(
        provider_type=ProviderType.EMAIL,
        provider_name="brevo",
        config={"api_key": "..."}
    )

    # Send email
    result = email_provider.send_email(
        to="user@example.com",
        subject="Hello",
        html_content="<p>Hi!</p>"
    )

    # Get SMS provider
    sms_provider = ProviderFactory.get_provider(
        provider_type=ProviderType.SMS,
        provider_name="twilio",
        config={"account_sid": "...", "auth_token": "..."}
    )

    # Send SMS
    result = sms_provider.send_sms(
        to="+1234567890",
        body="Hello from PARWA!"
    )
"""

from app.providers.base import (
    BaseProvider,
    ChatProvider,
    EmailProvider,
    ProviderCapability,
    ProviderResult,
    ProviderStatus,
    ProviderType,
    SMSProvider,
    VoiceProvider,
)
from app.providers.factory import ProviderFactory
from app.providers.registry import ProviderRegistry

__all__ = [
    # Base classes
    "BaseProvider",
    "ProviderType",
    "ProviderCapability",
    "ProviderStatus",
    "ProviderResult",
    "EmailProvider",
    "SMSProvider",
    "VoiceProvider",
    "ChatProvider",
    # Factory
    "ProviderFactory",
    # Registry
    "ProviderRegistry",
]
