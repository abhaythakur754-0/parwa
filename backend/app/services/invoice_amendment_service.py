"""Invoice Amendment Service (MF7) — Invoice amendments for admin."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional

from database.base import SessionLocal
from database.models.billing import Invoice
from database.models.billing_extended import InvoiceAmendment

logger = logging.getLogger("parwa.services.invoice_amendment")


class AmendmentError(Exception):
    """Base amendment error."""
    pass


class InvoiceNotFoundError(AmendmentError):
    pass


class AmendmentNotFoundError(AmendmentError):
    pass


class InvoiceAmendmentService:
    """MF7: Invoice amendment management."""

    def create_amendment(
        self,
        invoice_id: str,
        new_amount: Decimal,
        amendment_type: str,
        reason: str,
        approved_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Admin create amendment."""
        with SessionLocal() as db:
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise InvoiceNotFoundError(f"Invoice {invoice_id} not found")

            amendment = InvoiceAmendment(
                invoice_id=invoice_id,
                company_id=invoice.company_id,
                original_amount=invoice.amount,
                new_amount=new_amount,
                amendment_type=amendment_type,  # 'credit' or 'additional_charge'
                reason=reason,
                approved_by=approved_by,
            )
            db.add(amendment)
            db.commit()

            return {
                "id": amendment.id,
                "invoice_id": invoice_id,
                "original_amount": str(invoice.amount),
                "new_amount": str(new_amount),
                "amendment_type": amendment_type,
                "status": "created",
            }

    def list_amendments(self, invoice_id: str) -> List[Dict[str, Any]]:
        """List amendments for an invoice."""
        with SessionLocal() as db:
            amendments = (
                db.query(InvoiceAmendment)
                .filter(InvoiceAmendment.invoice_id == invoice_id)
                .order_by(InvoiceAmendment.created_at.desc())
                .all()
            )

            return [
                {
                    "id": a.id,
                    "invoice_id": a.invoice_id,
                    "original_amount": str(a.original_amount),
                    "new_amount": str(a.new_amount),
                    "amendment_type": a.amendment_type,
                    "reason": a.reason,
                    "approved_by": a.approved_by,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in amendments
            ]

    def process_amendment(self, amendment_id: str) -> Dict[str, Any]:
        """Create Paddle credit note or additional charge."""
        with SessionLocal() as db:
            amendment = (
                db.query(InvoiceAmendment)
                .filter(InvoiceAmendment.id == amendment_id)
                .first()
            )
            if not amendment:
                raise AmendmentNotFoundError(f"Amendment {amendment_id} not found")

            # In production, this would call Paddle API
            amendment.paddle_credit_note_id = f"cn_{amendment_id[:8]}"
            db.commit()

            return {
                "id": amendment.id,
                "status": "processed",
                "paddle_credit_note_id": amendment.paddle_credit_note_id,
            }


_amendment_service_instance: Optional[InvoiceAmendmentService] = None


def get_invoice_amendment_service() -> InvoiceAmendmentService:
    """Get singleton InvoiceAmendmentService instance."""
    global _amendment_service_instance
    if _amendment_service_instance is None:
        _amendment_service_instance = InvoiceAmendmentService()
    return _amendment_service_instance
