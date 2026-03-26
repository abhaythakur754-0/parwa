"""
Notification Service Layer.

Handles email, SMS, and push notifications.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.user import User
from backend.models.company import Company
from shared.core_functions.logger import get_logger
from shared.core_functions.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class NotificationChannel(str, Enum):
    """Notification channel types."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationStatus(str, Enum):
    """Notification status values."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


class NotificationService:
    """
    Service class for notification business logic.
    
    Provides email, SMS, push, and in-app notifications.
    All methods enforce company-scoped data access (RLS).
    """
    
    def __init__(self, db: AsyncSession, company_id: UUID) -> None:
        """
        Initialize notification service.
        
        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
        """
        self.db = db
        self.company_id = company_id
    
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Send an email notification.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            priority: Notification priority
            cc: Optional CC recipients
            bcc: Optional BCC recipients
            attachments: Optional list of attachments
            
        Returns:
            Dict with notification details
        """
        notification_id = UUID(int=0)  # Placeholder for actual UUID generation
        
        # TODO: Integrate with Brevo/SendGrid
        logger.info({
            "event": "email_sent",
            "company_id": str(self.company_id),
            "notification_id": str(notification_id),
            "to": self._mask_email(to),
            "subject": subject[:100],
            "priority": priority.value,
            "has_html": html_body is not None,
            "cc_count": len(cc) if cc else 0,
            "bcc_count": len(bcc) if bcc else 0,
            "attachment_count": len(attachments) if attachments else 0,
        })
        
        return {
            "notification_id": str(notification_id),
            "channel": NotificationChannel.EMAIL.value,
            "to": to,
            "subject": subject,
            "status": NotificationStatus.SENT.value,
            "priority": priority.value,
            "sent_at": datetime.utcnow().isoformat(),
            "company_id": str(self.company_id),
        }
    
    async def send_sms(
        self,
        to: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        sender_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an SMS notification.
        
        Args:
            to: Recipient phone number (E.164 format)
            message: SMS message content (max 1600 chars)
            priority: Notification priority
            sender_id: Optional custom sender ID
            
        Returns:
            Dict with notification details
        """
        notification_id = UUID(int=0)
        
        # Validate message length
        if len(message) > 1600:
            logger.warning({
                "event": "sms_truncated",
                "company_id": str(self.company_id),
                "original_length": len(message),
            })
            message = message[:1600]
        
        # TODO: Integrate with Twilio/Bird
        logger.info({
            "event": "sms_sent",
            "company_id": str(self.company_id),
            "notification_id": str(notification_id),
            "to": self._mask_phone(to),
            "message_length": len(message),
            "priority": priority.value,
            "sender_id": sender_id,
        })
        
        return {
            "notification_id": str(notification_id),
            "channel": NotificationChannel.SMS.value,
            "to": to,
            "message_length": len(message),
            "status": NotificationStatus.SENT.value,
            "priority": priority.value,
            "sent_at": datetime.utcnow().isoformat(),
            "company_id": str(self.company_id),
        }
    
    async def send_push(
        self,
        user_id: UUID,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        icon: Optional[str] = None,
        action_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a push notification.
        
        Args:
            user_id: Target user UUID
            title: Notification title
            body: Notification body
            data: Optional additional data payload
            icon: Optional icon URL
            action_url: Optional URL to open on click
            
        Returns:
            Dict with notification details
        """
        notification_id = UUID(int=0)
        
        logger.info({
            "event": "push_sent",
            "company_id": str(self.company_id),
            "notification_id": str(notification_id),
            "user_id": str(user_id),
            "title": title[:50],
            "has_data": data is not None,
            "has_action": action_url is not None,
        })
        
        return {
            "notification_id": str(notification_id),
            "channel": NotificationChannel.PUSH.value,
            "user_id": str(user_id),
            "title": title,
            "body": body,
            "status": NotificationStatus.SENT.value,
            "sent_at": datetime.utcnow().isoformat(),
            "company_id": str(self.company_id),
        }
    
    async def send_in_app(
        self,
        user_id: UUID,
        title: str,
        message: str,
        notification_type: Optional[str] = None,
        action_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send an in-app notification.
        
        Args:
            user_id: Target user UUID
            title: Notification title
            message: Notification message
            notification_type: Optional type categorization
            action_url: Optional URL for action
            metadata: Optional additional metadata
            
        Returns:
            Dict with notification details
        """
        notification_id = UUID(int=0)
        
        logger.info({
            "event": "in_app_notification_sent",
            "company_id": str(self.company_id),
            "notification_id": str(notification_id),
            "user_id": str(user_id),
            "title": title[:50],
            "notification_type": notification_type,
            "has_action": action_url is not None,
        })
        
        return {
            "notification_id": str(notification_id),
            "channel": NotificationChannel.IN_APP.value,
            "user_id": str(user_id),
            "title": title,
            "message": message,
            "notification_type": notification_type,
            "action_url": action_url,
            "status": NotificationStatus.DELIVERED.value,
            "created_at": datetime.utcnow().isoformat(),
            "company_id": str(self.company_id),
            "metadata": metadata or {},
        }
    
    async def send_notification(
        self,
        channel: NotificationChannel,
        to: Optional[str] = None,
        user_id: Optional[UUID] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        title: Optional[str] = None,
        message: Optional[str] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send notification through specified channel.
        
        This is a unified method that routes to the appropriate channel handler.
        
        Args:
            channel: Notification channel (email, sms, push, in_app)
            to: Recipient (email/phone) - required for email/SMS
            user_id: Target user UUID - required for push/in-app
            subject: Subject (for email)
            body: Body content
            title: Title (for push/in-app)
            message: Message content
            priority: Notification priority
            **kwargs: Additional channel-specific parameters
            
        Returns:
            Dict with notification details
            
        Raises:
            ValueError: If required parameters are missing or channel is unsupported
        """
        if channel == NotificationChannel.EMAIL:
            if not to:
                raise ValueError("Email address 'to' is required for email notifications")
            return await self.send_email(
                to=to,
                subject=subject or "Notification",
                body=body or message or "",
                priority=priority,
                **kwargs
            )
        elif channel == NotificationChannel.SMS:
            if not to:
                raise ValueError("Phone number 'to' is required for SMS notifications")
            return await self.send_sms(
                to=to,
                message=body or message or "",
                priority=priority,
                **kwargs
            )
        elif channel == NotificationChannel.PUSH:
            if not user_id:
                raise ValueError("user_id is required for push notifications")
            return await self.send_push(
                user_id=user_id,
                title=title or "Notification",
                body=body or message or "",
                **kwargs
            )
        elif channel == NotificationChannel.IN_APP:
            if not user_id:
                raise ValueError("user_id is required for in-app notifications")
            return await self.send_in_app(
                user_id=user_id,
                title=title or "Notification",
                message=body or message or "",
                **kwargs
            )
        else:
            raise ValueError(f"Unsupported channel: {channel}")
    
    async def send_bulk_email(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> Dict[str, Any]:
        """
        Send bulk email notifications.
        
        Args:
            recipients: List of recipient email addresses
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            priority: Notification priority
            
        Returns:
            Dict with bulk notification details
        """
        if not recipients:
            raise ValueError("Recipients list cannot be empty")
        
        results = []
        for recipient in recipients:
            try:
                result = await self.send_email(
                    to=recipient,
                    subject=subject,
                    body=body,
                    html_body=html_body,
                    priority=priority
                )
                results.append({"email": recipient, "status": "sent", "result": result})
            except Exception as e:
                logger.error({
                    "event": "bulk_email_failed",
                    "company_id": str(self.company_id),
                    "email": self._mask_email(recipient),
                    "error": str(e),
                })
                results.append({"email": recipient, "status": "failed", "error": str(e)})
        
        sent_count = sum(1 for r in results if r["status"] == "sent")
        
        return {
            "channel": NotificationChannel.EMAIL.value,
            "total_recipients": len(recipients),
            "sent_count": sent_count,
            "failed_count": len(recipients) - sent_count,
            "results": results,
            "company_id": str(self.company_id),
        }
    
    async def send_bulk_sms(
        self,
        recipients: List[str],
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> Dict[str, Any]:
        """
        Send bulk SMS notifications.
        
        Args:
            recipients: List of recipient phone numbers
            message: SMS message content
            priority: Notification priority
            
        Returns:
            Dict with bulk notification details
        """
        if not recipients:
            raise ValueError("Recipients list cannot be empty")
        
        results = []
        for recipient in recipients:
            try:
                result = await self.send_sms(
                    to=recipient,
                    message=message,
                    priority=priority
                )
                results.append({"phone": recipient, "status": "sent", "result": result})
            except Exception as e:
                logger.error({
                    "event": "bulk_sms_failed",
                    "company_id": str(self.company_id),
                    "phone": self._mask_phone(recipient),
                    "error": str(e),
                })
                results.append({"phone": recipient, "status": "failed", "error": str(e)})
        
        sent_count = sum(1 for r in results if r["status"] == "sent")
        
        return {
            "channel": NotificationChannel.SMS.value,
            "total_recipients": len(recipients),
            "sent_count": sent_count,
            "failed_count": len(recipients) - sent_count,
            "results": results,
            "company_id": str(self.company_id),
        }
    
    async def get_notification_history(
        self,
        user_id: Optional[UUID] = None,
        channel: Optional[NotificationChannel] = None,
        status: Optional[NotificationStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get notification history.
        
        Args:
            user_id: Filter by user
            channel: Filter by channel
            status: Filter by status
            limit: Max results (default 50, max 200)
            offset: Pagination offset
            
        Returns:
            List of notification records
        """
        # Enforce max limit
        limit = min(limit, 200)
        
        # TODO: Query from database when notification model is created
        logger.info({
            "event": "notification_history_query",
            "company_id": str(self.company_id),
            "user_id": str(user_id) if user_id else None,
            "channel": channel.value if channel else None,
            "status": status.value if status else None,
            "limit": limit,
            "offset": offset,
        })
        
        return []
    
    async def mark_as_read(
        self,
        notification_id: UUID,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Mark a notification as read.
        
        Args:
            notification_id: Notification UUID
            user_id: User UUID who read the notification
            
        Returns:
            Dict with updated notification status
        """
        logger.info({
            "event": "notification_marked_read",
            "company_id": str(self.company_id),
            "notification_id": str(notification_id),
            "user_id": str(user_id),
        })
        
        return {
            "notification_id": str(notification_id),
            "user_id": str(user_id),
            "read_at": datetime.utcnow().isoformat(),
            "status": "read",
        }
    
    async def get_unread_count(
        self,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Get count of unread notifications for a user.
        
        Args:
            user_id: User UUID
            
        Returns:
            Dict with unread count
        """
        # TODO: Query from database
        logger.info({
            "event": "unread_count_query",
            "company_id": str(self.company_id),
            "user_id": str(user_id),
        })
        
        return {
            "user_id": str(user_id),
            "unread_count": 0,
        }
    
    async def delete_notification(
        self,
        notification_id: UUID,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Delete a notification.
        
        Args:
            notification_id: Notification UUID
            user_id: User UUID who owns the notification
            
        Returns:
            Dict with deletion status
        """
        logger.info({
            "event": "notification_deleted",
            "company_id": str(self.company_id),
            "notification_id": str(notification_id),
            "user_id": str(user_id),
        })
        
        return {
            "notification_id": str(notification_id),
            "deleted": True,
            "deleted_at": datetime.utcnow().isoformat(),
        }
    
    # --- Helper Methods ---
    
    @staticmethod
    def _mask_email(email: str) -> str:
        """
        Mask email address for logging privacy.
        
        Args:
            email: Email address to mask
            
        Returns:
            Masked email (e.g., "j***@example.com")
        """
        if not email or "@" not in email:
            return email[:3] + "***" if len(email) > 3 else "***"
        
        local, domain = email.split("@", 1)
        if len(local) <= 1:
            masked_local = "*"
        elif len(local) <= 3:
            masked_local = local[0] + "*" * (len(local) - 1)
        else:
            masked_local = local[0] + "*" * min(len(local) - 2, 5) + local[-1]
        
        return f"{masked_local}@{domain}"
    
    @staticmethod
    def _mask_phone(phone: str) -> str:
        """
        Mask phone number for logging privacy.
        
        Args:
            phone: Phone number to mask
            
        Returns:
            Masked phone (e.g., "+123***7890")
        """
        if not phone:
            return "***"
        
        # Keep country code and last 4 digits
        if len(phone) <= 6:
            return phone[:2] + "***" + phone[-2:] if len(phone) > 4 else "***"
        
        return phone[:4] + "***" + phone[-4:]
