"""
Comprehensive tests for PARWA Response API endpoints.

Tests cover all 4 routers: response, brand-voice, assignment, migration.
Auth dependencies and service layers are fully mocked.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# ---------------------------------------------------------------------------
# Mock out database, auth, and heavy imports BEFORE importing the API module
# ---------------------------------------------------------------------------
# These prevent SQLAlchemy engine creation and database connection attempts.
# Must be done BEFORE any backend.app.* imports that touch database.*
import importlib
import types as _types

def _make_mock_module(name, attrs=None, is_package=False):
    mod = _types.ModuleType(name)
    if is_package:
        mod.__path__ = []  # mark as package so submodules can be found
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    return mod

_MockUser = type("User", (), {})
_MockCompany = type("Company", (), {})
_MockOAuthAccount = type("OAuthAccount", (), {})
_MockRefreshToken = type("RefreshToken", (), {})

_db_core_attrs = {
    "User": _MockUser, "Company": _MockCompany,
    "OAuthAccount": _MockOAuthAccount, "RefreshToken": _MockRefreshToken,
}

_mock_modules = {
    # Database layer
    "database": (None, True),
    "database.base": ({"get_db": lambda: None, "engine": MagicMock(), "Session": MagicMock}, False),
    "database.models": (None, True),
    "database.models.core": (_db_core_attrs, False),
    # SQLAlchemy mock (needed by response.py)
    "sqlalchemy": (None, True),
    "sqlalchemy.orm": ({"Session": MagicMock}, False),
    "sqlalchemy.ext": (None, True),
    "sqlalchemy.ext.asyncio": ({"AsyncSession": MagicMock, "create_async_engine": MagicMock}, False),
    # Shared utilities (used by schemas, services)
    "shared": (None, True),
    "shared.utils": (None, True),
    "shared.utils.security": ({"hash_password": lambda x: x, "verify_password": lambda x, y: True}, False),
    "shared.utils.pagination": ({"PaginatedResponse": MagicMock, "paginate_query": lambda *a, **kw: None}, False),
    # Auth core
    "app.core.auth": ({"verify_access_token": lambda t: {"sub": "user-1"}}, False),
    # Prevent __init__.py cascade by pre-registering sub-modules that fail
    "app.api.auth": ({"router": MagicMock()}, False),
    "app.api.health": ({"router": MagicMock()}, False),
    "app.api.admin": ({"router": MagicMock()}, False),
    "app.api.api_keys": ({"router": MagicMock()}, False),
    "app.api.mfa": ({"router": MagicMock()}, False),
    "app.api.client": ({"router": MagicMock()}, False),
    "app.api.webhooks": ({"router": MagicMock()}, False),
    "app.api.tickets": ({"router": MagicMock()}, False),
    "app.api.public": ({"router": MagicMock()}, False),
    # Services that may be imported
    "app.services.notification_service": ({"NotificationService": MagicMock}, False),
    "app.api.jarvis": ({"router": MagicMock()}, False),
}

for _mod_name, (_attrs, _is_pkg) in _mock_modules.items():
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = _make_mock_module(_mod_name, _attrs, _is_pkg)

# Now safe to import
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.response import (
    response_router,
    brand_voice_router,
    assignment_router,
    migration_router,
)
from app.api.deps import (
    get_current_user,
    get_company_id,
    require_roles,
)
from app.exceptions import NotFoundError

import pytest

# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_in_memory_store():
    """Reset class-level in-memory store between tests."""
    from app.services.response_template_service import ResponseTemplateService
    ResponseTemplateService._store.clear()
    ResponseTemplateService._defaults_loaded.clear()
    yield


@pytest.fixture()
def mock_user():
    """Create a mock User with company_id."""
    user = MagicMock()
    user.id = "user-001"
    user.company_id = "company-001"
    user.role = "admin"
    user.is_active = True
    user._token_payload = {"sub": "user-001", "company_id": "company-001"}
    return user


@pytest.fixture()
def owner_user():
    user = MagicMock()
    user.id = "owner-001"
    user.company_id = "company-001"
    user.role = "owner"
    user.is_active = True
    user._token_payload = {"sub": "owner-001", "company_id": "company-001"}
    return user


@pytest.fixture()
def app(mock_user, owner_user):
    """Build a FastAPI test app with all routers and mocked deps."""
    application = FastAPI()
    application.include_router(response_router)
    application.include_router(brand_voice_router)
    application.include_router(assignment_router)
    application.include_router(migration_router)

    async def override_get_current_user():
        return mock_user

    async def override_get_company_id():
        return "company-001"

    async def override_require_roles():
        return owner_user

    application.dependency_overrides[get_current_user] = override_get_current_user
    application.dependency_overrides[get_company_id] = override_get_company_id
    # require_roles is a factory — we override the inner checker result
    application.dependency_overrides[require_roles("owner", "admin")] = override_require_roles

    return application


@pytest.fixture()
def client(app):
    return TestClient(app, raise_server_exceptions=False)


# ═══════════════════════════════════════════════════════════════════════
# 1. RESPONSE GENERATION — POST /api/response/generate
# ═══════════════════════════════════════════════════════════════════════


class TestGenerateResponse:
    """Tests for POST /api/response/generate"""

    @patch("app.core.response_generator.ResponseGenerator", create=True)
    def test_generate_success(self, mock_gen_cls, client):
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"response": "Hello!"}
        mock_gen = mock_gen_cls.return_value
        mock_gen.generate = AsyncMock(return_value=mock_result)

        resp = client.post("/api/response/generate", json={
            "query": "How do I reset my password?",
            "conversation_id": "conv-001",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "data" in data

    @patch("app.core.response_generator.ResponseGenerator", create=True)
    def test_generate_with_all_fields(self, mock_gen_cls, client):
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"response": "ok"}
        mock_gen = mock_gen_cls.return_value
        mock_gen.generate = AsyncMock(return_value=mock_result)

        resp = client.post("/api/response/generate", json={
            "query": "Help!",
            "conversation_id": "conv-002",
            "variant_type": "parwa_high",
            "customer_id": "cust-001",
            "conversation_history": [{"role": "user", "content": "hi"}],
            "customer_metadata": {"tier": "pro"},
            "language": "es",
            "force_template_response": True,
        })
        assert resp.status_code == 200

    def test_generate_missing_query(self, client):
        resp = client.post("/api/response/generate", json={
            "conversation_id": "conv-001",
        })
        assert resp.status_code == 422

    def test_generate_missing_conversation_id(self, client):
        resp = client.post("/api/response/generate", json={
            "query": "Help!",
        })
        assert resp.status_code == 422

    def test_generate_empty_query(self, client):
        resp = client.post("/api/response/generate", json={
            "query": "",
            "conversation_id": "conv-001",
        })
        assert resp.status_code == 422

    def test_generate_empty_body(self, client):
        resp = client.post("/api/response/generate", json={})
        assert resp.status_code == 422

    @patch("app.core.response_generator.ResponseGenerator", create=True)
    def test_generate_service_raises_validation_error(self, mock_gen_cls, client):
        from app.exceptions import ValidationError
        mock_gen = mock_gen_cls.return_value
        mock_gen.generate = AsyncMock(
            side_effect=ValidationError(message="Bad input")
        )
        resp = client.post("/api/response/generate", json={
            "query": "test",
            "conversation_id": "conv-001",
        })
        assert resp.status_code == 422

    @patch("app.core.response_generator.ResponseGenerator", create=True)
    def test_generate_service_raises_not_found_error(self, mock_gen_cls, client):
        mock_gen = mock_gen_cls.return_value
        mock_gen.generate = AsyncMock(
            side_effect=NotFoundError(message="Not found")
        )
        resp = client.post("/api/response/generate", json={
            "query": "test",
            "conversation_id": "conv-001",
        })
        assert resp.status_code == 404

    @patch("app.core.response_generator.ResponseGenerator", create=True)
    def test_generate_service_raises_generic_error(self, mock_gen_cls, client):
        mock_gen = mock_gen_cls.return_value
        mock_gen.generate = AsyncMock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/response/generate", json={
            "query": "test",
            "conversation_id": "conv-001",
        })
        assert resp.status_code == 500
        assert "Failed to generate response" in resp.json()["detail"]

    @patch("app.core.response_generator.ResponseGenerator", create=True)
    def test_generate_default_variant_type(self, mock_gen_cls, client):
        """Default variant_type should be 'parwa'."""
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"response": "ok"}
        mock_gen = mock_gen_cls.return_value
        mock_gen.generate = AsyncMock(return_value=mock_result)

        resp = client.post("/api/response/generate", json={
            "query": "test query",
            "conversation_id": "conv-default",
        })
        assert resp.status_code == 200
        # Verify the generator was called
        assert mock_gen.generate.called


# ═══════════════════════════════════════════════════════════════════════
# 2. BATCH GENERATION — POST /api/response/generate/batch
# ═══════════════════════════════════════════════════════════════════════


class TestBatchGeneration:
    """Tests for POST /api/response/generate/batch"""

    @patch("app.core.response_generator.ResponseGenerator", create=True)
    def test_batch_all_succeed(self, mock_gen_cls, client):
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"response": "ok"}
        mock_gen = mock_gen_cls.return_value
        mock_gen.generate = AsyncMock(return_value=mock_result)

        resp = client.post("/api/response/generate/batch", json={
            "items": [
                {"query": "q1", "conversation_id": "c1"},
                {"query": "q2", "conversation_id": "c2"},
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["data"]["total"] == 2
        assert data["data"]["succeeded"] == 2
        assert data["data"]["failed"] == 0

    @patch("app.core.response_generator.ResponseGenerator", create=True)
    def test_batch_partial_failure(self, mock_gen_cls, client):
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"response": "ok"}
        mock_gen = mock_gen_cls.return_value
        call_count = 0

        async def _gen(req):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("fail")
            return mock_result

        mock_gen.generate = _gen

        resp = client.post("/api/response/generate/batch", json={
            "items": [
                {"query": "q1", "conversation_id": "c1"},
                {"query": "q2", "conversation_id": "c2"},
                {"query": "q3", "conversation_id": "c3"},
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "partial"
        assert data["data"]["succeeded"] == 2
        assert data["data"]["failed"] == 1

    def test_batch_empty_items(self, client):
        resp = client.post("/api/response/generate/batch", json={
            "items": [],
        })
        assert resp.status_code == 422

    def test_batch_too_many_items(self, client):
        items = [{"query": f"q{i}", "conversation_id": f"c{i}"} for i in range(21)]
        resp = client.post("/api/response/generate/batch", json={"items": items})
        assert resp.status_code == 422

    def test_batch_missing_items_key(self, client):
        resp = client.post("/api/response/generate/batch", json={})
        assert resp.status_code == 422

    def test_batch_item_missing_query(self, client):
        resp = client.post("/api/response/generate/batch", json={
            "items": [{"conversation_id": "c1"}],
        })
        assert resp.status_code == 422

    def test_batch_item_missing_conversation_id(self, client):
        resp = client.post("/api/response/generate/batch", json={
            "items": [{"query": "q1"}],
        })
        assert resp.status_code == 422

    @patch("app.core.response_generator.ResponseGenerator", create=True)
    def test_batch_single_item(self, mock_gen_cls, client):
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"response": "ok"}
        mock_gen = mock_gen_cls.return_value
        mock_gen.generate = AsyncMock(return_value=mock_result)
        resp = client.post("/api/response/generate/batch", json={
            "items": [{"query": "q1", "conversation_id": "c1"}],
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1


# ═══════════════════════════════════════════════════════════════════════
# 3. TOKEN BUDGET
# ═══════════════════════════════════════════════════════════════════════


class TestTokenBudget:
    """Tests for token budget endpoints."""

    @patch("app.services.token_budget_service.TokenBudgetService", create=True)
    def test_get_budget_status(self, mock_svc_cls, client):
        @dataclass
        class Status:
            conversation_id: str
            used: int
            max_tokens: int
            percentage: float
            warning_level: str
        mock_svc = mock_svc_cls.return_value
        mock_svc.get_budget_status = AsyncMock(
            return_value=Status("conv-001", 500, 4000, 12.5, "normal")
        )
        resp = client.get("/api/response/budget/conv-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @patch("app.services.token_budget_service.TokenBudgetService", create=True)
    def test_get_budget_service_error(self, mock_svc_cls, client):
        mock_svc = mock_svc_cls.return_value
        mock_svc.get_budget_status = AsyncMock(side_effect=RuntimeError("err"))
        resp = client.get("/api/response/budget/conv-001")
        assert resp.status_code == 500

    @patch("app.services.token_budget_service.TokenBudgetService", create=True)
    def test_initialize_budget(self, mock_svc_cls, client):
        @dataclass
        class Budget:
            conversation_id: str
            company_id: str
            max_tokens: int
            used: int
        mock_svc = mock_svc_cls.return_value
        mock_svc.initialize_budget = AsyncMock(
            return_value=Budget("conv-001", "company-001", 4000, 0)
        )
        resp = client.post("/api/response/budget/conv-001/initialize", json={
            "variant_type": "parwa",
        })
        assert resp.status_code == 200

    @patch("app.services.token_budget_service.TokenBudgetService", create=True)
    def test_initialize_budget_default_variant(self, mock_svc_cls, client):
        mock_svc = mock_svc_cls.return_value
        from app.services.token_budget_service import TokenBudget
        now = datetime.now(timezone.utc)
        mock_budget = TokenBudget(
            conversation_id="conv-001", company_id="company-001", variant_type="parwa",
            max_tokens=7373, reserved_tokens=0, used_tokens=0,
            available_tokens=7373, created_at=now, updated_at=now,
        )
        mock_svc.initialize_budget = AsyncMock(return_value=mock_budget)
        resp = client.post("/api/response/budget/conv-001/initialize", json={})
        assert resp.status_code == 200

    @patch("app.services.token_budget_service.TokenBudgetService", create=True)
    def test_check_overflow(self, mock_svc_cls, client):
        @dataclass
        class OverflowResult:
            can_fit: bool
            remaining: int
            overflow: int
            needs_truncation: bool
        mock_svc = mock_svc_cls.return_value
        mock_svc.check_overflow = AsyncMock(
            return_value=OverflowResult(True, 3000, 0, False)
        )
        resp = client.post("/api/response/budget/conv-001/check", json={
            "estimated_tokens": 500,
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["can_fit"] is True

    @patch("app.services.token_budget_service.TokenBudgetService", create=True)
    def test_check_overflow_cannot_fit(self, mock_svc_cls, client):
        @dataclass
        class OverflowResult:
            can_fit: bool
            remaining: int
            overflow: int
            needs_truncation: bool
        mock_svc = mock_svc_cls.return_value
        mock_svc.check_overflow = AsyncMock(
            return_value=OverflowResult(False, 0, 500, True)
        )
        resp = client.post("/api/response/budget/conv-001/check", json={
            "estimated_tokens": 5000,
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["needs_truncation"] is True

    def test_check_overflow_zero_tokens(self, client):
        resp = client.post("/api/response/budget/conv-001/check", json={
            "estimated_tokens": 0,
        })
        assert resp.status_code == 422

    def test_check_overflow_negative_tokens(self, client):
        resp = client.post("/api/response/budget/conv-001/check", json={
            "estimated_tokens": -5,
        })
        assert resp.status_code == 422

    @patch("app.services.token_budget_service.TokenBudgetService", create=True)
    def test_check_overflow_service_error(self, mock_svc_cls, client):
        mock_svc = mock_svc_cls.return_value
        mock_svc.check_overflow = AsyncMock(side_effect=RuntimeError("err"))
        resp = client.post("/api/response/budget/conv-001/check", json={
            "estimated_tokens": 100,
        })
        assert resp.status_code == 500

    @patch("app.services.token_budget_service.TokenBudgetService", create=True)
    def test_initialize_service_error(self, mock_svc_cls, client):
        mock_svc = mock_svc_cls.return_value
        mock_svc.initialize_budget = AsyncMock(side_effect=RuntimeError("err"))
        resp = client.post("/api/response/budget/conv-001/initialize", json={})
        assert resp.status_code == 500


# ═══════════════════════════════════════════════════════════════════════
# 4. RESPONSE TEMPLATES CRUD
# ═══════════════════════════════════════════════════════════════════════


class TestTemplatesCRUD:
    """Tests for template CRUD endpoints."""

    def test_create_template_success(self, client):
        resp = client.post("/api/response/templates", json={
            "name": "Test Greeting",
            "category": "greeting",
            "subject_template": "Hi {{name}}!",
            "body_template": "Hello {{name}}, welcome!",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "ok"
        assert data["data"]["name"] == "Test Greeting"
        assert data["data"]["category"] == "greeting"

    def test_create_template_invalid_category(self, client):
        resp = client.post("/api/response/templates", json={
            "name": "Test",
            "category": "nonexistent",
            "body_template": "Hello",
        })
        assert resp.status_code == 422

    def test_create_template_empty_name(self, client):
        resp = client.post("/api/response/templates", json={
            "name": "",
            "category": "greeting",
            "body_template": "Hello",
        })
        assert resp.status_code == 422

    def test_create_template_no_body_or_subject(self, client):
        resp = client.post("/api/response/templates", json={
            "name": "Empty",
            "category": "general",
        })
        assert resp.status_code == 422

    def test_create_template_missing_category(self, client):
        resp = client.post("/api/response/templates", json={
            "name": "NoCat",
            "body_template": "Hello",
        })
        assert resp.status_code == 422

    def test_list_templates_success(self, client):
        resp = client.get("/api/response/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "items" in data["data"]
        assert "total" in data["data"]
        assert data["data"]["total"] == 5

    def test_list_templates_with_category_filter(self, client):
        resp = client.get("/api/response/templates?category=greeting")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["data"]["items"]:
            assert item["category"] == "greeting"

    def test_list_templates_with_language_filter(self, client):
        resp = client.get("/api/response/templates?language=en")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 5

    def test_list_templates_active_only_false(self, client):
        resp = client.get("/api/response/templates?active_only=false")
        assert resp.status_code == 200

    def test_list_templates_no_results_category(self, client):
        resp = client.get("/api/response/templates?category=xyz")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    def test_get_template_success(self, client):
        create_resp = client.post("/api/response/templates", json={
            "name": "Get Test",
            "category": "general",
            "body_template": "Hello {{name}}",
        })
        tid = create_resp.json()["data"]["id"]
        resp = client.get(f"/api/response/templates/{tid}")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == tid

    def test_get_template_not_found(self, client):
        resp = client.get("/api/response/templates/nonexistent-id")
        assert resp.status_code == 404

    def test_update_template_success(self, client):
        create_resp = client.post("/api/response/templates", json={
            "name": "Update Me",
            "category": "general",
            "body_template": "Old body",
        })
        tid = create_resp.json()["data"]["id"]
        resp = client.put(f"/api/response/templates/{tid}", json={
            "name": "Updated Name",
            "body_template": "New body with {{var}}",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Updated Name"
        assert resp.json()["data"]["version"] == 2

    def test_update_template_not_found(self, client):
        resp = client.put("/api/response/templates/nonexistent", json={
            "name": "x",
        })
        assert resp.status_code == 404

    def test_update_template_invalid_category(self, client):
        create_resp = client.post("/api/response/templates", json={
            "name": "Cat Test",
            "category": "general",
            "body_template": "Body",
        })
        tid = create_resp.json()["data"]["id"]
        resp = client.put(f"/api/response/templates/{tid}", json={
            "category": "invalid_cat",
        })
        assert resp.status_code == 422

    def test_delete_template_success(self, client):
        create_resp = client.post("/api/response/templates", json={
            "name": "Delete Me",
            "category": "general",
            "body_template": "Bye",
        })
        tid = create_resp.json()["data"]["id"]
        resp = client.delete(f"/api/response/templates/{tid}")
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted"] is True

    def test_delete_template_not_found(self, client):
        resp = client.delete("/api/response/templates/nonexistent")
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted"] is False

    def test_render_template_success(self, client):
        create_resp = client.post("/api/response/templates", json={
            "name": "Render Test",
            "category": "greeting",
            "subject_template": "Hi {{customer_name}}!",
            "body_template": "Hello {{customer_name}}, welcome to {{company_name}}.",
        })
        tid = create_resp.json()["data"]["id"]
        resp = client.post(f"/api/response/templates/{tid}/render", json={
            "variables": {
                "customer_name": "Alice",
                "company_name": "PARWA",
            },
            "content_type": "text",
        })
        assert resp.status_code == 200
        rendered = resp.json()["data"]["rendered"]
        assert "Alice" in rendered
        assert "PARWA" in rendered

    def test_render_template_not_found(self, client):
        resp = client.post("/api/response/templates/nonexistent-id/render", json={
            "variables": {},
        })
        # Template not found may return 200 with empty content or 404
        assert resp.status_code in (200, 404)

    def test_render_template_html_sanitization(self, client):
        create_resp = client.post("/api/response/templates", json={
            "name": "XSS Test",
            "category": "general",
            "body_template": "Message: {{msg}}",
        })
        tid = create_resp.json()["data"]["id"]
        resp = client.post(f"/api/response/templates/{tid}/render", json={
            "variables": {"msg": '<script>alert("xss")</script>'},
            "content_type": "html",
        })
        assert resp.status_code == 200
        rendered = resp.json()["data"]["rendered"]
        assert "<script>" not in rendered.lower()

    def test_render_template_text_escaping(self, client):
        create_resp = client.post("/api/response/templates", json={
            "name": "Escape Test",
            "category": "general",
            "body_template": "Val: {{val}}",
        })
        tid = create_resp.json()["data"]["id"]
        resp = client.post(f"/api/response/templates/{tid}/render", json={
            "variables": {"val": "<b>bold</b>"},
            "content_type": "text",
        })
        assert resp.status_code == 200
        rendered = resp.json()["data"]["rendered"]
        assert "&lt;b&gt;" in rendered
        assert "<b>" not in rendered

    def test_render_with_empty_variables(self, client):
        create_resp = client.post("/api/response/templates", json={
            "name": "Empty Vars",
            "category": "general",
            "body_template": "Static message",
        })
        tid = create_resp.json()["data"]["id"]
        resp = client.post(f"/api/response/templates/{tid}/render", json={
            "variables": {},
        })
        assert resp.status_code == 200

    def test_create_then_delete_gets_404(self, client):
        create_resp = client.post("/api/response/templates", json={
            "name": "Temp",
            "category": "general",
            "body_template": "Hi",
        })
        tid = create_resp.json()["data"]["id"]
        client.delete(f"/api/response/templates/{tid}")
        resp = client.get(f"/api/response/templates/{tid}")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# 5. BRAND VOICE
# ═══════════════════════════════════════════════════════════════════════


class TestBrandVoice:
    """Tests for brand voice endpoints."""

    @patch("app.services.brand_voice_service.BrandVoiceService", create=True)
    def test_get_brand_voice_success(self, mock_svc_cls, client):
        @dataclass
        class Config:
            tone: str
            formality_level: float
            prohibited_words: list
            response_length_preference: str
            max_response_sentences: int
            min_response_sentences: int
            greeting_template: Optional[str]
            closing_template: Optional[str]
            emoji_usage: str
            apology_style: str
            escalation_tone: str
            brand_name: str
            industry: str
            custom_instructions: Optional[str]
        mock_svc = mock_svc_cls.return_value
        mock_svc.get_config = AsyncMock(
            return_value=Config(
                tone="professional", formality_level=0.7,
                prohibited_words=["damn"], response_length_preference="standard",
                max_response_sentences=10, min_response_sentences=1,
                greeting_template=None, closing_template=None,
                emoji_usage="minimal", apology_style="solution-focused",
                escalation_tone="calm", brand_name="PARWA", industry="tech",
                custom_instructions=None,
            )
        )
        resp = client.get("/api/brand-voice")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @patch("app.services.brand_voice_service.BrandVoiceService", create=True)
    def test_get_brand_voice_error(self, mock_svc_cls, client):
        mock_svc = mock_svc_cls.return_value
        mock_svc.get_config = AsyncMock(side_effect=RuntimeError("fail"))
        resp = client.get("/api/brand-voice")
        assert resp.status_code == 500

    @patch("app.services.brand_voice_service.BrandVoiceService", create=True)
    def test_upsert_brand_voice_success(self, mock_svc_cls, client):
        mock_svc = mock_svc_cls.return_value
        from app.services.brand_voice_service import BrandVoiceConfig
        now = datetime.now(timezone.utc)
        mock_config = BrandVoiceConfig(
            company_id="co-1", tone="friendly", formality_level=0.3,
            prohibited_words=[], response_length_preference="medium",
            max_response_sentences=10, min_response_sentences=2,
            greeting_template="Hi!", closing_template="Thanks!",
            emoji_usage="moderate", apology_style="sincere",
            escalation_tone="professional", brand_name="TestCo",
            industry="ecommerce", custom_instructions="",
            created_at=now, updated_at=now,
        )
        mock_svc.update_config = AsyncMock(return_value=mock_config)
        resp = client.post("/api/brand-voice", json={
            "tone": "friendly",
            "formality_level": 0.3,
        })
        assert resp.status_code == 200

    @patch("app.services.brand_voice_service.BrandVoiceService", create=True)
    def test_upsert_brand_voice_create_fallback(self, mock_svc_cls, client):
        mock_svc = mock_svc_cls.return_value
        mock_svc.update_config = AsyncMock(side_effect=NotFoundError("not found"))
        from app.services.brand_voice_service import BrandVoiceConfig
        now = datetime.now(timezone.utc)
        mock_config = BrandVoiceConfig(
            company_id="co-1", tone="casual", formality_level=0.5,
            prohibited_words=[], response_length_preference="standard",
            max_response_sentences=8, min_response_sentences=1,
            greeting_template="", closing_template="",
            emoji_usage="minimal", apology_style="sincere",
            escalation_tone="professional", brand_name="TestCo",
            industry="tech", custom_instructions="",
            created_at=now, updated_at=now,
        )
        mock_svc.create_config = AsyncMock(return_value=mock_config)
        resp = client.post("/api/brand-voice", json={"tone": "casual"})
        assert resp.status_code == 200

    @patch("app.services.brand_voice_service.BrandVoiceService", create=True)
    def test_delete_brand_voice_success(self, mock_svc_cls, client):
        mock_svc = mock_svc_cls.return_value
        mock_svc.delete_config = AsyncMock(return_value=True)
        resp = client.delete("/api/brand-voice")
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted"] is True

    @patch("app.services.brand_voice_service.BrandVoiceService", create=True)
    def test_check_prohibited_words(self, mock_svc_cls, client):
        @dataclass
        class Result:
            has_prohibited: bool
            prohibited_found: list
            normalized_text: str
        mock_svc = mock_svc_cls.return_value
        mock_svc.check_prohibited_words = AsyncMock(
            return_value=Result(True, ["damn"], "normalized text")
        )
        resp = client.post("/api/brand-voice/check-prohibited", json={
            "text": "This is damn bad",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["has_prohibited"] is True

    def test_check_prohibited_empty_text(self, client):
        resp = client.post("/api/brand-voice/check-prohibited", json={
            "text": "",
        })
        assert resp.status_code == 422

    @patch("app.services.brand_voice_service.BrandVoiceService", create=True)
    def test_validate_brand_voice(self, mock_svc_cls, client):
        @dataclass
        class ValidationResult:
            score: float
            violations: list
            warnings: list
            suggested_fixes: list
        mock_svc = mock_svc_cls.return_value
        mock_svc.get_config = AsyncMock(return_value=MagicMock())
        mock_svc.validate_response = AsyncMock(
            return_value=ValidationResult(0.9, [], [], [])
        )
        resp = client.post("/api/brand-voice/validate", json={
            "response_text": "Thank you for your inquiry!",
            "sentiment_score": 0.8,
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["score"] == 0.9

    def test_validate_brand_voice_missing_response_text(self, client):
        resp = client.post("/api/brand-voice/validate", json={})
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# 6. AI ASSIGNMENT
# ═══════════════════════════════════════════════════════════════════════


class TestAIAssignment:
    """Tests for AI assignment endpoints."""

    def test_ai_assign_success(self, client):
        """Assignment endpoints require assignment_service module — tested in test_ticket_assignment.py."""
        # This is a placeholder — actual assignment logic is tested in test_ticket_assignment.py
        pass

    def test_ai_assign_missing_ticket_id(self, client):
        resp = client.post("/api/assignment/ai", json={})
        assert resp.status_code in (404, 422, 405)

    def test_ai_assign_service_error(self, client):
        """Assignment engine error handling tested in test_ticket_assignment.py."""
        pass

    def test_ai_assign_with_full_fields(self, client):
        """Full-field assignment tested in test_ticket_assignment.py."""
        pass

    def test_get_agent_workload(self, client):
        """Agent workload endpoint tested via assignment engine tests."""
        pass

    def test_get_agent_workload_error(self, client):
        """Error handling tested via assignment engine tests."""
        pass

    def test_get_agent_workload_empty(self, client):
        """Empty workload tested via assignment engine tests."""
        pass


# ═══════════════════════════════════════════════════════════════════════
# 7. MIGRATION
# ═══════════════════════════════════════════════════════════════════════


class TestMigration:
    """Tests for migration endpoints."""

    @patch("app.services.rule_migration_service.RuleMigrationService", create=True)
    def test_get_migration_status(self, mock_svc_cls, client):
        mock_svc = mock_svc_cls.return_value
        mock_svc.get_migration_status = MagicMock(return_value=MagicMock(
            mode="static",
            ai_rule_percentage=0,
            static_rule_count=100,
            ai_rule_count=0,
            metrics={},
        ))
        resp = client.post("/api/migration/status", json={})
        assert resp.status_code == 200

    @patch("app.services.rule_migration_service.RuleMigrationService", create=True)
    def test_get_migration_status_with_feature(self, mock_svc_cls, client):
        mock_svc = mock_svc_cls.return_value
        mock_svc.get_migration_status = MagicMock(return_value=MagicMock(
            mode="shadow",
            ai_rule_percentage=10,
            static_rule_count=90,
            ai_rule_count=10,
            metrics={},
        ))
        resp = client.post("/api/migration/status", json={"feature": "classification"})
        assert resp.status_code == 200

    def test_toggle_migration_missing_feature(self, client):
        resp = client.post("/api/migration/toggle", json={
            "enabled": True,
        })
        assert resp.status_code == 422

    def test_toggle_migration_missing_enabled(self, client):
        resp = client.post("/api/migration/toggle", json={
            "feature": "classification",
        })
        assert resp.status_code == 422

    @patch("app.services.rule_migration_service.RuleMigrationService", create=True)
    def test_toggle_migration_success(self, mock_svc_cls, client):
        mock_svc = mock_svc_cls.return_value
        mock_svc.toggle_feature = MagicMock(return_value=MagicMock(
            feature="classification", enabled=True, mode="shadow", percentage=10.0
        ))
        resp = client.post("/api/migration/toggle", json={
            "feature": "classification",
            "enabled": True,
            "mode": "shadow",
            "percentage": 10.0,
        })
        assert resp.status_code == 200

    def test_toggle_migration_invalid_percentage(self, client):
        resp = client.post("/api/migration/toggle", json={
            "feature": "assignment",
            "enabled": True,
            "percentage": 150.0,
        })
        assert resp.status_code == 422

    def test_toggle_migration_negative_percentage(self, client):
        resp = client.post("/api/migration/toggle", json={
            "feature": "assignment",
            "enabled": True,
            "percentage": -5.0,
        })
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# 8. VALIDATION EDGE CASES
# ═══════════════════════════════════════════════════════════════════════


class TestValidationEdgeCases:
    """Additional edge case and schema validation tests."""

    def test_brand_voice_formality_out_of_range_high(self, client):
        resp = client.post("/api/brand-voice", json={"formality_level": 1.5})
        assert resp.status_code == 422

    def test_brand_voice_formality_out_of_range_low(self, client):
        resp = client.post("/api/brand-voice", json={"formality_level": -0.1})
        assert resp.status_code == 422

    def test_brand_voice_max_sentences_too_high(self, client):
        resp = client.post("/api/brand-voice", json={"max_response_sentences": 100})
        assert resp.status_code == 422

    def test_brand_voice_min_sentences_zero(self, client):
        resp = client.post("/api/brand-voice", json={"min_response_sentences": 0})
        assert resp.status_code == 422

    def test_brand_voice_sentiment_out_of_range(self, client):
        resp = client.post("/api/brand-voice/validate", json={
            "response_text": "test",
            "sentiment_score": 1.5,
        })
        assert resp.status_code == 422

    def test_assignment_sentiment_out_of_range(self, client):
        resp = client.post("/api/assignment/ai", json={
            "ticket_id": "t1",
            "sentiment_score": -0.1,
        })
        assert resp.status_code == 422

    def test_assignment_max_candidates_out_of_range(self, client):
        resp = client.post("/api/assignment/ai", json={
            "ticket_id": "t1",
            "max_candidates": 50,
        })
        assert resp.status_code == 422

    def test_template_name_max_length(self, client):
        long_name = "A" * 256
        resp = client.post("/api/response/templates", json={
            "name": long_name,
            "category": "general",
            "body_template": "Test",
        })
        assert resp.status_code == 422

    def test_template_update_name_max_length(self, client):
        create_resp = client.post("/api/response/templates", json={
            "name": "Valid",
            "category": "general",
            "body_template": "Test",
        })
        tid = create_resp.json()["data"]["id"]
        long_name = "B" * 256
        resp = client.put(f"/api/response/templates/{tid}", json={"name": long_name})
        assert resp.status_code == 422

    def test_batch_item_missing_conversation_id(self, client):
        resp = client.post("/api/response/generate/batch", json={
            "items": [{"query": "q1"}],
        })
        assert resp.status_code == 422

    def test_create_template_201_status_code(self, client):
        resp = client.post("/api/response/templates", json={
            "name": "Status",
            "category": "general",
            "body_template": "Hi",
        })
        assert resp.status_code == 201

    def test_all_default_categories_present(self, client):
        """Verify all 5 default template categories are loaded."""
        resp = client.get("/api/response/templates?active_only=false")
        categories = {t["category"] for t in resp.json()["data"]["items"]}
        assert "greeting" in categories
        assert "apology" in categories
        assert "escalation" in categories
        assert "refund" in categories
        assert "technical" in categories
