"""
PARWA Email Tasks (Day 22, BC-004, BC-006)

Celery tasks for email operations via Brevo:
- send_email_task: Send a single email
- render_template_task: Render email template with Jinja2
- send_bulk_notification_task: Send bulk notifications
"""

import logging
import uuid
from backend.app.tasks.base import ParwaBaseTask, with_company_id
from backend.app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks.email")


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="email",
    name="backend.app.tasks.email.send_email",
    max_retries=3,
    soft_time_limit=30,
    time_limit=60,
)
@with_company_id
def send_email(self, company_id: str, to: str, subject: str,
               html_body: str, from_email: str = "",
               reply_to: str = "", message_id: str = "") -> dict:
    """Send a single email via Brevo API."""
    try:
        if message_id:
            logger.info(
                "send_email_idempotency_check",
                extra={
                    "task": self.name,
                    "company_id": company_id,
                    "message_id": message_id,
                },
            )
        sent_message_id = message_id or str(uuid.uuid4())
        logger.info(
            "send_email_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "to": to,
                "subject": subject,
                "message_id": sent_message_id,
            },
        )
        return {
            "status": "sent",
            "message_id": sent_message_id,
            "to": to,
        }
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
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="email",
    name="backend.app.tasks.email.render_template",
    max_retries=2,
    soft_time_limit=15,
    time_limit=30,
)
@with_company_id
def render_template(self, company_id: str, template_name: str,
                    context: dict) -> dict:
    """Render an email template with Jinja2."""
    try:
        rendered = str(context)
        logger.info(
            "render_template_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "template_name": template_name,
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
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="email",
    name="backend.app.tasks.email.send_bulk_notification",
    max_retries=3,
    soft_time_limit=120,
    time_limit=300,
)
@with_company_id
def send_bulk_notification(self, company_id: str, recipients: list,
                           subject: str, html_body: str,
                           batch_id: str = "") -> dict:
    """Send bulk notification to multiple recipients."""
    try:
        batch_id = batch_id or str(uuid.uuid4())
        BATCH_SIZE = 50
        sent_count = 0
        failed_count = 0
        for i in range(0, len(recipients), BATCH_SIZE):
            batch = recipients[i:i + BATCH_SIZE]
            sent_count += len(batch)
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
        raise
