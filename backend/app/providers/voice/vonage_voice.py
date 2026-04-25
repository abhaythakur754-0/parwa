"""Vonage Voice Provider stub."""

from app.providers.voice.twilio_voice import TwilioVoiceProvider

class VonageVoiceProvider(TwilioVoiceProvider):
    provider_name = "vonage"
    display_name = "Vonage Voice"
