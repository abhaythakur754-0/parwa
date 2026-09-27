"""
Invoice Service — DB-only (Razorpay is the billing provider)

Paddle was removed on 2026-06-24. Invoices are now created locally when
Razorpay webhooks fire (see `app.services.razorpay_service._handle_charged`
and `_handle_payment_captured`). This service owns:
- Listing / fetching invoices from the local DB
- Generating PDF invoices locally (reportlab)
- Creating / updating invoice records (used by webhook handlers)

BC-001: All operations validate company_id
BC-002: All money calculations use Decimal
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from database.base import SessionLocal
from database.models.billing import Invoice, Subscription
from database.models.core import Company

logger = logging.getLogger("parwa.services.invoice")


# ── Exceptions ──────────────────────────────────────────────────────────

class InvoiceError(Exception):
    """Base exception for invoice errors."""
    def __init__(self, message: str = "Invoice operation failed", **kwargs):
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)


class InvoiceNotFoundError(InvoiceError):
    def __init__(self, message: str = "Invoice not found", **kwargs):
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)


class InvoiceAccessDeniedError(InvoiceError):
    def __init__(self, message: str = "Access denied to invoice", **kwargs):
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)


# ── Service ─────────────────────────────────────────────────────────────

class InvoiceService:
    """Invoice management service (DB-only, no provider sync)."""

    def __init__(self, *args, **kwargs):
        # No provider client anymore. Args kept for backward-compat calls.
        pass

    async def get_invoice_list(
        self,
        company_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Get paginated invoice list for a company."""
        page_size = min(page_size, 50)
        offset = (page - 1) * page_size

        def _db_work():
            with SessionLocal() as db:
                total = db.query(Invoice).filter(
                    Invoice.company_id == str(company_id),
                ).count()

                invoices = db.query(Invoice).filter(
                    Invoice.company_id == str(company_id),
                ).order_by(
                    desc(Invoice.invoice_date),
                    desc(Invoice.created_at),
                ).offset(offset).limit(page_size).all()

                return {
                    "invoices": [
                        {
                            "id": inv.id,
                            "paddle_invoice_id": inv.paddle_invoice_id,
                            "amount": str(inv.amount) if inv.amount else "0.00",
                            "currency": inv.currency or "USD",
                            "status": inv.status,
                            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                            "due_date": inv.due_date.isoformat() if inv.due_date else None,
                            "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
                            "created_at": inv.created_at.isoformat() if inv.created_at else None,
                        }
                        for inv in invoices
                    ],
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total": total,
                        "total_pages": (total + page_size - 1) // page_size,
                    },
                }
        return await asyncio.to_thread(_db_work)

    async def get_invoice(
        self,
        company_id: UUID,
        invoice_id: str,
    ) -> Dict[str, Any]:
        """Get single invoice details."""
        def _db_work():
            with SessionLocal() as db:
                invoice = db.query(Invoice).filter(
                    Invoice.id == invoice_id,
                ).first()

                if not invoice:
                    raise InvoiceNotFoundError(f"Invoice {invoice_id} not found")

                # BC-001: Validate company_id
                if invoice.company_id != str(company_id):
                    raise InvoiceAccessDeniedError("Access denied to this invoice")

                return {
                    "id": invoice.id,
                    "company_id": invoice.company_id,
                    "paddle_invoice_id": invoice.paddle_invoice_id,
                    "amount": str(invoice.amount) if invoice.amount else "0.00",
                    "currency": invoice.currency or "USD",
                    "status": invoice.status,
                    "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                    "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
                    "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
                    "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
                }
        return await asyncio.to_thread(_db_work)

    async def get_invoice_pdf(
        self,
        company_id: UUID,
        invoice_id: str,
    ) -> bytes:
        """Get invoice PDF bytes — always generated locally now (Paddle removed)."""
        invoice = await self.get_invoice(company_id, invoice_id)
        return await self._generate_local_pdf(invoice)

    async def _generate_local_pdf(self, invoice: Dict[str, Any]) -> bytes:
        """Generate a simple PDF invoice locally using reportlab."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            from reportlab.pdfgen import canvas
            from io import BytesIO

            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter

            c.setFont("Helvetica-Bold", 24)
            c.drawString(inch, height - inch, "PARWA")
            c.setFont("Helvetica", 12)
            c.drawString(inch, height - 1.5 * inch, "Invoice")

            c.setFont("Helvetica-Bold", 12)
            y = height - 2.5 * inch
            c.drawString(inch, y, f"Invoice ID: {invoice.get('id', 'N/A')}")
            y -= 0.3 * inch
            c.drawString(inch, y, f"Amount: {invoice.get('amount', '0.00')} {invoice.get('currency', 'USD')}")
            y -= 0.3 * inch
            c.drawString(inch, y, f"Status: {invoice.get('status', 'pending')}")
            y -= 0.3 * inch

            if invoice.get("invoice_date"):
                c.drawString(inch, y, f"Date: {invoice['invoice_date']}")
                y -= 0.3 * inch
            if invoice.get("due_date"):
                c.drawString(inch, y, f"Due: {invoice['due_date']}")
                y -= 0.3 * inch

            c.setFont("Helvetica", 10)
            c.drawString(inch, inch, "Thank you for your business!")
            c.save()
            buffer.seek(0)

            logger.info("invoice_pdf_generated_locally invoice_id=%s", invoice.get("id"))
            return buffer.read()

        except ImportError:
            logger.warning("reportlab_not_available invoice_id=%s", invoice.get("id"))
            # Minimal valid PDF fallback
            return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"

    async def create_invoice_record(
        self,
        company_id: UUID,
        amount: Decimal,
        currency: str = "USD",
        paddle_invoice_id: Optional[str] = None,
        status: str = "pending",
        invoice_date: Optional[datetime] = None,
        due_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Create a new invoice record (used by Razorpay webhook handlers).

        Note: `paddle_invoice_id` field name is kept on the DB model for
        backward compat — it now stores the Razorpay payment_id.
        """
        def _db_work():
            with SessionLocal() as db:
                invoice = Invoice(
                    company_id=str(company_id),
                    paddle_invoice_id=paddle_invoice_id,
                    amount=amount,
                    currency=currency,
                    status=status,
                    invoice_date=invoice_date or datetime.now(timezone.utc),
                    due_date=due_date,
                )
                db.add(invoice)
                db.commit()
                db.refresh(invoice)
                logger.info(
                    "invoice_created company_id=%s invoice_id=%s amount=%s",
                    company_id, invoice.id, amount,
                )
                return {
                    "id": invoice.id,
                    "company_id": invoice.company_id,
                    "amount": str(invoice.amount),
                    "currency": invoice.currency,
                    "status": invoice.status,
                    "created_at": invoice.created_at.isoformat(),
                }
        return await asyncio.to_thread(_db_work)

    async def update_invoice_status(
        self,
        invoice_id: str,
        status: str,
        paid_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Update invoice status."""
        valid_statuses = {"pending", "paid", "void", "refunded"}
        if status not in valid_statuses:
            raise InvoiceError(
                f"Invalid status: {status}. Must be one of {valid_statuses}"
            )

        def _db_work():
            with SessionLocal() as db:
                invoice = db.query(Invoice).filter(
                    Invoice.id == invoice_id,
                ).first()
                if not invoice:
                    raise InvoiceNotFoundError(f"Invoice {invoice_id} not found")

                invoice.status = status
                if paid_at:
                    invoice.paid_at = paid_at
                elif status == "paid":
                    invoice.paid_at = datetime.now(timezone.utc)

                db.commit()
                db.refresh(invoice)
                logger.info("invoice_status_updated invoice_id=%s status=%s", invoice_id, status)
                return {
                    "id": invoice.id,
                    "status": invoice.status,
                    "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
                }
        return await asyncio.to_thread(_db_work)

    # ── Deprecated provider-side sync ───────────────────────────────────

    async def sync_invoices_from_paddle(self, *args, **kwargs):
        """Deprecated — Paddle is removed. Invoices are created locally
        when Razorpay webhooks fire (see razorpay_service._handle_charged)."""
        return {"synced": 0, "message": "Paddle is removed. Invoices sync via Razorpay webhooks."}


# ── Singleton ───────────────────────────────────────────────────────────

_invoice_service: Optional[InvoiceService] = None


def get_invoice_service() -> InvoiceService:
    global _invoice_service
    if _invoice_service is None:
        _invoice_service = InvoiceService()
    return _invoice_service
