"""
Integration tests for the FlexPay charging flow — MOCKED (no real charges).

These tests verify the REAL code path works correctly by mocking
the Razorpay API responses. No real charges, no real keys needed.

What we test:
  1. When Razorpay returns "captured" → payment succeeds, DB updated
  2. When Razorpay returns "authorized" → capture is called → payment succeeds
  3. When Razorpay returns an error → payment fails, DB NOT updated
  4. When Razorpay API is unreachable → payment fails gracefully
  5. When no customer_id exists → payment fails (not simulated)
  6. Amount is correctly converted to cents
  7. Invoice + Transaction records are created on success
  8. Failed installment triggers failure handling

Run:  cd backend && python3 -m pytest ../tests/test_flexpay_charging_integration.py -v --noconftest
"""

from __future__ import annotations

import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── Helper: create a mock FlexPay plan + installment ────────────────────

def _mock_plan():
    """Create a mock FlexPayPlan with all fields the charge code needs."""
    plan = MagicMock()
    plan.id = "plan_test_001"
    plan.company_id = "comp_test_001"
    plan.variant_tier = "parwa"
    plan.razorpay_customer_id = "cust_test_001"
    plan.razorpay_token = "token_test_001"
    plan.status = "active"
    plan.total_installments = 30
    plan.completed_installments = 0
    plan.consecutive_failures = 0
    plan.last_failure_reason = None
    plan.last_failure_at = None
    return plan


def _mock_installment(amount=100.0, number=1):
    """Create a mock FlexPayInstallment."""
    inst = MagicMock()
    inst.id = "inst_test_001"
    inst.plan_id = "plan_test_001"
    inst.installment_number = number
    inst.amount = Decimal(str(amount))
    inst.status = "processing"  # Already set to processing by the code
    inst.razorpay_payment_id = None
    inst.processed_at = None
    return inst


def _mock_db(plan, installment):
    """Create a mock DB session that returns our plan + installment."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = plan
    # For the installment query (separate filter)
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = installment
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    return db


# ── 1. Razorpay returns "captured" → success ─────────────────────────────

def test_charge_success_captured():
    """When Razorpay returns status='captured', payment should succeed."""
    from app.services.flexpay_service import process_next_installment, InstallmentStatus

    plan = _mock_plan()
    inst = _mock_installment(amount=100.0)
    db = _mock_db(plan, inst)

    # Mock Razorpay client — returns "captured"
    mock_client = AsyncMock()
    mock_client.create_payment = AsyncMock(return_value={
        "id": "pay_real_001",
        "status": "captured",
        "amount": 10000,
    })

    result = asyncio.run(process_next_installment(db, "plan_test_001", mock_client))

    assert result["status"] == "success", f"Expected success, got {result['status']}"
    assert result["payment_id"] == "pay_real_001", "Must use real payment ID from Razorpay"
    assert result["amount"] == 100.0, "Amount must be $100"
    assert inst.status == InstallmentStatus.PAID.value, "Installment must be marked PAID"
    assert inst.razorpay_payment_id == "pay_real_001", "Must store real Razorpay payment ID"


# ── 2. Razorpay returns "authorized" → capture → success ────────────────

def test_charge_success_authorized_then_capture():
    """When Razorpay returns 'authorized', the code must capture it."""
    from app.services.flexpay_service import process_next_installment, InstallmentStatus

    plan = _mock_plan()
    inst = _mock_installment(amount=100.0)
    db = _mock_db(plan, inst)

    mock_client = AsyncMock()
    # First call returns "authorized"
    mock_client.create_payment = AsyncMock(return_value={
        "id": "pay_real_002",
        "status": "authorized",
        "amount": 10000,
    })
    # Capture call returns "captured"
    mock_client.capture_payment = AsyncMock(return_value={
        "id": "pay_real_002",
        "status": "captured",
    })

    result = asyncio.run(process_next_installment(db, "plan_test_001", mock_client))

    assert result["status"] == "success", f"Expected success after capture, got {result['status']}"
    assert inst.razorpay_payment_id == "pay_real_002"
    # Verify capture was called
    mock_client.capture_payment.assert_called_once()


# ── 3. Razorpay returns error → payment fails ────────────────────────────

def test_charge_failure_razorpay_error():
    """When Razorpay raises an exception, payment must fail (not succeed)."""
    from app.services.flexpay_service import process_next_installment

    plan = _mock_plan()
    inst = _mock_installment(amount=100.0)
    db = _mock_db(plan, inst)

    mock_client = AsyncMock()
    mock_client.create_payment = AsyncMock(side_effect=Exception("Card declined"))

    result = asyncio.run(process_next_installment(db, "plan_test_001", mock_client))

    assert result["status"] != "success", "Payment must NOT succeed on Razorpay error"
    # The installment should NOT be marked as paid
    assert inst.status != "PAID", "Installment must not be marked PAID on failure"


# ── 4. Razorpay API unreachable → payment fails gracefully ──────────────

def test_charge_failure_network_error():
    """When the network is down, payment must fail gracefully (no crash)."""
    from app.services.flexpay_service import process_next_installment

    plan = _mock_plan()
    inst = _mock_installment(amount=100.0)
    db = _mock_db(plan, inst)

    mock_client = AsyncMock()
    mock_client.create_payment = AsyncMock(side_effect=ConnectionError("Network timeout"))

    # Must not raise — must return a failure result
    result = asyncio.run(process_next_installment(db, "plan_test_001", mock_client))

    assert result["status"] != "success", "Must fail on network error"
    assert inst.status != "PAID", "Must not mark as paid"


# ── 5. No customer_id → payment fails (not simulated) ───────────────────

def test_charge_failure_no_customer_id():
    """When no customer_id exists, payment must fail — NOT simulate success."""
    from app.services.flexpay_service import process_next_installment

    plan = _mock_plan()
    plan.razorpay_customer_id = None  # No customer ID
    inst = _mock_installment(amount=100.0)
    db = _mock_db(plan, inst)

    mock_client = AsyncMock()

    result = asyncio.run(process_next_installment(db, "plan_test_001", mock_client))

    assert result["status"] != "success", "Must NOT succeed without customer_id"
    assert inst.status != "PAID", "Must not mark as paid without customer_id"
    # create_payment must NOT have been called
    mock_client.create_payment.assert_not_called()


# ── 6. No token → payment fails ──────────────────────────────────────────

def test_charge_failure_no_token():
    """When no card token exists, payment must fail."""
    from app.services.flexpay_service import process_next_installment

    plan = _mock_plan()
    plan.razorpay_token = None  # No token
    inst = _mock_installment(amount=100.0)
    db = _mock_db(plan, inst)

    mock_client = AsyncMock()
    mock_client.create_payment = AsyncMock(side_effect=Exception("Missing token"))

    result = asyncio.run(process_next_installment(db, "plan_test_001", mock_client))

    assert result["status"] != "success", "Must NOT succeed without token"


# ── 7. Amount is correctly converted to cents ───────────────────────────

def test_amount_converted_to_cents():
    """The charge amount must be converted from USD to cents (×100)."""
    from app.services.flexpay_service import process_next_installment

    plan = _mock_plan()
    inst = _mock_installment(amount=99.0)  # Last day = $99
    db = _mock_db(plan, inst)

    mock_client = AsyncMock()
    mock_client.create_payment = AsyncMock(return_value={
        "id": "pay_real_003",
        "status": "captured",
        "amount": 9900,  # $99 → 9900 cents
    })

    asyncio.run(process_next_installment(db, "plan_test_001", mock_client))

    # Check the amount passed to create_payment
    call_args = mock_client.create_payment.call_args
    assert call_args is not None, "create_payment must have been called"
    amount_passed = call_args.kwargs.get("amount") or call_args[1].get("amount")
    assert amount_passed == 9900, f"Expected 9900 cents ($99), got {amount_passed}"


# ── 8. Invoice + Transaction created on success ─────────────────────────

def test_invoice_and_transaction_created_on_success():
    """On successful charge, an Invoice and Transaction record must be created."""
    from app.services.flexpay_service import process_next_installment

    plan = _mock_plan()
    inst = _mock_installment(amount=100.0)
    db = _mock_db(plan, inst)

    mock_client = AsyncMock()
    mock_client.create_payment = AsyncMock(return_value={
        "id": "pay_real_004",
        "status": "captured",
    })

    asyncio.run(process_next_installment(db, "plan_test_001", mock_client))

    # db.add must have been called for Invoice + Transaction
    assert db.add.call_count >= 2, f"Must add Invoice + Transaction (got {db.add.call_count} calls)"
    db.commit.assert_called(), "Must commit to DB"


# ── 9. No "pay_simulated_" in the result ────────────────────────────────

def test_no_simulated_payment_id():
    """The payment_id must be from Razorpay, not 'pay_simulated_'."""
    from app.services.flexpay_service import process_next_installment

    plan = _mock_plan()
    inst = _mock_installment(amount=100.0)
    db = _mock_db(plan, inst)

    mock_client = AsyncMock()
    mock_client.create_payment = AsyncMock(return_value={
        "id": "pay_real_005",
        "status": "captured",
    })

    result = asyncio.run(process_next_installment(db, "plan_test_001", mock_client))

    payment_id = result.get("payment_id", "")
    assert "simulated" not in payment_id.lower(), \
           f"Payment ID must be real, got: {payment_id}"
    assert payment_id == "pay_real_005", f"Expected real Razorpay ID, got: {payment_id}"


# ── 10. Source code has no simulation left ───────────────────────────────

def test_source_no_simulation():
    """The flexpay_service.py charge section must not contain simulation code."""
    source = (_BACKEND / "app" / "services" / "flexpay_service.py").read_text()
    # Find the charge section
    if "ACTUAL RAZORPAY" in source:
        charge_section = source.split("ACTUAL RAZORPAY")[1].split("if payment_success")[0]
    else:
        charge_section = source

    assert "pay_simulated_" not in charge_section, "Still has simulated payment IDs"
    assert "payment_success = True" not in charge_section.replace("payment_success = payment_status", ""), \
           "Still has hardcoded payment_success = True"
    assert "simulate" not in charge_section.lower(), "Still simulates"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--noconftest"]))
