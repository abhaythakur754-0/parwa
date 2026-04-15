"""
Comprehensive tests for F-053 GSD State Engine (Guided Support Dialogue).

Covers: state transitions, escalation handling, variant config, history,
terminal state detection, conversation summary, resolution time estimation,
diagnostic questions, auto-close eligibility, reset, transition reasons,
event emission, error handling, and edge cases.

Target: ~230 tests across 18 categories.

Parent: Week 10 Day 11 (Thursday) — Task ID: 5
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.gsd_engine import (
    DEFAULT_RESOLUTION_ESTIMATE,
    ESCALATION_ELIGIBLE_STATES,
    FULL_TRANSITION_TABLE,
    GSDConfig,
    GSDEngine,
    GSDEngineError,
    GSDVariant,
    InvalidTransitionError,
    LEGAL_INTENTS,
    MINI_TRANSITION_TABLE,
    NEW_ISSUE_PHRASES,
    RESOLUTION_TIME_ESTIMATES,
    SATISFACTION_PHRASES,
    SIMPLE_RESOLUTION_INTENTS,
    TransitionRecord,
    TransitionEvent,
    EscalationCooldownError,
    get_gsd_engine,
    transition_state,
    get_next_gsd_state,
    should_escalate,
)
from backend.app.core.techniques.base import ConversationState, GSDState


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def engine():
    """Fresh GSDEngine instance per test."""
    return GSDEngine()


@pytest.fixture
def base_state():
    """ConversationState in NEW state with default signals."""
    return ConversationState(
        query="I need help with my order",
        ticket_id="tkt_001",
        conversation_id="conv_001",
        company_id="co_001",
    )


@pytest.fixture
def mini_config():
    """GSDConfig for mini_parwa variant."""
    return GSDConfig(
        company_id="co_mini",
        variant=GSDVariant.MINI_PARWA.value,
    )


@pytest.fixture
def parwa_config():
    """GSDConfig for parwa variant."""
    return GSDConfig(
        company_id="co_parwa",
        variant=GSDVariant.PARWA.value,
    )


@pytest.fixture
def parwa_high_config():
    """GSDConfig for parwa_high variant."""
    return GSDConfig(
        company_id="co_high",
        variant=GSDVariant.PARWA_HIGH.value,
    )


def _make_state(
    gsd_state: GSDState = GSDState.NEW,
    query: str = "test query",
    company_id: str = "co_001",
    ticket_id: str = "tkt_001",
    conversation_id: str = "conv_001",
    frustration_score: float = 0.0,
    confidence_score: float = 0.8,
    intent_type: str = "general",
    customer_tier: str = "free",
    query_complexity: float = 0.5,
    sentiment_score: float = 0.7,
    gsd_history: list | None = None,
    technique_results: dict | None = None,
    reasoning_thread: list | None = None,
) -> ConversationState:
    """Create a ConversationState with specific signal overrides."""
    from backend.app.core.technique_router import QuerySignals

    signals = QuerySignals(
        query_complexity=query_complexity,
        confidence_score=confidence_score,
        sentiment_score=sentiment_score,
        customer_tier=customer_tier,
        intent_type=intent_type,
        turn_count=3,
    )
    state = ConversationState(
        query=query,
        gsd_state=gsd_state,
        signals=signals,
        ticket_id=ticket_id,
        conversation_id=conversation_id,
        company_id=company_id,
        gsd_history=gsd_history or [],
        technique_results=technique_results or {},
        reasoning_thread=reasoning_thread or [],
    )
    # Inject frustration via technique_results so _extract_signal_data picks it up
    if frustration_score > 0:
        state.technique_results["sentiment_analysis"] = {
            "status": "success",
            "result": {
                "frustration_score": frustration_score,
                "sentiment_score": sentiment_score,
            },
        }
    return state


def _make_history_entry(state: str, trigger: str = "test") -> dict:
    """Helper to create a history record dict."""
    return {
        "state": state,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trigger": trigger,
        "metadata": {},
    }


# ══════════════════════════════════════════════════════════════════
# 1. STATE TRANSITIONS — VALID (25 tests)
# ══════════════════════════════════════════════════════════════════


class TestValidStateTransitions:
    """Test all legal state transitions succeed and update state correctly."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.asyncio
    async def test_new_to_greeting(self, base_state):
        result = await self.engine.transition(base_state, GSDState.GREETING)
        assert result.gsd_state == GSDState.GREETING

    @pytest.mark.asyncio
    async def test_greeting_to_diagnosis(self):
        state = _make_state(gsd_state=GSDState.GREETING)
        result = await self.engine.transition(state, GSDState.DIAGNOSIS)
        assert result.gsd_state == GSDState.DIAGNOSIS

    @pytest.mark.asyncio
    async def test_diagnosis_to_resolution(self):
        state = _make_state(gsd_state=GSDState.DIAGNOSIS, confidence_score=0.8)
        result = await self.engine.transition(state, GSDState.RESOLUTION)
        assert result.gsd_state == GSDState.RESOLUTION

    @pytest.mark.asyncio
    async def test_resolution_to_follow_up(self):
        state = _make_state(gsd_state=GSDState.RESOLUTION)
        result = await self.engine.transition(state, GSDState.FOLLOW_UP)
        assert result.gsd_state == GSDState.FOLLOW_UP

    @pytest.mark.asyncio
    async def test_resolution_to_closed(self):
        state = _make_state(gsd_state=GSDState.RESOLUTION)
        result = await self.engine.transition(state, GSDState.CLOSED)
        assert result.gsd_state == GSDState.CLOSED

    @pytest.mark.asyncio
    async def test_follow_up_to_closed(self):
        state = _make_state(gsd_state=GSDState.FOLLOW_UP)
        result = await self.engine.transition(state, GSDState.CLOSED)
        assert result.gsd_state == GSDState.CLOSED

    @pytest.mark.asyncio
    async def test_follow_up_to_diagnosis_new_issue(self):
        state = _make_state(gsd_state=GSDState.FOLLOW_UP)
        result = await self.engine.transition(state, GSDState.DIAGNOSIS)
        assert result.gsd_state == GSDState.DIAGNOSIS

    @pytest.mark.asyncio
    async def test_escalate_to_human_handoff(self):
        state = _make_state(gsd_state=GSDState.ESCALATE)
        result = await self.engine.transition(state, GSDState.HUMAN_HANDOFF)
        assert result.gsd_state == GSDState.HUMAN_HANDOFF

    @pytest.mark.asyncio
    async def test_human_handoff_to_diagnosis(self):
        state = _make_state(gsd_state=GSDState.HUMAN_HANDOFF)
        result = await self.engine.transition(state, GSDState.DIAGNOSIS)
        assert result.gsd_state == GSDState.DIAGNOSIS

    @pytest.mark.asyncio
    async def test_closed_to_new(self):
        state = _make_state(gsd_state=GSDState.CLOSED)
        result = await self.engine.transition(state, GSDState.NEW)
        assert result.gsd_state == GSDState.NEW

    @pytest.mark.asyncio
    async def test_diagnosis_to_escalate(self):
        state = _make_state(gsd_state=GSDState.DIAGNOSIS, frustration_score=90.0)
        result = await self.engine.transition(state, GSDState.ESCALATE)
        assert result.gsd_state == GSDState.ESCALATE

    @pytest.mark.asyncio
    async def test_transition_updates_gsd_history(self, base_state):
        await self.engine.transition(base_state, GSDState.GREETING)
        assert len(base_state.gsd_history) == 1
        entry = base_state.gsd_history[0]
        assert isinstance(entry, dict)
        assert entry["state"] == "greeting"
        assert "timestamp" in entry
        assert "trigger" in entry

    @pytest.mark.asyncio
    async def test_multiple_transitions_accumulate_history(self):
        state = _make_state(gsd_state=GSDState.NEW)
        await self.engine.transition(state, GSDState.GREETING)
        await self.engine.transition(state, GSDState.DIAGNOSIS)
        await self.engine.transition(state, GSDState.RESOLUTION)
        assert len(state.gsd_history) == 3

    @pytest.mark.asyncio
    async def test_transition_returns_updated_state(self, base_state):
        result = await self.engine.transition(base_state, GSDState.GREETING)
        assert result is base_state  # same object, mutated

    @pytest.mark.asyncio
    async def test_transition_with_trigger_reason(self, base_state):
        await self.engine.transition(
            base_state, GSDState.GREETING, trigger_reason="user_message"
        )
        entry = base_state.gsd_history[0]
        assert entry["trigger"] == "user_message"

    @pytest.mark.asyncio
    async def test_transition_with_metadata(self, base_state):
        meta = {"confidence": 0.9}
        await self.engine.transition(
            base_state, GSDState.GREETING, metadata=meta
        )
        entry = base_state.gsd_history[0]
        assert entry["metadata"] == meta

    @pytest.mark.asyncio
    async def test_transition_escalation_records_timestamp(self):
        state = _make_state(gsd_state=GSDState.DIAGNOSIS, company_id="co_001")
        await self.engine.transition(state, GSDState.ESCALATE)
        assert "co_001" in self.engine._escalation_timestamps

    @pytest.mark.asyncio
    async def test_transition_default_trigger_applied(self, base_state):
        await self.engine.transition(base_state, GSDState.GREETING)
        entry = base_state.gsd_history[0]
        assert entry["trigger"] == "initial_greeting"

    @pytest.mark.asyncio
    async def test_full_happy_path_flow(self, base_state):
        """NEW → GREETING → DIAGNOSIS → RESOLUTION → FOLLOW_UP → CLOSED."""
        s = base_state
        await self.engine.transition(s, GSDState.GREETING)
        await self.engine.transition(s, GSDState.DIAGNOSIS)
        await self.engine.transition(s, GSDState.RESOLUTION)
        await self.engine.transition(s, GSDState.FOLLOW_UP)
        await self.engine.transition(s, GSDState.CLOSED)
        assert s.gsd_state == GSDState.CLOSED
        assert len(s.gsd_history) == 5

    @pytest.mark.asyncio
    async def test_escalation_flow(self):
        """DIAGNOSIS → ESCALATE → HUMAN_HANDOFF → DIAGNOSIS."""
        state = _make_state(gsd_state=GSDState.DIAGNOSIS)
        await self.engine.transition(state, GSDState.ESCALATE)
        assert state.gsd_state == GSDState.ESCALATE
        await self.engine.transition(state, GSDState.HUMAN_HANDOFF)
        assert state.gsd_state == GSDState.HUMAN_HANDOFF
        await self.engine.transition(state, GSDState.DIAGNOSIS)
        assert state.gsd_state == GSDState.DIAGNOSIS

    @pytest.mark.asyncio
    async def test_reopen_closed_ticket(self):
        """CLOSED → NEW → GREETING."""
        state = _make_state(gsd_state=GSDState.CLOSED)
        await self.engine.transition(state, GSDState.NEW)
        await self.engine.transition(state, GSDState.GREETING)
        assert state.gsd_state == GSDState.GREETING

    @pytest.mark.asyncio
    async def test_string_target_state(self, base_state):
        """transition() should work with string target_state values."""
        result = await self.engine.transition(base_state, "greeting")
        assert result.gsd_state == GSDState.GREETING

    @pytest.mark.asyncio
    async def test_history_entry_has_metadata_key(self, base_state):
        await self.engine.transition(base_state, GSDState.GREETING)
        entry = base_state.gsd_history[0]
        assert "metadata" in entry
        assert isinstance(entry["metadata"], dict)

    @pytest.mark.asyncio
    async def test_history_entry_timestamp_is_iso(self, base_state):
        await self.engine.transition(base_state, GSDState.GREETING)
        entry = base_state.gsd_history[0]
        # ISO timestamps contain 'T' (e.g. 2025-01-15T...)
        assert "T" in entry["timestamp"]


# ══════════════════════════════════════════════════════════════════
# 2. STATE TRANSITIONS — INVALID (20 tests)
# ══════════════════════════════════════════════════════════════════


class TestInvalidStateTransitions:
    """Test that illegal transitions raise InvalidTransitionError."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.asyncio
    async def test_new_to_closed_raises(self, base_state):
        with pytest.raises(InvalidTransitionError) as exc_info:
            await self.engine.transition(base_state, GSDState.CLOSED)
        assert exc_info.value.from_state == "new"
        assert exc_info.value.to_state == "closed"

    @pytest.mark.asyncio
    async def test_greeting_to_closed_raises(self):
        state = _make_state(gsd_state=GSDState.GREETING)
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(state, GSDState.CLOSED)

    @pytest.mark.asyncio
    async def test_resolution_to_greeting_raises(self):
        state = _make_state(gsd_state=GSDState.RESOLUTION)
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(state, GSDState.GREETING)

    @pytest.mark.asyncio
    async def test_diagnosis_to_greeting_raises(self):
        state = _make_state(gsd_state=GSDState.DIAGNOSIS)
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(state, GSDState.GREETING)

    @pytest.mark.asyncio
    async def test_new_to_diagnosis_raises(self, base_state):
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(base_state, GSDState.DIAGNOSIS)

    @pytest.mark.asyncio
    async def test_new_to_resolution_raises(self, base_state):
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(base_state, GSDState.RESOLUTION)

    @pytest.mark.asyncio
    async def test_closed_to_greeting_raises(self):
        state = _make_state(gsd_state=GSDState.CLOSED)
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(state, GSDState.GREETING)

    @pytest.mark.asyncio
    async def test_escalate_to_closed_raises(self):
        state = _make_state(gsd_state=GSDState.ESCALATE)
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(state, GSDState.CLOSED)

    @pytest.mark.asyncio
    async def test_human_handoff_to_closed_raises(self):
        state = _make_state(gsd_state=GSDState.HUMAN_HANDOFF)
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(state, GSDState.CLOSED)

    @pytest.mark.asyncio
    async def test_escalate_to_escalate_raises(self):
        state = _make_state(gsd_state=GSDState.ESCALATE)
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(state, GSDState.ESCALATE)

    @pytest.mark.asyncio
    async def test_human_handoff_to_human_handoff_raises(self):
        state = _make_state(gsd_state=GSDState.HUMAN_HANDOFF)
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(state, GSDState.HUMAN_HANDOFF)

    @pytest.mark.asyncio
    async def test_human_handoff_to_escalate_raises(self):
        state = _make_state(gsd_state=GSDState.HUMAN_HANDOFF)
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(state, GSDState.ESCALATE)

    @pytest.mark.asyncio
    async def test_invalid_error_is_gsdtengine_error(self, base_state):
        with pytest.raises(GSDEngineError):
            await self.engine.transition(base_state, GSDState.CLOSED)

    @pytest.mark.asyncio
    async def test_invalid_error_has_reason(self, base_state):
        with pytest.raises(InvalidTransitionError) as exc_info:
            await self.engine.transition(base_state, GSDState.CLOSED)
        assert exc_info.value.reason  # non-empty

    @pytest.mark.asyncio
    async def test_invalid_error_has_details(self, base_state):
        with pytest.raises(InvalidTransitionError) as exc_info:
            await self.engine.transition(base_state, GSDState.CLOSED)
        assert "from_state" in exc_info.value.details
        assert "to_state" in exc_info.value.details

    @pytest.mark.asyncio
    async def test_new_to_follow_up_raises(self, base_state):
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(base_state, GSDState.FOLLOW_UP)

    @pytest.mark.asyncio
    async def test_new_to_human_handoff_raises(self, base_state):
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(base_state, GSDState.HUMAN_HANDOFF)

    @pytest.mark.asyncio
    async def test_new_to_escalate_raises(self, base_state):
        """NEW is not in ESCALATION_ELIGIBLE_STATES."""
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(base_state, GSDState.ESCALATE)

    @pytest.mark.asyncio
    async def test_closed_to_escalate_raises(self):
        """CLOSED is not in ESCALATION_ELIGIBLE_STATES."""
        state = _make_state(gsd_state=GSDState.CLOSED)
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(state, GSDState.ESCALATE)

    @pytest.mark.asyncio
    async def test_closed_to_diagnosis_raises(self):
        state = _make_state(gsd_state=GSDState.CLOSED)
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(state, GSDState.DIAGNOSIS)


# ══════════════════════════════════════════════════════════════════
# 3. TRANSITION VALIDATION — can_transition (15 tests)
# ══════════════════════════════════════════════════════════════════


class TestCanTransition:
    """Test can_transition returns correct boolean for all pairs."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.asyncio
    async def test_new_to_greeting_true(self):
        assert await self.engine.can_transition(GSDState.NEW, GSDState.GREETING)

    @pytest.mark.asyncio
    async def test_greeting_to_diagnosis_true(self):
        assert await self.engine.can_transition(GSDState.GREETING, GSDState.DIAGNOSIS)

    @pytest.mark.asyncio
    async def test_diagnosis_to_resolution_true(self):
        assert await self.engine.can_transition(GSDState.DIAGNOSIS, GSDState.RESOLUTION)

    @pytest.mark.asyncio
    async def test_diagnosis_to_escalate_true(self):
        assert await self.engine.can_transition(GSDState.DIAGNOSIS, GSDState.ESCALATE)

    @pytest.mark.asyncio
    async def test_resolution_to_follow_up_true(self):
        assert await self.engine.can_transition(GSDState.RESOLUTION, GSDState.FOLLOW_UP)

    @pytest.mark.asyncio
    async def test_resolution_to_closed_true(self):
        assert await self.engine.can_transition(GSDState.RESOLUTION, GSDState.CLOSED)

    @pytest.mark.asyncio
    async def test_follow_up_to_closed_true(self):
        assert await self.engine.can_transition(GSDState.FOLLOW_UP, GSDState.CLOSED)

    @pytest.mark.asyncio
    async def test_follow_up_to_diagnosis_true(self):
        assert await self.engine.can_transition(GSDState.FOLLOW_UP, GSDState.DIAGNOSIS)

    @pytest.mark.asyncio
    async def test_escalate_to_human_handoff_true(self):
        assert await self.engine.can_transition(GSDState.ESCALATE, GSDState.HUMAN_HANDOFF)

    @pytest.mark.asyncio
    async def test_human_handoff_to_diagnosis_true(self):
        assert await self.engine.can_transition(GSDState.HUMAN_HANDOFF, GSDState.DIAGNOSIS)

    @pytest.mark.asyncio
    async def test_closed_to_new_true(self):
        assert await self.engine.can_transition(GSDState.CLOSED, GSDState.NEW)

    @pytest.mark.asyncio
    async def test_new_to_closed_false(self):
        assert not await self.engine.can_transition(GSDState.NEW, GSDState.CLOSED)

    @pytest.mark.asyncio
    async def test_greeting_to_escalate_true(self):
        """GREETING is in ESCALATION_ELIGIBLE_STATES."""
        assert await self.engine.can_transition(GSDState.GREETING, GSDState.ESCALATE)

    @pytest.mark.asyncio
    async def test_resolution_to_escalate_true(self):
        assert await self.engine.can_transition(GSDState.RESOLUTION, GSDState.ESCALATE)

    @pytest.mark.asyncio
    async def test_closed_to_escalate_false(self):
        """CLOSED is NOT in ESCALATION_ELIGIBLE_STATES."""
        assert not await self.engine.can_transition(GSDState.CLOSED, GSDState.ESCALATE)


# ══════════════════════════════════════════════════════════════════
# 4. AVAILABLE TRANSITIONS (10 tests)
# ══════════════════════════════════════════════════════════════════


class TestAvailableTransitions:
    """Test get_available_transitions returns correct next states."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.asyncio
    async def test_new_has_greeting(self):
        avail = await self.engine.get_available_transitions(GSDState.NEW)
        assert GSDState.GREETING in avail

    @pytest.mark.asyncio
    async def test_greeting_has_diagnosis_and_escalate(self):
        avail = await self.engine.get_available_transitions(GSDState.GREETING)
        assert GSDState.DIAGNOSIS in avail
        assert GSDState.ESCALATE in avail

    @pytest.mark.asyncio
    async def test_diagnosis_has_resolution_and_escalate(self):
        avail = await self.engine.get_available_transitions(GSDState.DIAGNOSIS)
        assert GSDState.RESOLUTION in avail
        assert GSDState.ESCALATE in avail

    @pytest.mark.asyncio
    async def test_resolution_has_follow_up_closed_escalate(self):
        avail = await self.engine.get_available_transitions(GSDState.RESOLUTION)
        assert GSDState.FOLLOW_UP in avail
        assert GSDState.CLOSED in avail
        assert GSDState.ESCALATE in avail

    @pytest.mark.asyncio
    async def test_closed_has_new(self):
        avail = await self.engine.get_available_transitions(GSDState.CLOSED)
        assert GSDState.NEW in avail

    @pytest.mark.asyncio
    async def test_escalate_has_human_handoff_only(self):
        avail = await self.engine.get_available_transitions(GSDState.ESCALATE)
        assert len(avail) == 1
        assert GSDState.HUMAN_HANDOFF in avail

    @pytest.mark.asyncio
    async def test_human_handoff_has_diagnosis_only(self):
        avail = await self.engine.get_available_transitions(GSDState.HUMAN_HANDOFF)
        assert GSDState.DIAGNOSIS in avail
        # HUMAN_HANDOFF is NOT in ESCALATION_ELIGIBLE_STATES
        assert GSDState.ESCALATE not in avail

    @pytest.mark.asyncio
    async def test_all_returned_states_are_valid_enums(self):
        for gs in GSDState:
            avail = await self.engine.get_available_transitions(gs)
            for s in avail:
                assert isinstance(s, GSDState)

    @pytest.mark.asyncio
    async def test_mini_parwa_diagnosis_no_escalate(self):
        avail = await self.engine.get_available_transitions(
            GSDState.DIAGNOSIS, variant=GSDVariant.MINI_PARWA.value
        )
        assert GSDState.ESCALATE not in avail
        assert GSDState.RESOLUTION in avail

    @pytest.mark.asyncio
    async def test_results_are_sorted(self):
        avail = await self.engine.get_available_transitions(GSDState.RESOLUTION)
        values = [s.value for s in avail]
        assert values == sorted(values)


# ══════════════════════════════════════════════════════════════════
# 5. get_next_state — AI-driven transitions (20 tests)
# ══════════════════════════════════════════════════════════════════


class TestGetNextState:
    """Test AI-driven next-state determination."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.asyncio
    async def test_new_always_goes_to_greeting(self, base_state):
        next_s = await self.engine.get_next_state(base_state)
        assert next_s == GSDState.GREETING

    @pytest.mark.asyncio
    async def test_greeting_goes_to_diagnosis(self):
        state = _make_state(gsd_state=GSDState.GREETING)
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.DIAGNOSIS

    @pytest.mark.asyncio
    async def test_diagnosis_high_confidence_to_resolution(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            confidence_score=0.9,
            intent_type="billing",
        )
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.RESOLUTION

    @pytest.mark.asyncio
    async def test_diagnosis_low_confidence_stays_diagnosis(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            confidence_score=0.2,
            sentiment_score=0.9,  # low frustration
        )
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.DIAGNOSIS

    @pytest.mark.asyncio
    async def test_diagnosis_frustration_to_escalate(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            frustration_score=95.0,
            sentiment_score=0.05,
            confidence_score=0.3,
        )
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.ESCALATE

    @pytest.mark.asyncio
    async def test_diagnosis_legal_intent_to_escalate(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            intent_type="legal",
            query="I want to sue your company",
        )
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.ESCALATE

    @pytest.mark.asyncio
    async def test_diagnosis_vip_to_escalate(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            customer_tier="enterprise",
            confidence_score=0.5,
        )
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.ESCALATE

    @pytest.mark.asyncio
    async def test_resolution_normal_to_follow_up(self):
        state = _make_state(
            gsd_state=GSDState.RESOLUTION,
            intent_type="technical",
            query="I still have questions about this",
        )
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.FOLLOW_UP

    @pytest.mark.asyncio
    async def test_resolution_simple_to_closed(self):
        state = _make_state(
            gsd_state=GSDState.RESOLUTION,
            intent_type="faq",
            query="thanks",
        )
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.CLOSED

    @pytest.mark.asyncio
    async def test_follow_up_satisfied_to_closed(self):
        state = _make_state(
            gsd_state=GSDState.FOLLOW_UP,
            query="thanks that works great",
        )
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.CLOSED

    @pytest.mark.asyncio
    async def test_follow_up_new_question_to_diagnosis(self):
        state = _make_state(
            gsd_state=GSDState.FOLLOW_UP,
            query="also I have another thing to ask about",
        )
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.DIAGNOSIS

    @pytest.mark.asyncio
    async def test_escalate_to_human_handoff(self):
        state = _make_state(gsd_state=GSDState.ESCALATE)
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.HUMAN_HANDOFF

    @pytest.mark.asyncio
    async def test_human_handoff_to_diagnosis(self):
        state = _make_state(gsd_state=GSDState.HUMAN_HANDOFF)
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.DIAGNOSIS

    @pytest.mark.asyncio
    async def test_closed_to_new(self):
        state = _make_state(gsd_state=GSDState.CLOSED)
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.NEW

    @pytest.mark.asyncio
    async def test_diagnosis_loops_to_escalate(self):
        """After 3+ diagnosis loops, should auto-escalate."""
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            confidence_score=0.5,
            sentiment_score=0.9,
        )
        # Simulate 3 prior diagnosis entries in history
        state.gsd_history = [
            _make_history_entry("diagnosis"),
            _make_history_entry("diagnosis"),
            _make_history_entry("diagnosis"),
        ]
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.ESCALATE

    @pytest.mark.asyncio
    async def test_legal_keyword_in_query_to_escalate(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            query="I need to contact my attorney about gdpr",
            intent_type="general",
        )
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.ESCALATE

    @pytest.mark.asyncio
    async def test_follow_up_question_mark_to_diagnosis(self):
        state = _make_state(
            gsd_state=GSDState.FOLLOW_UP,
            query="how do I reset my password?",
        )
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.DIAGNOSIS

    @pytest.mark.asyncio
    async def test_follow_up_negation_to_diagnosis(self):
        state = _make_state(
            gsd_state=GSDState.FOLLOW_UP,
            query="that is actually not what I meant at all",
        )
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.DIAGNOSIS

    @pytest.mark.asyncio
    async def test_resolution_brief_acknowledgment_to_closed(self):
        state = _make_state(
            gsd_state=GSDState.RESOLUTION,
            intent_type="billing",
            query="ok",
        )
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.CLOSED

    @pytest.mark.asyncio
    async def test_mini_parwa_diagnosis_ignores_escalation(self):
        """Mini PARWA should never escalate via get_next_state."""
        self.engine.update_config("co_mini", GSDConfig(variant=GSDVariant.MINI_PARWA.value))
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            company_id="co_mini",
            frustration_score=99.0,
            sentiment_score=0.01,
        )
        next_s = await self.engine.get_next_state(state)
        assert next_s != GSDState.ESCALATE


# ══════════════════════════════════════════════════════════════════
# 6. ESCALATION HANDLING (20 tests)
# ══════════════════════════════════════════════════════════════════


class TestEscalationHandling:
    """Test escalation detection, cooldown, and metadata."""

    def setup_method(self):
        self.engine = GSDEngine()
        self.engine.update_config(
            "co_001",
            GSDConfig(
                company_id="co_001",
                frustration_threshold=80.0,
                escalation_cooldown_seconds=300.0,
                max_diagnosis_loops=3,
            ),
        )

    @pytest.mark.asyncio
    async def test_frustration_above_80_triggers(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            frustration_score=90.0,
            sentiment_score=0.1,
        )
        assert await self.engine._should_auto_escalate(state)

    @pytest.mark.asyncio
    async def test_frustration_below_80_no_trigger(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            frustration_score=30.0,
            sentiment_score=0.7,
        )
        assert not await self.engine._should_auto_escalate(state)

    @pytest.mark.asyncio
    async def test_legal_intent_triggers(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            intent_type="legal",
            query="I want to sue",
        )
        assert await self.engine._should_auto_escalate(state)

    @pytest.mark.asyncio
    async def test_vip_customer_triggers(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            customer_tier="enterprise",
        )
        assert await self.engine._should_auto_escalate(state)

    @pytest.mark.asyncio
    async def test_vip_tier_lowercase(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            customer_tier="VIP",
        )
        assert await self.engine._should_auto_escalate(state)

    @pytest.mark.asyncio
    async def test_diagnosis_loops_trigger(self):
        state = _make_state(gsd_state=GSDState.DIAGNOSIS, confidence_score=0.5)
        state.gsd_history = [
            _make_history_entry("diagnosis"),
            _make_history_entry("diagnosis"),
            _make_history_entry("diagnosis"),
        ]
        assert await self.engine._should_auto_escalate(state)

    @pytest.mark.asyncio
    async def test_cooldown_after_escalation(self):
        state = _make_state(gsd_state=GSDState.DIAGNOSIS, company_id="co_001")
        # Perform escalation
        await self.engine.transition(state, GSDState.ESCALATE)
        # Cooldown should be active
        remaining = self.engine._check_escalation_cooldown("co_001", 300.0)
        assert remaining > 0

    @pytest.mark.asyncio
    async def test_cooldown_expired(self):
        """Set escalation timestamp in the past so cooldown expires."""
        past = datetime.now(timezone.utc).isoformat()
        # Manually set a timestamp that's older than cooldown
        from datetime import timedelta
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
        self.engine._escalation_timestamps["co_001"] = old_time
        remaining = self.engine._check_escalation_cooldown("co_001", 300.0)
        assert remaining == 0.0

    @pytest.mark.asyncio
    async def test_escalation_cooldown_error_raised(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            company_id="co_001",
            frustration_score=95.0,
        )
        # Set recent escalation
        self.engine._escalation_timestamps["co_001"] = (
            datetime.now(timezone.utc).isoformat()
        )
        with pytest.raises(EscalationCooldownError) as exc_info:
            await self.engine.handle_escalation(state)
        assert exc_info.value.cooldown_remaining_seconds > 0

    @pytest.mark.asyncio
    async def test_handle_escalation_success(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            company_id="co_001",
            frustration_score=95.0,
        )
        result = await self.engine.handle_escalation(state)
        assert result.gsd_state == GSDState.ESCALATE

    @pytest.mark.asyncio
    async def test_handle_escalation_no_trigger_returns_unchanged(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            company_id="co_001",
            frustration_score=10.0,
            sentiment_score=0.9,
        )
        result = await self.engine.handle_escalation(state)
        assert result.gsd_state == GSDState.DIAGNOSIS

    @pytest.mark.asyncio
    async def test_escalation_metadata_set(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            company_id="co_001",
            frustration_score=90.0,
        )
        result = await self.engine.handle_escalation(state)
        last_entry = result.gsd_history[-1]
        meta = last_entry.get("metadata", {})
        assert "escalation_reason" in meta
        assert "frustration_score" in meta
        assert "escalated_at" in meta

    @pytest.mark.asyncio
    async def test_legal_escalation_reason(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            intent_type="legal",
            query="I want to sue",
        )
        reason = await self.engine._get_escalation_reason(state)
        assert "legal" in reason.lower()

    @pytest.mark.asyncio
    async def test_frustration_escalation_reason(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            frustration_score=90.0,
            sentiment_score=0.1,
        )
        reason = await self.engine._get_escalation_reason(state)
        assert "frustration" in reason.lower()

    @pytest.mark.asyncio
    async def test_vip_escalation_reason(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            customer_tier="enterprise",
        )
        reason = await self.engine._get_escalation_reason(state)
        assert "vip" in reason.lower()

    @pytest.mark.asyncio
    async def test_diagnosis_loop_escalation_reason(self):
        state = _make_state(gsd_state=GSDState.DIAGNOSIS)
        state.gsd_history = [
            _make_history_entry("diagnosis"),
            _make_history_entry("diagnosis"),
            _make_history_entry("diagnosis"),
        ]
        reason = await self.engine._get_escalation_reason(state)
        assert "diagnosis" in reason.lower() or "loop" in reason.lower()

    @pytest.mark.asyncio
    async def test_any_escalation_condition_triggers(self):
        """Any single condition triggers auto-escalation."""
        # Legal intent without any other trigger
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            intent_type="legal",
            frustration_score=0.0,
            customer_tier="free",
        )
        assert await self.engine._should_auto_escalate(state)

    @pytest.mark.asyncio
    async def test_no_company_id_no_cooldown_check(self):
        """Cooldown check returns 0 when company_id is None."""
        remaining = self.engine._check_escalation_cooldown(None, 300.0)
        assert remaining == 0.0

    @pytest.mark.asyncio
    async def test_cooldown_not_set_returns_zero(self):
        remaining = self.engine._check_escalation_cooldown("co_unknown", 300.0)
        assert remaining == 0.0

    @pytest.mark.asyncio
    async def test_escalation_evaluation_returns_four_conditions(self):
        state = _make_state(gsd_state=GSDState.DIAGNOSIS)
        config = self.engine.get_config("co_001")
        conditions = await self.engine._evaluate_escalation_conditions(state, config)
        assert len(conditions) == 4
        names = [c["condition"] for c in conditions]
        assert "frustration_exceeded" in names
        assert "legal_intent" in names
        assert "vip_customer" in names
        assert "diagnosis_loop_exceeded" in names


# ══════════════════════════════════════════════════════════════════
# 7. VARIANT-SPECIFIC CONFIG (15 tests)
# ══════════════════════════════════════════════════════════════════


class TestVariantConfig:
    """Test variant-specific transition table and config behavior."""

    def setup_method(self):
        self.engine = GSDEngine()

    def test_mini_parwa_config_has_variant(self):
        config = GSDConfig(variant=GSDVariant.MINI_PARWA.value)
        assert config.variant == "mini_parwa"

    def test_parwa_config_default_variant(self):
        config = GSDConfig()
        assert config.variant == GSDVariant.PARWA.value

    def test_parwa_high_config(self):
        config = GSDConfig(variant=GSDVariant.PARWA_HIGH.value)
        assert config.variant == "parwa_high"

    @pytest.mark.asyncio
    async def test_mini_parwa_cannot_escalate(self):
        assert not await self.engine.can_transition_with_variant(
            GSDState.DIAGNOSIS, GSDState.ESCALATE, GSDVariant.MINI_PARWA.value
        )

    @pytest.mark.asyncio
    async def test_parwa_can_escalate_from_diagnosis(self):
        assert await self.engine.can_transition_with_variant(
            GSDState.DIAGNOSIS, GSDState.ESCALATE, GSDVariant.PARWA.value
        )

    @pytest.mark.asyncio
    async def test_parwa_high_can_escalate(self):
        assert await self.engine.can_transition_with_variant(
            GSDState.DIAGNOSIS, GSDState.ESCALATE, GSDVariant.PARWA_HIGH.value
        )

    @pytest.mark.asyncio
    async def test_mini_parwa_linear_flow(self, mini_config):
        self.engine.update_config("co_mini", mini_config)
        state = _make_state(company_id="co_mini")
        await self.engine.transition(state, GSDState.GREETING)
        await self.engine.transition(state, GSDState.DIAGNOSIS)
        await self.engine.transition(state, GSDState.RESOLUTION)
        await self.engine.transition(state, GSDState.CLOSED)
        assert state.gsd_state == GSDState.CLOSED

    @pytest.mark.asyncio
    async def test_mini_parwa_cannot_escalate_via_variant_check(self, mini_config):
        """Mini PARWA blocks escalation at variant level."""
        assert not await self.engine.can_transition_with_variant(
            GSDState.DIAGNOSIS, GSDState.ESCALATE, GSDVariant.MINI_PARWA.value
        )

    @pytest.mark.asyncio
    async def test_get_variant_returns_configured(self):
        self.engine.update_config(
            "co_x", GSDConfig(variant=GSDVariant.MINI_PARWA.value)
        )
        assert self.engine.get_variant("co_x") == "mini_parwa"

    @pytest.mark.asyncio
    async def test_get_variant_default_parwa(self):
        assert self.engine.get_variant("nonexistent") == "parwa"

    @pytest.mark.asyncio
    async def test_get_variant_none_returns_default(self):
        assert self.engine.get_variant(None) == "parwa"

    @pytest.mark.asyncio
    async def test_get_config_returns_configured(self):
        cfg = GSDConfig(variant=GSDVariant.PARWA_HIGH.value, frustration_threshold=70.0)
        self.engine.update_config("co_y", cfg)
        got = self.engine.get_config("co_y")
        assert got.variant == "parwa_high"
        assert got.frustration_threshold == 70.0

    @pytest.mark.asyncio
    async def test_get_config_returns_default_when_missing(self):
        cfg = self.engine.get_config("co_nonexistent")
        assert cfg.variant == GSDVariant.PARWA.value

    @pytest.mark.asyncio
    async def test_get_config_empty_company_id(self):
        cfg = self.engine.get_config("")
        assert cfg.company_id == ""

    @pytest.mark.asyncio
    async def test_update_config_overwrites(self):
        cfg1 = GSDConfig(variant=GSDVariant.MINI_PARWA.value)
        cfg2 = GSDConfig(variant=GSDVariant.PARWA_HIGH.value)
        self.engine.update_config("co_z", cfg1)
        self.engine.update_config("co_z", cfg2)
        assert self.engine.get_config("co_z").variant == "parwa_high"


# ══════════════════════════════════════════════════════════════════
# 8. STATE HISTORY (10 tests)
# ══════════════════════════════════════════════════════════════════


class TestStateHistory:
    """Test GSD history recording and ring buffer behavior."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.asyncio
    async def test_first_transition_adds_entry(self, base_state):
        await self.engine.transition(base_state, GSDState.GREETING)
        assert len(base_state.gsd_history) == 1

    @pytest.mark.asyncio
    async def test_multiple_transitions_accumulate(self):
        state = _make_state()
        for target in [GSDState.GREETING, GSDState.DIAGNOSIS, GSDState.RESOLUTION]:
            await self.engine.transition(state, target)
        assert len(state.gsd_history) == 3

    @pytest.mark.asyncio
    async def test_history_format(self, base_state):
        await self.engine.transition(base_state, GSDState.GREETING)
        entry = base_state.gsd_history[0]
        assert "state" in entry
        assert "timestamp" in entry
        assert "trigger" in entry
        assert "metadata" in entry

    @pytest.mark.asyncio
    async def test_history_ring_buffer(self):
        """History trimmed to max_history_entries."""
        config = GSDConfig(max_history_entries=5)
        self.engine.update_config("co_001", config)
        state = _make_state(company_id="co_001")
        # Transition more than max
        for _ in range(10):
            await self.engine.transition(state, GSDState.GREETING)
            # Move back to new for next iteration
            state.gsd_state = GSDState.NEW
        assert len(state.gsd_history) <= 5

    @pytest.mark.asyncio
    async def test_history_entries_ordered(self):
        state = _make_state()
        await self.engine.transition(state, GSDState.GREETING)
        await self.engine.transition(state, GSDState.DIAGNOSIS)
        assert state.gsd_history[0]["state"] == "greeting"
        assert state.gsd_history[1]["state"] == "diagnosis"

    @pytest.mark.asyncio
    async def test_get_history_records_empty(self):
        state = _make_state()
        records = self.engine._get_history_records(state)
        assert records == []

    @pytest.mark.asyncio
    async def test_get_history_records_handles_legacy(self):
        """Legacy format: raw GSDState enum values in history."""
        state = _make_state()
        state.gsd_history = [GSDState.GREETING, GSDState.DIAGNOSIS]
        records = self.engine._get_history_records(state)
        assert len(records) == 2
        assert records[0]["trigger"] == "legacy_entry"

    @pytest.mark.asyncio
    async def test_count_diagnosis_loops(self):
        state = _make_state(gsd_state=GSDState.DIAGNOSIS)
        state.gsd_history = [
            _make_history_entry("diagnosis"),
            _make_history_entry("resolution"),
            _make_history_entry("diagnosis"),
        ]
        # Current state + 2 in history = 3
        count = self.engine._count_diagnosis_loops(state)
        assert count == 3

    @pytest.mark.asyncio
    async def test_count_diagnosis_loops_zero(self):
        state = _make_state(gsd_state=GSDState.NEW)
        count = self.engine._count_diagnosis_loops(state)
        assert count == 0

    @pytest.mark.asyncio
    async def test_transition_record_to_dict(self):
        record = TransitionRecord(
            state="greeting",
            timestamp="2025-01-01T00:00:00Z",
            trigger="test",
            metadata={"key": "val"},
        )
        d = record.to_dict()
        assert d["state"] == "greeting"
        assert d["metadata"]["key"] == "val"


# ══════════════════════════════════════════════════════════════════
# 9. TERMINAL STATE DETECTION (10 tests)
# ══════════════════════════════════════════════════════════════════


class TestTerminalStateDetection:
    """Test is_terminal correctly identifies terminal states."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.asyncio
    async def test_closed_is_terminal(self):
        state = _make_state(gsd_state=GSDState.CLOSED)
        assert await self.engine.is_terminal(state)

    @pytest.mark.asyncio
    async def test_human_handoff_is_terminal(self):
        state = _make_state(gsd_state=GSDState.HUMAN_HANDOFF)
        assert await self.engine.is_terminal(state)

    @pytest.mark.asyncio
    async def test_new_is_not_terminal(self, base_state):
        assert not await self.engine.is_terminal(base_state)

    @pytest.mark.asyncio
    async def test_greeting_is_not_terminal(self):
        state = _make_state(gsd_state=GSDState.GREETING)
        assert not await self.engine.is_terminal(state)

    @pytest.mark.asyncio
    async def test_diagnosis_is_not_terminal(self):
        state = _make_state(gsd_state=GSDState.DIAGNOSIS)
        assert not await self.engine.is_terminal(state)

    @pytest.mark.asyncio
    async def test_resolution_is_not_terminal(self):
        state = _make_state(gsd_state=GSDState.RESOLUTION)
        assert not await self.engine.is_terminal(state)

    @pytest.mark.asyncio
    async def test_follow_up_is_not_terminal(self):
        state = _make_state(gsd_state=GSDState.FOLLOW_UP)
        assert not await self.engine.is_terminal(state)

    @pytest.mark.asyncio
    async def test_escalate_is_not_terminal(self):
        state = _make_state(gsd_state=GSDState.ESCALATE)
        assert not await self.engine.is_terminal(state)

    @pytest.mark.asyncio
    async def test_returns_bool(self, base_state):
        result = await self.engine.is_terminal(base_state)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_all_states_have_exactly_two_terminal(self):
        terminal_count = 0
        for gs in GSDState:
            state = _make_state(gsd_state=gs)
            if await self.engine.is_terminal(state):
                terminal_count += 1
        assert terminal_count == 2


# ══════════════════════════════════════════════════════════════════
# 10. CONVERSATION SUMMARY (10 tests)
# ══════════════════════════════════════════════════════════════════


class TestConversationSummary:
    """Test get_conversation_summary returns comprehensive snapshot."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.asyncio
    async def test_summary_includes_current_state(self, base_state):
        summary = await self.engine.get_conversation_summary(base_state)
        assert summary["current_state"] == "new"

    @pytest.mark.asyncio
    async def test_summary_includes_history_length(self, base_state):
        summary = await self.engine.get_conversation_summary(base_state)
        assert "history_entry_count" in summary

    @pytest.mark.asyncio
    async def test_summary_includes_turn_count(self, base_state):
        summary = await self.engine.get_conversation_summary(base_state)
        assert "signals" in summary
        assert "turn_count" in summary["signals"]

    @pytest.mark.asyncio
    async def test_summary_includes_diagnosis_loops(self, base_state):
        summary = await self.engine.get_conversation_summary(base_state)
        assert "diagnosis_loop_count" in summary

    @pytest.mark.asyncio
    async def test_summary_includes_estimated_resolution_time(self, base_state):
        summary = await self.engine.get_conversation_summary(base_state)
        assert "estimated_resolution_time_minutes" in summary

    @pytest.mark.asyncio
    async def test_summary_includes_available_transitions(self, base_state):
        summary = await self.engine.get_conversation_summary(base_state)
        assert "available_transitions" in summary
        assert isinstance(summary["available_transitions"], list)

    @pytest.mark.asyncio
    async def test_summary_includes_is_terminal(self, base_state):
        summary = await self.engine.get_conversation_summary(base_state)
        assert "is_terminal" in summary

    @pytest.mark.asyncio
    async def test_summary_includes_escalation_eligible(self, base_state):
        summary = await self.engine.get_conversation_summary(base_state)
        assert "escalation_eligible" in summary

    @pytest.mark.asyncio
    async def test_summary_includes_variant(self, base_state):
        summary = await self.engine.get_conversation_summary(base_state)
        assert "variant" in summary

    @pytest.mark.asyncio
    async def test_summary_includes_token_usage(self, base_state):
        summary = await self.engine.get_conversation_summary(base_state)
        assert "token_usage" in summary


# ══════════════════════════════════════════════════════════════════
# 11. RESOLUTION TIME ESTIMATION (10 tests)
# ══════════════════════════════════════════════════════════════════


class TestResolutionTimeEstimation:
    """Test estimate_resolution_time returns sensible values."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.asyncio
    async def test_simple_faq_low_complexity(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            intent_type="faq",
            query_complexity=0.1,
        )
        est = await self.engine.estimate_resolution_time(state)
        assert est >= 0
        assert isinstance(est, int)

    @pytest.mark.asyncio
    async def test_technical_high_complexity(self):
        state = _make_state(
            gsd_state=GSDState.NEW,
            intent_type="technical",
            query_complexity=0.9,
        )
        est = await self.engine.estimate_resolution_time(state)
        assert est > 30  # technical high = 60 base + adjustments

    @pytest.mark.asyncio
    async def test_resolution_state_reduces_estimate(self):
        state_res = _make_state(gsd_state=GSDState.RESOLUTION, intent_type="billing", query_complexity=0.5)
        state_new = _make_state(gsd_state=GSDState.NEW, intent_type="billing", query_complexity=0.5)
        est_res = await self.engine.estimate_resolution_time(state_res)
        est_new = await self.engine.estimate_resolution_time(state_new)
        assert est_res < est_new

    @pytest.mark.asyncio
    async def test_follow_up_reduces_more(self):
        state_fu = _make_state(gsd_state=GSDState.FOLLOW_UP, intent_type="billing", query_complexity=0.5)
        state_new = _make_state(gsd_state=GSDState.NEW, intent_type="billing", query_complexity=0.5)
        est_fu = await self.engine.estimate_resolution_time(state_fu)
        est_new = await self.engine.estimate_resolution_time(state_new)
        assert est_fu < est_new

    @pytest.mark.asyncio
    async def test_escalate_increases_estimate(self):
        state_esc = _make_state(gsd_state=GSDState.ESCALATE, intent_type="billing", query_complexity=0.5)
        state_new = _make_state(gsd_state=GSDState.NEW, intent_type="billing", query_complexity=0.5)
        est_esc = await self.engine.estimate_resolution_time(state_esc)
        est_new = await self.engine.estimate_resolution_time(state_new)
        assert est_esc > est_new

    @pytest.mark.asyncio
    async def test_closed_returns_non_negative(self):
        state = _make_state(gsd_state=GSDState.CLOSED)
        est = await self.engine.estimate_resolution_time(state)
        assert est >= 0

    @pytest.mark.asyncio
    async def test_unknown_intent_uses_default(self):
        state = _make_state(gsd_state=GSDState.NEW, intent_type="unknown_xyz", query_complexity=0.5)
        est = await self.engine.estimate_resolution_time(state)
        assert est >= 0

    @pytest.mark.asyncio
    async def test_high_frustration_increases_estimate(self):
        state_low = _make_state(gsd_state=GSDState.NEW, intent_type="general", query_complexity=0.5, frustration_score=10.0, sentiment_score=0.9)
        state_high = _make_state(gsd_state=GSDState.NEW, intent_type="general", query_complexity=0.5, frustration_score=90.0, sentiment_score=0.1)
        est_low = await self.engine.estimate_resolution_time(state_low)
        est_high = await self.engine.estimate_resolution_time(state_high)
        assert est_high > est_low

    @pytest.mark.asyncio
    async def test_complexity_bucket_low(self):
        state = _make_state(gsd_state=GSDState.NEW, intent_type="billing", query_complexity=0.1)
        est = await self.engine.estimate_resolution_time(state)
        # Low complexity billing = 5 minutes
        assert est <= 10

    @pytest.mark.asyncio
    async def test_complexity_bucket_high(self):
        state = _make_state(gsd_state=GSDState.NEW, intent_type="billing", query_complexity=0.9)
        est = await self.engine.estimate_resolution_time(state)
        # High complexity billing = 45 minutes
        assert est > 30


# ══════════════════════════════════════════════════════════════════
# 12. DIAGNOSTIC QUESTIONS (10 tests)
# ══════════════════════════════════════════════════════════════════


class TestDiagnosticQuestions:
    """Test get_diagnostic_questions returns relevant questions."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.asyncio
    async def test_diagnosis_state_returns_questions(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            intent_type="refund",
            query="I want my money back",
        )
        questions = await self.engine.get_diagnostic_questions(state)
        assert isinstance(questions, list)
        assert len(questions) > 0

    @pytest.mark.asyncio
    async def test_non_diagnosis_returns_empty(self):
        state = _make_state(gsd_state=GSDState.GREETING)
        questions = await self.engine.get_diagnostic_questions(state)
        assert questions == []

    @pytest.mark.asyncio
    async def test_new_state_returns_empty(self, base_state):
        questions = await self.engine.get_diagnostic_questions(base_state)
        assert questions == []

    @pytest.mark.asyncio
    async def test_closed_state_returns_empty(self):
        state = _make_state(gsd_state=GSDState.CLOSED)
        questions = await self.engine.get_diagnostic_questions(state)
        assert questions == []

    @pytest.mark.asyncio
    async def test_refund_intent_specific_questions(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            intent_type="refund",
            query="help",
        )
        questions = await self.engine.get_diagnostic_questions(state)
        assert len(questions) > 0
        # At least one should mention order/transaction
        all_text = " ".join(questions).lower()
        assert "order" in all_text or "refund" in all_text or "transaction" in all_text

    @pytest.mark.asyncio
    async def test_technical_intent_specific_questions(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            intent_type="technical",
            query="something is broken",
        )
        questions = await self.engine.get_diagnostic_questions(state)
        assert len(questions) > 0

    @pytest.mark.asyncio
    async def test_max_three_questions(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            intent_type="technical",
            query="x",
        )
        questions = await self.engine.get_diagnostic_questions(state)
        assert len(questions) <= 3

    @pytest.mark.asyncio
    async def test_unknown_intent_returns_general_questions(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            intent_type="nonexistent_intent",
            query="help",
        )
        questions = await self.engine.get_diagnostic_questions(state)
        assert isinstance(questions, list)

    @pytest.mark.asyncio
    async def test_reasoning_thread_filters_duplicates(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            intent_type="refund",
            query="order",
            reasoning_thread=["Could you provide your order number?"],
        )
        questions = await self.engine.get_diagnostic_questions(state)
        # The order number question should be filtered since it overlaps with reasoning
        assert not any("order number" in q.lower() for q in questions)

    @pytest.mark.asyncio
    async def test_general_intent_returns_questions(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            intent_type="general",
            query="I have a question",
        )
        questions = await self.engine.get_diagnostic_questions(state)
        assert len(questions) > 0


# ══════════════════════════════════════════════════════════════════
# 13. AUTO-CLOSE ELIGIBILITY (10 tests)
# ══════════════════════════════════════════════════════════════════


class TestAutoCloseEligibility:
    """Test should_auto_close logic."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.asyncio
    async def test_faq_resolution_eligible(self):
        state = _make_state(
            gsd_state=GSDState.RESOLUTION,
            intent_type="faq",
            query="thanks",
        )
        assert await self.engine.should_auto_close(state)

    @pytest.mark.asyncio
    async def test_billing_resolution_eligible(self):
        state = _make_state(
            gsd_state=GSDState.RESOLUTION,
            intent_type="billing",
            query="ok got it",
        )
        assert await self.engine.should_auto_close(state)

    @pytest.mark.asyncio
    async def test_follow_up_satisfied_eligible(self):
        state = _make_state(
            gsd_state=GSDState.FOLLOW_UP,
            intent_type="faq",
            query="that worked perfectly",
        )
        assert await self.engine.should_auto_close(state)

    @pytest.mark.asyncio
    async def test_diagnosis_not_eligible(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            intent_type="faq",
            query="thanks",
        )
        assert not await self.engine.should_auto_close(state)

    @pytest.mark.asyncio
    async def test_new_not_eligible(self, base_state):
        assert not await self.engine.should_auto_close(base_state)

    @pytest.mark.asyncio
    async def test_closed_not_eligible(self):
        state = _make_state(gsd_state=GSDState.CLOSED, query="thanks")
        assert not await self.engine.should_auto_close(state)

    @pytest.mark.asyncio
    async def test_technical_not_auto_closed(self):
        """Technical intent is not in SIMPLE_RESOLUTION_INTENTS."""
        state = _make_state(
            gsd_state=GSDState.RESOLUTION,
            intent_type="technical",
            query="thanks",
        )
        assert not await self.engine.should_auto_close(state)

    @pytest.mark.asyncio
    async def test_long_message_not_auto_closed(self):
        """Resolution with a long message from customer doesn't auto-close."""
        state = _make_state(
            gsd_state=GSDState.RESOLUTION,
            intent_type="billing",
            query="I have a very detailed question about my bill that is more than five words",
        )
        assert not await self.engine.should_auto_close(state)

    @pytest.mark.asyncio
    async def test_empty_query_not_eligible(self):
        state = _make_state(
            gsd_state=GSDState.RESOLUTION,
            intent_type="faq",
            query="",
        )
        assert not await self.engine.should_auto_close(state)

    @pytest.mark.asyncio
    async def test_follow_up_no_satisfaction_not_eligible(self):
        state = _make_state(
            gsd_state=GSDState.FOLLOW_UP,
            intent_type="billing",
            query="I still have more questions",
        )
        assert not await self.engine.should_auto_close(state)


# ══════════════════════════════════════════════════════════════════
# 14. RESET CONVERSATION (10 tests)
# ══════════════════════════════════════════════════════════════════


class TestResetConversation:
    """Test reset_conversation behavior."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.asyncio
    async def test_reset_sets_state_to_new(self):
        state = _make_state(gsd_state=GSDState.CLOSED)
        result = await self.engine.reset_conversation(state)
        assert result.gsd_state == GSDState.NEW

    @pytest.mark.asyncio
    async def test_reset_preserves_ticket_id(self):
        state = _make_state(gsd_state=GSDState.CLOSED, ticket_id="tkt_preserve")
        result = await self.engine.reset_conversation(state)
        assert result.ticket_id == "tkt_preserve"

    @pytest.mark.asyncio
    async def test_reset_preserves_company_id(self):
        state = _make_state(gsd_state=GSDState.CLOSED, company_id="co_preserve")
        result = await self.engine.reset_conversation(state)
        assert result.company_id == "co_preserve"

    @pytest.mark.asyncio
    async def test_reset_preserves_query(self):
        state = _make_state(gsd_state=GSDState.CLOSED, query="original query")
        result = await self.engine.reset_conversation(state)
        assert result.query == "original query"

    @pytest.mark.asyncio
    async def test_reset_preserves_conversation_id(self):
        state = _make_state(gsd_state=GSDState.CLOSED, conversation_id="conv_keep")
        result = await self.engine.reset_conversation(state)
        assert result.conversation_id == "conv_keep"

    @pytest.mark.asyncio
    async def test_reset_adds_history_record(self):
        state = _make_state(gsd_state=GSDState.CLOSED)
        await self.engine.reset_conversation(state)
        entry = state.gsd_history[-1]
        assert entry["state"] == "new"
        assert entry["trigger"] == "conversation_reset"

    @pytest.mark.asyncio
    async def test_reset_clears_escalation_cooldown(self):
        self.engine._escalation_timestamps["co_001"] = (
            datetime.now(timezone.utc).isoformat()
        )
        state = _make_state(gsd_state=GSDState.CLOSED, company_id="co_001")
        await self.engine.reset_conversation(state)
        assert "co_001" not in self.engine._escalation_timestamps

    @pytest.mark.asyncio
    async def test_reset_from_any_state(self):
        for gs in GSDState:
            state = _make_state(gsd_state=gs, company_id="co_reset")
            result = await self.engine.reset_conversation(state)
            assert result.gsd_state == GSDState.NEW

    @pytest.mark.asyncio
    async def test_reset_metadata_has_previous_state(self):
        state = _make_state(gsd_state=GSDState.RESOLUTION)
        await self.engine.reset_conversation(state)
        entry = state.gsd_history[-1]
        assert "resolution" in entry["metadata"]["previous_state"].lower()

    @pytest.mark.asyncio
    async def test_reset_none_company_id_no_error(self):
        state = _make_state(gsd_state=GSDState.CLOSED, company_id=None)
        result = await self.engine.reset_conversation(state)
        assert result.gsd_state == GSDState.NEW


# ══════════════════════════════════════════════════════════════════
# 15. TRANSITION REASONS (10 tests)
# ══════════════════════════════════════════════════════════════════


class TestTransitionReasons:
    """Test get_transition_reason returns detailed explanation."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.asyncio
    async def test_reason_returns_dict(self, base_state):
        reason = await self.engine.get_transition_reason(base_state)
        assert isinstance(reason, dict)

    @pytest.mark.asyncio
    async def test_reason_has_current_state(self, base_state):
        reason = await self.engine.get_transition_reason(base_state)
        assert reason["current_state"] == "new"

    @pytest.mark.asyncio
    async def test_reason_has_recommended_next(self, base_state):
        reason = await self.engine.get_transition_reason(base_state)
        assert "recommended_next_state" in reason

    @pytest.mark.asyncio
    async def test_reason_has_reasoning_chain(self, base_state):
        reason = await self.engine.get_transition_reason(base_state)
        assert "reasoning_chain" in reason
        assert isinstance(reason["reasoning_chain"], list)

    @pytest.mark.asyncio
    async def test_reason_has_signals_snapshot(self, base_state):
        reason = await self.engine.get_transition_reason(base_state)
        assert "signals_snapshot" in reason

    @pytest.mark.asyncio
    async def test_reason_has_escalation_conditions(self, base_state):
        reason = await self.engine.get_transition_reason(base_state)
        assert "escalation_conditions_met" in reason

    @pytest.mark.asyncio
    async def test_reason_diagnosis_has_confidence_step(self):
        state = _make_state(gsd_state=GSDState.DIAGNOSIS, confidence_score=0.8)
        reason = await self.engine.get_transition_reason(state)
        steps = [r.get("step", "") for r in reason["reasoning_chain"]]
        assert "confidence_evaluation" in steps

    @pytest.mark.asyncio
    async def test_reason_has_variant(self, base_state):
        reason = await self.engine.get_transition_reason(base_state)
        assert "variant" in reason

    @pytest.mark.asyncio
    async def test_reason_frustration_above_zero_includes_check(self):
        state = _make_state(gsd_state=GSDState.DIAGNOSIS, frustration_score=50.0, sentiment_score=0.5)
        reason = await self.engine.get_transition_reason(state)
        steps = [r.get("step", "") for r in reason["reasoning_chain"]]
        assert "frustration_check" in steps

    @pytest.mark.asyncio
    async def test_reason_vip_includes_vip_check(self):
        state = _make_state(gsd_state=GSDState.DIAGNOSIS, customer_tier="enterprise")
        reason = await self.engine.get_transition_reason(state)
        steps = [r.get("step", "") for r in reason["reasoning_chain"]]
        assert "vip_check" in steps


# ══════════════════════════════════════════════════════════════════
# 16. EVENT EMISSION (10 tests)
# ══════════════════════════════════════════════════════════════════


class TestEventEmission:
    """Test that transitions emit structured log events."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.asyncio
    async def test_transition_emits_log_event(self, base_state):
        with patch.object(self.engine, "_emit_transition_event", wraps=self.engine._emit_transition_event) as mock_emit:
            await self.engine.transition(base_state, GSDState.GREETING)
            mock_emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_includes_ticket_id(self, base_state):
        with patch.object(self.engine, "_emit_transition_event") as mock_emit:
            await self.engine.transition(base_state, GSDState.GREETING)
            call_kwargs = mock_emit.call_args
            assert call_kwargs.kwargs.get("ticket_id") == "tkt_001" or call_kwargs[1].get("ticket_id") == "tkt_001"

    @pytest.mark.asyncio
    async def test_event_includes_from_state(self, base_state):
        with patch.object(self.engine, "_emit_transition_event") as mock_emit:
            await self.engine.transition(base_state, GSDState.GREETING)
            call_kwargs = mock_emit.call_args[1]
            assert call_kwargs["from_state"] == "new"

    @pytest.mark.asyncio
    async def test_event_includes_to_state(self, base_state):
        with patch.object(self.engine, "_emit_transition_event") as mock_emit:
            await self.engine.transition(base_state, GSDState.GREETING)
            call_kwargs = mock_emit.call_args[1]
            assert call_kwargs["to_state"] == "greeting"

    @pytest.mark.asyncio
    async def test_event_includes_company_id(self, base_state):
        with patch.object(self.engine, "_emit_transition_event") as mock_emit:
            await self.engine.transition(base_state, GSDState.GREETING)
            call_kwargs = mock_emit.call_args[1]
            assert call_kwargs["company_id"] == "co_001"

    @pytest.mark.asyncio
    async def test_event_includes_trigger_reason(self, base_state):
        with patch.object(self.engine, "_emit_transition_event") as mock_emit:
            await self.engine.transition(
                base_state, GSDState.GREETING, trigger_reason="custom_reason"
            )
            call_kwargs = mock_emit.call_args[1]
            assert call_kwargs["trigger_reason"] == "custom_reason"

    @pytest.mark.asyncio
    async def test_event_includes_metadata(self, base_state):
        with patch.object(self.engine, "_emit_transition_event") as mock_emit:
            meta = {"key": "value"}
            await self.engine.transition(base_state, GSDState.GREETING, metadata=meta)
            call_kwargs = mock_emit.call_args[1]
            assert call_kwargs["metadata"] == meta

    @pytest.mark.asyncio
    async def test_transition_event_dataclass(self):
        event = TransitionEvent(
            ticket_id="tkt_001",
            from_state="new",
            to_state="greeting",
            trigger_reason="test",
            timestamp="2025-01-01T00:00:00Z",
            company_id="co_001",
            metadata={"k": "v"},
        )
        assert event.ticket_id == "tkt_001"
        assert event.from_state == "new"
        assert event.to_state == "greeting"

    @pytest.mark.asyncio
    async def test_multiple_transitions_emit_multiple_events(self, base_state):
        with patch.object(self.engine, "_emit_transition_event") as mock_emit:
            await self.engine.transition(base_state, GSDState.GREETING)
            base_state.gsd_state = GSDState.NEW
            await self.engine.transition(base_state, GSDState.GREETING)
            assert mock_emit.call_count == 2

    @pytest.mark.asyncio
    async def test_structlog_called_with_correct_event_name(self, base_state):
        with patch("backend.app.core.gsd_engine.logger") as mock_logger:
            await self.engine.transition(base_state, GSDState.GREETING)
            # logger.info should have been called with "gsd_state_transition"
            assert mock_logger.info.called
            first_call_name = mock_logger.info.call_args[0][0]
            assert first_call_name == "gsd_state_transition"


# ══════════════════════════════════════════════════════════════════
# 17. ERROR HANDLING (10 tests)
# ══════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """Test custom exceptions and graceful error handling."""

    def setup_method(self):
        self.engine = GSDEngine()

    def test_invalid_transition_error_is_gsd_engine_error(self):
        err = InvalidTransitionError("new", "closed", "test")
        assert isinstance(err, GSDEngineError)

    def test_invalid_transition_error_attributes(self):
        err = InvalidTransitionError("new", "closed", "not permitted")
        assert err.from_state == "new"
        assert err.to_state == "closed"
        assert err.reason == "not permitted"

    def test_invalid_transition_error_message(self):
        err = InvalidTransitionError("new", "closed", "test reason")
        assert "new" in str(err)
        assert "closed" in str(err)

    def test_invalid_transition_error_details(self):
        err = InvalidTransitionError("new", "closed", "test")
        assert "from_state" in err.details
        assert "to_state" in err.details
        assert "reason" in err.details

    def test_escalation_cooldown_error_is_gsd_engine_error(self):
        err = EscalationCooldownError(cooldown_remaining_seconds=120.0)
        assert isinstance(err, GSDEngineError)

    def test_escalation_cooldown_error_attributes(self):
        err = EscalationCooldownError(
            cooldown_remaining_seconds=120.0,
            last_escalation_time="2025-01-01T00:00:00Z",
        )
        assert err.cooldown_remaining_seconds == 120.0
        assert err.last_escalation_time == "2025-01-01T00:00:00Z"

    def test_escalation_cooldown_error_message(self):
        err = EscalationCooldownError(cooldown_remaining_seconds=150.5)
        assert "150.5" in str(err)

    def test_gsd_engine_error_default_details(self):
        err = GSDEngineError("test error")
        assert err.details == {}

    def test_gsd_engine_error_custom_details(self):
        err = GSDEngineError("test error", details={"key": "val"})
        assert err.details["key"] == "val"

    @pytest.mark.asyncio
    async def test_invalid_transition_from_none_state(self):
        """Engine should handle edge case gracefully (BC-008)."""
        # gsd_history not being a list should be handled defensively
        state = _make_state(gsd_state=GSDState.NEW)
        state.gsd_history = "not a list"  # type: ignore
        # The _append_history method should handle this
        await self.engine.transition(state, GSDState.GREETING)
        assert state.gsd_state == GSDState.GREETING


# ══════════════════════════════════════════════════════════════════
# 18. EDGE CASES (15 tests)
# ══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.asyncio
    async def test_rapid_transitions(self, base_state):
        """Multiple rapid transitions should all succeed."""
        await self.engine.transition(base_state, GSDState.GREETING)
        await self.engine.transition(base_state, GSDState.DIAGNOSIS)
        await self.engine.transition(base_state, GSDState.RESOLUTION)
        assert base_state.gsd_state == GSDState.RESOLUTION
        assert len(base_state.gsd_history) == 3

    @pytest.mark.asyncio
    async def test_loop_detection_multiple_diagnosis(self):
        """Multiple diagnosis entries should be counted."""
        state = _make_state(gsd_state=GSDState.DIAGNOSIS)
        state.gsd_history = [
            _make_history_entry("diagnosis"),
            _make_history_entry("resolution"),
            _make_history_entry("diagnosis"),
            _make_history_entry("resolution"),
            _make_history_entry("diagnosis"),
        ]
        count = self.engine._count_diagnosis_loops(state)
        assert count >= 3

    @pytest.mark.asyncio
    async def test_empty_query_state(self):
        state = _make_state(gsd_state=GSDState.NEW, query="")
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.GREETING

    @pytest.mark.asyncio
    async def test_very_long_query(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            query="help " * 1000,
            confidence_score=0.8,
        )
        questions = await self.engine.get_diagnostic_questions(state)
        assert isinstance(questions, list)

    @pytest.mark.asyncio
    async def test_recovery_from_human_handoff(self):
        """After HUMAN_HANDOFF, can return to DIAGNOSIS."""
        state = _make_state(gsd_state=GSDState.HUMAN_HANDOFF)
        await self.engine.transition(state, GSDState.DIAGNOSIS)
        assert state.gsd_state == GSDState.DIAGNOSIS
        # Can continue normal flow
        await self.engine.transition(state, GSDState.RESOLUTION)
        assert state.gsd_state == GSDState.RESOLUTION

    @pytest.mark.asyncio
    async def test_multiple_escalations_with_cooldown_expiry(self):
        state = _make_state(
            gsd_state=GSDState.DIAGNOSIS,
            company_id="co_001",
            frustration_score=95.0,
        )
        # First escalation via handle_escalation
        result1 = await self.engine.handle_escalation(state)
        assert result1.gsd_state == GSDState.ESCALATE

        # Manually advance through human_handoff back to diagnosis
        # (bypassing transition() auto-escalation since frustration is still high)
        state.gsd_state = GSDState.HUMAN_HANDOFF
        state.gsd_history.append(_make_history_entry("human_handoff"))
        state.gsd_state = GSDState.DIAGNOSIS
        state.gsd_history.append(_make_history_entry("diagnosis"))

        # Clear cooldown to simulate time passing
        self.engine._escalation_timestamps.pop("co_001", None)

        # Second escalation should succeed
        result2 = await self.engine.handle_escalation(state)
        assert result2.gsd_state == GSDState.ESCALATE

    @pytest.mark.asyncio
    async def test_state_after_escalation_and_recovery(self):
        """Full escalation cycle: DIAGNOSIS → ESCALATE → HUMAN_HANDOFF → DIAGNOSIS → RESOLUTION."""
        state = _make_state(gsd_state=GSDState.DIAGNOSIS, confidence_score=0.8)
        await self.engine.transition(state, GSDState.ESCALATE)
        await self.engine.transition(state, GSDState.HUMAN_HANDOFF)
        await self.engine.transition(state, GSDState.DIAGNOSIS)
        await self.engine.transition(state, GSDState.RESOLUTION)
        assert state.gsd_state == GSDState.RESOLUTION

    @pytest.mark.asyncio
    async def test_transition_with_string_current_state(self):
        """can_transition handles string current state values."""
        result = await self.engine.can_transition("new", "greeting")
        assert result is True

    @pytest.mark.asyncio
    async def test_transition_with_string_target(self):
        result = await self.engine.can_transition(GSDState.NEW, "greeting")
        assert result is True

    @pytest.mark.asyncio
    async def test_none_company_id_in_transition(self):
        state = _make_state(gsd_state=GSDState.NEW, company_id=None)
        result = await self.engine.transition(state, GSDState.GREETING)
        assert result.gsd_state == GSDState.GREETING

    @pytest.mark.asyncio
    async def test_cooldown_invalid_timestamp(self):
        """Invalid timestamp in escalation timestamps should not crash."""
        self.engine._escalation_timestamps["co_001"] = "not-a-timestamp"
        remaining = self.engine._check_escalation_cooldown("co_001", 300.0)
        assert remaining == 0.0

    @pytest.mark.asyncio
    async def test_follow_up_with_question_and_negation(self):
        """Follow-up with '?' and negation should route to DIAGNOSIS."""
        state = _make_state(
            gsd_state=GSDState.FOLLOW_UP,
            query="actually I have a different problem here?",
        )
        next_s = await self.engine.get_next_state(state)
        assert next_s == GSDState.DIAGNOSIS

    @pytest.mark.asyncio
    async def test_state_distribution(self):
        state = _make_state()
        await self.engine.transition(state, GSDState.GREETING)
        await self.engine.transition(state, GSDState.DIAGNOSIS)
        # Manually add another diagnosis entry to simulate a loop
        state.gsd_history.append(_make_history_entry("diagnosis"))
        dist = self.engine._calculate_state_distribution(
            self.engine._get_history_records(state)
        )
        assert dist.get("greeting", 0) >= 1
        assert dist.get("diagnosis", 0) >= 2

    @pytest.mark.asyncio
    async def test_time_in_current_state_no_history(self):
        state = _make_state()
        time_in_state = self.engine._calculate_time_in_current_state([])
        assert time_in_state == 0.0

    @pytest.mark.asyncio
    async def test_time_in_current_state_with_history(self, base_state):
        await self.engine.transition(base_state, GSDState.GREETING)
        time_in_state = self.engine._calculate_time_in_current_state(
            self.engine._get_history_records(base_state)
        )
        assert time_in_state >= 0.0


# ══════════════════════════════════════════════════════════════════
# EXTRA: MODULE CONSTANTS AND DATA CLASSES (15 tests)
# ══════════════════════════════════════════════════════════════════


class TestConstantsAndDataClasses:
    """Test module-level constants and data classes."""

    def test_full_transition_table_completeness(self):
        """All GSDState values should be keys in FULL_TRANSITION_TABLE."""
        for gs in GSDState:
            assert gs.value in FULL_TRANSITION_TABLE, f"{gs.value} missing from FULL_TRANSITION_TABLE"

    def test_mini_transition_table_subset(self):
        """MINI_TRANSITION_TABLE should have same keys as FULL."""
        for key in FULL_TRANSITION_TABLE:
            assert key in MINI_TRANSITION_TABLE

    def test_escalation_eligible_states_no_closed(self):
        assert "closed" not in ESCALATION_ELIGIBLE_STATES
        assert "new" not in ESCALATION_ELIGIBLE_STATES

    def test_legal_intents_non_empty(self):
        assert len(LEGAL_INTENTS) > 0

    def test_satisfaction_phrases_non_empty(self):
        assert len(SATISFACTION_PHRASES) > 0

    def test_new_issue_phrases_non_empty(self):
        assert len(NEW_ISSUE_PHRASES) > 0

    def test_simple_resolution_intents_non_empty(self):
        assert len(SIMPLE_RESOLUTION_INTENTS) > 0

    def test_resolution_time_estimates_have_complexity_keys(self):
        for intent, estimates in RESOLUTION_TIME_ESTIMATES.items():
            assert "low" in estimates
            assert "medium" in estimates
            assert "high" in estimates

    def test_default_resolution_estimate_has_all_keys(self):
        assert "low" in DEFAULT_RESOLUTION_ESTIMATE
        assert "medium" in DEFAULT_RESOLUTION_ESTIMATE
        assert "high" in DEFAULT_RESOLUTION_ESTIMATE

    def test_gsd_config_defaults(self):
        config = GSDConfig()
        assert config.frustration_threshold == 80.0
        assert config.confidence_threshold == 0.6
        assert config.escalation_cooldown_seconds == 300.0
        assert config.max_diagnosis_loops == 3
        assert config.max_history_entries == 100

    def test_gsd_variant_values(self):
        assert GSDVariant.MINI_PARWA.value == "mini_parwa"
        assert GSDVariant.PARWA.value == "parwa"
        assert GSDVariant.PARWA_HIGH.value == "parwa_high"

    def test_gsd_state_enum_count(self):
        assert len(GSDState) == 8

    def test_gsd_state_values(self):
        expected = {"new", "greeting", "diagnosis", "resolution", "follow_up", "closed", "escalate", "human_handoff"}
        assert {gs.value for gs in GSDState} == expected

    def test_get_gsd_engine_singleton(self):
        """get_gsd_engine should return same instance."""
        # Reset singleton
        import backend.app.core.gsd_engine as mod
        mod._default_engine = None
        e1 = get_gsd_engine()
        e2 = get_gsd_engine()
        assert e1 is e2

    @pytest.mark.asyncio
    async def test_convenience_functions(self):
        """Test module-level convenience functions."""
        state = _make_state()
        # Reset singleton to ensure clean state
        import backend.app.core.gsd_engine as mod
        mod._default_engine = None

        result = await transition_state(state, GSDState.GREETING)
        assert result.gsd_state == GSDState.GREETING

        next_s = await get_next_gsd_state(state)
        assert next_s == GSDState.DIAGNOSIS

        can_esc = await should_escalate(state)
        assert isinstance(can_esc, bool)


# ══════════════════════════════════════════════════════════════════
# EXTRA: DEFAULT TRIGGER GENERATION (5 tests)
# ══════════════════════════════════════════════════════════════════


class TestDefaultTrigger:
    """Test _default_trigger helper."""

    def setup_method(self):
        self.engine = GSDEngine()

    def test_new_to_greeting_trigger(self):
        assert self.engine._default_trigger("new", "greeting") == "initial_greeting"

    def test_greeting_to_diagnosis_trigger(self):
        assert self.engine._default_trigger("greeting", "diagnosis") == "user_message_received"

    def test_diagnosis_to_resolution_trigger(self):
        assert self.engine._default_trigger("diagnosis", "resolution") == "intent_classified"

    def test_unknown_pair_returns_manual(self):
        trigger = self.engine._default_trigger("escalate", "new")
        assert "manual_transition" in trigger

    def test_follow_up_to_closed_trigger(self):
        assert self.engine._default_trigger("follow_up", "closed") == "customer_satisfied"


# ══════════════════════════════════════════════════════════════════
# EXTRA: EXPLAIN INVALID TRANSITION (5 tests)
# ══════════════════════════════════════════════════════════════════


class TestExplainInvalidTransition:
    """Test _explain_invalid_transition provides clear messages."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.asyncio
    async def test_explains_missing_state(self):
        state = _make_state()
        reason = await self.engine._explain_invalid_transition("new", "closed", state)
        assert "not permitted" in reason

    @pytest.mark.asyncio
    async def test_explains_variant_restriction_mini(self):
        self.engine.update_config("co_mini", GSDConfig(variant=GSDVariant.MINI_PARWA.value))
        state = _make_state(company_id="co_mini", gsd_state=GSDState.DIAGNOSIS)
        reason = await self.engine._explain_invalid_transition("diagnosis", "escalate", state)
        assert "mini_parwa" in reason

    @pytest.mark.asyncio
    async def test_explains_available_transitions(self):
        state = _make_state(gsd_state=GSDState.NEW)
        reason = await self.engine._explain_invalid_transition("new", "closed", state)
        assert "greeting" in reason

    @pytest.mark.asyncio
    async def test_explains_unknown_target(self):
        state = _make_state()
        reason = await self.engine._explain_invalid_transition("new", "nonexistent", state)
        assert "Unknown target state" in reason

    @pytest.mark.asyncio
    async def test_explains_unknown_from(self):
        state = _make_state()
        reason = await self.engine._explain_invalid_transition("nonexistent", "greeting", state)
        assert "Unknown current state" in reason


# ══════════════════════════════════════════════════════════════════
# EXTRA: SIGNAL EXTRACTION (10 tests)
# ══════════════════════════════════════════════════════════════════


class TestSignalExtraction:
    """Test _extract_signal_data extracts correct signal values."""

    def setup_method(self):
        self.engine = GSDEngine()

    def test_extracts_confidence_score(self):
        state = _make_state(confidence_score=0.85)
        signals = self.engine._extract_signal_data(state)
        assert signals["confidence_score"] == 0.85

    def test_extracts_intent_type(self):
        state = _make_state(intent_type="refund")
        signals = self.engine._extract_signal_data(state)
        assert signals["intent_type"] == "refund"

    def test_extracts_customer_tier(self):
        state = _make_state(customer_tier="enterprise")
        signals = self.engine._extract_signal_data(state)
        assert signals["customer_tier"] == "enterprise"

    def test_extracts_query_complexity(self):
        state = _make_state(query_complexity=0.75)
        signals = self.engine._extract_signal_data(state)
        assert signals["query_complexity"] == 0.75

    def test_frustration_from_technique_results(self):
        state = _make_state(frustration_score=45.0)
        signals = self.engine._extract_signal_data(state)
        assert signals["frustration_score"] == 45.0

    def test_frustration_derived_from_sentiment(self):
        """If no explicit frustration, derive from sentiment_score."""
        state = _make_state(sentiment_score=0.3)
        signals = self.engine._extract_signal_data(state)
        # (1.0 - 0.3) * 100 = 70
        assert abs(signals["frustration_score"] - 70.0) < 0.1

    def test_classification_result_overrides_confidence(self):
        state = _make_state(confidence_score=0.5)
        state.technique_results["intent_classification"] = {
            "status": "success",
            "result": {
                "primary_confidence": 0.95,
                "primary_intent": "billing",
            },
        }
        signals = self.engine._extract_signal_data(state)
        assert signals["confidence_score"] == 0.95
        assert signals["intent_type"] == "billing"

    def test_essential_keys_always_present(self):
        state = _make_state()
        signals = self.engine._extract_signal_data(state)
        essential = [
            "confidence_score", "frustration_score", "intent_type",
            "customer_tier", "query_complexity", "sentiment_score",
            "turn_count", "previous_response_status",
        ]
        for key in essential:
            assert key in signals, f"Missing essential key: {key}"

    def test_default_values_applied(self):
        """State with no signals should get sensible defaults."""
        state = ConversationState(query="test")
        signals = self.engine._extract_signal_data(state)
        assert signals["intent_type"] == "general"
        assert signals["confidence_score"] == 1.0
        assert signals["customer_tier"] == "free"

    def test_none_signals_handled(self):
        state = ConversationState(query="test", signals=None)  # type: ignore
        signals = self.engine._extract_signal_data(state)
        assert isinstance(signals, dict)
        assert "intent_type" in signals


# ══════════════════════════════════════════════════════════════════
# EXTRA: PARAMETRIZED VALID TRANSITIONS (5 tests)
# ══════════════════════════════════════════════════════════════════


class TestParametrizedTransitions:
    """Data-driven transition validation."""

    def setup_method(self):
        self.engine = GSDEngine()

    @pytest.mark.parametrize("current,target", [
        (GSDState.NEW, GSDState.GREETING),
        (GSDState.GREETING, GSDState.DIAGNOSIS),
        (GSDState.DIAGNOSIS, GSDState.RESOLUTION),
        (GSDState.DIAGNOSIS, GSDState.ESCALATE),
        (GSDState.RESOLUTION, GSDState.FOLLOW_UP),
        (GSDState.RESOLUTION, GSDState.CLOSED),
        (GSDState.FOLLOW_UP, GSDState.CLOSED),
        (GSDState.FOLLOW_UP, GSDState.DIAGNOSIS),
        (GSDState.ESCALATE, GSDState.HUMAN_HANDOFF),
        (GSDState.HUMAN_HANDOFF, GSDState.DIAGNOSIS),
        (GSDState.CLOSED, GSDState.NEW),
    ])
    @pytest.mark.asyncio
    async def test_all_valid_transitions_succeed(self, current, target):
        state = _make_state(gsd_state=current)
        result = await self.engine.transition(state, target)
        assert result.gsd_state == target

    @pytest.mark.parametrize("current,target", [
        (GSDState.NEW, GSDState.CLOSED),
        (GSDState.NEW, GSDState.DIAGNOSIS),
        (GSDState.NEW, GSDState.RESOLUTION),
        (GSDState.GREETING, GSDState.CLOSED),
        (GSDState.GREETING, GSDState.GREETING),
        (GSDState.DIAGNOSIS, GSDState.GREETING),
        (GSDState.RESOLUTION, GSDState.DIAGNOSIS),
        (GSDState.CLOSED, GSDState.DIAGNOSIS),
        (GSDState.CLOSED, GSDState.GREETING),
        (GSDState.ESCALATE, GSDState.CLOSED),
    ])
    @pytest.mark.asyncio
    async def test_all_invalid_transitions_fail(self, current, target):
        state = _make_state(gsd_state=current)
        with pytest.raises(InvalidTransitionError):
            await self.engine.transition(state, target)
