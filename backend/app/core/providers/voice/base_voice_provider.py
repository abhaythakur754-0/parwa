"""Voice provider adapter layer — bring-your-own calling platform.

Parwa NEVER provisions phone numbers and NEVER pays for telecom.
Every tenant connects their OWN calling platform account (pays that
platform directly) and Parwa talks to it through one of these adapters.

Adding a new provider (e.g. Exotel, Vonage):
  1. Create ``exotel_voice_provider.py`` implementing VoiceProviderBase
  2. Register it in ``get_voice_provider`` below
  3. Add the name to ``_VOICE_PROVIDERS`` in database/models/voice_channel.py

Each adapter is responsible for:
  - parsing the provider's webhook payload into a VoiceWebhookEvent
  - verifying the provider's request signature (HMAC etc.)
  - building the provider's call-script format (TwiML for Twilio)
  - placing outbound calls with the TENANT's credentials
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class VoiceWebhookEvent:
    """Normalized inbound webhook event from any voice provider."""

    provider: str = "twilio"
    call_sid: str = ""
    account_sid: str = ""
    from_number: str = ""
    to_number: str = ""
    call_status: str = ""          # ringing | in-progress | completed | ...
    direction: str = ""            # inbound | outbound
    speech_text: str = ""          # customer speech (gather events)
    digits: str = ""               # keypad input (gather events)
    event_kind: str = "status"     # status | gather | inbound_start
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderCredentials:
    """The TENANT's own provider account credentials (BYO)."""

    account_sid: str = ""
    auth_token: str = ""           # decrypted
    phone_number: str = ""


class VoiceProviderBase(ABC):
    """Interface every voice provider adapter must implement."""

    #: provider name stored in VoiceChannelConfig.provider
    name: str = "base"

    # ── Inbound webhook handling ────────────────────────────────

    @abstractmethod
    def parse_webhook(self, payload: Dict[str, Any]) -> VoiceWebhookEvent:
        """Convert a raw provider webhook payload into a normal event."""

    @abstractmethod
    def verify_signature(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        auth_token: str,
    ) -> bool:
        """Validate the request really came from the provider.

        Implementations must return True when no auth_token is configured
        (test/dev mode) so local testing is possible, and False on a bad
        signature in production.
        """

    # ── Call-script (TwiML for Twilio) building ─────────────────

    @abstractmethod
    def build_greeting_twiml(
        self,
        greeting: str,
        gather_action_url: str,
        language: str,
        voice: str,
    ) -> str:
        """First response of a call: speak the greeting, then listen."""

    @abstractmethod
    def build_conversation_twiml(
        self,
        say_text: str,
        gather_action_url: str,
        language: str,
        voice: str,
    ) -> str:
        """Mid-call turn: speak the agent reply, then listen again."""

    @abstractmethod
    def build_transfer_twiml(
        self,
        say_text: str,
        transfer_number: str,
        language: str,
        voice: str,
    ) -> str:
        """Warm hand-off: say something, then bridge to a human."""

    @abstractmethod
    def build_end_twiml(
        self,
        say_text: str,
        language: str,
        voice: str,
    ) -> str:
        """Final response: say something, then hang up."""

    # ── Outbound calls (using the TENANT's account) ─────────────

    @abstractmethod
    def initiate_call(
        self,
        credentials: ProviderCredentials,
        to_number: str,
        call_script: str,
        status_callback_url: str,
        record: bool = False,
    ) -> Dict[str, Any]:
        """Place an outbound call with the tenant's credentials.

        Returns {"success": bool, "call_sid": str|None, "error": str|None}.
        """


def xml_escape(text: str) -> str:
    """Escape text for embedding in an XML call script."""
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def get_voice_provider(name: Optional[str]) -> VoiceProviderBase:
    """Look up a provider adapter by config name (default: twilio)."""
    # Imported lazily to avoid circular imports at module load time.
    from app.core.providers.voice.twilio_voice_provider import (
        TwilioVoiceProvider,
    )

    registry: Dict[str, VoiceProviderBase] = {
        TwilioVoiceProvider.name: TwilioVoiceProvider(),
    }
    key = (name or "twilio").strip().lower()
    provider = registry.get(key)
    if provider is None:
        raise ValueError(
            f"Unknown voice provider '{key}'. Supported: {sorted(registry)}"
        )
    return provider
