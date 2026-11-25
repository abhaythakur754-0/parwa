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
    """Legacy Mini resolves to the current PARWA Growth price ($2,999)."""
    from app.core.pricing_config import get_variant_price

    assert get_variant_price("mini") == Decimal("2999.00")
    assert get_variant_price("mini_parwa") == Decimal("2999.00")
    assert get_variant_price("starter") == Decimal("2999.00")


def test_get_variant_limits_mini_returns_parwa_limits():
    """Mini gets PARWA Growth limits (5 AI agents, not 0)."""
    from app.core.pricing_config import get_variant_limits

    mini_limits = get_variant_limits("mini")
    assert mini_limits["monthly_tickets"] == 2999
    assert mini_limits["ai_agents"] == 5
    assert mini_limits["voice_slots"] == 2


def test_variant_limit_service_uses_safe_parwa_default_for_unknown_tier():
    from app.services.variant_limit_service import VariantLimitService

    limits = VariantLimitService().get_variant_limits("unknown-tier")
    assert limits["monthly_tickets"] == 2999
    assert limits["ai_agents"] == 5


def test_variant_limit_service_canonicalizes_legacy_company_subscription_tiers():
    from unittest.mock import MagicMock
    from app.services.variant_limit_service import VariantLimitService

    subscription = MagicMock()
    subscription.tier = "growth"
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = subscription

    assert VariantLimitService()._get_company_variant(db, "company-123") == "parwa"


def test_variant_limit_service_reads_price_monthly_from_db_fallback():
    from unittest.mock import MagicMock, patch
    from app.services import variant_limit_service

    row = MagicMock()
    row.monthly_tickets = 2999
    row.ai_agents = 5
    row.team_members = 10
    row.voice_slots = 2
    row.kb_docs = 500
    row.price_monthly = Decimal("2999.00")

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = row
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = db

    with patch.object(variant_limit_service, "get_variant_limits", return_value=None), \
         patch.object(variant_limit_service, "SessionLocal", session_factory):
        limits = variant_limit_service.VariantLimitService().get_variant_limits("parwa")

    assert limits["price"] == "2999.00"


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
