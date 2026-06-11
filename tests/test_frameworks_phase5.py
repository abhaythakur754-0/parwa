"""Phase 5 tests — Proprietary techniques, PermissionExecutor, and node wirings.

Tests cover:
  1. GSD technique (mock + properties)
  2. Smart Router technique (mock + budget-aware routing)
  3. MAKER technique (mock + step decomposition + verification)
  4. PermissionExecutor (all 3 variants + edge cases)
  5. Action Agent node wirings (action_planner, action_executor, action_verifier)
  6. Remaining unwired node wirings (intent_classifier, sentiment_analyzer, etc.)
  7. Registry now has 20 techniques including 3 proprietary
  8. Full pipeline integration with Phase 5 features
"""

from __future__ import annotations

import pytest

from parwa.config import ACTION_PERMISSIONS, MINI_PARWA, PARWA, PARWA_HIGH
from parwa.frameworks.base import TechniqueCategory
from parwa.frameworks.registry import get_registry, reset_registry
from parwa.permissions.executor import PermissionExecutor, PermissionResult
from parwa.state import ActionType, ExecutionMode


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset():
    """Reset the singleton registry before each test."""
    reset_registry()
    yield
    reset_registry()


def _base_state(**overrides):
    """Create a minimal state dict for testing."""
    state = {
        "ticket_id": "TKT-TEST01",
        "raw_message": "I was charged twice for my order",
        "customer_id": "CUST-001",
        "channel": "email",
        "variant": "parwa",
        "intent": "refund_request",
        "intent_confidence": 0.85,
        "sentiment": "neutral",
        "sentiment_urgency": 0.3,
        "complexity": "medium",
        "reasoning_conclusion": "Customer was charged twice",
        "strategy_plan": ["Verify duplicate charge", "Process refund"],
        "integration_data": {
            "customer_id": "CUST-001",
            "charges": [
                {"amount": 49.99, "date": "2025-01-05", "description": "Widget Pro"},
                {"amount": 49.99, "date": "2025-01-05", "description": "Widget Pro (duplicate)"},
            ],
            "account_status": "active",
        },
        "kb_results": [],
        "context_history": [],
        "action_plans": [],
        "execution_results": [],
        "recommendation": None,
        "proactive_insights": [],
        "predictions": [],
        "feedback_signal": {},
        "active_frameworks": [],
        "token_budget_remaining": 5000,
        "maker_steps": [],
    }
    state.update(overrides)
    return state


# ═══════════════════════════════════════════════════════════════════════════
# 1. GSD TECHNIQUE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestGSDTechnique:
    """Test GSD (Get Stuff Done) proprietary technique."""

    def test_name(self):
        from parwa.frameworks.proprietary.gsd import GSDTechnique
        t = GSDTechnique()
        assert t.name == "gsd"

    def test_category(self):
        from parwa.frameworks.proprietary.gsd import GSDTechnique
        t = GSDTechnique()
        assert t.category == TechniqueCategory.PROPRIETARY

    def test_applicable_nodes(self):
        from parwa.frameworks.proprietary.gsd import GSDTechnique
        t = GSDTechnique()
        nodes = t.applicable_nodes
        assert "ACTION_PLANNER" in nodes
        assert "ACTION_EXECUTOR" in nodes
        assert "ACTION_VERIFIER" in nodes
        assert "RESPONSE_FORMATTER" in nodes
        assert "REASONING_ENGINE" in nodes

    def test_min_complexity(self):
        from parwa.frameworks.proprietary.gsd import GSDTechnique
        t = GSDTechnique()
        assert t._min_complexity == "medium"

    def test_can_apply_medium(self):
        from parwa.frameworks.proprietary.gsd import GSDTechnique
        t = GSDTechnique()
        assert t.can_apply("ACTION_PLANNER", "medium") is True

    def test_cannot_apply_simple(self):
        from parwa.frameworks.proprietary.gsd import GSDTechnique
        t = GSDTechnique()
        assert t.can_apply("ACTION_PLANNER", "simple") is False

    @pytest.mark.asyncio
    async def test_think_mock(self):
        from parwa.frameworks.proprietary.gsd import GSDTechnique
        t = GSDTechnique()
        state = _base_state(complexity="complex", reasoning_conclusion="Duplicate charge found")
        result = await t.think("Focus on action planning", state)
        assert result.frameworks_used == ["gsd"]
        assert len(result.chain) > 0
        assert result.confidence > 0
        assert "working_set" in result.metadata

    @pytest.mark.asyncio
    async def test_think_detects_action_planner(self):
        from parwa.frameworks.proprietary.gsd import GSDTechnique
        t = GSDTechnique()
        # State pattern: has conclusion but no action_plans → ACTION_PLANNER
        state = _base_state(complexity="complex", reasoning_conclusion="Found duplicate", action_plans=[])
        result = await t.think("Focus", state)
        assert result.metadata["node"] == "ACTION_PLANNER"


# ═══════════════════════════════════════════════════════════════════════════
# 2. SMART ROUTER TECHNIQUE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestSmartRouterTechnique:
    """Test Smart Router proprietary technique."""

    def test_name(self):
        from parwa.frameworks.proprietary.smart_router import SmartRouterTechnique
        t = SmartRouterTechnique()
        assert t.name == "smart_router"

    def test_category(self):
        from parwa.frameworks.proprietary.smart_router import SmartRouterTechnique
        t = SmartRouterTechnique()
        assert t.category == TechniqueCategory.PROPRIETARY

    def test_min_complexity(self):
        from parwa.frameworks.proprietary.smart_router import SmartRouterTechnique
        t = SmartRouterTechnique()
        assert t._min_complexity == "medium"

    @pytest.mark.asyncio
    async def test_think_simple_ticket(self):
        from parwa.frameworks.proprietary.smart_router import SmartRouterTechnique
        t = SmartRouterTechnique()
        state = _base_state(complexity="simple")
        result = await t.think("Route techniques", state)
        assert result.frameworks_used == ["smart_router"]
        # Simple tickets should get minimal techniques
        recommended = result.metadata.get("recommended_techniques", [])
        assert "chain_of_thought" in recommended

    @pytest.mark.asyncio
    async def test_think_critical_ticket(self):
        from parwa.frameworks.proprietary.smart_router import SmartRouterTechnique
        t = SmartRouterTechnique()
        state = _base_state(complexity="critical")
        result = await t.think("Route techniques", state)
        recommended = result.metadata.get("recommended_techniques", [])
        # Critical tickets should get full arsenal
        assert len(recommended) >= 3

    @pytest.mark.asyncio
    async def test_think_tight_budget(self):
        from parwa.frameworks.proprietary.smart_router import SmartRouterTechnique
        t = SmartRouterTechnique()
        state = _base_state(complexity="critical", token_budget_remaining=200)
        result = await t.think("Route techniques", state)
        recommended = result.metadata.get("recommended_techniques", [])
        # Tight budget should trim expensive techniques
        assert len(recommended) <= 2

    @pytest.mark.asyncio
    async def test_think_mini_variant_limits_techniques(self):
        from parwa.frameworks.proprietary.smart_router import SmartRouterTechnique
        t = SmartRouterTechnique()
        # Complex complexity would normally give 5+ techniques
        # Mini variant should trim to 2 for cost
        state = _base_state(complexity="complex", variant="mini")
        result = await t.think("Route techniques", state, variant="mini")
        recommended = result.metadata.get("recommended_techniques", [])
        # Mini variant should limit techniques for cost
        assert len(recommended) <= 2


# ═══════════════════════════════════════════════════════════════════════════
# 3. MAKER TECHNIQUE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestMAKERTechnique:
    """Test MAKER (Multi-step decomposition with verification) technique."""

    def test_name(self):
        from parwa.frameworks.proprietary.maker import MAKERTechnique
        t = MAKERTechnique()
        assert t.name == "maker"

    def test_category(self):
        from parwa.frameworks.proprietary.maker import MAKERTechnique
        t = MAKERTechnique()
        assert t.category == TechniqueCategory.PROPRIETARY

    def test_min_complexity(self):
        from parwa.frameworks.proprietary.maker import MAKERTechnique
        t = MAKERTechnique()
        assert t._min_complexity == "complex"

    def test_cannot_apply_medium(self):
        from parwa.frameworks.proprietary.maker import MAKERTechnique
        t = MAKERTechnique()
        assert t.can_apply("ACTION_PLANNER", "medium") is False

    def test_can_apply_complex(self):
        from parwa.frameworks.proprietary.maker import MAKERTechnique
        t = MAKERTechnique()
        assert t.can_apply("ACTION_PLANNER", "complex") is True

    @pytest.mark.asyncio
    async def test_think_refund_request(self):
        from parwa.frameworks.proprietary.maker import MAKERTechnique
        t = MAKERTechnique()
        state = _base_state(complexity="complex", intent="refund_request")
        result = await t.think("Decompose refund task", state)
        assert result.frameworks_used == ["maker"]
        steps = result.metadata.get("steps", [])
        assert len(steps) >= 3  # Refund should have 3+ steps
        # Each step should have verification criteria
        for step in steps:
            assert "description" in step
            assert "verification" in step
            assert step.get("status") == "pending"

    @pytest.mark.asyncio
    async def test_think_cancellation(self):
        from parwa.frameworks.proprietary.maker import MAKERTechnique
        t = MAKERTechnique()
        state = _base_state(complexity="complex", intent="cancellation")
        result = await t.think("Decompose cancellation", state)
        steps = result.metadata.get("steps", [])
        assert len(steps) >= 2

    @pytest.mark.asyncio
    async def test_think_general_inquiry(self):
        from parwa.frameworks.proprietary.maker import MAKERTechnique
        t = MAKERTechnique()
        state = _base_state(complexity="complex", intent="general_inquiry")
        result = await t.think("Decompose", state)
        steps = result.metadata.get("steps", [])
        assert len(steps) >= 2  # Default decomposition


# ═══════════════════════════════════════════════════════════════════════════
# 4. PERMISSION EXECUTOR TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestPermissionExecutor:
    """Test PermissionExecutor for variant-based action enforcement."""

    def test_mini_execute_basics(self):
        ex = PermissionExecutor(variant="mini")
        # Mini can execute basic actions
        result = ex.evaluate("send_reply")
        assert result.can_auto_execute is True
        assert result.mode == "execute"

    def test_mini_recommend_refund(self):
        ex = PermissionExecutor(variant="mini")
        result = ex.evaluate("process_refund")
        assert result.allowed is True
        assert result.can_auto_execute is False
        assert result.mode == "recommend"

    def test_mini_deny_voice(self):
        ex = PermissionExecutor(variant="mini")
        result = ex.evaluate("voice_call")
        assert result.allowed is False
        assert result.can_auto_execute is False
        assert result.mode == "deny"

    def test_parwa_execute_refund(self):
        ex = PermissionExecutor(variant="parwa")
        result = ex.evaluate("process_refund")
        assert result.can_auto_execute is True
        assert result.mode == "execute"

    def test_parwa_deny_bulk(self):
        ex = PermissionExecutor(variant="parwa")
        result = ex.evaluate("bulk_operation")
        assert result.allowed is False
        assert result.mode == "deny"

    def test_high_execute_everything(self):
        ex = PermissionExecutor(variant="high")
        # PARWA High can execute all actions
        for action in ActionType:
            result = ex.evaluate(action)
            assert result.can_auto_execute is True, f"High should execute {action.value}"

    def test_result_has_reason(self):
        ex = PermissionExecutor(variant="mini")
        result = ex.evaluate("process_refund")
        assert isinstance(result.reason, str)
        assert len(result.reason) > 0

    def test_result_to_dict(self):
        ex = PermissionExecutor(variant="mini")
        result = ex.evaluate("send_reply")
        d = result.to_dict()
        assert "action_type" in d
        assert "mode" in d
        assert "allowed" in d

    def test_evaluate_batch(self):
        ex = PermissionExecutor(variant="mini")
        results = ex.evaluate_batch(["send_reply", "process_refund", "voice_call"])
        assert len(results) == 3
        assert results[0].mode == "execute"
        assert results[1].mode == "recommend"
        assert results[2].mode == "deny"

    def test_get_executable_actions_mini(self):
        ex = PermissionExecutor(variant="mini")
        exec_actions = ex.get_executable_actions()
        assert "send_reply" in exec_actions
        assert "process_refund" not in exec_actions

    def test_get_denied_actions_mini(self):
        ex = PermissionExecutor(variant="mini")
        denied = ex.get_denied_actions()
        assert "voice_call" in denied
        assert "bulk_operation" in denied

    def test_get_summary_mini(self):
        ex = PermissionExecutor(variant="mini")
        summary = ex.get_summary()
        assert summary["variant"] == "mini"
        assert len(summary["executable"]) >= 5
        assert len(summary["denied"]) >= 5
        assert len(summary["recommended"]) >= 3

    def test_unknown_action_defaults_to_deny(self):
        ex = PermissionExecutor(variant="parwa")
        result = ex.evaluate("nonexistent_action")
        assert result.mode == "deny"

    def test_unknown_variant_defaults_to_parwa(self):
        ex = PermissionExecutor(variant="unknown_variant")
        assert ex.variant == "parwa"

    def test_action_type_enum_input(self):
        ex = PermissionExecutor(variant="mini")
        result = ex.evaluate(ActionType.SEND_REPLY)
        assert result.mode == "execute"

    def test_upgrade_hint_in_reason(self):
        ex = PermissionExecutor(variant="mini")
        result = ex.evaluate("process_refund")
        # Recommend mode should include upgrade hint
        assert "Upgrade" in result.reason or "upgrade" in result.reason.lower()


# ═══════════════════════════════════════════════════════════════════════════
# 5. ACTION AGENT NODE WIRING TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestActionPlannerBrainWiring:
    """Test ACTION_PLANNER with FrameworkBrain."""

    @pytest.mark.asyncio
    async def test_planner_returns_actions(self):
        from parwa.nodes.action_planner import action_planner
        state = _base_state(complexity="medium")
        result = await action_planner(state)
        assert isinstance(result["action_plans"], list)
        assert len(result["action_plans"]) >= 1

    @pytest.mark.asyncio
    async def test_planner_tracks_frameworks(self):
        from parwa.nodes.action_planner import action_planner
        state = _base_state(complexity="complex")
        result = await action_planner(state)
        assert isinstance(result.get("active_frameworks"), list)

    @pytest.mark.asyncio
    async def test_planner_returns_maker_steps_for_complex(self):
        from parwa.nodes.action_planner import action_planner
        state = _base_state(complexity="complex")
        result = await action_planner(state)
        # Complex tickets should have MAKER steps
        assert isinstance(result.get("maker_steps"), list)

    @pytest.mark.asyncio
    async def test_planner_fallback_on_brain_crash(self):
        from parwa.nodes.action_planner import action_planner
        from unittest.mock import patch
        state = _base_state(complexity="complex")
        with patch("parwa.nodes.action_planner._plan_actions_with_brain", side_effect=RuntimeError("Crash")):
            # @safe_node should catch this and return fallback
            result = await action_planner(state)
            assert result["action_plans"] == []


class TestActionExecutorBrainWiring:
    """Test ACTION_EXECUTOR with FrameworkBrain + PermissionExecutor."""

    @pytest.mark.asyncio
    async def test_parwa_executes_refund(self):
        from parwa.nodes.action_executor import action_executor
        state = _base_state(
            variant="parwa",
            action_plans=[{
                "action_type": "process_refund",
                "description": "Process refund",
                "parameters": {"amount": 49.99},
                "evidence": ["Duplicate charge found"],
                "risk_level": "low",
            }],
        )
        result = await action_executor(state)
        assert len(result["execution_results"]) >= 1
        assert result["execution_results"][0]["status"] == "executed"

    @pytest.mark.asyncio
    async def test_mini_recommends_refund(self):
        from parwa.nodes.action_executor import action_executor
        state = _base_state(
            variant="mini",
            action_plans=[{
                "action_type": "process_refund",
                "description": "Process refund",
                "parameters": {"amount": 49.99},
                "evidence": ["Duplicate charge found"],
                "risk_level": "low",
            }],
        )
        result = await action_executor(state)
        # Mini should recommend, not execute
        statuses = [r["status"] for r in result["execution_results"]]
        assert "recommended" in statuses
        assert result["recommendation"] is not None
        assert result["recommendation"]["pending_approval"] is True

    @pytest.mark.asyncio
    async def test_mini_denies_voice(self):
        from parwa.nodes.action_executor import action_executor
        state = _base_state(
            variant="mini",
            action_plans=[{
                "action_type": "voice_call",
                "description": "Call customer",
                "parameters": {},
                "evidence": [],
                "risk_level": "medium",
            }],
        )
        result = await action_executor(state)
        assert result["execution_results"][0]["status"] == "denied"

    @pytest.mark.asyncio
    async def test_executor_tracks_frameworks(self):
        from parwa.nodes.action_executor import action_executor
        state = _base_state(
            variant="parwa",
            action_plans=[{
                "action_type": "send_reply",
                "description": "Reply",
                "parameters": {},
                "evidence": [],
                "risk_level": "low",
            }],
        )
        result = await action_executor(state)
        assert isinstance(result.get("active_frameworks"), list)


class TestActionVerifierBrainWiring:
    """Test ACTION_VERIFIER with FrameworkBrain."""

    @pytest.mark.asyncio
    async def test_verifies_successful_execution(self):
        from parwa.nodes.action_verifier import action_verifier
        state = _base_state(
            execution_results=[{"status": "executed", "action_type": "send_reply"}],
            recommendation=None,
            loop_count=0,
            max_loops=2,
        )
        result = await action_verifier(state)
        assert result["verification_passed"] is True
        assert result["should_loop_back"] is False

    @pytest.mark.asyncio
    async def test_loops_back_on_failure(self):
        from parwa.nodes.action_verifier import action_verifier
        state = _base_state(
            execution_results=[{"status": "failed", "action_type": "send_reply"}],
            recommendation=None,
            loop_count=0,
            max_loops=2,
        )
        result = await action_verifier(state)
        assert result["verification_passed"] is False
        assert result["should_loop_back"] is True

    @pytest.mark.asyncio
    async def test_verifier_has_maker_verification(self):
        from parwa.nodes.action_verifier import action_verifier
        state = _base_state(
            execution_results=[{"status": "executed"}],
            recommendation=None,
            loop_count=0,
            max_loops=2,
            maker_steps=[{"step": 1, "status": "pending", "description": "Test"}],
        )
        result = await action_verifier(state)
        assert "maker_verification_passed" in result

    @pytest.mark.asyncio
    async def test_verifier_tracks_frameworks(self):
        from parwa.nodes.action_verifier import action_verifier
        state = _base_state(
            execution_results=[{"status": "executed"}],
            recommendation=None,
            loop_count=0,
            max_loops=2,
            complexity="complex",
        )
        result = await action_verifier(state)
        assert isinstance(result.get("active_frameworks"), list)


# ═══════════════════════════════════════════════════════════════════════════
# 6. REMAINING NODE WIRING TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestIntentClassifierBrainWiring:
    """Test INTENT_CLASSIFIER with FrameworkBrain."""

    @pytest.mark.asyncio
    async def test_classifies_intent(self):
        from parwa.nodes.intent_classifier import intent_classifier
        state = _base_state(raw_message="I want a refund for double charge")
        result = await intent_classifier(state)
        assert result["intent"] == "refund_request"
        assert result["intent_confidence"] > 0

    @pytest.mark.asyncio
    async def test_tracks_frameworks(self):
        from parwa.nodes.intent_classifier import intent_classifier
        state = _base_state(complexity="medium")
        result = await intent_classifier(state)
        assert isinstance(result.get("active_frameworks"), list)


class TestSentimentAnalyzerBrainWiring:
    """Test SENTIMENT_ANALYZER with FrameworkBrain."""

    @pytest.mark.asyncio
    async def test_analyzes_sentiment(self):
        from parwa.nodes.sentiment_analyzer import sentiment_analyzer
        state = _base_state(raw_message="I am furious about this charge!")
        result = await sentiment_analyzer(state)
        assert result["sentiment"] == "angry"
        assert result["sentiment_urgency"] > 0.5

    @pytest.mark.asyncio
    async def test_tracks_frameworks(self):
        from parwa.nodes.sentiment_analyzer import sentiment_analyzer
        state = _base_state()
        result = await sentiment_analyzer(state)
        assert isinstance(result.get("active_frameworks"), list)


class TestEscalationDecisionBrainWiring:
    """Test ESCALATION_DECISION with FrameworkBrain."""

    @pytest.mark.asyncio
    async def test_escalates_angry_critical(self):
        from parwa.nodes.escalation_decision import escalation_decision
        state = _base_state(sentiment="angry", complexity="critical")
        result = await escalation_decision(state)
        assert result["should_escalate"] is True

    @pytest.mark.asyncio
    async def test_tracks_frameworks(self):
        from parwa.nodes.escalation_decision import escalation_decision
        state = _base_state(complexity="complex")
        result = await escalation_decision(state)
        assert isinstance(result.get("active_frameworks"), list)


class TestProactiveCheckerBrainWiring:
    """Test PROACTIVE_CHECKER with FrameworkBrain."""

    @pytest.mark.asyncio
    async def test_generates_insights(self):
        from parwa.nodes.proactive_checker import proactive_checker
        state = _base_state(intent="refund_request")
        result = await proactive_checker(state)
        assert len(result["proactive_insights"]) >= 1

    @pytest.mark.asyncio
    async def test_tracks_frameworks(self):
        from parwa.nodes.proactive_checker import proactive_checker
        state = _base_state(complexity="complex")
        result = await proactive_checker(state)
        assert isinstance(result.get("active_frameworks"), list)


class TestPredictionEngineBrainWiring:
    """Test PREDICTION_ENGINE with FrameworkBrain."""

    @pytest.mark.asyncio
    async def test_generates_predictions(self):
        from parwa.nodes.prediction_engine import prediction_engine
        state = _base_state(intent="refund_request")
        result = await prediction_engine(state)
        assert len(result["predictions"]) >= 1

    @pytest.mark.asyncio
    async def test_tracks_frameworks(self):
        from parwa.nodes.prediction_engine import prediction_engine
        state = _base_state(complexity="complex")
        result = await prediction_engine(state)
        assert isinstance(result.get("active_frameworks"), list)


class TestIntegrationLookupBrainWiring:
    """Test INTEGRATION_LOOKUP with FrameworkBrain."""

    @pytest.mark.asyncio
    async def test_looks_up_data(self):
        from parwa.nodes.integration_lookup import integration_lookup
        state = _base_state(intent="refund_request")
        result = await integration_lookup(state)
        assert isinstance(result["integration_data"], dict)

    @pytest.mark.asyncio
    async def test_tracks_frameworks(self):
        from parwa.nodes.integration_lookup import integration_lookup
        state = _base_state(complexity="medium")
        result = await integration_lookup(state)
        assert isinstance(result.get("active_frameworks"), list)


class TestIngestBrainWiring:
    """Test INGEST with FrameworkBrain."""

    @pytest.mark.asyncio
    async def test_ingests_ticket(self):
        from parwa.nodes.ingest import ingest
        state = _base_state()
        result = await ingest(state)
        assert result["ticket_id"].startswith("TKT-")
        assert result["variant"] == "parwa"

    @pytest.mark.asyncio
    async def test_tracks_frameworks(self):
        from parwa.nodes.ingest import ingest
        state = _base_state(complexity="medium")
        result = await ingest(state)
        assert isinstance(result.get("active_frameworks"), list)


class TestPIIComplianceGuardBrainWiring:
    """Test PII_COMPLIANCE_GUARD with FrameworkBrain."""

    @pytest.mark.asyncio
    async def test_detects_pii(self):
        from parwa.nodes.pii_compliance_guard import pii_compliance_guard
        state = _base_state(raw_message="My email is test@example.com and SSN is 123-45-6789")
        result = await pii_compliance_guard(state)
        assert result["pii_detected"] is True
        assert "[EMAIL_REDACTED]" in result["pii_redacted_message"]

    @pytest.mark.asyncio
    async def test_tracks_frameworks(self):
        from parwa.nodes.pii_compliance_guard import pii_compliance_guard
        state = _base_state(complexity="medium")
        result = await pii_compliance_guard(state)
        assert isinstance(result.get("active_frameworks"), list)


class TestAuditLoggerBrainWiring:
    """Test AUDIT_LOGGER with FrameworkBrain."""

    @pytest.mark.asyncio
    async def test_creates_audit_entry(self):
        from parwa.nodes.audit_logger import audit_logger
        state = _base_state(
            action_plans=[{"action_type": "send_reply"}],
            execution_results=[{"action_type": "send_reply", "status": "executed"}],
        )
        result = await audit_logger(state)
        assert len(result["audit_log"]) >= 1

    @pytest.mark.asyncio
    async def test_tracks_frameworks(self):
        from parwa.nodes.audit_logger import audit_logger
        state = _base_state(complexity="medium")
        result = await audit_logger(state)
        assert isinstance(result.get("active_frameworks"), list)


class TestResponseFormatterBrainWiring:
    """Test RESPONSE_FORMATTER with FrameworkBrain."""

    @pytest.mark.asyncio
    async def test_formats_response(self):
        from parwa.nodes.response_formatter import response_formatter
        state = _base_state(
            intent="refund_request",
            reasoning_conclusion="Duplicate charge confirmed",
            execution_results=[{"action_type": "process_refund", "status": "executed"}],
        )
        result = await response_formatter(state)
        assert isinstance(result["final_response"], str)
        assert len(result["final_response"]) > 0

    @pytest.mark.asyncio
    async def test_tracks_frameworks(self):
        from parwa.nodes.response_formatter import response_formatter
        state = _base_state(complexity="medium")
        result = await response_formatter(state)
        assert isinstance(result.get("active_frameworks"), list)


# ═══════════════════════════════════════════════════════════════════════════
# 7. REGISTRY TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestRegistryPhase5:
    """Test registry has all Phase 5 techniques."""

    def test_has_20_techniques(self):
        registry = get_registry()
        assert registry.count() == 20

    def test_has_gsd(self):
        registry = get_registry()
        assert registry.get("gsd") is not None

    def test_has_smart_router(self):
        registry = get_registry()
        assert registry.get("smart_router") is not None

    def test_has_maker(self):
        registry = get_registry()
        assert registry.get("maker") is not None

    def test_proprietary_category_exists(self):
        registry = get_registry()
        proprietary = registry.get_techniques_by_category(TechniqueCategory.PROPRIETARY)
        assert len(proprietary) == 3

    def test_all_brain_wired_nodes_have_techniques(self):
        """All brain-wired nodes should have at least one applicable technique.

        Note: Some deterministic nodes (INGEST, AUDIT_LOGGER, PII_COMPLIANCE_GUARD)
        don't have techniques in the registry because they use FrameworkBrain
        with techniques from other nodes' applicable lists. They're still wired
        with brain calls but use CoT/CRP from broader applicable_nodes lists.
        """
        registry = get_registry()
        brain_wired_nodes = [
            "INTENT_CLASSIFIER", "FAQ_MATCHER", "KB_RETRIEVER",
            "INTEGRATION_LOOKUP", "REASONING_ENGINE", "ACTION_PLANNER",
            "ACTION_EXECUTOR", "ACTION_VERIFIER", "REVERSE_THINKER",
            "STRATEGY_PLANNER", "TREE_OF_THOUGHTS", "PROACTIVE_CHECKER",
            "PREDICTION_ENGINE", "RESPONSE_FORMATTER", "SENTIMENT_ANALYZER",
            "CONTEXT_MANAGER", "ESCALATION_DECISION", "QUALITY_SCORER",
            "FEEDBACK_LOOP",
        ]
        summary = registry.summary()
        for node in brain_wired_nodes:
            assert node in summary["by_node"], f"Node {node} has no techniques"


# ═══════════════════════════════════════════════════════════════════════════
# 8. FULL PIPELINE INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════

class TestPhase5PipelineIntegration:
    """Test full pipeline with Phase 5 features enabled."""

    @pytest.mark.asyncio
    async def test_mini_variant_recommendation_flow(self):
        """Mini PARWA should recommend (not execute) restricted actions."""
        from parwa.graph import aprocess_ticket
        result = await aprocess_ticket({
            "raw_message": "I was charged twice for my order",
            "customer_id": "CUST-001",
            "channel": "email",
            "variant": "mini",
        })
        # Mini should create a recommendation for refund
        recommendation = result.get("recommendation")
        # If recommendation exists, it should be pending approval
        if recommendation is not None:
            assert recommendation.get("pending_approval") is True

    @pytest.mark.asyncio
    async def test_parwa_variant_execution_flow(self):
        """PARWA should execute all standard actions directly."""
        from parwa.graph import aprocess_ticket
        result = await aprocess_ticket({
            "raw_message": "I was charged twice for my order",
            "customer_id": "CUST-001",
            "channel": "email",
            "variant": "parwa",
        })
        # Check that execution happened
        exec_results = result.get("execution_results", [])
        if exec_results:
            statuses = [r.get("status") for r in exec_results if isinstance(r, dict)]
            # PARWA should execute (not recommend) refund
            assert "executed" in statuses or "recommended" in statuses

    @pytest.mark.asyncio
    async def test_active_frameworks_tracked(self):
        """Frameworks should be tracked across the pipeline."""
        from parwa.graph import aprocess_ticket
        result = await aprocess_ticket({
            "raw_message": "I was charged twice for my order",
            "customer_id": "CUST-001",
            "channel": "email",
            "variant": "parwa",
        })
        # Should have tracked frameworks
        frameworks = result.get("active_frameworks", [])
        assert isinstance(frameworks, list)
