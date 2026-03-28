# Mobile Notifier - Week 48 Builder 3
# Mobile-specific notification handling

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid

from enterprise.notifications.push_channel import PushChannel, PushNotification, PushPriority
from enterprise.notifications.sms_channel import SMSChannel, SMSMessage


class NotificationFallback(Enum):
    NONE = "none"
    PUSH_TO_SMS = "push_to_sms"
    SMS_TO_PUSH = "sms_to_push"


@dataclass
class MobileDevice:
    device_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    tenant_id: str = ""
    device_token: Optional[str] = None
    device_type: str = "android"  # android, ios
    phone_number: Optional[str] = None
    app_version: Optional[str] = None
    os_version: Optional[str] = None
    language: str = "en"
    timezone: str = "UTC"
    push_enabled: bool = True
    sms_enabled: bool = False
    quiet_hours_start: Optional[str] = None  # HH:MM format
    quiet_hours_end: Optional[str] = None
    last_active: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MobileNotification:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    tenant_id: str = ""
    title: str = ""
    body: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    priority: PushPriority = PushPriority.NORMAL
    fallback: NotificationFallback = NotificationFallback.PUSH_TO_SMS
    channels_used: List[str] = field(default_factory=list)
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)


class MobileNotifier:
    """Mobile notification manager with fallback support"""

    def __init__(
        self,
        push_channel: Optional[PushChannel] = None,
        sms_channel: Optional[SMSChannel] = None
    ):
        self.push_channel = push_channel or PushChannel()
        self.sms_channel = sms_channel or SMSChannel()
        self._devices: Dict[str, MobileDevice] = {}
        self._devices_by_user: Dict[str, List[str]] = {}
        self._notifications: Dict[str, MobileNotification] = {}
        self._metrics = {
            "total_sent": 0,
            "push_sent": 0,
            "sms_sent": 0,
            "fallback_triggered": 0
        }

    def register_device(
        self,
        user_id: str,
        tenant_id: str,
        device_token: str,
        device_type: str = "android",
        phone_number: Optional[str] = None,
        **kwargs
    ) -> MobileDevice:
        """Register a mobile device"""
        device = MobileDevice(
            user_id=user_id,
            tenant_id=tenant_id,
            device_token=device_token,
            device_type=device_type,
            phone_number=phone_number,
            **kwargs
        )

        self._devices[device.device_id] = device

        if user_id not in self._devices_by_user:
            self._devices_by_user[user_id] = []
        self._devices_by_user[user_id].append(device.device_id)

        # Register with push channel
        if device_token:
            self.push_channel.register_device(tenant_id, user_id, device_token, device_type)

        return device

    def update_device(
        self,
        device_id: str,
        device_token: Optional[str] = None,
        phone_number: Optional[str] = None,
        push_enabled: Optional[bool] = None,
        sms_enabled: Optional[bool] = None
    ) -> Optional[MobileDevice]:
        """Update device settings"""
        device = self._devices.get(device_id)
        if not device:
            return None

        if device_token is not None:
            device.device_token = device_token
        if phone_number is not None:
            device.phone_number = phone_number
        if push_enabled is not None:
            device.push_enabled = push_enabled
        if sms_enabled is not None:
            device.sms_enabled = sms_enabled

        device.last_active = datetime.utcnow()
        return device

    def unregister_device(self, device_id: str) -> bool:
        """Unregister a device"""
        device = self._devices.get(device_id)
        if not device:
            return False

        # Remove from user list
        if device.user_id in self._devices_by_user:
            self._devices_by_user[device.user_id] = [
                d for d in self._devices_by_user[device.user_id]
                if d != device_id
            ]

        # Remove from push channel
        if device.device_token:
            self.push_channel.unregister_device(device.device_token)

        del self._devices[device_id]
        return True

    def get_user_devices(self, user_id: str) -> List[MobileDevice]:
        """Get all devices for a user"""
        device_ids = self._devices_by_user.get(user_id, [])
        return [self._devices[did] for did in device_ids if did in self._devices]

    def create_notification(
        self,
        user_id: str,
        tenant_id: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        priority: PushPriority = PushPriority.NORMAL,
        fallback: NotificationFallback = NotificationFallback.PUSH_TO_SMS
    ) -> MobileNotification:
        """Create a mobile notification"""
        notification = MobileNotification(
            user_id=user_id,
            tenant_id=tenant_id,
            title=title,
            body=body,
            data=data or {},
            priority=priority,
            fallback=fallback
        )
        self._notifications[notification.id] = notification
        return notification

    async def send_notification(
        self,
        notification: MobileNotification
    ) -> Dict[str, Any]:
        """Send notification with fallback support"""
        devices = self.get_user_devices(notification.user_id)
        results = []

        for device in devices:
            # Check quiet hours
            if self._is_quiet_hours(device):
                continue

            result = await self._send_to_device(notification, device)
            results.append(result)

        self._metrics["total_sent"] += 1
        notification.status = "sent"

        return {
            "notification_id": notification.id,
            "devices_notified": len(results),
            "results": results
        }

    async def _send_to_device(
        self,
        notification: MobileNotification,
        device: MobileDevice
    ) -> Dict[str, Any]:
        """Send notification to a specific device"""
        result = {
            "device_id": device.device_id,
            "device_type": device.device_type,
            "channels": [],
            "success": False
        }

        # Try push first if enabled
        if device.push_enabled and device.device_token:
            push = self.push_channel.create_notification(
                tenant_id=device.tenant_id,
                device_token=device.device_token,
                title=notification.title,
                body=notification.body,
                data=notification.data,
                priority=notification.priority
            )
            push_result = await self.push_channel.send(push)

            if push_result.success:
                result["channels"].append("push")
                result["success"] = True
                notification.channels_used.append("push")
                self._metrics["push_sent"] += 1

                # Register device in push channel
                self.push_channel.register_device(
                    device.tenant_id,
                    device.user_id,
                    device.device_token,
                    device.device_type
                )
                return result
            elif push_result.invalid_token:
                # Token is invalid, disable push for this device
                device.push_enabled = False

        # Fallback to SMS if push failed and fallback is enabled
        if (
            notification.fallback == NotificationFallback.PUSH_TO_SMS
            and device.sms_enabled
            and device.phone_number
        ):
            sms = self.sms_channel.create_message(
                tenant_id=device.tenant_id,
                to_number=device.phone_number,
                body=f"{notification.title}: {notification.body}"
            )
            sms_result = await self.sms_channel.send(sms)

            if sms_result.success:
                result["channels"].append("sms")
                result["success"] = True
                notification.channels_used.append("sms")
                self._metrics["sms_sent"] += 1
                self._metrics["fallback_triggered"] += 1

        return result

    def _is_quiet_hours(self, device: MobileDevice) -> bool:
        """Check if current time is within quiet hours"""
        if not device.quiet_hours_start or not device.quiet_hours_end:
            return False

        now = datetime.utcnow()
        current_time = now.strftime("%H:%M")

        return device.quiet_hours_start <= current_time < device.quiet_hours_end

    async def broadcast(
        self,
        tenant_id: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Broadcast to all devices in a tenant"""
        devices = [
            d for d in self._devices.values()
            if d.tenant_id == tenant_id and d.push_enabled
        ]

        results = {
            "total_devices": len(devices),
            "successful": 0,
            "failed": 0
        }

        for device in devices:
            if device.device_token:
                push = self.push_channel.create_notification(
                    tenant_id=tenant_id,
                    device_token=device.device_token,
                    title=title,
                    body=body,
                    data=data
                )
                result = await self.push_channel.send(push)

                if result.success:
                    results["successful"] += 1
                else:
                    results["failed"] += 1

        return results

    def get_device(self, device_id: str) -> Optional[MobileDevice]:
        """Get a device by ID"""
        return self._devices.get(device_id)

    def get_notification(self, notification_id: str) -> Optional[MobileNotification]:
        """Get a notification by ID"""
        return self._notifications.get(notification_id)

    def get_metrics(self) -> Dict[str, Any]:
        """Get notifier metrics"""
        return {
            **self._metrics,
            "total_devices": len(self._devices),
            "total_users": len(self._devices_by_user),
            "total_notifications": len(self._notifications)
        }

    def get_devices_by_tenant(self, tenant_id: str) -> List[MobileDevice]:
        """Get all devices for a tenant"""
        return [d for d in self._devices.values() if d.tenant_id == tenant_id]
