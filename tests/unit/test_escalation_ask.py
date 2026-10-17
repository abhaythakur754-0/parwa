"""Unit tests for the structured escalation ask (app/services/escalation_ask.py).

Covers the contract the user asked for: EVERY escalation type — including
problems never seen before — produces the same structured, actionable ask
(problem / needed_from_team / after_that) that gets stored on the ticket,
pushed to the CRM, and (once the team answers) learned by the AI wiki.
"""

import json
import os
import sys

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import pytest  # noqa: E402

from app.services.escalation_ask import (  # noqa: E402
    ESCALATION_TYPE_LABELS,
    apply_escalation_ask,
    build_escalation_ask,
    classify_reason,
    format_ask_for_crm,
)


# ── classify_reason: every reason vocabulary maps to a structured type ──
@pytest.mark.parametrize(
    "reason,expected",
    [
        ("max_retries_exceeded", "technical_error"),
        ("pipeline_error", "technical_error"),
        ("worker_crash", "technical_error"),
        ("cove_blocked", "unverified_answer"),
        ("response_failed_verification", "unverified_answer"),
        ("client_requested_human", "customer_requested_human"),
        ("human_request", "customer_requested_human"),
        ("force_human_handoff", "customer_requested_human"),
        ("kb_gap_no_tool", "missing_knowledge"),
        ("missing_knowledge", "missing_knowledge"),
        ("no_answer", "missing_knowledge"),
        ("interrupt_needs_input", "missing_knowledge"),
        ("missing_connection", "missing_connection"),
        ("no_tool_for_action", "missing_connection"),
        ("integration_unavailable", "missing_connection"),
        ("approval_limit_exceeded", "approval_required"),
        ("pause_for_agent_approval", "approval_required"),
        ("", "unknown"),
        ("something_totally_new_2027", "unknown"),
    ],
)
def test_classify_reason(reason, expected):
    assert classify_reason(reason) == expected


# ── build_escalation_ask: all types produce the full actionable block ──
ALL_TYPES = [
    "missing_connection",
    "missing_knowledge",
    "unverified_answer",
    "approval_required",
    "technical_error",
    "customer_requested_human",
    "unknown",
]


@pytest.mark.parametrize("reason", ["cove_blocked", "kb_gap", "missing_connection",
                                    "approval_limit", "pipeline_error", "human_request",
                                    "brand_new_reason"])
def test_build_ask_has_all_fields(reason):
    ask = build_escalation_ask(reason, context_hint="extra context")
    assert ask["escalation_type"] in ALL_TYPES
    for field in ("problem", "needed_from_team", "after_that"):
        assert ask.get(field), f"{reason}: {field} must be non-empty"


def test_unknown_reason_still_actionable():
    """A problem NEVER seen before still gets a structured ask — no dead ends."""
    ask = build_escalation_ask("quantum_entanglement_failure", "")
    assert ask["escalation_type"] == "unknown"
    assert "Review the customer's request" in ask["needed_from_team"]
    assert "learns it" in ask["after_that"]  # the answer gets stored either way


# ── missing_connection: names the capability + the concrete ask ─────────
def test_refund_action_maps_to_payment_gateway():
    ask = build_escalation_ask("missing_connection", required_action="execute_refund")
    assert ask["escalation_type"] == "missing_connection"
    assert "payment gateway" in ask["problem"]
    assert "Connect" in ask["needed_from_team"]
    assert "Razorpay" in ask["needed_from_team"]
    assert "Retry" in ask["after_that"]


@pytest.mark.parametrize(
    "action,fragment",
    [
        ("track_shipment", "shipping"),
        ("update_order", "ecommerce"),
        ("upgrade_subscription", "billing"),
        ("reschedule_appointment", "scheduling"),
        ("weird_custom_action", "integration"),
    ],
)
def test_action_to_capability_mapping(action, fragment):
    ask = build_escalation_ask("missing_connection", required_action=action)
    assert fragment in (ask["problem"] + ask["needed_from_team"]).lower()


def test_empty_action_still_gives_generic_connection_ask():
    ask = build_escalation_ask("missing_connection", required_action="")
    assert "Connect" in ask["needed_from_team"]


# ── format_ask_for_crm: readable block for the CRM note ────────────────
def test_format_ask_contains_all_three_parts():
    ask = build_escalation_ask("missing_connection", required_action="execute_refund")
    text = format_ask_for_crm(ask)
    assert "[Missing connection]" in text
    assert "Problem:" in text
    assert "What I need from your team:" in text
    assert "Once done:" in text


def test_format_ask_handles_garbage():
    assert format_ask_for_crm({}) != ""  # empty ask still renders label
    assert format_ask_for_crm(None) == ""
    assert format_ask_for_crm("not a dict") == ""


# ── apply_escalation_ask: persists to ticket metadata, never crashes ────
class _FakeTicket:
    def __init__(self, metadata_json="{}"):
        self.metadata_json = metadata_json


def test_apply_writes_structured_metadata():
    t = _FakeTicket(json.dumps({"crm_ticket_id": "CRM-1"}))
    ask = apply_escalation_ask(t, reason="cove_blocked")
    meta = json.loads(t.metadata_json)
    assert meta["crm_ticket_id"] == "CRM-1"  # existing keys preserved
    assert meta["escalation_reason"] == "cove_blocked"
    assert meta["escalation_type"] == "unverified_answer"
    assert meta["escalation_ask"]["needed_from_team"]


def test_apply_survives_corrupted_metadata():
    t = _FakeTicket("not-json-at-all{{{")
    ask = apply_escalation_ask(t, reason="pipeline_error")
    meta = json.loads(t.metadata_json)
    assert meta["escalation_type"] == "technical_error"
    assert ask["escalation_type"] == "technical_error"


def test_apply_overwrites_stale_reason():
    t = _FakeTicket(json.dumps({"escalation_type": "unknown"}))
    apply_escalation_ask(t, reason="missing_connection", required_action="execute_refund")
    meta = json.loads(t.metadata_json)
    assert meta["escalation_type"] == "missing_connection"


# ── labels are complete for every type ──────────────────────────────────
def test_labels_cover_all_types():
    for t in ALL_TYPES:
        assert t in ESCALATION_TYPE_LABELS
