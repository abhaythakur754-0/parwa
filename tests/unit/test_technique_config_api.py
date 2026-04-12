"""
Tests for Per-Tenant Technique Configuration API (SG-17).

Covers:
- TechniqueConfigStore unit tests (BC-001, BC-008)
- API endpoint tests via FastAPI TestClient
- BC-009: Tier 1 techniques cannot be disabled
"""

import os

# Set test env BEFORE any app imports
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only_not_prod"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_not_prod"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

import threading
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from backend.app.api.technique_config import (
    TechniqueConfigStore,
    UpdateTechniqueConfigRequest,
    router as technique_config_router,
)
from backend.app.core.technique_router import (
    TechniqueID,
    TechniqueTier,
    TECHNIQUE_REGISTRY,
)


# ── Helpers ─────────────────────────────────────────────────────────


def _fresh_store() -> TechniqueConfigStore:
    """Create a fresh TechniqueConfigStore for isolation."""
    return TechniqueConfigStore()


def _fresh_app() -> FastAPI:
    """Create a minimal FastAPI app with only the technique_config router."""
    app = FastAPI()
    app.include_router(technique_config_router)
    return app


def _fresh_client() -> TestClient:
    """Create a TestClient with a fresh app."""
    return TestClient(_fresh_app(), raise_server_exceptions=False)


TIER_1_IDS = {
    t.value for t in TechniqueID if TECHNIQUE_REGISTRY[t].tier == TechniqueTier.TIER_1
}
TIER_2_IDS = {
    t.value for t in TechniqueID if TECHNIQUE_REGISTRY[t].tier == TechniqueTier.TIER_2
}
TIER_3_IDS = {
    t.value for t in TechniqueID if TECHNIQUE_REGISTRY[t].tier == TechniqueTier.TIER_3
}


# ════════════════════════════════════════════════════════════════════
# TechniqueConfigStore Tests
# ════════════════════════════════════════════════════════════════════


class TestTechniqueConfigStore:
    """Unit tests for the TechniqueConfigStore in-memory store."""

    def test_default_config_all_enabled(self):
        """New company has all techniques enabled by default."""
        store = _fresh_store()
        for tid in TechniqueID:
            config = store.get_config("company_new", tid.value)
            assert config["enabled"] is True
            assert config["config_overrides"] == {}
            assert config["updated_at"] is None

    def test_set_config_enable(self):
        """Enabling a technique stores the correct config."""
        store = _fresh_store()
        result = store.set_config("co1", "crp", enabled=True)
        assert result["enabled"] is True
        assert result["updated_at"] is not None

        # Verify via get
        got = store.get_config("co1", "crp")
        assert got["enabled"] is True
        assert got["updated_at"] is not None

    def test_set_config_disable(self):
        """Disabling a technique stores enabled=False."""
        store = _fresh_store()
        result = store.set_config("co1", "chain_of_thought", enabled=False)
        assert result["enabled"] is False

        got = store.get_config("co1", "chain_of_thought")
        assert got["enabled"] is False

    def test_set_config_with_overrides(self):
        """Setting config with overrides stores them correctly."""
        store = _fresh_store()
        overrides = {"temperature": 0.7, "max_tokens": 500}
        result = store.set_config(
            "co1", "react", enabled=True, overrides=overrides,
        )
        assert result["config_overrides"] == overrides

        got = store.get_config("co1", "react")
        assert got["config_overrides"] == overrides

    def test_get_config_nonexistent_company(self):
        """Returns defaults for an unknown company."""
        store = _fresh_store()
        config = store.get_config("ghost_co", "crp")
        assert config["enabled"] is True
        assert config["config_overrides"] == {}
        assert config["updated_at"] is None

    def test_get_config_nonexistent_technique(self):
        """Returns defaults for an unknown technique within a known company."""
        store = _fresh_store()
        store.set_config("co1", "crp", enabled=False)
        # A technique that was never set should return defaults
        config = store.get_config("co1", "chain_of_thought")
        assert config["enabled"] is True
        assert config["updated_at"] is None

    def test_list_configs_includes_all_techniques(self):
        """list_configs returns entries for every technique in TECHNIQUE_REGISTRY."""
        store = _fresh_store()
        configs = store.list_configs("co1")
        returned_ids = {c["technique_id"] for c in configs}
        expected_ids = {t.value for t in TechniqueID}
        assert returned_ids == expected_ids

    def test_list_configs_applies_overrides(self):
        """Stored overrides show in list output."""
        store = _fresh_store()
        store.set_config("co1", "react", enabled=False)
        store.set_config("co1", "crp", enabled=True, overrides={"mode": "strict"})

        configs = store.list_configs("co1")
        react_cfg = next(c for c in configs if c["technique_id"] == "react")
        assert react_cfg["enabled"] is False

        crp_cfg = next(c for c in configs if c["technique_id"] == "crp")
        assert crp_cfg["enabled"] is True
        assert crp_cfg["config_overrides"] == {"mode": "strict"}

    def test_reset_company(self):
        """reset_company removes all configs for a company."""
        store = _fresh_store()
        store.set_config("co1", "crp", enabled=False)
        store.set_config("co1", "react", enabled=False, overrides={"k": "v"})

        store.reset_company("co1")

        # After reset, should get defaults
        crp = store.get_config("co1", "crp")
        assert crp["enabled"] is True
        assert crp["updated_at"] is None

        react = store.get_config("co1", "react")
        assert react["enabled"] is True
        assert react["config_overrides"] == {}

    def test_thread_safety(self):
        """Concurrent set_config calls don't crash (BC-001 thread safety)."""
        store = _fresh_store()
        errors = []

        def writer(thread_id: int):
            try:
                for i in range(50):
                    tid = list(TechniqueID)[i % len(list(TechniqueID))]
                    store.set_config(
                        f"co_{thread_id}",
                        tid.value,
                        enabled=(i % 2 == 0),
                        overrides={"thread": thread_id, "iter": i},
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(i,))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"

    def test_store_never_crashes_on_exception(self):
        """BC-008: Store methods never crash even on bad input."""
        store = _fresh_store()
        # These should all return safely, never raise
        result = store.get_config("", "")
        assert "enabled" in result

        result = store.set_config("", "", True, overrides=None)
        assert "enabled" in result

        result = store.list_configs("")
        assert isinstance(result, list)

        # Calling reset with empty string should not crash
        store.reset_company("")

        # Monkey-patch _configs to force an exception inside the lock
        original = store._configs
        store._configs = None  # type: ignore[assignment]
        try:
            result = store.get_config("x", "y")
            assert "enabled" in result
            result = store.set_config("x", "y", False)
            assert "enabled" in result
            result = store.list_configs("x")
            assert isinstance(result, list)
            store.reset_company("x")  # Should not crash
        finally:
            store._configs = original


# ════════════════════════════════════════════════════════════════════
# API Endpoint Tests
# ════════════════════════════════════════════════════════════════════


class TestAPIListConfigs:
    """GET /api/techniques/config — list all technique configs."""

    def test_list_configs_success(self):
        """GET with company_id returns all techniques."""
        client = _fresh_client()
        resp = client.get(
            "/api/techniques/config",
            params={"company_id": "co1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_id"] == "co1"
        assert data["total"] == len(TechniqueID)
        returned_ids = {t["technique_id"] for t in data["techniques"]}
        expected_ids = {t.value for t in TechniqueID}
        assert returned_ids == expected_ids

    def test_list_configs_filter_by_tier(self):
        """Filter with variant_type=tier_1 returns only Tier 1 techniques."""
        client = _fresh_client()
        resp = client.get(
            "/api/techniques/config",
            params={"company_id": "co1", "variant_type": "tier_1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for t in data["techniques"]:
            assert t["tier"] == "tier_1"
        assert data["total"] == len(TIER_1_IDS)

    def test_list_configs_invalid_tier_filter(self):
        """Bad variant_type returns 400."""
        client = _fresh_client()
        resp = client.get(
            "/api/techniques/config",
            params={"company_id": "co1", "variant_type": "tier_99"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data or "detail" in data

    def test_list_configs_missing_company_id(self):
        """Missing company_id returns 422 (query param validation)."""
        client = _fresh_client()
        resp = client.get("/api/techniques/config")
        assert resp.status_code == 422


class TestAPIGetConfig:
    """GET /api/techniques/config/{technique_id} — get single config."""

    def test_get_config_success(self):
        """GET a valid technique returns its config."""
        client = _fresh_client()
        resp = client.get(
            "/api/techniques/config/crp",
            params={"company_id": "co1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["technique_id"] == "crp"
        assert data["tier"] == "tier_1"
        assert data["enabled"] is True

    def test_get_config_not_found(self):
        """Invalid technique_id returns 404."""
        client = _fresh_client()
        resp = client.get(
            "/api/techniques/config/nonexistent_technique",
            params={"company_id": "co1"},
        )
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data or "detail" in data


class TestAPIUpdateConfig:
    """PUT /api/techniques/config/{technique_id} — enable/disable technique."""

    def test_update_config_enable(self):
        """PUT enable a technique succeeds."""
        client = _fresh_client()
        resp = client.put(
            "/api/techniques/config/react",
            json={
                "company_id": "co1",
                "enabled": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["technique_id"] == "react"
        assert data["enabled"] is True

    def test_update_config_disable(self):
        """PUT disable a Tier 2 technique succeeds."""
        client = _fresh_client()
        resp = client.put(
            "/api/techniques/config/chain_of_thought",
            json={
                "company_id": "co1",
                "enabled": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["technique_id"] == "chain_of_thought"
        assert data["enabled"] is False

    def test_update_config_tier_1_locked(self):
        """PUT disable Tier 1 (CRP) returns 403 — BC-009 enforcement."""
        client = _fresh_client()
        resp = client.put(
            "/api/techniques/config/crp",
            json={
                "company_id": "co1",
                "enabled": False,
            },
        )
        assert resp.status_code == 403
        data = resp.json()
        assert "Tier 1 techniques cannot be disabled" in data.get("error", "")
        # Detail should list the Tier 1 technique IDs
        detail = data.get("detail", "")
        for t1_id in TIER_1_IDS:
            assert t1_id in detail

    def test_update_config_tier_1_clara_locked(self):
        """PUT disable Tier 1 (CLARA) also returns 403."""
        client = _fresh_client()
        resp = client.put(
            "/api/techniques/config/clara",
            json={
                "company_id": "co1",
                "enabled": False,
            },
        )
        assert resp.status_code == 403

    def test_update_config_tier_1_gsd_locked(self):
        """PUT disable Tier 1 (GSD) also returns 403."""
        client = _fresh_client()
        resp = client.put(
            "/api/techniques/config/gsd",
            json={
                "company_id": "co1",
                "enabled": False,
            },
        )
        assert resp.status_code == 403

    def test_update_config_tier_1_enable_allowed(self):
        """PUT enable a Tier 1 technique is allowed (idempotent)."""
        client = _fresh_client()
        resp = client.put(
            "/api/techniques/config/crp",
            json={
                "company_id": "co1",
                "enabled": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True

    def test_update_config_with_overrides(self):
        """PUT with config_overrides stores them."""
        client = _fresh_client()
        overrides = {"temperature": 0.5, "max_tokens": 100}
        resp = client.put(
            "/api/techniques/config/react",
            json={
                "company_id": "co1",
                "enabled": True,
                "config_overrides": overrides,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["config_overrides"] == overrides

    def test_update_config_invalid_technique(self):
        """PUT with invalid technique_id returns 404."""
        client = _fresh_client()
        resp = client.put(
            "/api/techniques/config/invalid_technique",
            json={
                "company_id": "co1",
                "enabled": True,
            },
        )
        assert resp.status_code == 404

    def test_update_config_empty_company_id(self):
        """PUT with whitespace-only company_id returns 400."""
        client = _fresh_client()
        resp = client.put(
            "/api/techniques/config/react",
            json={
                "company_id": "   ",
                "enabled": True,
            },
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "company_id" in str(data).lower()

    def test_update_config_tier_3_disable_allowed(self):
        """PUT disable a Tier 3 technique succeeds."""
        client = _fresh_client()
        resp = client.put(
            "/api/techniques/config/gst",
            json={
                "company_id": "co1",
                "enabled": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False


class TestAPINeverCrashes:
    """BC-008: API never crashes — even garbage input returns a response."""

    def test_api_never_crashes(self):
        """Even garbage input returns a valid HTTP response (no 500)."""
        client = _fresh_client()

        # Garbage technique_id
        resp = client.get(
            "/api/techniques/config/<<<garbage>>>",
            params={"company_id": "co1"},
        )
        assert resp.status_code in (400, 404)

        # Missing params
        resp = client.get("/api/techniques/config/crp")
        assert resp.status_code in (400, 422)

        # Invalid JSON body
        resp = client.put(
            "/api/techniques/config/crp",
            content=b"not json at all {{{",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code in (400, 422)

        # Valid JSON but missing required fields
        resp = client.put(
            "/api/techniques/config/crp",
            json={"enabled": True},
        )
        # Should be 422 (missing company_id)
        assert resp.status_code in (400, 422)

        # Empty JSON
        resp = client.put(
            "/api/techniques/config/crp",
            json={},
        )
        assert resp.status_code in (400, 422)
