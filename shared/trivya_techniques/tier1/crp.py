"""
PARWA CRP (Contextual Response Processing).

CRP is a Tier 1 technique that processes and compresses responses
to maintain conversation context efficiency. It works with the GSD
engine for context window management.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger
from shared.gsd_engine.compression import ContextCompressor
from shared.gsd_engine.state_schema import ConversationState, MessageRole

logger = get_logger(__name__)


class CRPResult(BaseModel):
    """
    Result from CRP processing.
    """
    original_response: str
    processed_response: str
    was_compressed: bool = False
    original_tokens: int = Field(default=0)
    processed_tokens: int = Field(default=0)
    compression_ratio: float = Field(default=1.0)
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class CRPConfig(BaseModel):
    """
    Configuration for CRP.
    """
    max_response_tokens: int = Field(default=500, ge=50, le=4000)
    compress_threshold: float = Field(default=0.8, ge=0.5, le=1.0)
    preserve_key_info: bool = Field(default=True)
    summarize_long_responses: bool = Field(default=True)
    min_response_length: int = Field(default=20, ge=10)

    model_config = ConfigDict(use_enum_values=True)


class CRP:
    """
    CRP - Contextual Response Processing.

    Tier 1 technique that processes and optimizes responses
    for efficient context window usage.

    Features:
    - Response compression when needed
    - Key information preservation
    - Token budget management
    - Integration with GSD compression
    - Response quality optimization
    """

    # Key phrases to preserve during compression
    PRESERVE_PHRASES = [
        "refund", "cancel", "escalate", "manager", "complaint",
        "approved", "denied", "pending", "processed", "failed",
        "important", "urgent", "immediately", "deadline",
        "policy", "terms", "agreement", "requirement"
    ]

    def __init__(
        self,
        compressor: Optional[ContextCompressor] = None,
        config: Optional[CRPConfig] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize CRP.

        Args:
            compressor: ContextCompressor instance
            config: CRP configuration
            company_id: Company UUID for scoping
        """
        self.config = config or CRPConfig()
        self.company_id = company_id
        self.compressor = compressor or ContextCompressor()

        # Performance tracking
        self._responses_processed = 0
        self._total_compressions = 0
        self._total_tokens_saved = 0

        logger.info({
            "event": "crp_initialized",
            "company_id": str(company_id) if company_id else None,
            "max_response_tokens": self.config.max_response_tokens,
        })

    def process(
        self,
        response: str,
        context_tokens: int = 0,
        max_context_tokens: int = 4000
    ) -> CRPResult:
        """
        Process a response for optimal context usage.

        Args:
            response: Original response text
            context_tokens: Current context token count
            max_context_tokens: Maximum context window size

        Returns:
            CRPResult with processed response

        Raises:
            ValueError: If response is empty
        """
        if not response or not response.strip():
            raise ValueError("Response cannot be empty")

        start_time = datetime.now()
        response = response.strip()

        # Estimate tokens
        original_tokens = self._estimate_tokens(response)

        # Determine if compression needed
        context_usage = context_tokens / max_context_tokens if max_context_tokens > 0 else 0

        if (
            original_tokens > self.config.max_response_tokens
            or context_usage > self.config.compress_threshold
        ):
            processed = self._compress_response(response, original_tokens)
            was_compressed = True
        else:
            processed = response
            was_compressed = False

        processed_tokens = self._estimate_tokens(processed)

        # Calculate compression ratio
        compression_ratio = processed_tokens / original_tokens if original_tokens > 0 else 1.0

        result = CRPResult(
            original_response=response,
            processed_response=processed,
            was_compressed=was_compressed,
            original_tokens=original_tokens,
            processed_tokens=processed_tokens,
            compression_ratio=compression_ratio,
            processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
        )

        # Update stats
        self._responses_processed += 1
        if was_compressed:
            self._total_compressions += 1
            self._total_tokens_saved += original_tokens - processed_tokens

        logger.info({
            "event": "crp_processed",
            "was_compressed": was_compressed,
            "original_tokens": original_tokens,
            "processed_tokens": processed_tokens,
            "compression_ratio": f"{compression_ratio:.2%}",
        })

        return result

    def process_for_conversation(
        self,
        response: str,
        conversation: ConversationState,
        max_tokens: int = 4000
    ) -> CRPResult:
        """
        Process response considering conversation state.

        Args:
            response: Response text
            conversation: Current conversation state
            max_tokens: Maximum context tokens

        Returns:
            CRPResult with processed response
        """
        context_tokens = conversation.get_token_count()
        return self.process(response, context_tokens, max_tokens)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get CRP statistics.

        Returns:
            Dict with CRP stats
        """
        return {
            "responses_processed": self._responses_processed,
            "total_compressions": self._total_compressions,
            "compression_rate": (
                self._total_compressions / self._responses_processed
                if self._responses_processed > 0 else 0
            ),
            "total_tokens_saved": self._total_tokens_saved,
            "average_tokens_saved": (
                self._total_tokens_saved / self._total_compressions
                if self._total_compressions > 0 else 0
            ),
            "config": self.config.model_dump(),
        }

    def _compress_response(
        self,
        response: str,
        original_tokens: int
    ) -> str:
        """
        Compress response while preserving key information.

        Args:
            response: Original response
            original_tokens: Estimated token count

        Returns:
            Compressed response
        """
        # Extract key sentences containing important phrases
        sentences = self._split_sentences(response)
        key_sentences = []
        other_sentences = []

        for sentence in sentences:
            if self._contains_key_phrase(sentence):
                key_sentences.append(sentence)
            else:
                other_sentences.append(sentence)

        # Calculate target length
        target_ratio = 0.6  # Aim for 60% of original
        target_chars = int(len(response) * target_ratio)

        # Build compressed response
        compressed_parts = []

        # Always include key sentences
        for sentence in key_sentences:
            compressed_parts.append(sentence)

        # Add other sentences until we hit target
        current_length = sum(len(s) for s in compressed_parts)
        for sentence in other_sentences:
            if current_length + len(sentence) <= target_chars:
                compressed_parts.append(sentence)
                current_length += len(sentence)
            else:
                break

        compressed = " ".join(compressed_parts)

        # Ensure minimum length
        if len(compressed) < self.config.min_response_length:
            # Truncate original to meet target
            compressed = response[:target_chars].rsplit(" ", 1)[0] + "..."

        return compressed

    def _split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        # Simple sentence splitting
        sentences = []
        current = []

        for char in text:
            current.append(char)
            if char in ".!?":
                sentences.append("".join(current).strip())
                current = []

        # Add remaining text
        if current:
            sentences.append("".join(current).strip())

        return [s for s in sentences if s]

    def _contains_key_phrase(self, text: str) -> bool:
        """
        Check if text contains key phrases to preserve.

        Args:
            text: Text to check

        Returns:
            True if contains key phrase
        """
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in self.PRESERVE_PHRASES)

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return max(1, len(text) // 4)

    def should_compress(
        self,
        response: str,
        context_tokens: int,
        max_tokens: int = 4000
    ) -> bool:
        """
        Determine if response should be compressed.

        Args:
            response: Response text
            context_tokens: Current context tokens
            max_tokens: Maximum context tokens

        Returns:
            True if compression recommended
        """
        response_tokens = self._estimate_tokens(response)
        total_tokens = context_tokens + response_tokens

        # Check response size
        if response_tokens > self.config.max_response_tokens:
            return True

        # Check context usage
        context_usage = total_tokens / max_tokens if max_tokens > 0 else 0
        return context_usage > self.config.compress_threshold
