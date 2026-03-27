"""
Invoice Generator for SaaS Advanced Module.

Provides invoice generation including:
- PDF invoice generation
- Line item breakdown
- Usage vs subscription charges
- Tax breakdown
- Payment terms display
- Invoice history tracking
- Integration with Paddle for payment
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class InvoiceStatus(str, Enum):
    """Invoice status enumeration."""
    DRAFT = "draft"
    PENDING = "pending"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    VOID = "void"
    REFUNDED = "refunded"


class PaymentTerms(str, Enum):
    """Payment terms enumeration."""
    IMMEDIATE = "immediate"
    NET_15 = "net_15"
    NET_30 = "net_30"
    NET_60 = "net_60"


@dataclass
class InvoiceLineItem:
    """Represents an invoice line item."""
    id: UUID = field(default_factory=uuid4)
    description: str = ""
    quantity: float = 0.0
    unit_price: float = 0.0
    subtotal: float = 0.0
    discount: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "description": self.description,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "subtotal": self.subtotal,
            "discount": self.discount,
            "tax": self.tax,
            "total": self.total,
            "metadata": self.metadata,
        }


@dataclass
class Invoice:
    """Represents a complete invoice."""
    id: UUID = field(default_factory=uuid4)
    invoice_number: str = ""
    client_id: str = ""
    company_name: str = ""
    company_email: str = ""
    status: InvoiceStatus = InvoiceStatus.DRAFT
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))
    due_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))
    payment_terms: PaymentTerms = PaymentTerms.NET_30
    line_items: List[InvoiceLineItem] = field(default_factory=list)
    subtotal: float = 0.0
    discounts: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    currency: str = "USD"
    paddle_invoice_id: Optional[str] = None
    paddle_payment_url: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "invoice_number": self.invoice_number,
            "client_id": self.client_id,
            "company_name": self.company_name,
            "company_email": self.company_email,
            "status": self.status.value,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "due_date": self.due_date.isoformat(),
            "payment_terms": self.payment_terms.value,
            "line_items": [item.to_dict() for item in self.line_items],
            "subtotal": self.subtotal,
            "discounts": self.discounts,
            "tax": self.tax,
            "total": self.total,
            "currency": self.currency,
            "paddle_invoice_id": self.paddle_invoice_id,
            "paddle_payment_url": self.paddle_payment_url,
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
        }


class InvoiceGenerator:
    """
    Generates invoices for SaaS subscriptions.

    Features:
    - PDF invoice generation
    - Line item breakdown
    - Usage vs subscription charges
    - Tax breakdown
    - Payment terms
    - History tracking
    - Paddle integration
    """

    def __init__(
        self,
        client_id: str = "",
        company_name: str = "",
        company_email: str = "",
        currency: str = "USD"
    ):
        """
        Initialize invoice generator.

        Args:
            client_id: Client identifier
            company_name: Company name for invoice
            company_email: Company email for invoice
            currency: Invoice currency
        """
        self.client_id = client_id
        self.company_name = company_name
        self.company_email = company_email
        self.currency = currency

        self._invoices: Dict[str, Invoice] = {}
        self._invoice_counter = 1000

    async def generate_invoice(
        self,
        subscription_tier: str,
        billing_cycle: str,
        usage_data: Dict[str, float],
        period_start: datetime,
        period_end: datetime,
        discount_codes: Optional[List[str]] = None,
        tax_rate: float = 0.0
    ) -> Invoice:
        """
        Generate a new invoice.

        Args:
            subscription_tier: Subscription tier
            billing_cycle: Billing cycle (monthly, annual)
            usage_data: Usage quantities by type
            period_start: Billing period start
            period_end: Billing period end
            discount_codes: Optional discount codes
            tax_rate: Tax rate to apply

        Returns:
            Generated Invoice
        """
        # Generate invoice number
        self._invoice_counter += 1
        invoice_number = f"INV-{datetime.now().year}-{self._invoice_counter:06d}"

        # Calculate due date
        due_date = datetime.now(timezone.utc) + timedelta(days=30)

        # Create line items
        line_items = []

        # Subscription charge
        base_prices = {
            "mini": {"monthly": 49, "annual": 470},
            "parwa": {"monthly": 149, "annual": 1430},
            "parwa_high": {"monthly": 499, "annual": 4790},
        }
        base_price = base_prices.get(subscription_tier, base_prices["mini"]).get(billing_cycle, 49)

        line_items.append(InvoiceLineItem(
            description=f"{subscription_tier.upper()} Subscription - {billing_cycle.title()}",
            quantity=1,
            unit_price=base_price,
            subtotal=base_price,
            total=base_price,
            metadata={"type": "subscription", "tier": subscription_tier},
        ))

        # Usage charges
        usage_rates = {
            "api_calls": 0.001,
            "ai_interactions": 0.02,
            "voice_minutes": 0.10,
            "storage_gb": 0.50,
            "sms_messages": 0.05,
        }

        for usage_type, quantity in usage_data.items():
            if quantity <= 0:
                continue

            rate = usage_rates.get(usage_type, 0.01)
            subtotal = quantity * rate

            line_items.append(InvoiceLineItem(
                description=f"Usage: {usage_type.replace('_', ' ').title()}",
                quantity=quantity,
                unit_price=rate,
                subtotal=round(subtotal, 2),
                total=round(subtotal, 2),
                metadata={"type": "usage", "usage_type": usage_type},
            ))

        # Calculate totals
        subtotal = sum(item.subtotal for item in line_items)

        # Apply discounts
        discount_amount = 0.0
        if discount_codes:
            for code in discount_codes:
                if code == "LAUNCH20":
                    discount_amount += subtotal * 0.20
                elif code == "FLAT50":
                    discount_amount += 50
                elif code == "ANNUAL15":
                    discount_amount += subtotal * 0.15

        # Calculate tax
        taxable_amount = subtotal - discount_amount
        tax = taxable_amount * tax_rate

        # Calculate total
        total = subtotal - discount_amount + tax

        invoice = Invoice(
            invoice_number=invoice_number,
            client_id=self.client_id,
            company_name=self.company_name,
            company_email=self.company_email,
            status=InvoiceStatus.DRAFT,
            period_start=period_start,
            period_end=period_end,
            due_date=due_date,
            line_items=line_items,
            subtotal=round(subtotal, 2),
            discounts=round(discount_amount, 2),
            tax=round(tax, 2),
            total=round(total, 2),
            currency=self.currency,
        )

        self._invoices[str(invoice.id)] = invoice

        logger.info(
            "Invoice generated",
            extra={
                "client_id": self.client_id,
                "invoice_number": invoice_number,
                "total": total,
            }
        )

        return invoice

    async def generate_pdf(self, invoice_id: UUID) -> Dict[str, Any]:
        """
        Generate PDF for an invoice.

        Args:
            invoice_id: Invoice UUID

        Returns:
            Dict with PDF details
        """
        invoice = self._invoices.get(str(invoice_id))
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        # In production, this would generate actual PDF
        # For now, return mock PDF data
        pdf_content = self._generate_pdf_content(invoice)

        return {
            "invoice_id": str(invoice_id),
            "invoice_number": invoice.invoice_number,
            "pdf_generated": True,
            "pdf_size_bytes": len(pdf_content),
            "filename": f"{invoice.invoice_number}.pdf",
        }

    async def send_invoice(
        self,
        invoice_id: UUID,
        recipient_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send invoice to customer.

        Args:
            invoice_id: Invoice UUID
            recipient_email: Optional override email

        Returns:
            Dict with send result
        """
        invoice = self._invoices.get(str(invoice_id))
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        email = recipient_email or invoice.company_email

        # Update status
        invoice.status = InvoiceStatus.SENT
        invoice.sent_at = datetime.now(timezone.utc)

        logger.info(
            "Invoice sent",
            extra={
                "client_id": self.client_id,
                "invoice_number": invoice.invoice_number,
                "email": email,
            }
        )

        return {
            "sent": True,
            "invoice_id": str(invoice_id),
            "invoice_number": invoice.invoice_number,
            "sent_to": email,
            "sent_at": invoice.sent_at.isoformat(),
        }

    async def mark_paid(
        self,
        invoice_id: UUID,
        paddle_payment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mark invoice as paid.

        Args:
            invoice_id: Invoice UUID
            paddle_payment_id: Optional Paddle payment ID

        Returns:
            Dict with payment result
        """
        invoice = self._invoices.get(str(invoice_id))
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = datetime.now(timezone.utc)
        invoice.paddle_invoice_id = paddle_payment_id

        logger.info(
            "Invoice paid",
            extra={
                "client_id": self.client_id,
                "invoice_number": invoice.invoice_number,
                "total": invoice.total,
            }
        )

        return {
            "paid": True,
            "invoice_id": str(invoice_id),
            "invoice_number": invoice.invoice_number,
            "paid_at": invoice.paid_at.isoformat(),
        }

    async def get_invoice(self, invoice_id: UUID) -> Optional[Invoice]:
        """
        Get invoice by ID.

        Args:
            invoice_id: Invoice UUID

        Returns:
            Invoice if found
        """
        return self._invoices.get(str(invoice_id))

    async def get_invoice_by_number(self, invoice_number: str) -> Optional[Invoice]:
        """
        Get invoice by number.

        Args:
            invoice_number: Invoice number

        Returns:
            Invoice if found
        """
        for invoice in self._invoices.values():
            if invoice.invoice_number == invoice_number:
                return invoice
        return None

    async def get_invoice_history(
        self,
        limit: int = 50,
        status: Optional[InvoiceStatus] = None
    ) -> List[Dict[str, Any]]:
        """
        Get invoice history.

        Args:
            limit: Maximum invoices to return
            status: Optional status filter

        Returns:
            List of invoices
        """
        invoices = [
            invoice.to_dict()
            for invoice in self._invoices.values()
            if invoice.client_id == self.client_id
        ]

        if status:
            invoices = [i for i in invoices if i["status"] == status.value]

        invoices.sort(key=lambda x: x["created_at"], reverse=True)

        return invoices[:limit]

    async def void_invoice(self, invoice_id: UUID, reason: str) -> Dict[str, Any]:
        """
        Void an invoice.

        Args:
            invoice_id: Invoice UUID
            reason: Reason for voiding

        Returns:
            Dict with void result
        """
        invoice = self._invoices.get(str(invoice_id))
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        if invoice.status == InvoiceStatus.PAID:
            raise ValueError("Cannot void a paid invoice")

        invoice.status = InvoiceStatus.VOID

        logger.info(
            "Invoice voided",
            extra={
                "client_id": self.client_id,
                "invoice_number": invoice.invoice_number,
                "reason": reason,
            }
        )

        return {
            "voided": True,
            "invoice_id": str(invoice_id),
            "invoice_number": invoice.invoice_number,
            "reason": reason,
        }

    async def create_paddle_checkout(
        self,
        invoice_id: UUID
    ) -> Dict[str, Any]:
        """
        Create Paddle checkout for invoice.

        CRITICAL: This creates a checkout but doesn't process payment
        without customer action.

        Args:
            invoice_id: Invoice UUID

        Returns:
            Dict with checkout details
        """
        invoice = self._invoices.get(str(invoice_id))
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        # Mock Paddle checkout creation
        checkout_id = f"cko_{uuid4().hex[:24]}"
        checkout_url = f"https://buy.paddle.com/checkout/{checkout_id}"

        invoice.paddle_payment_url = checkout_url

        logger.info(
            "Paddle checkout created",
            extra={
                "client_id": self.client_id,
                "invoice_number": invoice.invoice_number,
                "checkout_id": checkout_id,
            }
        )

        return {
            "invoice_id": str(invoice_id),
            "checkout_id": checkout_id,
            "checkout_url": checkout_url,
            "amount": invoice.total,
            "currency": invoice.currency,
        }

    def _generate_pdf_content(self, invoice: Invoice) -> str:
        """Generate PDF content for invoice (mock)."""
        content = f"""
INVOICE: {invoice.invoice_number}

Bill To:
{invoice.company_name}
{invoice.company_email}

Period: {invoice.period_start.date()} - {invoice.period_end.date()}
Due Date: {invoice.due_date.date()}

Items:
"""
        for item in invoice.line_items:
            content += f"  {item.description}: ${item.total:.2f}\n"

        content += f"""
Subtotal: ${invoice.subtotal:.2f}
Discounts: -${invoice.discounts:.2f}
Tax: ${invoice.tax:.2f}
TOTAL: ${invoice.total:.2f}
"""
        return content


# Export for testing
__all__ = [
    "InvoiceGenerator",
    "Invoice",
    "InvoiceLineItem",
    "InvoiceStatus",
    "PaymentTerms",
]
