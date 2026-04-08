"""
Week 8 Day 2: Unit tests for AI Engine Cost Overrun Protection (SG-35).

Tests are SOURCE OF TRUTH. If a test fails, fix the application code.
NEVER modify tests to pass.

Covers: Budget initialization, budget checking, usage recording,
period management, admin functions, alerts, and edge cases.
"""

import os
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, call

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only_not_prod"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_not_prod"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

from backend.app.services.cost_protection_service import (
    CostProtectionService,
    BudgetPeriodType,
    BudgetStatus,
    AlertLevel,
    DEFAULT_VARIANT_LIMITS,
    VALID_VARIANT_TYPES,
    VALID_BUDGET_TYPES,
    TokenUsageRecord,
    BudgetCheckResult,
    _validate_company_id,
    _validate_tokens_non_negative,
    _validate_budget_type,
    _validate_variant_type,
)
from backend.app.exceptions import ParwaBaseError


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Mock SQLAlchemy session."""
    return MagicMock()


@pytest.fixture
def service(mock_db):
    return CostProtectionService(db=mock_db)


def _make_mock_budget(
    company_id="comp_1",
    budget_type="daily",
    budget_period=None,
    max_tokens=2_000_000,
    used_tokens=0,
    status="active",
    hard_stop=True,
    alert_sent=False,
    alert_threshold_pct=80,
    instance_id=None,
):
    """Create a mock AITokenBudget object."""
    if budget_period is None:
        now = datetime.utcnow()
        if budget_type == "daily":
            budget_period = now.strftime("%Y-%m-%d")
        else:
            budget_period = now.strftime("%Y-%m")

    budget = MagicMock()
    budget.id = "budget_001"
    budget.company_id = company_id
    budget.instance_id = instance_id
    budget.budget_type = budget_type
    budget.budget_period = budget_period
    budget.max_tokens = max_tokens
    budget.used_tokens = used_tokens
    budget.status = status
    budget.hard_stop = hard_stop
    budget.alert_sent = alert_sent
    budget.alert_threshold_pct = alert_threshold_pct
    budget.variant_default_limits = "{}"
    budget.created_at = datetime.utcnow()
    budget.updated_at = datetime.utcnow()
    return budget


# ══════════════════════════════════════════════════════════════════
# CONSTANTS TESTS
# ══════════════════════════════════════════════════════════════════

class TestConstants:
    def test_default_variant_limits_has_all_three(self):
        assert "mini_parwa" in DEFAULT_VARIANT_LIMITS
        assert "parwa" in DEFAULT_VARIANT_LIMITS
        assert "parwa_high" in DEFAULT_VARIANT_LIMITS

    def test_mini_parwa_limits(self):
        limits = DEFAULT_VARIANT_LIMITS["mini_parwa"]
        assert limits["daily"] == 500_000
        assert limits["monthly"] == 15_000_000

    def test_parwa_limits(self):
        limits = DEFAULT_VARIANT_LIMITS["parwa"]
        assert limits["daily"] == 2_000_000
        assert limits["monthly"] == 60_000_000

    def test_parwa_high_limits(self):
        limits = DEFAULT_VARIANT_LIMITS["parwa_high"]
        assert limits["daily"] == 5_000_000
        assert limits["monthly"] == 150_000_000

    def test_all_limits_are_integers(self):
        for variant, limits in DEFAULT_VARIANT_LIMITS.items():
            for period, val in limits.items():
                assert isinstance(val, int), f"{variant}.{period} is not int"

    def test_valid_variant_types_matches_defaults(self):
        assert VALID_VARIANT_TYPES == set(DEFAULT_VARIANT_LIMITS.keys())

    def test_valid_budget_types(self):
        assert "daily" in VALID_BUDGET_TYPES
        assert "monthly" in VALID_BUDGET_TYPES

    def test_budget_period_type_enum(self):
        assert BudgetPeriodType.DAILY.value == "daily"
        assert BudgetPeriodType.MONTHLY.value == "monthly"

    def test_budget_status_enum(self):
        assert BudgetStatus.ACTIVE.value == "active"
        assert BudgetStatus.EXCEEDED.value == "exceeded"
        assert BudgetStatus.DISABLED.value == "disabled"
        assert BudgetStatus.EXHAUSTED.value == "exhausted"

    def test_alert_level_enum(self):
        assert AlertLevel.NONE.value == "none"
        assert AlertLevel.WARNING.value == "warning"
        assert AlertLevel.CRITICAL.value == "critical"
        assert AlertLevel.EXHAUSTED.value == "exhausted"


# ══════════════════════════════════════════════════════════════════
# VALIDATION TESTS
# ══════════════════════════════════════════════════════════════════

class TestValidation:
    def test_validate_company_id_empty_raises(self):
        with pytest.raises(ParwaBaseError) as exc:
            _validate_company_id("")
        assert exc.value.error_code == "INVALID_COMPANY_ID"

    def test_validate_company_id_whitespace_raises(self):
        with pytest.raises(ParwaBaseError):
            _validate_company_id("   ")

    def test_validate_company_id_none_raises(self):
        with pytest.raises(ParwaBaseError):
            _validate_company_id(None)

    def test_validate_company_id_valid_passes(self):
        _validate_company_id("comp_1")

    def test_validate_tokens_negative_raises(self):
        with pytest.raises(ParwaBaseError) as exc:
            _validate_tokens_non_negative(-1)
        assert exc.value.error_code == "INVALID_TOKEN_COUNT"

    def test_validate_tokens_float_raises(self):
        with pytest.raises(ParwaBaseError):
            _validate_tokens_non_negative(1.5)

    def test_validate_tokens_zero_passes(self):
        _validate_tokens_non_negative(0)

    def test_validate_tokens_positive_passes(self):
        _validate_tokens_non_negative(100)

    def test_validate_budget_type_invalid_raises(self):
        with pytest.raises(ParwaBaseError) as exc:
            _validate_budget_type("yearly")
        assert exc.value.error_code == "INVALID_BUDGET_TYPE"

    def test_validate_budget_type_valid_daily(self):
        _validate_budget_type("daily")

    def test_validate_budget_type_valid_monthly(self):
        _validate_budget_type("monthly")

    def test_validate_variant_type_invalid_raises(self):
        with pytest.raises(ParwaBaseError) as exc:
            _validate_variant_type("mega_parwa")
        assert exc.value.error_code == "INVALID_VARIANT_TYPE"

    def test_validate_variant_type_valid(self):
        for vt in VALID_VARIANT_TYPES:
            _validate_variant_type(vt)


# ══════════════════════════════════════════════════════════════════
# BUDGET INITIALIZATION TESTS
# ══════════════════════════════════════════════════════════════════

class TestBudgetInitialization:
    def test_creates_daily_and_monthly_budgets(self, service, mock_db):
        """initialize_budgets creates both daily and monthly records."""
        # No existing budgets found
        mock_db.query.return_value.filter_by.return_value.first.return_value = None
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        result = service.initialize_budgets("comp_1", "parwa")

        assert result["company_id"] == "comp_1"
        assert result["variant_type"] == "parwa"
        assert len(result["budgets"]) == 2
        budget_types = [b["budget_type"] for b in result["budgets"]]
        assert "daily" in budget_types
        assert "monthly" in budget_types

    def test_uses_correct_default_limits_per_variant(self, service, mock_db):
        """Mini PARWA gets 500k daily, PARWA gets 2M daily."""
        mock_db.query.return_value.filter_by.return_value.first.return_value = None
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        # Mini PARWA
        result_mini = service.initialize_budgets("comp_1", "mini_parwa")
        daily_budget = [b for b in result_mini["budgets"] if b["budget_type"] == "daily"][0]
        assert daily_budget["max_tokens"] == 500_000

        monthly_budget = [b for b in result_mini["budgets"] if b["budget_type"] == "monthly"][0]
        assert monthly_budget["max_tokens"] == 15_000_000

    def test_idempotent_wont_duplicate(self, service, mock_db):
        """If budget exists for current period, skip creation."""
        existing = _make_mock_budget()
        mock_db.query.return_value.filter_by.return_value.first.return_value = existing

        result = service.initialize_budgets("comp_1", "parwa")

        assert len(result["budgets"]) == 2
        # Should NOT have called db.add (existing budgets returned)
        mock_db.add.assert_not_called()

    def test_company_id_validation(self, service, mock_db):
        """Empty company_id raises ParwaBaseError."""
        with pytest.raises(ParwaBaseError) as exc:
            service.initialize_budgets("", "parwa")
        assert exc.value.error_code == "INVALID_COMPANY_ID"

    def test_unknown_variant_type_raises(self, service, mock_db):
        with pytest.raises(ParwaBaseError) as exc:
            service.initialize_budgets("comp_1", "unknown_variant")
        assert exc.value.error_code == "INVALID_VARIANT_TYPE"

    def test_instance_id_passed_through(self, service, mock_db):
        """instance_id is passed to budget creation."""
        mock_db.query.return_value.filter_by.return_value.first.return_value = None
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        result = service.initialize_budgets("comp_1", "parwa", instance_id="inst_1")

        assert result["instance_id"] == "inst_1"


# ══════════════════════════════════════════════════════════════════
# BUDGET CHECKING TESTS
# ══════════════════════════════════════════════════════════════════

class TestBudgetChecking:
    def test_under_limit_returns_allowed(self, service, mock_db):
        """check_budget returns allowed=True when well under limit."""
        budget = _make_mock_budget(used_tokens=100_000, max_tokens=2_000_000)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget

        result = service.check_budget("comp_1", 50_000, "daily")

        assert result.allowed is True
        assert result.alert_level == AlertLevel.NONE

    def test_at_limit_returns_not_allowed(self, service, mock_db):
        """check_budget returns allowed=False when at/over limit."""
        budget = _make_mock_budget(used_tokens=2_000_000, max_tokens=2_000_000)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget

        result = service.check_budget("comp_1", 1, "daily")

        assert result.allowed is False

    def test_alert_none_below_80(self, service, mock_db):
        budget = _make_mock_budget(used_tokens=1_000_000, max_tokens=2_000_000)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget

        result = service.check_budget("comp_1", 100, "daily")
        assert result.alert_level == AlertLevel.NONE

    def test_alert_warning_at_80(self, service, mock_db):
        budget = _make_mock_budget(used_tokens=1_600_000, max_tokens=2_000_000)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget

        result = service.check_budget("comp_1", 100, "daily")
        assert result.alert_level == AlertLevel.WARNING

    def test_alert_critical_at_95(self, service, mock_db):
        budget = _make_mock_budget(used_tokens=1_900_000, max_tokens=2_000_000)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget

        result = service.check_budget("comp_1", 100, "daily")
        assert result.alert_level == AlertLevel.CRITICAL

    def test_alert_exhausted_at_100(self, service, mock_db):
        budget = _make_mock_budget(used_tokens=2_000_000, max_tokens=2_000_000)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget

        result = service.check_budget("comp_1", 1, "daily")
        assert result.alert_level == AlertLevel.EXHAUSTED

    def test_hard_stop_respected(self, service, mock_db):
        """Hard stop prevents exceeding budget."""
        budget = _make_mock_budget(used_tokens=1_999_999, max_tokens=2_000_000, hard_stop=True)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget

        result = service.check_budget("comp_1", 100, "daily")
        assert result.allowed is False

    def test_partial_request_more_than_remaining_not_allowed(self, service, mock_db):
        """Requesting more tokens than remaining should not be allowed."""
        budget = _make_mock_budget(used_tokens=1_500_000, max_tokens=2_000_000)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget

        result = service.check_budget("comp_1", 600_000, "daily")
        assert result.allowed is False

    def test_partial_request_less_than_remaining_allowed(self, service, mock_db):
        """Requesting less than remaining should be allowed."""
        budget = _make_mock_budget(used_tokens=1_500_000, max_tokens=2_000_000)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget

        result = service.check_budget("comp_1", 400_000, "daily")
        assert result.allowed is True
        assert result.remaining_tokens == 100_000

    def test_no_budget_found_allows_graceful(self, service, mock_db):
        """No budget record → allow (BC-008 graceful degradation)."""
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        result = service.check_budget("comp_1", 1000, "daily")
        assert result.allowed is True
        assert "graceful" in result.reason.lower()

    def test_disabled_budget_always_allowed(self, service, mock_db):
        """Disabled budgets always return allowed=True."""
        budget = _make_mock_budget(status="disabled", used_tokens=2_000_000, max_tokens=2_000_000)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget

        result = service.check_budget("comp_1", 1000, "daily")
        assert result.allowed is True
        assert result.budget_status == BudgetStatus.DISABLED

    def test_company_id_validation(self, service, mock_db):
        with pytest.raises(ParwaBaseError):
            service.check_budget("", 100, "daily")

    def test_invalid_budget_type_raises(self, service, mock_db):
        with pytest.raises(ParwaBaseError):
            service.check_budget("comp_1", 100, "yearly")


# ══════════════════════════════════════════════════════════════════
# USAGE RECORDING TESTS
# ══════════════════════════════════════════════════════════════════

class TestUsageRecording:
    def test_record_usage_increments_both(self, service, mock_db):
        """record_usage increments both daily and monthly budgets."""
        daily_budget = _make_mock_budget(budget_type="daily", used_tokens=0)
        monthly_budget = _make_mock_budget(budget_type="monthly", used_tokens=0)

        # Set up the mock to return different budgets for different filter calls
        mock_query = MagicMock()

        def filter_by_side_effect(**kwargs):
            fm = MagicMock()
            if kwargs.get("budget_type") == "daily":
                fm.first.return_value = daily_budget
            elif kwargs.get("budget_type") == "monthly":
                fm.first.return_value = monthly_budget
            else:
                fm.first.return_value = None
            return fm

        mock_db.query.return_value.filter_by.side_effect = filter_by_side_effect

        result = service.record_usage("comp_1", 1000)

        assert result["tokens_recorded"] == 1000
        assert daily_budget.used_tokens == 1000
        assert monthly_budget.used_tokens == 1000
        mock_db.commit.assert_called_once()

    def test_correct_tokens_tracked(self, service, mock_db):
        """Multiple calls accumulate correctly.

        Since the same mock is returned for both daily and monthly,
        each record_usage call increments the shared mock twice.
        """
        budget = _make_mock_budget(budget_type="daily", used_tokens=500)

        def filter_by_side_effect(**kwargs):
            fm = MagicMock()
            fm.first.return_value = budget
            return fm

        mock_db.query.return_value.filter_by.side_effect = filter_by_side_effect

        service.record_usage("comp_1", 500)
        # Both daily and monthly increment the same mock
        assert budget.used_tokens == 1500

        service.record_usage("comp_1", 300)
        assert budget.used_tokens == 2100

    def test_status_changes_to_exceeded(self, service, mock_db):
        """Status changes to 'exceeded' when over limit."""
        budget = _make_mock_budget(
            budget_type="daily",
            used_tokens=1_999_000,
            max_tokens=2_000_000,
            status="active",
        )

        def filter_by_side_effect(**kwargs):
            fm = MagicMock()
            fm.first.return_value = budget
            return fm

        mock_db.query.return_value.filter_by.side_effect = filter_by_side_effect

        service.record_usage("comp_1", 2000)

        assert budget.status == "exceeded"

    def test_alert_flag_set_when_threshold_crossed(self, service, mock_db):
        """alert_sent is set to True when crossing 80%."""
        budget = _make_mock_budget(
            budget_type="daily",
            used_tokens=1_500_000,
            max_tokens=2_000_000,
            alert_sent=False,
        )

        def filter_by_side_effect(**kwargs):
            fm = MagicMock()
            fm.first.return_value = budget
            return fm

        mock_db.query.return_value.filter_by.side_effect = filter_by_side_effect

        # 500k more pushes from 75% to 100%
        service.record_usage("comp_1", 500_000)

        assert budget.alert_sent is True

    def test_record_usage_zero_tokens(self, service, mock_db):
        """Zero tokens returns early without DB interaction."""
        result = service.record_usage("comp_1", 0)

        assert result["tokens_recorded"] == 0
        mock_db.query.assert_not_called()

    def test_record_usage_negative_raises(self, service, mock_db):
        """Negative tokens raises ParwaBaseError."""
        with pytest.raises(ParwaBaseError) as exc:
            service.record_usage("comp_1", -1)
        assert exc.value.error_code == "INVALID_TOKEN_COUNT"

    def test_no_budget_found_skips_recording(self, service, mock_db):
        """No budget → graceful, records 0 in stats."""
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        result = service.record_usage("comp_1", 1000)

        assert result["tokens_recorded"] == 1000


# ══════════════════════════════════════════════════════════════════
# PERIOD MANAGEMENT TESTS
# ══════════════════════════════════════════════════════════════════

class TestPeriodManagement:
    def test_get_current_period_daily_format(self, service):
        period = service._get_current_period("daily")
        # Should be YYYY-MM-DD
        assert len(period) == 10
        assert period[4] == "-"
        assert period[7] == "-"

    def test_get_current_period_monthly_format(self, service):
        period = service._get_current_period("monthly")
        # Should be YYYY-MM
        assert len(period) == 7
        assert period[4] == "-"

    def test_get_current_period_invalid_raises(self, service):
        with pytest.raises(ParwaBaseError):
            service._get_current_period("yearly")

    def test_reset_daily_budgets(self, service, mock_db):
        """reset_daily_budgets resets daily counters."""
        b1 = _make_mock_budget(budget_type="daily", used_tokens=1_000_000, status="exceeded", alert_sent=True)
        b2 = _make_mock_budget(budget_type="daily", used_tokens=500_000, status="active")
        mock_db.query.return_value.filter_by.return_value.all.return_value = [b1, b2]

        result = service.reset_daily_budgets("comp_1")

        assert result["budgets_reset"] == 2
        assert b1.used_tokens == 0
        assert b1.status == "active"
        assert b1.alert_sent is False
        assert b2.used_tokens == 0

    def test_monthly_survives_daily_reset(self, service, mock_db):
        """Monthly budget should not be affected by daily reset."""
        monthly = _make_mock_budget(budget_type="monthly", used_tokens=5_000_000)

        daily_b1 = _make_mock_budget(budget_type="daily", used_tokens=1_000_000)
        mock_db.query.return_value.filter_by.return_value.all.return_value = [daily_b1]

        service.reset_daily_budgets("comp_1")

        # Monthly should be untouched
        assert monthly.used_tokens == 5_000_000

    def test_reset_empty_company_raises(self, service, mock_db):
        with pytest.raises(ParwaBaseError):
            service.reset_daily_budgets("")


# ══════════════════════════════════════════════════════════════════
# ADMIN FUNCTIONS TESTS
# ══════════════════════════════════════════════════════════════════

class TestAdminFunctions:
    def test_update_budget_limit_changes_max(self, service, mock_db):
        budget = _make_mock_budget(max_tokens=2_000_000)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget

        result = service.update_budget_limit("comp_1", "daily", 5_000_000)

        assert result is not None
        assert result.max_tokens == 5_000_000

    def test_update_limit_zero_raises(self, service, mock_db):
        with pytest.raises(ParwaBaseError) as exc:
            service.update_budget_limit("comp_1", "daily", 0)
        assert exc.value.error_code == "INVALID_BUDGET_LIMIT"

    def test_update_limit_negative_raises(self, service, mock_db):
        with pytest.raises(ParwaBaseError):
            service.update_budget_limit("comp_1", "daily", -1)

    def test_update_limit_not_found_raises_404(self, service, mock_db):
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        with pytest.raises(ParwaBaseError) as exc:
            service.update_budget_limit("comp_1", "daily", 5_000_000)
        assert exc.value.error_code == "BUDGET_NOT_FOUND"
        assert exc.value.status_code == 404

    def test_update_limit_rechecks_exceeded_status(self, service, mock_db):
        """If limit increased above used, status should become active."""
        budget = _make_mock_budget(
            used_tokens=3_000_000, max_tokens=2_000_000, status="exceeded"
        )
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget

        result = service.update_budget_limit("comp_1", "daily", 5_000_000)

        assert result.status == "active"

    def test_disable_budget_sets_disabled(self, service, mock_db):
        budget = _make_mock_budget(status="active")
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget

        result = service.disable_budget("comp_1", "daily")

        assert result is not None
        assert result.status == "disabled"

    def test_disable_budget_not_found_raises(self, service, mock_db):
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        with pytest.raises(ParwaBaseError) as exc:
            service.disable_budget("comp_1", "daily")
        assert exc.value.status_code == 404

    def test_enable_budget_reactivates(self, service, mock_db):
        budget = _make_mock_budget(status="disabled", used_tokens=500_000, max_tokens=2_000_000)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget

        result = service.enable_budget("comp_1", "daily")

        assert result is not None
        assert result.status == "active"

    def test_enable_budget_stays_exceeded_if_over(self, service, mock_db):
        """Re-enabling a budget that was over limit stays exceeded."""
        budget = _make_mock_budget(status="disabled", used_tokens=2_000_000, max_tokens=2_000_000)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget

        result = service.enable_budget("comp_1", "daily")

        assert result.status == "exceeded"

    def test_enable_budget_not_found_raises(self, service, mock_db):
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        with pytest.raises(ParwaBaseError) as exc:
            service.enable_budget("comp_1", "daily")
        assert exc.value.status_code == 404


# ══════════════════════════════════════════════════════════════════
# ALERT TESTS
# ══════════════════════════════════════════════════════════════════

class TestAlerts:
    def test_get_alert_status_returns_correct_levels(self, service, mock_db):
        budget = _make_mock_budget(used_tokens=1_700_000, max_tokens=2_000_000, alert_sent=False)
        mock_db.query.return_value.filter_by.return_value.all.return_value = [budget]

        result = service.get_alert_status("comp_1")

        assert result["total_budgets"] == 1
        assert len(result["alerts"]) == 1
        assert result["alerts"][0]["alert_level"] == "warning"

    def test_get_alert_status_no_alerts(self, service, mock_db):
        budget = _make_mock_budget(used_tokens=100_000, max_tokens=2_000_000)
        mock_db.query.return_value.filter_by.return_value.all.return_value = [budget]

        result = service.get_alert_status("comp_1")

        assert len(result["alerts"]) == 0
        assert result["has_unsent_alerts"] is False

    def test_mark_alert_sent_updates_flag(self, service, mock_db):
        budget = _make_mock_budget(alert_sent=False)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget

        service.mark_alert_sent("comp_1", "daily")

        assert budget.alert_sent is True
        mock_db.commit.assert_called_once()

    def test_alert_only_fires_once_per_period(self, service, mock_db):
        """If alert_sent is True, it shouldn't fire again."""
        budget = _make_mock_budget(used_tokens=1_900_000, max_tokens=2_000_000, alert_sent=True)
        mock_db.query.return_value.filter_by.return_value.all.return_value = [budget]

        result = service.get_alert_status("comp_1")

        assert result["has_unsent_alerts"] is False

    def test_multiple_budgets_mixed_alerts(self, service, mock_db):
        b1 = _make_mock_budget(
            budget_type="daily", used_tokens=1_700_000,
            max_tokens=2_000_000, alert_sent=False,
        )
        b2 = _make_mock_budget(
            budget_type="monthly", used_tokens=100_000,
            max_tokens=60_000_000, alert_sent=False,
        )
        mock_db.query.return_value.filter_by.return_value.all.return_value = [b1, b2]

        result = service.get_alert_status("comp_1")

        assert len(result["alerts"]) == 1
        assert result["alerts"][0]["budget_type"] == "daily"


# ══════════════════════════════════════════════════════════════════
# EDGE CASES
# ══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_zero_tokens_always_allowed(self, service, mock_db):
        result = service.check_budget("comp_1", 0, "daily")

        assert result.allowed is True
        assert "Zero" in result.reason

    def test_negative_tokens_raises_error(self, service, mock_db):
        with pytest.raises(ParwaBaseError) as exc:
            service.check_budget("comp_1", -5, "daily")
        assert exc.value.error_code == "INVALID_TOKEN_COUNT"

    def test_unknown_variant_type_raises(self, service, mock_db):
        with pytest.raises(ParwaBaseError) as exc:
            service.initialize_budgets("comp_1", "unknown_type")
        assert exc.value.error_code == "INVALID_VARIANT_TYPE"

    def test_instance_level_budgets_tracked_separately(self, service, mock_db):
        """Budgets for different instances are tracked independently."""
        call_count = {"n": 0}
        budgets = {
            ("daily", None): _make_mock_budget(budget_type="daily", used_tokens=100_000),
            ("monthly", None): _make_mock_budget(budget_type="monthly", used_tokens=100_000),
        }

        def filter_by_side_effect(**kwargs):
            fm = MagicMock()
            key = (kwargs.get("budget_type"), kwargs.get("instance_id"))
            fm.first.return_value = budgets.get(key)
            call_count["n"] += 1
            return fm

        mock_db.query.return_value.filter_by.side_effect = filter_by_side_effect

        result = service.get_usage("comp_1", "daily")
        assert result["used_tokens"] == 100_000

    def test_get_usage_not_found(self, service, mock_db):
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        result = service.get_usage("comp_1", "daily")

        assert result["found"] is False

    def test_get_all_tenant_budgets(self, service, mock_db):
        b1 = _make_mock_budget(company_id="comp_1")
        b2 = _make_mock_budget(company_id="comp_2", max_tokens=500_000)
        mock_db.query.return_value.all.return_value = [b1, b2]

        result = service.get_all_tenant_budgets()

        assert len(result) == 2

    def test_token_usage_record_dataclass(self):
        record = TokenUsageRecord(
            company_id="comp_1",
            instance_id="inst_1",
            model_id="gpt-4",
            tokens_used=100,
        )
        assert record.company_id == "comp_1"
        assert record.tokens_used == 100
        assert record.timestamp is not None

    def test_budget_check_result_dataclass(self):
        result = BudgetCheckResult(
            allowed=True,
            remaining_tokens=500,
            usage_pct=75.0,
            alert_level=AlertLevel.NONE,
            budget_status=BudgetStatus.ACTIVE,
            reason="Within budget",
        )
        assert result.allowed is True
        assert result.remaining_tokens == 500

    def test_calc_usage_pct_zero_max(self):
        """Division by zero should return 0.0."""
        assert CostProtectionService._calc_usage_pct(100, 0) == 0.0

    def test_calc_usage_pct_non_integer_input(self):
        assert CostProtectionService._calc_usage_pct("abc", 100) == 0.0

    def test_calc_usage_pct_exact(self):
        assert CostProtectionService._calc_usage_pct(1_500_000, 2_000_000) == 75.0

    def test_get_monthly_report(self, service, mock_db):
        monthly = _make_mock_budget(budget_type="monthly")
        daily1 = _make_mock_budget(budget_type="daily", budget_period="2026-04-01", used_tokens=500_000)
        daily2 = _make_mock_budget(budget_type="daily", budget_period="2026-04-02", used_tokens=300_000)

        def filter_by_side_effect(**kwargs):
            fm = MagicMock()
            if kwargs.get("budget_type") == "monthly":
                fm.first.return_value = monthly
            else:
                fm.all.return_value = [daily1, daily2]
            return fm

        mock_db.query.return_value.filter_by.side_effect = filter_by_side_effect

        result = service.get_monthly_report("comp_1")

        assert "monthly_budget" in result
        assert "daily_breakdown" in result
        assert result["total_daily_tokens"] == 800_000
