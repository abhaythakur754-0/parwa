"""
Webhook Recovery Tasks (BG-15, W5D5)

Celery tasks for detecting and recovering missed webhooks.
These tasks ensure no webhook events are lost due to:
- Network failures
- Server downtime
- Transient errors

Tasks:
- recover_missed_webhooks: Periodic check for missed Paddle events
- process_stuck_webhooks: Retry events stuck in pending/processing
- cleanup_idempotency_keys: Remove expired idempotency keys
- cleanup_webhook_sequences: Remove old processed sequences
"""

import logging
from datetime import datetime, timedelta, timezone

from backend.app.tasks.base import ParwaBaseTask, with_company_id
from backend.app.tasks.celery_app import app

logger = logging.getLogger("parwa.webhook_recovery")


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="webhook",
    name="backend.app.tasks.webhook_recovery.recover_missed_webhooks",
)
def recover_missed_webhooks(self):
    """
    Periodic task to recover missed Paddle webhooks.

    Runs every hour. For each active subscription:
    1. Call Paddle API to get recent events
    2. Compare with webhook_sequences table
    3. Process any missing events

    This ensures no events are lost due to downtime or network issues.
    """
    logger.info("webhook_recovery_started")

    recovered_count = 0
    error_count = 0

    try:
        # Get all companies with active subscriptions
        from database.base import SessionLocal
        from database.models.core import Company

        db = SessionLocal()
        try:
            companies = db.query(Company).filter(
                Company.subscription_status.in_(["active", "past_due", "paused"]),
                Company.paddle_subscription_id.isnot(None),
            ).all()

            logger.info(
                "webhook_recovery_companies_found count=%d",
                len(companies),
            )

            for company in companies:
                try:
                    recovered = _recover_company_webhooks(
                        company.id,
                        company.paddle_subscription_id,
                    )
                    recovered_count += recovered

                except Exception as e:
                    error_count += 1
                    logger.error(
                        "webhook_recovery_company_failed company_id=%s error=%s",
                        company.id, str(e),
                    )

        finally:
            db.close()

        logger.info(
            "webhook_recovery_completed recovered=%d errors=%d",
            recovered_count, error_count,
        )

        return {
            "recovered": recovered_count,
            "errors": error_count,
        }

    except Exception as e:
        logger.error("webhook_recovery_failed error=%s", str(e))
        raise


def _recover_company_webhooks(company_id: str, subscription_id: str) -> int:
    """
    Recover missed webhooks for a specific company.

    Returns count of recovered events.
    """
    from backend.app.services.webhook_ordering_service import (
        get_or_create_webhook_sequence,
        get_pending_events_ordered,
        mark_sequence_processing,
        mark_sequence_processed,
        mark_sequence_failed,
    )
    from backend.app.clients.paddle_client import get_paddle_client
    from database.base import SessionLocal
    from database.models.billing_extended import WebhookSequence

    db = SessionLocal()
    recovered = 0

    try:
        # Get recent events from Paddle
        paddle = get_paddle_client()

        try:
            # Try to fetch events from Paddle API
            # Note: This requires the Paddle client to have event listing capability
            events = paddle.list_subscription_events(subscription_id)
        except Exception as e:
            logger.warning(
                "webhook_recovery_paddle_error company_id=%s error=%s",
                company_id, str(e),
            )
            # Fall back to processing stuck events
            events = []

        # Check which events we're missing
        for event in events:
            event_id = event.get("event_id") or event.get("id")

            if not event_id:
                continue

            # Check if we have this event
            existing = db.query(WebhookSequence).filter(
                WebhookSequence.paddle_event_id == event_id,
            ).first()

            if not existing:
                # We missed this event - process it
                logger.info(
                    "webhook_recovery_missing_event event_id=%s company_id=%s",
                    event_id, company_id,
                )

                # Create sequence record and process
                _process_recovered_event(company_id, event)
                recovered += 1

    except Exception as e:
        logger.error(
            "webhook_recovery_company_error company_id=%s error=%s",
            company_id, str(e),
        )
    finally:
        db.close()

    return recovered


def _process_recovered_event(company_id: str, event: dict) -> None:
    """Process a recovered webhook event."""
    from backend.app.services.webhook_ordering_service import (
        get_or_create_webhook_sequence,
        mark_sequence_processing,
        mark_sequence_processed,
        mark_sequence_failed,
    )
    from backend.app.webhooks.paddle_handler import handle_paddle_event

    event_id = event.get("event_id") or event.get("id")
    event_type = event.get("event_type")
    occurred_at_str = event.get("occurred_at")

    # Parse occurred_at
    try:
        occurred_at = datetime.fromisoformat(occurred_at_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        occurred_at = datetime.now(timezone.utc)

    # Create sequence record
    sequence = get_or_create_webhook_sequence(
        paddle_event_id=event_id,
        event_type=event_type,
        occurred_at=occurred_at,
        company_id=company_id,
    )

    if sequence.status == "processed":
        return  # Already done

    # Mark as processing
    mark_sequence_processing(sequence.id)

    try:
        # Format event for handler
        formatted_event = {
            "event_id": event_id,
            "event_type": event_type,
            "company_id": company_id,
            "payload": event,
            "occurred_at": occurred_at,
        }

        # Process via handler
        result = handle_paddle_event(formatted_event)

        if result.get("status") == "processed":
            mark_sequence_processed(sequence.id)
            logger.info(
                "webhook_recovery_processed event_id=%s company_id=%s",
                event_id, company_id,
            )
        else:
            mark_sequence_failed(sequence.id, result.get("error", "Unknown error"))

    except Exception as e:
        mark_sequence_failed(sequence.id, str(e))
        logger.error(
            "webhook_recovery_process_failed event_id=%s error=%s",
            event_id, str(e),
        )


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="webhook",
    name="backend.app.tasks.webhook_recovery.process_stuck_webhooks",
)
def process_stuck_webhooks(self):
    """
    Retry webhook events stuck in pending or processing state.

    Runs every 30 minutes. Finds events that have been stuck
    for more than 1 hour and retries them.
    """
    logger.info("stuck_webhooks_processing_started")

    from backend.app.services.webhook_ordering_service import (
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
    name="backend.app.tasks.webhook_recovery.cleanup_idempotency_keys",
)
def cleanup_idempotency_keys(self):
    """
    Delete expired idempotency keys.

    Runs daily at 00:00. Removes keys that have expired
    to keep the table size manageable.
    """
    logger.info("idempotency_cleanup_started")

    from backend.app.services.webhook_processor import cleanup_expired_idempotency_keys

    deleted = cleanup_expired_idempotency_keys()

    logger.info("idempotency_cleanup_completed deleted=%d", deleted)

    return {"deleted": deleted}


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="webhook",
    name="backend.app.tasks.webhook_recovery.cleanup_webhook_sequences",
)
def cleanup_webhook_sequences(self):
    """
    Delete old processed webhook sequences.

    Runs weekly. Removes sequences older than 30 days
    that have been successfully processed.
    """
    logger.info("sequence_cleanup_started")

    from backend.app.services.webhook_ordering_service import cleanup_old_sequences

    deleted = cleanup_old_sequences(days=30)

    logger.info("sequence_cleanup_completed deleted=%d", deleted)

    return {"deleted": deleted}


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="webhook",
    name="backend.app.tasks.webhook_recovery.process_pending_events",
)
@with_company_id
def process_pending_events(self, company_id: str):
    """
    Process all pending webhook events for a company.

    This ensures events are processed in the correct order.

    Args:
        company_id: The company ID to process events for
    """
    logger.info("pending_events_processing_started company_id=%s", company_id)

    from backend.app.services.webhook_ordering_service import (
        get_pending_events_ordered,
        mark_sequence_processing,
        mark_sequence_processed,
        mark_sequence_failed,
        get_next_processing_order,
    )
    from backend.app.webhooks.paddle_handler import handle_paddle_event

    events = get_pending_events_ordered(company_id)
    processed_count = 0

    for sequence in events:
        try:
            # Mark as processing
            mark_sequence_processing(sequence.id)

            # Parse event data
            event_data = {
                "event_id": sequence.paddle_event_id,
                "event_type": sequence.event_type,
                "company_id": company_id,
                "occurred_at": sequence.occurred_at,
            }

            # Process
            result = handle_paddle_event(event_data)

            if result.get("status") == "processed":
                order = get_next_processing_order(company_id)
                mark_sequence_processed(sequence.id, order)
                processed_count += 1
            else:
                mark_sequence_failed(sequence.id, result.get("error", "Unknown error"))

        except Exception as e:
            mark_sequence_failed(sequence.id, str(e))
            logger.error(
                "pending_event_process_failed sequence_id=%s error=%s",
                sequence.id, str(e),
            )

    logger.info(
        "pending_events_processing_completed company_id=%s processed=%d",
        company_id, processed_count,
    )

    return {"processed": processed_count}
