"""
Node 1 money-amount extraction — regression tests for the 2026-09-20 live-test fix.

Live incident being guarded against:
  Ticket:  "I want a refund for order A-1002. I was charged $45 ..."
  Old bug: detector regex grabbed the FIRST digits after "refund…" → amount=1002.0
           (the ORDER NUMBER, not the price). Node 5 then blocked the refund as
           "exceeds $500 tier limit" → recommend-only downgrade → the Superglue
           tool never ran. Worse, a small order number (A-102) would have produced
           a refund for the WRONG amount.

Contract after the fix:
  1. Amounts are ONLY extracted when currency-anchored ($45, ₹500, USD 45,
     "45 dollars", $1,250.50 …).
  2. Order numbers / dates / bare digits are NEVER treated as amounts.
  3. No currency anchor → amount key is ABSENT (not 0, not guessed) so Node 5's
     zero-amount lane keeps the ticket in the honest recommend-only path.
  4. Action DETECTION (execute_refund / execute_credit / investigate_billing)
     is unchanged — only the amount sourcing changed.

Run: pytest tests/test_node1_money_amount_extraction.py -v --tb=short
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# ── Pre-import: stub langgraph (same pattern as test_parwa_v2_unit.py) ──
if "langgraph" not in sys.modules:
    sys.modules["langgraph"] = MagicMock()
    sys.modules["langgraph.graph"] = MagicMock()
    sys.modules["langgraph.graph"].END = "__end__"
    sys.modules["langgraph.graph"].StateGraph = MagicMock

from app.core.parwa_pipeline.nodes.node_1_ingest_classify import (  # noqa: E402
    _extract_action,
    _extract_money_amount,
)


# ── 1. The live incident, verbatim ────────────────────────────────────

def test_refund_with_order_number_does_not_take_order_digits_as_amount():
    """THE live bug: order digits must never become the refund amount."""
    action, details = _extract_action(
        "I want a refund for order A-1002. I was charged $45 on 12 Sept but "
        "the item never arrived. Please process my refund to the original "
        "payment method.",
        "refund_request",
    )
    assert action == "execute_refund"
    assert details.get("amount") == 45.0, (
        f"expected the real price 45.0, got {details.get('amount')} "
        "(order-number digits leaked into amount)"
    )


def test_refund_order_number_first_price_after_sentence_boundary():
    """Order number BEFORE the price, across a sentence boundary."""
    action, details = _extract_action(
        "This is a refund request. Order A-1006 arrived damaged and I want "
        "my money back. The charge was $32.50. Please refund to my original "
        "payment method.",
        "refund_request",
    )
    assert action == "execute_refund"
    assert details.get("amount") == 32.5


# ── 2. The dangerous twin: small order numbers ────────────────────────

def test_small_order_number_does_not_override_real_price():
    """A-102 + $450 must yield 450, not 102 (wrong-execution hazard)."""
    _, details = _extract_action(
        "Please refund order A-102 — I paid $450 and never got it.",
        "refund_request",
    )
    assert details.get("amount") == 450.0


def test_hash_order_reference_not_taken_as_amount():
    """#58210-style ticket references are bare digits — not amounts."""
    _, details = _extract_action(
        "I need a refund for order #58210, it arrived broken.",
        "refund_request",
    )
    assert "amount" not in details, (
        "bare order reference digits leaked into amount — fail-safe broken"
    )


# ── 3. Fail-safe: no currency anchor → NO amount key at all ──────────

def test_no_currency_anchor_means_amount_absent_not_zero():
    """No anchor → amount key must be ABSENT (Node 5 zero-amount lane)."""
    _, details = _extract_action(
        "I want a refund for order 1002 which arrived broken.",
        "refund_request",
    )
    assert "amount" not in details


def test_amount_absent_beats_wrong_amount():
    """Fail-safe direction check: absent amount, never a guessed one."""
    _, details = _extract_action(
        "refund my order 42 please, bought it on the 3rd of the month",
        "refund_request",
    )
    assert "amount" not in details


# ── 4. Currency-anchored variants that MUST extract ──────────────────

@pytest.mark.parametrize(
    "text,expected",
    [
        ("refund me $45 for order A-1", 45.0),
        ("please refund ₹500 to my account, order A-2", 500.0),
        ("refund my €9.99 for order B-7", 9.99),
        ("refund 45 dollars — order C-3 never arrived", 45.0),
        ("charge was USD 1,250.50, requesting refund for order D-9", 1250.50),
        ("credit order E-4 back, paid Rs. 750", 750.0),
        ("refund 1,299 rupees for order F-11", 1299.0),
    ],
)
def test_currency_anchored_amounts_extract_correctly(text, expected):
    _, details = _extract_action(text, "refund_request")
    assert details.get("amount") == expected


# ── 5. Same contract for execute_credit ──────────────────────────────

def test_credit_action_uses_currency_anchor_too():
    _, details = _extract_action(
        "issue me a credit for order G-88, I was overcharged $25",
        "billing_inquiry",
    )
    assert details.get("amount") == 25.0


def test_credit_without_anchor_has_no_amount():
    _, details = _extract_action(
        "give me a credit for order 2000, it arrived late",
        "billing_inquiry",
    )
    assert "amount" not in details


# ── 6. _extract_money_amount unit behaviour ──────────────────────────

def test_money_extractor_pure_unit_cases():
    assert _extract_money_amount("charged $45 on 12 Sept") == 45.0
    assert _extract_money_amount("price was $1,250.50 total") == 1250.50
    assert _extract_money_amount("nothing numeric here at all") is None
    assert _extract_money_amount("order 1002 and date 12") is None
    assert _extract_money_amount("") is None
    assert _extract_money_amount(None) is None


def test_money_extractor_currency_word_variants():
    """Currency-word anchors extract even without action keywords present."""
    assert _extract_money_amount("I want my €9.99 back for order B-7") == 9.99
    assert _extract_money_amount("paid Rs. 750 for order E-4") == 750.0
    assert _extract_money_amount("INR 2000 was deducted for order Z-1") == 2000.0


# ── 7. Detection must NOT regress ────────────────────────────────────

def test_detection_still_fires_for_refund_text():
    """Only amount sourcing changed — action detection stays intact."""
    action, _ = _extract_action(
        "I want a refund for order A-1002. I was charged $45.",
        "refund_request",
    )
    assert action == "execute_refund"


def test_non_action_query_still_provide_info():
    action, details = _extract_action(
        "Hello, I have a question about your return policy.",
        "general",
    )
    assert action == "provide_info"
    assert details == {}
