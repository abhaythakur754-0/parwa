"""
PARWA MCP — External Tool Bus

Variant-aware external service integration layer.
Provides a SINGLE unified API for all pipeline variants to call
external tools (SMS, email, voice, chat)
WITHOUT needing to know the implementation details.

Variant Channel Permissions:
    mini_parwa  → email, chat
    parwa       → email, chat, SMS, voice
    parwa_high  → email, chat, SMS, voice, push, webhook

Design Principles:
    - BC-008: Pipeline should never crash — all calls wrapped in try/except
    - Graceful degradation: If a provider is down, return helpful error, don't crash
    - Variant enforcement: Channels not allowed for a tier return clear permission error
    - Zero complexity: Agents just call bus.send_sms(), bus.make_call(), etc.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

# Add backend to path so we can import shared module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.core.channel_permissions import Channel, VARIANT_CHANNEL_PERMISSIONS, is_channel_allowed, get_allowed_channels

logger = logging.getLogger("parwa.external_tool_bus")


# ═══════════════════════════════════════════════════════════════════
# Variant-Channel Permission Matrix
# (Imported from shared module: backend/app/core/channel_permissions.py)
# ═══════════════════════════════════════════════════════════════════


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

    def __init__(self) -> None:
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

        # Provider check
        if not self.is_channel_configured(Channel.SMS):
            cfg = self._providers[Channel.SMS]
            return ToolResult(
                success=False,
                channel=Channel.SMS,
                provider="twilio_sms",
                error=f"SMS not configured. Missing env vars: {', '.join(cfg.missing_env_vars)}",
            )

        # Try real backend service first
        try:
            result = await self._send_sms_via_backend(company_id, to, body)
            if result:
                return result
        except Exception as exc:
            logger.warning("sms_backend_failed", error=str(exc)[:200])

        # Fallback: direct Twilio API call
        try:
            return await self._send_sms_via_twilio(to, body)
        except Exception as exc:
            logger.error("sms_send_failed", to=to, error=str(exc)[:200])
            return ToolResult(
                success=False,
                channel=Channel.SMS,
                provider="twilio_sms",
                error=f"SMS send failed: {str(exc)[:200]}",
            )

    async def _send_sms_via_backend(
        self, company_id: str, to: str, body: str,
    ) -> Optional[ToolResult]:
        """Send SMS via the backend FastAPI service."""
        import httpx

        backend_url = os.environ.get("BACKEND_URL", "http://localhost:5100")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{backend_url}/api/v1/sms/send",
                json={
                    "company_id": company_id,
                    "to": to,
                    "body": body,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return ToolResult(
                    success=True,
                    channel=Channel.SMS,
                    provider="twilio_sms",
                    message_id=data.get("sid", ""),
                    data=data,
                )
        return None

    # DEPRECATED: Direct API fallback — will be replaced by ProviderFactory in Phase 13
    # For now, these exist as safety fallbacks when backend is unreachable

    async def _send_sms_via_twilio(self, to: str, body: str) -> ToolResult:
        """Send SMS directly via Twilio REST API (fallback)."""
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

        # Provider check
        if not self.is_channel_configured(Channel.EMAIL):
            cfg = self._providers[Channel.EMAIL]
            return ToolResult(
                success=False,
                channel=Channel.EMAIL,
                provider="brevo",
                error=f"Email not configured. Missing: {', '.join(cfg.missing_env_vars)}",
            )

        # Normalize recipients
        recipients = [to] if isinstance(to, str) else to

        # Try backend service first
        try:
            result = await self._send_email_via_backend(
                company_id, recipients, subject, body, html_body, cc, bcc,
            )
            if result:
                return result
        except Exception as exc:
            logger.warning("email_backend_failed", error=str(exc)[:200])

        # Fallback: direct Brevo API call
        try:
            return await self._send_email_via_brevo(
                recipients, subject, body, html_body, cc, bcc,
            )
        except Exception as exc:
            logger.error("email_send_failed", error=str(exc)[:200])
            return ToolResult(
                success=False,
                channel=Channel.EMAIL,
                provider="brevo",
                error=f"Email send failed: {str(exc)[:200]}",
            )

    async def _send_email_via_backend(
        self,
        company_id: str,
        recipients: list[str],
        subject: str,
        body: str,
        html_body: str,
        cc: list[str] | None,
        bcc: list[str] | None,
    ) -> Optional[ToolResult]:
        """Send email via the backend FastAPI service."""
        import httpx

        backend_url = os.environ.get("BACKEND_URL", "http://localhost:5100")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{backend_url}/api/v1/email/send",
                json={
                    "company_id": company_id,
                    "to": recipients,
                    "subject": subject,
                    "body": body,
                    "html_body": html_body,
                    "cc": cc or [],
                    "bcc": bcc or [],
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return ToolResult(
                    success=True,
                    channel=Channel.EMAIL,
                    provider="brevo",
                    message_id=data.get("message_id", ""),
                    data=data,
                )
        return None

    # DEPRECATED: Direct API fallback — will be replaced by ProviderFactory in Phase 13
    # For now, these exist as safety fallbacks when backend is unreachable

    async def _send_email_via_brevo(
        self,
        recipients: list[str],
        subject: str,
        body: str,
        html_body: str,
        cc: list[str] | None,
        bcc: list[str] | None,
    ) -> ToolResult:
        """Send email directly via Brevo REST API (fallback)."""
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

        # Try VoiceChannelService via backend
        try:
            result = await self._make_call_via_backend(
                company_id, to, message, language, ticket_id, variant,
            )
            if result:
                return result
        except Exception as exc:
            logger.warning("voice_backend_failed", error=str(exc)[:200])

        # Fallback: direct Twilio call
        try:
            return await self._make_call_via_twilio(to, message, variant)
        except Exception as exc:
            logger.error("voice_call_failed", to=to, error=str(exc)[:200])
            return ToolResult(
                success=False,
                channel=Channel.VOICE,
                provider="twilio_voice",
                error=f"Voice call failed: {str(exc)[:200]}",
            )

    async def _make_call_via_backend(
        self,
        company_id: str,
        to: str,
        message: str,
        language: str,
        ticket_id: str,
        variant: str,
    ) -> Optional[ToolResult]:
        """Make call via backend VoiceChannelService."""
        import httpx

        backend_url = os.environ.get("BACKEND_URL", "http://localhost:5100")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{backend_url}/api/v1/voice/call",
                json={
                    "company_id": company_id,
                    "to_number": to,
                    "variant_tier": variant,
                    "message": message or None,
                    "ticket_id": ticket_id or None,
                    "sender_id": "jarvis",
                    "sender_role": "bot",
                },
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                return ToolResult(
                    success=True,
                    channel=Channel.VOICE,
                    provider="twilio_voice",
                    message_id=data.get("twilio_call_sid", ""),
                    data=data,
                )
        return None

    # DEPRECATED: Direct API fallback — will be replaced by ProviderFactory in Phase 13
    # For now, these exist as safety fallbacks when backend is unreachable

    async def _make_call_via_twilio(
        self, to: str, message: str, variant: str,
    ) -> ToolResult:
        """Make call directly via Twilio REST API (fallback)."""
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
            logger.warning("chat_backend_failed", error=str(exc)[:200])

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

        try:
            import httpx

            headers: dict[str, str] = {"Content-Type": "application/json"}

            # Add HMAC signature if secret provided
            if secret:
                import hashlib
                import hmac
                import json

                body_bytes = json.dumps(payload, separators=(",", ":")).encode()
                signature = hmac.new(
                    secret.encode(), body_bytes, hashlib.sha256
                ).hexdigest()
                headers["X-PARWA-Signature"] = f"sha256={signature}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
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
            return ToolResult(
                success=False,
                channel=Channel.WEBHOOK,
                provider="http_webhook",
                error=f"Webhook failed: {str(exc)[:200]}",
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
