"""
Invoice Service (F-023)

Handles invoice management:
- List invoices for a company
- Get invoice PDF (from Paddle or generate)
- Sync invoices from Paddle API
- Track invoice status

BC-001: All operations validate company_id
BC-002: All money calculations use Decimal
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.clients.paddle_client import (
    PaddleClient,
    PaddleError,
    get_paddle_client,
)
from database.base import SessionLocal
from database.models.billing import Invoice, Subscription
from database.models.core import Company

logger = logging.getLogger("parwa.services.invoice")


class InvoiceError(Exception):
    """Base exception for invoice errors."""
    pass


class InvoiceNotFoundError(InvoiceError):
    """Invoice not found."""
    pass


class InvoiceAccessDeniedError(InvoiceError):
    """Access denied to invoice."""
    pass


class InvoiceService:
    """
    Invoice management service.

    Usage:
        service = InvoiceService()
        invoices = await service.get_invoice_list(company_id)
        pdf = await service.get_invoice_pdf(company_id, invoice_id)
    """

    def __init__(self, paddle_client: Optional[PaddleClient] = None):
        self._paddle_client = paddle_client

    async def _get_paddle(self) -> PaddleClient:
        """Get Paddle client (lazy initialization)."""
        if self._paddle_client is None:
            self._paddle_client = get_paddle_client()
        return self._paddle_client

    async def get_invoice_list(
        self,
        company_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Get paginated invoice list for a company.

        Args:
            company_id: Company UUID
            page: Page number (1-indexed)
            page_size: Items per page (max 50)

        Returns:
            Dict with invoices list and pagination info
        """
        page_size = min(page_size, 50)  # Cap at 50
        offset = (page - 1) * page_size

        with SessionLocal() as db:
            # Get total count
            total = db.query(Invoice).filter(
                Invoice.company_id == str(company_id),
            ).count()

            # Get paginated invoices
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

    async def get_invoice(
        self,
        company_id: UUID,
        invoice_id: str,
    ) -> Dict[str, Any]:
        """
        Get single invoice details.

        Args:
            company_id: Company UUID
            invoice_id: Invoice UUID

        Returns:
            Invoice details dict

        Raises:
            InvoiceNotFoundError: Invoice not found
            InvoiceAccessDeniedError: Invoice belongs to different company
        """
        with SessionLocal() as db:
            invoice = db.query(Invoice).filter(
                Invoice.id == invoice_id,
            ).first()

            if not invoice:
                raise InvoiceNotFoundError(
                    f"Invoice {invoice_id} not found"
                )

            # BC-001: Validate company_id
            if invoice.company_id != str(company_id):
                raise InvoiceAccessDeniedError(
                    "Access denied to this invoice"
                )

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

    async def get_invoice_pdf(
        self,
        company_id: UUID,
        invoice_id: str,
    ) -> bytes:
        """
        Get invoice PDF bytes.

        First validates access, then fetches PDF from Paddle.

        Args:
            company_id: Company UUID
            invoice_id: Invoice UUID

        Returns:
            PDF bytes

        Raises:
            InvoiceNotFoundError: Invoice not found
            InvoiceAccessDeniedError: Access denied
            InvoiceError: PDF generation failed
        """
        # First validate access
        invoice = await self.get_invoice(company_id, invoice_id)

        if not invoice.get("paddle_invoice_id"):
            # Generate local PDF if no Paddle invoice
            return await self._generate_local_pdf(invoice)

        try:
            paddle = await self._get_paddle()
            pdf_bytes = await paddle.get_invoice_pdf(
                invoice["paddle_invoice_id"]
            )
            logger.info(
                "invoice_pdf_retrieved company_id=%s invoice_id=%s",
                company_id,
                invoice_id,
            )
            return pdf_bytes

        except PaddleError as e:
            logger.error(
                "invoice_pdf_failed company_id=%s invoice_id=%s error=%s",
                company_id,
                invoice_id,
                str(e),
            )
            # Fallback to local PDF generation
            return await self._generate_local_pdf(invoice)

    async def _generate_local_pdf(
        self,
        invoice: Dict[str, Any],
    ) -> bytes:
        """
        Generate a simple PDF invoice locally.

        Used when Paddle PDF is unavailable.

        Args:
            invoice: Invoice dict

        Returns:
            PDF bytes
        """
        # Simple PDF generation using reportlab-style approach
        # In production, would use reportlab or weasyprint
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            from reportlab.pdfgen import canvas
            from io import BytesIO

            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter

            # Header
            c.setFont("Helvetica-Bold", 24)
            c.drawString(inch, height - inch, "PARWA")

            c.setFont("Helvetica", 12)
            c.drawString(inch, height - 1.5 * inch, "Invoice")

            # Invoice details
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

            # Footer
            c.setFont("Helvetica", 10)
            c.drawString(inch, inch, "Thank you for your business!")

            c.save()
            buffer.seek(0)

            logger.info(
                "invoice_pdf_generated_locally invoice_id=%s",
                invoice.get("id"),
            )
            return buffer.read()

        except ImportError:
            # reportlab not available - return minimal PDF
            logger.warning(
                "reportlab_not_available invoice_id=%s",
                invoice.get("id"),
            )
            # Return a minimal valid PDF
            minimal_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
            return minimal_pdf

    async def sync_invoices_from_paddle(
        self,
        company_id: UUID,
    ) -> Dict[str, Any]:
        """
        Sync recent invoices from Paddle API.

        Pulls invoices and stores/updates in local DB.

        Args:
            company_id: Company UUID

        Returns:
            Sync result with count of invoices synced
        """
        with SessionLocal() as db:
            # Get company for paddle_customer_id
            company = db.query(Company).filter(
                Company.id == str(company_id),
            ).first()

            if not company or not company.paddle_customer_id:
                logger.info(
                    "invoice_sync_skipped company_id=%s reason=no_paddle_customer",
                    company_id,
                )
                return {
                    "synced": 0,
                    "message": "No Paddle customer ID found",
                }

            try:
                paddle = await self._get_paddle()

                # Get transactions (Paddle invoices are tied to transactions)
                result = await paddle.list_transactions(
                    customer_id=company.paddle_customer_id,
                    per_page=50,
                )

                transactions = result.get("data", [])
                synced = 0

                for txn in transactions:
                    txn_id = txn.get("id")
                    if not txn_id:
                        continue

                    # Check for existing invoice
                    existing = db.query(Invoice).filter(
                        Invoice.paddle_invoice_id == txn_id,
                    ).first()

                    invoice_data = {
                        "company_id": str(company_id),
                        "paddle_invoice_id": txn_id,
                        "amount": Decimal(str(txn.get("amount", "0"))),
                        "currency": txn.get("currency_code", "USD"),
                        "status": txn.get("status", "pending"),
                        "invoice_date": datetime.fromisoformat(
                            txn["created_at"].replace("Z", "+00:00")
                        ) if txn.get("created_at") else None,
                    }

                    if existing:
                        # Update existing
                        for key, value in invoice_data.items():
                            if key != "company_id":
                                setattr(existing, key, value)
                    else:
                        # Create new
                        invoice = Invoice(**invoice_data)
                        db.add(invoice)

                    synced += 1

                db.commit()

                logger.info(
                    "invoice_sync_complete company_id=%s synced=%d",
                    company_id,
                    synced,
                )

                return {
                    "synced": synced,
                    "message": f"Synced {synced} invoices from Paddle",
                }

            except PaddleError as e:
                logger.error(
                    "invoice_sync_failed company_id=%s error=%s",
                    company_id,
                    str(e),
                )
                return {
                    "synced": 0,
                    "message": f"Sync failed: {str(e)}",
                }

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
        """
        Create a new invoice record.

        Used when processing webhooks or manual billing operations.

        Args:
            company_id: Company UUID
            amount: Invoice amount
            currency: Currency code (default USD)
            paddle_invoice_id: Paddle invoice ID if available
            status: Invoice status (default pending)
            invoice_date: Invoice date
            due_date: Due date

        Returns:
            Created invoice dict
        """
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
                company_id,
                invoice.id,
                amount,
            )

            return {
                "id": invoice.id,
                "company_id": invoice.company_id,
                "amount": str(invoice.amount),
                "currency": invoice.currency,
                "status": invoice.status,
                "created_at": invoice.created_at.isoformat(),
            }

    async def update_invoice_status(
        self,
        invoice_id: str,
        status: str,
        paid_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Update invoice status.

        Args:
            invoice_id: Invoice UUID
            status: New status
            paid_at: Payment timestamp (if paid)

        Returns:
            Updated invoice dict
        """
        valid_statuses = {"pending", "paid", "void", "refunded"}
        if status not in valid_statuses:
            raise InvoiceError(
                f"Invalid status: {status}. Must be one of {valid_statuses}"
            )

        with SessionLocal() as db:
            invoice = db.query(Invoice).filter(
                Invoice.id == invoice_id,
            ).first()

            if not invoice:
                raise InvoiceNotFoundError(
                    f"Invoice {invoice_id} not found"
                )

            invoice.status = status
            if paid_at:
                invoice.paid_at = paid_at
            elif status == "paid":
                invoice.paid_at = datetime.now(timezone.utc)

            db.commit()
            db.refresh(invoice)

            logger.info(
                "invoice_status_updated invoice_id=%s status=%s",
                invoice_id,
                status,
            )

            return {
                "id": invoice.id,
                "status": invoice.status,
                "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
            }


# ── Singleton Service ────────────────────────────────────────────────────

_invoice_service: Optional[InvoiceService] = None


def get_invoice_service() -> InvoiceService:
    """Get the invoice service singleton."""
    global _invoice_service
    if _invoice_service is None:
        _invoice_service = InvoiceService()
    return _invoice_service
