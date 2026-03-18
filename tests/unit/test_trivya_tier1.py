"""
Unit tests for TRIVYA Tier 1 techniques.

Tests CLARA, CRP, GSD Integration, and T1 Orchestrator.
"""
import os
import uuid
import pytest
from datetime import datetime, timezone

# Set test environment variables
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from shared.trivya_techniques.tier1.clara import (
    CLARA,
    CLARAResult,
    CLARAConfig,
)
from shared.trivya_techniques.tier1.crp import (
    CRP,
    CRPResult,
    CRPConfig,
)
from shared.trivya_techniques.tier1.gsd_integration import (
    GSDIntegration,
    GSDIntegrationResult,
    GSDIntegrationConfig,
)
from shared.trivya_techniques.orchestrator import (
    T1Orchestrator,
    T1OrchestratorResult,
    T1OrchestratorConfig,
    ProcessingStage,
)


class TestCLARA:
    """Tests for CLARA - Contextual Learning and Retrieval."""

    def test_clara_initialization(self):
        """Test CLARA initializes correctly."""
        clara = CLARA()

        assert clara.config is not None
        assert clara.config.top_k == 5
        assert clara.config.use_hyde is True

    def test_clara_retrieve_with_context_override(self):
        """Test CLARA retrieval with context override."""
        clara = CLARA()

        result = clara.retrieve(
            query="What is your refund policy?",
            context_override="Our refund policy allows returns within 30 days."
        )

        assert isinstance(result, CLARAResult)
        assert result.query == "What is your refund policy?"
        assert "refund policy" in result.retrieved_context.lower()
        assert result.retrieval_method == "override"

    def test_clara_retrieve_empty_query_raises(self):
        """Test CLARA raises on empty query."""
        clara = CLARA()

        with pytest.raises(ValueError, match="Query cannot be empty"):
            clara.retrieve("")

    def test_clara_config_customization(self):
        """Test CLARA with custom configuration."""
        config = CLARAConfig(
            top_k=10,
            min_relevance_score=0.5,
            use_hyde=False,
            max_context_length=2000
        )
        clara = CLARA(config=config)

        assert clara.config.top_k == 10
        assert clara.config.min_relevance_score == 0.5
        assert clara.config.use_hyde is False

    def test_clara_stats(self):
        """Test CLARA statistics tracking."""
        clara = CLARA()

        # Process a query
        clara.retrieve(
            query="Test query",
            context_override="Test context"
        )

        stats = clara.get_stats()

        assert "queries_processed" in stats
        assert stats["queries_processed"] == 1


class TestCRP:
    """Tests for CRP - Contextual Response Processing."""

    def test_crp_initialization(self):
        """Test CRP initializes correctly."""
        crp = CRP()

        assert crp.config is not None
        assert crp.config.max_response_tokens == 500
        assert crp.config.compress_threshold == 0.8

    def test_crp_process_short_response(self):
        """Test CRP processing short response."""
        crp = CRP()

        result = crp.process(
            response="This is a short response.",
            context_tokens=100,
            max_context_tokens=4000
        )

        assert isinstance(result, CRPResult)
        assert result.original_response == "This is a short response."
        assert result.was_compressed is False

    def test_crp_process_long_response(self):
        """Test CRP processing long response triggers compression."""
        crp = CRP()

        long_response = "This is a very long response. " * 100

        result = crp.process(
            response=long_response,
            context_tokens=3500,  # High context usage
            max_context_tokens=4000
        )

        assert isinstance(result, CRPResult)
        assert result.was_compressed is True
        assert result.processed_tokens < result.original_tokens

    def test_crp_process_empty_response_raises(self):
        """Test CRP raises on empty response."""
        crp = CRP()

        with pytest.raises(ValueError, match="Response cannot be empty"):
            crp.process("")

    def test_crp_preserves_key_phrases(self):
        """Test CRP preserves key phrases during compression."""
        crp = CRP()

        response = (
            "Your refund has been approved. "
            "The cancellation is pending. "
            "Please escalate to a manager if you have concerns. "
        ) * 50  # Make it long enough to trigger compression

        result = crp.process(
            response=response,
            context_tokens=3500,
            max_context_tokens=4000
        )

        # Key phrases should be preserved
        processed_lower = result.processed_response.lower()
        assert "refund" in processed_lower or "approved" in processed_lower

    def test_crp_stats(self):
        """Test CRP statistics tracking."""
        crp = CRP()

        # Process a response
        crp.process(
            response="Test response",
            context_tokens=100,
            max_context_tokens=4000
        )

        stats = crp.get_stats()

        assert "responses_processed" in stats
        assert stats["responses_processed"] == 1


class TestGSDIntegration:
    """Tests for GSD Integration."""

    def test_gsd_integration_initialization(self):
        """Test GSD Integration initializes correctly."""
        gsd = GSDIntegration()

        assert gsd.state_engine is not None
        assert gsd.health_monitor is not None
        assert gsd.clara is not None
        assert gsd.crp is not None

    def test_create_conversation(self):
        """Test creating a conversation."""
        gsd = GSDIntegration()

        conversation = gsd.create_conversation(
            customer_id="test_customer",
            channel="web"
        )

        assert conversation.id is not None
        assert conversation.customer_id == "test_customer"
        assert conversation.channel == "web"

    def test_process_query(self):
        """Test processing a query."""
        gsd = GSDIntegration()

        # Create conversation first
        conv = gsd.create_conversation(customer_id="test_customer")

        result = gsd.process_query(
            conversation_id=conv.id,
            query="What are your hours?",
            perform_retrieval=False  # No KB in test
        )

        assert isinstance(result, GSDIntegrationResult)
        assert result.query == "What are your hours?"
        assert result.turn_count == 1

    def test_process_response(self):
        """Test processing a response."""
        gsd = GSDIntegration()

        # Create conversation and add query
        conv = gsd.create_conversation(customer_id="test_customer")
        gsd.process_query(conv.id, "Test query", perform_retrieval=False)

        result = gsd.process_response(
            conversation_id=conv.id,
            response="We are open 9-5."
        )

        assert isinstance(result, GSDIntegrationResult)
        assert result.crp_result is not None

    def test_escalation_detection(self):
        """Test escalation is detected after many turns."""
        gsd = GSDIntegration(config=GSDIntegrationConfig(
            max_turns_before_escalation=5
        ))

        conv = gsd.create_conversation(customer_id="test_customer")

        # Add multiple queries
        for i in range(6):
            gsd.process_query(
                conversation_id=conv.id,
                query=f"Query {i}",
                perform_retrieval=False
            )

        result = gsd.process_query(
            conversation_id=conv.id,
            query="Final query",
            perform_retrieval=False
        )

        assert result.should_escalate is True

    def test_stats(self):
        """Test GSD Integration statistics."""
        gsd = GSDIntegration()

        conv = gsd.create_conversation(customer_id="test_customer")
        gsd.process_query(conv.id, "Test", perform_retrieval=False)

        stats = gsd.get_stats()

        assert "queries_processed" in stats
        assert stats["queries_processed"] == 1


class TestT1Orchestrator:
    """Tests for T1 Orchestrator."""

    def test_orchestrator_initialization(self):
        """Test orchestrator initializes correctly."""
        orchestrator = T1Orchestrator()

        assert orchestrator.clara is not None
        assert orchestrator.crp is not None
        assert orchestrator.gsd_integration is not None
        assert orchestrator.smart_router is not None

    def test_process_query(self):
        """Test processing a query through orchestrator."""
        orchestrator = T1Orchestrator()

        result = orchestrator.process(
            query="What is your refund policy?"
        )

        assert isinstance(result, T1OrchestratorResult)
        assert result.query == "What is your refund policy?"
        assert result.stage == ProcessingStage.COMPLETED.value

    def test_tier1_always_fires(self):
        """Test that Tier 1 always fires on every query."""
        orchestrator = T1Orchestrator()

        # CLARA should always run
        result = orchestrator.process(query="Test query")

        # Check that CLARA ran (context should be set even if empty)
        assert result.clara_result is not None or result.context is not None

    def test_create_conversation_and_process(self):
        """Test creating conversation and processing through it."""
        orchestrator = T1Orchestrator()

        # Create conversation
        conv_id = orchestrator.create_conversation(
            customer_id="test_customer",
            channel="web"
        )

        assert conv_id is not None

        # Process through that conversation
        result = orchestrator.process(
            query="Hello",
            conversation_id=conv_id
        )

        assert result.conversation_id == conv_id

    def test_smart_router_integration(self):
        """Test smart router integration in orchestrator."""
        orchestrator = T1Orchestrator()

        # Simple query should route to light/medium
        simple_result = orchestrator.process(query="What are your hours?")

        # Complex query should route to heavy
        complex_result = orchestrator.process(
            query="I need a refund immediately and want to speak to a manager about this terrible issue!"
        )

        # Complex query should have higher tier
        assert complex_result.selected_tier in ["medium", "heavy"]

    def test_stats(self):
        """Test orchestrator statistics."""
        orchestrator = T1Orchestrator()

        orchestrator.process("Test query 1")
        orchestrator.process("Test query 2")

        stats = orchestrator.get_stats()

        assert stats["queries_processed"] == 2
        assert "average_processing_time_ms" in stats

    def test_empty_query_raises(self):
        """Test empty query raises ValueError."""
        orchestrator = T1Orchestrator()

        with pytest.raises(ValueError, match="Query cannot be empty"):
            orchestrator.process("")


class TestIntegration:
    """Integration tests for T1 pipeline."""

    def test_full_pipeline(self):
        """Test full T1 pipeline from query to response."""
        orchestrator = T1Orchestrator()

        # Create conversation
        conv_id = orchestrator.create_conversation(
            customer_id="integration_test"
        )

        # Process query
        query_result = orchestrator.process(
            query="I need help with my order",
            conversation_id=conv_id
        )

        assert query_result.stage == ProcessingStage.COMPLETED.value

        # Process response
        response_result = orchestrator.process_with_response(
            query="I need help with my order",
            response="I'd be happy to help with your order. Can you provide your order number?",
            conversation_id=conv_id
        )

        assert response_result.crp_result is not None

    def test_context_accumulation(self):
        """Test context accumulates across turns."""
        orchestrator = T1Orchestrator()

        conv_id = orchestrator.create_conversation()

        # First turn
        orchestrator.process(query="Hello", conversation_id=conv_id)

        # Second turn
        result = orchestrator.process(query="How are you?", conversation_id=conv_id)

        # Turn count should increase
        assert result.gsd_result.turn_count == 2

    def test_budget_downgrade(self):
        """Test budget-based tier downgrade."""
        orchestrator = T1Orchestrator()

        # Process with critical budget
        result = orchestrator.process(
            query="I need help with a complex issue",
            budget_remaining=0.5  # Critical budget
        )

        # Should use light tier due to budget
        assert result.selected_tier == "light"
