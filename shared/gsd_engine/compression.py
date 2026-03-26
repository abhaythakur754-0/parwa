"""
PARWA Context Compression.

Compresses conversation history to reduce token count
while preserving essential context.
"""
from typing import List, Dict, Any, Optional
from uuid import UUID

from shared.core_functions.logger import get_logger
from shared.gsd_engine.state_schema import (
    ConversationState,
    Message,
    MessageRole,
)

logger = get_logger(__name__)


class ContextCompressor:
    """
    Context Compressor for conversation history.

    Strategies:
    - Summarize older messages
    - Remove redundant messages
    - Keep recent context intact
    """

    TARGET_COMPRESSION_RATIO = 0.15  # Target: 15% of original tokens
    MIN_MESSAGES_TO_KEEP = 4  # Always keep last 4 messages
    SYSTEM_MESSAGE_PRIORITY = True  # Never remove system messages

    def __init__(
        self,
        target_ratio: float = TARGET_COMPRESSION_RATIO,
        min_messages: int = MIN_MESSAGES_TO_KEEP
    ) -> None:
        """
        Initialize Context Compressor.

        Args:
            target_ratio: Target compression ratio (0.15 = 15%)
            min_messages: Minimum messages to preserve
        """
        self.target_ratio = target_ratio
        self.min_messages = min_messages

    def compress(
        self,
        conversation: ConversationState,
        target_tokens: Optional[int] = None
    ) -> ConversationState:
        """
        Compress conversation history.

        Args:
            conversation: ConversationState to compress
            target_tokens: Target token count (defaults to 15% of current)

        Returns:
            ConversationState with compressed history
        """
        current_tokens = conversation.get_token_count()

        if target_tokens is None:
            target_tokens = int(current_tokens * self.target_ratio)

        # If already under target, no compression needed
        if current_tokens <= target_tokens:
            logger.info({
                "event": "compression_skipped",
                "reason": "already_under_target",
                "current_tokens": current_tokens,
                "target_tokens": target_tokens,
            })
            return conversation

        # Calculate how many tokens to remove
        tokens_to_remove = current_tokens - target_tokens

        # Get messages to potentially compress (exclude recent)
        compressible_messages = conversation.messages[:-self.min_messages]
        recent_messages = conversation.messages[-self.min_messages:]

        if not compressible_messages:
            logger.warning({
                "event": "compression_skipped",
                "reason": "insufficient_messages",
                "message_count": len(conversation.messages),
                "min_to_keep": self.min_messages,
            })
            return conversation

        # Create summary of older messages
        summary = self._create_summary(compressible_messages)
        summary_tokens = self._estimate_tokens(summary)

        # Build new message list
        new_messages = []

        # Add summary as system message
        if summary:
            summary_msg = Message(
                role=MessageRole.SYSTEM,
                content=f"[Previous conversation summary: {summary}]",
                token_count=summary_tokens
            )
            new_messages.append(summary_msg)

        # Add recent messages
        new_messages.extend(recent_messages)

        # Update conversation
        conversation.messages = new_messages
        conversation.context.total_tokens = sum(m.token_count for m in new_messages)
        conversation.context.message_count = len(new_messages)

        new_tokens = conversation.get_token_count()
        compression_ratio = new_tokens / current_tokens if current_tokens > 0 else 0

        logger.info({
            "event": "compression_complete",
            "original_tokens": current_tokens,
            "new_tokens": new_tokens,
            "compression_ratio": f"{compression_ratio:.2%}",
            "messages_removed": len(compressible_messages),
            "summary_added": bool(summary),
        })

        return conversation

    def _create_summary(self, messages: List[Message]) -> str:
        """
        Create a summary of messages.

        Args:
            messages: Messages to summarize

        Returns:
            Summary string
        """
        if not messages:
            return ""

        # Simple summarization: extract key points
        user_messages = [m for m in messages if m.role == MessageRole.USER]
        assistant_messages = [m for m in messages if m.role == MessageRole.ASSISTANT]

        summary_parts = []

        if user_messages:
            user_topics = self._extract_topics([m.content for m in user_messages])
            if user_topics:
                summary_parts.append(f"User asked about: {', '.join(user_topics[:3])}")

        if assistant_messages:
            assistant_actions = self._extract_topics([m.content for m in assistant_messages])
            if assistant_actions:
                summary_parts.append(f"Assistant addressed: {', '.join(assistant_actions[:3])}")

        return "; ".join(summary_parts)

    def _extract_topics(self, texts: List[str]) -> List[str]:
        """
        Extract key topics from texts.

        Args:
            texts: List of text strings

        Returns:
            List of topic keywords
        """
        # Simple keyword extraction
        keywords = []
        common_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                       "being", "have", "has", "had", "do", "does", "did", "will",
                       "would", "could", "should", "may", "might", "must", "shall",
                       "can", "need", "to", "of", "in", "for", "on", "with", "at",
                       "by", "from", "as", "into", "through", "during", "before",
                       "after", "above", "below", "between", "under", "again",
                       "further", "then", "once", "here", "there", "when", "where",
                       "why", "how", "all", "each", "few", "more", "most", "other",
                       "some", "such", "no", "nor", "not", "only", "own", "same",
                       "so", "than", "too", "very", "just", "and", "but", "if",
                       "or", "because", "until", "while", "this", "that", "these",
                       "those", "i", "me", "my", "myself", "we", "our", "ours",
                       "you", "your", "yours", "he", "him", "his", "she", "her",
                       "hers", "it", "its", "they", "them", "their", "what", "which",
                       "who", "whom", "get", "want", "know", "help", "thank", "thanks"}

        for text in texts:
            words = text.lower().split()
            for word in words:
                clean_word = ''.join(c for c in word if c.isalnum())
                if clean_word and clean_word not in common_words and len(clean_word) > 3:
                    if clean_word not in keywords:
                        keywords.append(clean_word)

        return keywords[:5]

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return max(1, len(text) // 4)

    def get_compression_stats(
        self,
        conversation: ConversationState
    ) -> Dict[str, Any]:
        """
        Get compression statistics for a conversation.

        Args:
            conversation: ConversationState to analyze

        Returns:
            Dict with compression statistics
        """
        current_tokens = conversation.get_token_count()
        target_tokens = int(current_tokens * self.target_ratio)

        return {
            "current_tokens": current_tokens,
            "target_tokens": target_tokens,
            "potential_reduction": current_tokens - target_tokens,
            "message_count": len(conversation.messages),
            "can_compress": current_tokens > target_tokens and len(conversation.messages) > self.min_messages,
        }
