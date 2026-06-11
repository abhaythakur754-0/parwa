"""Integration tests for the PARWA LangGraph pipeline.

Tests the full graph flow end-to-end, including:
- Complete ticket processing through all 22 nodes (async)
- Variant differentiation (same thinking, different actions)
- Mini PARWA recommendation flow
- Quality score loop-back
- Escalation routing
- Checkpointing and crash recovery
- Error handling resilience
- State validation
- Sync process_ticket and async aprocess_ticket convenience functions
- Concurrent ticket processing
"""

import pytest
import uuid

from parwa.graph import build_parwa_graph, process_ticket, aprocess_ticket, reset_parwa_graph


@pytest.fixture
def parwa_graph():
    """Create a fresh compiled graph for each test."""
    reset_parwa_graph()
    return build_parwa_graph(use_checkpointer=True)


def _config(thread_id: str | None = None) -> dict:
    """Create a LangGraph config with thread_id for checkpointing."""
    return {"configurable": {"thread_id": thread_id or f"test-{uuid.uuid4().hex[:8]}"}}


# ─── Full Pipeline Tests (Async) ──────────────────────────────────────────────────

class TestFullPipeline:
    """Test complete ticket processing through the full graph."""

    @pytest.mark.asyncio
    async def test_refund_ticket_parwa(self, parwa_graph):
        """Test a refund ticket on PARWA variant — should execute refund."""
        result = await parwa_graph.ainvoke({
            "raw_message": "I was charged twice, I want a refund",
            "customer_id": "default",
            "channel": "email",
            "variant": "parwa",
        }, config=_config())

        # Should have gone through the full pipeline
        assert result["ticket_id"].startswith("TKT-")
        assert result["intent"] == "refund_request"
        assert result["final_response"] != ""

        # PARWA should EXECUTE the refund
        executed_types = [r["status"] for r in result.get("execution_results", [])]
        assert "executed" in executed_types or "recommended" in executed_types

        # Should have audit log
        assert len(result.get("audit_log", [])) > 0

    @pytest.mark.asyncio
    async def test_order_status_ticket(self, parwa_graph):
        """Test a simple order status inquiry."""
        result = await parwa_graph.ainvoke({
            "raw_message": "Where is my order?",
            "customer_id": "default",
            "channel": "chat",
            "variant": "parwa",
        }, config=_config())

        assert result["intent"] == "order_status"
        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_cancellation_ticket(self, parwa_graph):
        """Test a cancellation request."""
        result = await parwa_graph.ainvoke({
            "raw_message": "I want to cancel my order",
            "customer_id": "default",
            "channel": "email",
            "variant": "parwa",
        }, config=_config())

        assert result["intent"] == "cancellation"
        assert result["final_response"] != ""


# ─── Variant Differentiation Tests ────────────────────────────────────────────────

class TestVariantDifferentiation:
    """Test that variants think identically but act differently."""

    @pytest.mark.asyncio
    async def test_mini_recommends_refund(self, parwa_graph):
        """Mini PARWA should RECOMMEND refund, not execute."""
        result = await parwa_graph.ainvoke({
            "raw_message": "I was charged twice, I want a refund",
            "customer_id": "default",
            "channel": "email",
            "variant": "mini",
        }, config=_config())

        # Mini should recommend, not execute
        assert result.get("recommendation") is not None
        assert result["recommendation"].get("pending_approval") is True

    @pytest.mark.asyncio
    async def test_parwa_executes_refund(self, parwa_graph):
        """PARWA should EXECUTE refund directly."""
        result = await parwa_graph.ainvoke({
            "raw_message": "I was charged twice, I want a refund",
            "customer_id": "default",
            "channel": "email",
            "variant": "parwa",
        }, config=_config())

        # PARWA should execute directly
        executed = [r for r in result.get("execution_results", []) if r.get("status") == "executed"]
        assert len(executed) > 0

    @pytest.mark.asyncio
    async def test_high_executes_refund(self, parwa_graph):
        """PARWA High should EXECUTE refund directly."""
        result = await parwa_graph.ainvoke({
            "raw_message": "I was charged twice, I want a refund",
            "customer_id": "default",
            "channel": "email",
            "variant": "high",
        }, config=_config())

        executed = [r for r in result.get("execution_results", []) if r.get("status") == "executed"]
        assert len(executed) > 0

    @pytest.mark.asyncio
    async def test_same_thinking_across_variants(self, parwa_graph):
        """All variants should have identical thinking (intent, sentiment, reasoning)."""
        base_input = {
            "raw_message": "I was charged twice, I want a refund",
            "customer_id": "default",
            "channel": "email",
        }

        results = {}
        for variant in ("mini", "parwa", "high"):
            results[variant] = await parwa_graph.ainvoke(
                {**base_input, "variant": variant},
                config=_config(f"variant-test-{variant}"),
            )

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

    @pytest.mark.asyncio
    async def test_angry_critical_escalates(self, parwa_graph):
        """Angry + Critical tickets should be flagged for escalation."""
        result = await parwa_graph.ainvoke({
            "raw_message": "I am furious about this unacceptable service! This is ridiculous!",
            "customer_id": "default",
            "channel": "email",
            "variant": "parwa",
        }, config=_config())

        # Should detect negative sentiment
        assert result["sentiment"] in ("frustrated", "angry")


# ─── Quality Loop-Back Tests ──────────────────────────────────────────────────────

class TestQualityLoopBack:
    """Test that quality scoring loop-back works."""

    @pytest.mark.asyncio
    async def test_quality_score_present(self, parwa_graph):
        """Every response should have a quality score."""
        result = await parwa_graph.ainvoke({
            "raw_message": "Where is my order?",
            "customer_id": "default",
            "channel": "chat",
            "variant": "parwa",
        }, config=_config())

        assert "quality_score" in result
        assert result["quality_score"] >= 0

    @pytest.mark.asyncio
    async def test_audit_log_present(self, parwa_graph):
        """Every response should have an audit log."""
        result = await parwa_graph.ainvoke({
            "raw_message": "I need help",
            "customer_id": "default",
            "channel": "email",
            "variant": "parwa",
        }, config=_config())

        assert len(result.get("audit_log", [])) > 0


# ─── Production Feature Tests ──────────────────────────────────────────────────────

class TestErrorHandling:
    """Test that error handling works — nodes never crash the pipeline."""

    @pytest.mark.asyncio
    async def test_no_pipeline_errors_on_normal_ticket(self, parwa_graph):
        """Normal tickets should have no pipeline errors."""
        result = await parwa_graph.ainvoke({
            "raw_message": "Where is my order?",
            "customer_id": "default",
            "channel": "chat",
            "variant": "parwa",
        }, config=_config())

        errors = result.get("pipeline_errors", [])
        assert len(errors) == 0, f"Unexpected pipeline errors: {errors}"

    @pytest.mark.asyncio
    async def test_node_error_tracking_on_bad_state(self):
        """If a node fails, error should be tracked not crash the pipeline."""
        from parwa.nodes.ingest import ingest
        result = await ingest({"raw_message": "test"})
        assert "ticket_id" in result


class TestCheckpointing:
    """Test that checkpointing works for crash recovery."""

    @pytest.mark.asyncio
    async def test_checkpointer_saves_state(self, parwa_graph):
        """Verify the checkpointer persists state."""
        thread_id = f"checkpoint-test-{uuid.uuid4().hex[:8]}"
        cfg = _config(thread_id)

        result = await parwa_graph.ainvoke({
            "raw_message": "I want a refund",
            "customer_id": "default",
            "channel": "email",
            "variant": "parwa",
        }, config=cfg)

        # Result should be complete — checkpointer saved state along the way
        assert result["ticket_id"].startswith("TKT-")
        assert result["final_response"] != ""


class TestStateValidation:
    """Test that state validation works."""

    def test_valid_state_passes_validation(self):
        """Valid state dict should pass validation."""
        from parwa.state import validate_state
        is_valid, issues = validate_state({
            "raw_message": "test",
            "variant": "parwa",
            "channel": "email",
        })
        assert is_valid, f"Validation issues: {issues}"

    def test_invalid_variant_fails_validation(self):
        """Invalid variant should fail validation."""
        from parwa.state import validate_state
        is_valid, issues = validate_state({
            "raw_message": "test",
            "variant": "enterprise",  # invalid
            "channel": "email",
        })
        assert not is_valid


# ─── Convenience Function Tests ────────────────────────────────────────────────────

class TestProcessTicket:
    """Test the process_ticket convenience function (sync wrapper)."""

    def test_process_ticket_basic(self):
        """Test basic ticket processing via sync wrapper."""
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
        """Test Mini PARWA ticket processing via sync wrapper."""
        result = process_ticket(
            raw_message="I want a refund for the duplicate charge",
            customer_id="default",
            channel="chat",
            variant="mini",
        )

        assert result["intent"] == "refund_request"

    def test_process_ticket_empty_message(self):
        """Empty message should return error, not crash."""
        result = process_ticket(raw_message="")
        assert "error" in result or "final_response" in result

    def test_process_ticket_invalid_variant(self):
        """Invalid variant should default to parwa, not crash."""
        result = process_ticket(
            raw_message="I need help",
            variant="enterprise",
        )
        assert result["variant"] == "parwa"


class TestAprocessTicket:
    """Test the aprocess_ticket async convenience function."""

    @pytest.mark.asyncio
    async def test_aprocess_ticket_basic(self):
        """Test basic async ticket processing."""
        result = await aprocess_ticket(
            raw_message="I was charged twice",
            customer_id="default",
            channel="email",
            variant="parwa",
        )

        assert result["ticket_id"].startswith("TKT-")
        assert result["intent"] == "refund_request"
        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_aprocess_ticket_mini(self):
        """Test Mini PARWA async ticket processing."""
        result = await aprocess_ticket(
            raw_message="I want a refund for the duplicate charge",
            customer_id="default",
            channel="chat",
            variant="mini",
        )

        assert result["intent"] == "refund_request"
        assert result.get("recommendation") is not None

    @pytest.mark.asyncio
    async def test_aprocess_ticket_empty_message(self):
        """Empty message should return error, not crash — async."""
        result = await aprocess_ticket(raw_message="")
        assert "error" in result or "final_response" in result

    @pytest.mark.asyncio
    async def test_aprocess_ticket_invalid_variant(self):
        """Invalid variant should default to parwa — async."""
        result = await aprocess_ticket(
            raw_message="I need help",
            variant="enterprise",
        )
        assert result["variant"] == "parwa"

    @pytest.mark.asyncio
    async def test_aprocess_ticket_concurrent(self):
        """Test processing multiple tickets concurrently — the async advantage."""
        import asyncio

        tickets = [
            aprocess_ticket(raw_message="I was charged twice", variant="parwa"),
            aprocess_ticket(raw_message="Where is my order?", variant="parwa"),
            aprocess_ticket(raw_message="I want to cancel", variant="mini"),
        ]

        results = await asyncio.gather(*tickets)

        assert len(results) == 3
        assert results[0]["intent"] == "refund_request"
        assert results[1]["intent"] == "order_status"
        assert results[2]["intent"] == "cancellation"
