"""
PARWA Example Tasks (BC-004)

Skeleton tasks to verify Celery infrastructure works.
These will be fleshed out in later days:
- send_welcome_email_task → BC-006 (Email)
- process_webhook_task → BC-003 (Webhooks)
- calculate_analytics_task → Analytics reporting

BC-001: Every task's first parameter is company_id.
"""

import logging

from app.tasks.base import ParwaBaseTask, with_company_id
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks")


@app.task(
    base=ParwaBaseTask,
    name="app.tasks.email.send_welcome_email",
    queue="email",
    bind=True,
)
@with_company_id
def send_welcome_email_task(
    self, company_id: str, user_email: str, user_name: str,
) -> dict:
    """Send welcome email to a new user (BC-006 skeleton).

    Args:
        company_id: Tenant identifier (BC-001).
        user_email: Recipient email address.
        user_name: Recipient display name.

    Returns:
        Dict with task result status.
    """
    logger.info(
        "send_welcome_email_task",
        extra={
            "company_id": company_id,
            "user_email": user_email,
            "user_name": user_name,
        },
    )
    # TODO: Implement actual email sending (BC-006)
    return {
        "status": "skipped",
        "message": "Email task skeleton — not yet implemented",
        "company_id": company_id,
    }


@app.task(
    base=ParwaBaseTask,
    name="app.tasks.webhook.process_webhook",
    queue="webhook",
    bind=True,
)
@with_company_id
def process_webhook_task(
    self, company_id: str, event_type: str, payload: dict,
) -> dict:
    """Process an incoming webhook event (BC-003 skeleton).

    Args:
        company_id: Tenant identifier (BC-001).
        event_type: Webhook event type (e.g. "payment.completed").
        payload: Webhook payload data.

    Returns:
        Dict with task result status.
    """
    logger.info(
        "process_webhook_task",
        extra={
            "company_id": company_id,
            "event_type": event_type,
        },
    )
    # TODO: Implement actual webhook processing (BC-003)
    return {
        "status": "skipped",
        "message": "Webhook task skeleton — not yet implemented",
        "company_id": company_id,
        "event_type": event_type,
    }


@app.task(
    base=ParwaBaseTask,
    name="app.tasks.analytics.calculate_analytics",
    queue="analytics",
    bind=True,
)
@with_company_id
def calculate_analytics_task(
    self, company_id: str, metric_type: str,
) -> dict:
    """Calculate analytics for a company (skeleton).

    Args:
        company_id: Tenant identifier (BC-001).
        metric_type: Type of metric to calculate.

    Returns:
        Dict with task result status.
    """
    logger.info(
        "calculate_analytics_task",
        extra={
            "company_id": company_id,
            "metric_type": metric_type,
        },
    )
    # TODO: Implement actual analytics calculation
    return {
        "status": "skipped",
        "message": "Analytics task skeleton — not yet implemented",
        "company_id": company_id,
        "metric_type": metric_type,
    }
