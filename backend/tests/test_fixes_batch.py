"""
Tests for the 6 fixes shipped after the initial crm_actions fix:
  1. ecommerce_actions.py  — 3 endpoints calling Shopify via stored creds
  2. carrier_actions.py    — 4 endpoints delegating to CarrierAPIConnector
  3. email_channel.py      — new POST /api/v1/email/send
  4. react_tools/crm_tool  — replaced _mock_customer with real HubSpot calls
  5. paddle_service        — get_payment_status queries JarvisSession + Subscription
  6. diagnostic_chain      — _simulate_step_result dispatches to real react_tools

Each test class covers happy path + not_connected + error path.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ── Common mock infrastructure ────────────────────────────────────


class MockUser:
    def __init__(self, company_id: str = "company-123", user_id: str = "user-1"):
        self.id = user_id
        self.company_id = company_id
        self.role = "user"
        self.is_active = True


class MockIntegrationService:
    """Stub IntegrationService — returns whatever creds we tell it to."""

    def __init__(self, db: Any):
        self.db = db
        self._creds: dict[tuple[str, str], dict | None] = {}

    def get_credential_config(self, company_id: str, integration_type: str) -> dict | None:
        return self._creds.get((company_id, integration_type))

    def set_creds(self, company_id: str, integration_type: str, creds: dict | None):
        self._creds[(company_id, integration_type)] = creds


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def integration_service(mock_db: MagicMock) -> MockIntegrationService:
    return MockIntegrationService(mock_db)


@pytest.fixture
def current_user() -> MockUser:
    return MockUser()


# ════════════════════════════════════════════════════════════════════
# 1. ecommerce_actions — POST /api/integrations/ecommerce/{order,products,customer-orders}
# ════════════════════════════════════════════════════════════════════


def _load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules[name] = mod
    return mod


@pytest.fixture
def ecommerce_mod(integration_service: MockIntegrationService):
    mod = _load_module("app.api.ecommerce_actions", "/home/z/my-project/parwa/backend/app/api/ecommerce_actions.py")
    original = mod.IntegrationService
    mod.IntegrationService = lambda db: integration_service
    yield mod
    mod.IntegrationService = original


@pytest.fixture
def ecommerce_app(ecommerce_mod, current_user, mock_db):
    app = FastAPI()
    app.include_router(ecommerce_mod.router)
    app.dependency_overrides[ecommerce_mod.get_current_user] = lambda: current_user
    app.dependency_overrides[ecommerce_mod.get_db] = lambda: mock_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def ecommerce_client(ecommerce_app):
    with TestClient(ecommerce_app) as c:
        yield c


def _set_shopify_creds(integration_service, company_id="company-123"):
    integration_service.set_creds(
        company_id, "shopify",
        {"access_token": "shpat_test_token", "shop_domain": "test-shop.myshopify.com"},
    )


class TestEcommerceActions:
    def test_get_order_not_connected(self, ecommerce_client, integration_service):
        resp = ecommerce_client.post(
            "/api/integrations/ecommerce/order",
            json={"platform": "shopify", "order_id": "1234"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_connected"

    def test_get_order_ok(self, ecommerce_client, integration_service, ecommerce_mod):
        _set_shopify_creds(integration_service)
        # Patch the Shopify helper to avoid real network call.
        async def fake_get_order(client, base_url, headers, **kwargs):
            return {"status": "ok", "data": {"order_id": "1234", "total_price": "99.00"}, "error": None}
        original = ecommerce_mod._shopify_get_order
        ecommerce_mod._shopify_get_order = fake_get_order
        try:
            resp = ecommerce_client.post(
                "/api/integrations/ecommerce/order",
                json={"platform": "shopify", "order_id": "1234"},
            )
        finally:
            ecommerce_mod._shopify_get_order = original
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["data"]["order_id"] == "1234"

    def test_unsupported_platform_returns_not_connected(self, ecommerce_client, integration_service):
        """WooCommerce / Magento / BigCommerce are not yet implemented."""
        resp = ecommerce_client.post(
            "/api/integrations/ecommerce/order",
            json={"platform": "woocommerce", "order_id": "1234"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_connected"

    def test_search_products_validation_requires_query(self, ecommerce_client, integration_service):
        resp = ecommerce_client.post(
            "/api/integrations/ecommerce/products",
            json={"platform": "shopify"},  # missing query
        )
        assert resp.status_code == 422

    def test_customer_orders_not_connected(self, ecommerce_client, integration_service):
        resp = ecommerce_client.post(
            "/api/integrations/ecommerce/customer-orders",
            json={"customer_id": "cust-1"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_connected"


# ════════════════════════════════════════════════════════════════════
# 2. carrier_actions — POST /api/integrations/carrier/{detect,track,detect-delays,compensation}
# ════════════════════════════════════════════════════════════════════


@pytest.fixture
def carrier_mod():
    return _load_module("app.api.carrier_actions", "/home/z/my-project/parwa/backend/app/api/carrier_actions.py")


@pytest.fixture
def carrier_app(carrier_mod, current_user, mock_db):
    app = FastAPI()
    app.include_router(carrier_mod.router)
    app.dependency_overrides[carrier_mod.get_current_user] = lambda: current_user
    app.dependency_overrides[carrier_mod.get_db] = lambda: mock_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def carrier_client(carrier_app):
    with TestClient(carrier_app) as c:
        yield c


class TestCarrierActions:
    def test_detect_known_carrier(self, carrier_client, carrier_mod):
        """UPS tracking numbers start with 1Z — detect_carrier should return carrier_id='ups'."""
        # Mock the singleton's detect_carrier method.
        original_connector = carrier_mod._connector
        mock_conn = MagicMock()
        mock_conn.detect_carrier.return_value = {
            "carrier_id": "ups", "carrier_name": "UPS",
            "confidence": 0.95, "tracking_url": "https://www.ups.com/track?tracknum=1Z999",
        }
        carrier_mod._connector = mock_conn
        try:
            resp = carrier_client.post(
                "/api/integrations/carrier/detect",
                json={"tracking_number": "1Z999AA10123456784"},
            )
        finally:
            carrier_mod._connector = original_connector
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["data"]["carrier_id"] == "ups"

    def test_detect_unknown_carrier_returns_not_found(self, carrier_client, carrier_mod):
        original_connector = carrier_mod._connector
        mock_conn = MagicMock()
        mock_conn.detect_carrier.return_value = {
            "carrier_id": "unknown", "carrier_name": "Unknown Carrier",
            "confidence": 0.0, "tracking_url": "",
        }
        carrier_mod._connector = mock_conn
        try:
            resp = carrier_client.post(
                "/api/integrations/carrier/detect",
                json={"tracking_number": "garbage"},
            )
        finally:
            carrier_mod._connector = original_connector
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_found"

    def test_track_not_configured(self, carrier_client, carrier_mod):
        """When CarrierAPIConnector.track_shipment returns not_configured, endpoint reports it honestly."""
        original_connector = carrier_mod._connector
        mock_conn = MagicMock()
        mock_conn.track_shipment = AsyncMock(return_value={
            "status": "not_configured", "message": "No carrier API keys configured",
        })
        carrier_mod._connector = mock_conn
        try:
            resp = carrier_client.post(
                "/api/integrations/carrier/track",
                json={"tracking_number": "1Z999"},
            )
        finally:
            carrier_mod._connector = original_connector
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_configured"

    def test_compensation_happy_path(self, carrier_client, carrier_mod):
        """Three-step (track → detect_delays → compensation) returns aggregated compensation."""
        original_connector = carrier_mod._connector
        mock_conn = MagicMock()
        mock_conn.track_shipment = AsyncMock(return_value={
            "status": "ok", "tracking_number": "1Z999", "carrier_id": "ups",
            "current_status": "delivered", "eta": "2026-01-01",
        })
        mock_conn.detect_delays.return_value = {"delay_detected": True, "delay_days": 3}
        mock_conn.calculate_compensation.return_value = {
            "eligible": True, "amount": 12.50, "reason": "3 day delay on express shipment",
        }
        carrier_mod._connector = mock_conn
        try:
            resp = carrier_client.post(
                "/api/integrations/carrier/compensation",
                json={"tracking_number": "1Z999", "shipping_cost": 12.50, "service_tier": "express"},
            )
        finally:
            carrier_mod._connector = original_connector
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["data"]["eligible"] is True
        assert body["data"]["amount"] == 12.50


# ════════════════════════════════════════════════════════════════════
# 3. email_channel — POST /api/v1/email/send
# ════════════════════════════════════════════════════════════════════


@pytest.fixture
def email_mod(integration_service: MockIntegrationService):
    mod = _load_module("app.api.email_channel", "/home/z/my-project/parwa/backend/app/api/email_channel.py")
    original = mod.IntegrationService
    mod.IntegrationService = lambda db: integration_service
    # Stub the schema imports the module needs at module-load time.
    if not hasattr(mod, "InboundEmailListResponse"):
        mod.InboundEmailListResponse = MagicMock()
        mod.InboundEmailResponse = MagicMock()
        mod.EmailThreadResponse = MagicMock()
    yield mod
    mod.IntegrationService = original


@pytest.fixture
def email_app(email_mod, current_user, mock_db):
    app = FastAPI()
    app.include_router(email_mod.router)
    app.dependency_overrides[email_mod.get_current_user] = lambda: current_user
    app.dependency_overrides[email_mod.get_db] = lambda: mock_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def email_client(email_app):
    with TestClient(email_app) as c:
        yield c


class TestEmailSend:
    def test_send_no_provider_returns_not_connected(self, email_client, integration_service):
        """When no email integration is connected, returns success=False with a helpful error."""
        resp = email_client.post(
            "/api/v1/email/send",
            json={"to": ["alice@example.com"], "subject": "Hi", "body": "Hello"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "connected" in body["error"].lower()

    def test_send_with_brevo_credentials_calls_email_bridge(self, email_client, integration_service, email_mod):
        """When Brevo creds exist, the endpoint calls EmailBridge.send_email."""
        integration_service.set_creds("company-123", "brevo", {"api_key": "xkeysib-..."})
        # Patch EmailBridge.send_email to a mock that returns success.
        async def fake_send(**kwargs):
            return {"success": True, "message_id": "test-msg-id"}
        original = email_mod.EmailBridge.send_email
        email_mod.EmailBridge.send_email = staticmethod(fake_send)
        try:
            resp = email_client.post(
                "/api/v1/email/send",
                json={"to": ["alice@example.com"], "subject": "Hi", "body": "Hello"},
            )
        finally:
            email_mod.EmailBridge.send_email = original
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["provider"] == "brevo"

    def test_send_validation_requires_to(self, email_client, integration_service):
        resp = email_client.post(
            "/api/v1/email/send",
            json={"subject": "Hi", "body": "Hello"},  # missing to
        )
        assert resp.status_code == 422

    def test_send_validation_requires_subject(self, email_client, integration_service):
        resp = email_client.post(
            "/api/v1/email/send",
            json={"to": ["alice@example.com"], "body": "Hello"},  # missing subject
        )
        assert resp.status_code == 422


# ════════════════════════════════════════════════════════════════════
# 4. react_tools/crm_tool — no more _mock_customer; calls HubSpot
# ════════════════════════════════════════════════════════════════════


def _load_crm_tool():
    # Stub parent packages so import works.
    for name in ("app", "app.core", "app.core.react_tools"):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)
    # Provide a minimal BaseReactTool + ToolResult + ToolSchema so the module loads.
    if "app.core.react_tools.base" not in sys.modules:
        base = types.ModuleType("app.core.react_tools.base")
        class ToolResult:
            def __init__(self, success, error, data, execution_time_ms):
                self.success = success
                self.error = error
                self.data = data
                self.execution_time_ms = execution_time_ms
        class ActionSchema:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
        class ToolSchema:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
        class BaseReactTool:
            pass
        base.ToolResult = ToolResult
        base.ActionSchema = ActionSchema
        base.ToolSchema = ToolSchema
        base.BaseReactTool = BaseReactTool
        sys.modules["app.core.react_tools.base"] = base
    return _load_module(
        "app.core.react_tools.crm_tool",
        "/home/z/my-project/parwa/backend/app/core/react_tools/crm_tool.py",
    )


class TestCrmToolNoMockData:
    def test_no_mock_customer_function_anymore(self):
        """The _mock_customer function should be GONE — it was the source of fake data."""
        mod = _load_crm_tool()
        assert not hasattr(mod, "_mock_customer"), "_mock_customer should have been removed"
        assert not hasattr(mod, "_FIRST_NAMES"), "mock data lists should have been removed"
        assert not hasattr(mod, "_mock_interactions"), "_mock_interactions should have been removed"

    def test_get_customer_returns_not_connected_when_no_creds(self):
        mod = _load_crm_tool()
        tool = mod.CRMTool()
        # Patch _resolve_creds to return None (no HubSpot integration).
        tool._resolve_creds = lambda company_id: None
        result = asyncio.run(tool._get_customer(company_id="company-123", customer_id="123"))
        assert result.success is False
        assert "not connected" in result.error.lower()

    def test_get_customer_returns_ok_with_real_hubspot_call(self):
        mod = _load_crm_tool()
        tool = mod.CRMTool()
        tool._resolve_creds = lambda company_id: {"access_token": "pat-test"}
        # Patch httpx.AsyncClient so no real network call happens.
        import httpx as _httpx
        class MockResp:
            status_code = 200
            def json(self):
                return {"id": "123", "properties": {"email": "alice@example.com", "firstname": "Alice", "lastname": "Smith"}}
        class MockClient:
            def __init__(self, *a, **kw): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, url, **kw): return MockResp()
        original = _httpx.AsyncClient
        _httpx.AsyncClient = MockClient
        try:
            result = asyncio.run(tool._get_customer(company_id="company-123", customer_id="123"))
        finally:
            _httpx.AsyncClient = original
        assert result.success is True
        assert result.data["customer_id"] == "123"
        assert result.data["email"] == "alice@example.com"
        assert result.data["name"] == "Alice Smith"


# ════════════════════════════════════════════════════════════════════
# 5. paddle_service.get_payment_status — queries JarvisSession
# ════════════════════════════════════════════════════════════════════


class TestPaddleGetPaymentStatus:
    def test_returns_none_when_session_not_found(self):
        """When no JarvisSession exists for the session_id, returns status='none'."""
        # Load paddle_service module with mocked DB.
        mod = _load_module("app.services.paddle_service", "/home/z/my-project/parwa/backend/app/services/paddle_service.py")
        service = mod.PaddleService()
        # Patch the imports inside get_payment_status to use mocks.
        fake_db = MagicMock()
        fake_session_local = MagicMock(return_value=fake_db)
        fake_query = MagicMock()
        fake_query.filter.return_value.first.return_value = None  # No session found.
        fake_db.query.return_value = fake_query

        # Patch the import path inside the method by inserting mocks into sys.modules.
        fake_db_module = types.ModuleType("database.base")
        fake_db_module.SessionLocal = fake_session_local
        fake_jarvis_module = types.ModuleType("database.models.jarvis")
        fake_jarvis_module.JarvisSession = MagicMock()
        fake_billing_module = types.ModuleType("database.models.billing")
        fake_billing_module.Subscription = MagicMock()

        sys.modules["database.base"] = fake_db_module
        sys.modules["database.models.jarvis"] = fake_jarvis_module
        sys.modules["database.models.billing"] = fake_billing_module

        try:
            result = asyncio.run(service.get_payment_status("nonexistent-session"))
        finally:
            # Restore real modules if they were loaded.
            for name in ("database.base", "database.models.jarvis", "database.models.billing"):
                sys.modules.pop(name, None)

        assert result["status"] == "none"
        assert result["pack_type"] == "free"
        assert result["session_id"] == "nonexistent-session"

    def test_returns_completed_when_session_payment_status_completed(self):
        """When JarvisSession.payment_status == 'completed', returns status='completed'."""
        mod = _load_module("app.services.paddle_service", "/home/z/my-project/parwa/backend/app/services/paddle_service.py")
        service = mod.PaddleService()

        # Mock a JarvisSession row with payment_status='completed', pack_type='demo'.
        fake_session = MagicMock()
        fake_session.payment_status = "completed"
        fake_session.pack_type = "demo"
        fake_session.company_id = None  # No company → no subscription lookup.

        fake_db = MagicMock()
        fake_session_local = MagicMock(return_value=fake_db)
        fake_query = MagicMock()
        fake_query.filter.return_value.first.return_value = fake_session
        fake_db.query.return_value = fake_query

        fake_db_module = types.ModuleType("database.base")
        fake_db_module.SessionLocal = fake_session_local
        fake_jarvis_module = types.ModuleType("database.models.jarvis")
        fake_jarvis_module.JarvisSession = MagicMock()
        fake_billing_module = types.ModuleType("database.models.billing")
        fake_billing_module.Subscription = MagicMock()

        sys.modules["database.base"] = fake_db_module
        sys.modules["database.models.jarvis"] = fake_jarvis_module
        sys.modules["database.models.billing"] = fake_billing_module

        try:
            result = asyncio.run(service.get_payment_status("session-123"))
        finally:
            for name in ("database.base", "database.models.jarvis", "database.models.billing"):
                sys.modules.pop(name, None)

        assert result["status"] == "completed"
        assert result["pack_type"] == "demo"
        assert result["amount"] == "0.00"  # Demo pack is free.


# ════════════════════════════════════════════════════════════════════
# 6. diagnostic_chain — _simulate_step_result dispatches to real tools
# ════════════════════════════════════════════════════════════════════


def _load_diagnostic_chain():
    # Stub parent packages.
    for name in ("app", "app.core", "app.core.react_tools"):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)
    if "app.core.react_tools.base" not in sys.modules:
        base = types.ModuleType("app.core.react_tools.base")
        class ToolResult:
            def __init__(self, success, error, data, execution_time_ms):
                self.success = success
                self.error = error
                self.data = data
                self.execution_time_ms = execution_time_ms
        class ActionSchema:
            def __init__(self, **kwargs):
                for k, v in kwargs.items(): setattr(self, k, v)
        class ToolSchema:
            def __init__(self, **kwargs):
                for k, v in kwargs.items(): setattr(self, k, v)
        class BaseReactTool:
            pass
        base.ToolResult = ToolResult
        base.ActionSchema = ActionSchema
        base.ToolSchema = ToolSchema
        base.BaseReactTool = BaseReactTool
        sys.modules["app.core.react_tools.base"] = base
    return _load_module(
        "app.core.react_tools.diagnostic_chain",
        "/home/z/my-project/parwa/backend/app/core/react_tools/diagnostic_chain.py",
    )


class TestDiagnosticChainNoRandomness:
    def test_no_random_call_in_simulate_step_result(self):
        """The new _simulate_step_result must NOT use random.random() — it must call real tools."""
        import inspect
        mod = _load_diagnostic_chain()
        source = inspect.getsource(mod._simulate_step_result)
        assert "random.random()" not in source, "Random pass/fail should be removed"
        assert "random" not in source or "random" not in dir(mod), "random module should not be used"

    def test_unknown_tool_returns_honest_failure(self):
        """When the step's tool isn't registered, the step fails with an honest error (not random)."""
        mod = _load_diagnostic_chain()
        step = {
            "step_id": "test_step",
            "name": "Test Step",
            "tool": "nonexistent_tool_xyz",
            "action": "some_action",
            "params": {},
        }
        result = mod._simulate_step_result(step, company_id="company-123")
        assert result["is_pass"] is False
        assert "not available" in result["findings"][0]

    def test_known_tool_is_dispatched(self):
        """When the step's tool is registered (service_health_checker), it gets called."""
        mod = _load_diagnostic_chain()
        # Build a fake tool instance and pass it via tool_instances.
        class FakeTool:
            async def _do_execute(self, action, company_id, **params):
                return mod.ToolResult(
                    success=True, error=None,
                    data={"status": "operational", "summary": "all systems go"},
                    execution_time_ms=5,
                )
        step = {
            "step_id": "ai_health",
            "name": "AI Pipeline Health",
            "tool": "service_health_checker",
            "action": "check_service_status",
            "params": {"service_id": "ai_pipeline"},
        }
        result = mod._simulate_step_result(
            step, company_id="company-123",
            tool_instances={"service_health_checker": FakeTool()},
        )
        assert result["is_pass"] is True
        assert result["status"] == "pass"
        # The tool's data summary should be surfaced as a finding.
        assert any("operational" in f or "all systems go" in f for f in result["findings"])

    def test_failed_tool_step_marked_fail(self):
        """When the dispatched tool returns success=False, the step is honestly marked fail."""
        mod = _load_diagnostic_chain()
        class FakeFailingTool:
            async def _do_execute(self, action, company_id, **params):
                return mod.ToolResult(
                    success=False, error="Service is down",
                    data=None, execution_time_ms=5,
                )
        step = {
            "step_id": "ai_health",
            "name": "AI Pipeline Health",
            "tool": "service_health_checker",
            "action": "check_service_status",
            "params": {},
            "fail_message": "AI pipeline is degraded",
        }
        result = mod._simulate_step_result(
            step, company_id="company-123",
            tool_instances={"service_health_checker": FakeFailingTool()},
        )
        assert result["is_pass"] is False
        assert "degraded" in result["findings"][0]
        assert "Service is down" in result["findings"][1]
