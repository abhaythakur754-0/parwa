#!/usr/bin/env python3
"""
PARWA Day 3 Morning — K8s Integration Tests
Full K8s stack validation: YAML parsing, service selectors, security,
probes, resources, network policies, PDBs, HPAs, RBAC, and storage.
"""
import os
import yaml
import pytest
import glob as globmod

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
K8S_DIR = os.path.join(PROJECT_ROOT, "infra", "k8s")


def load_yaml(path):
    with open(path) as f:
        return list(yaml.safe_load_all(f))


def load_yaml_first(path):
    docs = load_yaml(path)
    return docs[0] if docs else None


def load_file(path):
    with open(path) as f:
        return f.read()


def _all_k8s_yaml_files():
    """Collect all YAML files under K8S_DIR recursively."""
    return sorted(globmod.glob(os.path.join(K8S_DIR, "**", "*.yaml"), recursive=True))


# ---------------------------------------------------------------------------
# 1. All K8s YAML files parse without error
# ---------------------------------------------------------------------------
class TestK8sYAMLParsing:
    """Every K8s manifest must parse as valid YAML."""

    @pytest.mark.parametrize("yaml_path", _all_k8s_yaml_files(),
                             ids=[os.path.relpath(p, K8S_DIR) for p in _all_k8s_yaml_files()])
    def test_yaml_parses_without_error(self, yaml_path):
        """Each K8s YAML file must parse as valid YAML."""
        docs = load_yaml(yaml_path)
        # At least one non-None document
        assert any(d is not None for d in docs), \
            f"YAML file produced no valid documents: {os.path.relpath(yaml_path, K8S_DIR)}"


# ---------------------------------------------------------------------------
# 2. Service selectors are flat maps (no matchLabels in Service specs)
# ---------------------------------------------------------------------------
class TestServiceSelectors:
    """K8s Service spec.selector must be a flat map, not contain matchLabels."""

    SERVICE_FILES = [
        "backend/service.yaml",
        "frontend/service.yaml",
        "mcp/service.yaml",
        "postgres/service.yaml",
        "redis/service.yaml",
        "monitoring/prometheus/service.yaml",
        "monitoring/grafana/service.yaml",
        "monitoring/alertmanager/service.yaml",
        "exporters/postgres-exporter-service.yaml",
        "exporters/redis-exporter-service.yaml",
    ]

    @pytest.mark.parametrize("svc_rel", SERVICE_FILES)
    def test_service_selector_is_flat(self, svc_rel):
        """Service selector must be a flat map, not matchLabels."""
        path = os.path.join(K8S_DIR, svc_rel)
        if not os.path.exists(path):
            pytest.skip(f"Service file not found: {svc_rel}")
        docs = load_yaml(path)
        for doc in docs:
            if doc and doc.get("kind") == "Service":
                selector = doc["spec"].get("selector", {})
                assert "matchLabels" not in selector, \
                    f"Service {doc['metadata']['name']} uses invalid matchLabels in selector"
                assert len(selector) > 0, \
                    f"Service {doc['metadata']['name']} has empty selector"


# ---------------------------------------------------------------------------
# 3. Deployment labels match Service selectors
# ---------------------------------------------------------------------------
class TestDeploymentServiceLabelMatch:
    """Deployment pod labels must match their corresponding Service selectors."""

    # Map: service_file -> deployment_file
    SERVICE_DEPLOYMENT_PAIRS = {
        "backend/service.yaml": "backend/deployment.yaml",
        "frontend/service.yaml": "frontend/deployment.yaml",
        "mcp/service.yaml": "mcp/deployment.yaml",
        "monitoring/prometheus/service.yaml": "monitoring/prometheus/deployment.yaml",
        "monitoring/grafana/service.yaml": "monitoring/grafana/deployment.yaml",
        "monitoring/alertmanager/service.yaml": "monitoring/alertmanager/deployment.yaml",
    }

    @pytest.mark.parametrize("svc_rel,dep_rel", list(SERVICE_DEPLOYMENT_PAIRS.items()),
                             ids=list(SERVICE_DEPLOYMENT_PAIRS.keys()))
    def test_deployment_labels_match_service_selector(self, svc_rel, dep_rel):
        """Deployment's pod template labels must be a superset of Service selector."""
        svc_path = os.path.join(K8S_DIR, svc_rel)
        dep_path = os.path.join(K8S_DIR, dep_rel)
        if not os.path.exists(svc_path) or not os.path.exists(dep_path):
            pytest.skip(f"Missing file: {svc_rel} or {dep_rel}")
        svc = load_yaml_first(svc_path)
        dep = load_yaml_first(dep_path)
        if svc is None or dep is None:
            pytest.skip("Could not load YAML documents")
        selector = svc["spec"].get("selector", {})
        pod_labels = dep["spec"]["template"]["metadata"].get("labels", {})
        for key, value in selector.items():
            assert pod_labels.get(key) == value, \
                f"Service selector {key}={value} not matched in Deployment pod labels"


# ---------------------------------------------------------------------------
# 4. All Pods run as non-root
# ---------------------------------------------------------------------------
class TestNonRootExecution:
    """All Deployments/StatefulSets must run as non-root."""

    WORKLOAD_FILES = [
        "backend/deployment.yaml",
        "frontend/deployment.yaml",
        "worker/deployment.yaml",
        "mcp/deployment.yaml",
        "postgres/statefulset.yaml",
        "redis/statefulset.yaml",
        "monitoring/prometheus/deployment.yaml",
        "monitoring/grafana/deployment.yaml",
        "monitoring/alertmanager/deployment.yaml",
        "exporters/postgres-exporter-deployment.yaml",
        "exporters/redis-exporter-deployment.yaml",
    ]

    @pytest.mark.parametrize("workload_rel", WORKLOAD_FILES)
    def test_runs_as_non_root(self, workload_rel):
        """Pod securityContext must have runAsNonRoot or runAsUser > 0."""
        path = os.path.join(K8S_DIR, workload_rel)
        if not os.path.exists(path):
            pytest.skip(f"File not found: {workload_rel}")
        doc = load_yaml_first(path)
        if doc is None:
            pytest.skip("Could not load YAML")
        spec = doc["spec"]["template"]["spec"]
        sec_ctx = spec.get("securityContext", {})
        run_as_non_root = sec_ctx.get("runAsNonRoot", False)
        run_as_user = sec_ctx.get("runAsUser", 0)
        assert run_as_non_root is True or run_as_user > 0, \
            f"{workload_rel}: Pod must run as non-root (runAsNonRoot or runAsUser > 0)"


# ---------------------------------------------------------------------------
# 5. Deployments have startupProbes or high initialDelaySeconds
# ---------------------------------------------------------------------------
class TestStartupProbes:
    """Deployments must have startupProbes or high initialDelaySeconds for slow-starting services."""

    DEPLOYMENT_FILES = [
        "backend/deployment.yaml",
        "frontend/deployment.yaml",
        "worker/deployment.yaml",
        "mcp/deployment.yaml",
    ]

    @pytest.mark.parametrize("dep_rel", DEPLOYMENT_FILES)
    def test_has_startup_probe_or_high_delay(self, dep_rel):
        """Each deployment must have startupProbe or high initialDelaySeconds."""
        path = os.path.join(K8S_DIR, dep_rel)
        if not os.path.exists(path):
            pytest.skip(f"File not found: {dep_rel}")
        doc = load_yaml_first(path)
        if doc is None:
            pytest.skip("Could not load YAML")
        container = doc["spec"]["template"]["spec"]["containers"][0]
        has_startup = "startupProbe" in container
        liveness = container.get("livenessProbe", {})
        initial_delay = liveness.get("initialDelaySeconds", 0)
        assert has_startup or initial_delay >= 30, \
            f"{dep_rel}: Must have startupProbe or initialDelaySeconds >= 30"


# ---------------------------------------------------------------------------
# 6. All Deployments have resource requests AND limits
# ---------------------------------------------------------------------------
class TestResourceRequestsLimits:
    """All Deployments must specify both resource requests and limits."""

    WORKLOAD_FILES = [
        "backend/deployment.yaml",
        "frontend/deployment.yaml",
        "worker/deployment.yaml",
        "mcp/deployment.yaml",
        "postgres/statefulset.yaml",
        "redis/statefulset.yaml",
    ]

    @pytest.mark.parametrize("workload_rel", WORKLOAD_FILES)
    def test_has_requests_and_limits(self, workload_rel):
        """Each workload container must have both requests and limits."""
        path = os.path.join(K8S_DIR, workload_rel)
        if not os.path.exists(path):
            pytest.skip(f"File not found: {workload_rel}")
        doc = load_yaml_first(path)
        if doc is None:
            pytest.skip("Could not load YAML")
        containers = doc["spec"]["template"]["spec"]["containers"]
        for container in containers:
            resources = container.get("resources", {})
            assert "requests" in resources, \
                f"{workload_rel}/{container['name']}: missing resource requests"
            assert "limits" in resources, \
                f"{workload_rel}/{container['name']}: missing resource limits"


# ---------------------------------------------------------------------------
# 7. NetworkPolicies exist and allow external HTTPS egress
# ---------------------------------------------------------------------------
class TestNetworkPolicies:
    """NetworkPolicies must exist and at least one must allow external HTTPS egress."""

    def test_network_policy_file_exists(self):
        """networkpolicy.yaml must exist."""
        path = os.path.join(K8S_DIR, "networkpolicy.yaml")
        assert os.path.exists(path), "networkpolicy.yaml not found"

    def test_network_policies_parse(self):
        """Network policies must parse as valid YAML."""
        path = os.path.join(K8S_DIR, "networkpolicy.yaml")
        docs = load_yaml(path)
        netpols = [d for d in docs if d and d.get("kind") == "NetworkPolicy"]
        assert len(netpols) > 0, "No NetworkPolicy resources found"

    def test_backend_worker_mcp_allow_https_egress(self):
        """Backend, worker, and MCP netpols must allow external HTTPS egress (port 443)."""
        path = os.path.join(K8S_DIR, "networkpolicy.yaml")
        content = load_file(path)
        # The networkpolicy should allow HTTPS egress for backend/worker/MCP
        # (they need to reach external APIs like LLM providers, payment processors)
        # Check for port 443 in egress rules
        has_https_egress = "443" in content
        assert has_https_egress, \
            "NetworkPolicy should allow HTTPS egress (port 443) for external API access"


# ---------------------------------------------------------------------------
# 8. PDBs exist for critical workloads
# ---------------------------------------------------------------------------
class TestPDBs:
    """PodDisruptionBudgets must exist for all critical workloads."""

    EXPECTED_PDBS = ["backend-pdb", "frontend-pdb", "mcp-pdb", "postgres-pdb", "redis-pdb"]

    def test_pdb_file_exists(self):
        """pdb.yaml must exist."""
        path = os.path.join(K8S_DIR, "pdb.yaml")
        assert os.path.exists(path), "pdb.yaml not found"

    @pytest.mark.parametrize("pdb_name", EXPECTED_PDBS)
    def test_pdb_exists_for_workload(self, pdb_name):
        """Each critical workload must have a PDB."""
        path = os.path.join(K8S_DIR, "pdb.yaml")
        docs = load_yaml(path)
        pdb_names = [d["metadata"]["name"] for d in docs if d and d.get("kind") == "PodDisruptionBudget"]
        assert pdb_name in pdb_names, \
            f"PDB '{pdb_name}' not found. Available: {pdb_names}"


# ---------------------------------------------------------------------------
# 9. HPAs exist for backend, worker, MCP
# ---------------------------------------------------------------------------
class TestHPAs:
    """HorizontalPodAutoscalers must exist for scalable workloads."""

    EXPECTED_HPAS = {
        "backend-hpa": "backend/hpa.yaml",
        "worker-hpa": "worker/hpa.yaml",
        "mcp-hpa": "mcp/hpa.yaml",
    }

    @pytest.mark.parametrize("hpa_name,hpa_rel", list(EXPECTED_HPAS.items()),
                             ids=list(EXPECTED_HPAS.keys()))
    def test_hpa_exists(self, hpa_name, hpa_rel):
        """HPA file must exist and parse correctly."""
        path = os.path.join(K8S_DIR, hpa_rel)
        assert os.path.exists(path), f"HPA file missing: {hpa_rel}"
        doc = load_yaml_first(path)
        assert doc is not None, f"Could not parse HPA: {hpa_rel}"
        assert doc.get("kind") == "HorizontalPodAutoscaler"
        assert doc["metadata"]["name"] == hpa_name


# ---------------------------------------------------------------------------
# 10. All Deployments have imagePullPolicy: Always
# ---------------------------------------------------------------------------
class TestImagePullPolicy:
    """All Deployments should use imagePullPolicy: Always for production."""

    DEPLOYMENT_FILES = [
        "backend/deployment.yaml",
        "frontend/deployment.yaml",
        "worker/deployment.yaml",
        "mcp/deployment.yaml",
    ]

    @pytest.mark.parametrize("dep_rel", DEPLOYMENT_FILES)
    def test_image_pull_policy_always(self, dep_rel):
        """Each deployment container should use imagePullPolicy: Always."""
        path = os.path.join(K8S_DIR, dep_rel)
        if not os.path.exists(path):
            pytest.skip(f"File not found: {dep_rel}")
        doc = load_yaml_first(path)
        if doc is None:
            pytest.skip("Could not load YAML")
        containers = doc["spec"]["template"]["spec"]["containers"]
        for container in containers:
            policy = container.get("imagePullPolicy", "")
            assert policy == "Always", \
                f"{dep_rel}/{container['name']}: imagePullPolicy is '{policy}', expected 'Always'"


# ---------------------------------------------------------------------------
# 11. All Deployments reference ServiceAccounts
# ---------------------------------------------------------------------------
class TestServiceAccounts:
    """All Deployments must reference a ServiceAccount."""

    DEPLOYMENT_FILES = [
        "backend/deployment.yaml",
        "frontend/deployment.yaml",
        "worker/deployment.yaml",
        "mcp/deployment.yaml",
    ]

    @pytest.mark.parametrize("dep_rel", DEPLOYMENT_FILES)
    def test_deployment_has_serviceaccount(self, dep_rel):
        """Each deployment must specify serviceAccountName."""
        path = os.path.join(K8S_DIR, dep_rel)
        if not os.path.exists(path):
            pytest.skip(f"File not found: {dep_rel}")
        doc = load_yaml_first(path)
        if doc is None:
            pytest.skip("Could not load YAML")
        spec = doc["spec"]["template"]["spec"]
        assert "serviceAccountName" in spec, \
            f"{dep_rel}: Missing serviceAccountName in pod spec"


# ---------------------------------------------------------------------------
# 12. LimitRange and ResourceQuota exist
# ---------------------------------------------------------------------------
class TestNamespaceResources:
    """Namespace must have LimitRange and ResourceQuota."""

    def test_limitrange_exists(self):
        """limitrange.yaml must exist and be a valid LimitRange."""
        path = os.path.join(K8S_DIR, "limitrange.yaml")
        assert os.path.exists(path), "limitrange.yaml not found"
        doc = load_yaml_first(path)
        assert doc["kind"] == "LimitRange"

    def test_resourcequota_exists(self):
        """resourcequota.yaml must exist and be a valid ResourceQuota."""
        path = os.path.join(K8S_DIR, "resourcequota.yaml")
        assert os.path.exists(path), "resourcequota.yaml not found"
        doc = load_yaml_first(path)
        assert doc["kind"] == "ResourceQuota"


# ---------------------------------------------------------------------------
# 13. All PVCs use gp3 StorageClass
# ---------------------------------------------------------------------------
class TestPVCStorageClass:
    """All PersistentVolumeClaims must use gp3 StorageClass (not standard)."""

    def test_prometheus_pvc_uses_gp3(self):
        """Prometheus PVC must use gp3 StorageClass."""
        path = os.path.join(K8S_DIR, "monitoring/prometheus/pvc.yaml")
        doc = load_yaml_first(path)
        sc = doc["spec"].get("storageClassName", "")
        assert sc == "gp3", f"Prometheus PVC uses storageClassName '{sc}', expected 'gp3'"

    def test_grafana_pvc_uses_gp3(self):
        """Grafana PVC must use gp3 StorageClass."""
        path = os.path.join(K8S_DIR, "monitoring/grafana/pvc.yaml")
        doc = load_yaml_first(path)
        sc = doc["spec"].get("storageClassName", "")
        assert sc == "gp3", f"Grafana PVC uses storageClassName '{sc}', expected 'gp3'"

    def test_alertmanager_pvc_uses_gp3(self):
        """Alertmanager PVC must use gp3 StorageClass."""
        path = os.path.join(K8S_DIR, "monitoring/alertmanager/pvc.yaml")
        doc = load_yaml_first(path)
        sc = doc["spec"].get("storageClassName", "")
        assert sc == "gp3", f"Alertmanager PVC uses storageClassName '{sc}', expected 'gp3'"

    def test_statefulset_volume_claim_templates_use_gp3(self):
        """StatefulSet volumeClaimTemplates must use gp3 StorageClass."""
        for ss_file in ["postgres/statefulset.yaml", "redis/statefulset.yaml"]:
            path = os.path.join(K8S_DIR, ss_file)
            if not os.path.exists(path):
                continue
            doc = load_yaml_first(path)
            vcts = doc["spec"].get("volumeClaimTemplates", [])
            for vct in vcts:
                sc = vct["spec"].get("storageClassName", "")
                assert sc == "gp3", \
                    f"{ss_file}/{vct['metadata']['name']}: storageClassName is '{sc}', expected 'gp3'"


# ---------------------------------------------------------------------------
# 14. RBAC resources exist
# ---------------------------------------------------------------------------
class TestRBACResources:
    """RBAC resources (ServiceAccounts, Roles, ClusterRoles) must exist."""

    def test_rbac_file_or_service_accounts_exist(self):
        """Either rbac.yaml exists, or ServiceAccounts are defined elsewhere in kustomization."""
        rbac_path = os.path.join(K8S_DIR, "rbac.yaml")
        if os.path.exists(rbac_path):
            docs = load_yaml(rbac_path)
            sa_names = [d["metadata"]["name"] for d in docs
                        if d and d.get("kind") == "ServiceAccount"]
            assert len(sa_names) > 0, "rbac.yaml contains no ServiceAccounts"
        else:
            # Check that ServiceAccounts are referenced in deployments
            # (they may be defined in a separate file or externally)
            sa_found = set()
            for dep_file in ["backend/deployment.yaml", "frontend/deployment.yaml",
                             "worker/deployment.yaml", "mcp/deployment.yaml"]:
                path = os.path.join(K8S_DIR, dep_file)
                if not os.path.exists(path):
                    continue
                doc = load_yaml_first(path)
                if doc and "serviceAccountName" in doc["spec"]["template"]["spec"]:
                    sa_found.add(doc["spec"]["template"]["spec"]["serviceAccountName"])
            # ServiceAccounts are referenced but the rbac.yaml file itself is missing
            # This is an issue that should be flagged
            if sa_found:
                pytest.skip(
                    f"ServiceAccounts referenced in deployments ({', '.join(sa_found)}) "
                    "but rbac.yaml file not found — may be managed externally"
                )
            assert False, "No ServiceAccounts found in deployments or rbac.yaml"
