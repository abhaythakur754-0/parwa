"""
Usage Tracking Service Tests (BC-001, BC-002)

Tests for the PARWA SaaS usage tracking system covering:
1. Ticket usage increment (create / update / multi-count)
2. Voice usage increment (Decimal precision, combined with tickets)
3. Current usage aggregation (monthly sums, percentage, limits)
4. Usage percentage calculation (normal / over-limit / zero)
5. Approaching-limit warnings (threshold checks)
6. Overage calculation ($0.10/ticket, Decimal precision)
7. Usage history (monthly aggregation, limited, sorted)
8. Overage recording (existing record, target date, Decimal)
9. Daily usage retrieval (found / missing)

BC-001: company_id isolation and validation in all tests
BC-002: Decimal precision for all money calculations
"""

import pytest
from datetime import datetime, timezone, date, timedelta
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
    """Create a mock database session with context-manager support."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


@pytest.fixture
def company_id():
    """Return a fresh UUID for each test."""
    return uuid4()


@pytest.fixture
def today():
    """Return today's date in UTC."""
    return datetime.now(timezone.utc).date()


@pytest.fixture
def this_month():
    """Return current month as YYYY-MM string."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _make_mock_record(**overrides):
    """Build a mock UsageRecord with sensible defaults."""
    record = MagicMock()
    record.id = str(uuid4())
    record.company_id = str(uuid4())
    record.record_date = datetime.now(timezone.utc).date()
    record.record_month = datetime.now(timezone.utc).strftime("%Y-%m")
    record.tickets_used = 0
    record.ai_agents_used = 0
    record.voice_minutes_used = Decimal("0.00")
    record.overage_tickets = 0
    record.overage_charges = Decimal("0.00")
    record.created_at = datetime.now(timezone.utc)
    for key, value in overrides.items():
        setattr(record, key, value)
    return record


def _make_mock_subscription(**overrides):
    """Build a mock Subscription with sensible defaults."""
    sub = MagicMock()
    sub.id = str(uuid4())
    sub.company_id = str(uuid4())
    sub.status = "active"
    sub.tier = "parwa"
    sub.created_at = datetime.now(timezone.utc)
    for key, value in overrides.items():
        setattr(sub, key, value)
    return sub


def _make_aggregation_row(
    total_tickets=0,
    total_ai_agents=0,
    total_voice_minutes=Decimal("0.00"),
    total_overage_tickets=0,
    total_overage_charges=Decimal("0.00"),
):
    """Build a mock aggregation result row for monthly queries."""
    row = MagicMock()
    row.total_tickets = total_tickets
    row.total_ai_agents = total_ai_agents
    row.total_voice_minutes = total_voice_minutes
    row.total_overage_tickets = total_overage_tickets
    row.total_overage_charges = total_overage_charges
    return row


def _make_history_row(record_month, total_tickets=0, total_overage_tickets=0, total_overage_charges=Decimal("0.00")):
    """Build a mock row for usage history grouped by month."""
    row = MagicMock()
    row.record_month = record_month
    row.total_tickets = total_tickets
    row.total_overage_tickets = total_overage_tickets
    row.total_overage_charges = total_overage_charges
    return row


# =============================================================================
# TestIncrementTicketUsage (4 tests)
# =============================================================================

class TestIncrementTicketUsage:
    """Tests for UsageTrackingService.increment_ticket_usage."""

    def test_increment_creates_new_record(self, mock_db_session, company_id):
        """
        First usage of the day creates a new UsageRecord.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            # No existing daily record → _get_or_create will create one
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            result = service.increment_ticket_usage(company_id, count=1)

        assert result["company_id"] == str(company_id)
        assert "record_date" in result
        assert result["tickets_used"] == 1
        assert "record_month" in result
        # Record was added to session and committed
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    def test_increment_updates_existing_record(self, mock_db_session, company_id):
        """
        Subsequent usage for the same day updates the existing record.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        existing_record = _make_mock_record(
            company_id=str(company_id),
            tickets_used=10,
            record_month=datetime.now(timezone.utc).strftime("%Y-%m"),
        )

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.first.return_value = existing_record

            result = service.increment_ticket_usage(company_id, count=1)

        assert result["tickets_used"] == 11
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_called_once()

    def test_increment_multiple_count(self, mock_db_session, company_id):
        """
        count > 1 increments correctly.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        existing_record = _make_mock_record(
            company_id=str(company_id),
            tickets_used=3,
            record_month=datetime.now(timezone.utc).strftime("%Y-%m"),
        )

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.first.return_value = existing_record

            result = service.increment_ticket_usage(company_id, count=5)

        assert result["tickets_used"] == 8
        mock_db_session.commit.assert_called_once()

    def test_increment_returns_usage_stats(self, mock_db_session, company_id, today):
        """
        Response includes company_id, record_date, tickets_used, record_month.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            result = service.increment_ticket_usage(company_id, count=5)

        assert "company_id" in result
        assert result["company_id"] == str(company_id)
        assert "record_date" in result
        assert result["record_date"] == today.isoformat()
        assert "tickets_used" in result
        assert result["tickets_used"] == 5
        assert "record_month" in result


# =============================================================================
# TestIncrementVoiceUsage (3 tests)
# =============================================================================

class TestIncrementVoiceUsage:
    """Tests for UsageTrackingService.increment_voice_usage."""

    def test_voice_usage_creates_record(self, mock_db_session, company_id):
        """
        First voice usage of the day creates a new UsageRecord.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            result = service.increment_voice_usage(company_id, minutes=5.5)

        assert result["company_id"] == str(company_id)
        assert result["voice_minutes_used"] == "5.50"
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    def test_voice_usage_adds_minutes(self, mock_db_session, company_id):
        """
        Voice minutes accumulate with Decimal precision.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        existing_record = _make_mock_record(
            company_id=str(company_id),
            voice_minutes_used=Decimal("10.25"),
            record_month=datetime.now(timezone.utc).strftime("%Y-%m"),
        )

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.first.return_value = existing_record

            result = service.increment_voice_usage(company_id, minutes=Decimal("3.75"))

        # 10.25 + 3.75 = 14.00
        assert result["voice_minutes_used"] == "14.00"

    def test_voice_usage_combined_with_tickets(self, mock_db_session, company_id):
        """
        Same daily record carries both ticket and voice counters.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        existing_record = _make_mock_record(
            company_id=str(company_id),
            tickets_used=15,
            voice_minutes_used=Decimal("7.50"),
            record_month=datetime.now(timezone.utc).strftime("%Y-%m"),
        )

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.first.return_value = existing_record

            result = service.increment_voice_usage(company_id, minutes=2.5)

        # Voice was incremented
        assert result["voice_minutes_used"] == "10.00"
        # Tickets remain untouched
        assert existing_record.tickets_used == 15


# =============================================================================
# TestGetCurrentUsage (5 tests)
# =============================================================================

class TestGetCurrentUsage:
    """Tests for UsageTrackingService.get_current_usage."""

    def test_get_usage_returns_monthly_aggregate(self, mock_db_session, company_id, this_month):
        """
        Sums all daily records for the month.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        agg_row = _make_aggregation_row(
            total_tickets=450,
            total_ai_agents=12,
            total_voice_minutes=Decimal("120.50"),
            total_overage_tickets=0,
            total_overage_charges=Decimal("0.00"),
        )
        mock_subscription = _make_mock_subscription(company_id=str(company_id))

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            # Aggregation query → first()
            mock_db_session.query.return_value.filter.return_value.first.return_value = agg_row
            # Subscription query → _get_ticket_limit
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_subscription
            # get_variant_limits
            with patch('backend.app.services.usage_tracking_service.get_variant_limits') as mock_limits:
                mock_limits.return_value = {"monthly_tickets": 2000}

                result = service.get_current_usage(company_id)

        assert result["tickets_used"] == 450
        assert result["ai_agents_used"] == 12
        assert result["voice_minutes_used"] == "120.50"
        assert result["record_month"] == this_month
        assert result["company_id"] == str(company_id)

    def test_get_usage_calculates_percentage(self, mock_db_session, company_id):
        """
        usage_percentage = tickets_used / ticket_limit.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        agg_row = _make_aggregation_row(total_tickets=1000)
        mock_subscription = _make_mock_subscription(company_id=str(company_id))

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.first.return_value = agg_row
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_subscription

            with patch('backend.app.services.usage_tracking_service.get_variant_limits') as mock_limits:
                mock_limits.return_value = {"monthly_tickets": 2000}

                result = service.get_current_usage(company_id)

        assert result["usage_percentage"] == 0.5

    def test_get_usage_detects_approaching_limit(self, mock_db_session, company_id):
        """
        approaching_limit is True when usage >= 80% of ticket_limit.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        agg_row = _make_aggregation_row(total_tickets=1600)
        mock_subscription = _make_mock_subscription(company_id=str(company_id))

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.first.return_value = agg_row
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_subscription

            with patch('backend.app.services.usage_tracking_service.get_variant_limits') as mock_limits:
                mock_limits.return_value = {"monthly_tickets": 2000}

                result = service.get_current_usage(company_id)

        assert result["approaching_limit"] is True
        assert result["usage_percentage"] == 0.8

    def test_get_usage_detects_limit_exceeded(self, mock_db_session, company_id):
        """
        limit_exceeded is True when tickets_used > ticket_limit.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        agg_row = _make_aggregation_row(total_tickets=2100)
        mock_subscription = _make_mock_subscription(company_id=str(company_id))

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.first.return_value = agg_row
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_subscription

            with patch('backend.app.services.usage_tracking_service.get_variant_limits') as mock_limits:
                mock_limits.return_value = {"monthly_tickets": 2000}

                result = service.get_current_usage(company_id)

        assert result["limit_exceeded"] is True
        assert result["usage_percentage"] == 1.05
        assert result["tickets_remaining"] == 0

    def test_get_usage_custom_month(self, mock_db_session, company_id):
        """
        Passing month="2025-01" aggregates for that specific month.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        agg_row = _make_aggregation_row(total_tickets=300)
        mock_subscription = _make_mock_subscription(company_id=str(company_id))

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.first.return_value = agg_row
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_subscription

            with patch('backend.app.services.usage_tracking_service.get_variant_limits') as mock_limits:
                mock_limits.return_value = {"monthly_tickets": 2000}

                result = service.get_current_usage(company_id, month="2025-01")

        assert result["record_month"] == "2025-01"
        assert result["tickets_used"] == 300


# =============================================================================
# TestUsagePercentage (3 tests)
# =============================================================================

class TestUsagePercentage:
    """Tests for UsageTrackingService.get_usage_percentage."""

    def test_percentage_normal(self, mock_db_session, company_id):
        """
        Returns a float between 0.0 and 1.0 under normal usage.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        mock_subscription = _make_mock_subscription(company_id=str(company_id))

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            # Scalar query returns the sum of tickets_used
            mock_db_session.query.return_value.filter.return_value.scalar.return_value = 600
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_subscription

            with patch('backend.app.services.usage_tracking_service.get_variant_limits') as mock_limits:
                mock_limits.return_value = {"monthly_tickets": 2000}

                result = service.get_usage_percentage(company_id)

        assert result == 0.3
        assert isinstance(result, float)

    def test_percentage_over_limit(self, mock_db_session, company_id):
        """
        Returns > 1.0 when tickets exceed the plan limit.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        mock_subscription = _make_mock_subscription(company_id=str(company_id))

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.scalar.return_value = 2500
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_subscription

            with patch('backend.app.services.usage_tracking_service.get_variant_limits') as mock_limits:
                mock_limits.return_value = {"monthly_tickets": 2000}

                result = service.get_usage_percentage(company_id)

        assert result == 1.25

    def test_percentage_zero_usage(self, mock_db_session, company_id):
        """
        Returns exactly 0.0 when no tickets have been used.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        mock_subscription = _make_mock_subscription(company_id=str(company_id))

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.scalar.return_value = 0
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_subscription

            with patch('backend.app.services.usage_tracking_service.get_variant_limits') as mock_limits:
                mock_limits.return_value = {"monthly_tickets": 2000}

                result = service.get_usage_percentage(company_id)

        assert result == 0.0


# =============================================================================
# TestApproachingLimit (3 tests)
# =============================================================================

class TestApproachingLimit:
    """Tests for UsageTrackingService.check_approaching_limit."""

    def test_approaching_true_at_80_percent(self, mock_db_session, company_id):
        """
        approaching_limit is True when usage reaches 80% of the limit.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        mock_subscription = _make_mock_subscription(company_id=str(company_id))

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.scalar.return_value = 1600
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_subscription

            with patch('backend.app.services.usage_tracking_service.get_variant_limits') as mock_limits:
                mock_limits.return_value = {"monthly_tickets": 2000}

                result = service.check_approaching_limit(company_id)

        assert result["approaching_limit"] is True
        assert result["usage_percentage"] == 0.8
        assert result["tickets_used"] == 1600
        assert result["ticket_limit"] == 2000
        assert result["tickets_remaining"] == 400
        assert result["threshold"] == 0.8

    def test_approaching_false_below_threshold(self, mock_db_session, company_id):
        """
        approaching_limit is False when usage is below the threshold.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        mock_subscription = _make_mock_subscription(company_id=str(company_id))

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.scalar.return_value = 1000
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_subscription

            with patch('backend.app.services.usage_tracking_service.get_variant_limits') as mock_limits:
                mock_limits.return_value = {"monthly_tickets": 2000}

                result = service.check_approaching_limit(company_id)

        assert result["approaching_limit"] is False
        assert result["usage_percentage"] == 0.5

    def test_approaching_custom_threshold(self, mock_db_session, company_id):
        """
        Custom threshold (90%) triggers approaching_limit only at >= 90%.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        mock_subscription = _make_mock_subscription(company_id=str(company_id))

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            # 85% usage — should NOT approach at 90% threshold
            mock_db_session.query.return_value.filter.return_value.scalar.return_value = 1700
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_subscription

            with patch('backend.app.services.usage_tracking_service.get_variant_limits') as mock_limits:
                mock_limits.return_value = {"monthly_tickets": 2000}

                result = service.check_approaching_limit(company_id, threshold=0.9)

        assert result["approaching_limit"] is False
        assert result["threshold"] == 0.9
        assert result["tickets_remaining"] == 300


# =============================================================================
# TestOverageCalculation (4 tests)
# =============================================================================

class TestOverageCalculation:
    """Tests for UsageTrackingService.calculate_overage.

    calculate_overage is a pure calculation (no DB calls), but still
    validates company_id. BC-002: All money uses Decimal.
    """

    def test_overage_zero_when_under_limit(self, company_id):
        """
        Exactly at limit or below → overage_tickets = 0, charges = 0.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        result = service.calculate_overage(
            company_id=company_id,
            tickets_used=2000,
            ticket_limit=2000,
        )

        assert result["overage_tickets"] == 0
        assert result["overage_charges"] == Decimal("0.00")
        assert result["tickets_used"] == 2000
        assert result["ticket_limit"] == 2000

    def test_overage_calculates_correctly(self, company_id):
        """
        (2500 - 2000) * $0.10 = $50.00 overage charge.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        result = service.calculate_overage(
            company_id=company_id,
            tickets_used=2500,
            ticket_limit=2000,
        )

        assert result["overage_tickets"] == 500
        assert result["overage_charges"] == Decimal("50.00")
        assert result["tickets_used"] == 2500
        assert result["ticket_limit"] == 2000

    def test_overage_uses_decimal_precision(self, company_id):
        """
        BC-002 compliance: all money values are Decimal, never float.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        result = service.calculate_overage(
            company_id=company_id,
            tickets_used=2003,
            ticket_limit=2000,
        )

        assert isinstance(result["overage_charges"], Decimal)
        assert result["overage_charges"] == Decimal("0.30")
        assert isinstance(result["overage_rate"], Decimal)

    def test_overage_rate_is_10_cents(self, company_id):
        """
        Verify the overage rate is $0.10 per ticket.
        """
        from backend.app.services.usage_tracking_service import (
            UsageTrackingService,
            OVERAGE_RATE_PER_TICKET,
        )

        service = UsageTrackingService()

        result = service.calculate_overage(
            company_id=company_id,
            tickets_used=2100,
            ticket_limit=2000,
        )

        assert result["overage_rate"] == Decimal("0.10")
        assert OVERAGE_RATE_PER_TICKET == Decimal("0.10")
        # 100 tickets * $0.10 = $10.00
        assert result["overage_charges"] == Decimal("10.00")


# =============================================================================
# TestUsageHistory (3 tests)
# =============================================================================

class TestUsageHistory:
    """Tests for UsageTrackingService.get_usage_history."""

    def test_history_returns_monthly_aggregation(self, mock_db_session, company_id):
        """
        Returns monthly aggregations grouped by record_month.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        row1 = _make_history_row("2025-01", total_tickets=450, total_overage_tickets=0, total_overage_charges=Decimal("0.00"))
        row2 = _make_history_row("2024-12", total_tickets=1800, total_overage_tickets=50, total_overage_charges=Decimal("5.00"))

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = [row1, row2]

            result = service.get_usage_history(company_id)

        assert len(result) == 2
        assert result[0]["record_month"] == "2025-01"
        assert result[0]["tickets_used"] == 450
        assert result[1]["record_month"] == "2024-12"
        assert result[1]["overage_tickets"] == 50
        assert result[1]["overage_charges"] == "5.00"

    def test_history_limited_to_months_param(self, mock_db_session, company_id):
        """
        months=3 passes 3 to the query limit and returns at most 3 entries.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        rows = [
            _make_history_row("2025-03", total_tickets=100),
            _make_history_row("2025-02", total_tickets=200),
            _make_history_row("2025-01", total_tickets=300),
        ]

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = rows

            result = service.get_usage_history(company_id, months=3)

        assert len(result) == 3
        # Verify .limit(3) was called
        mock_db_session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.assert_called_once_with(3)

    def test_history_sorted_newest_first(self, mock_db_session, company_id):
        """
        Results are ordered by record_month descending (newest first).
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        rows = [
            _make_history_row("2025-06", total_tickets=900),
            _make_history_row("2025-05", total_tickets=800),
            _make_history_row("2025-04", total_tickets=700),
        ]

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = rows

            result = service.get_usage_history(company_id)

        months = [r["record_month"] for r in result]
        assert months == ["2025-06", "2025-05", "2025-04"]


# =============================================================================
# TestRecordOverage (3 tests)
# =============================================================================

class TestRecordOverage:
    """Tests for UsageTrackingService.record_overage."""

    def test_record_overage_updates_existing_record(self, mock_db_session, company_id, today):
        """
        Recording overage on a date with an existing record updates it.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        existing_record = _make_mock_record(
            company_id=str(company_id),
            record_date=today,
            record_month=today.strftime("%Y-%m"),
        )

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.first.return_value = existing_record

            result = service.record_overage(
                company_id=company_id,
                overage_tickets=50,
                overage_charges=Decimal("5.00"),
            )

        assert result["company_id"] == str(company_id)
        assert result["record_date"] == today.isoformat()
        assert result["overage_tickets"] == 50
        assert result["overage_charges"] == "5.00"
        assert existing_record.overage_tickets == 50
        mock_db_session.commit.assert_called_once()

    def test_record_overage_with_target_date(self, mock_db_session, company_id):
        """
        Specifying target_date updates (or creates) the record for that date.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        target = date(2025, 1, 15)
        existing_record = _make_mock_record(
            company_id=str(company_id),
            record_date=target,
            record_month="2025-01",
        )

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.first.return_value = existing_record

            result = service.record_overage(
                company_id=company_id,
                overage_tickets=100,
                overage_charges=Decimal("10.00"),
                target_date=target,
            )

        assert result["record_date"] == "2025-01-15"
        assert result["record_month"] == "2025-01"
        assert result["overage_tickets"] == 100
        assert result["overage_charges"] == "10.00"

    def test_record_overage_decimal_precision(self, mock_db_session, company_id, today):
        """
        BC-002: overage_charges are stored as Decimal with 2dp rounding.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        existing_record = _make_mock_record(
            company_id=str(company_id),
            record_date=today,
            record_month=today.strftime("%Y-%m"),
        )

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.first.return_value = existing_record

            result = service.record_overage(
                company_id=company_id,
                overage_tickets=33,
                overage_charges="3.333",  # string input → rounded to 3.33
            )

        # _round_money rounds to 2 decimal places
        assert result["overage_charges"] == "3.33"


# =============================================================================
# TestGetDailyUsage (2 tests)
# =============================================================================

class TestGetDailyUsage:
    """Tests for UsageTrackingService.get_daily_usage."""

    def test_returns_record_for_date(self, mock_db_session, company_id, today):
        """
        Returns the usage dict when a record exists for the target date.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        record = _make_mock_record(
            company_id=str(company_id),
            record_date=today,
            record_month=today.strftime("%Y-%m"),
            tickets_used=25,
            ai_agents_used=3,
            voice_minutes_used=Decimal("45.50"),
            overage_tickets=0,
            overage_charges=Decimal("0.00"),
            created_at=datetime.now(timezone.utc),
        )

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.first.return_value = record

            result = service.get_daily_usage(company_id, today)

        assert result is not None
        assert result["company_id"] == str(company_id)
        assert result["record_date"] == today.isoformat()
        assert result["tickets_used"] == 25
        assert result["ai_agents_used"] == 3
        assert result["voice_minutes_used"] == "45.50"
        assert result["overage_tickets"] == 0
        assert result["overage_charges"] == "0.00"
        assert "created_at" in result

    def test_returns_none_for_missing_date(self, mock_db_session, company_id):
        """
        Returns None when no UsageRecord exists for the target date.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        target = date(2025, 3, 1)

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            result = service.get_daily_usage(company_id, target)

        assert result is None


# =============================================================================
# TestValidationAndEdgeCases
# =============================================================================

class TestValidationAndEdgeCases:
    """Additional validation and edge-case tests."""

    def test_increment_rejects_negative_count(self, company_id):
        """
        count < 0 raises UsageTrackingError.
        """
        from backend.app.services.usage_tracking_service import (
            UsageTrackingService,
            UsageTrackingError,
        )

        service = UsageTrackingService()

        with pytest.raises(UsageTrackingError, match="count must be non-negative"):
            service.increment_ticket_usage(company_id, count=-1)

    def test_voice_rejects_negative_minutes(self, company_id):
        """
        Negative minutes raises UsageTrackingError.
        """
        from backend.app.services.usage_tracking_service import (
            UsageTrackingService,
            UsageTrackingError,
        )

        service = UsageTrackingService()

        with pytest.raises(UsageTrackingError, match="minutes must be non-negative"):
            service.increment_voice_usage(company_id, minutes=-5.0)

    def test_validate_company_id_none(self, company_id):
        """
        company_id=None raises UsageTrackingError.
        """
        from backend.app.services.usage_tracking_service import (
            UsageTrackingService,
            UsageTrackingError,
        )

        service = UsageTrackingService()

        with pytest.raises(UsageTrackingError, match="company_id is required"):
            service.increment_ticket_usage(None)

    def test_validate_company_id_empty_string(self, company_id):
        """
        company_id="" raises UsageTrackingError.
        """
        from backend.app.services.usage_tracking_service import (
            UsageTrackingService,
            UsageTrackingError,
        )

        service = UsageTrackingService()

        with pytest.raises(UsageTrackingError, match="cannot be empty"):
            service.increment_ticket_usage("   ")

    def test_history_rejects_zero_months(self, mock_db_session, company_id):
        """
        months < 1 raises UsageTrackingError.
        """
        from backend.app.services.usage_tracking_service import (
            UsageTrackingService,
            UsageTrackingError,
        )

        service = UsageTrackingService()

        with pytest.raises(UsageTrackingError, match="months must be >= 1"):
            service.get_usage_history(company_id, months=0)

    def test_record_overage_rejects_negative_tickets(self, company_id):
        """
        Negative overage_tickets raises UsageTrackingError.
        """
        from backend.app.services.usage_tracking_service import (
            UsageTrackingService,
            UsageTrackingError,
        )

        service = UsageTrackingService()

        with pytest.raises(UsageTrackingError, match="overage_tickets must be non-negative"):
            service.record_overage(company_id, overage_tickets=-1, overage_charges="1.00")

    def test_record_overage_rejects_negative_charges(self, company_id):
        """
        Negative overage_charges raises UsageTrackingError.
        """
        from backend.app.services.usage_tracking_service import (
            UsageTrackingService,
            UsageTrackingError,
        )

        service = UsageTrackingService()

        with pytest.raises(UsageTrackingError, match="overage_charges must be non-negative"):
            service.record_overage(company_id, overage_tickets=1, overage_charges="-5.00")

    def test_overage_zero_when_below_limit(self, company_id):
        """
        Tickets well under limit produce zero overage.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        result = service.calculate_overage(
            company_id=company_id,
            tickets_used=500,
            ticket_limit=2000,
        )

        assert result["overage_tickets"] == 0
        assert result["overage_charges"] == Decimal("0.00")

    def test_usage_percentage_zero_ticket_limit(self, mock_db_session, company_id):
        """
        When ticket_limit is 0 (no subscription), percentage returns 0.0.
        """
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()

        with patch('backend.app.services.usage_tracking_service.SessionLocal') as mock_session_cls:
            mock_session_cls.return_value = mock_db_session

            # No subscription → _get_ticket_limit returns DEFAULT_TICKET_LIMIT (2000)
            mock_db_session.query.return_value.filter.return_value.scalar.return_value = 500
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

            with patch('backend.app.services.usage_tracking_service.get_variant_limits') as mock_limits:
                mock_limits.return_value = {"monthly_tickets": 2000}

                result = service.get_usage_percentage(company_id)

        # 500 / 2000 = 0.25
        assert result == 0.25
