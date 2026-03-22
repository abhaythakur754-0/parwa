"""
PARWA Junior Update Knowledge Task.

Task for updating the knowledge base after resolution events.
Ensures learnings are captured for future reference.

PARWA Junior Features:
- Extracts insights from resolved tickets
- Creates FAQ entries from common questions
- Tracks learning metrics
- Medium tier analysis for knowledge extraction
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from variants.parwa.config import ParwaConfig, get_parwa_config
from variants.parwa.workflows.knowledge_update import (
    KnowledgeUpdateWorkflow,
    UpdateType,
    UpdateStatus,
)
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class KnowledgeTaskStatus(Enum):
    """Status of knowledge update task."""
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    PROCESSING = "processing"


@dataclass
class KnowledgeEntryInfo:
    """Information about the knowledge entry."""
    title: str
    category: str
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class UpdateKnowledgeResult:
    """Result from update knowledge task."""
    success: bool
    task_id: Optional[str] = None
    status: KnowledgeTaskStatus = KnowledgeTaskStatus.PROCESSING
    update_type: UpdateType = UpdateType.FAQ_ADDITION
    document_id: Optional[str] = None
    entry_info: Optional[KnowledgeEntryInfo] = None
    entries_added: int = 0
    entries_skipped: int = 0
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class UpdateKnowledgeTask:
    """
    Task for updating the knowledge base after resolution.

    This task uses the KnowledgeUpdateWorkflow to capture learnings
    from resolved tickets and add them to the knowledge base.

    Features:
    - Automatic insight extraction
    - FAQ entry creation
    - Learning metrics tracking
    - Category-based organization

    Example:
        task = UpdateKnowledgeTask()
        result = await task.execute({
            "ticket_id": "tkt_123",
            "resolution": "Refund processed for defective product",
            "customer_feedback": "positive",
            "resolution_type": "refund_approved"
        })
    """

    def __init__(
        self,
        parwa_config: Optional[ParwaConfig] = None,
        workflow: Optional[KnowledgeUpdateWorkflow] = None,
    ) -> None:
        """
        Initialize update knowledge task.

        Args:
            parwa_config: PARWA Junior configuration
            workflow: Optional workflow instance
        """
        self._config = parwa_config or get_parwa_config()
        self._workflow = workflow or KnowledgeUpdateWorkflow(parwa_config)

    async def execute(self, input_data: Dict[str, Any]) -> UpdateKnowledgeResult:
        """
        Execute the knowledge update task.

        Args:
            input_data: Dict with:
                - ticket_id: Source ticket identifier
                - resolution: Resolution details
                - customer_feedback: Customer feedback (positive/negative/neutral)
                - resolution_type: Type of resolution
                - question: Original question (for FAQ)
                - answer: Final answer provided
                - confidence: Resolution confidence

        Returns:
            UpdateKnowledgeResult with update status
        """
        ticket_id = input_data.get("ticket_id", "")
        resolution_type = input_data.get("resolution_type", "general")

        task_id = f"kb_task_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{ticket_id}"

        logger.info({
            "event": "update_knowledge_task_started",
            "task_id": task_id,
            "ticket_id": ticket_id,
            "resolution_type": resolution_type,
        })

        try:
            # Use workflow to process update
            workflow_result = await self._workflow.execute(input_data)

            # Build entry info if available
            entry_info = None
            if workflow_result.success and workflow_result.status == UpdateStatus.COMPLETED:
                # Extract entry info from the workflow
                entry_info = KnowledgeEntryInfo(
                    title=f"Entry from ticket {ticket_id}",
                    category=workflow_result.metadata.get("category", "general"),
                    tags=[resolution_type, "auto_generated"],
                    confidence=input_data.get("confidence", 0.5),
                )

            # Build result
            result = UpdateKnowledgeResult(
                success=workflow_result.success,
                task_id=task_id,
                status=self._map_status(workflow_result.status),
                update_type=workflow_result.update_type,
                document_id=workflow_result.document_id,
                entry_info=entry_info,
                entries_added=workflow_result.entries_added,
                entries_skipped=workflow_result.entries_skipped,
                message=workflow_result.message,
                metadata={
                    "variant": "parwa",
                    "tier": "medium",
                    "ticket_id": ticket_id,
                    **workflow_result.metadata,
                },
            )

            logger.info({
                "event": "update_knowledge_task_complete",
                "task_id": task_id,
                "status": result.status.value,
                "entries_added": result.entries_added,
                "document_id": result.document_id,
            })

            return result

        except Exception as e:
            logger.error({
                "event": "update_knowledge_task_error",
                "task_id": task_id,
                "error": str(e),
            })
            return UpdateKnowledgeResult(
                success=False,
                task_id=task_id,
                status=KnowledgeTaskStatus.FAILED,
                message=f"Error updating knowledge base: {str(e)}",
                metadata={"error": str(e), "ticket_id": ticket_id},
            )

    def _map_status(self, workflow_status: UpdateStatus) -> KnowledgeTaskStatus:
        """Map workflow status to task status."""
        mapping = {
            UpdateStatus.COMPLETED: KnowledgeTaskStatus.COMPLETED,
            UpdateStatus.SKIPPED: KnowledgeTaskStatus.SKIPPED,
            UpdateStatus.FAILED: KnowledgeTaskStatus.FAILED,
            UpdateStatus.PENDING: KnowledgeTaskStatus.PROCESSING,
            UpdateStatus.PROCESSING: KnowledgeTaskStatus.PROCESSING,
        }
        return mapping.get(workflow_status, KnowledgeTaskStatus.PROCESSING)

    async def batch_update(
        self,
        updates: List[Dict[str, Any]],
    ) -> List[UpdateKnowledgeResult]:
        """
        Process multiple knowledge updates.

        Args:
            updates: List of update data dictionaries

        Returns:
            List of UpdateKnowledgeResult
        """
        results = []

        for update_data in updates:
            result = await self.execute(update_data)
            results.append(result)

        # Log summary
        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)

        logger.info({
            "event": "batch_knowledge_update_complete",
            "total": len(updates),
            "successful": successful,
            "failed": failed,
        })

        return results

    def get_task_name(self) -> str:
        """Get task name."""
        return "update_knowledge"

    def get_variant(self) -> str:
        """Get variant name."""
        return "parwa"

    def get_tier(self) -> str:
        """Get tier used."""
        return "medium"
