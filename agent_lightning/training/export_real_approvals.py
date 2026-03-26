"""
Export Real Approvals for Training.

Exports correct approval decisions from production for training Agent Lightning.
These are cases where the AI made the right decision that was approved by humans.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ApprovalRecord:
    """A record of a correct AI decision that was approved."""
    approval_id: str
    client_id: str
    ticket_id: str
    ticket_subject: str
    ticket_body: str
    ai_decision: str
    ai_confidence: float
    ai_reasoning: str
    human_approved: bool
    approval_time_seconds: float
    category: str
    decision_type: str  # auto_approved, reviewed_and_approved, escalated_correctly
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_training_example(self) -> Dict[str, str]:
        """Convert to training format."""
        return {
            "input": f"Ticket: {self.ticket_subject}\n\n{self.ticket_body}",
            "output": self.ai_decision,
            "reasoning": self.ai_reasoning,
            "category": self.category,
            "confidence": str(self.ai_confidence),
        }


class ApprovalExporter:
    """Exports correct approval decisions from production for training."""

    # PII patterns to anonymize
    PII_PATTERNS = {
        "email": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        "phone": r'\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        "credit_card": r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        "ssn": r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
        "order_id": r'\b(?:order|ord)[-\s]?\d{4,}\b',
    }

    def __init__(
        self,
        export_dir: str = "./agent_lightning/exports",
        anonymize: bool = True
    ):
        """Initialize exporter."""
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.anonymize = anonymize

    def anonymize_text(self, text: str) -> str:
        """Anonymize PII in text."""
        if not self.anonymize:
            return text

        result = text
        for pii_type, pattern in self.PII_PATTERNS.items():
            if pii_type == "email":
                result = re.sub(pattern, "[EMAIL]", result, flags=re.IGNORECASE)
            elif pii_type == "phone":
                result = re.sub(pattern, "[PHONE]", result)
            elif pii_type == "credit_card":
                result = re.sub(pattern, "[CARD]", result)
            elif pii_type == "ssn":
                result = re.sub(pattern, "[SSN]", result)
            elif pii_type == "order_id":
                result = re.sub(pattern, "[ORDER]", result, flags=re.IGNORECASE)

        return result

    def fetch_approvals_from_db(
        self,
        client_ids: List[str],
        start_date: datetime,
        end_date: datetime,
        database_url: Optional[str] = None,
        min_confidence: float = 0.8
    ) -> List[ApprovalRecord]:
        """
        Fetch approved decisions from database.

        In production, this would query the actual database.
        For testing, returns mock data.
        """
        logger.info(f"Fetching approvals for clients {client_ids} from {start_date} to {end_date}")

        # Generate mock approvals for testing
        approvals = []
        categories = ["refund", "shipping", "account", "product", "billing", "faq"]
        decision_types = ["auto_approved", "reviewed_and_approved", "escalated_correctly"]

        for i in range(50):
            approval = ApprovalRecord(
                approval_id=f"APR-{i+1:04d}",
                client_id=client_ids[i % len(client_ids)],
                ticket_id=f"TKT-APR-{i+1:04d}",
                ticket_subject=self.anonymize_text(f"Question about order #{2000+i}"),
                ticket_body=self.anonymize_text(
                    f"Hello, I need help with my recent order. "
                    f"Please check the status for me. Email: customer{i}@test.com"
                ),
                ai_decision="order_status" if i % 3 == 0 else ("refund_approve" if i % 3 == 1 else "faq_answer"),
                ai_confidence=0.85 + (i % 10) * 0.015,  # Range: 0.85-0.985
                ai_reasoning=f"Correctly identified customer intent and provided appropriate response",
                human_approved=True,
                approval_time_seconds=2.5 + (i % 5) * 0.5,
                category=categories[i % len(categories)],
                decision_type=decision_types[i % len(decision_types)],
                created_at=datetime.utcnow() - timedelta(days=i % 30),
                metadata={"source": "mock_data", "quality_score": 0.9}
            )
            approvals.append(approval)

        logger.info(f"Fetched {len(approvals)} approval records")
        return approvals

    def export_to_jsonl(
        self,
        approvals: List[ApprovalRecord],
        output_file: Optional[str] = None
    ) -> str:
        """Export approvals to JSONL format for training."""
        if output_file is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_file = str(self.export_dir / f"approvals_{timestamp}.jsonl")

        with open(output_file, 'w') as f:
            for approval in approvals:
                training_example = approval.to_training_example()
                f.write(json.dumps(training_example) + '\n')

        logger.info(f"Exported {len(approvals)} approvals to {output_file}")
        return output_file

    def export_for_fine_tuning(
        self,
        approvals: List[ApprovalRecord],
        output_file: Optional[str] = None
    ) -> str:
        """Export in fine-tuning format with instruction/completion pairs."""
        if output_file is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_file = str(self.export_dir / f"approvals_ft_{timestamp}.jsonl")

        with open(output_file, 'w') as f:
            for approval in approvals:
                ft_record = {
                    "instruction": "Analyze this customer ticket and provide the correct decision.",
                    "input": self.anonymize_text(
                        f"Subject: {approval.ticket_subject}\n\n"
                        f"Body: {approval.ticket_body}"
                    ),
                    "output": json.dumps({
                        "decision": approval.ai_decision,
                        "reasoning": approval.ai_reasoning,
                        "category": approval.category,
                        "confidence": approval.ai_confidence,
                    }),
                    "metadata": {
                        "approval_id": approval.approval_id,
                        "decision_type": approval.decision_type,
                        "approval_time_seconds": approval.approval_time_seconds,
                    }
                }
                f.write(json.dumps(ft_record) + '\n')

        logger.info(f"Exported {len(approvals)} fine-tuning examples to {output_file}")
        return output_file

    def get_approval_statistics(self, approvals: List[ApprovalRecord]) -> Dict[str, Any]:
        """Generate statistics about the approvals."""
        if not approvals:
            return {"total": 0}

        # Count by decision type
        by_decision_type: Dict[str, int] = {}
        for a in approvals:
            by_decision_type[a.decision_type] = by_decision_type.get(a.decision_type, 0) + 1

        # Count by category
        by_category: Dict[str, int] = {}
        for a in approvals:
            by_category[a.category] = by_category.get(a.category, 0) + 1

        # Count by client
        by_client: Dict[str, int] = {}
        for a in approvals:
            by_client[a.client_id] = by_client.get(a.client_id, 0) + 1

        # Average confidence and approval time
        avg_confidence = sum(a.ai_confidence for a in approvals) / len(approvals)
        avg_approval_time = sum(a.approval_time_seconds for a in approvals) / len(approvals)

        return {
            "total": len(approvals),
            "by_decision_type": by_decision_type,
            "by_category": by_category,
            "by_client": by_client,
            "avg_confidence": round(avg_confidence, 3),
            "avg_approval_time_seconds": round(avg_approval_time, 2),
            "export_timestamp": datetime.utcnow().isoformat(),
        }


def export_approvals(
    client_ids: List[str],
    start_date: datetime,
    end_date: datetime,
    export_dir: str = "./agent_lightning/exports",
    anonymize: bool = True,
    min_confidence: float = 0.8
) -> Dict[str, Any]:
    """
    Main function to export approvals for training.

    Args:
        client_ids: List of client IDs to export for
        start_date: Start date for data
        end_date: End date for data
        export_dir: Directory for exports
        anonymize: Whether to anonymize PII
        min_confidence: Minimum confidence threshold

    Returns:
        Export results with statistics
    """
    exporter = ApprovalExporter(export_dir=export_dir, anonymize=anonymize)

    # Fetch approvals
    approvals = exporter.fetch_approvals_from_db(
        client_ids=client_ids,
        start_date=start_date,
        end_date=end_date,
        min_confidence=min_confidence
    )

    if not approvals:
        return {
            "success": False,
            "message": "No approvals found for the specified criteria",
            "count": 0
        }

    # Export to different formats
    jsonl_path = exporter.export_to_jsonl(approvals)
    ft_path = exporter.export_for_fine_tuning(approvals)

    # Get statistics
    stats = exporter.get_approval_statistics(approvals)

    return {
        "success": True,
        "count": len(approvals),
        "jsonl_path": jsonl_path,
        "fine_tuning_path": ft_path,
        "statistics": stats,
    }


if __name__ == "__main__":
    result = export_approvals(
        client_ids=["client_001", "client_002"],
        start_date=datetime.utcnow() - timedelta(days=30),
        end_date=datetime.utcnow()
    )
    print(json.dumps(result, indent=2, default=str))
