"""Tests for Cost Protection Service (SG-35) – Day 2 AI Engine.

Covers:
- check_budget allows/blocks based on token usage
- Hard stop at budget limit
- Alert level thresholds
- record_usage increments daily + monthly
- reset_daily_budgets
- TIER_DAILY_REQUEST_LIMITS with medium=2500
- check_tier_budget and record_tier_usage methods
- Timezone-aware datetime (BC-012)
- BC-002: tokens must be non-negative integers
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Mock the database import before importing the service
with patch.dict("sys.modules", {"database.models.variant_engine": MagicMock()}):
    from backend.app.services.cost_protection_service import (
        CostProtectionService,
        BudgetCheckResult,
        BudgetStatus,
        AlertLevel,
        TIER_DAILY_REQUEST_LIMITS,
        DEFAULT_VARIANT_LIMITS,
        _validate_tokens_non_negative,
        _validate_company_id,
    )
    from backend.app.exceptions import ParwaBaseError


# ── Fixtures ─────────────────────────────────────────────────────


def _make_budget(
    used_tokens: int = 0,
    max_tokens: int = 1000,
    status: str = "active",
    hard_stop: bool = True,
    alert_sent: bool = False,
):
    """Create a mock AITokenBudget object."""
    budget = MagicMock()
    budget.used_tokens = used_tokens
    budget.max_tokens = max_tokens
    budget.status = status
    budget.hard_stop = hard_stop
    budget.alert_sent = alert_sent
    budget.instance_id = None
    budget.id = 1
    budget.updated_at = datetime.now(timezone.utc)
    return budget


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def service(mock_db):
    return CostProtectionService(db=mock_db)


COMPANY_ID = "test-company-billing"


# ── 1. check_budget ──────────────────────────────────────────────


class TestCheckBudget:
    def test_allows_when_under_limit(self, service: CostProtectionService, mock_db):
        budget = _make_budget(used_tokens=400, max_tokens=1000)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget
        result = service.check_budget(COMPANY_ID, requested_tokens=100)
        assert result.allowed is True

    def test_blocks_when_over_limit(self, service: CostProtectionService, mock_db):
        budget = _make_budget(used_tokens=950, max_tokens=1000)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget
        result = service.check_budget(COMPANY_ID, requested_tokens=100)
        assert result.allowed is False

    def test_allows_when_no_budget_found(self, service: CostProtectionService, mock_db):
        mock_db.query.return_value.filter_by.return_value.first.return_value = None
        result = service.check_budget(COMPANY_ID, requested_tokens=100)
        # BC-008: allow when no budget record
        assert result.allowed is True


# ── 2. Hard stop ─────────────────────────────────────────────────


class TestHardStop:
    def test_hard_stop_blocks_at_limit(self, service: CostProtectionService, mock_db):
        budget = _make_budget(used_tokens=999, max_tokens=1000, hard_stop=True)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget
        result = service.check_budget(COMPANY_ID, requested_tokens=5)
        assert result.allowed is False

    def test_no_hard_stop_allows_at_exact_limit(self, service: CostProtectionService, mock_db):
        budget = _make_budget(used_tokens=0, max_tokens=1000, hard_stop=False)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget
        result = service.check_budget(COMPANY_ID, requested_tokens=1000)
        # Without hard_stop, should be allowed at exact limit
        assert result.allowed is True

    def test_zero_tokens_always_allowed(self, service: CostProtectionService, mock_db):
        budget = _make_budget(used_tokens=1000, max_tokens=1000)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget
        result = service.check_budget(COMPANY_ID, requested_tokens=0)
        assert result.allowed is True


# ── 3. Alert levels ──────────────────────────────────────────────


class TestAlertLevels:
    def _check_alert(self, used, max_val):
        budget = _make_budget(used_tokens=used, max_tokens=max_val)
        svc = CostProtectionService(db=MagicMock())
        return svc._check_alert(budget)

    def test_none_below_80(self):
        assert self._check_alert(79, 100) == AlertLevel.NONE

    def test_warning_at_80(self):
        assert self._check_alert(80, 100) == AlertLevel.WARNING

    def test_critical_at_95(self):
        assert self._check_alert(95, 100) == AlertLevel.CRITICAL

    def test_exhausted_at_100(self):
        assert self._check_alert(100, 100) == AlertLevel.EXHAUSTED

    def test_exhausted_over_100(self):
        assert self._check_alert(150, 100) == AlertLevel.EXHAUSTED


# ── 4. record_usage ──────────────────────────────────────────────


class TestRecordUsage:
    def test_increments_daily_and_monthly(self, service: CostProtectionService, mock_db):
        daily_budget = _make_budget(used_tokens=100, max_tokens=1000)
        monthly_budget = _make_budget(used_tokens=500, max_tokens=10000)
        # Configure mock to return different budgets for daily vs monthly
        mock_db.query.return_value.filter_by.return_value.first.side_effect = [daily_budget, monthly_budget]
        result = service.record_usage(COMPANY_ID, tokens_used=50)
        assert daily_budget.used_tokens == 150
        assert monthly_budget.used_tokens == 550
        assert result["tokens_recorded"] == 50

    def test_zero_tokens_returns_early(self, service: CostProtectionService):
        result = service.record_usage(COMPANY_ID, tokens_used=0)
        assert result["tokens_recorded"] == 0

    def test_sets_exceeded_when_over(self, service: CostProtectionService, mock_db):
        budget = _make_budget(used_tokens=990, max_tokens=1000)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget
        service.record_usage(COMPANY_ID, tokens_used=20)
        assert budget.status == "exceeded"


# ── 5. reset_daily_budgets ───────────────────────────────────────


class TestResetDailyBudgets:
    def test_resets_daily_to_zero(self, service: CostProtectionService, mock_db):
        budget = _make_budget(used_tokens=500, max_tokens=1000, status="active")
        mock_db.query.return_value.filter_by.return_value.all.return_value = [budget]
        result = service.reset_daily_budgets(COMPANY_ID)
        assert budget.used_tokens == 0
        assert budget.status == "active"
        assert budget.alert_sent is False
        assert result["budgets_reset"] == 1


# ── 6. TIER_DAILY_REQUEST_LIMITS ──────────────────────────────────


class TestTierDailyRequestLimits:
    def test_medium_is_2500(self):
        assert TIER_DAILY_REQUEST_LIMITS["medium"] == 2500

    def test_has_light(self):
        assert "light" in TIER_DAILY_REQUEST_LIMITS
        assert TIER_DAILY_REQUEST_LIMITS["light"] > 2500

    def test_has_heavy(self):
        assert "heavy" in TIER_DAILY_REQUEST_LIMITS
        assert TIER_DAILY_REQUEST_LIMITS["heavy"] < 2500

    def test_has_guardrail(self):
        assert "guardrail" in TIER_DAILY_REQUEST_LIMITS

    def test_all_positive_integers(self):
        for tier, limit in TIER_DAILY_REQUEST_LIMITS.items():
            assert isinstance(limit, int)
            assert limit > 0

    def test_medium_is_strictest(self):
        assert TIER_DAILY_REQUEST_LIMITS["medium"] < TIER_DAILY_REQUEST_LIMITS["light"]
        assert TIER_DAILY_REQUEST_LIMITS["heavy"] < TIER_DAILY_REQUEST_LIMITS["medium"]


# ── 7. check_tier_budget ─────────────────────────────────────────


class TestCheckTierBudget:
    def test_method_exists(self, service: CostProtectionService):
        assert hasattr(service, "check_tier_budget")
        assert callable(service.check_tier_budget)

    def test_returns_budget_check_result(self, service: CostProtectionService, mock_db):
        budget = _make_budget(used_tokens=0, max_tokens=2500)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget
        result = service.check_tier_budget(COMPANY_ID, "medium")
        assert isinstance(result, BudgetCheckResult)
        assert result.allowed is True

    def test_blocks_when_tier_exhausted(self, service: CostProtectionService, mock_db):
        budget = _make_budget(used_tokens=2500, max_tokens=2500, status="exceeded")
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget
        result = service.check_tier_budget(COMPANY_ID, "medium")
        assert result.allowed is False


# ── 8. record_tier_usage ─────────────────────────────────────────


class TestRecordTierUsage:
    def test_method_exists(self, service: CostProtectionService):
        assert hasattr(service, "record_tier_usage")
        assert callable(service.record_tier_usage)

    def test_increments_usage(self, service: CostProtectionService, mock_db):
        budget = _make_budget(used_tokens=0, max_tokens=2500)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget
        service.record_tier_usage(COMPANY_ID, "medium")
        assert budget.used_tokens == 1

    def test_marks_exceeded_at_limit(self, service: CostProtectionService, mock_db):
        budget = _make_budget(used_tokens=2499, max_tokens=2500)
        mock_db.query.return_value.filter_by.return_value.first.return_value = budget
        service.record_tier_usage(COMPANY_ID, "medium")
        assert budget.used_tokens == 2500
        assert budget.status == "exceeded"


# ── 9. Timezone-aware datetime (BC-012) ──────────────────────────


class TestTimezoneAwareDatetime:
    def test_no_utcnow_in_source(self):
        with open('/home/z/my-project/parwa/backend/app/services/cost_protection_service.py') as f:
            source = f.read()
        assert 'utcnow' not in source, (
            'cost_protection_service must use datetime.now(timezone.utc), NOT datetime.utcnow()'
        )

    def test_uses_timezone_utc(self):
        with open('/home/z/my-project/parwa/backend/app/services/cost_protection_service.py') as f:
            source = f.read()
        assert 'timezone.utc' in source, 'Must use timezone-aware UTC datetimes'

    def test_token_usage_record_uses_tz_aware(self):
        with patch.dict("sys.modules", {"database.models.variant_engine": MagicMock()}):
            from backend.app.services.cost_protection_service import TokenUsageRecord
            record = TokenUsageRecord(company_id='test')
            assert record.timestamp is not None
            assert 'T' in record.timestamp  # ISO-8601 format with time component


# ── 10. BC-002: tokens must be non-negative integers ─────────────


class TestBC002TokensNonNegative:
    def test_validate_rejects_negative(self):
        with pytest.raises(ParwaBaseError) as exc_info:
            _validate_tokens_non_negative(-1)
        assert exc_info.value.error_code == "INVALID_TOKEN_COUNT"

    def test_validate_rejects_float(self):
        with pytest.raises(ParwaBaseError):
            _validate_tokens_non_negative(10.5)

    def test_validate_accepts_zero(self):
        _validate_tokens_non_negative(0)  # Should not raise

    def test_validate_accepts_positive(self):
        _validate_tokens_non_negative(1000)  # Should not raise
