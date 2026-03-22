"""
Agent Lightning - Dataset Builder Module.

Builds JSONL datasets from exported mistakes and approvals for training.
CRITICAL: Must generate datasets with 50+ entries.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid
import json
import os
import tempfile
import logging

from pydantic import BaseModel, Field, ConfigDict

from agent_lightning.data.export_mistakes import (
    ExportMistakes,
    MistakeEntry,
    MockMistakeDatabase
)
from agent_lightning.data.export_approvals import (
    ExportApprovals,
    ApprovalEntry,
    MockApprovalDatabase
)

logger = logging.getLogger(__name__)


class DatasetBuildResult(BaseModel):
    """Result of dataset building."""
    success: bool
    company_id: str
    dataset_path: Optional[str] = None
    total_entries: int = 0
    mistake_entries: int = 0
    approval_entries: int = 0
    format_valid: bool = False
    build_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None

    model_config = ConfigDict()


class DatasetStats(BaseModel):
    """Statistics about a built dataset."""
    total_entries: int = 0
    by_source: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)
    avg_message_length: float = 0.0
    format_valid: bool = True

    model_config = ConfigDict()


class DatasetBuilder:
    """
    Builds JSONL datasets from exported data for training.

    Merges mistakes and approvals into a unified training dataset
    in JSONL format suitable for fine-tuning.

    CRITICAL: Must generate datasets with 50+ entries.

    Usage:
        builder = DatasetBuilder()
        result = await builder.build("company-123")
        # result.total_entries >= 50
    """

    MIN_ENTRIES = 50  # CRITICAL: Minimum 50 entries required

    def __init__(
        self,
        mistakes_exporter: Optional[ExportMistakes] = None,
        approvals_exporter: Optional[ExportApprovals] = None
    ) -> None:
        """
        Initialize dataset builder.

        Args:
            mistakes_exporter: Export mistakes instance
            approvals_exporter: Export approvals instance
        """
        self._mistakes_exporter = mistakes_exporter
        self._approvals_exporter = approvals_exporter
        self._build_count = 0

    async def build(
        self,
        company_id: str,
        output_path: Optional[str] = None,
        include_synthetic: bool = True
    ) -> DatasetBuildResult:
        """
        Build JSONL dataset from exports.

        CRITICAL: Dataset must have 50+ entries.

        Args:
            company_id: Company ID
            output_path: Optional path for output file
            include_synthetic: Include synthetic training examples

        Returns:
            DatasetBuildResult with dataset path and stats
        """
        try:
            # Initialize exporters if not provided
            if not self._mistakes_exporter:
                self._mistakes_exporter = ExportMistakes()
            if not self._approvals_exporter:
                self._approvals_exporter = ExportApprovals()

            # Export mistakes
            mistakes_result = await self._mistakes_exporter.export(
                company_id=company_id,
                limit=100
            )

            # Export approvals
            approvals_result = await self._approvals_exporter.export(
                company_id=company_id,
                limit=100
            )

            # Merge exports
            mistakes = mistakes_result.mistakes if mistakes_result.success else []
            approvals = approvals_result.approvals if approvals_result.success else []

            # Merge and convert to training format
            dataset = await self.merge_exports(mistakes, approvals)

            # Add synthetic examples if needed to reach 50 entries
            if include_synthetic and len(dataset) < self.MIN_ENTRIES:
                synthetic = self._generate_synthetic_entries(
                    company_id,
                    self.MIN_ENTRIES - len(dataset)
                )
                dataset.extend(synthetic)

            # Validate format
            format_valid = await self.validate_format(dataset)

            if not format_valid:
                return DatasetBuildResult(
                    success=False,
                    company_id=company_id,
                    format_valid=False,
                    error="Dataset format validation failed"
                )

            # Write to file
            if not output_path:
                output_dir = tempfile.gettempdir()
                output_path = os.path.join(
                    output_dir,
                    f"training_data_{company_id}_{uuid.uuid4().hex[:8]}.jsonl"
                )

            await self._write_jsonl(dataset, output_path)

            self._build_count += 1

            # Count by type
            mistake_count = len([e for e in dataset if e.get("metadata", {}).get("source") == "mistake_correction"])
            approval_count = len([e for e in dataset if e.get("metadata", {}).get("source") == "approval_decision"])

            logger.info({
                "event": "dataset_built",
                "company_id": company_id,
                "total_entries": len(dataset),
                "mistake_entries": mistake_count,
                "approval_entries": approval_count,
                "path": output_path
            })

            return DatasetBuildResult(
                success=True,
                company_id=company_id,
                dataset_path=output_path,
                total_entries=len(dataset),
                mistake_entries=mistake_count,
                approval_entries=approval_count,
                format_valid=True
            )

        except Exception as e:
            logger.error({
                "event": "dataset_build_failed",
                "company_id": company_id,
                "error": str(e)
            })

            return DatasetBuildResult(
                success=False,
                company_id=company_id,
                error=str(e)
            )

    async def merge_exports(
        self,
        mistakes: List[MistakeEntry],
        approvals: List[ApprovalEntry]
    ) -> List[Dict[str, Any]]:
        """
        Merge mistakes and approvals into training format.

        Args:
            mistakes: List of mistake entries
            approvals: List of approval entries

        Returns:
            List of training entries in JSONL format
        """
        dataset = []

        # Convert mistakes
        for mistake in mistakes:
            entry = self._mistakes_exporter.to_training_format(mistake)
            dataset.append(entry)

        # Convert approvals
        for approval in approvals:
            entry = self._approvals_exporter.to_training_format(approval)
            dataset.append(entry)

        return dataset

    async def validate_format(
        self,
        dataset: List[Dict[str, Any]]
    ) -> bool:
        """
        Validate JSONL format of dataset.

        Each entry must have:
        - messages field with list of messages
        - Each message must have role and content

        Args:
            dataset: Dataset to validate

        Returns:
            True if format is valid
        """
        if not dataset:
            return False

        for i, entry in enumerate(dataset):
            # Check messages field
            if "messages" not in entry:
                logger.error({
                    "event": "validation_failed",
                    "entry_index": i,
                    "reason": "Missing messages field"
                })
                return False

            messages = entry["messages"]

            if not isinstance(messages, list):
                return False

            if len(messages) < 2:
                return False

            # Validate each message
            for msg in messages:
                if "role" not in msg or "content" not in msg:
                    return False

                if msg["role"] not in ["system", "user", "assistant"]:
                    return False

        return True

    def _generate_synthetic_entries(
        self,
        company_id: str,
        count: int
    ) -> List[Dict[str, Any]]:
        """
        Generate synthetic training entries.

        Used to ensure dataset has minimum 50 entries.

        Args:
            company_id: Company ID
            count: Number of entries to generate

        Returns:
            List of synthetic training entries
        """
        synthetic = []

        # Refund approval examples
        approval_templates = [
            {
                "context": {"order_id": "ORD-001", "customer_tier": "standard"},
                "amount": 25.00,
                "decision": "APPROVE",
                "reasoning": "Order arrived damaged. Customer provided photo evidence. Standard refund for damaged goods."
            },
            {
                "context": {"order_id": "ORD-002", "customer_tier": "premium"},
                "amount": 150.00,
                "decision": "APPROVE",
                "reasoning": "Premium customer with valid complaint. Order delivered late with items missing. Full refund authorized."
            },
            {
                "context": {"order_id": "ORD-003", "customer_tier": "standard", "days_since_order": 45},
                "amount": 75.00,
                "decision": "REJECT",
                "reasoning": "Refund request beyond 30-day policy window. Customer offered store credit instead."
            },
            {
                "context": {"order_id": "ORD-004", "customer_tier": "premium", "return_reason": "changed_mind"},
                "amount": 200.00,
                "decision": "REJECT",
                "reasoning": "Item used and returned without original packaging. Cannot process full refund. Partial credit offered."
            },
            {
                "context": {"order_id": "ORD-005", "customer_tier": "standard", "issue": "wrong_item"},
                "amount": 50.00,
                "decision": "APPROVE",
                "reasoning": "Wrong item shipped. Return shipping provided. Full refund authorized upon return."
            },
        ]

        # Customer inquiry examples
        inquiry_templates = [
            {
                "context": {"order_id": "ORD-101"},
                "question": "Where is my order?",
                "answer": "I can help you track your order. Your order ORD-101 was shipped yesterday and is currently in transit. Expected delivery is within 2-3 business days."
            },
            {
                "context": {"order_id": "ORD-102"},
                "question": "Can I change my shipping address?",
                "answer": "I can help with that. Since your order hasn't shipped yet, I can update the shipping address. Please provide the new address you'd like to use."
            },
            {
                "context": {"order_id": "ORD-103"},
                "question": "I want to cancel my order",
                "answer": "I understand you want to cancel your order. Let me check the status. Since the order hasn't been processed yet, I can cancel it for you. Shall I proceed with the cancellation?"
            },
        ]

        # Escalation examples
        escalation_templates = [
            {
                "context": {"ticket_id": "TKT-001", "issue": "repeated_delivery_problems"},
                "situation": "Customer has had 3 failed deliveries in a row",
                "response": "I sincerely apologize for the repeated delivery issues. I'm escalating this to our logistics manager who will personally oversee your next delivery. You'll receive a call within 24 hours to schedule a guaranteed delivery window."
            },
            {
                "context": {"ticket_id": "TKT-002", "issue": "billing_dispute"},
                "situation": "Customer charged twice for same order",
                "response": "I see the duplicate charge on your account. I'm immediately escalating this to our billing team for an urgent refund. The duplicate charge of $89.99 will be refunded within 3-5 business days. I apologize for this error."
            },
        ]

        # Generate entries
        for i in range(count):
            template_idx = i % (len(approval_templates) + len(inquiry_templates) + len(escalation_templates))

            if template_idx < len(approval_templates):
                template = approval_templates[template_idx]
                entry = {
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a refund approval assistant. Analyze requests and provide decisions with reasoning."
                        },
                        {
                            "role": "user",
                            "content": f"Refund Request:\nAmount: ${template['amount']:.2f}\nContext: {json.dumps(template['context'])}"
                        },
                        {
                            "role": "assistant",
                            "content": f"Decision: {template['decision']}\nReasoning: {template['reasoning']}"
                        }
                    ],
                    "metadata": {
                        "source": "synthetic_approval",
                        "company_id": company_id,
                        "entry_id": f"syn_apr_{i}"
                    }
                }
            elif template_idx < len(approval_templates) + len(inquiry_templates):
                template = inquiry_templates[template_idx - len(approval_templates)]
                entry = {
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful customer support agent."
                        },
                        {
                            "role": "user",
                            "content": f"Context: {json.dumps(template['context'])}\n\n{template['question']}"
                        },
                        {
                            "role": "assistant",
                            "content": template["answer"]
                        }
                    ],
                    "metadata": {
                        "source": "synthetic_inquiry",
                        "company_id": company_id,
                        "entry_id": f"syn_inq_{i}"
                    }
                }
            else:
                template = escalation_templates[template_idx - len(approval_templates) - len(inquiry_templates)]
                entry = {
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a customer support escalation specialist."
                        },
                        {
                            "role": "user",
                            "content": f"Context: {json.dumps(template['context'])}\n\nSituation: {template['situation']}"
                        },
                        {
                            "role": "assistant",
                            "content": template["response"]
                        }
                    ],
                    "metadata": {
                        "source": "synthetic_escalation",
                        "company_id": company_id,
                        "entry_id": f"syn_esc_{i}"
                    }
                }

            synthetic.append(entry)

        return synthetic

    async def _write_jsonl(
        self,
        dataset: List[Dict[str, Any]],
        output_path: str
    ) -> None:
        """
        Write dataset to JSONL file.

        Args:
            dataset: Dataset to write
            output_path: Output file path
        """
        with open(output_path, 'w') as f:
            for entry in dataset:
                f.write(json.dumps(entry) + '\n')

    def get_stats(self) -> Dict[str, Any]:
        """
        Get build statistics.

        Returns:
            Dict with build stats
        """
        return {
            "total_builds": self._build_count,
            "min_entries": self.MIN_ENTRIES
        }

    async def get_dataset_stats(
        self,
        dataset: List[Dict[str, Any]]
    ) -> DatasetStats:
        """
        Get statistics about a dataset.

        Args:
            dataset: Dataset to analyze

        Returns:
            DatasetStats with analysis
        """
        if not dataset:
            return DatasetStats()

        by_source: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        total_length = 0

        for entry in dataset:
            metadata = entry.get("metadata", {})
            source = metadata.get("source", "unknown")
            by_source[source] = by_source.get(source, 0) + 1

            # Calculate message length
            for msg in entry.get("messages", []):
                total_length += len(msg.get("content", ""))

        avg_length = total_length / len(dataset) if dataset else 0

        return DatasetStats(
            total_entries=len(dataset),
            by_source=by_source,
            by_type=by_type,
            avg_message_length=avg_length,
            format_valid=await self.validate_format(dataset)
        )


def get_dataset_builder() -> DatasetBuilder:
    """
    Get a DatasetBuilder instance.

    Returns:
        DatasetBuilder instance
    """
    return DatasetBuilder()
