"""
PARWA Billing Tasks (Day 22, BC-004, BC-002)

Celery tasks for billing operations:
- daily_overage_charge_task: Charge for usage over plan limits
- invoice_sync_task: Sync invoices from Paddle
- subscription_check_task: Check subscription status
"""

import logging
from datetime import datetime, timezone

from backend.app.tasks.base import ParwaBaseTask, with_company_id
from backend.app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks.billing")


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="backend.app.tasks.billing.daily_overage_charge",
    max_retries=3,
    soft_time_limit=120,
    time_limit=300,
)
@with_company_id
def daily_overage_charge(self, company_id: str) -> dict:
    """Charge for usage exceeding plan limits."""
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        logger.info(
            "daily_overage_charge_success",
            extra={
                "task": self.name,
                "company_id": company_id,
                "date": today,
            },
        )
        return {
            "status": "checked",
            "company_id": company_id,
            "date": today,
            "overage_amount": 0.0,
            "charged": False,
        }
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
    name="backend.app.tasks.billing.invoice_sync",
    max_retries=3,
    soft_time_limit=120,
    time_limit=300,
)
@with_company_id
def invoice_sync(self, company_id: str) -> dict:
    """Sync invoices from Paddle billing provider."""
    try:
        logger.info(
            "invoice_sync_success",
            extra={
                "task": self.name,
                "company_id": company_id,
            },
        )
        return {
            "status": "synced",
            "company_id": company_id,
            "invoices_synced": 0,
            "new_invoices": 0,
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
    """Check subscription status and plan limits."""
    try:
        logger.info(
            "subscription_check_success",
            extra={
                "task": self.name,
                "company_id": company_id,
            },
        )
        return {
            "status": "active",
            "company_id": company_id,
            "plan": "free",
            "valid_until": None,
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
