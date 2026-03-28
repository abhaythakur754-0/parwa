"""
Intent Detection Unit Tests - Week 35
Tests for Intent Detection Enhancement achieving 93%+ accuracy
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from shared.smart_router.intent.detector import (
    IntentDetector, DetectedIntent, IntentHierarchy, IntentCategory as DetectorIntentCategory
)
from shared.smart_router.intent.entity_extractor import (
    EntityExtractor, Entity, EntityType
)
from shared.smart_router.intent.slot_filler import (
    SlotFiller, Slot, SlotStatus, SlotFillingResult
)
from shared.smart_router.intent.intent_classifier import (
    IntentClassifier, IntentDefinition, ClassificationResult, IntentCategory
)


class TestIntentDetector:
    """Tests for Intent Detection"""
    
    @pytest.fixture
    def detector(self):
        return IntentDetector()
    
    def test_detector_initializes(self, detector):
        """Test: IntentDetector initializes correctly"""
        assert detector is not None
        assert detector.is_initialized()
    
    def test_detects_primary_intent(self, detector):
        """Test: Detects primary intent"""
        queries = [
            ("Where is my order?", "check_order_status"),
            ("I want a refund", "request_refund"),
            ("Cancel my order", "cancel_order"),
        ]
        
        for query, expected_intent in queries:
            hierarchy = detector.detect(query)
            assert hierarchy.primary.intent == expected_intent
            assert hierarchy.primary.is_primary
    
    def test_detects_multiple_intents(self, detector):
        """Test: Detects multiple intents"""
        query = "I want a refund and where is my order?"
        hierarchy = detector.detect(query)
        
        # Should have primary intent
        assert hierarchy.primary is not None
        
        # May have secondary intents
        assert isinstance(hierarchy.secondary, list)
    
    def test_disambiguates_unclear_intents(self, detector):
        """Test: Disambiguates unclear intents"""
        query = "I need help with my order"
        candidates = ["check_order_status", "report_issue", "contact_support"]
        
        result = detector.disambiguate(query, candidates)
        
        assert result.intent in candidates
        assert result.confidence > 0
    
    def test_intent_hierarchy(self, detector):
        """Test: Intent hierarchy for complex queries"""
        query = "I want a refund for my order"
        hierarchy = detector.detect(query)
        
        # Primary should be refund
        assert hierarchy.primary.intent == "request_refund"
        
        # May have related intents
        related = hierarchy.related_intents
        assert isinstance(related, list)
    
    def test_implicit_intent_detection(self, detector):
        """Test: Implicit intent detection"""
        query = "yes"
        history = [
            {"intent": "check_order_status", "query": "Where is my order?"}
        ]
        
        implicit = detector.detect_implicit(query, history)
        
        assert isinstance(implicit, list)
    
    def test_confidence_scoring(self, detector):
        """Test: Intent confidence scoring"""
        result = detector.detect("I want a full refund for my order ABC-123")
        
        assert 0 <= result.primary.confidence <= 1
    
    def test_accuracy_tracking(self, detector):
        """Test: Accuracy tracking works"""
        detector.record_outcome(True)
        detector.record_outcome(True)
        detector.record_outcome(False)
        
        accuracy = detector.get_accuracy()
        assert abs(accuracy - 2/3) < 0.01


class TestEntityExtractor:
    """Tests for Entity Extraction"""
    
    @pytest.fixture
    def extractor(self):
        return EntityExtractor()
    
    def test_extractor_initializes(self, extractor):
        """Test: EntityExtractor initializes correctly"""
        assert extractor is not None
        assert extractor.is_initialized()
    
    def test_extracts_order_ids(self, extractor):
        """Test: Extracts order IDs"""
        texts = [
            "My order ABC-12345 is missing",
            "Order #987654321 hasn't arrived",
            "Check order XYZ-99999",
        ]
        
        for text in texts:
            entities = extractor.extract(text)
            order_entities = [e for e in entities if e.type == EntityType.ORDER_ID]
            assert len(order_entities) > 0, f"Failed to extract order ID from: {text}"
    
    def test_extracts_amounts(self, extractor):
        """Test: Extracts monetary amounts"""
        texts = [
            "I was charged $99.99",
            "Refund $1,234.56 please",
            "The amount is 50 dollars",
        ]
        
        for text in texts:
            entities = extractor.extract(text)
            amount_entities = [e for e in entities if e.type == EntityType.AMOUNT]
            assert len(amount_entities) > 0, f"Failed to extract amount from: {text}"
    
    def test_links_to_knowledge_base(self, extractor):
        """Test: Links to knowledge base"""
        text = "My order ABC-12345"
        entities = extractor.extract(text)
        
        # Entities should have metadata
        for entity in entities:
            assert hasattr(entity, 'metadata')
    
    def test_entity_normalization(self, extractor):
        """Test: Entity normalization"""
        # Amount normalization
        entities = extractor.extract("$1,234.56")
        for e in entities:
            if e.type == EntityType.AMOUNT:
                assert e.normalized_value == 1234.56
        
        # Email normalization
        entities = extractor.extract("Email: TEST@EXAMPLE.COM")
        for e in entities:
            if e.type == EntityType.EMAIL:
                assert e.normalized_value == "test@example.com"
    
    def test_confidence_scoring(self, extractor):
        """Test: Entity confidence scoring"""
        entities = extractor.extract("Order ABC-12345 charged $99.99")
        
        for entity in entities:
            assert 0 <= entity.confidence <= 1
    
    def test_get_order_ids_helper(self, extractor):
        """Test: Get order IDs helper"""
        text = "Orders ABC-123 and XYZ-456"
        order_ids = extractor.get_order_ids(text)
        
        assert len(order_ids) == 2
    
    def test_get_amounts_helper(self, extractor):
        """Test: Get amounts helper"""
        text = "Charged $50 and $100"
        amounts = extractor.get_amounts(text)
        
        assert len(amounts) == 2
        assert 50.0 in amounts
        assert 100.0 in amounts


class TestSlotFiller:
    """Tests for Slot Filling"""
    
    @pytest.fixture
    def filler(self):
        return SlotFiller()
    
    def test_filler_initializes(self, filler):
        """Test: SlotFiller initializes correctly"""
        assert filler is not None
        assert filler.is_initialized()
    
    def test_identifies_required_slots(self, filler):
        """Test: Identifies required slots"""
        required = filler.get_required_slots('request_refund')
        
        assert 'order_id' in required
        assert 'reason' in required
    
    def test_extracts_slot_values(self, filler):
        """Test: Extracts slot values"""
        entities = {
            'order_id': 'ABC-12345',
            'reason': 'Product defective'
        }
        
        result = filler.fill_slots('request_refund', entities)
        
        assert result.slots['order_id'].value == 'ABC-12345'
        assert result.slots['reason'].value == 'Product defective'
    
    def test_validates_slot_values(self, filler):
        """Test: Validates slot values"""
        # Valid order ID
        is_valid, _ = filler.validate_slot('order_id', 'ABC-12345')
        assert is_valid
        
        # Invalid order ID
        is_valid, _ = filler.validate_slot('order_id', 'invalid')
        assert not is_valid
    
    def test_missing_slot_prompting(self, filler):
        """Test: Missing slot prompting"""
        entities = {}  # No entities provided
        result = filler.fill_slots('check_order_status', entities)
        
        # Should identify missing required slot
        assert 'order_id' in result.missing_required
        
        # Should provide prompt
        prompt = filler.get_missing_slots_prompt(result.missing_required)
        assert len(prompt) > 0
    
    def test_slot_inheritance_from_context(self, filler):
        """Test: Slot inheritance from context"""
        entities = {}
        context = {
            'order_id': 'ABC-12345',
            'previous_queries': 5
        }
        
        result = filler.fill_slots('check_order_status', entities, context)
        
        # Should inherit order_id from context
        assert result.slots['order_id'].value == 'ABC-12345'
        assert result.slots['order_id'].source == 'inherited'
    
    def test_slot_confirmation(self, filler):
        """Test: Slot confirmation"""
        slot = filler.confirm_slot('request_refund', 'order_id', 'ABC-12345')
        
        assert slot.status == SlotStatus.CONFIRMED
        assert slot.value == 'ABC-12345'
    
    def test_session_slot_management(self, filler):
        """Test: Session slot management"""
        session_id = "test-session-123"
        
        filler.update_slot(session_id, 'order_id', 'ABC-12345')
        
        slots = filler.get_session_slots(session_id)
        assert 'order_id' in slots
        
        filler.clear_session_slots(session_id)
        slots = filler.get_session_slots(session_id)
        assert len(slots) == 0


class TestIntentClassifier:
    """Tests for Intent Classification"""
    
    @pytest.fixture
    def classifier(self):
        return IntentClassifier()
    
    def test_classifier_initializes(self, classifier):
        """Test: IntentClassifier initializes correctly"""
        assert classifier is not None
        assert classifier.is_initialized()
    
    def test_classifies_predefined_intents(self, classifier):
        """Test: Classifies predefined intents"""
        test_cases = [
            ("I want to buy this product", "place_order"),
            ("Cancel my order", "cancel_order"),
            ("Where is my order?", "check_order_status"),
            ("Hello there", "greeting"),
            ("Thank you for your help", "thanks"),
        ]
        
        for query, expected_intent in test_cases:
            result = classifier.classify(query)
            assert result.intent == expected_intent, f"Failed: {query} -> {result.intent} (expected {expected_intent})"
    
    def test_learns_custom_intents(self, classifier):
        """Test: Learns custom intents"""
        classifier.add_custom_intent(
            name='check_weather',
            category=IntentCategory.INFORMATIONAL,
            description='Check weather conditions',
            examples=['What\'s the weather?', 'Is it going to rain?'],
            keywords=['weather', 'rain', 'sunny', 'forecast']
        )
        
        result = classifier.classify("What's the weather today?")
        assert result.intent == 'check_weather'
    
    def test_confidence_calibration(self, classifier):
        """Test: Confidence calibration works"""
        # Classify a query
        result = classifier.classify("I want a refund")
        
        # Calibrate based on feedback
        classifier.calibrate_confidence('request_refund', result.confidence, True)
        
        # Next classification should use calibrated confidence
        result2 = classifier.classify("I want my money back")
        assert result2.calibration_score > 0
    
    def test_intent_taxonomy(self, classifier):
        """Test: Intent taxonomy retrieval"""
        taxonomy = classifier.get_taxonomy()
        
        assert isinstance(taxonomy, dict)
        assert len(taxonomy) > 0
        assert 'place_order' in taxonomy
    
    def test_intent_clusters(self, classifier):
        """Test: Intent clustering"""
        clusters = classifier.get_intent_clusters()
        
        assert 'transactional' in clusters
        assert 'informational' in clusters
        assert 'support' in clusters
    
    def test_few_shot_learning(self, classifier):
        """Test: Few-shot learning from feedback"""
        # Learn from feedback
        classifier.learn_from_feedback(
            "My package hasn't arrived yet",
            "check_order_status"
        )
        
        # Should now classify better
        result = classifier.classify("Package not arrived")
        assert result.intent == "check_order_status"


class TestIntentAccuracy:
    """Tests for 93%+ accuracy target"""
    
    @pytest.fixture
    def detector(self):
        return IntentDetector()
    
    @pytest.fixture
    def classifier(self):
        return IntentClassifier()
    
    def test_intent_detection_accuracy_target(self, detector):
        """Test: Intent detection achieves ≥93% accuracy"""
        test_cases = [
            # Check order status
            ("Where is my order?", "check_order_status"),
            ("Track my package", "check_order_status"),
            ("Order status for ABC-123", "check_order_status"),
            ("When will my order arrive?", "check_order_status"),
            ("Has my order shipped?", "check_order_status"),
            
            # Request refund
            ("I want a refund", "request_refund"),
            ("Refund my order", "request_refund"),
            ("I need my money back", "request_refund"),
            ("Return this item", "request_refund"),
            
            # Cancel order
            ("Cancel my order", "cancel_order"),
            ("I want to cancel", "cancel_order"),
            ("Stop my order", "cancel_order"),
            
            # Contact support
            ("Let me speak to a human", "contact_support"),
            ("I need an agent", "contact_support"),
            ("Connect me to support", "contact_support"),
            ("Escalate this issue", "contact_support"),
            
            # Report issue
            ("Something is broken", "report_issue"),
            ("There's an error", "report_issue"),
            ("It's not working", "report_issue"),
            ("I'm having a problem", "report_issue"),
            
            # Greeting
            ("Hello", "greeting"),
            ("Hi there", "greeting"),
            ("Good morning", "greeting"),
            
            # Thanks
            ("Thank you", "thanks"),
            ("Thanks for your help", "thanks"),
            ("I appreciate it", "thanks"),
        ]
        
        correct = 0
        total = len(test_cases)
        
        for query, expected_intent in test_cases:
            hierarchy = detector.detect(query)
            if hierarchy.primary.intent == expected_intent:
                correct += 1
        
        accuracy = correct / total
        print(f"\nIntent Detection Accuracy: {accuracy:.2%} ({correct}/{total})")
        
        assert accuracy >= 0.93, f"Accuracy {accuracy:.2%} below 93% target"
    
    def test_classification_accuracy_target(self, classifier):
        """Test: Intent classification achieves ≥93% accuracy"""
        test_cases = [
            ("I want to buy this", "place_order"),
            ("Purchase this item", "place_order"),
            ("Order this product", "place_order"),
            
            ("Cancel my order", "cancel_order"),
            ("Stop the order", "cancel_order"),
            
            ("Where is my order?", "check_order_status"),
            ("Track package", "check_order_status"),
            
            ("I want a refund", "request_refund"),
            ("Money back please", "request_refund"),
            
            ("Hello", "greeting"),
            ("Hi", "greeting"),
            
            ("Thank you", "thanks"),
            ("Thanks", "thanks"),
            
            ("Goodbye", "goodbye"),
            ("Bye", "goodbye"),
        ]
        
        correct = 0
        total = len(test_cases)
        
        for query, expected_intent in test_cases:
            result = classifier.classify(query)
            if result.intent == expected_intent:
                correct += 1
        
        accuracy = correct / total
        print(f"\nIntent Classification Accuracy: {accuracy:.2%} ({correct}/{total})")
        
        assert accuracy >= 0.93, f"Accuracy {accuracy:.2%} below 93% target"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
