"""
Tests for Kubernetes manifests validation
Tests: YAML validity, resource requirements, security contexts, and best practices
"""
import os
import yaml
import pytest
from pathlib import Path
from typing import Dict, List, Any


# Path to K8s manifests
K8S_DIR = Path(__file__).parent.parent.parent / "infra" / "k8s"


def load_yaml_files() -> Dict[str, Any]:
    """Load all YAML files from the k8s directory."""
    manifests = {}
    if not K8S_DIR.exists():
        pytest.skip(f"K8s directory not found: {K8S_DIR}")

    for yaml_file in K8S_DIR.glob("*.yaml"):
        with open(yaml_file, "r") as f:
            docs = list(yaml.safe_load_all(f))
            manifests[yaml_file.name] = [d for d in docs if d is not None]

    return manifests


class TestYAMLValidity:
    """Test that all manifests are valid YAML."""

    def test_namespace_yaml_valid(self):
        """Test namespace.yaml is valid YAML."""
        yaml_file = K8S_DIR / "namespace.yaml"
        assert yaml_file.exists(), f"File not found: {yaml_file}"

        with open(yaml_file, "r") as f:
            docs = list(yaml.safe_load_all(f))
            assert len(docs) > 0, "No documents found in namespace.yaml"
            for doc in docs:
                assert doc is not None, "Empty document found"

    def test_configmap_yaml_valid(self):
        """Test configmap.yaml is valid YAML."""
        yaml_file = K8S_DIR / "configmap.yaml"
        assert yaml_file.exists(), f"File not found: {yaml_file}"

        with open(yaml_file, "r") as f:
            docs = list(yaml.safe_load_all(f))
            assert len(docs) > 0, "No documents found in configmap.yaml"

    def test_secrets_yaml_valid(self):
        """Test secrets.yaml is valid YAML."""
        yaml_file = K8S_DIR / "secrets.yaml"
        assert yaml_file.exists(), f"File not found: {yaml_file}"

        with open(yaml_file, "r") as f:
            docs = list(yaml.safe_load_all(f))
            assert len(docs) > 0, "No documents found in secrets.yaml"

    def test_backend_deployment_yaml_valid(self):
        """Test backend-deployment.yaml is valid YAML."""
        yaml_file = K8S_DIR / "backend-deployment.yaml"
        assert yaml_file.exists(), f"File not found: {yaml_file}"

        with open(yaml_file, "r") as f:
            docs = list(yaml.safe_load_all(f))
            assert len(docs) > 0, "No documents found in backend-deployment.yaml"

    def test_frontend_deployment_yaml_valid(self):
        """Test frontend-deployment.yaml is valid YAML."""
        yaml_file = K8S_DIR / "frontend-deployment.yaml"
        assert yaml_file.exists(), f"File not found: {yaml_file}"

        with open(yaml_file, "r") as f:
            docs = list(yaml.safe_load_all(f))
            assert len(docs) > 0, "No documents found in frontend-deployment.yaml"

    def test_worker_deployment_yaml_valid(self):
        """Test worker-deployment.yaml is valid YAML."""
        yaml_file = K8S_DIR / "worker-deployment.yaml"
        assert yaml_file.exists(), f"File not found: {yaml_file}"

        with open(yaml_file, "r") as f:
            docs = list(yaml.safe_load_all(f))
            assert len(docs) > 0, "No documents found in worker-deployment.yaml"

    def test_mcp_deployment_yaml_valid(self):
        """Test mcp-deployment.yaml is valid YAML."""
        yaml_file = K8S_DIR / "mcp-deployment.yaml"
        assert yaml_file.exists(), f"File not found: {yaml_file}"

        with open(yaml_file, "r") as f:
            docs = list(yaml.safe_load_all(f))
            assert len(docs) > 0, "No documents found in mcp-deployment.yaml"

    def test_redis_statefulset_yaml_valid(self):
        """Test redis-statefulset.yaml is valid YAML."""
        yaml_file = K8S_DIR / "redis-statefulset.yaml"
        assert yaml_file.exists(), f"File not found: {yaml_file}"

        with open(yaml_file, "r") as f:
            docs = list(yaml.safe_load_all(f))
            assert len(docs) > 0, "No documents found in redis-statefulset.yaml"

    def test_postgres_statefulset_yaml_valid(self):
        """Test postgres-statefulset.yaml is valid YAML."""
        yaml_file = K8S_DIR / "postgres-statefulset.yaml"
        assert yaml_file.exists(), f"File not found: {yaml_file}"

        with open(yaml_file, "r") as f:
            docs = list(yaml.safe_load_all(f))
            assert len(docs) > 0, "No documents found in postgres-statefulset.yaml"

    def test_ingress_yaml_valid(self):
        """Test ingress.yaml is valid YAML."""
        yaml_file = K8S_DIR / "ingress.yaml"
        assert yaml_file.exists(), f"File not found: {yaml_file}"

        with open(yaml_file, "r") as f:
            docs = list(yaml.safe_load_all(f))
            assert len(docs) > 0, "No documents found in ingress.yaml"


class TestNamespaceConfiguration:
    """Test namespace configuration."""

    def test_namespace_exists(self):
        """Test that namespace resource exists."""
        with open(K8S_DIR / "namespace.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        namespace = next((d for d in docs if d.get("kind") == "Namespace"), None)
        assert namespace is not None, "Namespace not found"
        assert namespace["metadata"]["name"] == "parwa"

    def test_resource_quota_exists(self):
        """Test that resource quota exists."""
        with open(K8S_DIR / "namespace.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        quota = next((d for d in docs if d.get("kind") == "ResourceQuota"), None)
        assert quota is not None, "ResourceQuota not found"
        assert "hard" in quota["spec"], "ResourceQuota must have hard limits"

    def test_network_policy_exists(self):
        """Test that network policies exist."""
        with open(K8S_DIR / "namespace.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        network_policies = [d for d in docs if d.get("kind") == "NetworkPolicy"]
        assert len(network_policies) >= 2, "At least 2 NetworkPolicies expected"


class TestDeploymentConfiguration:
    """Test deployment configurations."""

    def test_backend_has_replicas(self):
        """Test backend deployment has replicas configured."""
        with open(K8S_DIR / "backend-deployment.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        deployment = next((d for d in docs if d.get("kind") == "Deployment"), None)
        assert deployment is not None, "Deployment not found"
        assert deployment["spec"]["replicas"] >= 2, "Backend should have at least 2 replicas"

    def test_backend_has_resource_limits(self):
        """Test backend has resource limits."""
        with open(K8S_DIR / "backend-deployment.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        deployment = next((d for d in docs if d.get("kind") == "Deployment"), None)
        containers = deployment["spec"]["template"]["spec"]["containers"]

        for container in containers:
            assert "resources" in container, f"Container {container['name']} missing resources"
            assert "limits" in container["resources"], f"Container {container['name']} missing limits"
            assert "requests" in container["resources"], f"Container {container['name']} missing requests"

    def test_backend_has_health_probes(self):
        """Test backend has liveness and readiness probes."""
        with open(K8S_DIR / "backend-deployment.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        deployment = next((d for d in docs if d.get("kind") == "Deployment"), None)
        containers = deployment["spec"]["template"]["spec"]["containers"]

        for container in containers:
            if container["name"] == "backend":
                assert "livenessProbe" in container, "Backend missing livenessProbe"
                assert "readinessProbe" in container, "Backend missing readinessProbe"

    def test_backend_has_security_context(self):
        """Test backend has security context configured."""
        with open(K8S_DIR / "backend-deployment.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        deployment = next((d for d in docs if d.get("kind") == "Deployment"), None)
        pod_spec = deployment["spec"]["template"]["spec"]

        # Check pod-level security context
        assert "securityContext" in pod_spec, "Pod-level security context missing"
        assert pod_spec["securityContext"].get("runAsNonRoot") == True, "Must run as non-root"

    def test_frontend_has_replicas(self):
        """Test frontend deployment has replicas configured."""
        with open(K8S_DIR / "frontend-deployment.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        deployment = next((d for d in docs if d.get("kind") == "Deployment"), None)
        assert deployment is not None, "Deployment not found"
        assert deployment["spec"]["replicas"] >= 2, "Frontend should have at least 2 replicas"

    def test_worker_has_graceful_shutdown(self):
        """Test worker has termination grace period."""
        with open(K8S_DIR / "worker-deployment.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        deployment = next((d for d in docs if d.get("kind") == "Deployment"), None)
        pod_spec = deployment["spec"]["template"]["spec"]

        assert "terminationGracePeriodSeconds" in pod_spec, "Worker needs terminationGracePeriodSeconds"
        assert pod_spec["terminationGracePeriodSeconds"] >= 60, "Grace period should be >= 60s"

    def test_mcp_deployment_exists(self):
        """Test MCP deployment exists with multiple containers."""
        with open(K8S_DIR / "mcp-deployment.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        deployment = next((d for d in docs if d.get("kind") == "Deployment"), None)
        assert deployment is not None, "MCP Deployment not found"

        containers = deployment["spec"]["template"]["spec"]["containers"]
        assert len(containers) >= 2, "MCP should have multiple server containers"


class TestStatefulSetConfiguration:
    """Test StatefulSet configurations."""

    def test_redis_statefulset_has_pvc(self):
        """Test Redis StatefulSet has persistent volume claim."""
        with open(K8S_DIR / "redis-statefulset.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        statefulset = next((d for d in docs if d.get("kind") == "StatefulSet"), None)
        assert statefulset is not None, "StatefulSet not found"

        assert "volumeClaimTemplates" in statefulset["spec"], "StatefulSet needs volumeClaimTemplates"
        assert len(statefulset["spec"]["volumeClaimTemplates"]) >= 1, "At least one PVC template needed"

    def test_redis_has_headless_service(self):
        """Test Redis has headless service for StatefulSet."""
        with open(K8S_DIR / "redis-statefulset.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        services = [d for d in docs if d.get("kind") == "Service"]
        headless = next((s for s in services if s["spec"].get("clusterIP") == "None"), None)

        assert headless is not None, "Headless service required for StatefulSet"

    def test_postgres_statefulset_has_pvc(self):
        """Test PostgreSQL StatefulSet has persistent volume claim."""
        with open(K8S_DIR / "postgres-statefulset.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        statefulset = next((d for d in docs if d.get("kind") == "StatefulSet"), None)
        assert statefulset is not None, "StatefulSet not found"

        assert "volumeClaimTemplates" in statefulset["spec"], "StatefulSet needs volumeClaimTemplates"

    def test_postgres_has_backup_sidecar(self):
        """Test PostgreSQL has backup sidecar container."""
        with open(K8S_DIR / "postgres-statefulset.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        statefulset = next((d for d in docs if d.get("kind") == "StatefulSet"), None)
        containers = statefulset["spec"]["template"]["spec"]["containers"]

        backup_container = next((c for c in containers if "backup" in c["name"].lower()), None)
        assert backup_container is not None, "Backup sidecar container expected"


class TestIngressConfiguration:
    """Test Ingress configuration."""

    def test_ingress_has_tls(self):
        """Test Ingress has TLS configured."""
        with open(K8S_DIR / "ingress.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        ingress = next((d for d in docs if d.get("kind") == "Ingress"), None)
        assert ingress is not None, "Ingress not found"

        assert "tls" in ingress["spec"], "Ingress must have TLS configured"
        assert len(ingress["spec"]["tls"]) >= 1, "At least one TLS entry required"

    def test_ingress_has_multiple_hosts(self):
        """Test Ingress has multiple hosts (app and api)."""
        with open(K8S_DIR / "ingress.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        ingress = next((d for d in docs if d.get("kind") == "Ingress"), None)
        rules = ingress["spec"]["rules"]

        hosts = [r["host"] for r in rules if "host" in r]
        assert len(hosts) >= 2, "Should have at least 2 hosts (app and api)"

    def test_ingress_has_security_annotations(self):
        """Test Ingress has security annotations."""
        with open(K8S_DIR / "ingress.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        ingress = next((d for d in docs if d.get("kind") == "Ingress"), None)
        annotations = ingress["metadata"].get("annotations", {})

        assert "nginx.ingress.kubernetes.io/ssl-redirect" in annotations, "SSL redirect annotation needed"


class TestConfigMapAndSecrets:
    """Test ConfigMap and Secrets configuration."""

    def test_configmap_has_required_keys(self):
        """Test ConfigMap has required application keys."""
        with open(K8S_DIR / "configmap.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        configmap = next((d for d in docs if d.get("kind") == "ConfigMap"), None)
        assert configmap is not None, "ConfigMap not found"

        data = configmap.get("data", {})
        required_keys = ["APP_ENV", "BACKEND_PORT"]
        for key in required_keys:
            assert key in data, f"ConfigMap missing required key: {key}"

    def test_secrets_are_templates(self):
        """Test secrets are templates without real values."""
        with open(K8S_DIR / "secrets.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        secret = next((d for d in docs if d.get("kind") == "Secret"), None)
        assert secret is not None, "Secret not found"

        # Check that secrets have placeholder values
        string_data = secret.get("stringData", {})
        # Non-sensitive keys that can have actual values
        non_sensitive_keys = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "REDIS_URL"]
        sensitive_keys = ["PASSWORD", "SECRET", "KEY", "TOKEN"]

        for key, value in string_data.items():
            # Skip non-sensitive configuration values
            if key in non_sensitive_keys:
                continue
            # Check sensitive keys have placeholder values
            if any(s in key.upper() for s in sensitive_keys):
                assert value == "REPLACE_ME" or value.startswith("$") or "REPLACE" in value, \
                    f"Secret {key} should have placeholder value"


class TestHPAAndPDB:
    """Test Horizontal Pod Autoscaler and Pod Disruption Budget."""

    def test_backend_has_hpa(self):
        """Test backend has HPA configured."""
        with open(K8S_DIR / "backend-deployment.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        hpa = next((d for d in docs if d.get("kind") == "HorizontalPodAutoscaler"), None)
        assert hpa is not None, "HPA not found for backend"

        assert hpa["spec"]["minReplicas"] >= 2, "Min replicas should be >= 2"
        assert hpa["spec"]["maxReplicas"] > hpa["spec"]["minReplicas"], "Max should be > min replicas"

    def test_backend_has_pdb(self):
        """Test backend has PDB configured."""
        with open(K8S_DIR / "backend-deployment.yaml", "r") as f:
            docs = list(yaml.safe_load_all(f))

        pdb = next((d for d in docs if d.get("kind") == "PodDisruptionBudget"), None)
        assert pdb is not None, "PDB not found for backend"


class TestBestPractices:
    """Test Kubernetes best practices."""

    def test_all_deployments_have_labels(self):
        """Test all deployments have proper labels."""
        deployment_files = [
            "backend-deployment.yaml",
            "frontend-deployment.yaml",
            "worker-deployment.yaml",
            "mcp-deployment.yaml",
        ]

        for filename in deployment_files:
            with open(K8S_DIR / filename, "r") as f:
                docs = list(yaml.safe_load_all(f))

            deployment = next((d for d in docs if d.get("kind") == "Deployment"), None)
            if deployment:
                labels = deployment["metadata"].get("labels", {})
                assert "app.kubernetes.io/name" in labels, f"{filename} missing app.kubernetes.io/name label"

    def test_all_containers_have_resource_limits(self):
        """Test all containers have resource limits."""
        deployment_files = [
            "backend-deployment.yaml",
            "frontend-deployment.yaml",
            "worker-deployment.yaml",
            "mcp-deployment.yaml",
        ]

        for filename in deployment_files:
            with open(K8S_DIR / filename, "r") as f:
                docs = list(yaml.safe_load_all(f))

            deployment = next((d for d in docs if d.get("kind") == "Deployment"), None)
            if deployment:
                containers = deployment["spec"]["template"]["spec"]["containers"]
                for container in containers:
                    assert "resources" in container, \
                        f"{filename} container {container['name']} missing resources"
                    assert "limits" in container["resources"], \
                        f"{filename} container {container['name']} missing limits"

    def test_all_containers_run_as_non_root(self):
        """Test all containers run as non-root user."""
        deployment_files = [
            "backend-deployment.yaml",
            "frontend-deployment.yaml",
            "worker-deployment.yaml",
            "mcp-deployment.yaml",
        ]

        for filename in deployment_files:
            with open(K8S_DIR / filename, "r") as f:
                docs = list(yaml.safe_load_all(f))

            deployment = next((d for d in docs if d.get("kind") == "Deployment"), None)
            if deployment:
                pod_spec = deployment["spec"]["template"]["spec"]
                security_context = pod_spec.get("securityContext", {})
                assert security_context.get("runAsNonRoot") == True, \
                    f"{filename} should run as non-root"

    def test_no_privilege_escalation(self):
        """Test containers don't allow privilege escalation."""
        deployment_files = [
            "backend-deployment.yaml",
            "frontend-deployment.yaml",
            "worker-deployment.yaml",
            "mcp-deployment.yaml",
        ]

        for filename in deployment_files:
            with open(K8S_DIR / filename, "r") as f:
                docs = list(yaml.safe_load_all(f))

            deployment = next((d for d in docs if d.get("kind") == "Deployment"), None)
            if deployment:
                containers = deployment["spec"]["template"]["spec"]["containers"]
                for container in containers:
                    container_security = container.get("securityContext", {})
                    assert container_security.get("allowPrivilegeEscalation") == False, \
                        f"{filename} container {container['name']} allows privilege escalation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
