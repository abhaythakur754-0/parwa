"""
PARWA Agent Lightning Data Module.

Handles exporting training data and building datasets for fine-tuning.

Components:
- export_mistakes: Export training mistakes from DB
- export_approvals: Export approval decisions for training
- dataset_builder: Build JSONL dataset from exports

Key Features:
- Export mistakes in correct format
- Export approvals with reasoning
- Build JSONL datasets with 50+ entries
- Validate JSONL format
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from enum import Enum
import json


class ExportFormat(str, Enum):
    """Export format types."""
    JSONL = "jsonl"
    JSON = "json"
    CSV = "csv"


class MistakeRecord(BaseException):
    """
    Mistake record for training data.

    Represents a collected mistake that can be used
    for training improvements.
    """

    def __init__(
        self,
        mistake_id: str,
        company_id: str,
        interaction_id: str,
        mistake_type: str,
        original_output: str,
        correct_output: str,
        context: Dict[str, Any],
        created_at: Optional[datetime] = None
    ) -> None:
        """
        Initialize mistake record.

        Args:
            mistake_id: Unique mistake identifier
            company_id: Company ID
            interaction_id: Related interaction ID
            mistake_type: Type of mistake
            original_output: What the agent originally output
            correct_output: What the correct output should be
            context: Additional context
            created_at: Creation timestamp
        """
        self.mistake_id = mistake_id
        self.company_id = company_id
        self.interaction_id = interaction_id
        self.mistake_type = mistake_type
        self.original_output = original_output
        self.correct_output = correct_output
        self.context = context
        self.created_at = created_at or datetime.now(timezone.utc)

    def to_training_format(self) -> Dict[str, Any]:
        """
        Convert to training format.

        Returns:
            Dict in training format
        """
        return {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful customer support agent for PARWA. Learn from this correction."
                },
                {
                    "role": "user",
                    "content": f"Context: {json.dumps(self.context)}\n\nOriginal (incorrect) response:\n{self.original_output}"
                },
                {
                    "role": "assistant",
                    "content": self.correct_output
                }
            ],
            "metadata": {
                "mistake_id": self.mistake_id,
                "mistake_type": self.mistake_type,
                "source": "mistake_correction"
            }
        }


class ApprovalRecord:
    """
    Approval record for training data.

    Represents an approval decision that can be used
    for training the refund decision model.
    """

    def __init__(
        self,
        approval_id: str,
        company_id: str,
        ticket_id: str,
        amount: float,
        decision: str,
        reasoning: str,
        context: Dict[str, Any],
        approver_id: Optional[str] = None,
        created_at: Optional[datetime] = None
    ) -> None:
        """
        Initialize approval record.

        Args:
            approval_id: Unique approval identifier
            company_id: Company ID
            ticket_id: Related ticket ID
            amount: Refund amount
            decision: Approval decision
            reasoning: Reasoning for decision
            context: Additional context
            approver_id: Approver ID
            created_at: Creation timestamp
        """
        self.approval_id = approval_id
        self.company_id = company_id
        self.ticket_id = ticket_id
        self.amount = amount
        self.decision = decision
        self.reasoning = reasoning
        self.context = context
        self.approver_id = approver_id
        self.created_at = created_at or datetime.now(timezone.utc)

    def to_training_format(self) -> Dict[str, Any]:
        """
        Convert to training format.

        Returns:
            Dict in training format
        """
        return {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a refund approval assistant. Analyze the request and provide a decision with reasoning."
                },
                {
                    "role": "user",
                    "content": f"Refund Request:\nAmount: ${self.amount}\nContext: {json.dumps(self.context)}"
                },
                {
                    "role": "assistant",
                    "content": f"Decision: {self.decision}\nReasoning: {self.reasoning}"
                }
            ],
            "metadata": {
                "approval_id": self.approval_id,
                "decision": self.decision,
                "source": "approval_decision"
            }
        }


def validate_dataset(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate a dataset for training.

    Args:
        dataset: List of training entries

    Returns:
        Validation result with stats
    """
    valid_entries = 0
    invalid_entries = 0
    errors = []

    for i, entry in enumerate(dataset):
        if "messages" not in entry:
            invalid_entries += 1
            errors.append(f"Entry {i}: Missing 'messages' field")
            continue

        messages = entry["messages"]
        if not isinstance(messages, list) or len(messages) < 2:
            invalid_entries += 1
            errors.append(f"Entry {i}: Invalid messages format")
            continue

        valid_entries += 1

    return {
        "valid": invalid_entries == 0,
        "total_entries": len(dataset),
        "valid_entries": valid_entries,
        "invalid_entries": invalid_entries,
        "errors": errors[:10]  # Limit error messages
    }


__all__ = [
    "ExportFormat",
    "MistakeRecord",
    "ApprovalRecord",
    "validate_dataset",
]
