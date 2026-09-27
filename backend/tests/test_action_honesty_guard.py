"""Tests for the ACTION HONESTY GUARD (2026-09-19 live-test finding).

Live bug: a tenant with ZERO integrations received "I have processed a
full refund" — the pipeline claimed a completed action that never ran.
The guard in _wiki_finalize_complex detects unexecuted-action completion
claims and rewrites them honestly (LLM rewrite, transparent fallback).

Also covers the node_4 synthesis prompt honesty rule (regression guard:
rule 5 must not instruct the model to claim completed actions).

Run from repo root:  venv/bin/python -m pytest backend/tests/test_action_honesty_guard.py -q
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR / "backend"))

from app.core.parwa_pipeline import graph_v2  # noqa: E402


def _base_state(**overrides):
    state = {
        "ticket_id": "t-test",
        "tenant_id": "",           # empty → wiki/quota helpers no-op
        "required_action": "execute_refund",
        "formatted_response": "Subject: Refund Processed\n\nDear customer, I have processed a full refund of $50.",
        "combined_answer": "",
        "cove_blocked": False,
        "action_audit": {"tool_executed": None},
        "pending_approval": False,
        "escalation_required": False,
    }
    state.update(overrides)
    return state


def test_guard_rewrites_false_completion_claim(monkeypatch):
    """Claim detected + no tool ran → reply must lose the false claim."""
    monkeypatch.setattr(
        graph_v2, "_wiki_write_on_resolve", lambda *a, **k: None
    )
    monkeypatch.setattr(graph_v2, "_consume_quota", lambda *a, **k: None)
    # Simulate a successful LLM rewrite
    import app.services.pipeline_dispatcher as pd
    monkeypatch.setattr(
        pd, "_run_async_safely",
        lambda coro: "Subject: Refund Update\n\nDear customer, your refund request of $50 is being handled and will complete within 5-7 business days.",
    )
    state = _base_state()
    result = graph_v2._wiki_finalize_complex(state)
    reply = result["final_response"]
    assert "have processed" not in reply.lower()
    assert "has been processed" not in reply.lower()
    assert "being handled" in reply.lower()


def test_guard_fallback_note_when_rewrite_fails(monkeypatch):
    """LLM rewrite unavailable → transparent correction note is appended."""
    monkeypatch.setattr(graph_v2, "_wiki_write_on_resolve", lambda *a, **k: None)
    monkeypatch.setattr(graph_v2, "_consume_quota", lambda *a, **k: None)
    import app.services.pipeline_dispatcher as pd

    def _boom(_coro):
        raise RuntimeError("no llm in test env")

    monkeypatch.setattr(pd, "_run_async_safely", _boom)
    state = _base_state()
    result = graph_v2._wiki_finalize_complex(state)
    reply = result["final_response"]
    assert "Correction:" in reply
    assert "NOT completed yet" in reply


def test_guard_skips_when_tool_actually_executed(monkeypatch):
    """Real tool ran → reply is left untouched (no false-positive rewrites)."""
    monkeypatch.setattr(graph_v2, "_wiki_write_on_resolve", lambda *a, **k: None)
    monkeypatch.setattr(graph_v2, "_consume_quota", lambda *a, **k: None)
    original = "Subject: Refund Done\n\nI have processed a full refund of $50."
    state = _base_state(
        formatted_response=original,
        action_audit={"tool_executed": "sg_tool_123"},
    )
    result = graph_v2._wiki_finalize_complex(state)
    assert result["final_response"] == original


def test_guard_skips_info_tickets_and_pending_approvals(monkeypatch):
    """Info tickets and approval-pending tickets are never touched."""
    monkeypatch.setattr(graph_v2, "_wiki_write_on_resolve", lambda *a, **k: None)
    monkeypatch.setattr(graph_v2, "_consume_quota", lambda *a, **k: None)
    original = "Your refund of $50 has been processed."
    state = _base_state(
        formatted_response=original,
        required_action="provide_info",
    )
    assert graph_v2._wiki_finalize_complex(state)["final_response"] == original

    original2 = "I have processed a full refund."
    state2 = _base_state(formatted_response=original2, pending_approval=True)
    assert graph_v2._wiki_finalize_complex(state2)["final_response"] == original2


def test_synthesis_prompt_has_honesty_rule():
    """node_4 synthesis prompt must forbid claiming completed actions."""
    src = (BACKEND_DIR / "backend" / "app/core/parwa_pipeline/nodes/node_4_reasoning_engine.py").read_text()
    assert "HONESTY RULE" in src
    assert "NEVER write that a refund/cancellation/change" in src


def test_detection_regex_covers_live_bug_variants():
    """The exact phrasings from the live bug + common variants must match."""
    import re
    pat = re.compile(
        r"\b(?:has|have)\s+been\s+(?:successfully\s+)?"
        r"(?:processed|refunded|cancelled|canceled|completed|issued|initiated|submitted)\b"
        r"|\bI\s+have\s+(?:processed|refunded|cancelled|canceled|issued)\b"
        r"|\b(?:was|were)\s+(?:successfully\s+)?"
        r"(?:refunded|cancelled|canceled|completed|issued)\b",
        re.IGNORECASE,
    )
    must_match = [
        "I have processed a full refund of $50",       # live bug
        "your refund has been processed",
        "the order was cancelled",
        "a credit has been issued",
        "your subscription was successfully cancelled",
    ]
    must_not_match = [
        "your refund is being processed",               # honest phrasing
        "your refund will be processed within 5 days",  # honest future
        "we received your refund request",              # neutral
    ]
    for s in must_match:
        assert pat.search(s), f"should match: {s}"
    for s in must_not_match:
        assert not pat.search(s), f"should NOT match: {s}"
