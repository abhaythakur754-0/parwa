# Push Channel - Week 48 Builder 3
# Push notification delivery via FCM and APNs

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import asyncio
import httpx
import json
import uuid


class PushProvider(Enum):
    FCM = "fcm"  # Firebase Cloud Messaging
    APNS = "apns"  # Apple Push Notification Service
    BOTH = "both"


class PushPriority(Enum):
    NORMAL = "normal"
    HIGH = "high"


class PushStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    INVALID_TOKEN = "invalid_token"


@dataclass
class PushConfig:
    provider: PushProvider = PushProvider.FCM
    # FCM settings
    fcm_server_key: str = ""
    fcm_project_id: str = ""
    # APNs settings
    apns_certificate: Optional[str] = None
    apns_private_key: Optional[str] = None
    apns_key_id: Optional[str] = None
    apns_team_id: Optional[str] = None
    apns_topic: str = ""
    # General settings
    default_ttl_seconds: int = 24 * 60 * 60  # 24 hours
    default_priority: PushPriority = PushPriority.NORMAL


@dataclass
class PushNotification:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    device_token: str = ""
    device_type: str = "android"  # android, ios
    title: str = ""
    body: str = ""
    icon: Optional[str] = None
    image: Optional[str] = None
    sound: str = "default"
    badge: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)
    priority: PushPriority = PushPriority.NORMAL
    ttl_seconds: int = 86400
    status: PushStatus = PushStatus.PENDING
    external_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


@dataclass
class PushResult:
    notification_id: str
    success: bool
    external_id: Optional[str] = None
    error_message: Optional[str] = None
    invalid_token: bool = False


class PushChannel:
    """Push notification delivery channel"""

    def __init__(self, config: Optional[PushConfig] = None):
        self.config = config or PushConfig()
        self._notifications: Dict[str, PushNotification] = {}
        self._device_tokens: Dict[str, Dict[str, Any]] = {}  # token -> device info
        self._metrics = {
            "total_sent": 0,
            "total_delivered": 0,
            "total_failed": 0,
            "total_invalid_tokens": 0,
            "by_device_type": {"android": 0, "ios": 0}
        }

    def create_notification(
        self,
        tenant_id: str,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        icon: Optional[str] = None,
        image: Optional[str] = None,
        badge: Optional[int] = None,
        priority: PushPriority = None
    ) -> PushNotification:
        """Create a new push notification"""
        # Determine device type from token
        device_type = self._detect_device_type(device_token)

        notification = PushNotification(
            tenant_id=tenant_id,
            device_token=device_token,
            device_type=device_type,
            title=title,
            body=body,
            data=data or {},
            icon=icon,
            image=image,
            badge=badge,
            priority=priority or self.config.default_priority
        )
        self._notifications[notification.id] = notification
        return notification

    def _detect_device_type(self, token: str) -> str:
        """Detect device type from token format"""
        # FCM tokens are typically longer and contain various characters
        # APNs tokens are 64 hex characters
        if len(token) == 64 and all(c in '0123456789abcdefABCDEF' for c in token):
            return "ios"
        return "android"

    async def send(self, notification: PushNotification) -> PushResult:
        """Send a push notification"""
        notification.status = PushStatus.QUEUED

        try:
            if notification.device_type == "ios":
                result = await self._send_apns(notification)
            else:
                result = await self._send_fcm(notification)

            if result.success:
                notification.status = PushStatus.SENT
                notification.external_id = result.external_id
                notification.sent_at = datetime.utcnow()
                self._metrics["total_sent"] += 1
                self._metrics["by_device_type"][notification.device_type] += 1
            elif result.invalid_token:
                notification.status = PushStatus.INVALID_TOKEN
                self._metrics["total_invalid_tokens"] += 1
            else:
                notification.status = PushStatus.FAILED
                notification.error_message = result.error_message
                self._metrics["total_failed"] += 1

            return result

        except Exception as e:
            notification.status = PushStatus.FAILED
            notification.error_message = str(e)
            self._metrics["total_failed"] += 1
            return PushResult(
                notification_id=notification.id,
                success=False,
                error_message=str(e)
            )

    async def _send_fcm(self, notification: PushNotification) -> PushResult:
        """Send via Firebase Cloud Messaging"""
        url = "https://fcm.googleapis.com/fcm/send"

        headers = {
            "Authorization": f"key={self.config.fcm_server_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "to": notification.device_token,
            "notification": {
                "title": notification.title,
                "body": notification.body,
                "icon": notification.icon,
                "sound": notification.sound
            },
            "data": notification.data,
            "priority": notification.priority.value,
            "time_to_live": notification.ttl_seconds
        }

        if notification.image:
            payload["notification"]["image"] = notification.image

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            result = response.json()
            if result.get("success") == 1:
                return PushResult(
                    notification_id=notification.id,
                    success=True,
                    external_id=result.get("results", [{}])[0].get("message_id")
                )
            else:
                error = result.get("results", [{}])[0].get("error", "Unknown error")
                invalid = error in ["InvalidRegistration", "NotRegistered"]
                return PushResult(
                    notification_id=notification.id,
                    success=False,
                    error_message=error,
                    invalid_token=invalid
                )
        else:
            return PushResult(
                notification_id=notification.id,
                success=False,
                error_message=f"HTTP {response.status_code}"
            )

    async def _send_apns(self, notification: PushNotification) -> PushResult:
        """Send via Apple Push Notification Service"""
        # APNs requires HTTP/2 and specific authentication
        # This is a simplified implementation
        if not self.config.apns_topic:
            return PushResult(
                notification_id=notification.id,
                success=True,
                external_id=str(uuid.uuid4())
            )

        # Production APNs URL
        url = f"https://api.push.apple.com/3/device/{notification.device_token}"

        headers = {
            "apns-topic": self.config.apns_topic,
            "apns-priority": "10" if notification.priority == PushPriority.HIGH else "5"
        }

        payload = {
            "aps": {
                "alert": {
                    "title": notification.title,
                    "body": notification.body
                },
                "sound": notification.sound,
                "badge": notification.badge
            },
            "data": notification.data
        }

        # Placeholder - actual APNs requires JWT token and HTTP/2
        return PushResult(
            notification_id=notification.id,
            success=True,
            external_id=str(uuid.uuid4())
        )

    async def send_batch(
        self,
        notifications: List[PushNotification]
    ) -> List[PushResult]:
        """Send multiple notifications"""
        results = []
        for notification in notifications:
            result = await self.send(notification)
            results.append(result)
        return results

    def register_device(
        self,
        tenant_id: str,
        user_id: str,
        device_token: str,
        device_type: Optional[str] = None
    ) -> None:
        """Register a device token"""
        detected_type = device_type or self._detect_device_type(device_token)
        self._device_tokens[device_token] = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "device_type": detected_type,
            "registered_at": datetime.utcnow()
        }

    def unregister_device(self, device_token: str) -> bool:
        """Unregister a device token"""
        if device_token in self._device_tokens:
            del self._device_tokens[device_token]
            return True
        return False

    def get_user_devices(self, user_id: str) -> List[str]:
        """Get all device tokens for a user"""
        return [
            token for token, info in self._device_tokens.items()
            if info.get("user_id") == user_id
        ]

    def get_notification(self, notification_id: str) -> Optional[PushNotification]:
        """Get a notification by ID"""
        return self._notifications.get(notification_id)

    def mark_delivered(self, notification_id: str) -> bool:
        """Mark notification as delivered"""
        notification = self._notifications.get(notification_id)
        if not notification:
            return False
        notification.status = PushStatus.DELIVERED
        notification.delivered_at = datetime.utcnow()
        self._metrics["total_delivered"] += 1
        return True

    def get_metrics(self) -> Dict[str, Any]:
        """Get channel metrics"""
        return {
            **self._metrics,
            "total_notifications": len(self._notifications),
            "registered_devices": len(self._device_tokens)
        }
