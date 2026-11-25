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

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url.endswith("/v1/systems"):
            return _Response(201, {"data": {"id": "hubspot"}})
        return _Response(201, {"data": {"id": "credential-1"}})


@pytest.mark.asyncio
async def test_customer_secrets_are_posted_with_tenant_key_not_admin_key(monkeypatch):
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
        tenant_id=None,
        credentials={"access_token": "customer-secret"},
        customer_api_key="tenant-service-account-key",
        credential_url="https://api.hubapi.com",
        template_id="hubspot",
    )

    assert result["success"] is True
    assert len(calls) == 2
    system_url, system_request = calls[0]
    credential_url, credential_request = calls[1]
    assert system_url.endswith("/v1/systems")
    assert system_request["headers"]["Authorization"] == "Bearer admin-secret"
    assert system_request["json"]["credentials"] == {}
    assert system_request["json"]["template"] == "hubspot"
    assert credential_url.endswith("/v1/credentials")
    assert credential_request["headers"]["Authorization"] == "Bearer tenant-service-account-key"
    assert credential_request["json"]["systemId"] == "hubspot"
    assert credential_request["json"]["credentials"] == {"access_token": "customer-secret"}
