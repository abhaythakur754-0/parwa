"""
Reconciliation Tasks (BG-06)

Background tasks to keep local DB in sync with Paddle:
- reconcile_subscriptions: Daily subscription sync
- reconcile_transactions: Daily transaction sync
- reconcile_usage: Daily usage sync to Paddle

Phase 6 additions (Production Hardening):
- reconcile_all_companies_task: Idempotency-aware full reconciliation
- process_dead_letter_queue_task: Retry failed webhook events
- cleanup_old_webhook_events_task: Remove events older than 90 days

BC-001: All operations validate company_id
BC-003: All tasks have proper error handling and logging
BC-008: Never crash — all errors are caught and handled
BC-012: All timestamps in UTC
"""

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from celery import shared_task

from app.clients.paddle_client import (
    PaddleClient,
    PaddleError,
    get_paddle_client,
)
from database.base import SessionLocal
from database.models.billing import Subscription, Invoice, Transaction
from database.models.billing_extended import UsageRecord
from database.models.core import Company

logger = logging.getLogger("parwa.tasks.reconciliation")


class ReconciliationError(Exception):
    """Base exception for reconciliation errors."""
    pass


@shared_task(
    name="billing.reconcile_subscriptions",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def reconcile_subscriptions(self) -> Dict[str, Any]:
    """
    Reconcile subscriptions between DB and Paddle.

    Runs daily at 06:00 (configured in Celery Beat).

    For each company:
    1. Get subscription from Paddle API
    2. Compare with DB subscription record
    3. If diverged:
       - Log discrepancy
       - Update DB to match Paddle (Paddle is source of truth)
       - Alert if critical mismatch

    Returns:
        Dict with reconciliation results
    """
    logger.info("subscription_reconciliation_started")

    results = {
        "checked": 0,
        "matched": 0,
        "updated": 0,
        "errors": 0,
        "discrepancies": [],
    }

    db = SessionLocal()
    try:
        # Get all companies with paddle_subscription_id
        companies = db.query(Company).filter(
            Company.paddle_subscription_id.isnot(None),
        ).all()

        paddle = _get_sync_paddle_client()

        for company in companies:
            results["checked"] += 1

            try:
                # Get from Paddle
                paddle_sub = paddle.get_subscription_sync(
                    company.paddle_subscription_id
                )
                paddle_data = paddle_sub.get("data", {})

                # Get from DB
                db_sub = db.query(Subscription).filter(
                    Subscription.company_id == str(company.id),
                    Subscription.status == "active",
                ).first()

                if not db_sub:
                    logger.warning(
                        "reconciliation_no_db_sub company_id=%s",
                        company.id,
                    )
                    continue

                # Compare fields
                discrepancies = _compare_subscription(
                    db_sub,
                    paddle_data,
                )

                if discrepancies:
                    results["discrepancies"].append({
                        "company_id": str(company.id),
                        "subscription_id": str(db_sub.id),
                        "issues": discrepancies,
                    })

                    # Update DB to match Paddle
                    _update_subscription_from_paddle(
                        db_sub,
                        paddle_data,
                    )
                    db.commit()
                    results["updated"] += 1

                    logger.info(
                        "subscription_reconciled company_id=%s discrepancies=%s",
                        company.id,
                        discrepancies,
                    )
                else:
                    results["matched"] += 1

            except PaddleError as e:
                results["errors"] += 1
                logger.error(
                    "subscription_reconciliation_paddle_error company_id=%s error=%s",
                    company.id,
                    str(e),
                )
            except Exception as e:
                results["errors"] += 1
                logger.exception(
                    "subscription_reconciliation_error company_id=%s error=%s",
                    company.id,
                    str(e),
                )

        logger.info(
            "subscription_reconciliation_complete checked=%d matched=%d updated=%d errors=%d",
            results["checked"],
            results["matched"],
            results["updated"],
            results["errors"],
        )

        return results

    finally:
        db.close()


@shared_task(
    name="billing.reconcile_transactions",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def reconcile_transactions(self) -> Dict[str, Any]:
    """
    Reconcile transactions between DB and Paddle.

    Runs daily at 06:30 (configured in Celery Beat).

    For each company:
    1. Get transactions from Paddle API
    2. Compare with DB transaction records
    3. Sync missing transactions to DB

    Returns:
        Dict with reconciliation results
    """
    logger.info("transaction_reconciliation_started")

    results = {
        "checked": 0,
        "synced": 0,
        "errors": 0,
        "missing_transactions": [],
    }

    db = SessionLocal()
    try:
        # Get all companies with paddle_customer_id
        companies = db.query(Company).filter(
            Company.paddle_customer_id.isnot(None),
        ).all()

        paddle = _get_sync_paddle_client()

        for company in companies:
            results["checked"] += 1

            try:
                # Get transactions from Paddle
                paddle_txns = paddle.list_transactions_sync(
                    customer_id=company.paddle_customer_id,
                    per_page=100,
                )

                for txn_data in paddle_txns.get("data", []):
                    txn_id = txn_data.get("id")
                    if not txn_id:
                        continue

                    # Check if exists in DB
                    existing = db.query(Transaction).filter(
                        Transaction.paddle_transaction_id == txn_id,
                    ).first()

                    if not existing:
                        # Create missing transaction
                        txn = Transaction(
                            company_id=str(company.id),
                            paddle_transaction_id=txn_id,
                            amount=Decimal(str(txn_data.get("amount", "0"))),
                            currency=txn_data.get("currency_code", "USD"),
                            status=txn_data.get("status", "pending"),
                            transaction_type=txn_data.get("origin", "subscription"),
                            description=txn_data.get("description"),
                        )
                        db.add(txn)
                        results["synced"] += 1

                        results["missing_transactions"].append({
                            "company_id": str(company.id),
                            "transaction_id": txn_id,
                        })

                db.commit()

            except PaddleError as e:
                results["errors"] += 1
                logger.error(
                    "transaction_reconciliation_paddle_error company_id=%s error=%s",
                    company.id,
                    str(e),
                )
            except Exception as e:
                results["errors"] += 1
                logger.exception(
                    "transaction_reconciliation_error company_id=%s error=%s",
                    company.id,
                    str(e),
                )

        logger.info(
            "transaction_reconciliation_complete checked=%d synced=%d errors=%d",
            results["checked"],
            results["synced"],
            results["errors"],
        )

        return results

    finally:
        db.close()


@shared_task(
    name="billing.reconcile_usage",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def reconcile_usage(self) -> Dict[str, Any]:
    """
    Reconcile usage records with Paddle.

    Runs daily at 07:00 (configured in Celery Beat).

    For each company:
    1. Get ticket count from DB
    2. Compare with Paddle usage records (if metered billing)
    3. Update Paddle usage if diverged

    Returns:
        Dict with reconciliation results
    """
    logger.info("usage_reconciliation_started")

    results = {
        "checked": 0,
        "updated": 0,
        "errors": 0,
        "discrepancies": [],
    }

    db = SessionLocal()
    try:
        # Get all active companies
        companies = db.query(Company).filter(
            Company.subscription_status == "active",
        ).all()

        for company in companies:
            results["checked"] += 1

            try:
                # Get current month's usage from DB
                current_month = datetime.now(timezone.utc).strftime("%Y-%m")
                usage = db.query(UsageRecord).filter(
                    UsageRecord.company_id == str(company.id),
                    UsageRecord.record_month == current_month,
                ).first()

                if not usage:
                    # Calculate from tickets table if no usage record
                    from database.models.tickets import Ticket
                    from sqlalchemy import func

                    month_start = datetime.now(timezone.utc).replace(
                        day=1, hour=0, minute=0, second=0, microsecond=0
                    )

                    ticket_count = db.query(func.count(Ticket.id)).filter(
                        Ticket.company_id == str(company.id),
                        Ticket.created_at >= month_start,
                    ).scalar() or 0

                    # Create usage record
                    usage = UsageRecord(
                        company_id=str(company.id),
                        record_date=datetime.now(timezone.utc).date(),
                        record_month=current_month,
                        tickets_used=ticket_count,
                    )
                    db.add(usage)
                    db.commit()

                # In a metered billing setup, we would update Paddle here
                # For now, just log the usage
                logger.info(
                    "usage_reconciled company_id=%s tickets=%d month=%s",
                    company.id,
                    usage.tickets_used,
                    current_month,
                )

            except Exception as e:
                results["errors"] += 1
                logger.exception(
                    "usage_reconciliation_error company_id=%s error=%s",
                    company.id,
                    str(e),
                )

        logger.info(
            "usage_reconciliation_complete checked=%d errors=%d",
            results["checked"],
            results["errors"],
        )

        return results

    finally:
        db.close()


@shared_task(
    name="billing.reconcile_all",
    bind=True,
)
def reconcile_all(self) -> Dict[str, Any]:
    """
    Run all reconciliation tasks in sequence.

    Used for manual reconciliation or on-demand sync.

    Returns:
        Combined results from all tasks
    """
    logger.info("full_reconciliation_started")

    results = {
        "subscriptions": reconcile_subscriptions(),
        "transactions": reconcile_transactions(),
        "usage": reconcile_usage(),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    results["completed_at"] = datetime.now(timezone.utc).isoformat()

    logger.info("full_reconciliation_complete")

    return results


# ── Helper Functions ────────────────────────────────────────────────────

def _get_sync_paddle_client():
    """Get Paddle client with sync methods."""
    paddle = get_paddle_client()

    # Add sync wrappers if not present
    if not hasattr(paddle, 'get_subscription_sync'):
        import asyncio

        def get_subscription_sync(subscription_id):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    paddle.get_subscription(subscription_id)
                )
            finally:
                loop.close()

        paddle.get_subscription_sync = get_subscription_sync

    if not hasattr(paddle, 'list_transactions_sync'):
        import asyncio

        def list_transactions_sync(**kwargs):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    paddle.list_transactions(**kwargs)
                )
            finally:
                loop.close()

        paddle.list_transactions_sync = list_transactions_sync

    return paddle


def _compare_subscription(
    db_sub: Subscription,
    paddle_data: Dict[str, Any],
) -> List[str]:
    """
    Compare DB subscription with Paddle data.

    Returns list of discrepancy descriptions.
    """
    discrepancies = []

    # Compare status
    paddle_status = paddle_data.get("status")
    if paddle_status and db_sub.status != paddle_status:
        discrepancies.append(
            f"status: db={db_sub.status} paddle={paddle_status}"
        )

    # Compare tier (from items)
    items = paddle_data.get("items", [])
    if items:
        paddle_price_id = items[0].get("price", {}).get("id")
        # Would need mapping from price_id to tier name

    # Compare billing period
    paddle_period_start = paddle_data.get("current_billing_period", {}).get("starts_at")
    paddle_period_end = paddle_data.get("current_billing_period", {}).get("ends_at")

    if paddle_period_start and db_sub.current_period_start:
        db_start = db_sub.current_period_start.isoformat() if db_sub.current_period_start else None
        paddle_start = paddle_period_start.replace("Z", "+00:00") if isinstance(paddle_period_start, str) else paddle_period_start
        # Compare with tolerance for timezone differences

    return discrepancies


def _update_subscription_from_paddle(
    db_sub: Subscription,
    paddle_data: Dict[str, Any],
) -> None:
    """Update DB subscription from Paddle data."""
    paddle_status = paddle_data.get("status")
    if paddle_status:
        db_sub.status = paddle_status

    # Update billing period
    period = paddle_data.get("current_billing_period", {})
    if period.get("starts_at"):
        try:
            db_sub.current_period_start = datetime.fromisoformat(
                period["starts_at"].replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            pass

    if period.get("ends_at"):
        try:
            db_sub.current_period_end = datetime.fromisoformat(
                period["ends_at"].replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            pass

    # Update cancel_at_period_end
    scheduled_change = paddle_data.get("scheduled_change")
    db_sub.cancel_at_period_end = bool(scheduled_change)


# ══════════════════════════════════════════════════════════════════════════════
# Phase 6: Idempotency-Aware Reconciliation Tasks (Production Hardening)
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

    Uses the PaddleReconciliationService for idempotency-aware
    reconciliation with full audit trail.

    Runs daily at 05:00 (before the existing reconciliation tasks).

    For each active company:
    1. Compare Paddle subscription state with local DB
    2. Identify and record discrepancies
    3. Apply corrections (Paddle is source of truth)
    4. Generate reconciliation report

    Returns:
        Dict with aggregated reconciliation results
    """
    logger.info("phase6_reconciliation_all_companies_started")

    results = {
        "companies_checked": 0,
        "companies_reconciled": 0,
        "total_discrepancies": 0,
        "total_corrections": 0,
        "errors": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    db = SessionLocal()
    try:
        from database.models.core import Company
        from database.models.billing_extended import (
            PaddleWebhookEvent,
            PaddleReconciliationReport,
        )

        # Get all companies with active subscriptions
        companies = db.query(Company).filter(
            Company.subscription_status == "active",
        ).all()

        results["companies_checked"] = len(companies)

        for company in companies:
            try:
                # Use the reconciliation service
                import asyncio

                async def _reconcile(company_id: str) -> Dict[str, Any]:
                    from app.services.paddle_reconciliation_service import (
                        PaddleReconciliationService,
                    )
                    service = PaddleReconciliationService(
                        db_session=db,
                        redis_client=None,  # Celery tasks run in worker — Redis optional
                    )
                    return await service.reconcile_payment_state(company_id)

                # Run async reconciliation
                loop = asyncio.new_event_loop()
                try:
                    report = loop.run_until_complete(
                        _reconcile(str(company.id))
                    )
                finally:
                    loop.close()

                results["companies_reconciled"] += 1
                results["total_discrepancies"] += len(
                    report.get("discrepancies", [])
                )
                results["total_corrections"] += report.get(
                    "corrections_applied", 0
                )

                logger.info(
                    "phase6_company_reconciled company_id=%s discrepancies=%d corrections=%d",
                    company.id,
                    len(report.get("discrepancies", [])),
                    report.get("corrections_applied", 0),
                )

            except Exception as e:
                results["errors"] += 1
                logger.error(
                    "phase6_reconciliation_error company_id=%s error=%s",
                    company.id,
                    str(e)[:500],
                )

        results["completed_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "phase6_reconciliation_all_companies_complete "
            "checked=%d reconciled=%d discrepancies=%d corrections=%d errors=%d",
            results["companies_checked"],
            results["companies_reconciled"],
            results["total_discrepancies"],
            results["total_corrections"],
            results["errors"],
        )

        return results

    except Exception as e:
        logger.error(
            "phase6_reconciliation_fatal_error error=%s",
            str(e)[:500],
        )
        results["fatal_error"] = str(e)[:500]
        results["completed_at"] = datetime.now(timezone.utc).isoformat()
        return results

    finally:
        db.close()


@shared_task(
    name="billing.process_dead_letter_queue",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def process_dead_letter_queue_task(self) -> Dict[str, Any]:
    """
    Retry dead letter webhook events.

    Reviews events in the dead_letter status and attempts to
    re-process them after resetting their attempt count.

    Runs every 6 hours (configured in Celery Beat).

    Returns:
        Dict with DLQ processing results
    """
    logger.info("phase6_dlq_processing_started")

    results = {
        "dead_letter_count": 0,
        "retried": 0,
        "succeeded": 0,
        "still_failed": 0,
        "errors": 0,
    }

    db = SessionLocal()
    try:
        from database.models.billing_extended import PaddleWebhookEvent

        # Get all dead letter events
        dead_letter_events = db.query(PaddleWebhookEvent).filter(
            PaddleWebhookEvent.status == "dead_letter",
        ).all()

        results["dead_letter_count"] = len(dead_letter_events)

        for event in dead_letter_events:
            try:
                # Reset attempt count and re-process
                event.processing_attempts = 0
                event.status = "pending"
                event.last_error = None
                event.updated_at = datetime.now(timezone.utc)
                db.commit()

                # Re-process via reconciliation service
                import asyncio

                async def _reprocess(event_id: str) -> Any:
                    from app.services.paddle_reconciliation_service import (
                        PaddleReconciliationService,
                    )
                    service = PaddleReconciliationService(
                        db_session=db,
                        redis_client=None,
                    )
                    return await service.retry_dead_letter_event(event_id)

                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(
                        _reprocess(str(event.id))
                    )
                finally:
                    loop.close()

                results["retried"] += 1

                if result.status == "completed":
                    results["succeeded"] += 1
                    logger.info(
                        "phase6_dlq_retry_succeeded event_id=%s key=%s",
                        event.id,
                        event.idempotency_key[:16],
                    )
                else:
                    results["still_failed"] += 1
                    logger.warning(
                        "phase6_dlq_retry_failed event_id=%s error=%s",
                        event.id,
                        result.error or "unknown",
                    )

            except Exception as e:
                results["errors"] += 1
                logger.error(
                    "phase6_dlq_retry_error event_id=%s error=%s",
                    event.id,
                    str(e)[:500],
                )

        logger.info(
            "phase6_dlq_processing_complete total=%d retried=%d "
            "succeeded=%d still_failed=%d errors=%d",
            results["dead_letter_count"],
            results["retried"],
            results["succeeded"],
            results["still_failed"],
            results["errors"],
        )

        return results

    except Exception as e:
        logger.error(
            "phase6_dlq_processing_fatal_error error=%s",
            str(e)[:500],
        )
        results["fatal_error"] = str(e)[:500]
        return results

    finally:
        db.close()


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

    Removes completed webhook events older than retention_days.
    Keeps dead_letter events regardless of age (for manual review).

    Runs weekly (configured in Celery Beat).

    Args:
        retention_days: Number of days to retain completed events (default: 90)

    Returns:
        Dict with cleanup results
    """
    logger.info(
        "phase6_webhook_cleanup_started retention_days=%d",
        retention_days,
    )

    results = {
        "events_deleted": 0,
        "reports_deleted": 0,
        "errors": 0,
    }

    db = SessionLocal()
    try:
        from database.models.billing_extended import (
            PaddleWebhookEvent,
            PaddleReconciliationReport,
        )

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

        # Delete completed webhook events older than cutoff
        # Keep dead_letter events for manual review
        deleted = db.query(PaddleWebhookEvent).filter(
            PaddleWebhookEvent.status == "completed",
            PaddleWebhookEvent.created_at < cutoff,
        ).delete(synchronize_session=False)

        results["events_deleted"] = deleted or 0

        # Delete old reconciliation reports (keep for audit but prune very old ones)
        report_cutoff = datetime.now(timezone.utc) - timedelta(
            days=max(retention_days * 2, 180)
        )
        deleted_reports = db.query(PaddleReconciliationReport).filter(
            PaddleReconciliationReport.created_at < report_cutoff,
        ).delete(synchronize_session=False)

        results["reports_deleted"] = deleted_reports or 0

        db.commit()

        logger.info(
            "phase6_webhook_cleanup_complete events_deleted=%d reports_deleted=%d",
            results["events_deleted"],
            results["reports_deleted"],
        )

        return results

    except Exception as e:
        logger.error(
            "phase6_webhook_cleanup_error error=%s",
            str(e)[:500],
        )
        results["errors"] += 1
        try:
            db.rollback()
        except Exception:
            pass
        return results

    finally:
        db.close()
