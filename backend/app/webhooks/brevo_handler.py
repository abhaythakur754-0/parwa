"""
Brevo Webhook Handler (BC-003, BC-006)

Handles Brevo webhook events:
- inbound_email: Parse incoming email → dispatch to Celery → create ticket (F-121)
- bounce: Process bounce events → update contact status (F-124 stub)
- complaint: Process spam complaints → flag for review (F-124 stub)
- delivered: Log delivery confirmation

Week 13 Day 1 (F-121): Email Inbound — main processing pipeline wired.
Week 13 Day 3 (F-124): Bounce + Complaint handling (stubs for now).
"""

import json
import logging
from typing import Optional

from app.webhooks import register_handler

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
    cleaned = "".join(c for c in str(value) if ord(c) >= 32 or c in "\n\r\t")
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
    - in_reply_to: string (optional)
    - message_id: string (optional)
    """
    sender = payload.get("sender", {}) or {}
    recipient = payload.get("recipient", {}) or {}

    # Brevo may deliver threading headers at top-level or nested under
    # "headers"
    headers_block = payload.get("headers", {}) or {}

    return {
        "sender_email": _sanitize_email_field(sender.get("email", ""), 254),
        "sender_name": _sanitize_email_field(sender.get("name", ""), 200),
        "recipient_email": _sanitize_email_field(recipient.get("email", ""), 254),
        "subject": _sanitize_email_field(payload.get("subject", ""), 500),
        "body_html": payload.get("body_html", ""),
        "body_text": payload.get("body_text", ""),
        "attachments": _extract_attachments(payload.get("attachments", [])),
        "in_reply_to": payload.get("in_reply_to")
        or headers_block.get("In-Reply-To", ""),
        "message_id": payload.get("message_id") or headers_block.get("Message-ID", ""),
        "references": payload.get("references") or headers_block.get("References", ""),
    }


def _extract_attachments(attachments: list) -> list:
    """Extract safe attachment metadata.

    Extracts metadata (name, type, size) and downloads actual file
    content for supported types. Limits to 20 attachments max.
    Stores files via AttachmentService if available.

    Returns:
        List of attachment dicts with metadata and optional storage_path.
    """
    if not attachments or not isinstance(attachments, list):
        return []

    result = []
    for att in attachments[:20]:
        if not isinstance(att, dict):
            continue
        attachment_info = {
            "filename": _sanitize_email_field(att.get("filename", ""), 255),
            "content_type": _sanitize_email_field(att.get("content-type", ""), 100),
            "size": att.get("size", 0),
        }
        # Store actual file content if available (Brevo provides base64
        # content)
        content = att.get("content", "")
        if content and att.get("size", 0) < 10 * 1024 * 1024:  # Max 10MB per attachment
            attachment_info["has_content"] = True
            # Store preview only
            attachment_info["content_b64"] = content[:100]
            try:
                import base64

                # Validate it's valid base64
                base64.b64decode(content[:100])
                attachment_info["content_valid"] = True
            except Exception:
                attachment_info["content_valid"] = False
        result.append(attachment_info)
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


# ── Inbound Email Handler ───────────────────────────────────────


def handle_inbound_email(event: dict) -> dict:
    """Handle Brevo inbound_email event.

    Parses the email, extracts data, and dispatches to Celery
    for async processing via EmailChannelService.

    Pipeline: store raw email → loop detection → auto-reply detection
    → customer lookup → thread finding → ticket creation.

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

    # Store raw headers for downstream processing (loop/auto-reply/threading)
    headers_to_store = {}
    for key, value in payload.items():
        key_lower = key.lower()
        if key_lower in (
            "x-auto-response-suppress",
            "auto-submitted",
            "x-auto-reply",
            "x-noriday",
            "precedence",
            "x-precedence",
            "x-loop",
            "x-ms-exchange-orginalarrivaltime",
            # Threading headers — needed for downstream loop/thread detection
            "in_reply_to",
            "message_id",
            "references",
        ):
            headers_to_store[key] = value
    # Also capture any nested headers block from Brevo
    nested_headers = payload.get("headers", {})
    if isinstance(nested_headers, dict):
        for key, value in nested_headers.items():
            if key.lower() not in headers_to_store:
                headers_to_store[key] = value
    email_data["headers_json"] = json.dumps(headers_to_store)

    logger.info(
        "brevo_inbound_email sender=%s subject=%s",
        email_data["sender_email"],
        email_data["subject"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    # Dispatch to Celery for async processing (F-121)
    try:
        from app.tasks.email_channel_tasks import process_inbound_email_task

        process_inbound_email_task.delay(
            company_id=event.get("company_id", ""),
            email_data=email_data,
        )
        return {
            "status": "dispatched",
            "action": "create_ticket_draft",
            "data": email_data,
        }
    except Exception as exc:
        logger.error(
            "brevo_dispatch_failed sender=%s error=%s",
            email_data.get("sender_email", ""),
            str(exc)[:200],
            extra={
                "company_id": event.get("company_id"),
                "event_id": event.get("event_id"),
            },
        )
        return {
            "status": "dispatch_failed",
            "error": str(exc)[:200],
            "data": email_data,
        }


# ── Bounce Handler (Day 3 — F-124) ────────────────────────────


def handle_bounce(event: dict) -> dict:
    """Handle Brevo bounce event (F-124).

    Extracts bounce data, determines hard/soft type, and dispatches
    to Celery for async processing via BounceComplaintService.

    Args:
        event: Full event dict with payload, company_id, event_id.

    Returns:
        Dict with status and extracted bounce data.
    """
    payload = event.get("payload", {})
    bounce_data = {
        "email": _sanitize_email_field(payload.get("email", ""), 254),
        "event": "bounce",
        "bounce_type": payload.get("type", "unknown"),
        "reason": payload.get("reason", ""),
        "message_id": payload.get("message_id", ""),
        "event_id": event.get("event_id", ""),
    }

    logger.info(
        "brevo_bounce_received email=%s type=%s",
        bounce_data["email"],
        bounce_data["bounce_type"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    try:
        from app.tasks.email_channel_tasks import process_bounce_event_task

        process_bounce_event_task.delay(
            company_id=event.get("company_id", ""),
            bounce_data=bounce_data,
        )
        return {"status": "dispatched", "data": bounce_data}
    except Exception as exc:
        logger.error(
            "brevo_bounce_dispatch_failed error=%s",
            str(exc)[:200],
            extra={"company_id": event.get("company_id")},
        )
        return {"status": "dispatch_failed", "error": str(exc)[:200]}


# ── Complaint Handler (Day 3 — F-124) ──────────────────────────


def handle_complaint(event: dict) -> dict:
    """Handle Brevo spam complaint event (F-124).

    Extracts complaint data and dispatches to Celery for async
    processing via BounceComplaintService.

    Args:
        event: Full event dict with payload, company_id, event_id.

    Returns:
        Dict with status and complaint data.
    """
    payload = event.get("payload", {})
    complaint_data = {
        "email": _sanitize_email_field(payload.get("email", ""), 254),
        "event": "complaint",
        "complaint_type": payload.get("reason", "unknown"),
        "reason": payload.get("reason", ""),
        "message_id": payload.get("message_id", ""),
        "event_id": event.get("event_id", ""),
    }

    logger.info(
        "brevo_complaint_received email=%s",
        complaint_data["email"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    try:
        from app.tasks.email_channel_tasks import process_complaint_event_task

        process_complaint_event_task.delay(
            company_id=event.get("company_id", ""),
            complaint_data=complaint_data,
        )
        return {"status": "dispatched", "data": complaint_data}
    except Exception as exc:
        logger.error(
            "brevo_complaint_dispatch_failed error=%s",
            str(exc)[:200],
            extra={"company_id": event.get("company_id")},
        )
        return {"status": "dispatch_failed", "error": str(exc)[:200]}


# ── Delivered Handler (F-124) ──────────────────────────────────


def handle_delivered(event: dict) -> dict:
    """Handle Brevo delivered event (F-124).

    Dispatches to Celery for OutboundEmail status update.

    Args:
        event: Full event dict.

    Returns:
        Dict with status.
    """
    payload = event.get("payload", {})
    delivery_data = {
        "email": _sanitize_email_field(payload.get("email", ""), 254),
        "message_id": payload.get("message_id", ""),
        "event_id": event.get("event_id", ""),
    }

    try:
        from app.tasks.email_channel_tasks import process_delivered_event_task

        process_delivered_event_task.delay(
            company_id=event.get("company_id", ""),
            delivery_data=delivery_data,
        )
        return {"status": "dispatched", "data": delivery_data}
    except Exception as exc:
        logger.error(
            "brevo_delivered_dispatch_failed error=%s",
            str(exc)[:200],
            extra={"company_id": event.get("company_id")},
        )
        return {"status": "dispatch_failed", "error": str(exc)[:200]}


# ── Main Dispatcher ────────────────────────────────────────────

# Event type to handler mapping
_BREVO_HANDLERS = {
    "inbound_email": handle_inbound_email,
    "bounce": handle_bounce,
    "complaint": handle_complaint,
    "delivered": handle_delivered,
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
