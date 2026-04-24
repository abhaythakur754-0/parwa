"""Tests for AI Monitoring Service (SG-19).

Comprehensive tests covering:
- Helper functions (timestamps, percentile, token estimation, bucket mapping)
- Metric recording (record_query master method)
- Latency metrics (stats, filtering, empty state)
- Confidence distribution (buckets, averages, pass rates)
- Guardrail stats (pass/block/flag rates, per-layer breakdown)
- Token usage metrics (estimation, averages)
- Error metrics (rates, by-type, by-provider)
- Provider comparison (side-by-side stats)
- Variant metrics (per-variant breakdowns)
- Alert conditions (error rate, confidence drop, latency spike, provider unhealthy)
- Dashboard snapshot (complete data aggregation)
- Data pruning (max data points respected)
- Edge cases (invalid company, empty records, bad timestamps)
- BC-008 never-crash on bad inputs
"""

from __future__ import annotations

import os

os.environ["ENVIRONMENT"] = "test"

import pytest

from app.core.ai_monitoring_service import (
    AIMonitoringService,
    AlertCondition,
    AlertLevel,
    BlockedResponseMetrics,
    ConfidenceDistribution,
    DashboardSnapshot,
    ErrorMetrics,
    GuardrailLayerBreakdown,
    GuardrailStats,
    LatencyStats,
    MetricPoint,
    ProviderComparison,
    TimeWindow,
    TokenUsageMetrics,
    _confidence_bucket,
    _estimate_tokens,
    _now_utc,
    _parse_iso,
    _percentile,
    _window_cutoff,
)


COMPANY_ID = "test-company-monitoring"
ANOTHER_COMPANY = "test-company-monitoring-2"


@pytest.fixture
def monitor() -> AIMonitoringService:
    """Fresh monitor with cleared state per test."""
    svc = AIMonitoringService()
    svc.reset()
    return svc


def _sample_routing(provider="google", model_id="gemini-2.0-flash", tier="medium", step="cot_reasoning"):
    return {"provider": provider, "model_id": model_id, "tier": tier, "step": step}


def _sample_confidence(score=85.0, passed=True, threshold=85.0):
    return {"overall_score": score, "passed": passed, "threshold": threshold}


def _sample_guardrails(passed=True, blocked_count=0, flagged_count=0, results=None):
    return {"passed": passed, "blocked_count": blocked_count, "flagged_count": flagged_count, "results": results or []}


# ════════════════════════════════════════════════════════════════
# 1. HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════


class TestHelperFunctions:
    def test_now_utc_returns_string(self):
        ts = _now_utc()
        assert isinstance(ts, str)
        assert _parse_iso(ts) is not None

    def test_parse_iso_valid(self):
        parsed = _parse_iso("2025-01-15T10:30:00+00:00")
        assert parsed is not None
        assert parsed.year == 2025

    def test_parse_iso_trailing_z(self):
        parsed = _parse_iso("2025-01-15T10:30:00Z")
        assert parsed is not None

    def test_parse_iso_empty(self):
        assert _parse_iso("") is None

    def test_parse_iso_garbage(self):
        assert _parse_iso("not-a-date") is None

    def test_parse_iso_none(self):
        assert _parse_iso(None) is None

    def test_estimate_tokens_text(self):
        assert _estimate_tokens("Hello world") > 0

    def test_estimate_tokens_empty(self):
        assert _estimate_tokens("") == 0

    def test_estimate_tokens_none(self):
        assert _estimate_tokens(None) == 0

    def test_confidence_bucket_0_20(self):
        assert _confidence_bucket(10.0) == "0-20"

    def test_confidence_bucket_20_40(self):
        assert _confidence_bucket(30.0) == "20-40"

    def test_confidence_bucket_40_60(self):
        assert _confidence_bucket(50.0) == "40-60"

    def test_confidence_bucket_60_80(self):
        assert _confidence_bucket(70.0) == "60-80"

    def test_confidence_bucket_80_100(self):
        assert _confidence_bucket(90.0) == "80-100"

    def test_confidence_bucket_boundary_20(self):
        assert _confidence_bucket(20.0) == "20-40"

    def test_percentile_empty(self):
        assert _percentile([], 50) == 0.0

    def test_percentile_single(self):
        assert _percentile([5.0], 50) == 5.0

    def test_percentile_p50(self):
        vals = sorted([10, 20, 30, 40, 50])
        result = _percentile(vals, 50)
        assert 25 <= result <= 35

    def test_percentile_p90(self):
        vals = sorted([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
        result = _percentile(vals, 90)
        assert result >= 85

    def test_percentile_p99(self):
        vals = sorted(range(1, 101))
        result = _percentile(vals, 99)
        assert result >= 95

    def test_window_cutoff(self):
        cutoff = _window_cutoff("1h")
        import time
        assert cutoff < time.time()

    def test_window_cutoff_24h(self):
        cutoff = _window_cutoff("24h")
        cutoff_1h = _window_cutoff("1h")
        assert cutoff < cutoff_1h


# ════════════════════════════════════════════════════════════════
# 2. RECORD QUERY
# ════════════════════════════════════════════════════════════════


class TestRecordQuery:
    def test_record_returns_dict(self, monitor):
        result = monitor.record_query(
            COMPANY_ID, "parwa", "Hello", "Hi there",
            routing_decision=_sample_routing(),
            confidence_result=_sample_confidence(85.0),
            guardrails_report=_sample_guardrails(True),
            latency_ms=150.0,
        )
        assert isinstance(result, dict)
        assert "timestamp" in result
        assert result["company_id"] == COMPANY_ID

    def test_record_stores_timestamp(self, monitor):
        result = monitor.record_query(COMPANY_ID, "parwa", "Q", "R")
        assert result.get("timestamp") is not None
        assert _parse_iso(result["timestamp"]) is not None

    def test_record_stores_variant(self, monitor):
        result = monitor.record_query(COMPANY_ID, "high_parwa", "Q", "R")
        assert result["variant_type"] == "high_parwa"

    def test_record_stores_latency(self, monitor):
        result = monitor.record_query(COMPANY_ID, "parwa", "Q", "R", latency_ms=250.5)
        assert result["latency_ms"] == 250.5

    def test_record_stores_confidence(self, monitor):
        result = monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            confidence_result=_sample_confidence(72.5, False, 85.0),
        )
        assert result["confidence_score"] == 72.5
        assert result["confidence_passed"] is False
        assert result["confidence_threshold"] == 85.0

    def test_record_stores_guardrails(self, monitor):
        result = monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            guardrails_report=_sample_guardrails(False, 2, 1),
        )
        assert result["guardrails_passed"] is False
        assert result["guardrails_blocked_count"] == 2
        assert result["guardrails_flagged_count"] == 1

    def test_record_stores_error(self, monitor):
        result = monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R", error="timeout",
        )
        assert result["error"] == "timeout"
        assert result["has_error"] is True

    def test_record_defaults_no_error(self, monitor):
        result = monitor.record_query(COMPANY_ID, "parwa", "Q", "R")
        assert result["has_error"] is False

    def test_record_stores_provider_info(self, monitor):
        result = monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            routing_decision=_sample_routing("cerebras", "llama-8b", "light"),
        )
        assert result["provider"] == "cerebras"
        assert result["model_id"] == "llama-8b"
        assert result["tier"] == "light"

    def test_record_defaults_unknown_provider(self, monitor):
        result = monitor.record_query(COMPANY_ID, "parwa", "Q", "R")
        assert result["provider"] == "unknown"
        assert result["model_id"] == "unknown"

    def test_record_increments_count(self, monitor):
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R")
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R")
        assert monitor.get_record_count(COMPANY_ID) == 2

    def test_record_company_isolation(self, monitor):
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R")
        assert monitor.get_record_count(ANOTHER_COMPANY) == 0

    def test_record_stores_token_estimates(self, monitor):
        query = "A" * 100
        response = "B" * 200
        result = monitor.record_query(COMPANY_ID, "parwa", query, response)
        assert result["input_tokens"] > 0
        assert result["output_tokens"] > 0
        assert result["output_tokens"] > result["input_tokens"]


# ════════════════════════════════════════════════════════════════
# 3. LATENCY METRICS
# ════════════════════════════════════════════════════════════════


class TestLatencyMetrics:
    def test_empty_returns_zero_stats(self, monitor):
        stats = monitor.get_latency_stats(COMPANY_ID)
        assert stats.count == 0
        assert stats.avg == 0.0

    def test_single_record(self, monitor):
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R", latency_ms=100.0)
        stats = monitor.get_latency_stats(COMPANY_ID)
        assert stats.count == 1
        assert stats.avg == 100.0

    def test_multiple_records_avg(self, monitor):
        for ms in [100, 200, 300]:
            monitor.record_query(COMPANY_ID, "parwa", "Q", "R", latency_ms=ms)
        stats = monitor.get_latency_stats(COMPANY_ID)
        assert stats.count == 3
        assert stats.avg == 200.0

    def test_min_max(self, monitor):
        for ms in [100, 200, 300]:
            monitor.record_query(COMPANY_ID, "parwa", "Q", "R", latency_ms=ms)
        stats = monitor.get_latency_stats(COMPANY_ID)
        assert stats.min_val == 100.0
        assert stats.max_val == 300.0

    def test_filter_by_provider(self, monitor):
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            routing_decision=_sample_routing("google", "g1", "medium"),
            latency_ms=100,
        )
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            routing_decision=_sample_routing("cerebras", "c1", "light"),
            latency_ms=200,
        )
        stats = monitor.get_latency_stats(COMPANY_ID, provider="google")
        assert stats.count == 1
        assert stats.avg == 100.0

    def test_percentiles(self, monitor):
        for ms in range(10, 110, 10):
            monitor.record_query(COMPANY_ID, "parwa", "Q", "R", latency_ms=float(ms))
        stats = monitor.get_latency_stats(COMPANY_ID)
        assert stats.p50 >= 40
        assert stats.p90 >= 85
        assert stats.p99 >= 95


# ════════════════════════════════════════════════════════════════
# 4. CONFIDENCE DISTRIBUTION
# ════════════════════════════════════════════════════════════════


class TestConfidenceDistribution:
    def test_empty_returns_defaults(self, monitor):
        dist = monitor.get_confidence_distribution(COMPANY_ID)
        assert dist.total_count == 0
        assert dist.avg_score == 50.0

    def test_single_bucket(self, monitor):
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            confidence_result=_sample_confidence(15.0),
        )
        dist = monitor.get_confidence_distribution(COMPANY_ID)
        assert dist.total_count == 1
        assert dist.buckets["0-20"] == 1

    def test_multiple_buckets(self, monitor):
        for score in [10, 30, 50, 70, 90]:
            monitor.record_query(
                COMPANY_ID, "parwa", "Q", "R",
                confidence_result=_sample_confidence(float(score)),
            )
        dist = monitor.get_confidence_distribution(COMPANY_ID)
        assert dist.total_count == 5
        assert dist.buckets["0-20"] == 1
        assert dist.buckets["20-40"] == 1
        assert dist.buckets["40-60"] == 1
        assert dist.buckets["60-80"] == 1
        assert dist.buckets["80-100"] == 1

    def test_avg_score(self, monitor):
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            confidence_result=_sample_confidence(60.0),
        )
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            confidence_result=_sample_confidence(80.0),
        )
        dist = monitor.get_confidence_distribution(COMPANY_ID)
        assert dist.avg_score == 70.0

    def test_pass_rate(self, monitor):
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            confidence_result=_sample_confidence(90.0, True),
        )
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            confidence_result=_sample_confidence(50.0, False),
        )
        dist = monitor.get_confidence_distribution(COMPANY_ID)
        assert dist.pass_rate == 0.5


# ════════════════════════════════════════════════════════════════
# 5. GUARDRAIL STATS
# ════════════════════════════════════════════════════════════════


class TestGuardrailStats:
    def test_empty_returns_defaults(self, monitor):
        stats = monitor.get_guardrail_stats(COMPANY_ID)
        assert stats.total_checked == 0
        assert stats.pass_rate == 1.0

    def test_all_pass(self, monitor):
        for _ in range(5):
            monitor.record_query(
                COMPANY_ID, "parwa", "Q", "R",
                guardrails_report=_sample_guardrails(True),
            )
        stats = monitor.get_guardrail_stats(COMPANY_ID)
        assert stats.total_checked == 5
        assert stats.pass_rate == 1.0
        assert stats.block_rate == 0.0

    def test_all_blocked(self, monitor):
        for _ in range(5):
            monitor.record_query(
                COMPANY_ID, "parwa", "Q", "R",
                guardrails_report=_sample_guardrails(False, 1),
            )
        stats = monitor.get_guardrail_stats(COMPANY_ID)
        assert stats.block_rate == 1.0
        assert stats.pass_rate == 0.0

    def test_mixed_pass_block(self, monitor):
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            guardrails_report=_sample_guardrails(True),
        )
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            guardrails_report=_sample_guardrails(False, 1),
        )
        stats = monitor.get_guardrail_stats(COMPANY_ID)
        assert stats.block_rate == 0.5
        assert stats.pass_rate == 0.5

    def test_per_layer_breakdown(self, monitor):
        layer_results = [
            {"layer": "content_safety", "action": "allow"},
            {"layer": "pii_leak", "action": "block"},
        ]
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            guardrails_report=_sample_guardrails(
                False, 1, 0, results=layer_results,
            ),
        )
        stats = monitor.get_guardrail_stats(COMPANY_ID)
        layer_map = {lb.layer: lb for lb in stats.per_layer}
        assert "content_safety" in layer_map
        assert "pii_leak" in layer_map
        assert layer_map["pii_leak"].blocked == 1


# ════════════════════════════════════════════════════════════════
# 6. TOKEN USAGE
# ════════════════════════════════════════════════════════════════


class TestTokenUsage:
    def test_empty_returns_defaults(self, monitor):
        usage = monitor.get_token_usage(COMPANY_ID)
        assert usage.total_requests == 0
        assert usage.total_input_tokens == 0

    def test_tracks_tokens(self, monitor):
        monitor.record_query(COMPANY_ID, "parwa", "A" * 100, "B" * 200)
        usage = monitor.get_token_usage(COMPANY_ID)
        assert usage.total_requests == 1
        assert usage.total_input_tokens > 0
        assert usage.total_output_tokens > 0

    def test_avg_per_request(self, monitor):
        monitor.record_query(COMPANY_ID, "parwa", "A" * 100, "B" * 200)
        monitor.record_query(COMPANY_ID, "parwa", "A" * 100, "B" * 200)
        usage = monitor.get_token_usage(COMPANY_ID)
        assert usage.avg_input_per_request > 0
        assert usage.avg_output_per_request > 0


# ════════════════════════════════════════════════════════════════
# 7. ERROR METRICS
# ════════════════════════════════════════════════════════════════


class TestErrorMetrics:
    def test_empty_returns_defaults(self, monitor):
        errors = monitor.get_error_metrics(COMPANY_ID)
        assert errors.total_errors == 0
        assert errors.error_rate == 0.0

    def test_tracks_errors(self, monitor):
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R", error="timeout")
        errors = monitor.get_error_metrics(COMPANY_ID)
        assert errors.total_errors == 1
        assert errors.error_rate == 1.0

    def test_error_rate_mixed(self, monitor):
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R")
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R", error="timeout")
        errors = monitor.get_error_metrics(COMPANY_ID)
        assert errors.error_rate == 0.5

    def test_error_by_type(self, monitor):
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R", error="timeout")
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R", error="rate_limit")
        errors = monitor.get_error_metrics(COMPANY_ID)
        assert errors.error_by_type.get("timeout") == 1
        assert errors.error_by_type.get("rate_limit") == 1

    def test_error_by_provider(self, monitor):
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            routing_decision=_sample_routing("google"),
            error="timeout",
        )
        errors = monitor.get_error_metrics(COMPANY_ID)
        assert errors.error_by_provider.get("google") == 1


# ════════════════════════════════════════════════════════════════
# 8. PROVIDER COMPARISON
# ════════════════════════════════════════════════════════════════


class TestProviderComparison:
    def test_empty_returns_empty_list(self, monitor):
        comparison = monitor.get_provider_comparison(COMPANY_ID)
        assert comparison == []

    def test_multiple_providers(self, monitor):
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            routing_decision=_sample_routing("google", "g1", "medium"),
            latency_ms=100,
        )
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            routing_decision=_sample_routing("cerebras", "c1", "light"),
            latency_ms=50,
        )
        comparison = monitor.get_provider_comparison(COMPANY_ID)
        providers = [c.provider for c in comparison]
        assert "google" in providers
        assert "cerebras" in providers

    def test_comparison_latency(self, monitor):
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            routing_decision=_sample_routing("google"),
            latency_ms=100,
        )
        comparison = monitor.get_provider_comparison(COMPANY_ID)
        google = [c for c in comparison if c.provider == "google"][0]
        assert google.latency is not None
        assert google.latency.avg == 100.0

    def test_comparison_confidence(self, monitor):
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            routing_decision=_sample_routing("google"),
            confidence_result=_sample_confidence(75.0),
        )
        comparison = monitor.get_provider_comparison(COMPANY_ID)
        google = [c for c in comparison if c.provider == "google"][0]
        assert google.confidence_avg == 75.0

    def test_comparison_error_rate(self, monitor):
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            routing_decision=_sample_routing("google"),
        )
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            routing_decision=_sample_routing("google"),
            error="timeout",
        )
        comparison = monitor.get_provider_comparison(COMPANY_ID)
        google = [c for c in comparison if c.provider == "google"][0]
        assert google.error_rate == 0.5


# ════════════════════════════════════════════════════════════════
# 9. VARIANT METRICS
# ════════════════════════════════════════════════════════════════


class TestVariantMetrics:
    def test_empty_returns_empty(self, monitor):
        metrics = monitor.get_variant_metrics(COMPANY_ID)
        assert metrics == {}

    def test_per_variant_breakdown(self, monitor):
        monitor.record_query(COMPANY_ID, "mini_parwa", "Q", "R", latency_ms=50)
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R", latency_ms=150)
        metrics = monitor.get_variant_metrics(COMPANY_ID)
        assert "mini_parwa" in metrics
        assert "parwa" in metrics
        assert metrics["mini_parwa"]["avg_latency"] == 50.0
        assert metrics["parwa"]["avg_latency"] == 150.0

    def test_variant_error_rate(self, monitor):
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R")
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R", error="fail")
        metrics = monitor.get_variant_metrics(COMPANY_ID)
        assert metrics["parwa"]["error_rate"] == 0.5

    def test_variant_block_rate(self, monitor):
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            guardrails_report=_sample_guardrails(True),
        )
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            guardrails_report=_sample_guardrails(False, 1),
        )
        metrics = monitor.get_variant_metrics(COMPANY_ID)
        assert metrics["parwa"]["block_rate"] == 0.5


# ════════════════════════════════════════════════════════════════
# 10. ALERT CONDITIONS
# ════════════════════════════════════════════════════════════════


class TestAlertConditions:
    def test_no_alerts_when_healthy(self, monitor):
        for _ in range(5):
            monitor.record_query(
                COMPANY_ID, "parwa", "Q", "R",
                confidence_result=_sample_confidence(85.0, True),
                latency_ms=100,
            )
        alerts = monitor.get_alert_conditions(COMPANY_ID)
        critical = [a for a in alerts if a.level == AlertLevel.CRITICAL.value]
        assert len(critical) == 0

    def test_critical_error_rate_alert(self, monitor):
        for _ in range(10):
            monitor.record_query(
                COMPANY_ID, "parwa", "Q", "R", error="timeout",
            )
        alerts = monitor.get_alert_conditions(COMPANY_ID)
        critical = [a for a in alerts if a.level == AlertLevel.CRITICAL.value]
        assert len(critical) > 0
        assert "error" in critical[0].message.lower()

    def test_warning_error_rate_alert(self, monitor):
        # 3 errors out of 10 = 30% which is > 10% but < 25%... actually need >10%
        for _ in range(7):
            monitor.record_query(COMPANY_ID, "parwa", "Q", "R")
        for _ in range(3):
            monitor.record_query(
                COMPANY_ID, "parwa", "Q", "R", error="fail",
            )
        alerts = monitor.get_alert_conditions(COMPANY_ID)
        warnings = [a for a in alerts if a.level == AlertLevel.WARNING.value]
        assert len(warnings) > 0

    def test_confidence_drop_alert(self, monitor):
        for _ in range(10):
            monitor.record_query(
                COMPANY_ID, "parwa", "Q", "R",
                confidence_result=_sample_confidence(30.0, False),
            )
        alerts = monitor.get_alert_conditions(COMPANY_ID)
        conf_alerts = [
            a for a in alerts
            if "confidence" in a.condition_id
        ]
        assert len(conf_alerts) > 0

    def test_provider_unhealthy_alert(self, monitor):
        for _ in range(15):
            monitor.record_query(
                COMPANY_ID, "parwa", "Q", "R",
                routing_decision=_sample_routing("google"),
                error="fail",
            )
        alerts = monitor.get_alert_conditions(COMPANY_ID)
        provider_alerts = [
            a for a in alerts
            if "provider_unhealthy" in a.condition_id
        ]
        assert len(provider_alerts) > 0

    def test_alert_stored(self, monitor):
        monitor.get_alert_conditions(COMPANY_ID)
        stored = monitor.get_stored_alerts(COMPANY_ID)
        assert isinstance(stored, list)


# ════════════════════════════════════════════════════════════════
# 11. DASHBOARD SNAPSHOT
# ════════════════════════════════════════════════════════════════


class TestDashboardSnapshot:
    def test_returns_dashboard(self, monitor):
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R")
        dashboard = monitor.get_dashboard_data(COMPANY_ID)
        assert isinstance(dashboard, DashboardSnapshot)

    def test_dashboard_has_all_sections(self, monitor):
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R")
        dashboard = monitor.get_dashboard_data(COMPANY_ID)
        assert dashboard.latency is not None
        assert dashboard.confidence is not None
        assert dashboard.guardrails is not None
        assert dashboard.blocked_responses is not None
        assert dashboard.token_usage is not None
        assert dashboard.errors is not None
        assert dashboard.alerts is not None
        assert dashboard.providers is not None
        assert dashboard.variant_metrics is not None

    def test_dashboard_has_timestamp(self, monitor):
        dashboard = monitor.get_dashboard_data(COMPANY_ID)
        assert dashboard.snapshot_at is not None
        assert _parse_iso(dashboard.snapshot_at) is not None

    def test_dashboard_total_requests(self, monitor):
        for _ in range(5):
            monitor.record_query(COMPANY_ID, "parwa", "Q", "R")
        dashboard = monitor.get_dashboard_data(COMPANY_ID)
        assert dashboard.total_requests == 5

    def test_dashboard_latency_overall(self, monitor):
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R", latency_ms=200)
        dashboard = monitor.get_dashboard_data(COMPANY_ID)
        assert "overall" in dashboard.latency
        assert dashboard.latency["overall"].avg == 200.0

    def test_empty_dashboard_safe(self, monitor):
        dashboard = monitor.get_dashboard_data("nonexistent-company")
        assert isinstance(dashboard, DashboardSnapshot)


# ════════════════════════════════════════════════════════════════
# 12. BLOCKED RESPONSE METRICS
# ════════════════════════════════════════════════════════════════


class TestBlockedResponseMetrics:
    def test_empty_returns_zero(self, monitor):
        metrics = monitor.get_blocked_metrics(COMPANY_ID)
        assert metrics.total_blocked == 0

    def test_counts_blocked(self, monitor):
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            guardrails_report=_sample_guardrails(False, 1),
        )
        metrics = monitor.get_blocked_metrics(COMPANY_ID)
        assert metrics.total_blocked == 1

    def test_ignores_passed(self, monitor):
        monitor.record_query(
            COMPANY_ID, "parwa", "Q", "R",
            guardrails_report=_sample_guardrails(True),
        )
        metrics = monitor.get_blocked_metrics(COMPANY_ID)
        assert metrics.total_blocked == 0


# ════════════════════════════════════════════════════════════════
# 13. DATA PRUNING
# ════════════════════════════════════════════════════════════════


class TestDataPruning:
    def test_prune_respects_max(self, monitor):
        from app.core.ai_monitoring_service import _MAX_DATA_POINTS
        for i in range(_MAX_DATA_POINTS + 20):
            monitor.record_query(COMPANY_ID, "parwa", f"Q{i}", f"R{i}")
        count = monitor.get_record_count(COMPANY_ID)
        assert count <= _MAX_DATA_POINTS

    def test_newest_records_kept_after_prune(self, monitor):
        from app.core.ai_monitoring_service import _MAX_DATA_POINTS
        for i in range(_MAX_DATA_POINTS + 10):
            monitor.record_query(
                COMPANY_ID, "parwa", "Q", f"R-{i}",
                latency_ms=float(i),
            )
        stats = monitor.get_latency_stats(COMPANY_ID)
        # Newest records should have highest latency values
        assert stats.max_val >= _MAX_DATA_POINTS


# ════════════════════════════════════════════════════════════════
# 14. EDGE CASES
# ════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_record_with_none_values(self, monitor):
        result = monitor.record_query(
            COMPANY_ID, "parwa", None, None,
            routing_decision=None,
            confidence_result=None,
            guardrails_report=None,
        )
        assert isinstance(result, dict)

    def test_record_with_empty_strings(self, monitor):
        result = monitor.record_query(COMPANY_ID, "", "", "")
        assert isinstance(result, dict)

    def test_latency_stats_unknown_company(self, monitor):
        stats = monitor.get_latency_stats("nonexistent")
        assert stats.count == 0

    def test_confidence_unknown_company(self, monitor):
        dist = monitor.get_confidence_distribution("nonexistent")
        assert dist.total_count == 0

    def test_guardrail_stats_unknown_company(self, monitor):
        stats = monitor.get_guardrail_stats("nonexistent")
        assert stats.total_checked == 0

    def test_error_metrics_unknown_company(self, monitor):
        errors = monitor.get_error_metrics("nonexistent")
        assert errors.total_errors == 0

    def test_dashboard_unknown_company(self, monitor):
        dashboard = monitor.get_dashboard_data("nonexistent")
        assert dashboard.total_requests == 0

    def test_reset_clears_everything(self, monitor):
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R")
        monitor.get_alert_conditions(COMPANY_ID)
        assert monitor.get_record_count(COMPANY_ID) > 0
        monitor.reset()
        assert monitor.get_record_count(COMPANY_ID) == 0

    def test_record_count_unknown_company(self, monitor):
        assert monitor.get_record_count("no-company") == 0

    def test_multiple_companies_isolated(self, monitor):
        monitor.record_query(COMPANY_ID, "parwa", "Q", "R", latency_ms=100)
        monitor.record_query(ANOTHER_COMPANY, "parwa", "Q", "R", latency_ms=200)
        stats1 = monitor.get_latency_stats(COMPANY_ID)
        stats2 = monitor.get_latency_stats(ANOTHER_COMPANY)
        assert stats1.avg == 100.0
        assert stats2.avg == 200.0

    def test_unicode_content(self, monitor):
        result = monitor.record_query(
            COMPANY_ID, "parwa",
            "こんにちは世界", "🎉 Это тест",
        )
        assert isinstance(result, dict)
        assert result["input_tokens"] > 0


# ════════════════════════════════════════════════════════════════
# 15. DATA CLASS STRUCTURE
# ════════════════════════════════════════════════════════════════


class TestDataClassStructure:
    def test_metric_point(self):
        mp = MetricPoint(timestamp="2025-01-01T00:00:00Z", value=42.0)
        assert mp.value == 42.0

    def test_latency_stats(self):
        ls = LatencyStats(avg=1.0, p50=2.0, p90=3.0, p99=4.0, min_val=0.5, max_val=5.0, count=10)
        assert ls.avg == 1.0

    def test_confidence_distribution(self):
        cd = ConfidenceDistribution(total_count=10)
        assert cd.total_count == 10

    def test_guardrail_stats(self):
        gs = GuardrailStats(total_checked=5)
        assert gs.total_checked == 5

    def test_blocked_response_metrics(self):
        brm = BlockedResponseMetrics(total_blocked=3)
        assert brm.total_blocked == 3

    def test_token_usage_metrics(self):
        tum = TokenUsageMetrics(total_requests=7)
        assert tum.total_requests == 7

    def test_error_metrics(self):
        em = ErrorMetrics(total_errors=2)
        assert em.total_errors == 2

    def test_provider_comparison(self):
        pc = ProviderComparison(provider="google")
        assert pc.provider == "google"

    def test_alert_condition(self):
        ac = AlertCondition(
            condition_id="test", level="warning",
            message="Test alert", metric_value=50.0,
            threshold=25.0, timestamp=_now_utc(),
        )
        assert ac.level == "warning"

    def test_dashboard_snapshot(self):
        ds = DashboardSnapshot(snapshot_at=_now_utc())
        assert ds.total_requests == 0


# ════════════════════════════════════════════════════════════════
# 16. GAP TESTS — Alert Threshold Boundaries
# ════════════════════════════════════════════════════════════════


class TestAlertBoundaryConditions:
    """Gap 5: Test exactly at threshold boundaries (strict > / < checks)."""

    def test_error_rate_exactly_10_percent_no_warning(self, monitor):
        """Error rate exactly 10% should NOT trigger warning (uses > not >=)."""
        for i in range(9):
            monitor.record_query("bnd_co1", "parwa", "q", "r", latency_ms=100)
        monitor.record_query(
            "bnd_co1", "parwa", "q", "r", latency_ms=100, error="fail",
        )
        alerts = monitor.get_alert_conditions("bnd_co1")
        error_alerts = [a for a in alerts if "error_rate" in a.condition_id]
        assert len(error_alerts) == 0

    def test_error_rate_above_10_percent_triggers_warning(self, monitor):
        """Error rate > 10% should trigger warning."""
        for i in range(9):
            monitor.record_query("bnd_co2", "parwa", "q", "r", latency_ms=100)
        monitor.record_query(
            "bnd_co2", "parwa", "q", "r", latency_ms=100, error="fail",
        )
        monitor.record_query(
            "bnd_co2", "parwa", "q", "r", latency_ms=100, error="fail",
        )
        alerts = monitor.get_alert_conditions("bnd_co2")
        warning = [
            a for a in alerts if a.condition_id == "error_rate_warning"
        ]
        assert len(warning) == 1

    def test_error_rate_exactly_25_percent_no_critical(self, monitor):
        """Error rate exactly 25% should NOT trigger critical."""
        for i in range(3):
            monitor.record_query(
                "bnd_co3", "parwa", "q", "r", latency_ms=100, error="fail",
            )
        for i in range(9):
            monitor.record_query("bnd_co3", "parwa", "q", "r", latency_ms=100)
        alerts = monitor.get_alert_conditions("bnd_co3")
        critical = [
            a for a in alerts if a.condition_id == "error_rate_critical"
        ]
        assert len(critical) == 0

    def test_confidence_avg_exactly_60_no_alert(self, monitor):
        """Average confidence exactly 60.0 should NOT trigger warning (< 60)."""
        monitor.record_query(
            "bnd_co4", "parwa", "q", "r",
            confidence_result={"overall_score": 60.0, "passed": True},
        )
        alerts = monitor.get_alert_conditions("bnd_co4")
        conf_alerts = [a for a in alerts if "confidence" in a.condition_id]
        assert len(conf_alerts) == 0

    def test_confidence_avg_below_60_triggers_alert(self, monitor):
        """Average confidence < 60 should trigger warning."""
        for _ in range(5):
            monitor.record_query(
                "bnd_co5", "parwa", "q", "r",
                confidence_result={"overall_score": 50.0, "passed": False},
            )
        alerts = monitor.get_alert_conditions("bnd_co5")
        conf_alerts = [
            a for a in alerts if "confidence" in a.condition_id
        ]
        assert len(conf_alerts) > 0

    def test_p90_latency_exactly_5000_no_alert(self, monitor):
        """P90 latency exactly 5000ms should NOT trigger warning (> 5000)."""
        for _ in range(10):
            monitor.record_query(
                "bnd_co6", "parwa", "q", "r", latency_ms=5000.0,
            )
        alerts = monitor.get_alert_conditions("bnd_co6")
        lat_alerts = [a for a in alerts if "latency" in a.condition_id]
        assert len(lat_alerts) == 0


# ════════════════════════════════════════════════════════════════
# 17. GAP TESTS — Bucket Boundary + Helper Edge Cases
# ════════════════════════════════════════════════════════════════


class TestBucketBoundariesAndHelperEdgeCases:
    """Gap 17 & 20: Bucket edge cases, invalid window, large strings."""

    def test_confidence_bucket_score_0(self):
        assert _confidence_bucket(0.0) == "0-20"

    def test_confidence_bucket_score_100(self):
        assert _confidence_bucket(100.0) == "80-100"

    def test_confidence_bucket_score_40(self):
        assert _confidence_bucket(40.0) == "40-60"

    def test_confidence_bucket_score_60(self):
        assert _confidence_bucket(60.0) == "60-80"

    def test_confidence_bucket_score_80(self):
        assert _confidence_bucket(80.0) == "80-100"

    def test_confidence_bucket_negative_score(self):
        assert _confidence_bucket(-5.0) == "0-20"

    def test_estimate_tokens_very_long_string(self):
        result = _estimate_tokens("x" * 1_000_000)
        assert result == 250_000

    def test_window_cutoff_invalid_string(self):
        import time
        cutoff = _window_cutoff("invalid_string")
        expected = time.time() - 86400  # defaults to 24h
        assert abs(cutoff - expected) < 2

    def test_window_cutoff_empty_string(self):
        import time
        cutoff = _window_cutoff("")
        expected = time.time() - 86400
        assert abs(cutoff - expected) < 2


# ════════════════════════════════════════════════════════════════
# 18. GAP TESTS — Pruning Boundary
# ════════════════════════════════════════════════════════════════


class TestPruningBoundary:
    """Gap 11: Exact boundary at _MAX_DATA_POINTS."""

    def test_exactly_at_max_no_prune(self, monitor):
        from app.core.ai_monitoring_service import _MAX_DATA_POINTS
        for i in range(_MAX_DATA_POINTS):
            monitor.record_query(
                "prune_bnd", "parwa", f"Q{i}", f"R{i}",
            )
        assert monitor.get_record_count("prune_bnd") == _MAX_DATA_POINTS

    def test_at_max_plus_one_prunes(self, monitor):
        from app.core.ai_monitoring_service import _MAX_DATA_POINTS
        for i in range(_MAX_DATA_POINTS + 1):
            monitor.record_query(
                "prune_bnd2", "parwa", f"Q{i}", f"R{i}",
            )
        assert monitor.get_record_count("prune_bnd2") == _MAX_DATA_POINTS


# ════════════════════════════════════════════════════════════════
# 19. GAP TESTS — Real Concurrency
# ════════════════════════════════════════════════════════════════


class TestMonitoringConcurrency:
    """Gap 4: Real multithreading tests for monitoring service."""

    def test_record_and_read_concurrently(self, monitor):
        """Multiple threads recording and reading should not crash."""
        import threading

        errors = []

        def writer(tid):
            try:
                for j in range(25):
                    monitor.record_query(
                        "conc_co", "parwa",
                        f"q-{tid}-{j}", f"r-{tid}-{j}",
                        latency_ms=100.0 + tid,
                    )
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(25):
                    monitor.get_latency_stats("conc_co")
                    monitor.get_confidence_distribution("conc_co")
                    monitor.get_alert_conditions("conc_co")
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(4):
            threads.append(threading.Thread(target=writer, args=(i,)))
        threads.append(threading.Thread(target=reader))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Concurrent errors: {errors}"
        # Records may be less than 100 due to pruning (_MAX_DATA_POINTS=50)
        assert monitor.get_record_count("conc_co") > 0
