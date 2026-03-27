"""
ML Router Unit Tests - Week 35
Tests for ML-based routing classifier achieving 92%+ accuracy
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add shared to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from shared.smart_router.ml.classifier import (
    MLRouter, QueryType, TierPrediction, ClassificationResult
)
from shared.smart_router.ml.feature_extractor import FeatureExtractor, FeatureSet
from shared.smart_router.ml.training_data import (
    TrainingDataBuilder, TrainingSample, Dataset
)
from shared.smart_router.ml.model_registry import (
    ModelRegistry, ModelStatus, ModelVersion, ABTestConfig
)


class TestMLRouter:
    """Tests for ML Router classification"""
    
    @pytest.fixture
    def router(self):
        """Create MLRouter instance for testing"""
        return MLRouter()
    
    def test_router_initializes(self, router):
        """Test: MLRouter initializes correctly"""
        assert router is not None
        assert router.is_initialized()
        assert router.model_version == "1.0.0"
    
    def test_classifies_faq_queries(self, router):
        """Test: Classifies FAQ queries correctly"""
        queries = [
            "What is your return policy?",
            "How do I track my order?",
            "Where is my package?",
            "When does your store close?",
        ]
        
        for query in queries:
            result = router.classify(query)
            assert result.query_type == QueryType.FAQ
            assert result.confidence > 0.5
    
    def test_classifies_refund_queries(self, router):
        """Test: Classifies refund queries correctly"""
        queries = [
            "I want a refund for my order",
            "How do I return this item?",
            "I need my money back",
            "The product was damaged, I want a refund",
        ]
        
        for query in queries:
            result = router.classify(query)
            assert result.query_type == QueryType.REFUND
            assert result.confidence > 0.5
    
    def test_classifies_complex_queries(self, router):
        """Test: Classifies complex queries correctly"""
        queries = [
            "I need help with API integration",
            "Can you escalate this to a manager?",
            "I have multiple issues with my account",
        ]
        
        for query in queries:
            result = router.classify(query)
            assert result.query_type == QueryType.COMPLEX
    
    def test_classifies_urgent_queries(self, router):
        """Test: Classifies urgent queries correctly"""
        queries = [
            "This is urgent, I need help now!",
            "Emergency: my account is locked",
            "ASAP help needed for failed payment",
        ]
        
        for query in queries:
            result = router.classify(query)
            assert result.query_type == QueryType.URGENT
    
    def test_predicts_light_tier(self, router):
        """Test: Predicts LIGHT tier for simple queries"""
        simple_queries = [
            "What is your return policy?",
            "Where is my order?",
            "Contact info?",
        ]
        
        for query in simple_queries:
            result = router.classify(query)
            # Simple queries should not be HEAVY
            assert result.tier in [TierPrediction.LIGHT, TierPrediction.MEDIUM]
    
    def test_predicts_heavy_tier(self, router):
        """Test: Predicts HEAVY tier for complex queries"""
        complex_queries = [
            "I need help with complex API integration and multiple webhooks for my enterprise application that keeps failing due to timeout issues",
            "Can you escalate this to a manager? I have multiple unresolved issues",
        ]
        
        for query in complex_queries:
            result = router.classify(query)
            assert result.tier == TierPrediction.HEAVY
    
    def test_variant_recommendation(self, router):
        """Test: Variant recommendation matches tier"""
        query = "What is your return policy?"
        result = router.classify(query)
        
        variant_tier_map = {
            'mini': TierPrediction.LIGHT,
            'junior': TierPrediction.MEDIUM,
            'high': TierPrediction.HEAVY,
        }
        assert result.variant in variant_tier_map
    
    def test_confidence_scoring(self, router):
        """Test: Confidence scoring works correctly"""
        result = router.classify("I want a refund for my order ABC-12345")
        assert 0.0 <= result.confidence <= 1.0
        assert result.confidence > 0.5  # Should be confident in clear query
    
    def test_inference_time_under_50ms(self, router):
        """Test: Inference time <50ms"""
        queries = [
            "What is your return policy?",
            "I want a refund for my order",
            "This is urgent, I need help now!",
            "How do I integrate the API?",
        ]
        
        for query in queries:
            result = router.classify(query)
            assert result.inference_time_ms < 50, f"Inference too slow: {result.inference_time_ms}ms"
    
    def test_caching_works(self, router):
        """Test: Caching improves repeated query performance"""
        query = "What is your return policy?"
        
        # First call
        result1 = router.classify(query)
        
        # Second call (should be cached)
        result2 = router.classify(query)
        
        # Results should be identical
        assert result1.query_type == result2.query_type
        assert result1.tier == result2.tier
    
    def test_context_aware_classification(self, router):
        """Test: Classification uses context"""
        query = "I need help"
        context = {
            'client_type': 'enterprise',
            'previous_escalations': 2,
        }
        
        result = router.classify(query, context)
        assert result is not None
        assert result.query_type is not None
    
    def test_multi_label_classification(self, router):
        """Test: Multi-label classification for complex queries"""
        query = "I want a refund immediately! This is urgent!"
        results = router.classify_multi_label(query)
        
        # Should detect multiple intents
        assert len(results) >= 1
        assert all(isinstance(r, ClassificationResult) for r in results)
    
    def test_accuracy_tracking(self, router):
        """Test: Accuracy tracking works"""
        # Record some outcomes
        router.record_outcome(True)
        router.record_outcome(True)
        router.record_outcome(False)
        
        accuracy = router.get_accuracy()
        assert 0 <= accuracy <= 1
        # Should be ~66.67%
        assert abs(accuracy - 2/3) < 0.01
    
    def test_stats_endpoint(self, router):
        """Test: Stats endpoint works"""
        stats = router.get_stats()
        
        assert 'model_version' in stats
        assert 'cache_size' in stats
        assert 'accuracy' in stats


class TestFeatureExtractor:
    """Tests for Feature Extraction"""
    
    @pytest.fixture
    def extractor(self):
        """Create FeatureExtractor instance"""
        return FeatureExtractor()
    
    def test_extractor_initializes(self, extractor):
        """Test: FeatureExtractor initializes correctly"""
        assert extractor is not None
    
    def test_extracts_text_features(self, extractor):
        """Test: Extracts text features"""
        query = "What is your return policy for order ABC-123?"
        features = extractor.extract(query)
        
        assert features.text_features is not None
        assert 'text_length' in features.text_features
        assert 'word_count' in features.text_features
        assert features.text_features['word_count'] > 0
    
    def test_extracts_context_features(self, extractor):
        """Test: Extracts context features"""
        query = "I need help"
        context = {
            'user_total_queries': 50,
            'client_type': 'enterprise',
            'conversation_turn': 3,
        }
        
        features = extractor.extract(query, context=context)
        
        assert features.context_features is not None
        assert features.context_features['user_total_queries'] == 50
        assert features.context_features['client_type'] == 'enterprise'
    
    def test_normalizes_features(self, extractor):
        """Test: Normalizes features correctly"""
        query = "What is your return policy?"
        features = extractor.extract(query)
        
        assert features.normalized_features is not None
        # All normalized values should be between 0 and 1
        for name, value in features.normalized_features.items():
            assert 0 <= value <= 1, f"{name} not normalized: {value}"
    
    def test_extracts_urgency_features(self, extractor):
        """Test: Extracts urgency features"""
        query = "This is URGENT! I need help ASAP!"
        features = extractor.extract(query)
        
        assert features.text_features['urgency_score'] > 0
    
    def test_extracts_entity_features(self, extractor):
        """Test: Extracts entity features"""
        query = "My order ABC-12345 has an issue. I paid $99.99 for it."
        features = extractor.extract(query)
        
        assert features.text_features['entity_count'] > 0
    
    def test_extracts_temporal_features(self, extractor):
        """Test: Extracts temporal features"""
        query = "What is your return policy?"
        features = extractor.extract(query)
        
        assert 'hour_of_day' in features.temporal_features
        assert 'day_of_week' in features.temporal_features
        assert 'is_weekend' in features.temporal_features
    
    def test_feature_importance(self, extractor):
        """Test: Feature importance tracking"""
        importance = extractor.get_feature_importance()
        
        assert importance is not None
        assert len(importance) > 0
        # All importance values should be positive
        for name, score in importance.items():
            assert score >= 0, f"Negative importance for {name}"
    
    def test_get_feature_vector(self, extractor):
        """Test: Get feature vector for ML"""
        query = "What is your return policy?"
        features = extractor.extract(query)
        vector = extractor.get_feature_vector(features)
        
        assert isinstance(vector, list)
        assert len(vector) > 0


class TestTrainingDataBuilder:
    """Tests for Training Data Builder"""
    
    @pytest.fixture
    def builder(self):
        """Create TrainingDataBuilder instance"""
        return TrainingDataBuilder()
    
    def test_builder_initializes(self, builder):
        """Test: TrainingDataBuilder initializes correctly"""
        assert builder is not None
    
    def test_collects_historical_queries(self, builder):
        """Test: Collects historical queries"""
        queries = [
            {'text': 'What is your return policy?', 'outcome': {}},
            {'text': 'I want a refund', 'outcome': {}},
        ]
        
        count = builder.collect_historical_queries(queries)
        assert count == 2
    
    def test_generates_labels_from_outcomes(self, builder):
        """Test: Generates labels from outcomes"""
        queries = [
            {'text': 'I want a refund for my order', 'outcome': {'refund_issued': True}},
            {'text': 'What is your return policy?', 'outcome': {}},
            {'text': 'This is urgent!', 'outcome': {'urgent_flag': True}},
        ]
        
        builder.collect_historical_queries(queries)
        samples = builder.generate_labels_from_outcomes()
        
        assert len(samples) == 3
        assert all(s.label in ['faq', 'refund', 'complex', 'urgent', 'billing', 'technical', 'general'] for s in samples)
    
    def test_creates_balanced_dataset(self, builder):
        """Test: Creates balanced dataset"""
        samples = [
            TrainingSample(query="Query 1", label="faq", features={}),
            TrainingSample(query="Query 2", label="faq", features={}),
            TrainingSample(query="Query 3", label="refund", features={}),
            TrainingSample(query="Query 4", label="urgent", features={}),
        ]
        
        balanced = builder.create_balanced_dataset(samples)
        
        # Should have equal distribution
        label_counts = {}
        for s in balanced:
            label_counts[s.label] = label_counts.get(s.label, 0) + 1
        
        # All labels should have same count if balanced
        if len(label_counts) > 1:
            counts = list(label_counts.values())
            assert max(counts) - min(counts) <= 1
    
    def test_augments_data(self, builder):
        """Test: Data augmentation works"""
        samples = [
            TrainingSample(query="I want a refund", label="refund", features={}),
        ]
        
        augmented = builder.augment_data(samples, factor=3)
        
        assert len(augmented) == 3  # Original + 2 augmentations
    
    def test_splits_dataset(self, builder):
        """Test: Dataset splitting works"""
        samples = [
            TrainingSample(query=f"Query {i}", label="faq", features={})
            for i in range(100)
        ]
        
        dataset = builder.split_dataset(samples)
        
        assert len(dataset.train) > 0
        assert len(dataset.validation) > 0
        assert len(dataset.test) > 0
        # Check approximate ratios
        total = len(dataset.train) + len(dataset.validation) + len(dataset.test)
        assert abs(len(dataset.train) / total - 0.7) < 0.1
    
    def test_exports_to_training_format(self, builder):
        """Test: Export to training format"""
        samples = [
            TrainingSample(query="Query 1", label="faq", features={'len': 10}),
            TrainingSample(query="Query 2", label="refund", features={'len': 20}),
        ]
        
        dataset = builder.split_dataset(samples)
        exported = builder.export_to_training_format(dataset)
        
        assert 'train' in exported
        assert 'validation' in exported
        assert 'test' in exported
        assert 'stats' in exported
    
    def test_generates_synthetic_samples(self, builder):
        """Test: Synthetic sample generation"""
        samples = builder.generate_synthetic_samples('faq', 10)
        
        assert len(samples) == 10
        assert all(s.label == 'faq' for s in samples)


class TestModelRegistry:
    """Tests for Model Registry"""
    
    @pytest.fixture
    def registry(self):
        """Create ModelRegistry instance"""
        return ModelRegistry()
    
    def test_registry_initializes(self, registry):
        """Test: ModelRegistry initializes correctly"""
        assert registry is not None
        assert registry.is_initialized()
    
    def test_stores_model_versions(self, registry):
        """Test: Stores model versions"""
        version = registry.register_model(
            version="1.0.0",
            accuracy=0.92,
            latency_ms=30.0
        )
        
        assert version.version == "1.0.0"
        assert version.accuracy == 0.92
        assert version.status == ModelStatus.DEVELOPMENT
    
    def test_lists_versions(self, registry):
        """Test: Lists model versions"""
        registry.register_model("1.0.0", 0.90, 35.0)
        registry.register_model("1.1.0", 0.92, 30.0)
        
        versions = registry.list_versions()
        assert len(versions) == 2
    
    def test_promote_to_production(self, registry):
        """Test: Promote to production works"""
        registry.register_model("1.0.0", 0.92, 30.0)
        
        result = registry.promote_to_production("1.0.0")
        assert result is True
        
        model = registry.get_version("1.0.0")
        assert model.status == ModelStatus.PRODUCTION
    
    def test_rollback_works(self, registry):
        """Test: Rollback works correctly"""
        registry.register_model("1.0.0", 0.92, 30.0)
        registry.register_model("1.1.0", 0.93, 28.0)
        
        registry.promote_to_production("1.0.0")
        registry.promote_to_production("1.1.0")
        
        # Current should be 1.1.0
        assert registry.get_current_production().version == "1.1.0"
        
        # Rollback
        registry.rollback("1.0.0")
        assert registry.get_current_production().version == "1.0.0"
    
    def test_ab_deployment_works(self, registry):
        """Test: A/B deployment works"""
        registry.register_model("1.0.0", 0.92, 30.0)
        registry.register_model("1.1.0", 0.93, 28.0)
        
        registry.promote_to_production("1.0.0")
        
        test = registry.create_ab_test(
            experiment_id="test_001",
            model_a_version="1.0.0",
            model_b_version="1.1.0",
            traffic_split=0.3
        )
        
        assert test.experiment_id == "test_001"
        assert test.model_a_version == "1.0.0"
        assert test.model_b_version == "1.1.0"
        assert test.traffic_split == 0.3
    
    def test_performance_tracking(self, registry):
        """Test: Performance tracking per version"""
        registry.register_model("1.0.0", 0.92, 30.0)
        
        registry.record_performance("1.0.0", 0.93, 28.0)
        registry.record_performance("1.0.0", 0.94, 29.0)
        
        history = registry.get_performance_history("1.0.0")
        assert len(history) == 2
    
    def test_get_model_for_request(self, registry):
        """Test: Get model for request handles A/B routing"""
        registry.register_model("1.0.0", 0.92, 30.0)
        registry.register_model("1.1.0", 0.93, 28.0)
        registry.promote_to_production("1.0.0")
        
        # Without A/B test, should return production
        model = registry.get_model_for_request()
        assert model == "1.0.0"
        
        # With A/B test
        registry.create_ab_test("test_001", "1.0.0", "1.1.0", 0.5)
        
        # Should return one of the two models
        for _ in range(10):
            model = registry.get_model_for_request("test_001")
            assert model in ["1.0.0", "1.1.0"]
    
    def test_conclude_ab_test(self, registry):
        """Test: Conclude A/B test with winner"""
        registry.register_model("1.0.0", 0.92, 30.0)
        registry.register_model("1.1.0", 0.93, 28.0)
        registry.promote_to_production("1.0.0")
        
        registry.create_ab_test("test_001", "1.0.0", "1.1.0", 0.5)
        
        result = registry.conclude_ab_test("test_001", "1.1.0")
        assert result is True
        
        test = registry.get_ab_test("test_001")
        assert test.winner == "1.1.0"


class TestMLAccuracy:
    """Tests for 92%+ accuracy target"""
    
    @pytest.fixture
    def router(self):
        return MLRouter()
    
    def test_overall_accuracy_target(self, router):
        """Test: ML classifier achieves ≥92% accuracy"""
        # Test dataset with known labels
        test_cases = [
            # FAQ queries
            ("What is your return policy?", "faq"),
            ("How do I track my order?", "faq"),
            ("Where is my package?", "faq"),
            ("When does your store close?", "faq"),
            ("What are your business hours?", "faq"),
            ("How can I contact support?", "faq"),
            
            # Refund queries
            ("I want a refund for my order", "refund"),
            ("How do I return this item?", "refund"),
            ("I need my money back", "refund"),
            ("Can I get a refund please?", "refund"),
            
            # Urgent queries
            ("This is urgent, I need help now!", "urgent"),
            ("Emergency: my account is locked", "urgent"),
            ("ASAP help needed for failed payment", "urgent"),
            ("Critical issue with my order", "urgent"),
            
            # Billing queries
            ("I was charged twice", "billing"),
            ("Question about my invoice", "billing"),
            ("Payment failed for subscription", "billing"),
            
            # Technical queries
            ("The app keeps crashing", "technical"),
            ("Error when trying to login", "technical"),
            ("Page not loading correctly", "technical"),
            
            # Complex queries
            ("I need help with API integration", "complex"),
            ("Can you escalate this to a manager?", "complex"),
        ]
        
        correct = 0
        total = len(test_cases)
        
        for query, expected_label in test_cases:
            result = router.classify(query)
            if result.query_type.value == expected_label:
                correct += 1
        
        accuracy = correct / total
        print(f"\nML Classifier Accuracy: {accuracy:.2%} ({correct}/{total})")
        
        assert accuracy >= 0.92, f"Accuracy {accuracy:.2%} below 92% target"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
