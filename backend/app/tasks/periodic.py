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

from app.tasks.base import ParwaBaseTask
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.periodic")


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.periodic.cleanup_stale_sessions",
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
    name="app.tasks.periodic.purge_dead_letter_queue",
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
        from app.tasks.celery_app import app as celery_app

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
    name="app.tasks.periodic.check_webhook_health",
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


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="analytics",
    name="app.tasks.periodic.flush_audit_queue",
    max_retries=1,
)
def flush_audit_queue(self):
    """Flush pending audit entries from Redis to the database.

    Pops entries from the Redis list ``parwa:audit:queue`` and
    batch-inserts them into the ``audit_trail`` table. Runs on the
    ``analytics`` queue to keep the default queue free for
    user-facing operations.

    If Redis or the database is temporarily unavailable, entries
    remain in the queue and will be retried on the next run
    (at-least-once delivery).

    BC-012: Audit failures must never break main operations.
    BC-004: Runs every 60 seconds via Celery Beat.
    """
    try:
        from app.services.audit_service import process_audit_queue

        result = process_audit_queue()
        logger.info("flush_audit_queue completed result=%s", result)
        return result
    except Exception as exc:
        logger.warning(
            "flush_audit_queue failed error=%s",
            exc,
        )
        return {"status": "failed", "error": str(exc)[:200]}


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.periodic.cleanup_audit_trail",
    max_retries=1,
)
def cleanup_audit_trail(self):
    """Daily cleanup of old audit trail entries.

    Deletes audit entries older than the configured retention period
    (default 365 days) for all tenants. Operates in batches to avoid
    long-running database transactions.

    BC-001: Operates across all tenants (no company_id filter).
    BC-004: Runs daily at 03:00 UTC via Celery Beat.
    """
    try:
        from app.services.audit_service import cleanup_old_audit_entries

        deleted = cleanup_old_audit_entries()
        logger.info(
            "cleanup_audit_trail completed deleted=%d",
            deleted,
        )
        return {"status": "ok", "deleted": deleted}
    except Exception as exc:
        logger.warning(
            "cleanup_audit_trail failed error=%s",
            exc,
        )
        return {"status": "failed", "error": str(exc)[:200]}


# ── Week 13 Day 3: Email Channel Periodic Tasks ─────────────────────


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="email",
    name="app.tasks.periodic.cleanup_expired_ooo_profiles",
    max_retries=1,
)
def cleanup_expired_ooo_profiles(self):
    """Hourly cleanup of expired OOO sender profiles.

    Resets active_ooo=false for profiles where ooo_until has passed.
    This ensures that follow-up emails resume after a customer's
    OOO period ends.

    BC-001: Scans across all tenants.
    BC-004: Runs hourly via Celery Beat.
    F-122: OOO detection Day 3 requirement.
    """
    try:
        from app.core.tenant_context import get_db_session
        from app.services.ooo_detection_service import OOODetectionService

        db = get_db_session()
        try:
            svc = OOODetectionService(db)
            cleaned = svc.cleanup_expired_profiles()
            logger.info(
                "cleanup_expired_ooo_profiles completed cleaned=%d",
                cleaned,
            )
            return {"status": "ok", "cleaned": cleaned}
        finally:
            db.close()
    except Exception as exc:
        logger.warning(
            "cleanup_expired_ooo_profiles failed error=%s",
            exc,
        )
        return {"status": "failed", "error": str(exc)[:200]}


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="email",
    name="app.tasks.periodic.retry_soft_bounces",
    max_retries=1,
)
def retry_soft_bounces(self):
    """Every 2 hours: retry soft-bounced emails that are due.

    Finds EmailDeliveryEvent records where event_type='soft_bounce',
    retry_count < max_retries, and next_retry_at <= now.
    For each, re-dispatches the original outbound email.

    BC-004: Runs every 2 hours via Celery Beat.
    F-124: Bounce handling Day 3 requirement.
    """
    try:
        from app.core.tenant_context import get_db_session
        from app.services.bounce_complaint_service import BounceComplaintService

        db = get_db_session()
        try:
            svc = BounceComplaintService(db)
            due_events = svc.get_soft_bounces_for_retry()
            retried = 0
            for event in due_events:
                try:
                    # Re-dispatch the original outbound email via Celery
                    from app.tasks.email_tasks import send_outbound_email
                    if event.outbound_email_id:
                        send_outbound_email.delay(
                            outbound_email_id=str(
                                event.outbound_email_id,
                            ),
                        )
                        retried += 1
                except Exception as retry_exc:
                    logger.warning(
                        "retry_soft_bounce_failed event_id=%s "
                        "error=%s",
                        str(event.id),
                        str(retry_exc)[:200],
                    )
            logger.info(
                "retry_soft_bounces completed due=%d retried=%d",
                len(due_events),
                retried,
            )
            return {
                "status": "ok",
                "due": len(due_events),
                "retried": retried,
            }
        finally:
            db.close()
    except Exception as exc:
        logger.warning(
            "retry_soft_bounces failed error=%s",
            exc,
        )
        return {"status": "failed", "error": str(exc)[:200]}


# ── Day 22: Beat Dispatchers ──────────────────────────────────────


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.periodic.approval_timeout_check",
    max_retries=1,
)
def dispatch_approval_timeout_check(self):
    """Dispatch approval timeout check across all companies."""
    try:
        from database.base import SessionLocal
        from database.models.core import Company
        db = SessionLocal()
        try:
            companies = db.query(Company).filter(
                Company.subscription_status == "active",
            ).all()
            dispatched = 0
            for company in companies:
                from app.tasks.approval_tasks import (
                    approval_timeout_check,
                )
                approval_timeout_check.delay(company.id)
                dispatched += 1
            logger.info(
                "dispatch_approval_timeout completed dispatched=%d",
                dispatched,
            )
            return {"status": "ok", "dispatched": dispatched}
        finally:
            db.close()
    except Exception as exc:
        logger.warning(
            "dispatch_approval_timeout failed error=%s", exc,
        )
        return {"status": "failed", "error": str(exc)[:200]}


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.periodic.approval_reminder_dispatch",
    max_retries=1,
)
def dispatch_approval_reminder(self):
    """Dispatch approval reminder across all companies."""
    try:
        from database.base import SessionLocal
        from database.models.core import Company
        db = SessionLocal()
        try:
            companies = db.query(Company).filter(
                Company.subscription_status == "active",
            ).all()
            dispatched = 0
            for company in companies:
                from app.tasks.approval_tasks import (
                    approval_reminder,
                )
                approval_reminder.delay(company.id)
                dispatched += 1
            logger.info(
                "dispatch_approval_reminder completed dispatched=%d",
                dispatched,
            )
            return {"status": "ok", "dispatched": dispatched}
        finally:
            db.close()
    except Exception as exc:
        logger.warning(
            "dispatch_approval_reminder failed error=%s", exc,
        )
        return {"status": "failed", "error": str(exc)[:200]}


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.periodic.daily_overage_charge",
    max_retries=1,
)
def dispatch_daily_overage(self):
    """Dispatch daily overage charge across all companies."""
    try:
        from database.base import SessionLocal
        from database.models.core import Company
        db = SessionLocal()
        try:
            companies = db.query(Company).filter(
                Company.subscription_status == "active",
            ).all()
            dispatched = 0
            for company in companies:
                from app.tasks.billing_tasks import (
                    daily_overage_charge,
                )
                daily_overage_charge.delay(company.id)
                dispatched += 1
            logger.info(
                "dispatch_daily_overage completed dispatched=%d",
                dispatched,
            )
            return {"status": "ok", "dispatched": dispatched}
        finally:
            db.close()
    except Exception as exc:
        logger.warning(
            "dispatch_daily_overage failed error=%s", exc,
        )
        return {"status": "failed", "error": str(exc)[:200]}


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="analytics",
    name="app.tasks.periodic.drift_detection_analysis",
    max_retries=1,
)
def dispatch_drift_detection(self):
    """Dispatch drift detection across all companies."""
    try:
        from database.base import SessionLocal
        from database.models.core import Company
        db = SessionLocal()
        try:
            companies = db.query(Company).filter(
                Company.subscription_status == "active",
            ).all()
            dispatched = 0
            for company in companies:
                from app.tasks.analytics_tasks import (
                    drift_detection,
                )
                drift_detection.delay(company.id)
                dispatched += 1
            logger.info(
                "dispatch_drift_detection completed dispatched=%d",
                dispatched,
            )
            return {"status": "ok", "dispatched": dispatched}
        finally:
            db.close()
    except Exception as exc:
        logger.warning(
            "dispatch_drift_detection failed error=%s", exc,
        )
        return {"status": "failed", "error": str(exc)[:200]}


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="analytics",
    name="app.tasks.periodic.metric_aggregation",
    max_retries=1,
)
def dispatch_metric_aggregation(self):
    """Dispatch metric aggregation across all companies."""
    try:
        from database.base import SessionLocal
        from database.models.core import Company
        db = SessionLocal()
        try:
            companies = db.query(Company).filter(
                Company.subscription_status == "active",
            ).all()
            dispatched = 0
            for company in companies:
                from app.tasks.analytics_tasks import (
                    aggregate_metrics,
                )
                aggregate_metrics.delay(
                    company.id, period="5min",
                )
                dispatched += 1
            logger.info(
                "dispatch_metric_aggregation completed dispatched=%d",
                dispatched,
            )
            return {"status": "ok", "dispatched": dispatched}
        finally:
            db.close()
    except Exception as exc:
        logger.warning(
            "dispatch_metric_aggregation failed error=%s", exc,
        )
        return {"status": "failed", "error": str(exc)[:200]}


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="training",
    name="app.tasks.periodic.training_mistake_check",
    max_retries=1,
)
def dispatch_training_mistake_check(self):
    """Dispatch training mistake threshold check."""
    try:
        from database.base import SessionLocal
        from database.models.core import Company
        db = SessionLocal()
        try:
            companies = db.query(Company).filter(
                Company.subscription_status == "active",
            ).all()
            dispatched = 0
            for company in companies:
                from app.tasks.training_tasks import (
                    check_mistake_threshold,
                )
                check_mistake_threshold.delay(company.id)
                dispatched += 1
            logger.info(
                "dispatch_training_mistake_check completed "
                "dispatched=%d",
                dispatched,
            )
            return {"status": "ok", "dispatched": dispatched}
        finally:
            db.close()
    except Exception as exc:
        logger.warning(
            "dispatch_training_mistake_check failed error=%s", exc,
        )
        return {"status": "failed", "error": str(exc)[:200]}
