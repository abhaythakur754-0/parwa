"""
Integration tests for PARWA High - Week 11.

Tests for PARWA High variant integration with other variants:
- All 3 variants import simultaneously with zero conflicts
- PARWA High churn prediction contains risk score
- Same ticket through all 3 variants: Mini collects, PARWA recommends, High executes
- No naming conflicts between variants
- Each variant returns correct tier
"""
import pytest

# Import all 3 variants simultaneously
from variants.mini.config import MiniConfig, get_mini_config
from variants.parwa.config import ParwaConfig, get_parwa_config
from variants.parwa_high.config import ParwaHighConfig, get_parwa_high_config

from variants.mini.agents.faq_agent import MiniFAQAgent
from variants.parwa.agents.faq_agent import ParwaFAQAgent
from variants.parwa_high.agents.video_agent import ParwaHighVideoAgent
from variants.parwa_high.agents.analytics_agent import ParwaHighAnalyticsAgent
from variants.parwa_high.agents.coordination_agent import ParwaHighCoordinationAgent

from variants.mini.tasks.verify_refund import VerifyRefundTask
from variants.parwa.workflows.refund_recommendation import RefundRecommendationWorkflow
from variants.parwa_high.tasks.customer_success import CustomerSuccessTask


# =============================================================================
# Variant Coexistence Tests
# =============================================================================

class TestVariantCoexistence:
    """Tests for all 3 variants coexisting without conflicts."""

    def test_all_variants_import_simultaneously(self):
        """Test all 3 variants import simultaneously with zero conflicts."""
        assert MiniConfig is not None
        assert ParwaConfig is not None
        assert ParwaHighConfig is not None

    def test_no_naming_conflicts_between_variants(self):
        """Test no naming conflicts between variants."""
        mini_config = get_mini_config()
        parwa_config = get_parwa_config()
        parwa_high_config = get_parwa_high_config()

        # Each variant has unique id
        assert mini_config.get_variant_id() == "mini"
        assert parwa_config.get_variant_id() == "parwa"
        assert parwa_high_config.get_variant_id() == "parwa_high"

    def test_variant_limits_are_different(self):
        """Test each variant has different limits."""
        mini_config = get_mini_config()
        parwa_config = get_parwa_config()
        parwa_high_config = get_parwa_high_config()

        # Concurrent calls increase with tier
        assert mini_config.max_concurrent_calls == 2
        assert parwa_config.max_concurrent_calls == 5
        assert parwa_high_config.max_concurrent_calls == 10

        # Refund limits increase with tier
        assert mini_config.refund_limit == 50.0
        assert parwa_config.refund_limit == 500.0
        assert parwa_high_config.refund_limit == 2000.0

        # Escalation threshold decreases with tier (more confident)
        assert mini_config.escalation_threshold == 0.70
        assert parwa_config.escalation_threshold == 0.60
        assert parwa_high_config.escalation_threshold == 0.50


# =============================================================================
# PARWA High Feature Tests
# =============================================================================

class TestParwaHighFeatures:
    """Tests for PARWA High specific features."""

    def test_parwa_high_video_agent_initializes(self):
        """Test PARWA High video agent initializes correctly."""
        agent = ParwaHighVideoAgent(agent_id="test_video")

        assert agent.get_tier() == "heavy"
        assert agent.get_variant() == "parwa_high"

    def test_parwa_high_analytics_agent_initializes(self):
        """Test PARWA High analytics agent initializes correctly."""
        agent = ParwaHighAnalyticsAgent(agent_id="test_analytics")

        assert agent.get_tier() == "heavy"
        assert agent.get_variant() == "parwa_high"

    def test_parwa_high_coordination_agent_manages_5_teams(self):
        """Test PARWA High coordination agent manages 5 teams."""
        agent = ParwaHighCoordinationAgent(agent_id="test_coord")

        assert agent.get_max_teams() == 5
        assert agent.get_tier() == "heavy"

    def test_parwa_high_can_execute_refunds(self):
        """Test PARWA High can execute refunds (with approval)."""
        config = get_parwa_high_config()

        assert config.can_execute_refunds is True

    @pytest.mark.asyncio
    async def test_churn_prediction_contains_risk_score(self):
        """Test PARWA High churn prediction contains risk score."""
        task = CustomerSuccessTask()

        result = await task.execute(customer_id="cust_test")

        assert result.success is True
        assert result.churn_risk is not None
        assert hasattr(result.churn_risk, "risk_score")
        assert 0.0 <= result.churn_risk.risk_score <= 1.0


# =============================================================================
# Cross-Variant Flow Tests
# =============================================================================

class TestCrossVariantFlow:
    """Tests for ticket flow through all 3 variants."""

    @pytest.mark.asyncio
    async def test_same_ticket_through_all_variants(self):
        """Test same ticket through all 3 variants.

        Flow: Mini collects → PARWA recommends → High executes
        """
        ticket_data = {
            "ticket_id": "TKT-12345",
            "customer_id": "cust_123",
            "amount": 100.0,
        }

        # Step 1: Mini collects ticket information
        mini_agent = MiniFAQAgent(agent_id="mini_test")
        mini_result = await mini_agent.process({
            "query": f"Process refund ticket {ticket_data['ticket_id']}",
            "customer_id": ticket_data["customer_id"],
        })

        assert mini_result.success is True
        assert mini_result.variant == "mini"

        # Step 2: PARWA Junior makes refund recommendation
        parwa_workflow = RefundRecommendationWorkflow()
        parwa_result = await parwa_workflow.execute({
            "order_id": "ord_123",
            "amount": ticket_data["amount"],
            "customer_id": ticket_data["customer_id"],
            "reason": "Customer request",
        })

        assert parwa_result.success is True
        assert parwa_result.paddle_called is False  # Never calls Paddle

        # Step 3: PARWA High provides customer success analysis
        high_task = CustomerSuccessTask()
        high_result = await high_task.execute(customer_id=ticket_data["customer_id"])

        assert high_result.success is True
        assert high_result.churn_risk is not None


# =============================================================================
# Manager Time Calculator Tests
# =============================================================================

class TestManagerTimeComparison:
    """Tests comparing manager time saved across variants."""

    def test_parwa_manager_time_per_day(self):
        """Test manager time per day for PARWA variants."""
        from variants.parwa.anti_arbitrage_config import get_parwa_anti_arbitrage_config
        from variants.parwa_high.anti_arbitrage_config import get_parwa_high_anti_arbitrage_config

        parwa_aa = get_parwa_anti_arbitrage_config()
        parwa_high_aa = get_parwa_high_anti_arbitrage_config()

        # Manager time per day decreases with higher tiers (more automation)
        assert parwa_aa.manager_time_per_day == 0.5  # 0.5 hrs/day
        assert parwa_high_aa.manager_time_per_day == 0.25  # 0.25 hrs/day

    def test_parwa_monthly_manager_time(self):
        """Test monthly manager time for PARWA variants."""
        from variants.parwa.anti_arbitrage_config import get_parwa_anti_arbitrage_config
        from variants.parwa_high.anti_arbitrage_config import get_parwa_high_anti_arbitrage_config

        parwa_aa = get_parwa_anti_arbitrage_config()
        parwa_high_aa = get_parwa_high_anti_arbitrage_config()

        # Calculate monthly time (22 business days)
        parwa_monthly = parwa_aa.calculate_manager_time(days=22)
        parwa_high_monthly = parwa_high_aa.calculate_manager_time(days=22)

        assert parwa_monthly == 11.0  # 11 hrs/month
        assert parwa_high_monthly == 5.5  # 5.5 hrs/month
