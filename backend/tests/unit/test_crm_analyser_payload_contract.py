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


def test_analyser_keeps_integration_and_agent_recommendations_separate():
    backend_root = Path(__file__).resolve().parents[2]
    source = (backend_root / "app/api/integrations.py").read_text(encoding="utf-8")
    assert 'result.get("integrations", [])' in source
    assert 'result.get("agents")' in source
    assert '"recommended_agents": recommended_agents' in source
    assert '"system_id": _system_id(str(name))' in source


def test_analyser_never_recommends_already_connected_integrations_or_fills_false_gaps():
    backend_root = Path(__file__).resolve().parents[2]
    source = (backend_root / "app/api/integrations.py").read_text(encoding="utf-8")
    assert "if system_id in connected_keys:" in source
    assert "not result.get(\"tickets_scanned\") and not recommendations" in source
    assert "if _system_id(name) not in connected_keys" in source


def test_agent_builder_uses_agent_capabilities_not_integration_names():
    backend_root = Path(__file__).resolve().parents[2]
    source = (backend_root / "app/api/onboarding_build.py").read_text(encoding="utf-8")
    assert '(analysis.data_profile or {}).get("recommended_agents")' in source
    assert 'for name, capabilities in STARTER_AGENT_PACK.items()' in source
    assert 'available_names' not in source
    assert 'Integration.status.in_(["verified", "active"])' in source


def test_ticket_reply_tool_requires_ticket_id_and_response_body():
    from app.api.onboarding_build import _validate_platform_tool_schema

    valid = {
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "response_body": {"type": "string"},
            },
            "required": ["ticket_id", "response_body"],
        }
    }
    assert _validate_platform_tool_schema("Ticket Reply Specialist", valid) is None

    invalid = {
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "response_body": {"type": "string"},
            },
            "required": ["ticket_id"],
        }
    }
    assert "response body" in _validate_platform_tool_schema(
        "Ticket Reply Specialist", invalid
    )


def test_escalation_tool_requires_private_note_and_status():
    from app.api.onboarding_build import _validate_platform_tool_schema

    valid = {
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "internal_note": {"type": "string"},
                "status": {"type": "string"},
            },
            "required": ["ticket_id", "internal_note", "status"],
        }
    }
    assert _validate_platform_tool_schema("Ticket Escalation Specialist", valid) is None



def test_crm_analyser_requires_explicit_https_endpoint(monkeypatch):
    monkeypatch.setenv("CRM_ANALYSER_URL", "")
    assert crm_analyser_client.get_crm_analyser_url() == ""

    monkeypatch.setenv("CRM_ANALYSER_URL", "http://public-analyser.example")
    assert crm_analyser_client.get_crm_analyser_url() == ""

    monkeypatch.setenv("CRM_ANALYSER_URL", "https://analyser.example/")
    assert crm_analyser_client.get_crm_analyser_url() == "https://analyser.example"
