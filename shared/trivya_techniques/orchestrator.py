"""
PARWA TRIVYA Tier 1 Orchestrator.

Orchestrates all Tier 1 techniques, ensuring they fire on every query.
Tier 1 is the foundation layer that provides grounded, contextual responses.
"""
from typing import Optional, Dict, Any, List, Callable
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger
from shared.smart_router.router import SmartRouter, AITier
from shared.trivya_techniques.tier1.clara import CLARA, CLARAResult, CLARAConfig
from shared.trivya_techniques.tier1.crp import CRP, CRPResult, CRPConfig
from shared.trivya_techniques.tier1.gsd_integration import (
    GSDIntegration,
    GSDIntegrationResult,
    GSDIntegrationConfig,
)

logger = get_logger(__name__)
settings = get_settings()


class ProcessingStage(str, Enum):
    """Processing stages for T1 pipeline."""
    INITIALIZED = "initialized"
    CONTEXT_RETRIEVED = "context_retrieved"
    QUERY_ROUTED = "query_routed"
    RESPONSE_PROCESSED = "response_processed"
    COMPLETED = "completed"
    FAILED = "failed"


class T1OrchestratorResult(BaseModel):
    """
    Result from T1 Orchestrator processing.
    """
    query: str
    conversation_id: Optional[UUID] = None
    stage: str = ProcessingStage.INITIALIZED.value
    clara_result: Optional[CLARAResult] = None
    routing_metadata: Optional[Dict[str, Any]] = None
    gsd_result: Optional[GSDIntegrationResult] = None
    crp_result: Optional[CRPResult] = None
    selected_tier: str = AITier.MEDIUM.value
    context: str = ""
    should_escalate: bool = False
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class T1OrchestratorConfig(BaseModel):
    """
    Configuration for T1 Orchestrator.
    """
    always_use_clara: bool = Field(default=True)
    use_smart_router: bool = Field(default=True)
    use_gsd_integration: bool = Field(default=True)
    use_crp: bool = Field(default=True)
    fallback_tier: str = Field(default=AITier.MEDIUM.value)
    log_all_stages: bool = Field(default=True)

    model_config = ConfigDict(use_enum_values=True)


class T1Orchestrator:
    """
    Tier 1 Orchestrator for TRIVYA.

    Ensures all Tier 1 techniques fire on every query in the correct order.
    Tier 1 provides grounded, contextual, and efficient AI responses.

    Processing Pipeline:
    1. CLARA - Retrieve relevant context from knowledge base
    2. Smart Router - Determine AI tier based on complexity
    3. GSD Integration - Manage conversation state
    4. CRP - Process and optimize response

    CRITICAL: Tier 1 ALWAYS fires on every query to provide grounding.
    """

    def __init__(
        self,
        clara: Optional[CLARA] = None,
        crp: Optional[CRP] = None,
        gsd_integration: Optional[GSDIntegration] = None,
        smart_router: Optional[SmartRouter] = None,
        embedding_fn: Optional[Callable[[str], List[float]]] = None,
        llm_client: Optional[Any] = None,
        config: Optional[T1OrchestratorConfig] = None,
        company_id: Optional[UUID] = None,
        company_settings: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize T1 Orchestrator.

        Args:
            clara: CLARA instance for retrieval
            crp: CRP instance for response processing
            gsd_integration: GSD Integration instance
            smart_router: SmartRouter instance for tier selection
            embedding_fn: Function to generate embeddings
            llm_client: LLM client for generation
            config: Orchestrator configuration
            company_id: Company UUID for scoping
            company_settings: Company-specific settings
        """
        self.config = config or T1OrchestratorConfig()
        self.company_id = company_id
        self.company_settings = company_settings or {}
        self.embedding_fn = embedding_fn
        self.llm_client = llm_client

        # Initialize components
        self.clara = clara or CLARA(
            embedding_fn=embedding_fn,
            llm_client=llm_client,
            company_id=company_id,
            config=CLARAConfig(use_hyde=True)
        )

        self.crp = crp or CRP(
            company_id=company_id
        )

        self.gsd_integration = gsd_integration or GSDIntegration(
            clara=self.clara,
            crp=self.crp,
            company_id=company_id
        )

        self.smart_router = smart_router or SmartRouter(
            company_id=company_id,
            company_settings=company_settings
        )

        # Processing stats
        self._queries_processed = 0
        self._total_processing_time = 0.0
        self._errors_encountered = 0

        logger.info({
            "event": "t1_orchestrator_initialized",
            "company_id": str(company_id) if company_id else None,
            "always_use_clara": self.config.always_use_clara,
        })

    def process(
        self,
        query: str,
        conversation_id: Optional[UUID] = None,
        customer_tier: Optional[str] = None,
        budget_remaining: Optional[float] = None
    ) -> T1OrchestratorResult:
        """
        Process a query through the T1 pipeline.

        TIER 1 ALWAYS FIRES - this is the foundation for all queries.

        Args:
            query: User query text
            conversation_id: Existing conversation ID (creates new if None)
            customer_tier: Customer subscription tier
            budget_remaining: Remaining AI budget

        Returns:
            T1OrchestratorResult with all processing results

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()
        query = query.strip()

        result = T1OrchestratorResult(
            query=query,
            conversation_id=conversation_id,
            stage=ProcessingStage.INITIALIZED.value
        )

        try:
            # Step 1: CLARA retrieval (ALWAYS runs)
            if self.config.always_use_clara:
                result = self._run_clara(query, result)

            # Step 2: Smart Router tier selection
            if self.config.use_smart_router:
                result = self._run_smart_router(
                    query, customer_tier, budget_remaining, result
                )

            # Step 3: GSD Integration
            if self.config.use_gsd_integration and conversation_id:
                result = self._run_gsd_integration(
                    query, conversation_id, result
                )

            result.stage = ProcessingStage.COMPLETED.value

        except Exception as e:
            result.stage = ProcessingStage.FAILED.value
            result.metadata["error"] = str(e)
            self._errors_encountered += 1

            logger.error({
                "event": "t1_orchestrator_failed",
                "error": str(e),
                "stage": result.stage,
            })

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        self._queries_processed += 1
        self._total_processing_time += result.processing_time_ms

        if self.config.log_all_stages:
            logger.info({
                "event": "t1_orchestrator_completed",
                "query_length": len(query),
                "stage": result.stage,
                "selected_tier": result.selected_tier,
                "processing_time_ms": result.processing_time_ms,
                "should_escalate": result.should_escalate,
            })

        return result

    def process_with_response(
        self,
        query: str,
        response: str,
        conversation_id: Optional[UUID] = None
    ) -> T1OrchestratorResult:
        """
        Process query and response through T1 pipeline.

        Args:
            query: User query text
            response: Assistant response text
            conversation_id: Conversation ID

        Returns:
            T1OrchestratorResult with full processing
        """
        # Process query first
        result = self.process(query, conversation_id=conversation_id)

        # Process response through GSD and CRP
        if self.config.use_gsd_integration and conversation_id:
            try:
                gsd_response = self.gsd_integration.process_response(
                    conversation_id,
                    response
                )
                result.crp_result = gsd_response.crp_result
                result.stage = ProcessingStage.RESPONSE_PROCESSED.value
            except Exception as e:
                logger.error({
                    "event": "t1_response_processing_failed",
                    "error": str(e),
                })

        return result

    def create_conversation(
        self,
        customer_id: Optional[str] = None,
        channel: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Create a new conversation.

        Args:
            customer_id: Customer identifier
            channel: Communication channel
            metadata: Additional metadata

        Returns:
            UUID of created conversation
        """
        conversation = self.gsd_integration.create_conversation(
            customer_id=customer_id,
            channel=channel,
            metadata=metadata
        )
        return conversation.id

    def get_conversation_context(
        self,
        conversation_id: UUID
    ) -> List[Dict[str, str]]:
        """
        Get conversation context for LLM.

        Args:
            conversation_id: Conversation UUID

        Returns:
            List of messages in LLM format
        """
        return self.gsd_integration.get_context_for_llm(conversation_id)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get orchestrator statistics.

        Returns:
            Dict with stats
        """
        return {
            "queries_processed": self._queries_processed,
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "errors_encountered": self._errors_encountered,
            "error_rate": (
                self._errors_encountered / self._queries_processed
                if self._queries_processed > 0 else 0
            ),
            "config": self.config.model_dump(),
            "clara_stats": self.clara.get_stats(),
            "crp_stats": self.crp.get_stats(),
            "gsd_stats": self.gsd_integration.get_stats(),
        }

    def _run_clara(
        self,
        query: str,
        result: T1OrchestratorResult
    ) -> T1OrchestratorResult:
        """
        Run CLARA retrieval.

        Args:
            query: User query
            result: Current result

        Returns:
            Updated result
        """
        try:
            clara_result = self.clara.retrieve(query)
            result.clara_result = clara_result
            result.context = clara_result.retrieved_context
            result.stage = ProcessingStage.CONTEXT_RETRIEVED.value

            if self.config.log_all_stages:
                logger.debug({
                    "event": "t1_clara_completed",
                    "relevance_score": clara_result.relevance_score,
                    "context_length": len(result.context),
                })

        except Exception as e:
            logger.warning({
                "event": "t1_clara_failed",
                "error": str(e),
            })
            # Continue with empty context

        return result

    def _run_smart_router(
        self,
        query: str,
        customer_tier: Optional[str],
        budget_remaining: Optional[float],
        result: T1OrchestratorResult
    ) -> T1OrchestratorResult:
        """
        Run Smart Router tier selection.

        Args:
            query: User query
            customer_tier: Customer tier
            budget_remaining: Budget remaining
            result: Current result

        Returns:
            Updated result
        """
        try:
            tier, routing_metadata = self.smart_router.route(
                query,
                customer_tier=customer_tier,
                budget_remaining=budget_remaining
            )

            result.selected_tier = tier.value
            result.routing_metadata = routing_metadata
            result.stage = ProcessingStage.QUERY_ROUTED.value

            if self.config.log_all_stages:
                logger.debug({
                    "event": "t1_router_completed",
                    "selected_tier": tier.value,
                    "complexity_score": routing_metadata.get("complexity_score"),
                })

        except Exception as e:
            logger.warning({
                "event": "t1_router_failed",
                "error": str(e),
            })
            # Use fallback tier
            result.selected_tier = self.config.fallback_tier

        return result

    def _run_gsd_integration(
        self,
        query: str,
        conversation_id: UUID,
        result: T1OrchestratorResult
    ) -> T1OrchestratorResult:
        """
        Run GSD Integration.

        Args:
            query: User query
            conversation_id: Conversation UUID
            result: Current result

        Returns:
            Updated result
        """
        try:
            gsd_result = self.gsd_integration.process_query(
                conversation_id,
                query,
                perform_retrieval=False  # CLARA already ran
            )

            result.gsd_result = gsd_result
            result.should_escalate = gsd_result.should_escalate
            result.conversation_id = conversation_id

            if self.config.log_all_stages:
                logger.debug({
                    "event": "t1_gsd_completed",
                    "turn_count": gsd_result.turn_count,
                    "should_escalate": gsd_result.should_escalate,
                })

        except Exception as e:
            logger.warning({
                "event": "t1_gsd_failed",
                "error": str(e),
            })

        return result
