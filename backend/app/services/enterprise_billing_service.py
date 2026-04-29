"""Enterprise Billing Service (MF6) — Manual/PO billing for enterprise."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional

from database.base import SessionLocal
from database.models.core import Company
from database.models.billing import Invoice

logger = logging.getLogger("parwa.services.enterprise_billing")


class EnterpriseBillingError(Exception):
    """Base enterprise billing error."""


class EnterpriseBillingService:
    """MF6: Manual/PO billing for enterprise customers."""

    def enable_manual_billing(self, company_id: str) -> Dict[str, Any]:
        """Set billing_method='manual'."""
        with SessionLocal() as db:
            company = db.query(Company).filter(Company.id == company_id).first()
            if not company:
                raise EnterpriseBillingError("Company not found")

            company.billing_method = "manual"
            db.commit()

            return {
                "company_id": company_id,
                "billing_method": "manual",
                "status": "enabled",
            }

    def create_manual_invoice(
        self,
        company_id: str,
        amount: Decimal,
        due_date: Optional[datetime] = None,
        line_items: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Admin creates manual invoice."""
        with SessionLocal() as db:
            company = db.query(Company).filter(Company.id == company_id).first()
            if not company:
                raise EnterpriseBillingError("Company not found")

            invoice = Invoice(
                company_id=company_id,
                amount=amount,
                currency=company.currency or "USD",
                status="pending",
                invoice_date=datetime.now(timezone.utc),
                due_date=due_date,
            )
            db.add(invoice)
            db.commit()

            return {
                "id": invoice.id,
                "company_id": company_id,
                "amount": str(amount),
                "currency": invoice.currency,
                "status": "pending",
                "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
                "billing_method": "manual",
            }

    def mark_invoice_paid(self, invoice_id: str) -> Dict[str, Any]:
        """Admin marks PO received."""
        with SessionLocal() as db:
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise EnterpriseBillingError("Invoice not found")

            invoice.status = "paid"
            invoice.paid_at = datetime.now(timezone.utc)
            db.commit()

            return {
                "id": invoice.id,
                "status": "paid",
                "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
            }

    def get_enterprise_billing_status(self, company_id: str) -> Dict[str, Any]:
        """Return billing method and status."""
        with SessionLocal() as db:
            company = db.query(Company).filter(Company.id == company_id).first()
            if not company:
                return {"status": "not_found"}

            return {
                "company_id": company_id,
                "billing_method": getattr(company, "billing_method", "paddle"),
                "currency": getattr(company, "currency", "USD"),
            }


_enterprise_service_instance: Optional[EnterpriseBillingService] = None


def get_enterprise_billing_service() -> EnterpriseBillingService:
    """Get singleton EnterpriseBillingService instance."""
    global _enterprise_service_instance
    if _enterprise_service_instance is None:
        _enterprise_service_instance = EnterpriseBillingService()
    return _enterprise_service_instance
