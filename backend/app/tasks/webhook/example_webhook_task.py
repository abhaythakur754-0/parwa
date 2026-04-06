"""
Example Webhook Task (Week 5 placeholder)

Paddle webhook processing task. Logs the event and marks
it as processed. Real implementation comes in Week 5.
"""

import logging

from backend.app.tasks.base import ParwaBaseTask

logger = logging.getLogger("parwa.webhook_tasks")


@ParwaBaseTask.bind(
    queue="webhook",
    max_retries=3,
)
def process_paddle_webhook(
    self, company_id: str, event_db_id: str,
):
    """Process a Paddle webhook event.

    This is a placeholder implementation that logs
    the event and marks it as processed.

    Real implementation comes in Week 5 with actual
    Paddle event handling logic.

    Args:
        company_id: Tenant company ID (BC-001).
        event_db_id: Webhook event database record ID.
    """
    logger.info(
        "paddle_webhook_processing",
        company_id=company_id,
        event_db_id=event_db_id,
    )

    try:
        from backend.app.services.webhook_service import (
            get_webhook_event,
            mark_webhook_processed,
        )

        event = get_webhook_event(event_db_id)
        logger.info(
            "paddle_webhook_event_loaded",
            event_type=event["event_type"],
            provider=event["provider"],
            company_id=company_id,
        )

        # Placeholder: mark as processed
        mark_webhook_processed(
            event_db_id, "processed",
        )

        logger.info(
            "paddle_webhook_processed",
            event_db_id=event_db_id,
            company_id=company_id,
        )
    except Exception as exc:
        logger.error(
            "paddle_webhook_failed",
            event_db_id=event_db_id,
            company_id=company_id,
            error=str(exc),
        )
        try:
            from backend.app.services.webhook_service import (
                mark_webhook_processed,
            )
            mark_webhook_processed(
                event_db_id, "failed",
                error=str(exc),
            )
        except Exception:
            logger.error(
                "paddle_webhook_mark_failed_error",
                event_db_id=event_db_id,
            )
        raise
