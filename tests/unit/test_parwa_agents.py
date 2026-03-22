"""
Unit tests for PARWA Junior agents.

Tests cover:
- ParwaFAQAgent: FAQ handling, medium tier routing, 60% escalation threshold
- ParwaEmailAgent: Email processing, intent extraction
- ParwaChatAgent: Chat session management
- ParwaSMSAgent: SMS processing
- ParwaVoiceAgent: Voice call handling (max 5 concurrent calls)
- ParwaTicketAgent: Support ticket creation and management
- ParwaEscalationAgent: Human handoff triggering
- ParwaRefundAgent: Refund processing with $500 limit, APPROVE/REVIEW/DENY

Critical tests:
- All PARWA agents route to 'medium' tier
- All PARWA agents escalate when confidence < 60%
- PARWA agents inherit from correct base classes
- CRITICAL: ParwaRefundAgent NEVER calls Paddle without approval
- CRITICAL: ParwaRefundAgent returns APPROVE/REVIEW/DENY with reasoning
"""
import pytest
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, patch

from variants.parwa.agents.faq_agent import ParwaFAQAgent
from variants.parwa.agents.email_agent import ParwaEmailAgent
from variants.parwa.agents.chat_agent import ParwaChatAgent
from variants.parwa.agents.sms_agent import ParwaSMSAgent
from variants.parwa.agents.voice_agent import ParwaVoiceAgent
from variants.parwa.agents.ticket_agent import ParwaTicketAgent
from variants.parwa.agents.escalation_agent import ParwaEscalationAgent
from variants.parwa.agents.refund_agent import ParwaRefundAgent
from variants.parwa.config import ParwaConfig, get_parwa_config
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
def parwa_config() -> ParwaConfig:
    """Create a test ParwaConfig."""
    return ParwaConfig()


@pytest.fixture
def faq_agent(company_id: UUID, parwa_config: ParwaConfig) -> ParwaFAQAgent:
    """Create a ParwaFAQAgent for testing."""
    return ParwaFAQAgent(
        agent_id="test-parwa-faq",
        config={"escalation_threshold": 0.60},
        company_id=company_id,
        parwa_config=parwa_config,
    )


@pytest.fixture
def email_agent(company_id: UUID, parwa_config: ParwaConfig) -> ParwaEmailAgent:
    """Create a ParwaEmailAgent for testing."""
    return ParwaEmailAgent(
        agent_id="test-parwa-email",
        config={"escalation_threshold": 0.60},
        company_id=company_id,
        parwa_config=parwa_config,
    )


@pytest.fixture
def chat_agent(company_id: UUID, parwa_config: ParwaConfig) -> ParwaChatAgent:
    """Create a ParwaChatAgent for testing."""
    return ParwaChatAgent(
        agent_id="test-parwa-chat",
        config={"escalation_threshold": 0.60},
        company_id=company_id,
        parwa_config=parwa_config,
    )


@pytest.fixture
def sms_agent(company_id: UUID, parwa_config: ParwaConfig) -> ParwaSMSAgent:
    """Create a ParwaSMSAgent for testing."""
    return ParwaSMSAgent(
        agent_id="test-parwa-sms",
        config={"escalation_threshold": 0.60},
        company_id=company_id,
        parwa_config=parwa_config,
    )


@pytest.fixture
def voice_agent(company_id: UUID, parwa_config: ParwaConfig) -> ParwaVoiceAgent:
    """Create a ParwaVoiceAgent for testing."""
    return ParwaVoiceAgent(
        agent_id="test-parwa-voice",
        config={"escalation_threshold": 0.60},
        company_id=company_id,
        parwa_config=parwa_config,
    )


@pytest.fixture
def ticket_agent(company_id: UUID, parwa_config: ParwaConfig) -> ParwaTicketAgent:
    """Create a ParwaTicketAgent for testing."""
    return ParwaTicketAgent(
        agent_id="test-parwa-ticket",
        config={"escalation_threshold": 0.60},
        company_id=company_id,
        parwa_config=parwa_config,
    )


@pytest.fixture
def escalation_agent(company_id: UUID, parwa_config: ParwaConfig) -> ParwaEscalationAgent:
    """Create a ParwaEscalationAgent for testing."""
    return ParwaEscalationAgent(
        agent_id="test-parwa-escalation",
        config={"escalation_threshold": 0.60},
        company_id=company_id,
        parwa_config=parwa_config,
    )


@pytest.fixture
def refund_agent(company_id: UUID, parwa_config: ParwaConfig) -> ParwaRefundAgent:
    """Create a ParwaRefundAgent for testing."""
    return ParwaRefundAgent(
        agent_id="test-parwa-refund",
        config={"escalation_threshold": 0.60},
        company_id=company_id,
        parwa_config=parwa_config,
    )


# =============================================================================
# ParwaConfig Tests
# =============================================================================

class TestParwaConfig:
    """Tests for ParwaConfig."""

    def test_parwa_config_defaults(self):
        """Test ParwaConfig default values."""
        config = ParwaConfig()

        assert config.max_concurrent_calls == 5
        assert config.escalation_threshold == 0.60
        assert config.refund_limit == 500.0
        assert "faq" in config.supported_channels
        assert "email" in config.supported_channels
        assert "chat" in config.supported_channels
        assert "sms" in config.supported_channels
        assert "voice" in config.supported_channels
        assert "video" in config.supported_channels

    def test_parwa_config_variant_name(self):
        """Test ParwaConfig variant name."""
        config = ParwaConfig()
        assert config.get_variant_name() == "PARWA Junior"
        assert config.get_variant_id() == "parwa"

    def test_parwa_config_tier(self):
        """Test ParwaConfig tier is 'medium'."""
        config = ParwaConfig()
        assert config.get_tier() == "medium"

    def test_parwa_config_channel_support(self):
        """Test channel support checking."""
        config = ParwaConfig()

        assert config.is_channel_supported("faq") is True
        assert config.is_channel_supported("email") is True
        assert config.is_channel_supported("voice") is True
        assert config.is_channel_supported("video") is True
        assert config.is_channel_supported("unknown") is False

    def test_parwa_config_refund_limits(self):
        """Test refund amount handling."""
        config = ParwaConfig()

        assert config.can_handle_refund_amount(100.0) is True
        assert config.can_handle_refund_amount(500.0) is True
        assert config.can_handle_refund_amount(600.0) is False

        assert config.should_escalate_refund(400.0) is False
        assert config.should_escalate_refund(600.0) is True

    def test_parwa_config_refund_thresholds(self):
        """Test refund recommendation thresholds."""
        config = ParwaConfig()
        thresholds = config.get_refund_recommendation_thresholds()

        assert thresholds["auto_approve"] == 100.0
        assert thresholds["review"] == 250.0
        assert thresholds["limit"] == 500.0

    def test_get_parwa_config_returns_default(self):
        """Test get_parwa_config returns default config."""
        config = get_parwa_config()
        assert isinstance(config, ParwaConfig)


# =============================================================================
# ParwaFAQAgent Tests
# =============================================================================

class TestParwaFAQAgent:
    """Tests for ParwaFAQAgent."""

    def test_parwa_faq_agent_inherits_from_base(self, faq_agent: ParwaFAQAgent):
        """Test ParwaFAQAgent inherits from BaseFAQAgent."""
        assert isinstance(faq_agent, BaseFAQAgent)
        assert isinstance(faq_agent, BaseAgent)

    def test_parwa_faq_agent_get_tier_returns_medium(self, faq_agent: ParwaFAQAgent):
        """Test ParwaFAQAgent.get_tier() returns 'medium'."""
        assert faq_agent.get_tier() == "medium"

    def test_parwa_faq_agent_get_variant_returns_parwa(self, faq_agent: ParwaFAQAgent):
        """Test ParwaFAQAgent.get_variant() returns 'parwa'."""
        assert faq_agent.get_variant() == "parwa"

    @pytest.mark.asyncio
    async def test_parwa_faq_agent_process_simple_query(self, faq_agent: ParwaFAQAgent):
        """Test ParwaFAQAgent processes simple FAQ query."""
        result = await faq_agent.process({"query": "How do I reset my password?"})

        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.tier_used == "medium"
        assert result.variant == "parwa"

    @pytest.mark.asyncio
    async def test_parwa_faq_agent_process_missing_query(self, faq_agent: ParwaFAQAgent):
        """Test ParwaFAQAgent handles missing query."""
        result = await faq_agent.process({})

        assert result.success is False
        assert "query" in result.message.lower() or "required" in result.message.lower()

    @pytest.mark.asyncio
    async def test_parwa_faq_agent_escalates_low_confidence(self, faq_agent: ParwaFAQAgent):
        """Test ParwaFAQAgent escalates when confidence < 60%."""
        # Use a query that won't match any FAQs (low confidence)
        result = await faq_agent.process({"query": "xyzabc123 random unknown query xyz"})

        # Should have low confidence and potentially escalate
        # PARWA uses 60% threshold vs Mini's 70%
        assert result.confidence < 0.60 or result.escalated is True

    @pytest.mark.asyncio
    async def test_parwa_faq_agent_search_faq(self, faq_agent: ParwaFAQAgent):
        """Test ParwaFAQAgent search_faq functionality."""
        results = await faq_agent.search_faq("password reset")

        assert isinstance(results, list)


# =============================================================================
# ParwaEmailAgent Tests
# =============================================================================

class TestParwaEmailAgent:
    """Tests for ParwaEmailAgent."""

    def test_parwa_email_agent_inherits_from_base(self, email_agent: ParwaEmailAgent):
        """Test ParwaEmailAgent inherits from BaseEmailAgent."""
        assert isinstance(email_agent, BaseEmailAgent)
        assert isinstance(email_agent, BaseAgent)

    def test_parwa_email_agent_get_tier_returns_medium(self, email_agent: ParwaEmailAgent):
        """Test ParwaEmailAgent.get_tier() returns 'medium'."""
        assert email_agent.get_tier() == "medium"

    def test_parwa_email_agent_get_variant_returns_parwa(self, email_agent: ParwaEmailAgent):
        """Test ParwaEmailAgent.get_variant() returns 'parwa'."""
        assert email_agent.get_variant() == "parwa"

    @pytest.mark.asyncio
    async def test_parwa_email_agent_process_email(self, email_agent: ParwaEmailAgent):
        """Test ParwaEmailAgent processes email."""
        email_content = """Subject: Refund Request
From: customer@example.com

I would like to request a refund for my order ORD-12345.
Thank you."""

        result = await email_agent.process({"email_content": email_content})

        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.tier_used == "medium"
        assert result.variant == "parwa"

    @pytest.mark.asyncio
    async def test_parwa_email_agent_missing_content(self, email_agent: ParwaEmailAgent):
        """Test ParwaEmailAgent handles missing email content."""
        result = await email_agent.process({})

        assert result.success is False
        assert "email" in result.message.lower() or "required" in result.message.lower()

    @pytest.mark.asyncio
    async def test_parwa_email_agent_parse_email(self, email_agent: ParwaEmailAgent):
        """Test ParwaEmailAgent email parsing."""
        parsed = await email_agent.parse_email("Subject: Test\n\nBody text")

        assert "subject" in parsed
        assert "body" in parsed


# =============================================================================
# ParwaChatAgent Tests
# =============================================================================

class TestParwaChatAgent:
    """Tests for ParwaChatAgent."""

    def test_parwa_chat_agent_inherits_from_base(self, chat_agent: ParwaChatAgent):
        """Test ParwaChatAgent inherits from BaseChatAgent."""
        assert isinstance(chat_agent, BaseChatAgent)
        assert isinstance(chat_agent, BaseAgent)

    def test_parwa_chat_agent_get_tier_returns_medium(self, chat_agent: ParwaChatAgent):
        """Test ParwaChatAgent.get_tier() returns 'medium'."""
        assert chat_agent.get_tier() == "medium"

    def test_parwa_chat_agent_get_variant_returns_parwa(self, chat_agent: ParwaChatAgent):
        """Test ParwaChatAgent.get_variant() returns 'parwa'."""
        assert chat_agent.get_variant() == "parwa"

    @pytest.mark.asyncio
    async def test_parwa_chat_agent_process_message(self, chat_agent: ParwaChatAgent):
        """Test ParwaChatAgent processes chat message."""
        result = await chat_agent.process({
            "message": "Hello, I need help with my order",
            "session_id": "test-session-123"
        })

        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.tier_used == "medium"
        assert result.variant == "parwa"

    @pytest.mark.asyncio
    async def test_parwa_chat_agent_missing_message(self, chat_agent: ParwaChatAgent):
        """Test ParwaChatAgent handles missing message."""
        result = await chat_agent.process({"session_id": "test"})

        assert result.success is False
        assert "message" in result.message.lower()

    @pytest.mark.asyncio
    async def test_parwa_chat_agent_session_management(self, chat_agent: ParwaChatAgent):
        """Test ParwaChatAgent session management."""
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
# ParwaSMSAgent Tests
# =============================================================================

class TestParwaSMSAgent:
    """Tests for ParwaSMSAgent."""

    def test_parwa_sms_agent_inherits_from_base(self, sms_agent: ParwaSMSAgent):
        """Test ParwaSMSAgent inherits from BaseSMSAgent."""
        assert isinstance(sms_agent, BaseSMSAgent)
        assert isinstance(sms_agent, BaseAgent)

    def test_parwa_sms_agent_get_tier_returns_medium(self, sms_agent: ParwaSMSAgent):
        """Test ParwaSMSAgent.get_tier() returns 'medium'."""
        assert sms_agent.get_tier() == "medium"

    def test_parwa_sms_agent_get_variant_returns_parwa(self, sms_agent: ParwaSMSAgent):
        """Test ParwaSMSAgent.get_variant() returns 'parwa'."""
        assert sms_agent.get_variant() == "parwa"

    @pytest.mark.asyncio
    async def test_parwa_sms_agent_process_message(self, sms_agent: ParwaSMSAgent):
        """Test ParwaSMSAgent processes SMS message."""
        result = await sms_agent.process({
            "message": "HELP I need order status for ORD-12345",
            "phone_number": "+1234567890"
        })

        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.tier_used == "medium"
        assert result.variant == "parwa"

    @pytest.mark.asyncio
    async def test_parwa_sms_agent_missing_content(self, sms_agent: ParwaSMSAgent):
        """Test ParwaSMSAgent handles missing SMS content."""
        result = await sms_agent.process({"phone_number": "+1234567890"})

        assert result.success is False
        assert "message" in result.message.lower()

    @pytest.mark.asyncio
    async def test_parwa_sms_agent_parse_sms(self, sms_agent: ParwaSMSAgent):
        """Test ParwaSMSAgent SMS parsing."""
        parsed = await sms_agent.parse_sms("Track my order ORD-12345")

        assert "message" in parsed
        assert "keywords" in parsed
        assert "order_references" in parsed


# =============================================================================
# Escalation Tests
# =============================================================================

class TestParwaAgentEscalation:
    """Tests for PARWA agent escalation behavior."""

    @pytest.mark.asyncio
    async def test_all_parwa_agents_escalate_low_confidence(
        self,
        faq_agent: ParwaFAQAgent,
        email_agent: ParwaEmailAgent,
        chat_agent: ParwaChatAgent,
        sms_agent: ParwaSMSAgent
    ):
        """Test all PARWA agents escalate when confidence < 60%."""
        # PARWA uses 60% threshold (lower than Mini's 70%)
        # Agents should escalate when confidence falls below this

        # Test that should_escalate works correctly
        assert faq_agent.should_escalate(0.5) is True
        assert faq_agent.should_escalate(0.7) is False

        assert email_agent.should_escalate(0.5) is True
        assert email_agent.should_escalate(0.7) is False

        assert chat_agent.should_escalate(0.5) is True
        assert chat_agent.should_escalate(0.7) is False

        assert sms_agent.should_escalate(0.5) is True
        assert sms_agent.should_escalate(0.7) is False

    @pytest.mark.asyncio
    async def test_escalation_uses_parwa_config_threshold(self, parwa_config: ParwaConfig):
        """Test escalation uses ParwaConfig threshold (60%)."""
        # Create agent with custom config
        custom_config = ParwaConfig(escalation_threshold=0.50)
        agent = ParwaFAQAgent(
            agent_id="test",
            parwa_config=custom_config
        )

        # Should escalate at 0.45 with 0.50 threshold
        assert agent.should_escalate(0.45) is True
        assert agent.should_escalate(0.55) is False


# =============================================================================
# Health Check Tests
# =============================================================================

class TestParwaAgentHealthCheck:
    """Tests for PARWA agent health checks."""

    @pytest.mark.asyncio
    async def test_faq_agent_health_check(self, faq_agent: ParwaFAQAgent):
        """Test ParwaFAQAgent health check."""
        health = await faq_agent.health_check()

        assert "healthy" in health
        assert "agent_id" in health
        assert health["agent_id"] == "test-parwa-faq"

    @pytest.mark.asyncio
    async def test_email_agent_health_check(self, email_agent: ParwaEmailAgent):
        """Test ParwaEmailAgent health check."""
        health = await email_agent.health_check()

        assert "healthy" in health
        assert health["agent_id"] == "test-parwa-email"

    @pytest.mark.asyncio
    async def test_chat_agent_health_check(self, chat_agent: ParwaChatAgent):
        """Test ParwaChatAgent health check."""
        health = await chat_agent.health_check()

        assert "healthy" in health
        assert health["agent_id"] == "test-parwa-chat"

    @pytest.mark.asyncio
    async def test_sms_agent_health_check(self, sms_agent: ParwaSMSAgent):
        """Test ParwaSMSAgent health check."""
        health = await sms_agent.health_check()

        assert "healthy" in health
        assert health["agent_id"] == "test-parwa-sms"


# =============================================================================
# ParwaVoiceAgent Tests
# =============================================================================

class TestParwaVoiceAgent:
    """Tests for ParwaVoiceAgent."""

    def test_parwa_voice_agent_inherits_from_base(self, voice_agent: ParwaVoiceAgent):
        """Test ParwaVoiceAgent inherits from BaseVoiceAgent."""
        assert isinstance(voice_agent, BaseVoiceAgent)
        assert isinstance(voice_agent, BaseAgent)

    def test_parwa_voice_agent_get_tier_returns_medium(self, voice_agent: ParwaVoiceAgent):
        """Test ParwaVoiceAgent.get_tier() returns 'medium'."""
        assert voice_agent.get_tier() == "medium"

    def test_parwa_voice_agent_get_variant_returns_parwa(self, voice_agent: ParwaVoiceAgent):
        """Test ParwaVoiceAgent.get_variant() returns 'parwa'."""
        assert voice_agent.get_variant() == "parwa"

    def test_parwa_voice_agent_max_concurrent_calls(self, voice_agent: ParwaVoiceAgent):
        """Test ParwaVoiceAgent has max 5 concurrent calls limit."""
        assert voice_agent.max_concurrent_calls == 5
        assert voice_agent.PARWA_MAX_CONCURRENT_CALLS == 5

    def test_can_accept_call_under_limit(self, voice_agent: ParwaVoiceAgent):
        """Test can_accept_call returns True when under limit."""
        assert voice_agent.can_accept_call() is True

    @pytest.mark.asyncio
    async def test_can_accept_call_at_limit(self, voice_agent: ParwaVoiceAgent):
        """Test can_accept_call returns False when at limit."""
        # Start 5 calls (PARWA limit)
        await voice_agent.start_call("call-1", "+1234567890")
        await voice_agent.start_call("call-2", "+1234567891")
        await voice_agent.start_call("call-3", "+1234567892")
        await voice_agent.start_call("call-4", "+1234567893")
        await voice_agent.start_call("call-5", "+1234567894")

        # Should not accept more
        assert voice_agent.can_accept_call() is False

    @pytest.mark.asyncio
    async def test_start_call_rejected_at_limit(self, voice_agent: ParwaVoiceAgent):
        """Test call start rejected when at capacity."""
        # Start 5 calls
        await voice_agent.start_call("call-1", "+1234567890")
        await voice_agent.start_call("call-2", "+1234567891")
        await voice_agent.start_call("call-3", "+1234567892")
        await voice_agent.start_call("call-4", "+1234567893")
        await voice_agent.start_call("call-5", "+1234567894")

        # Sixth call should be rejected
        result = await voice_agent.start_call("call-6", "+1234567895")
        assert result["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_voice_agent_process_audio(self, voice_agent: ParwaVoiceAgent):
        """Test ParwaVoiceAgent processes audio."""
        result = await voice_agent.process({
            "action": "transcribe",
            "audio_url": "https://example.com/audio.mp3"
        })

        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.tier_used == "medium"
        assert result.variant == "parwa"
        assert "transcription" in result.data

    @pytest.mark.asyncio
    async def test_voice_agent_missing_audio_url(self, voice_agent: ParwaVoiceAgent):
        """Test ParwaVoiceAgent handles missing action."""
        result = await voice_agent.process({})

        assert result.success is False
        assert "action" in result.message.lower()


# =============================================================================
# ParwaTicketAgent Tests
# =============================================================================

class TestParwaTicketAgent:
    """Tests for ParwaTicketAgent."""

    def test_parwa_ticket_agent_inherits_from_base(self, ticket_agent: ParwaTicketAgent):
        """Test ParwaTicketAgent inherits from BaseTicketAgent."""
        assert isinstance(ticket_agent, BaseTicketAgent)
        assert isinstance(ticket_agent, BaseAgent)

    def test_parwa_ticket_agent_get_tier_returns_medium(self, ticket_agent: ParwaTicketAgent):
        """Test ParwaTicketAgent.get_tier() returns 'medium'."""
        assert ticket_agent.get_tier() == "medium"

    def test_parwa_ticket_agent_get_variant_returns_parwa(self, ticket_agent: ParwaTicketAgent):
        """Test ParwaTicketAgent.get_variant() returns 'parwa'."""
        assert ticket_agent.get_variant() == "parwa"

    @pytest.mark.asyncio
    async def test_ticket_agent_create_ticket(self, ticket_agent: ParwaTicketAgent):
        """Test ParwaTicketAgent creates ticket."""
        result = await ticket_agent.process({
            "action": "create",
            "subject": "Test ticket",
            "description": "Test description",
            "priority": "normal"
        })

        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.tier_used == "medium"
        assert result.variant == "parwa"
        assert "ticket" in result.data

    @pytest.mark.asyncio
    async def test_ticket_agent_create_missing_subject(self, ticket_agent: ParwaTicketAgent):
        """Test ParwaTicketAgent handles missing subject."""
        result = await ticket_agent.process({
            "action": "create",
            "description": "Test description"
        })

        assert result.success is False
        assert "subject" in result.message.lower()

    @pytest.mark.asyncio
    async def test_ticket_agent_update_ticket(self, ticket_agent: ParwaTicketAgent):
        """Test ParwaTicketAgent updates ticket."""
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


# =============================================================================
# ParwaEscalationAgent Tests
# =============================================================================

class TestParwaEscalationAgent:
    """Tests for ParwaEscalationAgent."""

    def test_parwa_escalation_agent_inherits_from_base(self, escalation_agent: ParwaEscalationAgent):
        """Test ParwaEscalationAgent inherits from BaseEscalationAgent."""
        assert isinstance(escalation_agent, BaseEscalationAgent)
        assert isinstance(escalation_agent, BaseAgent)

    def test_parwa_escalation_agent_get_tier_returns_medium(self, escalation_agent: ParwaEscalationAgent):
        """Test ParwaEscalationAgent.get_tier() returns 'medium'."""
        assert escalation_agent.get_tier() == "medium"

    def test_parwa_escalation_agent_get_variant_returns_parwa(self, escalation_agent: ParwaEscalationAgent):
        """Test ParwaEscalationAgent.get_variant() returns 'parwa'."""
        assert escalation_agent.get_variant() == "parwa"

    def test_parwa_escalation_threshold(self, escalation_agent: ParwaEscalationAgent):
        """Test ParwaEscalationAgent uses 60% threshold."""
        assert escalation_agent.PARWA_ESCALATION_THRESHOLD == 0.60

    @pytest.mark.asyncio
    async def test_escalation_agent_triggers_on_low_confidence(self, escalation_agent: ParwaEscalationAgent):
        """Test ParwaEscalationAgent triggers on low confidence."""
        result = await escalation_agent.process({
            "action": "check",
            "context": {"confidence": 0.5},
            "ticket_id": "TKT-12345"
        })

        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.escalated is True

    @pytest.mark.asyncio
    async def test_escalation_agent_triggers_human_handoff(self, escalation_agent: ParwaEscalationAgent):
        """CRITICAL: Test ParwaEscalationAgent triggers human handoff."""
        result = await escalation_agent.process({
            "action": "escalate",
            "context": {
                "confidence": 0.5,
                "customer_sentiment": "frustrated"
            },
            "ticket_id": "TKT-12345"
        })

        assert result.escalated is True
        assert "escalation" in result.data

    @pytest.mark.asyncio
    async def test_escalation_agent_no_escalation_high_confidence(self, escalation_agent: ParwaEscalationAgent):
        """Test ParwaEscalationAgent does not escalate on high confidence."""
        result = await escalation_agent.process({
            "action": "check",
            "context": {"confidence": 0.9},
            "ticket_id": "TKT-12345"
        })

        assert result.escalated is False

    @pytest.mark.asyncio
    async def test_escalation_agent_customer_request(self, escalation_agent: ParwaEscalationAgent):
        """Test escalation on explicit customer request."""
        result = await escalation_agent.process({
            "action": "check",
            "context": {
                "confidence": 0.9,
                "customer_request": "human"
            },
            "ticket_id": "TKT-12345"
        })

        assert result.escalated is True


# =============================================================================
# ParwaRefundAgent Tests - CRITICAL
# =============================================================================

class TestParwaRefundAgent:
    """Tests for ParwaRefundAgent."""

    def test_parwa_refund_agent_inherits_from_base(self, refund_agent: ParwaRefundAgent):
        """Test ParwaRefundAgent inherits from BaseRefundAgent."""
        assert isinstance(refund_agent, BaseRefundAgent)
        assert isinstance(refund_agent, BaseAgent)

    def test_parwa_refund_agent_get_tier_returns_medium(self, refund_agent: ParwaRefundAgent):
        """Test ParwaRefundAgent.get_tier() returns 'medium'."""
        assert refund_agent.get_tier() == "medium"

    def test_parwa_refund_agent_get_variant_returns_parwa(self, refund_agent: ParwaRefundAgent):
        """Test ParwaRefundAgent.get_variant() returns 'parwa'."""
        assert refund_agent.get_variant() == "parwa"

    def test_parwa_refund_limit(self, refund_agent: ParwaRefundAgent):
        """Test ParwaRefundAgent has $500 limit."""
        assert refund_agent.PARWA_REFUND_LIMIT == 500.0

    def test_validate_refund_amount_within_limit(self, refund_agent: ParwaRefundAgent):
        """Test validate_refund_amount returns True for amount within limit."""
        assert refund_agent.validate_refund_amount(100.0) is True
        assert refund_agent.validate_refund_amount(500.0) is True

    def test_validate_refund_amount_over_limit(self, refund_agent: ParwaRefundAgent):
        """Test validate_refund_amount returns False for amount over limit."""
        assert refund_agent.validate_refund_amount(600.0) is False
        assert refund_agent.validate_refund_amount(1000.0) is False

    @pytest.mark.asyncio
    async def test_refund_agent_process_within_limit(self, refund_agent: ParwaRefundAgent):
        """Test ParwaRefundAgent processes refund within $500 limit."""
        result = await refund_agent.process({
            "order_id": "ORD-12345",
            "amount": 200.0
        })

        assert isinstance(result, AgentResponse)
        assert result.success is True
        assert result.tier_used == "medium"
        assert result.variant == "parwa"
        assert "pending_approval" in result.data

    @pytest.mark.asyncio
    async def test_refund_agent_creates_pending_approval(self, refund_agent: ParwaRefundAgent):
        """Test ParwaRefundAgent creates pending_approval for $200 refund."""
        result = await refund_agent.process({
            "order_id": "ORD-12345",
            "amount": 200.0
        })

        assert result.success is True
        pending = result.data.get("pending_approval", {})
        assert "approval_id" in pending
        assert pending.get("status") == "pending"

    @pytest.mark.asyncio
    async def test_refund_agent_escalates_over_limit(self, refund_agent: ParwaRefundAgent):
        """Test ParwaRefundAgent escalates $600 refund (over $500 limit)."""
        result = await refund_agent.process({
            "order_id": "ORD-12345",
            "amount": 600.0
        })

        assert result.success is True
        assert result.escalated is True
        assert result.data.get("exceeds_limit") is True

    @pytest.mark.asyncio
    async def test_refund_agent_missing_order_id(self, refund_agent: ParwaRefundAgent):
        """Test ParwaRefundAgent handles missing order_id."""
        result = await refund_agent.process({
            "amount": 200.0
        })

        assert result.success is False
        assert "order_id" in result.message.lower()


class TestParwaRefundGate:
    """CRITICAL: Tests verifying the refund gate is enforced."""

    @pytest.mark.asyncio
    async def test_paddle_not_called_directly(self, refund_agent: ParwaRefundAgent):
        """CRITICAL: Paddle must NOT be called when creating pending approval."""
        result = await refund_agent.process({
            "order_id": "ORD-12345",
            "amount": 200.0
        })

        # CRITICAL: Verify payment processor was NOT called
        pending = result.data.get("pending_approval", {})
        assert pending.get("payment_processor_called") is False

    @pytest.mark.asyncio
    async def test_no_direct_paddle_calls_parwa(self, refund_agent: ParwaRefundAgent):
        """CRITICAL: Verify no direct Paddle calls in ParwaRefundAgent process()."""
        result = await refund_agent.process({
            "order_id": "ORD-12345",
            "amount": 500.0
        })

        # Verify the refund gate is enforced
        assert result.data.get("payment_processor_called") is False

    @pytest.mark.asyncio
    async def test_create_pending_approval_no_processor_call(self, refund_agent: ParwaRefundAgent):
        """CRITICAL: create_pending_approval never calls payment processor."""
        approval = await refund_agent.create_pending_approval({
            "order_id": "ORD-12345",
            "amount": 250.0
        })

        assert approval.get("payment_processor_called") is False


class TestParwaRefundRecommendation:
    """Tests for PARWA refund recommendations with APPROVE/REVIEW/DENY."""

    def test_recommendation_approve_small_first_refund(self, refund_agent: ParwaRefundAgent):
        """Test approve recommendation for small first refund under $100."""
        recommendation = refund_agent.get_refund_recommendation({
            "amount": 75.0,
            "is_first_refund": True,
            "fraud_indicators": False
        })

        assert recommendation["recommendation"] == RefundRecommendation.APPROVE.value
        assert "reasoning" in recommendation
        assert len(recommendation["reasoning"]) > 0

    def test_recommendation_review_medium_amount(self, refund_agent: ParwaRefundAgent):
        """Test review recommendation for medium amount $100-$250."""
        recommendation = refund_agent.get_refund_recommendation({
            "amount": 150.0,
            "is_first_refund": True,
            "fraud_indicators": False
        })

        assert recommendation["recommendation"] == RefundRecommendation.REVIEW.value
        assert "reasoning" in recommendation

    def test_recommendation_review_high_value(self, refund_agent: ParwaRefundAgent):
        """Test review recommendation for high-value refund $250-$500."""
        recommendation = refund_agent.get_refund_recommendation({
            "amount": 400.0,
            "is_first_refund": True,
            "fraud_indicators": False
        })

        assert recommendation["recommendation"] == RefundRecommendation.REVIEW.value
        assert "high-value" in recommendation["reasoning"].lower() or "requires" in recommendation["reasoning"].lower()

    def test_recommendation_deny_fraud(self, refund_agent: ParwaRefundAgent):
        """Test deny recommendation for fraud indicators."""
        recommendation = refund_agent.get_refund_recommendation({
            "amount": 200.0,
            "fraud_indicators": True,
            "fraud_details": "Multiple refund requests from same IP"
        })

        assert recommendation["recommendation"] == RefundRecommendation.DENY.value
        assert "fraud" in recommendation["reasoning"].lower()

    def test_recommendation_includes_full_reasoning(self, refund_agent: ParwaRefundAgent):
        """CRITICAL: Test recommendation includes full reasoning."""
        recommendation = refund_agent.get_refund_recommendation({
            "amount": 75.0,
            "is_first_refund": True,
            "fraud_indicators": False,
            "customer_history": "normal"
        })

        # Must have reasoning
        assert "reasoning" in recommendation
        reasoning = recommendation["reasoning"]

        # Reasoning should be meaningful (not empty or single word)
        assert len(reasoning) > 20
        assert isinstance(reasoning, str)

    def test_recommendation_over_limit(self, refund_agent: ParwaRefundAgent):
        """Test recommendation for amount over PARWA limit."""
        recommendation = refund_agent.get_refund_recommendation({
            "amount": 600.0,
            "fraud_indicators": False
        })

        assert recommendation["recommendation"] == RefundRecommendation.REVIEW.value
        assert "exceeds" in recommendation["reasoning"].lower() or "limit" in recommendation["reasoning"].lower()

    def test_recommendation_old_order(self, refund_agent: ParwaRefundAgent):
        """Test recommendation for order over 30 days old."""
        recommendation = refund_agent.get_refund_recommendation({
            "amount": 100.0,
            "order_age_days": 45,
            "fraud_indicators": False
        })

        assert recommendation["recommendation"] == RefundRecommendation.REVIEW.value
        assert "30" in recommendation["reasoning"] or "days" in recommendation["reasoning"].lower()


# =============================================================================
# Day 5 Integration Tests
# =============================================================================

class TestParwaDay5Integration:
    """Integration tests for Day 5 agents."""

    @pytest.mark.asyncio
    async def test_all_parwa_agents_inherit_from_base(
        self,
        faq_agent: ParwaFAQAgent,
        email_agent: ParwaEmailAgent,
        chat_agent: ParwaChatAgent,
        sms_agent: ParwaSMSAgent,
        voice_agent: ParwaVoiceAgent,
        ticket_agent: ParwaTicketAgent,
        escalation_agent: ParwaEscalationAgent,
        refund_agent: ParwaRefundAgent
    ):
        """Test all PARWA agents inherit from BaseAgent."""
        assert isinstance(faq_agent, BaseAgent)
        assert isinstance(email_agent, BaseAgent)
        assert isinstance(chat_agent, BaseAgent)
        assert isinstance(sms_agent, BaseAgent)
        assert isinstance(voice_agent, BaseAgent)
        assert isinstance(ticket_agent, BaseAgent)
        assert isinstance(escalation_agent, BaseAgent)
        assert isinstance(refund_agent, BaseAgent)

    @pytest.mark.asyncio
    async def test_all_parwa_agents_return_medium_tier(
        self,
        faq_agent: ParwaFAQAgent,
        email_agent: ParwaEmailAgent,
        chat_agent: ParwaChatAgent,
        sms_agent: ParwaSMSAgent,
        voice_agent: ParwaVoiceAgent,
        ticket_agent: ParwaTicketAgent,
        escalation_agent: ParwaEscalationAgent,
        refund_agent: ParwaRefundAgent
    ):
        """Test all PARWA agents return 'medium' tier."""
        assert faq_agent.get_tier() == "medium"
        assert email_agent.get_tier() == "medium"
        assert chat_agent.get_tier() == "medium"
        assert sms_agent.get_tier() == "medium"
        assert voice_agent.get_tier() == "medium"
        assert ticket_agent.get_tier() == "medium"
        assert escalation_agent.get_tier() == "medium"
        assert refund_agent.get_tier() == "medium"

    @pytest.mark.asyncio
    async def test_all_parwa_agents_return_parwa_variant(
        self,
        faq_agent: ParwaFAQAgent,
        email_agent: ParwaEmailAgent,
        chat_agent: ParwaChatAgent,
        sms_agent: ParwaSMSAgent,
        voice_agent: ParwaVoiceAgent,
        ticket_agent: ParwaTicketAgent,
        escalation_agent: ParwaEscalationAgent,
        refund_agent: ParwaRefundAgent
    ):
        """Test all PARWA agents return 'parwa' variant."""
        assert faq_agent.get_variant() == "parwa"
        assert email_agent.get_variant() == "parwa"
        assert chat_agent.get_variant() == "parwa"
        assert sms_agent.get_variant() == "parwa"
        assert voice_agent.get_variant() == "parwa"
        assert ticket_agent.get_variant() == "parwa"
        assert escalation_agent.get_variant() == "parwa"
        assert refund_agent.get_variant() == "parwa"

    @pytest.mark.asyncio
    async def test_refund_to_escalation_flow(
        self,
        refund_agent: ParwaRefundAgent,
        escalation_agent: ParwaEscalationAgent
    ):
        """Test refund over limit triggers escalation flow."""
        # Process refund over limit
        refund_result = await refund_agent.process({
            "order_id": "ORD-12345",
            "amount": 600.0  # Over $500 limit
        })

        assert refund_result.escalated is True

        # Would trigger escalation
        escalation_result = await escalation_agent.process({
            "action": "check",
            "context": {
                "confidence": 0.5,
                "reason": "refund_over_limit"
            },
            "ticket_id": "TKT-12345"
        })

        assert escalation_result.escalated is True


# =============================================================================
# Manager Time Calculator Tests
# =============================================================================

def _get_manager_time_module():
    """Helper to import manager_time_calculator module directly."""
    import sys
    import importlib.util
    import os
    # Get the correct path relative to this test file
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    module_path = os.path.join(base_dir, "backend", "services", "manager_time_calculator.py")
    spec = importlib.util.spec_from_file_location(
        "manager_time_calculator",
        module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestManagerTimeCalculator:
    """Tests for Manager Time Calculator service."""

    def test_manager_time_calculator_import(self):
        """Test that ManagerTimeCalculator can be imported."""
        module = _get_manager_time_module()
        
        assert hasattr(module, 'ManagerTimeCalculator')
        assert hasattr(module, 'calculate_manager_time')

    def test_calculate_mini_manager_time(self):
        """Test manager time calculation for Mini variant."""
        module = _get_manager_time_module()
        result = module.calculate_manager_time("mini", units=1)

        assert result.variant == "mini"
        assert result.units == 1
        # Mini: 0.25 hrs/day per unit
        assert result.daily_hours_saved == 0.25

    def test_calculate_parwa_manager_time(self):
        """Test manager time calculation for PARWA variant.

        CRITICAL: 1x PARWA should show 0.5 hrs/day.
        """
        module = _get_manager_time_module()
        result = module.calculate_manager_time("parwa", units=1)

        assert result.variant == "parwa"
        assert result.units == 1
        # PARWA: 0.5 hrs/day per unit
        assert result.daily_hours_saved == 0.5

    def test_calculate_parwa_high_manager_time(self):
        """Test manager time calculation for PARWA High variant."""
        module = _get_manager_time_module()
        result = module.calculate_manager_time("parwa_high", units=1)

        assert result.variant == "parwa_high"
        assert result.units == 1
        # PARWA High: 1.0 hrs/day per unit
        assert result.daily_hours_saved == 1.0

    def test_manager_time_hourly_rate_calculation(self):
        """Test USD savings calculation with hourly rate."""
        module = _get_manager_time_module()
        result = module.calculate_manager_time("parwa", units=1, hourly_rate=75.0)

        # PARWA: 0.5 hrs/day * $75/hr = $37.50/day
        assert result.hourly_rate == 75.0
        assert result.daily_savings_usd == 37.50

    def test_manager_time_monthly_annual_projection(self):
        """Test monthly and annual time projections."""
        module = _get_manager_time_module()
        result = module.calculate_manager_time("parwa", units=1)

        # Daily: 0.5 hrs
        # Weekly: 0.5 * 7 = 3.5 hrs
        # Monthly: 0.5 * 30 = 15 hrs
        # Annual: 0.5 * 365 = 182.5 hrs
        assert result.weekly_hours_saved == 3.5
        assert result.monthly_hours_saved == 15.0
        assert result.annual_hours_saved == 182.5

    def test_manager_time_multiple_units(self):
        """Test manager time calculation with multiple units."""
        module = _get_manager_time_module()
        result = module.calculate_manager_time("parwa", units=3)

        assert result.units == 3
        # 3 units * 0.5 hrs/day = 1.5 hrs/day
        assert result.daily_hours_saved == 1.5

    def test_manager_time_with_channels(self):
        """Test manager time with active channels."""
        module = _get_manager_time_module()
        calculator = module.ManagerTimeCalculator()
        result = calculator.calculate(
            variant="parwa",
            units=1,
            active_channels=["faq", "email", "chat", "sms", "voice"]
        )

        assert result.variant == "parwa"
        # With 5 channels, should have channel multiplier effect
        assert result.daily_hours_saved > 0

    def test_manager_time_breakdown_includes_details(self):
        """Test that breakdown includes calculation details."""
        module = _get_manager_time_module()
        result = module.calculate_manager_time("parwa", units=1)

        assert "breakdown" in result.model_dump()
        breakdown = result.breakdown
        assert "base_hours_per_unit" in breakdown
        assert "units" in breakdown

    def test_compare_variants(self):
        """Test comparing manager time across variants."""
        module = _get_manager_time_module()
        calculator = module.ManagerTimeCalculator()
        comparison = calculator.compare_variants(units=1)

        assert "mini" in comparison
        assert "parwa" in comparison
        assert "parwa_high" in comparison

        # Verify ordering: mini < parwa < parwa_high
        assert comparison["mini"].daily_hours_saved < comparison["parwa"].daily_hours_saved
        assert comparison["parwa"].daily_hours_saved < comparison["parwa_high"].daily_hours_saved

    def test_roi_projection(self):
        """Test ROI projection calculation."""
        module = _get_manager_time_module()
        calculator = module.ManagerTimeCalculator()
        roi = calculator.get_roi_projection(
            variant="parwa",
            units=1,
            monthly_cost=200.0,
            hourly_rate=75.0
        )

        assert "roi_percentage" in roi
        assert "payback_days" in roi
        assert "total_investment_usd" in roi
        assert "total_savings_usd" in roi
        assert "net_savings_usd" in roi
