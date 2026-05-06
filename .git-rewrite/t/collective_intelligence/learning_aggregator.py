"""
Learning Aggregator - Aggregate learnings across clients without data leakage.

CRITICAL: This module must NEVER share client-specific data.
Only anonymized, aggregated patterns are extracted.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from enum import Enum
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class PatternType(Enum):
    """Types of learnable patterns"""
    RESOLUTION = "resolution"
    ESCALATION = "escalation"
    SENTIMENT = "sentiment"
    FAQ_MATCH = "faq_match"
    ERROR_PATTERN = "error_pattern"
    SUCCESS_PATTERN = "success_pattern"


class IndustryType(Enum):
    """Supported industries for pattern categorization"""
    ECOMMERCE = "ecommerce"
    SAAS = "saas"
    HEALTHCARE = "healthcare"
    LOGISTICS = "logistics"
    FINTECH = "fintech"
    GENERIC = "generic"


@dataclass
class ClientLearning:
    """Learning data from a single client (sanitized)"""
    client_id: str
    industry: IndustryType
    pattern_type: PatternType
    pattern_hash: str  # Hashed pattern, not actual data
    effectiveness_score: float
    occurrence_count: int
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate no client-specific data in metadata"""
        sensitive_keys = {"email", "phone", "name", "address", "phi", "ssn"}
        for key in self.metadata.keys():
            if any(s in key.lower() for s in sensitive_keys):
                raise ValueError(f"Sensitive data detected in metadata: {key}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "client_id": self.client_id,
            "industry": self.industry.value,
            "pattern_type": self.pattern_type.value,
            "pattern_hash": self.pattern_hash,
            "effectiveness_score": self.effectiveness_score,
            "occurrence_count": self.occurrence_count,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class AggregatedPattern:
    """Aggregated pattern across multiple clients"""
    pattern_id: str
    pattern_type: PatternType
    industries: Set[IndustryType]
    total_occurrences: int
    avg_effectiveness: float
    confidence_score: float
    created_at: datetime
    client_count: int  # Number of clients contributing (anonymized count)
    version: int = 1

    def __post_init__(self):
        """Generate pattern ID if not provided"""
        if not self.pattern_id:
            content = f"{self.pattern_type.value}_{len(self.industries)}"
            self.pattern_id = hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "industries": [i.value for i in self.industries],
            "total_occurrences": self.total_occurrences,
            "avg_effectiveness": self.avg_effectiveness,
            "confidence_score": self.confidence_score,
            "created_at": self.created_at.isoformat(),
            "client_count": self.client_count,
            "version": self.version,
        }


class LearningAggregator:
    """
    Aggregates learnings from multiple clients without exposing client data.

    CRITICAL: Never stores or transmits actual client data.
    Only hashes, counts, and aggregated metrics are used.
    """

    def __init__(self, min_clients_for_pattern: int = 2):
        """
        Initialize the learning aggregator.

        Args:
            min_clients_for_pattern: Minimum clients required to form a pattern
                                    (prevents re-identification)
        """
        self.min_clients_for_pattern = min_clients_for_pattern
        self._learnings: List[ClientLearning] = []
        self._aggregated_patterns: Dict[str, AggregatedPattern] = {}
        self._client_opt_out: Set[str] = set()

    def add_learning(self, learning: ClientLearning) -> bool:
        """
        Add a client learning to the aggregator.

        Args:
            learning: ClientLearning object (must be sanitized)

        Returns:
            True if learning was added, False if client opted out
        """
        if learning.client_id in self._client_opt_out:
            logger.info(f"Client {learning.client_id} has opted out")
            return False

        # Validate no PII in learning
        self._validate_learning_safety(learning)

        self._learnings.append(learning)
        logger.debug(f"Added learning from {learning.client_id}")
        return True

    def opt_out_client(self, client_id: str) -> None:
        """Register a client's opt-out from collective learning"""
        self._client_opt_out.add(client_id)
        # Remove existing learnings from opted-out client
        self._learnings = [
            l for l in self._learnings if l.client_id != client_id
        ]
        logger.info(f"Client {client_id} opted out, learnings removed")

    def aggregate_patterns(self) -> List[AggregatedPattern]:
        """
        Aggregate all learnings into patterns.

        CRITICAL: Only creates patterns if enough clients contribute
        to prevent re-identification.

        Returns:
            List of aggregated patterns
        """
        # Group learnings by pattern hash
        pattern_groups: Dict[str, List[ClientLearning]] = {}

        for learning in self._learnings:
            key = learning.pattern_hash
            if key not in pattern_groups:
                pattern_groups[key] = []
            pattern_groups[key].append(learning)

        # Create aggregated patterns only if enough clients
        new_patterns = []
        for pattern_hash, learnings in pattern_groups.items():
            unique_clients = set(l.client_id for l in learnings)

            if len(unique_clients) < self.min_clients_for_pattern:
                # Not enough clients, skip to prevent re-identification
                continue

            # Aggregate without exposing client data
            industries = set(l.industry for l in learnings)
            total_occurrences = sum(l.occurrence_count for l in learnings)
            avg_effectiveness = sum(
                l.effectiveness_score for l in learnings
            ) / len(learnings)

            # Calculate confidence based on diversity
            confidence = self._calculate_confidence(
                len(unique_clients),
                len(industries),
                total_occurrences
            )

            pattern = AggregatedPattern(
                pattern_id=pattern_hash[:16],
                pattern_type=learnings[0].pattern_type,
                industries=industries,
                total_occurrences=total_occurrences,
                avg_effectiveness=avg_effectiveness,
                confidence_score=confidence,
                created_at=datetime.now(),
                client_count=len(unique_clients),
            )

            self._aggregated_patterns[pattern.pattern_id] = pattern
            new_patterns.append(pattern)

        logger.info(f"Aggregated {len(new_patterns)} patterns from {len(self._learnings)} learnings")
        return new_patterns

    def get_patterns_for_industry(
        self, industry: IndustryType
    ) -> List[AggregatedPattern]:
        """Get patterns relevant to a specific industry"""
        return [
            p for p in self._aggregated_patterns.values()
            if industry in p.industries or IndustryType.GENERIC in p.industries
        ]

    def get_accuracy_improvement_estimate(self) -> float:
        """
        Estimate accuracy improvement from collective intelligence.

        Returns:
            Estimated accuracy improvement percentage
        """
        if not self._aggregated_patterns:
            return 0.0

        # Weight by confidence and effectiveness
        total_weight = 0.0
        weighted_improvement = 0.0

        for pattern in self._aggregated_patterns.values():
            weight = pattern.confidence_score * pattern.avg_effectiveness
            weighted_improvement += weight * 0.02  # ~2% per high-quality pattern
            total_weight += weight

        if total_weight == 0:
            return 0.0

        # Cap at reasonable improvement
        improvement = min(weighted_improvement / total_weight, 5.0)
        return round(improvement, 2)

    def _validate_learning_safety(self, learning: ClientLearning) -> None:
        """Validate that learning contains no sensitive data"""
        # Check metadata for sensitive patterns
        sensitive_patterns = [
            "@", "phone", "ssn", "credit", "password",
            "phi", "medical", "patient", "health record"
        ]

        metadata_str = json.dumps(learning.metadata).lower()
        for pattern in sensitive_patterns:
            if pattern in metadata_str:
                raise ValueError(
                    f"Potential sensitive data detected in learning metadata"
                )

    def _calculate_confidence(
        self,
        client_count: int,
        industry_count: int,
        occurrence_count: int
    ) -> float:
        """
        Calculate confidence score for a pattern.

        Higher confidence with more clients, industries, and occurrences.
        """
        # Client diversity factor (0-0.4)
        client_factor = min(client_count / 5.0, 1.0) * 0.4

        # Industry diversity factor (0-0.3)
        industry_factor = min(industry_count / 3.0, 1.0) * 0.3

        # Occurrence factor (0-0.3)
        occurrence_factor = min(occurrence_count / 100.0, 1.0) * 0.3

        return round(client_factor + industry_factor + occurrence_factor, 2)

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregator statistics"""
        return {
            "total_learnings": len(self._learnings),
            "unique_clients": len(set(l.client_id for l in self._learnings)),
            "aggregated_patterns": len(self._aggregated_patterns),
            "opted_out_clients": len(self._client_opt_out),
            "estimated_accuracy_improvement": self.get_accuracy_improvement_estimate(),
        }


def aggregate_client_learnings(
    learnings: List[ClientLearning],
    min_clients: int = 2
) -> List[AggregatedPattern]:
    """
    Convenience function to aggregate learnings.

    Args:
        learnings: List of client learnings
        min_clients: Minimum clients for a pattern

    Returns:
        List of aggregated patterns
    """
    aggregator = LearningAggregator(min_clients_for_pattern=min_clients)
    for learning in learnings:
        aggregator.add_learning(learning)
    return aggregator.aggregate_patterns()
