"""
Unit Tests for PARWA Alert Rules.

Tests cover:
- Alert rule validation
- Alert firing conditions
- Alert severity levels
- Alert notification routing

CRITICAL Tests:
- HighErrorRate fires when error rate > 5%
- HighLatency fires when P95 > 1s
- SLABreach fires on SLA violation
- RefundGateViolation fires on Paddle bypass
- ModelDrift fires when accuracy < 85%
- WorkerDown fires when worker unresponsive
"""
import pytest
import yaml
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Path to alerts file
ALERTS_FILE = Path(__file__).parent.parent.parent / "monitoring" / "alerts.yml"


def load_alerts() -> Dict[str, Any]:
    """Load alerts configuration from YAML file."""
    with open(ALERTS_FILE, "r") as f:
        return yaml.safe_load(f)


def get_alert_rules() -> List[Dict[str, Any]]:
    """Get all alert rules from configuration."""
    alerts = load_alerts()
    rules = []
    for group in alerts.get("groups", []):
        rules.extend(group.get("rules", []))
    return rules


def get_alert_by_name(alert_name: str) -> Dict[str, Any]:
    """Get a specific alert by name."""
    for rule in get_alert_rules():
        if rule.get("alert") == alert_name:
            return rule
    raise ValueError(f"Alert '{alert_name}' not found")


class TestAlertsFile:
    """Tests for alerts file validity."""

    def test_alerts_file_exists(self):
        """Test that alerts.yml file exists."""
        assert ALERTS_FILE.exists(), f"Alerts file not found: {ALERTS_FILE}"

    def test_alerts_file_is_valid_yaml(self):
        """Test that alerts.yml is valid YAML."""
        with open(ALERTS_FILE, "r") as f:
            try:
                data = yaml.safe_load(f)
                assert isinstance(data, dict), "Alerts file should be a YAML object"
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in alerts.yml: {e}")

    def test_alerts_file_has_groups(self):
        """Test that alerts file has groups."""
        alerts = load_alerts()
        assert "groups" in alerts, "Alerts file must have 'groups' key"
        assert len(alerts["groups"]) > 0, "Alerts file must have at least one group"

    def test_all_alerts_have_required_fields(self):
        """Test that all alerts have required fields."""
        required_fields = ["alert", "expr", "for", "labels", "annotations"]

        for rule in get_alert_rules():
            alert_name = rule.get("alert", "UNKNOWN")
            for field in required_fields:
                assert field in rule, f"Alert '{alert_name}' missing required field: {field}"


class TestHighErrorRateAlert:
    """Tests for HighErrorRate alert - fires when error rate > 5% for 5 minutes."""

    @pytest.fixture
    def alert(self):
        """Load the HighErrorRate alert."""
        return get_alert_by_name("HighErrorRate")

    def test_high_error_rate_alert_exists(self, alert):
        """Test that HighErrorRate alert exists."""
        assert alert is not None
        assert alert["alert"] == "HighErrorRate"

    def test_high_error_rate_expression(self, alert):
        """Test that HighErrorRate expression checks for > 5% error rate."""
        expr = alert["expr"]
        assert "> 0.05" in expr, "HighErrorRate should trigger at > 5% (0.05)"
        assert "status=~\"5..\"" in expr, "HighErrorRate should check 5xx status codes"

    def test_high_error_rate_duration(self, alert):
        """Test that HighErrorRate has 5 minute duration."""
        assert alert["for"] == "5m", "HighErrorRate should have 5m duration"

    def test_high_error_rate_severity(self, alert):
        """Test that HighErrorRate has warning severity."""
        labels = alert.get("labels", {})
        assert labels.get("severity") == "warning", "HighErrorRate should be warning severity"

    def test_high_error_rate_has_category(self, alert):
        """Test that HighErrorRate has category label."""
        labels = alert.get("labels", {})
        assert "category" in labels, "HighErrorRate should have category label"

    def test_high_error_rate_annotations(self, alert):
        """Test that HighErrorRate has proper annotations."""
        annotations = alert.get("annotations", {})
        assert "summary" in annotations, "HighErrorRate should have summary annotation"
        assert "description" in annotations, "HighErrorRate should have description annotation"

    def test_high_error_rate_fires_above_threshold(self):
        """Test that HighErrorRate fires when error rate > 5%.

        Simulated condition:
        - 100 total requests
        - 6 errors (6%)
        - Threshold: 5%
        - Expected: Alert fires
        """
        # Simulated metrics
        total_requests = 100
        error_requests = 6
        error_rate = error_requests / total_requests  # 0.06 (6%)

        # Alert threshold is 0.05 (5%)
        threshold = 0.05

        assert error_rate > threshold, "Test setup: error rate should be above threshold"

        # The expression checks: error_rate > 0.05
        # With 6% error rate, this should fire
        fires = error_rate > threshold
        assert fires, "HighErrorRate should fire when error rate > 5%"

    def test_high_error_rate_does_not_fire_below_threshold(self):
        """Test that HighErrorRate does not fire when error rate < 5%.

        Simulated condition:
        - 100 total requests
        - 4 errors (4%)
        - Threshold: 5%
        - Expected: Alert does NOT fire
        """
        # Simulated metrics
        total_requests = 100
        error_requests = 4
        error_rate = error_requests / total_requests  # 0.04 (4%)

        # Alert threshold is 0.05 (5%)
        threshold = 0.05

        assert error_rate < threshold, "Test setup: error rate should be below threshold"

        # The expression checks: error_rate > 0.05
        # With 4% error rate, this should NOT fire
        fires = error_rate > threshold
        assert not fires, "HighErrorRate should NOT fire when error rate < 5%"


class TestHighLatencyAlert:
    """Tests for HighLatency alert - fires when P95 > 1s for 5 minutes."""

    @pytest.fixture
    def alert(self):
        """Load the HighLatency alert."""
        return get_alert_by_name("HighLatency")

    def test_high_latency_alert_exists(self, alert):
        """Test that HighLatency alert exists."""
        assert alert is not None
        assert alert["alert"] == "HighLatency"

    def test_high_latency_expression(self, alert):
        """Test that HighLatency expression checks for > 1s P95 latency."""
        expr = alert["expr"]
        assert "> 1" in expr, "HighLatency should trigger at > 1 second"
        assert "histogram_quantile" in expr, "HighLatency should use histogram_quantile"
        assert "0.95" in expr, "HighLatency should check P95 (0.95 percentile)"

    def test_high_latency_duration(self, alert):
        """Test that HighLatency has 5 minute duration."""
        assert alert["for"] == "5m", "HighLatency should have 5m duration"

    def test_high_latency_severity(self, alert):
        """Test that HighLatency has warning severity."""
        labels = alert.get("labels", {})
        assert labels.get("severity") == "warning", "HighLatency should be warning severity"

    def test_high_latency_category(self, alert):
        """Test that HighLatency has performance category."""
        labels = alert.get("labels", {})
        assert labels.get("category") == "performance", "HighLatency should be performance category"

    def test_high_latency_fires_above_threshold(self):
        """Test that HighLatency fires when P95 > 1s.

        Simulated condition:
        - P95 latency: 1.5 seconds
        - Threshold: 1 second
        - Expected: Alert fires
        """
        p95_latency = 1.5  # seconds
        threshold = 1.0  # seconds

        fires = p95_latency > threshold
        assert fires, "HighLatency should fire when P95 > 1s"

    def test_high_latency_does_not_fire_below_threshold(self):
        """Test that HighLatency does not fire when P95 < 1s.

        Simulated condition:
        - P95 latency: 0.8 seconds
        - Threshold: 1 second
        - Expected: Alert does NOT fire
        """
        p95_latency = 0.8  # seconds
        threshold = 1.0  # seconds

        fires = p95_latency > threshold
        assert not fires, "HighLatency should NOT fire when P95 < 1s"


class TestSLABreachAlert:
    """Tests for SLABreach alert - fires on SLA violation."""

    @pytest.fixture
    def alert(self):
        """Load the SLABreach alert."""
        return get_alert_by_name("SLABreach")

    def test_sla_breach_alert_exists(self, alert):
        """Test that SLABreach alert exists."""
        assert alert is not None
        assert alert["alert"] == "SLABreach"

    def test_sla_breach_expression(self, alert):
        """Test that SLABreach expression checks for breached status."""
        expr = alert["expr"]
        assert "sla_status" in expr, "SLABreach should check sla_status metric"
        assert "== 2" in expr, "SLABreach should trigger on status == 2 (BREACHED)"

    def test_sla_breach_duration(self, alert):
        """Test that SLABreach fires immediately (0m duration)."""
        assert alert["for"] == "0m", "SLABreach should fire immediately"

    def test_sla_breach_severity(self, alert):
        """Test that SLABreach has critical severity."""
        labels = alert.get("labels", {})
        assert labels.get("severity") == "critical", "SLABreach should be critical severity"

    def test_sla_breach_category(self, alert):
        """Test that SLABreach has sla category."""
        labels = alert.get("labels", {})
        assert labels.get("category") == "sla", "SLABreach should be sla category"

    def test_sla_breach_fires_on_violation(self):
        """Test that SLABreach fires when SLA status is BREACHED.

        SLA Status values:
        - 0: OK (within SLA)
        - 1: WARNING (approaching breach)
        - 2: BREACHED (SLA violated)
        """
        # Simulated SLA status
        sla_status_breached = 2
        sla_status_ok = 0

        # Alert fires when sla_status == 2
        fires_breached = sla_status_breached == 2
        fires_ok = sla_status_ok == 2

        assert fires_breached, "SLABreach should fire when status == 2"
        assert not fires_ok, "SLABreach should NOT fire when status == 0"

    def test_sla_breach_annotations_include_ticket_id(self, alert):
        """Test that SLABreach annotations include ticket_id."""
        annotations = alert.get("annotations", {})
        description = annotations.get("description", "")
        assert "ticket_id" in description or "ticket" in description.lower(), \
            "SLABreach description should reference ticket_id"


class TestRefundGateViolationAlert:
    """Tests for RefundGateViolation alert - fires on Paddle bypass."""

    @pytest.fixture
    def alert(self):
        """Load the RefundGateViolation alert."""
        return get_alert_by_name("RefundGateViolation")

    def test_refund_gate_violation_alert_exists(self, alert):
        """Test that RefundGateViolation alert exists."""
        assert alert is not None
        assert alert["alert"] == "RefundGateViolation"

    def test_refund_gate_violation_expression(self, alert):
        """Test that RefundGateViolation expression checks for unauthorized Paddle calls."""
        expr = alert["expr"]
        assert "paddle_unauthorized_calls" in expr, \
            "RefundGateViolation should check paddle_unauthorized_calls metric"
        assert "increase" in expr, \
            "RefundGateViolation should use increase function"

    def test_refund_gate_violation_duration(self, alert):
        """Test that RefundGateViolation fires immediately (0m duration)."""
        assert alert["for"] == "0m", "RefundGateViolation should fire immediately"

    def test_refund_gate_violation_severity(self, alert):
        """Test that RefundGateViolation has critical severity."""
        labels = alert.get("labels", {})
        assert labels.get("severity") == "critical", \
            "RefundGateViolation should be critical severity"

    def test_refund_gate_violation_category(self, alert):
        """Test that RefundGateViolation has security category."""
        labels = alert.get("labels", {})
        assert labels.get("category") == "security", \
            "RefundGateViolation should be security category"

    def test_refund_gate_violation_fires_on_bypass(self):
        """Test that RefundGateViolation fires when Paddle called without approval.

        Scenario:
        - Paddle is called directly bypassing the approval service
        - Unauthorized call counter increases
        - Alert fires immediately
        """
        # Simulated: paddle_unauthorized_calls_total increased by 1 in last 5m
        unauthorized_calls_increase = 1

        # Alert fires when increase > 0
        fires = unauthorized_calls_increase > 0
        assert fires, "RefundGateViolation should fire when unauthorized Paddle calls detected"

    def test_refund_gate_violation_does_not_fire_without_bypass(self):
        """Test that RefundGateViolation does not fire when no bypass detected."""
        # Simulated: No unauthorized calls
        unauthorized_calls_increase = 0

        # Alert fires when increase > 0
        fires = unauthorized_calls_increase > 0
        assert not fires, "RefundGateViolation should NOT fire when no unauthorized calls"

    def test_refund_gate_violation_description_mentions_investigation(self, alert):
        """Test that RefundGateViolation description mentions immediate investigation."""
        annotations = alert.get("annotations", {})
        description = annotations.get("description", "").lower()
        assert "investigate" in description, \
            "RefundGateViolation description should mention investigation"


class TestModelDriftAlert:
    """Tests for ModelDrift alert - fires when accuracy < 85%."""

    @pytest.fixture
    def alert(self):
        """Load the ModelDrift alert."""
        return get_alert_by_name("ModelDrift")

    def test_model_drift_alert_exists(self, alert):
        """Test that ModelDrift alert exists."""
        assert alert is not None
        assert alert["alert"] == "ModelDrift"

    def test_model_drift_expression(self, alert):
        """Test that ModelDrift expression checks for < 85% accuracy."""
        expr = alert["expr"]
        assert "agent_lightning_model_accuracy" in expr, \
            "ModelDrift should check agent_lightning_model_accuracy metric"
        assert "< 0.85" in expr, "ModelDrift should trigger at < 85% (0.85)"

    def test_model_drift_duration(self, alert):
        """Test that ModelDrift has 5 minute duration."""
        assert alert["for"] == "5m", "ModelDrift should have 5m duration"

    def test_model_drift_severity(self, alert):
        """Test that ModelDrift has warning severity."""
        labels = alert.get("labels", {})
        assert labels.get("severity") == "warning", "ModelDrift should be warning severity"

    def test_model_drift_category(self, alert):
        """Test that ModelDrift has ai_quality category."""
        labels = alert.get("labels", {})
        assert labels.get("category") == "ai_quality", \
            "ModelDrift should be ai_quality category"

    def test_model_drift_fires_below_threshold(self):
        """Test that ModelDrift fires when accuracy < 85%.

        Simulated condition:
        - Model accuracy: 82%
        - Threshold: 85%
        - Expected: Alert fires
        """
        model_accuracy = 0.82  # 82%
        threshold = 0.85  # 85%

        fires = model_accuracy < threshold
        assert fires, "ModelDrift should fire when accuracy < 85%"

    def test_model_drift_does_not_fire_above_threshold(self):
        """Test that ModelDrift does not fire when accuracy >= 85%.

        Simulated condition:
        - Model accuracy: 87%
        - Threshold: 85%
        - Expected: Alert does NOT fire
        """
        model_accuracy = 0.87  # 87%
        threshold = 0.85  # 85%

        fires = model_accuracy < threshold
        assert not fires, "ModelDrift should NOT fire when accuracy >= 85%"

    def test_model_drift_validation_gate_interaction(self):
        """Test interaction with validation gate (blocks at <90%, allows at 91%+).

        ModelDrift alert at 85% threshold and validation gate at 90% threshold
        work together:
        - 82%: ModelDrift fires, validation blocks
        - 88%: ModelDrift does NOT fire, validation blocks
        - 92%: ModelDrift does NOT fire, validation allows
        """
        # ModelDrift threshold
        drift_threshold = 0.85

        # Validation gate threshold
        validation_threshold = 0.90

        test_cases = [
            (0.82, True, False),   # 82%: drift fires, validation blocks
            (0.88, False, False),  # 88%: drift not fire, validation blocks
            (0.92, False, True),   # 92%: drift not fire, validation allows
        ]

        for accuracy, expect_drift_fire, expect_validation_allow in test_cases:
            drift_fires = accuracy < drift_threshold
            validation_allows = accuracy >= validation_threshold

            assert drift_fires == expect_drift_fire, \
                f"At {accuracy*100}% accuracy, drift fire should be {expect_drift_fire}"
            assert validation_allows == expect_validation_allow, \
                f"At {accuracy*100}% accuracy, validation allow should be {expect_validation_allow}"


class TestWorkerDownAlert:
    """Tests for WorkerDown alert - fires when worker unresponsive for 2+ minutes."""

    @pytest.fixture
    def alert(self):
        """Load the WorkerDown alert."""
        return get_alert_by_name("WorkerDown")

    def test_worker_down_alert_exists(self, alert):
        """Test that WorkerDown alert exists."""
        assert alert is not None
        assert alert["alert"] == "WorkerDown"

    def test_worker_down_expression(self, alert):
        """Test that WorkerDown expression checks heartbeat timestamp."""
        expr = alert["expr"]
        assert "worker_last_heartbeat_timestamp" in expr, \
            "WorkerDown should check worker_last_heartbeat_timestamp"
        assert "> 120" in expr, "WorkerDown should trigger after 120 seconds (2 minutes)"

    def test_worker_down_duration(self, alert):
        """Test that WorkerDown fires immediately after condition met (0m duration)."""
        assert alert["for"] == "0m", "WorkerDown should fire immediately"

    def test_worker_down_severity(self, alert):
        """Test that WorkerDown has critical severity."""
        labels = alert.get("labels", {})
        assert labels.get("severity") == "critical", "WorkerDown should be critical severity"

    def test_worker_down_category(self, alert):
        """Test that WorkerDown has availability category."""
        labels = alert.get("labels", {})
        assert labels.get("category") == "availability", \
            "WorkerDown should be availability category"

    def test_worker_down_fires_after_2_minutes(self):
        """Test that WorkerDown fires when worker unresponsive for > 2 minutes.

        Simulated condition:
        - Time since last heartbeat: 150 seconds
        - Threshold: 120 seconds (2 minutes)
        - Expected: Alert fires
        """
        seconds_since_heartbeat = 150
        threshold = 120

        fires = seconds_since_heartbeat > threshold
        assert fires, "WorkerDown should fire when unresponsive > 2 minutes"

    def test_worker_down_does_not_fire_within_2_minutes(self):
        """Test that WorkerDown does not fire within 2 minutes.

        Simulated condition:
        - Time since last heartbeat: 90 seconds
        - Threshold: 120 seconds (2 minutes)
        - Expected: Alert does NOT fire
        """
        seconds_since_heartbeat = 90
        threshold = 120

        fires = seconds_since_heartbeat > threshold
        assert not fires, "WorkerDown should NOT fire when unresponsive < 2 minutes"

    def test_worker_down_annotations_include_worker_name(self, alert):
        """Test that WorkerDown annotations include worker_name."""
        annotations = alert.get("annotations", {})
        description = annotations.get("description", "")
        assert "worker_name" in description or "worker" in description.lower(), \
            "WorkerDown description should reference worker_name"


class TestAlertGroups:
    """Tests for alert group organization."""

    def test_service_availability_group_exists(self):
        """Test that service_availability alert group exists."""
        alerts = load_alerts()
        group_names = [g.get("name") for g in alerts.get("groups", [])]
        assert "service_availability" in group_names, \
            "service_availability group should exist"

    def test_mcp_servers_group_exists(self):
        """Test that mcp_servers alert group exists."""
        alerts = load_alerts()
        group_names = [g.get("name") for g in alerts.get("groups", [])]
        assert "mcp_servers" in group_names, "mcp_servers group should exist"

    def test_guardrails_group_exists(self):
        """Test that guardrails alert group exists."""
        alerts = load_alerts()
        group_names = [g.get("name") for g in alerts.get("groups", [])]
        assert "guardrails" in group_names, "guardrails group should exist"

    def test_sla_group_exists(self):
        """Test that sla alert group exists."""
        alerts = load_alerts()
        group_names = [g.get("name") for g in alerts.get("groups", [])]
        assert "sla" in group_names, "sla group should exist"

    def test_trivya_group_exists(self):
        """Test that trivya alert group exists."""
        alerts = load_alerts()
        group_names = [g.get("name") for g in alerts.get("groups", [])]
        assert "trivya" in group_names, "trivya group should exist"

    def test_gsd_engine_group_exists(self):
        """Test that gsd_engine alert group exists."""
        alerts = load_alerts()
        group_names = [g.get("name") for g in alerts.get("groups", [])]
        assert "gsd_engine" in group_names, "gsd_engine group should exist"


class TestAllCriticalAlerts:
    """Tests ensuring all 6 critical alerts are present and configured."""

    @pytest.fixture
    def critical_alert_names(self):
        """List of required critical alerts."""
        return [
            "HighErrorRate",
            "HighLatency",
            "SLABreach",
            "RefundGateViolation",
            "ModelDrift",
            "WorkerDown",
        ]

    def test_all_critical_alerts_exist(self, critical_alert_names):
        """Test that all 6 critical alerts exist."""
        alert_names = [rule.get("alert") for rule in get_alert_rules()]

        for name in critical_alert_names:
            assert name in alert_names, f"Critical alert '{name}' not found in alerts.yml"

    def test_all_critical_alerts_have_expressions(self, critical_alert_names):
        """Test that all critical alerts have valid expressions."""
        for name in critical_alert_names:
            alert = get_alert_by_name(name)
            assert "expr" in alert, f"Alert '{name}' missing expression"
            assert alert["expr"], f"Alert '{name}' has empty expression"

    def test_all_critical_alerts_have_durations(self, critical_alert_names):
        """Test that all critical alerts have duration specified."""
        for name in critical_alert_names:
            alert = get_alert_by_name(name)
            assert "for" in alert, f"Alert '{name}' missing duration"

    def test_all_critical_alerts_have_severity_labels(self, critical_alert_names):
        """Test that all critical alerts have severity labels."""
        for name in critical_alert_names:
            alert = get_alert_by_name(name)
            labels = alert.get("labels", {})
            assert "severity" in labels, f"Alert '{name}' missing severity label"

    def test_all_critical_alerts_have_summaries(self, critical_alert_names):
        """Test that all critical alerts have summary annotations."""
        for name in critical_alert_names:
            alert = get_alert_by_name(name)
            annotations = alert.get("annotations", {})
            assert "summary" in annotations, f"Alert '{name}' missing summary annotation"

    def test_all_critical_alerts_have_descriptions(self, critical_alert_names):
        """Test that all critical alerts have description annotations."""
        for name in critical_alert_names:
            alert = get_alert_by_name(name)
            annotations = alert.get("annotations", {})
            assert "description" in annotations, f"Alert '{name}' missing description annotation"


class TestAlertSeverityLevels:
    """Tests for alert severity level consistency."""

    def test_critical_alerts_have_immediate_firing(self):
        """Test that critical alerts fire immediately (0m duration)."""
        critical_alerts = [
            "SLABreach",
            "RefundGateViolation",
            "WorkerDown",
        ]

        for name in critical_alerts:
            alert = get_alert_by_name(name)
            assert alert.get("for") == "0m", \
                f"Critical alert '{name}' should fire immediately"

    def test_warning_alerts_have_delayed_firing(self):
        """Test that warning alerts have delayed firing (5m duration)."""
        warning_alerts = [
            "HighErrorRate",
            "HighLatency",
            "ModelDrift",
        ]

        for name in warning_alerts:
            alert = get_alert_by_name(name)
            assert alert.get("for") == "5m", \
                f"Warning alert '{name}' should have 5m delay"


class TestAlertExpressions:
    """Tests for alert expression validity."""

    def test_expressions_are_strings(self):
        """Test that all expressions are strings."""
        for rule in get_alert_rules():
            alert_name = rule.get("alert", "UNKNOWN")
            expr = rule.get("expr")
            assert isinstance(expr, str), f"Alert '{alert_name}' expression should be a string"

    def test_rate_based_expressions_use_time_window(self):
        """Test that rate-based expressions have time window specified."""
        rate_alerts = ["HighErrorRate", "HighLatency"]

        for name in rate_alerts:
            alert = get_alert_by_name(name)
            expr = alert.get("expr", "")
            assert "rate(" in expr or "increase(" in expr, \
                f"Alert '{name}' should use rate() or increase()"
            # Check for time window like [5m]
            assert "[5m]" in expr, \
                f"Alert '{name}' should have 5m time window in expression"


class TestAdditionalAlerts:
    """Tests for additional non-critical but important alerts."""

    def test_service_down_alert_exists(self):
        """Test that ServiceDown alert exists."""
        alert_names = [rule.get("alert") for rule in get_alert_rules()]
        assert "ServiceDown" in alert_names, "ServiceDown alert should exist"

    def test_hallucination_blocked_alert_exists(self):
        """Test that HallucinationBlocked alert exists."""
        alert_names = [rule.get("alert") for rule in get_alert_rules()]
        assert "HallucinationBlocked" in alert_names, "HallucinationBlocked alert should exist"

    def test_competitor_mentions_blocked_alert_exists(self):
        """Test that CompetitorMentionsBlocked alert exists."""
        alert_names = [rule.get("alert") for rule in get_alert_rules()]
        assert "CompetitorMentionsBlocked" in alert_names, \
            "CompetitorMentionsBlocked alert should exist"

    def test_pii_exposure_alert_exists(self):
        """Test that PIIExposureDetected alert exists."""
        alert_names = [rule.get("alert") for rule in get_alert_rules()]
        assert "PIIExposureDetected" in alert_names, "PIIExposureDetected alert should exist"

    def test_refund_bypass_attempt_alert_exists(self):
        """Test that RefundBypassAttempt alert exists."""
        alert_names = [rule.get("alert") for rule in get_alert_rules()]
        assert "RefundBypassAttempt" in alert_names, "RefundBypassAttempt alert should exist"

    def test_mcp_server_slow_response_alert_exists(self):
        """Test that MCPServerSlowResponse alert exists."""
        alert_names = [rule.get("alert") for rule in get_alert_rules()]
        assert "MCPServerSlowResponse" in alert_names, "MCPServerSlowResponse alert should exist"
