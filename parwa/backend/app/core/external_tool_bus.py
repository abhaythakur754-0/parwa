"""
PARWA — Canonical External Tool Bus

SINGLE integration layer for ALL external service calls.
Both MCP servers and Backend use this — no duplicate providers.

Call chain (per channel):
    1. ProviderFactory (DB-backed credentials) — preferred path
    2. Environment-variable direct API call     — last-resort fallback

Variant Channel Permissions:
    mini_parwa  → email, chat
    parwa       → email, chat, SMS, voice
    parwa_high  → email, chat, SMS, voice, push, webhook

Design Principles:
    - BC-001: company_id scoping on every call
    - BC-008: Pipeline should never crash — all calls wrapped in try/except
    - Graceful degradation: If a provider is down, return helpful error, don't crash
    - Variant enforcement: Channels not allowed for a tier return clear permission error
    - Zero complexity: Agents just call bus.send_sms(), bus.make_call(), etc.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from app.core.channel_permissions import (
    Channel,
    VARIANT_CHANNEL_PERMISSIONS,
    get_allowed_channels,
    is_channel_allowed,
)

logger = logging.getLogger("parwa.external_tool_bus")


# ═══════════════════════════════════════════════════════════════════
# Integration Name Mapping (Channel → Integration)
# ═══════════════════════════════════════════════════════════════════

CHANNEL_INTEGRATION_MAP: dict[Channel, str] = {
    Channel.SMS: "twilio",
    Channel.VOICE: "twilio",
    Channel.EMAIL: "brevo",
    Channel.CHAT: "parwa_chat",
    Channel.PUSH: "firebase",
    Channel.WEBHOOK: "http_webhook",
}


# ═══════════════════════════════════════════════════════════════════
# Result Types
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ToolResult:
    """Unified result from any external tool call."""
    success: bool
    channel: Channel
    provider: str = ""
    message_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "channel": self.channel.value,
            "provider": self.provider,
            "message_id": self.message_id,
            "data": self.data,
            "error": self.error,
        }


# ═══════════════════════════════════════════════════════════════════
# Provider Configuration
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ProviderConfig:
    """Configuration for a specific provider."""
    name: str
    channel: Channel
    configured: bool = False
    missing_env_vars: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


def _check_provider_configs() -> dict[Channel, ProviderConfig]:
    """Check which providers are configured from environment variables."""
    configs: dict[Channel, ProviderConfig] = {}

    # ── SMS (Twilio) ────────────────────────────────────────
    sms_missing = []
    if not os.environ.get("TWILIO_ACCOUNT_SID"):
        sms_missing.append("TWILIO_ACCOUNT_SID")
    if not os.environ.get("TWILIO_AUTH_TOKEN"):
        sms_missing.append("TWILIO_AUTH_TOKEN")
    if not os.environ.get("TWILIO_PHONE_NUMBER"):
        sms_missing.append("TWILIO_PHONE_NUMBER")

    configs[Channel.SMS] = ProviderConfig(
        name="twilio_sms",
        channel=Channel.SMS,
        configured=len(sms_missing) == 0,
        missing_env_vars=sms_missing,
    )

    # ── Voice (Twilio) ──────────────────────────────────────
    voice_missing = []
    if not os.environ.get("TWILIO_ACCOUNT_SID"):
        voice_missing.append("TWILIO_ACCOUNT_SID")
    if not os.environ.get("TWILIO_AUTH_TOKEN"):
        voice_missing.append("TWILIO_AUTH_TOKEN")

    configs[Channel.VOICE] = ProviderConfig(
        name="twilio_voice",
        channel=Channel.VOICE,
        configured=len(voice_missing) == 0,
        missing_env_vars=voice_missing,
    )

    # ── Email (Brevo/Sendinblue) ────────────────────────────
    email_missing = []
    if not os.environ.get("BREVO_API_KEY"):
        email_missing.append("BREVO_API_KEY")

    configs[Channel.EMAIL] = ProviderConfig(
        name="brevo",
        channel=Channel.EMAIL,
        configured=len(email_missing) == 0,
        missing_env_vars=email_missing,
    )

    # ── Chat (Internal — always available) ──────────────────
    configs[Channel.CHAT] = ProviderConfig(
        name="parwa_chat",
        channel=Channel.CHAT,
        configured=True,
    )

    # ── Push (Firebase/FCM) ─────────────────────────────────
    push_missing = []
    if not os.environ.get("FIREBASE_CREDENTIALS"):
        push_missing.append("FIREBASE_CREDENTIALS")

    configs[Channel.PUSH] = ProviderConfig(
        name="firebase",
        channel=Channel.PUSH,
        configured=len(push_missing) == 0,
        missing_env_vars=push_missing,
    )

    # ── Webhook (Always available — just HTTP POST) ─────────
    configs[Channel.WEBHOOK] = ProviderConfig(
        name="http_webhook",
        channel=Channel.WEBHOOK,
        configured=True,
    )

    return configs


# ═══════════════════════════════════════════════════════════════════
# External Tool Bus
# ═══════════════════════════════════════════════════════════════════

class ExternalToolBus:
    """Unified, variant-aware external tool integration layer.

    All pipeline variants call this bus to interact with external services.
    The bus enforces variant permissions and handles provider fallbacks.

    Usage:
        bus = ExternalToolBus()
        result = await bus.send_sms(
            variant="parwa",
            company_id="comp_123",
            to="+919652852014",
            body="Your ticket has been resolved!"
        )
    """

    def __init__(self, db: Any = None) -> None:
        self._db = db
        self._providers = _check_provider_configs()
        logger.info(
            "external_tool_bus_initialized",
            extra={
                "configured_channels": [
                    ch.value for ch, cfg in self._providers.items() if cfg.configured
                ],
                "total_channels": len(self._providers),
            },
        )

    def set_db(self, db: Any) -> None:
        """Set the database session for ProviderFactory lookups."""
        self._db = db

    # ── Permission Checks ───────────────────────────────────────

    def is_channel_allowed(self, variant: str, channel: Channel) -> bool:
        """Check if a variant tier is allowed to use a channel."""
        return is_channel_allowed(variant, channel)

    def get_allowed_channels(self, variant: str) -> list[str]:
        """Get list of channels allowed for a variant tier."""
        return get_allowed_channels(variant)

    def is_channel_configured(self, channel: Channel) -> bool:
        """Check if a channel's provider is configured."""
        cfg = self._providers.get(channel)
        return cfg.configured if cfg else False

    def get_provider_status(self) -> dict[str, Any]:
        """Get status of all providers (for health check / dashboard)."""
        return {
            ch.value: {
                "provider": cfg.name,
                "configured": cfg.configured,
                "missing_env_vars": cfg.missing_env_vars,
            }
            for ch, cfg in self._providers.items()
        }

    # ── SMS ─────────────────────────────────────────────────────

    async def send_sms(
        self,
        variant: str,
        company_id: str,
        to: str,
        body: str,
        **kwargs: Any,
    ) -> ToolResult:
        """Send an SMS message via Twilio.

        Args:
            variant: Variant tier (mini_parwa, parwa, parwa_high).
            company_id: Tenant company ID.
            to: Recipient phone number (E.164 format preferred).
            body: SMS message body (max 1600 chars).

        Returns:
            ToolResult with success status and message SID.
        """
        # Permission check
        if not self.is_channel_allowed(variant, Channel.SMS):
            return ToolResult(
                success=False,
                channel=Channel.SMS,
                error=f"Channel 'sms' not available for variant '{variant}'. "
                      f"Upgrade to 'parwa' or 'parwa_high' to access SMS.",
            )

        integration_name = self._get_integration_name(Channel.SMS)

        # Circuit breaker check
        degraded = self._check_circuit_breaker(integration_name, Channel.SMS)
        if degraded:
            return degraded

        # Rate limit check
        rate_limited = self._check_rate_limit(integration_name, company_id, Channel.SMS)
        if rate_limited:
            return rate_limited

        # Provider check
        if not self.is_channel_configured(Channel.SMS):
            cfg = self._providers[Channel.SMS]
            self._record_failure(integration_name)
            return ToolResult(
                success=False,
                channel=Channel.SMS,
                provider="twilio_sms",
                error=f"SMS not configured. Missing env vars: {', '.join(cfg.missing_env_vars)}",
            )

        # Try ProviderFactory (DB-backed credentials) first
        try:
            result = await self._send_sms_via_provider(company_id, to, body)
            if result:
                self._record_success(integration_name)
                return result
        except Exception as exc:
            logger.warning("sms_provider_failed: %s", str(exc)[:200])

        # Last-resort fallback: env-var-based direct Twilio call
        try:
            result = await self._retry_call(
                lambda: self._send_sms_via_env(to, body),
                integration_name, company_id,
            )
            return result
        except Exception as exc:
            logger.error("sms_send_failed: to=%s err=%s", to, str(exc)[:200])
            return ToolResult(
                success=False,
                channel=Channel.SMS,
                provider="twilio_sms",
                error=f"SMS send failed: {str(exc)[:200]}",
            )

    async def _send_sms_via_provider(
        self, company_id: str, to: str, body: str,
    ) -> Optional[ToolResult]:
        """Send SMS via ProviderFactory (uses registered provider)."""
        from app.core.providers import ProviderFactory

        if not self._db:
            return None

        try:
            provider = await ProviderFactory.create_from_config(
                db=self._db, company_id=company_id, category="sms", provider_type="twilio",
            )
            result = await provider.send_sms(to=to, message=body)
            if result.success:
                return ToolResult(
                    success=True,
                    channel=Channel.SMS,
                    provider="twilio",
                    message_id=(result.data or {}).get("sid", ""),
                    data=result.data or {},
                )
            return ToolResult(
                success=False,
                channel=Channel.SMS,
                provider="twilio",
                error=result.message,
            )
        except (KeyError, ValueError):
            # No DB config found — fall through to env-var path
            return None

    async def _send_sms_via_env(self, to: str, body: str) -> ToolResult:
        """Last-resort fallback: send SMS using environment variables directly."""
        import httpx

        account_sid = os.environ["TWILIO_ACCOUNT_SID"]
        auth_token = os.environ["TWILIO_AUTH_TOKEN"]
        from_number = os.environ["TWILIO_PHONE_NUMBER"]

        # Normalize phone number
        formatted_to = to.strip()
        if not formatted_to.startswith("+"):
            formatted_to = "+" + re.sub(r"[^0-9]", "", formatted_to)

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        auth = httpx.BasicAuth(account_sid, auth_token)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                auth=auth,
                data={
                    "From": from_number,
                    "To": formatted_to,
                    "Body": body[:1600],  # Twilio limit
                },
            )
            resp_data = resp.json()

            if resp.status_code in (200, 201):
                return ToolResult(
                    success=True,
                    channel=Channel.SMS,
                    provider="twilio_sms",
                    message_id=resp_data.get("sid", ""),
                    data=resp_data,
                )
            else:
                return ToolResult(
                    success=False,
                    channel=Channel.SMS,
                    provider="twilio_sms",
                    error=f"Twilio API error {resp.status_code}: {resp_data.get('message', 'Unknown')}",
                )

    # ── Email ───────────────────────────────────────────────────

    async def send_email(
        self,
        variant: str,
        company_id: str,
        to: str | list[str],
        subject: str,
        body: str,
        html_body: str = "",
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Send an email via Brevo (Sendinblue).

        Args:
            variant: Variant tier.
            company_id: Tenant company ID.
            to: Recipient email(s).
            subject: Email subject.
            body: Plain text body.
            html_body: HTML body (optional, falls back to plain text).
            cc: CC recipients.
            bcc: BCC recipients.

        Returns:
            ToolResult with success status and message ID.
        """
        # Permission check
        if not self.is_channel_allowed(variant, Channel.EMAIL):
            return ToolResult(
                success=False,
                channel=Channel.EMAIL,
                error=f"Channel 'email' not available for variant '{variant}'.",
            )

        integration_name = self._get_integration_name(Channel.EMAIL)

        # Circuit breaker check
        degraded = self._check_circuit_breaker(integration_name, Channel.EMAIL)
        if degraded:
            return degraded

        # Rate limit check
        rate_limited = self._check_rate_limit(integration_name, company_id, Channel.EMAIL)
        if rate_limited:
            return rate_limited

        # Provider check
        if not self.is_channel_configured(Channel.EMAIL):
            cfg = self._providers[Channel.EMAIL]
            self._record_failure(integration_name)
            return ToolResult(
                success=False,
                channel=Channel.EMAIL,
                provider="brevo",
                error=f"Email not configured. Missing: {', '.join(cfg.missing_env_vars)}",
            )

        # Normalize recipients
        recipients = [to] if isinstance(to, str) else to

        # Try ProviderFactory (DB-backed credentials) first
        try:
            result = await self._send_email_via_provider(
                company_id, recipients, subject, body, html_body, cc, bcc,
            )
            if result:
                self._record_success(integration_name)
                return result
        except Exception as exc:
            logger.warning("email_provider_failed: %s", str(exc)[:200])

        # Last-resort fallback: env-var-based direct Brevo call
        try:
            result = await self._retry_call(
                lambda: self._send_email_via_env(
                    recipients, subject, body, html_body, cc, bcc,
                ),
                integration_name, company_id,
            )
            return result
        except Exception as exc:
            logger.error("email_send_failed: %s", str(exc)[:200])
            return ToolResult(
                success=False,
                channel=Channel.EMAIL,
                provider="brevo",
                error=f"Email send failed: {str(exc)[:200]}",
            )

    async def _send_email_via_provider(
        self,
        company_id: str,
        recipients: list[str],
        subject: str,
        body: str,
        html_body: str,
        cc: list[str] | None,
        bcc: list[str] | None,
    ) -> Optional[ToolResult]:
        """Send email via ProviderFactory (uses registered provider)."""
        from app.core.providers import ProviderFactory

        if not self._db:
            return None

        try:
            provider = await ProviderFactory.create_from_config(
                db=self._db, company_id=company_id, category="email", provider_type="brevo",
            )
            result = await provider.send_email(
                to=", ".join(recipients),
                subject=subject,
                body=html_body or body,
            )
            if result.success:
                return ToolResult(
                    success=True,
                    channel=Channel.EMAIL,
                    provider="brevo",
                    message_id=(result.data or {}).get("messageId", ""),
                    data=result.data or {},
                )
            return ToolResult(
                success=False,
                channel=Channel.EMAIL,
                provider="brevo",
                error=result.message,
            )
        except (KeyError, ValueError):
            return None

    async def _send_email_via_env(
        self,
        recipients: list[str],
        subject: str,
        body: str,
        html_body: str,
        cc: list[str] | None,
        bcc: list[str] | None,
    ) -> ToolResult:
        """Last-resort fallback: send email using environment variables directly."""
        import httpx

        api_key = os.environ["BREVO_API_KEY"]
        from_email = os.environ.get("FROM_EMAIL", "noreply@parwa.io")
        from_name = os.environ.get("FROM_NAME", "PARWA")

        # Build HTML content
        html_content = html_body or (
            f"<div style='font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;'>"
            f"<p>{body}</p>"
            f"<hr style='border: none; border-top: 1px solid #eee; margin: 20px 0;' />"
            f"<p style='color: #888; font-size: 12px;'>Powered by PARWA AI Workforce Platform</p>"
            f"</div>"
        )

        payload: dict[str, Any] = {
            "sender": {"name": from_name, "email": from_email},
            "to": [{"email": r} for r in recipients],
            "subject": subject,
            "htmlContent": html_content,
        }
        if cc:
            payload["cc"] = [{"email": r} for r in cc]
        if bcc:
            payload["bcc"] = [{"email": r} for r in bcc]

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            if resp.status_code in (200, 201):
                data = resp.json() if resp.text else {}
                return ToolResult(
                    success=True,
                    channel=Channel.EMAIL,
                    provider="brevo",
                    message_id=data.get("messageId", ""),
                    data=data,
                )
            else:
                return ToolResult(
                    success=False,
                    channel=Channel.EMAIL,
                    provider="brevo",
                    error=f"Brevo API error {resp.status_code}: {resp.text[:200]}",
                )

    # ── Voice ───────────────────────────────────────────────────

    async def make_call(
        self,
        variant: str,
        company_id: str,
        to: str,
        message: str = "",
        language: str = "en-US",
        ticket_id: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        """Initiate an outbound voice call via Twilio.

        Args:
            variant: Variant tier.
            company_id: Tenant company ID.
            to: Phone number to call (E.164).
            message: TTS greeting message.
            language: Speech language.
            ticket_id: Optional ticket ID to link.

        Returns:
            ToolResult with call SID and status.
        """
        # Permission check
        if not self.is_channel_allowed(variant, Channel.VOICE):
            return ToolResult(
                success=False,
                channel=Channel.VOICE,
                error=f"Channel 'voice' not available for variant '{variant}'. "
                      f"Upgrade to 'parwa' or 'parwa_high' to access Voice calls.",
            )

        integration_name = self._get_integration_name(Channel.VOICE)

        # Circuit breaker check
        degraded = self._check_circuit_breaker(integration_name, Channel.VOICE)
        if degraded:
            return degraded

        # Rate limit check
        rate_limited = self._check_rate_limit(integration_name, company_id, Channel.VOICE)
        if rate_limited:
            return rate_limited

        # Try ProviderFactory first
        try:
            result = await self._make_call_via_provider(
                company_id, to, message, language, ticket_id, variant,
            )
            if result:
                self._record_success(integration_name)
                return result
        except Exception as exc:
            logger.warning("voice_provider_failed: %s", str(exc)[:200])

        # Last-resort fallback: env-var-based direct Twilio call
        try:
            result = await self._retry_call(
                lambda: self._make_call_via_env(to, message, variant),
                integration_name, company_id,
            )
            return result
        except Exception as exc:
            logger.error("voice_call_failed: to=%s err=%s", to, str(exc)[:200])
            return ToolResult(
                success=False,
                channel=Channel.VOICE,
                provider="twilio_voice",
                error=f"Voice call failed: {str(exc)[:200]}",
            )

    async def _make_call_via_provider(
        self,
        company_id: str,
        to: str,
        message: str,
        language: str,
        ticket_id: str,
        variant: str,
    ) -> Optional[ToolResult]:
        """Make call via ProviderFactory (uses registered provider)."""
        # Voice provider isn't in the ProviderFactory registry yet —
        # return None to fall through to env-var path.
        # TODO: Add VoiceProvider base class and TwilioVoiceProvider adapter
        return None

    async def _make_call_via_env(
        self, to: str, message: str, variant: str,
    ) -> ToolResult:
        """Last-resort fallback: make call using environment variables directly."""
        import httpx

        account_sid = os.environ["TWILIO_ACCOUNT_SID"]
        auth_token = os.environ["TWILIO_AUTH_TOKEN"]
        from_number = os.environ.get("TWILIO_PHONE_NUMBER", "")

        # Normalize phone number
        formatted_to = to.strip()
        if not formatted_to.startswith("+"):
            formatted_to = "+" + re.sub(r"[^0-9]", "", formatted_to)

        # Build TwiML
        greeting = message or "Hello, this is a call from your support team."
        greeting_escaped = (
            greeting.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        twiml = (
            f'<Response>'
            f'<Say>{greeting_escaped}</Say>'
            f'</Response>'
        )

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"
        auth = httpx.BasicAuth(account_sid, auth_token)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                auth=auth,
                data={
                    "From": from_number,
                    "To": formatted_to,
                    "Twiml": twiml,
                },
            )
            resp_data = resp.json()

            if resp.status_code in (200, 201):
                return ToolResult(
                    success=True,
                    channel=Channel.VOICE,
                    provider="twilio_voice",
                    message_id=resp_data.get("sid", ""),
                    data={
                        "call_sid": resp_data.get("sid", ""),
                        "status": resp_data.get("status", "queued"),
                        "to": formatted_to,
                        "variant_tier": variant,
                    },
                )
            else:
                return ToolResult(
                    success=False,
                    channel=Channel.VOICE,
                    provider="twilio_voice",
                    error=f"Twilio call error {resp.status_code}: {resp_data.get('message', 'Unknown')}",
                )

    # ── Chat ────────────────────────────────────────────────────

    async def send_chat(
        self,
        variant: str,
        company_id: str,
        message: str,
        conversation_id: str = "",
        customer_id: str = "",
        channel: str = "chat_widget",
        **kwargs: Any,
    ) -> ToolResult:
        """Send a chat message and get an AI-generated response.

        Chat is available to ALL variant tiers (mini_parwa, parwa, parwa_high).

        Args:
            variant: Variant tier.
            company_id: Tenant company ID.
            message: Customer message.
            conversation_id: Existing conversation ID (new if empty).
            customer_id: Customer identifier.
            channel: Chat channel (chat_widget, web, mobile).

        Returns:
            ToolResult with AI reply and conversation ID.
        """
        # Chat is available to all variants — no permission check needed
        # But we still verify the variant is valid
        if variant not in VARIANT_CHANNEL_PERMISSIONS:
            return ToolResult(
                success=False,
                channel=Channel.CHAT,
                error=f"Invalid variant: '{variant}'. Must be one of: mini_parwa, parwa, parwa_high",
            )

        # Try backend AI pipeline first
        try:
            result = await self._send_chat_via_backend(
                company_id, message, conversation_id, customer_id, channel, variant,
            )
            if result:
                return result
        except Exception as exc:
            logger.warning("chat_backend_failed: %s", str(exc)[:200])

        # Fallback: generate a simple template response
        return ToolResult(
            success=True,
            channel=Channel.CHAT,
            provider="parwa_chat",
            message_id=f"chat_{os.urandom(4).hex()}",
            data={
                "conversation_id": conversation_id or f"conv_{os.urandom(4).hex()}",
                "reply": self._generate_chat_template(message, variant),
                "is_ai_generated": True,
                "confidence": 0.7,
                "variant": variant,
            },
        )

    async def _send_chat_via_backend(
        self,
        company_id: str,
        message: str,
        conversation_id: str,
        customer_id: str,
        channel: str,
        variant: str,
    ) -> Optional[ToolResult]:
        """Send chat via backend AI pipeline."""
        import httpx

        backend_url = os.environ.get("BACKEND_URL", "http://localhost:5100")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{backend_url}/api/v1/chat/message",
                json={
                    "company_id": company_id,
                    "message": message,
                    "conversation_id": conversation_id or None,
                    "customer_id": customer_id or None,
                    "channel": channel,
                    "variant": variant,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return ToolResult(
                    success=True,
                    channel=Channel.CHAT,
                    provider="parwa_chat",
                    message_id=data.get("message_id", ""),
                    data=data,
                )
        return None

    @staticmethod
    def _generate_chat_template(message: str, variant: str) -> str:
        """Generate a template chat response when AI pipeline is unavailable."""
        msg_lower = message.lower()

        if any(word in msg_lower for word in ["refund", "return", "money back"]):
            return "I understand you'd like a refund. Let me look into this for you. Could you provide your order number?"
        if any(word in msg_lower for word in ["order", "tracking", "shipping", "delivery"]):
            return "I'd be happy to help with your order. Could you share your order number so I can check the status?"
        if any(word in msg_lower for word in ["cancel", "cancellation"]):
            return "I can help with cancellation. Let me check the current status. Could you provide your account or order details?"
        if any(word in msg_lower for word in ["billing", "charge", "payment", "invoice"]):
            return "I'll help you with your billing concern. Could you provide more details about the charge or invoice?"

        return (
            "Thank you for reaching out! I'm here to help. "
            "Could you provide more details about your concern so I can assist you better?"
        )

    # ── Webhook ─────────────────────────────────────────────────

    async def send_webhook(
        self,
        variant: str,
        company_id: str,
        url: str,
        payload: dict[str, Any],
        secret: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        """Send an outbound webhook.

        Args:
            variant: Variant tier.
            company_id: Tenant company ID.
            url: Webhook URL to POST to.
            payload: JSON payload to send.
            secret: Optional HMAC secret for signature.

        Returns:
            ToolResult with HTTP status.
        """
        if not self.is_channel_allowed(variant, Channel.WEBHOOK):
            return ToolResult(
                success=False,
                channel=Channel.WEBHOOK,
                error=f"Channel 'webhook' not available for variant '{variant}'.",
            )

        integration_name = self._get_integration_name(Channel.WEBHOOK)

        # Circuit breaker check
        degraded = self._check_circuit_breaker(integration_name, Channel.WEBHOOK)
        if degraded:
            return degraded

        # Rate limit check
        rate_limited = self._check_rate_limit(integration_name, company_id, Channel.WEBHOOK)
        if rate_limited:
            return rate_limited

        try:
            import httpx

            headers: dict[str, str] = {"Content-Type": "application/json"}

            # Add HMAC signature if secret provided
            if secret:
                body_bytes = json.dumps(payload, separators=(",", ":")).encode()
                signature = hmac.new(
                    secret.encode(), body_bytes, hashlib.sha256
                ).hexdigest()
                headers["X-PARWA-Signature"] = f"sha256={signature}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                self._record_success(integration_name)
                return ToolResult(
                    success=200 <= resp.status_code < 300,
                    channel=Channel.WEBHOOK,
                    provider="http_webhook",
                    data={
                        "status_code": resp.status_code,
                        "url": url,
                    },
                )
        except Exception as exc:
            self._record_failure(integration_name)
            return ToolResult(
                success=False,
                channel=Channel.WEBHOOK,
                provider="http_webhook",
                error=f"Webhook failed: {str(exc)[:200]}",
            )

    # ── Convenience: Send Notification ──────────────────────────

    async def send_notification(
        self,
        variant: str,
        company_id: str,
        subject: str,
        body: str,
        html_body: str = "",
        email: str = "",
        phone: str = "",
        sms_body: str = "",
        voice_message: str = "",
    ) -> dict[str, ToolResult]:
        """Send a notification across all available channels for a variant.

        Automatically determines which channels to use based on:
        1. Variant tier permissions
        2. Contact info availability
        3. Provider configuration

        Returns:
            Dict mapping channel name to ToolResult.
        """
        results: dict[str, ToolResult] = {}

        # Email notification
        if email and self.is_channel_allowed(variant, Channel.EMAIL):
            results["email"] = await self.send_email(
                variant=variant,
                company_id=company_id,
                to=email,
                subject=subject,
                body=body,
                html_body=html_body,
            )

        # SMS notification
        if phone and self.is_channel_allowed(variant, Channel.SMS):
            results["sms"] = await self.send_sms(
                variant=variant,
                company_id=company_id,
                to=phone,
                body=sms_body or body[:160],
            )

        # Voice notification (only for escalations / parwa_high)
        if phone and voice_message and self.is_channel_allowed(variant, Channel.VOICE):
            results["voice"] = await self.make_call(
                variant=variant,
                company_id=company_id,
                to=phone,
                message=voice_message,
            )

        return results

    # ── Rate Limiting & Circuit Breaker Integration ────────────────

    def _get_integration_name(self, channel: Channel) -> str:
        """Get the integration name for a channel."""
        return CHANNEL_INTEGRATION_MAP.get(channel, "custom")

    def _check_circuit_breaker(self, integration_name: str, channel: Channel) -> Optional[ToolResult]:
        """Check if the circuit breaker is open for an integration.

        Returns a degraded ToolResult if circuit is open, None if OK to proceed.
        """
        try:
            from app.core.circuit_breaker_manager import get_circuit_breaker_manager
            cb_manager = get_circuit_breaker_manager()
            if not cb_manager.is_available(integration_name):
                return self._degraded_result(channel, integration_name)
        except Exception:
            logger.warning("circuit_breaker_check_failed integration=%s", integration_name)
        return None

    def _check_rate_limit(self, integration_name: str, company_id: str, channel: Channel) -> Optional[ToolResult]:
        """Check if rate limit is exceeded for an integration.

        Returns a rate-limited ToolResult if exceeded, None if OK to proceed.
        """
        try:
            from app.core.integration_rate_limiter import get_integration_rate_limiter
            rate_limiter = get_integration_rate_limiter()
            if not rate_limiter.check_rate_limit(integration_name, company_id):
                return ToolResult(
                    success=False,
                    channel=channel,
                    provider=integration_name,
                    error=f"Rate limit exceeded for {integration_name}. Please retry in a moment.",
                )
            # Consume quota
            rate_limiter.record_call(integration_name, company_id)
        except Exception:
            logger.warning("rate_limit_check_failed integration=%s", integration_name)
        return None

    def _record_success(self, integration_name: str) -> None:
        """Record a successful call to the circuit breaker."""
        try:
            from app.core.circuit_breaker_manager import get_circuit_breaker_manager
            cb_manager = get_circuit_breaker_manager()
            cb_manager.record_success(integration_name)
        except Exception:
            pass  # BC-008: Never crash

    def _record_failure(self, integration_name: str) -> None:
        """Record a failed call to the circuit breaker."""
        try:
            from app.core.circuit_breaker_manager import get_circuit_breaker_manager
            cb_manager = get_circuit_breaker_manager()
            cb_manager.record_failure(integration_name)
        except Exception:
            pass  # BC-008: Never crash

    def _degraded_result(
        self, channel: Channel, integration_name: str, cached_data: Optional[dict] = None,
    ) -> ToolResult:
        """Return a degraded result with cached data fallback."""
        message = f"{integration_name} is temporarily unavailable."
        if cached_data:
            message += " Showing cached data."
        return ToolResult(
            success=bool(cached_data),
            channel=channel,
            provider=integration_name,
            data=cached_data or {},
            error=message if not cached_data else "",
        )

    async def _retry_call(
        self,
        call_fn: Callable,
        integration_name: str,
        company_id: str,
        max_retries: int = 3,
    ) -> Any:
        """Retry an external call with exponential backoff for transient errors.

        Only retries on transient errors (429, timeouts, connection errors).
        Non-transient errors are raised immediately.
        """
        for attempt in range(max_retries + 1):
            try:
                result = await call_fn()
                self._record_success(integration_name)
                return result
            except Exception as exc:
                is_transient = self._is_transient_error(exc)
                if not is_transient or attempt == max_retries:
                    self._record_failure(integration_name)
                    raise
                backoff = min(2 ** attempt, 8)  # 1s, 2s, 4s max
                logger.warning(
                    "retry_%s attempt=%d backoff=%ds err=%s",
                    integration_name, attempt + 1, backoff, str(exc)[:100],
                )
                await asyncio.sleep(backoff)

    @staticmethod
    def _is_transient_error(exc: Exception) -> bool:
        """Check if an exception is transient (retryable)."""
        try:
            from app.core.parwa_pipeline.retry import is_transient_error
            return is_transient_error(exc)
        except ImportError:
            pass

        # Fallback: basic classification
        status_code = getattr(exc, "status_code", None) or getattr(exc, "http_status", None)
        if status_code is not None:
            try:
                code = int(status_code)
                if code == 429 or code >= 500:
                    return True
                return False
            except (ValueError, TypeError):
                pass

        if isinstance(exc, (ConnectionError, TimeoutError, asyncio.TimeoutError)):
            return True

        exc_name = type(exc).__name__.lower()
        return any(p in exc_name for p in ("timeout", "connection", "ratelimit", "throttl"))

    def register_integration_circuit_breaker(
        self, integration_name: str, failure_threshold: int = 5, timeout: int = 60,
    ) -> None:
        """Register a circuit breaker for a new integration.

        Allows dynamic registration for custom connectors and new integrations.
        """
        try:
            from app.core.circuit_breaker_manager import (
                CircuitBreakerConfig,
                get_circuit_breaker_manager,
            )
            cb_manager = get_circuit_breaker_manager()
            cb_manager.register(
                integration_name,
                CircuitBreakerConfig(failure_threshold=failure_threshold, timeout=timeout),
            )
            logger.info(
                "integration_circuit_breaker_registered name=%s threshold=%d timeout=%d",
                integration_name, failure_threshold, timeout,
            )
        except Exception:
            logger.exception(
                "register_integration_circuit_breaker_failed name=%s", integration_name,
            )

    # ── Bulk / Broadcast ────────────────────────────────────────

    async def send_ticket_notification(
        self,
        variant: str,
        company_id: str,
        ticket_id: str,
        ticket_number: str,
        status: str,
        customer_name: str,
        customer_email: str = "",
        customer_phone: str = "",
        message: str = "",
    ) -> dict[str, ToolResult]:
        """Send a ticket status notification across all available channels.

        Automatically determines which channels to use based on:
        1. Variant tier permissions
        2. Customer contact info availability
        3. Provider configuration

        Returns:
            Dict mapping channel name to ToolResult.
        """
        results: dict[str, ToolResult] = {}

        # Build notification message
        prefix = f"[PARWA] {ticket_number}"
        notification_body = message or f"Hi {customer_name}, your ticket status has been updated to: {status}."

        # Email notification
        if customer_email:
            email_result = await self.send_email(
                variant=variant,
                company_id=company_id,
                to=customer_email,
                subject=f"{prefix}: Ticket Update — {status.title()}",
                body=notification_body,
            )
            results["email"] = email_result

        # SMS notification
        if customer_phone and self.is_channel_allowed(variant, Channel.SMS):
            sms_body = f"{prefix}: {notification_body}"[:160]
            sms_result = await self.send_sms(
                variant=variant,
                company_id=company_id,
                to=customer_phone,
                body=sms_body,
            )
            results["sms"] = sms_result

        return results


# ═══════════════════════════════════════════════════════════════════
# Singleton Instance
# ═══════════════════════════════════════════════════════════════════

external_tool_bus = ExternalToolBus()
