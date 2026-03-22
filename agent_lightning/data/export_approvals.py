"""
Agent Lightning - Export Approvals Module.

Exports approval decisions for training the refund decision model.
Approvals contain valuable reasoning that can improve agent decisions.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import json
import logging

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


class ApprovalEntry(BaseModel):
    """Single approval entry for export."""
    approval_id: str
    company_id: str
    ticket_id: str
    amount: float
    decision: str  # approved, rejected
    reasoning: str
    context: Dict[str, Any] = Field(default_factory=dict)
    approver_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict()


class ApprovalExportResult(BaseModel):
    """Result of exporting approvals."""
    success: bool
    company_id: str
    total_exported: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    approvals: List[ApprovalEntry] = Field(default_factory=list)
    export_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None

    model_config = ConfigDict()


class MockApprovalDatabase:
    """
    Mock database for testing approval exports.

    In production, this would connect to the actual approval records.
    """

    def __init__(self) -> None:
        """Initialize mock database."""
        self._approvals: Dict[str, List[Dict[str, Any]]] = {}

    def add_approval(
        self,
        company_id: str,
        ticket_id: str,
        amount: float,
        decision: str,
        reasoning: str,
        context: Optional[Dict[str, Any]] = None,
        approver_id: Optional[str] = None
    ) -> str:
        """
        Add an approval record.

        Args:
            company_id: Company ID
            ticket_id: Ticket ID
            amount: Refund amount
            decision: Decision (approved/rejected)
            reasoning: Reasoning for decision
            context: Additional context
            approver_id: Approver ID

        Returns:
            Approval ID
        """
        approval_id = f"APR-{uuid.uuid4().hex[:8].upper()}"

        approval = {
            "approval_id": approval_id,
            "company_id": company_id,
            "ticket_id": ticket_id,
            "amount": amount,
            "decision": decision,
            "reasoning": reasoning,
            "context": context or {},
            "approver_id": approver_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        if company_id not in self._approvals:
            self._approvals[company_id] = []
        self._approvals[company_id].append(approval)

        return approval_id

    def get_approvals(
        self,
        company_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get all approvals for a company."""
        approvals = self._approvals.get(company_id, [])
        return approvals[:limit]

    def get_approved(
        self,
        company_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get approved refunds for a company."""
        approvals = self._approvals.get(company_id, [])
        approved = [a for a in approvals if a["decision"] == "approved"]
        return approved[:limit]

    def get_rejected(
        self,
        company_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get rejected refunds for a company."""
        approvals = self._approvals.get(company_id, [])
        rejected = [a for a in approvals if a["decision"] == "rejected"]
        return rejected[:limit]


class ExportApprovals:
    """
    Export approval decisions for training.

    Approval decisions contain valuable reasoning that can train
    the agent to make better refund decisions.

    Usage:
        exporter = ExportApprovals()
        result = await exporter.export("company-123", limit=100)
    """

    def __init__(
        self,
        db: Optional[MockApprovalDatabase] = None
    ) -> None:
        """
        Initialize export approvals.

        Args:
            db: Database connection (uses mock if not provided)
        """
        self._db = db or MockApprovalDatabase()
        self._export_count = 0

    async def export(
        self,
        company_id: str,
        limit: int = 100
    ) -> ApprovalExportResult:
        """
        Export approvals for training.

        Args:
            company_id: Company ID
            limit: Maximum number of approvals to export

        Returns:
            ApprovalExportResult with exported approvals
        """
        try:
            approvals_data = self._db.get_approvals(company_id, limit)
            approvals = []
            approved_count = 0
            rejected_count = 0

            for data in approvals_data:
                entry = ApprovalEntry(
                    approval_id=data["approval_id"],
                    company_id=data["company_id"],
                    ticket_id=data["ticket_id"],
                    amount=data["amount"],
                    decision=data["decision"],
                    reasoning=data["reasoning"],
                    context=data.get("context", {}),
                    approver_id=data.get("approver_id"),
                    created_at=datetime.fromisoformat(
                        data["created_at"].replace("Z", "+00:00")
                    ) if isinstance(data["created_at"], str) else data["created_at"]
                )
                approvals.append(entry)

                if entry.decision == "approved":
                    approved_count += 1
                else:
                    rejected_count += 1

            self._export_count += len(approvals)

            logger.info({
                "event": "approvals_exported",
                "company_id": company_id,
                "count": len(approvals),
                "approved": approved_count,
                "rejected": rejected_count
            })

            return ApprovalExportResult(
                success=True,
                company_id=company_id,
                total_exported=len(approvals),
                approved_count=approved_count,
                rejected_count=rejected_count,
                approvals=approvals
            )

        except Exception as e:
            logger.error({
                "event": "approvals_export_failed",
                "company_id": company_id,
                "error": str(e)
            })

            return ApprovalExportResult(
                success=False,
                company_id=company_id,
                error=str(e)
            )

    async def get_approved_refunds(
        self,
        company_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get approved refund decisions for training.

        These show what conditions lead to approved refunds.

        Args:
            company_id: Company ID
            limit: Maximum records to return

        Returns:
            List of approved refund records
        """
        try:
            approved = self._db.get_approved(company_id, limit)

            logger.info({
                "event": "approved_refunds_retrieved",
                "company_id": company_id,
                "count": len(approved)
            })

            return approved

        except Exception as e:
            logger.error({
                "event": "approved_refunds_failed",
                "company_id": company_id,
                "error": str(e)
            })

            return []

    async def get_rejected_refunds(
        self,
        company_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get rejected refund decisions for training.

        These show what conditions lead to rejected refunds.

        Args:
            company_id: Company ID
            limit: Maximum records to return

        Returns:
            List of rejected refund records
        """
        try:
            rejected = self._db.get_rejected(company_id, limit)

            logger.info({
                "event": "rejected_refunds_retrieved",
                "company_id": company_id,
                "count": len(rejected)
            })

            return rejected

        except Exception as e:
            logger.error({
                "event": "rejected_refunds_failed",
                "company_id": company_id,
                "error": str(e)
            })

            return []

    def get_stats(self) -> Dict[str, Any]:
        """
        Get export statistics.

        Returns:
            Dict with export stats
        """
        return {
            "total_exports": self._export_count
        }

    def to_training_format(
        self,
        approval: ApprovalEntry
    ) -> Dict[str, Any]:
        """
        Convert an approval to training format.

        Args:
            approval: Approval entry to convert

        Returns:
            Dict in training format with messages
        """
        decision_label = "APPROVE" if approval.decision == "approved" else "REJECT"

        return {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a refund approval assistant. Analyze requests and provide decisions with reasoning."
                },
                {
                    "role": "user",
                    "content": f"Refund Request:\nAmount: ${approval.amount:.2f}\nContext: {json.dumps(approval.context)}"
                },
                {
                    "role": "assistant",
                    "content": f"Decision: {decision_label}\nReasoning: {approval.reasoning}"
                }
            ],
            "metadata": {
                "approval_id": approval.approval_id,
                "decision": approval.decision,
                "amount": approval.amount,
                "source": "approval_decision"
            }
        }


def get_export_approvals() -> ExportApprovals:
    """
    Get an ExportApprovals instance.

    Returns:
        ExportApprovals instance
    """
    return ExportApprovals()
