"""Regression tests for safe Superglue database schema discovery."""

import pytest

from app.core import superglue_client
from app.api.superglue_systems import _sanitize_schema_metadata


class _Response:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class _Client:
    def __init__(self, response, captured):
        self.response = response
        self.captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, **kwargs):
        self.captured.update({"url": url, **kwargs})
        return self.response


@pytest.mark.asyncio
async def test_schema_discovery_rejects_empty_success_response(monkeypatch):
    captured = {}
    monkeypatch.setattr(superglue_client, "is_configured", lambda: True)
    monkeypatch.setattr(superglue_client, "_get_config", lambda: ("https://sg.test/sgapi", "test-token"))
    monkeypatch.setattr(superglue_client, "_get_tenant_api_key", lambda tenant_id: "tenant-test-token")
    monkeypatch.setattr(superglue_client, "_session_headers", lambda: {})
    monkeypatch.setattr(
        superglue_client.httpx,
        "AsyncClient",
        lambda **kwargs: _Client(_Response(200, {"data": {"tables": []}}), captured),
    )

    result = await superglue_client.analyze_db_schema(
        db_connection_id="postgres",
        tenant_id="tenant-123",
        db_type="postgresql",
        connection_config={"host": "db.test", "readonly": True},
    )

    assert result["success"] is False
    assert result["schema"] is None
    assert "no verified tables" in result["error"].lower()
    assert captured["json"]["connection_id"] == "tenant_tenant-123__postgres"


@pytest.mark.asyncio
async def test_schema_discovery_accepts_real_table_metadata(monkeypatch):
    captured = {}
    schema = {
        "tables": [{"name": "customers", "columns": [{"name": "id", "type": "uuid"}]}],
        "source": "superglue",
    }
    monkeypatch.setattr(superglue_client, "is_configured", lambda: True)
    monkeypatch.setattr(superglue_client, "_get_config", lambda: ("https://sg.test/sgapi", "test-token"))
    monkeypatch.setattr(superglue_client, "_get_tenant_api_key", lambda tenant_id: "tenant-test-token")
    monkeypatch.setattr(superglue_client, "_session_headers", lambda: {})
    monkeypatch.setattr(
        superglue_client.httpx,
        "AsyncClient",
        lambda **kwargs: _Client(_Response(200, {"data": schema}), captured),
    )

    result = await superglue_client.analyze_db_schema(
        db_connection_id="postgres",
        tenant_id="tenant-123",
        db_type="postgresql",
        connection_config={"host": "db.test", "readonly": True},
    )

    assert result["success"] is True
    assert result["schema"]["tables"][0]["name"] == "customers"


def test_schema_persistence_removes_sample_rows_and_values():
    raw = {
        "source": "superglue",
        "summary": "Customer database",
        "tables": [{
            "name": "customers",
            "columns": [{"name": "email", "type": "text"}],
            "sample_rows": [{"email": "private@example.com"}],
        }],
    }

    safe = _sanitize_schema_metadata(raw)

    assert safe["tables"][0]["name"] == "customers"
    assert safe["tables"][0]["columns"] == [{"name": "email", "type": "text"}]
    assert "sample_rows" not in safe["tables"][0]
    assert "private@example.com" not in str(safe)
