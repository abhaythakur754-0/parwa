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

from backend.app.tasks.base import ParwaBaseTask, with_company_id
from backend.app.tasks.celery_app import app

logger = logging.getLogger("parwa.webhook_tasks")


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="webhook",
    name="backend.app.tasks.webhook_tasks.process_webhook_event",
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
        from backend.app.services.webhook_service import (
            get_webhook_event,
            mark_webhook_processed,
        )

        event = get_webhook_event(event_db_id)

        # Dispatch to provider-specific handler
        provider = event.get("provider", "")
        if provider == "paddle":
            _process_paddle_event(event)
        elif provider == "twilio":
            _process_twilio_event(event)
        elif provider == "brevo":
            _process_brevo_event(event)
        elif provider == "shopify":
            _process_shopify_event(event)
        else:
            logger.warning(
                "webhook_unknown_provider",
                provider=provider,
                event_db_id=event_db_id,
                company_id=company_id,
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
            from backend.app.services.webhook_service import (
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
    name="backend.app.tasks.webhook_tasks.process_paddle_webhook",
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
        from backend.app.services.webhook_service import (
            get_webhook_event,
            mark_webhook_processed,
        )

        event = get_webhook_event(event_db_id)
        _process_paddle_event(event)
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
            from backend.app.services.webhook_service import (
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
    name="backend.app.tasks.webhook_tasks.process_twilio_webhook",
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
        from backend.app.services.webhook_service import (
            get_webhook_event,
            mark_webhook_processed,
        )

        event = get_webhook_event(event_db_id)
        _process_twilio_event(event)
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
            from backend.app.services.webhook_service import (
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
    name="backend.app.tasks.webhook_tasks.process_brevo_webhook",
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
        from backend.app.services.webhook_service import (
            get_webhook_event,
            mark_webhook_processed,
        )

        event = get_webhook_event(event_db_id)
        _process_brevo_event(event)
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
            from backend.app.services.webhook_service import (
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
    name="backend.app.tasks.webhook_tasks.process_shopify_webhook",
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
        from backend.app.services.webhook_service import (
            get_webhook_event,
            mark_webhook_processed,
        )

        event = get_webhook_event(event_db_id)
        _process_shopify_event(event)
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
            from backend.app.services.webhook_service import (
                mark_webhook_processed,
            )
            mark_webhook_processed(
                event_db_id, status="failed",
                error=str(exc)[:500],
            )
        except Exception:
            pass


# ── Provider-specific event handlers (BC-003) ──────────────


def _process_paddle_event(event: dict):
    """Handle Paddle event types.

    Placeholder — actual business logic will be implemented
    in Week 5 (F-020 to F-027).
    """
    event_type = event.get("event_type", "")
    logger.info(
        "webhook_paddle_processed",
        event_id=event.get("event_id"),
        event_type=event_type,
        company_id=event.get("company_id"),
    )
    # Week 5 will add:
    # subscription.created -> create subscription record
    # payment.succeeded -> create invoice
    # subscription.cancelled -> cancel subscription


def _process_twilio_event(event: dict):
    """Handle Twilio SMS/voice event types.

    Placeholder — actual business logic will be implemented
    in Week 13 (F-126, F-127).
    """
    event_type = event.get("event_type", "")
    logger.info(
        "webhook_twilio_processed",
        event_id=event.get("event_id"),
        event_type=event_type,
        company_id=event.get("company_id"),
    )


def _process_brevo_event(event: dict):
    """Handle Brevo inbound email event types.

    Placeholder — actual business logic will be implemented
    in Week 6 (F-120 to F-124).
    """
    event_type = event.get("event_type", "")
    logger.info(
        "webhook_brevo_processed",
        event_id=event.get("event_id"),
        event_type=event_type,
        company_id=event.get("company_id"),
    )


def _process_shopify_event(event: dict):
    """Handle Shopify order event types.

    Placeholder — actual business logic will be implemented
    in Week 17 (F-131).
    """
    event_type = event.get("event_type", "")
    logger.info(
        "webhook_shopify_processed",
        event_id=event.get("event_id"),
        event_type=event_type,
        company_id=event.get("company_id"),
    )
