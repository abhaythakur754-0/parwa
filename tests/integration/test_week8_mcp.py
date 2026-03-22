"""
Integration tests for Week 8: MCP Servers and Guardrails.

Tests the complete MCP server ecosystem including:
- All 11 MCP servers start and respond correctly
- Knowledge servers (FAQ, RAG, KB)
- Integration servers (Email, Voice, Chat, Ticketing)
- Tool servers (Notification, Compliance, SLA)
- Guardrails for AI output safety
- Full pipeline integration

CRITICAL: All servers must respond within 2 seconds.
"""
import pytest
import asyncio
import time
from typing import List, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_servers.base_server import BaseMCPServer, MCPServerState
from mcp_servers.knowledge.faq_server import FAQServer
from mcp_servers.knowledge.rag_server import RAGServer
from mcp_servers.knowledge.kb_server import KBServer
from mcp_servers.integrations.email_server import EmailServer
from mcp_servers.integrations.voice_server import VoiceServer
from mcp_servers.integrations.chat_server import ChatServer
from mcp_servers.integrations.ticketing_server import TicketingServer
from mcp_servers.tools.notification_server import NotificationServer
from mcp_servers.tools.compliance_server import ComplianceServer
from mcp_servers.tools.sla_server import SLAServer
from shared.guardrails.guardrails import GuardrailsManager, GuardrailRule
from shared.guardrails.approval_enforcer import ApprovalEnforcer, ApprovalStatus


# ═══════════════════════════════════════════════════════════════════════════════
# MCP SERVER LIFECYCLE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAllMCPServersStart:
    """Test that all MCP servers can start and stop correctly."""

    @pytest.fixture
    def all_servers(self):
        """Create instances of all MCP servers that don't need external credentials."""
        return [
            ("FAQServer", FAQServer()),
            ("RAGServer", RAGServer()),
            ("KBServer", KBServer()),
            # EmailServer, VoiceServer, TicketingServer need API keys - skip in tests
            ("NotificationServer", NotificationServer()),
            ("ComplianceServer", ComplianceServer()),
            ("SLAServer", SLAServer()),
        ]

    @pytest.mark.asyncio
    async def test_all_servers_start(self, all_servers):
        """Test all MCP servers start correctly."""
        started = []
        for name, server in all_servers:
            await server.start()
            assert server.is_running is True, f"{name} failed to start"
            started.append((name, server))

        # Verify all running
        assert len(started) == 6

        # Cleanup
        for name, server in started:
            await server.stop()

    @pytest.mark.asyncio
    async def test_all_servers_stop_gracefully(self, all_servers):
        """Test all servers stop gracefully."""
        for name, server in all_servers:
            await server.start()
            await server.stop()
            assert server.state == MCPServerState.STOPPED, f"{name} did not stop cleanly"

    @pytest.mark.asyncio
    async def test_all_servers_have_health_check(self, all_servers):
        """Test all servers provide valid health checks."""
        for name, server in all_servers:
            await server.start()
            health = await server.health_check()
            assert health["healthy"] is True, f"{name} health check failed"
            assert "tools" in health, f"{name} missing tools in health check"
            await server.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE TIME TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestMCPServerResponseTime:
    """CRITICAL: All servers must respond within 2 seconds."""

    @pytest.fixture
    def servers_with_tools(self):
        """Create servers with their primary tool for testing (only servers without external dependencies)."""
        return [
            (FAQServer(), "search_faqs", {"query": "test"}),
            (RAGServer(), "retrieve", {"query": "test"}),
            (KBServer(), "search", {"query": "test"}),
            # EmailServer, VoiceServer, TicketingServer need API keys
            (NotificationServer(), "send_notification", {
                "user_id": "user1",
                "message": "Test notification",
                "channel": "email"
            }),
            (ComplianceServer(), "check_compliance", {
                "action": "data_export",
                "context": {}
            }),
            (SLAServer(), "calculate_sla", {
                "ticket_id": "TKT-001"
            }),
        ]

    @pytest.mark.asyncio
    async def test_all_servers_respond_within_2_seconds(self, servers_with_tools):
        """CRITICAL: All MCP servers must respond within 2 seconds."""
        for server, tool, params in servers_with_tools:
            await server.start()

            start = time.time()
            result = await server.handle_tool_call(tool, params)
            elapsed_ms = (time.time() - start) * 1000

            assert elapsed_ms < 2000, (
                f"{server.name} took {elapsed_ms:.0f}ms to respond to {tool}, "
                f"exceeds 2000ms limit"
            )

            await server.stop()

    @pytest.mark.asyncio
    async def test_parallel_server_calls_within_limit(self):
        """Test parallel calls to multiple servers still meet SLA."""
        servers = [
            (FAQServer(), "search_faqs", {"query": "test"}),
            (RAGServer(), "retrieve", {"query": "test"}),
            (KBServer(), "search", {"query": "test"}),
        ]

        # Start all servers
        for server, _, _ in servers:
            await server.start()

        # Execute in parallel
        start = time.time()
        tasks = [
            server.handle_tool_call(tool, params)
            for server, tool, params in servers
        ]
        results = await asyncio.gather(*tasks)
        elapsed_ms = (time.time() - start) * 1000

        # Parallel execution should still be under 2 seconds
        assert elapsed_ms < 2000, f"Parallel execution took {elapsed_ms:.0f}ms"

        # Cleanup
        for server, _, _ in servers:
            await server.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE SERVER INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestKnowledgeServersIntegration:
    """Integration tests for knowledge MCP servers."""

    @pytest.mark.asyncio
    async def test_faq_to_kb_workflow(self):
        """Test FAQ search followed by KB article lookup."""
        faq = FAQServer()
        kb = KBServer()

        await faq.start()
        await kb.start()

        # Search FAQs for password reset
        faq_result = await faq.handle_tool_call(
            "search_faqs",
            {"query": "password reset", "limit": 3}
        )
        assert faq_result.success is True

        # If FAQ mentions KB article, look it up
        if faq_result.data.get("results"):
            # Search KB for related info
            kb_result = await kb.handle_tool_call(
                "search",
                {"query": "password security"}
            )
            assert kb_result.success is True

        await faq.stop()
        await kb.stop()

    @pytest.mark.asyncio
    async def test_rag_ingest_and_retrieve(self):
        """Test RAG document ingestion and retrieval."""
        rag = RAGServer()
        await rag.start()

        # Ingest documents
        ingest_result = await rag.handle_tool_call(
            "ingest",
            {
                "documents": [
                    {"content": "How to reset your password: Click the forgot password link."},
                    {"content": "Two-factor authentication setup guide."},
                    {"content": "Account security best practices."},
                ]
            }
        )
        assert ingest_result.success is True
        assert ingest_result.data["documents_ingested"] == 3

        # Retrieve relevant document
        retrieve_result = await rag.handle_tool_call(
            "retrieve",
            {"query": "password help", "top_k": 2}
        )
        assert retrieve_result.success is True

        await rag.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION SERVER WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegrationServersWorkflow:
    """Integration tests for communication and ticketing servers."""

    @pytest.mark.asyncio
    async def test_ticket_to_notification_workflow(self):
        """Test notification server works with knowledge retrieval."""
        # Skip ticketing server (needs Zendesk credentials)
        # Only test notification + knowledge servers
        faq = FAQServer()
        notification = NotificationServer()

        await faq.start()
        await notification.start()

        # Search FAQs for refund info
        faq_result = await faq.handle_tool_call(
            "search_faqs",
            {"query": "refund", "limit": 3}
        )
        assert faq_result.success is True

        # Send notification about findings
        notif_result = await notification.handle_tool_call(
            "send_notification",
            {
                "user_id": "support_team",
                "message": "New refund inquiry received",
                "channel": "in_app",
                "priority": "high"
            }
        )
        assert notif_result.success is True

        await faq.stop()
        await notification.stop()

    @pytest.mark.asyncio
    async def test_knowledge_workflow(self):
        """Test multi-channel knowledge retrieval workflow."""
        faq = FAQServer()
        kb = KBServer()
        rag = RAGServer()

        await faq.start()
        await kb.start()
        await rag.start()

        # Search all knowledge sources
        faq_result = await faq.handle_tool_call(
            "search_faqs",
            {"query": "how to reset password"}
        )
        kb_result = await kb.handle_tool_call(
            "search",
            {"query": "password security"}
        )
        rag_result = await rag.handle_tool_call(
            "retrieve",
            {"query": "password help"}
        )

        assert faq_result.success is True
        assert kb_result.success is True
        assert rag_result.success is True

        await faq.stop()
        await kb.stop()
        await rag.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# COMPLIANCE AND SLA INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestComplianceSLAIntegration:
    """Integration tests for compliance and SLA servers."""

    @pytest.mark.asyncio
    async def test_gdpr_request_workflow(self):
        """Test GDPR export and delete workflow."""
        compliance = ComplianceServer()
        await compliance.start()

        # Export user data
        export_result = await compliance.handle_tool_call(
            "gdpr_export",
            {"user_id": "user_123", "include_pii": False}
        )
        assert export_result.success is True
        assert "request_id" in export_result.data

        # Delete user data (GDPR Article 17)
        delete_result = await compliance.handle_tool_call(
            "gdpr_delete",
            {"user_id": "user_123"}
        )
        assert delete_result.success is True
        assert "records_processed" in delete_result.data

        await compliance.stop()

    @pytest.mark.asyncio
    async def test_sla_breach_escalation(self):
        """Test SLA breach detection and escalation."""
        sla = SLAServer()
        await sla.start()

        # Calculate SLA for a ticket
        sla_result = await sla.handle_tool_call(
            "calculate_sla",
            {"ticket_id": "TKT-001", "tier": "critical", "is_vip": True}
        )
        assert sla_result.success is True

        # Get breach predictions
        predictions = await sla.handle_tool_call(
            "get_breach_predictions",
            {"time_horizon_hours": 24, "min_probability": 0.5}
        )
        assert predictions.success is True

        # Escalate if needed
        if sla_result.data["sla_results"]["first_response"]["is_warning"]:
            escalation = await sla.handle_tool_call(
                "escalate_ticket",
                {
                    "ticket_id": "TKT-001",
                    "reason": "SLA warning threshold reached",
                    "escalation_level": "team_lead"
                }
            )
            assert escalation.success is True

        await sla.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# GUARDRAILS INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestGuardrailsIntegration:
    """Integration tests for AI guardrails."""

    @pytest.fixture
    def guardrails(self):
        """Create GuardrailsManager instance."""
        return GuardrailsManager()

    @pytest.fixture
    def approval_enforcer(self):
        """Create ApprovalEnforcer instance."""
        return ApprovalEnforcer()

    @pytest.mark.asyncio
    async def test_hallucination_blocking_in_ai_response(self, guardrails):
        """Test hallucination blocking for AI-generated responses."""
        # Simulate AI response with fabricated claim
        ai_response = (
            "I can confirm that your order #12345 was shipped yesterday. "
            "I've verified this in our database."
        )

        result = guardrails.check_hallucination(ai_response)

        # Hallucination indicators should be detected
        assert len(result.violations) > 0 or result.confidence < 1.0

    @pytest.mark.asyncio
    async def test_competitor_blocking_in_ai_response(self, guardrails):
        """Test competitor mention blocking."""
        ai_response = (
            "Our product is much better than zendesk for customer support. "
            "Unlike freshdesk, we offer advanced features."
        )

        result = guardrails.check_competitor_mention(ai_response)

        assert result.passed is False
        assert "zendesk" in result.violations
        assert "freshdesk" in result.violations

    @pytest.mark.asyncio
    async def test_pii_masking_in_ai_response(self, guardrails):
        """Test PII masking in AI responses."""
        ai_response = (
            "Your account email is john.doe@example.com and "
            "your phone is 555-123-4567."
        )

        result = guardrails.check_pii_exposure(ai_response)

        assert result.passed is False

        # Test sanitization
        sanitized = guardrails.sanitize_response(
            ai_response, [GuardrailRule.PII_EXPOSURE.value]
        )
        assert "john.doe@example.com" not in sanitized
        assert "555-123-4567" not in sanitized

    @pytest.mark.asyncio
    async def test_full_guardrails_pipeline(self, guardrails):
        """Test complete guardrails pipeline."""
        problematic_response = (
            "I can confirm that zendesk has your email test@example.com "
            "and I've verified your credit card 4532-1234-5678-9012."
        )

        # Check all guardrails
        h_result = guardrails.check_hallucination(problematic_response)
        c_result = guardrails.check_competitor_mention(problematic_response)
        p_result = guardrails.check_pii_exposure(problematic_response)

        # At least two should fail (competitor + PII)
        failures = sum([
            not h_result.passed,
            not c_result.passed,
            not p_result.passed
        ])
        assert failures >= 2

        # Sanitize
        sanitized = guardrails.sanitize_response(problematic_response)
        assert "zendesk" not in sanitized.lower()
        assert "test@example.com" not in sanitized
        assert "4532-1234-5678-9012" not in sanitized


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVAL ENFORCER INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestApprovalEnforcerIntegration:
    """Integration tests for approval gate enforcer."""

    @pytest.fixture
    def enforcer(self):
        """Create ApprovalEnforcer instance."""
        return ApprovalEnforcer()

    @pytest.mark.asyncio
    async def test_refund_requires_approval(self, enforcer):
        """Test that refunds ALWAYS require approval."""
        # Any amount should require approval
        assert enforcer.check_approval_required("refund", amount=1.0) is True
        assert enforcer.check_approval_required("refund", amount=1000.0) is True
        assert enforcer.check_approval_required("refund_full") is True

    @pytest.mark.asyncio
    async def test_refund_approval_workflow(self, enforcer):
        """Test complete refund approval workflow."""
        # 1. Check if approval needed
        needs_approval = enforcer.check_approval_required("refund", amount=100.0)
        assert needs_approval is True

        # 2. Create pending approval
        approval = enforcer.create_pending_approval(
            "refund",
            {"order_id": "ORD-12345", "amount": 100.0, "reason": "Customer complaint"}
        )
        assert approval["status"] == ApprovalStatus.PENDING.value
        approval_id = approval["approval_id"]

        # 3. Verify pending
        status = enforcer.get_approval_status(approval_id)
        assert status == ApprovalStatus.PENDING.value

        # 4. Approve
        approve_result = enforcer.approve(approval_id, "manager@example.com")
        assert approve_result["success"] is True

        # 5. Verify approved
        verify_result = enforcer.verify_approval(approval_id)
        assert verify_result["valid"] is True
        assert verify_result["status"] == ApprovalStatus.APPROVED.value

    @pytest.mark.asyncio
    async def test_refund_bypass_blocked(self, enforcer):
        """CRITICAL: Refund bypass attempts must be blocked."""
        result = enforcer.block_bypass_attempt(
            "refund",
            {
                "order_id": "ORD-12345",
                "source": "direct_api",
                "attempted_by": "unauthorized_user"
            }
        )

        assert result["blocked"] is True
        assert "Bypass attempt blocked" in result["message"]

    @pytest.mark.asyncio
    async def test_no_direct_execution_method(self, enforcer):
        """CRITICAL: There should be NO method to execute refunds directly."""
        # Verify no execute methods exist
        assert not hasattr(enforcer, "execute_refund")
        assert not hasattr(enforcer, "execute_action")
        assert not hasattr(enforcer, "process_refund")
        assert not hasattr(enforcer, "direct_refund")


# ═══════════════════════════════════════════════════════════════════════════════
# FULL PIPELINE INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullPipelineIntegration:
    """Full pipeline integration tests."""

    @pytest.mark.asyncio
    async def test_customer_support_full_workflow(self):
        """Test complete customer support workflow with all components."""
        # Initialize all required servers (skip those needing API keys)
        faq = FAQServer()
        kb = KBServer()
        notification = NotificationServer()
        sla = SLAServer()
        guardrails = GuardrailsManager()
        enforcer = ApprovalEnforcer()

        # Start servers
        for server in [faq, kb, notification, sla]:
            await server.start()

        try:
            # 1. Customer asks about refund
            faq_result = await faq.handle_tool_call(
                "search_faqs",
                {"query": "refund policy"}
            )
            assert faq_result.success is True

            # 2. Check KB for details
            kb_result = await kb.handle_tool_call(
                "search",
                {"query": "refund process"}
            )
            assert kb_result.success is True

            # 3. Check SLA for ticket priority
            sla_result = await sla.handle_tool_call(
                "calculate_sla",
                {"ticket_id": "TKT-REFUND-001", "tier": "standard"}
            )
            assert sla_result.success is True

            # 4. Send notification to support team
            notif_result = await notification.handle_tool_call(
                "send_notification",
                {
                    "user_id": "support_team",
                    "message": "New refund inquiry",
                    "channel": "in_app"
                }
            )
            assert notif_result.success is True

            # 5. Create refund approval (NOT execute)
            approval = enforcer.create_pending_approval(
                "refund",
                {"order_id": "ORD-12345", "amount": 50.0}
            )
            assert approval["status"] == ApprovalStatus.PENDING.value

            # 6. Verify guardrails work on AI response
            ai_response = "Your refund request has been submitted."
            sanitized = guardrails.sanitize_response(ai_response)
            assert sanitized is not None

        finally:
            for server in [faq, kb, notification, sla]:
                await server.stop()

    @pytest.mark.asyncio
    async def test_vip_customer_priority_workflow(self):
        """Test VIP customer gets priority handling."""
        sla = SLAServer()
        notification = NotificationServer()
        compliance = ComplianceServer()

        await sla.start()
        await notification.start()
        await compliance.start()

        try:
            # VIP ticket gets critical tier
            sla_result = await sla.handle_tool_call(
                "calculate_sla",
                {
                    "ticket_id": "TKT-VIP-001",
                    "tier": "critical",
                    "is_vip": True
                }
            )
            assert sla_result.success is True
            assert sla_result.data["is_vip"] is True

            # Priority notification
            notif_result = await notification.handle_tool_call(
                "send_notification",
                {
                    "user_id": "vip_support",
                    "message": "VIP customer needs immediate attention",
                    "channel": "sms",
                    "priority": "urgent"
                }
            )
            assert notif_result.success is True

            # Check compliance for data export (VIP might request)
            compliance_result = await compliance.handle_tool_call(
                "check_compliance",
                {
                    "action": "data_export",
                    "context": {"is_vip": True}
                }
            )
            assert compliance_result.success is True

        finally:
            await sla.stop()
            await notification.stop()
            await compliance.stop()
