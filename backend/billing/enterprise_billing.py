"""
Enterprise Billing Module for Contract-Based Billing.

This module provides enterprise-specific billing features including
contract invoices, custom pricing, and enterprise billing management.
"""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ContractTier(BaseModel):
    """Enterprise contract tier definition."""
    
    name: str
    min_seats: int
    max_seats: Optional[int] = None
    price_per_seat: Decimal
    features: List[str] = Field(default_factory=list)
    custom_features: Dict[str, Any] = Field(default_factory=dict)


class EnterpriseContract(BaseModel):
    """Enterprise contract model."""
    
    contract_id: str = Field(default_factory=lambda: f"ENT-{uuid.uuid4().hex[:8].upper()}")
    tenant_id: str
    company_name: str
    contract_start: datetime
    contract_end: datetime
    billing_cycle: str = "monthly"  # monthly, quarterly, annual
    tiers: List[ContractTier] = Field(default_factory=list)
    seats_included: int
    overage_rate: Decimal = Decimal("0.00")
    discount_percent: Decimal = Decimal("0.00")
    payment_terms: str = "net_30"
    signed: bool = False
    signed_at: Optional[datetime] = None
    signed_by: Optional[str] = None
    
    def calculate_monthly_value(self) -> Decimal:
        """Calculate monthly contract value."""
        base = Decimal("0.00")
        remaining_seats = self.seats_included
        
        for tier in self.tiers:
            tier_seats = 0
            if tier.max_seats:
                tier_seats = min(remaining_seats, tier.max_seats - tier.min_seats + 1)
            else:
                tier_seats = remaining_seats
            
            base += Decimal(str(tier_seats)) * tier.price_per_seat
            remaining_seats -= tier_seats
            
            if remaining_seats <= 0:
                break
        
        # Apply discount
        if self.discount_percent > 0:
            base = base * (1 - self.discount_percent / 100)
        
        return base


class ContractInvoice(BaseModel):
    """Enterprise contract invoice model."""
    
    invoice_id: str = Field(default_factory=lambda: f"INV-{uuid.uuid4().hex[:8].upper()}")
    contract_id: str
    tenant_id: str
    invoice_number: str
    invoice_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    due_date: datetime
    period_start: datetime
    period_end: datetime
    line_items: List[Dict[str, Any]] = Field(default_factory=list)
    subtotal: Decimal = Decimal("0.00")
    discount_amount: Decimal = Decimal("0.00")
    tax_amount: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")
    currency: str = "USD"
    status: str = "draft"  # draft, sent, paid, overdue, cancelled
    notes: str = ""
    paid_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "invoice_id": self.invoice_id,
            "contract_id": self.contract_id,
            "tenant_id": self.tenant_id,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date.isoformat(),
            "due_date": self.due_date.isoformat(),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "line_items": self.line_items,
            "subtotal": str(self.subtotal),
            "discount_amount": str(self.discount_amount),
            "tax_amount": str(self.tax_amount),
            "total": str(self.total),
            "currency": self.currency,
            "status": self.status,
            "notes": self.notes
        }


class EnterpriseBillingService:
    """
    Enterprise billing service for contract-based billing.
    
    Provides contract management, invoice generation, and billing
    operations for enterprise clients.
    """
    
    def __init__(self):
        """Initialize enterprise billing service."""
        self._contracts: Dict[str, EnterpriseContract] = {}
        self._invoices: Dict[str, ContractInvoice] = {}
        self._tenant_contract_index: Dict[str, str] = {}
        self._invoice_counter = 1000
    
    def create_contract(
        self,
        tenant_id: str,
        company_name: str,
        seats_included: int,
        contract_duration_months: int = 12,
        billing_cycle: str = "monthly",
        custom_tiers: Optional[List[Dict[str, Any]]] = None,
        discount_percent: Decimal = Decimal("0.00"),
        payment_terms: str = "net_30"
    ) -> EnterpriseContract:
        """
        Create a new enterprise contract.
        
        Args:
            tenant_id: Tenant identifier
            company_name: Company name
            seats_included: Number of seats included
            contract_duration_months: Contract duration in months
            billing_cycle: Billing cycle (monthly, quarterly, annual)
            custom_tiers: Custom pricing tiers (optional)
            discount_percent: Discount percentage
            payment_terms: Payment terms
            
        Returns:
            Created EnterpriseContract
        """
        now = datetime.now(timezone.utc)
        contract_end = now + timedelta(days=30 * contract_duration_months)
        
        # Use default tiers if not provided
        tiers = []
        if custom_tiers:
            for t in custom_tiers:
                tiers.append(ContractTier(**t))
        else:
            tiers = [
                ContractTier(
                    name="Base",
                    min_seats=1,
                    max_seats=50,
                    price_per_seat=Decimal("49.00"),
                    features=["All PARWA High features", "Priority support", "SSO"]
                ),
                ContractTier(
                    name="Growth",
                    min_seats=51,
                    max_seats=200,
                    price_per_seat=Decimal("39.00"),
                    features=["All Base features", "Dedicated CSM", "API access"]
                ),
                ContractTier(
                    name="Enterprise",
                    min_seats=201,
                    max_seats=None,
                    price_per_seat=Decimal("29.00"),
                    features=["All Growth features", "Custom integrations", "SLA guarantee"]
                )
            ]
        
        contract = EnterpriseContract(
            tenant_id=tenant_id,
            company_name=company_name,
            contract_start=now,
            contract_end=contract_end,
            billing_cycle=billing_cycle,
            tiers=tiers,
            seats_included=seats_included,
            discount_percent=discount_percent,
            payment_terms=payment_terms
        )
        
        self._contracts[contract.contract_id] = contract
        self._tenant_contract_index[tenant_id] = contract.contract_id
        
        return contract
    
    def get_contract(self, contract_id: str) -> Optional[EnterpriseContract]:
        """Get contract by ID."""
        return self._contracts.get(contract_id)
    
    def get_contract_for_tenant(self, tenant_id: str) -> Optional[EnterpriseContract]:
        """Get contract for a tenant."""
        contract_id = self._tenant_contract_index.get(tenant_id)
        if contract_id:
            return self._contracts.get(contract_id)
        return None
    
    def sign_contract(
        self,
        contract_id: str,
        signed_by: str
    ) -> Optional[EnterpriseContract]:
        """
        Sign a contract.
        
        Args:
            contract_id: Contract identifier
            signed_by: Email of person signing
            
        Returns:
            Signed contract or None
        """
        contract = self._contracts.get(contract_id)
        if not contract:
            return None
        
        contract.signed = True
        contract.signed_at = datetime.now(timezone.utc)
        contract.signed_by = signed_by
        
        return contract
    
    def generate_contract_invoice(
        self,
        contract_id: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> ContractInvoice:
        """
        Generate an invoice for a contract.
        
        Args:
            contract_id: Contract identifier
            period_start: Billing period start (optional)
            period_end: Billing period end (optional)
            
        Returns:
            Generated ContractInvoice
        """
        contract = self._contracts.get(contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")
        
        now = datetime.now(timezone.utc)
        
        # Set period dates
        if not period_start:
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if not period_end:
            if contract.billing_cycle == "monthly":
                period_end = period_start + timedelta(days=30)
            elif contract.billing_cycle == "quarterly":
                period_end = period_start + timedelta(days=90)
            else:  # annual
                period_end = period_start + timedelta(days=365)
        
        # Calculate invoice amounts
        subtotal = contract.calculate_monthly_value()
        
        # Adjust for billing cycle
        if contract.billing_cycle == "quarterly":
            subtotal = subtotal * 3
        elif contract.billing_cycle == "annual":
            subtotal = subtotal * 12
        
        # Calculate discount
        discount_amount = subtotal * (contract.discount_percent / 100)
        
        # Calculate total
        total = subtotal - discount_amount
        
        # Generate invoice number
        self._invoice_counter += 1
        invoice_number = f"ENT-{now.strftime('%Y%m')}-{self._invoice_counter}"
        
        # Create line items
        line_items = [
            {
                "description": f"PARWA Enterprise - {contract.seats_included} seats",
                "quantity": contract.seats_included,
                "unit_price": str(subtotal / contract.seats_included),
                "amount": str(subtotal)
            }
        ]
        
        invoice = ContractInvoice(
            contract_id=contract_id,
            tenant_id=contract.tenant_id,
            invoice_number=invoice_number,
            due_date=now + timedelta(days=30),
            period_start=period_start,
            period_end=period_end,
            line_items=line_items,
            subtotal=subtotal,
            discount_amount=discount_amount,
            total=total
        )
        
        self._invoices[invoice.invoice_id] = invoice
        
        return invoice
    
    def get_invoice(self, invoice_id: str) -> Optional[ContractInvoice]:
        """Get invoice by ID."""
        return self._invoices.get(invoice_id)
    
    def get_invoices_for_tenant(self, tenant_id: str) -> List[ContractInvoice]:
        """Get all invoices for a tenant."""
        return [inv for inv in self._invoices.values() if inv.tenant_id == tenant_id]
    
    def mark_invoice_paid(self, invoice_id: str) -> Optional[ContractInvoice]:
        """Mark an invoice as paid."""
        invoice = self._invoices.get(invoice_id)
        if not invoice:
            return None
        
        invoice.status = "paid"
        invoice.paid_at = datetime.now(timezone.utc)
        
        return invoice
    
    def calculate_overage(
        self,
        contract_id: str,
        current_usage: int
    ) -> Decimal:
        """
        Calculate overage charges.
        
        Args:
            contract_id: Contract identifier
            current_usage: Current usage count
            
        Returns:
            Overage amount
        """
        contract = self._contracts.get(contract_id)
        if not contract or contract.overage_rate == Decimal("0.00"):
            return Decimal("0.00")
        
        if current_usage <= contract.seats_included:
            return Decimal("0.00")
        
        overage_seats = current_usage - contract.seats_included
        return Decimal(str(overage_seats)) * contract.overage_rate


# Global service instance
_enterprise_billing_service: Optional[EnterpriseBillingService] = None


def get_enterprise_billing_service() -> EnterpriseBillingService:
    """Get the enterprise billing service instance."""
    global _enterprise_billing_service
    if _enterprise_billing_service is None:
        _enterprise_billing_service = EnterpriseBillingService()
    return _enterprise_billing_service
