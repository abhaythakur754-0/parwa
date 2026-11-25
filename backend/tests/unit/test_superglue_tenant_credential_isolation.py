"""Superglue tenant credential API isolation tests."""

import pytest

from app.core import superglue_client


class _Response:
    def __init__(self, status_code, body, text=""):
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self):
        return self._body


class _Client:
    def __init__(self, calls):
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return _Response(404, {})

    async def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return _Response(201, {"data": {"id": "connection-1", "systemId": "hubspot"}})

    async def patch(self, url, **kwargs):
        self.calls.append(("PATCH", url, kwargs))
        return _Response(200, {"data": {"id": "connection-1", "systemId": "hubspot"}})

    async def delete(self, url, **kwargs):
        self.calls.append(("DELETE", url, kwargs))
        return _Response(204, {})


@pytest.mark.asyncio
async def test_customer_secrets_are_posted_to_connections_with_tenant_key(monkeypatch):
    calls = []
    monkeypatch.setattr(superglue_client, "is_configured", lambda: True)
    monkeypatch.setattr(
        superglue_client, "_get_config",
        lambda: ("https://sg.test/sgapi", "admin-secret"),
    )
    monkeypatch.setattr(superglue_client, "_session_headers", lambda: {})
    monkeypatch.setattr(
        superglue_client.httpx,
        "AsyncClient",
        lambda **kwargs: _Client(calls),
    )

    result = await superglue_client.create_system(
        system_id="hubspot",
        name="HubSpot",
        url="https://api.hubapi.com",
        tenant_id="tenant-1",
        credentials={"api_key": "customer-secret"},
        metadata={"auth_type": "api_key"},
        customer_api_key="tenant-service-account-key",
        credential_url="https://api.hubapi.com",
    )

    assert result["success"] is True
    get_call, post_call = calls
    assert get_call[0] == "GET"
    assert get_call[1].endswith("/v1/connections")
    assert get_call[2]["headers"]["Authorization"] == "Bearer tenant-service-account-key"
    assert post_call[0] == "POST"
    assert post_call[1].endswith("/v1/connections")
    assert post_call[2]["headers"]["Authorization"] == "Bearer tenant-service-account-key"
    assert post_call[2]["json"]["systemId"] == "hubspot"
    assert post_call[2]["json"]["authentication"] == {"type": "api_key"}
    assert post_call[2]["json"]["credentials"] == {"api_key": "customer-secret"}
    assert "admin-secret" not in str(post_call)


@pytest.mark.asyncio
async def test_oauth_connection_status_uses_tenant_connections_endpoint(monkeypatch):
    calls = []

    class OAuthClient(_Client):
        async def get(self, url, **kwargs):
            calls.append(("GET", url, kwargs))
            return _Response(200, {"data": [{
                "id": "connection-1",
                "systemId": "hubspot",
                "credentialKeys": [{"key": "access_token", "hasValue": True}],
            }]})

    monkeypatch.setattr(superglue_client, "is_configured", lambda: True)
    monkeypatch.setattr(superglue_client, "_get_config", lambda: ("https://sg.test/sgapi", "admin-secret"))
    monkeypatch.setattr(superglue_client, "_get_tenant_api_key", lambda tenant_id: "tenant-key")
    monkeypatch.setattr(superglue_client, "_session_headers", lambda: {})
    monkeypatch.setattr(superglue_client.httpx, "AsyncClient", lambda **kwargs: OAuthClient(calls))

    result = await superglue_client.check_oauth_credentials("hubspot", "tenant-1")

    assert result == {"success": True, "connected": True}
    assert calls[0][1].endswith("/v1/connections")
    assert calls[0][2]["headers"]["Authorization"] == "Bearer tenant-key"
    assert calls[0][2]["params"] == {"systemId": "hubspot"}




@pytest.mark.asyncio
async def test_oauth_exchange_uses_tenant_service_account_and_configured_app(monkeypatch):
    calls = []

    class OAuthStartClient(_Client):
        async def get(self, url, **kwargs):
            calls.append(("GET", url, kwargs))
            return _Response(200, {"data": [{"id": "oauth-app-1", "systemId": "hubspot"}]})

        async def post(self, url, **kwargs):
            calls.append(("POST", url, kwargs))
            return _Response(201, {"data": {"authorizationUrl": "https://provider.example/authorize"}})

    monkeypatch.setattr(superglue_client, "is_configured", lambda: True)
    monkeypatch.setattr(superglue_client, "_get_config", lambda: ("https://sg.test/sgapi", "admin-secret"))
    monkeypatch.setattr(superglue_client, "_get_tenant_api_key", lambda tenant_id: "tenant-key")
    monkeypatch.setattr(superglue_client, "_session_headers", lambda: {})
    monkeypatch.setattr(superglue_client.httpx, "AsyncClient", lambda **kwargs: OAuthStartClient(calls))

    result = await superglue_client.start_oauth_exchange("hubspot", "tenant-1")

    assert result == {"success": True, "authorization_url": "https://provider.example/authorize"}
    assert calls[0][0] == "GET"
    assert calls[0][1].endswith("/v1/oauth-apps")
    assert calls[0][2]["headers"]["Authorization"] == "Bearer tenant-key"
    assert calls[1][0] == "POST"
    assert calls[1][1].endswith("/v1/oauth/exchanges")
    assert calls[1][2]["headers"]["Authorization"] == "Bearer tenant-key"
    assert calls[1][2]["json"] == {"systemId": "hubspot", "oauthAppId": "oauth-app-1"}


@pytest.mark.asyncio
async def test_async_run_poll_uses_admin_only_for_server_returned_run_id(monkeypatch):
    calls = []

    class PollClient(_Client):
        async def get(self, url, **kwargs):
            calls.append(("GET", url, kwargs))
            return _Response(200, {
                "status": "success",
                "data": {"ok": True},
                "stepResults": [],
            })

    monkeypatch.setattr(superglue_client, "_get_config", lambda: ("https://sg.test/sgapi", "admin-secret"))
    monkeypatch.setattr(superglue_client, "_get_tenant_api_key", lambda tenant_id: "tenant-key")
    monkeypatch.setattr(superglue_client, "_session_headers", lambda: {})
    monkeypatch.setattr(superglue_client.httpx, "AsyncClient", lambda **kwargs: PollClient(calls))

    result = await superglue_client._poll_run_status(
        "run-created-by-this-request", tool_id="tenant-tool", tenant_id="tenant-1",
    )

    assert result["success"] is True
    assert calls[0][1].endswith("/v1/runs/run-created-by-this-request")
    assert calls[0][2]["headers"]["Authorization"] == "Bearer admin-secret"



def test_tool_generator_uses_canonical_system_ids_without_credentials():
    from app.core.superglue_tool_generator import _format_integrations

    systems = _format_integrations({
        "hubspot": {"system_id": "hubspot", "status": "verified"},
        "database:postgres": {"system_id": "postgres", "status": "verified"},
    })
    assert {item["id"] for item in systems} == {"hubspot", "postgres"}
    assert all(item["credentials"] == {} for item in systems)


@pytest.mark.asyncio
async def test_tool_verification_uses_tenant_key_and_namespaced_tool_id(monkeypatch):
    calls = []

    class _GetClient(_Client):
        async def get(self, url, **kwargs):
            calls.append((url, kwargs))
            return _Response(200, {"archived": False})

    monkeypatch.setattr(superglue_client, "is_configured", lambda: True)
    monkeypatch.setattr(superglue_client, "_get_config", lambda: ("https://sg.test/sgapi", "admin-secret"))
    monkeypatch.setattr(superglue_client, "_get_tenant_api_key", lambda tenant_id: "tenant-key")
    monkeypatch.setattr(superglue_client, "_session_headers", lambda: {})
    monkeypatch.setattr(superglue_client.httpx, "AsyncClient", lambda **kwargs: _GetClient([]))

    verified = await superglue_client.verify_tool_exists("refund-tool", tenant_id="tenant-123")

    assert verified is True
    url, request = calls[0]
    assert url.endswith("/v1/tools/tenant_tenant-123__refund-tool")
    assert request["headers"]["Authorization"] == "Bearer tenant-key"



def test_recovery_reconciles_outer_idempotency_record_in_tenant_scope():
    from types import SimpleNamespace
    from app.core.superglue_client import _sync_ticket_tool_execution_status

    class _DB:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
        def __init__(self):
            self.calls = []
        def execute(self, statement, params=None):
            self.calls.append((str(statement), params))

    db = _DB()
    _sync_ticket_tool_execution_status(
        db,
        company_id="tenant-a",
        idempotency_key="tenant-a:ticket-1:tool-1",
        status="completed",
    )

    assert len(db.calls) == 2
    assert "set_config('app.current_tenant_id'" in db.calls[0][0]
    sql, params = db.calls[1]
    assert "UPDATE ticket_tool_executions" in sql
    assert "company_id = :company_id" in sql
    assert params == {
        "status": "completed",
        "error_message": None,
        "idempotency_key": "tenant-a:ticket-1:tool-1",
        "company_id": "tenant-a",
    }



def test_recovery_only_replays_read_only_calls_automatically():
    from app.core.superglue_client import _can_safely_recover_tool_call

    assert _can_safely_recover_tool_call("read") is True
    assert _can_safely_recover_tool_call("sensitive_pii") is True
    for safety_level in ("write", "financial", "destructive", "unknown", None):
        assert _can_safely_recover_tool_call(safety_level) is False
