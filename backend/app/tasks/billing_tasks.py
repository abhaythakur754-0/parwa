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
from typing import Dict, List, Any

from backend.app.tasks.base import ParwaBaseTask, with_company_id
from backend.app.tasks.celery_app import app
from database.base import SessionLocal
from database.models.core import Company
from database.models.billing import Subscription

logger = logging.getLogger("parwa.tasks.billing")


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="backend.app.tasks.billing.daily_overage_charge",
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
        from backend.app.services.overage_service import get_overage_service
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
    name="backend.app.tasks.billing.process_all_overages",
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
    name="backend.app.tasks.billing.invoice_sync",
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
        from backend.app.clients.paddle_client import get_paddle_client
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
                    paddle.get_invoices(customer_id=company.paddle_customer_id)
                )
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
                        company_id=company_id,
                        paddle_invoice_id=paddle_invoice_id,
                        amount=Decimal(str(inv_data.get("total", 0))),
                        currency=inv_data.get("currency", "USD"),
                        status=inv_data.get("status", "draft"),
                        invoice_date=datetime.fromisoformat(
                            inv_data.get("created_at", datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")
                        ) if inv_data.get("created_at") else None,
                    )
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
    name="backend.app.tasks.billing.subscription_check",
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
        from backend.app.clients.paddle_client import get_paddle_client
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
                        paddle.get_subscription(subscription.paddle_subscription_id)
                    )
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
    name="backend.app.tasks.billing.send_usage_warning",
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
        from backend.app.services.overage_service import get_overage_service
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
            from backend.app.core.event_emitter import emit_billing_event

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
    name="backend.app.tasks.billing.check_all_usage_warnings",
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
