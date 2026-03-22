"""
Full AI Pipeline Integration Tests.

Tests the complete PARWA AI pipeline:
- GSD State Engine (conversation state management)
- Smart Router (query routing)
- Knowledge Base (RAG retrieval)
- TRIVYA Techniques (T1, T2, T3)
- MCP Server Integration
- Guardrails

This test suite validates end-to-end functionality across all components.
"""
import pytest
import asyncio
import time
from datetime import datetime
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# GSD Engine imports
from shared.gsd_engine.state_schema import (
    ConversationState, MessageRole, Message, ContextMetadata
)
from shared.gsd_engine.context_health import ContextHealthMonitor
from shared.gsd_engine.compression import ContextCompressor

# Smart Router imports
from shared.smart_router.router import SmartRouter, AITier
from shared.smart_router.tier_config import TierConfig
from shared.smart_router.complexity_scorer import ComplexityScorer

# Knowledge Base imports
from shared.knowledge_base.kb_manager import KnowledgeBaseManager
from shared.knowledge_base.rag_pipeline import RAGPipeline

# TRIVYA imports
from shared.trivya_techniques.orchestrator import T1Orchestrator
from shared.trivya_techniques.tier1.clara import CLARA
from shared.trivya_techniques.tier1.crp import CRP

# MCP Server imports
from mcp_servers.knowledge.faq_server import FAQServer
from mcp_servers.knowledge.rag_server import RAGServer
from mcp_servers.knowledge.kb_server import KBServer
from mcp_servers.integrations.ticketing_server import TicketingServer
from mcp_servers.tools.notification_server import NotificationServer
from mcp_servers.tools.compliance_server import ComplianceServer
from mcp_servers.tools.sla_server import SLAServer

# Guardrails imports
from shared.guardrails.guardrails import GuardrailsManager, GuardrailRule
from shared.guardrails.approval_enforcer import ApprovalEnforcer, ApprovalStatus


# ═══════════════════════════════════════════════════════════════════════════════
# GSD ENGINE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestGSDEngineIntegration:
    """Integration tests for GSD State Engine."""

    @pytest.fixture
    def health_monitor(self):
        """Create ContextHealthMonitor instance."""
        return ContextHealthMonitor()

    @pytest.fixture
    def compressor(self):
        """Create ContextCompressor instance."""
        return ContextCompressor()

    def test_conversation_state_creation(self):
        """Test creating and managing conversation state."""
        # Create new conversation
        state = ConversationState(
            customer_id="customer_001",
            channel="web"
        )

        assert state is not None
        assert state.customer_id == "customer_001"

        # Add messages
        state.add_message(MessageRole.USER, "What is your refund policy?", 20)
        state.add_message(MessageRole.ASSISTANT, "Our refund policy allows returns within 30 days.", 25)

        assert len(state.messages) == 2
        assert state.context.message_count == 2

    def test_context_health_checking(self, health_monitor):
        """Test context health evaluation."""
        # Create a conversation state
        state = ConversationState(
            conversation_id=uuid4(),
            messages=[]
        )

        # Add some messages
        for i in range(10):
            state.add_message(MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                             f"Message {i}", 50)

        # Check health
        health_result = health_monitor.check_health(state)

        assert health_result is not None
        assert health_result.message_count == 10

    def test_context_compression(self, compressor):
        """Test context compression for long conversations."""
        # Create state with many messages
        state = ConversationState(conversation_id=uuid4())
        
        for i in range(20):
            role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
            content = f"Message {i}: " + "x" * 100
            state.add_message(role, content, 50)

        original_count = len(state.messages)

        # Compress
        compressed = compressor.compress(state)

        assert compressed is not None
        # Should have compressed the messages
        assert len(compressed.messages) <= original_count


# ═══════════════════════════════════════════════════════════════════════════════
# SMART ROUTER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSmartRouterIntegration:
    """Integration tests for Smart Router."""

    @pytest.fixture
    def router(self):
        """Create SmartRouter instance."""
        return SmartRouter()

    @pytest.fixture
    def complexity_scorer(self):
        """Create ComplexityScorer instance."""
        return ComplexityScorer()

    def test_route_simple_query(self, router):
        """Test routing of simple queries."""
        tier, metadata = router.route("What is your refund policy?")

        assert tier in [AITier.LIGHT, AITier.MEDIUM, AITier.HEAVY]
        assert metadata is not None
        assert "complexity_score" in metadata

    def test_route_complex_query(self, router):
        """Test routing of complex queries."""
        complex_query = """
        I ordered three items last week but only received two. 
        The missing item was a birthday gift for my daughter. 
        I need to know: 
        1. How can I track the missing item?
        2. Can I get expedited shipping if it's lost?
        3. What compensation is available for the delay?
        4. How do I escalate this to a manager?
        """

        tier, metadata = router.route(complex_query)

        assert tier in [AITier.MEDIUM, AITier.HEAVY]
        assert metadata["complexity_score"] > 0.5

    def test_complexity_scoring(self, complexity_scorer):
        """Test complexity scoring."""
        simple_score = complexity_scorer.score("Hello")
        complex_score = complexity_scorer.score(
            "I need to dispute a charge and get a refund for a defective product"
        )

        # Complex queries should have higher scores
        assert simple_score is not None
        assert complex_score is not None


# ═══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestKnowledgeBaseIntegration:
    """Integration tests for Knowledge Base."""

    @pytest.fixture
    def kb_manager(self):
        """Create KnowledgeBaseManager instance."""
        return KnowledgeBaseManager()

    @pytest.fixture
    def rag_pipeline(self):
        """Create RAGPipeline instance."""
        return RAGPipeline()

    def test_knowledge_ingestion(self, kb_manager):
        """Test document ingestion."""
        result = kb_manager.ingest_document(
            content="Our refund policy allows returns within 30 days of purchase.",
            metadata={"category": "policy"}
        )

        assert result is not None
        assert result.status == "success"

    def test_rag_pipeline_creation(self, rag_pipeline):
        """Test RAG pipeline can be created."""
        assert rag_pipeline is not None


# ═══════════════════════════════════════════════════════════════════════════════
# TRIVYA TECHNIQUES TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestTRIVYATechniquesIntegration:
    """Integration tests for TRIVYA techniques."""

    @pytest.fixture
    def orchestrator(self):
        """Create T1Orchestrator instance."""
        return T1Orchestrator()

    @pytest.fixture
    def clara(self):
        """Create CLARA instance."""
        return CLARA()

    @pytest.fixture
    def crp(self):
        """Create CRP instance."""
        return CRP()

    def test_clara_technique(self, clara):
        """Test CLARA technique execution."""
        result = clara.retrieve("What is your refund policy?")

        assert result is not None
        assert result.query == "What is your refund policy?"

    def test_crp_technique(self, crp):
        """Test CRP technique execution."""
        # CRP processes and optimizes responses
        result = crp.process("This is a very long response that needs to be processed for context efficiency.")
        
        assert result is not None
        assert result.processed_response is not None

    def test_t1_orchestrator_process(self, orchestrator):
        """Test T1 Orchestrator processing."""
        result = orchestrator.process("How do I return a product?")

        assert result is not None
        assert result.query == "How do I return a product?"
        assert result.selected_tier in ["light", "medium", "heavy"]


# ═══════════════════════════════════════════════════════════════════════════════
# FULL PIPELINE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullAIPipeline:
    """Full AI pipeline integration tests."""

    def test_simple_query_pipeline(self):
        """Test simple query through full pipeline."""
        query = "What are your business hours?"

        # 1. Route query
        router = SmartRouter()
        tier, routing_metadata = router.route(query)
        assert tier is not None

        # 2. Process through T1
        orchestrator = T1Orchestrator()
        result = orchestrator.process(query)
        assert result is not None

        # 3. Apply guardrails to response
        guardrails = GuardrailsManager()
        ai_response = "Our business hours are 9 AM to 6 PM, Monday through Friday."
        sanitized = guardrails.sanitize_response(ai_response)
        assert sanitized is not None

    def test_complex_refund_query_pipeline(self):
        """Test complex refund query through full pipeline."""
        query = """
        I ordered a product 2 weeks ago and it arrived damaged.
        I need a full refund and I'm very frustrated with the delay.
        """

        # 1. Route - should go to higher tier
        router = SmartRouter()
        tier, routing_metadata = router.route(query)
        assert tier in [AITier.MEDIUM, AITier.HEAVY]

        # 2. Check guardrails
        guardrails = GuardrailsManager()
        competitor_check = guardrails.check_competitor_mention(query)
        assert competitor_check.passed is True  # No competitors mentioned

        # 3. Process through T1
        orchestrator = T1Orchestrator()
        result = orchestrator.process(query)
        assert result is not None

        # 4. Generate response
        ai_response = "I understand your frustration. I'll help you process a refund."
        halluc_check = guardrails.check_hallucination(ai_response)
        # Should be acceptable
        assert halluc_check.confidence >= 0.5 or halluc_check.passed


# ═══════════════════════════════════════════════════════════════════════════════
# MCP SERVER PIPELINE INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestMCPPipelineIntegration:
    """Integration tests for MCP servers in the pipeline."""

    @pytest.mark.asyncio
    async def test_knowledge_to_notification_pipeline(self):
        """Test knowledge retrieval to notification pipeline."""
        # Initialize servers (skip those needing API keys)
        faq = FAQServer()
        kb = KBServer()
        notification = NotificationServer()

        for server in [faq, kb, notification]:
            await server.start()

        try:
            # 1. Search FAQ
            faq_result = await faq.handle_tool_call(
                "search_faqs",
                {"query": "return policy", "limit": 3}
            )
            assert faq_result.success is True

            # 2. Search KB for more details
            kb_result = await kb.handle_tool_call(
                "search",
                {"query": "damaged product return"}
            )
            assert kb_result.success is True

            # 3. Notify support team
            notif = await notification.handle_tool_call(
                "send_notification",
                {
                    "user_id": "support_team",
                    "message": "New return inquiry received",
                    "channel": "in_app"
                }
            )
            assert notif.success is True

        finally:
            for server in [faq, kb, notification]:
                await server.stop()

    @pytest.mark.asyncio
    async def test_sla_escalation_with_guardrails(self):
        """Test SLA breach triggers escalation with proper guardrails."""
        sla = SLAServer()
        notification = NotificationServer()
        guardrails = GuardrailsManager()

        await sla.start()
        await notification.start()

        try:
            # 1. Calculate SLA for critical ticket
            sla_result = await sla.handle_tool_call(
                "calculate_sla",
                {"ticket_id": "TKT-CRITICAL-001", "tier": "critical", "is_vip": True}
            )
            assert sla_result.success is True

            # 2. Check for breach predictions
            predictions = await sla.handle_tool_call(
                "get_breach_predictions",
                {"time_horizon_hours": 1, "min_probability": 0.3}
            )
            assert predictions.success is True

            # 3. Escalate if needed
            escalation = await sla.handle_tool_call(
                "escalate_ticket",
                {
                    "ticket_id": "TKT-CRITICAL-001",
                    "reason": "Approaching SLA breach for VIP customer",
                    "escalation_level": "manager"
                }
            )
            assert escalation.success is True

            # 4. Notify manager with guardrails applied
            message = "VIP customer ticket needs immediate attention."
            guardrails.check_hallucination(message)

            notif = await notification.handle_tool_call(
                "send_notification",
                {
                    "user_id": "manager",
                    "message": message,
                    "channel": "sms",
                    "priority": "urgent"
                }
            )
            assert notif.success is True

        finally:
            await sla.stop()
            await notification.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelinePerformance:
    """Performance tests for the AI pipeline."""

    def test_pipeline_response_time(self):
        """Test full pipeline responds within acceptable time."""
        router = SmartRouter()
        guardrails = GuardrailsManager()

        query = "What is your refund policy?"

        start_time = time.time()

        # Route query
        tier, metadata = router.route(query)

        # Apply guardrails
        response = "Our refund policy allows returns within 30 days."
        guardrails.check_hallucination(response)
        guardrails.check_competitor_mention(response)

        elapsed_ms = (time.time() - start_time) * 1000

        # Pipeline should respond quickly
        assert elapsed_ms < 500, f"Pipeline took {elapsed_ms}ms"

    @pytest.mark.asyncio
    async def test_mcp_servers_response_time(self):
        """Test all MCP servers respond within 2 seconds."""
        # Only test servers that don't need API keys
        servers = [
            (FAQServer(), "search_faqs", {"query": "test"}),
            (RAGServer(), "retrieve", {"query": "test"}),
            (KBServer(), "search", {"query": "test"}),
            (NotificationServer(), "send_notification",
             {"user_id": "u1", "message": "test", "channel": "email"}),
            (ComplianceServer(), "check_compliance",
             {"action": "data_export", "context": {}}),
            (SLAServer(), "calculate_sla", {"ticket_id": "TKT-001"}),
        ]

        for server, tool, params in servers:
            await server.start()
            start = time.time()
            result = await server.handle_tool_call(tool, params)
            elapsed_ms = (time.time() - start) * 1000
            assert elapsed_ms < 2000, f"{server.name} took {elapsed_ms}ms"
            assert result.success is True
            await server.stop()
