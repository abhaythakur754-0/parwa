"""
MF2: Subscription Pause/Resume Service

Manages temporary subscription pauses:
- Pause subscription (max 30 days, 1 per 6 months)
- Resume subscription (extend period end by pause duration)
- Auto-resume if pause exceeds max
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


from database.base import SessionLocal
from database.models.billing import Subscription
from database.models.billing_extended import PauseRecord

logger = logging.getLogger(__name__)

MAX_PAUSE_DAYS = 30
MIN_PAUSE_INTERVAL_DAYS = 180  # 6 months


class PauseError(Exception):
    """Base error for pause operations."""


class AlreadyPausedError(PauseError):
    pass


class MaxPauseExceededError(PauseError):
    pass


class PauseCooldownError(PauseError):
    pass


class NotPausedError(PauseError):
    pass


class _PauseService:
    """Singleton pause service."""

    def pause_subscription(self, company_id: str) -> Dict[str, Any]:
        """
        Pause a company's subscription temporarily.

        Rules:
        - Max 30 days pause duration
        - 1 pause per 6 months
        - Stops agents, disables channels
        - No charges during pause
        """
        with SessionLocal() as db:
            subscription = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == "active",
                )
                .order_by(Subscription.created_at.desc())
                .first()
            )

            if not subscription:
                raise PauseError(
                    f"No active subscription for company {company_id} (PAUSE-001)")

            now = datetime.now(timezone.utc)

            # Check if already paused
            existing_pause = (
                db.query(PauseRecord)
                .filter(
                    PauseRecord.company_id == str(company_id),
                    PauseRecord.resumed_at.is_(None),
                )
                .first()
            )
            if existing_pause:
                raise AlreadyPausedError(
                    "Subscription already paused since "
                    f"{existing_pause.paused_at.isoformat()} (PAUSE-002)"
                )

            # Check cooldown (1 pause per 6 months)
            recent_pause = (
                db.query(PauseRecord) .filter(
                    PauseRecord.company_id == str(company_id),
                    PauseRecord.resumed_at.isnot(None),
                    PauseRecord.resumed_at > now
                    - timedelta(
                        days=MIN_PAUSE_INTERVAL_DAYS),
                ) .first())
            if recent_pause:
                days_since = (now - recent_pause.resumed_at).days
                raise PauseCooldownError(
                    f"Cannot pause again. Last pause resumed {days_since} days ago. "
                    f"Minimum interval: {MIN_PAUSE_INTERVAL_DAYS} days (PAUSE-003)"
                )

            # Create pause record
            pause = PauseRecord(
                company_id=str(company_id),
                subscription_id=subscription.id,
                paused_at=now,
                max_pause_days=MAX_PAUSE_DAYS,
            )
            db.add(pause)

            # Update subscription status
            subscription.status = "paused"
            db.flush()

            logger.info(
                "subscription_paused company_id=%s paused_at=%s",
                company_id,
                now.isoformat(),
            )

            return {
                "company_id": str(company_id),
                "paused_at": now.isoformat(),
                "max_pause_days": MAX_PAUSE_DAYS,
                "auto_resume_at": (
                    now
                    + timedelta(
                        days=MAX_PAUSE_DAYS)).isoformat(),
                "status": "paused",
            }

    def resume_subscription(self, company_id: str) -> Dict[str, Any]:
        """
        Resume a paused subscription.

        Extends period_end by the number of days paused.
        Restores agents and channels.
        """
        with SessionLocal() as db:
            pause = (
                db.query(PauseRecord)
                .filter(
                    PauseRecord.company_id == str(company_id),
                    PauseRecord.resumed_at.is_(None),
                )
                .first()
            )

            if not pause:
                raise NotPausedError(
                    f"No active pause found for company {company_id} (PAUSE-004)")

            now = datetime.now(timezone.utc)
            pause_duration = (now - pause.paused_at).days
            pause.resumed_at = now
            pause.pause_duration_days = pause_duration
            pause.period_end_extension_days = pause_duration
            db.flush()

            # Update subscription status and extend period
            subscription = (
                db.query(Subscription)
                .filter(Subscription.id == pause.subscription_id)
                .first()
            )
            if subscription:
                subscription.status = "active"
                if hasattr(
                        subscription,
                        "current_period_end") and subscription.current_period_end:
                    subscription.current_period_end = (
                        subscription.current_period_end
                        + timedelta(
                            days=pause_duration))
                db.flush()

            logger.info(
                "subscription_resumed company_id=%s pause_duration=%s days",
                company_id,
                pause_duration,
            )

            return {
                "company_id": str(company_id),
                "resumed_at": now.isoformat(),
                "pause_duration_days": pause_duration,
                "period_end_extended_by": pause_duration,
                "status": "active",
            }

    def get_pause_status(self, company_id: str) -> Dict[str, Any]:
        """Get current pause status for a company."""
        with SessionLocal() as db:
            pause = (
                db.query(PauseRecord)
                .filter(
                    PauseRecord.company_id == str(company_id),
                    PauseRecord.resumed_at.is_(None),
                )
                .first()
            )

            if not pause:
                return {"status": "not_paused"}

            now = datetime.now(timezone.utc)
            days_paused = (now - pause.paused_at).days
            remaining = max(0, pause.max_pause_days - days_paused)

            return {
                "status": "paused",
                "paused_at": pause.paused_at.isoformat(),
                "days_paused": days_paused,
                "remaining_days": remaining,
                "max_pause_days": pause.max_pause_days,
                "auto_resume_at": (
                    pause.paused_at + timedelta(days=pause.max_pause_days)
                ).isoformat(),
            }

    def process_max_pause_exceeded(self) -> Dict[str, Any]:
        """
        Celery task: Auto-resume subscriptions that exceeded max pause duration.
        """
        now = datetime.now(timezone.utc)
        auto_resumed = 0

        with SessionLocal() as db:
            expired_pauses = db.query(PauseRecord).filter(
                PauseRecord.resumed_at.is_(None),
                PauseRecord.paused_at < now - timedelta(days=MAX_PAUSE_DAYS),
            ).all()

            for pause in expired_pauses:
                pause_duration = MAX_PAUSE_DAYS
                pause.resumed_at = now
                pause.pause_duration_days = pause_duration
                pause.period_end_extension_days = pause_duration

                subscription = (
                    db.query(Subscription)
                    .filter(Subscription.id == pause.subscription_id)
                    .first()
                )
                if subscription:
                    subscription.status = "active"
                    if hasattr(
                            subscription,
                            "current_period_end") and subscription.current_period_end:
                        subscription.current_period_end = (
                            subscription.current_period_end
                            + timedelta(
                                days=pause_duration))

                auto_resumed += 1
                logger.info(
                    "pause_auto_resumed company_id=%s duration=%s days",
                    pause.company_id,
                    pause_duration,
                )

            db.flush()

        logger.info("pause_auto_resume_batch resumed=%d", auto_resumed)
        return {"auto_resumed": auto_resumed}


_pause_service_instance: Optional[_PauseService] = None


def get_pause_service() -> _PauseService:
    """Factory for pause service singleton."""
    global _pause_service_instance
    if _pause_service_instance is None:
        _pause_service_instance = _PauseService()
    return _pause_service_instance
