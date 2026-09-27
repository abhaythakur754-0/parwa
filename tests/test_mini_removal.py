"""
Tests for Mini PARWA removal — verifies that Mini is gone from the pricing
config but legacy "mini"/"starter"/"mini_parwa" strings auto-upgrade to "parwa"
so existing DB records and API calls don't break.

Run:  cd backend && python3 -m pytest ../tests/test_mini_removal.py -v --noconftest
"""

from __future__ import annotations

import sys
from pathlib import Path
from decimal import Decimal

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── 1. Enum no longer has MINI ─────────────────────────────────────────────

def test_variant_type_enum_has_only_two_members():
    """VariantType must have only PARWA and HIGH — no MINI."""
    from app.core.pricing_config import VariantType

    members = {v.value for v in VariantType}
    assert members == {"parwa", "high"}, f"Unexpected members: {members}"
    assert not hasattr(VariantType, "MINI"), "VariantType.MINI still exists"


# ── 2. Pricing dicts don't have Mini ───────────────────────────────────────

def test_variant_prices_has_no_mini():
    from app.core.pricing_config import VARIANT_PRICES, VariantType

    assert VariantType.MINI not in VARIANT_PRICES if hasattr(VariantType, "MINI") else True
    assert set(VARIANT_PRICES.keys()) == {VariantType.PARWA, VariantType.HIGH}


def test_variant_limits_has_no_mini():
    from app.core.pricing_config import VARIANT_LIMITS, VariantType

    assert set(VARIANT_LIMITS.keys()) == {VariantType.PARWA, VariantType.HIGH}


def test_variant_tier_order_has_two_levels():
    from app.core.pricing_config import VARIANT_TIER_ORDER

    assert len(VARIANT_TIER_ORDER) == 2
    # parwa < high
    assert VARIANT_TIER_ORDER[VariantType.PARWA] < VARIANT_TIER_ORDER[VariantType.HIGH] if False else True
    from app.core.pricing_config import VariantType
    assert VARIANT_TIER_ORDER[VariantType.PARWA] == 1
    assert VARIANT_TIER_ORDER[VariantType.HIGH] == 2


# ── 3. Legacy names auto-upgrade to parwa ──────────────────────────────────

def test_normalize_mini_returns_parwa():
    """The key test: 'mini' must normalize to 'parwa' (auto-upgrade)."""
    from app.core.pricing_config import normalize_variant_name

    assert normalize_variant_name("mini") == "parwa"
    assert normalize_variant_name("MINI") == "parwa"
    assert normalize_variant_name("mini_parwa") == "parwa"
    assert normalize_variant_name("starter") == "parwa"
    assert normalize_variant_name("mini-parwa") == "parwa"


def test_normalize_parwa_and_high_unchanged():
    from app.core.pricing_config import normalize_variant_name

    assert normalize_variant_name("parwa") == "parwa"
    assert normalize_variant_name("high") == "high"
    assert normalize_variant_name("parwa_high") == "high"


def test_get_variant_price_mini_returns_parwa_price():
    """Asking for Mini's price returns Parwa's price ($2499, not $999)."""
    from app.core.pricing_config import get_variant_price

    assert get_variant_price("mini") == Decimal("2499.00")
    assert get_variant_price("mini_parwa") == Decimal("2499.00")
    assert get_variant_price("starter") == Decimal("2499.00")


def test_get_variant_limits_mini_returns_parwa_limits():
    """Mini gets Parwa's limits (5 AI agents, not 0)."""
    from app.core.pricing_config import get_variant_limits

    mini_limits = get_variant_limits("mini")
    assert mini_limits["monthly_tickets"] == 2499  # was 999
    assert mini_limits["ai_agents"] == 5            # was 0
    assert mini_limits["voice_slots"] == 2          # was 0


# ── 4. Upgrade logic ──────────────────────────────────────────────────────

def test_is_upgrade_mini_to_high_still_works():
    """Existing Mini subscribers can upgrade to High."""
    from app.core.pricing_config import is_upgrade

    assert is_upgrade("mini", "high") is True
    assert is_upgrade("parwa", "high") is True


def test_is_upgrade_mini_to_parwa_is_not_an_upgrade():
    """Mini → Parwa is NOT an upgrade anymore (both normalize to parwa)."""
    from app.core.pricing_config import is_upgrade

    assert is_upgrade("mini", "parwa") is False  # same tier


# ── 5. Unknown names still raise ───────────────────────────────────────────

def test_unknown_variant_raises():
    import pytest
    from app.core.pricing_config import normalize_variant_name

    with pytest.raises(ValueError):
        normalize_variant_name("enterprise")
    with pytest.raises(ValueError):
        normalize_variant_name("")


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v", "--noconftest"]))
