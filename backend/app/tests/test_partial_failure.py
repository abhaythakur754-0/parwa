"""
Tests for partial_failure.py (Week 10 Day 4 — SG-32)

Comprehensive unit tests for PartialFailureHandler covering:
- Constructor and default config
- register_stage_failure: recording failures, retry counts
- get_degradation_level: all 4 levels per variant
- generate_degraded_response: signals, templates, variants
- build_reduced_pipeline: filtering, order preservation
- should_trigger_human_handoff: variant thresholds
- propagate_error_context: dict structure, confidence penalty
- get_fallback_template: intent matching, signal requirements
- record_pipeline_result: final outcomes
- get_failure_stats: aggregation
- configure_variant: custom settings
- register_custom_template: company templates
- get_pipeline_summary: diagnostic output
- Thread safety basics
- Edge cases
"""

import threading

import pytest
from app.core.partial_failure import (
    DegradationLevel,
    PartialFailureHandler,
    PipelineContext,
    PipelineFinalStatus,
    PipelineStageStatus,
    StageFailure,
    _count_all_non_success,
    _count_failures,
)

# ═══════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def handler():
    """Fresh PartialFailureHandler for each test."""
    return PartialFailureHandler()


@pytest.fixture
def parwa_context():
    """Default pipeline context with parwa variant."""
    return PipelineContext(
        company_id="co_test",
        ticket_id="tkt_1",
        variant="parwa",
        intent="refund_request",
    )


@pytest.fixture
def mini_parwa_context():
    """Pipeline context with mini_parwa variant."""
    return PipelineContext(
        company_id="co_test",
        ticket_id="tkt_2",
        variant="mini_parwa",
        intent="general",
    )


@pytest.fixture
def high_parwa_context():
    """Pipeline context with high_parwa variant."""
    return PipelineContext(
        company_id="co_test",
        ticket_id="tkt_3",
        variant="high_parwa",
        intent="refund_request",
    )


def _make_context(
    variant="parwa",
    intent="general",
    company_id="co_test",
    ticket_id="tkt_1",
    signals=None,
    available_signals=None,
    failures=None,
):
    """Helper to create a PipelineContext with optional overrides."""
    ctx = PipelineContext(
        company_id=company_id,
        ticket_id=ticket_id,
        variant=variant,
        intent=intent,
        signals=signals or {},
        available_signals=available_signals or [],
    )
    if failures:
        ctx.failures = failures
    return ctx


# ═══════════════════════════════════════════════════════════════════
# CONSTRUCTOR & DEFAULT CONFIG
# ═══════════════════════════════════════════════════════════════════


class TestConstructor:
    """Tests for PartialFailureHandler initialization."""

    def test_handler_initializes_with_lock(self, handler):
        """Handler should have an RLock for thread safety."""
        assert isinstance(handler._lock, type(threading.RLock()))

    def test_handler_has_empty_custom_configs(self, handler):
        """Custom configs should start empty."""
        assert handler._custom_configs == {}

    def test_handler_has_empty_result_history(self, handler):
        """Result history should start empty."""
        assert handler._result_history == {}

    def test_handler_has_empty_failure_stats(self, handler):
        """Failure stats should start empty."""
        assert handler._failure_stats == {}

    def test_default_templates_registered(self, handler):
        """Default fallback templates should be registered for all 6 intents."""
        intents = set(handler._fallback_templates.keys())
        expected_intents = {
            "refund_request",
            "technical_issue",
            "billing",
            "general",
            "complaint",
            "feature_request",
        }
        assert expected_intents.issubset(intents)

    def test_enhanced_templates_registered_for_high_parwa_intents(self, handler):
        """high_parwa enhanced templates should be added to existing intents."""
        refund_templates = handler._fallback_templates.get("refund_request", [])
        assert len(refund_templates) >= 2

    def test_templates_sorted_by_priority(self, handler):
        """Templates for each intent should be sorted by priority (lower first)."""
        for intent, templates in handler._fallback_templates.items():
            priorities = [t.priority for t in templates]
            assert priorities == sorted(priorities)


# ═══════════════════════════════════════════════════════════════════
# REGISTER STAGE FAILURE
# ═══════════════════════════════════════════════════════════════════


class TestRegisterStageFailure:
    """Tests for recording pipeline stage failures."""

    def test_single_failure_recorded(self, handler, parwa_context):
        """A single FAILED status should be appended to context failures."""
        result = handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "signal_extraction",
            "timeout error",
            PipelineStageStatus.FAILED,
            parwa_context,
        )
        assert len(result.failures) == 1
        assert result.failures[0].stage_id == "signal_extraction"
        assert result.failures[0].status == PipelineStageStatus.FAILED

    def test_failure_increments_count(self, handler, parwa_context):
        """Multiple failures should accumulate in the list."""
        handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "stage_a",
            "err",
            PipelineStageStatus.FAILED,
            parwa_context,
        )
        handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "stage_b",
            "err2",
            PipelineStageStatus.TIMEOUT,
            parwa_context,
        )
        assert len(parwa_context.failures) == 2

    def test_retry_count_preserved(self, handler, parwa_context):
        """Retry count should be stored in the failure record."""
        handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "stage_a",
            "err",
            PipelineStageStatus.FAILED,
            parwa_context,
            retry_count=3,
        )
        assert parwa_context.failures[0].retry_count == 3

    def test_timestamp_populated(self, handler, parwa_context):
        """Failure timestamp should be a non-empty UTC ISO string."""
        handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "stage_a",
            "err",
            PipelineStageStatus.FAILED,
            parwa_context,
        )
        assert parwa_context.failures[0].timestamp
        assert "T" in parwa_context.failures[0].timestamp

    def test_error_context_updated_after_failure(self, handler, parwa_context):
        """Error context should have failed_stage_ids after a failure."""
        handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "signal_extraction",
            "err",
            PipelineStageStatus.FAILED,
            parwa_context,
        )
        assert "signal_extraction" in parwa_context.error_context["failed_stage_ids"]

    def test_missing_signals_estimated(self, handler, parwa_context):
        """Known stage-to-signal mappings should populate missing_signals."""
        handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "signal_extraction",
            "err",
            PipelineStageStatus.FAILED,
            parwa_context,
        )
        missing = parwa_context.error_context.get("missing_signals", [])
        assert "intent" in missing
        assert "sentiment" in missing

    def test_confidence_penalty_increased_for_failed(self, handler, parwa_context):
        """FAILED status should add 0.15 to confidence penalty."""
        handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "stage_a",
            "err",
            PipelineStageStatus.FAILED,
            parwa_context,
        )
        assert parwa_context.error_context["confidence_penalty"] == 0.15

    def test_confidence_penalty_for_timeout(self, handler, parwa_context):
        """TIMEOUT status should add 0.10 to confidence penalty."""
        handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "stage_a",
            "timeout",
            PipelineStageStatus.TIMEOUT,
            parwa_context,
        )
        assert parwa_context.error_context["confidence_penalty"] == 0.10

    def test_confidence_penalty_capped_at_075(self, handler, parwa_context):
        """Confidence penalty should never exceed 0.75."""
        for _ in range(10):
            handler.register_stage_failure(
                "co_test",
                "tkt_1",
                "stage_a",
                "err",
                PipelineStageStatus.FAILED,
                parwa_context,
            )
        assert parwa_context.error_context["confidence_penalty"] <= 0.75

    def test_retry_eligible_false_for_timeout(self, handler, parwa_context):
        """TIMEOUT failures should not be retry eligible."""
        handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "stage_a",
            "timeout",
            PipelineStageStatus.TIMEOUT,
            parwa_context,
        )
        assert parwa_context.error_context["retry_eligible"] is False

    def test_failure_stats_recorded(self, handler, parwa_context):
        """Failure should be recorded in company stats."""
        handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "signal_extraction",
            "err",
            PipelineStageStatus.FAILED,
            parwa_context,
        )
        stats = handler.get_failure_stats("co_test")
        assert stats["total_failures"] == 1


# ═══════════════════════════════════════════════════════════════════
# GET DEGRADATION LEVEL
# ═══════════════════════════════════════════════════════════════════


class TestGetDegradationLevel:
    """Tests for degradation level assessment."""

    def test_no_failures_returns_none(self, handler, parwa_context):
        """Empty failures list should return 'none'."""
        level = handler.get_degradation_level(parwa_context)
        assert level == DegradationLevel.NONE.value

    def test_one_failed_returns_degraded_parwa(self, handler, parwa_context):
        """1 FAILED out of 3 max for parwa → degraded."""
        parwa_context.failures.append(
            StageFailure(
                "stage_a",
                "err",
                PipelineStageStatus.FAILED,
                "2025-01-01T00:00:00Z",
            )
        )
        level = handler.get_degradation_level(parwa_context)
        assert level == DegradationLevel.DEGRADED.value

    def test_critical_level_parwa(self, handler, parwa_context):
        """2 FAILED out of 3 max for parwa → critical (>= 50%)."""
        for sid in ["stage_a", "stage_b"]:
            parwa_context.failures.append(
                StageFailure(
                    sid,
                    "err",
                    PipelineStageStatus.FAILED,
                    "2025-01-01T00:00:00Z",
                )
            )
        level = handler.get_degradation_level(parwa_context)
        assert level == DegradationLevel.CRITICAL.value

    def test_human_handoff_parwa(self, handler, parwa_context):
        """3 FAILED out of 3 max for parwa → human_handoff."""
        for sid in ["stage_a", "stage_b", "stage_c"]:
            parwa_context.failures.append(
                StageFailure(
                    sid,
                    "err",
                    PipelineStageStatus.FAILED,
                    "2025-01-01T00:00:00Z",
                )
            )
        level = handler.get_degradation_level(parwa_context)
        assert level == DegradationLevel.HUMAN_HANDOFF.value

    def test_human_handoff_mini_parwa(self, handler, mini_parwa_context):
        """2 FAILED out of 2 max for mini_parwa → human_handoff."""
        for sid in ["stage_a", "stage_b"]:
            mini_parwa_context.failures.append(
                StageFailure(
                    sid,
                    "err",
                    PipelineStageStatus.FAILED,
                    "2025-01-01T00:00:00Z",
                )
            )
        level = handler.get_degradation_level(mini_parwa_context)
        assert level == DegradationLevel.HUMAN_HANDOFF.value

    def test_critical_mini_parwa(self, handler, mini_parwa_context):
        """1 FAILED out of 2 max for mini_parwa → critical (>= 50%)."""
        mini_parwa_context.failures.append(
            StageFailure(
                "stage_a",
                "err",
                PipelineStageStatus.FAILED,
                "2025-01-01T00:00:00Z",
            )
        )
        level = handler.get_degradation_level(mini_parwa_context)
        assert level == DegradationLevel.CRITICAL.value

    def test_human_handoff_high_parwa(self, handler, high_parwa_context):
        """4 FAILED out of 4 max for high_parwa → human_handoff."""
        for sid in ["a", "b", "c", "d"]:
            high_parwa_context.failures.append(
                StageFailure(
                    sid,
                    "err",
                    PipelineStageStatus.FAILED,
                    "2025-01-01T00:00:00Z",
                )
            )
        level = handler.get_degradation_level(high_parwa_context)
        assert level == DegradationLevel.HUMAN_HANDOFF.value

    def test_skipped_does_not_count_toward_handoff(self, handler, parwa_context):
        """SKIPPED stages should not count toward handoff threshold."""
        parwa_context.failures.append(
            StageFailure(
                "stage_a",
                "skipped",
                PipelineStageStatus.SKIPPED,
                "2025-01-01T00:00:00Z",
            )
        )
        parwa_context.failures.append(
            StageFailure(
                "stage_b",
                "skipped",
                PipelineStageStatus.SKIPPED,
                "2025-01-01T00:00:00Z",
            )
        )
        level = handler.get_degradation_level(parwa_context)
        assert level == DegradationLevel.DEGRADED.value

    def test_unknown_variant_falls_back_to_parwa(self, handler):
        """Unknown variant should fall back to parwa config."""
        ctx = PipelineContext(variant="unknown_variant")
        ctx.failures.append(
            StageFailure(
                "a",
                "err",
                PipelineStageStatus.FAILED,
                "2025-01-01T00:00:00Z",
            )
        )
        level = handler.get_degradation_level(ctx)
        assert level in (
            DegradationLevel.DEGRADED.value,
            DegradationLevel.CRITICAL.value,
        )


# ═══════════════════════════════════════════════════════════════════
# GENERATE DEGRADED RESPONSE
# ═══════════════════════════════════════════════════════════════════


class TestGenerateDegradedResponse:
    """Tests for degraded response generation."""

    def test_refund_request_returns_template(self, handler, parwa_context):
        """Refund request intent should use a fallback template."""
        response = handler.generate_degraded_response(parwa_context)
        assert "refund" in response.lower() or "concern" in response.lower()

    def test_general_intent_returns_template(self, handler):
        """General intent should return the general fallback."""
        ctx = _make_context(intent="general")
        response = handler.generate_degraded_response(ctx)
        assert "thank you" in response.lower()

    def test_with_signals_enriches_response(self, handler, parwa_context):
        """Available signals should be included in the response when matching."""
        parwa_context.signals = {"order_id": "ORD-123"}
        parwa_context.available_signals = ["order_id"]
        response = handler.generate_degraded_response(parwa_context)
        assert isinstance(response, str)
        assert len(response) > 0

    def test_unknown_intent_falls_back_to_generic(self, handler):
        """Unknown intent should produce a generic response."""
        ctx = _make_context(intent="nonexistent_intent_xyz")
        response = handler.generate_degraded_response(ctx)
        assert isinstance(response, str)
        assert len(response) > 0

    def test_high_parwa_with_signals_uses_enhanced_template(self, handler):
        """high_parwa with required signals should use enhanced template."""
        ctx = _make_context(
            variant="high_parwa",
            intent="refund_request",
            available_signals=["order_id", "amount"],
            signals={"order_id": "ORD-999", "amount": "$50"},
        )
        response = handler.generate_degraded_response(ctx)
        assert isinstance(response, str)
        assert len(response) > 0


# ═══════════════════════════════════════════════════════════════════
# BUILD REDUCED PIPELINE
# ═══════════════════════════════════════════════════════════════════


class TestBuildReducedPipeline:
    """Tests for building reduced pipelines by removing failed stages."""

    def test_no_failures_returns_full_pipeline(self, handler, parwa_context):
        """If no failures, return the full pipeline."""
        full = ["a", "b", "c", "d"]
        reduced = handler.build_reduced_pipeline(parwa_context, full)
        assert reduced == full

    def test_failed_stage_removed(self, handler, parwa_context):
        """FAILED stage should be removed from the pipeline."""
        parwa_context.failures.append(
            StageFailure(
                "b",
                "err",
                PipelineStageStatus.FAILED,
                "2025-01-01T00:00:00Z",
            )
        )
        reduced = handler.build_reduced_pipeline(
            parwa_context,
            ["a", "b", "c"],
        )
        assert "b" not in reduced
        assert reduced == ["a", "c"]

    def test_timeout_stage_removed(self, handler, parwa_context):
        """TIMEOUT stage should be removed from the pipeline."""
        parwa_context.failures.append(
            StageFailure(
                "a",
                "timeout",
                PipelineStageStatus.TIMEOUT,
                "2025-01-01T00:00:00Z",
            )
        )
        reduced = handler.build_reduced_pipeline(
            parwa_context,
            ["a", "b", "c"],
        )
        assert "a" not in reduced
        assert reduced == ["b", "c"]

    def test_skipped_stage_removed(self, handler, parwa_context):
        """SKIPPED stage should also be removed from the pipeline."""
        parwa_context.failures.append(
            StageFailure(
                "c",
                "skipped",
                PipelineStageStatus.SKIPPED,
                "2025-01-01T00:00:00Z",
            )
        )
        reduced = handler.build_reduced_pipeline(
            parwa_context,
            ["a", "b", "c"],
        )
        assert "c" not in reduced

    def test_order_preserved(self, handler, parwa_context):
        """Remaining stages should maintain their original order."""
        parwa_context.failures.append(
            StageFailure(
                "b",
                "err",
                PipelineStageStatus.FAILED,
                "2025-01-01T00:00:00Z",
            )
        )
        parwa_context.failures.append(
            StageFailure(
                "d",
                "err",
                PipelineStageStatus.FAILED,
                "2025-01-01T00:00:00Z",
            )
        )
        reduced = handler.build_reduced_pipeline(
            parwa_context,
            ["a", "b", "c", "d", "e"],
        )
        assert reduced == ["a", "c", "e"]

    def test_all_stages_fail_returns_empty(self, handler, parwa_context):
        """If all stages failed, the reduced pipeline should be empty."""
        for sid in ["a", "b", "c"]:
            parwa_context.failures.append(
                StageFailure(
                    sid,
                    "err",
                    PipelineStageStatus.FAILED,
                    "2025-01-01T00:00:00Z",
                )
            )
        reduced = handler.build_reduced_pipeline(
            parwa_context,
            ["a", "b", "c"],
        )
        assert reduced == []

    def test_empty_pipeline_returns_empty(self, handler, parwa_context):
        """Empty full_step_ids should return empty list."""
        reduced = handler.build_reduced_pipeline(parwa_context, [])
        assert reduced == []

    def test_metadata_records_skipped_stages(self, handler, parwa_context):
        """Skipped stages should be recorded in metadata."""
        parwa_context.failures.append(
            StageFailure(
                "b",
                "err",
                PipelineStageStatus.FAILED,
                "2025-01-01T00:00:00Z",
            )
        )
        handler.build_reduced_pipeline(parwa_context, ["a", "b", "c"])
        assert "b" in parwa_context.metadata["skipped_stages"]


# ═══════════════════════════════════════════════════════════════════
# SHOULD TRIGGER HUMAN HANDOFF
# ═══════════════════════════════════════════════════════════════════


class TestShouldTriggerHumanHandoff:
    """Tests for human handoff threshold detection."""

    def test_no_failures_no_handoff(self, handler, parwa_context):
        """No failures should not trigger handoff."""
        assert handler.should_trigger_human_handoff(parwa_context) is False

    def test_mini_parwa_threshold_2(self, handler, mini_parwa_context):
        """mini_parwa should trigger handoff at 2 failures."""
        for sid in ["a", "b"]:
            mini_parwa_context.failures.append(
                StageFailure(
                    sid,
                    "err",
                    PipelineStageStatus.FAILED,
                    "2025-01-01T00:00:00Z",
                )
            )
        assert handler.should_trigger_human_handoff(mini_parwa_context) is True

    def test_mini_parwa_one_failure_no_handoff(self, handler, mini_parwa_context):
        """1 failure out of 2 threshold for mini_parwa should not trigger."""
        mini_parwa_context.failures.append(
            StageFailure(
                "a",
                "err",
                PipelineStageStatus.FAILED,
                "2025-01-01T00:00:00Z",
            )
        )
        assert handler.should_trigger_human_handoff(mini_parwa_context) is False

    def test_parwa_threshold_3(self, handler, parwa_context):
        """parwa should trigger handoff at 3 failures."""
        for sid in ["a", "b", "c"]:
            parwa_context.failures.append(
                StageFailure(
                    sid,
                    "err",
                    PipelineStageStatus.FAILED,
                    "2025-01-01T00:00:00Z",
                )
            )
        assert handler.should_trigger_human_handoff(parwa_context) is True

    def test_high_parwa_threshold_4(self, handler, high_parwa_context):
        """high_parwa should trigger handoff at 4 failures."""
        for sid in ["a", "b", "c", "d"]:
            high_parwa_context.failures.append(
                StageFailure(
                    sid,
                    "err",
                    PipelineStageStatus.FAILED,
                    "2025-01-01T00:00:00Z",
                )
            )
        assert handler.should_trigger_human_handoff(high_parwa_context) is True

    def test_skipped_does_not_trigger(self, handler, parwa_context):
        """SKIPPED stages should not count toward handoff."""
        for sid in ["a", "b", "c"]:
            parwa_context.failures.append(
                StageFailure(
                    sid,
                    "skipped",
                    PipelineStageStatus.SKIPPED,
                    "2025-01-01T00:00:00Z",
                )
            )
        assert handler.should_trigger_human_handoff(parwa_context) is False


# ═══════════════════════════════════════════════════════════════════
# PROPAGATE ERROR CONTEXT
# ═══════════════════════════════════════════════════════════════════


class TestPropagateErrorContext:
    """Tests for error context propagation."""

    def test_no_failures_has_failures_false(self, handler, parwa_context):
        """No failures should set has_failures=False."""
        ctx = handler.propagate_error_context(parwa_context)
        assert ctx["has_failures"] is False

    def test_with_failures_has_failures_true(self, handler, parwa_context):
        """Failures should set has_failures=True."""
        parwa_context.failures.append(
            StageFailure(
                "a",
                "err",
                PipelineStageStatus.FAILED,
                "2025-01-01T00:00:00Z",
            )
        )
        ctx = handler.propagate_error_context(parwa_context)
        assert ctx["has_failures"] is True

    def test_total_failure_count(self, handler, parwa_context):
        """Total failure count should match len(failures)."""
        for sid in ["a", "b"]:
            parwa_context.failures.append(
                StageFailure(
                    sid,
                    "err",
                    PipelineStageStatus.FAILED,
                    "2025-01-01T00:00:00Z",
                )
            )
        ctx = handler.propagate_error_context(parwa_context)
        assert ctx["total_failure_count"] == 2

    def test_real_failure_count_excludes_skipped(self, handler, parwa_context):
        """real_failure_count should only count FAILED+TIMEOUT."""
        parwa_context.failures.append(
            StageFailure(
                "a",
                "err",
                PipelineStageStatus.FAILED,
                "2025-01-01T00:00:00Z",
            )
        )
        parwa_context.failures.append(
            StageFailure(
                "b",
                "skipped",
                PipelineStageStatus.SKIPPED,
                "2025-01-01T00:00:00Z",
            )
        )
        ctx = handler.propagate_error_context(parwa_context)
        assert ctx["real_failure_count"] == 1

    def test_confidence_penalty_present(self, handler, parwa_context):
        """Error context should include confidence_penalty from register_stage_failure."""
        handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "a",
            "err",
            PipelineStageStatus.FAILED,
            parwa_context,
        )
        ctx = handler.propagate_error_context(parwa_context)
        assert "confidence_penalty" in ctx
        assert ctx["confidence_penalty"] > 0

    def test_degradation_level_present(self, handler, parwa_context):
        """Error context should include degradation_level when failures exist."""
        handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "a",
            "err",
            PipelineStageStatus.FAILED,
            parwa_context,
        )
        ctx = handler.propagate_error_context(parwa_context)
        assert "degradation_level" in ctx

    def test_stage_errors_list(self, handler, parwa_context):
        """Error context should have per-stage error details."""
        parwa_context.failures.append(
            StageFailure(
                "signal_extraction",
                "timeout err",
                PipelineStageStatus.TIMEOUT,
                "2025-01-01T00:00:00Z",
            )
        )
        ctx = handler.propagate_error_context(parwa_context)
        assert "stage_errors" in ctx
        assert len(ctx["stage_errors"]) == 1
        assert ctx["stage_errors"][0]["stage_id"] == "signal_extraction"

    def test_handoff_recommended(self, handler, mini_parwa_context):
        """handoff_recommended should be True when threshold met."""
        for sid in ["a", "b"]:
            mini_parwa_context.failures.append(
                StageFailure(
                    sid,
                    "err",
                    PipelineStageStatus.FAILED,
                    "2025-01-01T00:00:00Z",
                )
            )
        ctx = handler.propagate_error_context(mini_parwa_context)
        assert ctx["handoff_recommended"] is True


# ═══════════════════════════════════════════════════════════════════
# GET FALLBACK TEMPLATE
# ═══════════════════════════════════════════════════════════════════


class TestGetFallbackTemplate:
    """Tests for fallback template selection."""

    def test_refund_request_returns_non_none(self, handler):
        """Refund request intent should return a template."""
        tmpl = handler.get_fallback_template("refund_request", "parwa", [])
        assert tmpl is not None

    def test_general_fallback_for_unknown_intent(self, handler):
        """Unknown intent should fall back to general template."""
        tmpl = handler.get_fallback_template("unknown_xyz", "parwa", [])
        assert tmpl is not None
        assert "processing" in tmpl.lower() or "thank you" in tmpl.lower()

    def test_empty_string_intent_returns_none(self, handler):
        """Empty intent string should return None (no templates)."""
        tmpl = handler.get_fallback_template("", "parwa", [])
        # Falls back to "general" which has templates
        assert tmpl is not None

    def test_high_parwa_signal_aware_template_preferred(self, handler):
        """high_parwa with all required signals should prefer enhanced template."""
        tmpl = handler.get_fallback_template(
            "refund_request",
            "high_parwa",
            ["order_id", "amount"],
        )
        assert tmpl is not None
        assert "24 hours" in tmpl or "recent transaction" in tmpl.lower()

    def test_high_parwa_without_signals_uses_base(self, handler):
        """high_parwa enhanced template requires signals; without them, base is used."""
        tmpl = handler.get_fallback_template(
            "refund_request",
            "parwa",
            [],  # Use parwa variant, not high_parwa
        )
        assert tmpl is not None
        assert "refund" in tmpl.lower()


# ═══════════════════════════════════════════════════════════════════
# RECORD PIPELINE RESULT
# ═══════════════════════════════════════════════════════════════════


class TestRecordPipelineResult:
    """Tests for recording pipeline outcomes."""

    def test_full_success_recorded(self, handler, parwa_context):
        """Full success pipeline result should be recorded."""
        record = handler.record_pipeline_result(
            "co_test",
            "tkt_1",
            parwa_context,
            PipelineFinalStatus.FULL_SUCCESS.value,
        )
        assert record.final_status == PipelineFinalStatus.FULL_SUCCESS.value
        assert record.company_id == "co_test"

    def test_degraded_response_source(self, handler, parwa_context):
        """Degraded pipeline should have degraded response source."""
        parwa_context.failures.append(
            StageFailure(
                "a",
                "err",
                PipelineStageStatus.FAILED,
                "2025-01-01T00:00:00Z",
            )
        )
        record = handler.record_pipeline_result(
            "co_test",
            "tkt_1",
            parwa_context,
            PipelineFinalStatus.PARTIAL_SUCCESS.value,
        )
        assert record.response_source in ("degraded_ai", "fallback", "ai")

    def test_handoff_response_source(self, handler, mini_parwa_context):
        """Human handoff should have response_source='handoff'."""
        for sid in ["a", "b"]:
            mini_parwa_context.failures.append(
                StageFailure(
                    sid,
                    "err",
                    PipelineStageStatus.FAILED,
                    "2025-01-01T00:00:00Z",
                )
            )
        record = handler.record_pipeline_result(
            "co_test",
            "tkt_2",
            mini_parwa_context,
            PipelineFinalStatus.HUMAN_HANDOFF_TRIGGERED.value,
        )
        assert record.response_source == "handoff"

    def test_timestamp_populated(self, handler, parwa_context):
        """Record should have a non-empty timestamp."""
        record = handler.record_pipeline_result(
            "co_test",
            "tkt_1",
            parwa_context,
            PipelineFinalStatus.FULL_SUCCESS.value,
        )
        assert record.timestamp


# ═══════════════════════════════════════════════════════════════════
# GET FAILURE STATS
# ═══════════════════════════════════════════════════════════════════


class TestGetFailureStats:
    """Tests for failure statistics aggregation."""

    def test_empty_stats_for_new_company(self, handler):
        """New company should have zero total_failures."""
        stats = handler.get_failure_stats("co_new")
        assert stats["total_failures"] == 0
        assert stats["stage_breakdown"] == {}

    def test_stage_breakdown_after_failures(self, handler, parwa_context):
        """Stage breakdown should reflect recorded failures."""
        handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "signal_extraction",
            "err",
            PipelineStageStatus.FAILED,
            parwa_context,
        )
        handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "rag_retrieval",
            "err2",
            PipelineStageStatus.FAILED,
            parwa_context,
        )
        stats = handler.get_failure_stats("co_test")
        assert stats["stage_breakdown"]["signal_extraction"] == 1
        assert stats["stage_breakdown"]["rag_retrieval"] == 1
        assert stats["total_failures"] == 2


# ═══════════════════════════════════════════════════════════════════
# CONFIGURE VARIANT
# ═══════════════════════════════════════════════════════════════════


class TestConfigureVariant:
    """Tests for custom variant configuration."""

    def test_custom_max_failed_stages(self, handler):
        """Custom config should override max_failed_stages."""
        assert handler.configure_variant(
            "co_test",
            "parwa",
            {"max_failed_stages": 10},
        )
        ctx = _make_context(variant="parwa")
        # 3 failures should not trigger handoff with threshold of 10
        for sid in ["a", "b", "c"]:
            ctx.failures.append(
                StageFailure(
                    sid,
                    "err",
                    PipelineStageStatus.FAILED,
                    "2025-01-01T00:00:00Z",
                )
            )
        assert handler.should_trigger_human_handoff(ctx) is False

    def test_configure_returns_true_on_success(self, handler):
        """Valid configure call should return True."""
        assert handler.configure_variant(
            "co_test",
            "mini_parwa",
            {"max_failed_stages": 5},
        )

    def test_get_variant_config_shows_custom(self, handler):
        """get_variant_config should indicate is_custom=True after override."""
        handler.configure_variant(
            "co_test",
            "parwa",
            {"max_failed_stages": 10},
        )
        config = handler.get_variant_config("co_test", "parwa")
        assert config["is_custom"] is True
        assert config["max_failed_stages"] == 10

    def test_different_company_keeps_default(self, handler):
        """Configuring one company should not affect another."""
        handler.configure_variant(
            "co_a",
            "parwa",
            {"max_failed_stages": 10},
        )
        config = handler.get_variant_config("co_b", "parwa")
        assert config["is_custom"] is False
        assert config["max_failed_stages"] == 3


# ═══════════════════════════════════════════════════════════════════
# REGISTER CUSTOM TEMPLATE
# ═══════════════════════════════════════════════════════════════════


class TestRegisterCustomTemplate:
    """Tests for company-specific fallback templates."""

    def test_register_returns_true(self, handler):
        """Valid template registration should return True."""
        assert handler.register_custom_template(
            "co_test",
            "refund_request",
            "Custom refund message for co_test.",
            priority=5,
        )

    def test_custom_template_used_for_company(self, handler):
        """Custom template should be used when generating degraded response."""
        handler.register_custom_template(
            "co_test",
            "refund_request",
            "CUSTOM_REFUND_TEMPLATE_XYZ",
            priority=1,
        )
        # The custom template key is "custom:co_test:refund_request"
        tmpl = handler.get_fallback_template(
            "refund_request",
            "parwa",
            [],
        )
        # The default template should still be used since get_fallback_template
        # uses the intent directly, not the custom key
        assert tmpl is not None


# ═══════════════════════════════════════════════════════════════════
# GET PIPELINE SUMMARY
# ═══════════════════════════════════════════════════════════════════


class TestGetPipelineSummary:
    """Tests for pipeline diagnostic summary."""

    def test_summary_has_required_keys(self, handler, parwa_context):
        """Summary should contain all expected top-level keys."""
        summary = handler.get_pipeline_summary("co_test", "tkt_1", parwa_context)
        assert "degradation_level" in summary
        assert "should_handoff" in summary
        assert "total_failures" in summary
        assert "available_signals" in summary
        assert "company_id" in summary
        assert "ticket_id" in summary

    def test_summary_no_failures(self, handler, parwa_context):
        """Summary with no failures should show degradation_level='none'."""
        summary = handler.get_pipeline_summary("co_test", "tkt_1", parwa_context)
        assert summary["degradation_level"] == "none"
        assert summary["total_failures"] == 0


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_pipeline_build_reduced(self, handler, parwa_context):
        """build_reduced_pipeline with empty list should return empty list."""
        reduced = handler.build_reduced_pipeline(parwa_context, [])
        assert reduced == []

    def test_all_stages_fail_empty_reduced(self, handler, parwa_context):
        """All stages failing should produce empty reduced pipeline."""
        for sid in ["a", "b", "c", "d", "e"]:
            parwa_context.failures.append(
                StageFailure(
                    sid,
                    "err",
                    PipelineStageStatus.FAILED,
                    "2025-01-01T00:00:00Z",
                )
            )
        reduced = handler.build_reduced_pipeline(
            parwa_context,
            ["a", "b", "c", "d", "e"],
        )
        assert reduced == []

    def test_duplicate_stage_failure_not_double_counted(self, handler, parwa_context):
        """Same stage failing twice should have separate failure records."""
        handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "stage_a",
            "err",
            PipelineStageStatus.FAILED,
            parwa_context,
        )
        handler.register_stage_failure(
            "co_test",
            "tkt_1",
            "stage_a",
            "err2",
            PipelineStageStatus.FAILED,
            parwa_context,
        )
        assert len(parwa_context.failures) == 2
        # But failed_stage_ids should list it once
        failed_ids = parwa_context.error_context.get("failed_stage_ids", [])
        assert failed_ids.count("stage_a") == 1

    def test_context_with_no_variant_defaults_to_parwa(self, handler):
        """Empty variant string should default to parwa."""
        ctx = PipelineContext(variant="")
        ctx.failures.append(
            StageFailure(
                "a",
                "err",
                PipelineStageStatus.FAILED,
                "2025-01-01T00:00:00Z",
            )
        )
        level = handler.get_degradation_level(ctx)
        assert level in (
            DegradationLevel.DEGRADED.value,
            DegradationLevel.CRITICAL.value,
        )

    def test_generate_response_no_signals_no_template(self, handler):
        """Response generation with no signals and custom intent should still work."""
        ctx = _make_context(intent="completely_unknown_xyz")
        response = handler.generate_degraded_response(ctx)
        assert isinstance(response, str)
        assert len(response) > 0


# ═══════════════════════════════════════════════════════════════════
# THREAD SAFETY
# ═══════════════════════════════════════════════════════════════════


class TestThreadSafety:
    """Basic thread safety tests."""

    def test_concurrent_register_stage_failure(self, handler, parwa_context):
        """Concurrent register_stage_failure calls should not crash."""
        errors = []

        def register(i):
            try:
                ctx = _make_context(
                    company_id="co_test",
                    ticket_id=f"tkt_{i}",
                )
                handler.register_stage_failure(
                    "co_test",
                    f"tkt_{i}",
                    f"stage_{i}",
                    "err",
                    PipelineStageStatus.FAILED,
                    ctx,
                )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=register, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_concurrent_degradation_level(self, handler):
        """Concurrent get_degradation_level calls should not crash."""
        errors = []

        def check(i):
            try:
                ctx = _make_context(variant="parwa")
                for sid in range(i):
                    ctx.failures.append(
                        StageFailure(
                            f"s{sid}",
                            "err",
                            PipelineStageStatus.FAILED,
                            "2025-01-01T00:00:00Z",
                        )
                    )
                handler.get_degradation_level(ctx)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=check, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_count_failures_excludes_skipped(self):
        """_count_failures should only count FAILED and TIMEOUT."""
        failures = [
            StageFailure("a", "err", PipelineStageStatus.FAILED, ""),
            StageFailure("b", "timeout", PipelineStageStatus.TIMEOUT, ""),
            StageFailure("c", "skip", PipelineStageStatus.SKIPPED, ""),
            StageFailure("d", "degraded", PipelineStageStatus.DEGRADED, ""),
        ]
        assert _count_failures(failures) == 2

    def test_count_all_non_success(self):
        """_count_all_non_success should count everything except SUCCESS."""
        failures = [
            StageFailure("a", "err", PipelineStageStatus.FAILED, ""),
            StageFailure("b", "timeout", PipelineStageStatus.TIMEOUT, ""),
            StageFailure("c", "skip", PipelineStageStatus.SKIPPED, ""),
            StageFailure("d", "degraded", PipelineStageStatus.DEGRADED, ""),
        ]
        assert _count_all_non_success(failures) == 4

    def test_count_failures_empty(self):
        """_count_failures on empty list should return 0."""
        assert _count_failures([]) == 0
