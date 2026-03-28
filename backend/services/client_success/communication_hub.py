"""
Communication Hub Service

Centralized client messaging with multi-channel support (email, in-app, SMS),
message history, read status tracking, and client preferences.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import asyncio
import uuid

logger = logging.getLogger(__name__)


class MessageChannel(str, Enum):
    """Communication channels."""
    EMAIL = "email"
    IN_APP = "in_app"
    SMS = "sms"
    SLACK = "slack"
    WEBHOOK = "webhook"


class MessageStatus(str, Enum):
    """Status of a message."""
    DRAFT = "draft"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    BOUNCED = "bounced"


class MessageType(str, Enum):
    """Types of messages."""
    CHECK_IN = "check_in"
    ANNOUNCEMENT = "announcement"
    ALERT = "alert"
    REMINDER = "reminder"
    RETENTION = "retention"
    ONBOARDING = "onboarding"
    SUPPORT = "support"
    CUSTOM = "custom"


@dataclass
class ClientMessage:
    """A message sent to a client."""
    message_id: str
    client_id: str
    channel: MessageChannel
    message_type: MessageType
    status: MessageStatus
    subject: str
    body: str
    sender: Optional[str] = None
    recipient: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    template_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClientPreference:
    """Communication preferences for a client."""
    client_id: str
    email_enabled: bool = True
    in_app_enabled: bool = True
    sms_enabled: bool = False
    slack_enabled: bool = False
    preferred_channel: MessageChannel = MessageChannel.EMAIL
    quiet_hours_start: Optional[int] = None  # Hour (0-23)
    quiet_hours_end: Optional[int] = None
    frequency_cap_daily: int = 5
    frequency_cap_weekly: int = 20


class CommunicationHub:
    """
    Centralized client communication hub.

    Provides:
    - Centralized client messaging
    - Multi-channel support (email, in-app, SMS)
    - Message history
    - Read status tracking
    - Client preferences
    """

    # All supported clients
    SUPPORTED_CLIENTS = [
        "client_001", "client_002", "client_003", "client_004", "client_005",
        "client_006", "client_007", "client_008", "client_009", "client_010"
    ]

    def __init__(self):
        """Initialize communication hub."""
        self._messages: Dict[str, List[ClientMessage]] = {
            client: [] for client in self.SUPPORTED_CLIENTS
        }
        self._preferences: Dict[str, ClientPreference] = {
            client: ClientPreference(client_id=client)
            for client in self.SUPPORTED_CLIENTS
        }
        self._message_counter = 0
        self._channel_handlers: Dict[MessageChannel, callable] = {}

    def register_channel_handler(
        self,
        channel: MessageChannel,
        handler: callable
    ) -> None:
        """
        Register a handler for a communication channel.

        Args:
            channel: Channel to register for
            handler: Async callable to handle sending
        """
        self._channel_handlers[channel] = handler
        logger.info(f"Registered handler for channel: {channel.value}")

    async def send_message(
        self,
        client_id: str,
        channel: MessageChannel,
        message_type: MessageType,
        subject: str,
        body: str,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
        template_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ClientMessage:
        """
        Send a message to a client.

        Args:
            client_id: Client identifier
            channel: Communication channel
            message_type: Type of message
            subject: Message subject
            body: Message body
            sender: Optional sender identifier
            recipient: Optional recipient override
            template_id: Optional template used
            metadata: Optional additional metadata

        Returns:
            ClientMessage with status
        """
        if client_id not in self.SUPPORTED_CLIENTS:
            raise ValueError(f"Unsupported client: {client_id}")

        # Check client preferences
        prefs = self._preferences.get(client_id)
        if prefs and not self._is_channel_allowed(prefs, channel):
            logger.warning(f"Channel {channel.value} disabled for {client_id}")
            # Fall back to preferred channel
            channel = prefs.preferred_channel

        # Check frequency caps
        if prefs and not self._check_frequency_cap(client_id, prefs):
            logger.warning(f"Frequency cap exceeded for {client_id}")

        # Check quiet hours
        if prefs and self._is_quiet_hours(prefs):
            logger.info(f"Quiet hours for {client_id}, message queued")

        self._message_counter += 1
        message_id = f"msg_{self._message_counter:06d}"

        message = ClientMessage(
            message_id=message_id,
            client_id=client_id,
            channel=channel,
            message_type=message_type,
            status=MessageStatus.QUEUED,
            subject=subject,
            body=body,
            sender=sender,
            recipient=recipient,
            template_id=template_id,
            metadata=metadata or {},
        )

        # Send via channel handler
        success = await self._send_via_channel(message)

        if success:
            message.status = MessageStatus.SENT
            message.sent_at = datetime.utcnow()
        else:
            message.status = MessageStatus.FAILED

        # Store message
        self._messages[client_id].append(message)
        logger.info(f"Message {message_id} sent to {client_id} via {channel.value}")

        return message

    async def _send_via_channel(self, message: ClientMessage) -> bool:
        """Send message through registered channel handler."""
        handler = self._channel_handlers.get(message.channel)

        if handler:
            try:
                await handler(message)
                return True
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                return False
        else:
            # Simulate sending
            logger.info(f"Simulating send via {message.channel.value}: {message.subject}")
            await asyncio.sleep(0.1)
            return True

    def _is_channel_allowed(
        self,
        prefs: ClientPreference,
        channel: MessageChannel
    ) -> bool:
        """Check if channel is allowed for client."""
        channel_enabled = {
            MessageChannel.EMAIL: prefs.email_enabled,
            MessageChannel.IN_APP: prefs.in_app_enabled,
            MessageChannel.SMS: prefs.sms_enabled,
            MessageChannel.SLACK: prefs.slack_enabled,
        }
        return channel_enabled.get(channel, True)

    def _check_frequency_cap(
        self,
        client_id: str,
        prefs: ClientPreference
    ) -> bool:
        """Check if frequency caps are not exceeded."""
        now = datetime.utcnow()
        today = now.date()
        week_start = today - timedelta(days=today.weekday())

        daily_count = sum(
            1 for m in self._messages.get(client_id, [])
            if m.created_at.date() == today and m.status != MessageStatus.FAILED
        )

        weekly_count = sum(
            1 for m in self._messages.get(client_id, [])
            if m.created_at.date() >= week_start and m.status != MessageStatus.FAILED
        )

        return (daily_count < prefs.frequency_cap_daily and
                weekly_count < prefs.frequency_cap_weekly)

    def _is_quiet_hours(self, prefs: ClientPreference) -> bool:
        """Check if current time is within quiet hours."""
        if prefs.quiet_hours_start is None or prefs.quiet_hours_end is None:
            return False

        current_hour = datetime.utcnow().hour
        start = prefs.quiet_hours_start
        end = prefs.quiet_hours_end

        if start < end:
            return start <= current_hour < end
        else:  # Spans midnight
            return current_hour >= start or current_hour < end

    def mark_read(
        self,
        message_id: str
    ) -> Optional[ClientMessage]:
        """
        Mark a message as read.

        Args:
            message_id: Message identifier

        Returns:
            Updated ClientMessage
        """
        for client_id, messages in self._messages.items():
            for message in messages:
                if message.message_id == message_id:
                    message.status = MessageStatus.READ
                    message.read_at = datetime.utcnow()
                    logger.info(f"Message {message_id} marked as read")
                    return message

        return None

    def mark_delivered(
        self,
        message_id: str
    ) -> Optional[ClientMessage]:
        """Mark a message as delivered."""
        for client_id, messages in self._messages.items():
            for message in messages:
                if message.message_id == message_id:
                    message.status = MessageStatus.DELIVERED
                    message.delivered_at = datetime.utcnow()
                    return message

        return None

    def get_message_history(
        self,
        client_id: str,
        limit: int = 50,
        channel: Optional[MessageChannel] = None,
        message_type: Optional[MessageType] = None
    ) -> List[ClientMessage]:
        """
        Get message history for a client.

        Args:
            client_id: Client identifier
            limit: Maximum messages to return
            channel: Optional filter by channel
            message_type: Optional filter by type

        Returns:
            List of messages
        """
        messages = self._messages.get(client_id, [])

        if channel:
            messages = [m for m in messages if m.channel == channel]
        if message_type:
            messages = [m for m in messages if m.message_type == message_type]

        # Sort by created_at (newest first)
        messages.sort(key=lambda m: m.created_at, reverse=True)
        return messages[:limit]

    def get_unread_count(self, client_id: str) -> int:
        """Get count of unread messages for a client."""
        messages = self._messages.get(client_id, [])
        return sum(1 for m in messages if m.status in [MessageStatus.SENT, MessageStatus.DELIVERED])

    def update_preferences(
        self,
        client_id: str,
        preferences: Dict[str, Any]
    ) -> ClientPreference:
        """
        Update communication preferences for a client.

        Args:
            client_id: Client identifier
            preferences: Dict of preference updates

        Returns:
            Updated ClientPreference
        """
        if client_id not in self._preferences:
            raise ValueError(f"Unsupported client: {client_id}")

        prefs = self._preferences[client_id]

        for key, value in preferences.items():
            if hasattr(prefs, key):
                setattr(prefs, key, value)

        logger.info(f"Updated preferences for {client_id}")
        return prefs

    def get_preferences(self, client_id: str) -> ClientPreference:
        """Get communication preferences for a client."""
        return self._preferences.get(client_id, ClientPreference(client_id=client_id))

    def get_communication_summary(self) -> Dict[str, Any]:
        """Get summary of all communications."""
        total = 0
        by_status = {s.value: 0 for s in MessageStatus}
        by_channel = {c.value: 0 for c in MessageChannel}
        by_type = {t.value: 0 for t in MessageType}

        for messages in self._messages.values():
            for message in messages:
                total += 1
                by_status[message.status.value] += 1
                by_channel[message.channel.value] += 1
                by_type[message.message_type.value] += 1

        read_rate = 0
        delivered = by_status.get("delivered", 0) + by_status.get("read", 0)
        if delivered > 0:
            read_rate = by_status.get("read", 0) / delivered * 100

        return {
            "total_messages": total,
            "by_status": by_status,
            "by_channel": by_channel,
            "by_type": by_type,
            "read_rate": round(read_rate, 1),
        }

    async def broadcast_message(
        self,
        client_ids: List[str],
        channel: MessageChannel,
        message_type: MessageType,
        subject: str,
        body: str
    ) -> Dict[str, ClientMessage]:
        """
        Send a message to multiple clients.

        Args:
            client_ids: List of client identifiers
            channel: Communication channel
            message_type: Type of message
            subject: Message subject
            body: Message body

        Returns:
            Dict mapping client_id to message
        """
        results = {}

        for client_id in client_ids:
            if client_id in self.SUPPORTED_CLIENTS:
                message = await self.send_message(
                    client_id=client_id,
                    channel=channel,
                    message_type=message_type,
                    subject=subject,
                    body=body
                )
                results[client_id] = message

        logger.info(f"Broadcast sent to {len(results)} clients")
        return results
