"""
PARWA Mini Notification Tool.

Provides notification functionality for Mini PARWA agents.
Supports SMS and Email notifications.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class NotificationTool:
    """
    Tool for sending notifications.

    Provides:
    - Send SMS notifications
    - Send Email notifications
    - Track notification status
    """

    def __init__(self) -> None:
        """Initialize notification tool."""
        self._notifications: List[Dict[str, Any]] = []
        self._notification_count = 0

    async def send_sms(
        self,
        to: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send SMS notification.

        Note: This is mocked for testing. In production,
        this would use the Twilio client.

        Args:
            to: Phone number to send to
            message: Message content
            metadata: Additional metadata

        Returns:
            Dict with send status
        """
        self._notification_count += 1
        notification_id = f"SMS-{self._notification_count}"

        # Validate phone number (basic)
        if not to or len(to) < 10:
            return {
                "success": False,
                "error": "Invalid phone number",
                "notification_id": notification_id,
            }

        # Validate message
        if not message or len(message) == 0:
            return {
                "success": False,
                "error": "Message cannot be empty",
                "notification_id": notification_id,
            }

        # Mock sending SMS
        now = datetime.now(timezone.utc).isoformat()

        notification = {
            "notification_id": notification_id,
            "type": "sms",
            "to": to,
            "message": message,
            "status": "sent",
            "sent_at": now,
            "metadata": metadata or {},
        }

        self._notifications.append(notification)

        logger.info({
            "event": "sms_sent",
            "notification_id": notification_id,
            "to": to,
            "message_length": len(message),
        })

        return {
            "success": True,
            "notification_id": notification_id,
            "status": "sent",
            "to": to,
        }

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send Email notification.

        Note: This is mocked for testing. In production,
        this would use the Email client.

        Args:
            to: Email address to send to
            subject: Email subject
            body: Email body content
            metadata: Additional metadata

        Returns:
            Dict with send status
        """
        self._notification_count += 1
        notification_id = f"EMAIL-{self._notification_count}"

        # Validate email (basic)
        if not to or "@" not in to:
            return {
                "success": False,
                "error": "Invalid email address",
                "notification_id": notification_id,
            }

        # Validate subject and body
        if not subject:
            return {
                "success": False,
                "error": "Subject cannot be empty",
                "notification_id": notification_id,
            }

        if not body:
            return {
                "success": False,
                "error": "Body cannot be empty",
                "notification_id": notification_id,
            }

        # Mock sending Email
        now = datetime.now(timezone.utc).isoformat()

        notification = {
            "notification_id": notification_id,
            "type": "email",
            "to": to,
            "subject": subject,
            "body": body,
            "status": "sent",
            "sent_at": now,
            "metadata": metadata or {},
        }

        self._notifications.append(notification)

        logger.info({
            "event": "email_sent",
            "notification_id": notification_id,
            "to": to,
            "subject": subject,
        })

        return {
            "success": True,
            "notification_id": notification_id,
            "status": "sent",
            "to": to,
        }

    async def send_bulk_sms(
        self,
        recipients: List[str],
        message: str
    ) -> Dict[str, Any]:
        """
        Send SMS to multiple recipients.

        Args:
            recipients: List of phone numbers
            message: Message content

        Returns:
            Dict with send results
        """
        results = []
        success_count = 0

        for recipient in recipients:
            result = await self.send_sms(recipient, message)
            results.append(result)
            if result.get("success"):
                success_count += 1

        return {
            "total": len(recipients),
            "successful": success_count,
            "failed": len(recipients) - success_count,
            "results": results,
        }

    async def send_bulk_email(
        self,
        recipients: List[str],
        subject: str,
        body: str
    ) -> Dict[str, Any]:
        """
        Send Email to multiple recipients.

        Args:
            recipients: List of email addresses
            subject: Email subject
            body: Email body

        Returns:
            Dict with send results
        """
        results = []
        success_count = 0

        for recipient in recipients:
            result = await self.send_email(recipient, subject, body)
            results.append(result)
            if result.get("success"):
                success_count += 1

        return {
            "total": len(recipients),
            "successful": success_count,
            "failed": len(recipients) - success_count,
            "results": results,
        }

    def get_notification_stats(self) -> Dict[str, Any]:
        """Get notification statistics."""
        sms_count = sum(1 for n in self._notifications if n["type"] == "sms")
        email_count = sum(1 for n in self._notifications if n["type"] == "email")

        return {
            "total_notifications": len(self._notifications),
            "sms_count": sms_count,
            "email_count": email_count,
        }

    async def get_notification(self, notification_id: str) -> Optional[Dict[str, Any]]:
        """Get notification by ID."""
        for notification in self._notifications:
            if notification["notification_id"] == notification_id:
                return notification
        return None
