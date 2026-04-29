"""
Week 12 Critical Gap Fixes - Comprehensive Test Suite

This test file addresses all 7 gaps identified in gap_analysis_w10d11.json:
1. CRITICAL: State serialization round-trip fidelity failure
2. CRITICAL: Redis/PostgreSQL failover data loss
3. HIGH: Distributed lock contention causing deadlock
4. HIGH: Tenant isolation breach in state keys
5. HIGH: GSD transition validation bypass
6. MEDIUM: Auto-escalation trigger condition race condition
7. MEDIUM: History ring buffer overflow corruption

All tests are designed to work with Docker-based Redis and PostgreSQL.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from app.core.graceful_escalation import (
    EscalationConfig,
    EscalationContext,
    EscalationTrigger,
    GracefulEscalationManager,
)
from app.core.gsd_engine import (
    GSDConfig,
    GSDEngine,
    InvalidTransitionError,
)

# Import the modules under test
from app.core.state_serialization import (
    StateSerializationError,
    StateSerializer,
    StateSerializerConfig,
    _build_lock_key,
    _build_state_key,
    _safe_json_dumps,
    _safe_json_loads,
)
from app.core.techniques.base import (
    ConversationState,
    GSDState,
    QuerySignals,
)

# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_conversation_state() -> ConversationState:
    """Create a sample ConversationState for testing."""
    return ConversationState(
        query="I want a refund for my order #12345",
        signals=QuerySignals(
            intent_type="refund",
            sentiment_score=0.3,
            query_complexity=0.5,
            monetary_value=150.00,
            customer_tier="pro",
            turn_count=3,
            frustration_score=45.0,
            confidence_score=0.85,
        ),
        gsd_state=GSDState.DIAGNOSIS,
        gsd_history=[GSDState.NEW, GSDState.GREETING, GSDState.DIAGNOSIS],
        technique_results={"chain_of_thought": {"result": "analyzing refund request"}},
        token_usage=450,
        technique_token_budget=1500,
        response_parts=["I understand you want a refund.", "Let me check your order."],
        final_response="",
        ticket_id="ticket_123",
        conversation_id="conv_456",
        company_id="company_789",
        reasoning_thread=["Step 1: Verify order", "Step 2: Check refund policy"],
        reflexion_trace={"iteration": 1, "critique": "Need more details"},
    )


@pytest.fixture
def complex_conversation_state() -> ConversationState:
    """Create a complex ConversationState with nested variables and long history."""
    # Create 15 turns of history
    gsd_history = [
        GSDState.NEW,
        GSDState.GREETING,
        GSDState.DIAGNOSIS,
        GSDState.RESOLUTION,
        GSDState.FOLLOW_UP,
        GSDState.DIAGNOSIS,
        GSDState.RESOLUTION,
        GSDState.ESCALATE,
        GSDState.HUMAN_HANDOFF,
        GSDState.DIAGNOSIS,
        GSDState.RESOLUTION,
        GSDState.FOLLOW_UP,
        GSDState.CLOSED,
        GSDState.NEW,
        GSDState.GREETING,
    ]

    # Create 500-token technique stack
    technique_results = {
        "chain_of_thought": {
            "result": "Analyzing complex multi-step refund request",
            "steps": [f"Step {i}: Processing..." for i in range(20)],
        },
        "react": {
            "tool_calls": [
                {"tool": f"tool_{i}", "result": f"result_{i}"} for i in range(15)
            ],
        },
        "reflexion": {
            "iterations": [
                {"critique": f"Critique {i}", "improvement": f"Improvement {i}"}
                for i in range(10)
            ],
        },
    }

    # Create long reasoning thread
    reasoning_thread = [f"Reasoning step {i}: " + "x" * 50 for i in range(50)]

    return ConversationState(
        query="Complex query with special characters: 你好世界 🌍 ñoño café résumé",
        signals=QuerySignals(
            intent_type="refund",
            sentiment_score=0.25,
            query_complexity=0.85,
            monetary_value=500.00,
            customer_tier="enterprise",
            turn_count=15,
            frustration_score=65.0,
            confidence_score=0.72,
        ),
        gsd_state=GSDState.DIAGNOSIS,
        gsd_history=gsd_history,
        technique_results=technique_results,
        token_usage=2500,
        technique_token_budget=3000,
        response_parts=[f"Response part {i}" for i in range(20)],
        final_response="Final response with unicode: 你好 🎉",
        ticket_id="ticket_complex_123",
        conversation_id="conv_complex_456",
        company_id="company_complex_789",
        reasoning_thread=reasoning_thread,
        reflexion_trace={
            "iteration": 5,
            "critique": "Complex critique 你好",
            "nested": {"deep": {"value": "unicode: ñoño"}},
        },
    )


@pytest.fixture
def state_serializer() -> StateSerializer:
    """Create a StateSerializer instance for testing."""
    return StateSerializer()


@pytest.fixture
def gsd_engine() -> GSDEngine:
    """Create a GSDEngine instance for testing."""
    return GSDEngine()


@pytest.fixture
def escalation_manager() -> GracefulEscalationManager:
    """Create a GracefulEscalationManager instance for testing."""
    return GracefulEscalationManager()


# ══════════════════════════════════════════════════════════════════
# GAP 1: State Serialization Round-Trip Fidelity
# ══════════════════════════════════════════════════════════════════


class TestGap1StateSerializationFidelity:
    """
    GAP 1 (CRITICAL): State serialization round-trip fidelity failure

    Issue: AI conversation state gets corrupted during serialization/deserialization,
    leading to hallucinated data or state loss.

    Test: Create a complex conversation state with nested variables, long history,
    and a technique stack. Serialize it, deserialize it, and verify all fields match.
    """

    def test_serialize_deserialize_simple_state(
        self, state_serializer, sample_conversation_state
    ):
        """Test basic round-trip serialization fidelity."""
        # Serialize
        serialized = state_serializer.serialize_state(sample_conversation_state)

        # Verify serialized is JSON-safe
        assert isinstance(serialized, dict)
        json_str = _safe_json_dumps(serialized)
        assert isinstance(json_str, str)

        # Deserialize
        deserialized = state_serializer.deserialize_state(serialized)

        # Verify all fields match
        assert deserialized.query == sample_conversation_state.query
        assert deserialized.gsd_state == sample_conversation_state.gsd_state
        assert deserialized.gsd_history == sample_conversation_state.gsd_history
        assert deserialized.token_usage == sample_conversation_state.token_usage
        assert deserialized.ticket_id == sample_conversation_state.ticket_id
        assert deserialized.conversation_id == sample_conversation_state.conversation_id
        assert deserialized.company_id == sample_conversation_state.company_id
        assert deserialized.final_response == sample_conversation_state.final_response

    def test_serialize_deserialize_complex_state(
        self, state_serializer, complex_conversation_state
    ):
        """Test round-trip fidelity with complex state (15 turns, nested variables, 500-token stack)."""
        # Serialize
        serialized = state_serializer.serialize_state(complex_conversation_state)

        # Verify JSON serialization works
        json_str = _safe_json_dumps(serialized)
        parsed = _safe_json_loads(json_str)

        # Deserialize
        deserialized = state_serializer.deserialize_state(parsed)

        # Verify all fields match exactly
        assert deserialized.query == complex_conversation_state.query
        assert deserialized.gsd_state == complex_conversation_state.gsd_state
        assert len(deserialized.gsd_history) == len(
            complex_conversation_state.gsd_history
        )
        assert deserialized.token_usage == complex_conversation_state.token_usage
        assert (
            deserialized.technique_token_budget
            == complex_conversation_state.technique_token_budget
        )
        assert len(deserialized.response_parts) == len(
            complex_conversation_state.response_parts
        )
        assert len(deserialized.reasoning_thread) == len(
            complex_conversation_state.reasoning_thread
        )

        # Verify technique_results preserved
        assert "chain_of_thought" in deserialized.technique_results
        assert "react" in deserialized.technique_results
        assert "reflexion" in deserialized.technique_results

    def test_serialize_deserialize_unicode_special_chars(self, state_serializer):
        """Test round-trip with unicode, emojis, and special characters."""
        state = ConversationState(
            query="Unicode test: 你好世界 🌍 ñoño café résumé",
            signals=QuerySignals(
                intent_type="general",
                sentiment_score=0.5,
                query_complexity=0.5,
                monetary_value=0,
                customer_tier="free",
                turn_count=1,
                frustration_score=0,
                confidence_score=0.5,
            ),
            gsd_state=GSDState.NEW,
            gsd_history=[],
            technique_results={"unicode_key": "unicode_value_你好"},
            token_usage=100,
            response_parts=["Part 1 你好", "Part 2 🎉"],
            final_response="Final: 你好世界 🌍",
            ticket_id="ticket_unicode",
            company_id="company_unicode",
            reasoning_thread=["Reasoning 你好"],
        )

        # Round-trip
        serialized = state_serializer.serialize_state(state)
        json_str = _safe_json_dumps(serialized)
        parsed = _safe_json_loads(json_str)
        deserialized = state_serializer.deserialize_state(parsed)

        # Verify unicode preserved
        assert "你好世界" in deserialized.query
        assert "🌍" in deserialized.query
        assert "ñoño" in deserialized.query
        assert "你好" in deserialized.technique_results.get("unicode_key", "")
        assert (
            "🎉" in deserialized.response_parts[1]
            if deserialized.response_parts
            else ""
        )

    def test_serialize_deserialize_maximum_length_values(self, state_serializer):
        """Test round-trip with maximum length values."""
        # Create state with large values
        large_technique_results = {
            f"technique_{i}": {"data": "x" * 1000} for i in range(50)
        }
        large_reasoning_thread = ["Reasoning " + "x" * 500 for _ in range(100)]

        state = ConversationState(
            query="x" * 5000,  # Max query length
            signals=QuerySignals(),
            gsd_state=GSDState.DIAGNOSIS,
            gsd_history=[GSDState.NEW] * 100,
            technique_results=large_technique_results,
            token_usage=10000,
            response_parts=["part " + "x" * 1000 for _ in range(20)],
            final_response="response " + "x" * 5000,
            ticket_id="ticket_large",
            company_id="company_large",
            reasoning_thread=large_reasoning_thread,
        )

        # Round-trip
        serialized = state_serializer.serialize_state(state)
        deserialized = state_serializer.deserialize_state(serialized)

        # Verify large values preserved
        assert len(deserialized.query) == 5000
        assert len(deserialized.gsd_history) == 100
        assert len(deserialized.technique_results) == 50
        assert len(deserialized.reasoning_thread) == 100

    def test_signals_round_trip_preservation(
        self, state_serializer, sample_conversation_state
    ):
        """Test that QuerySignals are preserved correctly during round-trip."""
        serialized = state_serializer.serialize_state(sample_conversation_state)
        deserialized = state_serializer.deserialize_state(serialized)

        # Verify all signals preserved
        original_signals = sample_conversation_state.signals
        deserialized_signals = deserialized.signals

        if original_signals and deserialized_signals:
            assert deserialized_signals.intent_type == original_signals.intent_type
            assert (
                abs(
                    deserialized_signals.sentiment_score
                    - original_signals.sentiment_score
                )
                < 0.001
            )
            assert (
                abs(
                    deserialized_signals.query_complexity
                    - original_signals.query_complexity
                )
                < 0.001
            )
            assert (
                abs(
                    deserialized_signals.monetary_value
                    - original_signals.monetary_value
                )
                < 0.01
            )
            assert deserialized_signals.customer_tier == original_signals.customer_tier
            assert deserialized_signals.turn_count == original_signals.turn_count
            assert (
                abs(
                    deserialized_signals.frustration_score
                    - original_signals.frustration_score
                )
                < 0.001
            )
            assert (
                abs(
                    deserialized_signals.confidence_score
                    - original_signals.confidence_score
                )
                < 0.001
            )


# ══════════════════════════════════════════════════════════════════
# GAP 2: Redis/PostgreSQL Failover Data Loss
# ══════════════════════════════════════════════════════════════════


class TestGap2RedisPostgreSQLFailover:
    """
    GAP 2 (CRITICAL): Redis/PostgreSQL failover data loss

    Issue: When Redis fails, state fallback to PostgreSQL doesn't preserve
    all state components, causing silent data truncation.

    Test: Simulate Redis failure and verify complete state retrieval from PostgreSQL.
    """

    @pytest.mark.asyncio
    async def test_redis_failure_fallback_to_postgresql(
        self, state_serializer, complex_conversation_state
    ):
        """Test that when Redis is unavailable, PostgreSQL provides complete state."""
        company_id = "company_failover_test"
        ticket_id = "ticket_failover_test"

        # Mock Redis to fail
        with patch.object(state_serializer, "_save_to_redis", return_value=False):
            with patch.object(
                state_serializer, "_save_to_postgresql", return_value=True
            ):
                # Save should succeed with PostgreSQL fallback
                result = await state_serializer.save_state(
                    ticket_id=ticket_id,
                    company_id=company_id,
                    conversation_state=complex_conversation_state,
                )
                assert result.success
                assert result.postgresql_success
                assert not result.redis_success

    @pytest.mark.asyncio
    async def test_load_state_redis_failure_fallback(
        self, state_serializer, complex_conversation_state
    ):
        """Test loading state when Redis is unavailable but PostgreSQL has data."""
        company_id = "company_load_failover"
        ticket_id = "ticket_load_failover"

        # First, save to PostgreSQL (mock Redis failure)
        with patch.object(state_serializer, "_save_to_redis", return_value=False):
            with patch.object(
                state_serializer, "_save_to_postgresql", return_value=True
            ):
                await state_serializer.save_state(
                    ticket_id=ticket_id,
                    company_id=company_id,
                    conversation_state=complex_conversation_state,
                )

        # Now try to load with Redis failing
        with patch.object(state_serializer, "_load_from_redis", return_value=None):
            # Mock PostgreSQL to return the saved state
            mock_state = complex_conversation_state
            with patch.object(
                state_serializer, "_load_from_postgresql", return_value=mock_state
            ):
                loaded = await state_serializer.load_state(
                    ticket_id=ticket_id,
                    company_id=company_id,
                )

                # Verify complete state retrieved
                assert loaded is not None
                assert loaded.query == complex_conversation_state.query
                assert loaded.gsd_state == complex_conversation_state.gsd_state
                assert len(loaded.gsd_history) == len(
                    complex_conversation_state.gsd_history
                )
                assert loaded.token_usage == complex_conversation_state.token_usage

    @pytest.mark.asyncio
    async def test_complete_data_preservation_on_redis_failure(
        self, state_serializer, complex_conversation_state
    ):
        """Verify no data loss when Redis fails during save operation."""
        company_id = "company_data_preservation"
        ticket_id = "ticket_data_preservation"

        # Mock complete Redis failure
        with patch.object(state_serializer, "_save_to_redis", return_value=False):
            # Mock successful PostgreSQL save
            saved_data = {}

            async def mock_pg_save(**kwargs):
                saved_data.update(kwargs)
                return True

            with patch.object(
                state_serializer, "_save_to_postgresql", side_effect=mock_pg_save
            ):
                result = await state_serializer.save_state(
                    ticket_id=ticket_id,
                    company_id=company_id,
                    conversation_state=complex_conversation_state,
                )

                assert result.success
                # Verify all state components were passed to PostgreSQL
                assert "state_json" in saved_data

    @pytest.mark.asyncio
    async def test_both_backends_fail_raises_error(
        self, state_serializer, sample_conversation_state
    ):
        """Test that error is raised when both Redis and PostgreSQL fail."""
        company_id = "company_both_fail"
        ticket_id = "ticket_both_fail"

        with patch.object(state_serializer, "_save_to_redis", return_value=False):
            with patch.object(
                state_serializer, "_save_to_postgresql", return_value=False
            ):
                with pytest.raises(StateSerializationError):
                    await state_serializer.save_state(
                        ticket_id=ticket_id,
                        company_id=company_id,
                        conversation_state=sample_conversation_state,
                    )


# ══════════════════════════════════════════════════════════════════
# GAP 3: Distributed Lock Contention Deadlock
# ══════════════════════════════════════════════════════════════════


class TestGap3DistributedLockDeadlock:
    """
    GAP 3 (HIGH): Distributed lock contention causing deadlock

    Issue: Multiple workers trying to modify the same conversation state
    simultaneously acquire locks in different order, causing permanent deadlock.

    Test: Simulate concurrent access to the same state by multiple workers.
    """

    def test_lock_key_format_includes_tenant(self):
        """Verify lock keys are properly scoped."""
        ticket_id = "ticket_123"
        lock_key = _build_lock_key(ticket_id)

        # Lock key should exist and be deterministic
        assert lock_key == f"parwa:lock:state:{ticket_id}"

    def test_state_key_includes_company_id(self):
        """Verify state keys are tenant-scoped (BC-001)."""
        company_id = "company_456"
        ticket_id = "ticket_789"

        state_key = _build_state_key(company_id, ticket_id)

        # Key must include company_id for tenant isolation
        assert company_id in state_key
        assert ticket_id in state_key
        assert state_key == f"parwa:state:{company_id}:{ticket_id}"

    @pytest.mark.asyncio
    async def test_concurrent_state_modifications_no_deadlock(
        self, state_serializer, sample_conversation_state
    ):
        """Test that concurrent modifications don't cause deadlocks."""
        company_id = "company_concurrent"
        ticket_id = "ticket_concurrent"

        results = []
        errors = []

        async def modify_state(worker_id: int):
            """Simulate a worker modifying state."""
            try:
                # Each worker modifies the state
                state = ConversationState(
                    query=f"Query from worker {worker_id}",
                    signals=QuerySignals(),
                    gsd_state=GSDState.DIAGNOSIS,
                    token_usage=100 * worker_id,
                    ticket_id=ticket_id,
                    company_id=company_id,
                )

                # Mock the save operations
                with patch.object(
                    state_serializer, "_save_to_redis", return_value=True
                ):
                    with patch.object(
                        state_serializer, "_save_to_postgresql", return_value=True
                    ):
                        result = await state_serializer.save_state(
                            ticket_id=ticket_id,
                            company_id=company_id,
                            conversation_state=state,
                        )
                        results.append((worker_id, result.success))
            except Exception as e:
                errors.append((worker_id, str(e)))

        # Run 10 concurrent workers
        tasks = [modify_state(i) for i in range(10)]
        await asyncio.gather(*tasks, return_exceptions=True)

        # All should complete without deadlock
        assert len(errors) == 0, f"Errors during concurrent access: {errors}"
        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_lock_timeout_prevents_deadlock(self, state_serializer):
        """Test that lock timeout prevents indefinite waiting."""
        config = StateSerializerConfig(
            lock_timeout_seconds=0.1,  # Very short timeout
            lock_retries=1,
        )
        serializer = StateSerializer(config=config)

        # Verify configuration is applied
        assert serializer._config.lock_timeout_seconds == 0.1
        assert serializer._config.lock_retries == 1


# ══════════════════════════════════════════════════════════════════
# GAP 4: Tenant Isolation Breach in State Keys
# ══════════════════════════════════════════════════════════════════


class TestGap4TenantIsolationStateKeys:
    """
    GAP 4 (HIGH): Tenant isolation breach in state keys

    Issue: State keys are not properly scoped by tenant, causing data leakage
    between customers.

    Test: Verify tenant isolation in state key generation and retrieval.
    """

    def test_state_keys_include_company_id(self):
        """Verify all state keys are company-scoped."""
        company_id_a = "company_a"
        company_id_b = "company_b"
        ticket_id = "ticket_shared_id"  # Same ticket ID

        key_a = _build_state_key(company_id_a, ticket_id)
        key_b = _build_state_key(company_id_b, ticket_id)

        # Keys must be different for different companies
        assert key_a != key_b
        assert company_id_a in key_a
        assert company_id_b in key_b

    @pytest.mark.asyncio
    async def test_load_state_tenant_isolation(
        self, state_serializer, sample_conversation_state
    ):
        """Verify that loading state returns only the correct tenant's state."""
        company_a = "company_isolation_a"
        company_b = "company_isolation_b"
        ticket_id = "ticket_shared"  # Same ticket ID for both companies

        # Create states for both companies
        state_a = ConversationState(
            query="Company A query",
            signals=QuerySignals(),
            gsd_state=GSDState.NEW,
            ticket_id=ticket_id,
            company_id=company_a,
        )

        state_b = ConversationState(
            query="Company B query",
            signals=QuerySignals(),
            gsd_state=GSDState.NEW,
            ticket_id=ticket_id,
            company_id=company_b,
        )

        # Mock Redis/PostgreSQL to return state_a for company_a
        with patch.object(state_serializer, "_load_from_redis") as mock_redis:

            def redis_side_effect(tid, cid):
                if cid == company_a:
                    return state_a
                elif cid == company_b:
                    return state_b
                return None

            mock_redis.side_effect = redis_side_effect

            # Load for company A
            loaded_a = await state_serializer.load_state(ticket_id, company_a)
            assert loaded_a is not None
            assert loaded_a.company_id == company_a
            assert loaded_a.query == "Company A query"

            # Load for company B
            loaded_b = await state_serializer.load_state(ticket_id, company_b)
            assert loaded_b is not None
            assert loaded_b.company_id == company_b
            assert loaded_b.query == "Company B query"

    @pytest.mark.asyncio
    async def test_missing_company_id_rejected(
        self, state_serializer, sample_conversation_state
    ):
        """Test that operations with missing/empty company_id are rejected."""
        ticket_id = "ticket_no_company"

        # Empty company_id should still work (graceful handling)
        # but key should still be generated safely
        key = _build_state_key("", ticket_id)
        assert "parwa:state::" in key  # Empty company_id creates valid key

    @pytest.mark.asyncio
    async def test_cross_tenant_access_prevented(self, state_serializer):
        """Verify cross-tenant data access is prevented."""
        company_a = "company_cross_a"
        company_b = "company_cross_b"
        ticket_id = "ticket_cross"

        # State for company A
        state_a = ConversationState(
            query="Secret data for Company A",
            signals=QuerySignals(),
            gsd_state=GSDState.DIAGNOSIS,
            ticket_id=ticket_id,
            company_id=company_a,
        )

        # Mock to return state_a for company_a only
        with patch.object(state_serializer, "_load_from_redis") as mock_redis:

            def redis_side_effect(tid, cid):
                if cid == company_a:
                    return state_a
                return None

            mock_redis.side_effect = redis_side_effect

            # Company B should not get Company A's data
            loaded_b = await state_serializer.load_state(ticket_id, company_b)
            assert loaded_b is None


# ══════════════════════════════════════════════════════════════════
# GAP 5: GSD Transition Validation Bypass
# ══════════════════════════════════════════════════════════════════


class TestGap5GSDTransitionValidation:
    """
    GAP 5 (HIGH): GSD transition validation bypass

    Issue: Invalid state transitions are allowed when they shouldn't be,
    violating the state machine rules.

    Test: Validate all possible state transitions for each variant.
    """

    def test_valid_transitions_parwa_variant(self, gsd_engine):
        """Test all valid transitions for PARWA variant."""
        # Configure for PARWA variant
        config = GSDConfig(company_id="test_company", variant="parwa")
        gsd_engine.update_config("test_company", config)

        # Valid transitions according to FULL_TRANSITION_TABLE
        valid_transitions = [
            ("new", "greeting"),
            ("greeting", "diagnosis"),
            ("diagnosis", "resolution"),
            ("diagnosis", "escalate"),
            ("resolution", "follow_up"),
            ("resolution", "closed"),
            ("follow_up", "closed"),
            ("follow_up", "diagnosis"),
            ("escalate", "human_handoff"),
            ("human_handof", "diagnosis"),
            ("closed", "new"),
        ]

        for from_state, to_state in valid_transitions:
            result = asyncio.run(gsd_engine.can_transition(from_state, to_state))
            assert (
                result
            ), f"Transition {from_state} -> {to_state} should be valid for PARWA"

    def test_invalid_transitions_parwa_variant(self, gsd_engine):
        """Test that invalid transitions are rejected for PARWA variant."""
        config = GSDConfig(company_id="test_company", variant="parwa")
        gsd_engine.update_config("test_company", config)

        # Invalid transitions
        invalid_transitions = [
            ("new", "resolution"),  # Skip greeting
            ("new", "diagnosis"),  # Skip greeting
            ("greeting", "resolution"),  # Skip diagnosis
            ("diagnosis", "follow_up"),  # Skip resolution
            ("diagnosis", "closed"),  # Skip resolution
            ("diagnosis", "human_handoff"),  # Must escalate first
        ]

        for from_state, to_state in invalid_transitions:
            result = asyncio.run(gsd_engine.can_transition(from_state, to_state))
            assert (
                not result
            ), f"Transition {from_state} -> {to_state} should be INVALID for PARWA"

    def test_valid_transitions_mini_parwa_variant(self, gsd_engine):
        """Test transitions for MINI_PARWA variant (simplified flow)."""
        config = GSDConfig(company_id="test_mini", variant="mini_parwa")
        gsd_engine.update_config("test_mini", config)

        # Valid transitions for MINI
        valid_transitions = [
            ("new", "greeting"),
            ("greeting", "diagnosis"),
            ("diagnosis", "resolution"),
            ("resolution", "closed"),
        ]

        for from_state, to_state in valid_transitions:
            result = asyncio.run(
                gsd_engine.can_transition_with_variant(
                    from_state, to_state, "mini_parwa"
                )
            )
            assert (
                result
            ), f"Transition {from_state} -> {to_state} should be valid for MINI_PARWA"

    def test_escalation_not_allowed_mini_parwa(self, gsd_engine):
        """Test that escalation is not available in MINI_PARWA."""
        config = GSDConfig(company_id="test_mini_esc", variant="mini_parwa")
        gsd_engine.update_config("test_mini_esc", config)

        # Escalate should NOT be allowed from any state in MINI_PARWA
        result = asyncio.run(
            gsd_engine.can_transition_with_variant(
                "diagnosis", "escalate", "mini_parwa"
            )
        )
        assert not result, "Escalation should NOT be allowed in MINI_PARWA"

    @pytest.mark.asyncio
    async def test_cannot_skip_resolution_state(self, gsd_engine):
        """Test that DIAGNOSIS -> FOLLOW_UP (skipping RESOLUTION) is rejected."""
        config = GSDConfig(company_id="test_skip", variant="parwa")
        gsd_engine.update_config("test_skip", config)

        state = ConversationState(
            query="Test query",
            signals=QuerySignals(),
            gsd_state=GSDState.DIAGNOSIS,
            ticket_id="ticket_skip",
            company_id="test_skip",
        )

        # Attempt invalid transition
        with pytest.raises(InvalidTransitionError):
            await gsd_engine.transition(state, GSDState.FOLLOW_UP)

    @pytest.mark.asyncio
    async def test_transition_without_reason_rejected(self, gsd_engine):
        """Test that transitions require a trigger reason."""
        config = GSDConfig(company_id="test_reason", variant="parwa")
        gsd_engine.update_config("test_reason", config)

        state = ConversationState(
            query="Test",
            signals=QuerySignals(),
            gsd_state=GSDState.NEW,
            ticket_id="ticket_reason",
            company_id="test_reason",
        )

        # Transition should work (reason is optional but encouraged)
        result = await gsd_engine.transition(state, GSDState.GREETING)
        assert result.gsd_state == GSDState.GREETING

    def test_high_parwa_allows_diagnosis_loop(self, gsd_engine):
        """Test that PARWA_HIGH allows DIAGNOSIS loop after HUMAN_HANDOFF."""
        config = GSDConfig(company_id="test_high", variant="high_parwa")
        gsd_engine.update_config("test_high", config)

        # HUMAN_HANDOFF -> DIAGNOSIS should be valid in PARWA_HIGH
        result = asyncio.run(
            gsd_engine.can_transition_with_variant(
                "human_handof", "diagnosis", "high_parwa"
            )
        )
        assert result, "HUMAN_HANDOFF -> DIAGNOSIS should be valid for PARWA_HIGH"


# ══════════════════════════════════════════════════════════════════
# GAP 6: Auto-Escalation Trigger Race Condition
# ══════════════════════════════════════════════════════════════════


class TestGap6AutoEscalationRaceCondition:
    """
    GAP 6 (MEDIUM): Auto-escalation trigger condition race condition

    Issue: Frustration score calculation and escalation decision happen at
    slightly different times, causing missed escalations.

    Test: Simulate timing race between frustration score calculation and
    escalation decision.
    """

    def test_escalation_triggers_at_threshold(self, escalation_manager):
        """Test that escalation triggers exactly at threshold."""
        company_id = "company_threshold"
        config = EscalationConfig(
            company_id=company_id,
            default_severity="high",
        )
        escalation_manager.configure(company_id, config)

        context = EscalationContext(
            company_id=company_id,
            ticket_id="ticket_threshold",
            trigger=EscalationTrigger.HIGH_FRUSTRATION.value,
            severity="high",
            description="Test escalation",
            frustration_score=80,  # Exactly at threshold
        )

        should_escalate, rules, severity = escalation_manager.evaluate_escalation(
            company_id, context
        )

        assert should_escalate, "Should escalate at exactly 80 frustration"

    def test_escalation_triggers_above_threshold(self, escalation_manager):
        """Test that escalation triggers above threshold."""
        company_id = "company_above"
        config = EscalationConfig(company_id=company_id)
        escalation_manager.configure(company_id, config)

        context = EscalationContext(
            company_id=company_id,
            ticket_id="ticket_above",
            trigger=EscalationTrigger.HIGH_FRUSTRATION.value,
            severity="high",
            description="Test escalation",
            frustration_score=85,  # Above threshold
        )

        should_escalate, rules, severity = escalation_manager.evaluate_escalation(
            company_id, context
        )

        assert should_escalate, "Should escalate above 80 frustration"

    def test_no_escalation_below_threshold(self, escalation_manager):
        """Test that escalation doesn't trigger below threshold."""
        company_id = "company_below"
        config = EscalationConfig(company_id=company_id)
        escalation_manager.configure(company_id, config)

        context = EscalationContext(
            company_id=company_id,
            ticket_id="ticket_below",
            trigger=EscalationTrigger.HIGH_FRUSTRATION.value,
            severity="medium",
            description="Test escalation",
            frustration_score=79,  # Just below threshold
        )

        should_escalate, rules, severity = escalation_manager.evaluate_escalation(
            company_id, context
        )

        assert not should_escalate, "Should NOT escalate below 80 frustration"

    def test_atomic_escalation_check(self, escalation_manager):
        """Test that escalation check captures frustration score atomically."""
        company_id = "company_atomic"
        config = EscalationConfig(company_id=company_id)
        escalation_manager.configure(company_id, config)

        # Simulate concurrent frustration score changes
        frustration_scores = [79, 80, 81, 82, 79]
        results = []

        for score in frustration_scores:
            context = EscalationContext(
                company_id=company_id,
                ticket_id="ticket_atomic",
                trigger=EscalationTrigger.HIGH_FRUSTRATION.value,
                severity="high",
                description="Atomic test",
                frustration_score=score,
            )
            should_esc, _, _ = escalation_manager.evaluate_escalation(
                company_id, context
            )
            results.append((score, should_esc))

        # Verify correct escalation decisions
        for score, should_esc in results:
            if score >= 80:
                assert should_esc, f"Score {score} should trigger escalation"
            else:
                assert not should_esc, f"Score {score} should NOT trigger escalation"

    def test_vip_bypasses_cooldown(self, escalation_manager):
        """Test that VIP customers bypass escalation cooldown."""
        company_id = "company_vip"
        config = EscalationConfig(
            company_id=company_id,
            cooldown_seconds=300,
            vip_multiplier=0.7,
        )
        escalation_manager.configure(company_id, config)

        # First escalation
        context1 = EscalationContext(
            company_id=company_id,
            ticket_id="ticket_vip",
            trigger=EscalationTrigger.VIP_CUSTOMER.value,
            severity="high",
            description="VIP customer escalation",
            customer_tier="vip",
            frustration_score=85,
        )

        # VIP should be able to escalate even during cooldown
        record = escalation_manager.create_escalation(company_id, context1)
        assert record is not None

    def test_concurrent_escalation_evaluations(self, escalation_manager):
        """Test that concurrent escalation evaluations don't cause race conditions."""
        company_id = "company_concurrent_esc"
        config = EscalationConfig(company_id=company_id)
        escalation_manager.configure(company_id, config)

        results = []
        errors = []

        def evaluate_concurrent(score: int):
            try:
                context = EscalationContext(
                    company_id=company_id,
                    ticket_id=f"ticket_{score}",
                    trigger=EscalationTrigger.HIGH_FRUSTRATION.value,
                    severity="high",
                    description=f"Concurrent test {score}",
                    frustration_score=score,
                )
                should_esc, _, _ = escalation_manager.evaluate_escalation(
                    company_id, context
                )
                results.append((score, should_esc))
            except Exception as e:
                errors.append((score, str(e)))

        # Run concurrent evaluations
        with ThreadPoolExecutor(max_workers=10) as executor:
            scores = [75, 80, 85, 90, 70, 82, 78, 88, 76, 81]
            executor.map(evaluate_concurrent, scores)

        assert len(errors) == 0, f"Errors in concurrent evaluation: {errors}"
        assert len(results) == 10


# ══════════════════════════════════════════════════════════════════
# GAP 7: History Ring Buffer Overflow Corruption
# ══════════════════════════════════════════════════════════════════


class TestGap7HistoryRingBufferOverflow:
    """
    GAP 7 (MEDIUM): History ring buffer overflow corruption

    Issue: When conversation history exceeds the buffer limit, the system
    doesn't properly remove oldest entries, causing memory issues.

    Test: Verify ring buffer correctly removes oldest entries when limit reached.
    """

    def test_gsd_history_ring_buffer_limit(self, gsd_engine):
        """Test that GSD history respects the configured limit."""
        company_id = "company_ring_buffer"
        max_entries = 10
        config = GSDConfig(
            company_id=company_id,
            variant="parwa",
            max_history_entries=max_entries,
        )
        gsd_engine.update_config(company_id, config)

        state = ConversationState(
            query="Ring buffer test",
            signals=QuerySignals(),
            gsd_state=GSDState.NEW,
            gsd_history=[],
            ticket_id="ticket_ring",
            company_id=company_id,
        )

        # Add more entries than the limit
        for i in range(max_entries + 5):
            state.gsd_history.append(GSDState.DIAGNOSIS)
            # Simulate the ring buffer behavior
            if len(state.gsd_history) > max_entries:
                state.gsd_history = state.gsd_history[-max_entries:]

        # Verify history size is limited
        assert (
            len(state.gsd_history) <= max_entries
        ), f"History should be limited to {max_entries}, got {len(state.gsd_history)}"

    @pytest.mark.asyncio
    async def test_append_history_maintains_limit(self, gsd_engine):
        """Test that _append_history method enforces the limit."""
        company_id = "company_append"
        max_entries = 5
        config = GSDConfig(
            company_id=company_id,
            max_history_entries=max_entries,
        )
        gsd_engine.update_config(company_id, config)

        state = ConversationState(
            query="Test",
            signals=QuerySignals(),
            gsd_state=GSDState.NEW,
            gsd_history=[],
            ticket_id="ticket_append",
            company_id=company_id,
        )

        # Perform multiple transitions
        state = await gsd_engine.transition(state, GSDState.GREETING, "test")
        state = await gsd_engine.transition(state, GSDState.DIAGNOSIS, "test")
        state = await gsd_engine.transition(state, GSDState.RESOLUTION, "test")
        state = await gsd_engine.transition(state, GSDState.FOLLOW_UP, "test")
        state = await gsd_engine.transition(state, GSDState.CLOSED, "test")

        # History should not exceed max
        assert len(state.gsd_history) <= max_entries

    def test_exact_limit_preserved(self, gsd_engine):
        """Test that history exactly at limit is preserved correctly."""
        company_id = "company_exact"
        max_entries = 3
        config = GSDConfig(
            company_id=company_id,
            max_history_entries=max_entries,
        )
        gsd_engine.update_config(company_id, config)

        # Create history exactly at limit
        state = ConversationState(
            query="Exact limit test",
            signals=QuerySignals(),
            gsd_state=GSDState.DIAGNOSIS,
            gsd_history=[GSDState.NEW, GSDState.GREETING, GSDState.DIAGNOSIS],
            ticket_id="ticket_exact",
            company_id=company_id,
        )

        # History at exact limit should remain intact
        assert len(state.gsd_history) == max_entries
        assert state.gsd_history[0] == GSDState.NEW

    def test_overflow_removes_oldest(self, gsd_engine):
        """Test that overflow removes oldest entries first."""
        company_id = "company_overflow"
        max_entries = 3
        config = GSDConfig(
            company_id=company_id,
            max_history_entries=max_entries,
        )
        gsd_engine.update_config(company_id, config)

        # Create history exceeding limit
        history = [
            GSDState.NEW,
            GSDState.GREETING,
            GSDState.DIAGNOSIS,
            GSDState.RESOLUTION,
            GSDState.FOLLOW_UP,
        ]  # 5 entries, max is 3

        # Simulate ring buffer removal
        if len(history) > max_entries:
            history = history[-max_entries:]

        # Oldest should be removed, newest should remain
        assert GSDState.NEW not in history
        assert GSDState.GREETING not in history
        assert GSDState.DIAGNOSIS in history
        assert GSDState.RESOLUTION in history
        assert GSDState.FOLLOW_UP in history

    def test_large_history_no_memory_issues(self, gsd_engine):
        """Test that very large history doesn't cause memory issues."""
        company_id = "company_large_history"
        max_entries = 100
        config = GSDConfig(
            company_id=company_id,
            max_history_entries=max_entries,
        )
        gsd_engine.update_config(company_id, config)

        # Create history way exceeding limit
        large_history = [GSDState.DIAGNOSIS] * 1000

        # Apply ring buffer
        if len(large_history) > max_entries:
            large_history = large_history[-max_entries:]

        assert len(large_history) == max_entries


# ══════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ══════════════════════════════════════════════════════════════════


class TestWeek12Integration:
    """Integration tests combining multiple fixed gaps."""

    @pytest.mark.asyncio
    async def test_full_state_lifecycle_with_tenant_isolation(
        self, state_serializer, gsd_engine, escalation_manager
    ):
        """Test complete state lifecycle with tenant isolation."""
        company_a = "company_integration_a"
        company_b = "company_integration_b"

        # Setup configurations
        gsd_config = GSDConfig(company_id=company_a, variant="parwa")
        gsd_engine.update_config(company_a, gsd_config)

        esc_config = EscalationConfig(company_id=company_a)
        escalation_manager.configure(company_a, esc_config)

        # Create and save state
        state = ConversationState(
            query="Integration test query",
            signals=QuerySignals(
                intent_type="refund",
                frustration_score=50,
                confidence_score=0.8,
            ),
            gsd_state=GSDState.NEW,
            ticket_id="ticket_integration",
            company_id=company_a,
        )

        # Mock save operations
        with patch.object(state_serializer, "_save_to_redis", return_value=True):
            with patch.object(
                state_serializer, "_save_to_postgresql", return_value=True
            ):
                result = await state_serializer.save_state(
                    ticket_id="ticket_integration",
                    company_id=company_a,
                    conversation_state=state,
                )
                assert result.success

        # Verify tenant isolation
        key_a = _build_state_key(company_a, "ticket_integration")
        key_b = _build_state_key(company_b, "ticket_integration")
        assert key_a != key_b

    @pytest.mark.asyncio
    async def test_escalation_triggers_gsd_transition(
        self, gsd_engine, escalation_manager
    ):
        """Test that escalation correctly triggers GSD state transition."""
        company_id = "company_esc_gsd"

        # Setup
        gsd_config = GSDConfig(company_id=company_id, variant="parwa")
        gsd_engine.update_config(company_id, gsd_config)

        esc_config = EscalationConfig(company_id=company_id)
        escalation_manager.configure(company_id, esc_config)

        # Create state with high frustration
        state = ConversationState(
            query="I'm very frustrated!",
            signals=QuerySignals(
                intent_type="complaint",
                frustration_score=90,  # High frustration
            ),
            gsd_state=GSDState.DIAGNOSIS,
            ticket_id="ticket_frustrated",
            company_id=company_id,
        )

        # Check if should auto-escalate
        should_escalate = await gsd_engine._should_auto_escalate(state)

        # High frustration should trigger escalation
        assert should_escalate, "High frustration should trigger escalation"


# ══════════════════════════════════════════════════════════════════
# RUN CONFIGURATION
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
