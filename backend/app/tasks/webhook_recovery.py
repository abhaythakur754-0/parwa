"""
Webhook Recovery Tasks (BG-15, W5D5)

Celery tasks for detecting and recovering missed webhooks.
These tasks ensure no webhook events are lost due to:
- Network failures
- Server downtime
- Transient errors

Tasks:
- recover_missed_webhooks: No-op (Paddle was removed; Razorpay webhooks are now handled inline)
- process_stuck_webhooks: Retry events stuck in pending/processing
- cleanup_idempotency_keys: Remove expired idempotency keys
- cleanup_webhook_sequences: Remove old processed sequences
- process_pending_events: No-op (Paddle was removed)
"""

import logging
from datetime import datetime, timedelta, timezone

from app.tasks.base_task import ParwaBaseTask, with_company_id
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.webhook_recovery")


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="webhook",
    name="app.tasks.webhook_recovery.recover_missed_webhooks",
)
def recover_missed_webhooks(self):
    """
    Periodic task to recover missed webhooks.

    NOTE: Paddle was removed; Razorpay webhooks are now handled inline
    by the Razorpay webhook handler. There is no external event-list API
    to poll, so this task is a no-op kept for scheduler compatibility.
    """
    logger.info(
        "webhook_recovery_skipped reason=Paddle was removed"
    )
    return {
        "status": "skipped",
        "reason": "Paddle was removed",
        "recovered": 0,
        "errors": 0,
    }


def _recover_company_webhooks(company_id: str, subscription_id: str) -> int:
    """
    Recover missed webhooks for a specific company.

    NOTE: Paddle was removed; this is now a no-op. Returns 0.
    """
    logger.info(
        "webhook_recovery_company_skipped company_id=%s reason=Paddle was removed",
        company_id,
    )
    return 0


def _process_recovered_event(company_id: str, event: dict) -> None:
    """
    Process a recovered webhook event.

    NOTE: Paddle was removed; this is now a no-op (the paddle_handler has
    been deleted). Kept for backward-compat external callers.
    """
    logger.info(
        "webhook_recovery_event_skipped company_id=%s reason=Paddle was removed",
        company_id,
    )
    return None


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="webhook",
    name="app.tasks.webhook_recovery.process_stuck_webhooks",
)
def process_stuck_webhooks(self):
    """
    Retry webhook events stuck in pending or processing state.

    Runs every 30 minutes. Finds events that have been stuck
    for more than 1 hour and retries them.
    """
    logger.info("stuck_webhooks_processing_started")

    from app.services.webhook_ordering_service import (
        get_stuck_events,
        retry_stuck_event,
    )

    stuck = get_stuck_events(max_age_hours=1)
    retried_count = 0

    for event in stuck:
        try:
            retry_stuck_event(event["id"])
            retried_count += 1

            logger.info(
                "stuck_webhook_retried sequence_id=%s event_type=%s",
                event["id"], event["event_type"],
            )

        except Exception as e:
            logger.error(
                "stuck_webhook_retry_failed sequence_id=%s error=%s",
                event["id"], str(e),
            )

    logger.info(
        "stuck_webhooks_processing_completed stuck=%d retried=%d",
        len(stuck), retried_count,
    )

    return {
        "stuck_found": len(stuck),
        "retried": retried_count,
    }


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="webhook",
    name="app.tasks.webhook_recovery.cleanup_idempotency_keys",
)
def cleanup_idempotency_keys(self):
    """
    Delete expired idempotency keys.

    Runs daily at 00:00. Removes keys that have expired
    to keep the table size manageable.
    """
    logger.info("idempotency_cleanup_started")

    from app.services.webhook_processor import cleanup_expired_idempotency_keys

    deleted = cleanup_expired_idempotency_keys()

    logger.info("idempotency_cleanup_completed deleted=%d", deleted)

    return {"deleted": deleted}


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="webhook",
    name="app.tasks.webhook_recovery.cleanup_webhook_sequences",
)
def cleanup_webhook_sequences(self):
    """
    Delete old processed webhook sequences.

    Runs weekly. Removes sequences older than 30 days
    that have been successfully processed.
    """
    logger.info("sequence_cleanup_started")

    from app.services.webhook_ordering_service import cleanup_old_sequences

    deleted = cleanup_old_sequences(days=30)

    logger.info("sequence_cleanup_completed deleted=%d", deleted)

    return {"deleted": deleted}


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="webhook",
    name="app.tasks.webhook_recovery.process_pending_events",
)
@with_company_id
def process_pending_events(self, company_id: str):
    """
    Process all pending webhook events for a company.

    NOTE: Paddle was removed; the paddle_handler has been deleted. This
    task is a no-op kept for scheduler compatibility. Razorpay webhook
    events are processed inline by the Razorpay webhook handler.

    Args:
        company_id: The company ID to process events for
    """
    logger.info(
        "pending_events_processing_skipped company_id=%s reason=Paddle was removed",
        company_id,
    )
    return {
        "status": "skipped",
        "reason": "Paddle was removed",
        "processed": 0,
    }
