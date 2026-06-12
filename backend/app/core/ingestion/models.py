"""PARWA Phase 3 Ingestion — Universal data models.

All incoming messages across all channels are normalized into IncomingMessage.
Category-first design means the model is channel-agnostic; the channel/category
field tells you the *kind* of message, not the *provider* that sent it.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ChannelCategory(str, Enum):
    """Top-level channel categories — the primary axis of routing."""
    EMAIL = "email"
    SMS = "sms"
    VOICE = "voice"
    CHAT = "chat"
    WEBHOOK = "webhook"


class MessagePriority(str, Enum):
    """Message priority levels, detected via heuristics or explicit flags."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageSentiment(str, Enum):
    """Quick sentiment classification for routing/escalation decisions."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    ANGRY = "angry"


class IngestionStatus(str, Enum):
    """Result status returned by the IngestionOrchestrator after processing."""
    INGESTED = "ingested"
    DUPLICATE = "duplicate"
    ERROR = "error"
    VALIDATION_ERROR = "validation_error"


@dataclass
class IncomingMessage:
    """Universal data model for all incoming messages across all channels.

    Every normalizer — whether provider-specific or generic — MUST produce
    a dict whose keys match these fields.  The orchestrator wraps the dict
    into this dataclass before returning it to the caller.

    BC-001: company_id is mandatory and scopes all downstream queries.
    """

    message_id: str = ""
    company_id: str = ""
    channel: ChannelCategory = ChannelCategory.EMAIL
    provider: str = ""
    sender_id: str = ""
    sender_name: str = ""
    sender_email: str = ""
    sender_phone: str = ""
    recipient_id: str = ""
    subject: str = ""
    body: str = ""
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    sentiment: MessageSentiment = MessageSentiment.NEUTRAL
    conversation_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    source_ip: str = ""

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict (enums become their string values)."""
        return {
            "message_id": self.message_id,
            "company_id": self.company_id,
            "channel": self.channel.value if isinstance(self.channel, ChannelCategory) else self.channel,
            "provider": self.provider,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "sender_email": self.sender_email,
            "sender_phone": self.sender_phone,
            "recipient_id": self.recipient_id,
            "subject": self.subject,
            "body": self.body,
            "raw_payload": self.raw_payload,
            "priority": self.priority.value if isinstance(self.priority, MessagePriority) else self.priority,
            "sentiment": self.sentiment.value if isinstance(self.sentiment, MessageSentiment) else self.sentiment,
            "conversation_id": self.conversation_id,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "source_ip": self.source_ip,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncomingMessage":
        """Build an IncomingMessage from a normalized dict.

        Enum fields are coerced from strings; unknown enum values fall back
        to their first member so we never crash (BC-008).
        """
        def _safe_enum(enum_cls, value, default=None):
            """Coerce *value* into an enum member; return *default* on failure."""
            if isinstance(value, enum_cls):
                return value
            try:
                return enum_cls(str(value))
            except (ValueError, KeyError):
                return default or list(enum_cls)[0]

        return cls(
            message_id=str(data.get("message_id", "")),
            company_id=str(data.get("company_id", "")),
            channel=_safe_enum(ChannelCategory, data.get("channel", "email"), ChannelCategory.EMAIL),
            provider=str(data.get("provider", "")),
            sender_id=str(data.get("sender_id", "")),
            sender_name=str(data.get("sender_name", "")),
            sender_email=str(data.get("sender_email", "")),
            sender_phone=str(data.get("sender_phone", "")),
            recipient_id=str(data.get("recipient_id", "")),
            subject=str(data.get("subject", "")),
            body=str(data.get("body", "")),
            raw_payload=data.get("raw_payload", {}),
            priority=_safe_enum(MessagePriority, data.get("priority", "normal"), MessagePriority.NORMAL),
            sentiment=_safe_enum(MessageSentiment, data.get("sentiment", "neutral"), MessageSentiment.NEUTRAL),
            conversation_id=str(data.get("conversation_id", "")),
            metadata=data.get("metadata", {}),
            timestamp=str(data.get("timestamp", "")),
            source_ip=str(data.get("source_ip", "")),
        )
