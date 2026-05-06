"""
Export Real Mistakes for Training.

Exports agent mistakes from production for training Agent Lightning.
Mistakes are cases where the AI made wrong decisions that were corrected by humans.
"""
import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MistakeRecord:
    """A record of an AI mistake."""
    mistake_id: str
    client_id: str
    ticket_id: str
    ticket_subject: str
    ticket_body: str
    ai_decision: str
    ai_confidence: float
    ai_reasoning: str
    correct_decision: str
    correct_reasoning: str
    mistake_type: str  # wrong_decision, wrong_confidence, wrong_reasoning
    category: str
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_training_example(self) -> Dict[str, str]:
        """Convert to training format."""
        return {
            "input": f"Ticket: {self.ticket_subject}\n\n{self.ticket_body}",
            "incorrect_output": self.ai_decision,
            "correct_output": self.correct_decision,
            "explanation": self.correct_reasoning,
            "category": self.category,
            "mistake_type": self.mistake_type,
        }


class MistakeExporter:
    """Exports mistakes from production for training."""

    # PII patterns to anonymize
    PII_PATTERNS = {
        "email": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        "phone": r'\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        "credit_card": r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        "ssn": r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
        "order_id": r'\b(?:order|ord)[-\s]?\d{4,}\b',
        "ip_address": r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
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
            elif pii_type == "ip_address":
                result = re.sub(pattern, "[IP]", result)

        return result

    def fetch_mistakes_from_db(
        self,
        client_ids: List[str],
        start_date: datetime,
        end_date: datetime,
        database_url: Optional[str] = None
    ) -> List[MistakeRecord]:
        """
        Fetch mistakes from database.

        In production, this would query the actual database.
        For testing, returns mock data.
        """
        # Mock implementation - in production would use actual DB
        logger.info(f"Fetching mistakes for clients {client_ids} from {start_date} to {end_date}")

        # Generate mock mistakes for testing
        mistakes = []
        mistake_types = ["wrong_decision", "wrong_confidence", "wrong_reasoning"]
        categories = ["refund", "shipping", "account", "product", "billing"]

        for i in range(25):
            mistake = MistakeRecord(
                mistake_id=f"MST-{i+1:04d}",
                client_id=client_ids[i % len(client_ids)],
                ticket_id=f"TKT-{i+1:04d}",
                ticket_subject=self.anonymize_text(f"Inquiry about my order #{1000+i}"),
                ticket_body=self.anonymize_text(
                    f"Hi, I have a question about my recent purchase. "
                    f"My email is customer{i}@example.com and I need help with a refund."
                ),
                ai_decision="auto_reply",
                ai_confidence=0.65,
                ai_reasoning="Customer is asking a general question",
                correct_decision="refund_approve",
                correct_reasoning="Customer is explicitly requesting a refund for their order",
                mistake_type=mistake_types[i % len(mistake_types)],
                category=categories[i % len(categories)],
                created_at=datetime.utcnow() - timedelta(days=i % 30),
                metadata={"source": "mock_data"}
            )
            mistakes.append(mistake)

        logger.info(f"Fetched {len(mistakes)} mistake records")
        return mistakes

    def export_to_jsonl(
        self,
        mistakes: List[MistakeRecord],
        output_file: Optional[str] = None
    ) -> str:
        """Export mistakes to JSONL format for training."""
        if output_file is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_file = str(self.export_dir / f"mistakes_{timestamp}.jsonl")

        with open(output_file, 'w') as f:
            for mistake in mistakes:
                training_example = mistake.to_training_example()
                f.write(json.dumps(training_example) + '\n')

        logger.info(f"Exported {len(mistakes)} mistakes to {output_file}")
        return output_file

    def export_for_fine_tuning(
        self,
        mistakes: List[MistakeRecord],
        output_file: Optional[str] = None
    ) -> str:
        """Export in fine-tuning format with instruction/completion pairs."""
        if output_file is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_file = str(self.export_dir / f"mistakes_ft_{timestamp}.jsonl")

        with open(output_file, 'w') as f:
            for mistake in mistakes:
                # Format for instruction fine-tuning
                ft_record = {
                    "instruction": "Analyze this customer ticket and provide the correct decision.",
                    "input": self.anonymize_text(
                        f"Subject: {mistake.ticket_subject}\n\n"
                        f"Body: {mistake.ticket_body}"
                    ),
                    "output": json.dumps({
                        "decision": mistake.correct_decision,
                        "reasoning": mistake.correct_reasoning,
                        "category": mistake.category,
                    }),
                    "metadata": {
                        "mistake_id": mistake.mistake_id,
                        "original_wrong_decision": mistake.ai_decision,
                        "mistake_type": mistake.mistake_type,
                    }
                }
                f.write(json.dumps(ft_record) + '\n')

        logger.info(f"Exported {len(mistakes)} fine-tuning examples to {output_file}")
        return output_file

    def get_mistake_statistics(self, mistakes: List[MistakeRecord]) -> Dict[str, Any]:
        """Generate statistics about the mistakes."""
        if not mistakes:
            return {"total": 0}

        # Count by mistake type
        by_type: Dict[str, int] = {}
        for m in mistakes:
            by_type[m.mistake_type] = by_type.get(m.mistake_type, 0) + 1

        # Count by category
        by_category: Dict[str, int] = {}
        for m in mistakes:
            by_category[m.category] = by_category.get(m.category, 0) + 1

        # Count by client
        by_client: Dict[str, int] = {}
        for m in mistakes:
            by_client[m.client_id] = by_client.get(m.client_id, 0) + 1

        # Average confidence of wrong decisions
        avg_confidence = sum(m.ai_confidence for m in mistakes) / len(mistakes)

        return {
            "total": len(mistakes),
            "by_type": by_type,
            "by_category": by_category,
            "by_client": by_client,
            "avg_wrong_confidence": round(avg_confidence, 3),
            "export_timestamp": datetime.utcnow().isoformat(),
        }


def export_mistakes(
    client_ids: List[str],
    start_date: datetime,
    end_date: datetime,
    export_dir: str = "./agent_lightning/exports",
    anonymize: bool = True
) -> Dict[str, Any]:
    """
    Main function to export mistakes for training.

    Args:
        client_ids: List of client IDs to export for
        start_date: Start date for data
        end_date: End date for data
        export_dir: Directory for exports
        anonymize: Whether to anonymize PII

    Returns:
        Export results with statistics
    """
    exporter = MistakeExporter(export_dir=export_dir, anonymize=anonymize)

    # Fetch mistakes
    mistakes = exporter.fetch_mistakes_from_db(
        client_ids=client_ids,
        start_date=start_date,
        end_date=end_date
    )

    if not mistakes:
        return {
            "success": False,
            "message": "No mistakes found for the specified criteria",
            "count": 0
        }

    # Export to different formats
    jsonl_path = exporter.export_to_jsonl(mistakes)
    ft_path = exporter.export_for_fine_tuning(mistakes)

    # Get statistics
    stats = exporter.get_mistake_statistics(mistakes)

    return {
        "success": True,
        "count": len(mistakes),
        "jsonl_path": jsonl_path,
        "fine_tuning_path": ft_path,
        "statistics": stats,
    }


if __name__ == "__main__":
    # Example usage
    result = export_mistakes(
        client_ids=["client_001", "client_002"],
        start_date=datetime.utcnow() - timedelta(days=30),
        end_date=datetime.utcnow()
    )
    print(json.dumps(result, indent=2, default=str))
