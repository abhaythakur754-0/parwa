"""CRM analyser request contract: pass the tenant's existing integration inventory."""

from pathlib import Path

import pytest
import httpx

from app.core import crm_analyser_client


@pytest.mark.asyncio
async def test_external_analyser_receives_connected_integration_keys(monkeypatch):
    captured = []

    class Response:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self.body

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json):
            captured.append(json)
            return Response({"request_id": "req-test"})

        async def get(self, url, params):
            return Response({
                "status": {
                    "status": "completed",
                    "result": {
                        "tickets_scanned": 1,
                        "work_order": {
                            "integrations": ["shopify"],
                            "agents": [],
                            "tools": [],
                        },
                    },
                },
            })

    monkeypatch.setattr(crm_analyser_client, "get_crm_analyser_url", lambda: "https://analyser.test")
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    result = await crm_analyser_client.analyze_crm_external(
        tickets=[{"subject": "Where is my order?"}],
        company_name="Example tenant",
        connected_integrations=["hubspot", "zendesk"],
        poll_interval=0,
        max_poll_attempts=1,
    )

    assert captured[0]["data"]["connected_integrations"] == ["hubspot", "zendesk"]
    assert result["integrations"] == ["shopify"]


def test_integrations_endpoint_passes_connected_keys_to_analyser():
    backend_root = Path(__file__).resolve().parents[2]
    source = (backend_root / "app/api/integrations.py").read_text(encoding="utf-8")
    assert "connected_integrations=connected_keys" in source
    assert 'Integration.status.in_(["active", "verified"])' in source
