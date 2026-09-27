"""
SMS Bridge — Provider-Agnostic SMS Integration (BC-024)

Mirrors the CRM and email bridge patterns. Provides a single SMSBridge
facade that delegates to provider-specific adapters:

Supported SMS Providers:
  - Twilio — existing integration
  - Vonage (formerly Nexmo) — alternative provider
  - Generic — for any SMS provider with webhook support

Each adapter implements:
  - parse_inbound_sms(): Parse inbound SMS webhook into PARWA format
  - send_sms(): Send outbound SMS (AI replies, notifications)
  - validate_webhook(): Verify webhook signature

Building Codes:
- BC-024: Provider-agnostic SMS integration + fix broken inbound + wire to AI
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger("parwa.sms_bridge")


# ═══════════════════════════════════════════════════════════════
# ABSTRACT SMS ADAPTER
# ═══════════════════════════════════════════════════════════════

class SMSAdapter(ABC):
    """Abstract SMS adapter. Each provider implements its own API calls."""

    @abstractmethod
    async def parse_inbound_sms(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse inbound SMS webhook payload into PARWA-compatible format.

        Returns:
            {
                "message_id": "SMxxx",            # Provider message ID
                "from_number": "+1234567890",
                "to_number": "+0987654321",
                "body": "Help with my order",
                "received_at": "2024-01-01T00:00:00Z",
                "metadata": {...},                 # Provider-specific metadata
            }
        """
        ...

    @abstractmethod
    async def send_sms(
        self,
        to_number: str,
        body: str,
        from_number: Optional[str] = None,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Send an outbound SMS.

        Args:
            to_number: Recipient phone number (E.164 format).
            body: SMS body text (max 1600 chars for most providers).
            from_number: Sender phone number (defaults to config's from_number).
            config: Provider connection config (API key, auth token, etc.).

        Returns:
            {"success": True/False, "message_id": "...", "provider_response": {...}}
        """
        ...

    @abstractmethod
    def validate_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """Validate inbound webhook signature."""
        ...


# ═══════════════════════════════════════════════════════════════
# TWILIO ADAPTER
# ═══════════════════════════════════════════════════════════════

class TwilioSMSAdapter(SMSAdapter):
    """Twilio SMS adapter.

    Wraps the existing twilio_handler.py logic in the SMSAdapter interface.
    Uses Twilio REST API for outbound and Twilio webhook for inbound.
    """

    PROVIDER = "twilio"

    async def parse_inbound_sms(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Twilio inbound SMS webhook payload.

        Twilio sends form-encoded data with fields like MessageSid, From, To, Body.
        The webhook handler converts this to a dict before passing to us.
        """
        try:
            return {
                "message_id": payload.get("MessageSid", payload.get("message_sid", "")),
                "from_number": payload.get("From", payload.get("from", "")),
                "to_number": payload.get("To", payload.get("to", "")),
                "body": payload.get("Body", payload.get("body", "")),
                "received_at": payload.get("DateSent", payload.get("date_sent", "")),
                "metadata": {
                    "provider": self.PROVIDER,
                    "account_sid": payload.get("AccountSid", ""),
                    "messaging_service_sid": payload.get("MessagingServiceSid", ""),
                    "num_media": payload.get("NumMedia", "0"),
                },
            }
        except Exception as exc:
            logger.error("twilio_parse_failed error=%s", str(exc)[:200])
            return {"_error": str(exc)[:200]}

    async def send_sms(
        self,
        to_number: str,
        body: str,
        from_number: Optional[str] = None,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Send SMS via Twilio REST API."""
        try:
            if not config:
                return {"success": False, "error": "No Twilio config provided"}

            account_sid = config.get("account_sid", config.get("api_key", ""))
            auth_token = config.get("auth_token", config.get("api_secret", ""))
            sender = from_number or config.get("from_number", config.get("phone_number", ""))

            if not account_sid or not auth_token or not sender:
                return {"success": False, "error": "Missing account_sid, auth_token, or from_number"}

            # Use Twilio HTTP API directly (avoids hard dependency on twilio-python package)
            import httpx
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            auth = (account_sid, auth_token)
            data = {
                "To": to_number,
                "From": sender,
                "Body": body[:1600],  # Twilio max 1600 chars
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, auth=auth, data=data)
                resp_data = resp.json()

            if resp.status_code in (200, 201):
                return {
                    "success": True,
                    "message_id": resp_data.get("sid", ""),
                    "provider_response": resp_data,
                }
            else:
                return {
                    "success": False,
                    "error": f"Twilio API error {resp.status_code}: {resp_data.get('message', '')}",
                    "provider_response": resp_data,
                }
        except Exception as exc:
            logger.error("twilio_send_failed error=%s", str(exc)[:200])
            return {"success": False, "error": str(exc)[:200]}

    def validate_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """Validate Twilio webhook signature.

        Twilio signs webhooks with X-Twilio-Signature header (HMAC-SHA256
        of the URL + sorted params with auth_token). TODO: implement proper
        HMAC verification — currently checks header exists.
        """
        signature = headers.get("X-Twilio-Signature", "") or headers.get("x-twilio-signature", "")
        return bool(signature)


# ═══════════════════════════════════════════════════════════════
# VONAGE (NEXMO) ADAPTER
# ═══════════════════════════════════════════════════════════════

class VonageSMSAdapter(SMSAdapter):
    """Vonage (formerly Nexmo) SMS adapter.

    Alternative SMS provider. Uses Vonage REST API for outbound and
    Vonage webhook for inbound.
    """

    PROVIDER = "vonage"

    async def parse_inbound_sms(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Vonage inbound SMS webhook payload.

        Vonage sends a JSON array of inbound SMS objects.
        """
        try:
            # Vonage sends an array of messages
            messages = payload.get("message", payload.get("messages", []))
            if isinstance(messages, list) and messages:
                msg = messages[0]
            elif isinstance(messages, dict):
                msg = messages
            else:
                msg = payload

            return {
                "message_id": msg.get("message-id", msg.get("messageId", "")),
                "from_number": msg.get("from", msg.get("msisdn", "")),
                "to_number": msg.get("to", msg.get("to_number", "")),
                "body": msg.get("text", msg.get("body", "")),
                "received_at": msg.get("timestamp", ""),
                "metadata": {
                    "provider": self.PROVIDER,
                    "message_type": msg.get("type", "text"),
                },
            }
        except Exception as exc:
            logger.error("vonage_parse_failed error=%s", str(exc)[:200])
            return {"_error": str(exc)[:200]}

    async def send_sms(
        self,
        to_number: str,
        body: str,
        from_number: Optional[str] = None,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Send SMS via Vonage REST API."""
        try:
            if not config:
                return {"success": False, "error": "No Vonage config provided"}

            api_key = config.get("api_key", "")
            api_secret = config.get("api_secret", "")
            sender = from_number or config.get("from_number", config.get("sender_id", "PARWA"))

            if not api_key or not api_secret:
                return {"success": False, "error": "Missing api_key or api_secret"}

            import httpx
            url = "https://rest.nexmo.com/sms/json"
            data = {
                "api_key": api_key,
                "api_secret": api_secret,
                "to": to_number,
                "from": sender,
                "text": body[:1600],
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, data=data)
                resp_data = resp.json()

            # Vonage returns 200 even if individual messages fail — check message status
            messages = resp_data.get("messages", [])
            if messages and messages[0].get("status") == "0":
                return {
                    "success": True,
                    "message_id": messages[0].get("message-id", ""),
                    "provider_response": resp_data,
                }
            else:
                return {
                    "success": False,
                    "error": f"Vonage API error: {messages[0].get('error-text', 'Unknown') if messages else 'No messages'}",
                    "provider_response": resp_data,
                }
        except Exception as exc:
            logger.error("vonage_send_failed error=%s", str(exc)[:200])
            return {"success": False, "error": str(exc)[:200]}

    def validate_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """Validate Vonage webhook signature.

        Vonage doesn't sign webhooks by default but can be configured to.
        For now, accept all (tenant should use HTTPS + shared secret in URL).
        """
        return True


# ═══════════════════════════════════════════════════════════════
# GENERIC SMS ADAPTER
# ═══════════════════════════════════════════════════════════════

class GenericSMSAdapter(SMSAdapter):
    """Generic SMS adapter for any provider with webhook support.

    Expects the inbound webhook payload to already be in normalized format
    (caller does the provider-specific parsing). Outbound uses a configurable
    HTTP endpoint (e.g. SMS gateway URL).
    """

    PROVIDER = "generic"

    async def parse_inbound_sms(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse already-normalized SMS payload."""
        try:
            return {
                "message_id": payload.get("message_id", ""),
                "from_number": payload.get("from_number", payload.get("from", "")),
                "to_number": payload.get("to_number", payload.get("to", "")),
                "body": payload.get("body", payload.get("text", "")),
                "received_at": payload.get("received_at", payload.get("timestamp", "")),
                "metadata": {"provider": self.PROVIDER, **payload.get("metadata", {})},
            }
        except Exception as exc:
            logger.error("generic_parse_failed error=%s", str(exc)[:200])
            return {"_error": str(exc)[:200]}

    async def send_sms(
        self,
        to_number: str,
        body: str,
        from_number: Optional[str] = None,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Send SMS via configurable HTTP endpoint (SMS gateway)."""
        try:
            if not config:
                return {"success": False, "error": "No SMS gateway config provided"}

            gateway_url = config.get("gateway_url", "")
            api_key = config.get("api_key", "")
            sender = from_number or config.get("from_number", "PARWA")

            if not gateway_url:
                return {"success": False, "error": "Missing gateway_url in config"}

            import httpx
            data = {
                "to": to_number,
                "from": sender,
                "body": body[:1600],
                "api_key": api_key,
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(gateway_url, json=data)
                resp_data = {}
                try:
                    resp_data = resp.json()
                except Exception:
                    resp_data = {"raw": resp.text[:500]}

            if resp.status_code in (200, 201):
                return {
                    "success": True,
                    "message_id": resp_data.get("message_id", ""),
                    "provider_response": resp_data,
                }
            else:
                return {
                    "success": False,
                    "error": f"SMS gateway error {resp.status_code}",
                    "provider_response": resp_data,
                }
        except Exception as exc:
            logger.error("generic_send_failed error=%s", str(exc)[:200])
            return {"success": False, "error": str(exc)[:200]}

    def validate_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """Generic — accept all (tenant should use HTTPS + shared secret in URL)."""
        return True


# ═══════════════════════════════════════════════════════════════
# SMS BRIDGE FACADE
# ═══════════════════════════════════════════════════════════════

_SMS_ADAPTERS: Dict[str, SMSAdapter] = {
    "twilio": TwilioSMSAdapter(),
    "vonage": VonageSMSAdapter(),
    "nexmo": VonageSMSAdapter(),  # legacy alias
    "generic": GenericSMSAdapter(),
}


class SMSBridge:
    """Provider-agnostic SMS bridge.

    Usage:
        result = await SMSBridge.ingest_sms("twilio", payload, headers)
        result = await SMSBridge.send_sms("vonage", to_number, body, config=config)
    """

    @staticmethod
    def get_adapter(provider: str) -> Optional[SMSAdapter]:
        """Get the SMS adapter for a provider."""
        return _SMS_ADAPTERS.get((provider or "").lower().strip())

    @staticmethod
    async def ingest_sms(
        provider: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Parse an inbound SMS from a webhook payload."""
        adapter = SMSBridge.get_adapter(provider)
        if not adapter:
            return {"success": False, "error": f"Unknown SMS provider: {provider}"}

        if headers and not adapter.validate_webhook(payload, headers):
            logger.warning("sms_webhook_validation_failed provider=%s", provider)
            return {"success": False, "error": "Webhook signature validation failed"}

        try:
            sms_data = await adapter.parse_inbound_sms(payload)
            if "_error" in sms_data:
                return {"success": False, "error": sms_data["_error"]}
            return {"success": True, "sms_data": sms_data, "provider": provider}
        except Exception as exc:
            logger.error("sms_ingest_failed provider=%s error=%s", provider, str(exc)[:200])
            return {"success": False, "error": str(exc)[:200]}

    @staticmethod
    async def send_sms(
        provider: str,
        to_number: str,
        body: str,
        from_number: Optional[str] = None,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Send an outbound SMS via the specified provider."""
        adapter = SMSBridge.get_adapter(provider)
        if not adapter:
            return {"success": False, "error": f"Unknown SMS provider: {provider}"}

        try:
            return await adapter.send_sms(
                to_number=to_number,
                body=body,
                from_number=from_number,
                config=config,
            )
        except Exception as exc:
            logger.error("sms_send_failed provider=%s error=%s", provider, str(exc)[:200])
            return {"success": False, "error": str(exc)[:200]}

    @staticmethod
    def list_supported_providers() -> list:
        """List supported SMS providers."""
        return sorted({a.PROVIDER for a in _SMS_ADAPTERS.values()})
