"""
HTTP-level Integration Tests for Shadow Mode API.

Uses FastAPI's TestClient to make actual HTTP requests to the
shadow mode router endpoints. Dependencies (auth, DB) are
overridden with mocks so no real JWT/SQLAlchemy stack is needed.

The router module is loaded via importlib to bypass app.api.__init__.py,
which would cascade into importing all API modules (auth, health, etc.)
that require sqlalchemy, jose, and other heavy dependencies.

Run with:
    cd /home/z/my-project/parwa/backend && python -m pytest tests/test_shadow_mode_http_integration.py -v
"""

from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════════
# BOOTSTRAP: Register mock modules BEFORE importing the router
# ═══════════════════════════════════════════════════════════════════

# ── Mock User class (replaces database.models.core.User) ──────────
# Must be a Pydantic BaseModel so FastAPI can resolve it as a
# dependency parameter type annotation.
from pydantic import BaseModel as _PydanticBaseModel


class MockUser(_PydanticBaseModel):
    """Simulates the SQLAlchemy User model used by deps.py.

    Inherits from Pydantic BaseModel so FastAPI can resolve it as
    a valid dependency parameter type when registering routes.
    """
    id: str = "test-user-001"
    company_id: str = "test-company-001"
    role: str = "admin"
    is_active: bool = True

    model_config = {"arbitrary_types_allowed": True}


# ── Pre-register mock modules that the router imports at top level ─

# 1. database.base (provides get_db)
if "database.base" not in sys.modules:
    _fake_db_base = types.ModuleType("database.base")
    _fake_db_base.get_db = lambda: None
    sys.modules["database.base"] = _fake_db_base

# 2. database.models.core (provides User) — MUST override the conftest
#    mock because conftest's _MockUser is a plain class, and FastAPI
#    requires Pydantic-compatible types for dependency annotations.
_db_core = sys.modules.get("database.models.core")
if _db_core is not None:
    # Override the User class in the existing module
    _db_core.User = MockUser
else:
    _fake_core = types.ModuleType("database.models.core")
    _fake_core.User = MockUser
    sys.modules["database.models.core"] = _fake_core

# 3. app.api.deps (provides require_roles, get_company_id, get_current_user)
if "app.api.deps" not in sys.modules:
    _fake_deps = types.ModuleType("app.api.deps")

    # NOTE: These must have NO parameters that FastAPI would try to
    # resolve from the request. get_company_id returns a plain string
    # and get_current_user returns a MockUser — both parameterless.
    def _fake_get_company_id() -> str:
        return "test-company-001"

    def _fake_get_current_user() -> MockUser:
        return MockUser()

    def _fake_require_roles(*roles: str):
        def checker() -> MockUser:
            return MockUser()
        return checker

    _fake_deps.get_company_id = _fake_get_company_id
    _fake_deps.get_current_user = _fake_get_current_user
    _fake_deps.require_roles = _fake_require_roles
    sys.modules["app.api.deps"] = _fake_deps

# 4. database.models.shadow_mode (lazy import inside endpoints)
if "database.models.shadow_mode" not in sys.modules:
    _fake_sm = types.ModuleType("database.models.shadow_mode")
    for _mn in ["ShadowModeConfig", "ShadowModeResult"]:
        setattr(_fake_sm, _mn, MagicMock(name=_mn))
    sys.modules["database.models.shadow_mode"] = _fake_sm

# 5. Ensure app.exceptions is importable (used by deps mock)
if "app.exceptions" not in sys.modules:
    # If the real module is available, it's already imported by conftest
    try:
        import app.exceptions  # noqa: F401
    except ImportError:
        _fake_exc = types.ModuleType("app.exceptions")

        class _ParwaBaseError(Exception):
            def __init__(self, message="Error", error_code="ERROR",
                         status_code=500, details=None):
                self.message = message
                self.error_code = error_code
                self.status_code = status_code
                self.details = details
                super().__init__(message)

        class _AuthorizationError(_ParwaBaseError):
            def __init__(self, message="Permission denied", details=None):
                super().__init__(
                    message=message,
                    error_code="AUTHORIZATION_ERROR",
                    status_code=403,
                    details=details,
                )

        _fake_exc.ParwaBaseError = _ParwaBaseError
        _fake_exc.AuthorizationError = _AuthorizationError
        sys.modules["app.exceptions"] = _fake_exc


# ── Now load the shadow_mode router module directly ───────────────

_SPEC = importlib.util.spec_from_file_location(
    "app.api.shadow_mode",
    "/home/z/my-project/parwa/backend/app/api/shadow_mode.py",
)
_shadow_mode_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_shadow_mode_mod)

# Extract the router object from the loaded module
ROUTER = _shadow_mode_mod.router

# Also extract the request model classes for reference
EnableShadowModeRequest = _shadow_mode_mod.EnableShadowModeRequest
DisableShadowModeRequest = _shadow_mode_mod.DisableShadowModeRequest
PromoteShadowModeRequest = _shadow_mode_mod.PromoteShadowModeRequest
HumanReviewRequest = _shadow_mode_mod.HumanReviewRequest

# Get the real deps module functions for dependency override keys
DEPS_MODULE = sys.modules["app.api.deps"]


# ═══════════════════════════════════════════════════════════════════
# MOCK SERVICE
# ═══════════════════════════════════════════════════════════════════

class MockShadowModeService:
    """In-memory mock of ShadowModeService that mimics real behaviour
    without any DB dependency."""

    def __init__(self) -> None:
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._comparisons: Dict[str, List[Dict[str, Any]]] = {}

    # ── Enable ────────────────────────────────────────────────────

    def enable_shadow_mode(
        self,
        company_id: str,
        live_variant: str,
        shadow_variant: str,
        sample_rate: float = 1.0,
        auto_graduation_threshold: float = 0.95,
        auto_graduation_window: int = 100,
        supervised_timeout_seconds: int = 300,
        auto_promote_to_supervised: bool = True,
        auto_promote_to_graduated: bool = False,
        live_instance_id: str = "",
        shadow_instance_id: str = "",
        user_id: str = "",
    ) -> Dict[str, Any]:
        VALID_VARIANT_TYPES = ("mini_parwa", "parwa", "parwa_high")
        VARIANT_RANKING = {"mini_parwa": 1, "parwa": 2, "parwa_high": 3}

        if live_variant not in VALID_VARIANT_TYPES:
            return {
                "success": False,
                "error": f"Invalid live_variant: {live_variant}. Must be one of {VALID_VARIANT_TYPES}",
            }
        if shadow_variant not in VALID_VARIANT_TYPES:
            return {
                "success": False,
                "error": f"Invalid shadow_variant: {shadow_variant}. Must be one of {VALID_VARIANT_TYPES}",
            }

        live_rank = VARIANT_RANKING.get(live_variant, 0)
        shadow_rank = VARIANT_RANKING.get(shadow_variant, 0)
        if shadow_rank <= live_rank:
            return {
                "success": False,
                "error": f"Shadow variant ({shadow_variant}, rank {shadow_rank}) "
                         f"must be higher than live variant ({live_variant}, "
                         f"rank {live_rank}). Shadow mode tests UPGRADES.",
            }

        if not (0.0 < sample_rate <= 1.0):
            return {
                "success": False,
                "error": f"Sample rate must be between 0.0 (exclusive) and 1.0, got {sample_rate}",
            }

        config_id = "cfg-" + company_id
        config = {
            "id": config_id,
            "company_id": company_id,
            "live_variant": live_variant,
            "shadow_variant": shadow_variant,
            "status": "shadow",
            "sample_rate": sample_rate,
            "auto_graduation_threshold": auto_graduation_threshold,
            "auto_graduation_window": auto_graduation_window,
            "is_active": True,
            "total_comparisons": 0,
            "shadow_wins": 0,
            "current_quality_streak": 0,
            "enabled_by_user_id": user_id,
        }
        self._configs[company_id] = config

        return {
            "success": True,
            "config_id": config_id,
            "status": "shadow",
            "live_variant": live_variant,
            "shadow_variant": shadow_variant,
            "sample_rate": sample_rate,
        }

    # ── Disable ───────────────────────────────────────────────────

    def disable_shadow_mode(
        self,
        company_id: str,
        reason: str = "",
    ) -> Dict[str, Any]:
        config = self._configs.get(company_id)
        if config is None or not config.get("is_active"):
            return {"success": False, "error": "No active shadow mode config found"}

        previous_status = config.get("status", "unknown")
        config["is_active"] = False
        config["status"] = "disabled"
        self._configs[company_id] = config

        return {
            "success": True,
            "company_id": company_id,
            "previous_status": previous_status,
            "reason": reason,
        }

    # ── Get Status ────────────────────────────────────────────────

    def get_status(self, company_id: str):
        config = self._configs.get(company_id)
        if config is None or not config.get("is_active"):
            return _MockShadowModeStatus(
                company_id=company_id,
                is_active=False,
                status="disabled",
            )

        total = config.get("total_comparisons", 0)
        wins = config.get("shadow_wins", 0)
        win_rate = (wins / total) if total > 0 else 0.0

        return _MockShadowModeStatus(
            company_id=company_id,
            is_active=True,
            status=config.get("status", "disabled"),
            live_variant=config.get("live_variant", ""),
            shadow_variant=config.get("shadow_variant", ""),
            sample_rate=float(config.get("sample_rate", 1.0)),
            total_comparisons=total,
            shadow_wins=wins,
            win_rate=win_rate,
            current_quality_streak=config.get("current_quality_streak", 0),
            auto_graduation_threshold=float(config.get("auto_graduation_threshold", 0.95)),
            auto_graduation_window=config.get("auto_graduation_window", 100),
            config_id=config.get("id", ""),
        )

    # ── Promote ───────────────────────────────────────────────────

    def promote(
        self,
        company_id: str,
        target_status: str = "",
    ) -> Dict[str, Any]:
        config = self._configs.get(company_id)
        if config is None or not config.get("is_active"):
            return {"success": False, "error": "No active shadow mode config found"}

        current = config.get("status", "disabled")

        if target_status:
            if target_status not in ("shadow", "supervised", "graduated"):
                return {"success": False, "error": f"Invalid target_status: {target_status}"}
            new_status = target_status
        else:
            progression = {"shadow": "supervised", "supervised": "graduated"}
            new_status = progression.get(current, "")
            if not new_status:
                return {"success": False, "error": f"Cannot promote from status '{current}'"}

        config["status"] = new_status
        self._configs[company_id] = config

        return {"success": True, "previous_status": current, "new_status": new_status}

    # ── Complete Graduation ───────────────────────────────────────

    def complete_graduation(self, company_id: str) -> Dict[str, Any]:
        config = self._configs.get(company_id)
        if config is None or not config.get("is_active"):
            return {"success": False, "error": "No active shadow mode config found"}

        current_status = config.get("status", "disabled")
        if current_status not in ("supervised", "graduated"):
            return {
                "success": False,
                "error": f"Cannot complete graduation from status '{current_status}'. "
                         f"Must be 'supervised' or 'graduated'.",
            }

        shadow_variant = config.get("shadow_variant", "")
        config["status"] = "graduated"
        config["is_active"] = False
        self._configs[company_id] = config

        return {
            "success": True,
            "company_id": company_id,
            "new_live_variant": shadow_variant,
        }

    # ── Get Comparison History ────────────────────────────────────

    def get_comparison_history(
        self,
        company_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        comparisons = self._comparisons.get(company_id, [])
        return comparisons[offset : offset + limit]

    # ── Get Statistics ────────────────────────────────────────────

    def get_statistics(self, company_id: str) -> Dict[str, Any]:
        config = self._configs.get(company_id)
        if config is None:
            return {"company_id": company_id, "is_active": False, "total_comparisons": 0}

        total = config.get("total_comparisons", 0)
        wins = config.get("shadow_wins", 0)
        win_rate = (wins / total) if total > 0 else 0.0

        return {
            "company_id": company_id,
            "is_active": config.get("is_active", False),
            "status": config.get("status", "disabled"),
            "live_variant": config.get("live_variant", ""),
            "shadow_variant": config.get("shadow_variant", ""),
            "total_comparisons": total,
            "shadow_wins": wins,
            "win_rate": round(win_rate, 4),
            "current_quality_streak": config.get("current_quality_streak", 0),
            "avg_quality_delta": 0.0,
            "avg_latency_delta_ms": 0,
            "sample_rate": float(config.get("sample_rate", 1.0)),
        }

    # ── Record Human Review ───────────────────────────────────────

    def record_human_review(
        self,
        company_id: str,
        result_id: str,
        verdict: str,
        reviewer_id: str = "",
        notes: str = "",
    ) -> Dict[str, Any]:
        valid_verdicts = ("shadow_better", "live_better", "equal", "skip")
        if verdict not in valid_verdicts:
            return {
                "success": False,
                "error": f"Invalid verdict: {verdict}. Must be one of {valid_verdicts}",
            }
        return {
            "success": True,
            "result_id": result_id,
            "verdict": verdict,
            "reviewer_id": reviewer_id,
        }


@dataclass
class _MockShadowModeStatus:
    """Mimics ShadowModeStatus dataclass from the service."""
    company_id: str
    is_active: bool = False
    status: str = "disabled"
    live_variant: str = ""
    shadow_variant: str = ""
    sample_rate: float = 1.0
    total_comparisons: int = 0
    shadow_wins: int = 0
    win_rate: float = 0.0
    current_quality_streak: int = 0
    auto_graduation_threshold: float = 0.95
    auto_graduation_window: int = 100
    config_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company_id": self.company_id,
            "is_active": self.is_active,
            "status": self.status,
            "live_variant": self.live_variant,
            "shadow_variant": self.shadow_variant,
            "sample_rate": self.sample_rate,
            "total_comparisons": self.total_comparisons,
            "shadow_wins": self.shadow_wins,
            "win_rate": round(self.win_rate, 4),
            "current_quality_streak": self.current_quality_streak,
            "auto_graduation_threshold": self.auto_graduation_threshold,
            "auto_graduation_window": self.auto_graduation_window,
            "config_id": self.config_id,
        }


# ═══════════════════════════════════════════════════════════════════
# PYTEST FIXTURES
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture()
def mock_service():
    """Provide a fresh MockShadowModeService for each test."""
    return MockShadowModeService()


@pytest.fixture()
def app_client(mock_service):
    """Create a FastAPI TestClient with dependency overrides and
    the shadow_mode router included."""

    app = FastAPI()
    app.include_router(ROUTER)

    # Override the dependency injections that the router uses.
    # The router imports these from app.api.deps, and FastAPI resolves
    # them by function identity, so we override using the same functions
    # that are referenced in the router's Depends() calls.
    app.dependency_overrides[DEPS_MODULE.get_company_id] = lambda: "test-company-001"
    app.dependency_overrides[DEPS_MODULE.get_current_user] = lambda: MockUser()

    # require_roles("owner", "admin") creates a unique `checker` closure
    # for each endpoint at module import time. We must override each
    # individual checker closure, NOT the factory function.
    for route in app.routes:
        if hasattr(route, "dependant"):
            for dep in route.dependant.dependencies:
                if dep.call.__name__ == "checker":
                    app.dependency_overrides[dep.call] = lambda: MockUser()

    # Patch get_shadow_mode_service so the lazy import inside each
    # endpoint returns our mock service. The patch stays active for
    # the entire lifetime of the TestClient.
    _patcher = patch(
        "app.services.shadow_mode_service.get_shadow_mode_service",
        return_value=mock_service,
    )
    _patcher.start()
    client = TestClient(app)
    yield client
    _patcher.stop()


@pytest.fixture()
def admin_user():
    """A mock admin user."""
    return MockUser(id="admin-001", company_id="test-company-001", role="admin")


@pytest.fixture()
def owner_user():
    """A mock owner user."""
    return MockUser(id="owner-001", company_id="test-company-001", role="owner")


@pytest.fixture()
def agent_user():
    """A mock agent user (limited permissions)."""
    return MockUser(id="agent-001", company_id="test-company-001", role="agent")


# ═══════════════════════════════════════════════════════════════════
# 1. ENABLE ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════════


class TestEnableEndpoint:
    """POST /api/shadow-mode/enable"""

    def test_enable_with_valid_data_returns_200(self, app_client, mock_service):
        """Enabling shadow mode with valid data returns 200 + config."""
        payload = {
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
            "sample_rate": 0.5,
        }
        response = app_client.post("/api/shadow-mode/enable", json=payload)
        if response.status_code != 200:
            pytest.fail(f"Expected 200, got {response.status_code}: {response.json()}")
        body = response.json()
        assert body["status"] == "ok"
        assert body["data"]["success"] is True
        assert body["data"]["live_variant"] == "mini_parwa"
        assert body["data"]["shadow_variant"] == "parwa"
        assert body["data"]["sample_rate"] == 0.5
        assert body["data"]["status"] == "shadow"
        assert "config_id" in body["data"]

    def test_enable_with_invalid_live_variant_returns_error(self, app_client, mock_service):
        """Invalid live_variant results in error response."""
        payload = {
            "live_variant": "invalid_variant",
            "shadow_variant": "parwa",
        }
        response = app_client.post("/api/shadow-mode/enable", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["data"]["success"] is False
        assert "Invalid live_variant" in body["data"]["error"]

    def test_enable_with_invalid_shadow_variant_returns_error(self, app_client, mock_service):
        """Invalid shadow_variant results in error response."""
        payload = {
            "live_variant": "mini_parwa",
            "shadow_variant": "not_a_variant",
        }
        response = app_client.post("/api/shadow-mode/enable", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["data"]["success"] is False
        assert "Invalid shadow_variant" in body["data"]["error"]

    def test_enable_with_downgrade_direction_returns_error(self, app_client, mock_service):
        """Shadow variant must rank higher than live variant."""
        payload = {
            "live_variant": "parwa",
            "shadow_variant": "mini_parwa",
        }
        response = app_client.post("/api/shadow-mode/enable", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["data"]["success"] is False
        assert "UPGRADES" in body["data"]["error"]

    def test_enable_with_invalid_sample_rate_returns_error(self, app_client, mock_service):
        """Sample rate outside (0.0, 1.0] is rejected."""
        payload = {
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
            "sample_rate": 0.0,
        }
        response = app_client.post("/api/shadow-mode/enable", json=payload)
        # Pydantic Field(ge=0.01) will catch this as a 422 validation error
        assert response.status_code == 422

    def test_enable_with_sample_rate_above_one_returns_error(self, app_client, mock_service):
        """Sample rate > 1.0 is rejected by Pydantic."""
        payload = {
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
            "sample_rate": 1.5,
        }
        response = app_client.post("/api/shadow-mode/enable", json=payload)
        assert response.status_code == 422

    def test_enable_same_variant_returns_error(self, app_client, mock_service):
        """Using the same variant for live and shadow is a downgrade (equal rank)."""
        payload = {
            "live_variant": "parwa",
            "shadow_variant": "parwa",
        }
        response = app_client.post("/api/shadow-mode/enable", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert "UPGRADES" in body["data"]["error"]


# ═══════════════════════════════════════════════════════════════════
# 2. DISABLE ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════════


class TestDisableEndpoint:
    """POST /api/shadow-mode/disable"""

    def test_disable_when_active_returns_200(self, app_client, mock_service):
        """Disabling an active shadow mode returns 200 + success."""
        # Enable first
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
        })
        # Now disable
        response = app_client.post("/api/shadow-mode/disable", json={"reason": "testing"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["data"]["success"] is True
        assert body["data"]["previous_status"] == "shadow"
        assert body["data"]["reason"] == "testing"

    def test_disable_when_not_active_returns_error(self, app_client, mock_service):
        """Disabling when no active config exists returns error."""
        response = app_client.post("/api/shadow-mode/disable", json={"reason": "no active"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["data"]["success"] is False
        assert "No active" in body["data"]["error"]

    def test_disable_with_reason_parameter(self, app_client, mock_service):
        """Reason parameter is included in the response."""
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "parwa",
            "shadow_variant": "parwa_high",
        })
        response = app_client.post("/api/shadow-mode/disable", json={
            "reason": "Quality check failed — reverting",
        })
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["reason"] == "Quality check failed — reverting"


# ═══════════════════════════════════════════════════════════════════
# 3. STATUS ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════════


class TestStatusEndpoint:
    """GET /api/shadow-mode/status"""

    def test_status_when_active_returns_status_object(self, app_client, mock_service):
        """Active shadow mode returns full status object."""
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
        })
        response = app_client.get("/api/shadow-mode/status")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        data = body["data"]
        assert data["is_active"] is True
        assert data["status"] == "shadow"
        assert data["live_variant"] == "mini_parwa"
        assert data["shadow_variant"] == "parwa"

    def test_status_when_inactive_returns_disabled(self, app_client, mock_service):
        """No active shadow mode returns disabled status."""
        response = app_client.get("/api/shadow-mode/status")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["is_active"] is False
        assert body["data"]["status"] == "disabled"

    def test_status_includes_all_required_fields(self, app_client, mock_service):
        """Status response contains all ShadowModeStatus fields."""
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
            "sample_rate": 0.8,
        })
        response = app_client.get("/api/shadow-mode/status")
        data = response.json()["data"]
        required_fields = [
            "company_id", "is_active", "status", "live_variant",
            "shadow_variant", "sample_rate", "total_comparisons",
            "shadow_wins", "win_rate", "current_quality_streak",
            "auto_graduation_threshold", "auto_graduation_window",
            "config_id",
        ]
        for field_name in required_fields:
            assert field_name in data, f"Missing field: {field_name}"

        assert data["sample_rate"] == 0.8
        assert data["total_comparisons"] == 0
        assert data["win_rate"] == 0.0


# ═══════════════════════════════════════════════════════════════════
# 4. PROMOTE ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════════


class TestPromoteEndpoint:
    """POST /api/shadow-mode/promote"""

    def test_promote_from_shadow_to_supervised(self, app_client, mock_service):
        """Auto-promote from shadow → supervised."""
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
        })
        response = app_client.post("/api/shadow-mode/promote", json={})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["data"]["success"] is True
        assert body["data"]["previous_status"] == "shadow"
        assert body["data"]["new_status"] == "supervised"

    def test_promote_from_supervised_to_graduated(self, app_client, mock_service):
        """Auto-promote from supervised → graduated."""
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
        })
        # First promote: shadow → supervised
        app_client.post("/api/shadow-mode/promote", json={})
        # Second promote: supervised → graduated
        response = app_client.post("/api/shadow-mode/promote", json={})
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["success"] is True
        assert body["data"]["previous_status"] == "supervised"
        assert body["data"]["new_status"] == "graduated"

    def test_promote_with_invalid_target_status(self, app_client, mock_service):
        """Invalid target_status returns error."""
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
        })
        response = app_client.post("/api/shadow-mode/promote", json={
            "target_status": "invalid_status",
        })
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["data"]["success"] is False
        assert "Invalid target_status" in body["data"]["error"]

    def test_promote_when_not_active_returns_error(self, app_client, mock_service):
        """Promoting when no active config returns error."""
        response = app_client.post("/api/shadow-mode/promote", json={})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert "No active" in body["data"]["error"]


# ═══════════════════════════════════════════════════════════════════
# 5. GRADUATE ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════════


class TestGraduateEndpoint:
    """POST /api/shadow-mode/graduate"""

    def test_graduate_from_supervised_status(self, app_client, mock_service):
        """Graduation from supervised status succeeds."""
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
        })
        app_client.post("/api/shadow-mode/promote", json={})  # shadow → supervised
        response = app_client.post("/api/shadow-mode/graduate")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["data"]["success"] is True
        assert body["data"]["new_live_variant"] == "parwa"

    def test_graduate_from_shadow_status_rejected(self, app_client, mock_service):
        """Graduation from shadow status (not supervised) is rejected."""
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
        })
        # Status is still "shadow" — graduation should fail
        response = app_client.post("/api/shadow-mode/graduate")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["data"]["success"] is False
        assert "Cannot complete graduation" in body["data"]["error"]

    def test_graduate_when_not_active_returns_error(self, app_client, mock_service):
        """Graduation when no active config returns error."""
        response = app_client.post("/api/shadow-mode/graduate")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["data"]["success"] is False
        assert "No active" in body["data"]["error"]


# ═══════════════════════════════════════════════════════════════════
# 6. COMPARISONS ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════════


class TestComparisonsEndpoint:
    """GET /api/shadow-mode/comparisons"""

    def test_comparisons_returns_list_with_pagination(self, app_client, mock_service):
        """Comparisons endpoint returns a list with pagination metadata."""
        # Seed some comparisons
        mock_service._comparisons["test-company-001"] = [
            {"id": f"comp-{i}", "company_id": "test-company-001", "quality_delta": 0.1}
            for i in range(5)
        ]
        response = app_client.get("/api/shadow-mode/comparisons")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "comparisons" in body["data"]
        assert body["data"]["limit"] == 50
        assert body["data"]["offset"] == 0

    def test_comparisons_with_limit_offset_parameters(self, app_client, mock_service):
        """Limit and offset query params are respected and echoed."""
        mock_service._comparisons["test-company-001"] = [
            {"id": f"comp-{i}"} for i in range(10)
        ]
        response = app_client.get("/api/shadow-mode/comparisons?limit=3&offset=2")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["limit"] == 3
        assert body["data"]["offset"] == 2
        # Should return at most 3 items starting from offset 2
        assert len(body["data"]["comparisons"]) <= 3

    def test_comparisons_when_no_comparisons_exist(self, app_client, mock_service):
        """No comparisons returns empty list."""
        response = app_client.get("/api/shadow-mode/comparisons")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["comparisons"] == []


# ═══════════════════════════════════════════════════════════════════
# 7. STATISTICS ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════════


class TestStatisticsEndpoint:
    """GET /api/shadow-mode/statistics"""

    def test_statistics_when_active_returns_full_stats(self, app_client, mock_service):
        """Active shadow mode returns complete statistics."""
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
            "sample_rate": 0.75,
        })
        response = app_client.get("/api/shadow-mode/statistics")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        data = body["data"]
        assert data["is_active"] is True
        assert data["live_variant"] == "mini_parwa"
        assert data["shadow_variant"] == "parwa"
        assert data["sample_rate"] == 0.75

    def test_statistics_when_inactive_returns_basic_stats(self, app_client, mock_service):
        """No config returns minimal statistics."""
        response = app_client.get("/api/shadow-mode/statistics")
        assert response.status_code == 200
        body = response.json()
        data = body["data"]
        assert data["is_active"] is False
        assert data["total_comparisons"] == 0

    def test_statistics_includes_required_fields(self, app_client, mock_service):
        """Statistics response includes all expected fields."""
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "parwa",
            "shadow_variant": "parwa_high",
        })
        response = app_client.get("/api/shadow-mode/statistics")
        data = response.json()["data"]
        required_fields = [
            "company_id", "is_active", "status",
            "live_variant", "shadow_variant",
            "total_comparisons", "shadow_wins", "win_rate",
            "current_quality_streak", "avg_quality_delta",
            "avg_latency_delta_ms", "sample_rate",
        ]
        for field_name in required_fields:
            assert field_name in data, f"Missing field: {field_name}"


# ═══════════════════════════════════════════════════════════════════
# 8. REVIEW ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════════


class TestReviewEndpoint:
    """POST /api/shadow-mode/review"""

    def test_review_with_valid_verdict(self, app_client, mock_service):
        """Valid verdict returns success."""
        payload = {
            "result_id": "result-001",
            "verdict": "shadow_better",
            "notes": "Shadow response was more detailed",
        }
        response = app_client.post("/api/shadow-mode/review", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["data"]["success"] is True
        assert body["data"]["verdict"] == "shadow_better"
        assert body["data"]["result_id"] == "result-001"

    def test_review_with_invalid_verdict_returns_error(self, app_client, mock_service):
        """Invalid verdict string returns error."""
        payload = {
            "result_id": "result-001",
            "verdict": "definitely_better",
        }
        response = app_client.post("/api/shadow-mode/review", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["data"]["success"] is False
        assert "Invalid verdict" in body["data"]["error"]

    def test_review_all_valid_verdicts(self, app_client, mock_service):
        """All four valid verdicts are accepted."""
        for verdict in ("shadow_better", "live_better", "equal", "skip"):
            payload = {"result_id": f"result-{verdict}", "verdict": verdict}
            response = app_client.post("/api/shadow-mode/review", json=payload)
            assert response.status_code == 200
            body = response.json()
            assert body["data"]["success"] is True, f"Verdict '{verdict}' failed"
            assert body["data"]["verdict"] == verdict


# ═══════════════════════════════════════════════════════════════════
# 9. AUTHENTICATION / AUTHORIZATION TESTS
# ═══════════════════════════════════════════════════════════════════


class TestAuthDependencies:
    """Verify that dependency injection wires correctly for auth."""

    def test_company_id_extracted_from_user(self, app_client, mock_service):
        """company_id comes from the overridden dependency (mock user)."""
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
        })
        # The mock user has company_id="test-company-001"
        # Check that the config was stored under that company_id
        status_resp = app_client.get("/api/shadow-mode/status")
        data = status_resp.json()["data"]
        assert data["company_id"] == "test-company-001"

    def test_user_object_passed_to_service(self, app_client, mock_service):
        """User ID is passed through to the service on enable."""
        payload = {
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
        }
        # The mock get_current_user returns MockUser with id="test-user-001"
        # The router passes str(user.id) as user_id
        app_client.post("/api/shadow-mode/enable", json=payload)
        # Verify the config was created (service was called with user_id)
        config = mock_service._configs.get("test-company-001")
        assert config is not None
        assert config["enabled_by_user_id"] == "test-user-001"

    def test_role_check_blocks_unauthorized_user(self, mock_service):
        """Endpoints requiring owner/admin block agent users.

        This test verifies the role-based access control by checking
        that the router's require_roles dependencies reference the
        correct roles (owner/admin) for protected endpoints. In a
        real deployment, FastAPI's dependency injection + the real
        deps.py would raise AuthorizationError (403) for unauthorized
        roles. Here we verify the wiring is correct by inspecting
        the route dependencies.
        """
        # Verify that /enable uses require_roles with owner/admin
        app = FastAPI()
        app.include_router(ROUTER)

        found_enable = False
        for route in app.routes:
            if hasattr(route, "path") and route.path == "/api/shadow-mode/enable":
                found_enable = True
                # Check that the route has a require_roles dependency
                has_role_dep = False
                for dep in route.dependant.dependencies:
                    if dep.call.__name__ == "checker":
                        has_role_dep = True
                        break
                assert has_role_dep, "enable endpoint should have require_roles dependency"
                break

        assert found_enable, "Could not find /api/shadow-mode/enable route"

        # Also verify /status uses get_current_user (not require_roles)
        found_status = False
        for route in app.routes:
            if hasattr(route, "path") and route.path == "/api/shadow-mode/status":
                found_status = True
                has_role_dep = False
                for dep in route.dependant.dependencies:
                    if dep.call.__name__ == "checker":
                        has_role_dep = True
                # Status should NOT require owner/admin — just any authenticated user
                assert not has_role_dep, "status endpoint should NOT require owner/admin role"
                break

        assert found_status, "Could not find /api/shadow-mode/status route"

    def test_role_check_allows_owner(self, mock_service):
        """Owner role is allowed on owner/admin endpoints."""
        owner = MockUser(id="owner-001", company_id="test-company-001", role="owner")

        app = FastAPI()
        app.include_router(ROUTER)

        app.dependency_overrides[DEPS_MODULE.get_current_user] = lambda: owner
        app.dependency_overrides[DEPS_MODULE.get_company_id] = lambda: str(owner.company_id)

        def _require_roles_check(*roles: str):
            def checker():
                if owner.role not in roles:
                    from app.exceptions import AuthorizationError
                    raise AuthorizationError(message="Insufficient permissions", details=None)
                return owner
            return checker

        app.dependency_overrides[DEPS_MODULE.require_roles] = _require_roles_check

        with patch(
            "app.services.shadow_mode_service.get_shadow_mode_service",
            return_value=mock_service,
        ):
            client = TestClient(app)
            response = client.post("/api/shadow-mode/enable", json={
                "live_variant": "mini_parwa",
                "shadow_variant": "parwa",
            })
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

    def test_review_allows_agent_role(self, mock_service):
        """The /review endpoint allows owner, admin, AND agent."""
        agent = MockUser(id="agent-001", company_id="test-company-001", role="agent")

        app = FastAPI()
        app.include_router(ROUTER)

        app.dependency_overrides[DEPS_MODULE.get_current_user] = lambda: agent
        app.dependency_overrides[DEPS_MODULE.get_company_id] = lambda: str(agent.company_id)

        # require_roles("owner", "admin", "agent") for /review
        def _require_roles_check(*roles: str):
            def checker():
                if agent.role not in roles:
                    from app.exceptions import AuthorizationError
                    raise AuthorizationError(message="Insufficient permissions", details=None)
                return agent
            return checker

        app.dependency_overrides[DEPS_MODULE.require_roles] = _require_roles_check

        with patch(
            "app.services.shadow_mode_service.get_shadow_mode_service",
            return_value=mock_service,
        ):
            client = TestClient(app)
            response = client.post("/api/shadow-mode/review", json={
                "result_id": "result-001",
                "verdict": "equal",
            })
            assert response.status_code == 200
            assert response.json()["data"]["success"] is True


# ═══════════════════════════════════════════════════════════════════
# ADDITIONAL EDGE-CASE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Additional edge-case and integration-flow tests."""

    def test_full_lifecycle_shadow_supervised_graduated(self, app_client, mock_service):
        """Full happy-path lifecycle: enable → promote → promote → graduate."""
        # 1. Enable
        resp = app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
        })
        assert resp.json()["data"]["status"] == "shadow"

        # 2. Promote to supervised
        resp = app_client.post("/api/shadow-mode/promote", json={})
        assert resp.json()["data"]["new_status"] == "supervised"

        # 3. Graduate
        resp = app_client.post("/api/shadow-mode/graduate")
        assert resp.json()["data"]["success"] is True
        assert resp.json()["data"]["new_live_variant"] == "parwa"

        # 4. Verify status is now disabled (graduated & inactive)
        resp = app_client.get("/api/shadow-mode/status")
        assert resp.json()["data"]["is_active"] is False

    def test_enable_replaces_existing_active_config(self, app_client, mock_service):
        """Enabling when already active replaces the old config."""
        # First enable
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
        })
        # Second enable with different variants
        resp = app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "parwa",
            "shadow_variant": "parwa_high",
        })
        assert resp.json()["data"]["success"] is True
        assert resp.json()["data"]["shadow_variant"] == "parwa_high"

        # Status should reflect the new config
        status_resp = app_client.get("/api/shadow-mode/status")
        assert status_resp.json()["data"]["shadow_variant"] == "parwa_high"

    def test_disable_then_check_status_is_disabled(self, app_client, mock_service):
        """After disabling, status shows disabled."""
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
        })
        app_client.post("/api/shadow-mode/disable", json={"reason": "done"})
        resp = app_client.get("/api/shadow-mode/status")
        assert resp.json()["data"]["is_active"] is False
        assert resp.json()["data"]["status"] == "disabled"

    def test_promote_with_explicit_target_status(self, app_client, mock_service):
        """Promote with explicit target_status skips to that phase."""
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
        })
        # Jump directly to graduated
        resp = app_client.post("/api/shadow-mode/promote", json={
            "target_status": "graduated",
        })
        assert resp.json()["data"]["success"] is True
        assert resp.json()["data"]["new_status"] == "graduated"

    def test_comparisons_default_limit_and_offset(self, app_client, mock_service):
        """Comparisons endpoint defaults: limit=50, offset=0."""
        response = app_client.get("/api/shadow-mode/comparisons")
        body = response.json()
        assert body["data"]["limit"] == 50
        assert body["data"]["offset"] == 0

    def test_comparisons_custom_limit_respected(self, app_client, mock_service):
        """Custom limit value is passed through correctly."""
        response = app_client.get("/api/shadow-mode/comparisons?limit=10&offset=5")
        body = response.json()
        assert body["data"]["limit"] == 10
        assert body["data"]["offset"] == 5

    def test_enable_with_all_optional_fields(self, app_client, mock_service):
        """Enable with every optional field populated."""
        payload = {
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa_high",
            "sample_rate": 0.25,
            "auto_graduation_threshold": 0.9,
            "auto_graduation_window": 50,
            "supervised_timeout_seconds": 600,
            "auto_promote_to_supervised": False,
            "auto_promote_to_graduated": True,
            "live_instance_id": "inst-live-001",
            "shadow_instance_id": "inst-shadow-001",
        }
        response = app_client.post("/api/shadow-mode/enable", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["success"] is True
        assert body["data"]["sample_rate"] == 0.25

    def test_promote_from_graduated_fails_auto(self, app_client, mock_service):
        """Auto-promote from graduated has no next phase → error."""
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
        })
        # Manually set to graduated
        app_client.post("/api/shadow-mode/promote", json={"target_status": "graduated"})
        # Try auto-promote (no target)
        resp = app_client.post("/api/shadow-mode/promote", json={})
        # graduated has no next progression
        assert resp.json()["data"]["success"] is False

    def test_review_with_notes(self, app_client, mock_service):
        """Review with notes field populated."""
        payload = {
            "result_id": "result-002",
            "verdict": "live_better",
            "notes": "Live was more concise and accurate",
        }
        response = app_client.post("/api/shadow-mode/review", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["success"] is True
        assert body["data"]["verdict"] == "live_better"

    def test_disable_twice_second_fails(self, app_client, mock_service):
        """Disabling twice in a row: second attempt fails."""
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
        })
        # First disable
        resp1 = app_client.post("/api/shadow-mode/disable", json={})
        assert resp1.json()["data"]["success"] is True
        # Second disable
        resp2 = app_client.post("/api/shadow-mode/disable", json={})
        assert resp2.json()["data"]["success"] is False
        assert "No active" in resp2.json()["data"]["error"]

    def test_enable_parwa_to_parwa_high(self, app_client, mock_service):
        """Enable shadow mode with parwa → parwa_high (tier 2→3)."""
        response = app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "parwa",
            "shadow_variant": "parwa_high",
        })
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["success"] is True
        assert body["data"]["live_variant"] == "parwa"
        assert body["data"]["shadow_variant"] == "parwa_high"

    def test_statistics_after_disable(self, app_client, mock_service):
        """Statistics after disable still returns data from config."""
        app_client.post("/api/shadow-mode/enable", json={
            "live_variant": "mini_parwa",
            "shadow_variant": "parwa",
        })
        app_client.post("/api/shadow-mode/disable", json={})
        response = app_client.get("/api/shadow-mode/statistics")
        # After disable, config still exists but is inactive
        data = response.json()["data"]
        # The mock still has the config (just is_active=False)
        assert "company_id" in data
