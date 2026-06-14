"""
Email Channel Celery Tasks: Async processing for email events.

Week 13 Day 1 (F-121: Email Inbound).
Week 13 Day 3 (F-122 + F-124: OOO + Bounce/Complaint).

Tasks:
- process_inbound_email_task: Process inbound email via Brevo webhook
- process_bounce_event_task: Process email bounce (F-124)
- process_complaint_event_task: Process spam complaint (F-124)
- process_delivered_event_task: Process delivery confirmation (F-124)

BC-003: Idempotent webhook processing.
BC-004: Celery task pattern (ParwaBaseTask + @with_company_id).
BC-006: Email communication.
BC-010: GDPR compliance (complaint handling).
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
    """Process email bounce event from Brevo (F-124).

    Determines hard vs soft bounce, updates contact status,
    schedules retries for soft bounces, and logs the event.

    Args:
        company_id: Tenant company ID.
        bounce_data: Bounce event payload with email, bounce_type,
            reason, message_id, event_id.

    Returns:
        Dict with status, event_type, actions taken.
    """
    try:
        from app.core.tenant_context import get_db_session
        from app.services.bounce_complaint_service import BounceComplaintService

        db = get_db_session()
        try:
            service = BounceComplaintService(db)
            result = service.process_bounce(
                company_id=company_id,
                bounce_data=bounce_data,
            )

            logger.info(
                "bounce_event_processed",
                extra={
                    "task": self.name,
                    "company_id": company_id,
                    "email": bounce_data.get("email"),
                    "status": result.get("status"),
                    "event_type": result.get("event_type"),
                },
            )
            return result
        finally:
            db.close()

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
    """Process email spam complaint event from Brevo (F-124).

    Marks the contact as complained (BC-010), updates outbound
    email status, and logs the event for review.

    Args:
        company_id: Tenant company ID.
        complaint_data: Complaint event payload with email,
            complaint_type, reason, message_id, event_id.

    Returns:
        Dict with status and actions taken.
    """
    try:
        from app.core.tenant_context import get_db_session
        from app.services.bounce_complaint_service import BounceComplaintService

        db = get_db_session()
        try:
            service = BounceComplaintService(db)
            result = service.process_complaint(
                company_id=company_id,
                complaint_data=complaint_data,
            )

            logger.info(
                "complaint_event_processed",
                extra={
                    "task": self.name,
                    "company_id": company_id,
                    "email": complaint_data.get("email"),
                    "status": result.get("status"),
                },
            )
            return result
        finally:
            db.close()

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


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="email",
    name="app.tasks.email_channel.process_delivered_event",
    max_retries=1,
    soft_time_limit=10,
    time_limit=20,
)
@with_company_id
def process_delivered_event_task(
    self,
    company_id: str,
    delivery_data: dict,
) -> dict:
    """Process email delivery confirmation from Brevo (F-124).

    Updates OutboundEmail status to "delivered" and stores the event.

    Args:
        company_id: Tenant company ID.
        delivery_data: Delivery event payload with email, message_id.

    Returns:
        Dict with status.
    """
    try:
        from app.core.tenant_context import get_db_session
        from app.services.bounce_complaint_service import BounceComplaintService

        db = get_db_session()
        try:
            service = BounceComplaintService(db)
            result = service.process_delivered(
                company_id=company_id,
                delivery_data=delivery_data,
            )
            return result
        finally:
            db.close()

    except Exception as exc:
        logger.error(
            "delivered_event_task_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "error": str(exc)[:200],
            },
        )
        raise
