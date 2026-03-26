"""Competitor Price Tracking.

Provides competitor monitoring:
- Competitor price monitoring
- Market positioning analysis
- Price gap analysis
- Alert on significant changes
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class CompetitorPrice:
    """Competitor price data."""
    competitor_name: str
    product_id: str
    price: Decimal
    currency: str
    last_updated: datetime


class CompetitorTracker:
    """Competitor price tracking system."""

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        self.client_id = client_id
        self.config = config or {}
        self._competitor_prices: Dict[str, List[CompetitorPrice]] = {}

    def track_competitor(
        self,
        competitor_name: str,
        product_id: str,
        price: Decimal
    ) -> None:
        """Track competitor price."""
        key = f"{competitor_name}:{product_id}"
        price_data = CompetitorPrice(
            competitor_name=competitor_name,
            product_id=product_id,
            price=price,
            currency="USD",
            last_updated=datetime.utcnow()
        )

        if key not in self._competitor_prices:
            self._competitor_prices[key] = []
        self._competitor_prices[key].append(price_data)

    def analyze_price_gap(
        self,
        product_id: str,
        our_price: Decimal
    ) -> Dict[str, Any]:
        """Analyze price gap vs competitors."""
        gaps = []

        for key, prices in self._competitor_prices.items():
            if product_id in key and prices:
                latest = prices[-1]
                gap = our_price - latest.price
                gap_percent = float(gap / latest.price * 100) if latest.price else 0
                gaps.append({
                    "competitor": latest.competitor_name,
                    "their_price": float(latest.price),
                    "gap": float(gap),
                    "gap_percent": gap_percent,
                    "position": "higher" if gap > 0 else "lower"
                })

        return {
            "product_id": product_id,
            "our_price": float(our_price),
            "competitor_gaps": gaps,
            "average_gap_percent": sum(g["gap_percent"] for g in gaps) / len(gaps) if gaps else 0
        }

    def get_market_position(
        self,
        product_id: str,
        our_price: Decimal
    ) -> str:
        """Get market positioning."""
        analysis = self.analyze_price_gap(product_id, our_price)
        avg_gap = analysis["average_gap_percent"]

        if avg_gap > 10:
            return "premium"
        elif avg_gap > 0:
            return "above_average"
        elif avg_gap > -10:
            return "competitive"
        else:
            return "budget"
