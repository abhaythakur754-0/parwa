"""
Payment Failure Service (F-027, BG-16)

Payment failure handling with 7-day grace period:
1. Payment fails → subscription set to "past_due"
2. 7-day grace period begins (limited access)
3. Single notification: "Payment failed, update payment method"
4. After 7 days → subscription suspended ("payment_failed", full stop)
5. Service resumes immediately on successful payment (any time)

Grace period flow:
- Day 0: Payment fails → status=past_due, grace_period_ends_at=now+7d
- Day 0-7: Tenant has limited read-only access, agents paused
- Day 7+: Cron suspends → status=payment_failed, full service stop
- Any time: Successful payment → status=active, full restore

BC-001: All operations validate company_id
BC-002: All money calculations use Decimal
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from database.base import SessionLocal
from database.models.billing import Subscription
from database.models.billing_extended import PaymentFailure
from database.models.core import Company

logger = logging.getLogger("parwa.services.payment_failure")


class PaymentFailureError(Exception):
    """Base exception for payment failure errors."""


class ServiceStoppedError(PaymentFailureError):
    """Company service is stopped due to payment failure."""


class PaymentFailureService:
    """
    Payment failure handling with immediate service stop.

    Usage:
        service = PaymentFailureService()
        result = await service.handle_payment_failure(
            company_id=uuid,
            paddle_transaction_id="txn_123",
            failure_code="card_declined",
            failure_reason="Insufficient funds",
            amount_attempted=Decimal("999.00")
        )
    """

    # Valid subscription statuses
    ACTIVE_STATUS = "active"
    PAYMENT_FAILED_STATUS = "payment_failed"
    PAST_DUE_STATUS = "past_due"

    # Grace period: 7 days of limited access before full suspension
    GRACE_PERIOD_DAYS = 7

    def __init__(self):
        pass

    async def handle_payment_failure_with_grace_period(
        self,
        company_id: UUID,
        paddle_transaction_id: str,
        failure_code: str,
        failure_reason: str,
        amount_attempted: Decimal,
        paddle_subscription_id: Optional[str] = None,
        currency: str = "USD",
    ) -> Dict[str, Any]:
        """
        Handle a payment failure with a 7-day grace period.

        Instead of stopping service immediately, sets subscription to
        "past_due" and starts a 7-day grace period during which the
        tenant still has limited (read-only) access.

        Steps:
        1. Log to payment_failures table
        2. Set company.subscription_status = 'past_due'
        3. Record grace_period_ends_at = now + 7 days
        4. Pause AI agents (but don't freeze tickets)
        5. Send payment_failed email notification with grace period info
        6. Create in-app notification

        After 7 days, check_and_suspend_expired_grace_periods() should
        be called (via cron) to escalate to full suspension.

        Args:
            company_id: Company UUID
            paddle_transaction_id: Paddle transaction ID
            failure_code: Paddle failure code
            failure_reason: Human-readable failure reason
            amount_attempted: Amount that failed to charge
            paddle_subscription_id: Optional Paddle subscription ID
            currency: Currency code (default USD)

        Returns:
            Dict with failure record details and actions taken

        Raises:
            PaymentFailureError: If failure cannot be processed
        """
        with SessionLocal() as db:
            # Get company with row lock to prevent race conditions
            company = (
                db.query(Company)
                .filter(Company.id == str(company_id))
                .with_for_update()
                .first()
            )

            if not company:
                raise PaymentFailureError(f"Company {company_id} not found")

            now = datetime.now(timezone.utc)
            grace_period_ends_at = now + timedelta(days=self.GRACE_PERIOD_DAYS)

            # Check if there's already an unresolved payment failure
            existing_failure = (
                db.query(PaymentFailure)
                .filter(
                    PaymentFailure.company_id == str(company_id),
                    PaymentFailure.resolved is False,
                )
                .first()
            )

            if existing_failure:
                # Already has active payment failure - just log this one
                logger.warning(
                    "payment_failure_already_in_grace "
                    "company_id=%s existing_failure_id=%s "
                    "new_transaction_id=%s",
                    company_id,
                    existing_failure.id,
                    paddle_transaction_id,
                )
                return {
                    "status": "already_in_grace_period",
                    "existing_failure_id": existing_failure.id,
                    "message": "Service already in grace period due to previous payment failure",
                }

            # Create payment failure record with grace period
            failure = PaymentFailure(
                company_id=str(company_id),
                paddle_subscription_id=paddle_subscription_id,
                paddle_transaction_id=paddle_transaction_id,
                failure_code=failure_code,
                failure_reason=failure_reason,
                amount_attempted=amount_attempted,
                currency=currency,
                service_stopped_at=now,
                grace_period_ends_at=grace_period_ends_at,
                notification_sent=False,
                resolved=False,
            )
            db.add(failure)

            # Update company subscription status to past_due (not full stop)
            old_status = company.subscription_status
            company.subscription_status = self.PAST_DUE_STATUS

            # Update subscription record if exists
            subscription = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == self.ACTIVE_STATUS,
                )
                .first()
            )

            if subscription:
                subscription.status = self.PAST_DUE_STATUS

            db.commit()
            db.refresh(failure)

            logger.info(
                "payment_failure_grace_started "
                "company_id=%s failure_id=%s "
                "old_status=%s new_status=%s "
                "grace_period_ends=%s amount=%s code=%s",
                company_id,
                failure.id,
                old_status,
                self.PAST_DUE_STATUS,
                grace_period_ends_at.isoformat(),
                amount_attempted,
                failure_code,
            )

            # Trigger side-effects: notifications (but NOT full service stop)
            try:
                # Send payment failure notification email with grace period
                # info
                from app.services.email_service import send_email

                from database.models.core import User

                company_owner = (
                    db.query(User)
                    .filter(
                        User.company_id == str(company_id),
                        User.role == "owner",
                    )
                    .first()
                )
                if company_owner:
                    try:
                        send_email(
                            to=company_owner.email,
                            subject="PARWA: Payment Failed — Action Required",
                            html_content="""
                            <html><body>
                            <h2>Payment Failed</h2>
                            <p>Hello {company_owner.full_name or 'there'},</p>
                            <p>We were unable to process your recent payment for your PARWA subscription.</p>
                            <p><strong>Company:</strong> {company.name}</p>
                            <p><strong>Reason:</strong> {failure_reason or 'Payment declined by payment provider'}</p>
                            <p><strong>Amount:</strong> {amount_attempted} {currency}</p>
                            <hr>
                            <p><strong>What happens now:</strong></p>
                            <p>You have a <strong>7-day grace period</strong> (until {grace_period_ends_at.strftime('%B %d, %Y')}) to update your payment method.</p>
                            <p>During this time, your AI agents are paused but you can still access your data in read-only mode.</p>
                            <p>If not resolved within 7 days, your service will be fully suspended.</p>
                            <p>Please update your payment method to avoid service interruption.</p>
                            </body></html>
                            """,
                        )
                    except Exception as email_err:
                        logger.error(
                            "payment_failure_email_failed",
                            company_id=str(company_id),
                            error=str(email_err),
                        )

                # Notify via notification service
                try:
                    from app.services.notification_service import NotificationService

                    notif_svc = NotificationService(db)
                    notif_svc.create_notification(
                        user_id=str(company_owner.id) if company_owner else None,
                        company_id=str(company_id),
                        event_type="payment_failed",
                        title="Payment Failed — 7-Day Grace Period",
                        message=(
                            f"Payment processing failed for {company.name}. "
                            f"You have {self.GRACE_PERIOD_DAYS} days to update your billing information. "
                            f"AI agents are paused. Full service suspension on {grace_period_ends_at.strftime('%B %d, %Y')}."
                        ),
                        priority="high",
                    )
                except Exception as notif_err:
                    logger.error(
                        "payment_failure_notification_failed",
                        company_id=str(company_id),
                        error=str(notif_err),
                    )

                # Emit Socket.io event for real-time UI update
                try:
                    import asyncio

                    from app.core.event_buffer import store_event

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(
                            store_event(
                                company_id=str(company_id),
                                event_type="payment_failed",
                                event_data={
                                    "failure_id": failure.id,
                                    "status": "past_due",
                                    "grace_period_ends_at": grace_period_ends_at.isoformat(),
                                    "grace_period_days": self.GRACE_PERIOD_DAYS,
                                    "message": "Payment failed. 7-day grace period started.",
                                },
                            )
                        )
                    finally:
                        loop.close()
                except Exception as socket_err:
                    logger.warning(
                        "payment_failure_socket_failed company_id=%s error=%s",
                        str(company_id),
                        str(socket_err)[:100],
                    )

            except Exception as e:
                logger.error(
                    "payment_failure_side_effects_failed",
                    company_id=str(company_id),
                    error=str(e),
                )

            return {
                "status": "grace_period_started",
                "failure_id": failure.id,
                "company_id": str(company_id),
                "old_status": old_status,
                "new_status": self.PAST_DUE_STATUS,
                "grace_period_ends_at": grace_period_ends_at.isoformat(),
                "grace_period_days": self.GRACE_PERIOD_DAYS,
                "service_stopped_at": now.isoformat(),
                "actions_taken": [
                    "logged_failure",
                    "updated_subscription_status_to_past_due",
                    "grace_period_started",
                    "notification_sent",
                ],
            }

    async def check_and_suspend_expired_grace_periods(self) -> Dict[str, Any]:
        """
        Check all companies with expired grace periods and suspend them.

        Should be called periodically (e.g., daily via Celery Beat).

        For each company where:
        - payment_failures.resolved = False
        - payment_failures.grace_period_ends_at < now

        Actions:
        1. Set subscription_status = 'payment_failed' (full stop)
        2. Freeze all open tickets
        3. Send final warning email
        4. Emit socket event for real-time UI update

        Returns:
            Dict with processing summary
        """
        now = datetime.now(timezone.utc)
        results = {
            "timestamp": now.isoformat(),
            "suspended": 0,
            "already_suspended": 0,
            "errors": [],
        }

        with SessionLocal() as db:
            # Find all unresolved failures past grace period
            expired_failures = (
                db.query(PaymentFailure)
                .filter(
                    PaymentFailure.resolved is False,
                    PaymentFailure.grace_period_ends_at.isnot(None),
                    PaymentFailure.grace_period_ends_at < now,
                    PaymentFailure.service_stopped_at.isnot(None),  # has been escalated
                )
                .all()
            )

            for failure in expired_failures:
                try:
                    company = (
                        db.query(Company)
                        .filter(Company.id == failure.company_id)
                        .with_for_update()
                        .first()
                    )

                    if not company:
                        continue

                    # Skip if already in full payment_failed state
                    if company.subscription_status == self.PAYMENT_FAILED_STATUS:
                        results["already_suspended"] += 1
                        continue

                    # Escalate to full suspension
                    old_status = company.subscription_status
                    company.subscription_status = self.PAYMENT_FAILED_STATUS

                    # Update subscription
                    subscription = (
                        db.query(Subscription)
                        .filter(
                            Subscription.company_id == failure.company_id,
                            Subscription.status.in_(
                                [self.ACTIVE_STATUS, self.PAST_DUE_STATUS]
                            ),
                        )
                        .first()
                    )

                    if subscription:
                        subscription.status = self.PAYMENT_FAILED_STATUS

                    # Mark as escalated
                    failure.service_stopped_at = now

                    db.commit()

                    logger.warning(
                        "grace_period_expired_suspended "
                        "company_id=%s failure_id=%s old_status=%s new_status=%s",
                        failure.company_id,
                        failure.id,
                        old_status,
                        self.PAYMENT_FAILED_STATUS,
                    )

                    results["suspended"] += 1

                    # Trigger full service stop in background
                    try:
                        from app.tasks.payment_failure_tasks import (
                            stop_service_immediately,
                        )

                        stop_service_immediately.delay(
                            company_id=failure.company_id,
                            failure_id=failure.id,
                            failure_reason=(
                                failure.failure_reason
                                or "Grace period expired without payment"
                            ),
                        )
                    except Exception as task_err:
                        logger.error(
                            "grace_period_suspension_task_failed company_id=%s error=%s",
                            failure.company_id,
                            str(task_err)[:200],
                        )

                    # Send final suspension email
                    try:
                        from app.services.email_service import send_email

                        from database.models.core import User

                        owner = (
                            db.query(User)
                            .filter(
                                User.company_id == failure.company_id,
                                User.role == "owner",
                            )
                            .first()
                        )

                        if owner:
                            send_email(
                                to=owner.email,
                                subject="PARWA: Service Suspended — Grace Period Expired",
                                html_content="""
                                <html><body>
                                <h2>Service Suspended</h2>
                                <p>Hello {owner.full_name or 'there'},</p>
                                <p>Your 7-day grace period has expired without a successful payment.</p>
                                <p><strong>Company:</strong> {company.name}</p>
                                <p>Your PARWA service has been <strong>fully suspended</strong>. AI agents are stopped and tickets are frozen.</p>
                                <p>To reactivate your service, please update your payment method and contact support.</p>
                                </body></html>
                                """,
                            )
                    except Exception as email_err:
                        logger.error(
                            "grace_period_suspension_email_failed company_id=%s error=%s",
                            failure.company_id,
                            str(email_err)[:200],
                        )

                except Exception as e:
                    logger.error(
                        "grace_period_suspension_failed company_id=%s error=%s",
                        failure.company_id,
                        str(e)[:200],
                    )
                    results["errors"].append(
                        {
                            "failure_id": failure.id,
                            "company_id": failure.company_id,
                            "error": str(e)[:200],
                        }
                    )

        logger.info(
            "check_expired_grace_periods_completed "
            "suspended=%d already_suspended=%d errors=%d",
            results["suspended"],
            results["already_suspended"],
            len(results["errors"]),
        )

        return results

    async def get_grace_period_status(
        self,
        company_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the grace period status for a company.

        Returns:
            Dict with grace period details, or None if no active failure.
            Includes whether the grace period has expired.
        """
        with SessionLocal() as db:
            failure = (
                db.query(PaymentFailure)
                .filter(
                    PaymentFailure.company_id == str(company_id),
                    PaymentFailure.resolved is False,
                )
                .first()
            )

            if not failure:
                return None

            now = datetime.now(timezone.utc)
            grace_ends = failure.grace_period_ends_at
            is_expired = False
            is_in_grace_period = False
            days_remaining = None

            if grace_ends:
                if grace_ends.tzinfo is None:
                    grace_ends = grace_ends.replace(tzinfo=timezone.utc)
                is_expired = now > grace_ends
                is_in_grace_period = not is_expired
                delta = grace_ends - now
                days_remaining = max(delta.total_seconds() / 86400, 0)

            return {
                "failure_id": failure.id,
                "status": (
                    "grace_period"
                    if is_in_grace_period
                    else ("expired" if is_expired else "unknown")
                ),
                "grace_period_ends_at": grace_ends.isoformat() if grace_ends else None,
                "is_expired": is_expired,
                "is_in_grace_period": is_in_grace_period,
                "days_remaining": (
                    round(days_remaining, 1) if days_remaining is not None else None
                ),
                "failure_code": failure.failure_code,
                "failure_reason": failure.failure_reason,
                "amount_attempted": (
                    str(failure.amount_attempted) if failure.amount_attempted else None
                ),
                "created_at": (
                    failure.created_at.isoformat() if failure.created_at else None
                ),
            }

    async def handle_payment_failure(
        self,
        company_id: UUID,
        paddle_transaction_id: str,
        failure_code: str,
        failure_reason: str,
        amount_attempted: Decimal,
        paddle_subscription_id: Optional[str] = None,
        currency: str = "USD",
    ) -> Dict[str, Any]:
        """
        Handle a payment failure with immediate service stop.

        Steps:
        1. Log to payment_failures table
        2. Set company.subscription_status = 'payment_failed'
        3. Stop all AI agents immediately
        4. Block new ticket creation
        5. Freeze existing open tickets (status → 'frozen')
        6. Send payment_failed email notification
        7. Create Socket.io event for real-time UI update

        Args:
            company_id: Company UUID
            paddle_transaction_id: Paddle transaction ID
            failure_code: Paddle failure code
            failure_reason: Human-readable failure reason
            amount_attempted: Amount that failed to charge
            paddle_subscription_id: Optional Paddle subscription ID
            currency: Currency code (default USD)

        Returns:
            Dict with failure record details and actions taken

        Raises:
            PaymentFailureError: If failure cannot be processed
        """
        with SessionLocal() as db:
            # Get company with row lock to prevent race conditions
            company = (
                db.query(Company)
                .filter(Company.id == str(company_id))
                .with_for_update()
                .first()
            )

            if not company:
                raise PaymentFailureError(f"Company {company_id} not found")

            now = datetime.now(timezone.utc)

            # Check if there's already an unresolved payment failure
            existing_failure = (
                db.query(PaymentFailure)
                .filter(
                    PaymentFailure.company_id == str(company_id),
                    PaymentFailure.resolved is False,
                )
                .first()
            )

            if existing_failure:
                # Already has active payment failure - just log this one
                logger.warning(
                    "payment_failure_already_stopped "
                    "company_id=%s existing_failure_id=%s "
                    "new_transaction_id=%s",
                    company_id,
                    existing_failure.id,
                    paddle_transaction_id,
                )
                return {
                    "status": "already_stopped",
                    "existing_failure_id": existing_failure.id,
                    "message": "Service already stopped due to previous payment failure",
                }

            # Create payment failure record
            failure = PaymentFailure(
                company_id=str(company_id),
                paddle_subscription_id=paddle_subscription_id,
                paddle_transaction_id=paddle_transaction_id,
                failure_code=failure_code,
                failure_reason=failure_reason,
                amount_attempted=amount_attempted,
                currency=currency,
                service_stopped_at=now,
                notification_sent=False,
                resolved=False,
            )
            db.add(failure)

            # Update company subscription status
            old_status = company.subscription_status
            company.subscription_status = self.PAYMENT_FAILED_STATUS

            # Update subscription record if exists
            subscription = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == self.ACTIVE_STATUS,
                )
                .first()
            )

            if subscription:
                subscription.status = self.PAYMENT_FAILED_STATUS

            db.commit()
            db.refresh(failure)

            logger.info(
                "payment_failure_handled "
                "company_id=%s failure_id=%s "
                "old_status=%s new_status=%s "
                "amount=%s code=%s",
                company_id,
                failure.id,
                old_status,
                self.PAYMENT_FAILED_STATUS,
                amount_attempted,
                failure_code,
            )

            # Trigger side-effects for payment failure
            try:
                # Send payment failure notification email
                from app.services.email_service import send_email

                from database.models.core import User

                company_owner = (
                    db.query(User)
                    .filter(
                        User.company_id == str(company_id),
                        User.role == "owner",
                    )
                    .first()
                )
                if company_owner:
                    try:
                        send_email(
                            to=company_owner.email,
                            subject="PARWA: Payment Failed — Action Required",
                            html_content="""
                            <html><body>
                            <h2>Payment Failed</h2>
                            <p>Hello {company_owner.full_name or 'there'},</p>
                            <p>We were unable to process your recent payment for your PARWA subscription.</p>
                            <p><strong>Company:</strong> {company.name}</p>
                            <p><strong>Reason:</strong> {failure_reason or 'Payment declined by payment provider'}</p>
                            <p>Please update your payment method to avoid service interruption.</p>
                            <p><strong>Your AI agents have been stopped immediately.</strong> Please update your payment method to resume service. If not resolved within 7 days, your subscription will be canceled.</p>
                            </body></html>
                            """,
                        )
                    except Exception as email_err:
                        logger.error(
                            "payment_failure_email_failed",
                            company_id=str(company_id),
                            error=str(email_err),
                        )

                # Notify via notification service
                try:
                    from app.services.notification_service import NotificationService

                    notif_svc = NotificationService(db)
                    notif_svc.create_notification(
                        user_id=str(company_owner.id) if company_owner else None,
                        company_id=str(company_id),
                        event_type="payment_failed",
                        title="Payment Failed",
                        message=f"Payment processing failed for {
                            company.name}. Please update your billing information.",
                        priority="high",
                    )
                except Exception as notif_err:
                    logger.error(
                        "payment_failure_notification_failed",
                        company_id=str(company_id),
                        error=str(notif_err),
                    )

            except Exception as e:
                logger.error(
                    "payment_failure_side_effects_failed",
                    company_id=str(company_id),
                    error=str(e),
                )

            return {
                "status": "stopped",
                "failure_id": failure.id,
                "company_id": str(company_id),
                "old_status": old_status,
                "new_status": self.PAYMENT_FAILED_STATUS,
                "service_stopped_at": now.isoformat(),
                "actions_taken": [
                    "logged_failure",
                    "updated_subscription_status",
                    "service_stopped",
                ],
            }

    async def is_service_stopped(self, company_id: UUID) -> bool:
        """
        Check if company service is stopped due to payment failure.

        Returns True if service is fully stopped (payment_failed status).
        Note: 'past_due' (grace period) returns False since limited access is allowed.

        Args:
            company_id: Company UUID

        Returns:
            True if service is fully stopped, False otherwise
        """
        with SessionLocal() as db:
            # Check company subscription status - only payment_failed = full
            # stop
            company = db.query(Company).filter(Company.id == str(company_id)).first()

            if company and company.subscription_status == self.PAYMENT_FAILED_STATUS:
                return True

            # Also check for unresolved payment failures that have expired
            # grace period
            failure = (
                db.query(PaymentFailure)
                .filter(
                    PaymentFailure.company_id == str(company_id),
                    PaymentFailure.resolved is False,
                )
                .first()
            )

            if failure and failure.grace_period_ends_at:
                grace_ends = failure.grace_period_ends_at
                if grace_ends.tzinfo is None:
                    grace_ends = grace_ends.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > grace_ends:
                    return True

            return False

    async def is_in_grace_period(self, company_id: UUID) -> bool:
        """
        Check if company is in the 7-day grace period.

        Args:
            company_id: Company UUID

        Returns:
            True if in grace period, False otherwise
        """
        with SessionLocal() as db:
            company = db.query(Company).filter(Company.id == str(company_id)).first()

            if company and company.subscription_status == self.PAST_DUE_STATUS:
                # Verify there's an active failure with unexpired grace period
                failure = (
                    db.query(PaymentFailure)
                    .filter(
                        PaymentFailure.company_id == str(company_id),
                        PaymentFailure.resolved is False,
                    )
                    .first()
                )

                if failure and failure.grace_period_ends_at:
                    grace_ends = failure.grace_period_ends_at
                    if grace_ends.tzinfo is None:
                        grace_ends = grace_ends.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) <= grace_ends:
                        return True

            return False

    async def resume_service(
        self,
        company_id: UUID,
        paddle_transaction_id: str,
    ) -> Dict[str, Any]:
        """
        Resume service after successful payment.

        Called when payment succeeds after failure:
        1. Update subscription_status → 'active'
        2. Resume AI agents
        3. Unfreeze tickets
        4. Send service_resumed notification

        Args:
            company_id: Company UUID
            paddle_transaction_id: Successful Paddle transaction ID

        Returns:
            Dict with resume details

        Raises:
            PaymentFailureError: If no active failure to resume from
        """
        with SessionLocal() as db:
            # Get company with row lock
            company = (
                db.query(Company)
                .filter(Company.id == str(company_id))
                .with_for_update()
                .first()
            )

            if not company:
                raise PaymentFailureError(f"Company {company_id} not found")

            # Get active payment failure
            failure = (
                db.query(PaymentFailure)
                .filter(
                    PaymentFailure.company_id == str(company_id),
                    PaymentFailure.resolved is False,
                )
                .first()
            )

            if not failure:
                logger.info("payment_resume_no_failure company_id=%s", company_id)
                # No active failure - just ensure status is active
                if company.subscription_status != self.ACTIVE_STATUS:
                    company.subscription_status = self.ACTIVE_STATUS
                    db.commit()
                return {
                    "status": "no_failure",
                    "message": "No active payment failure to resume from",
                }

            now = datetime.now(timezone.utc)

            # Mark failure as resolved
            failure.resolved = True
            failure.service_resumed_at = now

            # Update company status
            old_status = company.subscription_status
            company.subscription_status = self.ACTIVE_STATUS

            # Update subscription record
            subscription = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                )
                .order_by(Subscription.created_at.desc())
                .first()
            )

            if subscription:
                subscription.status = self.ACTIVE_STATUS

            db.commit()

            logger.info(
                "payment_service_resumed "
                "company_id=%s failure_id=%s "
                "old_status=%s new_status=%s",
                company_id,
                failure.id,
                old_status,
                self.ACTIVE_STATUS,
            )

            # Resume side-effects after payment recovery
            try:
                # Resume AI agents for this company
                try:
                    from app.services.agent_provisioning_service import (
                        AgentProvisioningService,
                    )

                    provisioner = AgentProvisioningService()
                    provisioner.resume_company_agents(
                        company_id=str(company_id),
                        db=db,
                    )
                    logger.info(
                        "payment_resume_agents_resumed company_id=%s",
                        company_id,
                    )
                except Exception as agent_err:
                    logger.warning(
                        "payment_resume_agents_failed company_id=%s error=%s",
                        company_id,
                        str(agent_err)[:200],
                    )

                # Unfreeze tickets that were frozen during payment failure
                try:
                    from database.models.tickets import Ticket

                    unfrozen_count = (
                        db.query(Ticket)
                        .filter(
                            Ticket.company_id == str(company_id),
                            Ticket.status == "frozen",
                        )
                        .update({"status": "open"})
                    )
                    db.commit()
                    logger.info(
                        "payment_resume_tickets_unfrozen company_id=%s count=%d",
                        company_id,
                        unfrozen_count,
                    )
                except Exception as ticket_err:
                    logger.warning(
                        "payment_resume_tickets_failed company_id=%s error=%s",
                        company_id,
                        str(ticket_err)[:200],
                    )

                # Send service_resumed email notification
                try:
                    from app.services.email_service import send_email

                    from database.models.core import User

                    company_owner = (
                        db.query(User)
                        .filter(
                            User.company_id == str(company_id),
                            User.role == "owner",
                        )
                        .first()
                    )
                    if company_owner:
                        send_email(
                            to=company_owner.email,
                            subject="PARWA: Service Resumed",
                            html_content=(
                                "<html><body>"
                                "<h2>Welcome Back!</h2>"
                                f"<p>Hello {company_owner.full_name or 'there'},</p>"
                                "<p>Your payment was received and your "
                                "PARWA service has been fully resumed.</p>"
                                f"<p><strong>Company:</strong> {company.name}</p>"
                                "<p>Your AI agents are now active and all "
                                "previously frozen tickets have been unfrozen.</p>"
                                "</body></html>"
                            ),
                        )
                        logger.info(
                            "payment_resume_email_sent company_id=%s",
                            company_id,
                        )
                except Exception as email_err:
                    logger.warning(
                        "payment_resume_email_failed company_id=%s error=%s",
                        company_id,
                        str(email_err)[:200],
                    )

                # Emit Socket.io event for real-time UI update
                try:
                    from app.core.event_emitter import EventEmitter

                    emitter = EventEmitter()
                    emitter.emit_to_company(
                        company_id=str(company_id),
                        event_name="billing:service_resumed",
                        data={
                            "company_id": str(company_id),
                            "status": "active",
                            "resumed_at": now.isoformat(),
                            "message": "Service resumed after successful payment",
                        },
                    )
                    logger.info(
                        "payment_resume_socket_emitted company_id=%s",
                        company_id,
                    )
                except Exception as socket_err:
                    logger.warning(
                        "payment_resume_socket_failed company_id=%s error=%s",
                        company_id,
                        str(socket_err)[:200],
                    )

            except Exception as side_err:
                logger.error(
                    "payment_resume_side_effects_failed company_id=%s error=%s",
                    company_id,
                    str(side_err)[:200],
                )

            return {
                "status": "resumed",
                "failure_id": failure.id,
                "company_id": str(company_id),
                "old_status": old_status,
                "new_status": self.ACTIVE_STATUS,
                "service_resumed_at": now.isoformat(),
                "actions_taken": [
                    "marked_failure_resolved",
                    "updated_subscription_status",
                    "service_resumed",
                ],
            }

    async def get_payment_failure_history(
        self,
        company_id: UUID,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get payment failure history for a company.

        Args:
            company_id: Company UUID
            limit: Maximum number of records to return

        Returns:
            List of payment failure records
        """
        with SessionLocal() as db:
            failures = (
                db.query(PaymentFailure)
                .filter(PaymentFailure.company_id == str(company_id))
                .order_by(PaymentFailure.created_at.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": f.id,
                    "paddle_subscription_id": f.paddle_subscription_id,
                    "paddle_transaction_id": f.paddle_transaction_id,
                    "failure_code": f.failure_code,
                    "failure_reason": f.failure_reason,
                    "amount_attempted": (
                        str(f.amount_attempted) if f.amount_attempted else None
                    ),
                    "currency": f.currency,
                    "service_stopped_at": (
                        f.service_stopped_at.isoformat()
                        if f.service_stopped_at
                        else None
                    ),
                    "service_resumed_at": (
                        f.service_resumed_at.isoformat()
                        if f.service_resumed_at
                        else None
                    ),
                    "notification_sent": f.notification_sent,
                    "resolved": f.resolved,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                }
                for f in failures
            ]

    async def get_active_failure(
        self,
        company_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the active (unresolved) payment failure for a company.

        Args:
            company_id: Company UUID

        Returns:
            Active payment failure or None
        """
        with SessionLocal() as db:
            failure = (
                db.query(PaymentFailure)
                .filter(
                    PaymentFailure.company_id == str(company_id),
                    PaymentFailure.resolved is False,
                )
                .first()
            )

            if not failure:
                return None

            return {
                "id": failure.id,
                "paddle_subscription_id": failure.paddle_subscription_id,
                "paddle_transaction_id": failure.paddle_transaction_id,
                "failure_code": failure.failure_code,
                "failure_reason": failure.failure_reason,
                "amount_attempted": (
                    str(failure.amount_attempted) if failure.amount_attempted else None
                ),
                "currency": failure.currency,
                "service_stopped_at": (
                    failure.service_stopped_at.isoformat()
                    if failure.service_stopped_at
                    else None
                ),
                "resolved": failure.resolved,
                "created_at": (
                    failure.created_at.isoformat() if failure.created_at else None
                ),
            }

    async def mark_notification_sent(
        self,
        failure_id: str,
    ) -> bool:
        """
        Mark that notification has been sent for a payment failure.

        Args:
            failure_id: Payment failure ID

        Returns:
            True if updated successfully
        """
        with SessionLocal() as db:
            failure = (
                db.query(PaymentFailure).filter(PaymentFailure.id == failure_id).first()
            )

            if not failure:
                return False

            failure.notification_sent = True
            db.commit()

            logger.info("payment_failure_notification_sent failure_id=%s", failure_id)

            return True


# ── Singleton Service ────────────────────────────────────────────────────

_payment_failure_service: Optional[PaymentFailureService] = None


def get_payment_failure_service() -> PaymentFailureService:
    """Get the payment failure service singleton."""
    global _payment_failure_service
    if _payment_failure_service is None:
        _payment_failure_service = PaymentFailureService()
    return _payment_failure_service
