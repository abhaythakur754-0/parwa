"""
Tests for Context Health Meter — Week 10 Day 12
Feature: F-201
Target: 65+ tests
"""

from unittest.mock import MagicMock, patch

import pytest


# Runtime-injected by _mock_logger fixture — satisfies flake8 F821
ContextHealthMeter = HealthConfig = HealthMetrics = HealthReport = HealthAlert = HealthStatus = HealthAlertType = ContextHealthError = _HEALTH_WEIGHTS = _VARIANT_HEALTH_CONFIGS = None  # type: ignore[assignment,misc]


@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("backend.app.logger.get_logger", return_value=MagicMock()):
        from backend.app.core.context_health import (  # noqa: F811,F401
            ContextHealthError,
            ContextHealthMeter,
            HealthAlert,
            HealthAlertType,
            HealthConfig,
            HealthMetrics,
            HealthReport,
            HealthStatus,
            _HEALTH_WEIGHTS,
            _VARIANT_HEALTH_CONFIGS,
        )
        globals().update({
            "ContextHealthMeter": ContextHealthMeter,
            "HealthConfig": HealthConfig,
            "HealthMetrics": HealthMetrics,
            "HealthReport": HealthReport,
            "HealthAlert": HealthAlert,
            "HealthStatus": HealthStatus,
            "HealthAlertType": HealthAlertType,
            "ContextHealthError": ContextHealthError,
            "_HEALTH_WEIGHTS": _HEALTH_WEIGHTS,
            "_VARIANT_HEALTH_CONFIGS": _VARIANT_HEALTH_CONFIGS,
        })


def _make_healthy_metrics():
    """Factory: create metrics representing a healthy context."""
    return HealthMetrics(
        token_usage_ratio=0.1,
        compression_ratio=0.95,
        relevance_score=0.95,
        freshness_score=0.9,
        signal_preservation=0.95,
        context_coherence=0.95,
    )


def _make_degrading_metrics():
    """Factory: create metrics representing a degrading context."""
    return HealthMetrics(
        token_usage_ratio=0.5,
        compression_ratio=0.6,
        relevance_score=0.55,
        freshness_score=0.5,
        signal_preservation=0.5,
        context_coherence=0.5,
    )


def _make_critical_metrics():
    """Factory: create metrics representing a critical context."""
    return HealthMetrics(
        token_usage_ratio=0.95,
        compression_ratio=0.1,
        relevance_score=0.1,
        freshness_score=0.05,
        signal_preservation=0.1,
        context_coherence=0.1,
    )


# ═══════════════════════════════════════════════════════════════════════
# 1. HealthConfig (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestHealthConfig:
    def test_default_company_id_empty(self):
        cfg = HealthConfig()
        assert cfg.company_id == ""

    def test_default_variant_type_parwa(self):
        cfg = HealthConfig()
        assert cfg.variant_type == "parwa"

    def test_default_token_budget_threshold(self):
        cfg = HealthConfig()
        assert cfg.token_budget_threshold == 0.8

    def test_default_compression_ratio_threshold(self):
        cfg = HealthConfig()
        assert cfg.compression_ratio_threshold == 0.4

    def test_default_relevance_decay_rate(self):
        cfg = HealthConfig()
        assert cfg.relevance_decay_rate == 0.1

    def test_default_freshness_decay_minutes(self):
        cfg = HealthConfig()
        assert cfg.freshness_decay_minutes == 30

    def test_custom_values(self):
        cfg = HealthConfig(
            company_id="corp-1",
            variant_type="parwa_high",
            token_budget_threshold=0.7,
            alert_cooldown_seconds=120,
        )
        assert cfg.company_id == "corp-1"
        assert cfg.variant_type == "parwa_high"
        assert cfg.token_budget_threshold == 0.7
        assert cfg.alert_cooldown_seconds == 120

    def test_alert_cooldown_default(self):
        cfg = HealthConfig()
        assert cfg.alert_cooldown_seconds == 60


# ═══════════════════════════════════════════════════════════════════════
# 2. HealthMetrics (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestHealthMetrics:
    def test_defaults(self):
        m = HealthMetrics()
        assert m.token_usage_ratio == 0.0
        assert m.compression_ratio == 1.0
        assert m.relevance_score == 1.0
        assert m.freshness_score == 1.0
        assert m.signal_preservation == 1.0
        assert m.context_coherence == 1.0

    def test_token_usage_ratio_default_zero(self):
        m = HealthMetrics()
        assert m.token_usage_ratio == 0.0

    def test_compression_ratio_default_one(self):
        m = HealthMetrics()
        assert m.compression_ratio == 1.0

    def test_all_fields_assignable(self):
        m = HealthMetrics(
            token_usage_ratio=0.9,
            compression_ratio=0.2,
            relevance_score=0.3,
            freshness_score=0.4,
            signal_preservation=0.5,
            context_coherence=0.6,
        )
        assert m.token_usage_ratio == 0.9
        assert m.relevance_score == 0.3

    def test_boundary_values(self):
        m = HealthMetrics(
            token_usage_ratio=1.0,
            compression_ratio=0.0,
        )
        assert m.token_usage_ratio == 1.0
        assert m.compression_ratio == 0.0

    def test_all_floats(self):
        m = _make_healthy_metrics()
        for attr in [
            "token_usage_ratio", "compression_ratio",
            "relevance_score", "freshness_score",
            "signal_preservation", "context_coherence",
        ]:
            assert isinstance(getattr(m, attr), float)


# ═══════════════════════════════════════════════════════════════════════
# 3. HealthAlert (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestHealthAlert:
    def test_creation(self):
        alert = HealthAlert(
            alert_type=HealthAlertType.TOKEN_BUDGET_LOW,
            severity=HealthStatus.DEGRADING,
            message="Token budget low",
            metric_name="token_usage_ratio",
            metric_value=0.9,
            threshold=0.8,
        )
        assert alert.alert_type == HealthAlertType.TOKEN_BUDGET_LOW
        assert alert.metric_name == "token_usage_ratio"
        assert alert.metric_value == 0.9
        assert alert.threshold == 0.8

    def test_default_timestamp_empty(self):
        alert = HealthAlert(
            alert_type=HealthAlertType.SIGNAL_DEGRADATION,
            severity=HealthStatus.CRITICAL,
            message="Signals lost",
            metric_name="signal_preservation",
            metric_value=0.2,
            threshold=0.5,
        )
        assert alert.timestamp == ""

    def test_alert_type_assignable(self):
        alert = HealthAlert(
            alert_type=HealthAlertType.FRESHNESS_EXPIRED,
            severity=HealthStatus.DEGRADING,
            message="Fresh",
            metric_name="freshness_score",
            metric_value=0.1,
            threshold=0.4,
        )
        assert isinstance(alert.alert_type, HealthAlertType)

    def test_severity_assignable(self):
        alert = HealthAlert(
            alert_type=HealthAlertType.CONTEXT_DRIFT,
            severity=HealthStatus.HEALTHY,
            message="drift",
            metric_name="context_drift",
            metric_value=0.1,
            threshold=0.3,
        )
        assert isinstance(alert.severity, HealthStatus)

    def test_metric_fields(self):
        alert = HealthAlert(
            alert_type=HealthAlertType.COMPRESSION_RATIO_HIGH,
            severity=HealthStatus.DEGRADING,
            message="compress",
            metric_name="compression_ratio",
            metric_value=0.2,
            threshold=0.4,
        )
        assert alert.metric_value == 0.2
        assert alert.threshold == 0.4
        assert alert.message == "compress"


# ═══════════════════════════════════════════════════════════════════════
# 4. HealthReport (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestHealthReport:
    def test_creation(self):
        r = HealthReport(
            company_id="c1",
            conversation_id="conv1",
            overall_score=0.85,
            status=HealthStatus.HEALTHY,
        )
        assert r.company_id == "c1"
        assert r.conversation_id == "conv1"
        assert r.overall_score == 0.85
        assert r.status == HealthStatus.HEALTHY

    def test_defaults(self):
        r = HealthReport()
        assert r.company_id == ""
        assert r.conversation_id == ""
        assert r.overall_score == 1.0
        assert r.status == HealthStatus.HEALTHY
        assert r.turn_number == 0
        assert r.alerts == []
        assert r.recommendations == []

    def test_status_mapping(self):
        for status in HealthStatus:
            r = HealthReport(status=status)
            assert r.status == status

    def test_recommendations_list(self):
        r = HealthReport(
            recommendations=["action 1", "action 2"],
        )
        assert len(r.recommendations) == 2

    def test_metrics_default_factory(self):
        r1 = HealthReport()
        r2 = HealthReport()
        # default_factory should create independent instances
        assert r1.metrics is not r2.metrics

    def test_timestamp_default_empty(self):
        r = HealthReport()
        assert r.timestamp == ""


# ═══════════════════════════════════════════════════════════════════════
# 5. HealthStatus (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestHealthStatus:
    def test_enum_values(self):
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADING.value == "degrading"
        assert HealthStatus.CRITICAL.value == "critical"
        assert HealthStatus.EXHAUSTED.value == "exhausted"

    def test_string_conversion(self):
        assert str(HealthStatus.HEALTHY) == "HealthStatus.HEALTHY"
        assert HealthStatus.HEALTHY.value == "healthy"

    def test_four_statuses(self):
        assert len(HealthStatus) == 4

    def test_unique_values(self):
        values = [s.value for s in HealthStatus]
        assert len(values) == len(set(values))


# ═══════════════════════════════════════════════════════════════════════
# 6. HealthAlertType (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestHealthAlertType:
    def test_five_types(self):
        assert len(HealthAlertType) == 5

    def test_all_values_are_strings(self):
        for at in HealthAlertType:
            assert isinstance(at.value, str)

    def test_unique_values(self):
        values = [at.value for at in HealthAlertType]
        assert len(values) == len(set(values))

    def test_all_types_covered(self):
        expected = {
            "token_budget_low",
            "compression_ratio_high",
            "signal_degradation",
            "context_drift",
            "freshness_expired",
        }
        actual = {at.value for at in HealthAlertType}
        assert actual == expected


# ═══════════════════════════════════════════════════════════════════════
# 7. Overall Score (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestOverallScore:
    def test_perfect_metrics_gives_high_score(self):
        meter = ContextHealthMeter()
        score = meter._calculate_overall_score(_make_healthy_metrics())
        assert score >= 0.7

    def test_zero_metrics_gives_low_score(self):
        meter = ContextHealthMeter()
        m = HealthMetrics(
            token_usage_ratio=1.0,
            compression_ratio=0.0,
            relevance_score=0.0,
            freshness_score=0.0,
            signal_preservation=0.0,
            context_coherence=0.0,
        )
        score = meter._calculate_overall_score(m)
        assert score < 0.2

    def test_mixed_metrics(self):
        meter = ContextHealthMeter()
        score = meter._calculate_overall_score(_make_degrading_metrics())
        assert 0.0 <= score <= 1.0

    def test_weights_sum_to_one(self):
        total = sum(_HEALTH_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_score_bounded_zero_to_one(self):
        meter = ContextHealthMeter()
        for metrics in [
            _make_healthy_metrics(),
            _make_degrading_metrics(),
            _make_critical_metrics(),
            HealthMetrics(),
        ]:
            score = meter._calculate_overall_score(metrics)
            assert 0.0 <= score <= 1.0


# ═══════════════════════════════════════════════════════════════════════
# 8. Status Determination (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestStatusDetermination:
    def test_healthy_threshold(self):
        meter = ContextHealthMeter()
        assert meter._determine_status(0.85) == HealthStatus.HEALTHY
        assert meter._determine_status(0.7) == HealthStatus.HEALTHY

    def test_degrading_threshold(self):
        meter = ContextHealthMeter()
        assert meter._determine_status(0.65) == HealthStatus.DEGRADING
        assert meter._determine_status(0.4) == HealthStatus.DEGRADING

    def test_critical_threshold(self):
        meter = ContextHealthMeter()
        assert meter._determine_status(0.35) == HealthStatus.CRITICAL
        assert meter._determine_status(0.2) == HealthStatus.CRITICAL

    def test_exhausted_threshold(self):
        meter = ContextHealthMeter()
        assert meter._determine_status(0.1) == HealthStatus.EXHAUSTED
        assert meter._determine_status(0.0) == HealthStatus.EXHAUSTED

    def test_boundary_070(self):
        meter = ContextHealthMeter()
        assert meter._determine_status(0.7) == HealthStatus.HEALTHY
        assert meter._determine_status(0.699) == HealthStatus.DEGRADING


# ═══════════════════════════════════════════════════════════════════════
# 9. CheckHealth (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCheckHealth:
    @pytest.mark.asyncio
    async def test_healthy_scenario(self):
        meter = ContextHealthMeter()
        report = await meter.check_health(
            "c1", "conv1", _make_healthy_metrics(), turn_number=1,
        )
        assert isinstance(report, HealthReport)
        assert report.company_id == "c1"
        assert report.conversation_id == "conv1"
        assert report.overall_score >= 0.7
        assert report.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_degrading_scenario(self):
        meter = ContextHealthMeter()
        report = await meter.check_health(
            "c1", "conv2", _make_degrading_metrics(), turn_number=3,
        )
        assert report.status in (
            HealthStatus.DEGRADING, HealthStatus.HEALTHY,
            HealthStatus.CRITICAL,
        )
        assert report.turn_number == 3

    @pytest.mark.asyncio
    async def test_critical_scenario(self):
        meter = ContextHealthMeter()
        report = await meter.check_health(
            "c1", "conv3", _make_critical_metrics(), turn_number=5,
        )
        assert report.status in (
            HealthStatus.CRITICAL, HealthStatus.EXHAUSTED,
        )
        assert report.turn_number == 5

    @pytest.mark.asyncio
    async def test_alerts_generated_for_critical(self):
        meter = ContextHealthMeter()
        report = await meter.check_health(
            "c1", "conv4", _make_critical_metrics(),
        )
        # Critical metrics should generate at least one alert
        assert len(report.alerts) >= 1

    @pytest.mark.asyncio
    async def test_recommendations_populated(self):
        meter = ContextHealthMeter()
        report = await meter.check_health(
            "c1", "conv5", _make_critical_metrics(),
        )
        assert len(report.recommendations) >= 1

    @pytest.mark.asyncio
    async def test_history_stored(self):
        meter = ContextHealthMeter()
        await meter.check_health("c1", "conv6", _make_healthy_metrics())
        history = meter.get_history("c1", "conv6")
        assert len(history) == 1


# ═══════════════════════════════════════════════════════════════════════
# 10. Alert Generation (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestAlertGeneration:
    @pytest.mark.asyncio
    async def test_token_budget_low_alert(self):
        meter = ContextHealthMeter()
        m = HealthMetrics(
            token_usage_ratio=0.95,
            compression_ratio=0.9,
            relevance_score=0.9,
            freshness_score=0.9,
            signal_preservation=0.9,
            context_coherence=0.9,
        )
        report = await meter.check_health("c1", "conv-a1", m)
        alert_types = [a.alert_type for a in report.alerts]
        assert HealthAlertType.TOKEN_BUDGET_LOW in alert_types

    @pytest.mark.asyncio
    async def test_compression_ratio_high_alert(self):
        meter = ContextHealthMeter()
        m = HealthMetrics(
            token_usage_ratio=0.1,
            compression_ratio=0.1,
            relevance_score=0.9,
            freshness_score=0.9,
            signal_preservation=0.9,
            context_coherence=0.9,
        )
        report = await meter.check_health("c1", "conv-a2", m)
        alert_types = [a.alert_type for a in report.alerts]
        assert HealthAlertType.COMPRESSION_RATIO_HIGH in alert_types

    @pytest.mark.asyncio
    async def test_signal_degradation_alert(self):
        meter = ContextHealthMeter()
        m = HealthMetrics(
            token_usage_ratio=0.1,
            compression_ratio=0.9,
            relevance_score=0.9,
            freshness_score=0.9,
            signal_preservation=0.1,
            context_coherence=0.9,
        )
        report = await meter.check_health("c1", "conv-a3", m)
        alert_types = [a.alert_type for a in report.alerts]
        assert HealthAlertType.SIGNAL_DEGRADATION in alert_types

    @pytest.mark.asyncio
    async def test_context_drift_alert(self):
        meter = ContextHealthMeter()
        m = HealthMetrics(
            token_usage_ratio=0.1,
            compression_ratio=0.9,
            relevance_score=0.1,
            freshness_score=0.9,
            signal_preservation=0.9,
            context_coherence=0.1,
        )
        report = await meter.check_health("c1", "conv-a4", m)
        alert_types = [a.alert_type for a in report.alerts]
        assert HealthAlertType.CONTEXT_DRIFT in alert_types

    @pytest.mark.asyncio
    async def test_freshness_expired_alert(self):
        meter = ContextHealthMeter()
        m = HealthMetrics(
            token_usage_ratio=0.1,
            compression_ratio=0.9,
            relevance_score=0.9,
            freshness_score=0.1,
            signal_preservation=0.9,
            context_coherence=0.9,
        )
        report = await meter.check_health("c1", "conv-a5", m)
        alert_types = [a.alert_type for a in report.alerts]
        assert HealthAlertType.FRESHNESS_EXPIRED in alert_types

    @pytest.mark.asyncio
    async def test_cooldown_prevents_duplicate_alerts(self):
        meter = ContextHealthMeter(
            HealthConfig(alert_cooldown_seconds=9999),
        )
        m = HealthMetrics(
            token_usage_ratio=0.95,
            compression_ratio=0.9,
            relevance_score=0.9,
            freshness_score=0.9,
            signal_preservation=0.9,
            context_coherence=0.9,
        )
        await meter.check_health("c1", "conv-a6", m)
        report2 = await meter.check_health("c1", "conv-a6", m)
        # Second check should be within cooldown — no duplicate alert
        token_alerts_2 = [
            a for a in report2.alerts
            if a.alert_type == HealthAlertType.TOKEN_BUDGET_LOW
        ]
        assert len(token_alerts_2) == 0


# ═══════════════════════════════════════════════════════════════════════
# 11. History (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestHistory:
    @pytest.mark.asyncio
    async def test_get_history(self):
        meter = ContextHealthMeter()
        await meter.check_health("c1", "conv-h1", _make_healthy_metrics())
        await meter.check_health("c1", "conv-h1", _make_degrading_metrics())
        history = meter.get_history("c1", "conv-h1")
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_get_latest(self):
        meter = ContextHealthMeter()
        await meter.check_health("c1", "conv-h2", _make_healthy_metrics())
        await meter.check_health("c1", "conv-h2", _make_critical_metrics())
        latest = meter.get_latest_report("c1", "conv-h2")
        assert latest is not None
        assert latest.status in (
            HealthStatus.CRITICAL, HealthStatus.EXHAUSTED,
        )

    @pytest.mark.asyncio
    async def test_empty_history(self):
        meter = ContextHealthMeter()
        history = meter.get_history("c1", "nonexistent")
        assert history == []

    @pytest.mark.asyncio
    async def test_multiple_entries_ordered(self):
        meter = ContextHealthMeter()
        for i in range(5):
            await meter.check_health(
                "c1", "conv-h3", _make_healthy_metrics(), turn_number=i,
            )
        history = meter.get_history("c1", "conv-h3")
        assert len(history) == 5
        turn_numbers = [r.turn_number for r in history]
        assert turn_numbers == [0, 1, 2, 3, 4]


# ═══════════════════════════════════════════════════════════════════════
# 12. Reset (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestReset:
    @pytest.mark.asyncio
    async def test_reset_clears_history(self):
        meter = ContextHealthMeter()
        await meter.check_health("c1", "conv-r1", _make_healthy_metrics())
        meter.reset("c1", "conv-r1")
        history = meter.get_history("c1", "conv-r1")
        assert history == []

    @pytest.mark.asyncio
    async def test_get_latest_after_reset_none(self):
        meter = ContextHealthMeter()
        await meter.check_health("c1", "conv-r2", _make_healthy_metrics())
        meter.reset("c1", "conv-r2")
        latest = meter.get_latest_report("c1", "conv-r2")
        assert latest is None

    @pytest.mark.asyncio
    async def test_reset_nonexistent_conversation(self):
        meter = ContextHealthMeter()
        # Should not raise
        meter.reset("c1", "nonexistent-conv")
        history = meter.get_history("c1", "nonexistent-conv")
        assert history == []


# ═══════════════════════════════════════════════════════════════════════
# 13. ContextHealthError (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestContextHealthError:
    def test_default_message(self):
        err = ContextHealthError()
        assert err.message == "Context health check failed"
        assert err.company_id == ""

    def test_inheritance_from_exception(self):
        err = ContextHealthError("test error")
        assert isinstance(err, Exception)

    def test_custom_company_id(self):
        err = ContextHealthError(
            message="Health check timeout",
            company_id="corp-42",
        )
        assert err.message == "Health check timeout"
        assert err.company_id == "corp-42"
        assert str(err) == "Health check timeout"


# ═══════════════════════════════════════════════════════════════════════
# 14. _HEALTH_WEIGHTS Constants (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestHealthWeights:
    def test_six_metrics(self):
        assert len(_HEALTH_WEIGHTS) == 6

    def test_all_positive_weights(self):
        for w in _HEALTH_WEIGHTS.values():
            assert w > 0

    def test_relevance_has_highest_weight(self):
        max_weight = max(_HEALTH_WEIGHTS.values())
        assert _HEALTH_WEIGHTS["relevance_score"] == max_weight


# ═══════════════════════════════════════════════════════════════════════
# 15. Variant Health Configs (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestVariantHealthConfigs:
    def test_three_variants(self):
        assert "mini_parwa" in _VARIANT_HEALTH_CONFIGS
        assert "parwa" in _VARIANT_HEALTH_CONFIGS
        assert "parwa_high" in _VARIANT_HEALTH_CONFIGS

    def test_get_variant_config_static(self):
        cfg = ContextHealthMeter.get_variant_config("parwa_high")
        assert isinstance(cfg, dict)
        assert "token_budget_threshold" in cfg

    def test_get_variant_config_defaults_for_unknown(self):
        cfg = ContextHealthMeter.get_variant_config("unknown_variant")
        assert isinstance(cfg, dict)
        # Falls back to parwa config
        parwa_cfg = ContextHealthMeter.get_variant_config("parwa")
        assert cfg == parwa_cfg


# ═══════════════════════════════════════════════════════════════════════
# 16. Recommendations (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestRecommendations:
    @pytest.mark.asyncio
    async def test_healthy_no_action(self):
        meter = ContextHealthMeter()
        report = await meter.check_health(
            "c1", "conv-rec1", _make_healthy_metrics(),
        )
        assert len(report.recommendations) >= 1
        assert any("no action needed" in r.lower() for r in report.recommendations)

    @pytest.mark.asyncio
    async def test_critical_has_recommendations(self):
        meter = ContextHealthMeter()
        report = await meter.check_health(
            "c1", "conv-rec2", _make_critical_metrics(),
        )
        assert len(report.recommendations) >= 1

    @pytest.mark.asyncio
    async def test_exhausted_recommends_reset(self):
        meter = ContextHealthMeter()
        m = HealthMetrics(
            token_usage_ratio=1.0,
            compression_ratio=0.0,
            relevance_score=0.0,
            freshness_score=0.0,
            signal_preservation=0.0,
            context_coherence=0.0,
        )
        report = await meter.check_health("c1", "conv-rec3", m)
        assert report.status == HealthStatus.EXHAUSTED
        has_reset_rec = any(
            "new conversation" in r.lower() or "reset" in r.lower()
            for r in report.recommendations
        )
        assert has_reset_rec


# ═══════════════════════════════════════════════════════════════════════
# 17. Reset All (2 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestResetAll:
    @pytest.mark.asyncio
    async def test_reset_all_clears_everything(self):
        meter = ContextHealthMeter()
        await meter.check_health("c1", "conv1", _make_healthy_metrics())
        await meter.check_health("c2", "conv2", _make_critical_metrics())
        meter.reset_all()
        assert meter.get_history("c1", "conv1") == []
        assert meter.get_history("c2", "conv2") == []

    @pytest.mark.asyncio
    async def test_reset_all_non_destructive_on_empty(self):
        meter = ContextHealthMeter()
        meter.reset_all()  # Should not raise
        assert meter.get_history("c1", "conv-x") == []


# ═══════════════════════════════════════════════════════════════════════
# 18. Timestamp and Metadata (2 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestTimestampAndMetadata:
    @pytest.mark.asyncio
    async def test_report_has_timestamp(self):
        meter = ContextHealthMeter()
        report = await meter.check_health(
            "c1", "conv-ts1", _make_healthy_metrics(),
        )
        assert report.timestamp != ""
        assert "T" in report.timestamp or "+" in report.timestamp

    @pytest.mark.asyncio
    async def test_alert_has_timestamp_when_generated(self):
        meter = ContextHealthMeter()
        m = HealthMetrics(
            token_usage_ratio=0.95,
            compression_ratio=0.9,
            relevance_score=0.9,
            freshness_score=0.9,
            signal_preservation=0.9,
            context_coherence=0.9,
        )
        report = await meter.check_health("c1", "conv-ts2", m)
        assert len(report.alerts) >= 1
        for alert in report.alerts:
            assert alert.timestamp != ""
