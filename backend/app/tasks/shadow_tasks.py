"""
PARWA Shadow Mode Queue Processing Tasks

Celery tasks for processing pending shadow queue items across channels
(email, SMS, chat). Handles:
  - Processing approved actions (dispatching to channel services)
  - Processing rejected actions (cleanup + notifications)
  - Auto-executing low-risk graduated-mode actions
  - Periodic cleanup of expired queued items
  - Undo processing for auto-approved actions

BC-001: All operations scoped by company_id.
BC-008: Never crash the caller — defensive error handling.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from app.tasks.celery_app import app as celery_app

logger = logging.getLogger("parwa.tasks.shadow")


# ── Task: Process approved email action ─────────────────────────────────────


@celery_app.task(
    name="app.tasks.shadow.process_approved_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def process_approved_email(self, shadow_log_id: str, company_id: str) -> Dict[str, Any]:
    """
    Process an approved email action from the shadow queue.

    Retrieves the shadow log entry, extracts the email payload,
    and sends it via the email service.

    Args:
        shadow_log_id: UUID of the shadow log entry.
        company_id: Company UUID (BC-001).

    Returns:
        Dict with processing result.
    """
    try:
        from database.base import SessionLocal
        from database.models.shadow_mode import ShadowLog

        with SessionLocal() as db:
            entry = (
                db.query(ShadowLog)
                .filter(
                    ShadowLog.id == shadow_log_id,
                    ShadowLog.company_id == company_id,
                )
                .first()
            )

            if not entry:
                return {"status": "error", "error": "Shadow log entry not found"}

            if entry.manager_decision != "approved":
                return {"status": "skipped", "reason": f"Entry is {
                        entry.manager_decision}"}

            payload = entry.action_payload or {}

            # Delegate to the email shadow interceptor's approval processor
            from app.interceptors.email_shadow import _execute_email_action

            result = _execute_email_action(
                company_id=company_id,
                email_payload=payload,
                shadow_log_id=shadow_log_id,
            )

            return {
                "status": "completed",
                "shadow_log_id": shadow_log_id,
                "company_id": company_id,
                "action_type": "email_reply",
                "result": result.get("status"),
            }

    except Exception as e:
        logger.error(
            "shadow_email_process_failed shadow_id=%s error=%s",
            shadow_log_id,
            str(e),
            exc_info=True,
        )
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


# ── Task: Process approved SMS action ───────────────────────────────────────


@celery_app.task(
    name="app.tasks.shadow.process_approved_sms",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def process_approved_sms(self, shadow_log_id: str, company_id: str) -> Dict[str, Any]:
    """
    Process an approved SMS action from the shadow queue.

    Args:
        shadow_log_id: UUID of the shadow log entry.
        company_id: Company UUID (BC-001).

    Returns:
        Dict with processing result.
    """
    try:
        from database.base import SessionLocal
        from database.models.shadow_mode import ShadowLog

        with SessionLocal() as db:
            entry = (
                db.query(ShadowLog)
                .filter(
                    ShadowLog.id == shadow_log_id,
                    ShadowLog.company_id == company_id,
                )
                .first()
            )

            if not entry:
                return {"status": "error", "error": "Shadow log entry not found"}

            if entry.manager_decision != "approved":
                return {"status": "skipped", "reason": f"Entry is {
                        entry.manager_decision}"}

            payload = entry.action_payload or {}

            from app.interceptors.sms_shadow import _execute_sms_action

            result = _execute_sms_action(
                company_id=company_id,
                sms_payload=payload,
                shadow_log_id=shadow_log_id,
            )

            return {
                "status": "completed",
                "shadow_log_id": shadow_log_id,
                "company_id": company_id,
                "action_type": "sms_reply",
                "result": result.get("status"),
            }

    except Exception as e:
        logger.error(
            "shadow_sms_process_failed shadow_id=%s error=%s",
            shadow_log_id,
            str(e),
            exc_info=True,
        )
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


# ── Task: Process approved voice action ─────────────────────────────────────


@celery_app.task(
    name="app.tasks.shadow.process_approved_voice",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def process_approved_voice(self, shadow_log_id: str, company_id: str) -> Dict[str, Any]:
    """
    Process an approved voice/TTS action from the shadow queue.

    Args:
        shadow_log_id: UUID of the shadow log entry.
        company_id: Company UUID (BC-001).

    Returns:
        Dict with processing result.
    """
    try:
        from database.base import SessionLocal
        from database.models.shadow_mode import ShadowLog

        with SessionLocal() as db:
            entry = (
                db.query(ShadowLog)
                .filter(
                    ShadowLog.id == shadow_log_id,
                    ShadowLog.company_id == company_id,
                )
                .first()
            )

            if not entry:
                return {"status": "error", "error": "Shadow log entry not found"}

            if entry.manager_decision != "approved":
                return {"status": "skipped", "reason": f"Entry is {
                        entry.manager_decision}"}

            payload = entry.action_payload or {}

            from app.interceptors.voice_shadow import _execute_voice_action

            result = _execute_voice_action(
                company_id=company_id,
                voice_payload=payload,
                shadow_log_id=shadow_log_id,
            )

            return {
                "status": "completed",
                "shadow_log_id": shadow_log_id,
                "company_id": company_id,
                "action_type": "voice_reply",
                "result": result.get("status"),
            }

    except Exception as e:
        logger.error(
            "shadow_voice_process_failed shadow_id=%s error=%s",
            shadow_log_id,
            str(e),
            exc_info=True,
        )
        raise self.retry(exc=e, countdown=30 * (self.request.retries + 1))


# ── Task: Dispatch approved action by type ───────────────────────────────────


@celery_app.task(
    name="app.tasks.shadow.dispatch_approved_action",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def dispatch_approved_action(
    self, shadow_log_id: str, company_id: str
) -> Dict[str, Any]:
    """
    Dispatch an approved shadow action to the appropriate channel processor.

    Looks up the action_type from the shadow log entry and routes to
    the correct channel-specific task (email, SMS, voice, chat).

    Args:
        shadow_log_id: UUID of the shadow log entry.
        company_id: Company UUID (BC-001).

    Returns:
        Dict with dispatch result.
    """
    try:
        from database.base import SessionLocal
        from database.models.shadow_mode import ShadowLog

        with SessionLocal() as db:
            entry = (
                db.query(ShadowLog)
                .filter(
                    ShadowLog.id == shadow_log_id,
                    ShadowLog.company_id == company_id,
                )
                .first()
            )

            if not entry:
                return {"status": "error", "error": "Shadow log entry not found"}

            action_type = entry.action_type

            # Route to the appropriate channel task
            channel_tasks = {
                "email_reply": process_approved_email,
                "sms_reply": process_approved_sms,
                "voice_reply": process_approved_voice,
            }

            task_func = channel_tasks.get(action_type)
            if task_func:
                task_func.delay(shadow_log_id, company_id)
                return {
                    "status": "dispatched",
                    "shadow_log_id": shadow_log_id,
                    "action_type": action_type,
                    "company_id": company_id,
                }
            else:
                logger.warning(
                    "shadow_dispatch_unknown_action_type shadow_id=%s type=%s",
                    shadow_log_id,
                    action_type,
                )
                return {
                    "status": "skipped",
                    "shadow_log_id": shadow_log_id,
                    "reason": f"No handler for action type: {action_type}",
                }

    except Exception as e:
        logger.error(
            "shadow_dispatch_failed shadow_id=%s error=%s",
            shadow_log_id,
            str(e),
            exc_info=True,
        )
        raise self.retry(exc=e, countdown=30 * (self.request.retries + 1))


# ── Task: Process chat queue (approved messages) ─────────────────────────────


@celery_app.task(
    name="app.tasks.shadow.process_chat_queue",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def process_chat_queue_batch(
    self, company_id: str, queue_ids: List[str]
) -> Dict[str, Any]:
    """
    Process a batch of approved chat messages from the shadow queue.

    Iterates through approved queue entries and sends the messages
    via the chat widget service.

    Args:
        company_id: Company UUID (BC-001).
        queue_ids: List of chat_shadow_queue entry IDs to process.

    Returns:
        Dict with batch processing results.
    """
    results = {"processed": 0, "failed": 0, "skipped": 0, "errors": []}

    try:
        from app.interceptors.chat_shadow import ChatShadowInterceptor

        interceptor = ChatShadowInterceptor()

        for queue_id in queue_ids:
            try:
                # Get the queue entry to find manager_id
                from database.base import SessionLocal
                from database.models.shadow_mode import ChatShadowQueue

                with SessionLocal() as db:
                    entry = (
                        db.query(ChatShadowQueue)
                        .filter(
                            ChatShadowQueue.id == queue_id,
                            ChatShadowQueue.company_id == company_id,
                            ChatShadowQueue.status == "approved",
                        )
                        .first()
                    )

                    if not entry:
                        results["skipped"] += 1
                        continue

                    manager_id = entry.approved_by

                # Approve and send the message
                approve_result = interceptor.approve_queued_message(
                    company_id=company_id,
                    queue_id=queue_id,
                    manager_id=manager_id or "system",
                )

                if approve_result.get("success"):
                    results["processed"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(
                        {
                            "queue_id": queue_id,
                            "error": approve_result.get("error"),
                        }
                    )

            except Exception as e:
                results["failed"] += 1
                results["errors"].append(
                    {
                        "queue_id": queue_id,
                        "error": str(e),
                    }
                )

        logger.info(
            "shadow_chat_batch_processed company_id=%s processed=%d failed=%d skipped=%d",
            company_id,
            results["processed"],
            results["failed"],
            results["skipped"],
        )

        return results

    except Exception as e:
        logger.error(
            "shadow_chat_batch_failed company_id=%s error=%s",
            company_id,
            str(e),
            exc_info=True,
        )
        raise self.retry(exc=e, countdown=60)


# ── Periodic: Cleanup expired shadow queue items ────────────────────────────


@celery_app.task(name="app.tasks.shadow.cleanup_expired_queue_items")
def cleanup_expired_shadow_queue() -> Dict[str, Any]:
    """
    Periodic task: Clean up expired pending shadow queue items.

    Items that have been pending for longer than the company's
    undo_window_minutes are flagged for review and a notification
    is dispatched to managers.

    Runs every 15 minutes via beat schedule.

    Returns:
        Dict with cleanup results.
    """
    results = {"flagged": 0, "companies_checked": 0}

    try:
        from database.base import SessionLocal
        from database.models.core import Company
        from database.models.shadow_mode import ShadowLog

        now = datetime.utcnow()

        with SessionLocal() as db:
            companies = (
                db.query(Company)
                .filter(Company.system_mode.in_(["shadow", "supervised"]))
                .all()
            )

            for company in companies:
                undo_window = company.undo_window_minutes or 30
                expiry_threshold = now - timedelta(minutes=undo_window)

                # Find expired pending entries
                expired = (
                    db.query(ShadowLog)
                    .filter(
                        ShadowLog.company_id == company.id,
                        ShadowLog.manager_decision.is_(None),
                        ShadowLog.created_at < expiry_threshold,
                    )
                    .all()
                )

                if expired:
                    results["flagged"] += len(expired)

                    # Emit notification event for each expired entry
                    for entry in expired:
                        try:
                            from app.services.shadow_mode_service import (
                                _emit_shadow_event_sync,
                            )

                            _emit_shadow_event_sync(
                                entry.company_id,
                                "shadow:action_expired",
                                {
                                    "shadow_log_id": entry.id,
                                    "action_type": entry.action_type,
                                    "created_at": (
                                        entry.created_at.isoformat()
                                        if entry.created_at
                                        else None
                                    ),
                                    "expired_at": now.isoformat(),
                                },
                            )
                        except Exception:
                            pass

                    logger.info(
                        "shadow_expired_items company_id=%s count=%d window=%dm",
                        company.id,
                        len(expired),
                        undo_window,
                    )

                results["companies_checked"] += 1

        return results

    except Exception as e:
        logger.error("shadow_cleanup_failed: %s", str(e), exc_info=True)
        return {"status": "error", "error": str(e)}


# ── Periodic: Aggregate shadow mode stats ───────────────────────────────────


@celery_app.task(name="app.tasks.shadow.aggregate_stats")
def aggregate_shadow_stats() -> Dict[str, Any]:
    """
    Periodic task: Aggregate shadow mode statistics for all companies.

    Computes approval rates, average risk scores, and action distributions.
    Stores aggregated results in Redis for fast dashboard retrieval.

    Returns:
        Dict with aggregation results.
    """
    results = {"companies_processed": 0, "errors": 0}

    try:
        import json
        from database.base import SessionLocal
        from database.models.core import Company
        from app.services.shadow_mode_service import ShadowModeService

        with SessionLocal() as db:
            companies = db.query(Company).filter(Company.system_mode.isnot(None)).all()

            service = ShadowModeService()

            for company in companies:
                try:
                    stats = service.get_shadow_stats(str(company.id))

                    # Cache stats in Redis for fast retrieval
                    try:
                        import redis
                        from app.config import get_settings

                        settings = get_settings()
                        redis_client = redis.from_url(settings.REDIS_URL)
                        redis_client.setex(
                            f"shadow:stats:{company.id}",
                            300,  # 5 minute TTL
                            json.dumps(stats),
                        )
                    except Exception:
                        pass

                    results["companies_processed"] += 1
                except Exception:
                    results["errors"] += 1

        logger.info(
            "shadow_stats_aggregated processed=%d errors=%d",
            results["companies_processed"],
            results["errors"],
        )

        return results

    except Exception as e:
        logger.error("shadow_stats_aggregation_failed: %s", str(e), exc_info=True)
        return {"status": "error", "error": str(e)}
