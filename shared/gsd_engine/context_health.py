"""
PARWA Context Health Monitor.

Monitors conversation context health and provides
warnings and recommendations for context management.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone

from shared.core_functions.logger import get_logger
from shared.gsd_engine.state_schema import (
    ConversationState,
    ContextHealthStatus,
    ContextMetadata,
)

logger = get_logger(__name__)


class ContextHealthMonitor:
    """
    Context Health Monitor for GSD conversations.

    Monitors:
    - Token count vs context window limits
    - Message count vs maximum
    - Turn count for escalation detection
    - Stale conversations
    """

    # Thresholds
    TOKEN_WARNING_THRESHOLD = 0.75  # 75% of max tokens
    TOKEN_CRITICAL_THRESHOLD = 0.90  # 90% of max tokens
    MESSAGE_WARNING_THRESHOLD = 0.70  # 70% of max messages
    MESSAGE_CRITICAL_THRESHOLD = 0.85  # 85% of max messages
    TURN_WARNING_THRESHOLD = 15  # Warn at 15 turns
    TURN_ESCALATION_THRESHOLD = 20  # Suggest escalation at 20 turns

    def __init__(
        self,
        max_tokens: int = 4000,
        max_messages: int = 50,
        max_turns: int = 20
    ) -> None:
        """
        Initialize Context Health Monitor.

        Args:
            max_tokens: Maximum tokens in context window
            max_messages: Maximum messages per conversation
            max_turns: Maximum turns before escalation suggested
        """
        self.max_tokens = max_tokens
        self.max_messages = max_messages
        self.max_turns = max_turns

    def check_health(self, conversation: ConversationState) -> ContextMetadata:
        """
        Check health of a conversation's context.

        Args:
            conversation: ConversationState to check

        Returns:
            Updated ContextMetadata with health status
        """
        token_count = conversation.get_token_count()
        message_count = len(conversation.messages)
        turn_count = conversation.context.turn_count

        # Determine health status
        health_status = ContextHealthStatus.HEALTHY
        warnings = []

        # Check token health
        token_ratio = token_count / self.max_tokens if self.max_tokens > 0 else 0
        if token_ratio >= self.TOKEN_CRITICAL_THRESHOLD:
            health_status = ContextHealthStatus.CRITICAL
            warnings.append(f"Token count at {token_ratio:.0%} of limit")
        elif token_ratio >= self.TOKEN_WARNING_THRESHOLD:
            health_status = ContextHealthStatus.WARNING
            warnings.append(f"Token count at {token_ratio:.0%} of limit")

        # Check message count health
        message_ratio = message_count / self.max_messages if self.max_messages > 0 else 0
        if message_ratio >= self.MESSAGE_CRITICAL_THRESHOLD:
            health_status = ContextHealthStatus.CRITICAL
            warnings.append(f"Message count at {message_ratio:.0%} of limit")
        elif message_ratio >= self.MESSAGE_WARNING_THRESHOLD:
            if health_status == ContextHealthStatus.HEALTHY:
                health_status = ContextHealthStatus.WARNING
            warnings.append(f"Message count at {message_ratio:.0%} of limit")

        # Check turn count
        if turn_count >= self.TURN_ESCALATION_THRESHOLD:
            warnings.append(f"Turn count ({turn_count}) suggests escalation")
        elif turn_count >= self.TURN_WARNING_THRESHOLD:
            warnings.append(f"Turn count ({turn_count}) approaching limit")

        # Update context metadata
        conversation.context.health_status = health_status
        conversation.context.total_tokens = token_count
        conversation.context.message_count = message_count
        conversation.context.turn_count = turn_count
        conversation.context.last_updated = datetime.now(timezone.utc)

        if warnings:
            logger.warning({
                "event": "context_health_warning",
                "conversation_id": str(conversation.id),
                "health_status": health_status.value,
                "warnings": warnings,
            })

        return conversation.context

    def get_recommendations(self, conversation: ConversationState) -> List[str]:
        """
        Get recommendations for context management.

        Args:
            conversation: ConversationState to analyze

        Returns:
            List of recommendation strings
        """
        recommendations = []

        token_count = conversation.get_token_count()
        turn_count = conversation.context.turn_count

        # Token-based recommendations
        token_ratio = token_count / self.max_tokens if self.max_tokens > 0 else 0
        if token_ratio >= self.TOKEN_WARNING_THRESHOLD:
            recommendations.append("Consider compressing conversation history")

        if token_ratio >= self.TOKEN_CRITICAL_THRESHOLD:
            recommendations.append("Immediate compression or summarization required")

        # Turn-based recommendations
        if turn_count >= self.TURN_WARNING_THRESHOLD:
            recommendations.append("Consider escalating to human agent")

        if turn_count >= self.TURN_ESCALATION_THRESHOLD:
            recommendations.append("Escalation strongly recommended")

        return recommendations

    def should_compress(self, conversation: ConversationState) -> bool:
        """
        Check if conversation should be compressed.

        Args:
            conversation: ConversationState to check

        Returns:
            True if compression recommended
        """
        token_count = conversation.get_token_count()
        token_ratio = token_count / self.max_tokens if self.max_tokens > 0 else 0

        return token_ratio >= self.TOKEN_WARNING_THRESHOLD

    def should_escalate(self, conversation: ConversationState) -> bool:
        """
        Check if conversation should be escalated.

        Args:
            conversation: ConversationState to check

        Returns:
            True if escalation recommended
        """
        return conversation.context.turn_count >= self.TURN_ESCALATION_THRESHOLD
