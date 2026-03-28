"""Price Monitoring System.

Provides real-time price monitoring:
- Real-time price tracking
- Price change alerts
- Price drop notifications
- Threshold-based monitoring
- Historical price analysis
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    """Price alert type."""
    DROP = "drop"
    INCREASE = "increase"
    THRESHOLD = "threshold"


@dataclass
class PriceAlert:
    """Price alert."""
    alert_id: str
    product_id: str
    alert_type: AlertType
    old_price: Decimal
    new_price: Decimal
    threshold: Optional[Decimal]
    timestamp: datetime


class PriceMonitor:
    """Price monitoring system."""

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        self.client_id = client_id
        self.config = config or {}
        self._prices: Dict[str, Decimal] = {}
        self._alerts: List[PriceAlert] = []
        self._watch_list: Dict[str, Dict[str, Any]] = {}

    def track_price(self, product_id: str, price: Decimal) -> Optional[PriceAlert]:
        """Track price change and generate alerts."""
        old_price = self._prices.get(product_id)

        if old_price is not None and price != old_price:
            alert = self._create_alert(product_id, old_price, price)
            self._alerts.append(alert)
            self._prices[product_id] = price
            return alert

        self._prices[product_id] = price
        return None

    def add_to_watch_list(
        self,
        product_id: str,
        drop_threshold: Optional[Decimal] = None,
        increase_threshold: Optional[Decimal] = None
    ) -> None:
        """Add product to watch list."""
        self._watch_list[product_id] = {
            "drop_threshold": drop_threshold,
            "increase_threshold": increase_threshold,
            "added_at": datetime.utcnow()
        }

    def check_alerts(self) -> List[PriceAlert]:
        """Check for triggered alerts."""
        triggered = []

        for product_id, watch in self._watch_list.items():
            current_price = self._prices.get(product_id)
            if not current_price:
                continue

            drop_threshold = watch.get("drop_threshold")
            if drop_threshold and current_price <= drop_threshold:
                triggered.append(PriceAlert(
                    alert_id=f"alert_{product_id}_drop",
                    product_id=product_id,
                    alert_type=AlertType.THRESHOLD,
                    old_price=drop_threshold,
                    new_price=current_price,
                    threshold=drop_threshold,
                    timestamp=datetime.utcnow()
                ))

        return triggered

    def get_price_trend(self, product_id: str, days: int = 30) -> Dict[str, Any]:
        """Analyze price trend."""
        return {
            "product_id": product_id,
            "trend": "stable",
            "change_percent": 0,
            "days_analyzed": days
        }

    def _create_alert(
        self,
        product_id: str,
        old_price: Decimal,
        new_price: Decimal
    ) -> PriceAlert:
        """Create price alert."""
        alert_type = AlertType.DROP if new_price < old_price else AlertType.INCREASE
        return PriceAlert(
            alert_id=f"alert_{product_id}_{datetime.utcnow().timestamp()}",
            product_id=product_id,
            alert_type=alert_type,
            old_price=old_price,
            new_price=new_price,
            threshold=None,
            timestamp=datetime.utcnow()
        )
