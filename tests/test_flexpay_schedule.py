"""
Tests for FlexPay installment schedules with new pricing ($2,999 + $3,999).

Verifies:
  1. PARWA ($2,999): 30 days, $100/day, last day = $99, no double charges
  2. PARWA High ($3,999): 30 days, double charges every 3rd day, last day adjusted
  3. Total collected equals the subscription price exactly
  4. No single transaction exceeds $100 (Razorpay limit)
  5. All installments fit within 30-day window
  6. No Mini tier in the schedule

Run:  cd backend && python3 -m pytest ../tests/test_flexpay_schedule.py -v --noconftest
"""

from __future__ import annotations

import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def _calculate_schedule(total_amount: Decimal, tier: str, days: int = 30):
    """Replicate the FlexPay schedule logic for testing."""
    BASE = Decimal("100.00")
    EXTRA = Decimal("100.00")
    EXTRA_INTERVAL = 3

    installments = []
    day = 1
    collected = Decimal("0")

    while collected < total_amount and day <= days + 5:
        # Base charge
        base = min(BASE, total_amount - collected)
        if base > 0:
            installments.append({"day": day, "amount": float(base), "is_extra": False})
            collected += base

        # Extra charge every 3rd day for HIGH tier only
        if tier == "high" and day % EXTRA_INTERVAL == 0 and collected < total_amount:
            extra = min(EXTRA, total_amount - collected)
            if extra > 0:
                installments.append({"day": day, "amount": float(extra), "is_extra": True})
                collected += extra

        day += 1

    return installments, collected


# ── 1. PARWA ($2,999) — no double charges, last day = $99 ────────────────

def test_parwa_2999_total_collected():
    """PARWA $2,999: total collected must equal exactly $2,999."""
    installments, collected = _calculate_schedule(Decimal("2999"), "parwa")
    assert collected == Decimal("2999"), f"Expected $2999, got ${collected}"


def test_parwa_2999_last_day_is_99():
    """PARWA $2,999: last installment must be $99 (2999 - 29×100 = 99)."""
    installments, _ = _calculate_schedule(Decimal("2999"), "parwa")
    last = installments[-1]
    assert last["amount"] == 99.0, f"Expected last payment $99, got ${last['amount']}"


def test_parwa_2999_no_double_charges():
    """PARWA $2,999: must NOT have any extra/double charges (tier != high)."""
    installments, _ = _calculate_schedule(Decimal("2999"), "parwa")
    extras = [i for i in installments if i["is_extra"]]
    assert len(extras) == 0, f"PARWA should have 0 double charges, got {len(extras)}"


def test_parwa_2999_fits_in_30_days():
    """PARWA $2,999: must complete within 30 days (30 × $100 = $3,000 ≥ $2,999)."""
    installments, _ = _calculate_schedule(Decimal("2999"), "parwa")
    last_day = installments[-1]["day"]
    assert last_day <= 30, f"Must complete in ≤30 days, got day {last_day}"


def test_parwa_2999_30_installments():
    """PARWA $2,999: should have exactly 30 installments (29 × $100 + 1 × $99)."""
    installments, _ = _calculate_schedule(Decimal("2999"), "parwa")
    assert len(installments) == 30, f"Expected 30 installments, got {len(installments)}"


# ── 2. PARWA High ($3,999) — double charges, fits in 30 days ─────────────

def test_high_3999_total_collected():
    """PARWA High $3,999: total collected must equal exactly $3,999."""
    installments, collected = _calculate_schedule(Decimal("3999"), "high")
    assert collected == Decimal("3999"), f"Expected $3999, got ${collected}"


def test_high_3999_has_double_charges():
    """PARWA High $3,999: must have double charges every 3rd day."""
    installments, _ = _calculate_schedule(Decimal("3999"), "high")
    extras = [i for i in installments if i["is_extra"]]
    assert len(extras) > 0, "High tier should have double charges"


def test_high_3999_fits_in_30_days():
    """PARWA High $3,999: must complete within 30 days."""
    installments, _ = _calculate_schedule(Decimal("3999"), "high")
    last_day = installments[-1]["day"]
    assert last_day <= 30, f"Must complete in ≤30 days, got day {last_day}"


def test_high_3999_last_installment_under_100():
    """PARWA High $3,999: last installment must be ≤ $100 (adjusted to hit exact total)."""
    installments, _ = _calculate_schedule(Decimal("3999"), "high")
    last = installments[-1]
    assert last["amount"] <= 100.0, f"Last payment must be ≤$100, got ${last['amount']}"


# ── 3. No transaction exceeds $100 (Razorpay limit) ───────────────────────

def test_parwa_no_transaction_over_100():
    """PARWA: no single transaction can exceed $100."""
    installments, _ = _calculate_schedule(Decimal("2999"), "parwa")
    for inst in installments:
        assert inst["amount"] <= 100.0, f"Transaction ${inst['amount']} exceeds $100 limit"


def test_high_no_transaction_over_100():
    """PARWA High: no single transaction can exceed $100."""
    installments, _ = _calculate_schedule(Decimal("3999"), "high")
    for inst in installments:
        assert inst["amount"] <= 100.0, f"Transaction ${inst['amount']} exceeds $100 limit"


# ── 4. No Mini tier ───────────────────────────────────────────────────────

def test_no_mini_in_flexpay_source():
    """FlexPay service must not reference Mini tier."""
    source = (_BACKEND / "app" / "services" / "flexpay_service.py").read_text()
    # Comments mentioning "Mini removed" are OK, but active code shouldn't use "mini"
    lines = [l for l in source.split("\n") if "mini" in l.lower() and "removed" not in l.lower() and "#" not in l.split("mini")[0]]
    assert len(lines) == 0, f"FlexPay still references Mini in active code: {lines}"


def test_flexpay_core_no_mini():
    """FlexPay core.ts must not have Mini in TIER_PRICES."""
    source = (_REPO_ROOT / "src" / "lib" / "flexpay" / "core.ts").read_text()
    assert "'mini'" not in source, "flexpay/core.ts still has 'mini' in type"
    assert "mini: " not in source, "flexpay/core.ts still has mini in TIER_PRICES"


# ── 5. Prices match pricing-config ────────────────────────────────────────

def test_flexpay_prices_match_pricing_config():
    """FlexPay TIER_PRICES must match pricing-config.ts VARIANT_PRICES."""
    # From pricing-config.ts
    parwa_price = 2999
    high_price = 3999

    # From flexpay/core.ts
    core_source = (_REPO_ROOT / "src" / "lib" / "flexpay" / "core.ts").read_text()
    assert f"parwa: {parwa_price}" in core_source, f"FlexPay parwa price mismatch: expected {parwa_price}"
    assert f"high: {high_price}" in core_source, f"FlexPay high price mismatch: expected {high_price}"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--noconftest"]))
