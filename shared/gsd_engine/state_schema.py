"""
PARWA GSD State Schema.

Defines the state structures for Guided Self-Dialogue conversations.
Includes conversation state, message tracking, and context metadata.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class ConversationStatus(str, Enum):
    """Conversation status types."""
    ACTIVE = "active"
    WAITING = "waiting"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


class MessageRole(str, Enum):
    """Message role types."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ContextHealthStatus(str, Enum):
    """Context health status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class Message(BaseModel):
    """Single message in a conversation."""
    id: UUID = Field(default_factory=uuid4)
    role: MessageRole
    content: str
    token_count: int = Field(default=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(use_enum_values=True)


class ContextMetadata(BaseModel):
    """Metadata about conversation context."""
    total_tokens: int = Field(default=0, ge=0)
    message_count: int = Field(default=0, ge=0)
    turn_count: int = Field(default=0, ge=0)
    health_status: ContextHealthStatus = Field(default=ContextHealthStatus.HEALTHY)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(use_enum_values=True)


class ConversationState(BaseModel):
    """
    Full conversation state for GSD engine.

    Tracks all messages, context health, and conversation metadata
    for intelligent context management.
    """
    id: UUID = Field(default_factory=uuid4)
    company_id: Optional[UUID] = None
    customer_id: Optional[str] = None
    channel: Optional[str] = None
    status: ConversationStatus = Field(default=ConversationStatus.ACTIVE)
    messages: List[Message] = Field(default_factory=list)
    context: ContextMetadata = Field(default_factory=ContextMetadata)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(use_enum_values=True)

    def add_message(self, role: MessageRole, content: str, token_count: int = 0) -> Message:
        """
        Add a message to the conversation.

        Args:
            role: Message role (user/assistant/system)
            content: Message content
            token_count: Number of tokens in the message

        Returns:
            The created Message instance
        """
        message = Message(
            role=role,
            content=content,
            token_count=token_count
        )
        self.messages.append(message)
        self.context.message_count = len(self.messages)
        self.context.total_tokens += token_count

        if role == MessageRole.USER:
            self.context.turn_count += 1

        self.updated_at = datetime.now(timezone.utc)
        return message

    def get_token_count(self) -> int:
        """
        Get total token count for all messages.

        Returns:
            Sum of all message token counts
        """
        return sum(msg.token_count for msg in self.messages)

    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """
        Get most recent messages.

        Args:
            limit: Maximum number of messages to return

        Returns:
            List of most recent messages
        """
        return self.messages[-limit:] if self.messages else []
