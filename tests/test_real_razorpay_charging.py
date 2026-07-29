"""
Tests for real Razorpay tokenized card charging.

Verifies:
  1. razorpay_client.py has create_payment, capture_payment, get_payment methods
  2. flexpay_service.py no longer uses simulated charges
  3. flexpay_service.py calls the real Razorpay API
  4. No "pay_simulated_" or "Math.random()" in the charge path
  5. Failure path is handled (payment_success = False on error)
  6. Frontend processTokenCharge calls backend (not Math.random)

Run:  cd backend && python3 -m pytest ../tests/test_real_razorpay_charging.py -v --noconftest
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── 1. Razorpay client has the new methods ────────────────────────────────

def test_razorpay_client_has_create_payment():
    """razorpay_client.py must have create_payment method."""
    source = (_BACKEND / "app" / "clients" / "razorpay_client.py").read_text()
    assert "async def create_payment" in source, "Missing create_payment method"
    assert "POST" in source and "/payments" in source, "Must POST to /payments endpoint"
    assert "customer_id" in source, "Must accept customer_id"
    assert "token" in source, "Must accept card token"
    assert "amount" in source, "Must accept amount"


def test_razorpay_client_has_capture_payment():
    """razorpay_client.py must have capture_payment method."""
    source = (_BACKEND / "app" / "clients" / "razorpay_client.py").read_text()
    assert "async def capture_payment" in source, "Missing capture_payment method"
    assert "/capture" in source, "Must POST to /payments/{id}/capture"


def test_razorpay_client_has_get_payment():
    """razorpay_client.py must have get_payment method."""
    source = (_BACKEND / "app" / "clients" / "razorpay_client.py").read_text()
    assert "async def get_payment" in source, "Missing get_payment method"


# ── 2. FlexPay service no longer simulates ──────────────────────────────

def test_flexpay_no_simulated_charges():
    """flexpay_service.py must NOT have 'pay_simulated_' or simulated success."""
    source = (_BACKEND / "app" / "services" / "flexpay_service.py").read_text()
    assert "pay_simulated_" not in source, "Still has simulated payment IDs"
    # The old code had: payment_success = True (unconditional)
    # The new code should get it from the Razorpay API response
    assert "payment_success = payment_status == \"captured\"" in source or \
           "payment_success = payment_status == 'captured'" in source, \
           "Must check Razorpay response status, not hardcode True"


def test_flexpay_calls_real_razorpay():
    """flexpay_service.py must call razorpay_client.create_payment."""
    source = (_BACKEND / "app" / "services" / "flexpay_service.py").read_text()
    assert "razorpay_client.create_payment" in source, \
           "Must call razorpay_client.create_payment for real charging"


def test_flexpay_handles_capture():
    """flexpay_service.py must handle 'authorized' → capture flow."""
    source = (_BACKEND / "app" / "services" / "flexpay_service.py").read_text()
    assert "authorized" in source, "Must handle 'authorized' status from Razorpay"
    assert "capture_payment" in source, "Must capture authorized payments"


def test_flexpay_handles_charge_failure():
    """flexpay_service.py must set payment_success=False on charge failure."""
    source = (_BACKEND / "app" / "services" / "flexpay_service.py").read_text()
    assert "payment_success = False" in source, \
           "Must set payment_success=False on failure"
    assert "except Exception as charge_exc" in source, \
           "Must catch charge exceptions"


def test_flexpay_no_todo():
    """flexpay_service.py must NOT have TODO in the charge section."""
    source = (_BACKEND / "app" / "services" / "flexpay_service.py").read_text()
    # Find the charge section (between "ACTUAL RAZORPAY" and "if payment_success")
    charge_section = source.split("ACTUAL RAZORPAY")[1].split("if payment_success")[0] if "ACTUAL RAZORPAY" in source else ""
    assert "TODO" not in charge_section, "Charge section still has TODO"
    assert "simulate" not in charge_section.lower(), "Charge section still simulates"


# ── 3. Frontend no longer simulates ──────────────────────────────────────

def test_frontend_no_math_random_in_charges():
    """razorpay-integration.ts must NOT use Math.random() for charges."""
    source = (_REPO_ROOT / "src" / "lib" / "flexpay" / "razorpay-integration.ts").read_text()
    # Find the processTokenCharge function
    func_start = source.find("export async function processTokenCharge")
    func_end = source.find("} catch", func_start)
    func_body = source[func_start:func_end] if func_start >= 0 else ""
    assert "Math.random()" not in func_body, \
           "processTokenCharge still uses Math.random() — must call real API"
    assert "fetch(" in func_body, \
           "processTokenCharge must call the backend API via fetch()"


def test_frontend_calls_backend_for_charges():
    """processTokenCharge must call /api/flexpay/process-installments."""
    source = (_REPO_ROOT / "src" / "lib" / "flexpay" / "razorpay-integration.ts").read_text()
    assert "/api/flexpay/process-installments" in source, \
           "Must call backend /api/flexpay/process-installments"


def test_process_installments_route_proxies_to_backend():
    """The process-installments route must proxy to the backend, not use frontend scheduler."""
    source = (_REPO_ROOT / "src" / "app" / "api" / "flexpay" / "process-installments" / "route.ts").read_text()
    assert "getBackendUrl" in source or "backend" in source.lower(), \
           "Must proxy to backend"
    assert "processAllPlans" not in source, \
           "Must NOT call frontend scheduler (which is simulated)"


# ── 4. Amount conversion is correct ──────────────────────────────────────

def test_amount_converted_to_cents():
    """flexpay_service.py must convert USD to cents for the API call."""
    source = (_BACKEND / "app" / "services" / "flexpay_service.py").read_text()
    assert "amount_cents = int(next_installment.amount * 100)" in source, \
           "Must convert USD to cents"
    assert 'currency="USD"' in source, "Must use USD currency"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--noconftest"]))
