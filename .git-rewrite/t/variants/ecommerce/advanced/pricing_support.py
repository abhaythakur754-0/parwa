"""Dynamic Pricing Support for E-commerce.

Provides dynamic pricing capabilities:
- Dynamic price inquiry handling
- Price history lookup
- Bulk pricing support
- Tiered pricing display
- Currency conversion
- Price match request handling
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PricingTier(str, Enum):
    """Pricing tier."""
    BUDGET = "budget"
    STANDARD = "standard"
    PREMIUM = "premium"


@dataclass
class PricePoint:
    """Price point in history."""
    price: Decimal
    currency: str
    timestamp: datetime
    source: str


@dataclass
class TierPrice:
    """Tiered pricing."""
    min_quantity: int
    max_quantity: Optional[int]
    unit_price: Decimal
    discount_percent: float


@dataclass
class PriceMatchRequest:
    """Price match request."""
    request_id: str
    product_id: str
    competitor_price: Decimal
    customer_id: str
    status: str = "pending"


class PricingSupport:
    """Dynamic pricing support engine."""

    # Supported currencies
    SUPPORTED_CURRENCIES = ["USD", "EUR", "GBP", "CAD", "AUD", "JPY"]

    # Exchange rates (mock)
    EXCHANGE_RATES = {
        "USD": 1.0,
        "EUR": 0.92,
        "GBP": 0.79,
        "CAD": 1.36,
        "AUD": 1.53,
        "JPY": 149.50
    }

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        """Initialize pricing support.

        Args:
            client_id: Client identifier
            config: Optional configuration
        """
        self.client_id = client_id
        self.config = config or {}
        self.default_currency = self.config.get("currency", "USD")
        self._price_history: Dict[str, List[PricePoint]] = {}
        self._price_match_requests: Dict[str, PriceMatchRequest] = {}

    def get_price(
        self,
        product_id: str,
        currency: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get product price with optional currency conversion.

        Args:
            product_id: Product identifier
            currency: Target currency

        Returns:
            Price information
        """
        base_price = self._get_base_price(product_id)
        target_currency = currency or self.default_currency

        # Convert currency
        converted_price = self._convert_currency(
            base_price, "USD", target_currency
        )

        return {
            "product_id": product_id,
            "base_price": float(base_price),
            "base_currency": "USD",
            "converted_price": float(converted_price),
            "currency": target_currency,
            "last_updated": datetime.utcnow().isoformat()
        }

    def get_price_history(
        self,
        product_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get price history for product.

        Args:
            product_id: Product identifier
            days: Number of days

        Returns:
            Price history
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        history = self._price_history.get(product_id, [])
        filtered = [
            {
                "price": float(p.price),
                "currency": p.currency,
                "timestamp": p.timestamp.isoformat(),
                "source": p.source
            }
            for p in history if p.timestamp >= cutoff
        ]

        return filtered

    def get_tiered_pricing(
        self,
        product_id: str,
        base_price: Decimal
    ) -> List[TierPrice]:
        """Get tiered pricing for bulk orders.

        Args:
            product_id: Product identifier
            base_price: Base unit price

        Returns:
            List of tier prices
        """
        return [
            TierPrice(
                min_quantity=1,
                max_quantity=9,
                unit_price=base_price,
                discount_percent=0
            ),
            TierPrice(
                min_quantity=10,
                max_quantity=49,
                unit_price=base_price * Decimal("0.95"),
                discount_percent=5
            ),
            TierPrice(
                min_quantity=50,
                max_quantity=99,
                unit_price=base_price * Decimal("0.90"),
                discount_percent=10
            ),
            TierPrice(
                min_quantity=100,
                max_quantity=None,
                unit_price=base_price * Decimal("0.85"),
                discount_percent=15
            )
        ]

    def calculate_bulk_price(
        self,
        product_id: str,
        quantity: int,
        base_price: Decimal
    ) -> Dict[str, Any]:
        """Calculate bulk price.

        Args:
            product_id: Product identifier
            quantity: Quantity
            base_price: Base price

        Returns:
            Bulk price calculation
        """
        tiers = self.get_tiered_pricing(product_id, base_price)

        applicable_tier = None
        for tier in tiers:
            if quantity >= tier.min_quantity:
                if tier.max_quantity is None or quantity <= tier.max_quantity:
                    applicable_tier = tier
                    break

        if not applicable_tier:
            applicable_tier = tiers[0]

        total = applicable_tier.unit_price * quantity
        savings = (base_price - applicable_tier.unit_price) * quantity

        return {
            "quantity": quantity,
            "unit_price": float(applicable_tier.unit_price),
            "total": float(total),
            "discount_percent": applicable_tier.discount_percent,
            "savings": float(savings),
            "tier": f"{applicable_tier.min_quantity}+"
        }

    def handle_price_match_request(
        self,
        product_id: str,
        competitor_price: Decimal,
        customer_id: str,
        competitor_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle price match request.

        Args:
            product_id: Product identifier
            competitor_price: Competitor's price
            customer_id: Customer identifier
            competitor_url: Optional competitor URL

        Returns:
            Price match request result
        """
        request_id = f"pm_{product_id}_{datetime.utcnow().timestamp()}"

        base_price = self._get_base_price(product_id)

        # Check if price match is possible
        match_eligible = competitor_price >= base_price * Decimal("0.85")

        request = PriceMatchRequest(
            request_id=request_id,
            product_id=product_id,
            competitor_price=competitor_price,
            customer_id=customer_id,
            status="approved" if match_eligible else "under_review"
        )

        self._price_match_requests[request_id] = request

        return {
            "request_id": request_id,
            "status": request.status,
            "original_price": float(base_price),
            "competitor_price": float(competitor_price),
            "match_eligible": match_eligible,
            "matched_price": float(competitor_price) if match_eligible else None
        }

    def _get_base_price(self, product_id: str) -> Decimal:
        """Get base price for product."""
        # Mock pricing
        return Decimal("99.99")

    def _convert_currency(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str
    ) -> Decimal:
        """Convert between currencies."""
        if from_currency == to_currency:
            return amount

        from_rate = Decimal(str(self.EXCHANGE_RATES.get(from_currency, 1.0)))
        to_rate = Decimal(str(self.EXCHANGE_RATES.get(to_currency, 1.0)))

        # Convert to USD first, then to target
        usd_amount = amount / from_rate
        return usd_amount * to_rate
