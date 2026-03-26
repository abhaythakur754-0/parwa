"""
Enhanced Aggregator for Collective Intelligence.

Aggregates learning from 20 clients with:
- Category tagging
- Quality scoring
- PII anonymization
- Differential privacy
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime
from enum import Enum
import logging
import hashlib
import random

logger = logging.getLogger(__name__)


class QualityScore(Enum):
    """Quality scores for learning samples."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class AggregatedSample:
    """A sample aggregated from a client."""
    sample_id: str
    client_id: str
    query: str
    intent: str
    response: str
    category: str
    quality_score: float
    privacy_applied: bool
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregationResult:
    """Result of aggregation process."""
    aggregation_id: str
    total_clients: int
    total_samples: int
    samples_by_category: Dict[str, int]
    average_quality: float
    privacy_metrics: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


class EnhancedAggregator:
    """
    Enhanced aggregator for collective intelligence.
    
    Features:
    - Aggregate from 20 clients
    - Category tagging
    - Quality scoring
    - PII anonymization
    - Differential privacy
    """

    # PII patterns to detect and remove
    PII_PATTERNS = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"\+?1?\d{9,15}",
        "ssn": r"\d{3}-\d{2}-\d{4}",
        "credit_card": r"\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}",
        "ip_address": r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",
    }

    # Sensitive keywords
    SENSITIVE_KEYWORDS = [
        "password", "secret", "api_key", "token",
        "ssn", "social_security", "credit_card",
    ]

    def __init__(
        self,
        min_clients: int = 1,
        privacy_budget: float = 1.0,
        noise_scale: float = 0.1
    ):
        """
        Initialize the enhanced aggregator.

        Args:
            min_clients: Minimum clients for aggregation
            privacy_budget: Differential privacy budget (epsilon)
            noise_scale: Scale of Laplacian noise
        """
        self.min_clients = min_clients
        self.privacy_budget = privacy_budget
        self.noise_scale = noise_scale

        self._aggregation_counter = 0
        self._aggregated_samples: List[AggregatedSample] = []
        self._client_contributions: Dict[str, int] = {}
        self._categories: Set[str] = set()

    def detect_pii(self, text: str) -> List[Tuple[str, str]]:
        """
        Detect PII patterns in text.

        Args:
            text: Text to analyze

        Returns:
            List of (pattern_type, matched_text) tuples
        """
        import re
        detected = []

        for pattern_type, pattern in self.PII_PATTERNS.items():
            matches = re.findall(pattern, text)
            for match in matches:
                detected.append((pattern_type, match))

        return detected

    def anonymize_text(self, text: str) -> Tuple[str, bool]:
        """
        Anonymize PII in text.

        Args:
            text: Text to anonymize

        Returns:
            Tuple of (anonymized_text, had_pii)
        """
        import re
        had_pii = False
        anonymized = text

        # Replace email addresses
        if re.search(self.PII_PATTERNS["email"], anonymized):
            anonymized = re.sub(
                self.PII_PATTERNS["email"],
                "[EMAIL_REDACTED]",
                anonymized
            )
            had_pii = True

        # Replace phone numbers
        if re.search(self.PII_PATTERNS["phone"], anonymized):
            anonymized = re.sub(
                self.PII_PATTERNS["phone"],
                "[PHONE_REDACTED]",
                anonymized
            )
            had_pii = True

        # Replace SSN
        if re.search(self.PII_PATTERNS["ssn"], anonymized):
            anonymized = re.sub(
                self.PII_PATTERNS["ssn"],
                "[SSN_REDACTED]",
                anonymized
            )
            had_pii = True

        # Replace credit cards
        if re.search(self.PII_PATTERNS["credit_card"], anonymized):
            anonymized = re.sub(
                self.PII_PATTERNS["credit_card"],
                "[CARD_REDACTED]",
                anonymized
            )
            had_pii = True

        # Replace IP addresses
        if re.search(self.PII_PATTERNS["ip_address"], anonymized):
            anonymized = re.sub(
                self.PII_PATTERNS["ip_address"],
                "[IP_REDACTED]",
                anonymized
            )
            had_pii = True

        return anonymized, had_pii

    def tag_category(
        self,
        query: str,
        intent: str,
        client_category: Optional[str] = None
    ) -> str:
        """
        Tag a sample with a category.

        Args:
            query: The query text
            intent: The intent
            client_category: Category from client (if known)

        Returns:
            Category tag
        """
        if client_category:
            return client_category

        # Infer from intent/query
        query_lower = query.lower()
        intent_lower = intent.lower()

        # E-commerce keywords
        if any(k in query_lower for k in ["order", "refund", "shipping", "tracking", "product", "cart"]):
            return "ecommerce"

        # SaaS keywords
        if any(k in query_lower for k in ["subscription", "billing", "feature", "plan", "account"]):
            return "saas"

        # Healthcare keywords
        if any(k in query_lower for k in ["appointment", "prescription", "insurance", "medical", "doctor"]):
            return "healthcare"

        # Financial keywords
        if any(k in query_lower for k in ["balance", "transaction", "fraud", "card", "bank"]):
            return "financial"

        # Default based on intent
        return "general"

    def calculate_quality_score(
        self,
        sample: Dict[str, Any]
    ) -> float:
        """
        Calculate quality score for a sample.

        Args:
            sample: Sample to score

        Returns:
            Quality score (0-1)
        """
        score = 1.0

        # Penalize short queries
        query = sample.get("query", "")
        if len(query) < 10:
            score -= 0.2
        elif len(query) < 20:
            score -= 0.1

        # Penalize missing response
        if not sample.get("response"):
            score -= 0.3

        # Penalize low confidence
        confidence = sample.get("confidence", 1.0)
        if confidence < 0.7:
            score -= 0.2
        elif confidence < 0.9:
            score -= 0.1

        # Reward human validation
        if sample.get("human_validated"):
            score += 0.1

        return max(0.0, min(1.0, score))

    def apply_differential_privacy(
        self,
        value: float,
        sensitivity: float = 1.0
    ) -> float:
        """
        Apply differential privacy noise.

        Args:
            value: Value to add noise to
            sensitivity: Sensitivity of the value

        Returns:
            Value with privacy-preserving noise
        """
        # Laplacian noise for differential privacy
        noise = random.gauss(0, self.noise_scale * sensitivity)
        return value + noise

    def aggregate_from_client(
        self,
        client_id: str,
        samples: List[Dict[str, Any]],
        client_category: Optional[str] = None
    ) -> List[AggregatedSample]:
        """
        Aggregate samples from a single client.

        Args:
            client_id: Client identifier
            samples: Samples from client
            client_category: Category for this client

        Returns:
            List of aggregated samples
        """
        aggregated = []

        for i, sample in enumerate(samples):
            # Anonymize
            query, had_pii = self.anonymize_text(sample.get("query", ""))
            response, _ = self.anonymize_text(sample.get("response", ""))

            # Skip if sensitive content
            if any(kw in query.lower() for kw in self.SENSITIVE_KEYWORDS):
                continue

            # Tag category
            category = self.tag_category(
                query,
                sample.get("intent", ""),
                client_category
            )

            # Calculate quality
            quality = self.calculate_quality_score(sample)

            # Create aggregated sample
            agg_sample = AggregatedSample(
                sample_id=f"{client_id}_{i}",
                client_id=client_id,
                query=query,
                intent=sample.get("intent", "unknown"),
                response=response,
                category=category,
                quality_score=quality,
                privacy_applied=had_pii,
                metadata={
                    "original_had_pii": had_pii,
                    "confidence": sample.get("confidence", 1.0),
                }
            )

            aggregated.append(agg_sample)
            self._categories.add(category)

        # Track contributions
        self._client_contributions[client_id] = len(aggregated)
        self._aggregated_samples.extend(aggregated)

        logger.info(
            f"Aggregated {len(aggregated)} samples from client {client_id}"
        )

        return aggregated

    def aggregate_from_all_clients(
        self,
        client_samples: Dict[str, List[Dict[str, Any]]],
        client_categories: Optional[Dict[str, str]] = None
    ) -> AggregationResult:
        """
        Aggregate samples from all clients.

        Args:
            client_samples: Samples keyed by client ID
            client_categories: Categories keyed by client ID

        Returns:
            AggregationResult with aggregation details
        """
        self._aggregation_counter += 1
        aggregation_id = f"agg_{self._aggregation_counter}"

        client_categories = client_categories or {}

        total_samples = 0
        samples_by_category: Dict[str, int] = {}
        quality_scores: List[float] = []
        pii_count = 0

        for client_id, samples in client_samples.items():
            category = client_categories.get(client_id)
            aggregated = self.aggregate_from_client(client_id, samples, category)

            total_samples += len(aggregated)

            for sample in aggregated:
                cat = sample.category
                samples_by_category[cat] = samples_by_category.get(cat, 0) + 1
                quality_scores.append(sample.quality_score)
                if sample.privacy_applied:
                    pii_count += 1

        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

        result = AggregationResult(
            aggregation_id=aggregation_id,
            total_clients=len(client_samples),
            total_samples=total_samples,
            samples_by_category=samples_by_category,
            average_quality=avg_quality,
            privacy_metrics={
                "samples_with_pii": pii_count,
                "privacy_budget_used": self.privacy_budget,
                "noise_scale": self.noise_scale,
            }
        )

        logger.info(
            f"Aggregation {aggregation_id}: {total_samples} samples from "
            f"{len(client_samples)} clients, avg quality: {avg_quality:.2f}"
        )

        return result

    def get_training_data(
        self,
        min_quality: float = 0.5
    ) -> List[AggregatedSample]:
        """
        Get training data with quality filter.

        Args:
            min_quality: Minimum quality score

        Returns:
            List of high-quality aggregated samples
        """
        return [
            s for s in self._aggregated_samples
            if s.quality_score >= min_quality
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregator statistics."""
        return {
            "total_samples": len(self._aggregated_samples),
            "total_clients": len(self._client_contributions),
            "categories": list(self._categories),
            "client_contributions": self._client_contributions,
            "aggregations_run": self._aggregation_counter,
            "privacy_budget": self.privacy_budget,
        }


def get_enhanced_aggregator(
    privacy_budget: float = 1.0
) -> EnhancedAggregator:
    """
    Factory function to create an enhanced aggregator.

    Args:
        privacy_budget: Differential privacy budget

    Returns:
        Configured EnhancedAggregator instance
    """
    return EnhancedAggregator(privacy_budget=privacy_budget)
