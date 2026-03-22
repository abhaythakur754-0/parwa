"""
PARWA Junior Knowledge Update Workflow.

Handles knowledge base updates after resolution events.
Ensures that learnings from resolved tickets are captured
and added to the knowledge base for future reference.

PARWA Junior Features:
- Automatically extracts insights from resolved tickets
- Updates knowledge base with new FAQ entries
- Tracks update history and learning metrics
- Medium tier analysis for knowledge extraction
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from enum import Enum

from variants.parwa.config import ParwaConfig, get_parwa_config
from shared.knowledge_base.kb_manager import KnowledgeBaseManager, KnowledgeBaseConfig
from shared.core_functions.logger import get_logger
from shared.core_functions.config import get_settings

logger = get_logger(__name__)


class UpdateType(Enum):
    """Types of knowledge base updates."""
    FAQ_ADDITION = "faq_addition"           # New FAQ entry
    RESOLUTION_PATTERN = "resolution_pattern"  # Successful resolution pattern
    FEEDBACK_LEARNING = "feedback_learning"   # Learning from customer feedback
    ESCALATION_NOTE = "escalation_note"       # Notes from escalations
    POLICY_UPDATE = "policy_update"           # Policy clarification


class UpdateStatus(Enum):
    """Status of knowledge update."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class KnowledgeEntry:
    """Knowledge entry to be added to KB."""
    title: str
    content: str
    category: str
    tags: List[str] = field(default_factory=list)
    source_ticket_id: Optional[str] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeUpdateResult:
    """Result from knowledge update workflow."""
    success: bool
    update_id: Optional[str] = None
    update_type: UpdateType = UpdateType.FAQ_ADDITION
    status: UpdateStatus = UpdateStatus.PENDING
    document_id: Optional[str] = None
    entries_added: int = 0
    entries_skipped: int = 0
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class KnowledgeUpdateWorkflow:
    """
    Workflow for updating the knowledge base after resolution.

    This workflow is triggered after a ticket is resolved to capture
    any learnings that could help with future similar tickets.

    Features:
    - Extracts resolution patterns from successful resolutions
    - Creates FAQ entries from common questions
    - Tracks feedback for continuous improvement
    - Associates updates with source tickets

    Example:
        workflow = KnowledgeUpdateWorkflow()
        result = await workflow.execute({
            "ticket_id": "tkt_123",
            "resolution": "Refund processed successfully...",
            "customer_feedback": "positive",
            "resolution_type": "refund_approved"
        })
    """

    def __init__(
        self,
        parwa_config: Optional[ParwaConfig] = None,
        kb_manager: Optional[KnowledgeBaseManager] = None,
        company_id: Optional[UUID] = None,
    ) -> None:
        """
        Initialize knowledge update workflow.

        Args:
            parwa_config: PARWA Junior configuration
            kb_manager: Knowledge base manager instance
            company_id: Company UUID for KB isolation
        """
        self._config = parwa_config or get_parwa_config()
        self._company_id = company_id
        self._kb_manager = kb_manager or KnowledgeBaseManager(
            config=KnowledgeBaseConfig(),
            company_id=company_id,
        )
        self._update_history: Dict[str, Dict[str, Any]] = {}

    async def execute(self, update_data: Dict[str, Any]) -> KnowledgeUpdateResult:
        """
        Execute the knowledge update workflow.

        Args:
            update_data: Dict with:
                - ticket_id: Source ticket identifier
                - resolution: Resolution details
                - customer_feedback: Optional feedback (positive/negative/neutral)
                - resolution_type: Type of resolution
                - question: Original question (for FAQ entries)
                - answer: Final answer provided
                - confidence: Confidence score of resolution

        Returns:
            KnowledgeUpdateResult with update status
        """
        ticket_id = update_data.get("ticket_id", "")
        resolution = update_data.get("resolution", "")
        customer_feedback = update_data.get("customer_feedback", "neutral")
        resolution_type = update_data.get("resolution_type", "general")
        question = update_data.get("question", "")
        answer = update_data.get("answer", "")
        confidence = update_data.get("confidence", 0.5)

        update_id = f"kb_upd_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{ticket_id}"

        logger.info({
            "event": "knowledge_update_workflow_started",
            "update_id": update_id,
            "ticket_id": ticket_id,
            "resolution_type": resolution_type,
            "feedback": customer_feedback,
        })

        # Step 1: Determine update type
        update_type = self._determine_update_type(resolution_type, customer_feedback)

        # Step 2: Extract knowledge entry
        entry = self._extract_knowledge_entry(
            ticket_id=ticket_id,
            resolution=resolution,
            question=question,
            answer=answer,
            resolution_type=resolution_type,
            customer_feedback=customer_feedback,
            confidence=confidence,
        )

        # Step 3: Validate entry quality
        if not self._should_update_kb(entry, customer_feedback):
            logger.info({
                "event": "knowledge_update_skipped",
                "update_id": update_id,
                "reason": "Entry quality threshold not met or negative feedback",
            })
            return KnowledgeUpdateResult(
                success=True,
                update_id=update_id,
                update_type=update_type,
                status=UpdateStatus.SKIPPED,
                entries_skipped=1,
                message="Knowledge update skipped due to quality threshold or feedback",
                metadata={"ticket_id": ticket_id, "feedback": customer_feedback},
            )

        # Step 4: Add to knowledge base
        try:
            ingest_result = self._kb_manager.ingest_document(
                content=entry.content,
                metadata={
                    "title": entry.title,
                    "category": entry.category,
                    "tags": entry.tags,
                    "source_ticket_id": entry.source_ticket_id,
                    "update_type": update_type.value,
                    "confidence": entry.confidence,
                    "variant": "parwa",
                    "tier": "medium",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Step 5: Record update history
            self._record_update(update_id, entry, ingest_result)

            logger.info({
                "event": "knowledge_update_completed",
                "update_id": update_id,
                "document_id": str(ingest_result.document_id),
                "update_type": update_type.value,
            })

            return KnowledgeUpdateResult(
                success=True,
                update_id=update_id,
                update_type=update_type,
                status=UpdateStatus.COMPLETED,
                document_id=str(ingest_result.document_id),
                entries_added=1,
                message=f"Knowledge base updated with entry from ticket {ticket_id}",
                metadata={
                    "document_id": str(ingest_result.document_id),
                    "ticket_id": ticket_id,
                    "category": entry.category,
                },
            )

        except Exception as e:
            logger.error({
                "event": "knowledge_update_failed",
                "update_id": update_id,
                "error": str(e),
            })
            return KnowledgeUpdateResult(
                success=False,
                update_id=update_id,
                update_type=update_type,
                status=UpdateStatus.FAILED,
                message=f"Failed to update knowledge base: {str(e)}",
                metadata={"error": str(e), "ticket_id": ticket_id},
            )

    def _determine_update_type(
        self,
        resolution_type: str,
        customer_feedback: str,
    ) -> UpdateType:
        """
        Determine the type of knowledge update.

        Args:
            resolution_type: Type of resolution
            customer_feedback: Customer feedback

        Returns:
            UpdateType for this update
        """
        # Positive feedback on resolution -> pattern
        if customer_feedback == "positive":
            return UpdateType.RESOLUTION_PATTERN

        # FAQ type resolutions
        if resolution_type in ["faq_answered", "information_provided"]:
            return UpdateType.FAQ_ADDITION

        # Escalation related
        if resolution_type in ["escalated", "escalation_resolved"]:
            return UpdateType.ESCALATION_NOTE

        # Policy clarifications
        if resolution_type in ["policy_clarification", "exception_approved"]:
            return UpdateType.POLICY_UPDATE

        # Feedback-based learning
        if customer_feedback in ["negative", "mixed"]:
            return UpdateType.FEEDBACK_LEARNING

        return UpdateType.RESOLUTION_PATTERN

    def _extract_knowledge_entry(
        self,
        ticket_id: str,
        resolution: str,
        question: str,
        answer: str,
        resolution_type: str,
        customer_feedback: str,
        confidence: float,
    ) -> KnowledgeEntry:
        """
        Extract a knowledge entry from resolution data.

        Args:
            ticket_id: Source ticket ID
            resolution: Resolution details
            question: Original question
            answer: Final answer
            resolution_type: Resolution type
            customer_feedback: Customer feedback
            confidence: Resolution confidence

        Returns:
            KnowledgeEntry ready for ingestion
        """
        # Build title based on resolution type
        if question:
            title = f"FAQ: {question[:100]}..." if len(question) > 100 else f"FAQ: {question}"
        else:
            title = f"Resolution Pattern: {resolution_type}"

        # Build content
        content_parts = []

        if question:
            content_parts.append(f"Question: {question}")

        if answer:
            content_parts.append(f"Answer: {answer}")
        elif resolution:
            content_parts.append(f"Resolution: {resolution}")

        content = "\n\n".join(content_parts)

        # Determine category
        category = self._categorize_resolution(resolution_type)

        # Build tags
        tags = [
            resolution_type,
            f"feedback_{customer_feedback}",
            f"confidence_{self._confidence_bucket(confidence)}",
            "parwa",
            "auto_generated",
        ]

        return KnowledgeEntry(
            title=title,
            content=content,
            category=category,
            tags=tags,
            source_ticket_id=ticket_id,
            confidence=confidence,
            metadata={
                "resolution_type": resolution_type,
                "customer_feedback": customer_feedback,
                "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _categorize_resolution(self, resolution_type: str) -> str:
        """
        Categorize the resolution type.

        Args:
            resolution_type: Type of resolution

        Returns:
            Category string
        """
        categories = {
            "refund_approved": "refunds",
            "refund_denied": "refunds",
            "refund_pending": "refunds",
            "faq_answered": "faq",
            "information_provided": "faq",
            "escalated": "escalations",
            "escalation_resolved": "escalations",
            "policy_clarification": "policies",
            "exception_approved": "policies",
            "order_status": "orders",
            "shipping_inquiry": "orders",
            "product_question": "products",
            "technical_support": "technical",
        }
        return categories.get(resolution_type, "general")

    def _confidence_bucket(self, confidence: float) -> str:
        """
        Get confidence bucket for tagging.

        Args:
            confidence: Confidence score

        Returns:
            Confidence bucket string
        """
        if confidence >= 0.9:
            return "high"
        elif confidence >= 0.7:
            return "medium"
        elif confidence >= 0.5:
            return "low"
        return "very_low"

    def _should_update_kb(
        self,
        entry: KnowledgeEntry,
        customer_feedback: str,
    ) -> bool:
        """
        Determine if entry should be added to KB.

        Args:
            entry: Knowledge entry
            customer_feedback: Customer feedback

        Returns:
            True if should update KB
        """
        # Skip if negative feedback and low confidence
        if customer_feedback == "negative" and entry.confidence < 0.5:
            return False

        # Skip if entry is too short
        if len(entry.content.strip()) < 50:
            return False

        # Skip if no meaningful content
        if not entry.content or entry.content == "Question: \n\nAnswer: ":
            return False

        return True

    def _record_update(
        self,
        update_id: str,
        entry: KnowledgeEntry,
        ingest_result: Any,
    ) -> None:
        """
        Record update in history.

        Args:
            update_id: Update identifier
            entry: Knowledge entry
            ingest_result: KB ingestion result
        """
        self._update_history[update_id] = {
            "entry": {
                "title": entry.title,
                "category": entry.category,
                "tags": entry.tags,
                "confidence": entry.confidence,
            },
            "document_id": str(ingest_result.document_id),
            "status": ingest_result.status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def batch_update(
        self,
        updates: List[Dict[str, Any]],
    ) -> List[KnowledgeUpdateResult]:
        """
        Process multiple knowledge updates.

        Args:
            updates: List of update data dictionaries

        Returns:
            List of KnowledgeUpdateResult
        """
        results = []

        for update_data in updates:
            result = await self.execute(update_data)
            results.append(result)

        # Log summary
        successful = sum(1 for r in results if r.success and r.status == UpdateStatus.COMPLETED)
        skipped = sum(1 for r in results if r.status == UpdateStatus.SKIPPED)
        failed = sum(1 for r in results if not r.success)

        logger.info({
            "event": "batch_knowledge_update_complete",
            "total": len(updates),
            "successful": successful,
            "skipped": skipped,
            "failed": failed,
        })

        return results

    def get_update_history(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get recent update history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of update records
        """
        sorted_history = sorted(
            self._update_history.items(),
            key=lambda x: x[1].get("timestamp", ""),
            reverse=True,
        )
        return [
            {"update_id": uid, **data}
            for uid, data in sorted_history[:limit]
        ]

    def get_workflow_name(self) -> str:
        """Get workflow name."""
        return "KnowledgeUpdateWorkflow"

    def get_variant(self) -> str:
        """Get variant name."""
        return "parwa"

    def get_tier(self) -> str:
        """Get AI tier used."""
        return "medium"
