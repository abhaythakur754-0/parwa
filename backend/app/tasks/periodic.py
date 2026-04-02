"""
PARWA Periodic Tasks (Day 16, BC-004)

Scheduled tasks executed by Celery Beat:
- cleanup_stale_sessions: Daily cleanup of expired user sessions
- purge_dead_letter_queue: Hourly cleanup of DLQ (tasks > 7 days)
- check_webhook_health: Every 5 min — check for stale pending webhooks

BC-004: All tasks use ParwaBaseTask with retry config.
"""

import logging
from datetime import datetime, timezone

from backend.app.tasks.base import ParwaBaseTask
from backend.app.tasks.celery_app import app

logger = logging.getLogger("parwa.periodic")


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="backend.app.tasks.periodic.cleanup_stale_sessions",
    max_retries=1,
)
def cleanup_stale_sessions(self):
    """Daily cleanup of stale user sessions.

    Removes sessions older than MAX_SESSIONS_PER_USER's refresh
    token expiry (7 days). Keeps only the most recent sessions
    per user.

    BC-001: Scans across all tenants.
    BC-004: Runs daily via Celery Beat.
    """
    try:
        from database.base import SessionLocal
        db = SessionLocal()
        try:
            # FIX L40: Cutoff should be 7 days ago, NOT now()
            # Previous bug would delete ALL sessions immediately
            from datetime import timedelta
            from sqlalchemy import text
            cutoff = datetime.now(timezone.utc) - timedelta(
                days=7,
            )
            # Delete sessions where updated_at is older than 7 days
            result = db.execute(
                text("DELETE FROM sessions WHERE updated_at < :cutoff"),
                {"cutoff": cutoff},
            )
            deleted = result.rowcount
            db.commit()
            logger.info(
                "cleanup_stale_sessions completed deleted=%d",
                deleted,
            )
            return {"status": "ok", "deleted": deleted}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as exc:
        logger.warning(
            "cleanup_stale_sessions failed error=%s",
            exc,
        )
        # Return gracefully — this is a background task
        return {"status": "failed", "error": str(exc)[:200]}


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="backend.app.tasks.periodic.purge_dead_letter_queue",
    max_retries=1,
)
def purge_dead_letter_queue(self):
    """Hourly cleanup of dead letter queue.

    Purges completed/failed tasks from the result backend
    that are older than 7 days. This prevents Redis memory
    bloat from accumulated task results.

    BC-004: Runs hourly via Celery Beat.
    """
    try:
        from backend.app.tasks.celery_app import app as celery_app

        # Clean up old task results from result backend
        backend = celery_app.backend
        if hasattr(backend, 'cleanup'):
            backend.cleanup()
            logger.info("dead_letter_queue purged")
        else:
            # Manual cleanup: delete old results
            try:
                backend.delete_expired(86400 * 7)  # 7 days
                logger.info("dead_letter_queue expired results deleted")
            except (AttributeError, NotImplementedError):
                logger.info(
                    "dead_letter_queue purge skipped "
                    "(backend does not support delete_expired)"
                )

        return {"status": "ok"}
    except Exception as exc:
        logger.warning(
            "purge_dead_letter_queue failed error=%s",
            exc,
        )
        return {"status": "failed", "error": str(exc)[:200]}


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="webhook",
    name="backend.app.tasks.periodic.check_webhook_health",
    max_retries=1,
)
def check_webhook_health(self):
    """Check for stale pending webhook events.

    Finds webhook events that have been in 'pending' status
    for more than 30 minutes and logs a warning. These may
    indicate a stuck Celery worker or processing issue.

    BC-003: Webhook events should not stay pending for long.
    BC-004: Runs every 5 minutes via Celery Beat.
    """
    try:
        from database.base import SessionLocal
        from database.models.webhook_event import WebhookEvent
        from datetime import datetime, timezone, timedelta

        db = SessionLocal()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(
                minutes=30,
            )
            stale_events = db.query(WebhookEvent).filter(
                WebhookEvent.status == "pending",
                WebhookEvent.created_at < cutoff,
            ).count()

            if stale_events > 0:
                logger.warning(
                    "check_webhook_health stale_events=%d",
                    stale_events,
                )
            else:
                logger.info(
                    "check_webhook_health all_clear",
                )

            return {
                "status": "ok",
                "stale_pending_events": stale_events,
            }
        finally:
            db.close()
    except Exception as exc:
        logger.warning(
            "check_webhook_health failed error=%s",
            exc,
        )
        return {"status": "failed", "error": str(exc)[:200]}
