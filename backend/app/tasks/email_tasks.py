"""
PARWA Email Tasks (F-120, BC-004, BC-006)

Celery tasks for email operations via Brevo:
- send_email: Send a single email with threading headers
- render_template: Render email template with Jinja2
- send_bulk_notification: Send bulk notifications (BC-006 rate limited)
- send_outbound_reply: Send AI-generated reply to customer (F-120)
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.tasks.base import ParwaBaseTask, with_company_id
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks.email")

# BC-006: Max bulk emails per recipient per hour
BC006_MAX_BULK_PER_RECIPIENT_PER_HOUR = 3


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="email",
    name="app.tasks.email.send_email",
    max_retries=3,
    soft_time_limit=30,
    time_limit=60,
)
@with_company_id
def send_email(
    self,
    company_id: str,
    to: str,
    subject: str,
    html_body: str,
    text_body: str = "",
    from_email: str = "",
    reply_to: str = "",
    message_id: str = "",
    reply_to_message_id: Optional[str] = None,
    references: Optional[str] = None,
    attachments: Optional[list] = None,
    outbound_email_id: Optional[str] = None,
) -> dict:
    """Send a single email via Brevo API.

    Actually calls email_service.send_email_tracked() with threading
    headers, attachments, and tracking. Updates OutboundEmail record
    with delivery status and Brevo message_id.

    Retries with exponential backoff: 60s, 120s, 240s (G-10 fix).
    """
    try:
        from app.services.email_service import send_email_tracked

        result = send_email_tracked(
            to=to,
            subject=subject,
            html_content=html_body,
            text_content=text_body or None,
            reply_to_message_id=reply_to_message_id,
            references=references,
            attachments=attachments,
        )

        sent_message_id = message_id or str(uuid.uuid4())

        if result.get("success"):
            brevo_msg_id = result.get("message_id")
            logger.info(
                "send_email_success",
                extra={
                    "task": self.name,
                    "company_id": company_id,
                    "to": to,
                    "subject": subject,
                    "message_id": sent_message_id,
                    "brevo_message_id": brevo_msg_id,
                    "reply_to": reply_to_message_id,
                    "outbound_email_id": outbound_email_id,
                },
            )

            # Update OutboundEmail tracking record if we have one
            if outbound_email_id:
                _update_outbound_status(
                    outbound_email_id=outbound_email_id,
                    status="sent",
                    brevo_message_id=brevo_msg_id,
                )

            return {
                "status": "sent",
                "message_id": sent_message_id,
                "brevo_message_id": brevo_msg_id,
                "to": to,
            }
        else:
            error = result.get("error", "unknown")
            logger.error(
                "send_email_returned_false",
                extra={
                    "task": self.name,
                    "company_id": company_id,
                    "to": to,
                    "error": error,
                },
            )

            # Update OutboundEmail as failed
            if outbound_email_id:
                _update_outbound_status(
                    outbound_email_id=outbound_email_id,
                    status="failed",
                    error_message=error,
                    retry_count=self.request.retries + 1,
                )

            raise Exception(f"email_service returned error: {error}")

    except Exception as exc:
        logger.error(
            "send_email_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "to": to,
                "error": str(exc)[:200],
                "retry": self.request.retries,
            },
        )
        # G-10: Exponential backoff — 60s * 2^retries = 60, 120, 240
        backoff = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=backoff)


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="email",
    name="app.tasks.email.render_template",
    max_retries=2,
    soft_time_limit=15,
    time_limit=30,
)
@with_company_id
def render_template(
    self,
    company_id: str,
    template_name: str,
    context: dict,
) -> dict:
    """Render an email template with Jinja2."""
    try:
        from app.core.email_renderer import render_email_template

        rendered = render_email_template(template_name, context)
        logger.info(
            "render_template_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "template_name": template_name,
                "rendered_length": len(rendered),
            },
        )
        return {
            "status": "rendered",
            "template_name": template_name,
            "rendered_length": len(rendered),
        }
    except Exception as exc:
        logger.error(
            "render_template_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "template_name": template_name,
                "error": str(exc)[:200],
            },
        )
        raise self.retry(exc=exc, countdown=30)


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="email",
    name="app.tasks.email.send_bulk_notification",
    max_retries=3,
    soft_time_limit=120,
    time_limit=300,
)
@with_company_id
def send_bulk_notification(
    self,
    company_id: str,
    recipients: list,
    subject: str,
    html_body: str,
    batch_id: str = "",
) -> dict:
    """Send bulk notification to multiple recipients.

    G-06: BC-006 rate limit — max 3 emails per recipient per hour.
    Recipients exceeding the limit are skipped (not retried).
    """
    try:
        from app.services.email_service import send_email

        batch_id = batch_id or str(uuid.uuid4())
        sent_count = 0
        failed_count = 0
        skipped_count = 0
        BATCH_SIZE = 50

        # Build rate-limit cache from database (G-06)
        from database.session import get_db_session  # noqa: F811
        db = get_db_session()
        try:
            from database.models.outbound_email import OutboundEmail
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            # Get recent sends per recipient
            recent_sends = (
                db.query(
                    OutboundEmail.recipient_email,
                    db.func.count(OutboundEmail.id).label("send_count"),
                )
                .filter(
                    OutboundEmail.company_id == company_id,
                    OutboundEmail.created_at >= one_hour_ago,
                )
                .group_by(OutboundEmail.recipient_email)
                .all()
            )
            rate_limit_cache = {
                row.recipient_email: row.send_count for row in recent_sends
            }
        except Exception:
            rate_limit_cache = {}
        finally:
            try:
                db.close()
            except Exception:
                pass

        for i in range(0, len(recipients), BATCH_SIZE):
            batch = recipients[i:i + BATCH_SIZE]
            for recipient in batch:
                email = recipient.get(
                    "email", "") if isinstance(
                    recipient, dict) else str(recipient)
                if not email:
                    failed_count += 1
                    continue

                # G-06: Check BC-006 rate limit per recipient
                current_count = rate_limit_cache.get(email, 0)
                if current_count >= BC006_MAX_BULK_PER_RECIPIENT_PER_HOUR:
                    logger.warning(
                        "bulk_rate_limited",
                        extra={
                            "task": self.name,
                            "company_id": company_id,
                            "email": email,
                            "count": current_count,
                        },
                    )
                    skipped_count += 1
                    continue

                try:
                    success = send_email(
                        to=email,
                        subject=subject,
                        html_content=html_body,
                    )
                    if success:
                        sent_count += 1
                        rate_limit_cache[email] = current_count + 1
                    else:
                        failed_count += 1
                except Exception:
                    failed_count += 1

            logger.info(
                "send_bulk_batch",
                extra={
                    "task": self.name,
                    "company_id": company_id,
                    "batch": i // BATCH_SIZE + 1,
                    "batch_size": len(batch),
                    "batch_id": batch_id,
                },
            )

        logger.info(
            "send_bulk_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "total": len(recipients),
                "sent": sent_count,
                "failed": failed_count,
                "skipped": skipped_count,
                "batch_id": batch_id,
            },
        )
        return {
            "status": "completed",
            "batch_id": batch_id,
            "total": len(recipients),
            "sent": sent_count,
            "failed": failed_count,
            "skipped": skipped_count,
        }
    except Exception as exc:
        logger.error(
            "send_bulk_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "batch_id": batch_id,
                "error": str(exc)[:200],
            },
        )
        raise self.retry(exc=exc, countdown=60)


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="email",
    name="app.tasks.email.send_outbound_reply",
    max_retries=3,
    soft_time_limit=60,
    time_limit=120,
)
@with_company_id
def send_outbound_reply(
    self,
    company_id: str,
    ticket_id: str,
    ai_response_html: str,
    ai_response_text: Optional[str] = None,
    sender_name: Optional[str] = None,
    model_used: Optional[str] = None,
    confidence: Optional[float] = None,
    attachments: Optional[list] = None,
) -> dict:
    """Send an AI-generated email reply to a customer (F-120).

    Uses OutboundEmailService to handle threading, rate limiting,
    template rendering, and message tracking.

    G-13: Idempotent — service checks dedup_id before sending.
    Retries with exponential backoff.
    """
    try:
        from database.session import get_db_session
        from app.services.outbound_email_service import OutboundEmailService

        db = get_db_session()
        try:
            service = OutboundEmailService(db)
            result = service.send_email_reply(
                company_id=company_id,
                ticket_id=ticket_id,
                ai_response_html=ai_response_html,
                ai_response_text=ai_response_text,
                sender_name=sender_name,
                model_used=model_used,
                confidence=confidence,
                attachments=attachments,
            )
            return result
        finally:
            db.close()
    except Exception as exc:
        logger.error(
            "send_outbound_reply_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "ticket_id": ticket_id,
                "error": str(exc)[:200],
                "retry": self.request.retries,
            },
        )
        # G-10: Exponential backoff — 60s, 120s, 240s
        backoff = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=backoff)


# ── Helpers ────────────────────────────────────────────────────


def _update_outbound_status(
    outbound_email_id: str,
    status: str,
    brevo_message_id: Optional[str] = None,
    error_message: Optional[str] = None,
    retry_count: Optional[int] = None,
) -> None:
    """Update OutboundEmail delivery status in the database.

    Called from Celery tasks after send attempt. Silently handles
    errors to avoid disrupting the task flow.

    Args:
        outbound_email_id: UUID of the OutboundEmail record.
        status: New delivery status (sent, delivered, failed, etc.).
        brevo_message_id: Brevo's message ID (if available).
        error_message: Error message (if failed).
        retry_count: Number of retries attempted.
    """
    if not outbound_email_id:
        return
    try:
        from database.session import get_db_session
        from database.models.outbound_email import OutboundEmail

        db = get_db_session()
        try:
            outbound = (
                db.query(OutboundEmail)
                .filter(OutboundEmail.id == outbound_email_id)
                .first()
            )
            if outbound:
                outbound.delivery_status = status
                if brevo_message_id:
                    outbound.brevo_message_id = brevo_message_id
                if status == "sent":
                    outbound.sent_at = datetime.now(timezone.utc)
                elif status == "delivered":
                    outbound.delivered_at = datetime.now(timezone.utc)
                elif status == "failed" and error_message:
                    outbound.error_message = error_message[:500]
                if retry_count is not None:
                    outbound.retry_count = retry_count
                db.commit()
                logger.info(
                    "outbound_status_updated",
                    extra={
                        "outbound_email_id": outbound_email_id,
                        "status": status,
                    },
                )
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception as exc:
        logger.warning(
            "outbound_status_update_failed",
            extra={
                "outbound_email_id": outbound_email_id,
                "error": str(exc)[:200],
            },
        )
