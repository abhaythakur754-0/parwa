"""Order Tracking System.

Provides real-time order tracking:
- Real-time order status lookup
- Multi-carrier tracking support
- Order history aggregation
- Tracking number validation
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"


@dataclass
class TrackingEvent:
    """Tracking event."""
    timestamp: datetime
    status: str
    location: str
    description: str


@dataclass
class OrderInfo:
    """Order information."""
    order_id: str
    customer_id: str
    status: OrderStatus
    tracking_number: Optional[str]
    carrier: Optional[str]
    items: List[Dict[str, Any]]
    total: Decimal
    created_at: datetime
    estimated_delivery: Optional[datetime] = None


class OrderTracking:
    """Order tracking system."""

    CARRIER_PATTERNS = {
        "UPS": ["1Z"],
        "FedEx": ["4", "6", "9"],
        "USPS": ["94", "95", "42"],
        "DHL": ["JD", "JJD"]
    }

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        self.client_id = client_id
        self.config = config or {}
        self._orders: Dict[str, OrderInfo] = {}
        self._tracking_events: Dict[str, List[TrackingEvent]] = {}

    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order status."""
        order = self._orders.get(order_id)
        if not order:
            return None

        return {
            "order_id": order.order_id,
            "status": order.status.value,
            "tracking_number": order.tracking_number,
            "carrier": order.carrier,
            "estimated_delivery": order.estimated_delivery.isoformat() if order.estimated_delivery else None,
            "items_count": len(order.items),
            "total": float(order.total)
        }

    def get_tracking_events(self, tracking_number: str) -> List[Dict[str, Any]]:
        """Get tracking events for tracking number."""
        events = self._tracking_events.get(tracking_number, [])
        return [
            {
                "timestamp": e.timestamp.isoformat(),
                "status": e.status,
                "location": e.location,
                "description": e.description
            }
            for e in events
        ]

    def validate_tracking_number(self, tracking_number: str) -> Dict[str, Any]:
        """Validate tracking number format."""
        carrier = self.detect_carrier(tracking_number)
        return {
            "tracking_number": tracking_number,
            "valid": carrier is not None,
            "carrier": carrier
        }

    def detect_carrier(self, tracking_number: str) -> Optional[str]:
        """Detect carrier from tracking number."""
        for carrier, prefixes in self.CARRIER_PATTERNS.items():
            for prefix in prefixes:
                if tracking_number.startswith(prefix):
                    return carrier
        return None

    def get_order_history(
        self,
        customer_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get customer order history."""
        orders = [
            o for o in self._orders.values()
            if o.customer_id == customer_id
        ]

        return [
            {
                "order_id": o.order_id,
                "status": o.status.value,
                "total": float(o.total),
                "created_at": o.created_at.isoformat(),
                "items_count": len(o.items)
            }
            for o in sorted(orders, key=lambda x: x.created_at, reverse=True)
        ][:limit]

    def create_order(
        self,
        order_id: str,
        customer_id: str,
        items: List[Dict[str, Any]],
        total: Decimal
    ) -> OrderInfo:
        """Create new order."""
        order = OrderInfo(
            order_id=order_id,
            customer_id=customer_id,
            status=OrderStatus.PENDING,
            tracking_number=None,
            carrier=None,
            items=items,
            total=total,
            created_at=datetime.utcnow()
        )

        self._orders[order_id] = order
        return order

    def update_status(
        self,
        order_id: str,
        new_status: OrderStatus,
        tracking_number: Optional[str] = None
    ) -> Optional[OrderInfo]:
        """Update order status."""
        order = self._orders.get(order_id)
        if not order:
            return None

        order.status = new_status
        if tracking_number:
            order.tracking_number = tracking_number
            order.carrier = self.detect_carrier(tracking_number)

        return order
