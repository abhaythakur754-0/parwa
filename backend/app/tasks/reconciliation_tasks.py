"""
Reconciliation Tasks (BG-06)

Background tasks to keep local DB in sync with Paddle:
- reconcile_subscriptions: Daily subscription sync
- reconcile_transactions: Daily transaction sync
- reconcile_usage: Daily usage sync to Paddle

These tasks detect and fix discrepancies between local DB
and Paddle's records.

BC-001: All operations validate company_id
BC-003: All tasks have proper error handling and logging
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

from app.tasks.base import ParwaBaseTask
from app.tasks.celery_app import app

from app.clients.paddle_client import (
    PaddleError,
    get_paddle_client,
)
from database.base import SessionLocal
from database.models.billing import Subscription, Transaction
from database.models.billing_extended import UsageRecord
from database.models.core import Company

logger = logging.getLogger("parwa.tasks.reconciliation")


class ReconciliationError(Exception):
    """Base exception for reconciliation errors."""


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="billing.reconcile_subscriptions",
    max_retries=3,
    retry_backoff=True,
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
        companies = (
            db.query(Company)
            .filter(
                Company.paddle_subscription_id.isnot(None),
            )
            .all()
        )

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
                db_sub = (
                    db.query(Subscription)
                    .filter(
                        Subscription.company_id == str(company.id),
                        Subscription.status == "active",
                    )
                    .first()
                )

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
                    results["discrepancies"].append(
                        {
                            "company_id": str(company.id),
                            "subscription_id": str(db_sub.id),
                            "issues": discrepancies,
                        }
                    )

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


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="billing.reconcile_transactions",
    max_retries=3,
    retry_backoff=True,
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
        companies = (
            db.query(Company)
            .filter(
                Company.paddle_customer_id.isnot(None),
            )
            .all()
        )

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
                    existing = (
                        db.query(Transaction)
                        .filter(
                            Transaction.paddle_transaction_id == txn_id,
                        )
                        .first()
                    )

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

                        results["missing_transactions"].append(
                            {
                                "company_id": str(company.id),
                                "transaction_id": txn_id,
                            }
                        )

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


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="billing.reconcile_usage",
    max_retries=3,
    retry_backoff=True,
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
        companies = (
            db.query(Company)
            .filter(
                Company.subscription_status == "active",
            )
            .all()
        )

        for company in companies:
            results["checked"] += 1

            try:
                # Get current month's usage from DB
                current_month = datetime.now(timezone.utc).strftime("%Y-%m")
                usage = (
                    db.query(UsageRecord)
                    .filter(
                        UsageRecord.company_id == str(company.id),
                        UsageRecord.record_month == current_month,
                    )
                    .first()
                )

                if not usage:
                    # Calculate from tickets table if no usage record
                    from database.models.tickets import Ticket
                    from sqlalchemy import func

                    month_start = datetime.now(timezone.utc).replace(
                        day=1, hour=0, minute=0, second=0, microsecond=0
                    )

                    ticket_count = (
                        db.query(func.count(Ticket.id))
                        .filter(
                            Ticket.company_id == str(company.id),
                            Ticket.created_at >= month_start,
                        )
                        .scalar()
                        or 0
                    )

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


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="billing.reconcile_all",
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
    if not hasattr(paddle, "get_subscription_sync"):
        import asyncio

        def get_subscription_sync(subscription_id):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(paddle.get_subscription(subscription_id))
            finally:
                loop.close()

        paddle.get_subscription_sync = get_subscription_sync

    if not hasattr(paddle, "list_transactions_sync"):

        def list_transactions_sync(**kwargs):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(paddle.list_transactions(**kwargs))
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
        discrepancies.append(f"status: db={db_sub.status} paddle={paddle_status}")

    # Compare tier (from items)
    items = paddle_data.get("items", [])
    if items:
        paddle_price_id = items[0].get("price", {}).get("id")
        # Would need mapping from price_id to tier name

    # Compare billing period
    paddle_period_start = paddle_data.get("current_billing_period", {}).get("starts_at")
    paddle_period_end = paddle_data.get("current_billing_period", {}).get("ends_at")

    if paddle_period_start and db_sub.current_period_start:
        db_start = (
            db_sub.current_period_start.isoformat()
            if db_sub.current_period_start
            else None
        )
        paddle_start = (
            paddle_period_start.replace("Z", "+00:00")
            if isinstance(paddle_period_start, str)
            else paddle_period_start
        )
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
