"""
PARWA Event Tasks (BC-004, BC-005)

Celery tasks for asynchronous event emission with:
- Fan-out to multiple tenants or users
- Retry with exponential backoff
- Dead letter queue routing
- company_id as first parameter (BC-004)
"""

from typing import Any, Dict, List, Optional

from backend.app.logger import get_logger
from backend.app.tasks.base import ParwaBaseTask, with_company_id
from backend.app.tasks.celery_app import app as celery_app

logger = get_logger("event_tasks")


@celery_app.task(
    base=ParwaBaseTask,
    queue="default",
    max_retries=3,
    acks_late=True,
    reject_on_worker_lost=True,
)
@with_company_id
def fanout_event_task(
    company_id: str,
    event_type: str,
    payload: Dict[str, Any],
    target_user_ids: Optional[List[str]] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Fan-out an event to a tenant's connected clients.

    Uses async event emission via the event emitter.
    Runs in the default queue for immediate processing.

    Args:
        company_id: Tenant identifier (BC-004 first param).
        event_type: Registered event type.
        payload: Event data.
        target_user_ids: Optional list of user IDs to target.
        correlation_id: Optional trace ID.

    Returns:
        Dict with success status and metadata.
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()

    async def _emit():
        from backend.app.core.event_emitter import emit_event

        if target_user_ids:
            for uid in target_user_ids:
                await emit_event(
                    company_id=company_id,
                    event_type=event_type,
                    payload={**payload, "target_user_id": uid},
                    correlation_id=correlation_id,
                )
        else:
            await emit_event(
                company_id=company_id,
                event_type=event_type,
                payload=payload,
                correlation_id=correlation_id,
            )

    try:
        loop.run_until_complete(_emit())
        return {
            "status": "emitted",
            "company_id": company_id,
            "event_type": event_type,
            "target_count": len(target_user_ids) if target_user_ids else 1,
        }
    except Exception as exc:
        logger.error(
            "fanout_event_failed",
            company_id=company_id,
            event_type=event_type,
            error=str(exc),
        )
        raise fanout_event_task.retry(exc=exc, countdown=2 ** fanout_event_task.request.retries)


@celery_app.task(
    base=ParwaBaseTask,
    queue="default",
    max_retries=2,
    acks_late=True,
)
@with_company_id
def cleanup_event_buffer_task(company_id: str) -> Dict[str, Any]:
    """Periodic cleanup of old events from the event buffer.

    BC-005: Event buffer retention is 24 hours.

    Args:
        company_id: Tenant identifier (BC-004 first param).

    Returns:
        Dict with cleanup results.
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()

    async def _cleanup():
        from backend.app.core.event_buffer import cleanup_old_events
        return await cleanup_old_events(company_id)

    try:
        removed = loop.run_until_complete(_cleanup())
        return {
            "status": "cleaned",
            "company_id": company_id,
            "events_removed": removed,
        }
    except Exception as exc:
        logger.error(
            "event_buffer_cleanup_failed",
            company_id=company_id,
            error=str(exc),
        )
        return {"status": "error", "company_id": company_id, "error": str(exc)}
