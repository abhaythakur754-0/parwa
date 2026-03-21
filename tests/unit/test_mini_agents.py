"""
Unit tests for Mini PARWA agents.

Tests cover:
- MiniFAQAgent: FAQ handling, light tier routing, escalation
- MiniEmailAgent: Email processing, intent extraction
- MiniChatAgent: Chat session management
- MiniSMSAgent: SMS processing

Critical tests:
- All Mini agents route to 'light' tier
- All Mini agents escalate when confidence < 70%
- Mini agents inherit from correct base classes
"""
import pytest
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, patch

from variants.mini.agents.faq_agent import MiniFAQAgent
from variants.mini.agents.email_agent import MiniEmailAgent
from variants.mini.agents.chat_agent import MiniChatAgent
from variants.mini.agents.sms_agent import MiniSMSAgent
from variants.mini.config import MiniConfig, get_mini_config
from variants.base_agents.base_agent import AgentResponse, BaseAgent
from variants.base_agents.base_faq_agent import BaseFAQAgent
from variants.base_agents.base_email_agent import BaseEmailAgent
from variants.base_agents.base_chat_agent import BaseChatAgent
from variants.base_agents.base_sms_agent import BaseSMSAgent


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
