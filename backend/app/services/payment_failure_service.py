"""
Payment Failure Service (F-027, BG-16)

Netflix-style payment failure handling:
1. Payment fails → IMMEDIATE service stop
2. No grace period
3. No dunning emails
4. Single notification: "Payment failed, update payment method"
5. Service resumes immediately on successful payment

This is deliberately strict to reduce churn from forgotten cards.

BC-001: All operations validate company_id
BC-002: All money calculations use Decimal
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from database.base import SessionLocal
from database.models.billing import Subscription
from database.models.billing_extended import PaymentFailure
from database.models.core import Company

logger = logging.getLogger("parwa.services.payment_failure")


class PaymentFailureError(Exception):
    """Base exception for payment failure errors."""
    pass


class ServiceStoppedError(PaymentFailureError):
    """Company service is stopped due to payment failure."""
    pass


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

    def __init__(self):
        pass

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
            company = db.query(Company).filter(
                Company.id == str(company_id)
            ).with_for_update().first()

            if not company:
                raise PaymentFailureError(f"Company {company_id} not found")

            now = datetime.now(timezone.utc)

            # Check if there's already an unresolved payment failure
            existing_failure = db.query(PaymentFailure).filter(
                PaymentFailure.company_id == str(company_id),
                PaymentFailure.resolved == False,
            ).first()

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
            subscription = db.query(Subscription).filter(
                Subscription.company_id == str(company_id),
                Subscription.status == self.ACTIVE_STATUS,
            ).first()

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

            # TODO: In production, trigger these async tasks:
            # - Stop all AI agents for this company
            # - Freeze open tickets
            # - Send payment_failed email
            # - Emit Socket.io event for real-time UI update

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

        Args:
            company_id: Company UUID

        Returns:
            True if service is stopped, False otherwise
        """
        with SessionLocal() as db:
            # Check for unresolved payment failure
            failure = db.query(PaymentFailure).filter(
                PaymentFailure.company_id == str(company_id),
                PaymentFailure.resolved == False,
            ).first()

            if failure:
                return True

            # Also check company subscription status
            company = db.query(Company).filter(
                Company.id == str(company_id)
            ).first()

            if company and company.subscription_status == self.PAYMENT_FAILED_STATUS:
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
            company = db.query(Company).filter(
                Company.id == str(company_id)
            ).with_for_update().first()

            if not company:
                raise PaymentFailureError(f"Company {company_id} not found")

            # Get active payment failure
            failure = db.query(PaymentFailure).filter(
                PaymentFailure.company_id == str(company_id),
                PaymentFailure.resolved == False,
            ).first()

            if not failure:
                logger.info(
                    "payment_resume_no_failure company_id=%s", company_id
                )
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
            subscription = db.query(Subscription).filter(
                Subscription.company_id == str(company_id),
            ).order_by(Subscription.created_at.desc()).first()

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

            # TODO: In production, trigger these async tasks:
            # - Resume AI agents for this company
            # - Unfreeze tickets
            # - Send service_resumed email
            # - Emit Socket.io event for real-time UI update

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
            failures = db.query(PaymentFailure).filter(
                PaymentFailure.company_id == str(company_id)
            ).order_by(
                PaymentFailure.created_at.desc()
            ).limit(limit).all()

            return [
                {
                    "id": f.id,
                    "paddle_subscription_id": f.paddle_subscription_id,
                    "paddle_transaction_id": f.paddle_transaction_id,
                    "failure_code": f.failure_code,
                    "failure_reason": f.failure_reason,
                    "amount_attempted": float(f.amount_attempted) if f.amount_attempted else None,
                    "currency": f.currency,
                    "service_stopped_at": f.service_stopped_at.isoformat() if f.service_stopped_at else None,
                    "service_resumed_at": f.service_resumed_at.isoformat() if f.service_resumed_at else None,
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
            failure = db.query(PaymentFailure).filter(
                PaymentFailure.company_id == str(company_id),
                PaymentFailure.resolved == False,
            ).first()

            if not failure:
                return None

            return {
                "id": failure.id,
                "paddle_subscription_id": failure.paddle_subscription_id,
                "paddle_transaction_id": failure.paddle_transaction_id,
                "failure_code": failure.failure_code,
                "failure_reason": failure.failure_reason,
                "amount_attempted": float(failure.amount_attempted) if failure.amount_attempted else None,
                "currency": failure.currency,
                "service_stopped_at": failure.service_stopped_at.isoformat() if failure.service_stopped_at else None,
                "resolved": failure.resolved,
                "created_at": failure.created_at.isoformat() if failure.created_at else None,
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
            failure = db.query(PaymentFailure).filter(
                PaymentFailure.id == failure_id
            ).first()

            if not failure:
                return False

            failure.notification_sent = True
            db.commit()

            logger.info(
                "payment_failure_notification_sent failure_id=%s", failure_id
            )

            return True


# ── Singleton Service ────────────────────────────────────────────────────

_payment_failure_service: Optional[PaymentFailureService] = None


def get_payment_failure_service() -> PaymentFailureService:
    """Get the payment failure service singleton."""
    global _payment_failure_service
    if _payment_failure_service is None:
        _payment_failure_service = PaymentFailureService()
    return _payment_failure_service
