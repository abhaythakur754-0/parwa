"""Unit tests for Phase 4: GSD Compressor, Smart Router, Memory techniques.

Tests cover:
  - GSD compression and decompression
  - GSD compression ratio targets
  - Smart Router model selection logic
  - Smart Router variant-based routing
  - ThoT (Thread of Thought) technique
  - Dynamic Context technique
  - Contextual Compression technique
  - FrameworkBrain integration with memory techniques
  - Wired feedback_loop node with ThoT
"""

import pytest
from unittest.mock import patch

from parwa.frameworks.base import TechniqueCategory, TechniqueResult
from parwa.frameworks.registry import get_registry, reset_registry
from parwa.frameworks.brain import FrameworkBrain


# ─── GSD Compressor Tests ────────────────────────────────────────────────────

class TestGSDCompressor:

    def test_compress_state_returns_dict(self):
        from parwa.gsd import compress_state
        state = {"raw_message": "I was charged twice", "intent": "refund_request", "quality_score": 85.0}
        compressed = compress_state(state)
        assert isinstance(compressed, dict)
        assert compressed.get("_gsd_compressed") is True

    def test_compress_preserves_critical_fields(self):
        from parwa.gsd import compress_state
        state = {
            "raw_message": "I was charged twice",
            "intent": "refund_request",
            "quality_score": 85.0,
            "reasoning_conclusion": "Eligible for refund",
            "verification_passed": True,
        }
        compressed = compress_state(state)
        assert compressed["raw_message"] == "I was charged twice"
        assert compressed["intent"] == "refund_request"
        assert compressed["quality_score"] == 85.0
        assert compressed["reasoning_conclusion"] == "Eligible for refund"

    def test_compress_summarizes_lists(self):
        from parwa.gsd import compress_state
        state = {
            "reasoning_chain": ["Step 1", "Step 2", "Step 3", "Step 4"],
            "kb_results": [{"content": "Doc 1"}, {"content": "Doc 2"}],
        }
        compressed = compress_state(state)
        # reasoning_chain should be summarized (count + first + last)
        assert isinstance(compressed["reasoning_chain"], dict)
        assert compressed["reasoning_chain"]["count"] == 4
        assert compressed["reasoning_chain"]["_gsd_summary"] is True

    def test_compress_reduces_size(self):
        from parwa.gsd import compress_state, get_compression_ratio
        state = {
            "raw_message": "test",
            "intent": "refund_request",
            "reasoning_chain": [f"Step {i}: " + "x" * 200 for i in range(10)],
            "kb_results": [{"content": "x" * 500} for _ in range(5)],
            "quality_score": 85.0,
        }
        ratio = get_compression_ratio(state)
        assert ratio < 1.0  # Should be smaller than original

    def test_decompress_marks_state(self):
        from parwa.gsd import compress_state, decompress_state, is_compressed
        state = {"raw_message": "test", "intent": "refund_request"}
        compressed = compress_state(state)
        assert is_compressed(compressed) is True
        assert is_compressed(state) is False

    def test_decompress_without_original(self):
        from parwa.gsd import compress_state, decompress_state
        state = {"raw_message": "test", "intent": "refund_request", "quality_score": 85.0}
        compressed = compress_state(state)
        decompressed = decompress_state(compressed)
        assert decompressed["raw_message"] == "test"
        assert decompressed["quality_score"] == 85.0

    def test_compress_empty_state(self):
        from parwa.gsd import compress_state
        compressed = compress_state({})
        assert isinstance(compressed, dict)

    def test_compress_with_nested_data(self):
        from parwa.gsd import compress_state
        state = {
            "raw_message": "test",
            "integration_data": {"orders": [{"id": 1}, {"id": 2}], "charges": [49.99, 49.99]},
            "reverse_validation": {"passed": True, "trace": "x" * 500},
        }
        compressed = compress_state(state)
        assert compressed["raw_message"] == "test"
        # integration_data should be truncated
        assert isinstance(compressed.get("integration_data"), (str, dict))

    def test_get_compression_ratio_empty(self):
        from parwa.gsd import get_compression_ratio
        # Empty state — compressed version adds metadata so ratio = 1.0 (no reduction)
        ratio = get_compression_ratio({})
        assert ratio <= 1.0  # At minimum, shouldn't exceed 1.0


# ─── Smart Router Tests ──────────────────────────────────────────────────────

class TestSmartRouter:

    def test_simple_nodes_use_mini_model(self):
        from parwa.utils.llm import smart_route_model
        assert smart_route_model("INGEST") == "gpt-4o-mini"
        assert smart_route_model("INTENT_CLASSIFIER") == "gpt-4o-mini"
        assert smart_route_model("SENTIMENT_ANALYZER") == "gpt-4o-mini"

    def test_reasoning_nodes_use_better_model(self):
        from parwa.utils.llm import smart_route_model
        assert smart_route_model("REASONING_ENGINE") == "gpt-4o"
        assert smart_route_model("TREE_OF_THOUGHTS") == "gpt-4o"
        assert smart_route_model("QUALITY_SCORER") == "gpt-4o"

    def test_mini_variant_always_cheap(self):
        from parwa.utils.llm import smart_route_model
        # Even reasoning nodes should use gpt-4o-mini for mini variant
        assert smart_route_model("REASONING_ENGINE", variant="mini") == "gpt-4o-mini"
        assert smart_route_model("TREE_OF_THOUGHTS", variant="mini") == "gpt-4o-mini"

    def test_critical_complexity_uses_best_model(self):
        from parwa.utils.llm import smart_route_model
        # Unknown node with critical complexity → o1-preview
        assert smart_route_model("UNKNOWN_NODE", complexity="critical") == "o1-preview"

    def test_simple_complexity_default(self):
        from parwa.utils.llm import smart_route_model
        assert smart_route_model("UNKNOWN_NODE", complexity="simple") == "gpt-4o-mini"

    def test_frameworkbrain_nodes_routed(self):
        from parwa.utils.llm import smart_route_model
        assert smart_route_model("FRAMEWORKBRAIN_COT") == "gpt-4o"
        assert smart_route_model("FRAMEWORKBRAIN_REACT") == "gpt-4o"
        assert smart_route_model("FRAMEWORKBRAIN_CLARA") == "gpt-4o"

    def test_all_22_nodes_have_model_assignment(self):
        from parwa.utils.llm import smart_route_model, _NODE_MODEL_OVERRIDES
        expected_nodes = [
            "INGEST", "INTENT_CLASSIFIER", "SENTIMENT_ANALYZER", "ESCALATION_DECISION",
            "FAQ_MATCHER", "KB_RETRIEVER", "CONTEXT_MANAGER", "INTEGRATION_LOOKUP",
            "REASONING_ENGINE", "REVERSE_THINKER", "TREE_OF_THOUGHTS", "STRATEGY_PLANNER",
            "ACTION_PLANNER", "ACTION_EXECUTOR", "ACTION_VERIFIER",
            "PROACTIVE_CHECKER", "PREDICTION_ENGINE", "FEEDBACK_LOOP",
            "PII_COMPLIANCE_GUARD", "AUDIT_LOGGER", "QUALITY_SCORER", "RESPONSE_FORMATTER",
        ]
        for node in expected_nodes:
            model = smart_route_model(node)
            assert model in ("gpt-4o-mini", "gpt-4o", "o1-preview"), f"Node {node} got unexpected model {model}"


# ─── ThoT (Thread of Thought) Tests ──────────────────────────────────────────

class TestThreadOfThoughtTechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_thot_produces_result(self):
        from parwa.frameworks.memory.thot import ThreadOfThoughtTechnique
        technique = ThreadOfThoughtTechnique()
        result = await technique.think(
            "Build reasoning thread",
            {
                "reasoning_chain": ["Step 1: Analyzed", "Step 2: Concluded"],
                "reasoning_conclusion": "Eligible for refund",
                "reverse_validation": {"passed": True},
                "quality_score": 85.0,
            },
        )
        assert isinstance(result, TechniqueResult)
        assert "thread_of_thought" in result.frameworks_used
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_thot_builds_thread(self):
        from parwa.frameworks.memory.thot import ThreadOfThoughtTechnique
        technique = ThreadOfThoughtTechnique()
        result = await technique.think(
            "Build thread",
            {
                "reasoning_chain": ["Step 1", "Step 2"],
                "reasoning_conclusion": "Refund eligible",
                "reverse_validation": {"passed": True},
                "quality_score": 92.0,
            },
        )
        thread = result.metadata["thread_entries"]
        assert len(thread) > 0
        assert result.metadata["has_conclusion"] is True
        assert result.metadata["validated"] is True

    @pytest.mark.asyncio
    async def test_thot_name_and_category(self):
        from parwa.frameworks.memory.thot import ThreadOfThoughtTechnique
        technique = ThreadOfThoughtTechnique()
        assert technique.name == "thread_of_thought"
        assert technique.category == TechniqueCategory.MEMORY

    @pytest.mark.asyncio
    async def test_thot_requires_medium(self):
        from parwa.frameworks.memory.thot import ThreadOfThoughtTechnique
        technique = ThreadOfThoughtTechnique()
        assert technique.can_apply("FEEDBACK_LOOP", "simple") is False
        assert technique.can_apply("FEEDBACK_LOOP", "medium") is True

    @pytest.mark.asyncio
    async def test_thot_compresses_long_thread(self):
        from parwa.frameworks.memory.thot import ThreadOfThoughtTechnique
        technique = ThreadOfThoughtTechnique()
        result = await technique.think(
            "Build thread",
            {
                "reasoning_chain": [f"Step {i}" for i in range(15)],
                "reasoning_conclusion": "Conclusion",
                "reverse_validation": {},
                "quality_score": 50.0,
            },
        )
        # Should have compressed the thread
        assert result.metadata["thread_length"] > 0

    @pytest.mark.asyncio
    async def test_thot_handles_empty_state(self):
        from parwa.frameworks.memory.thot import ThreadOfThoughtTechnique
        technique = ThreadOfThoughtTechnique()
        result = await technique.think("Test", {})
        assert result.confidence > 0
        assert result.output != ""


# ─── Dynamic Context Tests ───────────────────────────────────────────────────

class TestDynamicContextTechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_dynamic_context_produces_result(self):
        from parwa.frameworks.memory.dynamic_context import DynamicContextTechnique
        technique = DynamicContextTechnique()
        result = await technique.think(
            "Plan context",
            {"complexity": "simple"},
        )
        assert isinstance(result, TechniqueResult)
        assert "dynamic_context" in result.frameworks_used
        assert result.metadata["window_size"] > 0

    @pytest.mark.asyncio
    async def test_dynamic_context_variant_windows(self):
        from parwa.frameworks.memory.dynamic_context import DynamicContextTechnique
        technique = DynamicContextTechnique()

        # Mini gets smaller windows
        result_mini = await technique.think("test", {"complexity": "simple"}, variant="mini")
        result_high = await technique.think("test", {"complexity": "simple"}, variant="high")
        assert result_mini.metadata["window_size"] < result_high.metadata["window_size"]

    @pytest.mark.asyncio
    async def test_dynamic_context_complexity_windows(self):
        from parwa.frameworks.memory.dynamic_context import DynamicContextTechnique
        technique = DynamicContextTechnique()

        result_simple = await technique.think("test", {"complexity": "simple"}, variant="parwa")
        result_critical = await technique.think("test", {"complexity": "critical"}, variant="parwa")
        assert result_simple.metadata["window_size"] < result_critical.metadata["window_size"]

    @pytest.mark.asyncio
    async def test_dynamic_context_name_and_category(self):
        from parwa.frameworks.memory.dynamic_context import DynamicContextTechnique
        technique = DynamicContextTechnique()
        assert technique.name == "dynamic_context"
        assert technique.category == TechniqueCategory.MEMORY

    @pytest.mark.asyncio
    async def test_dynamic_context_activates_on_simple(self):
        from parwa.frameworks.memory.dynamic_context import DynamicContextTechnique
        technique = DynamicContextTechnique()
        assert technique.can_apply("REASONING_ENGINE", "simple") is True

    @pytest.mark.asyncio
    async def test_dynamic_context_prioritizes(self):
        from parwa.frameworks.memory.dynamic_context import DynamicContextTechnique
        technique = DynamicContextTechnique()
        result = await technique.think(
            "Plan context",
            {"complexity": "medium", "raw_message": "test"},
            variant="parwa",
        )
        priorities = result.metadata["priority_order"]
        assert priorities[0] == "raw_message"  # Customer's words first


# ─── Contextual Compression Tests ────────────────────────────────────────────

class TestContextualCompressionTechnique:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_compression_produces_result(self):
        from parwa.frameworks.memory.contextual_compression import ContextualCompressionTechnique
        technique = ContextualCompressionTechnique()
        result = await technique.think(
            "Compress docs",
            {"kb_results": [{"content": "Refund policy allows full refunds within 30 days"}], "faq_match": None},
        )
        assert isinstance(result, TechniqueResult)
        assert "contextual_compression" in result.frameworks_used

    @pytest.mark.asyncio
    async def test_compression_reduces_tokens(self):
        from parwa.frameworks.memory.contextual_compression import ContextualCompressionTechnique
        technique = ContextualCompressionTechnique()
        result = await technique.think(
            "Compress",
            {"kb_results": [{"content": "x" * 500}], "faq_match": {"content": "y" * 300}},
        )
        assert result.metadata["compressed_tokens"] < result.metadata["original_tokens"]
        assert result.metadata["reduction_pct"] > 0

    @pytest.mark.asyncio
    async def test_compression_name_and_category(self):
        from parwa.frameworks.memory.contextual_compression import ContextualCompressionTechnique
        technique = ContextualCompressionTechnique()
        assert technique.name == "contextual_compression"
        assert technique.category == TechniqueCategory.MEMORY

    @pytest.mark.asyncio
    async def test_compression_activates_on_simple(self):
        from parwa.frameworks.memory.contextual_compression import ContextualCompressionTechnique
        technique = ContextualCompressionTechnique()
        assert technique.can_apply("KB_RETRIEVER", "simple") is True

    @pytest.mark.asyncio
    async def test_compression_empty_kb(self):
        from parwa.frameworks.memory.contextual_compression import ContextualCompressionTechnique
        technique = ContextualCompressionTechnique()
        result = await technique.think("Compress", {"kb_results": [], "faq_match": None})
        assert result.output != ""
        assert result.confidence > 0


# ─── Feedback Loop Integration (Phase 4) ────────────────────────────────────

class TestFeedbackLoopPhase4:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_feedback_loop_uses_brain(self):
        from parwa.nodes.feedback_loop import feedback_loop
        result = await feedback_loop({
            "intent": "refund_request",
            "quality_score": 85.0,
            "verification_passed": True,
            "recommendation": None,
            "complexity": "medium",
            "active_frameworks": [],
        })
        assert isinstance(result["feedback_signal"], dict)
        assert isinstance(result.get("active_frameworks", []), list)

    @pytest.mark.asyncio
    async def test_feedback_loop_brain_failure_fallback(self):
        from parwa.nodes.feedback_loop import feedback_loop
        with patch("parwa.nodes.feedback_loop._feedback_with_brain", side_effect=RuntimeError("Crash")):
            result = await feedback_loop({
                "intent": "refund_request",
                "quality_score": 85.0,
                "verification_passed": True,
                "recommendation": None,
                "active_frameworks": [],
            })
        assert isinstance(result["feedback_signal"], dict)

    @pytest.mark.asyncio
    async def test_feedback_loop_tracks_frameworks(self):
        from parwa.nodes.feedback_loop import feedback_loop
        result = await feedback_loop({
            "intent": "refund_request",
            "quality_score": 85.0,
            "verification_passed": True,
            "recommendation": None,
            "complexity": "medium",
            "active_frameworks": [],
        })
        assert isinstance(result.get("active_frameworks", []), list)


# ─── FrameworkBrain + Phase 4 Memory Techniques ──────────────────────────────

class TestFrameworkBrainPhase4:

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_brain_with_memory_techniques(self):
        brain = FrameworkBrain(
            node="FEEDBACK_LOOP",
            state={"complexity": "medium", "intent": "refund_request"},
        )
        result = await brain.think(
            prompt="Build feedback thread",
            techniques=["thread_of_thought", "dynamic_context"],
        )
        assert len(result.frameworks_used) >= 1

    @pytest.mark.asyncio
    async def test_brain_with_compression_on_kb_retriever(self):
        brain = FrameworkBrain(
            node="KB_RETRIEVER",
            state={"complexity": "simple", "intent": "order_status"},
        )
        result = await brain.think(
            prompt="Compress KB results",
            techniques=["contextual_compression", "dynamic_context"],
        )
        # Both should activate on simple
        assert "contextual_compression" in result.frameworks_used
        assert "dynamic_context" in result.frameworks_used

    @pytest.mark.asyncio
    async def test_registry_has_all_phase4_techniques(self):
        registry = get_registry()
        assert registry.get("thread_of_thought") is not None
        assert registry.get("dynamic_context") is not None
        assert registry.get("contextual_compression") is not None
        # Total: 6 reasoning + 4 RAG + 4 quality + 3 memory = 17
        assert registry.count() == 20
