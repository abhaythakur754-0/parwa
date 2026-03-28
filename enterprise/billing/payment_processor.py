"""
Enterprise Billing - Payment Processor
Process enterprise payments
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import uuid


class PaymentMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    BANK_TRANSFER = "bank_transfer"
    WIRE = "wire"
    ACH = "ach"
    CHECK = "check"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payment(BaseModel):
    """Payment record"""
    payment_id: str = Field(default_factory=lambda: f"pay_{uuid.uuid4().hex[:8]}")
    invoice_id: str
    client_id: str
    amount: float
    currency: str = "USD"
    method: PaymentMethod
    status: PaymentStatus = PaymentStatus.PENDING
    reference: Optional[str] = None
    processed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict()


class PaymentProcessor:
    """
    Process enterprise payments.
    """

    def __init__(self):
        self.payments: Dict[str, Payment] = {}

    def process_payment(
        self,
        invoice_id: str,
        client_id: str,
        amount: float,
        method: PaymentMethod,
        reference: Optional[str] = None
    ) -> Payment:
        """Process a payment"""
        payment = Payment(
            invoice_id=invoice_id,
            client_id=client_id,
            amount=amount,
            method=method,
            reference=reference
        )
        self.payments[payment.payment_id] = payment
        return payment

    def complete_payment(self, payment_id: str) -> bool:
        """Mark payment as completed"""
        if payment_id not in self.payments:
            return False

        payment = self.payments[payment_id]
        payment.status = PaymentStatus.COMPLETED
        payment.processed_at = datetime.utcnow()
        return True

    def fail_payment(self, payment_id: str, reason: str) -> bool:
        """Mark payment as failed"""
        if payment_id not in self.payments:
            return False

        payment = self.payments[payment_id]
        payment.status = PaymentStatus.FAILED
        payment.metadata["failure_reason"] = reason
        return True

    def refund_payment(self, payment_id: str) -> bool:
        """Refund a payment"""
        if payment_id not in self.payments:
            return False

        payment = self.payments[payment_id]
        if payment.status != PaymentStatus.COMPLETED:
            return False

        payment.status = PaymentStatus.REFUNDED
        payment.metadata["refunded_at"] = datetime.utcnow().isoformat()
        return True

    def get_client_payments(self, client_id: str) -> List[Payment]:
        """Get all payments for a client"""
        return [p for p in self.payments.values() if p.client_id == client_id]

    def get_invoice_payments(self, invoice_id: str) -> List[Payment]:
        """Get all payments for an invoice"""
        return [p for p in self.payments.values() if p.invoice_id == invoice_id]
