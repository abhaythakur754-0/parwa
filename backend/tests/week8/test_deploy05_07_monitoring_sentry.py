"""
Week 8 Tests: DEPLOY-05/07 — Monitoring Stack and Sentry Integration

Validates:
- Monitoring infrastructure files exist and are valid
- AlertManager configuration (email, Slack, webhook receivers)
- Sentry integration (PII scrubbing, tenant context, BC-008)
- Grafana dashboard provisioning
"""

import os
import re
import yaml
import pytest


MONITORING_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "monitoring"
)
ALERTMANAGER_PATH = os.path.join(MONITORING_DIR, "alertmanager", "alertmanager.yml")
RULES_PATH = os.path.join(MONITORING_DIR, "alerting", "rules.yml")
SENTRY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "backend", "app", "core", "sentry.py"
)


class TestMonitoringInfraFiles:
    """Verify monitoring infrastructure files exist."""

    def test_prometheus_yml_exists(self):
        assert os.path.exists(os.path.join(MONITORING_DIR, "prometheus.yml"))

    def test_alertmanager_yml_exists(self):
        assert os.path.exists(ALERTMANAGER_PATH)

    def test_alert_rules_yml_exists(self):
        assert os.path.exists(RULES_PATH)

    def test_grafana_datasource_exists(self):
        assert os.path.exists(os.path.join(
            MONITORING_DIR, "grafana", "provisioning",
            "datasources", "datasource.yml"
        ))

    def test_grafana_dashboards_yml_exists(self):
        assert os.path.exists(os.path.join(
            MONITORING_DIR, "grafana", "provisioning",
            "dashboards", "dashboards.yml"
        ))


class TestAlertManagerConfig:
    """Validate AlertManager configuration."""

    def test_valid_yaml(self):
        with open(ALERTMANAGER_PATH, "r") as f:
            config = yaml.safe_load(f)
        assert isinstance(config, dict)

    def test_has_smtp_config(self):
        """Must have SMTP configuration for email alerts."""
        with open(ALERTMANAGER_PATH, "r") as f:
            config = yaml.safe_load(f)
        global_conf = config.get("global", {})
        assert "smtp_smarthost" in global_conf, "Missing SMTP host"
        assert "smtp_from" in global_conf, "Missing SMTP from"

    def test_has_default_receiver(self):
        """Must have a default receiver."""
        with open(ALERTMANAGER_PATH, "r") as f:
            config = yaml.safe_load(f)
        receivers = config.get("receivers", [])
        names = [r.get("name", "") for r in receivers]
        assert "default-receiver" in names

    def test_has_critical_receiver(self):
        """Must have a critical receiver."""
        with open(ALERTMANAGER_PATH, "r") as f:
            config = yaml.safe_load(f)
        receivers = config.get("receivers", [])
        names = [r.get("name", "") for r in receivers]
        assert "critical-receiver" in names

    def test_critical_receiver_has_slack(self):
        """Critical receiver must have Slack integration."""
        with open(ALERTMANAGER_PATH, "r") as f:
            config = yaml.safe_load(f)
        for receiver in config.get("receivers", []):
            if receiver.get("name") == "critical-receiver":
                slack = receiver.get("slack_configs", [])
                assert len(slack) > 0, "Critical receiver missing Slack config"
                break

    def test_critical_receiver_has_email(self):
        """Critical receiver must have email integration."""
        with open(ALERTMANAGER_PATH, "r") as f:
            config = yaml.safe_load(f)
        for receiver in config.get("receivers", []):
            if receiver.get("name") == "critical-receiver":
                email = receiver.get("email_configs", [])
                assert len(email) > 0, "Critical receiver missing email config"
                break

    def test_has_inhibit_rules(self):
        """Must have inhibition rules (critical suppresses warning)."""
        with open(ALERTMANAGER_PATH, "r") as f:
            config = yaml.safe_load(f)
        inhibitions = config.get("inhibit_rules", [])
        assert len(inhibitions) > 0, "Missing inhibition rules"

    def test_critical_suppresses_warning(self):
        """Critical alerts should suppress warning alerts."""
        with open(ALERTMANAGER_PATH, "r") as f:
            config = yaml.safe_load(f)
        inhibitions = config.get("inhibit_rules", [])
        found = False
        for rule in inhibitions:
            src = rule.get("source_match", {})
            tgt = rule.get("target_match", {})
            if src.get("severity") == "critical" and tgt.get("severity") == "warning":
                found = True
                break
        assert found, "Missing critical-suppresses-warning inhibition"


class TestAlertRules:
    """Validate Prometheus alert rules."""

    def test_valid_yaml(self):
        with open(RULES_PATH, "r") as f:
            rules = yaml.safe_load(f)
        assert isinstance(rules, dict)

    def test_has_health_alerts(self):
        """Must have parwa_health alert group."""
        with open(RULES_PATH, "r") as f:
            rules = yaml.safe_load(f)
        groups = [g.get("name", "") for g in rules.get("groups", [])]
        assert "parwa_health" in groups

    def test_has_api_alerts(self):
        """Must have parwa_api alert group."""
        with open(RULES_PATH, "r") as f:
            rules = yaml.safe_load(f)
        groups = [g.get("name", "") for g in rules.get("groups", [])]
        assert "parwa_api" in groups

    def test_has_celery_alerts(self):
        """Must have parwa_celery alert group."""
        with open(RULES_PATH, "r") as f:
            rules = yaml.safe_load(f)
        groups = [g.get("name", "") for g in rules.get("groups", [])]
        assert "parwa_celery" in groups

    def test_api_error_rate_alert(self):
        """Must have HighAPIErrorRate alert."""
        with open(RULES_PATH, "r") as f:
            rules = yaml.safe_load(f)
        all_alerts = []
        for g in rules.get("groups", []):
            all_alerts.extend(g.get("rules", []))
        names = [a.get("alert", "") for a in all_alerts]
        assert "HighAPIErrorRate" in names

    def test_api_latency_alert(self):
        """Must have HighAPILatency alert."""
        with open(RULES_PATH, "r") as f:
            rules = yaml.safe_load(f)
        all_alerts = []
        for g in rules.get("groups", []):
            all_alerts.extend(g.get("rules", []))
        names = [a.get("alert", "") for a in all_alerts]
        assert "HighAPILatency" in names


class TestSentryIntegration:
    """Validate Sentry error tracking configuration."""

    def test_sentry_module_exists(self):
        """sentry.py must exist."""
        assert os.path.exists(SENTRY_PATH)

    def test_sentry_has_init_function(self):
        """Must have init_sentry function."""
        with open(SENTRY_PATH, "r") as f:
            content = f.read()
        assert "def init_sentry" in content, "Missing init_sentry function"

    def test_sentry_has_pii_scrubbing(self):
        """Must have PII scrubbing (email/phone)."""
        with open(SENTRY_PATH, "r") as f:
            content = f.read()
        assert "scrub_pii" in content, "Missing PII scrubbing"
        assert "email" in content.lower() or "phone" in content.lower()

    def test_sentry_has_tenant_context(self):
        """Must add tenant context (company_id) to events."""
        with open(SENTRY_PATH, "r") as f:
            content = f.read()
        assert "company_id" in content, "Missing tenant context"
        assert "add_tenant_context" in content or "tenant" in content.lower()

    def test_sentry_bc008_compliance(self):
        """Must have BC-008 compliance (never crash)."""
        with open(SENTRY_PATH, "r") as f:
            content = f.read()
        assert "BC-008" in content or "never crash" in content.lower() or \
               "except" in content, "Missing BC-008 compliance"

    def test_sentry_has_capture_exception(self):
        """Must have capture_exception wrapper."""
        with open(SENTRY_PATH, "r") as f:
            content = f.read()
        assert "capture_exception" in content

    def test_sentry_has_health_status(self):
        """Must have health status endpoint function."""
        with open(SENTRY_PATH, "r") as f:
            content = f.read()
        assert "get_sentry_status" in content or "health" in content.lower()

    def test_sentry_has_sample_rates(self):
        """Must have environment-aware sample rates."""
        with open(SENTRY_PATH, "r") as f:
            content = f.read()
        assert "sample_rate" in content or "traces_sample_rate" in content


class TestGrafanaDashboards:
    """Validate Grafana dashboard provisioning."""

    def test_dashboard_count(self):
        """Must have at least 4 dashboard JSON files."""
        dashboards_dir = os.path.join(MONITORING_DIR, "grafana_dashboards")
        json_files = [f for f in os.listdir(dashboards_dir) if f.endswith(".json")]
        assert len(json_files) >= 4, f"Expected >= 4 dashboards, got {len(json_files)}"

    def test_api_performance_dashboard(self):
        """Must have API performance dashboard."""
        dashboards_dir = os.path.join(MONITORING_DIR, "grafana_dashboards")
        files = os.listdir(dashboards_dir)
        assert any("api" in f.lower() and "performance" in f.lower() for f in files), \
            "Missing API performance dashboard"

    def test_celery_dashboard(self):
        """Must have Celery queues dashboard."""
        dashboards_dir = os.path.join(MONITORING_DIR, "grafana_dashboards")
        files = os.listdir(dashboards_dir)
        assert any("celery" in f.lower() for f in files), "Missing Celery dashboard"

    def test_system_dashboard(self):
        """Must have system overview dashboard."""
        dashboards_dir = os.path.join(MONITORING_DIR, "grafana_dashboards")
        files = os.listdir(dashboards_dir)
        assert any("system" in f.lower() for f in files), "Missing system dashboard"

    def test_all_dashboards_valid_json(self):
        """All dashboard JSON files must be valid JSON."""
        dashboards_dir = os.path.join(MONITORING_DIR, "grafana_dashboards")
        for fname in os.listdir(dashboards_dir):
            if fname.endswith(".json"):
                fpath = os.path.join(dashboards_dir, fname)
                with open(fpath, "r") as f:
                    data = __import__("json").load(f)
                assert isinstance(data, dict), f"{fname} is not valid JSON"
