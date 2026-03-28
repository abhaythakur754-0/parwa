"""Customer Behavior Analyzer.

Analyzes customer behavior patterns:
- Purchase history analysis
- Browsing pattern detection
- Customer segment identification
- Seasonal preference tracking
- Return rate analysis
- Lifetime value calculation
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import logging
import statistics

logger = logging.getLogger(__name__)


class CustomerSegment(str, Enum):
    """Customer segment classification."""
    NEW = "new"
    OCCASIONAL = "occasional"
    REGULAR = "regular"
    VIP = "vip"
    AT_RISK = "at_risk"
    CHURNED = "churned"


class PurchaseFrequency(str, Enum):
    """Purchase frequency classification."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    RARELY = "rarely"


@dataclass
class PurchasePattern:
    """Purchase pattern analysis result."""
    total_orders: int
    total_spent: Decimal
    average_order_value: Decimal
    purchase_frequency: PurchaseFrequency
    preferred_categories: List[str]
    preferred_price_range: str  # 'budget', 'mid', 'premium'
    seasonal_peaks: List[str]  # months with highest activity


@dataclass
class BehaviorAnalysis:
    """Complete behavior analysis result."""
    customer_id: str
    segment: CustomerSegment
    lifetime_value: Decimal
    purchase_pattern: PurchasePattern
    browsing_interests: List[str]
    return_rate: float
    engagement_score: float
    churn_risk: float
    recommendations: List[str]


class BehaviorAnalyzer:
    """Customer behavior analysis engine."""

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        """Initialize behavior analyzer.

        Args:
            client_id: Client identifier for tenant isolation
            config: Optional configuration overrides
        """
        self.client_id = client_id
        self.config = config or {}
        self._customer_cache: Dict[str, Dict[str, Any]] = {}

    def analyze_customer(
        self,
        customer_id: str,
        include_history: bool = True
    ) -> BehaviorAnalysis:
        """Perform comprehensive behavior analysis.

        Args:
            customer_id: Customer identifier
            include_history: Whether to include historical data

        Returns:
            Complete behavior analysis
        """
        # Get customer data
        customer_data = self._get_customer_data(customer_id)

        # Calculate purchase pattern
        purchase_pattern = self._analyze_purchase_pattern(customer_data)

        # Determine segment
        segment = self._determine_segment(customer_data, purchase_pattern)

        # Calculate lifetime value
        ltv = self._calculate_ltv(customer_data, purchase_pattern)

        # Analyze browsing interests
        browsing_interests = self._analyze_browsing(customer_data)

        # Calculate return rate
        return_rate = self._calculate_return_rate(customer_data)

        # Calculate engagement score
        engagement_score = self._calculate_engagement(customer_data)

        # Calculate churn risk
        churn_risk = self._calculate_churn_risk(
            customer_data, segment, engagement_score
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            segment, purchase_pattern, browsing_interests
        )

        logger.info(
            "Behavior analysis completed",
            extra={
                "client_id": self.client_id,
                "customer_id": customer_id,
                "segment": segment.value,
                "ltv": float(ltv)
            }
        )

        return BehaviorAnalysis(
            customer_id=customer_id,
            segment=segment,
            lifetime_value=ltv,
            purchase_pattern=purchase_pattern,
            browsing_interests=browsing_interests,
            return_rate=return_rate,
            engagement_score=engagement_score,
            churn_risk=churn_risk,
            recommendations=recommendations
        )

    def identify_segment(self, customer_id: str) -> CustomerSegment:
        """Identify customer segment.

        Args:
            customer_id: Customer identifier

        Returns:
            Customer segment classification
        """
        customer_data = self._get_customer_data(customer_id)
        purchase_pattern = self._analyze_purchase_pattern(customer_data)
        return self._determine_segment(customer_data, purchase_pattern)

    def calculate_ltv(self, customer_id: str) -> Decimal:
        """Calculate customer lifetime value.

        Args:
            customer_id: Customer identifier

        Returns:
            Lifetime value in base currency
        """
        customer_data = self._get_customer_data(customer_id)
        purchase_pattern = self._analyze_purchase_pattern(customer_data)
        return self._calculate_ltv(customer_data, purchase_pattern)

    def get_purchase_history(
        self,
        customer_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get customer purchase history (no PII).

        Args:
            customer_id: Customer identifier
            limit: Maximum number of records

        Returns:
            List of purchase records (anonymized)
        """
        customer_data = self._get_customer_data(customer_id)
        orders = customer_data.get("orders", [])[:limit]

        # Return anonymized data
        return [
            {
                "order_id": order["id"],
                "category": order.get("category"),
                "total": order["total"],
                "date": order["date"],
                "items_count": order.get("items_count", 1)
            }
            for order in orders
        ]

    def analyze_trends(
        self,
        customer_ids: List[str]
    ) -> Dict[str, Any]:
        """Analyze trends across multiple customers.

        Args:
            customer_ids: List of customer identifiers

        Returns:
            Aggregate trend analysis
        """
        segments = {}
        total_ltv = Decimal("0")
        avg_engagement = []

        for cid in customer_ids:
            analysis = self.analyze_customer(cid, include_history=False)

            segment = analysis.segment.value
            segments[segment] = segments.get(segment, 0) + 1
            total_ltv += analysis.lifetime_value
            avg_engagement.append(analysis.engagement_score)

        return {
            "total_customers": len(customer_ids),
            "segment_distribution": segments,
            "average_ltv": float(total_ltv / len(customer_ids)) if customer_ids else 0,
            "average_engagement": statistics.mean(avg_engagement) if avg_engagement else 0
        }

    def _analyze_purchase_pattern(
        self,
        customer_data: Dict[str, Any]
    ) -> PurchasePattern:
        """Analyze purchase patterns."""
        orders = customer_data.get("orders", [])

        if not orders:
            return PurchasePattern(
                total_orders=0,
                total_spent=Decimal("0"),
                average_order_value=Decimal("0"),
                purchase_frequency=PurchaseFrequency.RARELY,
                preferred_categories=[],
                preferred_price_range="mid",
                seasonal_peaks=[]
            )

        # Calculate totals
        totals = [Decimal(str(o.get("total", 0))) for o in orders]
        total_spent = sum(totals)
        avg_order = total_spent / len(orders)

        # Determine frequency
        if len(orders) >= 12:  # Monthly or more
            frequency = PurchaseFrequency.MONTHLY
        elif len(orders) >= 4:
            frequency = PurchaseFrequency.QUARTERLY
        else:
            frequency = PurchaseFrequency.RARELY

        # Category preferences
        categories = [o.get("category") for o in orders if o.get("category")]
        category_counts = {}
        for cat in categories:
            category_counts[cat] = category_counts.get(cat, 0) + 1
        preferred_categories = sorted(
            category_counts.keys(),
            key=lambda x: category_counts[x],
            reverse=True
        )[:3]

        # Price range preference
        avg_total = float(avg_order)
        if avg_total < 50:
            price_range = "budget"
        elif avg_total < 150:
            price_range = "mid"
        else:
            price_range = "premium"

        # Seasonal peaks
        months = [o.get("date", "")[:7] for o in orders if o.get("date")]
        month_counts = {}
        for m in months:
            month_counts[m] = month_counts.get(m, 0) + 1
        seasonal_peaks = sorted(
            month_counts.keys(),
            key=lambda x: month_counts[x],
            reverse=True
        )[:3]

        return PurchasePattern(
            total_orders=len(orders),
            total_spent=total_spent,
            average_order_value=avg_order,
            purchase_frequency=frequency,
            preferred_categories=preferred_categories,
            preferred_price_range=price_range,
            seasonal_peaks=seasonal_peaks
        )

    def _determine_segment(
        self,
        customer_data: Dict[str, Any],
        pattern: PurchasePattern
    ) -> CustomerSegment:
        """Determine customer segment."""
        days_since_last = customer_data.get("days_since_last_order", 0)
        total_orders = pattern.total_orders

        # Churned: no orders in 365+ days
        if days_since_last > 365:
            return CustomerSegment.CHURNED

        # At risk: no orders in 180+ days
        if days_since_last > 180:
            return CustomerSegment.AT_RISK

        # New: first order within 30 days
        if total_orders == 1 and days_since_last < 30:
            return CustomerSegment.NEW

        # VIP: 10+ orders, regular purchaser
        if total_orders >= 10 and pattern.purchase_frequency in [
            PurchaseFrequency.WEEKLY, PurchaseFrequency.MONTHLY
        ]:
            return CustomerSegment.VIP

        # Regular: 5+ orders
        if total_orders >= 5:
            return CustomerSegment.REGULAR

        # Occasional: 2-4 orders
        if total_orders >= 2:
            return CustomerSegment.OCCASIONAL

        return CustomerSegment.NEW

    def _calculate_ltv(
        self,
        customer_data: Dict[str, Any],
        pattern: PurchasePattern
    ) -> Decimal:
        """Calculate lifetime value with prediction."""
        # Base LTV is historical spend
        historical_ltv = pattern.total_spent

        # Predict future value based on segment
        segment = self._determine_segment(customer_data, pattern)

        if segment == CustomerSegment.VIP:
            # VIPs typically spend 2x their historical average
            future_multiplier = 2.0
        elif segment == CustomerSegment.REGULAR:
            future_multiplier = 1.5
        elif segment == CustomerSegment.OCCASIONAL:
            future_multiplier = 1.2
        else:
            future_multiplier = 1.0

        predicted_ltv = historical_ltv * Decimal(str(future_multiplier))

        return predicted_ltv

    def _analyze_browsing(
        self,
        customer_data: Dict[str, Any]
    ) -> List[str]:
        """Analyze browsing interests."""
        return customer_data.get("browsing_categories", [])

    def _calculate_return_rate(
        self,
        customer_data: Dict[str, Any]
    ) -> float:
        """Calculate return rate percentage."""
        orders = customer_data.get("orders", [])
        returns = customer_data.get("returns", 0)

        if not orders:
            return 0.0

        return min(returns / len(orders), 1.0)

    def _calculate_engagement(
        self,
        customer_data: Dict[str, Any]
    ) -> float:
        """Calculate engagement score (0-1)."""
        orders = customer_data.get("orders", [])
        browsing_events = customer_data.get("browsing_events", 0)
        wishlist_items = customer_data.get("wishlist_items", 0)

        # Order engagement
        order_score = min(len(orders) / 20, 1.0) * 0.5

        # Browsing engagement
        browsing_score = min(browsing_events / 100, 1.0) * 0.3

        # Wishlist engagement
        wishlist_score = min(wishlist_items / 10, 1.0) * 0.2

        return order_score + browsing_score + wishlist_score

    def _calculate_churn_risk(
        self,
        customer_data: Dict[str, Any],
        segment: CustomerSegment,
        engagement: float
    ) -> float:
        """Calculate churn risk score (0-1)."""
        if segment == CustomerSegment.CHURNED:
            return 1.0
        if segment == CustomerSegment.AT_RISK:
            return 0.75

        days_since_last = customer_data.get("days_since_last_order", 0)

        # Time-based risk
        time_risk = min(days_since_last / 180, 1.0)

        # Engagement-based risk (inverse)
        engagement_risk = 1.0 - engagement

        # Combined risk
        combined = (time_risk * 0.6) + (engagement_risk * 0.4)

        return min(combined, 1.0)

    def _generate_recommendations(
        self,
        segment: CustomerSegment,
        pattern: PurchasePattern,
        browsing_interests: List[str]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        if segment == CustomerSegment.NEW:
            recommendations.append("Send welcome series with first-purchase discount")
        elif segment == CustomerSegment.AT_RISK:
            recommendations.append("Send win-back campaign with exclusive offer")
        elif segment == CustomerSegment.VIP:
            recommendations.append("Offer VIP perks and early access to new products")

        if pattern.preferred_categories:
            recommendations.append(
                f"Promote products in {pattern.preferred_categories[0]} category"
            )

        if browsing_interests:
            recommendations.append(
                f"Send personalized recommendations for {browsing_interests[0]}"
            )

        return recommendations

    def _get_customer_data(self, customer_id: str) -> Dict[str, Any]:
        """Get customer data (mock implementation, no PII)."""
        if customer_id in self._customer_cache:
            return self._customer_cache[customer_id]

        # Mock customer data
        data = {
            "orders": [
                {"id": "ord_001", "total": 149.99, "category": "electronics", "date": "2026-01-15", "items_count": 2},
                {"id": "ord_002", "total": 79.99, "category": "clothing", "date": "2026-02-10", "items_count": 1},
                {"id": "ord_003", "total": 299.99, "category": "electronics", "date": "2026-03-05", "items_count": 1},
            ],
            "days_since_last_order": 21,
            "browsing_categories": ["electronics", "home"],
            "browsing_events": 45,
            "wishlist_items": 3,
            "returns": 1
        }

        self._customer_cache[customer_id] = data
        return data
