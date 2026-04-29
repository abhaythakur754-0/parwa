"""
Client Refund Service (BG-09)

PARWA clients refunding THEIR customers.
This is NOT PARWA refunding clients (NO REFUNDS policy).

Use case: PARWA client has e-commerce store, customer requests refund,
PARWA AI agent processes refund, we track for analytics.

BC-001: All operations validate company_id
BC-002: All money calculations use Decimal
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import desc

from database.base import SessionLocal
from database.models.billing_extended import ClientRefund

logger = logging.getLogger("parwa.services.client_refund")


class ClientRefundError(Exception):
    """Base exception for client refund errors."""


class ClientRefundNotFoundError(ClientRefundError):
    """Refund request not found."""


class ClientRefundService:
    """
    Client refund tracking service.

    This tracks when PARWA clients (businesses using PARWA)
    issue refunds to THEIR end customers.

    Example: An e-commerce store using PARWA AI support
    processes a refund for a customer's order.

    This is separate from PARWA's own billing - PARWA does
    NOT offer refunds (Netflix style).
    """

    VALID_STATUSES = {"pending", "processed", "failed", "canceled"}

    def create_refund_request(
        self,
        company_id: UUID,
        amount: Decimal,
        currency: str = "USD",
        ticket_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        external_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new refund request.

        This records a refund that a PARWA client wants to issue
        to their customer. The actual refund processing happens
        in the client's own payment system.

        Args:
            company_id: Company UUID (PARWA client)
            amount: Refund amount
            currency: Currency code (default USD)
            ticket_id: Optional related ticket UUID
            reason: Refund reason
            external_ref: Reference from client's payment system

        Returns:
            Created refund request dict
        """
        if amount <= 0:
            raise ClientRefundError("Refund amount must be positive")

        with SessionLocal() as db:
            refund = ClientRefund(
                company_id=str(company_id),
                ticket_id=str(ticket_id) if ticket_id else None,
                amount=amount,
                currency=currency.upper(),
                reason=reason or "",
                status="pending",
            )
            db.add(refund)
            db.commit()
            db.refresh(refund)

            logger.info(
                "client_refund_created company_id=%s refund_id=%s amount=%s",
                company_id,
                refund.id,
                amount,
            )

            return self._to_dict(refund)

    def get_refund(
        self,
        company_id: UUID,
        refund_id: str,
    ) -> Dict[str, Any]:
        """
        Get a refund request by ID.

        Args:
            company_id: Company UUID
            refund_id: Refund UUID

        Returns:
            Refund request dict

        Raises:
            ClientRefundNotFoundError: Refund not found or access denied
        """
        with SessionLocal() as db:
            refund = db.query(ClientRefund).filter(
                ClientRefund.id == refund_id,
            ).first()

            if not refund:
                raise ClientRefundNotFoundError(
                    f"Refund request {refund_id} not found"
                )

            # BC-001: Validate company_id
            if refund.company_id != str(company_id):
                raise ClientRefundNotFoundError(
                    "Refund request not found"
                )

            return self._to_dict(refund)

    def list_refunds(
        self,
        company_id: UUID,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        List refund requests for a company.

        Args:
            company_id: Company UUID
            status: Filter by status (optional)
            page: Page number (1-indexed)
            page_size: Items per page (max 50)

        Returns:
            Dict with refunds list and pagination info
        """
        page_size = min(page_size, 50)
        offset = (page - 1) * page_size

        with SessionLocal() as db:
            query = db.query(ClientRefund).filter(
                ClientRefund.company_id == str(company_id),
            )

            if status and status in self.VALID_STATUSES:
                query = query.filter(ClientRefund.status == status)

            total = query.count()
            refunds = query.order_by(
                desc(ClientRefund.created_at),
            ).offset(offset).limit(page_size).all()

            return {
                "refunds": [self._to_dict(r) for r in refunds],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size,
                },
            }

    def process_refund(
        self,
        company_id: UUID,
        refund_id: str,
        external_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Mark a refund request as processed.

        This is called when the client confirms the refund
        was processed in their payment system.

        Args:
            company_id: Company UUID
            refund_id: Refund UUID
            external_ref: External reference from payment system

        Returns:
            Updated refund request dict

        Raises:
            ClientRefundNotFoundError: Refund not found
            ClientRefundError: Refund not in pending status
        """
        with SessionLocal() as db:
            refund = db.query(ClientRefund).filter(
                ClientRefund.id == refund_id,
                ClientRefund.company_id == str(company_id),
            ).first()

            if not refund:
                raise ClientRefundNotFoundError(
                    f"Refund request {refund_id} not found"
                )

            if refund.status != "pending":
                raise ClientRefundError(
                    f"Cannot process refund with status '{refund.status}'"
                )

            refund.status = "processed"
            refund.processed_at = datetime.now(timezone.utc)

            db.commit()
            db.refresh(refund)

            logger.info(
                "client_refund_processed company_id=%s refund_id=%s external_ref=%s",
                company_id,
                refund_id,
                external_ref,
            )

            return self._to_dict(refund)

    def mark_refund_failed(
        self,
        company_id: UUID,
        refund_id: str,
        failure_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Mark a refund request as failed.

        Args:
            company_id: Company UUID
            refund_id: Refund UUID
            failure_reason: Reason for failure

        Returns:
            Updated refund request dict
        """
        with SessionLocal() as db:
            refund = db.query(ClientRefund).filter(
                ClientRefund.id == refund_id,
                ClientRefund.company_id == str(company_id),
            ).first()

            if not refund:
                raise ClientRefundNotFoundError(
                    f"Refund request {refund_id} not found"
                )

            refund.status = "failed"
            # Could add failure_reason column if needed

            db.commit()
            db.refresh(refund)

            logger.info(
                "client_refund_failed company_id=%s refund_id=%s reason=%s",
                company_id,
                refund_id,
                failure_reason,
            )

            return self._to_dict(refund)

    def cancel_refund(
        self,
        company_id: UUID,
        refund_id: str,
    ) -> Dict[str, Any]:
        """
        Cancel a pending refund request.

        Args:
            company_id: Company UUID
            refund_id: Refund UUID

        Returns:
            Updated refund request dict
        """
        with SessionLocal() as db:
            refund = db.query(ClientRefund).filter(
                ClientRefund.id == refund_id,
                ClientRefund.company_id == str(company_id),
            ).first()

            if not refund:
                raise ClientRefundNotFoundError(
                    f"Refund request {refund_id} not found"
                )

            if refund.status != "pending":
                raise ClientRefundError(
                    f"Cannot cancel refund with status '{refund.status}'"
                )

            refund.status = "canceled"

            db.commit()
            db.refresh(refund)

            logger.info(
                "client_refund_canceled company_id=%s refund_id=%s",
                company_id,
                refund_id,
            )

            return self._to_dict(refund)

    def get_refund_history(
        self,
        company_id: UUID,
        months: int = 12,
    ) -> List[Dict[str, Any]]:
        """
        Get refund history for analytics.

        Args:
            company_id: Company UUID
            months: Number of months to look back

        Returns:
            List of refund records
        """
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)

        with SessionLocal() as db:
            refunds = db.query(ClientRefund).filter(
                ClientRefund.company_id == str(company_id),
                ClientRefund.created_at >= cutoff,
            ).order_by(desc(ClientRefund.created_at)).all()

            return [self._to_dict(r) for r in refunds]

    def get_refund_stats(
        self,
        company_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get refund statistics for a company.

        Args:
            company_id: Company UUID

        Returns:
            Stats dict with counts and totals
        """
        with SessionLocal() as db:
            refunds = db.query(ClientRefund).filter(
                ClientRefund.company_id == str(company_id),
            ).all()

            total_count = len(refunds)
            total_amount = sum(r.amount or Decimal("0") for r in refunds)
            pending_count = sum(1 for r in refunds if r.status == "pending")
            processed_count = sum(
                1 for r in refunds if r.status == "processed")
            failed_count = sum(1 for r in refunds if r.status == "failed")

            return {
                "total_count": total_count,
                "total_amount": str(total_amount),
                "pending_count": pending_count,
                "processed_count": processed_count,
                "failed_count": failed_count,
            }

    def _to_dict(self, refund: ClientRefund) -> Dict[str, Any]:
        """Convert ClientRefund model to dict."""
        return {
            "id": refund.id,
            "company_id": refund.company_id,
            "ticket_id": refund.ticket_id,
            "amount": str(
                refund.amount) if refund.amount else "0.00",
            "currency": refund.currency or "USD",
            "reason": refund.reason or "",
            "status": refund.status,
            "processed_at": refund.processed_at.isoformat() if refund.processed_at else None,
            "created_at": refund.created_at.isoformat() if refund.created_at else None,
            "updated_at": refund.updated_at.isoformat() if refund.updated_at else None,
        }


# ── Singleton Service ────────────────────────────────────────────────────

_client_refund_service: Optional[ClientRefundService] = None


def get_client_refund_service() -> ClientRefundService:
    """Get the client refund service singleton."""
    global _client_refund_service
    if _client_refund_service is None:
        _client_refund_service = ClientRefundService()
    return _client_refund_service
