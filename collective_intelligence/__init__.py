"""
Collective Intelligence System - Privacy-Preserving Cross-Client Learning

This package provides collective intelligence capabilities for PARWA:
- Learning aggregation across clients WITHOUT sharing data
- Pattern sharing with differential privacy
- Knowledge federation for FAQ enrichment
- Privacy-preserving data combination

CRITICAL: No client-specific data is ever shared between clients.
Only anonymized, aggregated patterns are exchanged.
"""

from .learning_aggregator import (
    LearningAggregator,
    AggregatedPattern,
    ClientLearning,
    PatternType,
    IndustryType,
    aggregate_client_learnings,
)

from .pattern_sharing import (
    PatternSharing,
    SharedPattern,
    PatternVersion,
    PatternStatus,
    share_patterns_across_clients,
)

from .knowledge_federation import (
    KnowledgeFederation,
    FederatedKnowledge,
    IndustryKnowledgePool,
    KnowledgeType,
    federate_knowledge_bases,
)

from .privacy_preserving_share import (
    PrivacyPreservingShare,
    DifferentialPrivacyConfig,
    KAnonymityConfig,
    ShareAuditEntry,
    PrivacyLevel,
    ShareStatus,
    create_privacy_preserving_share,
)

__version__ = "1.0.0"
__all__ = [
    # Enums
    "PatternType",
    "IndustryType",
    "KnowledgeType",
    "PatternStatus",
    "PrivacyLevel",
    "ShareStatus",
    # Learning Aggregator
    "LearningAggregator",
    "AggregatedPattern",
    "ClientLearning",
    "aggregate_client_learnings",
    # Pattern Sharing
    "PatternSharing",
    "SharedPattern",
    "PatternVersion",
    "share_patterns_across_clients",
    # Knowledge Federation
    "KnowledgeFederation",
    "FederatedKnowledge",
    "IndustryKnowledgePool",
    "federate_knowledge_bases",
    # Privacy Preserving Share
    "PrivacyPreservingShare",
    "DifferentialPrivacyConfig",
    "KAnonymityConfig",
    "ShareAuditEntry",
    "create_privacy_preserving_share",
]
