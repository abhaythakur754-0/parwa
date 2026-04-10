"""
HIGH severity gap tests for Week 9-10.

Covers:
1. Intent classification ambiguity (signal_extraction + classification_engine)
2. Technique tier bypass (technique_tier_access)
3. Edge case handler ordering (edge_case_handlers)
4. Cross-variant escalation billing (cross_variant_routing)
5. Human checkpoint / workflow timeout (langgraph_workflow)
6. GSD transition validation (gsd_engine)
7. Distributed lock contention (state_serialization)
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# ── Imports under test ─────────────────────────────────────────────

from app.core.signal_extraction import (
    SignalExtractor,
    SignalExtractionRequest,
    ExtractedSignals,
)
from app.core.classification_engine import (
    ClassificationEngine,
    KeywordClassifier,
    IntentType,
    IntentResult,
)
from app.core.technique_tier_access import (
    TechniqueTierAccessChecker,
    TierAccessDecision,
)
from app.core.technique_router import TechniqueID
from app.core.edge_case_handlers import (
    EdgeCaseRegistry,
    EdgeCaseAction,
    EdgeCaseSeverity,
    EdgeCaseHandler,
    EdgeCaseResult,
    EmptyQueryHandler,
    MaliciousHTMLHandler,
    BlockedUserHandler,
    SystemCommandsHandler,
    LegalTerminologyHandler,
    CodeBlocksHandler,
    CompetitorMentionHandler,
    VARIANT_HANDLER_WHITELIST,
    CHAIN_TIMEOUT_SECONDS,
)
from app.core.cross_variant_routing import (
    CrossVariantRouter,
    ChannelType,
    RoutingDecisionType,
    EscalationReason,
    CAPACITY_THRESHOLD_PCT,
    AI_OVERLOAD_FLAG,
    ESCALATION_CHAIN,
)
from app.core.langgraph_workflow import (
    LangGraphWorkflow,
    WorkflowConfig,
    WorkflowResult,
    WorkflowStepResult,
    VARIANT_PIPELINE_CONFIG,
)
from app.core.gsd_engine import (
    GSDEngine,
    GSDConfig,
    GSDVariant,
    InvalidTransitionError,
    EscalationCooldownError,
    FULL_TRANSITION_TABLE,
    MINI_TRANSITION_TABLE,
    ESCALATION_ELIGIBLE_STATES,
)
from app.core.state_serialization import (
    StateSerializer,
    StateSerializerConfig,
    StateSerializationError,
    _safe_json_dumps,
    _safe_json_loads,
    _build_lock_key,
    _build_state_key,
)
from app.core.techniques.base import GSDState, ConversationState


# ══════════════════════════════════════════════════════════════════
# 1. INTENT CLASSIFICATION AMBIGUITY
# ══════════════════════════════════════════════════════════════════


class TestIntentClassificationAmbiguity:
    """W9-GAP-008 / HIGH: Unclear intent gets a reasonable result."""

    @pytest.mark.asyncio
    async def test_empty_string_returns_general_intent(self):
        """ClassificationEngine returns 'general' for empty string."""
        engine = ClassificationEngine()
        result = await engine.classify("", company_id="test_co")
        assert result.primary_intent == "general"
        assert result.primary_confidence == 0.0
        assert result.classification_method == "fallback"

    @pytest.mark.asyncio
    async def test_none_input_returns_safe_default(self):
        """ClassificationEngine handles None input gracefully."""
        engine = ClassificationEngine()
        result = await engine.classify(None, company_id="test_co")  # type: ignore[arg-type]
        assert result.primary_intent == "general"
        assert result.primary_confidence == 0.0

    @pytest.mark.asyncio
    async def test_whitespace_only_returns_too_short(self):
        """ClassificationEngine returns fallback for whitespace-only input."""
        engine = ClassificationEngine()
        result = await engine.classify("   ", company_id="test_co")
        assert result.primary_intent == "general"
        assert result.classification_method == "fallback"

    @pytest.mark.asyncio
    async def test_ambiguous_query_gets_reasonable_intent(self):
        """A vague multi-topic query should not crash and returns a valid intent."""
        extractor = SignalExtractor()
        request = SignalExtractionRequest(
            query="hello there, I have some questions about things",
            company_id="co1",
            variant_type="parwa",
        )
        result = await extractor.extract(request)
        assert result.intent in (
            "general", "inquiry", "feedback", "account",
            "technical", "billing", "complaint",
        )

    @pytest.mark.asyncio
    async def test_signal_extractor_returns_valid_sentiment_range(self):
        """Sentiment is always 0.0-1.0 regardless of input."""
        extractor = SignalExtractor()
        for query in ["", "   ", "xyzzy nonsense", "I am very happy and great"]:
            req = SignalExtractionRequest(query=query, company_id="c")
            result = await extractor.extract(req)
            assert 0.0 <= result.sentiment <= 1.0

    @pytest.mark.asyncio
    async def test_non_string_company_id_handled(self):
        """D6-GAP-07: Non-string company_id does not crash."""
        engine = ClassificationEngine()
        result = await engine.classify("refund my order", company_id=12345)  # type: ignore[arg-type]
        assert result.primary_intent == "refund"
        assert result.primary_confidence > 0.0


# ══════════════════════════════════════════════════════════════════
# 2. TECHNIQUE TIER BYPASS
# ══════════════════════════════════════════════════════════════════


class TestTechniqueTierBypass:
    """W9-GAP-029 / HIGH: mini_parwa cannot access Tier 2/3."""

    def test_mini_parwa_cannot_access_tier2(self):
        """parwa_lite blocked from chain_of_thought (Tier 2)."""
        checker = TechniqueTierAccessChecker()
        result = checker.check_access(
            TechniqueID.CHAIN_OF_THOUGHT.value,
            "parwa_lite",
        )
        assert result.decision in (TierAccessDecision.BLOCKED, TierAccessDecision.DOWNGRADED)

    def test_mini_parwa_cannot_access_tier3(self):
        """parwa_lite blocked from gst (Tier 3)."""
        checker = TechniqueTierAccessChecker()
        result = checker.check_access(
            TechniqueID.GST.value,
            "parwa_lite",
        )
        assert result.decision in (TierAccessDecision.BLOCKED, TierAccessDecision.DOWNGRADED)

    def test_parwa_allowed_tier2_blocked_tier3(self):
        """parwa can use Tier 2 but not Tier 3."""
        checker = TechniqueTierAccessChecker()
        t2 = checker.check_access(TechniqueID.CHAIN_OF_THOUGHT.value, "parwa")
        t3 = checker.check_access(TechniqueID.GST.value, "parwa")
        assert t2.decision == TierAccessDecision.ALLOWED
        assert t3.decision != TierAccessDecision.ALLOWED

    def test_parwa_high_allowed_all_tiers(self):
        """parwa_high can access Tier 1, 2, and 3 techniques."""
        checker = TechniqueTierAccessChecker()
        for tid in [
            TechniqueID.CLARA.value,
            TechniqueID.CHAIN_OF_THOUGHT.value,
            TechniqueID.GST.value,
        ]:
            result = checker.check_access(tid, "parwa_high")
            assert result.decision == TierAccessDecision.ALLOWED, (
                f"parwa_high should allow {tid}, got {result.decision}"
            )

    def test_unknown_variant_treated_as_restricted(self):
        """Unknown variant gets BLOCKED for all techniques."""
        checker = TechniqueTierAccessChecker()
        result = checker.check_access(
            TechniqueID.CHAIN_OF_THOUGHT.value, "unknown_variant",
        )
        assert result.decision == TierAccessDecision.BLOCKED
        assert "unknown_variant" in result.reason

    def test_filter_techniques_replaces_blocked_with_fallback(self):
        """filter_techniques swaps blocked techniques for their fallbacks."""
        checker = TechniqueTierAccessChecker()
        filtered = checker.filter_techniques(
            [TechniqueID.GST.value, TechniqueID.CLARA.value],
            "parwa_lite",
        )
        # GST should be replaced by its fallback (CLARA), deduped
        assert TechniqueID.CLARA.value in filtered
        assert TechniqueID.GST.value not in filtered

    def test_cache_returns_consistent_results(self):
        """Caching (W9-GAP-029) returns the same result within TTL."""
        checker = TechniqueTierAccessChecker()
        r1 = checker.check_access(TechniqueID.GST.value, "parwa")
        r2 = checker.check_access(TechniqueID.GST.value, "parwa")
        assert r1.decision == r2.decision
        assert r1.technique == r2.technique


# ══════════════════════════════════════════════════════════════════
# 3. EDGE CASE HANDLER ORDERING
# ══════════════════════════════════════════════════════════════════


class TestEdgeCaseHandlerOrdering:
    """GAP-022/GAP-023: Handlers fire in correct priority order."""

    def test_empty_query_handler_has_lowest_priority_number(self):
        """EmptyQueryHandler must have priority 1 (runs first)."""
        h = EmptyQueryHandler()
        assert h.priority == 1
        assert h.handler_type == "empty_query"

    def test_handlers_sorted_by_priority_in_registry(self):
        """Registry sorts handlers by priority ascending."""
        registry = EdgeCaseRegistry(variant="parwa")
        priorities = [h.priority for h in registry._handlers]
        assert priorities == sorted(priorities)
        assert priorities[0] == 1  # empty_query first

    def test_mini_parwa_runs_reduced_handler_set(self):
        """GAP-023: mini_parwa runs fewer handlers."""
        full = EdgeCaseRegistry(variant="parwa")
        mini = EdgeCaseRegistry(variant="mini_parwa")
        whitelist = VARIANT_HANDLER_WHITELIST["mini_parwa"]
        assert len(mini._handlers) == len(whitelist)
        assert len(mini._handlers) < len(full._handlers)

    def test_malicious_html_blocked(self):
        """Malicious HTML query triggers BLOCK action."""
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process("<script>alert('xss')</script>", context={})
        assert result.blocked is True
        assert result.final_action == EdgeCaseAction.BLOCK

    def test_system_commands_blocked(self):
        """System command query triggers BLOCK."""
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process("sudo rm -rf /", context={})
        assert result.blocked is True
        assert result.final_action == EdgeCaseAction.BLOCK

    def test_blocked_user_triggers_block(self):
        """Blocked user context triggers BLOCK."""
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process(
            "help me", context={"is_blocked": True}
        )
        assert result.blocked is True
        assert result.final_action == EdgeCaseAction.BLOCK

    def test_legal_terminology_escalates(self):
        """Legal terminology triggers ESCALATE action."""
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process(
            "I want to file a lawsuit for breach of contract",
            context={},
        )
        assert EdgeCaseAction.ESCALATE in [
            r.action for r in result.results
        ]

    def test_timeout_handler_fires_on_elapsed(self):
        """TimeoutHandler fires when elapsed exceeds threshold."""
        h = SystemCommandsHandler()
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process(
            "hello",
            context={"_processing_elapsed_ms": CHAIN_TIMEOUT_SECONDS * 1000 + 1},
        )
        handler_types = [r.handler_type for r in result.results]
        assert "timeout" in handler_types


# ══════════════════════════════════════════════════════════════════
# 4. CROSS-VARIANT ESCALATION BILLING
# ══════════════════════════════════════════════════════════════════


class TestCrossVariantEscalationBilling:
    """W9-GAP-015 / HIGH: Billing accurate during escalation."""

    def test_normal_routing_bills_to_originating_variant(self):
        """No escalation → billed_to_variant equals original_variant."""
        router = CrossVariantRouter()
        result = router.route_ticket(
            company_id="co1", ticket_id="t1",
            channel=ChannelType.CHAT,
        )
        assert result.billed_to_variant == result.original_variant
        assert result.escalated is False

    def test_capacity_overflow_triggers_escalation(self):
        """When variant is >90% capacity, escalation happens."""
        router = CrossVariantRouter()
        router.update_capacity("co1", "parwa_lite", 95, 100)
        result = router.route_ticket(
            company_id="co1", ticket_id="t2",
            channel=ChannelType.CHAT,
        )
        assert result.escalated is True
        assert result.decision == RoutingDecisionType.ESCALATE

    def test_escalation_still_bills_to_origin(self):
        """Escalated ticket bills to original variant, not target."""
        router = CrossVariantRouter()
        router.update_capacity("co1", "parwa_lite", 95, 100)
        result = router.route_ticket(
            company_id="co1", ticket_id="t3",
            channel=ChannelType.CHAT,
        )
        assert result.billed_to_variant == "parwa_lite"

    def test_all_tiers_full_routes_to_queue_or_human(self):
        """All tiers at capacity → QUEUE or HUMAN_OVERRIDE (not normal route)."""
        router = CrossVariantRouter()
        for variant in ESCALATION_CHAIN:
            router.update_capacity("co1", variant, 95, 100)
        result = router.route_ticket(
            company_id="co1", ticket_id="t4",
            channel=ChannelType.CHAT,
        )
        # Must be escalated and either queued or sent to human
        assert result.escalated is True
        assert result.decision in (
            RoutingDecisionType.QUEUE,
            RoutingDecisionType.HUMAN_OVERRIDE,
        )

    def test_explicit_escalation_validates_direction(self):
        """Escalation parwa_high → parwa (backwards) is rejected."""
        router = CrossVariantRouter()
        result = router.escalate_ticket(
            company_id="co1", ticket_id="t5",
            from_variant="parwa_high",
            to_variant="parwa",
            reason=EscalationReason.MANUAL_REQUEST,
        )
        assert result.decision == RoutingDecisionType.ROUTE
        assert "invalid" in result.reason.lower()

    def test_process_pending_queue_returns_empty_when_no_tickets(self):
        """Empty queue returns empty list (no crash)."""
        router = CrossVariantRouter()
        results = router.process_pending_queue()
        assert results == []


# ══════════════════════════════════════════════════════════════════
# 5. HUMAN CHECKPOINT / WORKFLOW TIMEOUT
# ══════════════════════════════════════════════════════════════════


class TestWorkflowTimeout:
    """F-200: LangGraph workflow handles timeouts and step errors."""

    def test_mini_parwa_pipeline_has_three_steps(self):
        """mini_parwa should have 3 steps."""
        config = WorkflowConfig(variant_type="mini_parwa")
        wf = LangGraphWorkflow(config)
        wf.build_graph()
        assert len(wf._steps) == 3

    def test_parwa_pipeline_has_six_steps(self):
        """parwa should have 6 steps."""
        config = WorkflowConfig(variant_type="parwa")
        wf = LangGraphWorkflow(config)
        wf.build_graph()
        assert len(wf._steps) == 6

    def test_parwa_high_pipeline_has_nine_steps(self):
        """parwa_high should have 9 steps."""
        config = WorkflowConfig(variant_type="parwa_high")
        wf = LangGraphWorkflow(config)
        wf.build_graph()
        assert len(wf._steps) == 9

    @pytest.mark.asyncio
    async def test_execute_returns_valid_result(self):
        """Workflow execute returns a WorkflowResult with valid status."""
        config = WorkflowConfig(variant_type="mini_parwa")
        wf = LangGraphWorkflow(config)
        result = await wf.execute(
            company_id="co1", query="hello world"
        )
        assert isinstance(result, WorkflowResult)
        assert result.status in ("success", "partial", "failed", "timeout")
        assert result.variant_type == "mini_parwa"
        assert len(result.steps_completed) > 0

    @pytest.mark.asyncio
    async def test_pipeline_topology_returns_structure(self):
        """get_pipeline_topology returns valid structure."""
        config = WorkflowConfig(variant_type="parwa")
        wf = LangGraphWorkflow(config)
        topology = wf.get_pipeline_topology(company_id="co1")
        assert "steps" in topology
        assert "total_steps" in topology
        assert topology["total_steps"] == 6
        assert topology["variant_type"] == "parwa"

    @pytest.mark.asyncio
    async def test_failed_workflow_returns_status_failed(self):
        """When execute raises, returns status='failed' (BC-008)."""
        config = WorkflowConfig(variant_type="mini_parwa")
        wf = LangGraphWorkflow(config)
        # Force a step to fail by making _execute_step raise
        with patch.object(wf, "_execute_step", side_effect=RuntimeError("boom")):
            result = await wf.execute(company_id="co1", query="test")
        assert result.status == "failed"


# ══════════════════════════════════════════════════════════════════
# 6. GSD TRANSITION VALIDATION
# ══════════════════════════════════════════════════════════════════


class TestGSDTransitionValidation:
    """HIGH: Invalid GSD transitions are properly rejected."""

    @pytest.mark.asyncio
    async def test_invalid_transition_new_to_diagnosis_rejected(self):
        """new → diagnosis is invalid (must go through greeting)."""
        engine = GSDEngine()
        state = ConversationState(query="test", company_id="co1")
        state.gsd_state = GSDState.NEW
        with pytest.raises(InvalidTransitionError):
            await engine.transition(state, GSDState.DIAGNOSIS)

    @pytest.mark.asyncio
    async def test_mini_parwa_cannot_escalate(self):
        """mini_parwa variant blocks escalation transitions."""
        engine = GSDEngine()
        engine.update_config("co1", GSDConfig(variant="mini_parwa"))
        state = ConversationState(query="test", company_id="co1")
        state.gsd_state = GSDState.DIAGNOSIS
        can = await engine.can_transition_with_variant(
            GSDState.DIAGNOSIS, GSDState.ESCALATE, "mini_parwa",
        )
        assert can is False

    @pytest.mark.asyncio
    async def test_parwa_can_escalate_from_diagnosis(self):
        """parwa variant allows escalation from diagnosis."""
        engine = GSDEngine()
        can = await engine.can_transition_with_variant(
            GSDState.DIAGNOSIS, GSDState.ESCALATE, "parwa",
        )
        assert can is True

    @pytest.mark.asyncio
    async def test_closed_to_new_is_valid(self):
        """closed → new is a valid transition (reopen)."""
        engine = GSDEngine()
        can = await engine.can_transition(GSDState.CLOSED, GSDState.NEW)
        assert can is True

    @pytest.mark.asyncio
    async def test_transition_table_consistency(self):
        """All states in FULL_TRANSITION_TABLE have valid targets."""
        all_states = {"new", "greeting", "diagnosis", "resolution",
                      "follow_up", "escalate", "human_handoff", "closed"}
        for state, targets in FULL_TRANSITION_TABLE.items():
            assert state in all_states, f"Unknown state {state} in table"
            for t in targets:
                assert t in all_states, f"Unknown target {t} from {state}"

    @pytest.mark.asyncio
    async def test_escalation_eligible_states_do_not_include_terminals(self):
        """CLOSED and HUMAN_HANDOFF should not be escalation-eligible."""
        assert "closed" not in ESCALATION_ELIGIBLE_STATES
        assert "human_handoff" not in ESCALATION_ELIGIBLE_STATES
        assert "new" not in ESCALATION_ELIGIBLE_STATES

    @pytest.mark.asyncio
    async def test_escalation_cooldown_prevents_rapid_escalation(self):
        """Rapid re-escalation raises EscalationCooldownError."""
        engine = GSDEngine()
        config = GSDConfig(variant="parwa", escalation_cooldown_seconds=300.0)
        engine.update_config("co1", config)
        state = ConversationState(
            query="I'm very frustrated!",
            company_id="co1",
        )
        state.gsd_state = GSDState.DIAGNOSIS

        # Set frustration high to trigger auto-escalation
        engine._escalation_timestamps["co1"] = (
            datetime.now(timezone.utc).isoformat()
        )
        with pytest.raises(EscalationCooldownError):
            await engine.handle_escalation(state)


# ══════════════════════════════════════════════════════════════════
# 7. DISTRIBUTED LOCK CONTENTION / STATE SERIALIZATION
# ══════════════════════════════════════════════════════════════════


class TestDistributedLockContention:
    """HIGH: Lock timeout, release, and serialization safety."""

    def test_lock_key_format_includes_ticket_id(self):
        """Lock key is scoped to ticket_id."""
        key = _build_lock_key("ticket_123")
        assert "ticket_123" in key
        assert "parwa:lock:state:" in key

    def test_state_key_format_includes_company_and_ticket(self):
        """State key is scoped to company_id and ticket_id."""
        key = _build_state_key("co_acme", "ticket_456")
        assert "co_acme" in key
        assert "ticket_456" in key

    def test_serialize_deserialize_roundtrip(self):
        """State survives serialize → deserialize cycle."""
        serializer = StateSerializer()
        state = ConversationState(
            query="refund my order",
            ticket_id="t1",
            company_id="c1",
            gsd_state=GSDState.DIAGNOSIS,
            token_usage=42,
        )
        data = serializer.serialize_state(state)
        assert data["query"] == "refund my order"
        assert data["gsd_state"] == "diagnosis"
        assert data["token_usage"] == 42

        restored = serializer.deserialize_state(data)
        assert restored.query == state.query
        assert restored.gsd_state == GSDState.DIAGNOSIS
        assert restored.ticket_id == state.ticket_id
        assert restored.company_id == state.company_id

    def test_deserialize_invalid_gsd_state_falls_back_to_new(self):
        """Invalid gsd_state string falls back to GSDState.NEW."""
        serializer = StateSerializer()
        data = {
            "query": "test",
            "gsd_state": "totally_invalid_state",
        }
        restored = serializer.deserialize_state(data)
        assert restored.gsd_state == GSDState.NEW

    def test_safe_json_loads_raises_on_invalid_input(self):
        """_safe_json_loads raises StateSerializationError for bad JSON."""
        with pytest.raises(StateSerializationError):
            _safe_json_loads("not valid json {{{")

    def test_safe_json_dumps_raises_on_too_large_input(self):
        """_safe_json_dumps raises StateSerializationError for oversized data."""
        huge = {"data": "x" * (6 * 1024 * 1024)}  # 6 MB
        with pytest.raises(StateSerializationError):
            _safe_json_dumps(huge, max_size=5 * 1024 * 1024)

    def test_config_lock_timeout_is_configurable(self):
        """StateSerializerConfig allows custom lock timeout."""
        cfg = StateSerializerConfig(lock_timeout_seconds=10.0)
        assert cfg.lock_timeout_seconds == 10.0
        serializer = StateSerializer(config=cfg)
        assert serializer._config.lock_timeout_seconds == 10.0

    def test_serialize_state_handles_enum_values(self):
        """Enum values (GSDState) are serialized to strings."""
        serializer = StateSerializer()
        state = ConversationState(
            gsd_state=GSDState.ESCALATE,
            gsd_history=[GSDState.NEW, GSDState.GREETING, GSDState.DIAGNOSIS],
        )
        data = serializer.serialize_state(state)
        assert data["gsd_state"] == "escalate"
        assert data["gsd_history"] == ["new", "greeting", "diagnosis"]
