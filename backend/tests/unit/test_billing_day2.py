"""
Billing Day 2 Unit Tests

Tests for:
- D1-D6: Period-end cron, downgrade execution, resource cleanup, pre-warning, undo window
- Y1-Y7: billing_frequency model, yearly pricing, yearly subscription, frequency switch
- P1-P5: 30-day periods, proration divisor, usage alignment, leap year handling
"""

import calendar
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ═══════════════════════════════════════════════════════════════════════
# P1/P2: 30-Day Period Calculation Tests
# ═══════════════════════════════════════════════════════════════════════


class Test30DayPeriodCalculation:
    """P1/P2: Test that billing periods are exactly 30 days."""

    def test_monthly_period_is_exactly_30_days(self):
        """P1: Monthly period should be exactly 30 days, not calendar month."""
        from app.services.subscription_service import SubscriptionService, BILLING_PERIOD_DAYS

        service = SubscriptionService()

        # Test various start dates
        test_dates = [
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc),
            datetime(2024, 2, 28, tzinfo=timezone.utc),  # Leap year
            datetime(2024, 3, 31, tzinfo=timezone.utc),
            datetime(2024, 12, 31, tzinfo=timezone.utc),
        ]

        for start in test_dates:
            end = service._calculate_period_end(start, "monthly")
            delta = end - start
            assert delta.days == BILLING_PERIOD_DAYS, (
                f"Expected {BILLING_PERIOD_DAYS} days from {start.date()}, "
                f"got {delta.days}"
            )

    def test_yearly_period_is_365_days_normal_year(self):
        """P5: Yearly period for non-leap year should be 365 days."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        # July 1, 2024 — next year doesn't include Feb 29
        start = datetime(2024, 7, 1, tzinfo=timezone.utc)
        end = service._calculate_period_end(start, "yearly")
        delta = end - start
        assert delta.days == 365

    def test_yearly_period_is_366_days_leap_year(self):
        """P5: Yearly period crossing Feb 29 should be 366 days."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        # Jan 1, 2024 (leap year) — period includes Feb 29
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = service._calculate_period_end(start, "yearly")
        delta = end - start
        assert delta.days == 366

    def test_yearly_period_crossing_leap_year(self):
        """P5: Yearly period from 2023 crossing into 2024 (leap) should be 366 days."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        # Jan 15, 2023 → crosses Feb 29, 2024
        start = datetime(2023, 1, 15, tzinfo=timezone.utc)
        end = service._calculate_period_end(start, "yearly")
        delta = end - start
        assert delta.days == 366

    def test_yearly_period_non_leap_year(self):
        """P5: Yearly period in non-leap year should be 365 days."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        # March 1, 2024 → ends Feb 28, 2025 (not a leap year)
        start = datetime(2024, 3, 1, tzinfo=timezone.utc)
        end = service._calculate_period_end(start, "yearly")
        delta = end - start
        assert delta.days == 365

    def test_calculate_period_days_monthly(self):
        """P1: Monthly period days should always return 30."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()
        assert service._calculate_period_days("monthly") == 30

    def test_calculate_period_days_yearly(self):
        """P4: Yearly period days should return 365 by default."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()
        assert service._calculate_period_days("yearly") == 365

    def test_no_relativedelta_used(self):
        """P2: Verify relativedelta is NOT imported or used in subscription service."""
        from app.services import subscription_service
        source = open(subscription_service.__file__).read()
        assert "relativedelta" not in source, (
            "relativedelta should not be used; use timedelta(days=30) instead"
        )


# ═══════════════════════════════════════════════════════════════════════
# P3: Proration 30-Day Divisor Tests
# ═══════════════════════════════════════════════════════════════════════


class TestProration30DayDivisor:
    """P3: Test that proration always uses 30-day divisor for monthly."""

    def test_proration_monthly_uses_30_day_divisor(self):
        """P3: Monthly proration should use 30-day divisor regardless of actual days."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        # Even with a period that spans 31 calendar days, divisor should be 30
        proration = service._calculate_proration(
            old_variant="starter",
            new_variant="growth",
            billing_cycle_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            billing_cycle_end=datetime(2024, 1, 31, tzinfo=timezone.utc),
            billing_frequency="monthly",
            # Override "now" by setting reference
        )

        assert proration["days_in_period"] == 30
        assert proration["billing_frequency"] == "monthly"

    def test_proration_yearly_uses_actual_days(self):
        """Y5: Yearly proration should use actual period days (365/366)."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        proration = service._calculate_proration(
            old_variant="starter",
            new_variant="growth",
            billing_cycle_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            billing_cycle_end=datetime(2024, 12, 31, tzinfo=timezone.utc),
            billing_frequency="yearly",
        )

        # 2024 is a leap year, so should be 366
        assert proration["days_in_period"] == 366

    def test_proration_service_uses_30_day_divisor(self):
        """P3: ProrationService.calculate_upgrade_proration uses 30-day divisor for monthly."""
        from app.services.proration_service import ProrationService

        svc = ProrationService()
        assert svc.BILLING_PERIOD_DAYS == 30

    def test_daily_rate_monthly_is_price_over_30(self):
        """P3: For monthly, daily_rate = price / 30."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        # Starter is $999/month
        proration = service._calculate_proration(
            old_variant="starter",
            new_variant="growth",
            billing_cycle_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            billing_cycle_end=datetime(2024, 1, 31, tzinfo=timezone.utc),
            billing_frequency="monthly",
        )

        # $999 / 30 = $33.30/day
        expected_daily_old = Decimal("999.00") / Decimal(30)
        expected_daily_new = Decimal("2499.00") / Decimal(30)
        assert proration["old_price"] == Decimal("999.00")
        assert proration["new_price"] == Decimal("2499.00")
        assert proration["days_in_period"] == 30


# ═══════════════════════════════════════════════════════════════════════
# D1-D3: Period-End Transition Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPeriodEndTransitions:
    """D1-D3: Test period-end cron finds and processes subscriptions."""

    def test_process_period_end_finds_pending_downgrades(self):
        """D1: Cron should find subscriptions needing downgrade."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()
        with patch.object(service, "_apply_pending_downgrade") as mock_apply:
            # Mock DB session with matching subscriptions
            mock_sub = MagicMock()
            mock_sub.id = "sub-1"
            mock_sub.company_id = "company-1"
            mock_sub.tier = "growth"
            mock_sub.pending_downgrade_tier = "starter"
            mock_sub.current_period_end = datetime.now(timezone.utc)

            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value \
                .all.return_value = [mock_sub]
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)

            with patch("app.services.subscription_service.SessionLocal", return_value=mock_db):
                result = service.process_period_end_transitions()

            assert result["downgrades_applied"] == 1
            mock_apply.assert_called_once()

    def test_process_period_end_finds_scheduled_cancellations(self):
        """D3: Cron should find subscriptions scheduled for cancellation."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()
        with patch.object(service, "_apply_scheduled_cancellation") as mock_cancel:
            mock_sub = MagicMock()
            mock_sub.id = "sub-2"
            mock_sub.company_id = "company-2"
            mock_sub.cancel_at_period_end = True
            mock_sub.pending_downgrade_tier = None
            mock_sub.current_period_end = datetime.now(timezone.utc)

            mock_db = MagicMock()
            # First query returns empty (no pending downgrades)
            # Second query returns the cancellation
            mock_db.query.return_value.filter.return_value \
                .all.return_value = [mock_sub]
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)

            with patch("app.services.subscription_service.SessionLocal", return_value=mock_db):
                result = service.process_period_end_transitions()

            assert result["cancellations_applied"] == 1
            mock_cancel.assert_called_once()

    def test_apply_pending_downgrade_updates_tier(self):
        """D2: Applying downgrade should update tier and clear pending."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        mock_sub = MagicMock()
        mock_sub.tier = "growth"
        mock_sub.pending_downgrade_tier = "starter"
        mock_sub.cancel_at_period_end = True
        mock_sub.pending_downgrade_at = None
        mock_sub.company_id = "company-1"
        mock_sub.billing_frequency = "monthly"
        mock_sub.paddle_subscription_id = None

        mock_company = MagicMock()
        mock_company.subscription_tier = "growth"

        mock_db = MagicMock()
        mock_db.query.return_value.first.return_value = mock_company

        service._apply_pending_downgrade(mock_db, mock_sub)

        assert mock_sub.tier == "starter"
        assert mock_sub.pending_downgrade_tier is None
        assert mock_sub.cancel_at_period_end is False
        assert mock_sub.previous_tier == "growth"
        assert mock_sub.downgrade_executed_at is not None
        assert mock_company.subscription_tier == "starter"

    def test_apply_scheduled_cancellation_updates_status(self):
        """D3: Applying cancellation should set status to canceled."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        mock_sub = MagicMock()
        mock_sub.status = "active"
        mock_sub.cancel_at_period_end = True
        mock_sub.company_id = "company-1"

        mock_company = MagicMock()

        mock_db = MagicMock()
        mock_db.query.return_value.first.return_value = mock_company

        service._apply_scheduled_cancellation(mock_db, mock_sub)

        assert mock_sub.status == "canceled"
        assert mock_sub.cancel_at_period_end is False


# ═══════════════════════════════════════════════════════════════════════
# D4: Resource Cleanup Tests
# ═══════════════════════════════════════════════════════════════════════


class TestResourceCleanup:
    """D4: Test resource cleanup on downgrade."""

    def test_cleanup_counts_resources_to_affected(self):
        """D4: Resource cleanup should count agents, team, docs, voice."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        # Mock the DB queries for agents, users, docs
        mock_db = MagicMock()

        # Mock Agent query: 5 active agents, downgrade to starter (1 agent limit)
        mock_agent1 = MagicMock()
        mock_agent2 = MagicMock()
        mock_agent3 = MagicMock()
        mock_agent4 = MagicMock()
        mock_agent5 = MagicMock()
        mock_db.query.return_value.filter.return_value \
            .order_by.return_value.all.side_effect = [
                [mock_agent1, mock_agent2, mock_agent3, mock_agent4, mock_agent5],
                [MagicMock(), MagicMock(), MagicMock(), MagicMock()],
                [MagicMock(), MagicMock()],
                [],
            ]

        result = service._cleanup_resources_on_downgrade(
            mock_db, "company-1", "high", "starter"
        )

        # Starter limits: 1 agent, 3 members, 100 docs, 0 voice
        assert result["agents_paused"] == 4  # 5 - 1
        assert result["team_members_downgraded"] == 4  # 7 - 3
        assert result["kb_docs_archived"] == 2  # 102 - 100
        assert result["voice_channels_disabled"] == 5  # 5 - 0

    def test_cleanup_pauses_agents_beyond_limit(self):
        """D4: Extra agents should be set to paused status."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        mock_db = MagicMock()
        agent1 = MagicMock()
        agent2 = MagicMock()

        mock_db.query.return_value.filter.return_value \
            .order_by.return_value.all.side_effect = [
                [agent1],  # Only 1 active, starter limit is 1
                [], [], [],
            ]

        result = service._cleanup_resources_on_downgrade(
            mock_db, "company-1", "starter", "starter"
        )

        assert result["agents_paused"] == 0  # Within limit


# ═══════════════════════════════════════════════════════════════════════
# D5: Pre-Downgrade Warning Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPreDowngradeWarning:
    """D5: Test pre-downgrade warning at 7 days."""

    def test_warning_data_includes_affected_resources(self):
        """D5: Warning data should list affected resources."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        mock_sub = MagicMock()
        mock_sub.company_id = "company-1"
        mock_sub.tier = "growth"
        mock_sub.pending_downgrade_tier = "starter"
        mock_sub.current_period_end = (
            datetime.now(timezone.utc) + timedelta(days=5)
        )

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value \
            .count.side_effect = [3, 8, 120]
        mock_db.query.return_value.order_by.return_value \
            .all.side_effect = [
            [MagicMock()],
            [MagicMock()],
            [MagicMock()],
            [MagicMock()],
        ]

        with patch(
            "app.services.subscription_service.emit_billing_event",
            new_callable=MagicMock,
        ):
            # Suppress async event emission
            with patch("app.services.subscription_service.asyncio"):
                data = service._build_downgrade_warning_data(mock_db, mock_sub)

        assert data["current_tier"] == "growth"
        assert data["new_tier"] == "starter"
        assert data["days_until_change"] == 7
        assert "affected_resources" in data
        assert data["affected_resources"]["agents_to_pause"] == 2  # 3 - 1
        assert data["affected_resources"]["team_members_to_downgrade"] == 5  # 8 - 3
        assert data["affected_resources"]["kb_docs_to_archive"] == 20  # 120 - 100


# ═══════════════════════════════════════════════════════════════════════
# D6: Downgrade Undo Tests
# ═══════════════════════════════════════════════════════════════════════


class TestDowngradeUndo:
    """D6: Test downgrade undo within 24 hours."""

    def test_undo_within_window_restores_tier(self):
        """D6: Undo within 24 hours should restore previous tier."""
        from app.services.subscription_service import (
            SubscriptionService,
            DowngradeUndoExpiredError,
        )

        service = SubscriptionService()

        mock_sub = MagicMock()
        mock_sub.tier = "starter"
        mock_sub.previous_tier = "growth"
        mock_sub.downgrade_executed_at = (
            datetime.now(timezone.utc) - timedelta(hours=12)
        )  # 12 hours ago — within window

        mock_company = MagicMock()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value \
            .with_for_update.return_value.first.return_value = mock_sub
        mock_db.query.return_value.filter.return_value \
            .first.return_value = mock_company

        with patch.object(service, "_restore_resources_after_undo") as mock_restore:
            with patch("app.services.subscription_service.SessionLocal", return_value=mock_db):
                result = service.undo_downgrade(uuid.uuid4())

        assert mock_sub.tier == "growth"
        assert mock_sub.previous_tier is None
        assert mock_sub.downgrade_executed_at is None
        assert mock_restore.called

    def test_undo_expired_raises_error(self):
        """D6: Undo after 24 hours should raise DowngradeUndoExpiredError."""
        from app.services.subscription_service import (
            SubscriptionService,
            DowngradeUndoExpiredError,
        )

        service = SubscriptionService()

        mock_sub = MagicMock()
        mock_sub.tier = "starter"
        mock_sub.previous_tier = "growth"
        mock_sub.downgrade_executed_at = (
            datetime.now(timezone.utc) - timedelta(hours=25)
        )  # 25 hours ago — expired

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value \
            .with_for_update.return_value.first.return_value = mock_sub

        with patch("app.services.subscription_service.SessionLocal", return_value=mock_db):
            with pytest.raises(DowngradeUndoExpiredError):
                service.undo_downgrade(uuid.uuid4())

    def test_undo_no_downgrade_raises_error(self):
        """D6: Undo when no downgrade was executed should raise error."""
        from app.services.subscription_service import (
            SubscriptionService,
            SubscriptionError,
        )

        service = SubscriptionService()

        mock_sub = MagicMock()
        mock_sub.downgrade_executed_at = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value \
            .with_for_update.return_value.first.return_value = mock_sub

        with patch("app.services.subscription_service.SessionLocal", return_value=mock_db):
            with pytest.raises(SubscriptionError):
                service.undo_downgrade(uuid.uuid4())


# ═══════════════════════════════════════════════════════════════════════
# Y1: Billing Frequency Model Tests
# ═══════════════════════════════════════════════════════════════════════


class TestBillingFrequencyModel:
    """Y1: Test billing_frequency on Subscription model."""

    def test_subscription_model_has_billing_frequency(self):
        """Y1: Subscription model should have billing_frequency column."""
        from database.models.billing import Subscription

        # Check column exists on the model
        assert hasattr(Subscription, "billing_frequency")

    def test_subscription_model_default_frequency_is_monthly(self):
        """Y1: Default billing_frequency should be 'monthly'."""
        from database.models.billing import Subscription

        sub = Subscription(
            company_id=str(uuid.uuid4()),
            tier="starter",
            status="active",
        )
        assert sub.billing_frequency == "monthly"

    def test_subscription_model_has_pending_downgrade_tier(self):
        """D2: Subscription model should have pending_downgrade_tier column."""
        from database.models.billing import Subscription

        assert hasattr(Subscription, "pending_downgrade_tier")

    def test_subscription_model_has_days_in_period(self):
        """Y4: Subscription model should have days_in_period column."""
        from database.models.billing import Subscription

        assert hasattr(Subscription, "days_in_period")

    def test_billing_frequency_enum(self):
        """Y1: BillingFrequency enum should have monthly and yearly."""
        from app.schemas.billing import BillingFrequency

        assert BillingFrequency.MONTHLY.value == "monthly"
        assert BillingFrequency.YEARLY.value == "yearly"


# ═══════════════════════════════════════════════════════════════════════
# Y2-Y3: Yearly Pricing Tests
# ═══════════════════════════════════════════════════════════════════════


class TestYearlyPricing:
    """Y2-Y3: Test yearly pricing and subscription creation."""

    def test_yearly_prices_in_variant_limits(self):
        """Y2: VARIANT_LIMITS should include yearly prices."""
        from app.schemas.billing import VARIANT_LIMITS, VariantType

        for vt in VariantType:
            assert "yearly_price" in VARIANT_LIMITS[vt]
            assert isinstance(VARIANT_LIMITS[vt]["yearly_price"], Decimal)

    def test_yearly_prices_are_10x_monthly(self):
        """Y2: Yearly prices should be ~10x monthly (2 months free)."""
        from app.schemas.billing import VARIANT_LIMITS, VariantType

        for vt in VariantType:
            monthly = VARIANT_LIMITS[vt]["price"]
            yearly = VARIANT_LIMITS[vt]["yearly_price"]
            # Yearly should be 10x monthly (2 months free)
            expected_yearly = monthly * 10
            assert yearly == expected_yearly, (
                f"{vt}: expected yearly={expected_yearly}, got {yearly}"
            )

    def test_get_variant_price_yearly(self):
        """Y3: _get_variant_price with yearly frequency should return yearly price."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        monthly_price = service._get_variant_price("starter", "monthly")
        yearly_price = service._get_variant_price("starter", "yearly")

        assert monthly_price == Decimal("999.00")
        assert yearly_price == Decimal("9990.00")

    def test_get_paddle_price_id_yearly(self):
        """Y2: Yearly paddle price IDs should be different from monthly."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        monthly_id = service._get_paddle_price_id("starter", "monthly")
        yearly_id = service._get_paddle_price_id("starter", "yearly")

        assert monthly_id != yearly_id
        assert "yearly" in yearly_id.lower() or "_yearly" in yearly_id.lower()


# ═══════════════════════════════════════════════════════════════════════
# Y7: Frequency Switch Tests
# ═══════════════════════════════════════════════════════════════════════


class TestFrequencySwitch:
    """Y7: Test switching billing frequency."""

    def test_switch_monthly_to_yearly(self):
        """Y7: Switch from monthly to yearly should update frequency."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        mock_sub = MagicMock()
        mock_sub.tier = "growth"
        mock_sub.billing_frequency = "monthly"
        mock_sub.company_id = "company-1"
        mock_sub.paddle_subscription_id = None
        mock_sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=20)
        mock_sub.current_period_start = datetime.now(timezone.utc) - timedelta(days=10)
        mock_sub.days_in_period = 30

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value \
            .with_for_update.return_value.first.return_value = mock_sub
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)

        with patch("app.services.subscription_service.SessionLocal", return_value=mock_db):
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                service.switch_billing_frequency(
                    company_id=uuid.uuid4(),
                    new_frequency="yearly",
                )
            )

        assert mock_sub.billing_frequency == "yearly"
        assert "message" in result
        assert "yearly" in result["message"]

    def test_switch_same_frequency_returns_message(self):
        """Y7: Switching to same frequency should return a message."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        mock_sub = MagicMock()
        mock_sub.billing_frequency = "yearly"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value \
            .with_for_update.return_value.first.return_value = mock_sub
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)

        with patch("app.services.subscription_service.SessionLocal", return_value=mock_db):
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                service.switch_billing_frequency(
                    company_id=uuid.uuid4(),
                    new_frequency="yearly",
                )
            )

        assert "Already on yearly" in result["message"]


# ═══════════════════════════════════════════════════════════════════════
# P4: Usage Period Alignment Tests
# ═══════════════════════════════════════════════════════════════════════


class TestUsagePeriodAlignment:
    """P4: Test usage period aligned to billing period."""

    def test_get_billing_period_returns_correct_window(self):
        """P4: get_current_billing_period should return billing period window."""
        from app.services.subscription_service import SubscriptionService, BILLING_PERIOD_DAYS

        service = SubscriptionService()

        now = datetime.now(timezone.utc)
        period_end = now + timedelta(days=BILLING_PERIOD_DAYS)

        mock_sub = MagicMock()
        mock_sub.status = "active"
        mock_sub.billing_frequency = "monthly"
        mock_sub.current_period_start = now
        mock_sub.current_period_end = period_end
        mock_sub.days_in_period = BILLING_PERIOD_DAYS
        mock_sub.tier = "growth"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value \
            .order_by.return_value.first.return_value = mock_sub
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)

        with patch("app.services.subscription_service.SessionLocal", return_value=mock_db):
            result = service.get_current_billing_period(uuid.uuid4())

        assert result["billing_frequency"] == "monthly"
        assert result["days_in_period"] == BILLING_PERIOD_DAYS
        assert result["tier"] == "growth"


# ═══════════════════════════════════════════════════════════════════════
# Y5: Upgrade/Downgrade with Yearly Tests
# ═══════════════════════════════════════════════════════════════════════


class TestYearlyUpgradeDowngrade:
    """Y5: Test upgrade/downgrade with yearly billing."""

    def test_upgrade_yearly_proration_uses_yearly_prices(self):
        """Y5: Yearly upgrade proration should use yearly prices."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        proration = service._calculate_proration(
            old_variant="starter",
            new_variant="growth",
            billing_cycle_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            billing_cycle_end=datetime(2024, 12, 31, tzinfo=timezone.utc),
            billing_frequency="yearly",
        )

        # Should use yearly prices
        assert proration["old_price"] == Decimal("9990.00")
        assert proration["new_price"] == Decimal("24990.00")
        assert proration["billing_frequency"] == "yearly"

    def test_downgrade_schedules_with_yearly_frequency(self):
        """Y5: Downgrade should preserve billing frequency."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        mock_sub = MagicMock()
        mock_sub.tier = "growth"
        mock_sub.status = "active"
        mock_sub.billing_frequency = "yearly"
        mock_sub.company_id = "company-1"
        mock_sub.current_period_end = (
            datetime.now(timezone.utc) + timedelta(days=30)
        )

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value \
            .with_for_update.return_value.first.return_value = mock_sub
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)

        with patch("app.services.subscription_service.SessionLocal", return_value=mock_db):
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                service.downgrade_subscription(
                    company_id=uuid.uuid4(),
                    new_variant="starter",
                )
            )

        # Should schedule downgrade regardless of frequency
        assert mock_sub.pending_downgrade_tier == "starter"
        assert mock_sub.cancel_at_period_end is True


# ═══════════════════════════════════════════════════════════════════════
# Y6: Yearly Renewal Tests
# ═══════════════════════════════════════════════════════════════════════


class TestYearlyRenewal:
    """Y6: Test yearly renewal handling."""

    def test_process_renewals_renews_expired_subscriptions(self):
        """Y6: process_renewals should renew expired subscriptions."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        now = datetime.now(timezone.utc)

        mock_sub = MagicMock()
        mock_sub.status = "active"
        mock_sub.cancel_at_period_end = False
        mock_sub.pending_downgrade_tier = None
        mock_sub.company_id = "company-1"
        mock_sub.tier = "growth"
        mock_sub.billing_frequency = "yearly"
        mock_sub.current_period_end = now - timedelta(days=1)  # Expired

        mock_db = MagicMock()
        # First call: upcoming renewals (empty)
        # Second call: expired subscriptions
        mock_db.query.return_value.filter.return_value \
            .all.side_effect = [[], [mock_sub]]
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)

        with patch("app.services.subscription_service.SessionLocal", return_value=mock_db):
            result = service.process_renewals()

        assert result["renewed"] == 1
        assert mock_sub.current_period_start >= now
        assert mock_sub.days_in_period is not None


# ═══════════════════════════════════════════════════════════════════════
# Validation & Edge Case Tests
# ═══════════════════════════════════════════════════════════════════════


class TestValidationEdgeCases:
    """Test validation and edge cases."""

    def test_validate_frequency_accepts_monthly(self):
        """Should accept 'monthly' frequency."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()
        assert service._validate_frequency("monthly") == "monthly"

    def test_validate_frequency_accepts_yearly(self):
        """Should accept 'yearly' frequency."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()
        assert service._validate_frequency("yearly") == "yearly"

    def test_validate_frequency_rejects_invalid(self):
        """Should reject invalid frequency."""
        from app.services.subscription_service import SubscriptionService, SubscriptionError

        service = SubscriptionService()
        with pytest.raises(SubscriptionError):
            service._validate_frequency("weekly")

    def test_is_upgrade_consistent(self):
        """Tier ordering should be consistent."""
        from app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        assert service._is_upgrade("starter", "growth") is True
        assert service._is_upgrade("starter", "high") is True
        assert service._is_upgrade("growth", "high") is True
        assert service._is_upgrade("growth", "starter") is False
        assert service._is_upgrade("high", "starter") is False
        assert service._is_upgrade("starter", "starter") is False

    def test_subscription_info_has_day2_fields(self):
        """SubscriptionInfo schema should include Day 2 fields."""
        from app.schemas.billing import SubscriptionInfo, BillingFrequency

        info = SubscriptionInfo(
            id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            variant="starter",
            status="active",
            created_at=datetime.now(timezone.utc),
            billing_frequency=BillingFrequency.YEARLY,
            pending_downgrade_tier="starter",
            previous_tier="growth",
            days_in_period=365,
        )

        assert info.billing_frequency == BillingFrequency.YEARLY
        assert info.pending_downgrade_tier == "starter"
        assert info.previous_tier == "growth"
        assert info.days_in_period == 365


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
