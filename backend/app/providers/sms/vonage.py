"""Vonage SMS Provider stub."""

from app.providers.sms.twilio import TwilioSMSProvider

class VonageSMSProvider(TwilioSMSProvider):
    """Vonage SMS provider - using similar API structure."""
    provider_name = "vonage"
    display_name = "Vonage"
    pass
