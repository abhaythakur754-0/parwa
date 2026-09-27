"""
Celery task for running the PARWA pipeline on a ticket.

This task is consumed by the parwa-worker service (Celery worker).
The dispatcher sends a task with:
    celery_app.send_task(
        "parwa.run_pipeline_for_ticket",
        kwargs={"ticket_id": ..., "company_id": ..., "channel": ...},
    )

The worker picks it up and runs _run_pipeline_sync().
"""
from __future__ import annotations

import logging

from app.tasks.celery_app import app

logger = logging.getLogger("parwa.celery_tasks.pipeline")


@app.task(
    name="parwa.run_pipeline_for_ticket",
    queue="parwa_default",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    acks_late=True,
)
def run_pipeline_for_ticket(self, ticket_id: str, company_id: str, channel: str = "email"):
    """Run the 8-node PARWA pipeline on a ticket.

    This is the Celery entry point. The worker calls this when a ticket
    is dispatched via Celery. It runs the same _run_pipeline_sync()
    function that sync mode uses, but in the worker process instead
    of the web server process.

    Args:
        ticket_id: The ticket to process.
        company_id: Tenant ID for isolation (BC-001).
        channel: Ticket channel (email, chat, sms, voice).
    """
    from app.services.pipeline_dispatcher import _run_pipeline_sync

    logger.info(
        "celery_pipeline_task_started ticket_id=%s company_id=%s channel=%s",
        ticket_id, company_id, channel,
    )

    try:
        result = _run_pipeline_sync(ticket_id, company_id, channel)
        logger.info(
            "celery_pipeline_task_completed ticket_id=%s status=%s",
            ticket_id, result.get("status", "unknown"),
        )
        return result
    except Exception as exc:
        logger.error(
            "celery_pipeline_task_failed ticket_id=%s error=%s",
            ticket_id, str(exc)[:300],
        )
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=10 * (2 ** self.request.retries))
