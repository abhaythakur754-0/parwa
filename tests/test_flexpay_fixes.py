"""
Tests for: razorpay_token column + FlexPay scheduler loop + billing modal fixes.

Verifies:
  1. FlexPayPlan model has razorpay_token column
  2. main.py has FlexPay scheduler background loop
  3. Billing modal has max-height + overflow-y-auto (scrollable)
  4. Billing modal uses max-w-md (compact, not max-w-lg)
  5. Schedule list has max-h-48 (scrollable, not full height)
  6. Actions section is sticky (shrink-0)
  7. Button text says "Pay $100 Today" (not "Pay $100 • Start FlexPay")

Run:  cd backend && python3 -m pytest ../tests/test_flexpay_fixes.py -v --noconftest
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── 1. FlexPayPlan has razorpay_token ────────────────────────────────────

def test_flexpay_model_has_token_column():
    """FlexPayPlan model must have razorpay_token column."""
    source = (_BACKEND / "database" / "models" / "flexpay.py").read_text()
    assert "razorpay_token" in source, "Missing razorpay_token column in FlexPayPlan"
    assert "Card token for recurring charges" in source, "Missing token docstring"


def test_flexpay_model_has_customer_id():
    """FlexPayPlan model must still have razorpay_customer_id."""
    source = (_BACKEND / "database" / "models" / "flexpay.py").read_text()
    assert "razorpay_customer_id" in source, "Missing razorpay_customer_id column"


# ── 2. main.py has FlexPay scheduler loop ───────────────────────────────

def test_main_has_flexpay_loop():
    """main.py must have a _flexpay_scheduler_loop background task."""
    source = (_BACKEND / "app" / "main.py").read_text()
    assert "_flexpay_scheduler_loop" in source, "Missing FlexPay scheduler loop in main.py"
    assert "asyncio.create_task(_flexpay_scheduler_loop())" in source, "Loop must be started"
    assert "flexpay_scheduler_loop_started" in source, "Missing startup log"


def test_flexpay_loop_uses_scheduler():
    """The loop must call FlexPayScheduler.run_once()."""
    source = (_BACKEND / "app" / "main.py").read_text()
    assert "FlexPayScheduler" in source, "Must import FlexPayScheduler"
    assert "scheduler.run_once()" in source, "Must call run_once()"


def test_flexpay_loop_has_error_handling():
    """The loop must catch exceptions (never die)."""
    source = (_BACKEND / "app" / "main.py").read_text()
    # Find the flexpay loop section
    loop_start = source.find("_flexpay_scheduler_loop")
    loop_end = source.find("yield", loop_start)
    loop_section = source[loop_start:loop_end] if loop_start >= 0 else ""
    assert "except Exception" in loop_section, "Loop must catch exceptions"
    assert "flexpay_scheduler_loop_error" in loop_section, "Must log errors"


def test_flexpay_loop_sleep_interval():
    """The loop must sleep 3600 seconds (1 hour) between runs."""
    source = (_BACKEND / "app" / "main.py").read_text()
    loop_start = source.find("_flexpay_scheduler_loop")
    loop_end = source.find("yield", loop_start)
    loop_section = source[loop_start:loop_end] if loop_start >= 0 else ""
    assert "3600" in loop_section, "Must sleep 3600 seconds (1 hour)"


# ── 3. Billing modal is compact + scrollable ─────────────────────────────

def test_billing_modal_has_max_height():
    """Modal must have max-h to prevent full-screen popup."""
    source = (_REPO_ROOT / "src" / "app" / "dashboard" / "billing" / "page.tsx").read_text()
    assert "max-h-[85vh]" in source, "Modal must have max-height 85vh"
    assert "flex flex-col" in source, "Modal must use flex column for scroll layout"


def test_billing_modal_compact_width():
    """Modal must be max-w-md (compact), not max-w-lg (wide)."""
    source = (_REPO_ROOT / "src" / "app" / "dashboard" / "billing" / "page.tsx").read_text()
    assert "max-w-md" in source, "Modal should be max-w-md (compact)"


def test_billing_schedule_scrollable():
    """The payment schedule list must be scrollable (max-h + overflow)."""
    source = (_REPO_ROOT / "src" / "app" / "dashboard" / "billing" / "page.tsx").read_text()
    assert "max-h-48" in source or "max-h-40" in source, "Schedule list must have max-height for scrolling"
    assert "overflow-y-auto" in source, "Schedule must have overflow-y-auto"


def test_billing_content_scrollable():
    """The content area must be scrollable."""
    source = (_REPO_ROOT / "src" / "app" / "dashboard" / "billing" / "page.tsx").read_text()
    # Find the content div (between header and actions)
    content_start = source.find("Content — scrollable")
    if content_start < 0:
        content_start = source.find("overflow-y-auto flex-1")
    assert content_start >= 0, "Content area must have overflow-y-auto + flex-1"


def test_billing_actions_sticky():
    """The actions section must be sticky (shrink-0)."""
    source = (_REPO_ROOT / "src" / "app" / "dashboard" / "billing" / "page.tsx").read_text()
    assert "shrink-0" in source, "Actions section must have shrink-0 (sticky bottom)"


def test_billing_button_text_simple():
    """Button text must be simple ('Pay $100 Today')."""
    source = (_REPO_ROOT / "src" / "app" / "dashboard" / "billing" / "page.tsx").read_text()
    assert "Pay $100 Today" in source, "Button should say 'Pay $100 Today' (simple)"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--noconftest"]))
