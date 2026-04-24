"""
Variant Limit Service Tests

Tests for subscription variant limit enforcement:
1. Get variant limits (starter / growth / high)
2. Get company limits based on subscription tier
3. Check ticket, team member, AI agent, voice slot, and KB doc limits
4. Enforce limits — raises VariantLimitExceededError
5. Get all limit checks
6. Exception hierarchy and attributes

BC-001: company_id isolation in all tests
BC-002: Decimal precision for amounts
BC-007: Feature gating per variant tier

Locked Variant Limits:
  | Variant | Tickets | AI Agents | Team | Voice | KB Docs | Price    |
  |---------|---------|-----------|------|-------|---------|----------|
  | Starter | 2,000   | 1         | 3    | 0     | 100     | $999.00  |
  | Growth  | 5,000   | 3         | 10   | 2     | 500     | $2,499.00|
  | High    | 15,000  | 5         | 25   | 5     | 2,000   | $3,999.00|
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4

import sys
sys.path.insert(0, '/home/z/my-project/parwa')


# =============================================================================
# Shared Fixtures
# =============================================================================

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


@pytest.fixture
def mock_company():
    """Create a mock company."""
    company = MagicMock()
    company.id = str(uuid4())
    company.subscription_status = "active"
    company.subscription_tier = "parwa"
    return company


@pytest.fixture
def mock_subscription():
    """Create a mock subscription."""
    subscription = MagicMock()
    subscription.id = str(uuid4())
    subscription.company_id = str(uuid4())
    subscription.status = "active"
    subscription.tier = "parwa"
    return subscription


# =============================================================================
# Helpers & Constants
# =============================================================================

STARTER_LIMITS = {
    "monthly_tickets": 2000, "ai_agents": 1, "team_members": 3,
    "voice_slots": 0, "kb_docs": 100, "price": "999.00",
}

GROWTH_LIMITS = {
    "monthly_tickets": 5000, "ai_agents": 3, "team_members": 10,
    "voice_slots": 2, "kb_docs": 500, "price": "2499.00",
}

HIGH_LIMITS = {
    "monthly_tickets": 15000, "ai_agents": 5, "team_members": 25,
    "voice_slots": 5, "kb_docs": 2000, "price": "3999.00",
}

VARIANT_LIMITS_MAP = {
    "mini_parwa": STARTER_LIMITS,
    "parwa": GROWTH_LIMITS,
    "high": HIGH_LIMITS,
}


def _make_mock_session():
    """Create a fresh mock database session with context-manager support."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


def _setup_subscription_lookup(session, tier="mini_parwa"):
    """Configure mock session so _get_company_variant returns *tier*.

    Sets up the subscription query chain:
        db.query(Subscription).filter(...).order_by(...).first() → subscription
    """
    sub = MagicMock()
    sub.tier = tier
    session.query.return_value.filter.return_value.order_by.return_value.first.return_value = sub


def _setup_no_subscription(session):
    """Configure mock session so _get_company_variant falls back to 'mini_parwa'.

    Both the subscription and company queries return None.
    """
    session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    session.query.return_value.filter.return_value.first.return_value = None


def _patch_service_deps(session, limits=None):
    """Patch SessionLocal and the imported get_variant_limits function.

    Returns a dict suitable for use with ``with ... as ctx:``.
    """
    import contextlib

    return {
        "session_local": patch(
            'backend.app.services.variant_limit_service.SessionLocal',
            return_value=session,
        ),
        "billing_fn": patch(
            'backend.app.services.variant_limit_service.get_variant_limits',
            return_value=limits,
        ),
    }


# =============================================================================
# 1. Test Get Variant Limits
# =============================================================================

class TestGetVariantLimits:
    """Test VariantLimitService.get_variant_limits()."""

    def test_get_starter_limits(self):
        """
        Test that starter variant returns correct limit values.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()

        session = _make_mock_session()
        session.query.return_value.filter.return_value.first.return_value = None

        with patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=None), \
             patch('backend.app.services.variant_limit_service.SessionLocal', return_value=session):
            result = service.get_variant_limits("mini_parwa")

        assert result["monthly_tickets"] == 2000
        assert result["ai_agents"] == 1
        assert result["team_members"] == 3
        assert result["voice_slots"] == 0
        assert result["kb_docs"] == 100
        assert result["price"] == "999.00"

    def test_get_growth_limits(self):
        """
        Test that growth variant returns correct limit values.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()

        session = _make_mock_session()
        session.query.return_value.filter.return_value.first.return_value = None

        with patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=None), \
             patch('backend.app.services.variant_limit_service.SessionLocal', return_value=session):
            result = service.get_variant_limits("parwa")

        assert result["monthly_tickets"] == 5000
        assert result["ai_agents"] == 3
        assert result["team_members"] == 10
        assert result["voice_slots"] == 2
        assert result["kb_docs"] == 500
        assert result["price"] == "2499.00"

    def test_get_high_limits(self):
        """
        Test that high variant returns correct limit values.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()

        session = _make_mock_session()
        session.query.return_value.filter.return_value.first.return_value = None

        with patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=None), \
             patch('backend.app.services.variant_limit_service.SessionLocal', return_value=session):
            result = service.get_variant_limits("high")

        assert result["monthly_tickets"] == 15000
        assert result["ai_agents"] == 5
        assert result["team_members"] == 25
        assert result["voice_slots"] == 5
        assert result["kb_docs"] == 2000
        assert result["price"] == "3999.00"

    def test_get_invalid_variant_returns_starter_defaults(self):
        """
        Test that an invalid variant gracefully falls back to starter limits.

        BC-007: Unknown variant → safest default (starter).
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()

        session = _make_mock_session()
        session.query.return_value.filter.return_value.first.return_value = None

        with patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=None), \
             patch('backend.app.services.variant_limit_service.SessionLocal', return_value=session):
            result = service.get_variant_limits("nonexistent_plan")

        # Hardcoded fallback defaults to starter
        assert result["monthly_tickets"] == 2000
        assert result["ai_agents"] == 1
        assert result["team_members"] == 3
        assert result["voice_slots"] == 0
        assert result["kb_docs"] == 100


# =============================================================================
# 2. Test Get Company Limits
# =============================================================================

class TestGetCompanyLimits:
    """Test VariantLimitService.get_company_limits()."""

    def test_company_with_subscription(self, mock_db_session):
        """
        Test that a company with an active subscription returns that tier's limits.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="parwa")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=GROWTH_LIMITS):
            result = service.get_company_limits(company_id)

        assert result["variant"] == "parwa"
        assert result["monthly_tickets"] == 5000
        assert result["ai_agents"] == 3
        assert result["team_members"] == 10
        assert result["voice_slots"] == 2
        assert result["kb_docs"] == 500
        assert result["price"] == "2499.00"

    def test_company_without_subscription_defaults_to_starter(self, mock_db_session):
        """
        Test that a company without a subscription defaults to starter limits.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_no_subscription(mock_db_session)

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=STARTER_LIMITS):
            result = service.get_company_limits(company_id)

        assert result["variant"] == "mini_parwa"
        assert result["monthly_tickets"] == 2000
        assert result["ai_agents"] == 1
        assert result["team_members"] == 3

    def test_company_with_different_tiers(self, mock_db_session):
        """
        Test that growth and high tiers return their respective limits.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()

        # --- growth ---
        company_id_a = uuid4()
        session_a = _make_mock_session()
        _setup_subscription_lookup(session_a, tier="parwa")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=session_a), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=GROWTH_LIMITS):
            result_a = service.get_company_limits(company_id_a)

        assert result_a["variant"] == "parwa"
        assert result_a["monthly_tickets"] == 5000

        # --- high ---
        company_id_b = uuid4()
        session_b = _make_mock_session()
        _setup_subscription_lookup(session_b, tier="high")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=session_b), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=HIGH_LIMITS):
            result_b = service.get_company_limits(company_id_b)

        assert result_b["variant"] == "high"
        assert result_b["monthly_tickets"] == 15000
        assert result_b["ai_agents"] == 5


# =============================================================================
# 3. Test Check Ticket Limit
# =============================================================================

class TestCheckTicketLimit:
    """Test VariantLimitService.check_ticket_limit()."""

    def test_under_limit_allowed(self, mock_db_session):
        """
        Test that usage under the ticket limit returns allowed=True.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="mini_parwa")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=STARTER_LIMITS):
            result = service.check_ticket_limit(company_id, current_count=100)

        assert result["allowed"] is True
        assert result["current_usage"] == 100
        assert result["limit"] == 2000
        assert result["remaining"] == 1900
        assert "100/2000" in result["message"]

    def test_at_limit_allowed(self, mock_db_session):
        """
        Test that usage exactly at the ticket limit returns allowed=False.

        At-limit means 0 remaining, so further creation is blocked.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="mini_parwa")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=STARTER_LIMITS):
            result = service.check_ticket_limit(company_id, current_count=2000)

        # usage (2000) < limit (2000) is False → not allowed
        assert result["allowed"] is False
        assert result["current_usage"] == 2000
        assert result["remaining"] == 0

    def test_over_limit_blocked(self, mock_db_session):
        """
        Test that usage over the ticket limit returns allowed=False.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="parwa")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=GROWTH_LIMITS):
            result = service.check_ticket_limit(company_id, current_count=5001)

        assert result["allowed"] is False
        assert result["current_usage"] == 5001
        assert result["limit"] == 5000
        assert result["remaining"] == 0
        assert "exceeded" in result["message"].lower()

    def test_auto_count_from_usage_records(self, mock_db_session):
        """
        Test that when current_count=None, usage is queried from UsageRecord.

        GAP: Auto-sum of tickets_used for the current billing month.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="mini_parwa")

        # Mock the UsageRecord sum query: db.query(func.sum(...)).filter(...).scalar()
        mock_db_session.query.return_value.filter.return_value.scalar.return_value = 750

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=STARTER_LIMITS):
            result = service.check_ticket_limit(company_id, current_count=None)

        assert result["allowed"] is True
        assert result["current_usage"] == 750
        assert result["remaining"] == 1250
        assert result["variant"] == "mini_parwa"

        # Verify scalar was called (UsageRecord sum query executed)
        mock_db_session.query.return_value.filter.return_value.scalar.assert_called()


# =============================================================================
# 4. Test Check Team Member Limit
# =============================================================================

class TestCheckTeamMemberLimit:
    """Test VariantLimitService.check_team_member_limit()."""

    def test_under_team_limit(self, mock_db_session):
        """
        Test that team count under the limit returns allowed=True.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="parwa")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=GROWTH_LIMITS):
            result = service.check_team_member_limit(company_id, current_count=7)

        assert result["allowed"] is True
        assert result["current_usage"] == 7
        assert result["limit"] == 10
        assert result["remaining"] == 3

    def test_at_team_limit(self, mock_db_session):
        """
        Test that team count exactly at the limit returns allowed=False.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="mini_parwa")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=STARTER_LIMITS):
            result = service.check_team_member_limit(company_id, current_count=3)

        assert result["allowed"] is False
        assert result["current_usage"] == 3
        assert result["limit"] == 3
        assert result["remaining"] == 0

    def test_over_team_limit(self, mock_db_session):
        """
        Test that team count over the limit returns allowed=False.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="mini_parwa")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=STARTER_LIMITS):
            result = service.check_team_member_limit(company_id, current_count=5)

        assert result["allowed"] is False
        assert result["current_usage"] == 5
        assert result["limit"] == 3
        assert result["remaining"] == 0


# =============================================================================
# 5. Test Check AI Agent Limit
# =============================================================================

class TestCheckAIAgentLimit:
    """Test VariantLimitService.check_ai_agent_limit()."""

    def test_under_agent_limit(self, mock_db_session):
        """
        Test that agent count under the limit returns allowed=True.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="parwa")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=GROWTH_LIMITS):
            result = service.check_ai_agent_limit(company_id, current_count=2)

        assert result["allowed"] is True
        assert result["current_usage"] == 2
        assert result["limit"] == 3
        assert result["remaining"] == 1

    def test_at_agent_limit(self, mock_db_session):
        """
        Test that agent count exactly at the limit returns allowed=False.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="parwa")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=GROWTH_LIMITS):
            result = service.check_ai_agent_limit(company_id, current_count=3)

        assert result["allowed"] is False
        assert result["current_usage"] == 3
        assert result["limit"] == 3
        assert result["remaining"] == 0

    def test_over_agent_limit(self, mock_db_session):
        """
        Test that agent count over the limit returns allowed=False.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="high")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=HIGH_LIMITS):
            result = service.check_ai_agent_limit(company_id, current_count=6)

        assert result["allowed"] is False
        assert result["current_usage"] == 6
        assert result["limit"] == 5
        assert result["remaining"] == 0


# =============================================================================
# 6. Test Check Voice Slot Limit
# =============================================================================

class TestCheckVoiceSlotLimit:
    """Test VariantLimitService.check_voice_slot_limit()."""

    def test_starter_zero_voice_slots(self, mock_db_session):
        """
        Test that starter plan (0 voice slots) always blocks when count > 0.

        BC-007: Voice slots are gated; starter has no voice capability.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="mini_parwa")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=STARTER_LIMITS):
            result = service.check_voice_slot_limit(company_id, current_count=1)

        assert result["allowed"] is False
        assert result["current_usage"] == 1
        assert result["limit"] == 0
        assert result["remaining"] == 0

    def test_growth_under_voice_limit(self, mock_db_session):
        """
        Test that growth plan allows voice slots under the limit.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="parwa")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=GROWTH_LIMITS):
            result = service.check_voice_slot_limit(company_id, current_count=1)

        assert result["allowed"] is True
        assert result["current_usage"] == 1
        assert result["limit"] == 2
        assert result["remaining"] == 1

    def test_high_over_voice_limit(self, mock_db_session):
        """
        Test that high plan blocks when voice slots exceed the limit.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="high")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=HIGH_LIMITS):
            result = service.check_voice_slot_limit(company_id, current_count=6)

        assert result["allowed"] is False
        assert result["current_usage"] == 6
        assert result["limit"] == 5
        assert result["remaining"] == 0


# =============================================================================
# 7. Test Check KB Doc Limit
# =============================================================================

class TestCheckKBDocLimit:
    """Test VariantLimitService.check_kb_doc_limit()."""

    def test_under_kb_limit(self, mock_db_session):
        """
        Test that KB doc count under the limit returns allowed=True.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="mini_parwa")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=STARTER_LIMITS):
            result = service.check_kb_doc_limit(company_id, current_count=50)

        assert result["allowed"] is True
        assert result["current_usage"] == 50
        assert result["limit"] == 100
        assert result["remaining"] == 50

    def test_at_kb_limit(self, mock_db_session):
        """
        Test that KB doc count exactly at the limit returns allowed=False.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="parwa")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=GROWTH_LIMITS):
            result = service.check_kb_doc_limit(company_id, current_count=500)

        assert result["allowed"] is False
        assert result["current_usage"] == 500
        assert result["limit"] == 500
        assert result["remaining"] == 0

    def test_over_kb_limit(self, mock_db_session):
        """
        Test that KB doc count over the limit returns allowed=False.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        _setup_subscription_lookup(mock_db_session, tier="high")

        with patch('backend.app.services.variant_limit_service.SessionLocal', return_value=mock_db_session), \
             patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=HIGH_LIMITS):
            result = service.check_kb_doc_limit(company_id, current_count=2001)

        assert result["allowed"] is False
        assert result["current_usage"] == 2001
        assert result["limit"] == 2000
        assert result["remaining"] == 0


# =============================================================================
# 8. Test Enforce Limit
# =============================================================================

class TestEnforceLimit:
    """Test VariantLimitService.enforce_limit()."""

    def test_enforce_passes_when_allowed(self):
        """
        Test that enforce_limit returns the check result when within limits.

        No exception should be raised.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        allowed_result = {
            "limit_type": "tickets",
            "allowed": True,
            "current_usage": 100,
            "limit": 2000,
            "remaining": 1900,
            "variant": "mini_parwa",
            "message": "100/2000 tickets used this month. 1900 remaining.",
        }

        with patch.object(service, 'check_ticket_limit', return_value=allowed_result):
            result = service.enforce_limit(company_id, "tickets")

        assert result["allowed"] is True
        assert result["current_usage"] == 100
        assert result["remaining"] == 1900

    def test_enforce_raises_when_exceeded(self):
        """
        Test that enforce_limit raises VariantLimitExceededError when limit exceeded.
        """
        from backend.app.services.variant_limit_service import (
            VariantLimitService,
            VariantLimitExceededError,
        )

        service = VariantLimitService()
        company_id = uuid4()

        blocked_result = {
            "limit_type": "tickets",
            "allowed": False,
            "current_usage": 2000,
            "limit": 2000,
            "remaining": 0,
            "variant": "mini_parwa",
            "message": "Ticket limit exceeded: 2000/2000. Upgrade your plan for more capacity.",
        }

        with patch.object(service, 'check_ticket_limit', return_value=blocked_result):
            with pytest.raises(VariantLimitExceededError) as exc_info:
                service.enforce_limit(company_id, "tickets")

        assert exc_info.value.limit_type == "tickets"
        assert exc_info.value.current_usage == 2000
        assert exc_info.value.limit == 2000

    def test_enforce_error_has_details(self):
        """
        Test that the raised VariantLimitExceededError carries all detail fields.
        """
        from backend.app.services.variant_limit_service import (
            VariantLimitService,
            VariantLimitExceededError,
        )

        service = VariantLimitService()
        company_id = uuid4()

        blocked_result = {
            "limit_type": "ai_agents",
            "allowed": False,
            "current_usage": 3,
            "limit": 3,
            "remaining": 0,
            "variant": "parwa",
            "message": "Ai Agents limit exceeded: 3/3. Upgrade your plan to add more AI agents.",
        }

        with patch.object(service, '_check_count_limit', return_value=blocked_result):
            with pytest.raises(VariantLimitExceededError) as exc_info:
                service.enforce_limit(company_id, "ai_agents", current_count=3)

        error = exc_info.value
        assert error.limit_type == "ai_agents"
        assert error.current_usage == 3
        assert error.limit == 3
        assert error.message is not None
        assert "3/3" in error.message
        assert "upgrade" in error.message.lower()

    @pytest.mark.parametrize("limit_type,current_count", [
        ("tickets", None),
        ("team_members", 5),
        ("ai_agents", 2),
        ("voice_slots", 1),
        ("kb_docs", 50),
    ])
    def test_enforce_all_limit_types(self, limit_type, current_count):
        """
        Test that enforce_limit works for all five limit types.

        Uses parametrize to cover every VALID_LIMIT_TYPE.
        """
        from backend.app.services.variant_limit_service import (
            VariantLimitService,
            VariantLimitExceededError,
        )

        service = VariantLimitService()
        company_id = uuid4()

        allowed_result = {
            "limit_type": limit_type,
            "allowed": True,
            "current_usage": 0,
            "limit": 999,
            "remaining": 999,
            "variant": "parwa",
            "message": "0/999 in use. 999 remaining.",
        }
        blocked_result = {
            "limit_type": limit_type,
            "allowed": False,
            "current_usage": 999,
            "limit": 999,
            "remaining": 0,
            "variant": "parwa",
            "message": f"{limit_type} limit exceeded: 999/999.",
        }

        if limit_type == "tickets":
            check_method = 'check_ticket_limit'
        else:
            check_method = '_check_count_limit'

        # --- passes when allowed ---
        with patch.object(service, check_method, return_value=allowed_result):
            result = service.enforce_limit(
                company_id, limit_type, current_count=current_count,
            )
        assert result["allowed"] is True

        # --- raises when exceeded ---
        with patch.object(service, check_method, return_value=blocked_result):
            with pytest.raises(VariantLimitExceededError) as exc_info:
                service.enforce_limit(
                    company_id, limit_type, current_count=current_count,
                )
        assert exc_info.value.limit_type == limit_type


# =============================================================================
# 9. Test Get All Limit Checks
# =============================================================================

class TestGetAllLimitChecks:
    """Test VariantLimitService.get_all_limit_checks()."""

    def test_returns_all_five_checks(self):
        """
        Test that get_all_limit_checks returns a dict with all five limit types.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        ticket_result = {
            "limit_type": "tickets",
            "allowed": True,
            "current_usage": 100,
            "limit": 2000,
            "remaining": 1900,
            "variant": "mini_parwa",
            "message": "100/2000 tickets used this month. 1900 remaining.",
        }

        with patch.object(service, '_get_company_variant', return_value="mini_parwa"), \
             patch.object(service, 'get_variant_limits', return_value=STARTER_LIMITS), \
             patch.object(service, 'check_ticket_limit', return_value=ticket_result), \
             patch.object(service, '_query_resource_count', return_value=0):
            result = service.get_all_limit_checks(company_id)

        assert result["company_id"] == str(company_id)
        assert result["variant"] == "mini_parwa"
        assert "checks" in result
        expected_keys = {"tickets", "team_members", "ai_agents", "voice_slots", "kb_docs"}
        assert set(result["checks"].keys()) == expected_keys

        # All counts are 0, so all should be allowed except voice (0 < 0 = False)
        assert result["checks"]["tickets"]["allowed"] is True
        assert result["checks"]["team_members"]["allowed"] is True
        assert result["checks"]["ai_agents"]["allowed"] is True
        # starter voice_slots = 0, 0 < 0 is False
        assert result["checks"]["voice_slots"]["allowed"] is False
        assert result["checks"]["kb_docs"]["allowed"] is True

    def test_mixed_results(self):
        """
        Test that get_all_limit_checks correctly reports mixed allowed/blocked states.

        Uses growth tier with counts that produce both allowed and blocked.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()
        company_id = uuid4()

        ticket_result = {
            "limit_type": "tickets",
            "allowed": True,
            "current_usage": 4000,
            "limit": 5000,
            "remaining": 1000,
            "variant": "parwa",
            "message": "4000/5000 tickets used this month. 1000 remaining.",
        }

        # team=8 (limit 10 → allowed), agents=3 (limit 3 → blocked),
        # voice=2 (limit 2 → blocked), kb=499 (limit 500 → allowed)
        resource_counts = [8, 3, 2, 499]

        with patch.object(service, '_get_company_variant', return_value="parwa"), \
             patch.object(service, 'get_variant_limits', return_value=GROWTH_LIMITS), \
             patch.object(service, 'check_ticket_limit', return_value=ticket_result), \
             patch.object(service, '_query_resource_count', side_effect=resource_counts):
            result = service.get_all_limit_checks(company_id)

        checks = result["checks"]
        assert result["variant"] == "parwa"

        # tickets: 4000/5000 → allowed
        assert checks["tickets"]["allowed"] is True
        assert checks["tickets"]["current_usage"] == 4000

        # team_members: 8/10 → allowed
        assert checks["team_members"]["allowed"] is True
        assert checks["team_members"]["current_usage"] == 8

        # ai_agents: 3/3 → blocked (at limit)
        assert checks["ai_agents"]["allowed"] is False
        assert checks["ai_agents"]["current_usage"] == 3
        assert checks["ai_agents"]["limit"] == 3

        # voice_slots: 2/2 → blocked (at limit)
        assert checks["voice_slots"]["allowed"] is False
        assert checks["voice_slots"]["current_usage"] == 2

        # kb_docs: 499/500 → allowed
        assert checks["kb_docs"]["allowed"] is True
        assert checks["kb_docs"]["current_usage"] == 499
        assert checks["kb_docs"]["remaining"] == 1


# =============================================================================
# 10. Test Variant Limit Exceptions
# =============================================================================

class TestVariantLimitExceptions:
    """Test exception hierarchy and attribute behaviour."""

    def test_limit_exceeded_error_attributes(self):
        """
        Test that VariantLimitExceededError exposes limit_type, current_usage, limit, and message.

        BC-001: Error details include the exact resource and usage numbers.
        """
        from backend.app.services.variant_limit_service import VariantLimitExceededError

        error = VariantLimitExceededError(
            limit_type="tickets",
            current_usage=2500,
            limit=2000,
        )

        assert error.limit_type == "tickets"
        assert error.current_usage == 2500
        assert error.limit == 2000
        assert error.message is not None
        assert "2500" in error.message
        assert "2000" in error.message
        assert "upgrade" in error.message.lower()

    def test_limit_exceeded_error_custom_message(self):
        """
        Test that a custom message overrides the auto-generated one.
        """
        from backend.app.services.variant_limit_service import VariantLimitExceededError

        custom_msg = "You have exceeded your AI agent quota. Contact sales for an upgrade."
        error = VariantLimitExceededError(
            limit_type="ai_agents",
            current_usage=4,
            limit=3,
            message=custom_msg,
        )

        assert error.message == custom_msg
        assert error.limit_type == "ai_agents"
        assert error.current_usage == 4
        assert error.limit == 3

    def test_limit_error_inheritance(self):
        """
        Test that VariantLimitExceededError is a subclass of VariantLimitError.
        """
        from backend.app.services.variant_limit_service import (
            VariantLimitError,
            VariantLimitExceededError,
        )

        assert issubclass(VariantLimitExceededError, VariantLimitError)

        error = VariantLimitExceededError(
            limit_type="kb_docs",
            current_usage=600,
            limit=500,
        )

        assert isinstance(error, VariantLimitError)
        assert isinstance(error, Exception)

    def test_limit_error_base_attributes(self):
        """
        Test that VariantLimitError (base class) stores all attributes.
        """
        from backend.app.services.variant_limit_service import VariantLimitError

        error = VariantLimitError(
            message="Something went wrong",
            limit_type="voice_slots",
            current_usage=10,
            limit=5,
        )

        assert error.limit_type == "voice_slots"
        assert error.current_usage == 10
        assert error.limit == 5
        assert str(error) == "Something went wrong"

    def test_limit_error_without_optional_fields(self):
        """
        Test that VariantLimitError works without optional fields.
        """
        from backend.app.services.variant_limit_service import VariantLimitError

        error = VariantLimitError(message="Generic limit error")

        assert error.message == "Generic limit error"
        assert error.limit_type is None
        assert error.current_usage is None
        assert error.limit is None


# =============================================================================
# 11. Edge Cases
# =============================================================================

class TestVariantLimitEdgeCases:
    """Test edge-case scenarios in variant limit enforcement."""

    def test_company_id_validation_none_raises_error(self):
        """
        Test that None company_id raises VariantLimitError.

        BC-001: company_id is required.
        """
        from backend.app.services.variant_limit_service import (
            VariantLimitService,
            VariantLimitError,
        )

        service = VariantLimitService()

        with pytest.raises(VariantLimitError, match="company_id is required"):
            service.get_company_limits(None)

    def test_company_id_validation_empty_raises_error(self):
        """
        Test that empty string company_id raises VariantLimitError.

        BC-001: company_id cannot be empty.
        """
        from backend.app.services.variant_limit_service import (
            VariantLimitService,
            VariantLimitError,
        )

        service = VariantLimitService()

        with pytest.raises(VariantLimitError, match="company_id cannot be empty"):
            service.get_company_limits("   ")

    def test_invalid_limit_type_raises_error(self):
        """
        Test that an invalid limit_type in enforce_limit raises VariantLimitError.
        """
        from backend.app.services.variant_limit_service import (
            VariantLimitService,
            VariantLimitError,
        )

        service = VariantLimitService()
        company_id = uuid4()

        with pytest.raises(VariantLimitError, match="Invalid limit_type"):
            service.enforce_limit(company_id, "unknown_resource_type")

    def test_enforce_limit_requires_current_count_for_non_tickets(self):
        """
        Test that enforce_limit raises when current_count is None for non-ticket types.
        """
        from backend.app.services.variant_limit_service import (
            VariantLimitService,
            VariantLimitError,
        )

        service = VariantLimitService()
        company_id = uuid4()

        with pytest.raises(VariantLimitError, match="current_count is required"):
            service.enforce_limit(company_id, "ai_agents")

    def test_variant_name_case_insensitive(self):
        """
        Test that variant names are handled case-insensitively.
        """
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()

        session = _make_mock_session()
        session.query.return_value.filter.return_value.first.return_value = None

        with patch('backend.app.services.variant_limit_service.get_variant_limits', return_value=None), \
             patch('backend.app.services.variant_limit_service.SessionLocal', return_value=session):
            result_upper = service.get_variant_limits("STARTER")
            result_mixed = service.get_variant_limits("GrOwTh")

        assert result_upper["monthly_tickets"] == 2000
        assert result_mixed["monthly_tickets"] == 5000
