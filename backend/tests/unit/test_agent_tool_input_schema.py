"""Tests that agents only execute tools with schema-complete inputs."""

import pytest

from app.core.parwa_pipeline.nodes.node_5_act_verify import (
    _extract_tool_inputs,
    _execute_with_idempotency,
)


def test_input_extractor_maps_ticket_and_crm_data_to_tool_schema():
    tool_definition = {
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_email": {"type": "string"},
                "order_id": {"type": "string"},
                "amount_cents": {"type": "integer"},
                "account_id": {"type": "string"},
                "ticket_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["customer_email", "order_id", "amount_cents", "account_id"],
        }
    }
    inputs = _extract_tool_inputs(
        {"description": "Please refund order #ABCD1234 for $49.99", "amount": 49.99},
        "refund order",
        "Customer email is customer@example.com",
        tool_definition=tool_definition,
        crm_data={"customer": {"account_id": "acct-123"}},
        ticket_id="ticket-456",
    )

    assert inputs["customer_email"] == "customer@example.com"
    assert inputs["order_id"] == "ABCD1234"
    assert inputs["amount_cents"] == 4999
    assert inputs["account_id"] == "acct-123"
    assert inputs["ticket_id"] == "ticket-456"
    assert inputs["reason"] == "Please refund order #ABCD1234 for $49.99"
    assert "_missing_required" not in inputs


def test_input_extractor_marks_unknown_required_fields_instead_of_guessing():
    inputs = _extract_tool_inputs(
        {"description": "Please refund my order"},
        "refund",
        "",
        tool_definition={
            "inputSchema": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "warehouse_id": {"type": "string"},
                },
                "required": ["order_id", "warehouse_id"],
            }
        },
    )

    assert inputs["order_id"]
    assert inputs["_missing_required"] == ["warehouse_id"]


@pytest.mark.asyncio
async def test_missing_required_inputs_block_tool_execution_before_network():
    result = await _execute_with_idempotency(
        "refund-tool",
        {"_missing_required": ["customer_id"]},
        "ticket-1:refund-tool:refund",
        "ticket-1",
        "refund",
        "tenant-1",
    )

    assert result["success"] is False
    assert result["needs_customer_info"] is True
    assert result["missing_required"] == ["customer_id"]


def test_input_extractor_maps_public_crm_reply_contract():
    tool_definition = {
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticketId": {"type": "string"},
                "responseBody": {"type": "string"},
                "public": {"type": "boolean"},
                "status": {"type": "string"},
            },
            "required": ["ticketId", "responseBody", "public"],
        }
    }
    inputs = _extract_tool_inputs(
        {
            "ticket_id": "crm-123",
            "response": "We have resolved your issue.",
            "status": "resolved",
            "public": True,
        },
        "reply_to_ticket",
        "",
        tool_definition=tool_definition,
        ticket_id="crm-123",
    )
    assert inputs == {
        "ticketId": "crm-123",
        "responseBody": "We have resolved your issue.",
        "public": True,
        "status": "resolved",
    }


def test_input_extractor_maps_private_escalation_contract():
    tool_definition = {
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
    inputs = _extract_tool_inputs(
        {
            "ticket_id": "crm-456",
            "internal_note": "Requires human approval for a policy exception.",
            "status": "open",
            "public": False,
            "internal": True,
        },
        "create_private_escalation_note",
        "",
        tool_definition=tool_definition,
        ticket_id="crm-456",
    )
    assert inputs["ticket_id"] == "crm-456"
    assert inputs["internal_note"].startswith("Requires human approval")
    assert inputs["status"] == "open"
    assert inputs["internal"] is True
    assert "_missing_required" not in inputs


@pytest.mark.asyncio
async def test_idempotency_reserves_before_tool_side_effect(monkeypatch):
    from types import SimpleNamespace
    from database import base
    from app.core import superglue_client
    from app.core.parwa_pipeline.nodes import node_5_act_verify

    events = []

    class _Result:
        rowcount = 1
        def fetchone(self):
            return None

    class _DB:
        bind = None
        def execute(self, statement, params=None):
            sql = str(statement).lower()
            if "insert into ticket_tool_executions" in sql:
                events.append("reserve")
            elif "update ticket_tool_executions" in sql:
                events.append("complete")
            return _Result()
        def commit(self):
            pass
        def rollback(self):
            pass
        def close(self):
            pass

    async def fake_execute_tool(*args, **kwargs):
        events.append("tool")
        return {"success": True, "data": {"ok": True}}

    monkeypatch.setattr(base, "SessionLocal", lambda: _DB())
    monkeypatch.setattr(superglue_client, "execute_tool", fake_execute_tool)
    monkeypatch.setattr(
        node_5_act_verify,
        "_run_action_safety_gate",
        lambda *args, **kwargs: {"blocked": False, "needs_approval": False},
    )

    result = await _execute_with_idempotency(
        "tenant_tool",
        {"ticket_id": "ticket-1"},
        "ticket-1:action",
        "ticket-1",
        "update_ticket",
        "tenant-1",
    )

    assert result["success"] is True
    assert events == ["reserve", "tool", "complete"]


@pytest.mark.asyncio
async def test_idempotency_storage_failure_blocks_external_action(monkeypatch):
    from types import SimpleNamespace
    from database import base
    from app.core import superglue_client
    from app.core.parwa_pipeline.nodes import node_5_act_verify

    calls = []

    class _DB:
        bind = None
        def execute(self, statement, params=None):
            if "INSERT INTO ticket_tool_executions" in str(statement):
                raise RuntimeError("database unavailable")
            return SimpleNamespace(rowcount=1, fetchone=lambda: None)
        def commit(self):
            pass
        def rollback(self):
            pass
        def close(self):
            pass

    async def fake_execute_tool(*args, **kwargs):
        calls.append("executed")
        return {"success": True}

    monkeypatch.setattr(base, "SessionLocal", lambda: _DB())
    monkeypatch.setattr(superglue_client, "execute_tool", fake_execute_tool)
    monkeypatch.setattr(
        node_5_act_verify,
        "_run_action_safety_gate",
        lambda *args, **kwargs: {"blocked": False, "needs_approval": False},
    )

    result = await _execute_with_idempotency(
        "tenant_tool",
        {"ticket_id": "ticket-1"},
        "ticket-1:action",
        "ticket-1",
        "update_ticket",
        "tenant-1",
    )

    assert result["success"] is False
    assert result["guardrail_blocked"] is True
    assert calls == []


def test_customer_reply_and_escalation_tools_are_classified_as_writes():
    from app.core.action_safety import ActionSafetyLevel, classify_action

    assert classify_action("tenant__ticket-reply-specialist").level == ActionSafetyLevel.WRITE
    assert classify_action("tenant__ticket-escalation-specialist").level == ActionSafetyLevel.WRITE


def test_unclassified_tool_is_blocked_by_pipeline_safety_gate():
    from app.core.parwa_pipeline.nodes.node_5_act_verify import _run_action_safety_gate

    result = _run_action_safety_gate(
        "tenant__unfamiliar-tool",
        "",
        {},
        "tenant-1",
        "parwa",
    )
    assert result["blocked"] is True
    assert result["needs_approval"] is True
