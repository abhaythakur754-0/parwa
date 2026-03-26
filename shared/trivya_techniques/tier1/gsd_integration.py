"""
PARWA GSD Integration for Tier 1.

Integrates GSD State Engine with TRIVYA Tier 1 techniques,
enabling conversation-aware processing and context management.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger
from shared.gsd_engine.state_engine import StateEngine
from shared.gsd_engine.state_schema import (
    ConversationState,
    ConversationStatus,
    MessageRole,
    ContextHealthStatus,
)
from shared.gsd_engine.context_health import ContextHealthMonitor
from shared.gsd_engine.compression import ContextCompressor
from shared.trivya_techniques.tier1.clara import CLARA, CLARAResult
from shared.trivya_techniques.tier1.crp import CRP, CRPResult

logger = get_logger(__name__)


class GSDIntegrationResult(BaseModel):
    """
    Result from GSD Integration processing.
    """
    conversation_id: UUID
    query: str
    clara_result: Optional[CLARAResult] = None
    crp_result: Optional[CRPResult] = None
    context_health: str = "healthy"
    should_compress: bool = False
    should_escalate: bool = False
    turn_count: int = 0
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class GSDIntegrationConfig(BaseModel):
    """
    Configuration for GSD Integration.
    """
    max_turns_before_escalation: int = Field(default=20, ge=5, le=50)
    compression_threshold_turns: int = Field(default=10, ge=5, le=30)
    max_context_tokens: int = Field(default=4000, ge=1000, le=8000)
    auto_compress_enabled: bool = Field(default=True)
    escalation_on_critical_health: bool = Field(default=True)

    model_config = ConfigDict(use_enum_values=True)


class GSDIntegration:
    """
    GSD Integration for Tier 1.

    Integrates GSD State Engine with TRIVYA Tier 1 techniques
    for conversation-aware AI processing.

    Features:
    - Conversation state management
    - Context health monitoring
    - Automatic compression triggers
    - Escalation detection
    - Tier 1 technique coordination
    """

    def __init__(
        self,
        state_engine: Optional[StateEngine] = None,
        health_monitor: Optional[ContextHealthMonitor] = None,
        compressor: Optional[ContextCompressor] = None,
        clara: Optional[CLARA] = None,
        crp: Optional[CRP] = None,
        config: Optional[GSDIntegrationConfig] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize GSD Integration.

        Args:
            state_engine: StateEngine instance
            health_monitor: ContextHealthMonitor instance
            compressor: ContextCompressor instance
            clara: CLARA instance
            crp: CRP instance
            config: GSD Integration configuration
            company_id: Company UUID for scoping
        """
        self.config = config or GSDIntegrationConfig()
        self.company_id = company_id

        # Initialize components
        self.state_engine = state_engine or StateEngine(
            company_id=company_id,
            max_tokens=self.config.max_context_tokens
        )
        self.health_monitor = health_monitor or ContextHealthMonitor(
            max_tokens=self.config.max_context_tokens,
            max_turns=self.config.max_turns_before_escalation
        )
        self.compressor = compressor or ContextCompressor()
        self.clara = clara or CLARA(company_id=company_id)
        self.crp = crp or CRP(company_id=company_id)

        # Processing stats
        self._queries_processed = 0
        self._compressions_triggered = 0
        self._escalations_triggered = 0

        logger.info({
            "event": "gsd_integration_initialized",
            "company_id": str(company_id) if company_id else None,
            "max_turns": self.config.max_turns_before_escalation,
        })

    def process_query(
        self,
        conversation_id: UUID,
        query: str,
        perform_retrieval: bool = True
    ) -> GSDIntegrationResult:
        """
        Process a query with GSD integration.

        Args:
            conversation_id: Conversation UUID
            query: User query text
            perform_retrieval: Whether to perform CLARA retrieval

        Returns:
            GSDIntegrationResult with processing results

        Raises:
            ValueError: If conversation not found or query empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()
        query = query.strip()

        # Get conversation
        conversation = self.state_engine.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Add user message
        self.state_engine.add_message(
            conversation_id,
            MessageRole.USER,
            query
        )

        # Check context health
        health = self.health_monitor.check_health(conversation)

        # Perform CLARA retrieval if requested
        clara_result = None
        if perform_retrieval:
            clara_result = self.clara.retrieve(query)

        # Determine if compression needed
        should_compress = (
            self.config.auto_compress_enabled
            and self.health_monitor.should_compress(conversation)
        )

        # Determine if escalation needed (use configured threshold)
        should_escalate = (
            conversation.context.turn_count >= self.config.max_turns_before_escalation
            or (
                self.config.escalation_on_critical_health
                and health.health_status == ContextHealthStatus.CRITICAL
            )
        )

        result = GSDIntegrationResult(
            conversation_id=conversation_id,
            query=query,
            clara_result=clara_result,
            context_health=health.health_status.value if hasattr(health.health_status, 'value') else health.health_status,
            should_compress=should_compress,
            should_escalate=should_escalate,
            turn_count=conversation.context.turn_count,
            processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
        )

        # Update stats
        self._queries_processed += 1
        if should_compress:
            self._compressions_triggered += 1
        if should_escalate:
            self._escalations_triggered += 1

        logger.info({
            "event": "gsd_integration_query_processed",
            "conversation_id": str(conversation_id),
            "turn_count": result.turn_count,
            "context_health": result.context_health,
            "should_compress": should_compress,
            "should_escalate": should_escalate,
        })

        return result

    def process_response(
        self,
        conversation_id: UUID,
        response: str
    ) -> GSDIntegrationResult:
        """
        Process a response with GSD integration.

        Args:
            conversation_id: Conversation UUID
            response: Assistant response text

        Returns:
            GSDIntegrationResult with CRP processing

        Raises:
            ValueError: If conversation not found or response empty
        """
        if not response or not response.strip():
            raise ValueError("Response cannot be empty")

        start_time = datetime.now()
        response = response.strip()

        # Get conversation
        conversation = self.state_engine.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Process with CRP
        crp_result = self.crp.process_for_conversation(
            response,
            conversation,
            self.config.max_context_tokens
        )

        # Add processed response to conversation
        self.state_engine.add_message(
            conversation_id,
            MessageRole.ASSISTANT,
            crp_result.processed_response
        )

        # Compress if needed
        if crp_result.was_compressed:
            conversation = self._maybe_compress_conversation(conversation)

        result = GSDIntegrationResult(
            conversation_id=conversation_id,
            query="",
            crp_result=crp_result,
            context_health=conversation.context.health_status.value if hasattr(conversation.context.health_status, 'value') else conversation.context.health_status,
            processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
        )

        logger.info({
            "event": "gsd_integration_response_processed",
            "conversation_id": str(conversation_id),
            "was_compressed": crp_result.was_compressed,
            "compression_ratio": f"{crp_result.compression_ratio:.2%}",
        })

        return result

    def create_conversation(
        self,
        customer_id: Optional[str] = None,
        channel: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationState:
        """
        Create a new conversation.

        Args:
            customer_id: Customer identifier
            channel: Communication channel
            metadata: Additional metadata

        Returns:
            Created ConversationState
        """
        conversation = self.state_engine.create_conversation(
            customer_id=customer_id,
            channel=channel,
            metadata=metadata
        )

        logger.info({
            "event": "gsd_integration_conversation_created",
            "conversation_id": str(conversation.id),
            "customer_id": customer_id,
        })

        return conversation

    def get_conversation(
        self,
        conversation_id: UUID
    ) -> Optional[ConversationState]:
        """
        Get a conversation by ID.

        Args:
            conversation_id: Conversation UUID

        Returns:
            ConversationState if found, None otherwise
        """
        return self.state_engine.get_conversation(conversation_id)

    def get_context_for_llm(
        self,
        conversation_id: UUID,
        max_tokens: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Get conversation context formatted for LLM.

        Args:
            conversation_id: Conversation UUID
            max_tokens: Maximum tokens to include

        Returns:
            List of messages in LLM format
        """
        return self.state_engine.get_context_for_llm(
            conversation_id,
            max_tokens or self.config.max_context_tokens
        )

    def trigger_escalation(
        self,
        conversation_id: UUID,
        reason: str = "manual"
    ) -> bool:
        """
        Trigger escalation for a conversation.

        Args:
            conversation_id: Conversation UUID
            reason: Escalation reason

        Returns:
            True if successful
        """
        conversation = self.state_engine.get_conversation(conversation_id)
        if not conversation:
            return False

        self.state_engine.transition_status(
            conversation_id,
            ConversationStatus.ESCALATED
        )

        self._escalations_triggered += 1

        logger.warning({
            "event": "gsd_integration_escalation_triggered",
            "conversation_id": str(conversation_id),
            "reason": reason,
            "turn_count": conversation.context.turn_count,
        })

        return True

    def get_stats(self) -> Dict[str, Any]:
        """
        Get GSD Integration statistics.

        Returns:
            Dict with stats
        """
        return {
            "queries_processed": self._queries_processed,
            "compressions_triggered": self._compressions_triggered,
            "escalations_triggered": self._escalations_triggered,
            "compression_rate": (
                self._compressions_triggered / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "escalation_rate": (
                self._escalations_triggered / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "config": self.config.model_dump(),
            "state_engine_stats": {
                "active_conversations": len(self.state_engine.get_active_conversations()),
            },
            "clara_stats": self.clara.get_stats(),
            "crp_stats": self.crp.get_stats(),
        }

    def _maybe_compress_conversation(
        self,
        conversation: ConversationState
    ) -> ConversationState:
        """
        Compress conversation if needed.

        Args:
            conversation: ConversationState to potentially compress

        Returns:
            ConversationState (possibly compressed)
        """
        if self.health_monitor.should_compress(conversation):
            compressed = self.compressor.compress(conversation)
            self._compressions_triggered += 1

            logger.info({
                "event": "gsd_integration_conversation_compressed",
                "conversation_id": str(conversation.id),
                "original_tokens": compressed.context.total_tokens,
            })

            return compressed

        return conversation
