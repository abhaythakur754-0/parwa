"""
Feedback Collector for Active Learning.

Collects and manages human feedback for model improvement:
- Priority queue for corrections
- Quality scoring
- Automatic labeling suggestions
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from collections import defaultdict
import logging
import json

logger = logging.getLogger(__name__)


class FeedbackPriority(Enum):
    """Priority levels for feedback items."""
    CRITICAL = 1  # Safety/compliance issues
    HIGH = 2      # Accuracy issues
    MEDIUM = 3    # Quality improvements
    LOW = 4       # Minor corrections


class FeedbackQuality(Enum):
    """Quality levels for feedback."""
    HIGH = "high"       # Expert annotation
    MEDIUM = "medium"   # Manager correction
    LOW = "low"         # Automated suggestion


@dataclass
class FeedbackItem:
    """A single feedback item."""
    feedback_id: str
    sample_id: str
    query: str
    original_prediction: str
    corrected_label: str
    priority: FeedbackPriority
    quality: FeedbackQuality
    source: str  # "manager", "expert", "auto"
    timestamp: datetime = field(default_factory=datetime.now)
    notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "feedback_id": self.feedback_id,
            "sample_id": self.sample_id,
            "query": self.query,
            "original_prediction": self.original_prediction,
            "corrected_label": self.corrected_label,
            "priority": self.priority.value,
            "quality": self.quality.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "notes": self.notes,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeedbackItem":
        """Create from dictionary."""
        return cls(
            feedback_id=data["feedback_id"],
            sample_id=data["sample_id"],
            query=data["query"],
            original_prediction=data["original_prediction"],
            corrected_label=data["corrected_label"],
            priority=FeedbackPriority(data["priority"]),
            quality=FeedbackQuality(data["quality"]),
            source=data["source"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            notes=data.get("notes"),
            metadata=data.get("metadata", {})
        )


class FeedbackCollector:
    """
    Collects and manages human feedback for active learning.

    Features:
    - Priority queue for corrections
    - Quality scoring
    - Aggregation from multiple sources
    - Automatic labeling suggestions
    """

    def __init__(
        self,
        max_queue_size: int = 1000,
        auto_label_threshold: float = 0.95
    ):
        """
        Initialize the feedback collector.

        Args:
            max_queue_size: Maximum items in feedback queue
            auto_label_threshold: Confidence threshold for auto-labeling
        """
        self.max_queue_size = max_queue_size
        self.auto_label_threshold = auto_label_threshold
        self._feedback_queue: List[FeedbackItem] = []
        self._feedback_by_source: Dict[str, List[FeedbackItem]] = defaultdict(list)
        self._feedback_count = 0
        self._auto_label_suggestions: List[Dict[str, Any]] = []

    def add_feedback(
        self,
        sample_id: str,
        query: str,
        original_prediction: str,
        corrected_label: str,
        source: str = "manager",
        priority: FeedbackPriority = FeedbackPriority.MEDIUM,
        quality: FeedbackQuality = FeedbackQuality.MEDIUM,
        notes: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FeedbackItem:
        """
        Add a new feedback item.

        Args:
            sample_id: ID of the sample being corrected
            query: The original query
            original_prediction: What the model predicted
            corrected_label: The correct label
            source: Source of feedback (manager, expert, auto)
            priority: Priority level
            quality: Quality level
            notes: Optional notes
            metadata: Optional metadata

        Returns:
            The created FeedbackItem
        """
        feedback = FeedbackItem(
            feedback_id=f"fb_{self._feedback_count}",
            sample_id=sample_id,
            query=query,
            original_prediction=original_prediction,
            corrected_label=corrected_label,
            priority=priority,
            quality=quality,
            source=source,
            notes=notes,
            metadata=metadata or {}
        )

        self._feedback_queue.append(feedback)
        self._feedback_by_source[source].append(feedback)
        self._feedback_count += 1

        # Sort by priority
        self._feedback_queue.sort(key=lambda x: x.priority.value)

        # Trim queue if needed
        if len(self._feedback_queue) > self.max_queue_size:
            removed = self._feedback_queue[self.max_queue_size:]
            self._feedback_queue = self._feedback_queue[:self.max_queue_size]
            logger.warning(f"Trimmed {len(removed)} feedback items from queue")

        logger.info(
            f"Added feedback {feedback.feedback_id} from {source}, "
            f"priority={priority.name}"
        )

        return feedback

    def get_pending_feedback(
        self,
        limit: Optional[int] = None,
        priority: Optional[FeedbackPriority] = None
    ) -> List[FeedbackItem]:
        """
        Get pending feedback items.

        Args:
            limit: Maximum items to return
            priority: Filter by priority level

        Returns:
            List of pending feedback items
        """
        items = self._feedback_queue

        if priority:
            items = [f for f in items if f.priority == priority]

        if limit:
            items = items[:limit]

        return items

    def suggest_auto_labels(
        self,
        predictions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate auto-labeling suggestions for high-confidence predictions.

        Args:
            predictions: List of predictions with confidence scores

        Returns:
            List of auto-label suggestions
        """
        suggestions = []

        for pred in predictions:
            confidence = pred.get("confidence", 0)
            if confidence >= self.auto_label_threshold:
                suggestion = {
                    "sample_id": pred.get("sample_id", ""),
                    "query": pred.get("query", ""),
                    "suggested_label": pred.get("prediction", ""),
                    "confidence": confidence,
                    "needs_review": False
                }
                suggestions.append(suggestion)
            elif confidence >= self.auto_label_threshold - 0.1:
                # Medium confidence - needs review
                suggestion = {
                    "sample_id": pred.get("sample_id", ""),
                    "query": pred.get("query", ""),
                    "suggested_label": pred.get("prediction", ""),
                    "confidence": confidence,
                    "needs_review": True
                }
                suggestions.append(suggestion)

        self._auto_label_suggestions.extend(suggestions)

        logger.info(
            f"Generated {len(suggestions)} auto-label suggestions "
            f"({sum(1 for s in suggestions if not s['needs_review'])} high confidence)"
        )

        return suggestions

    def aggregate_manager_corrections(
        self,
        manager_id: str,
        corrections: List[Dict[str, Any]]
    ) -> int:
        """
        Aggregate corrections from a manager.

        Args:
            manager_id: ID of the manager
            corrections: List of correction dicts

        Returns:
            Number of corrections added
        """
        added = 0

        for correction in corrections:
            self.add_feedback(
                sample_id=correction.get("sample_id", ""),
                query=correction.get("query", ""),
                original_prediction=correction.get("original_prediction", ""),
                corrected_label=correction.get("corrected_label", ""),
                source=f"manager_{manager_id}",
                priority=FeedbackPriority.HIGH,
                quality=FeedbackQuality.MEDIUM
            )
            added += 1

        return added

    def calculate_feedback_quality_score(self) -> float:
        """
        Calculate overall quality score of collected feedback.

        Returns:
            Quality score in [0, 1]
        """
        if not self._feedback_queue:
            return 0.0

        quality_weights = {
            FeedbackQuality.HIGH: 1.0,
            FeedbackQuality.MEDIUM: 0.7,
            FeedbackQuality.LOW: 0.4
        }

        total_score = sum(
            quality_weights[f.quality] for f in self._feedback_queue
        )

        return total_score / len(self._feedback_queue)

    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get feedback collection statistics."""
        priority_counts = defaultdict(int)
        for f in self._feedback_queue:
            priority_counts[f.priority.name] += 1

        source_counts = {
            source: len(items)
            for source, items in self._feedback_by_source.items()
        }

        return {
            "total_feedback": len(self._feedback_queue),
            "total_collected": self._feedback_count,
            "by_priority": dict(priority_counts),
            "by_source": source_counts,
            "quality_score": self.calculate_feedback_quality_score(),
            "auto_label_suggestions": len(self._auto_label_suggestions)
        }

    def export_feedback(self) -> List[Dict[str, Any]]:
        """Export all feedback for training."""
        return [f.to_dict() for f in self._feedback_queue]

    def clear_processed(self, feedback_ids: List[str]) -> int:
        """
        Remove processed feedback items.

        Args:
            feedback_ids: IDs of processed items

        Returns:
            Number of items removed
        """
        ids_set = set(feedback_ids)
        original_len = len(self._feedback_queue)

        self._feedback_queue = [
            f for f in self._feedback_queue if f.feedback_id not in ids_set
        ]

        removed = original_len - len(self._feedback_queue)
        logger.info(f"Cleared {removed} processed feedback items")

        return removed


def get_feedback_collector(
    max_queue_size: int = 1000
) -> FeedbackCollector:
    """
    Factory function to create a feedback collector.

    Args:
        max_queue_size: Maximum items in queue

    Returns:
        Configured FeedbackCollector instance
    """
    return FeedbackCollector(max_queue_size=max_queue_size)
