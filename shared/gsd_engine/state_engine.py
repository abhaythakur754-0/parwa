"""
PARWA GSD State Engine.

Manages conversation state lifecycle, message handling,
and state transitions for Guided Self-Dialogue.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime, timezone

from shared.core_functions.logger import get_logger
from shared.gsd_engine.state_schema import (
    ConversationState,
    ConversationStatus,
    MessageRole,
    Message,
    ContextMetadata,
)

logger = get_logger(__name__)


class StateEngine:
    """
    GSD State Engine for conversation management.

    Features:
    - Create and manage conversation states
    - Message addition with token tracking
    - State transitions (active → waiting → resolved/escalated)
    - Context window management
    """

    MAX_MESSAGES = 50
    MAX_TOKENS = 4000

    def __init__(
        self,
        company_id: Optional[UUID] = None,
        max_messages: int = MAX_MESSAGES,
        max_tokens: int = MAX_TOKENS
    ) -> None:
        """
        Initialize State Engine.

        Args:
            company_id: Company UUID for scoping
            max_messages: Maximum messages per conversation
            max_tokens: Maximum tokens in context window
        """
        self.company_id = company_id
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self._conversations: Dict[UUID, ConversationState] = {}

    def create_conversation(
        self,
        customer_id: Optional[str] = None,
        channel: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationState:
        """
        Create a new conversation state.

        Args:
            customer_id: Customer identifier
            channel: Communication channel
            metadata: Additional metadata

        Returns:
            Created ConversationState instance
        """
        state = ConversationState(
            company_id=self.company_id,
            customer_id=customer_id,
            channel=channel,
            metadata=metadata or {}
        )

        self._conversations[state.id] = state

        logger.info({
            "event": "conversation_created",
            "conversation_id": str(state.id),
            "company_id": str(self.company_id) if self.company_id else None,
            "channel": channel,
        })

        return state

    def get_conversation(self, conversation_id: UUID) -> Optional[ConversationState]:
        """
        Get a conversation by ID.

        Args:
            conversation_id: Conversation UUID

        Returns:
            ConversationState if found, None otherwise
        """
        return self._conversations.get(conversation_id)

    def add_message(
        self,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        token_count: Optional[int] = None
    ) -> Optional[Message]:
        """
        Add a message to a conversation.

        Args:
            conversation_id: Conversation UUID
            role: Message role (user/assistant/system)
            content: Message content
            token_count: Token count (estimated if not provided)

        Returns:
            Created Message if successful, None if conversation not found
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            logger.warning({
                "event": "message_add_failed",
                "reason": "conversation_not_found",
                "conversation_id": str(conversation_id),
            })
            return None

        # Estimate tokens if not provided
        if token_count is None:
            token_count = self._estimate_tokens(content)

        message = conversation.add_message(role, content, token_count)

        # Check if context window is approaching limit
        if conversation.get_token_count() > self.max_tokens * 0.8:
            logger.warning({
                "event": "context_window_warning",
                "conversation_id": str(conversation_id),
                "token_count": conversation.get_token_count(),
                "max_tokens": self.max_tokens,
            })

        logger.info({
            "event": "message_added",
            "conversation_id": str(conversation_id),
            "role": role.value,
            "token_count": token_count,
            "total_tokens": conversation.get_token_count(),
        })

        return message

    def transition_status(
        self,
        conversation_id: UUID,
        new_status: ConversationStatus
    ) -> bool:
        """
        Transition conversation to a new status.

        Args:
            conversation_id: Conversation UUID
            new_status: Target status

        Returns:
            True if successful, False if conversation not found
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return False

        old_status = conversation.status
        conversation.status = new_status
        conversation.updated_at = datetime.now(timezone.utc)

        logger.info({
            "event": "status_transition",
            "conversation_id": str(conversation_id),
            "old_status": old_status,
            "new_status": new_status.value,
        })

        return True

    def get_context_for_llm(
        self,
        conversation_id: UUID,
        max_tokens: int = 4000
    ) -> List[Dict[str, str]]:
        """
        Get conversation context formatted for LLM.

        Args:
            conversation_id: Conversation UUID
            max_tokens: Maximum tokens to include

        Returns:
            List of messages in LLM format [{"role": ..., "content": ...}]
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return []

        context = []
        total_tokens = 0

        # Add messages from newest to oldest until limit
        for message in reversed(conversation.messages):
            if total_tokens + message.token_count > max_tokens:
                break

            context.insert(0, {
                "role": message.role.value if isinstance(message.role, MessageRole) else message.role,
                "content": message.content,
            })
            total_tokens += message.token_count

        return context

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text (rough: 4 chars per token).

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        return max(1, len(text) // 4)

    def get_active_conversations(self) -> List[ConversationState]:
        """
        Get all active conversations.

        Returns:
            List of active ConversationState instances
        """
        return [
            conv for conv in self._conversations.values()
            if conv.status == ConversationStatus.ACTIVE
        ]
