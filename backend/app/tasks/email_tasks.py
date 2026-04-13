"""
PARWA Email Tasks (Day 22, BC-004, BC-006)

Celery tasks for email operations via Brevo:
- send_email: Send a single email with threading headers
- render_template: Render email template with Jinja2
- send_bulk_notification: Send bulk notifications
- send_outbound_reply: Send AI-generated reply to customer (F-120)
"""

import logging
import uuid
from typing import Optional

from app.tasks.base import ParwaBaseTask, with_company_id
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks.email")


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
    from_email: str = "",
    reply_to: str = "",
    message_id: str = "",
    reply_to_message_id: Optional[str] = None,
    references: Optional[str] = None,
) -> dict:
    """Send a single email via Brevo API.

    Actually calls email_service.send_email() with threading headers.
    Retries up to 3 times on transient failures.
    """
    try:
        from app.services.email_service import send_email as do_send

        success = do_send(
            to=to,
            subject=subject,
            html_content=html_body,
            reply_to_message_id=reply_to_message_id,
            references=references,
        )

        if success:
            sent_message_id = message_id or str(uuid.uuid4())
            logger.info(
                "send_email_success",
                extra={
                    "task": self.name,
                    "company_id": company_id,
                    "to": to,
                    "subject": subject,
                    "message_id": sent_message_id,
                    "reply_to": reply_to_message_id,
                },
            )
            return {
                "status": "sent",
                "message_id": sent_message_id,
                "to": to,
            }
        else:
            logger.error(
                "send_email_returned_false",
                extra={
                    "task": self.name,
                    "company_id": company_id,
                    "to": to,
                },
            )
            raise Exception("email_service.send_email returned False")

    except Exception as exc:
        logger.error(
            "send_email_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "to": to,
                "error": str(exc)[:200],
            },
        )
        # Retry on transient failures
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


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
    """Send bulk notification to multiple recipients."""
    try:
        from app.services.email_service import send_email

        batch_id = batch_id or str(uuid.uuid4())
        sent_count = 0
        failed_count = 0
        BATCH_SIZE = 50

        for i in range(0, len(recipients), BATCH_SIZE):
            batch = recipients[i:i + BATCH_SIZE]
            for recipient in batch:
                email = recipient.get("email", "") if isinstance(recipient, dict) else str(recipient)
                if not email:
                    failed_count += 1
                    continue
                try:
                    success = send_email(
                        to=email,
                        subject=subject,
                        html_content=html_body,
                    )
                    if success:
                        sent_count += 1
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
                "batch_id": batch_id,
            },
        )
        return {
            "status": "completed",
            "batch_id": batch_id,
            "total": len(recipients),
            "sent": sent_count,
            "failed": failed_count,
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
) -> dict:
    """Send an AI-generated email reply to a customer (F-120).

    Uses OutboundEmailService to handle threading, rate limiting,
    template rendering, and message tracking.
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
            },
        )
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
