#!/usr/bin/env python3
"""
PARWA Day 3 Morning — Monitoring E2E Tests
Full monitoring pipeline validation: Prometheus config, alerting rules,
Alertmanager routing, Grafana provisioning, dashboards, and exporters.
"""
import os
import yaml
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
K8S_DIR = os.path.join(PROJECT_ROOT, "infra", "k8s")
MON_DIR = os.path.join(K8S_DIR, "monitoring")
EXP_DIR = os.path.join(K8S_DIR, "exporters")


def load_yaml(path):
    with open(path) as f:
        return list(yaml.safe_load_all(f))


def load_yaml_first(path):
    docs = load_yaml(path)
    return docs[0] if docs else None


def load_file(path):
    with open(path) as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1-3. Prometheus ConfigMap: exists, alerting, rule_files
# ---------------------------------------------------------------------------
class TestPrometheusConfig:
    """Prometheus ConfigMap must exist with proper alerting and rule_files config."""

    def test_prometheus_configmap_exists(self):
        """Prometheus ConfigMap must exist and parse as valid YAML."""
        path = os.path.join(MON_DIR, "prometheus", "configmap.yaml")
        assert os.path.exists(path), "Prometheus ConfigMap not found"
        doc = load_yaml_first(path)
        assert doc is not None
        assert doc["kind"] == "ConfigMap"

    def test_prometheus_config_has_alerting_section(self):
        """Prometheus config must have an alerting section pointing to alertmanager."""
        cm = load_yaml_first(os.path.join(MON_DIR, "prometheus", "configmap.yaml"))
        config = cm["data"]["prometheus.yml"]
        assert "alerting:" in config, "Prometheus config missing 'alerting:' section"
        assert "alertmanager" in config, "Prometheus config missing alertmanager reference"

    def test_prometheus_config_has_rule_files(self):
        """Prometheus config must have rule_files reference."""
        cm = load_yaml_first(os.path.join(MON_DIR, "prometheus", "configmap.yaml"))
        config = cm["data"]["prometheus.yml"]
        assert "rule_files:" in config, "Prometheus config missing 'rule_files:' section"


# ---------------------------------------------------------------------------
# 4. All scrape targets configured
# ---------------------------------------------------------------------------
class TestPrometheusScrapeTargets:
    """All required scrape targets must be configured in Prometheus."""

    EXPECTED_TARGETS = [
        "parwa-backend",
        "parwa-postgres",
        "parwa-redis",
        "parwa-frontend",
        "parwa-worker",
        "parwa-mcp",
        "prometheus-self",
        "grafana",
        "nginx-exporter",
    ]

    @pytest.mark.parametrize("target", EXPECTED_TARGETS)
    def test_scrape_target_configured(self, target):
        """Each required scrape target must appear in the Prometheus config."""
        cm = load_yaml_first(os.path.join(MON_DIR, "prometheus", "configmap.yaml"))
        config = cm["data"]["prometheus.yml"]
        assert target in config, f"Prometheus config missing scrape target: {target}"


# ---------------------------------------------------------------------------
# 5-6. Alerting rules: runbook_url annotations and regex usage
# ---------------------------------------------------------------------------
class TestAlertRules:
    """Alerting rules must have runbook_url annotations and proper regex."""

    def test_rules_configmap_exists(self):
        """Prometheus alerting rules ConfigMap must exist."""
        path = os.path.join(MON_DIR, "prometheus", "rules-configmap.yaml")
        assert os.path.exists(path), "Rules ConfigMap not found"

    def test_all_alerts_have_runbook_url(self):
        """All alert rules must have runbook_url annotations."""
        cm = load_yaml_first(os.path.join(MON_DIR, "prometheus", "rules-configmap.yaml"))
        for key, val in cm["data"].items():
            if not val or not val.strip():
                continue
            rules_docs = list(yaml.safe_load_all(val))
            for doc in rules_docs:
                if doc and "groups" in doc:
                    for group in doc["groups"]:
                        for rule in group.get("rules", []):
                            if "alert" in rule:
                                annotations = rule.get("annotations", {})
                                assert "runbook_url" in annotations, \
                                    f"Alert '{rule['alert']}' missing runbook_url annotation"

    def test_subsystem_degraded_uses_regex_match(self):
        """ParwaSubsystemDegraded alert must use =~ (regex) not exact match =."""
        cm = load_yaml_first(os.path.join(MON_DIR, "prometheus", "rules-configmap.yaml"))
        all_data = "\n".join(cm["data"].values())
        # Find the ParwaSubsystemDegraded alert expression
        assert "ParwaSubsystemDegraded" in all_data, \
            "ParwaSubsystemDegraded alert not found"
        for key, val in cm["data"].items():
            if not val or not val.strip():
                continue
            if "ParwaSubsystemDegraded" not in val:
                continue
            rules_docs = list(yaml.safe_load_all(val))
            for doc in rules_docs:
                if doc and "groups" in doc:
                    for group in doc["groups"]:
                        for rule in group.get("rules", []):
                            if rule.get("alert") == "ParwaSubsystemDegraded":
                                expr = rule.get("expr", "")
                                assert "=~" in str(expr), \
                                    "ParwaSubsystemDegraded must use =~ regex, not exact match ="


# ---------------------------------------------------------------------------
# 7-8. Alertmanager ConfigMap: route tree and dead-mans-switch
# ---------------------------------------------------------------------------
class TestAlertmanagerConfig:
    """Alertmanager must have proper route tree and fallback receiver."""

    def test_alertmanager_configmap_exists(self):
        """Alertmanager ConfigMap must exist and parse."""
        path = os.path.join(MON_DIR, "alertmanager", "configmap.yaml")
        assert os.path.exists(path), "Alertmanager ConfigMap not found"
        cm = load_yaml_first(path)
        assert cm["kind"] == "ConfigMap"

    def test_alertmanager_has_route_tree(self):
        """Alertmanager config must have route tree with critical/warning receivers."""
        cm = load_yaml_first(os.path.join(MON_DIR, "alertmanager", "configmap.yaml"))
        config = cm["data"]["alertmanager.yml"]
        # Parse the YAML inside the ConfigMap data
        am_config = yaml.safe_load(config)
        assert "route" in am_config, "Alertmanager config missing 'route' section"
        route = am_config["route"]
        assert "routes" in route, "Alertmanager route missing sub-routes"
        # Check for critical and warning routing
        routes = route["routes"]
        receivers_in_routes = []
        for r in routes:
            recv = r.get("receiver", "")
            receivers_in_routes.append(recv)
        # Should have at least one critical and one warning receiver
        has_critical = any("critical" in r.lower() for r in receivers_in_routes)
        has_warning = any("warning" in r.lower() for r in receivers_in_routes)
        assert has_critical, "Alertmanager route tree missing critical receiver"
        assert has_warning, "Alertmanager route tree missing warning receiver"

    def test_alertmanager_has_dead_mans_switch(self):
        """Alertmanager must have a dead-mans-switch / fallback receiver."""
        cm = load_yaml_first(os.path.join(MON_DIR, "alertmanager", "configmap.yaml"))
        config = cm["data"]["alertmanager.yml"]
        assert "dead-mans-switch" in config, \
            "Alertmanager config missing dead-mans-switch receiver"

    def test_alertmanager_has_receivers(self):
        """Alertmanager must define receivers."""
        cm = load_yaml_first(os.path.join(MON_DIR, "alertmanager", "configmap.yaml"))
        config = cm["data"]["alertmanager.yml"]
        am_config = yaml.safe_load(config)
        assert "receivers" in am_config, "Alertmanager config missing 'receivers' section"
        assert len(am_config["receivers"]) >= 3, \
            "Alertmanager should have at least 3 receivers (critical, warning, dead-mans-switch)"


# ---------------------------------------------------------------------------
# 9-10. Grafana provisioning: datasource and dashboard
# ---------------------------------------------------------------------------
class TestGrafanaProvisioning:
    """Grafana must have proper datasource and dashboard provisioning."""

    def test_datasource_provisioning_exists(self):
        """Grafana datasource provisioning ConfigMap must exist."""
        path = os.path.join(MON_DIR, "grafana", "datasource-configmap.yaml")
        assert os.path.exists(path), "Grafana datasource ConfigMap not found"

    def test_datasource_has_uid_prometheus(self):
        """Grafana datasource must have uid: prometheus."""
        cm = load_yaml_first(os.path.join(MON_DIR, "grafana", "datasource-configmap.yaml"))
        all_data = "\n".join(cm["data"].values())
        assert "uid: prometheus" in all_data, \
            "Grafana datasource missing 'uid: prometheus'"

    def test_dashboard_provisioning_exists(self):
        """Grafana dashboard provisioning ConfigMap must exist."""
        path = os.path.join(MON_DIR, "grafana", "dashboard-configmap.yaml")
        assert os.path.exists(path), "Grafana dashboard provisioning ConfigMap not found"

    def test_dashboard_not_editable(self):
        """Grafana dashboards must be provisioned as non-editable."""
        cm = load_yaml_first(os.path.join(MON_DIR, "grafana", "dashboard-configmap.yaml"))
        all_data = "\n".join(cm["data"].values())
        assert "editable: false" in all_data, \
            "Grafana dashboard provisioning must set editable: false"


# ---------------------------------------------------------------------------
# 11. Dashboard ConfigMaps exist for Redis, PostgreSQL, Nginx
# ---------------------------------------------------------------------------
class TestDashboardConfigMaps:
    """Dashboard JSON ConfigMaps must exist for key infrastructure."""

    EXPECTED_DASHBOARDS = {
        "redis": "monitoring/grafana/dashboards/redis-dashboard-configmap.yaml",
        "postgres": "monitoring/grafana/dashboards/postgres-dashboard-configmap.yaml",
        "nginx": "monitoring/grafana/dashboards/nginx-dashboard-configmap.yaml",
    }

    @pytest.mark.parametrize("name,rel_path", list(EXPECTED_DASHBOARDS.items()),
                             ids=list(EXPECTED_DASHBOARDS.keys()))
    def test_dashboard_configmap_exists(self, name, rel_path):
        """Dashboard ConfigMap must exist."""
        path = os.path.join(K8S_DIR, rel_path)
        assert os.path.exists(path), f"Dashboard ConfigMap missing: {name}"

    @pytest.mark.parametrize("name,rel_path", list(EXPECTED_DASHBOARDS.items()),
                             ids=list(EXPECTED_DASHBOARDS.keys()))
    def test_dashboard_json_valid(self, name, rel_path):
        """Dashboard JSON must parse and contain panels."""
        path = os.path.join(K8S_DIR, rel_path)
        cm = load_yaml_first(path)
        for key, val in cm["data"].items():
            if val and val.strip():
                dashboard = yaml.safe_load(val)
                assert "panels" in dashboard, \
                    f"{name} dashboard JSON missing 'panels' key"


# ---------------------------------------------------------------------------
# 12. Exporter deployments exist
# ---------------------------------------------------------------------------
class TestExporterDeployments:
    """Postgres and Redis exporter deployments must exist."""

    def test_postgres_exporter_deployment_exists(self):
        """Postgres exporter deployment must exist."""
        path = os.path.join(EXP_DIR, "postgres-exporter-deployment.yaml")
        assert os.path.exists(path), "Postgres exporter deployment not found"
        doc = load_yaml_first(path)
        assert doc["kind"] == "Deployment"

    def test_redis_exporter_deployment_exists(self):
        """Redis exporter deployment must exist."""
        path = os.path.join(EXP_DIR, "redis-exporter-deployment.yaml")
        assert os.path.exists(path), "Redis exporter deployment not found"
        doc = load_yaml_first(path)
        assert doc["kind"] == "Deployment"

    def test_postgres_exporter_service_exists(self):
        """Postgres exporter service must exist."""
        path = os.path.join(EXP_DIR, "postgres-exporter-service.yaml")
        assert os.path.exists(path), "Postgres exporter service not found"
        doc = load_yaml_first(path)
        assert doc["kind"] == "Service"

    def test_redis_exporter_service_exists(self):
        """Redis exporter service must exist."""
        path = os.path.join(EXP_DIR, "redis-exporter-service.yaml")
        assert os.path.exists(path), "Redis exporter service not found"
        doc = load_yaml_first(path)
        assert doc["kind"] == "Service"
