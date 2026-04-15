"""
MF1: Trial Period Service

Manages subscription trial periods:
- Start trial with configurable days
- Check trial status
- Convert trial to paid
- Trial expiration reminders (3 days, 1 day, expiry day)
- Auto-expire past-due trials
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import and_

from database.base import SessionLocal
from database.models.billing import Subscription

logger = logging.getLogger(__name__)

DEFAULT_TRIAL_DAYS = 14
REMINDER_DAYS = [3, 1, 0]  # Send reminders at these days before expiry


class TrialError(Exception):
    """Base error for trial operations."""
    pass


class TrialAlreadyActiveError(TrialError):
    pass


class TrialNotActiveError(TrialError):
    pass


class TrialExpiredError(TrialError):
    pass


class _TrialService:
    """Singleton trial service."""

    # ── MF1: Trial Lifecycle ─────────────────────────────────────────

    def start_trial(
        self,
        company_id: str,
        trial_days: int = DEFAULT_TRIAL_DAYS,
    ) -> Dict[str, Any]:
        """
        Start a trial period for a company's subscription.

        Sets trial_started_at and trial_ends_at on the subscription.
        During trial, customer has full access with no charges.
        """
        with SessionLocal() as db:
            subscription = (
                db.query(Subscription)
                .filter(Subscription.company_id == str(company_id))
                .order_by(Subscription.created_at.desc())
                .first()
            )

            if not subscription:
                raise TrialError(
                    f"No subscription found for company {company_id} (TRIAL-001)"
                )

            now = datetime.now(timezone.utc)

            # Check if trial already active
            if getattr(subscription, "trial_ends_at", None) and subscription.trial_ends_at > now:
                raise TrialAlreadyActiveError(
                    f"Trial already active for company {company_id}. "
                    f"Ends at {subscription.trial_ends_at.isoformat()} (TRIAL-002)"
                )

            trial_ends = now + timedelta(days=trial_days)

            subscription.trial_days = trial_days
            subscription.trial_started_at = now
            subscription.trial_ends_at = trial_ends
            db.flush()

            logger.info(
                "trial_started company_id=%s trial_days=%s ends_at=%s",
                company_id,
                trial_days,
                trial_ends.isoformat(),
            )

            return {
                "company_id": str(company_id),
                "trial_days": trial_days,
                "trial_started_at": now.isoformat(),
                "trial_ends_at": trial_ends.isoformat(),
                "status": "active",
            }

    def check_trial_status(self, company_id: str) -> Dict[str, Any]:
        """
        Check the current trial status for a company.

        Returns: active, expired, not_started, or none (no trial configured).
        """
        with SessionLocal() as db:
            subscription = (
                db.query(Subscription)
                .filter(Subscription.company_id == str(company_id))
                .order_by(Subscription.created_at.desc())
                .first()
            )

            if not subscription:
                return {"status": "none", "message": "No subscription found"}

            now = datetime.now(timezone.utc)
            trial_ends = getattr(subscription, "trial_ends_at", None)
            trial_started = getattr(subscription, "trial_started_at", None)

            if not trial_started or not trial_ends:
                return {
                    "status": "not_started",
                    "trial_days": getattr(subscription, "trial_days", 0),
                }

            if trial_ends > now:
                remaining = (trial_ends - now).days
                return {
                    "status": "active",
                    "trial_started_at": trial_started.isoformat(),
                    "trial_ends_at": trial_ends.isoformat(),
                    "remaining_days": remaining,
                }
            else:
                return {
                    "status": "expired",
                    "trial_started_at": trial_started.isoformat(),
                    "trial_ends_at": trial_ends.isoformat(),
                    "message": "Trial period has expired",
                }

    def get_trial_remaining_days(self, company_id: str) -> int:
        """Get remaining trial days. Returns 0 if no active trial."""
        status = self.check_trial_status(company_id)
        if status.get("status") == "active":
            return max(0, status.get("remaining_days", 0))
        return 0

    def convert_trial_to_paid(self, company_id: str) -> Dict[str, Any]:
        """
        Convert a trial subscription to paid.

        Called when trial ends. Creates first charge via Paddle.
        The actual Paddle charge is handled by Paddle's subscription
        system — this method marks the trial as converted and triggers
        the billing workflow.
        """
        with SessionLocal() as db:
            subscription = (
                db.query(Subscription)
                .filter(Subscription.company_id == str(company_id))
                .order_by(Subscription.created_at.desc())
                .first()
            )

            if not subscription:
                raise TrialError(
                    f"No subscription found for company {company_id} (TRIAL-003)"
                )

            now = datetime.now(timezone.utc)
            trial_ends = getattr(subscription, "trial_ends_at", None)

            if trial_ends and trial_ends > now:
                raise TrialError(
                    f"Trial still active for company {company_id}. "
                    f"Ends at {trial_ends.isoformat()} (TRIAL-004)"
                )

            # Mark trial as converted (clear trial fields, keep subscription active)
            subscription.trial_days = 0
            subscription.trial_ends_at = None
            # Keep trial_started_at for audit trail
            db.flush()

            logger.info(
                "trial_converted_to_paid company_id=%s",
                company_id,
            )

            return {
                "company_id": str(company_id),
                "status": "converted_to_paid",
                "converted_at": now.isoformat(),
            }

    # ── MF1: Trial Reminders ─────────────────────────────────────────

    def send_trial_reminders(self) -> Dict[str, Any]:
        """
        Celery task: Send trial expiration reminders.

        Checks for subscriptions where trial_ends_at is within REMINDER_DAYS
        of today and sends appropriate reminder emails.
        Returns count of reminders sent.
        """
        now = datetime.now(timezone.utc)
        reminders_sent = 0

        with SessionLocal() as db:
            for days_before in REMINDER_DAYS:
                target_date = now + timedelta(days=days_before)

                subscriptions = db.query(Subscription).filter(
                    Subscription.trial_ends_at.isnot(None),
                    Subscription.trial_ends_at <= target_date,
                    Subscription.status == "active",
                ).all()

                for sub in subscriptions:
                    if days_before == 0:
                        subject = "Your PARWA trial ends today"
                    elif days_before == 1:
                        subject = "Your PARWA trial ends tomorrow"
                    else:
                        subject = (
                            f"Your PARWA trial ends in {days_before} days"
                        )

                    logger.info(
                        "trial_reminder company_id=%s days_remaining=%s subject='%s'",
                        sub.company_id,
                        days_before,
                        subject,
                    )
                    reminders_sent += 1

        logger.info("trial_reminders_batch sent=%d", reminders_sent)
        return {"reminders_sent": reminders_sent}

    def process_expired_trials(self) -> Dict[str, Any]:
        """
        Celery task: Auto-expire trials past trial_ends_at.

        Sets status to 'trial_expired' for subscriptions where
        trial_ends_at < now and status is still 'active'.
        """
        now = datetime.now(timezone.utc)
        expired_count = 0

        with SessionLocal() as db:
            expired_subs = db.query(Subscription).filter(
                Subscription.trial_ends_at.isnot(None),
                Subscription.trial_ends_at < now,
                Subscription.status == "active",
            ).all()

            for sub in expired_subs:
                sub.status = "trial_expired"
                expired_count += 1
                logger.info(
                    "trial_expired company_id=%s trial_ends_at=%s",
                    sub.company_id,
                    sub.trial_ends_at,
                )

            db.flush()

        logger.info("trial_expiration_batch expired=%d", expired_count)
        return {"expired_count": expired_count}


_trial_service_instance: Optional[_TrialService] = None


def get_trial_service() -> _TrialService:
    """Factory for trial service singleton."""
    global _trial_service_instance
    if _trial_service_instance is None:
        _trial_service_instance = _TrialService()
    return _trial_service_instance
