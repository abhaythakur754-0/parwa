"""
Unit tests for Mini PARWA agents.

Tests cover:
- MiniFAQAgent: FAQ handling, light tier routing, escalation
- MiniEmailAgent: Email processing, intent extraction
- MiniChatAgent: Chat session management
- MiniSMSAgent: SMS processing
- MiniVoiceAgent: Voice call handling (max 2 concurrent calls)
- MiniTicketAgent: Support ticket creation and management
- MiniEscalationAgent: Human handoff triggering
- MiniRefundAgent: Refund processing with $50 limit

Critical tests:
- All Mini agents route to 'light' tier
- All Mini agents escalate when confidence < 70%
- Mini agents inherit from correct base classes
- CRITICAL: MiniRefundAgent NEVER calls Paddle without approval
"""
import pytest
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, patch

from variants.mini.agents.faq_agent import MiniFAQAgent
from variants.mini.agents.email_agent import MiniEmailAgent
from variants.mini.agents.chat_agent import MiniChatAgent
from variants.mini.agents.sms_agent import MiniSMSAgent
from variants.mini.agents.voice_agent import MiniVoiceAgent
from variants.mini.agents.ticket_agent import MiniTicketAgent
from variants.mini.agents.escalation_agent import MiniEscalationAgent
from variants.mini.agents.refund_agent import MiniRefundAgent
from variants.mini.config import MiniConfig, get_mini_config
from variants.base_agents.base_agent import AgentResponse, BaseAgent
from variants.base_agents.base_faq_agent import BaseFAQAgent
from variants.base_agents.base_email_agent import BaseEmailAgent
from variants.base_agents.base_chat_agent import BaseChatAgent
from variants.base_agents.base_sms_agent import BaseSMSAgent
from variants.base_agents.base_voice_agent import BaseVoiceAgent
from variants.base_agents.base_ticket_agent import BaseTicketAgent
from variants.base_agents.base_escalation_agent import BaseEscalationAgent
from variants.base_agents.base_refund_agent import BaseRefundAgent, RefundRecommendation


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def company_id() -> UUID:
    """Create a test company ID."""
    return uuid4()


@pytest.fixture
def mini_config() -> MiniConfig:
    """Create a test MiniConfig."""
    return MiniConfig()


@pytest.fixture
def faq_agent(company_id: UUID, mini_config: MiniConfig) -> MiniFAQAgent:
    """Create a MiniFAQAgent for testing."""
    return MiniFAQAgent(
        agent_id="test-mini-faq",
        config={"escalation_threshold": 0.70},
        company_id=company_id,
        mini_config=mini_config,
    )


@pytest.fixture
def email_agent(company_id: UUID, mini_config: MiniConfig) -> MiniEmailAgent:
    """Create a MiniEmailAgent for testing."""
    return MiniEmailAgent(
        agent_id="test-mini-email",
        config={"escalation_threshold": 0.70},
        company_id=company_id,
        mini_config=mini_config,
    )


@pytest.fixture
def chat_agent(company_id: UUID, mini_config: MiniConfig) -> MiniChatAgent:
    """Create a MiniChatAgent for testing."""
    return MiniChatAgent(
        agent_id="test-mini-chat",
        config={"escalation_threshold": 0.70},
        company_id=company_id,
        mini_config=mini_config,
    )


@pytest.fixture
def sms_agent(company_id: UUID, mini_config: MiniConfig) -> MiniSMSAgent:
    """Create a MiniSMSAgent for testing."""
    return MiniSMSAgent(
        agent_id="test-mini-sms",
        config={"escalation_threshold": 0.70},
        company_id=company_id,
        mini_config=mini_config,
    )


@pytest.fixture
def voice_agent(company_id: UUID, mini_config: MiniConfig) -> MiniVoiceAgent:
    """Create a MiniVoiceAgent for testing."""
    return MiniVoiceAgent(
        agent_id="test-mini-voice",
        config={"escalation_threshold": 0.70},
        company_id=company_id,
        mini_config=mini_config,
    )


@pytest.fixture
def ticket_agent(company_id: UUID, mini_config: MiniConfig) -> MiniTicketAgent:
    """Create a MiniTicketAgent for testing."""
    return MiniTicketAgent(
        agent_id="test-mini-ticket",
        config={"escalation_threshold": 0.70},
        company_id=company_id,
        mini_config=mini_config,
    )


@pytest.fixture
def escalation_agent(company_id: UUID, mini_config: MiniConfig) -> MiniEscalationAgent:
    """Create a MiniEscalationAgent for testing."""
    return MiniEscalationAgent(
        agent_id="test-mini-escalation",
        config={"escalation_threshold": 0.70},
        company_id=company_id,
        mini_config=mini_config,
    )


@pytest.fixture
def refund_agent(company_id: UUID, mini_config: MiniConfig) -> MiniRefundAgent:
    """Create a MiniRefundAgent for testing."""
    return MiniRefundAgent(
        agent_id="test-mini-refund",
        config={"escalation_threshold": 0.70},
        company_id=company_id,
        mini_config=mini_config,
    )


# =============================================================================
# MiniConfig Tests
# =============================================================================

class TestMiniConfig:
    """Tests for MiniConfig."""

    def test_mini_config_defaults(self):
        """Test MiniConfig default values."""
        config = MiniConfig()

        assert config.max_concurrent_calls == 2
        assert config.escalation_threshold == 0.70
        assert config.refund_limit == 50.0
        assert "faq" in config.supported_channels
        assert "email" in config.supported_channels
        assert "chat" in config.supported_channels
        assert "sms" in config.supported_channels

    def test_mini_config_variant_name(self):
        """Test MiniConfig variant name."""
        config = MiniConfig()
        assert config.get_variant_name() == "Mini PARWA"
        assert config.get_variant_id() == "mini"

    def test_mini_config_channel_support(self):
        """Test channel support checking."""
        config = MiniConfig()

        assert config.is_channel_supported("faq") is True
        assert config.is_channel_supported("email") is True
        assert config.is_channel_supported("voice") is False

    def test_mini_config_refund_limits(self):
        """Test refund amount handling."""
        config = MiniConfig()

        assert config.can_handle_refund_amount(30.0) is True
        assert config.can_handle_refund_amount(50.0) is True
        assert config.can_handle_refund_amount(100.0) is False

        assert config.should_escalate_refund(30.0) is False
        assert config.should_escalate_refund(100.0) is True

    def test_get_mini_config_returns_default(self):
        """Test get_mini_config returns default config."""
        config = get_mini_config()
        assert isinstance(config, MiniConfig)


# =============================================================================
# MiniFAQAgent Tests
# =============================================================================

class TestMiniFAQAgent:
    """Tests for MiniFAQAgent."""

    def test_mini_faq_agent_inherits_from_base(self, faq_agent: MiniFAQAgent):
        """Test MiniFAQAgent inherits from BaseFAQAgent."""
        assert isinstance(faq_agent, BaseFAQAgent)
        assert isinstance(faq_agent, BaseAgent)

    def test_mini_faq_agent_get_tier_returns_light(self, faq_agent: MiniFAQAgent):
        """Test MiniFAQAgent.get_tier() returns 'light'."""
        assert faq_agent.get_tier() == "light"

    def test_mini_faq_agent_get_variant_returns_mini(self, faq_agent: MiniFAQAgent):
        """Test MiniFAQAgent.get_variant() returns 'mini'."""
        assert faq_agent.get_variant() == "mini"

    @pytest.mark.asyncio
    async def test_mini_faq_agent_process_simple_query(self, faq_agent: MiniFAQAgent):
        """Test MiniFAQAgent processes simple FAQ query."""
        result = await faq_agent.process({"query": "How do I reset my password?"})

        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.tier_used == "light"
        assert result.variant == "mini"

    @pytest.mark.asyncio
    async def test_mini_faq_agent_process_missing_query(self, faq_agent: MiniFAQAgent):
        """Test MiniFAQAgent handles missing query."""
        result = await faq_agent.process({})

        assert result.success is False
        # Validation error for missing required field
        assert "input" in result.message.lower() or "query" in result.message.lower() or "required" in result.message.lower()

    @pytest.mark.asyncio
    async def test_mini_faq_agent_escalates_low_confidence(self, faq_agent: MiniFAQAgent):
        """Test MiniFAQAgent escalates when confidence < 70%."""
        # Use a query that won't match any FAQs (low confidence)
        result = await faq_agent.process({"query": "xyzabc123 random unknown query"})

        # Should have low confidence and potentially escalate
        assert result.confidence < 0.70 or result.escalated is True

    @pytest.mark.asyncio
    async def test_mini_faq_agent_search_faq(self, faq_agent: MiniFAQAgent):
        """Test MiniFAQAgent search_faq functionality."""
        results = await faq_agent.search_faq("password reset")

        assert isinstance(results, list)


# =============================================================================
# MiniEmailAgent Tests
# =============================================================================

class TestMiniEmailAgent:
    """Tests for MiniEmailAgent."""

    def test_mini_email_agent_inherits_from_base(self, email_agent: MiniEmailAgent):
        """Test MiniEmailAgent inherits from BaseEmailAgent."""
        assert isinstance(email_agent, BaseEmailAgent)
        assert isinstance(email_agent, BaseAgent)

    def test_mini_email_agent_get_tier_returns_light(self, email_agent: MiniEmailAgent):
        """Test MiniEmailAgent.get_tier() returns 'light'."""
        assert email_agent.get_tier() == "light"

    def test_mini_email_agent_get_variant_returns_mini(self, email_agent: MiniEmailAgent):
        """Test MiniEmailAgent.get_variant() returns 'mini'."""
        assert email_agent.get_variant() == "mini"

    @pytest.mark.asyncio
    async def test_mini_email_agent_process_email(self, email_agent: MiniEmailAgent):
        """Test MiniEmailAgent processes email."""
        email_content = """Subject: Refund Request
From: customer@example.com

I would like to request a refund for my order ORD-12345.
Thank you."""

        result = await email_agent.process({"email_content": email_content})

        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.tier_used == "light"
        assert result.variant == "mini"

    @pytest.mark.asyncio
    async def test_mini_email_agent_missing_content(self, email_agent: MiniEmailAgent):
        """Test MiniEmailAgent handles missing email content."""
        result = await email_agent.process({})

        assert result.success is False
        # Validation error for missing required field
        assert "input" in result.message.lower() or "email" in result.message.lower() or "required" in result.message.lower()

    @pytest.mark.asyncio
    async def test_mini_email_agent_parse_email(self, email_agent: MiniEmailAgent):
        """Test MiniEmailAgent email parsing."""
        parsed = await email_agent.parse_email("Subject: Test\n\nBody text")

        assert "subject" in parsed
        assert "body" in parsed


# =============================================================================
# MiniChatAgent Tests
# =============================================================================

class TestMiniChatAgent:
    """Tests for MiniChatAgent."""

    def test_mini_chat_agent_inherits_from_base(self, chat_agent: MiniChatAgent):
        """Test MiniChatAgent inherits from BaseChatAgent."""
        assert isinstance(chat_agent, BaseChatAgent)
        assert isinstance(chat_agent, BaseAgent)

    def test_mini_chat_agent_get_tier_returns_light(self, chat_agent: MiniChatAgent):
        """Test MiniChatAgent.get_tier() returns 'light'."""
        assert chat_agent.get_tier() == "light"

    def test_mini_chat_agent_get_variant_returns_mini(self, chat_agent: MiniChatAgent):
        """Test MiniChatAgent.get_variant() returns 'mini'."""
        assert chat_agent.get_variant() == "mini"

    @pytest.mark.asyncio
    async def test_mini_chat_agent_process_message(self, chat_agent: MiniChatAgent):
        """Test MiniChatAgent processes chat message."""
        result = await chat_agent.process({
            "message": "Hello, I need help with my order",
            "session_id": "test-session-123"
        })

        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.tier_used == "light"
        assert result.variant == "mini"

    @pytest.mark.asyncio
    async def test_mini_chat_agent_missing_message(self, chat_agent: MiniChatAgent):
        """Test MiniChatAgent handles missing message."""
        result = await chat_agent.process({"session_id": "test"})

        assert result.success is False
        assert "message" in result.message.lower()

    @pytest.mark.asyncio
    async def test_mini_chat_agent_session_management(self, chat_agent: MiniChatAgent):
        """Test MiniChatAgent session management."""
        # Process first message
        await chat_agent.process({
            "message": "First message",
            "session_id": "session-1"
        })

        # Process second message
        await chat_agent.process({
            "message": "Second message",
            "session_id": "session-1"
        })

        # Check session count
        assert chat_agent.get_session_count() >= 1


# =============================================================================
# MiniSMSAgent Tests
# =============================================================================

class TestMiniSMSAgent:
    """Tests for MiniSMSAgent."""

    def test_mini_sms_agent_inherits_from_base(self, sms_agent: MiniSMSAgent):
        """Test MiniSMSAgent inherits from BaseSMSAgent."""
        assert isinstance(sms_agent, BaseSMSAgent)
        assert isinstance(sms_agent, BaseAgent)

    def test_mini_sms_agent_get_tier_returns_light(self, sms_agent: MiniSMSAgent):
        """Test MiniSMSAgent.get_tier() returns 'light'."""
        assert sms_agent.get_tier() == "light"

    def test_mini_sms_agent_get_variant_returns_mini(self, sms_agent: MiniSMSAgent):
        """Test MiniSMSAgent.get_variant() returns 'mini'."""
        assert sms_agent.get_variant() == "mini"

    @pytest.mark.asyncio
    async def test_mini_sms_agent_process_message(self, sms_agent: MiniSMSAgent):
        """Test MiniSMSAgent processes SMS message."""
        result = await sms_agent.process({
            "sms_content": "HELP I need order status for ORD-12345",
            "from_number": "+1234567890"
        })

        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.tier_used == "light"
        assert result.variant == "mini"

    @pytest.mark.asyncio
    async def test_mini_sms_agent_missing_content(self, sms_agent: MiniSMSAgent):
        """Test MiniSMSAgent handles missing SMS content."""
        result = await sms_agent.process({"from_number": "+1234567890"})

        assert result.success is False
        assert "sms_content" in result.message.lower()

    @pytest.mark.asyncio
    async def test_mini_sms_agent_parse_sms(self, sms_agent: MiniSMSAgent):
        """Test MiniSMSAgent SMS parsing."""
        parsed = await sms_agent.parse_sms("Track my order ORD-12345")

        assert "message" in parsed
        assert "keywords" in parsed
        assert "order_references" in parsed
        assert "track" in parsed.get("keywords", [])
        assert "ORD-12345" in parsed.get("order_references", [])

    @pytest.mark.asyncio
    async def test_mini_sms_agent_stats(self, sms_agent: MiniSMSAgent):
        """Test MiniSMSAgent stats tracking."""
        # Process a message
        await sms_agent.process({
            "sms_content": "Help",
            "from_number": "+1234567890"
        })

        stats = sms_agent.get_stats()
        assert "total_messages_sent" in stats
        assert "active_conversations" in stats


# =============================================================================
# Escalation Tests
# =============================================================================

class TestMiniAgentEscalation:
    """Tests for Mini agent escalation behavior."""

    @pytest.mark.asyncio
    async def test_all_mini_agents_escalate_low_confidence(
        self,
        faq_agent: MiniFAQAgent,
        email_agent: MiniEmailAgent,
        chat_agent: MiniChatAgent,
        sms_agent: MiniSMSAgent
    ):
        """Test all Mini agents escalate when confidence < 70%."""
        # The escalation threshold is 0.70 from MiniConfig
        # Agents should escalate when confidence falls below this

        # Test that should_escalate works correctly
        assert faq_agent.should_escalate(0.5) is True
        assert faq_agent.should_escalate(0.8) is False

        assert email_agent.should_escalate(0.5) is True
        assert email_agent.should_escalate(0.8) is False

        assert chat_agent.should_escalate(0.5) is True
        assert chat_agent.should_escalate(0.8) is False

        assert sms_agent.should_escalate(0.5) is True
        assert sms_agent.should_escalate(0.8) is False

    @pytest.mark.asyncio
    async def test_escalation_uses_mini_config_threshold(self, mini_config: MiniConfig):
        """Test escalation uses MiniConfig threshold (70%)."""
        # Create agent with custom config
        custom_config = MiniConfig(escalation_threshold=0.80)
        agent = MiniFAQAgent(
            agent_id="test",
            mini_config=custom_config
        )

        # Should escalate at 0.75 with 0.80 threshold
        assert agent.should_escalate(0.75) is True
        assert agent.should_escalate(0.85) is False


# =============================================================================
# Health Check Tests
# =============================================================================

class TestMiniAgentHealthCheck:
    """Tests for Mini agent health checks."""

    @pytest.mark.asyncio
    async def test_faq_agent_health_check(self, faq_agent: MiniFAQAgent):
        """Test MiniFAQAgent health check."""
        health = await faq_agent.health_check()

        assert "healthy" in health
        assert "agent_id" in health
        assert health["agent_id"] == "test-mini-faq"

    @pytest.mark.asyncio
    async def test_email_agent_health_check(self, email_agent: MiniEmailAgent):
        """Test MiniEmailAgent health check."""
        health = await email_agent.health_check()

        assert "healthy" in health
        assert health["agent_id"] == "test-mini-email"

    @pytest.mark.asyncio
    async def test_chat_agent_health_check(self, chat_agent: MiniChatAgent):
        """Test MiniChatAgent health check."""
        health = await chat_agent.health_check()

        assert "healthy" in health
        assert health["agent_id"] == "test-mini-chat"

    @pytest.mark.asyncio
    async def test_sms_agent_health_check(self, sms_agent: MiniSMSAgent):
        """Test MiniSMSAgent health check."""
        health = await sms_agent.health_check()

        assert "healthy" in health
        assert health["agent_id"] == "test-mini-sms"


# =============================================================================
# Agent Response Model Tests
# =============================================================================

class TestAgentResponse:
    """Tests for AgentResponse model."""

    def test_agent_response_defaults(self):
        """Test AgentResponse default values."""
        response = AgentResponse()

        assert response.success is True
        assert response.confidence == 0.0
        assert response.tier_used == "light"
        assert response.variant == "mini"
        assert response.escalated is False

    def test_agent_response_with_data(self):
        """Test AgentResponse with data."""
        response = AgentResponse(
            success=True,
            message="Test response",
            data={"key": "value"},
            confidence=0.85,
            tier_used="light",
            variant="mini",
        )

        assert response.success is True
        assert response.message == "Test response"
        assert response.data["key"] == "value"
        assert response.confidence == 0.85


# =============================================================================
# MiniVoiceAgent Tests (Day 4)
# =============================================================================

class TestMiniVoiceAgent:
    """Tests for MiniVoiceAgent."""

    def test_mini_voice_agent_inherits_from_base(self, voice_agent: MiniVoiceAgent):
        """Test MiniVoiceAgent inherits from BaseVoiceAgent."""
        assert isinstance(voice_agent, BaseVoiceAgent)
        assert isinstance(voice_agent, BaseAgent)

    def test_mini_voice_agent_get_tier_returns_light(self, voice_agent: MiniVoiceAgent):
        """Test MiniVoiceAgent.get_tier() returns 'light'."""
        assert voice_agent.get_tier() == "light"

    def test_mini_voice_agent_get_variant_returns_mini(self, voice_agent: MiniVoiceAgent):
        """Test MiniVoiceAgent.get_variant() returns 'mini'."""
        assert voice_agent.get_variant() == "mini"

    def test_mini_voice_agent_max_concurrent_calls(self, voice_agent: MiniVoiceAgent):
        """Test MiniVoiceAgent has max 2 concurrent calls limit."""
        assert voice_agent.max_concurrent_calls == 2
        assert voice_agent.MINI_MAX_CONCURRENT_CALLS == 2

    def test_can_accept_call_under_limit(self, voice_agent: MiniVoiceAgent):
        """Test can_accept_call returns True when under limit."""
        assert voice_agent.can_accept_call() is True

    @pytest.mark.asyncio
    async def test_can_accept_call_at_limit(self, voice_agent: MiniVoiceAgent):
        """Test can_accept_call returns False when at limit."""
        # Start 2 calls (Mini limit)
        await voice_agent.start_call("call-1", "+1234567890")
        await voice_agent.start_call("call-2", "+1234567891")

        # Should not accept more
        assert voice_agent.can_accept_call() is False

    @pytest.mark.asyncio
    async def test_start_call_rejected_at_limit(self, voice_agent: MiniVoiceAgent):
        """Test call start rejected when at capacity."""
        # Start 2 calls
        await voice_agent.start_call("call-1", "+1234567890")
        await voice_agent.start_call("call-2", "+1234567891")

        # Third call should be rejected
        result = await voice_agent.start_call("call-3", "+1234567892")
        assert result["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_voice_agent_process_audio(self, voice_agent: MiniVoiceAgent):
        """Test MiniVoiceAgent processes audio."""
        result = await voice_agent.process({
            "audio_url": "https://example.com/audio.mp3"
        })

        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.tier_used == "light"
        assert result.variant == "mini"
        assert "transcription" in result.data

    @pytest.mark.asyncio
    async def test_voice_agent_missing_audio_url(self, voice_agent: MiniVoiceAgent):
        """Test MiniVoiceAgent handles missing audio_url."""
        result = await voice_agent.process({})

        assert result.success is False
        assert "audio_url" in result.message.lower()


# =============================================================================
# MiniTicketAgent Tests (Day 4)
# =============================================================================

class TestMiniTicketAgent:
    """Tests for MiniTicketAgent."""

    def test_mini_ticket_agent_inherits_from_base(self, ticket_agent: MiniTicketAgent):
        """Test MiniTicketAgent inherits from BaseTicketAgent."""
        assert isinstance(ticket_agent, BaseTicketAgent)
        assert isinstance(ticket_agent, BaseAgent)

    def test_mini_ticket_agent_get_tier_returns_light(self, ticket_agent: MiniTicketAgent):
        """Test MiniTicketAgent.get_tier() returns 'light'."""
        assert ticket_agent.get_tier() == "light"

    def test_mini_ticket_agent_get_variant_returns_mini(self, ticket_agent: MiniTicketAgent):
        """Test MiniTicketAgent.get_variant() returns 'mini'."""
        assert ticket_agent.get_variant() == "mini"

    @pytest.mark.asyncio
    async def test_ticket_agent_create_ticket(self, ticket_agent: MiniTicketAgent):
        """Test MiniTicketAgent creates ticket."""
        result = await ticket_agent.process({
            "action": "create",
            "subject": "Test ticket",
            "description": "Test description",
            "priority": "normal"
        })

        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.tier_used == "light"
        assert result.variant == "mini"
        assert "ticket" in result.data

    @pytest.mark.asyncio
    async def test_ticket_agent_create_missing_subject(self, ticket_agent: MiniTicketAgent):
        """Test MiniTicketAgent handles missing subject."""
        result = await ticket_agent.process({
            "action": "create",
            "description": "Test description"
        })

        assert result.success is False
        assert "subject" in result.message.lower()

    @pytest.mark.asyncio
    async def test_ticket_agent_update_ticket(self, ticket_agent: MiniTicketAgent):
        """Test MiniTicketAgent updates ticket."""
        # Create ticket first
        create_result = await ticket_agent.process({
            "action": "create",
            "subject": "Test ticket",
            "description": "Test description"
        })
        ticket_id = create_result.data["ticket"]["ticket_id"]

        # Update ticket
        result = await ticket_agent.process({
            "action": "update",
            "ticket_id": ticket_id,
            "updates": {"status": "in_progress"}
        })

        assert result.success is True

    @pytest.mark.asyncio
    async def test_ticket_agent_add_comment(self, ticket_agent: MiniTicketAgent):
        """Test MiniTicketAgent adds comment."""
        # Create ticket first
        create_result = await ticket_agent.process({
            "action": "create",
            "subject": "Test ticket",
            "description": "Test description"
        })
        ticket_id = create_result.data["ticket"]["ticket_id"]

        # Add comment
        result = await ticket_agent.process({
            "action": "comment",
            "ticket_id": ticket_id,
            "comment": "This is a test comment",
            "author": "Test User"
        })

        assert result.success is True


# =============================================================================
# MiniEscalationAgent Tests (Day 4)
# =============================================================================

class TestMiniEscalationAgent:
    """Tests for MiniEscalationAgent."""

    def test_mini_escalation_agent_inherits_from_base(self, escalation_agent: MiniEscalationAgent):
        """Test MiniEscalationAgent inherits from BaseEscalationAgent."""
        assert isinstance(escalation_agent, BaseEscalationAgent)
        assert isinstance(escalation_agent, BaseAgent)

    def test_mini_escalation_agent_get_tier_returns_light(self, escalation_agent: MiniEscalationAgent):
        """Test MiniEscalationAgent.get_tier() returns 'light'."""
        assert escalation_agent.get_tier() == "light"

    def test_mini_escalation_agent_get_variant_returns_mini(self, escalation_agent: MiniEscalationAgent):
        """Test MiniEscalationAgent.get_variant() returns 'mini'."""
        assert escalation_agent.get_variant() == "mini"

    @pytest.mark.asyncio
    async def test_escalation_agent_triggers_on_low_confidence(self, escalation_agent: MiniEscalationAgent):
        """Test MiniEscalationAgent triggers on low confidence."""
        result = await escalation_agent.process({
            "context": {"confidence": 0.5},
            "ticket_id": "TKT-12345"
        })

        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.escalated is True
        assert "escalation" in result.data

    @pytest.mark.asyncio
    async def test_escalation_agent_triggers_human_handoff(self, escalation_agent: MiniEscalationAgent):
        """CRITICAL: Test MiniEscalationAgent triggers human handoff."""
        result = await escalation_agent.process({
            "context": {
                "confidence": 0.5,
                "customer_sentiment": "frustrated"
            },
            "ticket_id": "TKT-12345"
        })

        assert result.escalated is True
        assert result.data.get("human_handoff") is True
        assert "channel" in result.data

    @pytest.mark.asyncio
    async def test_escalation_agent_no_escalation_high_confidence(self, escalation_agent: MiniEscalationAgent):
        """Test MiniEscalationAgent does not escalate on high confidence."""
        result = await escalation_agent.process({
            "context": {"confidence": 0.9},
            "ticket_id": "TKT-12345"
        })

        assert result.escalated is False

    @pytest.mark.asyncio
    async def test_escalation_agent_customer_request(self, escalation_agent: MiniEscalationAgent):
        """Test escalation on explicit customer request."""
        result = await escalation_agent.process({
            "context": {
                "confidence": 0.9,
                "customer_request": "human"
            },
            "ticket_id": "TKT-12345"
        })

        assert result.escalated is True


# =============================================================================
# MiniRefundAgent Tests (Day 4) - CRITICAL
# =============================================================================

class TestMiniRefundAgent:
    """Tests for MiniRefundAgent."""

    def test_mini_refund_agent_inherits_from_base(self, refund_agent: MiniRefundAgent):
        """Test MiniRefundAgent inherits from BaseRefundAgent."""
        assert isinstance(refund_agent, BaseRefundAgent)
        assert isinstance(refund_agent, BaseAgent)

    def test_mini_refund_agent_get_tier_returns_light(self, refund_agent: MiniRefundAgent):
        """Test MiniRefundAgent.get_tier() returns 'light'."""
        assert refund_agent.get_tier() == "light"

    def test_mini_refund_agent_get_variant_returns_mini(self, refund_agent: MiniRefundAgent):
        """Test MiniRefundAgent.get_variant() returns 'mini'."""
        assert refund_agent.get_variant() == "mini"

    def test_mini_refund_limit(self, refund_agent: MiniRefundAgent):
        """Test MiniRefundAgent has $50 limit."""
        assert refund_agent.MINI_REFUND_LIMIT == 50.0

    def test_validate_refund_amount_within_limit(self, refund_agent: MiniRefundAgent):
        """Test validate_refund_amount returns True for amount within limit."""
        assert refund_agent.validate_refund_amount(30.0) is True
        assert refund_agent.validate_refund_amount(50.0) is True

    def test_validate_refund_amount_over_limit(self, refund_agent: MiniRefundAgent):
        """Test validate_refund_amount returns False for amount over limit."""
        assert refund_agent.validate_refund_amount(75.0) is False
        assert refund_agent.validate_refund_amount(100.0) is False

    @pytest.mark.asyncio
    async def test_refund_agent_process_within_limit(self, refund_agent: MiniRefundAgent):
        """Test MiniRefundAgent processes refund within $50 limit."""
        result = await refund_agent.process({
            "order_id": "ORD-12345",
            "amount": 30.0
        })

        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.tier_used == "light"
        assert result.variant == "mini"
        assert "pending_approval" in result.data

    @pytest.mark.asyncio
    async def test_refund_agent_creates_pending_approval(self, refund_agent: MiniRefundAgent):
        """Test MiniRefundAgent creates pending_approval for $30 refund."""
        result = await refund_agent.process({
            "order_id": "ORD-12345",
            "amount": 30.0
        })

        assert result.success is True
        pending = result.data.get("pending_approval", {})
        assert "approval_id" in pending
        assert pending.get("status") == "pending"

    @pytest.mark.asyncio
    async def test_refund_agent_escalates_over_limit(self, refund_agent: MiniRefundAgent):
        """Test MiniRefundAgent escalates $100 refund (over $50 limit)."""
        result = await refund_agent.process({
            "order_id": "ORD-12345",
            "amount": 100.0
        })

        assert result.success is True
        assert result.escalated is True
        assert result.data.get("exceeds_limit") is True

    @pytest.mark.asyncio
    async def test_refund_agent_missing_order_id(self, refund_agent: MiniRefundAgent):
        """Test MiniRefundAgent handles missing order_id."""
        result = await refund_agent.process({
            "amount": 30.0
        })

        assert result.success is False
        assert "order_id" in result.message.lower()


class TestMiniRefundGate:
    """CRITICAL: Tests verifying the refund gate is enforced."""

    @pytest.mark.asyncio
    async def test_paddle_not_called_directly(self, refund_agent: MiniRefundAgent):
        """CRITICAL: Paddle must NOT be called when creating pending approval."""
        result = await refund_agent.process({
            "order_id": "ORD-12345",
            "amount": 30.0
        })

        # CRITICAL: Verify payment processor was NOT called
        pending = result.data.get("pending_approval", {})
        assert pending.get("payment_processor_called") is False

    @pytest.mark.asyncio
    async def test_no_direct_paddle_calls_mini(self, refund_agent: MiniRefundAgent):
        """CRITICAL: Verify no direct Paddle calls in MiniRefundAgent process()."""
        result = await refund_agent.process({
            "order_id": "ORD-12345",
            "amount": 50.0
        })

        # Verify the refund gate is enforced
        assert result.data.get("payment_processor_called") is False

    @pytest.mark.asyncio
    async def test_create_pending_approval_no_processor_call(self, refund_agent: MiniRefundAgent):
        """CRITICAL: create_pending_approval never calls payment processor."""
        approval = await refund_agent.create_pending_approval({
            "order_id": "ORD-12345",
            "amount": 25.0
        })

        assert approval.get("payment_processor_called") is False


class TestMiniRefundRecommendation:
    """Tests for Mini refund recommendations."""

    def test_recommendation_approve_small_first_refund(self, refund_agent: MiniRefundAgent):
        """Test approve recommendation for small first refund."""
        recommendation = refund_agent.get_refund_recommendation({
            "amount": 20.0,
            "is_first_refund": True,
            "fraud_indicators": False
        })

        assert recommendation == RefundRecommendation.APPROVE.value

    def test_recommendation_review_medium_amount(self, refund_agent: MiniRefundAgent):
        """Test review recommendation for medium amount."""
        recommendation = refund_agent.get_refund_recommendation({
            "amount": 40.0,
            "is_first_refund": False,
            "fraud_indicators": False
        })

        assert recommendation == RefundRecommendation.REVIEW.value

    def test_recommendation_deny_fraud(self, refund_agent: MiniRefundAgent):
        """Test deny recommendation for fraud indicators."""
        recommendation = refund_agent.get_refund_recommendation({
            "amount": 30.0,
            "fraud_indicators": True
        })

        assert recommendation == RefundRecommendation.DENY.value


# =============================================================================
# Day 4 Integration Tests
# =============================================================================

class TestMiniDay4Integration:
    """Integration tests for Day 4 agents."""

    @pytest.mark.asyncio
    async def test_all_day4_agents_inherit_from_base(
        self,
        voice_agent: MiniVoiceAgent,
        ticket_agent: MiniTicketAgent,
        escalation_agent: MiniEscalationAgent,
        refund_agent: MiniRefundAgent
    ):
        """Test all Day 4 agents inherit from BaseAgent."""
        assert isinstance(voice_agent, BaseAgent)
        assert isinstance(ticket_agent, BaseAgent)
        assert isinstance(escalation_agent, BaseAgent)
        assert isinstance(refund_agent, BaseAgent)

    @pytest.mark.asyncio
    async def test_all_day4_agents_return_light_tier(
        self,
        voice_agent: MiniVoiceAgent,
        ticket_agent: MiniTicketAgent,
        escalation_agent: MiniEscalationAgent,
        refund_agent: MiniRefundAgent
    ):
        """Test all Day 4 agents return 'light' tier."""
        assert voice_agent.get_tier() == "light"
        assert ticket_agent.get_tier() == "light"
        assert escalation_agent.get_tier() == "light"
        assert refund_agent.get_tier() == "light"

    @pytest.mark.asyncio
    async def test_all_day4_agents_return_mini_variant(
        self,
        voice_agent: MiniVoiceAgent,
        ticket_agent: MiniTicketAgent,
        escalation_agent: MiniEscalationAgent,
        refund_agent: MiniRefundAgent
    ):
        """Test all Day 4 agents return 'mini' variant."""
        assert voice_agent.get_variant() == "mini"
        assert ticket_agent.get_variant() == "mini"
        assert escalation_agent.get_variant() == "mini"
        assert refund_agent.get_variant() == "mini"

    @pytest.mark.asyncio
    async def test_refund_to_escalation_flow(
        self,
        refund_agent: MiniRefundAgent,
        escalation_agent: MiniEscalationAgent
    ):
        """Test refund over limit triggers escalation flow."""
        # Process refund over limit
        refund_result = await refund_agent.process({
            "order_id": "ORD-12345",
            "amount": 100.0  # Over $50 limit
        })

        assert refund_result.escalated is True

        # Would trigger escalation
        escalation_result = await escalation_agent.process({
            "context": {
                "confidence": 0.5,
                "reason": "refund_over_limit"
            },
            "ticket_id": "TKT-12345"
        })

        assert escalation_result.escalated is True
        assert escalation_result.data.get("human_handoff") is True
