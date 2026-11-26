"""Ticket lifecycle delivery must use tenant Superglue tools for OAuth CRMs."""

import json
from types import SimpleNamespace

import pytest


class _Query:
    def __init__(self, row=None):
        self.row = row

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.row


class _DB:
    def __init__(self, assignment):
        self.assignment = assignment

    def query(self, model):
        from database.models.variant_engine import AIAgentAssignment
        if model is AIAgentAssignment:
            return _Query(self.assignment)
        return _Query(None)

    def close(self):
        pass


@pytest.mark.asyncio
async def test_node_6_5_uses_tenant_ticket_reply_tool(monkeypatch):
    from database import base
    from app.core.parwa_pipeline.nodes import node_5_act_verify
    from app.core.parwa_pipeline.nodes.node_6_5_deliver import _push_to_crm_via_superglue

    definition = {
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticketId": {"type": "string"},
                "responseBody": {"type": "string"},
                "public": {"type": "boolean"},
            },
            "required": ["ticketId", "responseBody", "public"],
        }
    }
    assignment = SimpleNamespace(
        superglue_tool_id="tenant_tenant-1__ticket-reply",
        superglue_tool_definition=json.dumps(definition),
    )
    calls = []

    async def fake_execute(*args, **kwargs):
        calls.append((args, kwargs))
        return {"success": True, "data": {"comment_id": "comment-1"}}

    monkeypatch.setattr(base, "SessionLocal", lambda: _DB(assignment))
    monkeypatch.setattr(node_5_act_verify, "_execute_with_idempotency", fake_execute)

    handled, result, error = await _push_to_crm_via_superglue(
        state={"tenant_id": "tenant-1", "ticket_id": "local-1", "quality_score": 0.98},
        response_text="Your refund has been processed.",
        crm_ticket_id="crm-ticket-1",
    )

    assert handled is True
    assert result["success"] is True
    assert error is None
    inputs = calls[0][0][1]
    assert inputs == {
        "ticketId": "crm-ticket-1",
        "responseBody": "Your refund has been processed.",
        "public": True,
    }
    assert calls[0][0][5] == "tenant-1"


@pytest.mark.asyncio
async def test_node_8_uses_private_escalation_tool_for_oauth_crm(monkeypatch):
    from database import base
    from app.core.parwa_pipeline.nodes import node_5_act_verify
    from app.core.parwa_pipeline.nodes.node_8_super_node import _push_escalation_to_crm_with_retry

    definition = {
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "internal_note": {"type": "string"},
                "status": {"type": "string"},
                "internal": {"type": "boolean"},
            },
            "required": ["ticket_id", "internal_note", "status", "internal"],
        }
    }
    assignment = SimpleNamespace(
        superglue_tool_id="tenant_tenant-1__ticket-escalation",
        superglue_tool_definition=json.dumps(definition),
    )
    calls = []

    async def fake_execute(*args, **kwargs):
        calls.append((args, kwargs))
        return {"success": True, "data": {"note_id": "note-1"}}

    monkeypatch.setattr(base, "SessionLocal", lambda: _DB(assignment))
    monkeypatch.setattr(node_5_act_verify, "_execute_with_idempotency", fake_execute)

    status, result, retries, error, dlq_id = await _push_escalation_to_crm_with_retry(
        tenant_id="tenant-1",
        ticket_id="local-2",
        crm_provider="hubspot",
        crm_ticket_id="crm-ticket-2",
        escalation_context={"internal_note": "Human review required for policy exception."},
        max_retries=0,
        backoff_base=0,
        backoff_max=0,
        metrics_enabled=False,
        dlq_on_failure=False,
    )

    assert status == "success"
    assert result["success"] is True
    assert retries == 0
    assert error is None
    assert dlq_id is None
    inputs = calls[0][0][1]
    assert inputs["ticket_id"] == "crm-ticket-2"
    assert inputs["internal_note"].startswith("Human review required")
    assert inputs["status"] == "open"
    assert inputs["internal"] is True
