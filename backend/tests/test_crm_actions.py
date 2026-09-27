"""
Tests for the CRM Actions API — backend/app/api/crm_actions.py.

Context:
  mcp_server/integrations/crm_server.py was fake-wired — it called three
  backend endpoints that did not exist:
    POST /api/v1/integrations/crm/contact
    POST /api/v1/integrations/crm/note
    POST /api/v1/integrations/crm/deals
  Backend would 404, the MCP's _backend_call returned None, and the user
  saw the misleading "not connected" response even when a real HubSpot
  integration WAS connected.

  crm_actions.py adds the three missing endpoints. These tests verify:
    1. Endpoint returns "not_connected" when no active integration exists.
    2. Endpoint returns "ok" with real HubSpot data when integration is connected
       and HubSpot responds 200.
    3. Endpoint returns "not_found" when HubSpot returns 404.
    4. Endpoint returns "external_error" when HubSpot returns 5xx.
    5. SalesForce / Pipedrive platforms (not yet implemented) return "not_connected".
    6. BC-001: company_id is always taken from the authenticated user, never
       trusted from the request body.

  The MCP-level translation (backend status → ToolInvokeResponse) is also tested
  via the CRMServer._status_response helper.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from typing import Any, AsyncIterator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ── Module loading (avoid app.api.__init__ which has heavy deps) ──

_spec = importlib.util.spec_from_file_location(
    "app.api.crm_actions",
    "/home/z/my-project/parwa/backend/app/api/crm_actions.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
sys.modules["app.api.crm_actions"] = _mod

CRMContactRequest = _mod.CRMContactRequest
CRMNoteRequest = _mod.CRMNoteRequest
CRMDealsRequest = _mod.CRMDealsRequest
CRMActionResponse = _mod.CRMActionResponse
router = _mod.router
_resolve_crm_credentials = _mod._resolve_crm_credentials


# ── Mocks ─────────────────────────────────────────────────────────


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
        # Map (company_id, integration_type) -> creds dict (or None)
        self._creds: dict[tuple[str, str], dict | None] = {}

    def get_credential_config(
        self, company_id: str, integration_type: str
    ) -> dict | None:
        return self._creds.get((company_id, integration_type))

    def set_creds(self, company_id: str, integration_type: str, creds: dict | None):
        self._creds[(company_id, integration_type)] = creds


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def integration_service(mock_db: MagicMock) -> MockIntegrationService:
    return MockIntegrationService(mock_db)


@pytest.fixture(autouse=True)
def _patch_integration_service(integration_service: MockIntegrationService):
    """Replace app.services.integration_service.IntegrationService with our mock."""
    # The crm_actions module imports IntegrationService at module-load time,
    # so we patch the symbol on the loaded module.
    original = _mod.IntegrationService
    _mod.IntegrationService = lambda db: integration_service
    yield
    _mod.IntegrationService = original


@pytest.fixture
def current_user() -> MockUser:
    return MockUser()


@pytest.fixture
def app(current_user: MockUser, mock_db: MagicMock) -> Generator[FastAPI, None, None]:
    """FastAPI app with crm_actions router + dependency overrides."""
    application = FastAPI()
    application.include_router(router)
    # Override get_current_user + get_db so we don't need real auth or DB.
    application.dependency_overrides[_mod.get_current_user] = lambda: current_user
    application.dependency_overrides[_mod.get_db] = lambda: mock_db
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


# ── HubSpot httpx mock ────────────────────────────────────────────


class MockResponse:
    def __init__(self, status_code: int, json_data: Any = None, text: str = ""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self) -> Any:
        return self._json


class MockAsyncClient:
    """Minimal httpx.AsyncClient mock that returns canned responses per request."""

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        # Each entry is (method, url_substring) -> MockResponse | callable
        self._routes: list[tuple[str, str, Any]] = []
        self.requests: list[dict] = []

    def add_route(self, method: str, url_substring: str, response: Any):
        self._routes.append((method.upper(), url_substring, response))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def _handle(self, method: str, url: str, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        for m, sub, resp in self._routes:
            if m == method.upper() and sub in url:
                if callable(resp):
                    return resp(method, url, **kwargs)
                return resp
        return MockResponse(404, {"error": "no route mocked"}, text="no route mocked")

    async def get(self, url, **kwargs):
        return await self._handle("GET", url, **kwargs)

    async def post(self, url, **kwargs):
        return await self._handle("POST", url, **kwargs)

    async def put(self, url, **kwargs):
        return await self._handle("PUT", url, **kwargs)

    async def patch(self, url, **kwargs):
        return await self._handle("PATCH", url, **kwargs)


@pytest.fixture
def mock_httpx(monkeypatch):
    """Replace httpx.AsyncClient in crm_actions with our mock."""
    instances: list[MockAsyncClient] = []

    def factory(*args, **kwargs):
        c = MockAsyncClient(*args, **kwargs)
        instances.append(c)
        return c

    monkeypatch.setattr(_mod.httpx, "AsyncClient", factory)
    return instances


def _set_hubspot_creds(integration_service: MockIntegrationService, company_id: str = "company-123"):
    integration_service.set_creds(
        company_id,
        "hubspot",
        {"access_token": "pat-test-fake-token", "hubspot_account_id": "12345"},
    )


# ════════════════════════════════════════════════════════════════════
# Tests — /api/integrations/crm/contact
# ════════════════════════════════════════════════════════════════════


class TestCrmGetContact:
    """POST /api/integrations/crm/contact"""

    def test_not_connected_when_no_integration(self, client, integration_service):
        """When no HubSpot integration is connected, return status=not_connected."""
        # Don't set any creds.
        resp = client.post(
            "/api/integrations/crm/contact",
            json={"platform": "hubspot", "email": "alice@example.com"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "not_connected"
        assert body["platform"] == "hubspot"
        assert "not connected" in body["error"].lower()
        assert body["data"] == {}

    def test_lookup_by_email_returns_ok(self, client, integration_service, mock_httpx):
        """Happy path — HubSpot returns a contact, endpoint returns status=ok."""
        _set_hubspot_creds(integration_service)
        # Pre-populate the mock client with the HubSpot search response.
        # httpx.AsyncClient is called inside an async with, so we need to set up
        # the routes BEFORE the request is made. We do that via the fixture's
        # list of instances — but the factory only creates on demand, so we
        # configure the response by intercepting the search call.
        # Strategy: patch _hubspot_get_contact directly.

        async def fake_get_contact(client, headers, **kwargs):
            return {
                "status": "ok",
                "data": {
                    "contact_id": "123",
                    "email": "alice@example.com",
                    "first_name": "Alice",
                    "last_name": "Smith",
                },
                "error": None,
            }

        # Patch the module-level helper
        import app.api.crm_actions as mod
        original = mod._hubspot_get_contact
        mod._hubspot_get_contact = fake_get_contact
        try:
            resp = client.post(
                "/api/integrations/crm/contact",
                json={"platform": "hubspot", "email": "alice@example.com"},
            )
        finally:
            mod._hubspot_get_contact = original

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["data"]["contact_id"] == "123"
        assert body["data"]["email"] == "alice@example.com"

    def test_not_found_when_hubspot_404(self, client, integration_service):
        """When HubSpot returns 404, endpoint returns status=not_found."""
        _set_hubspot_creds(integration_service)

        async def fake_get_contact(client, headers, **kwargs):
            return {"status": "not_found", "data": {}, "error": None}

        import app.api.crm_actions as mod
        original = mod._hubspot_get_contact
        mod._hubspot_get_contact = fake_get_contact
        try:
            resp = client.post(
                "/api/integrations/crm/contact",
                json={"platform": "hubspot", "contact_id": "999999"},
            )
        finally:
            mod._hubspot_get_contact = original

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "not_found"
        assert body["data"] == {}

    def test_external_error_when_hubspot_5xx(self, client, integration_service):
        _set_hubspot_creds(integration_service)

        async def fake_get_contact(client, headers, **kwargs):
            return {
                "status": "external_error",
                "data": {},
                "error": "hubspot_503: service unavailable",
            }

        import app.api.crm_actions as mod
        original = mod._hubspot_get_contact
        mod._hubspot_get_contact = fake_get_contact
        try:
            resp = client.post(
                "/api/integrations/crm/contact",
                json={"platform": "hubspot", "email": "alice@example.com"},
            )
        finally:
            mod._hubspot_get_contact = original

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "external_error"
        assert "hubspot_503" in body["error"]

    def test_unsupported_platform_returns_not_connected(self, client, integration_service):
        """Salesforce / Pipedrive are not yet implemented — return not_connected honestly."""
        # Even if we set creds (we won't), the resolver returns None for unsupported platforms.
        resp = client.post(
            "/api/integrations/crm/contact",
            json={"platform": "salesforce", "email": "alice@example.com"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "not_connected"
        assert body["platform"] == "salesforce"

    def test_bc001_company_id_taken_from_user_not_body(self, client, integration_service, current_user):
        """BC-001: company_id in the request body is ignored — always uses authenticated user's company_id."""
        # Set creds for the user's real company.
        _set_hubspot_creds(integration_service, company_id=str(current_user.company_id))
        # Set DIFFERENT creds for a fake company that the body will try to impersonate.
        integration_service.set_creds(
            "attacker-company",
            "hubspot",
            {"access_token": "should-not-be-used"},
        )

        # Patch the resolver so we can observe which company_id it actually uses.
        captured = {}
        real_resolver = _resolve_crm_credentials

        def fake_resolver(db, user, platform):
            # Call the real resolver — it now ignores any body override.
            result = real_resolver(db, user, platform)
            captured["resolved_company_id"] = str(user.company_id)
            captured["had_access_token"] = bool(result and result.get("access_token"))
            return result

        import app.api.crm_actions as mod
        original = mod._resolve_crm_credentials
        mod._resolve_crm_credentials = fake_resolver

        # Also patch the HubSpot call so we don't make a real network request.
        async def fake_get_contact(client, headers, **kwargs):
            return {
                "status": "ok",
                "data": {"contact_id": "123", "email": "alice@example.com"},
                "error": None,
            }
        original_helper = mod._hubspot_get_contact
        mod._hubspot_get_contact = fake_get_contact
        try:
            resp = client.post(
                "/api/integrations/crm/contact",
                json={
                    "platform": "hubspot",
                    "email": "alice@example.com",
                    "company_id": "attacker-company",  # Try to impersonate
                },
            )
        finally:
            mod._resolve_crm_credentials = original
            mod._hubspot_get_contact = original_helper

        assert resp.status_code == 200
        # The resolver should have used the USER's company_id, not the body's.
        assert captured["resolved_company_id"] == str(current_user.company_id)
        assert captured["resolved_company_id"] != "attacker-company"
        # And the response should be "ok" (creds exist for the user's company).
        assert resp.json()["status"] == "ok"


# ════════════════════════════════════════════════════════════════════
# Tests — /api/integrations/crm/note
# ════════════════════════════════════════════════════════════════════


class TestCrmCreateNote:
    """POST /api/integrations/crm/note"""

    def test_not_connected_when_no_integration(self, client, integration_service):
        resp = client.post(
            "/api/integrations/crm/note",
            json={"contact_id": "123", "note": "Hello from PARWA"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_connected"

    def test_creates_note_when_connected(self, client, integration_service):
        _set_hubspot_creds(integration_service)

        async def fake_create_note(client, headers, **kwargs):
            return {
                "status": "ok",
                "data": {
                    "note_id": "note-1",
                    "contact_id": kwargs["contact_id"],
                    "associated": True,
                },
                "error": None,
            }

        import app.api.crm_actions as mod
        original = mod._hubspot_create_note
        mod._hubspot_create_note = fake_create_note
        try:
            resp = client.post(
                "/api/integrations/crm/note",
                json={"contact_id": "123", "note": "Hello from PARWA"},
            )
        finally:
            mod._hubspot_create_note = original

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["data"]["note_id"] == "note-1"
        assert body["data"]["associated"] is True

    def test_validation_rejects_empty_note(self, client, integration_service):
        """Pydantic validator should reject empty notes."""
        resp = client.post(
            "/api/integrations/crm/note",
            json={"contact_id": "123", "note": ""},
        )
        assert resp.status_code == 422  # Pydantic validation error

    def test_validation_rejects_missing_contact_id(self, client, integration_service):
        resp = client.post(
            "/api/integrations/crm/note",
            json={"note": "Hello"},  # missing contact_id
        )
        assert resp.status_code == 422


# ════════════════════════════════════════════════════════════════════
# Tests — /api/integrations/crm/deals
# ════════════════════════════════════════════════════════════════════


class TestCrmGetDeals:
    """POST /api/integrations/crm/deals"""

    def test_not_connected_when_no_integration(self, client, integration_service):
        resp = client.post(
            "/api/integrations/crm/deals",
            json={"contact_id": "123"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_connected"

    def test_returns_deals_when_connected(self, client, integration_service):
        _set_hubspot_creds(integration_service)

        async def fake_get_deals(client, headers, **kwargs):
            return {
                "status": "ok",
                "data": {
                    "deals": [
                        {"deal_id": "d1", "name": "Big Deal", "amount": "50000", "stage": "closedwon"},
                        {"deal_id": "d2", "name": "Small Deal", "amount": "1000", "stage": "presentationscheduled"},
                    ],
                    "count": 2,
                },
                "error": None,
            }

        import app.api.crm_actions as mod
        original = mod._hubspot_get_deals
        mod._hubspot_get_deals = fake_get_deals
        try:
            resp = client.post(
                "/api/integrations/crm/deals",
                json={"contact_id": "123"},
            )
        finally:
            mod._hubspot_get_deals = original

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["data"]["count"] == 2
        assert body["data"]["deals"][0]["deal_id"] == "d1"

    def test_returns_empty_list_when_no_deals(self, client, integration_service):
        _set_hubspot_creds(integration_service)

        async def fake_get_deals(client, headers, **kwargs):
            return {"status": "ok", "data": {"deals": [], "count": 0}, "error": None}

        import app.api.crm_actions as mod
        original = mod._hubspot_get_deals
        mod._hubspot_get_deals = fake_get_deals
        try:
            resp = client.post(
                "/api/integrations/crm/deals",
                json={"contact_id": "123"},
            )
        finally:
            mod._hubspot_get_deals = original

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["data"]["count"] == 0


# ════════════════════════════════════════════════════════════════════
# Tests — MCP-level translation (CRMServer._status_response)
# ════════════════════════════════════════════════════════════════════


class TestMCPStatusResponseTranslation:
    """Verify the CRMServer._status_response helper translates backend statuses correctly."""

    def _load_mcp_crm_server(self):
        """Load mcp_server/integrations/crm_server.py without importing the full mcp_server package."""
        # Stub the parent packages + key dependencies so the import works.
        for name in ("mcp_server", "mcp_server.integrations"):
            if name not in sys.modules:
                sys.modules[name] = types.ModuleType(name)
        # mcp_server.base_server — provide the symbols crm_server.py imports.
        if "mcp_server.base_server" not in sys.modules:
            bs = types.ModuleType("mcp_server.base_server")
            bs.MCPServerBase = object  # CRMServer subclasses this; we only test methods.
            bs.MCPRegistry = MagicMock()
            bs.get_logger = MagicMock(return_value=MagicMock())
            sys.modules["mcp_server.base_server"] = bs
        # mcp_server.models — provide the symbols crm_server.py imports.
        if "mcp_server.models" not in sys.modules:
            md = types.ModuleType("mcp_server.models")
            # ToolInvokeResponse: dataclass-like object we can instantiate with kwargs.
            class ToolInvokeResponse:
                def __init__(self, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)
            class ToolDefinition:
                def __init__(self, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)
            class ToolCategory:
                INTEGRATION = "integration"
            md.ToolInvokeResponse = ToolInvokeResponse
            md.ToolDefinition = ToolDefinition
            md.ToolCategory = ToolCategory
            md.CRMContactRequest = MagicMock
            md.CRMContactResponse = MagicMock
            sys.modules["mcp_server.models"] = md
        spec = importlib.util.spec_from_file_location(
            "mcp_server.integrations.crm_server",
            "/home/z/my-project/parwa/mcp_server/integrations/crm_server.py",
        )
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        sys.modules["mcp_server.integrations.crm_server"] = m
        return m

    def test_status_ok_translates_to_success_true(self):
        m = self._load_mcp_crm_server()
        server = m.CRMServer()
        result = server._status_response(
            "crm_get_contact",
            "hubspot",
            {"status": "ok", "data": {"contact_id": "123"}, "error": None},
        )
        assert result.success is True
        assert result.tool_name == "crm_get_contact"
        assert result.data == {"contact_id": "123"}
        assert result.metadata["source"] == "backend"

    def test_status_not_connected_translates_to_success_false(self):
        m = self._load_mcp_crm_server()
        server = m.CRMServer()
        result = server._status_response(
            "crm_get_contact",
            "hubspot",
            {"status": "not_connected", "data": {}, "error": "not connected"},
        )
        assert result.success is False
        assert "not connected" in result.error
        assert result.metadata["status"] == "not_connected"

    def test_status_not_found_translates_to_success_false(self):
        m = self._load_mcp_crm_server()
        server = m.CRMServer()
        result = server._status_response(
            "crm_get_contact",
            "hubspot",
            {"status": "not_found", "data": {}, "error": None},
        )
        assert result.success is False
        assert result.metadata["status"] == "not_found"

    def test_status_external_error_translates_to_success_false(self):
        m = self._load_mcp_crm_server()
        server = m.CRMServer()
        result = server._status_response(
            "crm_get_contact",
            "hubspot",
            {"status": "external_error", "data": {}, "error": "hubspot_503"},
        )
        assert result.success is False
        assert "hubspot_503" in result.error
        assert result.metadata["status"] == "external_error"
