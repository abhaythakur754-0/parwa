"""
Reconciliation Tasks (BG-06)

NOTE: Paddle was removed. These Celery tasks are kept as no-ops so the
existing Celery Beat schedule and any external callers don't break. They
now log a single "skipped" line and return an empty/zero result dict.

Original responsibilities (now DB-managed by subscription_service,
invoice_service, and overage_service):
- reconcile_subscriptions: Daily subscription sync
- reconcile_transactions: Daily transaction sync
- reconcile_usage: Daily usage sync
- reconcile_all_companies_task: Idempotency-aware full reconciliation
- process_dead_letter_queue_task: Retry failed webhook events
- cleanup_old_webhook_events_task: Remove events older than 90 days

BC-001: All operations validate company_id
BC-003: All tasks have proper error handling and logging
BC-008: Never crash — all errors are caught and handled
BC-012: All timestamps in UTC
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from celery import shared_task

logger = logging.getLogger("parwa.tasks.reconciliation")


class ReconciliationError(Exception):
    """Base exception for reconciliation errors."""
    pass


def _skipped(reason: str = "Paddle was removed; reconciliation is DB-managed") -> Dict[str, Any]:
    """Return a standard 'skipped' result payload."""
    return {
        "status": "skipped",
        "reason": reason,
        "checked": 0,
        "matched": 0,
        "updated": 0,
        "synced": 0,
        "errors": 0,
        "discrepancies": [],
        "missing_transactions": [],
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


@shared_task(
    name="billing.reconcile_subscriptions",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def reconcile_subscriptions(self) -> Dict[str, Any]:
    """
    Reconcile subscriptions between DB and the billing provider.

    NOTE: Paddle was removed; subscriptions are now the local DB's source
    of truth (managed by subscription_service / Razorpay webhooks). This
    task is a no-op kept for scheduler compatibility.
    """
    logger.info(
        "subscription_reconciliation_skipped reason=Paddle was removed"
    )
    return _skipped()


@shared_task(
    name="billing.reconcile_transactions",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def reconcile_transactions(self) -> Dict[str, Any]:
    """
    Reconcile transactions between DB and the billing provider.

    NOTE: Paddle was removed; transactions are now sourced from Razorpay
    webhooks. This task is a no-op kept for scheduler compatibility.
    """
    logger.info(
        "transaction_reconciliation_skipped reason=Paddle was removed"
    )
    return _skipped()


@shared_task(
    name="billing.reconcile_usage",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def reconcile_usage(self) -> Dict[str, Any]:
    """
    Reconcile usage records with the billing provider.

    NOTE: Paddle was removed; usage records are now managed DB-side by
    overage_service. This task is a no-op kept for scheduler compatibility.
    """
    logger.info("usage_reconciliation_skipped reason=Paddle was removed")
    return _skipped()


@shared_task(
    name="billing.reconcile_all",
    bind=True,
)
def reconcile_all(self) -> Dict[str, Any]:
    """
    Run all reconciliation tasks in sequence.

    NOTE: Paddle was removed; this task is a no-op kept for compatibility.
    """
    logger.info("full_reconciliation_skipped reason=Paddle was removed")
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "status": "skipped",
        "reason": "Paddle was removed",
        "subscriptions": _skipped(),
        "transactions": _skipped(),
        "usage": _skipped(),
        "started_at": now_iso,
        "completed_at": now_iso,
    }


# ── Helper Functions ────────────────────────────────────────────────────
#
# NOTE: Paddle was removed. The following helpers are kept as no-op stubs
# so any external callers don't break; they no longer perform any work.

def _compare_subscription(
    db_sub,  # Subscription
    paddle_data: Dict[str, Any],
) -> List[str]:
    """Compare DB subscription with provider data. No-op (Paddle was removed)."""
    return []


def _update_subscription_from_paddle(
    db_sub,  # Subscription
    paddle_data: Dict[str, Any],
) -> None:
    """Update DB subscription from provider data. No-op (Paddle was removed)."""
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Phase 6: Idempotency-Aware Reconciliation Tasks (Production Hardening)
# NOTE: Paddle was removed. These are now no-ops kept for scheduler compat.
# ══════════════════════════════════════════════════════════════════════════════


@shared_task(
    name="billing.reconcile_all_companies",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def reconcile_all_companies_task(self) -> Dict[str, Any]:
    """
    Reconcile payment state for all active companies.

    NOTE: Paddle was removed; the PaddleReconciliationService has been
    deleted. This task is a no-op kept for Celery Beat compatibility.
    """
    logger.info(
        "phase6_reconciliation_all_companies_skipped reason=Paddle was removed"
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "status": "skipped",
        "reason": "Paddle was removed",
        "companies_checked": 0,
        "companies_reconciled": 0,
        "total_discrepancies": 0,
        "total_corrections": 0,
        "errors": 0,
        "started_at": now_iso,
        "completed_at": now_iso,
    }


@shared_task(
    name="billing.process_dead_letter_queue",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def process_dead_letter_queue_task(self) -> Dict[str, Any]:
    """
    Retry dead letter webhook events.

    NOTE: Paddle was removed; the PaddleReconciliationService (and its
    dead-letter retry logic) has been deleted. This task is a no-op kept
    for Celery Beat compatibility.
    """
    logger.info(
        "phase6_dlq_processing_skipped reason=Paddle was removed"
    )
    return {
        "status": "skipped",
        "reason": "Paddle was removed",
        "dead_letter_count": 0,
        "retried": 0,
        "succeeded": 0,
        "still_failed": 0,
        "errors": 0,
    }


@shared_task(
    name="billing.cleanup_old_webhook_events",
    bind=True,
    max_retries=1,
    default_retry_delay=600,
)
def cleanup_old_webhook_events_task(
    self,
    retention_days: int = 90,
) -> Dict[str, Any]:
    """
    Clean up webhook events older than the retention period.

    NOTE: Paddle was removed; the PaddleWebhookEvent /
    PaddleReconciliationReport tables are no longer actively written to.
    This task is a no-op kept for Celery Beat compatibility.
    """
    logger.info(
        "phase6_webhook_cleanup_skipped reason=Paddle was removed retention_days=%d",
        retention_days,
    )
    return {
        "status": "skipped",
        "reason": "Paddle was removed",
        "events_deleted": 0,
        "reports_deleted": 0,
        "errors": 0,
    }
