"""
Tests for USD currency in Razorpay billing (no INR for US users).

Verifies:
  1. razorpay_service.py defaults to USD (not INR) in payment capture
  2. razorpay_service.py defaults to USD (not INR) in refund processing
  3. razorpay_checkout.py default currency is USD
  4. No 'INR' as a default currency in backend billing code
  5. Frontend billing page uses USD (not INR)
  6. FlexPay razorpay-integration uses USD (not INR)

Run:  cd backend && python3 -m pytest ../tests/test_usd_currency.py -v --noconftest
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── 1. Backend — no INR defaults ───────────────────────────────────────────

def test_razorpay_service_no_inr_default():
    """razorpay_service.py must not default to INR anywhere."""
    source = (_BACKEND / "app" / "services" / "razorpay_service.py").read_text()
    assert 'or "INR"' not in source, 'Found: or "INR" — should be or "USD"'
    assert 'or "USD"' in source, "Missing USD default"


def test_razorpay_checkout_default_usd():
    """razorpay_checkout.py default currency must be USD."""
    source = (_BACKEND / "app" / "api" / "razorpay_checkout.py").read_text()
    assert 'Field("USD"' in source, "razorpay_checkout.py should default to USD"
    assert 'Field("INR"' not in source, "razorpay_checkout.py still defaults to INR"
    assert "paise" not in source, "Should say 'cents' not 'paise'"


def test_billing_razorpay_currency_usd():
    """billing_razorpay.py pricing endpoint should show USD."""
    source = (_BACKEND / "app" / "api" / "billing_razorpay.py").read_text()
    assert '"currency": "USD"' in source, "billing_razorpay.py should show USD"


# ── 2. Frontend — no INR in user-facing code ──────────────────────────────

def test_billing_page_usd():
    """Dashboard billing page must use USD (not INR)."""
    source = (_REPO_ROOT / "src" / "app" / "dashboard" / "billing" / "page.tsx").read_text()
    assert 'currency="USD"' in source, "Billing page should use USD"
    assert 'currency="INR"' not in source, "Billing page still uses INR"


def test_verify_payment_usd():
    """verify-payment route must use USD (not INR)."""
    source = (_REPO_ROOT / "src" / "app" / "api" / "razorpay" / "verify-payment" / "route.ts").read_text()
    assert "currency: 'USD'" in source, "verify-payment should use USD"
    assert "currency: 'INR'" not in source, "verify-payment still uses INR"
    assert "rupees" not in source, "Should say 'dollars' not 'rupees'"


def test_flexpay_integration_usd():
    """FlexPay razorpay-integration must use USD (not INR)."""
    source = (_REPO_ROOT / "src" / "lib" / "flexpay" / "razorpay-integration.ts").read_text()
    # Active code (not comments) should not have INR as currency
    active_lines = [l for l in source.split("\n") if "INR" in l and "//" not in l.split("INR")[0] and "*" not in l.split("INR")[0]]
    assert len(active_lines) == 0, f"FlexPay still has INR in active code: {active_lines}"


def test_flexpay_no_paise_in_active_code():
    """FlexPay should not reference 'paise' in active code (comments OK)."""
    source = (_REPO_ROOT / "src" / "lib" / "flexpay" / "razorpay-integration.ts").read_text()
    active_lines = [l for l in source.split("\n") if "paise" in l.lower() and "//" not in l.split("paise")[0] and "*" not in l.split("paise")[0]]
    assert len(active_lines) == 0, f"FlexPay still references paise: {active_lines}"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--noconftest"]))
