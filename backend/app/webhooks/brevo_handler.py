"""
Brevo Webhook Handler (BC-003, GAP 1.5)

Handles Brevo inbound email webhooks.
- inbound_email: Parse incoming email → create ticket draft

All handlers:
- Validate email structure and required fields
- Extract sender, subject, body, attachments metadata
- Return structured result for service layer processing
- Are idempotent (checked at webhook_service level)
"""

import logging
from typing import Optional

from backend.app.webhooks import register_handler

logger = logging.getLogger("parwa.webhooks.brevo")

# Maximum inbound email body size (1MB)
MAX_EMAIL_BODY_SIZE = 1 * 1024 * 1024

# Required fields for inbound email
REQUIRED_INBOUND_FIELDS = ["sender_email", "subject", "body_html", "recipient_email"]


def _sanitize_email_field(value: str, max_length: int = 500) -> str:
    """Sanitize email field to prevent XSS and control characters.

    Strips control characters, HTML tags from plain fields,
    and truncates to max_length.
    """
    if not value:
        return ""
    # Strip control characters
    cleaned = "".join(
        c for c in str(value) if ord(c) >= 32 or c in "\n\r\t"
    )
    # Truncate
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned.strip()


def _extract_inbound_email_data(payload: dict) -> dict:
    """Extract and normalize inbound email data from Brevo payload.

    Brevo sends inbound email data with fields like:
    - sender: {email, name}
    - recipient: {email}
    - subject: string
    - body_html: string
    - body_text: string (optional)
    - attachments: array of {filename, content-type, size}
    """
    sender = payload.get("sender", {}) or {}
    recipient = payload.get("recipient", {}) or {}

    return {
        "sender_email": _sanitize_email_field(sender.get("email", ""), 254),
        "sender_name": _sanitize_email_field(sender.get("name", ""), 200),
        "recipient_email": _sanitize_email_field(recipient.get("email", ""), 254),
        "subject": _sanitize_email_field(payload.get("subject", ""), 500),
        "body_html": payload.get("body_html", ""),
        "body_text": payload.get("body_text", ""),
        "attachments": _extract_attachments(payload.get("attachments", [])),
        "in_reply_to": payload.get("in_reply_to"),
        "message_id": payload.get("message_id"),
    }


def _extract_attachments(attachments: list) -> list:
    """Extract safe attachment metadata.

    Only extracts metadata (name, type, size) — not file contents.
    Limits to 20 attachments max.
    """
    if not attachments or not isinstance(attachments, list):
        return []

    result = []
    for att in attachments[:20]:  # Max 20 attachments
        if not isinstance(att, dict):
            continue
        result.append({
            "filename": _sanitize_email_field(att.get("filename", ""), 255),
            "content_type": _sanitize_email_field(att.get("content-type", ""), 100),
            "size": att.get("size", 0),
        })
    return result


def _validate_inbound_email(data: dict) -> Optional[str]:
    """Validate inbound email data has required fields.

    Returns:
        Error message if validation fails, None if OK.
    """
    for field in REQUIRED_INBOUND_FIELDS:
        val = data.get(field)
        if not val or not isinstance(val, str) or not val.strip():
            return f"Missing required field: {field}"
    return None


def handle_inbound_email(event: dict) -> dict:
    """Handle Brevo inbound_email event.

    Parses the email, extracts data, and returns a ticket draft.
    The actual ticket creation happens in the service layer.

    Args:
        event: Full event dict with keys:
            - event_type: "inbound_email"
            - payload: Raw Brevo payload
            - company_id: Tenant company ID
            - event_id: Provider event ID

    Returns:
        Dict with status, action, and extracted email data.
    """
    payload = event.get("payload", {})
    email_data = _extract_inbound_email_data(payload)

    # Validate
    error = _validate_inbound_email(email_data)
    if error:
        return {"status": "validation_error", "error": error}

    # Check body size
    if len(email_data.get("body_html", "")) > MAX_EMAIL_BODY_SIZE:
        logger.warning(
            "brevo_email_body_too_large sender=%s size=%s",
            email_data["sender_email"],
            len(email_data["body_html"]),
            extra={
                "company_id": event.get("company_id"),
                "event_id": event.get("event_id"),
            },
        )
        email_data["body_html"] = email_data["body_html"][:MAX_EMAIL_BODY_SIZE]
        email_data["body_truncated"] = True

    logger.info(
        "brevo_inbound_email sender=%s subject=%s",
        email_data["sender_email"],
        email_data["subject"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "create_ticket_draft",
        "data": email_data,
    }


# Event type to handler mapping
_BREVO_HANDLERS = {
    "inbound_email": handle_inbound_email,
}


@register_handler("brevo")
def handle_brevo_event(event: dict) -> dict:
    """Main Brevo webhook handler dispatcher.

    Routes to the correct sub-handler based on event_type.

    Args:
        event: Full event dict.

    Returns:
        Dict with status, action, and extracted data.
    """
    event_type = event.get("event_type", "")

    handler = _BREVO_HANDLERS.get(event_type)
    if not handler:
        logger.warning(
            "brevo_unknown_event_type type=%s event_id=%s",
            event_type,
            event.get("event_id"),
            extra={"company_id": event.get("company_id")},
        )
        return {
            "status": "validation_error",
            "error": f"Unknown Brevo event type: {event_type}",
            "supported_types": list(_BREVO_HANDLERS.keys()),
        }

    return handler(event)
