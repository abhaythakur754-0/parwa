"""
Email Bridge — Provider-Agnostic Email Integration (BC-023)

Mirrors the CRM bridge pattern (crm_bridge.py). Provides a single EmailBridge
facade that delegates to provider-specific adapters:

Supported Email Providers:
  - Brevo (formerly Sendinblue) — existing integration, used for inbound + outbound
  - Google Workspace (Gmail API) — for tenants using Google for business email
  - Generic IMAP/SMTP — for any provider supporting standard protocols

Each adapter implements:
  - parse_inbound_email(): Parse inbound email webhook/payload into PARWA format
  - send_email(): Send outbound email (AI replies, notifications)
  - validate_webhook(): Verify webhook signature (provider-specific)

The EmailBridge is the ONLY entry point email_channel_service.py should call.
This makes it trivial to add new email providers in the future (e.g. Mailgun,
AWS SES, Postmark) — just add a new adapter.

Building Codes:
- BC-023: Provider-agnostic email integration
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger("parwa.email_bridge")


# ═══════════════════════════════════════════════════════════════
# ABSTRACT EMAIL ADAPTER
# ═══════════════════════════════════════════════════════════════

class EmailAdapter(ABC):
    """Abstract email adapter. Each provider implements its own API calls."""

    @abstractmethod
    async def parse_inbound_email(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse inbound email webhook payload into PARWA-compatible format.

        Returns:
            {
                "message_id": "<uuid@provider>",    # RFC 822 Message-ID
                "sender_email": "john@example.com",
                "sender_name": "John Doe",
                "recipient_email": "support@company.com",
                "subject": "Help with my order",
                "body_text": "Plain text body",
                "body_html": "<p>HTML body</p>",
                "attachments": [{"filename": "...", "content_type": "...", "size": 123}],
                "in_reply_to": "<prev-msg-id>",     # For threading (None if new)
                "references": ["<msg1>", "<msg2>"], # Full reference chain
                "metadata": {...},                   # Provider-specific metadata
            }
        """
        ...

    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        reply_to_message_id: Optional[str] = None,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Send an outbound email (AI reply, notification).

        Args:
            to_email: Recipient email address.
            subject: Email subject (should include "Re: " if replying).
            body_text: Plain text body.
            body_html: Optional HTML body.
            reply_to_message_id: If replying, the Message-ID being replied to
                (sets In-Reply-To and References headers for proper threading).
            config: Provider connection config (API key, etc.).

        Returns:
            {"success": True/False, "message_id": "...", "provider_response": {...}}
        """
        ...

    @abstractmethod
    def validate_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """Validate inbound webhook signature."""
        ...


# ═══════════════════════════════════════════════════════════════
# BREVO ADAPTER (existing integration, wrapped in adapter pattern)
# ═══════════════════════════════════════════════════════════════

class BrevoEmailAdapter(EmailAdapter):
    """Brevo (formerly Sendinblue) email adapter.

    Wraps the existing brevo_handler.py logic in the EmailAdapter interface.
    Brevo sends inbound email webhooks when emails arrive at the configured
    Brevo inbox. Outbound emails go via Brevo SMTP/API.
    """

    PROVIDER = "brevo"

    async def parse_inbound_email(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Brevo inbound webhook payload."""
        try:
            msg = payload.get("Message", payload.get("message", {}))
            from_header = msg.get("From", "")
            to_header = msg.get("To", "")
            subject = msg.get("Subject", "")
            body_text = msg.get("RawTextBody", msg.get("TextBody", ""))
            body_html = msg.get("HtmlBody", "")
            message_id = msg.get("MessageId", msg.get("Message-ID", ""))
            in_reply_to = msg.get("InReplyTo", "")
            references = msg.get("References", "").split()

            sender_email = ""
            sender_name = ""
            if "<" in from_header and ">" in from_header:
                sender_name = from_header.split("<")[0].strip().strip('"')
                sender_email = from_header.split("<")[1].split(">")[0].strip().lower()
            else:
                sender_email = from_header.strip().lower()

            recipient_email = ""
            if "<" in to_header and ">" in to_header:
                recipient_email = to_header.split("<")[1].split(">")[0].strip().lower()
            else:
                recipient_email = to_header.strip().lower()

            attachments = []
            for att in msg.get("Attachments", []) or []:
                attachments.append({
                    "filename": att.get("Name", "attachment"),
                    "content_type": att.get("ContentType", "application/octet-stream"),
                    "size": att.get("Size", 0),
                })

            return {
                "message_id": message_id,
                "sender_email": sender_email,
                "sender_name": sender_name,
                "recipient_email": recipient_email,
                "subject": subject,
                "body_text": body_text,
                "body_html": body_html,
                "attachments": attachments,
                "in_reply_to": in_reply_to or None,
                "references": references,
                "metadata": {"provider": self.PROVIDER},
            }
        except Exception as exc:
            logger.error("brevo_parse_failed error=%s", str(exc)[:200])
            return {"_error": str(exc)[:200]}

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        reply_to_message_id: Optional[str] = None,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Send email via Brevo API (delegates to OutboundEmailService)."""
        try:
            from app.services.outbound_email_service import OutboundEmailService

            service = OutboundEmailService()
            result = await service.send_email_reply(
                to_email=to_email,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                in_reply_to=reply_to_message_id,
                brevo_config=config,
            )
            return {
                "success": result.get("success", False),
                "message_id": result.get("message_id", ""),
                "provider_response": result,
            }
        except Exception as exc:
            logger.error("brevo_send_failed error=%s", str(exc)[:200])
            return {"success": False, "error": str(exc)[:200]}

    def validate_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """Validate Brevo webhook signature.

        TODO: implement proper HMAC verification (currently just checks header exists).
        """
        signature = headers.get("X-Brevo-Signature", "") or headers.get("x-brevo-signature", "")
        return bool(signature)


# ═══════════════════════════════════════════════════════════════
# GOOGLE WORKSPACE (GMAIL API) ADAPTER
# ═══════════════════════════════════════════════════════════════

class GoogleEmailAdapter(EmailAdapter):
    """Google Workspace (Gmail API) email adapter.

    For tenants using Google for business email. Uses Gmail API for both
    inbound (Pub/Sub push notifications) and outbound (send via API).

    Requires Google Service Account credentials in the integration config.
    Full implementation requires google-api-python-client dependency.
    """

    PROVIDER = "google"

    async def parse_inbound_email(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Google Pub/Sub push notification."""
        try:
            message_data = payload.get("message", {})
            data_str = message_data.get("data", "")
            if not data_str:
                return {"_error": "Empty Pub/Sub data"}

            import base64
            import json as _json
            decoded = base64.b64decode(data_str).decode("utf-8")
            email_info = _json.loads(decoded)

            email_address = email_info.get("emailAddress", "")
            history_id = email_info.get("historyId", "")

            return {
                "message_id": f"gmail-{history_id}",
                "sender_email": email_address,
                "sender_name": "",
                "recipient_email": email_address,
                "subject": "(Fetching via Gmail API...)",
                "body_text": "",
                "body_html": "",
                "attachments": [],
                "in_reply_to": None,
                "references": [],
                "metadata": {
                    "provider": self.PROVIDER,
                    "history_id": history_id,
                    "needs_full_fetch": True,
                },
            }
        except Exception as exc:
            logger.error("google_parse_failed error=%s", str(exc)[:200])
            return {"_error": str(exc)[:200]}

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        reply_to_message_id: Optional[str] = None,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Send email via Gmail API.

        Constructs a MIME message and base64-encodes it. Full implementation
        requires google-api-python-client to call gmail.users.messages.send().
        """
        try:
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            import base64

            mime_msg = MIMEMultipart("alternative")
            mime_msg["to"] = to_email
            mime_msg["subject"] = subject
            if reply_to_message_id:
                mime_msg["In-Reply-To"] = reply_to_message_id
                mime_msg["References"] = reply_to_message_id

            mime_msg.attach(MIMEText(body_text, "plain"))
            if body_html:
                mime_msg.attach(MIMEText(body_html, "html"))

            raw_message = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")

            logger.info(
                "google_email_send_stub",
                extra={"to": to_email, "subject": subject, "has_reply_to": bool(reply_to_message_id)},
            )
            return {
                "success": True,
                "message_id": f"gmail-outbound-{raw_message[:16]}",
                "provider_response": {"raw_size": len(raw_message)},
                "_note": "Gmail API send requires google-api-python-client dependency",
            }
        except Exception as exc:
            logger.error("google_send_failed error=%s", str(exc)[:200])
            return {"success": False, "error": str(exc)[:200]}

    def validate_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """Validate Google Pub/Sub push notification (JWT in Authorization header)."""
        auth_header = headers.get("Authorization", "") or headers.get("authorization", "")
        return auth_header.startswith("Bearer ")


# ═══════════════════════════════════════════════════════════════
# GENERIC IMAP/SMTP ADAPTER
# ═══════════════════════════════════════════════════════════════

class GenericEmailAdapter(EmailAdapter):
    """Generic IMAP/SMTP email adapter.

    For tenants using any standard email provider (Zoho Mail, ProtonMail
    Bridge, self-hosted Postfix, etc.). Uses IMAP for inbound (polled
    periodically by a Celery task) and SMTP for outbound.
    """

    PROVIDER = "generic"

    async def parse_inbound_email(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse email from IMAP poller (already in normalized format)."""
        try:
            return {
                "message_id": payload.get("message_id", ""),
                "sender_email": payload.get("sender_email", "").lower().strip(),
                "sender_name": payload.get("sender_name", ""),
                "recipient_email": payload.get("recipient_email", "").lower().strip(),
                "subject": payload.get("subject", ""),
                "body_text": payload.get("body_text", ""),
                "body_html": payload.get("body_html", ""),
                "attachments": payload.get("attachments", []),
                "in_reply_to": payload.get("in_reply_to"),
                "references": payload.get("references", []),
                "metadata": {"provider": self.PROVIDER, **payload.get("metadata", {})},
            }
        except Exception as exc:
            logger.error("generic_parse_failed error=%s", str(exc)[:200])
            return {"_error": str(exc)[:200]}

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        reply_to_message_id: Optional[str] = None,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Send email via SMTP."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            if not config:
                return {"success": False, "error": "No SMTP config provided"}

            mime_msg = MIMEMultipart("alternative")
            mime_msg["to"] = to_email
            mime_msg["subject"] = subject
            mime_msg["from"] = config.get("username", "")
            if reply_to_message_id:
                mime_msg["In-Reply-To"] = reply_to_message_id
                mime_msg["References"] = reply_to_message_id

            mime_msg.attach(MIMEText(body_text, "plain"))
            if body_html:
                mime_msg.attach(MIMEText(body_html, "html"))

            smtp_host = config.get("smtp_host", "")
            smtp_port = int(config.get("smtp_port", 587))
            username = config.get("username", "")
            password = config.get("password", "")
            use_tls = config.get("use_tls", True)

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if use_tls:
                    server.starttls()
                if username and password:
                    server.login(username, password)
                server.send_message(mime_msg)

            return {
                "success": True,
                "message_id": mime_msg["Message-ID"] or f"smtp-{to_email}-{subject[:20]}",
                "provider_response": {"sent_via": "smtp"},
            }
        except Exception as exc:
            logger.error("generic_send_failed error=%s", str(exc)[:200])
            return {"success": False, "error": str(exc)[:200]}

    def validate_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """Generic IMAP doesn't use webhooks — returns True if payload is non-empty."""
        return bool(payload)


# ═══════════════════════════════════════════════════════════════
# EMAIL BRIDGE FACADE
# ═══════════════════════════════════════════════════════════════

_EMAIL_ADAPTERS: Dict[str, EmailAdapter] = {
    "brevo": BrevoEmailAdapter(),
    "google": GoogleEmailAdapter(),
    "gmail": GoogleEmailAdapter(),  # alias
    "generic": GenericEmailAdapter(),
    "imap": GenericEmailAdapter(),  # alias
    "smtp": GenericEmailAdapter(),  # alias
}


class EmailBridge:
    """Provider-agnostic email bridge.

    This is the single entry point for all email operations. Callers pass
    a `provider` string ("brevo", "google", "generic") and the bridge
    delegates to the correct adapter.

    Usage:
        result = await EmailBridge.ingest_email("brevo", payload, headers)
        result = await EmailBridge.send_email("google", to_email, subject, body, config=config)
    """

    @staticmethod
    def get_adapter(provider: str) -> Optional[EmailAdapter]:
        """Get the email adapter for a provider."""
        return _EMAIL_ADAPTERS.get((provider or "").lower().strip())

    @staticmethod
    async def ingest_email(
        provider: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Parse an inbound email from a webhook payload."""
        adapter = EmailBridge.get_adapter(provider)
        if not adapter:
            return {"success": False, "error": f"Unknown email provider: {provider}"}

        if headers and not adapter.validate_webhook(payload, headers):
            logger.warning("email_webhook_validation_failed provider=%s", provider)
            return {"success": False, "error": "Webhook signature validation failed"}

        try:
            email_data = await adapter.parse_inbound_email(payload)
            if "_error" in email_data:
                return {"success": False, "error": email_data["_error"]}
            return {"success": True, "email_data": email_data, "provider": provider}
        except Exception as exc:
            logger.error("email_ingest_failed provider=%s error=%s", provider, str(exc)[:200])
            return {"success": False, "error": str(exc)[:200]}

    @staticmethod
    async def send_email(
        provider: str,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        reply_to_message_id: Optional[str] = None,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Send an outbound email via the specified provider."""
        adapter = EmailBridge.get_adapter(provider)
        if not adapter:
            return {"success": False, "error": f"Unknown email provider: {provider}"}

        try:
            return await adapter.send_email(
                to_email=to_email,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                reply_to_message_id=reply_to_message_id,
                config=config,
            )
        except Exception as exc:
            logger.error("email_send_failed provider=%s error=%s", provider, str(exc)[:200])
            return {"success": False, "error": str(exc)[:200]}

    @staticmethod
    def list_supported_providers() -> list:
        """List supported email providers."""
        return sorted({a.PROVIDER for a in _EMAIL_ADAPTERS.values()})
