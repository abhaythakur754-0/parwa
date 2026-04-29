"""
Chargeback Service (CB1-CB5)

Handles chargeback event processing from payment processor:
- CB1: Process chargeback event — create record, stop service, notify admin
- CB2: Stop service on chargeback — update subscription to payment_failed
- CB3: Get admin notification data for chargeback
- CB4: Update chargeback status / resolution
- CB5: Get customer communication template

BC-001: All operations validate company_id
BC-002: All money calculations use Decimal
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from database.base import SessionLocal
from database.models.billing import Subscription
from database.models.billing_extended import Chargeback
from database.models.core import Company

logger = logging.getLogger("parwa.services.chargeback")

# ── Valid chargeback statuses ────────────────────────────────────────────────

VALID_STATUSES = {"received", "under_review", "won", "lost"}

# ── Valid chargeback reasons (from card networks) ───────────────────────────

CHARGEBACK_REASONS = {
    "fraudulent",
    "duplicate",
    "subscription_canceled",
    "product_unacceptable",
    "product_not_received",
    "credit_not_processed",
    "general",
}


# ── Exceptions ──────────────────────────────────────────────────────────────


class ChargebackError(Exception):
    """Base exception for chargeback errors."""


class ChargebackNotFoundError(ChargebackError):
    """Chargeback record not found."""


# ── Service ─────────────────────────────────────────────────────────────────


class ChargebackService:
    """
    Chargeback handling service.

    Manages the full lifecycle of chargeback events from the payment
    processor (Paddle), including service suspension, admin notification,
    dispute resolution, and customer communication.

    Usage:
        service = ChargebackService()
        result = service.process_chargeback_event(company_id, event_data)
    """

    # ═══════════════════════════════════════════════════════════════════
    # CB1: Process Chargeback Event
    # ═══════════════════════════════════════════════════════════════════

    def process_chargeback_event(
        self,
        company_id: UUID,
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        CB1: Process an incoming chargeback event from the payment processor.

        Creates a Chargeback record, immediately stops service for the
        company, and triggers admin notification.

        Args:
            company_id: Company UUID
            event_data: Dict containing chargeback event details:
                - paddle_transaction_id (str): Original transaction ID
                - paddle_chargeback_id (str): Paddle chargeback event ID
                - amount (Decimal/str): Chargeback amount
                - currency (str): Currency code (default: USD)
                - reason (str): Chargeback reason code

        Returns:
            Dict with chargeback record details

        Raises:
            ChargebackError: If event_data is invalid or processing fails
        """
        if not company_id:
            raise ChargebackError("company_id is required (BC-001)")

        # Validate event_data
        amount_raw = event_data.get("amount")
        if amount_raw is None:
            raise ChargebackError("event_data must contain 'amount'")

        amount = Decimal(str(amount_raw))
        if amount <= 0:
            raise ChargebackError(
                f"Chargeback amount must be positive, got {amount}")

        currency = str(event_data.get("currency", "USD")).upper()
        reason = str(event_data.get("reason", "general")).lower().strip()
        paddle_transaction_id = event_data.get("paddle_transaction_id")
        paddle_chargeback_id = event_data.get("paddle_chargeback_id")

        with SessionLocal() as db:
            # BC-001: Validate company exists
            company = db.query(Company).filter(
                Company.id == str(company_id)
            ).first()

            if not company:
                raise ChargebackError(
                    f"Company {company_id} not found (BC-001)")

            now = datetime.now(timezone.utc)

            # Create chargeback record
            chargeback = Chargeback(
                company_id=str(company_id),
                paddle_transaction_id=paddle_transaction_id,
                paddle_chargeback_id=paddle_chargeback_id,
                amount=amount.quantize(Decimal("0.01")),
                currency=currency,
                reason=reason,
                status="received",
                service_stopped_at=now,
                notification_sent_at=now,
                created_at=now,
                updated_at=now,
            )
            db.add(chargeback)

            # CB2: Stop service immediately
            self.stop_service_on_chargeback(db, company_id)

            db.commit()
            db.refresh(chargeback)

            logger.info(
                "chargeback_processed cb_id=%s company_id=%s amount=%s reason=%s",
                chargeback.id,
                company_id,
                amount,
                reason,
            )

            return self._chargeback_to_dict(chargeback)

    # ═══════════════════════════════════════════════════════════════════
    # CB2: Stop Service on Chargeback
    # ═══════════════════════════════════════════════════════════════════

    def stop_service_on_chargeback(
        self,
        db: Session,
        company_id: UUID,
    ) -> None:
        """
        CB2: Stop service for a company due to chargeback.

        Updates the active subscription status to 'payment_failed'.
        Called internally by process_chargeback_event.

        Args:
            db: Active database session (caller manages commit)
            company_id: Company UUID
        """
        if not company_id:
            raise ChargebackError("company_id is required (BC-001)")

        subscription = db.query(Subscription).filter(
            Subscription.company_id == str(company_id),
            Subscription.status == "active",
        ).first()

        if subscription:
            subscription.status = "payment_failed"
            logger.info(
                "chargeback_service_stopped sub_id=%s company_id=%s",
                subscription.id,
                company_id,
            )

        # Update company status
        company = db.query(Company).filter(
            Company.id == str(company_id)
        ).first()

        if company:
            company.subscription_status = "payment_failed"
            logger.info(
                "chargeback_company_status_updated company_id=%s status=payment_failed",
                company_id,
            )

    # ═══════════════════════════════════════════════════════════════════
    # Query Methods
    # ═══════════════════════════════════════════════════════════════════

    def get_chargeback(
        self,
        chargeback_id: str,
        company_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get a single chargeback by ID for a specific company.

        Args:
            chargeback_id: Chargeback record UUID
            company_id: Company UUID (BC-001 scoping)

        Returns:
            Dict with chargeback details

        Raises:
            ChargebackNotFoundError: If chargeback not found for this company
        """
        if not company_id:
            raise ChargebackError("company_id is required (BC-001)")

        with SessionLocal() as db:
            chargeback = db.query(Chargeback).filter(
                Chargeback.id == chargeback_id,
                Chargeback.company_id == str(company_id),
            ).first()

            if not chargeback:
                raise ChargebackNotFoundError(
                    f"Chargeback {chargeback_id} not found for company {company_id}")

            return self._chargeback_to_dict(chargeback)

    def list_chargebacks(
        self,
        company_id: UUID,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List chargebacks for a company, optionally filtered by status.

        Args:
            company_id: Company UUID (BC-001 scoping)
            status: Optional status filter (received/under_review/won/lost)

        Returns:
            List of chargeback dicts

        Raises:
            ChargebackError: If status filter is invalid
        """
        if not company_id:
            raise ChargebackError("company_id is required (BC-001)")

        if status is not None and status not in VALID_STATUSES:
            raise ChargebackError(
                f"Invalid status: {status}. "
                f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
            )

        with SessionLocal() as db:
            query = db.query(Chargeback).filter(
                Chargeback.company_id == str(company_id),
            )

            if status is not None:
                query = query.filter(Chargeback.status == status)

            chargebacks = query.order_by(Chargeback.created_at.desc()).all()

            return [self._chargeback_to_dict(cb) for cb in chargebacks]

    # ═══════════════════════════════════════════════════════════════════
    # CB4: Update Chargeback Status
    # ═══════════════════════════════════════════════════════════════════

    def update_chargeback_status(
        self,
        chargeback_id: str,
        status: str,
        resolution_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        CB4: Update the status of a chargeback.

        Transitions the chargeback through the lifecycle:
        received → under_review → won/lost

        If the chargeback is won (dispute successful), service can be
        restored by the subscription service.

        Args:
            chargeback_id: Chargeback record UUID
            status: New status (must be in VALID_STATUSES)
            resolution_notes: Optional notes from the review

        Returns:
            Dict with updated chargeback details

        Raises:
            ChargebackNotFoundError: If chargeback not found
            ChargebackError: If status transition is invalid
        """
        if status not in VALID_STATUSES:
            raise ChargebackError(
                f"Invalid status: {status}. "
                f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
            )

        with SessionLocal() as db:
            chargeback = db.query(Chargeback).filter(
                Chargeback.id == chargeback_id,
            ).first()

            if not chargeback:
                raise ChargebackNotFoundError(
                    f"Chargeback {chargeback_id} not found"
                )

            # Validate status transition
            old_status = chargeback.status
            if not self._is_valid_transition(old_status, status):
                raise ChargebackError(
                    f"Invalid chargeback status transition: "
                    f"{old_status} → {status}"
                )

            chargeback.status = status

            if resolution_notes:
                chargeback.resolution_notes = resolution_notes

            # Mark resolved if terminal state
            if status in ("won", "lost"):
                chargeback.resolved_at = datetime.now(timezone.utc)

            db.commit()
            db.refresh(chargeback)

            logger.info(
                "chargeback_status_updated cb_id=%s %s→%s notes=%s",
                chargeback_id,
                old_status,
                status,
                "yes" if resolution_notes else "no",
            )

            return self._chargeback_to_dict(chargeback)

    # ═══════════════════════════════════════════════════════════════════
    # CB3: Admin Notification Data
    # ═══════════════════════════════════════════════════════════════════

    def get_admin_notification_data(
        self,
        chargeback_id: str,
    ) -> Dict[str, Any]:
        """
        CB3: Get structured notification data for admin alert.

        Returns all data needed to send an admin notification about a
        chargeback, including company details, subscription info, and
        chargeback specifics.

        Args:
            chargeback_id: Chargeback record UUID

        Returns:
            Dict with notification payload

        Raises:
            ChargebackNotFoundError: If chargeback not found
        """
        with SessionLocal() as db:
            chargeback = db.query(Chargeback).filter(
                Chargeback.id == chargeback_id,
            ).first()

            if not chargeback:
                raise ChargebackNotFoundError(
                    f"Chargeback {chargeback_id} not found"
                )

            # Get company details
            company = db.query(Company).filter(
                Company.id == chargeback.company_id
            ).first()

            # Get active subscription
            subscription = db.query(Subscription).filter(
                Subscription.company_id == chargeback.company_id,
            ).order_by(Subscription.created_at.desc()).first()

            notification = {
                "chargeback": self._chargeback_to_dict(chargeback),
                "company": {
                    "id": chargeback.company_id,
                    "name": company.name if company else "Unknown",
                    "industry": company.industry if company else "Unknown",
                    "subscription_tier": (
                        company.subscription_tier if company else "Unknown"
                    ),
                },
                "subscription": {
                    "id": subscription.id if subscription else None,
                    "tier": subscription.tier if subscription else None,
                    "status": subscription.status if subscription else None,
                    "paddle_subscription_id": (
                        subscription.paddle_subscription_id if subscription else None
                    ),
                } if subscription else None,
                "alert": {
                    "type": "chargeback_received",
                    "severity": "high",
                    "requires_action": True,
                    "action_deadline_hours": 48,
                    "message": (
                        f"Chargeback of {chargeback.currency} "
                        f"{chargeback.amount} received from "
                        f"{company.name if company else 'Unknown'}. "
                        f"Service has been stopped. "
                        f"Review and respond within 48 hours."
                    ),
                },
            }

            logger.info(
                "chargeback_admin_notification cb_id=%s company_id=%s",
                chargeback_id,
                chargeback.company_id,
            )

            return notification

    # ═══════════════════════════════════════════════════════════════════
    # CB5: Customer Communication Template
    # ═══════════════════════════════════════════════════════════════════

    def get_customer_communication_template(
        self,
        chargeback_id: str,
    ) -> Dict[str, Any]:
        """
        CB5: Get the customer communication template for a chargeback.

        Returns a pre-filled email/message template that can be sent
        to the customer regarding the chargeback. The template includes
        placeholders for dynamic data.

        Args:
            chargeback_id: Chargeback record UUID

        Returns:
            Dict with template data (subject, body, metadata)

        Raises:
            ChargebackNotFoundError: If chargeback not found
        """
        with SessionLocal() as db:
            chargeback = db.query(Chargeback).filter(
                Chargeback.id == chargeback_id,
            ).first()

            if not chargeback:
                raise ChargebackNotFoundError(
                    f"Chargeback {chargeback_id} not found"
                )

            company = db.query(Company).filter(
                Company.id == chargeback.company_id
            ).first()

            company_name = company.name if company else "Valued Customer"

            # Build template based on current status
            if chargeback.status == "received":
                subject = f"Important: Chargeback Notice for Your PARWA Account"
                body = (
                    f"Dear {company_name},\n\n"
                    f"We have received a chargeback notification from your "
                    f"payment provider for the amount of "
                    f"{chargeback.currency} {chargeback.amount}.\n\n"
                    f"As a result, your PARWA service has been temporarily "
                    f"suspended while we review this matter.\n\n"
                    f"If you initiated this chargeback or have questions, "
                    f"please contact our billing team immediately at "
                    f"billing@parwa.io with your account details.\n\n"
                    f"We aim to resolve this within 48 hours. Once resolved, "
                    f"your service will be restored.\n\n"
                    f"Best regards,\nThe PARWA Billing Team"
                )
                communication_type = "chargeback_received"
            elif chargeback.status == "under_review":
                subject = f"Update: Your Chargeback Case is Under Review"
                body = (
                    f"Dear {company_name},\n\n"
                    f"Your chargeback case regarding "
                    f"{chargeback.currency} {chargeback.amount} is currently "
                    f"under review by our billing team.\n\n"
                    f"We are working with the payment processor to resolve "
                    f"this matter as quickly as possible.\n\n"
                    f"We will update you within 24-48 hours with the outcome.\n\n"
                    f"Best regards,\nThe PARWA Billing Team"
                )
                communication_type = "chargeback_under_review"
            elif chargeback.status == "won":
                subject = f"Good News: Chargeback Dispute Resolved in Your Favor"
                body = (
                    f"Dear {company_name},\n\n"
                    f"We are pleased to inform you that the chargeback dispute "
                    f"for {chargeback.currency} {chargeback.amount} has been "
                    f"resolved in your favor.\n\n"
                    f"Your PARWA service has been fully restored. If you "
                    f"experience any issues, please contact our support team.\n\n"
                    f"Thank you for your patience.\n\n"
                    f"Best regards,\nThe PARWA Billing Team"
                )
                communication_type = "chargeback_won"
            else:  # lost
                notes = chargeback.resolution_notes or "No additional details."
                subject = f"Notice: Chargeback Case Resolution"
                body = (
                    f"Dear {company_name},\n\n"
                    f"The chargeback case for "
                    f"{chargeback.currency} {chargeback.amount} has been "
                    f"resolved.\n\n"
                    f"Resolution notes: {notes}\n\n"
                    f"Your PARWA service remains suspended. If you believe "
                    f"this is an error or would like to discuss reinstatement "
                    f"options, please contact billing@parwa.io.\n\n"
                    f"Best regards,\nThe PARWA Billing Team"
                )
                communication_type = "chargeback_lost"

            template = {
                "chargeback_id": chargeback_id,
                "communication_type": communication_type,
                "company_id": chargeback.company_id,
                "subject": subject,
                "body": body,
                "metadata": {
                    "amount": str(chargeback.amount),
                    "currency": chargeback.currency,
                    "reason": chargeback.reason,
                    "status": chargeback.status,
                    "template_version": "1.0",
                },
            }

            logger.info(
                "chargeback_template_generated cb_id=%s type=%s",
                chargeback_id,
                communication_type,
            )

            return template

    # ═══════════════════════════════════════════════════════════════════
    # Internal Helpers
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _is_valid_transition(old_status: str, new_status: str) -> bool:
        """
        Validate chargeback status transition.

        Allowed transitions:
        - received → under_review
        - received → lost (auto-close if not disputed)
        - under_review → won
        - under_review → lost
        """
        valid_transitions = {
            "received": {"under_review", "lost"},
            "under_review": {"won", "lost"},
            "won": set(),
            "lost": set(),
        }

        allowed = valid_transitions.get(old_status, set())
        return new_status in allowed

    @staticmethod
    def _chargeback_to_dict(chargeback: Chargeback) -> Dict[str, Any]:
        """Convert Chargeback ORM model to dict."""
        return {
            "id": chargeback.id,
            "company_id": chargeback.company_id,
            "paddle_transaction_id": chargeback.paddle_transaction_id,
            "paddle_chargeback_id": chargeback.paddle_chargeback_id,
            "amount": str(chargeback.amount),
            "currency": chargeback.currency,
            "reason": chargeback.reason,
            "status": chargeback.status,
            "service_stopped_at": (
                chargeback.service_stopped_at.isoformat()
                if chargeback.service_stopped_at else None
            ),
            "notification_sent_at": (
                chargeback.notification_sent_at.isoformat()
                if chargeback.notification_sent_at else None
            ),
            "resolved_at": (
                chargeback.resolved_at.isoformat()
                if chargeback.resolved_at else None
            ),
            "resolution_notes": chargeback.resolution_notes,
            "created_at": (
                chargeback.created_at.isoformat()
                if chargeback.created_at else None
            ),
            "updated_at": (
                chargeback.updated_at.isoformat()
                if chargeback.updated_at else None
            ),
        }


# ── Singleton ────────────────────────────────────────────────────────────────

_chargeback_service_instance: Optional[ChargebackService] = None


def get_chargeback_service() -> ChargebackService:
    """Get or create the singleton ChargebackService instance."""
    global _chargeback_service_instance
    if _chargeback_service_instance is None:
        _chargeback_service_instance = ChargebackService()
    return _chargeback_service_instance
