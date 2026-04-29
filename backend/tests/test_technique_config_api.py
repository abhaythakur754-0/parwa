"""
Tests for Per-Tenant Technique Configuration Admin API (SG-17)

Tests for:
- TechniqueConfigStore CRUD
- GET /config endpoint
- PUT /config/{technique_id} endpoint
- GET /config/{technique_id} endpoint
- Validation (missing company_id, invalid technique_id)
- Company isolation
- Default enabled state
- Error handling

Minimum 40 tests.
"""

import importlib.util
import sys
from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import technique_router directly (no problematic deps)
from app.core.technique_router import (
    TechniqueID,
    TECHNIQUE_REGISTRY,
)

# Load technique_config module directly to avoid app.api.__init__
# which imports auth/sqlalchemy/etc.
_module_path = sys.modules.get("app.core.technique_metrics_pipeline")
if _module_path is None:
    pass  # No dependency needed for import

_spec = importlib.util.spec_from_file_location(
    "app.api.technique_config",
    "/home/z/my-project/parwa/backend/app/api/technique_config.py",
)
_tc_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tc_mod)
sys.modules["app.api.technique_config"] = _tc_mod

TechniqueConfigStore = _tc_mod.TechniqueConfigStore
UpdateTechniqueConfigRequest = _tc_mod.UpdateTechniqueConfigRequest
router = _tc_mod.router
get_config_store = _tc_mod.get_config_store


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def store() -> Generator[TechniqueConfigStore, None, None]:
    """Provide a fresh TechniqueConfigStore for each test."""
    s = TechniqueConfigStore()
    yield s


@pytest.fixture(autouse=True)
def _reset_store():
    """Reset global technique config store before every test."""
    _tc_mod._config_store._configs.clear()
    yield
    _tc_mod._config_store._configs.clear()


@pytest.fixture
def app() -> Generator[FastAPI, None, None]:
    """Provide a fresh FastAPI app with the technique_config router."""

    application = FastAPI()
    application.include_router(router)
    yield application

    # Cleanup handled by autouse fixture


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Provide a TestClient for the app."""
    with TestClient(app) as c:
        yield c


# ════════════════════════════════════════════════════════════════════
# TechniqueConfigStore Tests
# ════════════════════════════════════════════════════════════════════


class TestTechniqueConfigStore:

    def test_get_config_default_enabled(self, store):
        """Test default config has technique enabled."""
        config = store.get_config("company_1", "clara")
        assert config["enabled"] is True
        assert config["config_overrides"] == {}
        assert config["updated_at"] is None

    def test_get_config_nonexistent_company(self, store):
        """Test getting config for nonexistent company returns default."""
        config = store.get_config("nonexistent", "clara")
        assert config["enabled"] is True

    def test_get_config_nonexistent_technique(self, store):
        """Test getting config for any technique returns default."""
        config = store.get_config("company_1", "nonexistent_tech")
        assert config["enabled"] is True

    def test_set_config_enables_technique(self, store):
        """Test setting config with enabled=True."""
        config = store.set_config(
            "company_1", "clara", enabled=True,
        )
        assert config["enabled"] is True
        assert config["updated_at"] is not None

    def test_set_config_disables_technique(self, store):
        """Test setting config with enabled=False."""
        config = store.set_config(
            "company_1", "clara", enabled=False,
        )
        assert config["enabled"] is False

    def test_set_config_with_overrides(self, store):
        """Test setting config with overrides."""
        overrides = {"max_tokens": 5000, "temperature": 0.8}
        config = store.set_config(
            "company_1", "clara", enabled=True,
            overrides=overrides,
        )
        assert config["config_overrides"] == overrides

    def test_set_config_empty_overrides(self, store):
        """Test setting config with empty overrides."""
        config = store.set_config(
            "company_1", "clara", enabled=True,
            overrides={},
        )
        assert config["config_overrides"] == {}

    def test_set_config_none_overrides(self, store):
        """Test setting config with None overrides defaults to {}."""
        config = store.set_config(
            "company_1", "clara", enabled=True,
            overrides=None,
        )
        assert config["config_overrides"] == {}

    def test_set_then_get_roundtrip(self, store):
        """Test set then get returns same values."""
        store.set_config(
            "company_1", "clara", enabled=False,
            overrides={"key": "value"},
        )
        config = store.get_config("company_1", "clara")
        assert config["enabled"] is False
        assert config["config_overrides"] == {"key": "value"}
        assert config["updated_at"] is not None

    def test_set_overwrites_previous(self, store):
        """Test setting config twice overwrites first."""
        store.set_config("company_1", "clara", enabled=True)
        store.set_config(
            "company_1", "clara", enabled=False,
            overrides={"new": "data"},
        )
        config = store.get_config("company_1", "clara")
        assert config["enabled"] is False
        assert config["config_overrides"] == {"new": "data"}

    def test_list_configs_returns_all_techniques(self, store):
        """Test list_configs returns all techniques from registry."""
        configs = store.list_configs("company_1")
        assert len(configs) == len(TECHNIQUE_REGISTRY)
        technique_ids = {c["technique_id"] for c in configs}
        for tid in TechniqueID:
            assert tid.value in technique_ids

    def test_list_configs_all_enabled_by_default(self, store):
        """Test list_configs shows all enabled by default."""
        configs = store.list_configs("company_1")
        for c in configs:
            assert c["enabled"] is True

    def test_list_configs_after_set_disabled(self, store):
        """Test list_configs reflects disabled technique."""
        store.set_config("company_1", "clara", enabled=False)
        configs = store.list_configs("company_1")
        clara_config = next(
            c for c in configs if c["technique_id"] == "clara"
        )
        assert clara_config["enabled"] is False
        # Others should still be enabled
        for c in configs:
            if c["technique_id"] != "clara":
                assert c["enabled"] is True

    def test_list_configs_includes_registry_info(self, store):
        """Test list_configs includes tier, description, etc."""
        configs = store.list_configs("company_1")
        clara_config = next(
            c for c in configs if c["technique_id"] == "clara"
        )
        assert clara_config["tier"] == "tier_1"
        assert clara_config["description"] != ""
        assert clara_config["estimated_tokens"] > 0
        assert clara_config["time_budget_ms"] > 0

    def test_list_configs_empty_company(self, store):
        """Test list_configs for company with no configs."""
        configs = store.list_configs("new_company")
        assert len(configs) == len(TECHNIQUE_REGISTRY)

    def test_reset_company_clears_configs(self, store):
        """Test reset_company removes all configs."""
        store.set_config("company_1", "clara", enabled=False)
        store.set_config("company_1", "gsd", enabled=False)
        store.reset_company("company_1")
        config = store.get_config("company_1", "clara")
        assert config["enabled"] is True  # Back to default

    def test_reset_nonexistent_company(self, store):
        """Test reset for nonexistent company doesn't crash."""
        store.reset_company("nonexistent")  # No crash

    def test_company_isolation(self, store):
        """Test configs are isolated between companies."""
        store.set_config("company_a", "clara", enabled=False)
        store.set_config("company_b", "clara", enabled=True)

        config_a = store.get_config("company_a", "clara")
        config_b = store.get_config("company_b", "clara")

        assert config_a["enabled"] is False
        assert config_b["enabled"] is True

    def test_get_config_returns_copy(self, store):
        """Test get_config returns a copy, not a reference."""
        store.set_config(
            "company_1", "clara", enabled=False,
            overrides={"k": "v"},
        )
        config = store.get_config("company_1", "clara")
        config["enabled"] = True
        config["config_overrides"]["new"] = "key"

        # Original should be unchanged
        original = store.get_config("company_1", "clara")
        assert original["enabled"] is False
        assert "new" not in original["config_overrides"]

    def test_list_configs_filter_by_tier(self):
        """Test listing configs can be filtered by tier."""
        store = TechniqueConfigStore()
        all_configs = store.list_configs("company_1")
        tier_1_configs = [
            c for c in all_configs if c["tier"] == "tier_1"
        ]
        assert len(tier_1_configs) == 3  # clara, crp, gsd


# ════════════════════════════════════════════════════════════════════
# GET /api/techniques/config Tests
# ════════════════════════════════════════════════════════════════════


class TestGetTechniqueConfigsEndpoint:

    def test_list_configs_success(self, client):
        """Test GET /api/techniques/config returns all techniques."""
        response = client.get(
            "/api/techniques/config",
            params={"company_id": "company_1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["company_id"] == "company_1"
        assert data["total"] == len(TECHNIQUE_REGISTRY)
        assert len(data["techniques"]) == len(TECHNIQUE_REGISTRY)

    def test_list_configs_missing_company_id(self, client):
        """Test GET /api/techniques/config without company_id."""
        response = client.get("/api/techniques/config")
        assert response.status_code == 422  # Validation error

    def test_list_configs_empty_company_id(self, client):
        """Test GET /api/techniques/config with empty company_id."""
        response = client.get(
            "/api/techniques/config",
            params={"company_id": ""},
        )
        assert response.status_code == 422  # Validation error

    def test_list_configs_all_enabled_by_default(self, client):
        """Test all techniques enabled by default in API response."""
        response = client.get(
            "/api/techniques/config",
            params={"company_id": "new_company"},
        )
        assert response.status_code == 200
        data = response.json()
        for t in data["techniques"]:
            assert t["enabled"] is True

    def test_list_configs_with_variant_type_filter(self, client):
        """Test filtering by tier_1 variant_type."""
        response = client.get(
            "/api/techniques/config",
            params={
                "company_id": "company_1",
                "variant_type": "tier_1",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3  # clara, crp, gsd
        for t in data["techniques"]:
            assert t["tier"] == "tier_1"

    def test_list_configs_with_tier_2_filter(self, client):
        """Test filtering by tier_2 variant_type."""
        response = client.get(
            "/api/techniques/config",
            params={
                "company_id": "company_1",
                "variant_type": "tier_2",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        for t in data["techniques"]:
            assert t["tier"] == "tier_2"

    def test_list_configs_with_tier_3_filter(self, client):
        """Test filtering by tier_3 variant_type."""
        response = client.get(
            "/api/techniques/config",
            params={
                "company_id": "company_1",
                "variant_type": "tier_3",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 6
        for t in data["techniques"]:
            assert t["tier"] == "tier_3"

    def test_list_configs_invalid_variant_type(self, client):
        """Test invalid variant_type returns error."""
        response = client.get(
            "/api/techniques/config",
            params={
                "company_id": "company_1",
                "variant_type": "invalid_tier",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_list_configs_reflects_disabled_technique(self, client):
        """Test API reflects previously disabled technique."""
        # First disable a technique via the store
        store = get_config_store()
        store.set_config("company_1", "clara", enabled=False)

        response = client.get(
            "/api/techniques/config",
            params={"company_id": "company_1"},
        )
        assert response.status_code == 200
        data = response.json()
        clara = next(
            t for t in data["techniques"]
            if t["technique_id"] == "clara"
        )
        assert clara["enabled"] is False

    def test_list_configs_response_has_required_fields(self, client):
        """Test response includes all required fields."""
        response = client.get(
            "/api/techniques/config",
            params={"company_id": "company_1"},
        )
        data = response.json()
        technique = data["techniques"][0]
        assert "technique_id" in technique
        assert "technique_name" in technique
        assert "tier" in technique
        assert "description" in technique
        assert "enabled" in technique
        assert "config_overrides" in technique
        assert "estimated_tokens" in technique
        assert "time_budget_ms" in technique


# ════════════════════════════════════════════════════════════════════
# PUT /api/techniques/config/{technique_id} Tests
# ════════════════════════════════════════════════════════════════════


class TestUpdateTechniqueConfigEndpoint:

    def test_update_disable_technique(self, client):
        """Test PUT disables a technique."""
        response = client.put(
            "/api/techniques/config/chain_of_thought",
            json={
                "company_id": "company_1",
                "enabled": False,
                "config_overrides": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["technique_id"] == "chain_of_thought"

    def test_update_enable_technique(self, client):
        """Test PUT enables a technique."""
        # First disable
        store = get_config_store()
        store.set_config("company_1", "chain_of_thought", enabled=False)

        response = client.put(
            "/api/techniques/config/chain_of_thought",
            json={
                "company_id": "company_1",
                "enabled": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True

    def test_update_with_config_overrides(self, client):
        """Test PUT with config_overrides."""
        response = client.put(
            "/api/techniques/config/chain_of_thought",
            json={
                "company_id": "company_1",
                "enabled": True,
                "config_overrides": {
                    "custom_threshold": 0.95,
                    "max_tokens": 5000,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["config_overrides"]["custom_threshold"] == 0.95
        assert data["config_overrides"]["max_tokens"] == 5000

    def test_update_invalid_technique_id(self, client):
        """Test PUT with invalid technique_id returns error."""
        response = client.put(
            "/api/techniques/config/nonexistent",
            json={
                "company_id": "company_1",
                "enabled": True,
            },
        )
        assert response.status_code == 404
        data = response.json()
        assert "error" in data

    def test_update_empty_company_id(self, client):
        """Test PUT with empty company_id returns error."""
        response = client.put(
            "/api/techniques/config/clara",
            json={
                "company_id": "",
                "enabled": True,
            },
        )
        assert response.status_code == 422  # Validation error

    def test_update_missing_company_id(self, client):
        """Test PUT without company_id returns validation error."""
        response = client.put(
            "/api/techniques/config/clara",
            json={"enabled": True},
        )
        assert response.status_code == 422

    def test_update_whitespace_company_id(self, client):
        """Test PUT with whitespace-only company_id."""
        response = client.put(
            "/api/techniques/config/clara",
            json={
                "company_id": "   ",
                "enabled": True,
            },
        )
        # The body validation allows whitespace (min_length=1),
        # but the endpoint should return error
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_update_returns_updated_at(self, client):
        """Test PUT response includes updated_at timestamp."""
        response = client.put(
            "/api/techniques/config/chain_of_thought",
            json={
                "company_id": "company_1",
                "enabled": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["updated_at"] is not None

    def test_update_returns_technique_info(self, client):
        """Test PUT response includes technique registry info."""
        response = client.put(
            "/api/techniques/config/clara",
            json={
                "company_id": "company_1",
                "enabled": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "tier_1"
        assert data["description"] != ""
        assert data["estimated_tokens"] > 0

    def test_update_default_enabled_true(self, client):
        """Test PUT defaults enabled to True if not provided."""
        response = client.put(
            "/api/techniques/config/clara",
            json={"company_id": "company_1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True

    def test_update_persists_across_get(self, client):
        """Test PUT update is reflected in GET."""
        client.put(
            "/api/techniques/config/chain_of_thought",
            json={
                "company_id": "company_1",
                "enabled": False,
            },
        )
        response = client.get(
            "/api/techniques/config/chain_of_thought",
            params={"company_id": "company_1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False


# ════════════════════════════════════════════════════════════════════
# GET /api/techniques/config/{technique_id} Tests
# ════════════════════════════════════════════════════════════════════


class TestGetTechniqueConfigEndpoint:

    def test_get_specific_technique(self, client):
        """Test GET specific technique config."""
        response = client.get(
            "/api/techniques/config/clara",
            params={"company_id": "company_1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["technique_id"] == "clara"
        assert data["enabled"] is True

    def test_get_specific_technique_default_enabled(self, client):
        """Test GET specific technique is enabled by default."""
        response = client.get(
            "/api/techniques/config/gsd",
            params={"company_id": "new_company"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True

    def test_get_specific_technique_invalid_id(self, client):
        """Test GET with invalid technique_id."""
        response = client.get(
            "/api/techniques/config/nonexistent",
            params={"company_id": "company_1"},
        )
        assert response.status_code == 404
        data = response.json()
        assert "error" in data

    def test_get_specific_technique_missing_company_id(self, client):
        """Test GET specific technique without company_id."""
        response = client.get("/api/techniques/config/clara")
        assert response.status_code == 422  # Validation error

    def test_get_specific_technique_empty_company_id(self, client):
        """Test GET specific technique with empty company_id."""
        response = client.get(
            "/api/techniques/config/clara",
            params={"company_id": ""},
        )
        assert response.status_code == 422

    def test_get_specific_reflects_update(self, client):
        """Test GET reflects previous PUT update."""
        client.put(
            "/api/techniques/config/chain_of_thought",
            json={
                "company_id": "company_1",
                "enabled": False,
                "config_overrides": {"test": True},
            },
        )
        response = client.get(
            "/api/techniques/config/chain_of_thought",
            params={"company_id": "company_1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["config_overrides"] == {"test": True}

    def test_get_specific_returns_registry_info(self, client):
        """Test GET specific returns technique registry info."""
        response = client.get(
            "/api/techniques/config/chain_of_thought",
            params={"company_id": "company_1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "tier_2"
        assert data["description"] != ""
        assert data["estimated_tokens"] > 0
        assert data["time_budget_ms"] > 0

    def test_get_specific_default_overrides_empty(self, client):
        """Test GET specific has empty overrides by default."""
        response = client.get(
            "/api/techniques/config/clara",
            params={"company_id": "new_company"},
        )
        data = response.json()
        assert data["config_overrides"] == {}

    def test_get_specific_updated_at_none_by_default(self, client):
        """Test GET specific has None updated_at by default."""
        response = client.get(
            "/api/techniques/config/clara",
            params={"company_id": "new_company"},
        )
        data = response.json()
        assert data["updated_at"] is None


# ════════════════════════════════════════════════════════════════════
# Company Isolation API Tests
# ════════════════════════════════════════════════════════════════════


class TestCompanyIsolationAPI:

    def test_company_isolation_in_list(self, client):
        """Test list configs is company-isolated."""
        # Disable clara for company_a
        client.put(
            "/api/techniques/config/clara",
            json={
                "company_id": "company_a",
                "enabled": False,
            },
        )

        # company_b should still have clara enabled
        response = client.get(
            "/api/techniques/config",
            params={"company_id": "company_b"},
        )
        data = response.json()
        clara = next(
            t for t in data["techniques"]
            if t["technique_id"] == "clara"
        )
        assert clara["enabled"] is True

    def test_company_isolation_in_get(self, client):
        """Test get specific config is company-isolated."""
        client.put(
            "/api/techniques/config/chain_of_thought",
            json={
                "company_id": "company_a",
                "enabled": False,
                "config_overrides": {"a": 1},
            },
        )

        response_a = client.get(
            "/api/techniques/config/chain_of_thought",
            params={"company_id": "company_a"},
        )
        response_b = client.get(
            "/api/techniques/config/chain_of_thought",
            params={"company_id": "company_b"},
        )

        assert response_a.json()["enabled"] is False
        assert response_b.json()["enabled"] is True

    def test_different_companies_different_configs(self, client):
        """Test multiple companies have independent configs."""
        client.put(
            "/api/techniques/config/chain_of_thought",
            json={
                "company_id": "a",
                "enabled": False,
            },
        )
        client.put(
            "/api/techniques/config/reverse_thinking",
            json={
                "company_id": "b",
                "enabled": False,
            },
        )

        list_a = client.get(
            "/api/techniques/config",
            params={"company_id": "a"},
        ).json()
        list_b = client.get(
            "/api/techniques/config",
            params={"company_id": "b"},
        ).json()

        cot_a = next(
            t for t in list_a["techniques"]
            if t["technique_id"] == "chain_of_thought"
        )
        rt_b = next(
            t for t in list_b["techniques"]
            if t["technique_id"] == "reverse_thinking"
        )

        assert cot_a["enabled"] is False
        rt_b_enabled = next(
            t for t in list_a["techniques"]
            if t["technique_id"] == "reverse_thinking"
        )
        assert rt_b_enabled["enabled"] is True
        assert rt_b["enabled"] is False


# ════════════════════════════════════════════════════════════════════
# Error Handling / Edge Cases
# ════════════════════════════════════════════════════════════════════


class TestErrorHandling:

    def test_put_with_extra_fields_ignored(self, client):
        """Test PUT with extra fields doesn't crash."""
        response = client.put(
            "/api/techniques/config/clara",
            json={
                "company_id": "company_1",
                "enabled": True,
                "extra_field": "ignored",
            },
        )
        # Extra fields are ignored by Pydantic
        assert response.status_code == 200

    def test_list_all_techniques_in_registry(self, client):
        """Test list returns exactly all techniques in registry."""
        response = client.get(
            "/api/techniques/config",
            params={"company_id": "company_1"},
        )
        data = response.json()
        assert data["total"] == len(TECHNIQUE_REGISTRY)
        returned_ids = {t["technique_id"] for t in data["techniques"]}
        for tid in TechniqueID:
            assert tid.value in returned_ids

    def test_update_all_technique_ids(self, client):
        """Test updating every T2/T3 technique_id works (T1 cannot be disabled)."""
        tier_1 = {TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD}
        for tid in TechniqueID:
            if tid in tier_1:
                continue  # T1 techniques cannot be disabled per BC-009
            response = client.put(
                f"/api/techniques/config/{tid.value}",
                json={
                    "company_id": "company_1",
                    "enabled": False,
                },
            )
            assert response.status_code == 200

    def test_get_all_technique_ids(self, client):
        """Test getting every technique_id in the registry works."""
        for tid in TechniqueID:
            response = client.get(
                f"/api/techniques/config/{tid.value}",
                params={"company_id": "company_1"},
            )
            assert response.status_code == 200

    def test_consecutive_updates_same_technique(self, client):
        """Test consecutive updates to same technique."""
        for i in range(5):
            enabled = i % 2 == 0
            response = client.put(
                "/api/techniques/config/chain_of_thought",
                json={
                    "company_id": "company_1",
                    "enabled": enabled,
                },
            )
            assert response.status_code == 200
            assert response.json()["enabled"] == enabled

    def test_update_then_list_then_update_then_get(self, client):
        """Test full CRUD cycle."""
        # Update
        client.put(
            "/api/techniques/config/chain_of_thought",
            json={
                "company_id": "company_1",
                "enabled": False,
                "config_overrides": {"key": "v1"},
            },
        )
        # List
        list_resp = client.get(
            "/api/techniques/config",
            params={"company_id": "company_1"},
        )
        cot = next(
            t for t in list_resp.json()["techniques"]
            if t["technique_id"] == "chain_of_thought"
        )
        assert cot["enabled"] is False
        # Update again
        client.put(
            "/api/techniques/config/chain_of_thought",
            json={
                "company_id": "company_1",
                "enabled": True,
                "config_overrides": {"key": "v2"},
            },
        )
        # Get
        get_resp = client.get(
            "/api/techniques/config/chain_of_thought",
            params={"company_id": "company_1"},
        )
        data = get_resp.json()
        assert data["enabled"] is True
        assert data["config_overrides"]["key"] == "v2"
