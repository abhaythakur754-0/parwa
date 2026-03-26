"""
Pattern Sharing - Share anonymized patterns across clients.

CRITICAL: Never shares actual client data, only patterns.
Patterns are abstracted representations that cannot be reverse-engineered.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from enum import Enum
import hashlib
import logging

from .learning_aggregator import (
    AggregatedPattern,
    PatternType,
    IndustryType,
)

logger = logging.getLogger(__name__)


class PatternStatus(Enum):
    """Status of a shared pattern"""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    CONFLICT = "conflict"
    PENDING = "pending"


@dataclass
class PatternVersion:
    """Version history for a pattern"""
    version: int
    created_at: datetime
    changes: str
    effectiveness_delta: float = 0.0


@dataclass
class SharedPattern:
    """A pattern shared across clients"""
    pattern_id: str
    pattern_type: PatternType
    industries: Set[IndustryType]
    abstraction: str  # Abstracted pattern representation
    effectiveness_score: float
    confidence_score: float
    client_count: int
    status: PatternStatus
    version: int
    version_history: List[PatternVersion] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    tags: Set[str] = field(default_factory=set)

    def __post_init__(self):
        """Initialize version history if empty"""
        if not self.version_history:
            self.version_history = [
                PatternVersion(
                    version=1,
                    created_at=self.created_at,
                    changes="Initial pattern creation",
                )
            ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "industries": [i.value for i in self.industries],
            "abstraction": self.abstraction,
            "effectiveness_score": self.effectiveness_score,
            "confidence_score": self.confidence_score,
            "client_count": self.client_count,
            "status": self.status.value,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": list(self.tags),
        }


@dataclass
class PatternConflict:
    """Represents a conflict between patterns"""
    pattern_id_1: str
    pattern_id_2: str
    conflict_type: str
    resolution_strategy: str
    resolved: bool = False


class PatternSharing:
    """
    Manages pattern sharing across clients with privacy guarantees.

    CRITICAL: All shared patterns are abstracted and cannot be
    reverse-engineered to reveal client data.
    """

    def __init__(self, min_confidence: float = 0.5):
        """
        Initialize pattern sharing.

        Args:
            min_confidence: Minimum confidence for sharing a pattern
        """
        self.min_confidence = min_confidence
        self._patterns: Dict[str, SharedPattern] = {}
        self._conflicts: List[PatternConflict] = []
        self._effectiveness_history: Dict[str, List[float]] = {}

    def share_pattern(
        self,
        aggregated_pattern: AggregatedPattern,
        abstraction: str
    ) -> Optional[SharedPattern]:
        """
        Create a shareable pattern from an aggregated pattern.

        Args:
            aggregated_pattern: Source aggregated pattern
            abstraction: Abstracted representation (no client data)

        Returns:
            SharedPattern if created, None if confidence too low
        """
        if aggregated_pattern.confidence_score < self.min_confidence:
            logger.warning(
                f"Pattern {aggregated_pattern.pattern_id} confidence "
                f"{aggregated_pattern.confidence_score} below minimum "
                f"{self.min_confidence}"
            )
            return None

        # Validate abstraction doesn't contain sensitive data
        if not self._validate_abstraction(abstraction):
            raise ValueError("Abstraction contains potential sensitive data")

        pattern = SharedPattern(
            pattern_id=aggregated_pattern.pattern_id,
            pattern_type=aggregated_pattern.pattern_type,
            industries=aggregated_pattern.industries,
            abstraction=abstraction,
            effectiveness_score=aggregated_pattern.avg_effectiveness,
            confidence_score=aggregated_pattern.confidence_score,
            client_count=aggregated_pattern.client_count,
            status=PatternStatus.ACTIVE,
            version=aggregated_pattern.version,
        )

        self._patterns[pattern.pattern_id] = pattern
        self._effectiveness_history[pattern.pattern_id] = [
            pattern.effectiveness_score
        ]

        logger.info(f"Shared pattern {pattern.pattern_id}")
        return pattern

    def get_patterns_for_client(
        self,
        industry: IndustryType,
        pattern_types: Optional[List[PatternType]] = None
    ) -> List[SharedPattern]:
        """
        Get patterns applicable to a client.

        Args:
            industry: Client's industry
            pattern_types: Optional filter by pattern types

        Returns:
            List of applicable patterns
        """
        patterns = []
        for pattern in self._patterns.values():
            # Check industry match
            if industry not in pattern.industries:
                if IndustryType.GENERIC not in pattern.industries:
                    continue

            # Check pattern type filter
            if pattern_types and pattern.pattern_type not in pattern_types:
                continue

            # Only return active patterns
            if pattern.status != PatternStatus.ACTIVE:
                continue

            patterns.append(pattern)

        return patterns

    def update_pattern_effectiveness(
        self,
        pattern_id: str,
        new_effectiveness: float
    ) -> bool:
        """
        Update pattern effectiveness score.

        Args:
            pattern_id: Pattern to update
            new_effectiveness: New effectiveness measurement

        Returns:
            True if updated, False if not found
        """
        if pattern_id not in self._patterns:
            return False

        pattern = self._patterns[pattern_id]
        old_effectiveness = pattern.effectiveness_score

        # Track history
        self._effectiveness_history[pattern_id].append(new_effectiveness)

        # Calculate moving average
        history = self._effectiveness_history[pattern_id][-10:]
        pattern.effectiveness_score = sum(history) / len(history)

        # Check for significant change - may need version update
        delta = abs(pattern.effectiveness_score - old_effectiveness)
        if delta > 0.1:
            self._create_new_version(pattern, f"Effectiveness updated by {delta:.2f}")

        pattern.updated_at = datetime.now()
        logger.info(f"Updated pattern {pattern_id} effectiveness to {pattern.effectiveness_score:.2f}")
        return True

    def detect_conflicts(self) -> List[PatternConflict]:
        """
        Detect conflicts between patterns.

        Returns:
            List of detected conflicts
        """
        conflicts = []
        patterns = list(self._patterns.values())

        for i, p1 in enumerate(patterns):
            for p2 in patterns[i + 1:]:
                conflict = self._check_pattern_conflict(p1, p2)
                if conflict:
                    conflicts.append(conflict)
                    self._conflicts.append(conflict)

        logger.info(f"Detected {len(conflicts)} pattern conflicts")
        return conflicts

    def resolve_conflict(
        self,
        conflict: PatternConflict,
        resolution: str
    ) -> bool:
        """
        Resolve a pattern conflict.

        Args:
            conflict: Conflict to resolve
            resolution: Resolution strategy ('keep_both', 'merge', 'deprecate_lower')

        Returns:
            True if resolved
        """
        p1 = self._patterns.get(conflict.pattern_id_1)
        p2 = self._patterns.get(conflict.pattern_id_2)

        if not p1 or not p2:
            return False

        if resolution == "keep_both":
            # Mark both as active, they serve different purposes
            conflict.resolution_strategy = "keep_both"
            conflict.resolved = True

        elif resolution == "deprecate_lower":
            # Deprecate the pattern with lower effectiveness
            if p1.effectiveness_score < p2.effectiveness_score:
                p1.status = PatternStatus.DEPRECATED
            else:
                p2.status = PatternStatus.DEPRECATED
            conflict.resolution_strategy = "deprecate_lower"
            conflict.resolved = True

        elif resolution == "merge":
            # Merge industries from both patterns
            p1.industries.update(p2.industries)
            p2.status = PatternStatus.DEPRECATED
            conflict.resolution_strategy = "merge"
            conflict.resolved = True

        logger.info(f"Resolved conflict with strategy: {resolution}")
        return True

    def get_pattern_stats(self) -> Dict[str, Any]:
        """Get pattern sharing statistics"""
        active_count = sum(
            1 for p in self._patterns.values()
            if p.status == PatternStatus.ACTIVE
        )

        by_type: Dict[PatternType, int] = {}
        for pattern in self._patterns.values():
            by_type[pattern.pattern_type] = by_type.get(pattern.pattern_type, 0) + 1

        return {
            "total_patterns": len(self._patterns),
            "active_patterns": active_count,
            "deprecated_patterns": len(self._patterns) - active_count,
            "unresolved_conflicts": sum(1 for c in self._conflicts if not c.resolved),
            "patterns_by_type": {t.value: c for t, c in by_type.items()},
            "avg_effectiveness": sum(
                p.effectiveness_score for p in self._patterns.values()
            ) / len(self._patterns) if self._patterns else 0.0,
        }

    def _validate_abstraction(self, abstraction: str) -> bool:
        """Validate abstraction doesn't contain sensitive data"""
        sensitive_patterns = [
            "@", "phone", "email", "ssn", "credit card",
            "password", "api_key", "token", "secret",
            "patient", "medical record", "phi"
        ]

        abstraction_lower = abstraction.lower()
        for pattern in sensitive_patterns:
            if pattern in abstraction_lower:
                return False

        return True

    def _check_pattern_conflict(
        self,
        p1: SharedPattern,
        p2: SharedPattern
    ) -> Optional[PatternConflict]:
        """Check if two patterns conflict"""
        # Same type, similar effectiveness but different abstraction
        if p1.pattern_type != p2.pattern_type:
            return None

        # Check if abstractions are similar but different
        if p1.abstraction == p2.abstraction:
            return None

        # Check for overlap in industries
        if not p1.industries.intersection(p2.industries):
            return None

        # Similar effectiveness scores indicate potential conflict
        if abs(p1.effectiveness_score - p2.effectiveness_score) < 0.1:
            return PatternConflict(
                pattern_id_1=p1.pattern_id,
                pattern_id_2=p2.pattern_id,
                conflict_type="similar_effectiveness",
                resolution_strategy="pending",
            )

        return None

    def _create_new_version(self, pattern: SharedPattern, changes: str) -> None:
        """Create a new version of a pattern"""
        pattern.version += 1
        pattern.version_history.append(
            PatternVersion(
                version=pattern.version,
                created_at=datetime.now(),
                changes=changes,
                effectiveness_delta=pattern.effectiveness_score,
            )
        )


def share_patterns_across_clients(
    aggregated_patterns: List[AggregatedPattern],
    abstraction_func=lambda p: f"pattern_{p.pattern_type.value}"
) -> List[SharedPattern]:
    """
    Convenience function to share patterns.

    Args:
        aggregated_patterns: Patterns to share
        abstraction_func: Function to create abstraction from pattern

    Returns:
        List of shared patterns
    """
    sharing = PatternSharing()
    shared = []

    for pattern in aggregated_patterns:
        abstraction = abstraction_func(pattern)
        result = sharing.share_pattern(pattern, abstraction)
        if result:
            shared.append(result)

    return shared
