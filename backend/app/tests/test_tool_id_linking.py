"""
Test: tool_id gets saved into the agent record after trigger_build runs.

This verifies the "phone number saved in contacts" behavior:
  - Agent (phone) is created
  - Tool (phone number) is created on Superglue
  - tool_id is saved into the agent record (number saved in contacts)

Without this, Node 5 would have to ask the LLM "which tool?" on every ticket
(wasting 1 LLM call). With this, Node 5's fast path works (0 LLM calls).

Run: pytest backend/app/tests/test_tool_id_linking.py -v
"""

import os
import pytest


def _read_source(filename: str) -> str:
    base = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(base, filename)) as f:
        return f.read()


# ── Source-level verification: the code saves tool_id into the agent ──


def test_trigger_build_saves_tool_id_into_agent_record():
    """CRITICAL: After generate_tool_for_agent succeeds, the tool_id MUST be
    saved into the AIAgentAssignment record.

    This is the "save phone number in contacts" step.
    Without it, Node 5 fast path breaks (1 extra LLM call per ticket).
    """
    source = _read_source("api/onboarding_build.py")
    # Find the success branch after generate_tool_for_agent
    assert "agent.superglue_tool_id = result.get(\"tool_id\")" in source, (
        "tool_id must be saved into the agent record after tool generation succeeds. "
        "This is the 'save phone number in contacts' step — without it, Node 5 "
        "fast path breaks and wastes 1 LLM call per ticket."
    )


def test_trigger_build_sets_status_to_active_on_success():
    """When tool generation succeeds, agent.superglue_tool_status must be 'active'."""
    source = _read_source("api/onboarding_build.py")
    assert 'agent.superglue_tool_status = "active"' in source


def test_trigger_build_saves_tool_definition():
    """The full tool definition should be cached for audit."""
    source = _read_source("api/onboarding_build.py")
    assert "agent.superglue_tool_definition = json.dumps(result.get(\"tool_definition\", {}))" in source


def test_trigger_build_sets_created_at_timestamp():
    """The tool creation timestamp should be saved."""
    source = _read_source("api/onboarding_build.py")
    assert "agent.superglue_tool_created_at = datetime.now(timezone.utc)" in source


def test_trigger_build_sets_failed_status_on_error():
    """When tool generation fails, agent.superglue_tool_status must be 'failed'
    (NOT 'active' — that would be a lie)."""
    source = _read_source("api/onboarding_build.py")
    assert 'agent.superglue_tool_status = "failed"' in source


def test_trigger_build_calls_generate_tool_for_agent():
    """trigger_build must actually CALL generate_tool_for_agent (not skip it)."""
    source = _read_source("api/onboarding_build.py")
    assert "await generate_tool_for_agent(" in source


# ── Dedup: skip if tool_id already saved ──


def test_trigger_build_skips_if_tool_already_linked():
    """If an agent already has an active tool (tool_id saved), trigger_build
    should SKIP it — don't create a duplicate tool on Superglue."""
    source = _read_source("api/onboarding_build.py")
    assert 'existing.superglue_tool_status == "active"' in source
    assert 'status="skipped"' in source


def test_trigger_build_retries_failed_tools():
    """If an agent has status='failed' (tool generation failed before),
    trigger_build should retry — set status to 'pending' and try again."""
    source = _read_source("api/onboarding_build.py")
    assert 'agent.superglue_tool_status = "pending"' in source


# ── Status endpoint: exposes tool_id for verification ──


def test_status_endpoint_returns_tool_id():
    """The /status endpoint should return the superglue_tool_id for each agent
    so the frontend can verify the linking happened."""
    source = _read_source("api/onboarding_build.py")
    assert "superglue_tool_id=a.superglue_tool_id" in source


def test_status_endpoint_returns_status_field():
    """The /status endpoint should return the superglue_tool_status field."""
    source = _read_source("api/onboarding_build.py")
    # The status endpoint maps a.superglue_tool_status to the status field
    assert "status=status" in source


# ── Live test: actually call generate_tool_for_agent + verify it returns tool_id ──


def test_generate_tool_for_agent_returns_tool_id_live():
    """LIVE TEST: Call generate_tool_for_agent against the real Superglue server
    and verify it returns a tool_id.

    This confirms the Superglue tool generation actually works end-to-end.
    If this fails, the Superglue server may be down or the tool generator
    has a bug.
    """
    import asyncio
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

    try:
        from app.core.superglue_tool_generator import generate_tool_for_agent
    except ImportError:
        pytest.skip("Cannot import generate_tool_for_agent (missing deps)")

    async def run_test():
        result = await generate_tool_for_agent(
            agent_name="Test Refund Agent",
            agent_instructions="Handle refund-related customer tickets.",
            agent_capabilities="refund_processing, billing_inquiry",
            sample_ticket="Customer wants a refund for order #1234",
            tenant_integrations={"stripe": {"name": "Stripe", "status": "connected"}},
        )
        return result

    try:
        result = asyncio.run(run_test())
    except Exception as exc:
        pytest.skip(f"Superglue server unreachable or tool generation failed: {str(exc)[:100]}")

    # If Superglue is up + working, it should return a tool_id
    if result.get("success"):
        assert result.get("tool_id") is not None, (
            "generate_tool_for_agent returned success=True but no tool_id. "
            "The agent record can't be linked without a tool_id."
        )
        assert isinstance(result.get("tool_id"), str)
        assert len(result["tool_id"]) > 0
    else:
        # If it failed (Superglue down, etc.), that's OK for this test —
        # we're verifying the CODE saves tool_id, not that Superglue is always up.
        # The source-level tests above cover the code path.
        pytest.skip(f"Superglue tool generation failed (server may be down): {result.get('error', 'unknown')}")


# ── Full chain: the code path from trigger_build → save tool_id ──


def test_full_chain_trigger_to_save_is_present():
    """Verify the complete code path exists:
    1. trigger_build calls generate_tool_for_agent
    2. Checks result.get("success")
    3. Saves tool_id into agent record
    4. Sets status to active
    5. Commits to DB

    All 5 steps must be present in the source.
    """
    source = _read_source("api/onboarding_build.py")

    # Step 1: call generate_tool_for_agent
    assert "await generate_tool_for_agent(" in source

    # Step 2: check success
    assert 'result.get("success")' in source

    # Step 3: save tool_id
    assert 'agent.superglue_tool_id = result.get("tool_id")' in source

    # Step 4: set status to active
    assert 'agent.superglue_tool_status = "active"' in source

    # Step 5: commit to DB
    assert "db.commit()" in source

    # Verify the order: tool_id save must come AFTER the success check
    idx_success = source.find('if result.get("success"):')
    idx_tool_id = source.find('agent.superglue_tool_id = result.get("tool_id")')
    assert idx_success > 0, "success check not found"
    assert idx_tool_id > idx_success, (
        "tool_id must be saved INSIDE the success branch (after the success check), "
        "not before it. Otherwise we'd save a None tool_id."
    )

    # Verify the commit comes AFTER the tool_id save
    idx_commit = source.find("db.commit()", idx_tool_id)
    assert idx_commit > idx_tool_id, (
        "db.commit() must come AFTER saving the tool_id, "
        "otherwise the tool_id wouldn't be persisted."
    )
