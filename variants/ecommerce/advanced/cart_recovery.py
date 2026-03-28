"""Cart Abandonment Recovery System.

Provides abandoned cart detection and recovery:
- Abandoned cart detection
- Multi-channel recovery (email, SMS, push)
- Personalized recovery messages
- Cart content analysis
- Recovery attempt tracking
- Customer opt-out handling
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CartStatus(str, Enum):
    """Cart status."""
    ACTIVE = "active"
    ABANDONED = "abandoned"
    RECOVERED = "recovered"
    EXPIRED = "expired"


class RecoveryChannel(str, Enum):
    """Recovery communication channel."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


@dataclass
class CartItem:
    """Cart item."""
    product_id: str
    product_name: str
    price: Decimal
    quantity: int
    image_url: Optional[str] = None


@dataclass
class AbandonedCart:
    """Abandoned cart representation."""
    cart_id: str
    customer_id: str
    items: List[CartItem]
    total_value: Decimal
    abandoned_at: datetime
    status: CartStatus
    recovery_attempts: int = 0
    last_recovery_attempt: Optional[datetime] = None


@dataclass
class RecoveryMessage:
    """Recovery message."""
    message_id: str
    cart_id: str
    channel: RecoveryChannel
    subject: str
    body: str
    scheduled_at: datetime
    sent_at: Optional[datetime] = None
    opened: bool = False
    clicked: bool = False
    converted: bool = False


class CartRecovery:
    """Cart abandonment recovery system."""

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        """Initialize cart recovery.

        Args:
            client_id: Client identifier for tenant isolation
            config: Optional configuration overrides
        """
        self.client_id = client_id
        self.config = config or {}
        self.abandonment_threshold_minutes = self.config.get(
            "abandonment_threshold_minutes", 30
        )
        self.max_recovery_attempts = self.config.get("max_recovery_attempts", 3)
        self._carts: Dict[str, AbandonedCart] = {}
        self._messages: Dict[str, RecoveryMessage] = {}

    def detect_abandoned_carts(
        self,
        threshold_minutes: Optional[int] = None
    ) -> List[AbandonedCart]:
        """Detect abandoned carts.

        Args:
            threshold_minutes: Minutes of inactivity to consider abandoned

        Returns:
            List of abandoned carts
        """
        threshold = threshold_minutes or self.abandonment_threshold_minutes
        cutoff = datetime.utcnow() - timedelta(minutes=threshold)

        abandoned = []
        for cart in self._get_all_carts():
            if (cart.status == CartStatus.ACTIVE and
                cart.abandoned_at < cutoff):
                # Mark as abandoned
                cart.status = CartStatus.ABANDONED
                abandoned.append(cart)

        logger.info(
            "Detected abandoned carts",
            extra={
                "client_id": self.client_id,
                "count": len(abandoned)
            }
        )

        return abandoned

    def generate_recovery_message(
        self,
        cart: AbandonedCart,
        channel: RecoveryChannel,
        template_vars: Optional[Dict[str, Any]] = None
    ) -> RecoveryMessage:
        """Generate recovery message for cart.

        Args:
            cart: Abandoned cart
            channel: Communication channel
            template_vars: Optional template variables

        Returns:
            Recovery message
        """
        template_vars = template_vars or {}

        # Generate message content
        items_summary = ", ".join([item.product_name for item in cart.items[:3]])
        if len(cart.items) > 3:
            items_summary += f" and {len(cart.items) - 3} more"

        if channel == RecoveryChannel.EMAIL:
            subject = f"Complete your purchase: {items_summary}"
            body = f"""
Hi there!

You left some items in your cart:
{items_summary}

Total: ${cart.total_value}

Complete your purchase before they're gone!

[Complete Purchase]
"""
        elif channel == RecoveryChannel.SMS:
            subject = "Cart Reminder"
            body = f"Complete your purchase! Items waiting: {items_summary}. Total: ${cart.total_value}"
        else:  # PUSH
            subject = "Don't forget your cart!"
            body = f"You have {len(cart.items)} items waiting. Total: ${cart.total_value}"

        message = RecoveryMessage(
            message_id=f"msg_{cart.cart_id}_{channel.value}_{datetime.utcnow().timestamp()}",
            cart_id=cart.cart_id,
            channel=channel,
            subject=subject,
            body=body,
            scheduled_at=datetime.utcnow()
        )

        self._messages[message.message_id] = message

        return message

    def send_recovery_message(
        self,
        message: RecoveryMessage,
        customer_contact: str
    ) -> bool:
        """Send recovery message.

        Args:
            message: Message to send
            customer_contact: Customer contact (email/phone)

        Returns:
            True if sent successfully
        """
        # In production, integrate with email/SMS clients
        message.sent_at = datetime.utcnow()

        # Update cart recovery attempts
        cart = self._carts.get(message.cart_id)
        if cart:
            cart.recovery_attempts += 1
            cart.last_recovery_attempt = datetime.utcnow()

        logger.info(
            "Sent recovery message",
            extra={
                "client_id": self.client_id,
                "message_id": message.message_id,
                "channel": message.channel.value
            }
        )

        return True

    def analyze_cart_content(self, cart: AbandonedCart) -> Dict[str, Any]:
        """Analyze cart content for recovery strategy.

        Args:
            cart: Cart to analyze

        Returns:
            Analysis result
        """
        total_items = len(cart.items)
        total_quantity = sum(item.quantity for item in cart.items)
        avg_item_price = cart.total_value / total_items if total_items > 0 else Decimal("0")

        # Categorize cart
        if cart.total_value > Decimal("200"):
            cart_type = "high_value"
        elif cart.total_value > Decimal("50"):
            cart_type = "medium_value"
        else:
            cart_type = "low_value"

        # Detect categories
        categories = set()
        for item in cart.items:
            # Extract category from product_id (mock)
            categories.add(item.product_id.split("_")[0] if "_" in item.product_id else "general")

        return {
            "cart_type": cart_type,
            "total_items": total_items,
            "total_quantity": total_quantity,
            "average_item_price": float(avg_item_price),
            "categories": list(categories),
            "recommended_channel": self._recommend_channel(cart),
            "recommended_discount": self._recommend_discount(cart)
        }

    def check_opt_out(self, customer_id: str) -> bool:
        """Check if customer has opted out.

        Args:
            customer_id: Customer identifier

        Returns:
            True if customer has opted out
        """
        # In production, check database/opt-out list
        return False

    def record_conversion(
        self,
        cart_id: str,
        order_value: Decimal
    ) -> bool:
        """Record successful cart recovery conversion.

        Args:
            cart_id: Cart identifier
            order_value: Final order value

        Returns:
            True if recorded successfully
        """
        cart = self._carts.get(cart_id)
        if cart:
            cart.status = CartStatus.RECOVERED
            logger.info(
                "Cart recovered",
                extra={
                    "client_id": self.client_id,
                    "cart_id": cart_id,
                    "order_value": float(order_value)
                }
            )
            return True
        return False

    def get_recovery_stats(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get recovery statistics.

        Args:
            days: Number of days to analyze

        Returns:
            Recovery statistics
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        total_abandoned = 0
        total_recovered = 0
        total_messages_sent = 0

        for cart in self._carts.values():
            if cart.abandoned_at >= cutoff:
                total_abandoned += 1
                if cart.status == CartStatus.RECOVERED:
                    total_recovered += 1

        for msg in self._messages.values():
            if msg.sent_at and msg.sent_at >= cutoff:
                total_messages_sent += 1

        recovery_rate = total_recovered / total_abandoned if total_abandoned > 0 else 0

        return {
            "period_days": days,
            "total_abandoned": total_abandoned,
            "total_recovered": total_recovered,
            "recovery_rate": recovery_rate,
            "total_messages_sent": total_messages_sent
        }

    def _recommend_channel(self, cart: AbandonedCart) -> RecoveryChannel:
        """Recommend best channel for recovery."""
        if cart.total_value > Decimal("150"):
            return RecoveryChannel.EMAIL
        else:
            return RecoveryChannel.SMS

    def _recommend_discount(self, cart: AbandonedCart) -> float:
        """Recommend discount percentage."""
        if cart.total_value > Decimal("200"):
            return 0.10  # 10% for high value
        elif cart.recovery_attempts >= 2:
            return 0.15  # 15% for second attempt
        return 0.05  # 5% default

    def _get_all_carts(self) -> List[AbandonedCart]:
        """Get all carts (mock)."""
        if not self._carts:
            # Create mock abandoned carts
            self._carts = {
                "cart_001": AbandonedCart(
                    cart_id="cart_001",
                    customer_id="cust_001",
                    items=[
                        CartItem("prod_001", "Wireless Headphones", Decimal("149.99"), 1),
                        CartItem("prod_002", "Phone Case", Decimal("29.99"), 2)
                    ],
                    total_value=Decimal("209.97"),
                    abandoned_at=datetime.utcnow() - timedelta(hours=2),
                    status=CartStatus.ACTIVE
                )
            }
        return list(self._carts.values())
