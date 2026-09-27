"""
Week 8 Tests: DEPLOY-06 — AI Pipeline Metrics and Monitoring

Validates:
- AI Pipeline Grafana dashboard JSON structure
- AI Pipeline alert rules YAML
- Prometheus config includes AI pipeline scrape target
- Alert rules have correct severity levels and thresholds
"""

import os
import json
import yaml
import pytest


GRAFANA_DASHBOARD_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "monitoring", "grafana_dashboards", "ai-pipeline-metrics.json"
)
AI_ALERTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "monitoring", "alerting", "ai-pipeline-rules.yml"
)
PROMETHEUS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "monitoring", "prometheus.yml"
)


class TestAIPipelineGrafanaDashboard:
    """Validate AI Pipeline Metrics Grafana dashboard."""

    def test_dashboard_exists(self):
        """ai-pipeline-metrics.json must exist."""
        assert os.path.exists(GRAFANA_DASHBOARD_PATH)

    def test_valid_json(self):
        """Dashboard must be valid JSON."""
        with open(GRAFANA_DASHBOARD_PATH, "r") as f:
            dashboard = json.load(f)
        assert isinstance(dashboard, dict)

    def test_has_uid(self):
        """Dashboard must have a unique ID."""
        with open(GRAFANA_DASHBOARD_PATH, "r") as f:
            dashboard = json.load(f)
        assert "uid" in dashboard, "Dashboard missing uid"
        assert len(dashboard["uid"]) > 0

    def test_has_title(self):
        """Dashboard must have a title referencing AI pipeline."""
        with open(GRAFANA_DASHBOARD_PATH, "r") as f:
            dashboard = json.load(f)
        title = dashboard.get("title", "").lower()
        assert any(kw in title for kw in ["ai", "pipeline", "metrics"]), \
            f"Title should reference AI pipeline: {dashboard.get('title')}"

    def test_has_panels(self):
        """Dashboard must have at least 5 panels."""
        with open(GRAFANA_DASHBOARD_PATH, "r") as f:
            dashboard = json.load(f)
        panels = dashboard.get("panels", [])
        assert len(panels) >= 5, f"Expected >= 5 panels, got {len(panels)}"

    def test_uses_prometheus_datasource(self):
        """Dashboard must use Prometheus datasource."""
        with open(GRAFANA_DASHBOARD_PATH, "r") as f:
            dashboard = json.load(f)
        # Check templating or annotations for datasource
        content = json.dumps(dashboard).lower()
        assert "prometheus" in content, "Must reference Prometheus datasource"

    def test_has_ai_specific_panels(self):
        """Must have panels for AI-specific metrics."""
        with open(GRAFANA_DASHBOARD_PATH, "r") as f:
            dashboard = json.load(f)
        panels = dashboard.get("panels", [])
        panel_titles = " ".join(
            p.get("title", "").lower() for p in panels
        )
        # Should have at least 3 AI-related panels
        ai_keywords = ["technique", "latency", "token", "llm", "error", "fake", "jarvis"]
        found = sum(1 for kw in ai_keywords if kw in panel_titles)
        assert found >= 3, f"Need >= 3 AI-specific panels, found {found}"


class TestAIPipelineAlertRules:
    """Validate AI Pipeline alerting rules."""

    def test_alert_rules_exist(self):
        """ai-pipeline-rules.yml must exist."""
        assert os.path.exists(AI_ALERTS_PATH)

    def test_valid_yaml(self):
        """Alert rules must be valid YAML."""
        with open(AI_ALERTS_PATH, "r") as f:
            rules = yaml.safe_load(f)
        assert isinstance(rules, dict)

    def test_has_alert_groups(self):
        """Must define at least one alert group."""
        with open(AI_ALERTS_PATH, "r") as f:
            rules = yaml.safe_load(f)
        groups = rules.get("groups", [])
        assert len(groups) >= 1

    def test_has_parwa_ai_pipeline_group(self):
        """Must have 'parwa_ai_pipeline' alert group."""
        with open(AI_ALERTS_PATH, "r") as f:
            rules = yaml.safe_load(f)
        group_names = [g.get("name", "") for g in rules.get("groups", [])]
        assert "parwa_ai_pipeline" in group_names

    def test_has_minimum_5_rules(self):
        """Must have at least 5 AI pipeline alert rules."""
        with open(AI_ALERTS_PATH, "r") as f:
            rules = yaml.safe_load(f)
        total_rules = sum(len(g.get("rules", [])) for g in rules.get("groups", []))
        assert total_rules >= 5, f"Expected >= 5 rules, got {total_rules}"

    def test_rules_have_service_label(self):
        """All rules must have parwa_service label."""
        with open(AI_ALERTS_PATH, "r") as f:
            rules = yaml.safe_load(f)
        for group in rules.get("groups", []):
            for rule in group.get("rules", []):
                labels = rule.get("labels", {})
                assert "parwa_service" in labels, (
                    f"Rule '{rule.get('alert')}' missing parwa_service label"
                )

    def test_rules_have_severity(self):
        """All rules must have severity label (critical or warning)."""
        with open(AI_ALERTS_PATH, "r") as f:
            rules = yaml.safe_load(f)
        for group in rules.get("groups", []):
            for rule in group.get("rules", []):
                labels = rule.get("labels", {})
                assert "severity" in labels, (
                    f"Rule '{rule.get('alert')}' missing severity label"
                )
                assert labels["severity"] in ("critical", "warning")

    def test_rules_have_annotations(self):
        """All rules must have summary annotation."""
        with open(AI_ALERTS_PATH, "r") as f:
            rules = yaml.safe_load(f)
        for group in rules.get("groups", []):
            for rule in group.get("rules", []):
                annotations = rule.get("annotations", {})
                assert "summary" in annotations, (
                    f"Rule '{rule.get('alert')}' missing summary annotation"
                )

    def test_has_llm_error_rate_rule(self):
        """Must have LLM error rate alert."""
        with open(AI_ALERTS_PATH, "r") as f:
            rules = yaml.safe_load(f)
        all_rules = []
        for group in rules.get("groups", []):
            all_rules.extend(group.get("rules", []))
        alert_names = [r.get("alert", "") for r in all_rules]
        assert any("llm" in a.lower() and "error" in a.lower() for a in alert_names), \
            "Missing LLM error rate alert"

    def test_has_fallback_rule(self):
        """Must have Smart Router fallback alert."""
        with open(AI_ALERTS_PATH, "r") as f:
            rules = yaml.safe_load(f)
        all_rules = []
        for group in rules.get("groups", []):
            all_rules.extend(group.get("rules", []))
        alert_names = [r.get("alert", "") for r in all_rules]
        assert any("fallback" in a.lower() for a in alert_names), \
            "Missing Smart Router fallback alert"


class TestPrometheusAIConfig:
    """Validate Prometheus scrape configuration for AI metrics."""

    def test_prometheus_config_exists(self):
        """prometheus.yml must exist."""
        assert os.path.exists(PROMETHEUS_PATH)

    def test_valid_yaml(self):
        """Must be valid YAML."""
        with open(PROMETHEUS_PATH, "r") as f:
            config = yaml.safe_load(f)
        assert isinstance(config, dict)

    def test_has_ai_pipeline_scrape_job(self):
        """Must have parwa_ai_pipeline scrape job."""
        with open(PROMETHEUS_PATH, "r") as f:
            config = yaml.safe_load(f)
        jobs = [j.get("job_name", "") for j in config.get("scrape_configs", [])]
        assert "parwa_ai_pipeline" in jobs, "Missing parwa_ai_pipeline scrape job"

    def test_ai_scrape_targets_backend(self):
        """AI pipeline scrape must target backend:8000."""
        with open(PROMETHEUS_PATH, "r") as f:
            config = yaml.safe_load(f)
        for job in config.get("scrape_configs", []):
            if job.get("job_name") == "parwa_ai_pipeline":
                targets = job.get("static_configs", [{}])[0].get("targets", [])
                assert "backend:8000" in targets
                break

    def test_ai_scrape_interval_10s(self):
        """AI pipeline scrape interval should be 10s."""
        with open(PROMETHEUS_PATH, "r") as f:
            config = yaml.safe_load(f)
        for job in config.get("scrape_configs", []):
            if job.get("job_name") == "parwa_ai_pipeline":
                assert job.get("scrape_interval") == "10s"
                break

    def test_includes_ai_alert_rules(self):
        """Must include ai-pipeline-rules.yml in rule_files."""
        with open(PROMETHEUS_PATH, "r") as f:
            config = yaml.safe_load(f)
        rule_files = config.get("rule_files", [])
        assert any("ai-pipeline" in str(rf) for rf in rule_files), \
            "Missing ai-pipeline-rules.yml in rule_files"


class TestMonitoringAlertingIntegration:
    """Validate integration between Prometheus, AlertManager, and Grafana."""

    def test_prometheus_has_alertmanager_config(self):
        """Prometheus must be configured to send alerts to AlertManager."""
        with open(PROMETHEUS_PATH, "r") as f:
            config = yaml.safe_load(f)
        alertmanagers = config.get("alerting", {}).get("alertmanagers", [])
        assert len(alertmanagers) > 0, "No AlertManager targets configured"

    def test_alertmanager_config_exists(self):
        """alertmanager.yml must exist."""
        am_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "monitoring", "alertmanager", "alertmanager.yml"
        )
        assert os.path.exists(am_path)

    def test_alertmanager_has_receivers(self):
        """AlertManager must have at least 2 receivers."""
        am_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "monitoring", "alertmanager", "alertmanager.yml"
        )
        with open(am_path, "r") as f:
            am_config = yaml.safe_load(f)
        receivers = am_config.get("receivers", [])
        assert len(receivers) >= 2, f"Expected >= 2 receivers, got {len(receivers)}"

    def test_alertmanager_has_critical_routing(self):
        """AlertManager must route critical alerts to specific receiver."""
        am_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "monitoring", "alertmanager", "alertmanager.yml"
        )
        with open(am_path, "r") as f:
            am_config = yaml.safe_load(f)
        routes = am_config.get("route", {}).get("routes", [])
        severity_routes = [r for r in routes if r.get("match", {}).get("severity") == "critical"]
        assert len(severity_routes) > 0, "Missing critical severity route"

    def test_grafana_datasource_provisioned(self):
        """Grafana must have Prometheus datasource provisioned."""
        ds_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "monitoring", "grafana", "provisioning", "datasources", "datasource.yml"
        )
        assert os.path.exists(ds_path)
        with open(ds_path, "r") as f:
            ds_config = yaml.safe_load(f)
        datasources = ds_config.get("datasources", [])
        assert any("prometheus" in str(ds).lower() for ds in datasources)

    def test_multiple_grafana_dashboards(self):
        """Must have at least 4 Grafana dashboards provisioned."""
        dashboards_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "monitoring", "grafana_dashboards"
        )
        json_files = [f for f in os.listdir(dashboards_dir) if f.endswith(".json")]
        assert len(json_files) >= 4, f"Expected >= 4 dashboards, got {len(json_files)}"
