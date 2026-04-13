"""
Email Channel Celery Tasks: Async processing for inbound emails.

Week 13 Day 1 (F-121: Email Inbound).

Tasks:
- process_inbound_email_task: Process inbound email via Brevo webhook
- process_bounce_event_task: Process email bounce (Day 3 stub)
- process_complaint_event_task: Process spam complaint (Day 3 stub)

BC-003: Idempotent webhook processing.
BC-004: Celery task pattern (ParwaBaseTask + @with_company_id).
BC-006: Email communication.
"""

import logging

from app.tasks.base import ParwaBaseTask, with_company_id
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks.email_channel")


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="email",
    name="app.tasks.email_channel.process_inbound_email",
    max_retries=3,
    soft_time_limit=30,
    time_limit=60,
)
@with_company_id
def process_inbound_email_task(
    self,
    company_id: str,
    email_data: dict,
) -> dict:
    """Process an inbound email asynchronously.

    Dispatched from brevo_handler when an inbound_email event is received.
    Calls EmailChannelService.process_inbound_email() to handle the
    full pipeline: store raw email → loop detection → auto-reply detection
    → customer lookup → thread finding → ticket creation.

    Args:
        company_id: Tenant company ID.
        email_data: Dict from brevo_handler with sender_email, subject,
            body_html, body_text, message_id, in_reply_to, references,
            attachments.

    Returns:
        Dict with status, ticket_id, inbound_email_id, error.
    """
    try:
        from app.core.tenant_context import get_db_session
        from app.services.email_channel_service import EmailChannelService

        db = get_db_session()
        service = EmailChannelService(db)

        result = service.process_inbound_email(
            company_id=company_id,
            email_data=email_data,
        )

        logger.info(
            "inbound_email_task_complete",
            extra={
                "task": self.name,
                "company_id": company_id,
                "status": result.get("status"),
                "ticket_id": result.get("ticket_id"),
                "inbound_email_id": result.get("inbound_email_id"),
            },
        )

        return result

    except Exception as exc:
        logger.error(
            "inbound_email_task_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "sender": email_data.get("sender_email", "unknown"),
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="email",
    name="app.tasks.email_channel.process_bounce_event",
    max_retries=2,
    soft_time_limit=15,
    time_limit=30,
)
@with_company_id
def process_bounce_event_task(
    self,
    company_id: str,
    bounce_data: dict,
) -> dict:
    """Process email bounce event from Brevo.

    Day 3 stub — will be fully implemented in Week 13 Day 3 (F-124).
    For now, just logs the event.

    Args:
        company_id: Tenant company ID.
        bounce_data: Bounce event payload from Brevo.

    Returns:
        Dict with status.
    """
    try:
        email = bounce_data.get("email", "unknown")
        bounce_type = bounce_data.get("event", "unknown")
        reason = bounce_data.get("reason", "")

        logger.info(
            "bounce_event_received_stub",
            extra={
                "task": self.name,
                "company_id": company_id,
                "email": email,
                "bounce_type": bounce_type,
                "reason": str(reason)[:200],
            },
        )

        # TODO: Day 3 — implement full bounce processing
        # - Update contact email status
        # - Track in EmailDeliveryEvent table
        # - Notify agents

        return {
            "status": "stub_processed",
            "email": email,
            "bounce_type": bounce_type,
        }

    except Exception as exc:
        logger.error(
            "bounce_event_task_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="email",
    name="app.tasks.email_channel.process_complaint_event",
    max_retries=2,
    soft_time_limit=15,
    time_limit=30,
)
@with_company_id
def process_complaint_event_task(
    self,
    company_id: str,
    complaint_data: dict,
) -> dict:
    """Process email spam complaint event from Brevo.

    Day 3 stub — will be fully implemented in Week 13 Day 3 (F-124).
    For now, just logs the event.

    Args:
        company_id: Tenant company ID.
        complaint_data: Complaint event payload from Brevo.

    Returns:
        Dict with status.
    """
    try:
        email = complaint_data.get("email", "unknown")
        complaint_type = complaint_data.get("event", "unknown")

        logger.info(
            "complaint_event_received_stub",
            extra={
                "task": self.name,
                "company_id": company_id,
                "email": email,
                "complaint_type": complaint_type,
            },
        )

        # TODO: Day 3 — implement full complaint processing
        # - Update contact email status
        # - Flag for review
        # - Notify admins

        return {
            "status": "stub_processed",
            "email": email,
            "complaint_type": complaint_type,
        }

    except Exception as exc:
        logger.error(
            "complaint_event_task_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "error": str(exc)[:200],
            },
        )
        raise
