"""
Tests for Node 1 agent-creation approval flow.

Covers the four gaps closed in this change:
  1. Quota awareness — agent:quota_status event emitted with {used, max, remaining}
  2. Approval gate — agent:approval_required event + pause_for_agent_approval action
     + escalation saved to vault with SOURCE_NODE_1_AGENT_REQUEST
  3. Enriched limit-reached event — now includes {used, max, remaining: 0}
  4. Builder block bypassed when paused for approval

Run: pytest tests/test_node1_agent_creation_approval.py -v --tb=short
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub langgraph so node_1 imports cleanly without the real dependency.
if "langgraph" not in sys.modules:
    sys.modules["langgraph"] = MagicMock()
    sys.modules["langgraph.graph"] = MagicMock()
    sys.modules["langgraph.graph"].END = "__end__"
    sys.modules["langgraph.graph"].StateGraph = MagicMock


@pytest.fixture
def base_state() -> Dict[str, Any]:
    """Minimal state that triggers Node 1's capability-detection path."""
    return {
        "ticket_id": "TKT-APPROVAL-001",
        "tenant_id": "tenant_acme",
        "query": "I want a refund for my annual subscription",
        "channel_type": "email",
        "customer_context": {
            "account_tier": "parwa",
            "customer_tenure_days": 180,
            "recent_ticket_count": 2,
            "lifetime_value": 1200,
        },
        "metadata": {"sender": "user@example.com", "timestamp": "2026-01-15T10:00:00Z"},
    }


@pytest.fixture
def mock_llm_call():
    """Mock llm_call — Node 1 uses UoT to measure classification confidence."""
    with patch("app.core.parwa_pipeline.llm_client.llm_call", new_callable=AsyncMock) as mock:
        mock.return_value = "0.85"
        yield mock


@pytest.fixture
def mock_wiki_store():
    """Mock the AI Wiki store so Node 1 doesn't touch real storage."""
    with patch("app.core.parwa_pipeline.ai_wiki_store.get_wiki_store") as mock_get:
        mock_store = MagicMock()
        mock_store.find_similar_patterns.return_value = []
        mock_store.search.return_value = []
        mock_store.read.return_value = []
        mock_store.write_ticket_pattern.return_value = MagicMock(entry_key="wiki_test_001")
        mock_store.check_policy_sync.return_value = {"synced": True, "version": "v2.0", "previous_version": None}
        mock_get.return_value = mock_store
        yield mock_store, mock_get


@pytest.fixture
def captured_events() -> List[Dict[str, Any]]:
    """Captured emit_ticket_event calls."""
    return []


@pytest.fixture
def patch_emit_ticket_event(captured_events):
    """Patch emit_ticket_event to record calls instead of hitting Socket.io."""
    async def _capture(company_id, event_type, payload, correlation_id=None):
        captured_events.append({
            "company_id": company_id,
            "event_type": event_type,
            "payload": payload,
            "correlation_id": correlation_id,
        })
        return True
    with patch("app.core.event_emitter.emit_ticket_event", new=_capture):
        yield


@pytest.fixture
def patch_no_capability_claimed():
    """Make _tenant_claims_capability return False so the limit/approval block runs."""
    with patch(
        "app.core.parwa_pipeline.nodes.node_1_ingest_classify._tenant_claims_capability",
        return_value=False,
    ):
        yield


@pytest.fixture
def patch_no_embedded_kb():
    """Make _tenant_has_embedded_kb return False — Builder block requires KB."""
    with patch(
        "app.core.parwa_pipeline.nodes.node_1_ingest_classify._tenant_has_embedded_kb",
        return_value=False,
    ):
        yield


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Quota awareness — agent:quota_status emitted with full quota
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_quota_status_event_emitted_with_used_max_remaining(
    base_state, mock_llm_call, mock_wiki_store,
    patch_emit_ticket_event, patch_no_capability_claimed, patch_no_embedded_kb,
    captured_events,
):
    """When Node 1 detects an unclaimed capability, it MUST emit
    agent:quota_status with {used, max, remaining} before anything else."""
    # Mock the limit service: quota is 3/5 used, 2 remaining, limit OK
    _quota_check = {
        "ai_agents": {
            "allowed": True,
            "current_usage": 3,
            "limit": 5,
            "remaining": 2,
        },
    }
    _limit_svc = MagicMock()
    _limit_svc.get_all_limit_checks.return_value = _quota_check
    _limit_svc.enforce_limit.return_value = _quota_check["ai_agents"]
    with patch(
        "app.services.variant_limit_service.get_variant_limit_service",
        return_value=_limit_svc,
    ):
        # Mock VaultManager so we don't touch real storage
        _vault_record = {"escalation_id": "esc_test_001"}
        with patch(
            "app.core.escalation_vault.vault_manager.VaultManager.save_escalation_from_pipeline",
            new_callable=AsyncMock,
            return_value=_vault_record,
        ):
            from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify
            await node_1_ingest_classify(base_state)

    quota_events = [e for e in captured_events if e["event_type"] == "agent:quota_status"]
    assert len(quota_events) == 1, f"expected 1 quota_status event, got {len(quota_events)}"
    payload = quota_events[0]["payload"]
    assert payload["used"] == 3
    assert payload["max"] == 5
    assert payload["remaining"] == 2
    assert "capability" in payload
    assert payload["ticket_id"] == "TKT-APPROVAL-001"


# ═══════════════════════════════════════════════════════════════════════
# Test 2: Approval gate — agent:approval_required + pause_for_agent_approval
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_approval_required_event_and_pause_action_when_quota_ok(
    base_state, mock_llm_call, mock_wiki_store,
    patch_emit_ticket_event, patch_no_capability_claimed, patch_no_embedded_kb,
    captured_events,
):
    """When quota is OK, Node 1 MUST:
       - emit agent:approval_required with escalation_id + quota
       - set required_action = pause_for_agent_approval
       - NOT run the Builder (no agent created in this turn)
    """
    _quota_check = {
        "ai_agents": {"allowed": True, "current_usage": 2, "limit": 5, "remaining": 3},
    }
    _limit_svc = MagicMock()
    _limit_svc.get_all_limit_checks.return_value = _quota_check
    _limit_svc.enforce_limit.return_value = _quota_check["ai_agents"]
    with patch(
        "app.services.variant_limit_service.get_variant_limit_service",
        return_value=_limit_svc,
    ):
        _vault_record = {"escalation_id": "esc_test_002"}
        with patch(
            "app.core.escalation_vault.vault_manager.VaultManager.save_escalation_from_pipeline",
            new_callable=AsyncMock,
            return_value=_vault_record,
        ) as mock_save:
            from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify
            result = await node_1_ingest_classify(base_state)

    # agent:approval_required emitted with escalation_id + quota
    approval_events = [e for e in captured_events if e["event_type"] == "agent:approval_required"]
    assert len(approval_events) == 1, f"expected 1 approval_required event, got {len(approval_events)}"
    payload = approval_events[0]["payload"]
    assert payload["escalation_id"] == "esc_test_002"
    assert payload["used"] == 2
    assert payload["max"] == 5
    assert payload["remaining"] == 3

    # VaultManager.save_escalation_from_pipeline was called once with SOURCE_NODE_1_AGENT_REQUEST
    assert mock_save.await_count == 1
    _args, _kwargs = mock_save.call_args
    assert _kwargs.get("escalation_source") == "node_1_agent_creation"

    # Pipeline action is pause_for_agent_approval
    assert result.get("required_action") == "pause_for_agent_approval"
    assert result.get("action_details", {}).get("reason") == "agent_creation_pending_approval"
    assert result.get("action_details", {}).get("escalation_id") == "esc_test_002"


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Builder block bypassed when paused for approval
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_builder_not_run_when_paused_for_approval(
    base_state, mock_llm_call, mock_wiki_store,
    patch_emit_ticket_event, patch_no_capability_claimed, patch_no_embedded_kb,
    captured_events,
):
    """When paused for approval, the Builder Agent pipeline MUST NOT run.
    No agent_created log entry should appear in this turn."""
    _quota_check = {
        "ai_agents": {"allowed": True, "current_usage": 0, "limit": 5, "remaining": 5},
    }
    _limit_svc = MagicMock()
    _limit_svc.get_all_limit_checks.return_value = _quota_check
    _limit_svc.enforce_limit.return_value = _quota_check["ai_agents"]
    with patch(
        "app.services.variant_limit_service.get_variant_limit_service",
        return_value=_limit_svc,
    ):
        with patch(
            "app.core.escalation_vault.vault_manager.VaultManager.save_escalation_from_pipeline",
            new_callable=AsyncMock,
            return_value={"escalation_id": "esc_test_003"},
        ):
            # If the Builder block runs, this import would be attempted.
            # Patch run_builder_pipeline to explode if it's ever called.
            with patch(
                "app.core.builder_agent.builder_pipeline.run_builder_pipeline",
                new_callable=AsyncMock,
                side_effect=AssertionError("Builder must NOT run when paused for approval"),
            ):
                from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify
                result = await node_1_ingest_classify(base_state)

    # No agent was created in this turn
    assert not result.get("agent_created", False)
    builder_logs = [l for l in result.get("logs", []) if "Builder" in l.get("result_summary", "")]
    assert len(builder_logs) == 0, f"Builder logs should be empty, got: {builder_logs}"


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Limit-reached event now includes remaining: 0
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_limit_reached_event_includes_remaining_zero(
    base_state, mock_llm_call, mock_wiki_store,
    patch_emit_ticket_event, patch_no_capability_claimed, patch_no_embedded_kb,
    captured_events,
):
    """When the limit is exceeded, agent:limit_reached MUST include
    {used, max, remaining: 0} and escalate_human."""
    from app.services.variant_limit_service import VariantLimitExceededError

    _quota_check = {
        "ai_agents": {"allowed": True, "current_usage": 4, "limit": 5, "remaining": 1},
    }
    _limit_svc = MagicMock()
    _limit_svc.get_all_limit_checks.return_value = _quota_check
    _limit_svc.enforce_limit.side_effect = VariantLimitExceededError(
        limit_type="ai_agents",
        current_usage=5,
        limit=5,
        message="AI agents limit exceeded: 5/5 used.",
    )
    with patch(
        "app.services.variant_limit_service.get_variant_limit_service",
        return_value=_limit_svc,
    ):
        from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify
        result = await node_1_ingest_classify(base_state)

    limit_events = [e for e in captured_events if e["event_type"] == "agent:limit_reached"]
    assert len(limit_events) == 1, f"expected 1 limit_reached event, got {len(limit_events)}"
    payload = limit_events[0]["payload"]
    assert payload["used"] == 5
    assert payload["max"] == 5
    assert payload["remaining"] == 0

    assert result.get("required_action") == "escalate_human"
    assert result.get("action_details", {}).get("reason") == "agent_limit_reached"
    assert result.get("action_details", {}).get("remaining") == 0


# ═══════════════════════════════════════════════════════════════════════
# Test 5: New escalation source constant exists
# ═══════════════════════════════════════════════════════════════════════


def test_source_node_1_agent_request_constant_exists():
    """The new SOURCE_NODE_1_AGENT_REQUEST constant must be importable
    from vault_db and distinct from the existing SOURCE_NODE_1."""
    from app.core.escalation_vault.vault_db import (
        SOURCE_NODE_1,
        SOURCE_NODE_1_AGENT_REQUEST,
    )
    assert SOURCE_NODE_1_AGENT_REQUEST == "node_1_agent_creation"
    assert SOURCE_NODE_1_AGENT_REQUEST != SOURCE_NODE_1


# ═══════════════════════════════════════════════════════════════════════
# Test 6: Mini tier (max_agents=0) skips agent creation entirely
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_mini_tier_skips_agent_creation_uses_generic_ai(
    base_state, mock_llm_call, mock_wiki_store,
    patch_emit_ticket_event, patch_no_capability_claimed, patch_no_embedded_kb,
    captured_events,
):
    """Mini tier (max_agents=0) must NOT enter the agent-creation flow at all.

    Per TIER_2_AGENT_BUILDER_ROADMAP §3: 'mini_parwa: No agents (generic AI only)'.

    Expected behavior:
    - Node 1 detects capability, sees no agent claims it
    - Quota check shows max=0 → tier_allows_agents=False
    - Node 1 sets required_action='process' (NOT escalate_human, NOT pause)
    - No vault escalation saved
    - No agent:approval_required event emitted
    - No agent:limit_reached event emitted
    - Builder pipeline NOT called
    """
    # Mock quota: Mini tier = 0 agents
    _quota_check = {
        "ai_agents": {"allowed": True, "current_usage": 0, "limit": 0, "remaining": 0},
    }
    _limit_svc = MagicMock()
    _limit_svc.get_all_limit_checks.return_value = _quota_check
    # enforce_limit should NOT be called for Mini — if it is, fail the test
    _limit_svc.enforce_limit.side_effect = AssertionError(
        "enforce_limit must NOT be called for Mini tier (max_agents=0)"
    )
    with patch(
        "app.services.variant_limit_service.get_variant_limit_service",
        return_value=_limit_svc,
    ):
        # VaultManager.save_escalation_from_pipeline must NOT be called for Mini
        with patch(
            "app.core.escalation_vault.vault_manager.VaultManager.save_escalation_from_pipeline",
            new_callable=AsyncMock,
            side_effect=AssertionError("Vault save must NOT happen for Mini tier"),
        ):
            # Builder must NOT run for Mini
            with patch(
                "app.core.builder_agent.builder_pipeline.run_builder_pipeline",
                new_callable=AsyncMock,
                side_effect=AssertionError("Builder must NOT run for Mini tier"),
            ):
                from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify
                result = await node_1_ingest_classify(base_state)

    # Quota status event WAS emitted (awareness)
    quota_events = [e for e in captured_events if e["event_type"] == "agent:quota_status"]
    assert len(quota_events) == 1
    assert quota_events[0]["payload"]["max"] == 0
    assert quota_events[0]["payload"]["tier_allows_agents"] is False

    # NO approval_required event for Mini
    approval_events = [e for e in captured_events if e["event_type"] == "agent:approval_required"]
    assert len(approval_events) == 0, "Mini tier must NOT emit agent:approval_required"

    # NO limit_reached event for Mini
    limit_events = [e for e in captured_events if e["event_type"] == "agent:limit_reached"]
    assert len(limit_events) == 0, "Mini tier must NOT emit agent:limit_reached"

    # required_action = "process" (NOT escalate_human, NOT pause_for_agent_approval)
    assert result.get("required_action") == "process"
    assert result.get("action_details", {}).get("reason") == "mini_tier_generic_ai"


# ═══════════════════════════════════════════════════════════════════════
# Test 7: Parwa tier (max_agents=5) still triggers approval flow
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_parwa_tier_triggers_approval_flow(
    base_state, mock_llm_call, mock_wiki_store,
    patch_emit_ticket_event, patch_no_capability_claimed, patch_no_embedded_kb,
    captured_events,
):
    """Parwa tier (max_agents=5) with quota available must trigger the
    approval flow — save to vault, emit agent:approval_required, pause."""
    _quota_check = {
        "ai_agents": {"allowed": True, "current_usage": 2, "limit": 5, "remaining": 3},
    }
    _limit_svc = MagicMock()
    _limit_svc.get_all_limit_checks.return_value = _quota_check
    _limit_svc.enforce_limit.return_value = _quota_check["ai_agents"]
    with patch(
        "app.services.variant_limit_service.get_variant_limit_service",
        return_value=_limit_svc,
    ):
        with patch(
            "app.core.escalation_vault.vault_manager.VaultManager.save_escalation_from_pipeline",
            new_callable=AsyncMock,
            return_value={"escalation_id": "esc_parwa_001"},
        ):
            from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify
            result = await node_1_ingest_classify(base_state)

    # Quota status event shows tier_allows_agents=True
    quota_events = [e for e in captured_events if e["event_type"] == "agent:quota_status"]
    assert len(quota_events) == 1
    assert quota_events[0]["payload"]["tier_allows_agents"] is True
    assert quota_events[0]["payload"]["max"] == 5

    # Approval required event WAS emitted
    approval_events = [e for e in captured_events if e["event_type"] == "agent:approval_required"]
    assert len(approval_events) == 1

    # required_action = "pause_for_agent_approval"
    assert result.get("required_action") == "pause_for_agent_approval"
    assert result.get("action_details", {}).get("escalation_id") == "esc_parwa_001"
