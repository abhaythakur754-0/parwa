"""
Tests for Node 2 / Node 5 capability matrix reconciliation.

After Mini PARWA was removed, both node_2_smart_route.py and
node_5_act_verify.py must agree on:
  1. Only 2 tiers exist: parwa + high (no mini entry).
  2. Both tiers have execute_refund/execute_credit/account_change = True.
  3. Parwa has financial limits ($500 refund / $200 credit).
  4. High has unlimited financial actions.
  5. Node 5's default fallback is "parwa" (not the deleted "mini").

Run:  cd backend && python3 -m pytest ../tests/test_capability_matrix_consistency.py -v --noconftest
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── 1. Node 2 (smart route) ────────────────────────────────────────────────

def test_node2_capability_matrix_has_no_mini():
    from app.core.parwa_pipeline.nodes.node_2_smart_route import CAPABILITY_MATRIX

    assert "mini" not in CAPABILITY_MATRIX, "Node 2 still has mini in CAPABILITY_MATRIX"
    assert set(CAPABILITY_MATRIX.keys()) == {"parwa", "high"}


def test_node2_execution_limits_have_no_mini():
    from app.core.parwa_pipeline.nodes.node_2_smart_route import EXECUTION_LIMITS

    assert "mini" not in EXECUTION_LIMITS
    assert set(EXECUTION_LIMITS.keys()) == {"parwa", "high"}


def test_node2_tier_order_has_two_tiers():
    from app.core.parwa_pipeline.nodes.node_2_smart_route import TIER_ORDER

    assert TIER_ORDER == ["parwa", "high"]


def test_node2_both_tiers_have_full_capabilities():
    from app.core.parwa_pipeline.nodes.node_2_smart_route import CAPABILITY_MATRIX

    for tier in ("parwa", "high"):
        caps = CAPABILITY_MATRIX[tier]
        assert caps["execute_refund"] is True
        assert caps["execute_credit"] is True
        assert caps["account_change"] is True


def test_node2_parwa_has_financial_limits():
    """Parwa (lower tier) must have financial guardrails."""
    from app.core.parwa_pipeline.nodes.node_2_smart_route import EXECUTION_LIMITS

    assert EXECUTION_LIMITS["parwa"]["max_refund"] == 500
    assert EXECUTION_LIMITS["parwa"]["max_credit"] == 200


def test_node2_high_has_unlimited_financials():
    """High tier has unlimited financial actions."""
    from app.core.parwa_pipeline.nodes.node_2_smart_route import EXECUTION_LIMITS
    import math

    assert math.isinf(EXECUTION_LIMITS["high"]["max_refund"])
    assert math.isinf(EXECUTION_LIMITS["high"]["max_credit"])


# ── 2. Node 5 (act verify) ─────────────────────────────────────────────────

def test_node5_capability_matrix_has_no_mini():
    from app.core.parwa_pipeline.nodes.node_5_act_verify import _CAPABILITY_MATRIX

    assert "mini" not in _CAPABILITY_MATRIX
    assert set(_CAPABILITY_MATRIX.keys()) == {"parwa", "high"}


def test_node5_exec_limits_have_no_mini():
    from app.core.parwa_pipeline.nodes.node_5_act_verify import _EXEC_LIMITS

    assert "mini" not in _EXEC_LIMITS
    assert set(_EXEC_LIMITS.keys()) == {"parwa", "high"}


def test_node5_default_fallback_is_parwa_not_mini():
    """The .get(tier, default) fallback must use 'parwa', not the deleted 'mini'."""
    # Read the source to verify the fallback string literal.
    source = (
        _BACKEND
        / "app/core/parwa_pipeline/nodes/node_5_act_verify.py"
    ).read_text()
    assert '_CAPABILITY_MATRIX["mini"]' not in source, (
        "Node 5 still falls back to _CAPABILITY_MATRIX['mini'] — should be 'parwa'"
    )
    assert '_EXEC_LIMITS["mini"]' not in source, (
        "Node 5 still falls back to _EXEC_LIMITS['mini'] — should be 'parwa'"
    )


# ── 3. Cross-file consistency ──────────────────────────────────────────────

def test_node2_and_node5_agree_on_parwa_limits():
    """Both files must have the same limits for parwa."""
    from app.core.parwa_pipeline.nodes.node_2_smart_route import EXECUTION_LIMITS
    from app.core.parwa_pipeline.nodes.node_5_act_verify import _EXEC_LIMITS

    assert EXECUTION_LIMITS["parwa"] == _EXEC_LIMITS["parwa"]


def test_node2_and_node5_agree_on_high_limits():
    """Both files must have the same limits for high."""
    from app.core.parwa_pipeline.nodes.node_2_smart_route import EXECUTION_LIMITS
    from app.core.parwa_pipeline.nodes.node_5_act_verify import _EXEC_LIMITS

    assert EXECUTION_LIMITS["high"] == _EXEC_LIMITS["high"]


def test_node2_and_node5_agree_on_capabilities():
    """Both files must agree that parwa + high have all capabilities True."""
    from app.core.parwa_pipeline.nodes.node_2_smart_route import CAPABILITY_MATRIX
    from app.core.parwa_pipeline.nodes.node_5_act_verify import _CAPABILITY_MATRIX

    for tier in ("parwa", "high"):
        n2 = CAPABILITY_MATRIX[tier]
        n5 = _CAPABILITY_MATRIX[tier]
        assert n2["execute_refund"] == n5["execute_refund"] is True
        assert n2["execute_credit"] == n5["execute_credit"] is True
        assert n2["account_change"] == n5["account_change"] is True


# ── 4. Rule-based check respects limits ────────────────────────────────────

def test_rule_based_check_blocks_parwa_refund_over_500():
    """Parwa can refund up to $500; over that is blocked."""
    from app.core.parwa_pipeline.nodes.node_5_act_verify import _rule_based_check

    result = _rule_based_check("execute_refund", 501, "parwa")
    assert result["can_execute"] is False
    assert "500" in result["reason"]


def test_rule_based_check_allows_parwa_refund_under_500():
    from app.core.parwa_pipeline.nodes.node_5_act_verify import _rule_based_check

    result = _rule_based_check("execute_refund", 499, "parwa")
    assert result["can_execute"] is True


def test_rule_based_check_allows_high_unlimited_refund():
    from app.core.parwa_pipeline.nodes.node_5_act_verify import _rule_based_check

    result = _rule_based_check("execute_refund", 999999, "high")
    assert result["can_execute"] is True


def test_rule_based_check_unknown_tier_falls_back_to_parwa():
    """An unknown tier string must fall back to parwa limits (not crash)."""
    from app.core.parwa_pipeline.nodes.node_5_act_verify import _rule_based_check

    # "mini" is no longer in the matrix → falls back to parwa ($500 limit)
    result = _rule_based_check("execute_refund", 600, "mini")
    assert result["can_execute"] is False  # $600 > $500 parwa limit


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v", "--noconftest"]))
