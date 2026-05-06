# Email Channel - Week 48 Builder 2
# Email delivery provider for notifications

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import uuid


class EmailProvider(Enum):
    SMTP = "smtp"
    SENDGRID = "sendgrid"
    MAILGUN = "mailgun"
    SES = "ses"
    POSTMARK = "postmark"


class EmailStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"
    OPENED = "opened"
    CLICKED = "clicked"


@dataclass
class EmailAddress:
    email: str
    name: Optional[str] = None

    def to_string(self) -> str:
        if self.name:
            return f"{self.name} <{self.email}>"
        return self.email


@dataclass
class EmailMessage:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    from_address: Optional[EmailAddress] = None
    to_addresses: List[EmailAddress] = field(default_factory=list)
    cc_addresses: List[EmailAddress] = field(default_factory=list)
    bcc_addresses: List[EmailAddress] = field(default_factory=list)
    subject: str = ""
    body_text: str = ""
    body_html: Optional[str] = None
    template_id: Optional[str] = None
    template_vars: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    status: EmailStatus = EmailStatus.PENDING
    external_id: Optional[str] = None
    provider: EmailProvider = EmailProvider.SMTP
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


@dataclass
class EmailConfig:
    provider: EmailProvider = EmailProvider.SMTP
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    default_from_email: str = "noreply@example.com"
    default_from_name: str = "Notification System"
    api_key: Optional[str] = None
    api_url: Optional[str] = None


@dataclass
class SendResult:
    message_id: str
    success: bool
    external_id: Optional[str] = None
    error_message: Optional[str] = None


class EmailChannel:
    """Email delivery channel for notifications"""

    def __init__(self, config: Optional[EmailConfig] = None):
        self.config = config or EmailConfig()
        self._messages: Dict[str, EmailMessage] = {}
        self._metrics = {
            "total_sent": 0,
            "total_delivered": 0,
            "total_bounced": 0,
            "total_failed": 0,
            "total_opened": 0,
            "total_clicked": 0
        }

    def create_message(
        self,
        tenant_id: str,
        to_addresses: List[str],
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        template_id: Optional[str] = None,
        template_vars: Optional[Dict[str, Any]] = None
    ) -> EmailMessage:
        """Create a new email message"""
        message = EmailMessage(
            tenant_id=tenant_id,
            from_address=EmailAddress(
                email=from_email or self.config.default_from_email,
                name=from_name or self.config.default_from_name
            ),
            to_addresses=[EmailAddress(email=e) for e in to_addresses],
            cc_addresses=[EmailAddress(email=e) for e in (cc or [])],
            bcc_addresses=[EmailAddress(email=e) for e in (bcc or [])],
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            template_id=template_id,
            template_vars=template_vars or {}
        )
        self._messages[message.id] = message
        return message

    async def send(self, message: EmailMessage) -> SendResult:
        """Send an email message"""
        message.status = EmailStatus.QUEUED

        try:
            if self.config.provider == EmailProvider.SMTP:
                result = await self._send_smtp(message)
            else:
                result = await self._send_api(message)

            if result.success:
                message.status = EmailStatus.SENT
                message.external_id = result.external_id
                message.sent_at = datetime.utcnow()
                self._metrics["total_sent"] += 1
            else:
                message.status = EmailStatus.FAILED
                self._metrics["total_failed"] += 1

            return result

        except Exception as e:
            message.status = EmailStatus.FAILED
            self._metrics["total_failed"] += 1
            return SendResult(
                message_id=message.id,
                success=False,
                error_message=str(e)
            )

    async def _send_smtp(self, message: EmailMessage) -> SendResult:
        """Send via SMTP"""
        loop = asyncio.get_event_loop()

        def _send():
            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.subject
            msg["From"] = message.from_address.to_string()
            msg["To"] = ", ".join(a.to_string() for a in message.to_addresses)

            if message.cc_addresses:
                msg["Cc"] = ", ".join(a.to_string() for a in message.cc_addresses)

            for key, value in message.headers.items():
                msg[key] = value

            msg.attach(MIMEText(message.body_text, "plain"))
            if message.body_html:
                msg.attach(MIMEText(message.body_html, "html"))

            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.smtp_use_tls:
                    server.starttls()
                if self.config.smtp_username:
                    server.login(self.config.smtp_username, self.config.smtp_password)
                server.send_message(msg)

            return str(uuid.uuid4())

        try:
            external_id = await loop.run_in_executor(None, _send)
            return SendResult(
                message_id=message.id,
                success=True,
                external_id=external_id
            )
        except Exception as e:
            return SendResult(
                message_id=message.id,
                success=False,
                error_message=str(e)
            )

    async def _send_api(self, message: EmailMessage) -> SendResult:
        """Send via API (placeholder for actual implementation)"""
        # Placeholder for SendGrid, Mailgun, SES, etc.
        return SendResult(
            message_id=message.id,
            success=True,
            external_id=str(uuid.uuid4())
        )

    async def send_batch(
        self,
        messages: List[EmailMessage]
    ) -> List[SendResult]:
        """Send multiple emails"""
        results = []
        for message in messages:
            result = await self.send(message)
            results.append(result)
        return results

    def get_message(self, message_id: str) -> Optional[EmailMessage]:
        """Get a message by ID"""
        return self._messages.get(message_id)

    def get_messages_by_tenant(self, tenant_id: str) -> List[EmailMessage]:
        """Get all messages for a tenant"""
        return [m for m in self._messages.values() if m.tenant_id == tenant_id]

    def mark_delivered(self, message_id: str) -> bool:
        """Mark message as delivered"""
        message = self._messages.get(message_id)
        if not message:
            return False
        message.status = EmailStatus.DELIVERED
        message.delivered_at = datetime.utcnow()
        self._metrics["total_delivered"] += 1
        return True

    def mark_bounced(self, message_id: str) -> bool:
        """Mark message as bounced"""
        message = self._messages.get(message_id)
        if not message:
            return False
        message.status = EmailStatus.BOUNCED
        self._metrics["total_bounced"] += 1
        return True

    def mark_opened(self, message_id: str) -> bool:
        """Mark message as opened"""
        message = self._messages.get(message_id)
        if not message:
            return False
        if message.status not in [EmailStatus.SENT, EmailStatus.DELIVERED]:
            return False
        message.status = EmailStatus.OPENED
        self._metrics["total_opened"] += 1
        return True

    def mark_clicked(self, message_id: str) -> bool:
        """Mark message as clicked"""
        message = self._messages.get(message_id)
        if not message:
            return False
        message.status = EmailStatus.CLICKED
        self._metrics["total_clicked"] += 1
        return True

    def get_metrics(self) -> Dict[str, Any]:
        """Get channel metrics"""
        return {
            **self._metrics,
            "total_messages": len(self._messages)
        }

    def get_pending_messages(self) -> List[EmailMessage]:
        """Get all pending messages"""
        return [m for m in self._messages.values() 
                if m.status in [EmailStatus.PENDING, EmailStatus.QUEUED]]

    def get_failed_messages(self) -> List[EmailMessage]:
        """Get all failed messages"""
        return [m for m in self._messages.values() 
                if m.status == EmailStatus.FAILED]

    async def retry_failed(self, message_id: str) -> SendResult:
        """Retry a failed message"""
        message = self._messages.get(message_id)
        if not message or message.status != EmailStatus.FAILED:
            return SendResult(
                message_id=message_id,
                success=False,
                error_message="Message not found or not in failed state"
            )
        message.status = EmailStatus.PENDING
        return await self.send(message)
