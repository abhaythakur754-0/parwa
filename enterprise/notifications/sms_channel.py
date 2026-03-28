# SMS Channel - Week 48 Builder 3
# SMS delivery via Twilio

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import asyncio
import httpx
import uuid
import os


class SMSProvider(Enum):
    TWILIO = "twilio"
    AWS_SNS = "aws_sns"
    NEXMO = "nexmo"
    CUSTOM = "custom"


class SMSStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    UNDELIVERED = "undelivered"


@dataclass
class SMSConfig:
    provider: SMSProvider = SMSProvider.TWILIO
    # Twilio credentials (load from environment)
    twilio_account_sid: str = ""  # Set via TWILIO_ACCOUNT_SID env var
    twilio_auth_token: str = ""   # Set via TWILIO_AUTH_TOKEN env var
    twilio_phone_number: str = ""
    # General settings
    default_country_code: str = "+1"
    max_message_length: int = 1600
    enable_delivery_reports: bool = True


@dataclass
class SMSMessage:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    from_number: str = ""
    to_number: str = ""
    body: str = ""
    status: SMSStatus = SMSStatus.PENDING
    provider: SMSProvider = SMSProvider.TWILIO
    external_id: Optional[str] = None
    segments: int = 1
    cost: float = 0.0
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


@dataclass
class SendResult:
    message_id: str
    success: bool
    external_id: Optional[str] = None
    segments: int = 1
    cost: float = 0.0
    error_message: Optional[str] = None


class SMSChannel:
    """SMS delivery channel using Twilio"""

    def __init__(self, config: Optional[SMSConfig] = None):
        self.config = config or SMSConfig()
        # Load credentials from environment if not provided
        if not self.config.twilio_account_sid:
            self.config.twilio_account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        if not self.config.twilio_auth_token:
            self.config.twilio_auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self._messages: Dict[str, SMSMessage] = {}
        self._metrics = {
            "total_sent": 0,
            "total_delivered": 0,
            "total_failed": 0,
            "total_segments": 0,
            "total_cost": 0.0
        }

    def create_message(
        self,
        tenant_id: str,
        to_number: str,
        body: str,
        from_number: Optional[str] = None
    ) -> SMSMessage:
        """Create a new SMS message"""
        # Normalize phone number
        to_number = self._normalize_number(to_number)

        message = SMSMessage(
            tenant_id=tenant_id,
            from_number=from_number or self.config.twilio_phone_number,
            to_number=to_number,
            body=body,
            segments=self._calculate_segments(body)
        )
        self._messages[message.id] = message
        return message

    def _normalize_number(self, number: str) -> str:
        """Normalize phone number format"""
        # Remove all non-numeric characters
        digits = ''.join(c for c in number if c.isdigit())

        # Add country code if missing
        if not digits.startswith('1') and len(digits) == 10:
            digits = '1' + digits

        return '+' + digits

    def _calculate_segments(self, body: str) -> int:
        """Calculate number of SMS segments"""
        length = len(body)
        if length <= 160:
            return 1
        # Multi-part messages have 153 chars per segment (GSM-7)
        return (length + 152) // 153

    async def send(self, message: SMSMessage) -> SendResult:
        """Send an SMS message via Twilio"""
        message.status = SMSStatus.QUEUED

        try:
            if self.config.provider == SMSProvider.TWILIO:
                result = await self._send_twilio(message)
            else:
                result = await self._send_other(message)

            if result.success:
                message.status = SMSStatus.SENT
                message.external_id = result.external_id
                message.segments = result.segments
                message.cost = result.cost
                message.sent_at = datetime.utcnow()
                self._metrics["total_sent"] += 1
                self._metrics["total_segments"] += result.segments
                self._metrics["total_cost"] += result.cost
            else:
                message.status = SMSStatus.FAILED
                message.error_message = result.error_message
                self._metrics["total_failed"] += 1

            return result

        except Exception as e:
            message.status = SMSStatus.FAILED
            message.error_message = str(e)
            self._metrics["total_failed"] += 1
            return SendResult(
                message_id=message.id,
                success=False,
                error_message=str(e)
            )

    async def _send_twilio(self, message: SMSMessage) -> SendResult:
        """Send via Twilio API"""
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.config.twilio_account_sid}/Messages.json"

        auth = (self.config.twilio_account_sid, self.config.twilio_auth_token)

        data = {
            "From": message.from_number,
            "To": message.to_number,
            "Body": message.body
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, auth=auth, data=data)

        if response.status_code == 201:
            result = response.json()
            return SendResult(
                message_id=message.id,
                success=True,
                external_id=result.get("sid"),
                segments=int(result.get("num_segments", 1)),
                cost=float(result.get("price", 0) or 0)
            )
        else:
            error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            return SendResult(
                message_id=message.id,
                success=False,
                error_message=error_data.get("message", f"HTTP {response.status_code}")
            )

    async def _send_other(self, message: SMSMessage) -> SendResult:
        """Send via other providers (placeholder)"""
        return SendResult(
            message_id=message.id,
            success=True,
            external_id=str(uuid.uuid4())
        )

    async def send_batch(
        self,
        messages: List[SMSMessage]
    ) -> List[SendResult]:
        """Send multiple SMS messages"""
        results = []
        for message in messages:
            result = await self.send(message)
            results.append(result)
        return results

    def get_message(self, message_id: str) -> Optional[SMSMessage]:
        """Get a message by ID"""
        return self._messages.get(message_id)

    def get_messages_by_tenant(self, tenant_id: str) -> List[SMSMessage]:
        """Get all messages for a tenant"""
        return [m for m in self._messages.values() if m.tenant_id == tenant_id]

    def mark_delivered(self, message_id: str) -> bool:
        """Mark message as delivered"""
        message = self._messages.get(message_id)
        if not message:
            return False
        message.status = SMSStatus.DELIVERED
        message.delivered_at = datetime.utcnow()
        self._metrics["total_delivered"] += 1
        return True

    def get_pending_messages(self) -> List[SMSMessage]:
        """Get all pending messages"""
        return [m for m in self._messages.values()
                if m.status in [SMSStatus.PENDING, SMSStatus.QUEUED]]

    def get_failed_messages(self) -> List[SMSMessage]:
        """Get all failed messages"""
        return [m for m in self._messages.values()
                if m.status == SMSStatus.FAILED]

    async def retry_failed(self, message_id: str) -> SendResult:
        """Retry a failed message"""
        message = self._messages.get(message_id)
        if not message or message.status != SMSStatus.FAILED:
            return SendResult(
                message_id=message_id,
                success=False,
                error_message="Message not found or not in failed state"
            )
        message.status = SMSStatus.PENDING
        return await self.send(message)

    async def check_delivery_status(
        self,
        external_id: str
    ) -> Optional[str]:
        """Check delivery status from Twilio"""
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.config.twilio_account_sid}/Messages/{external_id}.json"

        auth = (self.config.twilio_account_sid, self.config.twilio_auth_token)

        async with httpx.AsyncClient() as client:
            response = await client.get(url, auth=auth)

        if response.status_code == 200:
            result = response.json()
            return result.get("status")
        return None

    def get_metrics(self) -> Dict[str, Any]:
        """Get channel metrics"""
        return {
            **self._metrics,
            "total_messages": len(self._messages)
        }

    def estimate_cost(self, body: str) -> float:
        """Estimate cost for a message"""
        segments = self._calculate_segments(body)
        # Approximate Twilio pricing ($0.0075 per segment in US)
        return segments * 0.0075
