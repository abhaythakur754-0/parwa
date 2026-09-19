"""Twilio voice provider adapter (adapter #1).

Implements the provider contract for tenants who bring their OWN Twilio
account (BYO). Parwa holds only the tenant's encrypted credentials and
never pays for anything — every call is billed by Twilio to the tenant.

Call-script format: TwiML (Twilio's XML). Signature: Twilio HMAC scheme.
Outbound calls use the twilio SDK with the TENANT's account credentials.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.core.providers.voice.base_voice_provider import (
    ProviderCredentials,
    VoiceProviderBase,
    VoiceWebhookEvent,
    xml_escape,
)

logger = logging.getLogger("parwa.voice.provider.twilio")


class TwilioVoiceProvider(VoiceProviderBase):
    """Adapter for a tenant's own Twilio account."""

    name = "twilio"

    # ── Inbound webhook handling ────────────────────────────────

    def parse_webhook(self, payload: Dict[str, Any]) -> VoiceWebhookEvent:
        """Normalize a Twilio form-encoded webhook payload.

        Gather callbacks carry SpeechResult / Digits; call-start callbacks
        carry CallStatus; we detect which kind of event this is.
        """
        speech = str(payload.get("SpeechResult", "") or "")
        digits = str(payload.get("Digits", "") or "")
        call_status = str(payload.get("CallStatus", "") or "")

        if speech or digits:
            event_kind = "gather"
        elif call_status:
            event_kind = "status"
        else:
            event_kind = "status"

        return VoiceWebhookEvent(
            provider=self.name,
            call_sid=str(payload.get("CallSid", "") or ""),
            account_sid=str(payload.get("AccountSid", "") or ""),
            from_number=str(payload.get("From", "") or ""),
            to_number=str(payload.get("To", "") or ""),
            call_status=call_status,
            direction=str(payload.get("Direction", "") or ""),
            speech_text=speech,
            digits=digits,
            event_kind=event_kind,
            raw=dict(payload or {}),
        )

    def verify_signature(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        auth_token: str,
    ) -> bool:
        """Verify Twilio's X-Twilio-Signature HMAC.

        No tenant auth token (test/dev) → allow. Bad signature in
        production → reject.
        """
        token = (auth_token or "").strip()
        if not token:
            return True

        signature = (
            headers.get("x-twilio-signature")
            or headers.get("X-Twilio-Signature")
            or ""
        )
        if not signature:
            return False

        try:
            from app.security.hmac_verification import verify_twilio_signature

            return bool(verify_twilio_signature(url, payload, signature, token))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("twilio_signature_check_failed error=%s", str(exc)[:200])
            return False

    # ── Call-script (TwiML) building ────────────────────────────

    def build_greeting_twiml(
        self,
        greeting: str,
        gather_action_url: str,
        language: str,
        voice: str,
    ) -> str:
        """Greeting + start listening (this is where the AI conversation
        begins — the Gather action points at Parwa's gather webhook)."""
        return (
            "<Response>"
            f"<Say language=\"{language}\" voice=\"{voice}\">"
            f"{xml_escape(greeting)}"
            "</Say>"
            f"<Gather input=\"speech\" action=\"{xml_escape(gather_action_url)}\" "
            f"method=\"POST\" speechTimeout=\"auto\" language=\"{language}\">"
            f"<Say language=\"{language}\" voice=\"{voice}\"></Say>"
            "</Gather>"
            # If the caller says nothing, give them one more chance on the
            # same URL — the engine handles empty turns gracefully.
            f"<Redirect method=\"POST\">{xml_escape(gather_action_url)}</Redirect>"
            "</Response>"
        )

    def build_conversation_twiml(
        self,
        say_text: str,
        gather_action_url: str,
        language: str,
        voice: str,
    ) -> str:
        """Speak the agent reply, then keep listening."""
        return (
            "<Response>"
            f"<Say language=\"{language}\" voice=\"{voice}\">"
            f"{xml_escape(say_text)}"
            "</Say>"
            f"<Gather input=\"speech\" action=\"{xml_escape(gather_action_url)}\" "
            f"method=\"POST\" speechTimeout=\"auto\" language=\"{language}\">"
            f"<Say language=\"{language}\" voice=\"{voice}\"></Say>"
            "</Gather>"
            f"<Redirect method=\"POST\">{xml_escape(gather_action_url)}</Redirect>"
            "</Response>"
        )

    def build_transfer_twiml(
        self,
        say_text: str,
        transfer_number: str,
        language: str,
        voice: str,
    ) -> str:
        """Say goodbye, then bridge the live call to a human number."""
        return (
            "<Response>"
            f"<Say language=\"{language}\" voice=\"{voice}\">"
            f"{xml_escape(say_text)}"
            "</Say>"
            f"<Dial timeout=\"30\">{xml_escape(transfer_number)}</Dial>"
            "</Response>"
        )

    def build_end_twiml(
        self,
        say_text: str,
        language: str,
        voice: str,
    ) -> str:
        """Say the last message, then hang up."""
        return (
            "<Response>"
            f"<Say language=\"{language}\" voice=\"{voice}\">"
            f"{xml_escape(say_text)}"
            "</Say>"
            "<Hangup/>"
            "</Response>"
        )

    # ── Outbound calls (tenant's own account) ───────────────────

    def initiate_call(
        self,
        credentials: ProviderCredentials,
        to_number: str,
        call_script: str,
        status_callback_url: str,
        record: bool = False,
    ) -> Dict[str, Any]:
        """Place an outbound call using the TENANT's Twilio credentials."""
        try:
            from twilio.rest import Client

            client = Client(credentials.account_sid, credentials.auth_token)
            call = client.calls.create(
                to=to_number,
                from_=credentials.phone_number,
                twiml=call_script,
                status_callback=status_callback_url,
                status_callback_event=[
                    "initiated", "ringing", "answered", "completed",
                ],
                record=record,
            )
            return {"success": True, "call_sid": call.sid, "status": call.status}
        except Exception as exc:
            logger.error(
                "twilio_outbound_failed to=%s error=%s",
                to_number, str(exc)[:200],
            )
            return {"success": False, "call_sid": None, "error": str(exc)[:300]}
