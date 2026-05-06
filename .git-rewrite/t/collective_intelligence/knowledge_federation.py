"""
Knowledge Federation - Federate knowledge across clients.

CRITICAL: Shares knowledge enrichment, NOT actual client data.
Only FAQ patterns, terminology mappings, and quality improvements are shared.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from enum import Enum
import hashlib
import json
import logging

from .learning_aggregator import IndustryType

logger = logging.getLogger(__name__)


class KnowledgeType(Enum):
    """Types of federated knowledge"""
    FAQ_PATTERN = "faq_pattern"
    TERMINOLOGY = "terminology"
    CATEGORY_STRUCTURE = "category_structure"
    RESPONSE_TEMPLATE = "response_template"
    ESCALATION_TRIGGER = "escalation_trigger"


@dataclass
class IndustryKnowledgePool:
    """
    Industry-specific knowledge pool.
    Contains aggregated knowledge for an industry.
    """
    industry: IndustryType
    knowledge_entries: List[Dict[str, Any]]
    quality_score: float
    contributor_count: int  # Number of clients (anonymized)
    last_updated: datetime
    terminology_mappings: Dict[str, str] = field(default_factory=dict)
    category_structures: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "industry": self.industry.value,
            "knowledge_entries": self.knowledge_entries,
            "quality_score": self.quality_score,
            "contributor_count": self.contributor_count,
            "last_updated": self.last_updated.isoformat(),
            "terminology_mappings": self.terminology_mappings,
            "category_structures": self.category_structures,
        }


@dataclass
class FederatedKnowledge:
    """
    Knowledge that has been federated across clients.
    Contains no client-specific data.
    """
    knowledge_id: str
    knowledge_type: KnowledgeType
    industry: IndustryType
    content: Dict[str, Any]  # Sanitized content
    source_count: int  # Number of clients contributing
    quality_score: float
    created_at: datetime
    enriched_at: Optional[datetime] = None
    version: int = 1

    def __post_init__(self):
        """Generate knowledge ID if needed"""
        if not self.knowledge_id:
            content_hash = hashlib.sha256(
                json.dumps(self.content, sort_keys=True).encode()
            ).hexdigest()[:16]
            self.knowledge_id = f"fk_{content_hash}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "knowledge_id": self.knowledge_id,
            "knowledge_type": self.knowledge_type.value,
            "industry": self.industry.value,
            "content": self.content,
            "source_count": self.source_count,
            "quality_score": self.quality_score,
            "created_at": self.created_at.isoformat(),
            "enriched_at": self.enriched_at.isoformat() if self.enriched_at else None,
            "version": self.version,
        }


class KnowledgeFederation:
    """
    Manages knowledge federation across clients.

    CRITICAL: Never exposes client data. Only federates:
    - FAQ patterns (questions without answers)
    - Terminology mappings
    - Category structures
    - Response templates (generic)
    """

    def __init__(self, min_contributors: int = 2):
        """
        Initialize knowledge federation.

        Args:
            min_contributors: Minimum contributors to federate knowledge
        """
        self.min_contributors = min_contributors
        self._industry_pools: Dict[IndustryType, IndustryKnowledgePool] = {}
        self._federated_knowledge: Dict[str, FederatedKnowledge] = {}
        self._terminology_registry: Dict[str, Dict[str, str]] = {}

    def add_client_knowledge(
        self,
        client_id: str,
        industry: IndustryType,
        knowledge_type: KnowledgeType,
        content: Dict[str, Any]
    ) -> bool:
        """
        Add client knowledge to federation pool.

        Args:
            client_id: Client identifier
            industry: Client's industry
            knowledge_type: Type of knowledge
            content: Sanitized knowledge content

        Returns:
            True if added successfully
        """
        # Validate content is sanitized
        if not self._validate_content(content):
            logger.warning(f"Invalid content from {client_id}")
            return False

        # Get or create industry pool
        if industry not in self._industry_pools:
            self._industry_pools[industry] = IndustryKnowledgePool(
                industry=industry,
                knowledge_entries=[],
                quality_score=0.0,
                contributor_count=0,
                last_updated=datetime.now(),
            )

        pool = self._industry_pools[industry]

        # Add entry with anonymized source
        entry = {
            "knowledge_type": knowledge_type.value,
            "content": content,
            "client_hash": hashlib.sha256(client_id.encode()).hexdigest()[:8],
            "timestamp": datetime.now().isoformat(),
        }

        pool.knowledge_entries.append(entry)
        pool.last_updated = datetime.now()

        logger.debug(f"Added knowledge from {client_id} to {industry.value} pool")
        return True

    def federate_knowledge(self) -> List[FederatedKnowledge]:
        """
        Federate knowledge from industry pools.

        CRITICAL: Only creates federated knowledge if enough contributors
        to prevent re-identification.

        Returns:
            List of newly federated knowledge items
        """
        federated = []

        for industry, pool in self._industry_pools.items():
            # Count unique contributors
            unique_contributors = set(
                entry["client_hash"] for entry in pool.knowledge_entries
            )

            if len(unique_contributors) < self.min_contributors:
                continue

            # Group by knowledge type
            by_type: Dict[KnowledgeType, List[Dict]] = {}
            for entry in pool.knowledge_entries:
                ktype = KnowledgeType(entry["knowledge_type"])
                if ktype not in by_type:
                    by_type[ktype] = []
                by_type[ktype].append(entry)

            # Federate each knowledge type
            for ktype, entries in by_type.items():
                federated_item = self._create_federated_knowledge(
                    industry, ktype, entries
                )
                if federated_item:
                    self._federated_knowledge[federated_item.knowledge_id] = federated_item
                    federated.append(federated_item)

            # Update pool stats
            pool.contributor_count = len(unique_contributors)
            pool.quality_score = self._calculate_pool_quality(pool)

        logger.info(f"Federated {len(federated)} knowledge items")
        return federated

    def get_faq_enrichment(
        self,
        industry: IndustryType
    ) -> List[Dict[str, Any]]:
        """
        Get FAQ enrichment for an industry.

        Args:
            industry: Target industry

        Returns:
            List of FAQ patterns and suggestions
        """
        enrichments = []

        for knowledge in self._federated_knowledge.values():
            if knowledge.industry != industry:
                continue

            if knowledge.knowledge_type == KnowledgeType.FAQ_PATTERN:
                enrichments.append({
                    "pattern": knowledge.content.get("pattern"),
                    "category": knowledge.content.get("category"),
                    "frequency": knowledge.content.get("frequency"),
                    "quality_score": knowledge.quality_score,
                })

        # Sort by quality score
        enrichments.sort(key=lambda x: x["quality_score"], reverse=True)
        return enrichments[:50]  # Top 50

    def get_terminology_mapping(
        self,
        industry: IndustryType
    ) -> Dict[str, str]:
        """
        Get terminology mapping for an industry.

        Returns standardized term mappings.
        """
        if industry not in self._terminology_registry:
            return {}

        return self._terminology_registry[industry]

    def add_terminology_mapping(
        self,
        industry: IndustryType,
        client_term: str,
        standard_term: str
    ) -> None:
        """Add a terminology mapping"""
        if industry not in self._terminology_registry:
            self._terminology_registry[industry] = {}
        self._terminology_registry[industry][client_term] = standard_term

    def get_industry_pool(self, industry: IndustryType) -> Optional[IndustryKnowledgePool]:
        """Get industry knowledge pool"""
        return self._industry_pools.get(industry)

    def get_federation_stats(self) -> Dict[str, Any]:
        """Get federation statistics"""
        stats = {
            "total_industries": len(self._industry_pools),
            "total_federated_items": len(self._federated_knowledge),
            "by_industry": {},
            "by_type": {},
        }

        # By industry
        for industry, pool in self._industry_pools.items():
            stats["by_industry"][industry.value] = {
                "entries": len(pool.knowledge_entries),
                "contributors": pool.contributor_count,
                "quality": pool.quality_score,
            }

        # By type
        for knowledge in self._federated_knowledge.values():
            ktype = knowledge.knowledge_type.value
            stats["by_type"][ktype] = stats["by_type"].get(ktype, 0) + 1

        return stats

    def _validate_content(self, content: Dict[str, Any]) -> bool:
        """Validate content doesn't contain sensitive data"""
        content_str = json.dumps(content).lower()

        sensitive_patterns = [
            "@", "phone", "email", "ssn", "credit card",
            "password", "api_key", "secret", "token",
            "patient_id", "medical_record", "phi",
            "account_number", "routing_number"
        ]

        for pattern in sensitive_patterns:
            if pattern in content_str:
                return False

        return True

    def _create_federated_knowledge(
        self,
        industry: IndustryType,
        knowledge_type: KnowledgeType,
        entries: List[Dict]
    ) -> Optional[FederatedKnowledge]:
        """Create federated knowledge from entries"""
        # Count unique sources
        sources = set(entry["client_hash"] for entry in entries)

        if len(sources) < self.min_contributors:
            return None

        # Aggregate content
        aggregated_content = self._aggregate_content(entries)

        # Calculate quality score
        quality = self._calculate_knowledge_quality(entries)

        return FederatedKnowledge(
            knowledge_id="",
            knowledge_type=knowledge_type,
            industry=industry,
            content=aggregated_content,
            source_count=len(sources),
            quality_score=quality,
            created_at=datetime.now(),
        )

    def _aggregate_content(self, entries: List[Dict]) -> Dict[str, Any]:
        """Aggregate content from multiple entries"""
        # Extract common patterns
        all_content = [entry["content"] for entry in entries]

        # For FAQ patterns, find common structures
        if all_content and isinstance(all_content[0], dict):
            keys = set()
            for content in all_content:
                keys.update(content.keys())

            return {
                "pattern": self._extract_pattern(all_content),
                "frequency": len(entries),
                "common_keys": list(keys),
            }

        return {"entries": len(entries)}

    def _extract_pattern(self, contents: List[Dict]) -> str:
        """Extract common pattern from contents"""
        # Simple pattern extraction
        if not contents:
            return ""

        # Find most common category
        categories = [c.get("category", "unknown") for c in contents if isinstance(c, dict)]
        if categories:
            return f"category_{max(set(categories), key=categories.count)}"

        return "generic_pattern"

    def _calculate_knowledge_quality(self, entries: List[Dict]) -> float:
        """Calculate quality score for knowledge"""
        # Base quality on number of sources
        sources = set(entry["client_hash"] for entry in entries)
        source_factor = min(len(sources) / 5.0, 1.0) * 0.5

        # Recency factor
        timestamps = [
            datetime.fromisoformat(entry["timestamp"])
            for entry in entries
        ]
        if timestamps:
            avg_age = (datetime.now() - min(timestamps)).days
            recency_factor = max(0, 1 - avg_age / 30) * 0.3
        else:
            recency_factor = 0

        # Consistency factor
        consistency_factor = 0.2

        return round(source_factor + recency_factor + consistency_factor, 2)

    def _calculate_pool_quality(self, pool: IndustryKnowledgePool) -> float:
        """Calculate quality score for industry pool"""
        if not pool.knowledge_entries:
            return 0.0

        return self._calculate_knowledge_quality(pool.knowledge_entries)


def federate_knowledge_bases(
    client_knowledge: List[Dict[str, Any]],
    min_contributors: int = 2
) -> List[FederatedKnowledge]:
    """
    Convenience function to federate knowledge.

    Args:
        client_knowledge: List of client knowledge items
        min_contributors: Minimum contributors

    Returns:
        List of federated knowledge items
    """
    federation = KnowledgeFederation(min_contributors=min_contributors)

    for item in client_knowledge:
        federation.add_client_knowledge(
            client_id=item["client_id"],
            industry=IndustryType(item["industry"]),
            knowledge_type=KnowledgeType(item["knowledge_type"]),
            content=item["content"],
        )

    return federation.federate_knowledge()
