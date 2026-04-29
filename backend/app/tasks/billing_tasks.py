"""
PARWA Billing Tasks (Day 22, Day 23, BC-004, BC-002)

Celery tasks for billing operations:
- daily_overage_charge_task: Charge for usage over plan limits (F-024)
- invoice_sync_task: Sync invoices from Paddle (F-023)
- subscription_check_task: Check subscription status
- process_all_overages_task: Batch process overages for all companies
- send_usage_warning_task: Send warning when approaching limit
"""

import logging
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal

from app.tasks.base import ParwaBaseTask, with_company_id
from app.tasks.celery_app import app
from database.base import SessionLocal
from database.models.core import Company
from database.models.billing import Subscription

logger = logging.getLogger("parwa.tasks.billing")


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.billing.daily_overage_charge",
    max_retries=3,
    soft_time_limit=120,
    time_limit=300,
    retry_backoff=True,
    retry_jitter=True,
)
@with_company_id
def daily_overage_charge(self, company_id: str) -> dict:
    """
    Charge for usage exceeding plan limits.

    F-024: Daily Overage Charging

    This task:
    1. Gets company's subscription and plan limits
    2. Calculates yesterday's ticket usage
    3. Determines overage (tickets over limit)
    4. Creates overage charge at $0.10/ticket
    5. Submits charge to Paddle
    6. Sends email + Socket.io notification

    Args:
        company_id: Company UUID string

    Returns:
        Dict with charge status and details
    """
    try:
        from app.services.overage_service import get_overage_service
        import asyncio

        overage_service = get_overage_service()

        # Process yesterday's overage
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()

        # Run async process in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                overage_service.process_daily_overage(
                    company_id=company_id,
                    target_date=yesterday,
                )
            )
        finally:
            loop.close()

        logger.info(
            "daily_overage_charge_completed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "date": yesterday.isoformat(),
                "status": result.get("status"),
                "overage_tickets": result.get("overage_tickets", 0),
                "overage_charges": result.get("overage_charges", "0.00"),
            },
        )

        return result

    except Exception as exc:
        logger.error(
            "daily_overage_charge_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.billing.process_all_overages",
    max_retries=2,
    soft_time_limit=600,
    time_limit=900,
)
def process_all_overages(self, target_date: str = None) -> dict:
    """
    Process overages for all active companies.

    This is the main task called by Celery Beat daily.

    Args:
        target_date: Date to process in YYYY-MM-DD format (default: yesterday)

    Returns:
        Dict with processing summary
    """
    try:
        if target_date:
            process_date = date.fromisoformat(target_date)
        else:
            process_date = (
                datetime.now(
                    timezone.utc) -
                timedelta(
                    days=1)).date()

        results = {
            "date": process_date.isoformat(),
            "total_companies": 0,
            "processed": 0,
            "skipped": 0,
            "charged": 0,
            "failed": 0,
            "total_overage_charges": Decimal("0.00"),
            "errors": [],
        }

        with SessionLocal() as db:
            # Get all active companies with subscriptions
            active_companies = db.query(Company).join(
                Subscription,
                Company.id == Subscription.company_id,
            ).filter(
                Subscription.status == "active",
            ).all()

            results["total_companies"] = len(active_companies)

            for company in active_companies:
                try:
                    # Dispatch individual overage task
                    daily_overage_charge.delay(company_id=str(company.id))
                    results["processed"] += 1

                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({
                        "company_id": str(company.id),
                        "error": str(e)[:100],
                    })

        logger.info(
            "process_all_overages_completed",
            extra={
                "task": self.name,
                "date": process_date.isoformat(),
                "total": results["total_companies"],
                "processed": results["processed"],
                "failed": results["failed"],
            },
        )

        return results

    except Exception as exc:
        logger.error(
            "process_all_overages_failed",
            extra={
                "task": self.name,
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.billing.invoice_sync",
    max_retries=3,
    soft_time_limit=120,
    time_limit=300,
    retry_backoff=True,
)
@with_company_id
def invoice_sync(self, company_id: str) -> dict:
    """
    Sync invoices from Paddle billing provider.

    F-023: Invoice History

    This task:
    1. Fetches recent invoices from Paddle API
    2. Creates/updates local invoice records
    3. Stores PDF URLs for download

    Args:
        company_id: Company UUID string

    Returns:
        Dict with sync status and invoice count
    """
    try:
        from app.clients.paddle_client import get_paddle_client
        from database.models.billing import Invoice
        import asyncio

        with SessionLocal() as db:
            company = db.query(Company).filter(
                Company.id == company_id
            ).first()

            if not company or not company.paddle_customer_id:
                return {
                    "status": "skipped",
                    "company_id": company_id,
                    "reason": "no_paddle_customer",
                    "invoices_synced": 0,
                    "new_invoices": 0,
                }

            # Fetch invoices from Paddle
            paddle = get_paddle_client()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                invoices = loop.run_until_complete(
                    paddle.list_invoices(
                        customer_id=company.paddle_customer_id))
            finally:
                loop.close()

            invoices_synced = 0
            new_invoices = 0

            for inv_data in invoices.get("data", []):
                paddle_invoice_id = inv_data.get("id")
                if not paddle_invoice_id:
                    continue

                # Check if invoice exists
                existing = db.query(Invoice).filter(
                    Invoice.paddle_invoice_id == paddle_invoice_id,
                ).first()

                if existing:
                    # Update existing
                    existing.status = inv_data.get("status", existing.status)
                    existing.amount = Decimal(str(inv_data.get("total", 0)))
                    if inv_data.get("paid_at"):
                        existing.paid_at = datetime.fromisoformat(
                            inv_data["paid_at"].replace("Z", "+00:00")
                        )
                else:
                    # Create new
                    invoice = Invoice(
                        company_id=company_id, paddle_invoice_id=paddle_invoice_id, amount=Decimal(
                            str(
                                inv_data.get(
                                    "total", 0))), currency=inv_data.get(
                            "currency", "USD"), status=inv_data.get(
                            "status", "draft"), invoice_date=datetime.fromisoformat(
                            inv_data.get(
                                "created_at", datetime.now(
                                    timezone.utc).isoformat()).replace(
                                        "Z", "+00:00")) if inv_data.get("created_at") else None, )
                    db.add(invoice)
                    new_invoices += 1

                invoices_synced += 1

            db.commit()

        logger.info(
            "invoice_sync_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "invoices_synced": invoices_synced,
                "new_invoices": new_invoices,
            },
        )

        return {
            "status": "synced",
            "company_id": company_id,
            "invoices_synced": invoices_synced,
            "new_invoices": new_invoices,
        }

    except Exception as exc:
        logger.error(
            "invoice_sync_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.billing.subscription_check",
    max_retries=2,
    soft_time_limit=60,
    time_limit=120,
)
@with_company_id
def subscription_check(self, company_id: str) -> dict:
    """
    Check subscription status and plan limits.

    This task verifies the subscription is still active in Paddle
    and updates local status if needed.

    Args:
        company_id: Company UUID string

    Returns:
        Dict with subscription status
    """
    try:
        from app.clients.paddle_client import get_paddle_client
        import asyncio

        with SessionLocal() as db:
            subscription = db.query(Subscription).filter(
                Subscription.company_id == company_id,
            ).order_by(Subscription.created_at.desc()).first()

            if not subscription:
                return {
                    "status": "not_found",
                    "company_id": company_id,
                    "plan": None,
                    "valid_until": None,
                }

            # Check with Paddle if we have subscription ID
            if subscription.paddle_subscription_id:
                paddle = get_paddle_client()

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    paddle_sub = loop.run_until_complete(
                        paddle.get_subscription(
                            subscription.paddle_subscription_id))
                finally:
                    loop.close()

                paddle_status = paddle_sub.get("data", {}).get("status")

                # Update local status if different
                if paddle_status and paddle_status != subscription.status:
                    subscription.status = paddle_status
                    db.commit()

        logger.info(
            "subscription_check_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "plan": subscription.tier if subscription else None,
                "status": subscription.status if subscription else None,
            },
        )

        return {
            "status": subscription.status if subscription else "none",
            "company_id": company_id,
            "plan": subscription.tier if subscription else "free",
            "valid_until": subscription.current_period_end.isoformat() if subscription and subscription.current_period_end else None,
        }

    except Exception as exc:
        logger.error(
            "subscription_check_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.billing.send_usage_warning",
    max_retries=2,
    soft_time_limit=60,
    time_limit=120,
)
@with_company_id
def send_usage_warning(self, company_id: str, threshold: float = 80.0) -> dict:
    """
    Send warning when approaching plan limit.

    This task checks if company is approaching their limit
    and sends a warning notification if threshold is crossed.

    Args:
        company_id: Company UUID string
        threshold: Usage percentage threshold (default: 80%)

    Returns:
        Dict with warning status
    """
    try:
        from app.services.overage_service import get_overage_service
        import asyncio

        overage_service = get_overage_service()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            check_result = loop.run_until_complete(
                overage_service.check_approaching_limit(
                    company_id=company_id,
                    threshold=threshold,
                )
            )
        finally:
            loop.close()

        if check_result["approaching_limit"]:
            # Send notification
            from app.core.event_emitter import emit_billing_event

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    emit_billing_event(
                        company_id=company_id,
                        event_type="usage_warning",
                        data={
                            "usage_percentage": check_result["usage_percentage"],
                            "tickets_used": check_result["tickets_used"],
                            "ticket_limit": check_result["ticket_limit"],
                            "tickets_remaining": check_result["tickets_remaining"],
                            "threshold": threshold,
                        },
                    ))
            finally:
                loop.close()

        logger.info(
            "send_usage_warning_completed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "approaching_limit": check_result["approaching_limit"],
                "usage_percentage": check_result["usage_percentage"],
            },
        )

        return {
            "status": "sent" if check_result["approaching_limit"] else "not_needed",
            "company_id": company_id,
            "approaching_limit": check_result["approaching_limit"],
            "usage_percentage": check_result["usage_percentage"],
        }

    except Exception as exc:
        logger.error(
            "send_usage_warning_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.billing.check_all_usage_warnings",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def check_all_usage_warnings(self, threshold: float = 80.0) -> dict:
    """
    Check usage warnings for all active companies.

    Called by Celery Beat to proactively notify companies
    approaching their plan limits.

    Args:
        threshold: Usage percentage threshold (default: 80%)

    Returns:
        Dict with check summary
    """
    try:
        results = {
            "total_checked": 0,
            "warnings_sent": 0,
            "threshold": threshold,
        }

        with SessionLocal() as db:
            active_companies = db.query(Company).join(
                Subscription,
                Company.id == Subscription.company_id,
            ).filter(
                Subscription.status == "active",
            ).all()

            for company in active_companies:
                results["total_checked"] += 1
                # Dispatch individual check task
                send_usage_warning.delay(
                    company_id=str(company.id),
                    threshold=threshold,
                )

        logger.info(
            "check_all_usage_warnings_completed",
            extra={
                "task": self.name,
                "total_checked": results["total_checked"],
                "threshold": threshold,
            },
        )

        return results

    except Exception as exc:
        logger.error(
            "check_all_usage_warnings_failed",
            extra={
                "task": self.name,
                "error": str(exc)[:200],
            },
        )
        raise


# ═══════════════════════════════════════════════════════════════════════
# Day 2 Tasks: Period-End Transitions, Pre-Downgrade Warnings, Renewals
# ═══════════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.billing.process_period_end_transitions",
    max_retries=3,
    soft_time_limit=300,
    time_limit=600,
    retry_backoff=True,
)
def period_end_transitions(self) -> dict:
    """
    D1: Period-end automation cron task.

    Runs daily at midnight UTC. Processes:
    - D2: Apply pending downgrades where period_end <= today
    - D3: Apply scheduled cancellations where period_end <= today

    Returns:
        Dict with processing summary
    """
    try:
        from app.services.subscription_service import get_subscription_service
        service = get_subscription_service()
        result = service.process_period_end_transitions()

        logger.info(
            "period_end_transitions_completed",
            extra={
                "task": self.name,
                "downgrades_applied": result["downgrades_applied"],
                "cancellations_applied": result["cancellations_applied"],
                "errors": len(result["errors"]),
            },
        )

        return result

    except Exception as exc:
        logger.error(
            "period_end_transitions_failed",
            extra={
                "task": self.name,
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.billing.pre_downgrade_warnings",
    max_retries=2,
    soft_time_limit=120,
    time_limit=300,
)
def pre_downgrade_warnings(self) -> dict:
    """
    D5: Pre-downgrade warning task.

    7 days before period end with pending downgrade, send email + notification
    warning about what resources will be affected.

    Returns:
        Dict with warning summary
    """
    try:
        from app.services.subscription_service import get_subscription_service
        service = get_subscription_service()
        result = service.check_pre_downgrade_warnings()

        logger.info(
            "pre_downgrade_warnings_completed",
            extra={
                "task": self.name,
                "warnings_sent": result["warnings_sent"],
                "errors": len(result["errors"]),
            },
        )

        return result

    except Exception as exc:
        logger.error(
            "pre_downgrade_warnings_failed",
            extra={
                "task": self.name,
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.billing.process_renewals",
    max_retries=3,
    soft_time_limit=300,
    time_limit=600,
    retry_backoff=True,
)
def process_renewals(self) -> dict:
    """
    Y6: Process subscription renewals.

    At period end for active subscriptions (not canceled, not pending
    downgrade), renew the billing period.
    Send renewal reminder 30 days before.

    Returns:
        Dict with renewal summary
    """
    try:
        from app.services.subscription_service import get_subscription_service
        service = get_subscription_service()
        result = service.process_renewals()

        logger.info(
            "process_renewals_completed",
            extra={
                "task": self.name,
                "renewed": result["renewed"],
                "errors": len(result["errors"]),
            },
        )

        return result

    except Exception as exc:
        logger.error(
            "process_renewals_failed",
            extra={
                "task": self.name,
                "error": str(exc)[:200],
            },
        )
        raise


# ═══════════════════════════════════════════════════════════════════════
# Day 4 Tasks: Retention Cron, Payment Failure Timeout, Auto-Retry
# ═══════════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="billing.process_retention_cron",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def process_retention_cron(self) -> dict:
    """
    C6: Daily data retention policy cron.

    Runs daily to process canceled subscriptions past the 30-day
    retention period. Executes GDPR-compliant data cleanup:
    - Soft-delete tickets
    - Anonymize customer PII
    - Archive KB docs
    - RETAIN billing records (7-year financial compliance)

    Returns:
        Dict with processing summary
    """
    try:
        from app.services.data_retention_service import DataRetentionService
        service = DataRetentionService()
        result = service.process_retention_cron()

        logger.info(
            "process_retention_cron_completed",
            extra={
                "task": self.name,
                "companies_processed": result["companies_processed"],
                "errors": len(result["errors"]),
            },
        )

        return result

    except Exception as exc:
        logger.error(
            "process_retention_cron_failed",
            extra={
                "task": self.name,
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="billing.process_payment_failure_timeout",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def process_payment_failure_timeout(self) -> dict:
    """
    G2: Auto-cancel subscriptions after 7 days of payment failure.

    Queries all subscriptions with status=payment_failed where
    payment_failed_at + 7 days <= now. For each: cancel the
    subscription and enter 30-day data retention.

    Returns:
        Dict with processing summary
    """
    try:
        from app.services.subscription_service import get_subscription_service
        service = get_subscription_service()
        result = service.process_payment_failure_timeouts()

        logger.info(
            "payment_failure_timeout_completed",
            extra={
                "task": self.name,
                "canceled": result["subscriptions_canceled"],
                "errors": len(result["errors"]),
            },
        )

        return result

    except Exception as exc:
        logger.error(
            "payment_failure_timeout_failed",
            extra={
                "task": self.name,
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="billing.auto_retry_payments",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def auto_retry_payments(self) -> dict:
    """
    G3: Auto-retry failed payments on Day 1, 3, 5, 7 after failure.

    Checks all payment_failed subscriptions and retries if today
    is an eligible retry day (1, 3, 5, or 7 days after failure).
    Uses Paddle resume_subscription to trigger a new payment attempt.

    Returns:
        Dict with processing summary
    """
    try:
        from app.services.subscription_service import get_subscription_service
        service = get_subscription_service()
        result = service.process_auto_retry_payments()

        logger.info(
            "auto_retry_payments_completed",
            extra={
                "task": self.name,
                "attempted": result["retries_attempted"],
                "succeeded": result["retries_succeeded"],
                "errors": len(result["errors"]),
            },
        )

        return result

    except Exception as exc:
        logger.error(
            "auto_retry_payments_failed",
            extra={
                "task": self.name,
                "error": str(exc)[:200],
            },
        )
        raise


# ═══════════════════════════════════════════════════════════════════════
# Day 6 Tasks: Trial, Pause automation
# ═══════════════════════════════════════════════════════════════════════


@app.task(base=ParwaBaseTask, name="billing.send_trial_reminders")
def send_trial_reminders(self):
    """MF1: Send trial expiration reminders."""
    try:
        from app.services.trial_service import get_trial_service
        service = get_trial_service()
        result = service.send_trial_reminders()
        logger.info(
            "trial_reminders_completed",
            extra={
                "task": self.name,
                "reminders_sent": result.get(
                    "reminders_sent",
                    0)})
        return result
    except Exception as exc:
        logger.error(
            "trial_reminders_failed",
            extra={
                "task": self.name,
                "error": str(exc)[
                    :200]})
        raise


@app.task(base=ParwaBaseTask, name="billing.process_expired_trials")
def process_expired_trials(self):
    """MF1: Auto-expire trials past trial_ends_at."""
    try:
        from app.services.trial_service import get_trial_service
        service = get_trial_service()
        result = service.process_expired_trials()
        logger.info(
            "expired_trials_processed",
            extra={
                "task": self.name,
                "expired_count": result.get(
                    "expired_count",
                    0)})
        return result
    except Exception as exc:
        logger.error(
            "expired_trials_failed",
            extra={
                "task": self.name,
                "error": str(exc)[
                    :200]})
        raise


@app.task(base=ParwaBaseTask, name="billing.process_max_pause_exceeded")
def process_max_pause_exceeded(self):
    """MF2: Auto-resume subscriptions that exceeded max pause duration (30 days)."""
    try:
        from app.services.pause_service import get_pause_service
        service = get_pause_service()
        result = service.process_max_pause_exceeded()
        logger.info(
            "max_pause_exceeded_processed",
            extra={
                "task": self.name,
                "auto_resumed": result.get(
                    "auto_resumed",
                    0)})
        return result
    except Exception as exc:
        logger.error(
            "max_pause_exceeded_failed",
            extra={
                "task": self.name,
                "error": str(exc)[
                    :200]})
        raise


# ═══════════════════════════════════════════════════════════════════════
# Day 3.2: Redis-PostgreSQL Usage Sync (BG-13)
# ═══════════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="billing.sync_redis_usage_to_postgres",
    max_retries=3,
    soft_time_limit=300,
    time_limit=600,
)
@with_company_id
def sync_redis_usage_to_postgres(self, company_id: str) -> dict:
    """
    BG-13: Sync Redis usage counter to PostgreSQL.

    Runs periodically to ensure persistence and reconciliation.

    Args:
        company_id: Company UUID string

    Returns:
        Dict with sync status
    """
    import asyncio
    try:
        from app.services.usage_tracking_service import get_usage_tracking_service

        service = get_usage_tracking_service()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                service.sync_redis_to_postgres(company_id=company_id)
            )
        finally:
            loop.close()

        logger.info(
            "redis_usage_sync_completed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "status": result.get("status"),
                "redis_count": result.get("redis_count"),
                "postgres_count": result.get("postgres_count"),
            },
        )

        return result

    except Exception as exc:
        logger.error(
            "redis_usage_sync_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "error": str(exc)[:200],
            },
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="billing.sync_all_redis_usage",
    max_retries=2,
    soft_time_limit=600,
    time_limit=900,
)
def sync_all_redis_usage(self) -> dict:
    """
    BG-13: Sync Redis usage for all active companies.

    Called by Celery Beat daily (after midnight) to reconcile
    all Redis counters with PostgreSQL.
    """
    try:
        results = {
            "total_companies": 0,
            "synced": 0,
            "failed": 0,
            "errors": [],
        }

        with SessionLocal() as db:
            # Get all active companies
            active_companies = db.query(Company).join(
                Subscription,
                Company.id == Subscription.company_id,
            ).filter(
                Subscription.status == "active",
            ).all()

            results["total_companies"] = len(active_companies)

            for company in active_companies:
                try:
                    sync_redis_usage_to_postgres.delay(
                        company_id=str(company.id))
                    results["synced"] += 1
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({
                        "company_id": str(company.id),
                        "error": str(e)[:100],
                    })

        logger.info(
            "sync_all_redis_usage_completed",
            extra={
                "task": self.name,
                "total": results["total_companies"],
                "synced": results["synced"],
                "failed": results["failed"],
            },
        )

        return results

    except Exception as exc:
        logger.error(
            "sync_all_redis_usage_failed",
            extra={
                "task": self.name,
                "error": str(exc)[:200],
            },
        )
        raise
