"""E-commerce Analytics Dashboard Backend.

Provides comprehensive analytics:
- Product performance metrics
- Conversion rate tracking
- Cart abandonment analysis
- Revenue attribution
- Customer journey mapping
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MetricPeriod(str, Enum):
    """Analytics period."""
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"


@dataclass
class MetricPoint:
    """Metric data point."""
    timestamp: datetime
    value: Decimal
    category: Optional[str] = None


@dataclass
class ProductMetrics:
    """Product performance metrics."""
    product_id: str
    product_name: str
    views: int
    add_to_cart: int
    purchases: int
    revenue: Decimal
    conversion_rate: float
    cart_abandonment_rate: float


@dataclass
class DashboardSummary:
    """Dashboard summary metrics."""
    total_revenue: Decimal
    total_orders: int
    total_customers: int
    average_order_value: Decimal
    conversion_rate: float
    cart_abandonment_rate: float
    top_products: List[ProductMetrics]


class EcommerceAnalytics:
    """E-commerce analytics engine."""

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        self.client_id = client_id
        self.config = config or {}
        self._events: List[Dict[str, Any]] = []
        self._metrics_cache: Dict[str, Any] = {}

    def track_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        timestamp: Optional[datetime] = None
    ) -> None:
        """Track analytics event (no PII)."""
        event = {
            "event_type": event_type,
            "data": data,
            "timestamp": (timestamp or datetime.utcnow()).isoformat(),
            "client_id": self.client_id
        }
        self._events.append(event)
        self._invalidate_cache()

    def get_dashboard_summary(
        self,
        period: MetricPeriod = MetricPeriod.WEEK
    ) -> DashboardSummary:
        """Get dashboard summary metrics."""
        events = self._filter_events_by_period(period)

        # Calculate metrics
        revenue = sum(
            Decimal(str(e["data"].get("revenue", 0)))
            for e in events if e["event_type"] == "purchase"
        )

        orders = len([e for e in events if e["event_type"] == "purchase"])
        customers = len(set(
            e["data"].get("customer_id")
            for e in events if e["data"].get("customer_id")
        ))

        aov = revenue / orders if orders > 0 else Decimal("0")

        # Conversion metrics
        views = len([e for e in events if e["event_type"] == "product_view"])
        purchases = len([e for e in events if e["event_type"] == "purchase"])
        conversion_rate = purchases / views if views > 0 else 0

        add_to_cart = len([e for e in events if e["event_type"] == "add_to_cart"])
        cart_abandonment = 1 - (purchases / add_to_cart) if add_to_cart > 0 else 0

        return DashboardSummary(
            total_revenue=revenue,
            total_orders=orders,
            total_customers=customers,
            average_order_value=aov,
            conversion_rate=conversion_rate,
            cart_abandonment_rate=cart_abandonment,
            top_products=self._get_top_products(events, limit=5)
        )

    def get_product_metrics(
        self,
        product_id: str,
        period: MetricPeriod = MetricPeriod.WEEK
    ) -> ProductMetrics:
        """Get metrics for specific product."""
        events = self._filter_events_by_period(period)
        product_events = [
            e for e in events
            if e["data"].get("product_id") == product_id
        ]

        views = len([e for e in product_events if e["event_type"] == "product_view"])
        add_to_cart = len([e for e in product_events if e["event_type"] == "add_to_cart"])
        purchases = len([e for e in product_events if e["event_type"] == "purchase"])

        revenue = sum(
            Decimal(str(e["data"].get("price", 0)))
            for e in product_events if e["event_type"] == "purchase"
        )

        conversion_rate = purchases / views if views > 0 else 0
        cart_abandonment = 1 - (purchases / add_to_cart) if add_to_cart > 0 else 0

        return ProductMetrics(
            product_id=product_id,
            product_name=f"Product {product_id}",
            views=views,
            add_to_cart=add_to_cart,
            purchases=purchases,
            revenue=revenue,
            conversion_rate=conversion_rate,
            cart_abandonment_rate=cart_abandonment
        )

    def get_conversion_funnel(
        self,
        period: MetricPeriod = MetricPeriod.WEEK
    ) -> Dict[str, Any]:
        """Get conversion funnel data."""
        events = self._filter_events_by_period(period)

        stages = {
            "views": len([e for e in events if e["event_type"] == "product_view"]),
            "add_to_cart": len([e for e in events if e["event_type"] == "add_to_cart"]),
            "checkout_start": len([e for e in events if e["event_type"] == "checkout_start"]),
            "purchase": len([e for e in events if e["event_type"] == "purchase"])
        }

        rates = {}
        prev_count = stages["views"]
        for stage, count in stages.items():
            rates[f"{stage}_rate"] = count / prev_count if prev_count > 0 else 0
            prev_count = count

        return {
            "stages": stages,
            "conversion_rates": rates,
            "overall_conversion": stages["purchase"] / stages["views"] if stages["views"] > 0 else 0
        }

    def get_revenue_trend(
        self,
        period: MetricPeriod = MetricPeriod.MONTH,
        granularity: str = "day"
    ) -> List[Dict[str, Any]]:
        """Get revenue trend over time."""
        events = self._filter_events_by_period(period)
        purchase_events = [e for e in events if e["event_type"] == "purchase"]

        # Group by granularity
        grouped: Dict[str, Decimal] = {}
        for event in purchase_events:
            ts = datetime.fromisoformat(event["timestamp"])
            if granularity == "day":
                key = ts.strftime("%Y-%m-%d")
            elif granularity == "week":
                key = ts.strftime("%Y-W%W")
            else:
                key = ts.strftime("%Y-%m")

            revenue = Decimal(str(event["data"].get("revenue", 0)))
            grouped[key] = grouped.get(key, Decimal("0")) + revenue

        return [
            {"date": k, "revenue": float(v)}
            for k, v in sorted(grouped.items())
        ]

    def get_cart_abandonment_analysis(
        self,
        period: MetricPeriod = MetricPeriod.WEEK
    ) -> Dict[str, Any]:
        """Analyze cart abandonment patterns."""
        events = self._filter_events_by_period(period)

        abandoned = len([e for e in events if e["event_type"] == "cart_abandoned"])
        recovered = len([e for e in events if e["event_type"] == "cart_recovered"])

        reasons = {}
        for e in events:
            if e["event_type"] == "cart_abandoned":
                reason = e["data"].get("reason", "unknown")
                reasons[reason] = reasons.get(reason, 0) + 1

        return {
            "total_abandoned": abandoned,
            "recovered": recovered,
            "recovery_rate": recovered / abandoned if abandoned > 0 else 0,
            "abandonment_reasons": reasons,
            "potential_revenue_lost": sum(
                Decimal(str(e["data"].get("cart_value", 0)))
                for e in events if e["event_type"] == "cart_abandoned"
            )
        }

    def get_recommendation_performance(
        self,
        period: MetricPeriod = MetricPeriod.WEEK
    ) -> Dict[str, Any]:
        """Track recommendation system effectiveness."""
        events = self._filter_events_by_period(period)

        rec_shown = len([e for e in events if e["event_type"] == "recommendation_shown"])
        rec_clicked = len([e for e in events if e["event_type"] == "recommendation_clicked"])
        rec_purchased = len([e for e in events if e["event_type"] == "recommendation_purchased"])

        return {
            "recommendations_shown": rec_shown,
            "click_rate": rec_clicked / rec_shown if rec_shown > 0 else 0,
            "purchase_rate": rec_purchased / rec_clicked if rec_clicked > 0 else 0,
            "revenue_from_recommendations": sum(
                Decimal(str(e["data"].get("revenue", 0)))
                for e in events if e["event_type"] == "recommendation_purchased"
            )
        }

    def _filter_events_by_period(
        self,
        period: MetricPeriod
    ) -> List[Dict[str, Any]]:
        """Filter events by time period."""
        now = datetime.utcnow()
        period_days = {
            MetricPeriod.DAY: 1,
            MetricPeriod.WEEK: 7,
            MetricPeriod.MONTH: 30,
            MetricPeriod.QUARTER: 90
        }

        cutoff = now - timedelta(days=period_days.get(period, 7))

        return [
            e for e in self._events
            if datetime.fromisoformat(e["timestamp"]) >= cutoff
        ]

    def _get_top_products(
        self,
        events: List[Dict[str, Any]],
        limit: int = 5
    ) -> List[ProductMetrics]:
        """Get top performing products."""
        product_data: Dict[str, Dict[str, Any]] = {}

        for event in events:
            product_id = event["data"].get("product_id")
            if not product_id:
                continue

            if product_id not in product_data:
                product_data[product_id] = {
                    "views": 0, "add_to_cart": 0, "purchases": 0, "revenue": Decimal("0")
                }

            if event["event_type"] == "product_view":
                product_data[product_id]["views"] += 1
            elif event["event_type"] == "add_to_cart":
                product_data[product_id]["add_to_cart"] += 1
            elif event["event_type"] == "purchase":
                product_data[product_id]["purchases"] += 1
                product_data[product_id]["revenue"] += Decimal(
                    str(event["data"].get("price", 0))
                )

        # Sort by revenue
        sorted_products = sorted(
            product_data.items(),
            key=lambda x: x[1]["revenue"],
            reverse=True
        )[:limit]

        return [
            ProductMetrics(
                product_id=pid,
                product_name=f"Product {pid}",
                views=data["views"],
                add_to_cart=data["add_to_cart"],
                purchases=data["purchases"],
                revenue=data["revenue"],
                conversion_rate=data["purchases"] / data["views"] if data["views"] > 0 else 0,
                cart_abandonment_rate=1 - (data["purchases"] / data["add_to_cart"]) if data["add_to_cart"] > 0 else 0
            )
            for pid, data in sorted_products
        ]

    def _invalidate_cache(self) -> None:
        """Invalidate metrics cache."""
        self._metrics_cache.clear()
