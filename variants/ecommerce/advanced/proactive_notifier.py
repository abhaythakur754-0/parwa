"""Proactive Notification System.

Provides proactive notifications:
- Shipped notification
- Out for delivery alert
- Delivered confirmation
- Exception alerts
- Multi-channel support
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Notification type."""
    SHIPPED = "shipped"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    EXCEPTION = "exception"
    DELAYED = "delayed"
    RETURNED = "returned"


class NotificationChannel(str, Enum):
    """Notification channel."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


@dataclass
class Notification:
    """Notification record."""
    notification_id: str
    customer_id: str
    order_id: str
    notification_type: NotificationType
    channel: NotificationChannel
    message: str
    sent_at: datetime
    delivered: bool = False


class ProactiveNotifier:
    """Proactive notification system."""

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        self.client_id = client_id
        self.config = config or {}
        self._notifications: List[Notification] = []

    def send_shipped_notification(
        self,
        customer_id: str,
        order_id: str,
        tracking_number: str,
        carrier: str,
        channels: Optional[List[NotificationChannel]] = None
    ) -> List[Notification]:
        """Send shipped notification."""
        channels = channels or [NotificationChannel.EMAIL]
        message = f"Your order {order_id} has shipped! Track with {carrier}: {tracking_number}"

        return self._send_notification(
            customer_id=customer_id,
            order_id=order_id,
            notification_type=NotificationType.SHIPPED,
            message=message,
            channels=channels
        )

    def send_out_for_delivery_notification(
        self,
        customer_id: str,
        order_id: str,
        estimated_time: Optional[str] = None
    ) -> List[Notification]:
        """Send out for delivery notification."""
        time_str = f" Expected around {estimated_time}" if estimated_time else ""
        message = f"Your order {order_id} is out for delivery!{time_str}"

        return self._send_notification(
            customer_id=customer_id,
            order_id=order_id,
            notification_type=NotificationType.OUT_FOR_DELIVERY,
            message=message,
            channels=[NotificationChannel.SMS, NotificationChannel.PUSH]
        )

    def send_delivered_notification(
        self,
        customer_id: str,
        order_id: str,
        delivered_at: Optional[str] = None
    ) -> List[Notification]:
        """Send delivered notification."""
        message = f"Your order {order_id} has been delivered! Thank you for shopping with us."

        return self._send_notification(
            customer_id=customer_id,
            order_id=order_id,
            notification_type=NotificationType.DELIVERED,
            message=message,
            channels=[NotificationChannel.EMAIL, NotificationChannel.SMS]
        )

    def send_exception_notification(
        self,
        customer_id: str,
        order_id: str,
        exception_type: str,
        resolution: str
    ) -> List[Notification]:
        """Send exception notification."""
        message = f"Update on order {order_id}: {exception_type}. {resolution}"

        return self._send_notification(
            customer_id=customer_id,
            order_id=order_id,
            notification_type=NotificationType.EXCEPTION,
            message=message,
            channels=[NotificationChannel.EMAIL]
        )

    def check_customer_preferences(
        self,
        customer_id: str
    ) -> Dict[str, Any]:
        """Check customer notification preferences."""
        return {
            "email_enabled": True,
            "sms_enabled": True,
            "push_enabled": True,
            "preferred_channels": ["email", "sms"]
        }

    def _send_notification(
        self,
        customer_id: str,
        order_id: str,
        notification_type: NotificationType,
        message: str,
        channels: List[NotificationChannel]
    ) -> List[Notification]:
        """Send notification across channels."""
        notifications = []

        for channel in channels:
            notification = Notification(
                notification_id=f"notif_{order_id}_{channel.value}_{datetime.utcnow().timestamp()}",
                customer_id=customer_id,
                order_id=order_id,
                notification_type=notification_type,
                channel=channel,
                message=message,
                sent_at=datetime.utcnow(),
                delivered=True
            )

            self._notifications.append(notification)
            notifications.append(notification)

            logger.info(
                f"Sent {notification_type.value} notification via {channel.value}",
                extra={"order_id": order_id}
            )

        return notifications
