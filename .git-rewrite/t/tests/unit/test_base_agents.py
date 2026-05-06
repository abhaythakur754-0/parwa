"""
Unit tests for Week 9 Day 1 Base Agents.

Tests for:
- BaseAgent (abstract base class)
- BaseFAQAgent
- BaseEmailAgent
- BaseChatAgent
- BaseSMSAgent
- BaseVoiceAgent
- BaseTicketAgent
- BaseEscalationAgent

CRITICAL: Tests verify inheritance, confidence calculation,
and escalation logic.
"""
import pytest
from uuid import uuid4
from datetime import datetime

from variants.base_agents import (
    BaseAgent,
    BaseFAQAgent,
    BaseEmailAgent,
    BaseChatAgent,
    BaseSMSAgent,
    BaseVoiceAgent,
    BaseTicketAgent,
    BaseEscalationAgent,
    AgentResponse,
    AgentState,
    AgentConfig,
)


# ============================================================================
# Concrete Test Agents (to test abstract base class)
# ============================================================================

class ConcreteTestAgent(BaseAgent):
    """Concrete implementation of BaseAgent for testing."""

    async def process(self, input_data: dict) -> AgentResponse:
        """Test implementation of process."""
        return AgentResponse(
            success=True,
            message="Test processed",
            data={"result": "ok"},
            confidence=0.85,
        )

    def get_tier(self) -> str:
        """Return test tier."""
        return "light"

    def get_variant(self) -> str:
        """Return test variant."""
        return "mini"


class ConcreteTestFAQAgent(BaseFAQAgent):
    """Concrete implementation of BaseFAQAgent for testing."""

    async def process(self, input_data: dict) -> AgentResponse:
        """Test implementation of process."""
        query = input_data.get("query", "")
        results = await self.search_faq(query)

        if results:
            confidence = self.calculate_faq_confidence(results)
            return AgentResponse(
                success=True,
                message="FAQ found",
                data={"results": results},
                confidence=confidence,
            )

        return AgentResponse(
            success=False,
            message="No FAQ found",
            confidence=0.0,
        )

    def get_tier(self) -> str:
        return "light"

    def get_variant(self) -> str:
        return "mini"


class ConcreteTestEmailAgent(BaseEmailAgent):
    """Concrete implementation of BaseEmailAgent for testing."""

    async def process(self, input_data: dict) -> AgentResponse:
        """Test implementation of process."""
        email = input_data.get("email_content", "")
        parsed = await self.parse_email(email)
        intent = await self.extract_intent(parsed)
        confidence = self.get_intent_confidence(parsed, intent)

        return AgentResponse(
            success=True,
            message="Email processed",
            data={"intent": intent, "parsed": parsed},
            confidence=confidence,
        )

    def get_tier(self) -> str:
        return "light"

    def get_variant(self) -> str:
        return "mini"


class ConcreteTestChatAgent(BaseChatAgent):
    """Concrete implementation of BaseChatAgent for testing."""

    async def process(self, input_data: dict) -> AgentResponse:
        """Test implementation of process."""
        message = input_data.get("message", "")
        context = input_data.get("context", {})
        result = await self.handle_message(message, context)

        return AgentResponse(
            success=True,
            message="Chat processed",
            data=result,
            confidence=0.8,
        )

    def get_tier(self) -> str:
        return "light"

    def get_variant(self) -> str:
        return "mini"


class ConcreteTestSMSAgent(BaseSMSAgent):
    """Concrete implementation of BaseSMSAgent for testing."""

    async def process(self, input_data: dict) -> AgentResponse:
        """Test implementation of process."""
        sms = input_data.get("sms_content", "")
        parsed = await self.parse_sms(sms)

        return AgentResponse(
            success=True,
            message="SMS processed",
            data=parsed,
            confidence=0.75,
        )

    def get_tier(self) -> str:
        return "light"

    def get_variant(self) -> str:
        return "mini"


class ConcreteTestVoiceAgent(BaseVoiceAgent):
    """Concrete implementation of BaseVoiceAgent for testing."""

    async def process(self, input_data: dict) -> AgentResponse:
        """Test implementation of process."""
        audio_url = input_data.get("audio_url", "")
        text = await self.transcribe(audio_url)

        return AgentResponse(
            success=True,
            message="Voice processed",
            data={"transcription": text},
            confidence=0.7,
        )

    def get_tier(self) -> str:
        return "light"

    def get_variant(self) -> str:
        return "mini"


class ConcreteTestTicketAgent(BaseTicketAgent):
    """Concrete implementation of BaseTicketAgent for testing."""

    async def process(self, input_data: dict) -> AgentResponse:
        """Test implementation of process."""
        subject = input_data.get("subject", "Test Ticket")
        description = input_data.get("description", "")
        ticket = await self.create_ticket(subject, description)

        return AgentResponse(
            success=True,
            message="Ticket created",
            data={"ticket": ticket},
            confidence=0.9,
        )

    def get_tier(self) -> str:
        return "light"

    def get_variant(self) -> str:
        return "mini"


class ConcreteTestEscalationAgent(BaseEscalationAgent):
    """Concrete implementation of BaseEscalationAgent for testing."""

    async def process(self, input_data: dict) -> AgentResponse:
        """Test implementation of process."""
        context = input_data.get("context", {})
        needs_escalation = await self.check_escalation_needed(context)

        if needs_escalation:
            escalation = await self.escalate(
                ticket_id=input_data.get("ticket_id", "TKT-TEST"),
                reason="low_confidence",
                context=context
            )
            return AgentResponse(
                success=True,
                message="Escalated",
                data={"escalation": escalation},
                confidence=context.get("confidence", 0.5),
                escalated=True,
            )

        return AgentResponse(
            success=True,
            message="No escalation needed",
            confidence=context.get("confidence", 0.9),
        )

    def get_tier(self) -> str:
        return "light"

    def get_variant(self) -> str:
        return "mini"


# ============================================================================
# BaseAgent Tests
# ============================================================================

class TestBaseAgent:
    """Tests for BaseAgent abstract class."""

    @pytest.fixture
    def agent(self):
        """Create test agent."""
        return ConcreteTestAgent(
            agent_id="test-agent-001",
            company_id=uuid4()
        )

    def test_agent_initialization(self, agent):
        """Test agent initializes correctly."""
        assert agent.agent_id == "test-agent-001"
        assert agent.company_id is not None
        assert agent.state == AgentState.IDLE

    def test_agent_health_check(self, agent):
        """Test health check returns valid status."""
        import asyncio
        health = asyncio.run(agent.health_check())

        assert health["healthy"] is True
        assert health["agent_id"] == "test-agent-001"
        assert health["variant"] == "mini"
        assert health["tier"] == "light"

    def test_get_confidence_with_empty_result(self, agent):
        """Test confidence with empty result."""
        confidence = agent.get_confidence({})
        assert confidence == 0.0  # Empty dict returns 0.0

    def test_get_confidence_with_result(self, agent):
        """Test confidence with result."""
        confidence = agent.get_confidence({"success": True})
        assert confidence >= 0.5  # Base confidence

    def test_get_confidence_with_success(self, agent):
        """Test confidence with successful result."""
        confidence = agent.get_confidence({"success": True, "data": {"key": "value"}})
        assert confidence >= 0.7

    def test_should_escalate_low_confidence(self, agent):
        """Test escalation triggers on low confidence."""
        assert agent.should_escalate(0.3) is True
        assert agent.should_escalate(0.5) is True

    def test_should_escalate_high_confidence(self, agent):
        """Test no escalation on high confidence."""
        assert agent.should_escalate(0.9) is False
        assert agent.should_escalate(0.8) is False

    def test_should_escalate_forced(self, agent):
        """Test forced escalation."""
        assert agent.should_escalate(0.9, {"force_escalate": True}) is True

    def test_validate_input_missing_field(self, agent):
        """Test validation catches missing fields."""
        schema = {"required": ["email"]}
        error = agent.validate_input({"name": "test"}, schema)  # Has data but missing email
        assert "email" in error

    def test_validate_input_empty_data(self, agent):
        """Test validation catches empty data."""
        schema = {"required": ["email"]}
        error = agent.validate_input({}, schema)  # Empty dict
        assert "Input data is required" in error

    def test_validate_input_success(self, agent):
        """Test validation passes for valid input."""
        schema = {"required": ["email"]}
        error = agent.validate_input({"email": "test@example.com"}, schema)
        assert error is None

    def test_log_action(self, agent):
        """Test action logging."""
        agent.log_action("test_action", {"key": "value"})
        log = agent.get_action_log()
        assert len(log) == 1
        assert log[0]["action"] == "test_action"

    @pytest.mark.asyncio
    async def test_process_returns_response(self, agent):
        """Test process returns AgentResponse."""
        response = await agent.process({"input": "test"})
        assert isinstance(response, AgentResponse)
        assert response.success is True


# ============================================================================
# BaseFAQAgent Tests
# ============================================================================

class TestBaseFAQAgent:
    """Tests for BaseFAQAgent."""

    @pytest.fixture
    def agent(self):
        """Create test FAQ agent."""
        return ConcreteTestFAQAgent(agent_id="faq-agent-001")

    @pytest.mark.asyncio
    async def test_search_faq_returns_results(self, agent):
        """Test FAQ search returns results."""
        results = await agent.search_faq("password reset")
        assert len(results) > 0
        assert "relevance_score" in results[0]

    @pytest.mark.asyncio
    async def test_search_faq_with_limit(self, agent):
        """Test FAQ search respects limit."""
        results = await agent.search_faq("order", limit=2)
        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_get_faq_answer(self, agent):
        """Test getting FAQ by ID."""
        faq = await agent.get_faq_answer("FAQ-001")
        assert faq is not None
        assert faq["faq_id"] == "FAQ-001"

    @pytest.mark.asyncio
    async def test_get_faq_answer_not_found(self, agent):
        """Test getting non-existent FAQ."""
        faq = await agent.get_faq_answer("INVALID")
        assert faq is None

    @pytest.mark.asyncio
    async def test_get_faq_categories(self, agent):
        """Test getting FAQ categories."""
        categories = await agent.get_faq_categories()
        assert len(categories) > 0
        assert "Account" in categories

    def test_calculate_faq_confidence(self, agent):
        """Test confidence calculation."""
        results = [{"relevance_score": 0.8}]
        confidence = agent.calculate_faq_confidence(results)
        assert 0.0 <= confidence <= 1.0

    def test_inherits_from_base_agent(self, agent):
        """Test FAQ agent inherits from BaseAgent."""
        assert isinstance(agent, BaseAgent)


# ============================================================================
# BaseEmailAgent Tests
# ============================================================================

class TestBaseEmailAgent:
    """Tests for BaseEmailAgent."""

    @pytest.fixture
    def agent(self):
        """Create test Email agent."""
        return ConcreteTestEmailAgent(agent_id="email-agent-001")

    @pytest.mark.asyncio
    async def test_parse_email(self, agent):
        """Test email parsing."""
        email = "Subject: Test Subject\nFrom: test@example.com\n\nThis is the body."
        parsed = await agent.parse_email(email)

        assert parsed["subject"] == "Test Subject"
        assert "test@example.com" in parsed["sender"]
        assert "body" in parsed

    @pytest.mark.asyncio
    async def test_extract_intent_refund(self, agent):
        """Test intent extraction for refund."""
        parsed = {"subject": "I want a refund", "body": "Please refund my order"}
        intent = await agent.extract_intent(parsed)
        assert intent == "refund"

    @pytest.mark.asyncio
    async def test_extract_intent_order_status(self, agent):
        """Test intent extraction for order status."""
        parsed = {"subject": "Order status", "body": "Where is my order?"}
        intent = await agent.extract_intent(parsed)
        assert intent == "order_status"

    def test_inherits_from_base_agent(self, agent):
        """Test Email agent inherits from BaseAgent."""
        assert isinstance(agent, BaseAgent)


# ============================================================================
# BaseChatAgent Tests
# ============================================================================

class TestBaseChatAgent:
    """Tests for BaseChatAgent."""

    @pytest.fixture
    def agent(self):
        """Create test Chat agent."""
        return ConcreteTestChatAgent(agent_id="chat-agent-001")

    @pytest.mark.asyncio
    async def test_handle_message(self, agent):
        """Test message handling."""
        result = await agent.handle_message("Hello", {"session_id": "test-session"})
        assert result["message"] == "Hello"
        assert result["session_id"] == "test-session"

    @pytest.mark.asyncio
    async def test_get_conversation_context(self, agent):
        """Test getting conversation context."""
        context = await agent.get_conversation_context("new-session")
        assert context["session_id"] == "new-session"
        assert "messages" in context

    def test_get_session_count(self, agent):
        """Test session counting."""
        import asyncio
        asyncio.run(agent.get_conversation_context("session-1"))
        asyncio.run(agent.get_conversation_context("session-2"))
        assert agent.get_session_count() == 2

    def test_inherits_from_base_agent(self, agent):
        """Test Chat agent inherits from BaseAgent."""
        assert isinstance(agent, BaseAgent)


# ============================================================================
# BaseSMSAgent Tests
# ============================================================================

class TestBaseSMSAgent:
    """Tests for BaseSMSAgent."""

    @pytest.fixture
    def agent(self):
        """Create test SMS agent."""
        return ConcreteTestSMSAgent(agent_id="sms-agent-001")

    @pytest.mark.asyncio
    async def test_parse_sms(self, agent):
        """Test SMS parsing."""
        sms = "Help with order ORD-12345"
        parsed = await agent.parse_sms(sms)

        assert "help" in parsed["keywords"]
        assert "ORD-12345" in parsed["order_references"]

    @pytest.mark.asyncio
    async def test_send_response(self, agent):
        """Test sending SMS response."""
        result = await agent.send_response("+1234567890", "Test message")
        assert result["status"] == "sent"
        assert "message_id" in result

    def test_inherits_from_base_agent(self, agent):
        """Test SMS agent inherits from BaseAgent."""
        assert isinstance(agent, BaseAgent)


# ============================================================================
# BaseVoiceAgent Tests
# ============================================================================

class TestBaseVoiceAgent:
    """Tests for BaseVoiceAgent."""

    @pytest.fixture
    def agent(self):
        """Create test Voice agent."""
        return ConcreteTestVoiceAgent(agent_id="voice-agent-001")

    @pytest.mark.asyncio
    async def test_transcribe(self, agent):
        """Test transcription."""
        text = await agent.transcribe("https://example.com/audio.mp3")
        assert isinstance(text, str)
        assert len(text) > 0

    @pytest.mark.asyncio
    async def test_synthesize(self, agent):
        """Test synthesis."""
        url = await agent.synthesize("Hello world")
        assert url.startswith("https://")

    def test_can_accept_call(self, agent):
        """Test call acceptance check."""
        assert agent.can_accept_call() is True

    @pytest.mark.asyncio
    async def test_start_call(self, agent):
        """Test starting a call."""
        result = await agent.start_call("call-001", "+1234567890")
        assert result["status"] == "started"
        assert agent.get_active_call_count() == 1

    @pytest.mark.asyncio
    async def test_end_call(self, agent):
        """Test ending a call."""
        await agent.start_call("call-001", "+1234567890")
        result = await agent.end_call("call-001")
        assert result["status"] == "ended"
        assert "duration_seconds" in result

    def test_inherits_from_base_agent(self, agent):
        """Test Voice agent inherits from BaseAgent."""
        assert isinstance(agent, BaseAgent)


# ============================================================================
# BaseTicketAgent Tests
# ============================================================================

class TestBaseTicketAgent:
    """Tests for BaseTicketAgent."""

    @pytest.fixture
    def agent(self):
        """Create test Ticket agent."""
        return ConcreteTestTicketAgent(agent_id="ticket-agent-001")

    @pytest.mark.asyncio
    async def test_create_ticket(self, agent):
        """Test ticket creation."""
        ticket = await agent.create_ticket("Test Subject", "Test Description")
        assert ticket["ticket_id"].startswith("TKT-")
        assert ticket["subject"] == "Test Subject"
        assert ticket["status"] == "open"

    @pytest.mark.asyncio
    async def test_update_ticket(self, agent):
        """Test ticket update."""
        ticket = await agent.create_ticket("Test", "Test")
        updated = await agent.update_ticket(ticket["ticket_id"], {"priority": "high"})

        assert updated["priority"] == "high"

    @pytest.mark.asyncio
    async def test_add_comment(self, agent):
        """Test adding comment to ticket."""
        ticket = await agent.create_ticket("Test", "Test")
        result = await agent.add_comment(ticket["ticket_id"], "Test comment", "agent")

        assert len(result["comments"]) == 1

    def test_inherits_from_base_agent(self, agent):
        """Test Ticket agent inherits from BaseAgent."""
        assert isinstance(agent, BaseAgent)


# ============================================================================
# BaseEscalationAgent Tests
# ============================================================================

class TestBaseEscalationAgent:
    """Tests for BaseEscalationAgent."""

    @pytest.fixture
    def agent(self):
        """Create test Escalation agent."""
        return ConcreteTestEscalationAgent(agent_id="escalation-agent-001")

    @pytest.mark.asyncio
    async def test_check_escalation_needed_low_confidence(self, agent):
        """Test escalation needed for low confidence."""
        result = await agent.check_escalation_needed({"confidence": 0.3})
        assert result is True

    @pytest.mark.asyncio
    async def test_check_escalation_needed_high_confidence(self, agent):
        """Test no escalation for high confidence."""
        result = await agent.check_escalation_needed({"confidence": 0.9})
        assert result is False

    @pytest.mark.asyncio
    async def test_check_escalation_customer_request(self, agent):
        """Test escalation on customer request."""
        result = await agent.check_escalation_needed({
            "confidence": 0.9,
            "customer_request": "human"
        })
        assert result is True

    @pytest.mark.asyncio
    async def test_escalate(self, agent):
        """Test creating escalation."""
        result = await agent.escalate(
            ticket_id="TKT-001",
            reason="low_confidence",
            context={"confidence": 0.3}
        )

        assert result["escalation_id"].startswith("ESC-")
        assert result["status"] == "pending"

    def test_get_escalation_channel(self, agent):
        """Test escalation channel routing."""
        channel = agent.get_escalation_channel({"reason": "refund"})
        assert channel == "supervisor"

    def test_inherits_from_base_agent(self, agent):
        """Test Escalation agent inherits from BaseAgent."""
        assert isinstance(agent, BaseAgent)


# ============================================================================
# Integration Tests
# ============================================================================

class TestBaseAgentsIntegration:
    """Integration tests for base agents."""

    @pytest.mark.asyncio
    async def test_all_agents_inherit_from_base(self):
        """Test all base agents inherit from BaseAgent."""
        agents = [
            ConcreteTestFAQAgent("test"),
            ConcreteTestEmailAgent("test"),
            ConcreteTestChatAgent("test"),
            ConcreteTestSMSAgent("test"),
            ConcreteTestVoiceAgent("test"),
            ConcreteTestTicketAgent("test"),
            ConcreteTestEscalationAgent("test"),
        ]

        for agent in agents:
            assert isinstance(agent, BaseAgent)

    @pytest.mark.asyncio
    async def test_all_agents_return_agent_response(self):
        """Test all agents return AgentResponse from process()."""
        agents = [
            (ConcreteTestFAQAgent("test"), {"query": "password"}),
            (ConcreteTestEmailAgent("test"), {"email_content": "Subject: Test"}),
            (ConcreteTestChatAgent("test"), {"message": "Hello"}),
            (ConcreteTestSMSAgent("test"), {"sms_content": "Help"}),
            (ConcreteTestVoiceAgent("test"), {"audio_url": "https://test.com/a.mp3"}),
            (ConcreteTestTicketAgent("test"), {"subject": "Test"}),
            (ConcreteTestEscalationAgent("test"), {"context": {"confidence": 0.5}}),
        ]

        for agent, input_data in agents:
            response = await agent.process(input_data)
            assert isinstance(response, AgentResponse)

    @pytest.mark.asyncio
    async def test_escalation_flow(self):
        """Test escalation flow from low confidence to human handoff."""
        agent = ConcreteTestEscalationAgent("test")

        # Low confidence should trigger escalation
        context = {"confidence": 0.3, "ticket_id": "TKT-TEST"}
        response = await agent.process({"context": context, "ticket_id": "TKT-TEST"})

        assert response.escalated is True
        assert "escalation" in response.data
