"""Ensure removed Mini tiers never become the default for new tenants."""

import pytest
pytest.importorskip("langgraph")

from app.core.parwa_pipeline.nodes.node_2_smart_route import (
    _load_tenant_variants,
    clear_test_registry,
    set_test_variant,
)


def test_legacy_mini_test_variant_is_upgraded_to_parwa():
    clear_test_registry()
    try:
        set_test_variant("company-legacy", "mini", quota_total=100)
        result = _load_tenant_variants("company-legacy")
        assert result["available_tiers"] == ["parwa"]
        assert result["highest_tier_short"] == "parwa"
        assert result["highest_tier_db"] == "parwa"
    finally:
        clear_test_registry()


def test_unknown_tenant_tier_fallback_is_parwa(monkeypatch):
    import database.base

    def unavailable_session():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(database.base, "SessionLocal", unavailable_session)
    result = _load_tenant_variants("company-without-subscription")
    assert result["available_tiers"] == ["parwa"]
    assert result["highest_tier_short"] == "parwa"
    assert result["highest_tier_db"] == "parwa"
