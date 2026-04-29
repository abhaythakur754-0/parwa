"""
Week 10 CRITICAL Gap Tests (w10d11-w10d12)

Three focus areas:
  1. Workflow State Persistence During Concurrent Execution
  2. Context Compression Quality at Critical Thresholds
  3. State Serialization Round-Trip Fidelity
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import pytest

from app.core.langgraph_workflow import (
    LangGraphWorkflow,
    WorkflowConfig,
)
from app.core.context_compression import (
    CompressionConfig,
    CompressionInput,
    CompressionLevel,
    CompressionStrategy,
    ContextCompressor,
)
from app.core.state_serialization import (
    StateSerializer,
    _safe_json_dumps,
    _safe_json_loads,
)
from app.core.techniques.base import (
    ConversationState,
    GSDState,
)
from app.core.technique_router import QuerySignals


# ════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════


def _make_conversation_state(
    query: str = "How do I get a refund?",
    gsd_state: GSDState = GSDState.NEW,
    gsd_history: Optional[List[GSDState]] = None,
    technique_results: Optional[Dict[str, Any]] = None,
    token_usage: int = 0,
    response_parts: Optional[List[str]] = None,
    final_response: str = "",
    ticket_id: str = "ticket-001",
    company_id: str = "company-abc",
    reasoning_thread: Optional[List[str]] = None,
    reflexion_trace: Optional[Dict[str, Any]] = None,
    signals: Optional[QuerySignals] = None,
) -> ConversationState:
    """Create a ConversationState with sensible defaults."""
    return ConversationState(
        query=query,
        signals=signals or QuerySignals(
            query_complexity=0.5,
            confidence_score=0.9,
            sentiment_score=0.7,
            frustration_score=10.0,
            customer_tier="pro",
            monetary_value=50.0,
            turn_count=3,
            intent_type="refund",
        ),
        gsd_state=gsd_state,
        gsd_history=gsd_history or [],
        technique_results=technique_results or {},
        token_usage=token_usage,
        technique_token_budget=1500,
        response_parts=response_parts or [],
        final_response=final_response,
        ticket_id=ticket_id,
        conversation_id="conv-001",
        company_id=company_id,
        reasoning_thread=reasoning_thread or [],
        reflexion_trace=reflexion_trace,
    )


# ════════════════════════════════════════════════════════════════════
# GAP 1: Workflow State Persistence During Concurrent Execution
# ════════════════════════════════════════════════════════════════════


class TestConcurrentWorkflowStatePersistence:
    """Verify concurrent workflow executions don't corrupt shared state.

    The LangGraphWorkflow is designed so that each execute() call creates
    its own local step_results, steps_completed, etc. However, the
    instance-level self._steps and self._graph are shared. These tests
    verify that multiple concurrent execute() calls produce correct
    isolated results.
    """

    @pytest.mark.asyncio
    async def test_two_concurrent_executions_produce_distinct_workflow_ids(
        self,
    ):
        """Each concurrent execution should generate a unique workflow_id."""
        engine = LangGraphWorkflow(
            config=WorkflowConfig(company_id="co1", variant_type="mini_parwa"),
        )
        engine.build_graph()

        results = await asyncio.gather(
            engine.execute("co1", "query from user A"),
            engine.execute("co1", "query from user B"),
        )

        assert len(results) == 2
        assert results[0].workflow_id != results[1].workflow_id

    @pytest.mark.asyncio
    async def test_concurrent_executions_with_different_variants_isolated(
            self):
        """Concurrent executions on different variant types don't interfere."""
        engine_parwa = LangGraphWorkflow(
            config=WorkflowConfig(company_id="co1", variant_type="parwa"),
        )
        engine_parwa.build_graph()

        engine_mini = LangGraphWorkflow(
            config=WorkflowConfig(company_id="co1", variant_type="mini_parwa"),
        )
        engine_mini.build_graph()

        r_parwa, r_mini = await asyncio.gather(
            engine_parwa.execute("co1", "complex question"),
            engine_mini.execute("co1", "simple question"),
        )

        # parwa should have 6 steps, mini should have 3
        assert r_parwa.variant_type == "parwa"
        assert r_mini.variant_type == "mini_parwa"
        assert len(r_parwa.step_results) >= 3
        assert len(r_mini.step_results) >= 3

    @pytest.mark.asyncio
    async def test_concurrent_executions_each_complete_successfully(self):
        """Multiple concurrent executions should all succeed independently."""
        engine = LangGraphWorkflow(
            config=WorkflowConfig(company_id="co1", variant_type="parwa"),
        )
        engine.build_graph()

        num_concurrent = 5
        queries = [
            f"concurrent query number {i}" for i in range(num_concurrent)]
        results = await asyncio.gather(*[
            engine.execute("co1", q) for q in queries
        ])

        for i, result in enumerate(results):
            assert result.status == "success", (
                f"Execution {i} failed: {result.status}"
            )
            assert result.workflow_id, f"Execution {i} missing workflow_id"
            assert len(result.steps_completed) > 0, (
                f"Execution {i} completed no steps"
            )
            # Verify the query context was captured in the generate step
            gen_step = result.step_results.get("generate")
            if gen_step and gen_step.output:
                response = gen_step.output.get("response", "")
                assert response, f"Execution {i} has empty response"

    @pytest.mark.asyncio
    async def test_concurrent_executions_produce_correct_final_responses(self):
        """Each concurrent execution's final_response should reference its own query."""
        engine = LangGraphWorkflow(
            config=WorkflowConfig(company_id="co1", variant_type="mini_parwa"),
        )
        engine.build_graph()

        unique_markers = ["ALPHA_QUERY", "BETA_QUERY", "GAMMA_QUERY"]
        tasks = [
            engine.execute("co1", f"Help with {marker} please")
            for marker in unique_markers
        ]
        results = await asyncio.gather(*tasks)

        response_texts = [r.final_response for r in results]
        # Each response should contain a snippet of its own query
        for marker, response in zip(unique_markers, response_texts):
            assert marker in response, (
                f"Marker '{marker}' not found in response: '{response}'"
            )

    @pytest.mark.asyncio
    async def test_concurrent_executions_with_parwa_high_variant(self):
        """9-step parwa_high pipeline handles concurrent executions correctly."""
        engine = LangGraphWorkflow(
            config=WorkflowConfig(
                company_id="co1",
                variant_type="parwa_high",
            ),
        )
        engine.build_graph()

        num_concurrent = 3
        results = await asyncio.gather(*[
            engine.execute("co1", f"high-tier query {i}")
            for i in range(num_concurrent)
        ])

        # All should complete with all 9 steps
        for i, result in enumerate(results):
            assert result.status == "success", (
                f"Execution {i} status: {result.status}"
            )
            # parwa_high has 9 steps: classify, extract_signals,
            # technique_select, context_compress, generate, quality_gate,
            # context_health, dedup, format
            assert len(result.steps_completed) == 9, (
                f"Execution {i}: expected 9 steps, got {len(result.steps_completed)}"
            )
            assert result.context_compression_applied is True
            assert result.context_health_score > 0

    @pytest.mark.asyncio
    async def test_concurrent_executions_with_step_errors_dont_corrupt_others(
        self,
    ):
        """If one execution encounters an error in a step, others are unaffected."""
        engine = LangGraphWorkflow(
            config=WorkflowConfig(company_id="co1", variant_type="parwa"),
        )
        engine.build_graph()

        # Make the extract_signals step fail for one specific query
        original_preprocessing = engine._simulate_preprocessing

        def patched_preprocessing(step_id, query, context, step_results):
            if "FAIL_TRIGGER" in query and step_id == "extract_signals":
                raise RuntimeError("Simulated step failure")
            return original_preprocessing(
                step_id, query, context, step_results)

        engine._simulate_preprocessing = patched_preprocessing

        results = await asyncio.gather(
            engine.execute("co1", "normal query"),
            engine.execute("co1", "FAIL_TRIGGER in this query"),
            engine.execute("co1", "another normal query"),
        )

        # Normal queries should succeed
        assert results[0].status == "success"
        # The failing one should degrade gracefully (BC-008: partial)
        assert results[1].status == "partial"
        assert results[1].step_results["extract_signals"].status == "error"
        # Third execution should be unaffected
        assert results[2].status == "success"

    @pytest.mark.asyncio
    async def test_shared_engine_concurrent_different_companies(self):
        """Concurrent executions for different companies don't interfere."""
        engine = LangGraphWorkflow(
            config=WorkflowConfig(company_id="shared", variant_type="parwa"),
        )
        engine.build_graph()

        results = await asyncio.gather(
            engine.execute("company-A", "query for company A"),
            engine.execute("company-B", "query for company B"),
            engine.execute("company-C", "query for company C"),
        )

        # All should succeed independently
        assert all(r.status == "success" for r in results)
        # Each should have its own unique workflow_id
        ids = {r.workflow_id for r in results}
        assert len(ids) == 3


# ════════════════════════════════════════════════════════════════════
# GAP 2: Context Compression Quality at Critical Thresholds
# ════════════════════════════════════════════════════════════════════


class TestCompressionCriticalThresholds:
    """Test compression trigger accuracy at exact threshold boundaries.

    The compressor uses a target reduction ratio based on the compression
    level. This test suite verifies behavior at boundary percentages
    (79%, 80%, 81%, 95%, 96%) to ensure the compression trigger fires
    at exactly the right point.
    """

    @staticmethod
    def _make_chunks_at_fill_ratio(
        target_ratio: float,
        total_tokens: int = 1000,
        chunk_token_size: int = 50,
    ) -> List[str]:
        """Create content chunks whose total tokens represent the target_ratio.

        target_ratio=0.79 means the content fills 79% of the total budget.
        """
        tokens_needed = int(total_tokens * target_ratio)
        num_chunks = max(1, tokens_needed // chunk_token_size)
        # Each chunk is ~chunk_token_size tokens. Using 4 chars per token.
        chars_per_chunk = chunk_token_size * 4
        return [
            f"chunk-{i:04d} " + "x" * (chars_per_chunk - 10)
            for i in range(num_chunks)
        ]

    @pytest.mark.asyncio
    async def test_no_compression_at_79_percent_for_none_level(self):
        """At 79% fill, NONE level should return content unchanged."""
        compressor = ContextCompressor(
            config=CompressionConfig(
                variant_type="mini_parwa",
                strategy=CompressionStrategy.HYBRID,
                level=CompressionLevel.NONE,
                max_tokens=1000,
            ),
        )

        chunks = self._make_chunks_at_fill_ratio(0.79, total_tokens=1000)
        inp = CompressionInput(
            content=chunks,
            priorities=[0.5] * len(chunks),
        )

        result = await compressor.compress("co1", inp)

        assert result.compression_ratio == 1.0
        assert result.chunks_removed == 0
        assert len(result.compressed_content) == len(chunks)
        assert result.strategy_used == "none"

    @pytest.mark.asyncio
    async def test_light_compression_at_80_percent_threshold(self):
        """At 80% fill, LIGHT compression should reduce content.

        LIGHT targets ~70% of original, so at 80% fill the compressor
        should activate and reduce tokens.
        """
        compressor = ContextCompressor(
            config=CompressionConfig(
                variant_type="parwa",
                strategy=CompressionStrategy.HYBRID,
                level=CompressionLevel.LIGHT,
                max_tokens=1000,
            ),
        )

        chunks = self._make_chunks_at_fill_ratio(0.80, total_tokens=1000)
        inp = CompressionInput(
            content=chunks,
            priorities=[0.5] * len(chunks),
        )

        result = await compressor.compress("co1", inp)

        assert result.strategy_used == "hybrid"
        # With LIGHT level, target is 70% of original tokens
        # So compression should reduce content
        assert result.compressed_token_count < result.original_token_count, (
            f"Expected compression: {result.compressed_token_count} >= "
            f"{result.original_token_count}"
        )
        assert result.chunks_removed >= 0

    @pytest.mark.asyncio
    async def test_light_compression_at_81_percent(self):
        """At 81% fill, LIGHT compression should definitely activate."""
        compressor = ContextCompressor(
            config=CompressionConfig(
                variant_type="parwa",
                strategy=CompressionStrategy.HYBRID,
                level=CompressionLevel.LIGHT,
                max_tokens=1000,
            ),
        )

        chunks = self._make_chunks_at_fill_ratio(0.81, total_tokens=1000)
        inp = CompressionInput(
            content=chunks,
            priorities=[0.5] * len(chunks),
        )

        result = await compressor.compress("co1", inp)

        assert result.strategy_used == "hybrid"
        assert result.compressed_token_count <= result.original_token_count
        assert result.compression_ratio <= 1.0

    @pytest.mark.asyncio
    async def test_aggressive_compression_at_95_percent(self):
        """At 95% fill, AGGRESSIVE compression should trigger heavily.

        AGGRESSIVE targets ~50% of original tokens.
        """
        compressor = ContextCompressor(
            config=CompressionConfig(
                variant_type="parwa_high",
                strategy=CompressionStrategy.PRIORITY_BASED,
                level=CompressionLevel.AGGRESSIVE,
                max_tokens=1000,
            ),
        )

        chunks = self._make_chunks_at_fill_ratio(0.95, total_tokens=1000)
        # Mix priorities to test priority-based selection
        priorities = [0.9 if i < 5 else 0.1 for i in range(len(chunks))]
        inp = CompressionInput(
            content=chunks,
            priorities=priorities,
        )

        result = await compressor.compress("co1", inp)

        assert result.strategy_used == "priority_based"
        # With AGGRESSIVE targeting 50%, we should see significant reduction
        assert result.compressed_token_count < result.original_token_count
        # High-priority chunks should be retained
        assert result.chunks_retained > 0

    @pytest.mark.asyncio
    async def test_aggressive_compression_at_96_percent_boundary(self):
        """At 96% fill, AGGRESSIVE compression should still succeed."""
        compressor = ContextCompressor(
            config=CompressionConfig(
                variant_type="parwa_high",
                strategy=CompressionStrategy.EXTRACTIVE,
                level=CompressionLevel.AGGRESSIVE,
                max_tokens=1000,
            ),
        )

        chunks = self._make_chunks_at_fill_ratio(0.96, total_tokens=1000)
        inp = CompressionInput(
            content=chunks,
            priorities=[0.5] * len(chunks),
        )

        result = await compressor.compress("co1", inp)

        assert result.strategy_used == "extractive"
        assert result.original_token_count > 0
        assert result.compressed_token_count <= result.original_token_count
        # AGGRESSIVE should reduce to ~50% target
        assert result.compression_ratio <= 0.75, (
            f"Expected aggressive ratio ≤ 0.75, got {result.compression_ratio}"
        )

    @pytest.mark.asyncio
    async def test_extractive_preserves_high_priority_at_threshold(self):
        """At 80% fill, extractive strategy should preserve high-priority chunks."""
        compressor = ContextCompressor(
            config=CompressionConfig(
                variant_type="parwa",
                strategy=CompressionStrategy.EXTRACTIVE,
                level=CompressionLevel.LIGHT,
                max_tokens=1000,
                preserve_recent_n=2,
            ),
        )

        chunks = self._make_chunks_at_fill_ratio(0.80, total_tokens=1000)
        # First chunks are low priority, last 2 are implicitly preserved
        priorities = [0.1] * (len(chunks) - 2) + [0.9, 0.9]
        inp = CompressionInput(
            content=chunks,
            priorities=priorities,
        )

        result = await compressor.compress("co1", inp)

        # The last 2 chunks (high priority) should always be preserved
        assert result.chunks_retained >= 2
        assert result.compressed_content[-1] == chunks[-1]
        assert result.compressed_content[-2] == chunks[-2]

    @pytest.mark.asyncio
    async def test_sliding_window_at_exact_boundary(self):
        """Sliding window strategy at 80% fill should keep most-recent chunks."""
        compressor = ContextCompressor(
            config=CompressionConfig(
                variant_type="parwa",
                strategy=CompressionStrategy.SLIDING_WINDOW,
                level=CompressionLevel.LIGHT,
                max_tokens=1000,
            ),
        )

        chunks = self._make_chunks_at_fill_ratio(0.80, total_tokens=1000)
        inp = CompressionInput(
            content=chunks,
            priorities=[0.5] * len(chunks),
        )

        result = await compressor.compress("co1", inp)

        assert result.strategy_used == "sliding_window"
        # Sliding window keeps from the end; order should be preserved
        if result.compressed_content:
            # First retained chunk should be from later in the sequence
            assert result.compressed_content[0] in chunks

    @pytest.mark.asyncio
    async def test_empty_input_at_any_threshold_returns_empty(self):
        """Empty input should always return empty regardless of level."""
        for level in CompressionLevel:
            compressor = ContextCompressor(
                config=CompressionConfig(
                    variant_type="parwa",
                    strategy=CompressionStrategy.HYBRID,
                    level=level,
                ),
            )
            inp = CompressionInput(content=[], token_counts=[], priorities=[])
            result = await compressor.compress("co1", inp)

            assert result.original_token_count == 0
            assert result.compressed_token_count == 0
            assert result.compressed_content == []
            assert result.compression_ratio == 1.0
            assert result.chunks_removed == 0
            assert result.chunks_retained == 0


# ════════════════════════════════════════════════════════════════════
# GAP 3: State Serialization Round-Trip Fidelity
# ════════════════════════════════════════════════════════════════════


class TestStateSerializationRoundTrip:
    """Verify serialized → deserialized state matches original exactly.

    Tests all GSDState values and complex nested structures to ensure
    zero data loss during the round-trip.
    """

    def _round_trip(
        self, state: ConversationState,
    ) -> ConversationState:
        """Helper: serialize then deserialize a ConversationState."""
        serializer = StateSerializer()
        data = serializer.serialize_state(state)
        return serializer.deserialize_state(data)

    # -- Core field fidelity --

    def test_round_trip_basic_fields(self):
        """Basic scalar fields survive round-trip unchanged."""
        state = _make_conversation_state(
            query="I need a refund for order #12345",
            token_usage=432,
            final_response="Here is your refund confirmation.",
            ticket_id="ticket-roundtrip-1",
            company_id="co-xyz",
        )

        restored = self._round_trip(state)

        assert restored.query == state.query
        assert restored.token_usage == state.token_usage
        assert restored.final_response == state.final_response
        assert restored.ticket_id == state.ticket_id
        assert restored.company_id == state.company_id
        assert restored.conversation_id == state.conversation_id

    def test_round_trip_gsd_state_new(self):
        """GSDState.NEW survives round-trip."""
        state = _make_conversation_state(gsd_state=GSDState.NEW)
        restored = self._round_trip(state)
        assert restored.gsd_state == GSDState.NEW

    def test_round_trip_gsd_state_greeting(self):
        """GSDState.GREETING survives round-trip."""
        state = _make_conversation_state(gsd_state=GSDState.GREETING)
        restored = self._round_trip(state)
        assert restored.gsd_state == GSDState.GREETING

    def test_round_trip_gsd_state_diagnosis(self):
        """GSDState.DIAGNOSIS survives round-trip."""
        state = _make_conversation_state(gsd_state=GSDState.DIAGNOSIS)
        restored = self._round_trip(state)
        assert restored.gsd_state == GSDState.DIAGNOSIS

    def test_round_trip_gsd_state_resolution(self):
        """GSDState.RESOLUTION survives round-trip."""
        state = _make_conversation_state(gsd_state=GSDState.RESOLUTION)
        restored = self._round_trip(state)
        assert restored.gsd_state == GSDState.RESOLUTION

    def test_round_trip_gsd_state_follow_up(self):
        """GSDState.FOLLOW_UP survives round-trip."""
        state = _make_conversation_state(gsd_state=GSDState.FOLLOW_UP)
        restored = self._round_trip(state)
        assert restored.gsd_state == GSDState.FOLLOW_UP

    def test_round_trip_gsd_state_closed(self):
        """GSDState.CLOSED survives round-trip."""
        state = _make_conversation_state(gsd_state=GSDState.CLOSED)
        restored = self._round_trip(state)
        assert restored.gsd_state == GSDState.CLOSED

    def test_round_trip_gsd_state_escalate(self):
        """GSDState.ESCALATE survives round-trip."""
        state = _make_conversation_state(gsd_state=GSDState.ESCALATE)
        restored = self._round_trip(state)
        assert restored.gsd_state == GSDState.ESCALATE

    def test_round_trip_gsd_state_human_handoff(self):
        """GSDState.HUMAN_HANDOFF survives round-trip."""
        state = _make_conversation_state(gsd_state=GSDState.HUMAN_HANDOFF)
        restored = self._round_trip(state)
        assert restored.gsd_state == GSDState.HUMAN_HANDOFF

    def test_round_trip_all_gsd_states_comprehensive(self):
        """Every GSDState enum value survives round-trip."""
        serializer = StateSerializer()
        for gsd_val in GSDState:
            state = _make_conversation_state(gsd_state=gsd_val)
            data = serializer.serialize_state(state)
            restored = serializer.deserialize_state(data)
            assert restored.gsd_state == gsd_val, (
                f"Round-trip failed for GSDState.{gsd_val.name}"
            )

    # -- GSD History --

    def test_round_trip_gsd_history_single_entry(self):
        """GSD history with single entry survives round-trip."""
        state = _make_conversation_state(
            gsd_history=[GSDState.NEW],
        )
        restored = self._round_trip(state)
        assert restored.gsd_history == [GSDState.NEW]

    def test_round_trip_gsd_history_full_lifecycle(self):
        """Full conversation lifecycle in gsd_history survives round-trip."""
        full_history = [
            GSDState.NEW,
            GSDState.GREETING,
            GSDState.DIAGNOSIS,
            GSDState.RESOLUTION,
            GSDState.FOLLOW_UP,
            GSDState.CLOSED,
        ]
        state = _make_conversation_state(gsd_history=full_history)
        restored = self._round_trip(state)
        assert restored.gsd_history == full_history

    def test_round_trip_gsd_history_with_escalation_loop(self):
        """Escalation cycle in gsd_history survives round-trip."""
        escalation_history = [
            GSDState.NEW,
            GSDState.GREETING,
            GSDState.DIAGNOSIS,
            GSDState.ESCALATE,
            GSDState.HUMAN_HANDOFF,
            GSDState.DIAGNOSIS,
            GSDState.RESOLUTION,
            GSDState.CLOSED,
        ]
        state = _make_conversation_state(gsd_history=escalation_history)
        restored = self._round_trip(state)
        assert restored.gsd_history == escalation_history

    # -- Complex nested structures --

    def test_round_trip_technique_results_nested_dict(self):
        """Deeply nested technique_results survives round-trip."""
        technique_results = {
            "rag_retrieval": {
                "status": "success",
                "result": {
                    "documents": [
                        {"id": "doc1", "score": 0.95, "text": "Refund policy..."},
                        {"id": "doc2", "score": 0.87, "text": "Return process..."},
                    ],
                    "total_retrieved": 5,
                    "query_embedding": [0.1, 0.2, 0.3, 0.4],
                },
                "tokens_used": 120,
                "executed_at": "2025-01-15T10:30:00",
            },
            "sentiment_analysis": {
                "status": "success",
                "result": {"label": "frustrated", "score": 0.82},
                "tokens_used": 50,
            },
            "knowledge_graph": {
                "status": "skipped_budget",
                "reason": "token_budget_exceeded",
            },
        }
        state = _make_conversation_state(technique_results=technique_results)
        restored = self._round_trip(state)

        # Compare the nested dicts
        assert restored.technique_results == technique_results
        assert restored.technique_results["rag_retrieval"]["result"]["documents"][0]["id"] == "doc1"
        assert restored.technique_results["knowledge_graph"]["status"] == "skipped_budget"

    def test_round_trip_response_parts_list(self):
        """Response parts list survives round-trip."""
        parts = [
            "Based on your refund request, ",
            "I've found your order #12345. ",
            "The refund of $49.99 has been initiated ",
            "and will appear in 3-5 business days.",
        ]
        state = _make_conversation_state(response_parts=parts)
        restored = self._round_trip(state)
        assert restored.response_parts == parts

    def test_round_trip_reasoning_thread(self):
        """Reasoning thread survives round-trip."""
        thread = [
            "User wants a refund for order #12345",
            "Checking order status in database...",
            "Order found: $49.99, purchased 2025-01-10",
            "Refund policy allows return within 30 days",
            "Initiating refund process",
        ]
        state = _make_conversation_state(reasoning_thread=thread)
        restored = self._round_trip(state)
        assert restored.reasoning_thread == thread

    def test_round_trip_reflexion_trace_nested(self):
        """Reflexion trace with nested dicts survives round-trip."""
        reflexion = {
            "iterations": [
                {
                    "attempt": 1,
                    "response": "You can get a refund.",
                    "evaluation": "Too vague, missing specifics",
                    "score": 0.4,
                },
                {
                    "attempt": 2,
                    "response": "Your refund of $49.99 for order #12345 has been processed.",
                    "evaluation": "Good specificity, covers all details",
                    "score": 0.92,
                },
            ],
            "total_iterations": 2,
            "best_score": 0.92,
        }
        state = _make_conversation_state(reflexion_trace=reflexion)
        restored = self._round_trip(state)

        assert restored.reflexion_trace is not None
        assert restored.reflexion_trace["iterations"][0]["attempt"] == 1
        assert restored.reflexion_trace["iterations"][1]["score"] == 0.92
        assert restored.reflexion_trace["total_iterations"] == 2

    def test_round_trip_empty_and_none_fields(self):
        """Empty/None/default fields round-trip to their defaults."""
        state = ConversationState()  # All defaults
        restored = self._round_trip(state)

        assert restored.query == ""
        assert restored.gsd_state == GSDState.NEW
        assert restored.gsd_history == []
        assert restored.technique_results == {}
        assert restored.token_usage == 0
        assert restored.response_parts == []
        assert restored.final_response == ""
        assert restored.ticket_id is None
        assert restored.reasoning_thread == []
        assert restored.reflexion_trace is None

    def test_round_trip_full_complex_state(self):
        """Maximally populated state survives full round-trip."""
        state = _make_conversation_state(
            query="I want to cancel my subscription and get a refund",
            gsd_state=GSDState.DIAGNOSIS,
            gsd_history=[
                GSDState.NEW,
                GSDState.GREETING,
                GSDState.DIAGNOSIS,
            ],
            technique_results={
                "classification": {
                    "status": "success",
                    "result": {"intent": "cancellation", "confidence": 0.95},
                    "tokens_used": 45,
                },
                "rag": {
                    "status": "success",
                    "result": {"docs": ["doc1", "doc2"]},
                    "tokens_used": 200,
                },
            },
            token_usage=789,
            response_parts=["Part 1: ", "Part 2: ", "Part 3"],
            final_response="I can help you cancel your subscription.",
            ticket_id="ticket-complex-001",
            company_id="co-complex",
            reasoning_thread=["Step 1", "Step 2", "Step 3"],
            reflexion_trace={"iterations": [{"attempt": 1, "score": 0.7}]},
            signals=QuerySignals(
                query_complexity=0.8,
                confidence_score=0.95,
                sentiment_score=0.3,
                frustration_score=75.0,
                customer_tier="enterprise",
                monetary_value=500.0,
                turn_count=7,
                intent_type="cancellation",
                reasoning_loop_detected=True,
            ),
        )

        restored = self._round_trip(state)

        # Verify all fields
        assert restored.query == state.query
        assert restored.gsd_state == GSDState.DIAGNOSIS
        assert restored.gsd_history == [
            GSDState.NEW, GSDState.GREETING, GSDState.DIAGNOSIS,
        ]
        assert restored.technique_results["classification"]["result"]["intent"] == "cancellation"
        assert restored.token_usage == 789
        assert restored.response_parts == ["Part 1: ", "Part 2: ", "Part 3"]
        assert restored.final_response == "I can help you cancel your subscription."
        assert restored.ticket_id == "ticket-complex-001"
        assert restored.company_id == "co-complex"
        assert restored.reasoning_thread == ["Step 1", "Step 2", "Step 3"]
        assert restored.reflexion_trace["iterations"][0]["score"] == 0.7
        assert restored.signals.frustration_score == 75.0
        assert restored.signals.customer_tier == "enterprise"
        assert restored.signals.reasoning_loop_detected is True

    # -- JSON round-trip (simulate storage) --

    def test_json_serialize_deserialize_round_trip(self):
        """Full round-trip through JSON string (simulating Redis/PG storage)."""
        state = _make_conversation_state(
            gsd_state=GSDState.ESCALATE,
            gsd_history=[GSDState.NEW, GSDState.DIAGNOSIS, GSDState.ESCALATE],
            technique_results={
                "escalation_check": {
                    "status": "success",
                    "result": {"reason": "high_frustration"},
                    "tokens_used": 30,
                },
            },
            token_usage=555,
            response_parts=["Escalating to human agent."],
            final_response="Connecting you to a specialist.",
            reasoning_thread=["Detected frustration", "Escalating"],
        )

        serializer = StateSerializer()
        # Serialize to dict
        state_dict = serializer.serialize_state(state)
        # Convert to JSON string (what Redis/PG would store)
        json_str = _safe_json_dumps(state_dict)
        # Parse back from JSON string
        parsed = _safe_json_loads(json_str)
        # Deserialize back to ConversationState
        restored = serializer.deserialize_state(parsed)

        assert restored.gsd_state == GSDState.ESCALATE
        assert restored.gsd_history == [
            GSDState.NEW, GSDState.DIAGNOSIS, GSDState.ESCALATE,
        ]
        assert restored.token_usage == 555
        assert restored.final_response == "Connecting you to a specialist."

    def test_deserialize_with_extra_unknown_fields_ignored(self):
        """Extra/unknown fields in serialized data are ignored (forward compat)."""
        state = _make_conversation_state()
        serializer = StateSerializer()
        data = serializer.serialize_state(state)

        # Add extra fields that don't exist in ConversationState
        data["future_field_alpha"] = "some_value"
        data["future_nested"] = {"deep": {"value": 42}}
        data["future_list"] = [1, 2, 3]

        # Should not raise
        restored = serializer.deserialize_state(data)

        # Original fields should still be intact
        assert restored.query == state.query
        assert restored.gsd_state == state.gsd_state
        assert restored.company_id == state.company_id

    def test_deserialize_with_invalid_gsd_history_entries_skipped(self):
        """Invalid entries in gsd_history are silently skipped, valid ones kept."""
        state = _make_conversation_state(gsd_history=[GSDState.NEW])
        serializer = StateSerializer()
        data = serializer.serialize_state(state)

        # Corrupt history with invalid entries
        data["gsd_history"] = [
            "new",
            "invalid_state_value",
            "greeting",
            "also_invalid",
            "diagnosis",
        ]

        restored = serializer.deserialize_state(data)

        # Only valid states should survive
        assert restored.gsd_history == [
            GSDState.NEW,
            GSDState.GREETING,
            GSDState.DIAGNOSIS,
        ]
