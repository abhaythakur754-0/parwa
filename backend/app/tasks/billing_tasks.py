"""
PARWA Billing Tasks (Day 22, Day 23, BC-004, BC-002)

Celery tasks for billing operations:
- daily_overage_charge_task: Charge for usage over plan limits (F-024)
- invoice_sync_task: Invoice sync (Paddle was removed — now a no-op)
- subscription_check_task: Check subscription status (Paddle was removed — now a no-op)
- process_all_overages_task: Batch process overages for all companies
- send_usage_warning_task: Send warning when approaching limit
- send_renewal_reminder_task: Send renewal reminder X days before auto-charge
- check_all_renewal_reminders_task: Batch dispatch renewal reminders
- subscription_check_all_task: Batch dispatch subscription status syncs
"""

import logging
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import Dict, List, Any

from app.tasks.base_task import ParwaBaseTask, with_company_id
from app.tasks.celery_app import app
from app.tasks.error_callbacks import billing_failure_callback
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
    link_error=billing_failure_callback.s(),  # CL-04: Alert on permanent failure
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
    5. Records the overage charge in the DB (Paddle was removed)
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
            process_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

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
    link_error=billing_failure_callback.s(),  # CL-04: Alert on permanent failure
)
@with_company_id
def invoice_sync(self, company_id: str) -> dict:
    """
    Sync invoices from billing provider.

    F-023: Invoice History

    NOTE: Paddle was removed; invoices are now generated DB-side by
    invoice_service. This task is kept as a no-op so the existing Celery
    Beat schedule / scheduler registrations don't break.

    Args:
        company_id: Company UUID string

    Returns:
        Dict with sync status and invoice count
    """
    logger.info(
        "invoice_sync_skipped",
        extra={
            "task": self.name,
            "company_id": company_id,
            "reason": "Paddle was removed; invoices are DB-managed",
        },
    )
    return {
        "status": "skipped",
        "company_id": company_id,
        "reason": "Paddle was removed; invoices are DB-managed",
        "invoices_synced": 0,
        "new_invoices": 0,
    }


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.billing.subscription_check",
    max_retries=2,
    soft_time_limit=60,
    time_limit=120,
    link_error=billing_failure_callback.s(),  # CL-04: Alert on permanent failure
)
@with_company_id
def subscription_check(self, company_id: str) -> dict:
    """
    Check subscription status and plan limits.

    NOTE: Paddle was removed; subscription status is now sourced directly
    from the local DB (managed by subscription_service / Razorpay webhooks).
    This task is kept as a no-op so the existing Celery Beat schedule /
    scheduler registrations don't break.

    Args:
        company_id: Company UUID string

    Returns:
        Dict with subscription status
    """
    try:
        with SessionLocal() as db:
            subscription = db.query(Subscription).filter(
                Subscription.company_id == company_id,
            ).order_by(Subscription.created_at.desc()).first()

            if not subscription:
                result = {
                    "status": "not_found",
                    "company_id": company_id,
                    "plan": None,
                    "valid_until": None,
                }
            else:
                result = {
                    "status": subscription.status,
                    "company_id": company_id,
                    "plan": subscription.tier,
                    "valid_until": subscription.current_period_end.isoformat()
                    if subscription.current_period_end
                    else None,
                }

        logger.info(
            "subscription_check_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "plan": result.get("plan"),
                "status": result.get("status"),
                "source": "db_only",
            },
        )
        return result

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
    link_error=billing_failure_callback.s(),  # CL-04: Alert on permanent failure
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
                    )
                )
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


# ── Renewal Reminder Tasks (Netflix-style auto-charge heads-up) ────────


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.billing.send_renewal_reminder",
    max_retries=2,
    soft_time_limit=60,
    time_limit=120,
    link_error=billing_failure_callback.s(),
)
@with_company_id
def send_renewal_reminder(
    self,
    company_id: str,
    days_before: int = 7,
) -> dict:
    """
    Send a renewal reminder for a company's upcoming auto-charge.

    The billing provider auto-charges the saved payment method on
    `current_period_end` (Razorpay; Paddle was removed). This task runs
    X days before that date to notify the subscriber ("Your subscription
    renews on YYYY-MM-DD, $XXX will be charged").

    Args:
        company_id: Company UUID string
        days_before: Send reminder if renewal is within this many days

    Returns:
        Dict with reminder status
    """
    try:
        with SessionLocal() as db:
            subscription = db.query(Subscription).filter(
                Subscription.company_id == company_id,
                Subscription.status == "active",
            ).order_by(Subscription.created_at.desc()).first()

            if not subscription:
                return {
                    "status": "no_subscription",
                    "company_id": company_id,
                    "reminder_sent": False,
                }

            if not subscription.current_period_end:
                return {
                    "status": "no_renewal_date",
                    "company_id": company_id,
                    "reminder_sent": False,
                }

            # Compute days until renewal
            now = datetime.now(timezone.utc)
            renewal_date = subscription.current_period_end
            if renewal_date.tzinfo is None:
                renewal_date = renewal_date.replace(tzinfo=timezone.utc)

            days_until_renewal = (renewal_date - now).days

            # Only send reminder if within the window and not past due
            if days_until_renewal < 0 or days_until_renewal > days_before:
                return {
                    "status": "outside_window",
                    "company_id": company_id,
                    "days_until_renewal": days_until_renewal,
                    "reminder_sent": False,
                }

            # Skip if subscription is set to cancel at period end
            if subscription.cancel_at_period_end:
                return {
                    "status": "canceling",
                    "company_id": company_id,
                    "days_until_renewal": days_until_renewal,
                    "reminder_sent": False,
                }

            # Look up the variant price for the reminder message
            try:
                from app.core.pricing_config import get_variant_price
                amount = get_variant_price(subscription.tier, "monthly")
            except Exception:
                amount = None

            renewal_iso = renewal_date.date().isoformat()

            # Emit billing event (socket.io + downstream notification)
            from app.core.event_emitter import emit_billing_event
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    emit_billing_event(
                        company_id=company_id,
                        event_type="renewal_reminder",
                        data={
                            "variant": subscription.tier,
                            "renewal_date": renewal_iso,
                            "days_until_renewal": days_until_renewal,
                            "amount": str(amount) if amount else None,
                            "currency": "USD",
                            "message": (
                                f"Your {subscription.tier} plan renews on "
                                f"{renewal_iso}. "
                                f"{f'${amount} will be charged.' if amount else ''}"
                            ),
                        },
                    )
                )
            finally:
                loop.close()

        logger.info(
            "renewal_reminder_sent",
            extra={
                "task": self.name,
                "company_id": company_id,
                "days_until_renewal": days_until_renewal,
                "renewal_date": renewal_iso,
            },
        )

        return {
            "status": "sent",
            "company_id": company_id,
            "days_until_renewal": days_until_renewal,
            "renewal_date": renewal_iso,
            "amount": str(amount) if amount else None,
            "reminder_sent": True,
        }

    except Exception as exc:
        logger.error(
            "renewal_reminder_failed",
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
    name="app.tasks.billing.check_all_renewal_reminders",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def check_all_renewal_reminders(self, days_before: int = 7) -> dict:
    """
    Batch dispatch renewal reminders for all active subscribers.

    Called by Celery Beat daily. For each active subscription, dispatches
    a send_renewal_reminder task that decides whether to actually send
    based on days-until-renewal window.

    Args:
        days_before: Send reminder if renewal is within this many days (default 7)

    Returns:
        Dict with batch summary
    """
    try:
        results = {
            "total_checked": 0,
            "reminders_dispatched": 0,
            "days_before": days_before,
        }

        with SessionLocal() as db:
            active_subs = db.query(Subscription).filter(
                Subscription.status == "active",
                Subscription.current_period_end.isnot(None),
            ).all()

            for sub in active_subs:
                results["total_checked"] += 1
                send_renewal_reminder.delay(
                    company_id=str(sub.company_id),
                    days_before=days_before,
                )
                results["reminders_dispatched"] += 1

        logger.info(
            "check_all_renewal_reminders_completed",
            extra={
                "task": self.name,
                "total_checked": results["total_checked"],
                "dispatched": results["reminders_dispatched"],
            },
        )

        return results

    except Exception as exc:
        logger.error(
            "check_all_renewal_reminders_failed",
            extra={"task": self.name, "error": str(exc)[:200]},
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.billing.subscription_check_all",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def subscription_check_all(self) -> dict:
    """
    Batch dispatch subscription status syncs for all companies.

    Called by Celery Beat daily. For each company with a subscription,
    dispatches a subscription_check task that reads local DB status
    (Paddle was removed; status is managed by Razorpay webhooks).

    Returns:
        Dict with batch summary
    """
    try:
        results = {"total_checked": 0, "dispatched": 0}

        with SessionLocal() as db:
            companies_with_subs = db.query(
                Company.id
            ).join(
                Subscription,
                Company.id == Subscription.company_id,
            ).distinct().all()

            for (company_id,) in companies_with_subs:
                results["total_checked"] += 1
                subscription_check.delay(company_id=str(company_id))
                results["dispatched"] += 1

        logger.info(
            "subscription_check_all_completed",
            extra={
                "task": self.name,
                "total": results["total_checked"],
                "dispatched": results["dispatched"],
            },
        )

        return results

    except Exception as exc:
        logger.error(
            "subscription_check_all_failed",
            extra={"task": self.name, "error": str(exc)[:200]},
        )
        raise
