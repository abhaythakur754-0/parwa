"""
Unit Tests for Proration Service (W5D2)

Tests for:
- Proration calculation
- Billing period validation
- Edge cases (first day, last day)
- Audit trail creation
- Decimal precision

BC-002: All money calculations use Decimal
"""

import pytest
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4, UUID

from backend.app.services.proration_service import (
    ProrationService,
    ProrationError,
    InvalidProrationPeriodError,
    get_proration_service,
)
from backend.app.schemas.billing import (
    ProrationResult,
    VariantType,
    VARIANT_LIMITS,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def proration_service():
    """Create proration service instance."""
    return ProrationService()


@pytest.fixture
def sample_company_id():
    """Sample company UUID."""
    return uuid4()


@pytest.fixture
def standard_billing_period():
    """Standard 30-day billing period."""
    today = datetime.now(timezone.utc).date()
    start = today.replace(day=1)
    # Calculate next month
    if today.month == 12:
        end = date(today.year + 1, 1, 1)
    else:
        end = date(today.year, today.month + 1, 1)
    return start, end


# ── Proration Calculation Tests ───────────────────────────────────────────

class TestProrationCalculation:
    """Tests for proration calculation."""

    @pytest.mark.asyncio
    async def test_calculate_upgrade_starter_to_growth(
        self, proration_service, sample_company_id, standard_billing_period
    ):
        """Test calculating proration for starter to growth upgrade."""
        start, end = standard_billing_period

        result = await proration_service.calculate_upgrade_proration(
            company_id=sample_company_id,
            old_variant="starter",
            new_variant="growth",
            billing_cycle_start=start,
            billing_cycle_end=end,
        )

        assert result.old_variant == VariantType.STARTER
        assert result.new_variant == VariantType.GROWTH
        assert result.old_price == Decimal("999.00")
        assert result.new_price == Decimal("2499.00")
        assert result.net_charge > Decimal("0")  # Upgrade costs money

    @pytest.mark.asyncio
    async def test_calculate_upgrade_growth_to_high(
        self, proration_service, sample_company_id, standard_billing_period
    ):
        """Test calculating proration for growth to high upgrade."""
        start, end = standard_billing_period

        result = await proration_service.calculate_upgrade_proration(
            company_id=sample_company_id,
            old_variant="growth",
            new_variant="high",
            billing_cycle_start=start,
            billing_cycle_end=end,
        )

        assert result.old_variant == VariantType.GROWTH
        assert result.new_variant == VariantType.HIGH
        assert result.old_price == Decimal("2499.00")
        assert result.new_price == Decimal("3999.00")

    @pytest.mark.asyncio
    async def test_calculate_upgrade_starter_to_high(
        self, proration_service, sample_company_id, standard_billing_period
    ):
        """Test calculating proration for starter to high upgrade (skip tier)."""
        start, end = standard_billing_period

        result = await proration_service.calculate_upgrade_proration(
            company_id=sample_company_id,
            old_variant="starter",
            new_variant="high",
            billing_cycle_start=start,
            billing_cycle_end=end,
        )

        assert result.old_variant == VariantType.STARTER
        assert result.new_variant == VariantType.HIGH
        assert result.old_price == Decimal("999.00")
        assert result.new_price == Decimal("3999.00")

    @pytest.mark.asyncio
    async def test_calculate_proration_non_upgrade_fails(
        self, proration_service, sample_company_id, standard_billing_period
    ):
        """Test that calculating proration for downgrade raises error."""
        start, end = standard_billing_period

        with pytest.raises(ProrationError) as exc_info:
            await proration_service.calculate_upgrade_proration(
                company_id=sample_company_id,
                old_variant="growth",
                new_variant="starter",  # This is a downgrade
                billing_cycle_start=start,
                billing_cycle_end=end,
            )

        assert "non-upgrade" in str(exc_info.value)


# ── Billing Period Validation Tests ────────────────────────────────────────

class TestBillingPeriodValidation:
    """Tests for billing period validation."""

    @pytest.mark.asyncio
    async def test_invalid_period_end_before_start(
        self, proration_service, sample_company_id
    ):
        """Test that end date before start date raises error."""
        start = date(2024, 2, 1)
        end = date(2024, 1, 1)  # Before start

        with pytest.raises(InvalidProrationPeriodError):
            await proration_service.calculate_upgrade_proration(
                company_id=sample_company_id,
                old_variant="starter",
                new_variant="growth",
                billing_cycle_start=start,
                billing_cycle_end=end,
            )

    @pytest.mark.asyncio
    async def test_invalid_period_same_day(
        self, proration_service, sample_company_id
    ):
        """Test that same day start and end raises error."""
        same_day = date(2024, 1, 15)

        with pytest.raises(InvalidProrationPeriodError):
            await proration_service.calculate_upgrade_proration(
                company_id=sample_company_id,
                old_variant="starter",
                new_variant="growth",
                billing_cycle_start=same_day,
                billing_cycle_end=same_day,
            )

    @pytest.mark.asyncio
    async def test_unreasonable_period_too_long(
        self, proration_service, sample_company_id
    ):
        """Test that unreasonably long period raises error."""
        start = date(2024, 1, 1)
        end = date(2024, 12, 1)  # 11 months - too long

        with pytest.raises(InvalidProrationPeriodError) as exc_info:
            await proration_service.calculate_upgrade_proration(
                company_id=sample_company_id,
                old_variant="starter",
                new_variant="growth",
                billing_cycle_start=start,
                billing_cycle_end=end,
            )

        assert "Unusual billing period" in str(exc_info.value)

    def test_validate_billing_period_valid(
        self, proration_service, standard_billing_period
    ):
        """Test that valid billing period passes validation."""
        start, end = standard_billing_period
        # Should not raise
        proration_service._validate_billing_period(start, end)

    def test_validate_billing_period_invalid(
        self, proration_service
    ):
        """Test that invalid billing period fails validation."""
        with pytest.raises(InvalidProrationPeriodError):
            proration_service._validate_billing_period(
                date(2024, 2, 1),
                date(2024, 1, 1),  # End before start
            )


# ── Edge Case Tests ───────────────────────────────────────────────────────

class TestProrationEdgeCases:
    """Tests for edge cases in proration."""

    @pytest.mark.asyncio
    async def test_first_day_proration(
        self, proration_service
    ):
        """Test proration on first day of billing period."""
        start = date(2024, 1, 1)
        end = date(2024, 2, 1)

        result = await proration_service.calculate_first_day_proration(
            old_variant="starter",
            new_variant="growth",
            billing_cycle_start=start,
            billing_cycle_end=end,
        )

        # First day = full period remaining
        assert result.days_remaining == result.days_in_period
        # Full unused amount = old price
        assert result.unused_amount == Decimal("999.00")
        # Full new charge = new price
        assert result.new_charge == Decimal("2499.00")
        # Net charge = difference
        expected_net = Decimal("2499.00") - Decimal("999.00")
        assert result.net_charge == expected_net

    @pytest.mark.asyncio
    async def test_last_day_proration(
        self, proration_service
    ):
        """Test proration on last day of billing period."""
        start = date(2024, 1, 1)
        end = date(2024, 2, 1)

        result = await proration_service.calculate_last_day_proration(
            old_variant="starter",
            new_variant="growth",
            billing_cycle_start=start,
            billing_cycle_end=end,
        )

        # Last day = 0 days remaining
        assert result.days_remaining == 0
        # No unused amount
        assert result.unused_amount == Decimal("0.00")
        # No new charge
        assert result.new_charge == Decimal("0.00")
        # Net charge should be 0
        assert result.net_charge == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_mid_month_proration(
        self, proration_service, sample_company_id
    ):
        """Test mid-month proration calculation."""
        result = await proration_service.calculate_mid_month_proration(
            company_id=sample_company_id,
            old_variant="starter",
            new_variant="growth",
            days_into_period=15,  # Halfway through
        )

        assert "proration" in result
        assert result["days_elapsed"] == 15
        # Should have ~15 days remaining
        assert result["proration"].days_remaining == 15


# ── Estimate Tests ─────────────────────────────────────────────────────────

class TestUpgradeEstimate:
    """Tests for upgrade cost estimation."""

    @pytest.mark.asyncio
    async def test_estimate_upgrade_cost(
        self, proration_service
    ):
        """Test quick upgrade cost estimation."""
        estimate = await proration_service.estimate_upgrade_cost(
            old_variant="starter",
            new_variant="growth",
            days_remaining=15,
            days_in_period=30,
        )

        assert "old_price" in estimate
        assert "new_price" in estimate
        assert "unused_credit" in estimate
        assert "new_charge" in estimate
        assert "net_cost" in estimate
        assert "per_day_difference" in estimate

        # Verify values
        assert estimate["old_price"] == Decimal("999.00")
        assert estimate["new_price"] == Decimal("2499.00")

    @pytest.mark.asyncio
    async def test_estimate_upgrade_half_period(
        self, proration_service
    ):
        """Test upgrade estimate for half period remaining."""
        estimate = await proration_service.estimate_upgrade_cost(
            old_variant="starter",
            new_variant="growth",
            days_remaining=15,
            days_in_period=30,
        )

        # Half period = half price difference
        old_daily = Decimal("999.00") / 30
        new_daily = Decimal("2499.00") / 30
        expected_net = (new_daily - old_daily) * 15

        assert estimate["net_cost"] == expected_net.quantize(Decimal("0.01"))


# ── Audit Trail Tests ──────────────────────────────────────────────────────

class TestProrationAudit:
    """Tests for proration audit trail."""

    @pytest.mark.asyncio
    async def test_apply_proration_creates_audit(
        self, proration_service, sample_company_id, standard_billing_period
    ):
        """Test that applying proration creates audit record."""
        start, end = standard_billing_period

        # Calculate proration first
        result = await proration_service.calculate_upgrade_proration(
            company_id=sample_company_id,
            old_variant="starter",
            new_variant="growth",
            billing_cycle_start=start,
            billing_cycle_end=end,
        )

        # Mock database session
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_audit = MagicMock()
        mock_audit.id = str(uuid4())

        # Mock ProrationAudit to avoid SQLAlchemy relationship issues
        with patch(
            "backend.app.services.proration_service.SessionLocal",
            return_value=mock_session
        ), patch(
            "backend.app.services.proration_service.ProrationAudit"
        ) as MockProrationAudit:
            MockProrationAudit.return_value = mock_audit

            mock_session.add = MagicMock()
            mock_session.commit = MagicMock()
            mock_session.refresh = MagicMock()

            audit = await proration_service.apply_proration_credit(
                company_id=sample_company_id,
                proration_result=result,
            )

            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()


# ── Decimal Precision Tests ───────────────────────────────────────────────

class TestDecimalPrecision:
    """Tests for Decimal precision (BC-002)."""

    @pytest.mark.asyncio
    async def test_all_amounts_are_decimal(
        self, proration_service, sample_company_id, standard_billing_period
    ):
        """Test that all monetary values are Decimal."""
        start, end = standard_billing_period

        result = await proration_service.calculate_upgrade_proration(
            company_id=sample_company_id,
            old_variant="starter",
            new_variant="growth",
            billing_cycle_start=start,
            billing_cycle_end=end,
        )

        assert isinstance(result.old_price, Decimal)
        assert isinstance(result.new_price, Decimal)
        assert isinstance(result.unused_amount, Decimal)
        assert isinstance(result.proration_credit, Decimal)
        assert isinstance(result.new_charge, Decimal)
        assert isinstance(result.net_charge, Decimal)

    @pytest.mark.asyncio
    async def test_precision_two_decimal_places(
        self, proration_service, sample_company_id, standard_billing_period
    ):
        """Test that amounts have exactly 2 decimal places."""
        start, end = standard_billing_period

        result = await proration_service.calculate_upgrade_proration(
            company_id=sample_company_id,
            old_variant="starter",
            new_variant="growth",
            billing_cycle_start=start,
            billing_cycle_end=end,
        )

        for field in [
            result.unused_amount,
            result.proration_credit,
            result.new_charge,
            result.net_charge,
        ]:
            str_value = str(field)
            if "." in str_value:
                decimals = len(str_value.split(".")[1])
                assert decimals <= 2, f"Value {field} has more than 2 decimal places"

    def test_round_method(
        self, proration_service
    ):
        """Test the round method produces correct precision."""
        # Test with various inputs
        assert proration_service._round(Decimal("123.456")) == Decimal("123.46")
        assert proration_service._round(Decimal("123.454")) == Decimal("123.45")
        assert proration_service._round(Decimal("123.455")) == Decimal("123.46")  # Round half up


# ── Variant Validation Tests ───────────────────────────────────────────────

class TestVariantValidation:
    """Tests for variant validation."""

    def test_validate_variant_lowercase(self, proration_service):
        """Test that variant is lowercased."""
        assert proration_service._validate_variant("STARTER") == "starter"
        assert proration_service._validate_variant("Growth") == "growth"
        assert proration_service._validate_variant("HIGH") == "high"

    def test_validate_variant_stripped(self, proration_service):
        """Test that variant is stripped of whitespace."""
        assert proration_service._validate_variant("  starter  ") == "starter"

    def test_validate_variant_invalid(self, proration_service):
        """Test that invalid variant raises error."""
        with pytest.raises(ProrationError):
            proration_service._validate_variant("enterprise")

        with pytest.raises(ProrationError):
            proration_service._validate_variant("free")


# ── Upgrade Detection Tests ────────────────────────────────────────────────

class TestUpgradeDetection:
    """Tests for upgrade detection logic."""

    def test_is_upgrade_true(self, proration_service):
        """Test cases where it IS an upgrade."""
        assert proration_service._is_upgrade("starter", "growth") is True
        assert proration_service._is_upgrade("starter", "high") is True
        assert proration_service._is_upgrade("growth", "high") is True

    def test_is_upgrade_false(self, proration_service):
        """Test cases where it is NOT an upgrade."""
        assert proration_service._is_upgrade("growth", "starter") is False
        assert proration_service._is_upgrade("high", "growth") is False
        assert proration_service._is_upgrade("high", "starter") is False
        assert proration_service._is_upgrade("starter", "starter") is False


# ── Downgrade Date Tests ───────────────────────────────────────────────────

class TestDowngradeDate:
    """Tests for downgrade effective date calculation."""

    @pytest.mark.asyncio
    async def test_downgrade_effective_date(
        self, proration_service
    ):
        """Test that downgrade is effective at billing cycle end."""
        billing_end = date(2024, 2, 15)

        effective = await proration_service.calculate_downgrade_effective_date(
            billing_cycle_end=billing_end
        )

        assert effective == billing_end


# ── Singleton Tests ────────────────────────────────────────────────────────

class TestProrationSingleton:
    """Tests for proration service singleton."""

    def test_get_proration_service_singleton(self):
        """Test that get_proration_service returns singleton."""
        service1 = get_proration_service()
        service2 = get_proration_service()

        assert service1 is service2


# ── Gap Fix Tests ──────────────────────────────────────────────────────────

class TestGapFixesProration:
    """Gap-fix tests for proration service private helpers.

    Each test is self-contained with its own ProrationService instance
    and tests synchronous helper methods directly (no DB, no async).
    """

    def test_validate_variant_invalid_name(self):
        """_validate_variant('enterprise') should raise ProrationError."""
        svc = ProrationService()
        with pytest.raises(ProrationError):
            svc._validate_variant("enterprise")

    def test_validate_variant_empty_string(self):
        """_validate_variant('') should raise ProrationError."""
        svc = ProrationService()
        with pytest.raises(ProrationError):
            svc._validate_variant("")

    def test_validate_variant_whitespace(self):
        """_validate_variant('  growth  ') should succeed and return 'growth'."""
        svc = ProrationService()
        result = svc._validate_variant("  growth  ")
        assert result == "growth"

    def test_is_upgrade_same_variant(self):
        """_is_upgrade with identical variants should return False."""
        svc = ProrationService()
        assert svc._is_upgrade("starter", "starter") is False

    def test_is_upgrade_downgrade(self):
        """_is_upgrade for a downgrade (growth -> starter) should return False."""
        svc = ProrationService()
        assert svc._is_upgrade("growth", "starter") is False

    def test_round_precision(self):
        """_round should correctly round to 2 decimal places with ROUND_HALF_UP."""
        svc = ProrationService()
        result = svc._round(Decimal("1.005"))
        assert result == Decimal("1.01")

    def test_validate_billing_period_equal_dates(self):
        """_validate_billing_period with equal start and end should raise InvalidProrationPeriodError."""
        svc = ProrationService()
        with pytest.raises(InvalidProrationPeriodError):
            svc._validate_billing_period(date(2024, 1, 1), date(2024, 1, 1))

    def test_validate_billing_period_too_long(self):
        """_validate_billing_period with period > 60 days should raise InvalidProrationPeriodError."""
        svc = ProrationService()
        # 61-day period
        with pytest.raises(InvalidProrationPeriodError):
            svc._validate_billing_period(date(2024, 1, 1), date(2024, 3, 2))

    def test_validate_billing_period_exactly_60_days(self):
        """_validate_billing_period with exactly 60 days should be accepted (boundary)."""
        svc = ProrationService()
        # 60-day period — must not raise
        svc._validate_billing_period(date(2024, 1, 1), date(2024, 3, 1))
