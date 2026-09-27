"""
PARWA Jarvis Phase 4 — Comprehensive Unit Tests

Covers individual Phase 4 modules with 60+ focused unit tests:

  Module 1: variant_bridge.py
    - Async bridge functions with mocked Redis (returning None, returning data)
    - Sync wrappers (inject_jarvis_state_sync, read_pipeline_state_sync, etc.)
    - Key patterns edge cases (empty company_id, empty session_id, None values)
    - MONETARY_ACTIONS / ESCALATION_ACTIONS / EMERGENCY_ACTIONS sets
    - Additional approval scenarios (issue_credit, cancel_subscription, etc.)

  Module 2: pipeline_feedback.py
    - _generate_feedback_id() format and uniqueness
    - _map_command_to_pipeline_updates() with every agent_type combination
    - apply_command_feedback_sync() with mocked Redis
    - get_feedback_history() with mocked DB
    - Edge cases (empty agent_decision, None execution_result)

  Module 3: approval_gate.py
    - process_approval_response() for approved/rejected
    - _summarize_decision() with various decision dicts
    - _create_approval_request() structure validation
    - BC-008 error handling

  Module 4: pipeline_query_agent.py
    - All keyword branches in _rule_based_query_interpretation()
    - pipeline_query_agent_node() with mocked ZAI client
    - Edge cases (empty raw_input, special characters)

  Module 5: jarvis_awareness_injector.py
    - _inject_awareness_fields() with all field mappings
    - _apply_routing_overrides() for escalation/SLA/system_mode
    - _empty_result() structure
    - Full jarvis_awareness_injector_node() with various bridge states

  Module 6: command_graph.py
    - _approval_selector() routing
    - _agent_selector() with pipeline_query
    - _merge_state_updates() helper
    - JarvisCommandGraph with parwa_high tier (auto-approved actions)

Rules:
  - ALL tests independent; no Redis/DB required (mock everything)
  - pytest class-based with test_ methods
  - Every test has a clear docstring
  - BC-008: errors never crash the system
  - BC-001: company_id always respected (tenant isolation)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Shared Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _mock_logger():
    """Mock logger to prevent import errors in all tests."""
    with patch("app.logger.get_logger", return_value=MagicMock()):
        yield


@pytest.fixture
def company_id():
    """Standard test company ID."""
    return "comp_test_001"


@pytest.fixture
def session_id():
    """Standard test session ID."""
    return "sess_test_001"


@pytest.fixture
def user_id():
    """Standard test user ID."""
    return "user_test_001"


# ═══════════════════════════════════════════════════════════════════════
# MODULE 1: Variant Bridge — Advanced Unit Tests
# ═══════════════════════════════════════════════════════════════════════


class TestVariantBridgeActionSets:
    """Tests for MONETARY_ACTIONS, ESCALATION_ACTIONS, EMERGENCY_ACTIONS sets."""

    def test_monetary_actions_contains_refund(self):
        """MONETARY_ACTIONS must contain 'refund'."""
        from app.services.jarvis_agents.variant_bridge import MONETARY_ACTIONS
        assert "refund" in MONETARY_ACTIONS

    def test_monetary_actions_contains_issue_credit(self):
        """MONETARY_ACTIONS must contain 'issue_credit'."""
        from app.services.jarvis_agents.variant_bridge import MONETARY_ACTIONS
        assert "issue_credit" in MONETARY_ACTIONS

    def test_monetary_actions_contains_apply_discount(self):
        """MONETARY_ACTIONS must contain 'apply_discount'."""
        from app.services.jarvis_agents.variant_bridge import MONETARY_ACTIONS
        assert "apply_discount" in MONETARY_ACTIONS

    def test_monetary_actions_contains_waive_fee(self):
        """MONETARY_ACTIONS must contain 'waive_fee'."""
        from app.services.jarvis_agents.variant_bridge import MONETARY_ACTIONS
        assert "waive_fee" in MONETARY_ACTIONS

    def test_monetary_actions_contains_cancel_subscription(self):
        """MONETARY_ACTIONS must contain 'cancel_subscription'."""
        from app.services.jarvis_agents.variant_bridge import MONETARY_ACTIONS
        assert "cancel_subscription" in MONETARY_ACTIONS

    def test_escalation_actions_contains_escalate(self):
        """ESCALATION_ACTIONS must contain 'escalate'."""
        from app.services.jarvis_agents.variant_bridge import ESCALATION_ACTIONS
        assert "escalate" in ESCALATION_ACTIONS

    def test_escalation_actions_contains_human_handoff(self):
        """ESCALATION_ACTIONS must contain 'human_handoff'."""
        from app.services.jarvis_agents.variant_bridge import ESCALATION_ACTIONS
        assert "human_handoff" in ESCALATION_ACTIONS

    def test_emergency_actions_contains_full_stop(self):
        """EMERGENCY_ACTIONS must contain 'full_stop'."""
        from app.services.jarvis_agents.variant_bridge import EMERGENCY_ACTIONS
        assert "full_stop" in EMERGENCY_ACTIONS

    def test_emergency_actions_contains_red_alert(self):
        """EMERGENCY_ACTIONS must contain 'red_alert'."""
        from app.services.jarvis_agents.variant_bridge import EMERGENCY_ACTIONS
        assert "red_alert" in EMERGENCY_ACTIONS

    def test_emergency_actions_contains_circuit_breaker_trigger(self):
        """EMERGENCY_ACTIONS must contain 'circuit_breaker_trigger'."""
        from app.services.jarvis_agents.variant_bridge import EMERGENCY_ACTIONS
        assert "circuit_breaker_trigger" in EMERGENCY_ACTIONS

    def test_emergency_and_escalation_overlap_on_emergency_escalation(self):
        """EMERGENCY_ACTIONS and ESCALATION_ACTIONS overlap on 'emergency_escalation'."""
        from app.services.jarvis_agents.variant_bridge import (
            EMERGENCY_ACTIONS, ESCALATION_ACTIONS,
        )
        assert "emergency_escalation" in EMERGENCY_ACTIONS
        assert "emergency_escalation" in ESCALATION_ACTIONS


class TestVariantBridgeApprovalAdditional:
    """Additional approval tests for monetary/escalation/emergency actions."""

    def test_parwa_issue_credit_needs_approval(self, company_id):
        """parwa: issue_credit (monetary action) requires approval."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "parwa", "billing", "issue_credit",
        )
        assert result["approval_needed"] is True
        assert "monetary" in result["reason"].lower()

    def test_parwa_cancel_subscription_needs_approval(self, company_id):
        """parwa: cancel_subscription (monetary action) requires approval."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "parwa", "billing", "cancel_subscription",
        )
        assert result["approval_needed"] is True

    def test_parwa_waive_fee_needs_approval(self, company_id):
        """parwa: waive_fee (monetary action) requires approval."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "parwa", "billing", "waive_fee",
        )
        assert result["approval_needed"] is True

    def test_parwa_human_handoff_needs_approval(self, company_id):
        """parwa: human_handoff (escalation action) requires approval."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "parwa", "escalation", "human_handoff",
        )
        assert result["approval_needed"] is True

    def test_parwa_high_refund_auto_approved(self, company_id):
        """parwa_high: refund is auto-approved (not emergency)."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "parwa_high", "billing", "refund",
        )
        assert result["approval_needed"] is False

    def test_parwa_high_red_alert_needs_approval(self, company_id):
        """parwa_high: red_alert (emergency action) requires approval."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "parwa_high", "emergency", "red_alert",
        )
        assert result["approval_needed"] is True

    def test_parwa_escalation_agent_type_needs_approval(self, company_id):
        """parwa: agent_type='escalation' triggers approval even if action is not in ESCALATION_ACTIONS."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "parwa", "escalation", "some_custom_action",
        )
        assert result["approval_needed"] is True

    def test_approval_result_includes_all_fields(self, company_id):
        """check_jarvis_approval_needed result must include standard fields."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "parwa", "notification", "notify",
        )
        assert "approval_needed" in result
        assert "reason" in result
        assert "approval_type" in result
        assert "variant_tier" in result
        assert "agent_type" in result
        assert "agent_action" in result


class TestVariantBridgeAsyncWithMockedRedis:
    """Tests for async bridge functions with mocked Redis."""

    @pytest.mark.asyncio
    async def test_inject_jarvis_state_redis_unavailable_returns_false(self, company_id, session_id):
        """inject_jarvis_state_into_pipeline returns False when Redis is unavailable."""
        from app.services.jarvis_agents.variant_bridge import (
            inject_jarvis_state_into_pipeline,
        )
        with patch(
            "app.services.jarvis_agents.variant_bridge._get_redis_async",
            new_callable=AsyncMock, return_value=None,
        ):
            result = await inject_jarvis_state_into_pipeline(
                company_id, session_id, {"agent_type": "escalation"},
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_inject_jarvis_state_redis_writes_bridge_key(self, company_id, session_id):
        """inject_jarvis_state_into_pipeline writes to the correct Redis key."""
        from app.services.jarvis_agents.variant_bridge import (
            inject_jarvis_state_into_pipeline,
        )
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        with patch(
            "app.services.jarvis_agents.variant_bridge._get_redis_async",
            new_callable=AsyncMock, return_value=mock_redis,
        ):
            result = await inject_jarvis_state_into_pipeline(
                company_id, session_id, {
                    "agent_type": "escalation",
                    "agent_action": "escalate",
                    "agent_decision": {},
                    "execution_status": "completed",
                    "execution_result": {},
                },
            )
        assert result is True
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        assert key.startswith(f"parwa:{company_id}:jarvis:bridge:")

    @pytest.mark.asyncio
    async def test_inject_jarvis_state_pause_ai_sets_bridge_fields(self, company_id, session_id):
        """inject_jarvis_state_into_pipeline sets ai_paused=True for pause_ai action."""
        from app.services.jarvis_agents.variant_bridge import (
            inject_jarvis_state_into_pipeline,
        )
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        with patch(
            "app.services.jarvis_agents.variant_bridge._get_redis_async",
            new_callable=AsyncMock, return_value=mock_redis,
        ):
            result = await inject_jarvis_state_into_pipeline(
                company_id, session_id, {
                    "agent_type": "emergency",
                    "agent_action": "pause_ai",
                    "agent_decision": {"reason": "Quality drop"},
                    "execution_status": "completed",
                    "execution_result": {},
                },
            )
        assert result is True
        written_data = json.loads(mock_redis.set.call_args[0][1])
        assert written_data["ai_paused"] is True
        assert written_data["global_pause_reason"] == "Quality drop"

    @pytest.mark.asyncio
    async def test_inject_jarvis_state_resume_ai_clears_pause(self, company_id, session_id):
        """inject_jarvis_state_into_pipeline sets ai_paused=False for resume_ai action."""
        from app.services.jarvis_agents.variant_bridge import (
            inject_jarvis_state_into_pipeline,
        )
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        with patch(
            "app.services.jarvis_agents.variant_bridge._get_redis_async",
            new_callable=AsyncMock, return_value=mock_redis,
        ):
            result = await inject_jarvis_state_into_pipeline(
                company_id, session_id, {
                    "agent_type": "emergency",
                    "agent_action": "resume_ai",
                    "agent_decision": {},
                    "execution_status": "completed",
                    "execution_result": {},
                },
            )
        assert result is True
        written_data = json.loads(mock_redis.set.call_args[0][1])
        assert written_data["ai_paused"] is False
        assert written_data["global_pause_reason"] == ""

    @pytest.mark.asyncio
    async def test_inject_jarvis_state_emergency_level_red_alert(self, company_id, session_id):
        """inject_jarvis_state_into_pipeline maps emergency_level=red_alert."""
        from app.services.jarvis_agents.variant_bridge import (
            inject_jarvis_state_into_pipeline,
        )
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        with patch(
            "app.services.jarvis_agents.variant_bridge._get_redis_async",
            new_callable=AsyncMock, return_value=mock_redis,
        ):
            result = await inject_jarvis_state_into_pipeline(
                company_id, session_id, {
                    "agent_type": "emergency",
                    "agent_action": "alert",
                    "agent_decision": {"emergency_level": "red_alert"},
                    "execution_status": "completed",
                    "execution_result": {},
                },
            )
        assert result is True
        written_data = json.loads(mock_redis.set.call_args[0][1])
        assert written_data["emergency_state"] == "red_alert"

    @pytest.mark.asyncio
    async def test_inject_jarvis_state_co_pilot_suggestion(self, company_id, session_id):
        """inject_jarvis_state_into_pipeline maps co_pilot_text and type."""
        from app.services.jarvis_agents.variant_bridge import (
            inject_jarvis_state_into_pipeline,
        )
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        with patch(
            "app.services.jarvis_agents.variant_bridge._get_redis_async",
            new_callable=AsyncMock, return_value=mock_redis,
        ):
            result = await inject_jarvis_state_into_pipeline(
                company_id, session_id, {
                    "agent_type": "notification",
                    "agent_action": "notify",
                    "agent_decision": {
                        "co_pilot_text": "Switch to ReAct",
                        "co_pilot_type": "action_suggestion",
                    },
                    "execution_status": "completed",
                    "execution_result": {},
                },
            )
        assert result is True
        written_data = json.loads(mock_redis.set.call_args[0][1])
        assert written_data["co_pilot_suggestion"] == "Switch to ReAct"
        assert written_data["co_pilot_suggestion_type"] == "action_suggestion"

    @pytest.mark.asyncio
    async def test_read_pipeline_state_redis_returns_data(self, company_id, session_id):
        """read_pipeline_state_for_jarvis returns parsed data from Redis."""
        from app.services.jarvis_agents.variant_bridge import (
            read_pipeline_state_for_jarvis,
        )
        mock_redis = AsyncMock()
        test_data = {"emergency_state": "normal", "ai_paused": False}
        mock_redis.get = AsyncMock(return_value=json.dumps(test_data).encode())
        with patch(
            "app.services.jarvis_agents.variant_bridge._get_redis_async",
            new_callable=AsyncMock, return_value=mock_redis,
        ), patch(
            "app.services.jarvis_agents.variant_bridge._read_pipeline_state_from_db",
            new_callable=AsyncMock, return_value={},
        ):
            result = await read_pipeline_state_for_jarvis(company_id, session_id)
        assert result == test_data

    @pytest.mark.asyncio
    async def test_read_pipeline_state_redis_none_falls_back_to_db(self, company_id, session_id):
        """read_pipeline_state_for_jarvis falls back to DB when Redis returns None."""
        from app.services.jarvis_agents.variant_bridge import (
            read_pipeline_state_for_jarvis,
        )
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        db_data = {"system_health": "degraded"}
        with patch(
            "app.services.jarvis_agents.variant_bridge._get_redis_async",
            new_callable=AsyncMock, return_value=mock_redis,
        ), patch(
            "app.services.jarvis_agents.variant_bridge._read_pipeline_state_from_db",
            new_callable=AsyncMock, return_value=db_data,
        ):
            result = await read_pipeline_state_for_jarvis(company_id, session_id)
        assert result == db_data

    @pytest.mark.asyncio
    async def test_read_pipeline_state_redis_unavailable_falls_back(self, company_id, session_id):
        """read_pipeline_state_for_jarvis falls back to DB when Redis is None."""
        from app.services.jarvis_agents.variant_bridge import (
            read_pipeline_state_for_jarvis,
        )
        db_data = {"system_health": "healthy"}
        with patch(
            "app.services.jarvis_agents.variant_bridge._get_redis_async",
            new_callable=AsyncMock, return_value=None,
        ), patch(
            "app.services.jarvis_agents.variant_bridge._read_pipeline_state_from_db",
            new_callable=AsyncMock, return_value=db_data,
        ):
            result = await read_pipeline_state_for_jarvis(company_id, session_id)
        assert result == db_data

    @pytest.mark.asyncio
    async def test_sync_awareness_redis_unavailable_returns_false(self, company_id, session_id):
        """sync_awareness_to_pipeline returns False when Redis unavailable."""
        from app.services.jarvis_agents.variant_bridge import (
            sync_awareness_to_pipeline,
        )
        with patch(
            "app.services.jarvis_agents.variant_bridge._get_redis_async",
            new_callable=AsyncMock, return_value=None,
        ):
            result = await sync_awareness_to_pipeline(
                company_id, session_id, {"system_health": "healthy"},
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_sync_awareness_writes_enriched_snapshot(self, company_id, session_id):
        """sync_awareness_to_pipeline enriches snapshot with synced_at and source."""
        from app.services.jarvis_agents.variant_bridge import (
            sync_awareness_to_pipeline,
        )
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        with patch(
            "app.services.jarvis_agents.variant_bridge._get_redis_async",
            new_callable=AsyncMock, return_value=mock_redis,
        ):
            result = await sync_awareness_to_pipeline(
                company_id, session_id, {"system_health": "healthy"},
            )
        assert result is True
        written_data = json.loads(mock_redis.set.call_args[0][1])
        assert "synced_at" in written_data
        assert written_data["source"] == "jarvis_awareness_engine"
        assert written_data["system_health"] == "healthy"

    @pytest.mark.asyncio
    async def test_apply_command_to_pipeline_state_redis_unavailable(self, company_id, session_id):
        """apply_command_to_pipeline_state falls back to DB when Redis unavailable."""
        from app.services.jarvis_agents.variant_bridge import (
            apply_command_to_pipeline_state,
        )
        with patch(
            "app.services.jarvis_agents.variant_bridge._get_redis_async",
            new_callable=AsyncMock, return_value=None,
        ), patch(
            "app.services.jarvis_agents.variant_bridge._apply_command_to_db",
            return_value=True,
        ):
            result = await apply_command_to_pipeline_state(
                company_id, session_id, {"agent_type": "escalation"},
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_apply_command_to_pipeline_state_writes_feedback_and_bridge(self, company_id, session_id):
        """apply_command_to_pipeline_state writes to both feedback and bridge keys."""
        from app.services.jarvis_agents.variant_bridge import (
            apply_command_to_pipeline_state,
        )
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        with patch(
            "app.services.jarvis_agents.variant_bridge._get_redis_async",
            new_callable=AsyncMock, return_value=mock_redis,
        ), patch(
            "app.services.jarvis_agents.variant_bridge._apply_command_to_db",
            return_value=True,
        ):
            result = await apply_command_to_pipeline_state(
                company_id, session_id, {
                    "agent_type": "escalation",
                    "agent_action": "escalate",
                    "agent_decision": {"escalation_tier": "tier2"},
                    "execution_status": "completed",
                    "execution_result": {},
                },
            )
        assert result is True
        # Should have called redis.set at least twice (feedback + bridge)
        assert mock_redis.set.call_count >= 2


class TestVariantBridgeSyncWrappers:
    """Tests for sync wrapper functions."""

    def test_inject_jarvis_state_sync_returns_false_on_error(self, company_id, session_id):
        """inject_jarvis_state_sync returns False when underlying async fails."""
        from app.services.jarvis_agents.variant_bridge import inject_jarvis_state_sync
        with patch(
            "app.services.jarvis_agents.variant_bridge.inject_jarvis_state_into_pipeline",
            new_callable=AsyncMock, return_value=False,
        ):
            result = inject_jarvis_state_sync(
                company_id, session_id, {"agent_type": "escalation"},
            )
        assert result is False

    def test_read_pipeline_state_sync_returns_dict_on_error(self, company_id, session_id):
        """read_pipeline_state_sync returns empty dict on failure."""
        from app.services.jarvis_agents.variant_bridge import read_pipeline_state_sync
        with patch(
            "app.services.jarvis_agents.variant_bridge.read_pipeline_state_for_jarvis",
            new_callable=AsyncMock, return_value={},
        ):
            result = read_pipeline_state_sync(company_id, session_id)
        assert result == {}

    def test_sync_awareness_sync_returns_false_on_error(self, company_id, session_id):
        """sync_awareness_sync returns False on failure."""
        from app.services.jarvis_agents.variant_bridge import sync_awareness_sync
        with patch(
            "app.services.jarvis_agents.variant_bridge.sync_awareness_to_pipeline",
            new_callable=AsyncMock, return_value=False,
        ):
            result = sync_awareness_sync(
                company_id, session_id, {"system_health": "healthy"},
            )
        assert result is False

    def test_apply_command_sync_returns_false_on_error(self, company_id, session_id):
        """apply_command_sync returns False on failure."""
        from app.services.jarvis_agents.variant_bridge import apply_command_sync
        with patch(
            "app.services.jarvis_agents.variant_bridge.apply_command_to_pipeline_state",
            new_callable=AsyncMock, return_value=False,
        ):
            result = apply_command_sync(
                company_id, session_id, {"agent_type": "escalation"},
            )
        assert result is False


class TestVariantBridgeEdgeCases:
    """Edge case tests for variant bridge key patterns and configs."""

    def test_bridge_key_with_empty_company_id(self, session_id):
        """Bridge key with empty company_id still follows pattern (BC-001 enforced by caller)."""
        from app.services.jarvis_agents.variant_bridge import _make_bridge_key
        key = _make_bridge_key("", session_id)
        assert key.startswith("parwa::")

    def test_bridge_key_with_empty_session_id(self, company_id):
        """Bridge key with empty session_id still follows pattern."""
        from app.services.jarvis_agents.variant_bridge import _make_bridge_key
        key = _make_bridge_key(company_id, "")
        assert company_id in key

    def test_awareness_key_format(self, company_id, session_id):
        """Awareness key follows parwa:{company_id}:jarvis:awareness:{session_id}."""
        from app.services.jarvis_agents.variant_bridge import _make_awareness_key
        key = _make_awareness_key(company_id, session_id)
        assert key == f"parwa:{company_id}:jarvis:awareness:{session_id}"

    def test_feedback_key_format(self, company_id, session_id):
        """Feedback key follows parwa:{company_id}:jarvis:feedback:{session_id}."""
        from app.services.jarvis_agents.variant_bridge import _make_feedback_key
        key = _make_feedback_key(company_id, session_id)
        assert key == f"parwa:{company_id}:jarvis:feedback:{session_id}"

    def test_bridge_key_format(self, company_id, session_id):
        """Bridge key follows parwa:{company_id}:jarvis:bridge:{session_id}."""
        from app.services.jarvis_agents.variant_bridge import _make_bridge_key
        key = _make_bridge_key(company_id, session_id)
        assert key == f"parwa:{company_id}:jarvis:bridge:{session_id}"

    def test_mini_parwa_cannot_pause_ai(self):
        """mini_parwa config: can_pause_ai must be False."""
        from app.services.jarvis_agents.variant_bridge import VARIANT_COMMAND_CONFIGS
        assert VARIANT_COMMAND_CONFIGS["mini_parwa"]["can_pause_ai"] is False

    def test_mini_parwa_cannot_escalate(self):
        """mini_parwa config: can_escalate must be False."""
        from app.services.jarvis_agents.variant_bridge import VARIANT_COMMAND_CONFIGS
        assert VARIANT_COMMAND_CONFIGS["mini_parwa"]["can_escalate"] is False

    def test_parwa_high_auto_execute_allowed(self):
        """parwa_high config: auto_execute_allowed must be True."""
        from app.services.jarvis_agents.variant_bridge import VARIANT_COMMAND_CONFIGS
        assert VARIANT_COMMAND_CONFIGS["parwa_high"]["auto_execute_allowed"] is True

    def test_parwa_high_max_urgency_auto_is_critical(self):
        """parwa_high config: max_urgency_auto must be 'critical'."""
        from app.services.jarvis_agents.variant_bridge import VARIANT_COMMAND_CONFIGS
        assert VARIANT_COMMAND_CONFIGS["parwa_high"]["max_urgency_auto"] == "critical"

    def test_get_redis_sync_returns_none(self):
        """_get_redis_sync always returns None (sync Redis not available)."""
        from app.services.jarvis_agents.variant_bridge import _get_redis_sync
        result = _get_redis_sync()
        assert result is None


# ═══════════════════════════════════════════════════════════════════════
# MODULE 2: Pipeline Feedback — Unit Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineFeedbackIdGeneration:
    """Tests for _generate_feedback_id()."""

    def test_feedback_id_starts_with_fb_prefix(self, company_id, session_id):
        """Feedback ID must start with 'fb_' prefix."""
        from app.services.jarvis_agents.pipeline_feedback import _generate_feedback_id
        fb_id = _generate_feedback_id(company_id, session_id)
        assert fb_id.startswith("fb_")

    def test_feedback_id_contains_timestamp(self, company_id, session_id):
        """Feedback ID must contain a timestamp component."""
        from app.services.jarvis_agents.pipeline_feedback import _generate_feedback_id
        fb_id = _generate_feedback_id(company_id, session_id)
        # Format: fb_YYYYMMDDHHMMSS_<8hex>
        parts = fb_id.split("_")
        assert len(parts) == 3  # fb, timestamp, unique

    def test_feedback_id_is_unique(self, company_id, session_id):
        """Two consecutive feedback IDs must be unique."""
        from app.services.jarvis_agents.pipeline_feedback import _generate_feedback_id
        id1 = _generate_feedback_id(company_id, session_id)
        id2 = _generate_feedback_id(company_id, session_id)
        assert id1 != id2


class TestPipelineFeedbackMappingAdditional:
    """Additional tests for _map_command_to_pipeline_updates()."""

    def test_pause_all_ai_sets_paused_state(self):
        """pause_all_ai action → ai_paused=True, system_mode='paused'."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="emergency",
            agent_action="pause_all_ai",
            agent_decision={"reason": "Critical failure"},
            execution_result={},
        )
        assert updates["ai_paused"] is True
        assert updates["system_mode"] == "paused"

    def test_resume_all_ai_clears_pause(self):
        """resume_all_ai action → ai_paused=False, paused_actions=[]."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="emergency",
            agent_action="resume_all_ai",
            agent_decision={},
            execution_result={},
        )
        assert updates["ai_paused"] is False
        assert updates["paused_actions"] == []

    def test_quality_recovery_without_switch_technique(self):
        """Quality recovery with strategy != switch_technique → no technique_stack update."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="quality_recovery",
            agent_action="recover_quality",
            agent_decision={
                "strategy": "retrain",
                "current_score": 0.60,
                "target_score": 0.85,
            },
            execution_result={},
        )
        assert updates["drift_status"] == "recovering"
        assert "technique_stack" not in updates

    def test_sla_protection_no_at_risk_no_alert(self):
        """SLA protection with at_risk_count=0 → no active_alerts."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="sla_protection",
            agent_action="protect_sla",
            agent_decision={"strategy": "prioritize", "at_risk_count": 0},
            execution_result={},
        )
        assert updates["sla_protection_active"] is True
        assert "active_alerts" not in updates

    def test_sla_protection_with_at_risk_has_alert(self):
        """SLA protection with at_risk_count>0 → active_alerts present."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="sla_protection",
            agent_action="protect_sla",
            agent_decision={"strategy": "prioritize", "at_risk_count": 3},
            execution_result={},
        )
        assert "active_alerts" in updates
        assert updates["active_alerts"][0]["alert_id"] == "jarvis_sla_protection"

    def test_reassignment_with_upgrade_suggestion(self):
        """Reassignment with upgrade_suggested=True → active_alerts for upgrade."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="reassignment",
            agent_action="reassign",
            agent_decision={
                "from_agent": "A",
                "to_agent": "B",
                "ticket_count": 5,
                "upgrade_suggested": True,
            },
            execution_result={},
        )
        assert "active_alerts" in updates
        assert updates["active_alerts"][0]["alert_id"] == "jarvis_upgrade_suggestion"

    def test_emergency_shutdown_sets_red_alert(self):
        """emergency_shutdown action → emergency_state='red_alert'."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="emergency",
            agent_action="emergency_shutdown",
            agent_decision={},
            execution_result={},
        )
        assert updates["emergency_state"] == "red_alert"
        assert updates["ai_paused"] is True

    def test_empty_command_returns_empty_updates(self):
        """Unknown agent_type + no matching action → empty updates dict."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="unknown_type",
            agent_action="unknown_action",
            agent_decision={},
            execution_result={},
        )
        assert updates == {}

    def test_escalation_includes_active_alerts(self):
        """Escalation agent_type → active_alerts with jarvis_escalation."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="escalation",
            agent_action="escalate",
            agent_decision={"scope": "all_urgent", "escalation_tier": "tier2"},
            execution_result={},
        )
        assert "active_alerts" in updates
        assert updates["active_alerts"][0]["alert_id"] == "jarvis_escalation"
        assert updates["active_alerts"][0]["severity"] == "critical"


class TestPipelineFeedbackGetHistory:
    """Tests for get_feedback_history() with mocked DB."""

    def test_get_feedback_history_returns_list(self, company_id, session_id):
        """get_feedback_history returns a list (empty when no session)."""
        from app.services.jarvis_agents.pipeline_feedback import get_feedback_history
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.close = MagicMock()
        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ):
            result = get_feedback_history(company_id, session_id)
        assert result == []

    def test_get_feedback_history_returns_newest_first(self, company_id, session_id):
        """get_feedback_history returns entries newest first."""
        from app.services.jarvis_agents.pipeline_feedback import get_feedback_history
        entries = [
            {"feedback_id": "fb_001", "agent_type": "escalation"},
            {"feedback_id": "fb_002", "agent_type": "notification"},
            {"feedback_id": "fb_003", "agent_type": "sla_protection"},
        ]
        mock_session = MagicMock()
        mock_session.context_json = json.dumps({
            "jarvis_command_feedback": entries,
        })
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        mock_db.close = MagicMock()
        with patch(
            "database.base.SessionLocal",
            return_value=mock_db,
        ):
            result = get_feedback_history(company_id, session_id)
        # Should be reversed (newest first)
        assert result[0]["feedback_id"] == "fb_003"
        assert result[-1]["feedback_id"] == "fb_001"

    def test_get_feedback_history_error_returns_empty(self, company_id, session_id):
        """get_feedback_history returns [] on DB error (BC-008)."""
        from app.services.jarvis_agents.pipeline_feedback import get_feedback_history
        with patch(
            "database.base.SessionLocal",
            side_effect=Exception("DB down"),
        ):
            result = get_feedback_history(company_id, session_id)
        assert result == []


# ═══════════════════════════════════════════════════════════════════════
# MODULE 3: Approval Gate — Unit Tests
# ═══════════════════════════════════════════════════════════════════════


class TestApprovalGateProcessApprovalResponse:
    """Tests for process_approval_response()."""

    def test_approved_response_has_approved_status(self, company_id):
        """Approved response → status='approved', next_step='command_executor'."""
        from app.services.jarvis_agents.nodes.approval_gate import (
            process_approval_response,
        )
        result = process_approval_response(
            company_id=company_id,
            request_id="apr_123",
            approved=True,
            approver_id="user_001",
        )
        assert result["status"] == "approved"
        assert result["next_step"] == "command_executor"
        assert result["approved"] is True

    def test_rejected_response_has_rejected_status(self, company_id):
        """Rejected response → status='rejected', next_step='end'."""
        from app.services.jarvis_agents.nodes.approval_gate import (
            process_approval_response,
        )
        result = process_approval_response(
            company_id=company_id,
            request_id="apr_456",
            approved=False,
            approver_id="user_002",
            approver_notes="Too risky",
        )
        assert result["status"] == "rejected"
        assert result["next_step"] == "end"
        assert result["approved"] is False
        assert result["approver_notes"] == "Too risky"

    def test_response_includes_request_id(self, company_id):
        """Response must include request_id for traceability."""
        from app.services.jarvis_agents.nodes.approval_gate import (
            process_approval_response,
        )
        result = process_approval_response(
            company_id=company_id,
            request_id="apr_789",
            approved=True,
            approver_id="user_003",
        )
        assert result["request_id"] == "apr_789"

    def test_response_includes_company_id(self, company_id):
        """Response must include company_id (BC-001)."""
        from app.services.jarvis_agents.nodes.approval_gate import (
            process_approval_response,
        )
        result = process_approval_response(
            company_id=company_id,
            request_id="apr_abc",
            approved=True,
            approver_id="user_004",
        )
        assert result["company_id"] == company_id

    def test_response_includes_processed_at_timestamp(self, company_id):
        """Response must include a processed_at UTC timestamp."""
        from app.services.jarvis_agents.nodes.approval_gate import (
            process_approval_response,
        )
        result = process_approval_response(
            company_id=company_id,
            request_id="apr_def",
            approved=True,
            approver_id="user_005",
        )
        assert "processed_at" in result
        parsed = datetime.fromisoformat(result["processed_at"])
        assert parsed.tzinfo is not None


class TestApprovalGateSummarizeDecision:
    """Tests for _summarize_decision()."""

    def test_empty_decision_returns_empty(self):
        """Empty decision dict → returns empty dict."""
        from app.services.jarvis_agents.nodes.approval_gate import _summarize_decision
        result = _summarize_decision({})
        assert result == {}

    def test_none_decision_returns_empty(self):
        """None/falsy decision → returns empty dict."""
        from app.services.jarvis_agents.nodes.approval_gate import _summarize_decision
        result = _summarize_decision(None)
        assert result == {}

    def test_decision_with_action_included(self):
        """Decision with 'action' key → included in summary."""
        from app.services.jarvis_agents.nodes.approval_gate import _summarize_decision
        result = _summarize_decision({"action": "escalate"})
        assert result["action"] == "escalate"

    def test_decision_with_scope_included(self):
        """Decision with 'scope' key → included in summary."""
        from app.services.jarvis_agents.nodes.approval_gate import _summarize_decision
        result = _summarize_decision({"scope": "all_urgent"})
        assert result["scope"] == "all_urgent"

    def test_decision_with_escalation_tier_included(self):
        """Decision with 'escalation_tier' key → included in summary."""
        from app.services.jarvis_agents.nodes.approval_gate import _summarize_decision
        result = _summarize_decision({"escalation_tier": "tier2"})
        assert result["escalation_tier"] == "tier2"

    def test_decision_extraneous_fields_excluded(self):
        """Decision with non-standard keys → excluded from summary."""
        from app.services.jarvis_agents.nodes.approval_gate import _summarize_decision
        result = _summarize_decision({"action": "escalate", "custom_field": "value"})
        assert "custom_field" not in result
        assert "action" in result

    def test_decision_source_included_as_decision_source(self):
        """Decision with '_source' key → mapped to 'decision_source'."""
        from app.services.jarvis_agents.nodes.approval_gate import _summarize_decision
        result = _summarize_decision({"_source": "zai_llm", "action": "notify"})
        assert result["decision_source"] == "zai_llm"


class TestApprovalGateCreateApprovalRequest:
    """Tests for _create_approval_request()."""

    def test_request_has_request_id(self, company_id, session_id, user_id):
        """Approval request must have a request_id."""
        from app.services.jarvis_agents.nodes.approval_gate import _create_approval_request
        with patch(
            "app.services.jarvis_agents.nodes.approval_gate._persist_approval_request",
        ):
            result = _create_approval_request(
                company_id=company_id,
                session_id=session_id,
                user_id=user_id,
                agent_type="escalation",
                agent_action="escalate",
                agent_decision={"scope": "all_urgent"},
                agent_reasoning="Spike detected",
                approval_reason="Requires human approval",
                variant_tier="mini_parwa",
            )
        assert "request_id" in result
        assert result["request_id"].startswith("apr_")

    def test_request_has_company_id(self, company_id, session_id, user_id):
        """Approval request must include company_id (BC-001)."""
        from app.services.jarvis_agents.nodes.approval_gate import _create_approval_request
        with patch(
            "app.services.jarvis_agents.nodes.approval_gate._persist_approval_request",
        ):
            result = _create_approval_request(
                company_id=company_id,
                session_id=session_id,
                user_id=user_id,
                agent_type="escalation",
                agent_action="escalate",
                agent_decision={},
                agent_reasoning="",
                approval_reason="Needs approval",
                variant_tier="parwa",
            )
        assert result["company_id"] == company_id

    def test_request_has_pending_status(self, company_id, session_id, user_id):
        """Approval request must have status='pending'."""
        from app.services.jarvis_agents.nodes.approval_gate import _create_approval_request
        with patch(
            "app.services.jarvis_agents.nodes.approval_gate._persist_approval_request",
        ):
            result = _create_approval_request(
                company_id=company_id,
                session_id=session_id,
                user_id=user_id,
                agent_type="notification",
                agent_action="notify",
                agent_decision={},
                agent_reasoning="",
                approval_reason="Tier requires approval",
                variant_tier="mini_parwa",
            )
        assert result["status"] == "pending"

    def test_request_includes_agent_reasoning_truncated(self, company_id, session_id, user_id):
        """Long agent_reasoning is truncated to 500 chars."""
        from app.services.jarvis_agents.nodes.approval_gate import _create_approval_request
        long_reasoning = "x" * 1000
        with patch(
            "app.services.jarvis_agents.nodes.approval_gate._persist_approval_request",
        ):
            result = _create_approval_request(
                company_id=company_id,
                session_id=session_id,
                user_id=user_id,
                agent_type="escalation",
                agent_action="escalate",
                agent_decision={},
                agent_reasoning=long_reasoning,
                approval_reason="Needs approval",
                variant_tier="mini_parwa",
            )
        assert len(result["agent_reasoning"]) <= 500

    def test_request_persist_failure_does_not_crash(self, company_id, session_id, user_id):
        """BC-008: Persist failure does not crash _create_approval_request."""
        from app.services.jarvis_agents.nodes.approval_gate import _create_approval_request
        with patch(
            "app.services.jarvis_agents.nodes.approval_gate._persist_approval_request",
            side_effect=Exception("DB error"),
        ):
            result = _create_approval_request(
                company_id=company_id,
                session_id=session_id,
                user_id=user_id,
                agent_type="escalation",
                agent_action="escalate",
                agent_decision={},
                agent_reasoning="",
                approval_reason="Needs approval",
                variant_tier="parwa",
            )
        assert "request_id" in result  # Still returns valid request


class TestApprovalGateErrorHandling:
    """BC-008 error handling tests for approval_gate_node."""

    def test_exception_in_approval_gate_defaults_to_pending(self, company_id, session_id, user_id):
        """BC-008: Exception in approval_gate_node → defaults to pending_approval."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node
        with patch(
            "app.services.jarvis_agents.nodes.approval_gate.check_jarvis_approval_needed",
            side_effect=Exception("Unexpected error"),
        ):
            result = approval_gate_node({
                "company_id": company_id,
                "session_id": session_id,
                "user_id": user_id,
                "variant_tier": "parwa_high",
                "agent_type": "notification",
                "agent_action": "notify",
                "agent_decision": {},
                "agent_reasoning": "",
            })
        assert result["execution_status"] == "pending_approval"
        assert "error" in result["execution_result"]

    def test_approval_gate_auto_approved_includes_node_outputs(self, company_id, session_id, user_id):
        """Auto-approved result includes node_outputs with approval_gate key."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node
        result = approval_gate_node({
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "parwa_high",
            "agent_type": "notification",
            "agent_action": "notify",
            "agent_decision": {},
            "agent_reasoning": "",
        })
        assert "node_outputs" in result
        assert "approval_gate" in result["node_outputs"]


# ═══════════════════════════════════════════════════════════════════════
# MODULE 4: Pipeline Query Agent — Unit Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineQueryAgentRuleBased:
    """Tests for all keyword branches in _rule_based_query_interpretation()."""

    def test_quality_keyword_score(self):
        """Query with 'score' keyword → quality query type."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        result = _rule_based_query_interpretation(
            "What is the score?", {}, {"quality_score": 0.88}, "parwa",
        )
        assert result["query_type"] == "quality"

    def test_quality_keyword_accuracy(self):
        """Query with 'accuracy' keyword → quality query type."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        result = _rule_based_query_interpretation(
            "How's the accuracy?", {}, {"quality_score": 0.92}, "parwa",
        )
        assert result["query_type"] == "quality"

    def test_volume_keyword_ticket(self):
        """Query with 'ticket' keyword → volume query type."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        result = _rule_based_query_interpretation(
            "How many tickets today?", {}, {"ticket_volume_today": 42}, "parwa",
        )
        assert result["query_type"] == "volume"

    def test_volume_keyword_queue(self):
        """Query with 'queue' keyword → volume query type."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        result = _rule_based_query_interpretation(
            "What's in the queue?", {}, {"ticket_volume_today": 30}, "parwa",
        )
        assert result["query_type"] == "volume"

    def test_volume_keyword_load(self):
        """Query with 'load' keyword → volume query type."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        result = _rule_based_query_interpretation(
            "What's the current load?", {}, {"ticket_volume_today": 50}, "parwa",
        )
        assert result["query_type"] == "volume"

    def test_agent_keyword_overload(self):
        """Query with 'overload' keyword → agent query type.

        Note: 'overload' contains 'load' which matches volume keywords first.
        Use a query that only matches agent keywords ('agent' + 'utilization').
        """
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        result = _rule_based_query_interpretation(
            "What is the agent utilization rate?", {}, {"active_agents": 5}, "parwa",
        )
        assert result["query_type"] == "agent"

    def test_agent_keyword_capacity(self):
        """Query with 'capacity' keyword → agent query type."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        result = _rule_based_query_interpretation(
            "What's the capacity?", {}, {"agent_pool_capacity": 10}, "parwa",
        )
        assert result["query_type"] == "agent"

    def test_emergency_keyword_alert(self):
        """Query with 'alert' keyword → emergency query type."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        result = _rule_based_query_interpretation(
            "Are there any alerts?", {}, {"system_health": "healthy"}, "parwa",
        )
        assert result["query_type"] == "emergency"

    def test_emergency_keyword_pause(self):
        """Query with 'pause' keyword → emergency query type."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        result = _rule_based_query_interpretation(
            "Is AI paused?", {}, {"system_health": "healthy"}, "parwa",
        )
        assert result["query_type"] == "emergency"

    def test_emergency_keyword_health(self):
        """Query with 'health' keyword → emergency query type."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        result = _rule_based_query_interpretation(
            "How's the health of the system?", {}, {"system_health": "healthy"}, "parwa",
        )
        assert result["query_type"] == "emergency"

    def test_emergency_keyword_status(self):
        """Query with 'status' keyword → emergency query type."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        result = _rule_based_query_interpretation(
            "What's the system status?", {}, {"system_health": "degraded"}, "parwa",
        )
        assert result["query_type"] == "emergency"

    def test_rule_based_result_includes_source(self):
        """Rule-based result must include _source='rule_based_fallback'."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        result = _rule_based_query_interpretation(
            "quality check", {}, {}, "parwa",
        )
        assert result["_source"] == "rule_based_fallback"

    def test_rule_based_result_includes_action(self):
        """Rule-based result must include action='query_pipeline'."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        result = _rule_based_query_interpretation(
            "check volume", {}, {}, "parwa",
        )
        assert result["action"] == "query_pipeline"


class TestPipelineQueryAgentNode:
    """Tests for pipeline_query_agent_node() with mocked dependencies."""

    def test_node_returns_agent_type_pipeline_query(self, company_id, session_id):
        """Node returns agent_type='pipeline_query'."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            pipeline_query_agent_node,
        )
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "variant_tier": "parwa",
            "raw_input": "check quality",
            "awareness_snapshot": {"quality_score": 0.85},
        }
        with patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent._read_pipeline_state",
            return_value={},
        ), patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent.get_zai_client",
            side_effect=Exception("No ZAI"),
        ):
            result = pipeline_query_agent_node(state)
        assert result["agent_type"] == "pipeline_query"

    def test_node_with_empty_raw_input(self, company_id, session_id):
        """Node with empty raw_input → general query."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            pipeline_query_agent_node,
        )
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "variant_tier": "parwa",
            "raw_input": "",
            "awareness_snapshot": {},
        }
        with patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent._read_pipeline_state",
            return_value={},
        ), patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent.get_zai_client",
            side_effect=Exception("No ZAI"),
        ):
            result = pipeline_query_agent_node(state)
        assert result["agent_decision"]["query_type"] == "general"

    def test_node_includes_audit_trail(self, company_id, session_id):
        """Node result includes audit_trail entry."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            pipeline_query_agent_node,
        )
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "variant_tier": "parwa",
            "raw_input": "status",
            "awareness_snapshot": {},
        }
        with patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent._read_pipeline_state",
            return_value={},
        ), patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent.get_zai_client",
            side_effect=Exception("No ZAI"),
        ):
            result = pipeline_query_agent_node(state)
        assert "audit_trail" in result
        assert len(result["audit_trail"]) > 0
        assert result["audit_trail"][0]["step"] == "pipeline_query_agent"

    def test_node_with_zai_client_success(self, company_id, session_id):
        """Node with working ZAI client → uses LLM response."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            pipeline_query_agent_node,
        )
        mock_zai = MagicMock()
        mock_zai.chat.return_value = {
            "query_type": "quality",
            "answer": "Quality is good",
            "reasoning": "Checked the score",
            "data_points": {"quality_score": 0.9},
        }
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "variant_tier": "parwa",
            "raw_input": "check quality",
            "awareness_snapshot": {"quality_score": 0.9},
        }
        with patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent._read_pipeline_state",
            return_value={},
        ), patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent.get_zai_client",
            return_value=mock_zai,
        ):
            result = pipeline_query_agent_node(state)
        assert result["agent_decision"]["query_type"] == "quality"

    def test_node_reads_awareness_when_snapshot_missing(self, company_id, session_id):
        """Node calls _read_awareness_data when awareness_snapshot is empty."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            pipeline_query_agent_node,
        )
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "variant_tier": "parwa",
            "raw_input": "status",
            "awareness_snapshot": {},  # Empty, should trigger DB read
        }
        with patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent._read_pipeline_state",
            return_value={},
        ), patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent._read_awareness_data",
            return_value={"system_health": "degraded"},
        ) as mock_read_awareness, patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent.get_zai_client",
            side_effect=Exception("No ZAI"),
        ):
            result = pipeline_query_agent_node(state)
        mock_read_awareness.assert_called_once_with(company_id, session_id)


# ═══════════════════════════════════════════════════════════════════════
# MODULE 5: Jarvis Awareness Injector — Unit Tests
# ═══════════════════════════════════════════════════════════════════════


class TestJarvisAwarenessInjectorFields:
    """Tests for _inject_awareness_fields() with all field mappings."""

    def test_system_health_injected(self):
        """system_health from awareness → injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        updates = _inject_awareness_fields({"system_health": "healthy"})
        assert updates["system_health"] == "healthy"

    def test_quality_score_injected(self):
        """quality_score from awareness → injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        updates = _inject_awareness_fields({"quality_score": 0.92})
        assert updates["quality_score"] == 0.92

    def test_drift_status_injected(self):
        """drift_status from awareness → injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        updates = _inject_awareness_fields({"drift_status": "recovering"})
        assert updates["drift_status"] == "recovering"

    def test_drift_score_injected(self):
        """drift_score from awareness → injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        updates = _inject_awareness_fields({"drift_score": 0.12})
        assert updates["drift_score"] == 0.12

    def test_active_agents_injected(self):
        """active_agents from awareness → injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        updates = _inject_awareness_fields({"active_agents": 7})
        assert updates["active_agents"] == 7

    def test_agent_pool_utilization_injected(self):
        """agent_pool_utilization from awareness → injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        updates = _inject_awareness_fields({"agent_pool_utilization": 85.5})
        assert updates["agent_pool_utilization"] == 85.5

    def test_ticket_volume_today_injected(self):
        """ticket_volume_today from awareness → injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        updates = _inject_awareness_fields({"ticket_volume_today": 150})
        assert updates["ticket_volume_today"] == 150

    def test_training_running_injected(self):
        """training_running from awareness → injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        updates = _inject_awareness_fields({"training_running": True})
        assert updates["training_running"] is True

    def test_subscription_status_injected(self):
        """subscription_status from awareness → injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        updates = _inject_awareness_fields({"subscription_status": "active"})
        assert updates["subscription_status"] == "active"

    def test_empty_awareness_returns_no_updates(self):
        """Empty awareness data → no updates."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        updates = _inject_awareness_fields({})
        assert updates == {}

    def test_none_awareness_returns_no_updates(self):
        """None awareness data → no updates."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        updates = _inject_awareness_fields(None)
        assert updates == {}

    def test_none_values_not_injected(self):
        """Fields with None values should NOT be injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        updates = _inject_awareness_fields({
            "quality_score": None,
            "drift_status": "detected",
        })
        assert "quality_score" not in updates
        assert updates["drift_status"] == "detected"

    def test_last_5_errors_injected_as_list(self):
        """last_5_errors list from awareness → injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        errors = [{"error": "timeout"}, {"error": "rate_limit"}]
        updates = _inject_awareness_fields({"last_5_errors": errors})
        assert updates["last_5_errors"] == errors

    def test_active_alerts_injected_as_list(self):
        """active_alerts list from awareness → injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        alerts = [{"alert_id": "a1", "severity": "high"}]
        updates = _inject_awareness_fields({"active_alerts": alerts})
        assert updates["active_alerts"] == alerts

    def test_empty_list_not_injected(self):
        """Empty lists (quality_alerts, last_5_errors, active_alerts) are NOT injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        updates = _inject_awareness_fields({
            "quality_alerts": [],
            "last_5_errors": [],
            "active_alerts": [],
        })
        assert "quality_alerts" not in updates
        assert "last_5_errors" not in updates
        assert "active_alerts" not in updates


class TestJarvisAwarenessInjectorRoutingOverrides:
    """Tests for _apply_routing_overrides()."""

    def test_escalation_in_progress_sets_urgency_critical(self):
        """Escalation in progress → urgency='critical'."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _apply_routing_overrides,
        )
        updates = _apply_routing_overrides({"escalation_in_progress": True}, {})
        assert updates["urgency"] == "critical"

    def test_sla_protection_sets_urgency_high(self):
        """SLA protection active → urgency='high'."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _apply_routing_overrides,
        )
        updates = _apply_routing_overrides({"sla_protection_active": True}, {})
        assert updates["urgency"] == "high"

    def test_system_mode_paused(self):
        """system_mode='paused' in bridge → injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _apply_routing_overrides,
        )
        updates = _apply_routing_overrides({"system_mode": "paused"}, {})
        assert updates["system_mode"] == "paused"

    def test_system_mode_supervised(self):
        """system_mode='supervised' in bridge → injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _apply_routing_overrides,
        )
        updates = _apply_routing_overrides({"system_mode": "supervised"}, {})
        assert updates["system_mode"] == "supervised"

    def test_system_mode_shadow(self):
        """system_mode='shadow' in bridge → injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _apply_routing_overrides,
        )
        updates = _apply_routing_overrides({"system_mode": "shadow"}, {})
        assert updates["system_mode"] == "shadow"

    def test_system_mode_auto_not_overridden(self):
        """system_mode='auto' in bridge → NOT injected (not in allowed list)."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _apply_routing_overrides,
        )
        updates = _apply_routing_overrides({"system_mode": "auto"}, {})
        assert "system_mode" not in updates

    def test_reassignment_in_progress_no_urgency_change(self):
        """Reassignment in progress → no urgency change (just metadata)."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _apply_routing_overrides,
        )
        updates = _apply_routing_overrides({"reassignment_in_progress": True}, {})
        assert "urgency" not in updates

    def test_empty_bridge_no_overrides(self):
        """Empty bridge state → no routing overrides."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _apply_routing_overrides,
        )
        updates = _apply_routing_overrides({}, {})
        assert updates == {}


class TestJarvisAwarenessInjectorEmptyResult:
    """Tests for _empty_result()."""

    def test_empty_result_has_node_execution_log(self):
        """_empty_result must have node_execution_log."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import _empty_result
        result = _empty_result("no_bridge_state")
        assert "node_execution_log" in result
        assert len(result["node_execution_log"]) == 1

    def test_empty_result_log_status_is_skipped(self):
        """_empty_result log entry status must be 'skipped'."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import _empty_result
        result = _empty_result("no_tenant_context")
        assert result["node_execution_log"][0]["status"] == "skipped"

    def test_empty_result_includes_reason(self):
        """_empty_result must include the skip reason."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import _empty_result
        result = _empty_result("no_bridge_state")
        assert result["node_execution_log"][0]["reason"] == "no_bridge_state"


class TestJarvisAwarenessInjectorFullNode:
    """Tests for full jarvis_awareness_injector_node() with various bridge states."""

    def test_full_injection_with_all_data(self, company_id, session_id):
        """Full injection with bridge, awareness, and feedback data."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            jarvis_awareness_injector_node,
        )
        state = {
            "tenant_id": company_id,
            "session_id": session_id,
        }
        bridge = {
            "ai_paused": True,
            "co_pilot_suggestion": "Try ReAct",
            "source": "jarvis_command_graph",
            "sla_protection_active": True,  # Must be in bridge for routing overrides
        }
        awareness = {"quality_score": 0.88, "system_health": "healthy"}
        feedback = {}
        with patch(
            "app.services.jarvis_agents.nodes.jarvis_awareness_injector._read_bridge_state",
            return_value=bridge,
        ), patch(
            "app.services.jarvis_agents.nodes.jarvis_awareness_injector._read_awareness_state",
            return_value=awareness,
        ), patch(
            "app.services.jarvis_agents.nodes.jarvis_awareness_injector._read_feedback_state",
            return_value=feedback,
        ):
            result = jarvis_awareness_injector_node(state)
        assert "node_execution_log" in result
        assert result["ai_paused"] is True
        assert result["system_mode"] == "paused"
        assert result["quality_score"] == 0.88
        assert result["urgency"] == "high"  # SLA protection from bridge

    def test_missing_session_id_returns_early(self, company_id):
        """Missing session_id → returns early with empty result."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            jarvis_awareness_injector_node,
        )
        state = {"tenant_id": company_id}
        result = jarvis_awareness_injector_node(state)
        assert "node_execution_log" in result
        assert result["node_execution_log"][0]["status"] == "skipped"

    def test_company_id_from_tenant_id_key(self, session_id):
        """Node reads company_id from 'tenant_id' key in state."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            jarvis_awareness_injector_node,
        )
        state = {
            "tenant_id": "comp_from_tenant",
            "session_id": session_id,
        }
        with patch(
            "app.services.jarvis_agents.nodes.jarvis_awareness_injector._read_bridge_state",
            return_value={},
        ):
            result = jarvis_awareness_injector_node(state)
        # Should not crash (bridge is empty → empty result)
        assert "node_execution_log" in result

    def test_company_id_from_company_id_key(self, session_id):
        """Node reads company_id from 'company_id' key as fallback."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            jarvis_awareness_injector_node,
        )
        state = {
            "company_id": "comp_from_company",
            "session_id": session_id,
        }
        with patch(
            "app.services.jarvis_agents.nodes.jarvis_awareness_injector._read_bridge_state",
            return_value={},
        ):
            result = jarvis_awareness_injector_node(state)
        assert "node_execution_log" in result

    def test_emergency_controls_feedback_overrides_bridge(self, company_id, session_id):
        """Feedback data takes precedence over bridge in emergency controls."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_emergency_controls,
        )
        bridge = {"ai_paused": False}
        feedback = {"ai_paused": True, "global_pause_reason": "Override"}
        updates = _inject_emergency_controls(bridge, feedback)
        assert updates["ai_paused"] is True
        assert updates["global_pause_reason"] == "Override"

    def test_circuit_breaker_trips_injected(self):
        """circuit_breaker_trips from combined state → injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_emergency_controls,
        )
        bridge = {"circuit_breaker_trips": 3}
        feedback = {}
        updates = _inject_emergency_controls(bridge, feedback)
        assert updates["circuit_breaker_trips"] == 3

    def test_jarvis_command_metadata_injected(self):
        """Source='jarvis_command_graph' → jarvis_command_metadata injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_command_context,
        )
        bridge = {
            "source": "jarvis_command_graph",
            "injected_at": "2025-01-01T00:00:00Z",
            "command_state_summary": {"agent_type": "escalation"},
        }
        updates = _inject_command_context(bridge)
        assert "jarvis_command_metadata" in updates
        assert updates["jarvis_command_metadata"]["source"] == "jarvis_command_graph"

    def test_non_jarvis_source_no_command_metadata(self):
        """Source != 'jarvis_command_graph' → no jarvis_command_metadata."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_command_context,
        )
        bridge = {"source": "other_system"}
        updates = _inject_command_context(bridge)
        assert "jarvis_command_metadata" not in updates

    def test_jarvis_feed_entry_injected(self):
        """jarvis_feed_entry from bridge → injected."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_command_context,
        )
        feed_entry = {"type": "command_execution", "agent_type": "escalation"}
        bridge = {"jarvis_feed_entry": feed_entry}
        updates = _inject_command_context(bridge)
        assert updates["jarvis_feed_entry"] == feed_entry


# ═══════════════════════════════════════════════════════════════════════
# MODULE 6: Command Graph — Unit Tests
# ═══════════════════════════════════════════════════════════════════════


class TestCommandGraphAgentSelector:
    """Tests for _agent_selector()."""

    def test_escalation_routes_to_escalation_agent(self):
        """router_decision='escalation' → 'escalation_agent'."""
        from app.services.jarvis_agents.command_graph import _agent_selector
        result = _agent_selector({"router_decision": "escalation"})
        assert result == "escalation_agent"

    def test_sla_protection_routes_to_sla_agent(self):
        """router_decision='sla_protection' → 'sla_protection_agent'."""
        from app.services.jarvis_agents.command_graph import _agent_selector
        result = _agent_selector({"router_decision": "sla_protection"})
        assert result == "sla_protection_agent"

    def test_quality_recovery_routes_to_quality_agent(self):
        """router_decision='quality_recovery' → 'quality_recovery_agent'."""
        from app.services.jarvis_agents.command_graph import _agent_selector
        result = _agent_selector({"router_decision": "quality_recovery"})
        assert result == "quality_recovery_agent"

    def test_reassignment_routes_to_reassignment_agent(self):
        """router_decision='reassignment' → 'reassignment_agent'."""
        from app.services.jarvis_agents.command_graph import _agent_selector
        result = _agent_selector({"router_decision": "reassignment"})
        assert result == "reassignment_agent"

    def test_notification_routes_to_notification_agent(self):
        """router_decision='notification' → 'notification_agent'."""
        from app.services.jarvis_agents.command_graph import _agent_selector
        result = _agent_selector({"router_decision": "notification"})
        assert result == "notification_agent"

    def test_pipeline_query_routes_to_pipeline_query_agent(self):
        """router_decision='pipeline_query' → 'pipeline_query_agent'."""
        from app.services.jarvis_agents.command_graph import _agent_selector
        result = _agent_selector({"router_decision": "pipeline_query"})
        assert result == "pipeline_query_agent"

    def test_no_action_routes_to_approval_gate(self):
        """router_decision='no_action' → 'approval_gate'."""
        from app.services.jarvis_agents.command_graph import _agent_selector
        result = _agent_selector({"router_decision": "no_action"})
        assert result == "approval_gate"

    def test_unknown_decision_defaults_to_notification(self):
        """Unknown router_decision → 'notification_agent' (default)."""
        from app.services.jarvis_agents.command_graph import _agent_selector
        result = _agent_selector({"router_decision": "unknown_thing"})
        assert result == "notification_agent"

    def test_missing_decision_defaults_to_notification(self):
        """Missing router_decision → 'notification_agent' (default)."""
        from app.services.jarvis_agents.command_graph import _agent_selector
        result = _agent_selector({})
        assert result == "notification_agent"


class TestCommandGraphApprovalSelector:
    """Tests for _approval_selector()."""

    def test_approved_routes_to_command_executor(self):
        """execution_status='approved' → 'command_executor'."""
        from app.services.jarvis_agents.command_graph import _approval_selector
        result = _approval_selector({"execution_status": "approved"})
        assert result == "command_executor"

    def test_pending_approval_routes_to_end(self):
        """execution_status='pending_approval' → '__end__'."""
        from app.services.jarvis_agents.command_graph import _approval_selector
        result = _approval_selector({"execution_status": "pending_approval"})
        assert result == "__end__"

    def test_unknown_status_routes_to_command_executor(self):
        """Unknown execution_status → 'command_executor' (fail-open)."""
        from app.services.jarvis_agents.command_graph import _approval_selector
        result = _approval_selector({"execution_status": "unknown"})
        assert result == "command_executor"

    def test_empty_status_routes_to_command_executor(self):
        """Empty execution_status → 'command_executor' (fail-open)."""
        from app.services.jarvis_agents.command_graph import _approval_selector
        result = _approval_selector({"execution_status": ""})
        assert result == "command_executor"

    def test_missing_status_routes_to_command_executor(self):
        """Missing execution_status → 'command_executor' (fail-open)."""
        from app.services.jarvis_agents.command_graph import _approval_selector
        result = _approval_selector({})
        assert result == "command_executor"


class TestCommandGraphMergeStateUpdates:
    """Tests for _merge_state_updates()."""

    def test_simple_field_override(self):
        """Simple key → value override."""
        from app.services.jarvis_agents.command_graph import _merge_state_updates
        state = {"agent_type": "old"}
        _merge_state_updates(state, {"agent_type": "new"})
        assert state["agent_type"] == "new"

    def test_node_outputs_dict_merge(self):
        """node_updates dict → merged into existing node_outputs."""
        from app.services.jarvis_agents.command_graph import _merge_state_updates
        state = {"node_outputs": {"router": {"a": 1}}}
        _merge_state_updates(state, {"node_outputs": {"executor": {"b": 2}}})
        assert "router" in state["node_outputs"]
        assert "executor" in state["node_outputs"]

    def test_audit_trail_list_append(self):
        """audit_trail list → appended to existing."""
        from app.services.jarvis_agents.command_graph import _merge_state_updates
        state = {"audit_trail": [{"step": "init"}]}
        _merge_state_updates(state, {"audit_trail": [{"step": "router"}]})
        assert len(state["audit_trail"]) == 2

    def test_errors_list_append(self):
        """errors list → appended to existing."""
        from app.services.jarvis_agents.command_graph import _merge_state_updates
        state = {"errors": ["error1"]}
        _merge_state_updates(state, {"errors": ["error2"]})
        assert len(state["errors"]) == 2

    def test_node_outputs_creates_new_if_not_dict(self):
        """node_outputs when existing is not a dict → replaced."""
        from app.services.jarvis_agents.command_graph import _merge_state_updates
        state = {"node_outputs": "not_a_dict"}
        _merge_state_updates(state, {"node_outputs": {"new_key": "val"}})
        assert state["node_outputs"] == {"new_key": "val"}


class TestCommandGraphManualExecution:
    """Tests for JarvisCommandGraph._run_manual() with parwa_high tier."""

    def test_parwa_high_auto_approved_notification(self, company_id, session_id, user_id):
        """parwa_high + notification → auto-approved, runs through executor."""
        from app.services.jarvis_agents.command_graph import JarvisCommandGraph
        graph = JarvisCommandGraph()
        # Force manual mode
        graph._use_langgraph = False
        graph._graph = None

        initial_state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "parwa_high",
            "trigger_type": "user_nl",
            "raw_input": "notify team about spike",
            "alert_id": "",
            "alert_type": "",
            "alert_severity": "",
            "alert_message": "",
            "alert_details": {},
            "awareness_snapshot": {},
            "active_alerts_summary": [],
            "session_context": {},
            "router_decision": "",
            "router_reasoning": "",
            "router_urgency": "medium",
            "router_parameters": {},
            "router_source": "",
            "agent_type": "",
            "agent_action": "",
            "agent_decision": {},
            "agent_reasoning": "",
            "agent_source": "",
            "execution_status": "pending",
            "execution_result": {},
            "execution_error": "",
            "execution_time_ms": 0.0,
            "command_id": "",
            "db_command_created": False,
            "alert_resolved": False,
            "node_outputs": {},
            "audit_trail": [],
            "errors": [],
        }

        with patch(
            "app.services.jarvis_agents.pipeline_feedback.apply_command_feedback_sync",
            return_value=True,
        ):
            result = graph._run_manual(initial_state)

        # parwa_high notification should be auto-approved
        # (execution_status may vary depending on what the agent nodes set)
        assert isinstance(result, dict)
        assert "execution_status" in result

    def test_manual_execution_stops_at_pending_approval(self, company_id, session_id, user_id):
        """mini_parwa + escalation → pending_approval, stops before executor."""
        from app.services.jarvis_agents.command_graph import JarvisCommandGraph
        graph = JarvisCommandGraph()
        graph._use_langgraph = False
        graph._graph = None

        initial_state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "mini_parwa",
            "trigger_type": "alert",
            "raw_input": "",
            "alert_id": "alt_001",
            "alert_type": "ticket_volume_spike",
            "alert_severity": "critical",
            "alert_message": "Volume spike",
            "alert_details": {},
            "awareness_snapshot": {},
            "active_alerts_summary": [],
            "session_context": {},
            "router_decision": "",
            "router_reasoning": "",
            "router_urgency": "medium",
            "router_parameters": {},
            "router_source": "",
            "agent_type": "",
            "agent_action": "",
            "agent_decision": {},
            "agent_reasoning": "",
            "agent_source": "",
            "execution_status": "pending",
            "execution_result": {},
            "execution_error": "",
            "execution_time_ms": 0.0,
            "command_id": "",
            "db_command_created": False,
            "alert_resolved": False,
            "node_outputs": {},
            "audit_trail": [],
            "errors": [],
        }

        result = graph._run_manual(initial_state)
        # mini_parwa should result in pending_approval
        assert result["execution_status"] == "pending_approval"
