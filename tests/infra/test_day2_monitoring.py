#!/usr/bin/env python3
"""
PARWA Day 2 — Monitoring Stack Tests
Tests: PVCs, Prometheus config, Alertmanager config, alert rules,
       exporters, Grafana provisioning, dashboards, service selectors
"""
import unittest
import yaml
import os
import glob

K8S_DIR = "/home/z/my-project/download/parwa/infra/k8s"
MON_DIR = f"{K8S_DIR}/monitoring"
EXP_DIR = f"{K8S_DIR}/exporters"


def load_yaml(path):
    with open(path) as f:
        return list(yaml.safe_load_all(f))


def load_yaml_first(path):
    docs = load_yaml(path)
    return docs[0] if docs else None


class TestMonitoringPVCs(unittest.TestCase):
    """#100, #108, #115: Monitoring data must persist across pod restarts"""

    def test_prometheus_pvc_exists(self):
        pvc = load_yaml_first(f"{MON_DIR}/prometheus/pvc.yaml")
        self.assertEqual(pvc["kind"], "PersistentVolumeClaim")
        self.assertEqual(pvc["metadata"]["name"], "prometheus-data")

    def test_prometheus_pvc_size(self):
        pvc = load_yaml_first(f"{MON_DIR}/prometheus/pvc.yaml")
        self.assertEqual(pvc["spec"]["resources"]["requests"]["storage"], "50Gi")

    def test_prometheus_pvc_storageclass(self):
        pvc = load_yaml_first(f"{MON_DIR}/prometheus/pvc.yaml")
        self.assertEqual(pvc["spec"]["storageClassName"], "gp3")

    def test_grafana_pvc_exists(self):
        pvc = load_yaml_first(f"{MON_DIR}/grafana/pvc.yaml")
        self.assertEqual(pvc["kind"], "PersistentVolumeClaim")
        self.assertEqual(pvc["metadata"]["name"], "grafana-data")

    def test_grafana_pvc_size(self):
        pvc = load_yaml_first(f"{MON_DIR}/grafana/pvc.yaml")
        self.assertEqual(pvc["spec"]["resources"]["requests"]["storage"], "5Gi")

    def test_alertmanager_pvc_exists(self):
        pvc = load_yaml_first(f"{MON_DIR}/alertmanager/pvc.yaml")
        self.assertEqual(pvc["kind"], "PersistentVolumeClaim")
        self.assertEqual(pvc["metadata"]["name"], "alertmanager-data")

    def test_prometheus_deployment_uses_pvc(self):
        dep = load_yaml_first(f"{MON_DIR}/prometheus/deployment.yaml")
        volumes = dep["spec"]["template"]["spec"]["volumes"]
        data_vol = next(v for v in volumes if v["name"] == "prometheus-data")
        self.assertIn("persistentVolumeClaim", data_vol)
        self.assertNotIn("emptyDir", data_vol)

    def test_grafana_deployment_uses_pvc(self):
        dep = load_yaml_first(f"{MON_DIR}/grafana/deployment.yaml")
        volumes = dep["spec"]["template"]["spec"]["volumes"]
        data_vol = next(v for v in volumes if v["name"] == "grafana-data")
        self.assertIn("persistentVolumeClaim", data_vol)
        self.assertNotIn("emptyDir", data_vol)

    def test_alertmanager_deployment_uses_pvc(self):
        dep = load_yaml_first(f"{MON_DIR}/alertmanager/deployment.yaml")
        volumes = dep["spec"]["template"]["spec"]["volumes"]
        data_vol = next(v for v in volumes if v["name"] == "alertmanager-data")
        self.assertIn("persistentVolumeClaim", data_vol)
        self.assertNotIn("emptyDir", data_vol)


class TestPrometheusConfig(unittest.TestCase):
    """#102, #103, #145-150: Complete Prometheus configuration"""

    def test_prometheus_config_has_alerting(self):
        cm = load_yaml_first(f"{MON_DIR}/prometheus/configmap.yaml")
        config = cm["data"]["prometheus.yml"]
        self.assertIn("alerting:", config)

    def test_prometheus_config_has_rule_files(self):
        cm = load_yaml_first(f"{MON_DIR}/prometheus/configmap.yaml")
        config = cm["data"]["prometheus.yml"]
        self.assertIn("rule_files:", config)

    def test_prometheus_config_has_self_scrape(self):
        cm = load_yaml_first(f"{MON_DIR}/prometheus/configmap.yaml")
        config = cm["data"]["prometheus.yml"]
        self.assertIn("prometheus-self", config)

    def test_prometheus_config_has_grafana_scrape(self):
        cm = load_yaml_first(f"{MON_DIR}/prometheus/configmap.yaml")
        config = cm["data"]["prometheus.yml"]
        self.assertIn("grafana", config)

    def test_prometheus_config_has_nginx_exporter_scrape(self):
        cm = load_yaml_first(f"{MON_DIR}/prometheus/configmap.yaml")
        config = cm["data"]["prometheus.yml"]
        self.assertIn("nginx-exporter", config)

    def test_prometheus_config_has_external_labels(self):
        cm = load_yaml_first(f"{MON_DIR}/prometheus/configmap.yaml")
        config = cm["data"]["prometheus.yml"]
        self.assertIn("external_labels:", config)

    def test_prometheus_deployment_has_rules_volume(self):
        dep = load_yaml_first(f"{MON_DIR}/prometheus/deployment.yaml")
        volumes = dep["spec"]["template"]["spec"]["volumes"]
        rules_vols = [v for v in volumes if v["name"] == "rules"]
        self.assertTrue(len(rules_vols) > 0, "No 'rules' volume found in Prometheus deployment")


class TestAlertmanagerConfig(unittest.TestCase):
    """#114, #116, #163, #165, #167, #168"""

    def test_alertmanager_configmap_exists(self):
        path = f"{MON_DIR}/alertmanager/configmap.yaml"
        self.assertTrue(os.path.exists(path))

    def test_alertmanager_has_receivers(self):
        cm = load_yaml_first(f"{MON_DIR}/alertmanager/configmap.yaml")
        config = cm["data"]["alertmanager.yml"]
        self.assertIn("receivers:", config)

    def test_alertmanager_has_inhibit_rules(self):
        cm = load_yaml_first(f"{MON_DIR}/alertmanager/configmap.yaml")
        config = cm["data"]["alertmanager.yml"]
        self.assertIn("inhibit_rules:", config)

    def test_alertmanager_has_mute_time_intervals(self):
        cm = load_yaml_first(f"{MON_DIR}/alertmanager/configmap.yaml")
        config = cm["data"]["alertmanager.yml"]
        self.assertIn("mute_time_intervals:", config)

    def test_alertmanager_has_dead_mans_switch(self):
        cm = load_yaml_first(f"{MON_DIR}/alertmanager/configmap.yaml")
        config = cm["data"]["alertmanager.yml"]
        self.assertIn("dead-mans-switch", config)

    def test_alertmanager_deployment_mounts_config(self):
        dep = load_yaml_first(f"{MON_DIR}/alertmanager/deployment.yaml")
        mounts = dep["spec"]["template"]["spec"]["containers"][0]["volumeMounts"]
        mount_paths = [m["mountPath"] for m in mounts]
        self.assertTrue(any("/etc/alertmanager" in p for p in mount_paths))


class TestAlertRules(unittest.TestCase):
    """#151-161: Prometheus alerting rules"""

    def test_rules_configmap_exists(self):
        path = f"{MON_DIR}/prometheus/rules-configmap.yaml"
        self.assertTrue(os.path.exists(path))

    def test_subsystem_degraded_rule_uses_regex(self):
        """#151, #159: Must use =~ not ="""
        cm = load_yaml_first(f"{MON_DIR}/prometheus/rules-configmap.yaml")
        for key, val in cm["data"].items():
            if "infrastructure" in key or "application" in key:
                self.assertIn("=~", val, f"Rule file {key} must use =~ for regex matching")

    def test_all_alerts_have_runbook_url(self):
        """#158: All alerts must have runbook_url annotations"""
        cm = load_yaml_first(f"{MON_DIR}/prometheus/rules-configmap.yaml")
        for key, val in cm["data"].items():
            if not val.strip():
                continue
            rules_docs = list(yaml.safe_load_all(val))
            for doc in rules_docs:
                if doc and "groups" in doc:
                    for group in doc["groups"]:
                        for rule in group.get("rules", []):
                            if "alert" in rule:
                                self.assertIn("runbook_url", rule.get("annotations", {}),
                                              f"Alert {rule['alert']} missing runbook_url")

    def test_ssl_cert_expiry_alert_exists(self):
        cm = load_yaml_first(f"{MON_DIR}/prometheus/rules-configmap.yaml")
        all_data = "\n".join(cm["data"].values())
        self.assertIn("ParwaSSLCertExpiry", all_data)

    def test_backup_failure_alert_exists(self):
        cm = load_yaml_first(f"{MON_DIR}/prometheus/rules-configmap.yaml")
        all_data = "\n".join(cm["data"].values())
        self.assertIn("ParwaBackupFailed", all_data)

    def test_disk_space_alert_exists(self):
        cm = load_yaml_first(f"{MON_DIR}/prometheus/rules-configmap.yaml")
        all_data = "\n".join(cm["data"].values())
        self.assertIn("ParwaDiskSpaceLow", all_data)

    def test_redis_down_alert_exists(self):
        cm = load_yaml_first(f"{MON_DIR}/prometheus/rules-configmap.yaml")
        all_data = "\n".join(cm["data"].values())
        self.assertIn("ParwaRedisDown", all_data)

    def test_llm_provider_outage_alert_exists(self):
        cm = load_yaml_first(f"{MON_DIR}/prometheus/rules-configmap.yaml")
        all_data = "\n".join(cm["data"].values())
        self.assertIn("ParwaLLMProviderOutage", all_data)


class TestExporters(unittest.TestCase):
    """#104: postgres-exporter and redis-exporter deployments"""

    def test_postgres_exporter_deployment_exists(self):
        path = f"{EXP_DIR}/postgres-exporter-deployment.yaml"
        self.assertTrue(os.path.exists(path))

    def test_postgres_exporter_service_exists(self):
        svc = load_yaml_first(f"{EXP_DIR}/postgres-exporter-service.yaml")
        self.assertEqual(svc["kind"], "Service")
        self.assertEqual(svc["spec"]["ports"][0]["port"], 9187)

    def test_redis_exporter_deployment_exists(self):
        path = f"{EXP_DIR}/redis-exporter-deployment.yaml"
        self.assertTrue(os.path.exists(path))

    def test_redis_exporter_service_exists(self):
        svc = load_yaml_first(f"{EXP_DIR}/redis-exporter-service.yaml")
        self.assertEqual(svc["kind"], "Service")
        self.assertEqual(svc["spec"]["ports"][0]["port"], 9121)

    def test_postgres_exporter_dsn_from_secret(self):
        dep = load_yaml_first(f"{EXP_DIR}/postgres-exporter-deployment.yaml")
        envs = dep["spec"]["template"]["spec"]["containers"][0].get("env", [])
        dsn_env = next((e for e in envs if e.get("name") == "DATA_SOURCE_NAME"), None)
        self.assertIsNotNone(dsn_env, "DATA_SOURCE_NAME env not found")
        self.assertIn("secretKeyRef", dsn_env.get("valueFrom", {}))

    def test_redis_exporter_password_from_secret(self):
        dep = load_yaml_first(f"{EXP_DIR}/redis-exporter-deployment.yaml")
        envs = dep["spec"]["template"]["spec"]["containers"][0].get("env", [])
        pwd_env = next((e for e in envs if e.get("name") == "REDIS_PASSWORD"), None)
        self.assertIsNotNone(pwd_env, "REDIS_PASSWORD env not found")
        self.assertIn("secretKeyRef", pwd_env.get("valueFrom", {}))


class TestGrafanaProvisioning(unittest.TestCase):
    """#109-113, #176, #177, #179, #180"""

    def test_datasource_configmap_exists(self):
        path = f"{MON_DIR}/grafana/datasource-configmap.yaml"
        self.assertTrue(os.path.exists(path))

    def test_datasource_has_uid(self):
        """#176: datasource must have uid: prometheus"""
        cm = load_yaml_first(f"{MON_DIR}/grafana/datasource-configmap.yaml")
        all_data = "\n".join(cm["data"].values())
        self.assertIn("uid: prometheus", all_data)

    def test_dashboard_configmap_not_editable(self):
        """#179: dashboards must be non-editable"""
        cm = load_yaml_first(f"{MON_DIR}/grafana/dashboard-configmap.yaml")
        all_data = "\n".join(cm["data"].values())
        self.assertIn("editable: false", all_data)

    def test_grafana_admin_user_from_secret(self):
        """#113: admin user from secret"""
        dep = load_yaml_first(f"{MON_DIR}/grafana/deployment.yaml")
        envs = dep["spec"]["template"]["spec"]["containers"][0]["env"]
        user_env = next((e for e in envs if e.get("name") == "GF_SECURITY_ADMIN_USER"), None)
        self.assertIsNotNone(user_env, "GF_SECURITY_ADMIN_USER not found")
        self.assertIn("secretKeyRef", user_env.get("valueFrom", {}))

    def test_grafana_admin_password_from_secret(self):
        dep = load_yaml_first(f"{MON_DIR}/grafana/deployment.yaml")
        envs = dep["spec"]["template"]["spec"]["containers"][0]["env"]
        pwd_env = next((e for e in envs if e.get("name") == "GF_SECURITY_ADMIN_PASSWORD"), None)
        self.assertIsNotNone(pwd_env)
        self.assertIn("secretKeyRef", pwd_env.get("valueFrom", {}))

    def test_grafana_has_serviceaccount(self):
        """#112"""
        dep = load_yaml_first(f"{MON_DIR}/grafana/deployment.yaml")
        self.assertIn("serviceAccountName", dep["spec"]["template"]["spec"])

    def test_dashboard_jsons_exist(self):
        for name in ["redis", "postgres", "nginx"]:
            path = f"{MON_DIR}/grafana/dashboards/{name}-dashboard-configmap.yaml"
            self.assertTrue(os.path.exists(path), f"Missing {name} dashboard")

    def test_dashboard_jsons_valid_yaml(self):
        for name in ["redis", "postgres", "nginx"]:
            path = f"{MON_DIR}/grafana/dashboards/{name}-dashboard-configmap.yaml"
            cm = load_yaml_first(path)
            for key, val in cm["data"].items():
                if val.strip():
                    dashboard = yaml.safe_load(val)
                    self.assertIn("panels", dashboard, f"{name} dashboard missing panels")


class TestServiceSelectors(unittest.TestCase):
    """All K8s Services must use flat selector (not matchLabels)"""

    def _check_service_selector(self, path):
        svc = load_yaml_first(path)
        selector = svc["spec"].get("selector", {})
        self.assertNotIn("matchLabels", selector,
                         f"Service {svc['metadata']['name']} uses invalid matchLabels in selector")
        self.assertTrue(len(selector) > 0, f"Service {svc['metadata']['name']} has empty selector")

    def test_prometheus_service_selector(self):
        self._check_service_selector(f"{MON_DIR}/prometheus/service.yaml")

    def test_grafana_service_selector(self):
        self._check_service_selector(f"{MON_DIR}/grafana/service.yaml")

    def test_alertmanager_service_selector(self):
        self._check_service_selector(f"{MON_DIR}/alertmanager/service.yaml")

    def test_backend_service_selector(self):
        self._check_service_selector(f"{K8S_DIR}/backend/service.yaml")

    def test_frontend_service_selector(self):
        self._check_service_selector(f"{K8S_DIR}/frontend/service.yaml")

    def test_mcp_service_selector(self):
        self._check_service_selector(f"{K8S_DIR}/mcp/service.yaml")

    def test_postgres_service_selector(self):
        self._check_service_selector(f"{K8S_DIR}/postgres/service.yaml")

    def test_redis_service_selector(self):
        self._check_service_selector(f"{K8S_DIR}/redis/service.yaml")


class TestSecretsComplete(unittest.TestCase):
    """GRAFANA_ADMIN_USER and GRAFANA_ADMIN_PASSWORD in secrets"""

    def test_grafana_admin_user_in_secrets(self):
        secrets = load_yaml_first(f"{K8S_DIR}/secrets.yaml")
        self.assertIn("GRAFANA_ADMIN_USER", secrets["stringData"])

    def test_grafana_admin_password_in_secrets(self):
        secrets = load_yaml_first(f"{K8S_DIR}/secrets.yaml")
        self.assertIn("GRAFANA_ADMIN_PASSWORD", secrets["stringData"])


if __name__ == "__main__":
    unittest.main()
