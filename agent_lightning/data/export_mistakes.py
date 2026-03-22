"""
Agent Lightning - Export Mistakes Module.

Exports training mistakes from the database for fine-tuning.
Mistakes are collected from negative rewards and corrections.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import json
import logging

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


class MistakeEntry(BaseModel):
    """Single mistake entry for export."""
    mistake_id: str
    company_id: str
    interaction_id: str
    mistake_type: str
    original_output: str
    correct_output: str
    context: Dict[str, Any] = Field(default_factory=dict)
    negative_reward: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict()


class MistakeExportResult(BaseModel):
    """Result of exporting mistakes."""
    success: bool
    company_id: str
    total_exported: int = 0
    mistakes: List[MistakeEntry] = Field(default_factory=list)
    export_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None

    model_config = ConfigDict()


class MockMistakeDatabase:
    """
    Mock database for testing mistake exports.

    In production, this would connect to the actual database.
    """

    def __init__(self) -> None:
        """Initialize mock database."""
        self._mistakes: Dict[str, List[Dict[str, Any]]] = {}
        self._negative_rewards: Dict[str, List[Dict[str, Any]]] = {}
        self._corrections: Dict[str, Dict[str, Any]] = {}

    def add_mistake(
        self,
        company_id: str,
        interaction_id: str,
        mistake_type: str,
        original_output: str,
        correct_output: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a mistake record.

        Args:
            company_id: Company ID
            interaction_id: Interaction ID
            mistake_type: Type of mistake
            original_output: Original incorrect output
            correct_output: Correct output
            context: Additional context

        Returns:
            Mistake ID
        """
        mistake_id = f"MST-{uuid.uuid4().hex[:8].upper()}"

        mistake = {
            "mistake_id": mistake_id,
            "company_id": company_id,
            "interaction_id": interaction_id,
            "mistake_type": mistake_type,
            "original_output": original_output,
            "correct_output": correct_output,
            "context": context or {},
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        if company_id not in self._mistakes:
            self._mistakes[company_id] = []
        self._mistakes[company_id].append(mistake)

        return mistake_id

    def add_negative_reward(
        self,
        company_id: str,
        interaction_id: str,
        reward: float,
        reason: str
    ) -> str:
        """
        Add a negative reward record.

        Args:
            company_id: Company ID
            interaction_id: Interaction ID
            reward: Negative reward value
            reason: Reason for negative reward

        Returns:
            Reward record ID
        """
        reward_id = f"NRW-{uuid.uuid4().hex[:8].upper()}"

        record = {
            "reward_id": reward_id,
            "company_id": company_id,
            "interaction_id": interaction_id,
            "reward": reward,
            "reason": reason,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        if company_id not in self._negative_rewards:
            self._negative_rewards[company_id] = []
        self._negative_rewards[company_id].append(record)

        return reward_id

    def add_correction(
        self,
        interaction_id: str,
        original: str,
        correction: str,
        corrected_by: str
    ) -> str:
        """
        Add a correction record.

        Args:
            interaction_id: Interaction ID
            original: Original output
            correction: Corrected output
            corrected_by: Who made the correction

        Returns:
            Correction ID
        """
        correction_id = f"COR-{uuid.uuid4().hex[:8].upper()}"

        self._corrections[interaction_id] = {
            "correction_id": correction_id,
            "interaction_id": interaction_id,
            "original": original,
            "correction": correction,
            "corrected_by": corrected_by,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        return correction_id

    def get_mistakes(
        self,
        company_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get mistakes for a company."""
        mistakes = self._mistakes.get(company_id, [])
        return mistakes[:limit]

    def get_negative_rewards(
        self,
        company_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get negative rewards for a company."""
        rewards = self._negative_rewards.get(company_id, [])
        return rewards[:limit]

    def get_correction(
        self,
        interaction_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get correction for an interaction."""
        return self._corrections.get(interaction_id)


class ExportMistakes:
    """
    Export training mistakes from the database.

    Mistakes are collected from:
    - Negative reward records
    - Human corrections
    - Incorrect classifications
    - Wrong refund decisions

    Usage:
        exporter = ExportMistakes()
        result = await exporter.export("company-123", limit=100)
    """

    def __init__(
        self,
        db: Optional[MockMistakeDatabase] = None
    ) -> None:
        """
        Initialize export mistakes.

        Args:
            db: Database connection (uses mock if not provided)
        """
        self._db = db or MockMistakeDatabase()
        self._export_count = 0

    async def export(
        self,
        company_id: str,
        limit: int = 100
    ) -> MistakeExportResult:
        """
        Export mistakes for training.

        Args:
            company_id: Company ID
            limit: Maximum number of mistakes to export

        Returns:
            MistakeExportResult with exported mistakes
        """
        try:
            mistakes_data = self._db.get_mistakes(company_id, limit)
            mistakes = []

            for data in mistakes_data:
                entry = MistakeEntry(
                    mistake_id=data["mistake_id"],
                    company_id=data["company_id"],
                    interaction_id=data["interaction_id"],
                    mistake_type=data["mistake_type"],
                    original_output=data["original_output"],
                    correct_output=data["correct_output"],
                    context=data.get("context", {}),
                    created_at=datetime.fromisoformat(
                        data["created_at"].replace("Z", "+00:00")
                    ) if isinstance(data["created_at"], str) else data["created_at"]
                )
                mistakes.append(entry)

            self._export_count += len(mistakes)

            logger.info({
                "event": "mistakes_exported",
                "company_id": company_id,
                "count": len(mistakes)
            })

            return MistakeExportResult(
                success=True,
                company_id=company_id,
                total_exported=len(mistakes),
                mistakes=mistakes
            )

        except Exception as e:
            logger.error({
                "event": "mistakes_export_failed",
                "company_id": company_id,
                "error": str(e)
            })

            return MistakeExportResult(
                success=False,
                company_id=company_id,
                error=str(e)
            )

    async def get_negative_rewards(
        self,
        company_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get negative reward records for a company.

        Negative rewards indicate areas where the agent performed poorly.

        Args:
            company_id: Company ID
            limit: Maximum records to return

        Returns:
            List of negative reward records
        """
        try:
            rewards = self._db.get_negative_rewards(company_id, limit)

            logger.info({
                "event": "negative_rewards_retrieved",
                "company_id": company_id,
                "count": len(rewards)
            })

            return rewards

        except Exception as e:
            logger.error({
                "event": "negative_rewards_failed",
                "company_id": company_id,
                "error": str(e)
            })

            return []

    async def get_correction_data(
        self,
        interaction_id: str
    ) -> Dict[str, Any]:
        """
        Get correction data for a specific interaction.

        Corrections show the original incorrect output and
        the corrected output provided by humans.

        Args:
            interaction_id: Interaction ID

        Returns:
            Correction data or empty dict if not found
        """
        try:
            correction = self._db.get_correction(interaction_id)

            if not correction:
                return {
                    "found": False,
                    "interaction_id": interaction_id
                }

            return {
                "found": True,
                "interaction_id": interaction_id,
                "correction_id": correction["correction_id"],
                "original": correction["original"],
                "correction": correction["correction"],
                "corrected_by": correction["corrected_by"],
                "created_at": correction["created_at"]
            }

        except Exception as e:
            logger.error({
                "event": "correction_data_failed",
                "interaction_id": interaction_id,
                "error": str(e)
            })

            return {
                "found": False,
                "interaction_id": interaction_id,
                "error": str(e)
            }

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
        mistake: MistakeEntry
    ) -> Dict[str, Any]:
        """
        Convert a mistake to training format.

        Args:
            mistake: Mistake entry to convert

        Returns:
            Dict in training format with messages
        """
        return {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a customer support agent learning from corrections."
                },
                {
                    "role": "user",
                    "content": f"Context: {json.dumps(mistake.context)}\n\nYour previous response was incorrect:\n{mistake.original_output}"
                },
                {
                    "role": "assistant",
                    "content": mistake.correct_output
                }
            ],
            "metadata": {
                "mistake_id": mistake.mistake_id,
                "mistake_type": mistake.mistake_type,
                "source": "mistake_correction"
            }
        }


def get_export_mistakes() -> ExportMistakes:
    """
    Get an ExportMistakes instance.

    Returns:
        ExportMistakes instance
    """
    return ExportMistakes()
