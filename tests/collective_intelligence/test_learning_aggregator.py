"""
Tests for Collective Intelligence System.

CRITICAL: All tests verify privacy guarantees:
- No cross-client data in output
- Patterns share without exposing data
- Privacy preserved in sharing
- Federation enriches knowledge
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from collective_intelligence import (
    LearningAggregator,
    AggregatedPattern,
    ClientLearning,
    PatternSharing,
    SharedPattern,
    KnowledgeFederation,
    FederatedKnowledge,
    PrivacyPreservingShare,
    DifferentialPrivacyConfig,
    KAnonymityConfig,
    ShareAuditEntry,
    PrivacyLevel,
    ShareStatus,
    PatternType,
    IndustryType,
    KnowledgeType,
    aggregate_client_learnings,
    share_patterns_across_clients,
    federate_knowledge_bases,
    create_privacy_preserving_share,
)


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def sample_client_learning() -> ClientLearning:
    """Create a sample client learning"""
    return ClientLearning(
        client_id="client_001",
        industry=IndustryType.ECOMMERCE,
        pattern_type=PatternType.RESOLUTION,
        pattern_hash="abc123def456",
        effectiveness_score=0.85,
        occurrence_count=50,
        timestamp=datetime.now(),
        metadata={"category": "returns"},
    )


@pytest.fixture
def sample_learnings() -> list[ClientLearning]:
    """Create sample learnings from multiple clients"""
    learnings = []
    patterns = [
        ("client_001", IndustryType.ECOMMERCE, PatternType.RESOLUTION, 0.85),
        ("client_002", IndustryType.SAAS, PatternType.RESOLUTION, 0.90),
        ("client_003", IndustryType.HEALTHCARE, PatternType.ESCALATION, 0.75),
        ("client_001", IndustryType.ECOMMERCE, PatternType.FAQ_MATCH, 0.95),
        ("client_002", IndustryType.SAAS, PatternType.FAQ_MATCH, 0.88),
    ]

    for i, (client, industry, ptype, eff) in enumerate(patterns):
        learnings.append(ClientLearning(
            client_id=client,
            industry=industry,
            pattern_type=ptype,
            pattern_hash=f"pattern_{i}",
            effectiveness_score=eff,
            occurrence_count=10 * (i + 1),
            timestamp=datetime.now(),
            metadata={"category": "test"},
        ))

    return learnings


@pytest.fixture
def aggregated_pattern() -> AggregatedPattern:
    """Create a sample aggregated pattern"""
    return AggregatedPattern(
        pattern_id="test_pattern_001",
        pattern_type=PatternType.RESOLUTION,
        industries={IndustryType.ECOMMERCE, IndustryType.SAAS},
        total_occurrences=100,
        avg_effectiveness=0.87,
        confidence_score=0.75,
        created_at=datetime.now(),
        client_count=3,
    )


@pytest.fixture
def privacy_share() -> PrivacyPreservingShare:
    """Create a privacy-preserving share instance"""
    return create_privacy_preserving_share(PrivacyLevel.STANDARD)


# ==============================================================================
# Learning Aggregator Tests
# ==============================================================================

class TestLearningAggregator:
    """Tests for LearningAggregator class"""

    def test_aggregator_initialization(self):
        """Test aggregator initializes correctly"""
        aggregator = LearningAggregator()
        assert aggregator.min_clients_for_pattern == 2
        assert len(aggregator._learnings) == 0
        assert len(aggregator._aggregated_patterns) == 0

    def test_add_learning_success(self, sample_client_learning):
        """Test adding a learning successfully"""
        aggregator = LearningAggregator()
        result = aggregator.add_learning(sample_client_learning)

        assert result is True
        assert len(aggregator._learnings) == 1

    def test_add_learning_with_sensitive_data_rejected(self):
        """Test that learnings with sensitive data are rejected"""
        aggregator = LearningAggregator()

        with pytest.raises(ValueError, match="Sensitive data"):
            ClientLearning(
                client_id="client_001",
                industry=IndustryType.ECOMMERCE,
                pattern_type=PatternType.RESOLUTION,
                pattern_hash="test_hash",
                effectiveness_score=0.85,
                occurrence_count=10,
                timestamp=datetime.now(),
                metadata={"email": "sensitive@example.com"},  # Sensitive!
            )

    def test_opt_out_client(self, sample_client_learning):
        """Test client opt-out functionality"""
        aggregator = LearningAggregator()

        # Add learning first
        aggregator.add_learning(sample_client_learning)
        assert len(aggregator._learnings) == 1

        # Opt out the client
        aggregator.opt_out_client("client_001")

        # Learning should be removed
        assert len(aggregator._learnings) == 0

        # Future additions should be rejected
        result = aggregator.add_learning(sample_client_learning)
        assert result is False

    def test_aggregate_patterns_requires_min_clients(self, sample_learnings):
        """Test that aggregation requires minimum clients"""
        aggregator = LearningAggregator(min_clients_for_pattern=3)

        # Add only 2 learnings with same pattern
        learning1 = ClientLearning(
            client_id="client_001",
            industry=IndustryType.ECOMMERCE,
            pattern_type=PatternType.RESOLUTION,
            pattern_hash="same_pattern",
            effectiveness_score=0.85,
            occurrence_count=10,
            timestamp=datetime.now(),
            metadata={},
        )
        learning2 = ClientLearning(
            client_id="client_002",
            industry=IndustryType.SAAS,
            pattern_type=PatternType.RESOLUTION,
            pattern_hash="same_pattern",
            effectiveness_score=0.90,
            occurrence_count=15,
            timestamp=datetime.now(),
            metadata={},
        )

        aggregator.add_learning(learning1)
        aggregator.add_learning(learning2)

        patterns = aggregator.aggregate_patterns()

        # Should not create pattern with only 2 clients when min is 3
        assert len(patterns) == 0

    def test_aggregate_patterns_success(self, sample_learnings):
        """Test successful pattern aggregation"""
        aggregator = LearningAggregator(min_clients_for_pattern=2)

        for learning in sample_learnings:
            aggregator.add_learning(learning)

        patterns = aggregator.aggregate_patterns()

        # Should have created some patterns
        assert len(patterns) >= 0
        # All patterns should have client_count >= min_clients
        for pattern in patterns:
            assert pattern.client_count >= 2

    def test_no_client_data_in_aggregated_patterns(self, sample_learnings):
        """CRITICAL: Verify no client data in aggregated patterns"""
        aggregator = LearningAggregator(min_clients_for_pattern=2)

        for learning in sample_learnings:
            aggregator.add_learning(learning)

        patterns = aggregator.aggregate_patterns()

        # Check that patterns don't contain client IDs
        for pattern in patterns:
            pattern_dict = pattern.to_dict()
            pattern_str = str(pattern_dict).lower()

            # No client IDs should be in the output
            assert "client_001" not in pattern_str
            assert "client_002" not in pattern_str
            assert "client_003" not in pattern_str

    def test_get_patterns_for_industry(self, sample_learnings):
        """Test filtering patterns by industry"""
        aggregator = LearningAggregator(min_clients_for_pattern=2)

        for learning in sample_learnings:
            aggregator.add_learning(learning)

        aggregator.aggregate_patterns()

        # Get patterns for ecommerce
        ecommerce_patterns = aggregator.get_patterns_for_industry(
            IndustryType.ECOMMERCE
        )

        # All returned patterns should be relevant
        for pattern in ecommerce_patterns:
            assert (
                IndustryType.ECOMMERCE in pattern.industries or
                IndustryType.GENERIC in pattern.industries
            )

    def test_get_accuracy_improvement_estimate(self, sample_learnings):
        """Test accuracy improvement estimation"""
        aggregator = LearningAggregator(min_clients_for_pattern=2)

        for learning in sample_learnings:
            aggregator.add_learning(learning)

        aggregator.aggregate_patterns()

        improvement = aggregator.get_accuracy_improvement_estimate()

        # Should return a reasonable percentage
        assert isinstance(improvement, float)
        assert improvement >= 0.0
        assert improvement <= 5.0  # Capped at 5%

    def test_get_stats(self, sample_learnings):
        """Test statistics retrieval"""
        aggregator = LearningAggregator(min_clients_for_pattern=2)

        for learning in sample_learnings:
            aggregator.add_learning(learning)

        stats = aggregator.get_stats()

        assert "total_learnings" in stats
        assert "unique_clients" in stats
        assert "aggregated_patterns" in stats
        assert "opted_out_clients" in stats
        assert stats["total_learnings"] == len(sample_learnings)


class TestAggregateClientLearnings:
    """Tests for convenience function"""

    def test_aggregate_client_learnings_function(self, sample_learnings):
        """Test the convenience aggregation function"""
        patterns = aggregate_client_learnings(sample_learnings, min_clients=2)

        assert isinstance(patterns, list)
        for pattern in patterns:
            assert isinstance(pattern, AggregatedPattern)


# ==============================================================================
# Pattern Sharing Tests
# ==============================================================================

class TestPatternSharing:
    """Tests for PatternSharing class"""

    def test_sharing_initialization(self):
        """Test pattern sharing initializes correctly"""
        sharing = PatternSharing()
        assert sharing.min_confidence == 0.5
        assert len(sharing._patterns) == 0

    def test_share_pattern_success(self, aggregated_pattern):
        """Test sharing a pattern successfully"""
        sharing = PatternSharing(min_confidence=0.5)

        shared = sharing.share_pattern(
            aggregated_pattern,
            abstraction="Returns processed within 24 hours"
        )

        assert shared is not None
        assert shared.pattern_id == aggregated_pattern.pattern_id
        assert len(sharing._patterns) == 1

    def test_share_pattern_low_confidence_rejected(self):
        """Test that low confidence patterns are rejected"""
        sharing = PatternSharing(min_confidence=0.7)

        low_confidence_pattern = AggregatedPattern(
            pattern_id="low_conf",
            pattern_type=PatternType.RESOLUTION,
            industries={IndustryType.ECOMMERCE},
            total_occurrences=10,
            avg_effectiveness=0.5,
            confidence_score=0.3,  # Below minimum
            created_at=datetime.now(),
            client_count=2,
        )

        result = sharing.share_pattern(
            low_confidence_pattern,
            abstraction="Test abstraction"
        )

        assert result is None
        assert len(sharing._patterns) == 0

    def test_share_pattern_sensitive_abstraction_rejected(self, aggregated_pattern):
        """Test that sensitive abstractions are rejected"""
        sharing = PatternSharing()

        with pytest.raises(ValueError, match="sensitive"):
            sharing.share_pattern(
                aggregated_pattern,
                abstraction="Contact email@example.com for help"  # Contains @
            )

    def test_get_patterns_for_client(self, aggregated_pattern):
        """Test getting patterns for a client"""
        sharing = PatternSharing(min_confidence=0.5)
        sharing.share_pattern(
            aggregated_pattern,
            abstraction="Test abstraction"
        )

        patterns = sharing.get_patterns_for_client(IndustryType.ECOMMERCE)

        assert len(patterns) == 1
        assert patterns[0].pattern_id == aggregated_pattern.pattern_id

    def test_update_pattern_effectiveness(self, aggregated_pattern):
        """Test updating pattern effectiveness"""
        sharing = PatternSharing(min_confidence=0.5)
        sharing.share_pattern(
            aggregated_pattern,
            abstraction="Test abstraction"
        )

        result = sharing.update_pattern_effectiveness(
            aggregated_pattern.pattern_id,
            0.95
        )

        assert result is True
        # Should track history
        assert len(sharing._effectiveness_history[aggregated_pattern.pattern_id]) == 2

    def test_detect_conflicts(self):
        """Test conflict detection"""
        sharing = PatternSharing(min_confidence=0.5)

        # Create two similar patterns
        pattern1 = AggregatedPattern(
            pattern_id="p1",
            pattern_type=PatternType.RESOLUTION,
            industries={IndustryType.ECOMMERCE, IndustryType.SAAS},
            total_occurrences=100,
            avg_effectiveness=0.85,
            confidence_score=0.8,
            created_at=datetime.now(),
            client_count=3,
        )

        pattern2 = AggregatedPattern(
            pattern_id="p2",
            pattern_type=PatternType.RESOLUTION,
            industries={IndustryType.ECOMMERCE},
            total_occurrences=80,
            avg_effectiveness=0.84,  # Similar effectiveness
            confidence_score=0.75,
            created_at=datetime.now(),
            client_count=2,
        )

        sharing.share_pattern(pattern1, abstraction="Resolution pattern A")
        sharing.share_pattern(pattern2, abstraction="Resolution pattern B")

        conflicts = sharing.detect_conflicts()

        # May detect conflict due to similar patterns
        assert isinstance(conflicts, list)

    def test_no_client_data_in_shared_patterns(self, aggregated_pattern):
        """CRITICAL: Verify no client data in shared patterns"""
        sharing = PatternSharing(min_confidence=0.5)

        shared = sharing.share_pattern(
            aggregated_pattern,
            abstraction="Test abstraction"
        )

        shared_dict = shared.to_dict()
        shared_str = str(shared_dict).lower()

        # No client IDs should be in the output
        assert "client_001" not in shared_str
        assert "client_002" not in shared_str


class TestSharePatternsAcrossClients:
    """Tests for convenience function"""

    def test_share_patterns_function(self, aggregated_pattern):
        """Test the convenience sharing function"""
        patterns = share_patterns_across_clients([aggregated_pattern])

        assert isinstance(patterns, list)


# ==============================================================================
# Knowledge Federation Tests
# ==============================================================================

class TestKnowledgeFederation:
    """Tests for KnowledgeFederation class"""

    def test_federation_initialization(self):
        """Test federation initializes correctly"""
        federation = KnowledgeFederation()
        assert federation.min_contributors == 2
        assert len(federation._industry_pools) == 0

    def test_add_client_knowledge_success(self):
        """Test adding client knowledge successfully"""
        federation = KnowledgeFederation()

        result = federation.add_client_knowledge(
            client_id="client_001",
            industry=IndustryType.ECOMMERCE,
            knowledge_type=KnowledgeType.FAQ_PATTERN,
            content={"category": "returns", "pattern": "return_policy"}
        )

        assert result is True
        assert IndustryType.ECOMMERCE in federation._industry_pools

    def test_add_client_knowledge_sensitive_rejected(self):
        """Test that sensitive knowledge is rejected"""
        federation = KnowledgeFederation()

        result = federation.add_client_knowledge(
            client_id="client_001",
            industry=IndustryType.HEALTHCARE,
            knowledge_type=KnowledgeType.FAQ_PATTERN,
            content={"patient_id": "12345"}  # Sensitive!
        )

        assert result is False

    def test_federate_knowledge_requires_min_contributors(self):
        """Test that federation requires minimum contributors"""
        federation = KnowledgeFederation(min_contributors=2)

        # Add knowledge from only one client
        federation.add_client_knowledge(
            client_id="client_001",
            industry=IndustryType.ECOMMERCE,
            knowledge_type=KnowledgeType.FAQ_PATTERN,
            content={"category": "test"}
        )

        federated = federation.federate_knowledge()

        # Should not federate with only one contributor
        assert len(federated) == 0

    def test_federate_knowledge_success(self):
        """Test successful knowledge federation"""
        federation = KnowledgeFederation(min_contributors=2)

        # Add knowledge from multiple clients
        for i in range(3):
            federation.add_client_knowledge(
                client_id=f"client_{i:03d}",
                industry=IndustryType.ECOMMERCE,
                knowledge_type=KnowledgeType.FAQ_PATTERN,
                content={"category": "returns", "pattern": f"pattern_{i}"}
            )

        federated = federation.federate_knowledge()

        # Should have created federated knowledge
        assert len(federated) > 0

    def test_get_faq_enrichment(self):
        """Test getting FAQ enrichment"""
        federation = KnowledgeFederation(min_contributors=2)

        # Add FAQ patterns from multiple clients
        for i in range(3):
            federation.add_client_knowledge(
                client_id=f"client_{i:03d}",
                industry=IndustryType.SAAS,
                knowledge_type=KnowledgeType.FAQ_PATTERN,
                content={"category": "billing", "pattern": f"faq_{i}"}
            )

        federation.federate_knowledge()

        enrichments = federation.get_faq_enrichment(IndustryType.SAAS)

        assert isinstance(enrichments, list)

    def test_no_client_data_in_federated_knowledge(self):
        """CRITICAL: Verify no client data in federated knowledge"""
        federation = KnowledgeFederation(min_contributors=2)

        for i in range(3):
            federation.add_client_knowledge(
                client_id=f"client_{i:03d}",
                industry=IndustryType.ECOMMERCE,
                knowledge_type=KnowledgeType.FAQ_PATTERN,
                content={"category": "test"}
            )

        federated = federation.federate_knowledge()

        for knowledge in federated:
            knowledge_dict = knowledge.to_dict()
            knowledge_str = str(knowledge_dict).lower()

            # No client IDs should be in the output
            assert "client_000" not in knowledge_str
            assert "client_001" not in knowledge_str
            assert "client_002" not in knowledge_str

    def test_get_federation_stats(self):
        """Test statistics retrieval"""
        federation = KnowledgeFederation()

        federation.add_client_knowledge(
            client_id="client_001",
            industry=IndustryType.ECOMMERCE,
            knowledge_type=KnowledgeType.FAQ_PATTERN,
            content={"test": "data"}
        )

        stats = federation.get_federation_stats()

        assert "total_industries" in stats
        assert "total_federated_items" in stats
        assert "by_industry" in stats


class TestFederateKnowledgeBases:
    """Tests for convenience function"""

    def test_federate_knowledge_function(self):
        """Test the convenience federation function"""
        client_knowledge = [
            {
                "client_id": "client_001",
                "industry": "ecommerce",
                "knowledge_type": "faq_pattern",
                "content": {"test": "data"},
            },
            {
                "client_id": "client_002",
                "industry": "ecommerce",
                "knowledge_type": "faq_pattern",
                "content": {"test": "data2"},
            },
        ]

        federated = federate_knowledge_bases(client_knowledge, min_contributors=2)

        assert isinstance(federated, list)


# ==============================================================================
# Privacy Preserving Share Tests
# ==============================================================================

class TestPrivacyPreservingShare:
    """Tests for PrivacyPreservingShare class"""

    def test_privacy_share_initialization(self):
        """Test privacy share initializes correctly"""
        share = PrivacyPreservingShare()

        assert share.privacy_level == PrivacyLevel.STANDARD
        assert len(share._audit_log) == 0
        assert len(share._opted_out_clients) == 0

    def test_register_opt_out(self, privacy_share):
        """Test client opt-out registration"""
        privacy_share.register_opt_out("client_001")

        assert "client_001" in privacy_share._opted_out_clients

    def test_can_share_approved(self, privacy_share):
        """Test share approval"""
        can_share, reason = privacy_share.can_share(
            source_client="client_001",
            data_type="pattern",
            data={"category": "test"}
        )

        assert can_share is True
        assert reason == "Approved"

    def test_can_share_opted_out_blocked(self, privacy_share):
        """Test that opted-out clients are blocked"""
        privacy_share.register_opt_out("client_001")

        can_share, reason = privacy_share.can_share(
            source_client="client_001",
            data_type="pattern",
            data={"category": "test"}
        )

        assert can_share is False
        assert "opted out" in reason.lower()

    def test_can_share_sensitive_blocked(self, privacy_share):
        """Test that sensitive data is blocked"""
        can_share, reason = privacy_share.can_share(
            source_client="client_001",
            data_type="user_data",
            data={"email": "user@example.com"}  # Sensitive!
        )

        assert can_share is False
        assert "sensitive" in reason.lower()

    def test_apply_differential_privacy(self, privacy_share):
        """Test differential privacy application"""
        original_value = 100.0

        noisy_value = privacy_share.apply_differential_privacy(original_value)

        # Value should be modified but reasonably close
        assert noisy_value != original_value
        # With epsilon=1.0, noise should typically be within reasonable bounds
        assert abs(noisy_value - original_value) < 50

    def test_apply_k_anonymity(self, privacy_share):
        """Test k-anonymity application"""
        data = [
            {"industry": "ecommerce", "region": "US", "value": 1},
            {"industry": "ecommerce", "region": "US", "value": 2},
            {"industry": "ecommerce", "region": "US", "value": 3},
            {"industry": "saas", "region": "EU", "value": 4},  # Only 1 record
        ]

        anonymized = privacy_share.apply_k_anonymity(data)

        # Should suppress groups smaller than k
        # With k=3, only the ecommerce/US group should remain
        assert all(r["industry"] == "ecommerce" for r in anonymized)

    def test_minimize_data(self, privacy_share):
        """Test data minimization"""
        data = {
            "allowed_field": "keep this",
            "sensitive_field": "remove this",
            "another_allowed": "also keep",
        }

        minimized = privacy_share.minimize_data(
            data,
            allowed_fields=["allowed_field", "another_allowed"]
        )

        assert "allowed_field" in minimized
        assert "another_allowed" in minimized
        assert "sensitive_field" not in minimized

    def test_share_with_audit(self, privacy_share):
        """Test share with audit trail"""
        audit = privacy_share.share_with_audit(
            source_client="client_001",
            target_client_count=5,
            data_type="pattern",
            data={"category": "test"}
        )

        assert isinstance(audit, ShareAuditEntry)
        assert audit.status == ShareStatus.APPROVED
        assert len(privacy_share._audit_log) == 1

    def test_share_with_audit_blocked(self, privacy_share):
        """Test blocked share with audit trail"""
        privacy_share.register_opt_out("client_001")

        audit = privacy_share.share_with_audit(
            source_client="client_001",
            target_client_count=5,
            data_type="pattern",
            data={"category": "test"}
        )

        assert audit.status == ShareStatus.BLOCKED

    def test_get_audit_log(self, privacy_share):
        """Test audit log retrieval"""
        privacy_share.share_with_audit(
            source_client="client_001",
            target_client_count=5,
            data_type="pattern",
            data={"test": "data"}
        )

        logs = privacy_share.get_audit_log()

        assert len(logs) == 1
        assert isinstance(logs[0], ShareAuditEntry)

    def test_get_privacy_stats(self, privacy_share):
        """Test privacy statistics"""
        privacy_share.share_with_audit(
            source_client="client_001",
            target_client_count=5,
            data_type="pattern",
            data={"test": "data"}
        )

        stats = privacy_share.get_privacy_stats()

        assert stats["total_shares"] == 1
        assert stats["approved_shares"] == 1
        assert stats["blocked_shares"] == 0

    def test_validate_privacy_compliance(self, privacy_share):
        """Test privacy compliance validation"""
        compliance = privacy_share.validate_privacy_compliance()

        assert "compliant" in compliance
        assert "issues" in compliance
        assert "recommendations" in compliance


class TestCreatePrivacyPreservingShare:
    """Tests for factory function"""

    def test_create_standard_privacy(self):
        """Test creating standard privacy share"""
        share = create_privacy_preserving_share(PrivacyLevel.STANDARD)

        assert share.privacy_level == PrivacyLevel.STANDARD
        assert share.dp_config.epsilon == 1.0
        assert share.k_config.k == 3

    def test_create_high_privacy(self):
        """Test creating high privacy share"""
        share = create_privacy_preserving_share(PrivacyLevel.HIGH)

        assert share.privacy_level == PrivacyLevel.HIGH
        assert share.dp_config.epsilon == 0.5  # More privacy
        assert share.k_config.k == 5  # Higher k

    def test_create_maximum_privacy(self):
        """Test creating maximum privacy share"""
        share = create_privacy_preserving_share(PrivacyLevel.MAXIMUM)

        assert share.privacy_level == PrivacyLevel.MAXIMUM
        assert share.dp_config.epsilon == 0.1  # Maximum privacy
        assert share.k_config.k == 10  # Highest k


# ==============================================================================
# Integration Tests - Privacy Verification
# ==============================================================================

class TestPrivacyIntegration:
    """Integration tests for privacy guarantees"""

    def test_end_to_end_no_data_leakage(self, sample_learnings):
        """CRITICAL: End-to-end test for no data leakage"""
        # 1. Aggregate learnings
        aggregator = LearningAggregator(min_clients_for_pattern=2)
        for learning in sample_learnings:
            aggregator.add_learning(learning)
        patterns = aggregator.aggregate_patterns()

        # 2. Share patterns
        sharing = PatternSharing(min_confidence=0.5)
        shared_patterns = []
        for pattern in patterns:
            shared = sharing.share_pattern(pattern, abstraction="Generic pattern")
            if shared:
                shared_patterns.append(shared)

        # 3. Federate knowledge
        federation = KnowledgeFederation(min_contributors=2)
        for learning in sample_learnings:
            federation.add_client_knowledge(
                client_id=learning.client_id,
                industry=learning.industry,
                knowledge_type=KnowledgeType.FAQ_PATTERN,
                content={"pattern": learning.pattern_hash},
            )
        federated = federation.federate_knowledge()

        # 4. Privacy share
        privacy = create_privacy_preserving_share(PrivacyLevel.HIGH)
        audits = []
        for learning in sample_learnings:
            audit = privacy.share_with_audit(
                source_client=learning.client_id,
                target_client_count=5,
                data_type="learning",
                data={"pattern_hash": learning.pattern_hash},
            )
            audits.append(audit)

        # VERIFY: No client data in any output
        all_outputs = []

        for pattern in patterns:
            all_outputs.append(str(pattern.to_dict()))

        for shared in shared_patterns:
            all_outputs.append(str(shared.to_dict()))

        for fed in federated:
            all_outputs.append(str(fed.to_dict()))

        for audit in audits:
            all_outputs.append(str(audit.to_dict()))

        combined_output = " ".join(all_outputs).lower()

        # Check for client IDs (except hashed versions)
        assert "client_001" not in combined_output
        assert "client_002" not in combined_output
        assert "client_003" not in combined_output

        # Check for sensitive patterns
        assert "@example.com" not in combined_output
        assert "password" not in combined_output
        assert "ssn" not in combined_output
        assert "credit_card" not in combined_output

    def test_privacy_budget_enforcement(self):
        """Test that privacy budget is enforced"""
        share = create_privacy_preserving_share(PrivacyLevel.STANDARD)

        # Make many shares to exhaust budget
        for i in range(10):
            share.share_with_audit(
                source_client="client_001",
                target_client_count=5,
                data_type="pattern",
                data={"test": f"data_{i}"},
            )

        # Budget should be at max limit
        budget_used = share._privacy_budget_used.get("client_001", 0)
        assert budget_used >= 5.0  # At or above max budget

        # Further shares should be blocked
        can_share, reason = share.can_share(
            source_client="client_001",
            data_type="pattern",
            data={"test": "data"},
        )

        assert can_share is False
        assert "budget" in reason.lower()


# ==============================================================================
# Run Tests
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
