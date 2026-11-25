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
