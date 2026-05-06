"""
Enterprise Billing - Invoice Generator
Generate enterprise invoices
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import uuid


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class InvoiceLineItem(BaseModel):
    """Invoice line item"""
    description: str
    quantity: float
    unit_price: float
    total: float
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict()


class EnterpriseInvoice(BaseModel):
    """Enterprise invoice"""
    invoice_id: str = Field(default_factory=lambda: f"inv_{uuid.uuid4().hex[:8]}")
    client_id: str
    contract_id: Optional[str] = None
    invoice_number: str = ""
    status: InvoiceStatus = InvoiceStatus.DRAFT
    issue_date: datetime = Field(default_factory=datetime.utcnow)
    due_date: datetime
    line_items: List[InvoiceLineItem] = Field(default_factory=list)
    subtotal: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    currency: str = "USD"
    notes: Optional[str] = None
    paid_at: Optional[datetime] = None

    model_config = ConfigDict()


class InvoiceGenerator:
    """
    Generate enterprise invoices.
    """

    def __init__(self):
        self.invoices: Dict[str, EnterpriseInvoice] = {}
        self.counter = 1

    def create_invoice(
        self,
        client_id: str,
        line_items: List[Dict[str, Any]],
        due_days: int = 30,
        contract_id: Optional[str] = None,
        tax_rate: float = 0.0
    ) -> EnterpriseInvoice:
        """Create a new invoice"""
        now = datetime.utcnow()
        invoice_number = f"INV-{now.strftime('%Y%m')}-{self.counter:04d}"
        self.counter += 1

        items = [
            InvoiceLineItem(
                description=item["description"],
                quantity=item.get("quantity", 1),
                unit_price=item["unit_price"],
                total=item.get("quantity", 1) * item["unit_price"]
            )
            for item in line_items
        ]

        subtotal = sum(item.total for item in items)
        tax = subtotal * tax_rate
        total = subtotal + tax

        invoice = EnterpriseInvoice(
            client_id=client_id,
            contract_id=contract_id,
            invoice_number=invoice_number,
            due_date=now + timedelta(days=due_days),
            line_items=items,
            subtotal=subtotal,
            tax=tax,
            total=total
        )

        self.invoices[invoice.invoice_id] = invoice
        return invoice

    def send_invoice(self, invoice_id: str) -> bool:
        """Mark invoice as sent"""
        if invoice_id not in self.invoices:
            return False
        self.invoices[invoice_id].status = InvoiceStatus.SENT
        return True

    def mark_paid(self, invoice_id: str) -> bool:
        """Mark invoice as paid"""
        if invoice_id not in self.invoices:
            return False
        invoice = self.invoices[invoice_id]
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = datetime.utcnow()
        return True

    def get_client_invoices(self, client_id: str) -> List[EnterpriseInvoice]:
        """Get all invoices for a client"""
        return [i for i in self.invoices.values() if i.client_id == client_id]

    def get_overdue_invoices(self) -> List[EnterpriseInvoice]:
        """Get all overdue invoices"""
        now = datetime.utcnow()
        return [
            i for i in self.invoices.values()
            if i.status == InvoiceStatus.SENT and i.due_date < now
        ]

    def generate_monthly_invoice(
        self,
        client_id: str,
        base_amount: float,
        usage_charges: Optional[Dict[str, float]] = None
    ) -> EnterpriseInvoice:
        """Generate monthly invoice"""
        line_items = [
            {"description": "Monthly Subscription", "unit_price": base_amount}
        ]

        if usage_charges:
            for usage_type, amount in usage_charges.items():
                line_items.append({
                    "description": f"Usage: {usage_type}",
                    "unit_price": amount
                })

        return self.create_invoice(client_id, line_items)
