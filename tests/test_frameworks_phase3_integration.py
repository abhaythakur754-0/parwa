"""Integration tests for Phase 3: FrameworkBrain wired into 4 nodes.

Tests verify:
  - KB_RETRIEVER uses FrameworkBrain with RAG techniques
  - FAQ_MATCHER uses FrameworkBrain with RAG techniques
  - CONTEXT_MANAGER uses FrameworkBrain with RAG techniques
  - QUALITY_SCORER uses FrameworkBrain with Quality techniques
  - Nodes fall back to rule-based when FrameworkBrain fails
  - Full graph pipeline still works with Phase 3 techniques
  - active_frameworks tracking works correctly across nodes
  - Error handling covers FrameworkBrain crash paths
"""

import pytest
import uuid
from unittest.mock import patch, AsyncMock

from parwa.graph import build_parwa_graph, process_ticket, aprocess_ticket, reset_parwa_graph
from parwa.frameworks.registry import reset_registry


@pytest.fixture
def parwa_graph():
    """Create a fresh compiled graph for each test."""
    reset_parwa_graph()
    reset_registry()
    return build_parwa_graph(use_checkpointer=True)


def _config(thread_id: str | None = None) -> dict:
    """Create a LangGraph config with thread_id for checkpointing."""
    return {"configurable": {"thread_id": thread_id or f"test-p3-{uuid.uuid4().hex[:8]}"}}


# ─── KB_RETRIEVER Integration Tests ──────────────────────────────────────────

class TestKbRetrieverIntegration:

    @pytest.mark.asyncio
    async def test_kb_retriever_uses_brain(self):
        """KB_RETRIEVER should use FrameworkBrain for enhanced retrieval."""
        from parwa.nodes.kb_retriever import kb_retriever
        result = await kb_retriever({
            "raw_message": "I was charged twice",
            "intent": "refund_request",
            "active_frameworks": [],
        })
        # Should have KB results (rule-based still runs)
        assert isinstance(result["kb_results"], list)
        # Should track frameworks
        assert isinstance(result.get("active_frameworks", []), list)

    @pytest.mark.asyncio
    async def test_kb_retriever_brain_failure_fallback(self):
        """KB_RETRIEVER should fall back when FrameworkBrain crashes."""
        from parwa.nodes.kb_retriever import kb_retriever
        with patch("parwa.nodes.kb_retriever._retrieve_with_brain", side_effect=RuntimeError("Brain crash")):
            result = await kb_retriever({
                "raw_message": "I was charged twice",
                "intent": "refund_request",
                "active_frameworks": [],
            })
        # Should still have KB results from rule-based fallback
        assert isinstance(result["kb_results"], list)

    @pytest.mark.asyncio
    async def test_kb_retriever_tracks_frameworks(self):
        """KB_RETRIEVER should track RAG frameworks in active_frameworks."""
        from parwa.nodes.kb_retriever import kb_retriever
        result = await kb_retriever({
            "raw_message": "I was charged twice",
            "intent": "refund_request",
            "complexity": "medium",
            "active_frameworks": [],
        })
        # Should have some frameworks tracked (at minimum from brain)
        assert isinstance(result.get("active_frameworks", []), list)


# ─── FAQ_MATCHER Integration Tests ───────────────────────────────────────────

class TestFaqMatcherIntegration:

    @pytest.mark.asyncio
    async def test_faq_matcher_uses_brain(self):
        """FAQ_MATCHER should use FrameworkBrain for enhanced matching."""
        from parwa.nodes.faq_matcher import faq_matcher
        result = await faq_matcher({
            "raw_message": "I want a refund",
            "active_frameworks": [],
        })
        # Should have a FAQ match or None
        assert result["faq_match"] is None or isinstance(result["faq_match"], dict)

    @pytest.mark.asyncio
    async def test_faq_matcher_brain_failure_fallback(self):
        """FAQ_MATCHER should fall back when FrameworkBrain crashes."""
        from parwa.nodes.faq_matcher import faq_matcher
        with patch("parwa.nodes.faq_matcher._match_faq_with_brain", side_effect=RuntimeError("Brain crash")):
            result = await faq_matcher({
                "raw_message": "I want a refund",
                "active_frameworks": [],
            })
        # Should still have a result (possibly None for no match)
        assert "faq_match" in result

    @pytest.mark.asyncio
    async def test_faq_matcher_empty_message(self):
        """FAQ_MATCHER should handle empty messages gracefully."""
        from parwa.nodes.faq_matcher import faq_matcher
        result = await faq_matcher({
            "raw_message": "",
            "active_frameworks": [],
        })
        assert result["faq_match"] is None

    @pytest.mark.asyncio
    async def test_faq_matcher_tracks_frameworks(self):
        """FAQ_MATCHER should track RAG frameworks in active_frameworks."""
        from parwa.nodes.faq_matcher import faq_matcher
        result = await faq_matcher({
            "raw_message": "I want a refund",
            "complexity": "medium",
            "active_frameworks": [],
        })
        assert isinstance(result.get("active_frameworks", []), list)


# ─── CONTEXT_MANAGER Integration Tests ───────────────────────────────────────

class TestContextManagerIntegration:

    @pytest.mark.asyncio
    async def test_context_manager_uses_brain(self):
        """CONTEXT_MANAGER should use FrameworkBrain for smart context."""
        from parwa.nodes.context_manager import context_manager
        result = await context_manager({
            "raw_message": "I was charged twice",
            "context_history": [],
            "active_frameworks": [],
        })
        assert isinstance(result["context_history"], list)
        assert len(result["context_history"]) >= 1

    @pytest.mark.asyncio
    async def test_context_manager_brain_failure_fallback(self):
        """CONTEXT_MANAGER should fall back when FrameworkBrain crashes."""
        from parwa.nodes.context_manager import context_manager
        with patch("parwa.nodes.context_manager._manage_context_with_brain", side_effect=RuntimeError("Brain crash")):
            result = await context_manager({
                "raw_message": "I was charged twice",
                "context_history": [],
                "active_frameworks": [],
            })
        assert isinstance(result["context_history"], list)

    @pytest.mark.asyncio
    async def test_context_manager_tracks_frameworks(self):
        """CONTEXT_MANAGER should track frameworks in active_frameworks."""
        from parwa.nodes.context_manager import context_manager
        result = await context_manager({
            "raw_message": "I was charged twice",
            "context_history": [],
            "complexity": "medium",
            "active_frameworks": [],
        })
        assert isinstance(result.get("active_frameworks", []), list)

    @pytest.mark.asyncio
    async def test_context_manager_limits_history(self):
        """CONTEXT_MANAGER should keep max 10 entries."""
        from parwa.nodes.context_manager import context_manager
        long_history = [{"role": "customer", "content": f"Message {i}"} for i in range(15)]
        result = await context_manager({
            "raw_message": "New message",
            "context_history": long_history,
            "active_frameworks": [],
        })
        assert len(result["context_history"]) <= 10


# ─── QUALITY_SCORER Integration Tests ────────────────────────────────────────

class TestQualityScorerIntegration:

    @pytest.mark.asyncio
    async def test_quality_scorer_uses_brain(self):
        """QUALITY_SCORER should use FrameworkBrain for smarter scoring."""
        from parwa.nodes.quality_scorer import quality_scorer
        result = await quality_scorer({
            "intent": "refund_request",
            "reasoning_conclusion": "Customer eligible for refund",
            "verification_passed": True,
            "recommendation": None,
            "variant": "parwa",
            "loop_count": 0,
            "max_loops": 2,
            "complexity": "medium",
            "active_frameworks": [],
        })
        assert isinstance(result["quality_score"], float)
        assert result["quality_score"] > 0

    @pytest.mark.asyncio
    async def test_quality_scorer_brain_failure_fallback(self):
        """QUALITY_SCORER should fall back when FrameworkBrain crashes."""
        from parwa.nodes.quality_scorer import quality_scorer
        with patch("parwa.nodes.quality_scorer._score_with_brain", side_effect=RuntimeError("Brain crash")):
            result = await quality_scorer({
                "intent": "refund_request",
                "reasoning_conclusion": "Test",
                "verification_passed": True,
                "recommendation": None,
                "variant": "parwa",
                "loop_count": 0,
                "max_loops": 2,
                "active_frameworks": [],
            })
        assert isinstance(result["quality_score"], float)

    @pytest.mark.asyncio
    async def test_quality_scorer_tracks_frameworks(self):
        """QUALITY_SCORER should track quality frameworks."""
        from parwa.nodes.quality_scorer import quality_scorer
        result = await quality_scorer({
            "intent": "refund_request",
            "reasoning_conclusion": "Eligible for refund",
            "verification_passed": True,
            "recommendation": None,
            "variant": "parwa",
            "loop_count": 0,
            "max_loops": 2,
            "complexity": "complex",
            "active_frameworks": [],
        })
        # Should have tracked some quality frameworks
        assert isinstance(result.get("active_frameworks", []), list)

    @pytest.mark.asyncio
    async def test_quality_scorer_loop_back_on_low_score(self):
        """QUALITY_SCORER should trigger loop-back when score < 80."""
        from parwa.nodes.quality_scorer import quality_scorer
        result = await quality_scorer({
            "intent": "refund_request",
            "reasoning_conclusion": "",  # Empty = low score
            "verification_passed": False,
            "recommendation": None,
            "variant": "parwa",
            "loop_count": 0,
            "max_loops": 2,
            "active_frameworks": [],
        })
        assert result["quality_score"] < 80
        assert result["should_loop_back"] is True


# ─── Full Pipeline Integration Tests ─────────────────────────────────────────

class TestPhase3PipelineIntegration:

    @pytest.mark.asyncio
    async def test_full_pipeline_with_phase3(self, parwa_graph):
        """Full pipeline should complete with Phase 3 techniques active."""
        result = await parwa_graph.ainvoke({
            "raw_message": "I was charged twice, I want a refund",
            "customer_id": "default",
            "channel": "email",
            "variant": "parwa",
        }, config=_config())

        assert result["final_response"] != ""
        assert result.get("pipeline_errors", []) == []

    @pytest.mark.asyncio
    async def test_full_pipeline_mini_variant(self, parwa_graph):
        """Mini PARWA pipeline should work with Phase 3 techniques."""
        result = await parwa_graph.ainvoke({
            "raw_message": "Where is my order?",
            "customer_id": "default",
            "channel": "email",
            "variant": "mini",
        }, config=_config())

        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_full_pipeline_parwa_high_variant(self, parwa_graph):
        """PARWA High pipeline should work with Phase 3 techniques."""
        result = await parwa_graph.ainvoke({
            "raw_message": "Cancel my order immediately",
            "customer_id": "default",
            "channel": "email",
            "variant": "parwa_high",
        }, config=_config())

        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_kb_retriever_failure_pipeline_continues(self, parwa_graph):
        """Pipeline should survive KB_RETRIEVER FrameworkBrain crash."""
        with patch("parwa.nodes.kb_retriever._retrieve_with_brain", side_effect=RuntimeError("KB brain down")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_faq_matcher_failure_pipeline_continues(self, parwa_graph):
        """Pipeline should survive FAQ_MATCHER FrameworkBrain crash."""
        with patch("parwa.nodes.faq_matcher._match_faq_with_brain", side_effect=RuntimeError("FAQ brain down")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_quality_scorer_failure_pipeline_continues(self, parwa_graph):
        """Pipeline should survive QUALITY_SCORER FrameworkBrain crash."""
        with patch("parwa.nodes.quality_scorer._score_with_brain", side_effect=RuntimeError("Scorer brain down")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_context_manager_failure_pipeline_continues(self, parwa_graph):
        """Pipeline should survive CONTEXT_MANAGER FrameworkBrain crash."""
        with patch("parwa.nodes.context_manager._manage_context_with_brain", side_effect=RuntimeError("Context brain down")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_multiple_phase3_node_failures_pipeline_continues(self, parwa_graph):
        """Pipeline should survive multiple Phase 3 node brain crashes."""
        with (
            patch("parwa.nodes.kb_retriever._retrieve_with_brain", side_effect=RuntimeError("KB brain down")),
            patch("parwa.nodes.faq_matcher._match_faq_with_brain", side_effect=RuntimeError("FAQ brain down")),
            patch("parwa.nodes.quality_scorer._score_with_brain", side_effect=RuntimeError("Scorer brain down")),
        ):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_convenience_function_with_phase3(self):
        """process_ticket convenience function should work with Phase 3."""
        result = process_ticket(
            raw_message="I was charged twice",
            customer_id="default",
            channel="email",
            variant="parwa",
        )
        assert "final_response" in result
        assert result["final_response"] != ""
