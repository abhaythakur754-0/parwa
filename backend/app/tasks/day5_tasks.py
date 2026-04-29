"""
PARWA Day 5 Tasks — Financial Safety, Webhook Health, Anomaly Detection

Celery tasks for:
- Dead letter queue processing (WH3)
- Daily anomaly detection (FS2)
- Weekly invoice audit (FS3)
- Webhook health check (WH2)
- Soft cap alert check (SC3)
- Credit balance expiry
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any

from app.tasks.base import ParwaBaseTask
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks.day5")


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.day5.process_dead_letter_queue",
    max_retries=2,
    soft_time_limit=120,
    time_limit=300,
)
def process_dead_letter_queue(self) -> dict:
    """
    Process the dead letter queue for failed webhooks. (WH3)

    Finds all pending/retrying webhooks where next_retry_at <= now
    and attempts to re-process each one. On success marks as "processed",
    on failure increments retry count with exponential backoff.

    Runs hourly via Celery Beat.

    Returns:
        Dict with processing summary: processed, failed, exhausted, errors
    """
    try:
        from app.services.webhook_health_service import WebhookHealthService

        service = WebhookHealthService()
        result = service.process_dead_letter_queue()

        logger.info(
            "process_dead_letter_queue_completed",
            extra={
                "task": self.name,
                "processed": result.get("processed", 0),
                "failed": result.get("failed", 0),
                "exhausted": result.get("exhausted", 0),
                "errors": len(result.get("errors", [])),
            },
        )

        return result

    except Exception as exc:
        logger.error(
            "process_dead_letter_queue_failed",
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
    name="app.tasks.day5.daily_anomaly_check",
    max_retries=2,
    soft_time_limit=120,
    time_limit=300,
)
def daily_anomaly_check(self) -> dict:
    """
    Run daily anomaly detection for all active companies. (FS2)

    Compares today's ticket volume against yesterday's for each company
    with an active subscription. Flags companies where volume exceeds
    3x yesterday's (and yesterday >= 100 tickets).

    Runs daily via Celery Beat.

    Returns:
        Dict with anomaly check summary: companies_checked, anomalies_found, anomalies
    """
    try:
        from app.services.financial_safety_service import FinancialSafetyService

        service = FinancialSafetyService()
        result = service.run_daily_anomaly_check()

        logger.info(
            "daily_anomaly_check_completed",
            extra={
                "task": self.name,
                "companies_checked": result.get("companies_checked", 0),
                "anomalies_found": result.get("anomalies_found", 0),
                "errors": len(result.get("errors", [])),
            },
        )

        return result

    except Exception as exc:
        logger.error(
            "daily_anomaly_check_failed",
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
    name="app.tasks.day5.weekly_invoice_audit",
    max_retries=2,
    soft_time_limit=120,
    time_limit=300,
)
def weekly_invoice_audit(self) -> dict:
    """
    Run weekly invoice audit for all companies. (FS3)

    Reconciles local invoice records against Paddle invoices for every
    company with a Paddle customer ID. Flags mismatches, missing local,
    and missing Paddle records. Auto-syncs missing local invoices.

    Runs weekly on Monday via Celery Beat.

    Returns:
        Dict with audit summary: companies_audited, total_matched,
        total_mismatched, companies_with_issues
    """
    try:
        from app.services.financial_safety_service import FinancialSafetyService

        service = FinancialSafetyService()
        result = service.run_weekly_invoice_audit()

        logger.info(
            "weekly_invoice_audit_completed",
            extra={
                "task": self.name,
                "companies_audited": result.get("companies_audited", 0),
                "total_matched": result.get("total_matched", 0),
                "total_mismatched": result.get("total_mismatched", 0),
                "companies_with_issues": result.get("companies_with_issues", 0),
                "errors": len(result.get("errors", [])),
            },
        )

        return result

    except Exception as exc:
        logger.error(
            "weekly_invoice_audit_failed",
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
    name="app.tasks.day5.webhook_health_summary",
    max_retries=2,
    soft_time_limit=120,
    time_limit=300,
)
def webhook_health_summary(self) -> dict:
    """
    Generate webhook health summary report. (WH2)

    Retrieves webhook health metrics for the past 7 days including
    total received/processed/failed counts, failure rate, and average
    processing time. Flags alert conditions.

    Runs daily via Celery Beat.

    Returns:
        Dict with health summary: total_received, total_processed,
        total_failed, failure_rate, alerts
    """
    try:
        from app.services.webhook_health_service import WebhookHealthService

        service = WebhookHealthService()
        result = service.get_webhook_health(provider="paddle", days=7)

        logger.info(
            "webhook_health_summary_completed",
            extra={
                "task": self.name,
                "total_received": result.get("total_received", 0),
                "total_processed": result.get("total_processed", 0),
                "total_failed": result.get("total_failed", 0),
                "failure_rate": result.get("failure_rate", "0.00"),
                "alerts": len(result.get("alerts", [])),
            },
        )

        return result

    except Exception as exc:
        logger.error(
            "webhook_health_summary_failed",
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
    name="app.tasks.day5.check_spending_caps",
    max_retries=2,
    soft_time_limit=120,
    time_limit=300,
)
def check_spending_caps(self) -> dict:
    """
    Check soft-cap alerts for all companies with active caps. (SC3)

    Iterates all companies that have an active spending cap configured,
    calculates their current month's overage, and fires soft-cap alert
    notifications for thresholds that have been crossed.

    Runs daily via Celery Beat.

    Returns:
        Dict with check summary: companies_checked, alerts_triggered, errors
    """
    try:
        from app.services.spending_cap_service import SpendingCapService

        cap_service = SpendingCapService()

        results: Dict[str, Any] = {
            "companies_checked": 0,
            "alerts_triggered": 0,
            "companies_with_alerts": [],
            "errors": [],
        }

        from database.base import SessionLocal

        with SessionLocal() as db:
            # Lazily import the SpendingCap model (may not exist yet)
            try:
                from database.models.billing_extended import (
                    SpendingCap as SpendingCapModel,
                )

                table_available = True
            except ImportError:
                table_available = False
                logger.warning(
                    "check_spending_caps_table_unavailable",
                    extra={"task": self.name},
                )

            if not table_available:
                return {
                    **results,
                    "message": "Spending cap table not available.",
                }

            # Get all active caps
            active_caps = (
                db.query(SpendingCapModel)
                .filter(SpendingCapModel.is_active is True)  # noqa: E712
                .all()
            )

            results["companies_checked"] = len(active_caps)

            for cap in active_caps:
                try:
                    # Calculate current month overage for this company
                    from sqlalchemy import func
                    from database.models.billing_extended import UsageRecord

                    current_month = datetime.now(timezone.utc).strftime("%Y-%m")

                    current_overage = (
                        db.query(
                            func.coalesce(
                                func.sum(UsageRecord.overage_charges),
                                Decimal("0.00"),
                            )
                        )
                        .filter(
                            UsageRecord.company_id == cap.company_id,
                            UsageRecord.record_month == current_month,
                        )
                        .scalar()
                    )

                    current_overage = Decimal(str(current_overage or 0))

                    # Check soft-cap alerts
                    alerts = cap_service.check_soft_cap_alerts(
                        company_id=cap.company_id,
                        current_overage_amount=current_overage,
                    )

                    if alerts.get("alerts"):
                        results["alerts_triggered"] += len(alerts["alerts"])
                        results["companies_with_alerts"].append(
                            {
                                "company_id": cap.company_id,
                                "current_overage": str(current_overage),
                                "max_cap": str(cap.max_overage_amount),
                                "alerts_fired": len(alerts["alerts"]),
                            }
                        )

                except Exception as exc:
                    results["errors"].append(
                        {
                            "company_id": str(cap.company_id) if cap else "unknown",
                            "error": str(exc)[:200],
                        }
                    )

        logger.info(
            "check_spending_caps_completed",
            extra={
                "task": self.name,
                "companies_checked": results["companies_checked"],
                "alerts_triggered": results["alerts_triggered"],
                "errors": len(results["errors"]),
            },
        )

        return results

    except Exception as exc:
        logger.error(
            "check_spending_caps_failed",
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
    name="app.tasks.day5.expire_credits",
    max_retries=2,
    soft_time_limit=120,
    time_limit=300,
)
def expire_credits(self) -> dict:
    """
    Expire credit balances that have passed their expires_at date.

    Finds all credit balance records where expires_at <= now and
    sets their status to "expired". This ensures expired credits
    are no longer usable for overage offsets.

    Runs daily via Celery Beat.

    Returns:
        Dict with expiry summary: total_expired, errors
    """
    try:
        from database.base import SessionLocal

        results: Dict[str, Any] = {
            "total_expired": 0,
            "errors": [],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        now = datetime.now(timezone.utc)

        # Lazily import the CreditBalance model (may not exist yet)
        try:
            from database.models.billing_extended import CreditBalance

            table_available = True
        except ImportError:
            table_available = False
            logger.warning(
                "expire_credits_table_unavailable",
                extra={"task": self.name},
            )
            return {
                **results,
                "message": "Credit balance table not available.",
            }

        with SessionLocal() as db:
            # Find all unexpired credit balances past their expiration
            expired_credits = (
                db.query(CreditBalance)
                .filter(
                    CreditBalance.expires_at <= now,
                    CreditBalance.status == "active",  # noqa: E712
                )
                .all()
            )

            for credit in expired_credits:
                try:
                    credit.status = "expired"
                    results["total_expired"] += 1

                    logger.info(
                        "credit_expired id=%s company_id=%s amount=%s",
                        credit.id,
                        credit.company_id,
                        credit.amount,
                        extra={
                            "task": self.name,
                        },
                    )

                except Exception as exc:
                    results["errors"].append(
                        {
                            "credit_id": str(credit.id) if credit else "unknown",
                            "error": str(exc)[:200],
                        }
                    )

            if expired_credits:
                db.commit()

        logger.info(
            "expire_credits_completed",
            extra={
                "task": self.name,
                "total_expired": results["total_expired"],
                "errors": len(results["errors"]),
            },
        )

        return results

    except Exception as exc:
        logger.error(
            "expire_credits_failed",
            extra={
                "task": self.name,
                "error": str(exc)[:200],
            },
        )
        raise
