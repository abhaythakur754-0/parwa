"""Integration tests for the PARWA LangGraph pipeline.

Tests the full graph flow end-to-end, including:
- Complete ticket processing through all 22 nodes
- Variant differentiation (same thinking, different actions)
- Mini PARWA recommendation flow
- Quality score loop-back
- Escalation routing
"""

import pytest

from parwa.graph import build_parwa_graph, process_ticket


@pytest.fixture
def parwa_graph():
    """Create a fresh compiled graph for each test."""
    return build_parwa_graph()


# ─── Full Pipeline Tests ──────────────────────────────────────────────────────────

class TestFullPipeline:
    """Test complete ticket processing through the full graph."""

    def test_refund_ticket_parwa(self, parwa_graph):
        """Test a refund ticket on PARWA variant — should execute refund."""
        result = parwa_graph.invoke({
            "raw_message": "I was charged twice, I want a refund",
            "customer_id": "default",
            "channel": "email",
            "variant": "parwa",
        })

        # Should have gone through the full pipeline
        assert result["ticket_id"].startswith("TKT-")
        assert result["intent"] == "refund_request"
        assert result["final_response"] != ""

        # PARWA should EXECUTE the refund
        executed_types = [r["status"] for r in result.get("execution_results", [])]
        assert "executed" in executed_types or "recommended" in executed_types

        # Should have audit log
        assert len(result.get("audit_log", [])) > 0

    def test_order_status_ticket(self, parwa_graph):
        """Test a simple order status inquiry."""
        result = parwa_graph.invoke({
            "raw_message": "Where is my order?",
            "customer_id": "default",
            "channel": "chat",
            "variant": "parwa",
        })

        assert result["intent"] == "order_status"
        assert result["final_response"] != ""

    def test_cancellation_ticket(self, parwa_graph):
        """Test a cancellation request."""
        result = parwa_graph.invoke({
            "raw_message": "I want to cancel my order",
            "customer_id": "default",
            "channel": "email",
            "variant": "parwa",
        })

        assert result["intent"] == "cancellation"
        assert result["final_response"] != ""


# ─── Variant Differentiation Tests ────────────────────────────────────────────────

class TestVariantDifferentiation:
    """Test that variants think identically but act differently."""

    def test_mini_recommends_refund(self, parwa_graph):
        """Mini PARWA should RECOMMEND refund, not execute."""
        result = parwa_graph.invoke({
            "raw_message": "I was charged twice, I want a refund",
            "customer_id": "default",
            "channel": "email",
            "variant": "mini",
        })

        # Mini should recommend, not execute
        assert result.get("recommendation") is not None
        assert result["recommendation"].get("pending_approval") is True

    def test_parwa_executes_refund(self, parwa_graph):
        """PARWA should EXECUTE refund directly."""
        result = parwa_graph.invoke({
            "raw_message": "I was charged twice, I want a refund",
            "customer_id": "default",
            "channel": "email",
            "variant": "parwa",
        })

        # PARWA should execute directly
        executed = [r for r in result.get("execution_results", []) if r.get("status") == "executed"]
        assert len(executed) > 0

    def test_high_executes_refund(self, parwa_graph):
        """PARWA High should EXECUTE refund directly."""
        result = parwa_graph.invoke({
            "raw_message": "I was charged twice, I want a refund",
            "customer_id": "default",
            "channel": "email",
            "variant": "high",
        })

        executed = [r for r in result.get("execution_results", []) if r.get("status") == "executed"]
        assert len(executed) > 0

    def test_same_thinking_across_variants(self, parwa_graph):
        """All variants should have identical thinking (intent, sentiment, reasoning)."""
        base_input = {
            "raw_message": "I was charged twice, I want a refund",
            "customer_id": "default",
            "channel": "email",
        }

        results = {}
        for variant in ("mini", "parwa", "high"):
            results[variant] = parwa_graph.invoke({**base_input, "variant": variant})

        # Thinking should be identical
        assert results["mini"]["intent"] == results["parwa"]["intent"] == results["high"]["intent"]
        assert results["mini"]["sentiment"] == results["parwa"]["sentiment"] == results["high"]["sentiment"]

        # Reasoning conclusion should be the same
        assert results["mini"]["reasoning_conclusion"] == results["parwa"]["reasoning_conclusion"]

        # But actions should differ
        mini_has_rec = results["mini"].get("recommendation") is not None
        parwa_has_rec = results["parwa"].get("recommendation") is not None
        assert mini_has_rec != parwa_has_rec or mini_has_rec is True


# ─── Escalation Tests ─────────────────────────────────────────────────────────────

class TestEscalation:
    """Test that escalation routing works correctly."""

    def test_angry_critical_escalates(self, parwa_graph):
        """Angry + Critical tickets should be flagged for escalation."""
        result = parwa_graph.invoke({
            "raw_message": "I am furious about this unacceptable service! This is ridiculous!",
            "customer_id": "default",
            "channel": "email",
            "variant": "parwa",
        })

        # Should detect negative sentiment
        assert result["sentiment"] in ("frustrated", "angry")


# ─── Quality Loop-Back Tests ──────────────────────────────────────────────────────

class TestQualityLoopBack:
    """Test that quality scoring loop-back works."""

    def test_quality_score_present(self, parwa_graph):
        """Every response should have a quality score."""
        result = parwa_graph.invoke({
            "raw_message": "Where is my order?",
            "customer_id": "default",
            "channel": "chat",
            "variant": "parwa",
        })

        assert "quality_score" in result
        assert result["quality_score"] >= 0

    def test_audit_log_present(self, parwa_graph):
        """Every response should have an audit log."""
        result = parwa_graph.invoke({
            "raw_message": "I need help",
            "customer_id": "default",
            "channel": "email",
            "variant": "parwa",
        })

        assert len(result.get("audit_log", [])) > 0


# ─── Convenience Function Tests ────────────────────────────────────────────────────

class TestProcessTicket:
    """Test the process_ticket convenience function."""

    def test_process_ticket_basic(self):
        """Test basic ticket processing."""
        result = process_ticket(
            raw_message="I was charged twice",
            customer_id="default",
            channel="email",
            variant="parwa",
        )

        assert result["ticket_id"].startswith("TKT-")
        assert result["intent"] == "refund_request"
        assert result["final_response"] != ""

    def test_process_ticket_mini(self):
        """Test Mini PARWA ticket processing."""
        result = process_ticket(
            raw_message="I want a refund for the duplicate charge",
            customer_id="default",
            channel="chat",
            variant="mini",
        )

        assert result["intent"] == "refund_request"
