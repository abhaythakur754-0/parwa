"""
Billing Calculator for SaaS Advanced Module.

Provides billing calculation including:
- Tiered pricing calculation
- Volume discount application
- Overage rate calculation
- Proration for mid-cycle changes
- Tax calculation per jurisdiction
- Multi-currency support
- Invoice preview generation
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class BillingTier(str, Enum):
    """Billing tier levels."""
    TIER_1 = "tier_1"  # 0-1000 units
    TIER_2 = "tier_2"  # 1001-5000 units
    TIER_3 = "tier_3"  # 5001-20000 units
    TIER_4 = "tier_4"  # 20001+ units


class Currency(str, Enum):
    """Supported currencies."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"
    AUD = "AUD"


class TaxType(str, Enum):
    """Tax types."""
    VAT = "vat"
    SALES_TAX = "sales_tax"
    GST = "gst"
    NONE = "none"


@dataclass
class BillingLineItem:
    """Represents a billing line item."""
    id: UUID = field(default_factory=uuid4)
    description: str = ""
    quantity: float = 0.0
    unit_price: float = 0.0
    subtotal: float = 0.0
    discount: float = 0.0
    tax: float = 0.0
    total: float = 0.0

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
        }


@dataclass
class BillingSummary:
    """Complete billing summary."""
    id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))
    currency: Currency = Currency.USD
    line_items: List[BillingLineItem] = field(default_factory=list)
    subtotal: float = 0.0
    discounts: float = 0.0
    tax: float = 0.0
    total: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "client_id": self.client_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "currency": self.currency.value,
            "line_items": [item.to_dict() for item in self.line_items],
            "subtotal": self.subtotal,
            "discounts": self.discounts,
            "tax": self.tax,
            "total": self.total,
        }


# Tier pricing per unit (USD)
TIERED_RATES = {
    "api_calls": {
        BillingTier.TIER_1: 0.001,  # $0.001 per call
        BillingTier.TIER_2: 0.0008,
        BillingTier.TIER_3: 0.0005,
        BillingTier.TIER_4: 0.0003,
    },
    "ai_interactions": {
        BillingTier.TIER_1: 0.02,  # $0.02 per interaction
        BillingTier.TIER_2: 0.015,
        BillingTier.TIER_3: 0.01,
        BillingTier.TIER_4: 0.007,
    },
    "voice_minutes": {
        BillingTier.TIER_1: 0.10,  # $0.10 per minute
        BillingTier.TIER_2: 0.08,
        BillingTier.TIER_3: 0.05,
        BillingTier.TIER_4: 0.03,
    },
    "storage_gb": {
        BillingTier.TIER_1: 0.50,  # $0.50 per GB
        BillingTier.TIER_2: 0.40,
        BillingTier.TIER_3: 0.30,
        BillingTier.TIER_4: 0.20,
    },
    "sms_messages": {
        BillingTier.TIER_1: 0.05,  # $0.05 per SMS
        BillingTier.TIER_2: 0.04,
        BillingTier.TIER_3: 0.03,
        BillingTier.TIER_4: 0.02,
    },
}

# Volume discounts
VOLUME_DISCOUNTS = [
    {"min_amount": 100, "discount_percent": 5},
    {"min_amount": 500, "discount_percent": 10},
    {"min_amount": 1000, "discount_percent": 15},
    {"min_amount": 2500, "discount_percent": 20},
    {"min_amount": 5000, "discount_percent": 25},
]

# Tax rates by region
TAX_RATES = {
    "US": {"type": TaxType.SALES_TAX, "rate": 0.0},  # Varies by state
    "US_CA": {"type": TaxType.SALES_TAX, "rate": 0.0725},
    "US_NY": {"type": TaxType.SALES_TAX, "rate": 0.08},
    "US_TX": {"type": TaxType.SALES_TAX, "rate": 0.0625},
    "EU": {"type": TaxType.VAT, "rate": 0.20},
    "EU_DE": {"type": TaxType.VAT, "rate": 0.19},
    "EU_FR": {"type": TaxType.VAT, "rate": 0.20},
    "EU_UK": {"type": TaxType.VAT, "rate": 0.20},
    "AU": {"type": TaxType.GST, "rate": 0.10},
    "CA": {"type": TaxType.GST, "rate": 0.05},
    "NONE": {"type": TaxType.NONE, "rate": 0.0},
}

# Exchange rates (mock rates - would use live API in production)
EXCHANGE_RATES = {
    Currency.USD: 1.0,
    Currency.EUR: 0.92,
    Currency.GBP: 0.79,
    Currency.CAD: 1.36,
    Currency.AUD: 1.53,
}


class BillingCalculator:
    """
    Calculates billing for SaaS subscriptions.

    Features:
    - Tiered pricing calculation
    - Volume discounts
    - Overage rates
    - Proration
    - Tax calculation
    - Multi-currency support
    """

    def __init__(
        self,
        client_id: str = "",
        currency: Currency = Currency.USD,
        region: str = "US"
    ):
        """
        Initialize billing calculator.

        Args:
            client_id: Client identifier
            currency: Billing currency
            region: Tax region
        """
        self.client_id = client_id
        self.currency = currency
        self.region = region

    async def calculate_tiered_pricing(
        self,
        usage_type: str,
        quantity: float
    ) -> Dict[str, Any]:
        """
        Calculate tiered pricing for usage.

        Args:
            usage_type: Type of usage (api_calls, ai_interactions, etc.)
            quantity: Total usage quantity

        Returns:
            Dict with pricing breakdown
        """
        rates = TIERED_RATES.get(usage_type, {})
        if not rates:
            return {
                "usage_type": usage_type,
                "quantity": quantity,
                "total": 0.0,
                "breakdown": [],
            }

        # Determine billing tier
        if quantity <= 1000:
            tier = BillingTier.TIER_1
        elif quantity <= 5000:
            tier = BillingTier.TIER_2
        elif quantity <= 20000:
            tier = BillingTier.TIER_3
        else:
            tier = BillingTier.TIER_4

        # Calculate tiered cost
        breakdown = []
        remaining = quantity
        total = 0.0

        tier_boundaries = [
            (BillingTier.TIER_1, 1000),
            (BillingTier.TIER_2, 4000),
            (BillingTier.TIER_3, 15000),
            (BillingTier.TIER_4, float('inf')),
        ]

        prev_boundary = 0
        for current_tier, boundary in tier_boundaries:
            if remaining <= 0:
                break

            tier_quantity = min(remaining, boundary - prev_boundary)
            if current_tier == BillingTier.TIER_4:
                tier_quantity = remaining

            tier_rate = rates.get(current_tier, 0)
            tier_cost = tier_quantity * tier_rate

            if tier_quantity > 0:
                breakdown.append({
                    "tier": current_tier.value,
                    "quantity": tier_quantity,
                    "rate": tier_rate,
                    "cost": round(tier_cost, 2),
                })

            total += tier_cost
            remaining -= tier_quantity
            prev_boundary = boundary

        return {
            "usage_type": usage_type,
            "quantity": quantity,
            "tier": tier.value,
            "total": round(total, 2),
            "breakdown": breakdown,
        }

    async def apply_volume_discount(
        self,
        subtotal: float
    ) -> Dict[str, Any]:
        """
        Apply volume discount to subtotal.

        Args:
            subtotal: Pre-discount amount

        Returns:
            Dict with discount details
        """
        discount_percent = 0
        discount_tier = None

        for tier in reversed(VOLUME_DISCOUNTS):
            if subtotal >= tier["min_amount"]:
                discount_percent = tier["discount_percent"]
                discount_tier = tier
                break

        discount_amount = subtotal * (discount_percent / 100)

        return {
            "subtotal": subtotal,
            "discount_percent": discount_percent,
            "discount_amount": round(discount_amount, 2),
            "final_amount": round(subtotal - discount_amount, 2),
            "tier": discount_tier,
        }

    async def calculate_overage(
        self,
        usage_type: str,
        included: float,
        actual: float,
        overage_rate: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate overage charges.

        Args:
            usage_type: Type of usage
            included: Included amount in plan
            actual: Actual usage
            overage_rate: Optional custom overage rate

        Returns:
            Dict with overage details
        """
        if actual <= included:
            return {
                "usage_type": usage_type,
                "included": included,
                "actual": actual,
                "overage": 0,
                "overage_cost": 0.0,
            }

        overage = actual - included

        # Get default overage rate (150% of tier 1 rate)
        if overage_rate is None:
            tier1_rate = TIERED_RATES.get(usage_type, {}).get(BillingTier.TIER_1, 0.01)
            overage_rate = tier1_rate * 1.5

        overage_cost = overage * overage_rate

        return {
            "usage_type": usage_type,
            "included": included,
            "actual": actual,
            "overage": overage,
            "overage_rate": overage_rate,
            "overage_cost": round(overage_cost, 2),
        }

    async def calculate_proration(
        self,
        monthly_amount: float,
        days_in_period: int,
        days_used: int
    ) -> Dict[str, Any]:
        """
        Calculate proration for mid-cycle changes.

        Args:
            monthly_amount: Full monthly amount
            days_in_period: Total days in billing period
            days_used: Days already used

        Returns:
            Dict with proration details
        """
        daily_rate = monthly_amount / days_in_period
        used_amount = daily_rate * days_used
        remaining_amount = daily_rate * (days_in_period - days_used)

        return {
            "monthly_amount": monthly_amount,
            "daily_rate": round(daily_rate, 4),
            "days_in_period": days_in_period,
            "days_used": days_used,
            "days_remaining": days_in_period - days_used,
            "used_amount": round(used_amount, 2),
            "remaining_amount": round(remaining_amount, 2),
            "credit": round(remaining_amount, 2),  # Credit for unused portion
        }

    async def calculate_tax(
        self,
        subtotal: float,
        region: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate tax for a region.

        Args:
            subtotal: Pre-tax amount
            region: Tax region (uses instance region if not provided)

        Returns:
            Dict with tax details
        """
        region = region or self.region
        tax_info = TAX_RATES.get(region, TAX_RATES["NONE"])

        tax_type = tax_info["type"]
        tax_rate = tax_info["rate"]
        tax_amount = subtotal * tax_rate

        return {
            "region": region,
            "tax_type": tax_type.value,
            "tax_rate": tax_rate,
            "tax_rate_percent": round(tax_rate * 100, 2),
            "tax_amount": round(tax_amount, 2),
            "total_with_tax": round(subtotal + tax_amount, 2),
        }

    async def convert_currency(
        self,
        amount: float,
        from_currency: Currency,
        to_currency: Currency
    ) -> Dict[str, Any]:
        """
        Convert amount between currencies.

        Args:
            amount: Amount to convert
            from_currency: Source currency
            to_currency: Target currency

        Returns:
            Dict with conversion details
        """
        # Convert to USD first, then to target
        usd_amount = amount / EXCHANGE_RATES.get(from_currency, 1.0)
        target_amount = usd_amount * EXCHANGE_RATES.get(to_currency, 1.0)

        return {
            "original_amount": amount,
            "original_currency": from_currency.value,
            "converted_amount": round(target_amount, 2),
            "converted_currency": to_currency.value,
            "exchange_rate": round(
                EXCHANGE_RATES.get(to_currency, 1.0) / EXCHANGE_RATES.get(from_currency, 1.0),
                4
            ),
        }

    async def generate_invoice_preview(
        self,
        subscription_tier: str,
        billing_cycle: str,
        usage_data: Dict[str, float],
        discounts: Optional[List[str]] = None,
        region: Optional[str] = None
    ) -> BillingSummary:
        """
        Generate a complete invoice preview.

        Args:
            subscription_tier: Subscription tier (mini, parwa, parwa_high)
            billing_cycle: Billing cycle (monthly, annual)
            usage_data: Usage quantities by type
            discounts: Optional discount codes
            region: Tax region

        Returns:
            BillingSummary with complete invoice
        """
        now = datetime.now(timezone.utc)
        period_end = now + timedelta(days=30 if billing_cycle == "monthly" else 365)

        # Base subscription cost
        base_prices = {
            "mini": {"monthly": 49, "annual": 470},
            "parwa": {"monthly": 149, "annual": 1430},
            "parwa_high": {"monthly": 499, "annual": 4790},
        }

        base_price = base_prices.get(subscription_tier, base_prices["mini"]).get(billing_cycle, 49)

        line_items = []

        # Subscription line item
        line_items.append(BillingLineItem(
            description=f"{subscription_tier.upper()} Subscription ({billing_cycle})",
            quantity=1,
            unit_price=base_price,
            subtotal=base_price,
            total=base_price,
        ))

        # Usage line items
        for usage_type, quantity in usage_data.items():
            usage_pricing = await self.calculate_tiered_pricing(usage_type, quantity)
            if usage_pricing["total"] > 0:
                line_items.append(BillingLineItem(
                    description=f"Usage: {usage_type}",
                    quantity=quantity,
                    unit_price=usage_pricing["total"] / quantity if quantity > 0 else 0,
                    subtotal=usage_pricing["total"],
                    total=usage_pricing["total"],
                ))

        # Calculate subtotal
        subtotal = sum(item.subtotal for item in line_items)

        # Apply volume discount
        discount_result = await self.apply_volume_discount(subtotal)
        discount_amount = discount_result["discount_amount"]

        # Apply additional discount codes
        if discounts:
            for code in discounts:
                if code == "LAUNCH20":
                    code_discount = subtotal * 0.20
                    discount_amount += code_discount
                elif code == "FLAT50":
                    discount_amount += 50

        # Calculate tax
        tax_result = await self.calculate_tax(subtotal - discount_amount, region)

        # Calculate total
        total = subtotal - discount_amount + tax_result["tax_amount"]

        return BillingSummary(
            client_id=self.client_id,
            period_start=now,
            period_end=period_end,
            currency=self.currency,
            line_items=line_items,
            subtotal=round(subtotal, 2),
            discounts=round(discount_amount, 2),
            tax=round(tax_result["tax_amount"], 2),
            total=round(total, 2),
        )

    async def calculate_mrr_projection(
        self,
        current_mrr: float,
        growth_rate: float,
        churn_rate: float,
        months: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Calculate MRR projection over time.

        Args:
            current_mrr: Current monthly recurring revenue
            growth_rate: Monthly growth rate (decimal)
            churn_rate: Monthly churn rate (decimal)
            months: Number of months to project

        Returns:
            List of monthly projections
        """
        projections = []
        mrr = current_mrr

        for month in range(1, months + 1):
            new_mrr = mrr * (1 + growth_rate - churn_rate)
            growth = mrr * growth_rate
            churn = mrr * churn_rate

            projections.append({
                "month": month,
                "starting_mrr": round(mrr, 2),
                "growth_addition": round(growth, 2),
                "churn_loss": round(churn, 2),
                "ending_mrr": round(new_mrr, 2),
                "net_change": round(new_mrr - mrr, 2),
            })

            mrr = new_mrr

        return projections


# Export for testing
__all__ = [
    "BillingCalculator",
    "BillingLineItem",
    "BillingSummary",
    "BillingTier",
    "Currency",
    "TaxType",
    "TIERED_RATES",
    "VOLUME_DISCOUNTS",
    "TAX_RATES",
    "EXCHANGE_RATES",
]
