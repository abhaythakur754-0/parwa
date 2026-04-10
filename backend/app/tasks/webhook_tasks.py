"""
Webhook Celery Tasks (BC-003, BC-004, BC-001)

Async webhook processing tasks dispatched by the webhook API.
All tasks inherit from ParwaBaseTask with company_id as first
parameter (BC-001) and route to the 'webhook' queue.

Tasks:
- process_webhook_event: Generic webhook processor
- process_paddle_webhook: Paddle-specific events
- process_twilio_webhook: Twilio SMS/voice events
- process_brevo_webhook: Brevo inbound email events
- process_shopify_webhook: Shopify order events
"""

import logging

from app.tasks.base import ParwaBaseTask, with_company_id
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.webhook_tasks")


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="webhook",
    name="app.tasks.webhook_tasks.process_webhook_event",
)
@with_company_id
def process_webhook_event(
    self, company_id: str, event_db_id: str,
):
    """Generic webhook event processor.

    Loads the webhook event from DB, dispatches to provider-specific
    handler based on provider field, and marks status on completion.

    Args:
        company_id: Tenant company ID (BC-001).
        event_db_id: Webhook event database record ID.
    """
    try:
        from app.services.webhook_service import (
            get_webhook_event,
            mark_webhook_processed,
        )

        event = get_webhook_event(event_db_id)

        # Dispatch to provider-specific handler via registry
        from app.webhooks import dispatch_event

        provider = event.get("provider", "")
        result = dispatch_event(provider, event)
        logger.info(
            "webhook_dispatched provider=%s status=%s",
            provider,
            result.get("status"),
            extra={
                "event_db_id": event_db_id,
                "company_id": company_id,
            },
        )

        mark_webhook_processed(
            event_db_id, status="processed",
        )
    except Exception as exc:
        logger.error(
            "webhook_task_failed",
            event_db_id=event_db_id,
            error=str(exc),
            company_id=company_id,
        )
        try:
            from app.services.webhook_service import (
                mark_webhook_processed,
            )
            mark_webhook_processed(
                event_db_id, status="failed",
                error=str(exc)[:500],
            )
        except Exception:
            pass


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="webhook",
    name="app.tasks.webhook_tasks.process_paddle_webhook",
)
@with_company_id
def process_paddle_webhook(
    self, company_id: str, event_db_id: str,
):
    """Process Paddle webhook event (subscription, payment).

    Args:
        company_id: Tenant company ID (BC-001).
        event_db_id: Webhook event database record ID.
    """
    try:
        from app.services.webhook_service import (
            get_webhook_event,
            mark_webhook_processed,
        )

        event = get_webhook_event(event_db_id)
        from app.webhooks import dispatch_event
        dispatch_event("paddle", event)
        mark_webhook_processed(
            event_db_id, status="processed",
        )
    except Exception as exc:
        logger.error(
            "webhook_paddle_failed",
            event_db_id=event_db_id,
            error=str(exc),
            company_id=company_id,
        )
        try:
            from app.services.webhook_service import (
                mark_webhook_processed,
            )
            mark_webhook_processed(
                event_db_id, status="failed",
                error=str(exc)[:500],
            )
        except Exception:
            pass


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="webhook",
    name="app.tasks.webhook_tasks.process_twilio_webhook",
)
@with_company_id
def process_twilio_webhook(
    self, company_id: str, event_db_id: str,
):
    """Process Twilio SMS/voice webhook event.

    Args:
        company_id: Tenant company ID (BC-001).
        event_db_id: Webhook event database record ID.
    """
    try:
        from app.services.webhook_service import (
            get_webhook_event,
            mark_webhook_processed,
        )

        event = get_webhook_event(event_db_id)
        from app.webhooks import dispatch_event
        dispatch_event("twilio", event)
        mark_webhook_processed(
            event_db_id, status="processed",
        )
    except Exception as exc:
        logger.error(
            "webhook_twilio_failed",
            event_db_id=event_db_id,
            error=str(exc),
            company_id=company_id,
        )
        try:
            from app.services.webhook_service import (
                mark_webhook_processed,
            )
            mark_webhook_processed(
                event_db_id, status="failed",
                error=str(exc)[:500],
            )
        except Exception:
            pass


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="webhook",
    name="app.tasks.webhook_tasks.process_brevo_webhook",
)
@with_company_id
def process_brevo_webhook(
    self, company_id: str, event_db_id: str,
):
    """Process Brevo inbound email webhook event.

    Args:
        company_id: Tenant company ID (BC-001).
        event_db_id: Webhook event database record ID.
    """
    try:
        from app.services.webhook_service import (
            get_webhook_event,
            mark_webhook_processed,
        )

        event = get_webhook_event(event_db_id)
        from app.webhooks import dispatch_event
        dispatch_event("brevo", event)
        mark_webhook_processed(
            event_db_id, status="processed",
        )
    except Exception as exc:
        logger.error(
            "webhook_brevo_failed",
            event_db_id=event_db_id,
            error=str(exc),
            company_id=company_id,
        )
        try:
            from app.services.webhook_service import (
                mark_webhook_processed,
            )
            mark_webhook_processed(
                event_db_id, status="failed",
                error=str(exc)[:500],
            )
        except Exception:
            pass


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="webhook",
    name="app.tasks.webhook_tasks.process_shopify_webhook",
)
@with_company_id
def process_shopify_webhook(
    self, company_id: str, event_db_id: str,
):
    """Process Shopify order webhook event.

    Args:
        company_id: Tenant company ID (BC-001).
        event_db_id: Webhook event database record ID.
    """
    try:
        from app.services.webhook_service import (
            get_webhook_event,
            mark_webhook_processed,
        )

        event = get_webhook_event(event_db_id)
        from app.webhooks import dispatch_event
        dispatch_event("shopify", event)
        mark_webhook_processed(
            event_db_id, status="processed",
        )
    except Exception as exc:
        logger.error(
            "webhook_shopify_failed",
            event_db_id=event_db_id,
            error=str(exc),
            company_id=company_id,
        )
        try:
            from app.services.webhook_service import (
                mark_webhook_processed,
            )
            mark_webhook_processed(
                event_db_id, status="failed",
                error=str(exc)[:500],
            )
        except Exception:
            pass


# ── Provider handlers now use registry (Day 23) ──────────
# Import handlers to register them with the registry.
# Actual processing is in backend.app.webhooks.{provider}_handler
import app.webhooks.paddle_handler  # noqa: E402, F401
import app.webhooks.brevo_handler  # noqa: E402, F401
import app.webhooks.twilio_handler  # noqa: E402, F401
import app.webhooks.shopify_handler  # noqa: E402, F401
