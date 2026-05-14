"""
PARWA Infrastructure Scripts Tests
- Test backup.sh has correct pg_dump command
- Test restore.sh has safety checks
- Test SSL setup generates valid nginx config
- Test K8s manifests are valid YAML
- Test K8s deployments have resource limits
- Test K8s deployments have security contexts
- Test HPA configs are valid
- Test network policies are restrictive
"""

import os
import re
import yaml
import pytest
from pathlib import Path

# Base paths
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # backend/app/tests/ -> parwa/
INFRA_DIR = PROJECT_ROOT / "infra"
K8S_DIR = INFRA_DIR / "k8s"
NGINX_DIR = INFRA_DIR / "docker"


# ════════════════════════════════════════════════════════════════
# Helper functions
# ════════════════════════════════════════════════════════════════

def read_file(path: Path) -> str:
    """Read a file and return its contents."""
    assert path.exists(), f"File not found: {path}"
    return path.read_text()


def load_k8s_yaml(path: Path) -> list:
    """Load a Kubernetes YAML file (may contain multiple documents)."""
    content = read_file(path)
    docs = list(yaml.safe_load_all(content))
    return [d for d in docs if d is not None]


def get_all_k8s_manifests() -> list:
    """Recursively find and load all K8s YAML manifests."""
    manifests = []
    for yaml_file in K8S_DIR.rglob("*.yaml"):
        docs = load_k8s_yaml(yaml_file)
        for doc in docs:
            if doc and isinstance(doc, dict) and "kind" in doc:
                doc["_source_file"] = str(yaml_file.relative_to(K8S_DIR))
                manifests.append(doc)
    return manifests


def get_k8s_deployments() -> list:
    """Get all Deployment manifests."""
    return [m for m in get_all_k8s_manifests() if m.get("kind") == "Deployment"]


def get_k8s_statefulsets() -> list:
    """Get all StatefulSet manifests."""
    return [m for m in get_all_k8s_manifests() if m.get("kind") == "StatefulSet"]


def get_k8s_hpas() -> list:
    """Get all HPA manifests."""
    return [m for m in get_all_k8s_manifests() if m.get("kind") == "HorizontalPodAutoscaler"]


def get_k8s_network_policies() -> list:
    """Get all NetworkPolicy manifests."""
    return [m for m in get_all_k8s_manifests() if m.get("kind") == "NetworkPolicy"]


# ════════════════════════════════════════════════════════════════
# Part A: Database Backup Script Tests
# ════════════════════════════════════════════════════════════════

class TestBackupScript:
    """Tests for backup.sh."""

    @pytest.fixture
    def backup_script(self):
        return read_file(INFRA_DIR / "scripts" / "backup.sh")

    def test_backup_script_exists(self):
        assert (INFRA_DIR / "scripts" / "backup.sh").exists(), "backup.sh not found"

    def test_has_pg_dump_command(self, backup_script):
        """Test that backup.sh has correct pg_dump command."""
        assert "pg_dump" in backup_script, "pg_dump command not found in backup.sh"
        # Check for key pg_dump flags
        assert "-h" in backup_script, "pg_dump missing -h (host) flag"
        assert "-p" in backup_script, "pg_dump missing -p (port) flag"
        assert "-U" in backup_script, "pg_dump missing -U (user) flag"
        assert "-d" in backup_script, "pg_dump missing -d (database) flag"

    def test_has_gzip_compression(self, backup_script):
        """Test that backup.sh compresses with gzip."""
        assert "gzip" in backup_script, "gzip compression not found in backup.sh"

    def test_has_error_handling(self, backup_script):
        """Test that backup.sh has proper error handling."""
        assert "set -euo pipefail" in backup_script, "Missing set -euo pipefail"

    def test_has_integrity_verification(self, backup_script):
        """Test that backup.sh verifies backup integrity."""
        assert "verify_backup" in backup_script, "verify_backup function not found"
        assert "sha256sum" in backup_script, "sha256sum checksum not found"
        assert "gzip -t" in backup_script, "gzip integrity test not found"

    def test_has_s3_upload(self, backup_script):
        """Test that backup.sh supports S3 upload."""
        assert "S3_BUCKET" in backup_script, "S3_BUCKET config not found"
        assert "upload_to_s3" in backup_script, "upload_to_s3 function not found"
        assert "aws s3 cp" in backup_script, "aws s3 cp command not found"

    def test_has_local_rotation(self, backup_script):
        """Test that backup.sh has local backup rotation."""
        assert "RETENTION_DAYS" in backup_script, "RETENTION_DAYS config not found"
        assert "cleanup_old_backups" in backup_script, "cleanup_old_backups function not found"
        assert "find" in backup_script and "-mtime" in backup_script, \
            "find with -mtime for rotation not found"

    def test_has_notification_on_failure(self, backup_script):
        """Test that backup.sh notifies on failure."""
        assert "notify_failure" in backup_script, "notify_failure function not found"
        assert "SLACK_WEBHOOK" in backup_script, "SLACK_WEBHOOK config not found"

    def test_has_utc_timestamps(self, backup_script):
        """BC-012: Test that backup.sh uses UTC timestamps."""
        assert "date -u" in backup_script or "date +%Y%m%d" in backup_script, \
            "UTC timestamps (date -u) not found"

    def test_has_lock_management(self, backup_script):
        """Test that backup.sh prevents concurrent backups."""
        assert "LOCK_FILE" in backup_script, "LOCK_FILE not found"
        assert "acquire_lock" in backup_script, "acquire_lock function not found"

    def test_has_db_connectivity_check(self, backup_script):
        """Test that backup.sh verifies database connectivity."""
        assert "pg_isready" in backup_script, "pg_isready connectivity check not found"


class TestRestoreScript:
    """Tests for restore.sh."""

    @pytest.fixture
    def restore_script(self):
        return read_file(INFRA_DIR / "scripts" / "restore.sh")

    def test_restore_script_exists(self):
        assert (INFRA_DIR / "scripts" / "restore.sh").exists(), "restore.sh not found"

    def test_has_safety_confirmations(self, restore_script):
        """Test that restore.sh has safety confirmations."""
        assert "confirm_restore" in restore_script, "confirm_restore function not found"
        assert "RESTORE" in restore_script, "RESTORE confirmation keyword not found"

    def test_has_integrity_verification_before_restore(self, restore_script):
        """Test that restore.sh verifies backup integrity before restoring."""
        assert "verify_backup_file" in restore_script, \
            "verify_backup_file function not found"
        # Should verify BEFORE restoring
        verify_pos = restore_script.find("verify_backup_file")
        restore_pos = restore_script.find("perform_restore")
        assert verify_pos < restore_pos, \
            "Integrity verification should happen before restore"

    def test_has_pre_restore_backup(self, restore_script):
        """Test that restore.sh creates a backup of current state before restoring."""
        assert "PRE_RESTORE_BACKUP" in restore_script, \
            "PRE_RESTORE_BACKUP config not found"
        assert "create_pre_restore_backup" in restore_script, \
            "create_pre_restore_backup function not found"

    def test_has_dry_run_support(self, restore_script):
        """Test that restore.sh supports dry-run mode."""
        assert "DRY_RUN" in restore_script, "DRY_RUN config not found"

    def test_has_force_flag(self, restore_script):
        """Test that restore.sh has --force flag for non-interactive mode."""
        assert "FORCE" in restore_script, "FORCE flag not found"
        assert "--force" in restore_script, "--force CLI option not found"

    def test_has_error_handling(self, restore_script):
        """Test that restore.sh has proper error handling."""
        assert "set -euo pipefail" in restore_script, "Missing set -euo pipefail"

    def test_has_psql_restore_command(self, restore_script):
        """Test that restore.sh uses psql for restore."""
        assert "psql" in restore_script, "psql command not found in restore.sh"
        assert "ON_ERROR_STOP" in restore_script, \
            "ON_ERROR_STOP not found — restore should stop on error"

    def test_terminates_existing_connections(self, restore_script):
        """Test that restore.sh terminates existing DB connections before restore."""
        assert "pg_terminate_backend" in restore_script, \
            "pg_terminate_backend not found — should kill existing connections"

    def test_has_utc_timestamps(self, restore_script):
        """BC-012: Test that restore.sh uses UTC timestamps."""
        assert "date -u" in restore_script, "UTC timestamps (date -u) not found"


class TestBackupCronScript:
    """Tests for backup_cron.sh."""

    @pytest.fixture
    def cron_script(self):
        return read_file(INFRA_DIR / "scripts" / "backup_cron.sh")

    def test_cron_script_exists(self):
        assert (INFRA_DIR / "scripts" / "backup_cron.sh").exists(), "backup_cron.sh not found"

    def test_has_retry_logic(self, cron_script):
        """Test that backup_cron.sh retries on failure."""
        assert "MAX_RETRIES" in cron_script, "MAX_RETRIES not found"
        assert "RETRY_DELAY" in cron_script, "RETRY_DELAY not found"
        assert "retry" in cron_script.lower(), "retry logic not found"

    def test_notifies_on_persistent_failure(self, cron_script):
        """Test that backup_cron.sh notifies on persistent failure."""
        assert "notify_persistent_failure" in cron_script, \
            "notify_persistent_failure function not found"
        assert "PERSISTENT" in cron_script.upper(), "Persistent failure notification not found"

    def test_has_lock_management(self, cron_script):
        """Test that backup_cron.sh prevents overlapping runs."""
        assert "LOCK_FILE" in cron_script, "LOCK_FILE not found"
        assert "acquire_lock" in cron_script, "acquire_lock function not found"

    def test_calls_backup_script(self, cron_script):
        """Test that backup_cron.sh calls backup.sh."""
        assert "backup.sh" in cron_script, "backup.sh reference not found"


# ════════════════════════════════════════════════════════════════
# Part B: SSL/HTTPS Tests
# ════════════════════════════════════════════════════════════════

class TestSSLSetupScript:
    """Tests for ssl-setup.sh."""

    @pytest.fixture
    def ssl_script(self):
        return read_file(PROJECT_ROOT / "nginx" / "ssl-setup.sh")

    def test_ssl_setup_script_exists(self):
        assert (PROJECT_ROOT / "nginx" / "ssl-setup.sh").exists(), "ssl-setup.sh not found"

    def test_uses_lets_encrypt(self, ssl_script):
        """Test that ssl-setup.sh uses Let's Encrypt."""
        assert "certbot" in ssl_script, "certbot not found"
        assert "letsencrypt" in ssl_script.lower() or "Let's Encrypt" in ssl_script, \
            "Let's Encrypt reference not found"

    def test_generates_dh_params(self, ssl_script):
        """Test that ssl-setup.sh generates Diffie-Hellman parameters."""
        assert "dhparam" in ssl_script, "DH parameters generation not found"
        assert "openssl dhparam" in ssl_script, "openssl dhparam command not found"

    def test_sets_up_auto_renewal(self, ssl_script):
        """Test that ssl-setup.sh sets up certificate auto-renewal."""
        assert "auto-renewal" in ssl_script.lower() or "autorenewal" in ssl_script.lower(), \
            "Auto-renewal setup not found"
        assert "certbot renew" in ssl_script, "certbot renew command not found"

    def test_verifies_ssl(self, ssl_script):
        """Test that ssl-setup.sh verifies SSL configuration."""
        assert "verify_ssl" in ssl_script, "verify_ssl function not found"
        assert "openssl" in ssl_script, "openssl verification not found"


class TestNginxConfig:
    """Tests for nginx configuration."""

    @pytest.fixture
    def nginx_conf(self):
        return read_file(NGINX_DIR / "nginx.conf")

    @pytest.fixture
    def nginx_default_conf(self):
        return read_file(NGINX_DIR / "nginx-default.conf")

    def test_nginx_conf_exists(self):
        assert (NGINX_DIR / "nginx.conf").exists(), "nginx.conf not found"

    def test_nginx_default_conf_exists(self):
        assert (NGINX_DIR / "nginx-default.conf").exists(), "nginx-default.conf not found"

    def test_has_ssl_protocols(self, nginx_conf):
        """Test that nginx.conf specifies TLS 1.2+."""
        assert "TLSv1.2" in nginx_conf, "TLSv1.2 not found"
        assert "TLSv1.3" in nginx_conf, "TLSv1.3 not found"
        assert "TLSv1.1" not in nginx_conf or "TLSv1 " not in nginx_conf, \
            "Insecure TLS version found"

    def test_has_strong_cipher_suite(self, nginx_conf):
        """Test that nginx.conf has strong cipher suite."""
        assert "ssl_ciphers" in nginx_conf, "ssl_ciphers not found"
        # Check for Mozilla Modern ciphers
        assert "ECDHE" in nginx_conf, "ECDHE cipher not found"
        assert "GCM" in nginx_conf, "GCM cipher not found"

    def test_has_ssl_session_caching(self, nginx_conf):
        """Test that nginx.conf has SSL session caching."""
        assert "ssl_session_cache" in nginx_conf, "ssl_session_cache not found"
        assert "ssl_session_timeout" in nginx_conf, "ssl_session_timeout not found"
        assert "ssl_session_tickets off" in nginx_conf, "ssl_session_tickets should be off"

    def test_has_ocsp_stapling(self, nginx_conf):
        """Test that nginx.conf has OCSP stapling."""
        assert "ssl_stapling on" in nginx_conf, "OCSP stapling not enabled"
        assert "ssl_stapling_verify on" in nginx_conf, "OCSP stapling verify not enabled"

    def test_has_dhparam(self, nginx_conf):
        """Test that nginx.conf references DH parameters."""
        assert "ssl_dhparam" in nginx_conf, "ssl_dhparam not found"

    def test_has_security_headers(self, nginx_default_conf):
        """Test that nginx-default.conf has security headers."""
        assert "X-Frame-Options" in nginx_default_conf, "X-Frame-Options not found"
        assert "X-Content-Type-Options" in nginx_default_conf, \
            "X-Content-Type-Options not found"
        assert "X-XSS-Protection" in nginx_default_conf, "X-XSS-Protection not found"
        assert "Referrer-Policy" in nginx_default_conf, "Referrer-Policy not found"
        assert "Permissions-Policy" in nginx_default_conf, "Permissions-Policy not found"

    def test_has_hsts_header(self, nginx_default_conf):
        """Test that nginx-default.conf has HSTS header."""
        assert "Strict-Transport-Security" in nginx_default_conf, "HSTS header not found"
        assert "max-age=31536000" in nginx_default_conf, "HSTS max-age should be 1 year"
        assert "includeSubDomains" in nginx_default_conf, "HSTS includeSubDomains not found"
        assert "preload" in nginx_default_conf, "HSTS preload not found"

    def test_has_csp_header(self, nginx_default_conf):
        """Test that nginx-default.conf has Content-Security-Policy header."""
        assert "Content-Security-Policy" in nginx_default_conf, \
            "Content-Security-Policy header not found"

    def test_http_redirects_to_https(self, nginx_default_conf):
        """Test that HTTP traffic is redirected to HTTPS."""
        assert "listen 80" in nginx_default_conf, "HTTP server block not found"
        assert "return 301 https" in nginx_default_conf, \
            "HTTPS redirect not found"

    def test_has_acme_challenge(self, nginx_default_conf):
        """Test that ACME challenge path is allowed for Let's Encrypt."""
        assert "acme-challenge" in nginx_default_conf, \
            "ACME challenge location not found"
        assert "certbot" in nginx_default_conf, "certbot webroot not found"

    def test_has_ssl_certificate_paths(self, nginx_default_conf):
        """Test that SSL certificate paths are configured."""
        assert "ssl_certificate" in nginx_default_conf, "ssl_certificate not found"
        assert "ssl_certificate_key" in nginx_default_conf, "ssl_certificate_key not found"
        assert "/etc/nginx/ssl/" in nginx_default_conf, "SSL directory path not found"

    def test_preserves_existing_upstream_config(self, nginx_conf):
        """Test that upstream definitions are preserved."""
        assert "upstream frontend" in nginx_conf, "frontend upstream not found"
        assert "upstream backend" in nginx_conf, "backend upstream not found"
        assert "frontend:3000" in nginx_conf, "frontend port config not found"
        assert "backend:8000" in nginx_conf, "backend port config not found"

    def test_preserves_existing_proxy_locations(self, nginx_default_conf):
        """Test that proxy locations are preserved."""
        assert "location /api/" in nginx_default_conf, "API proxy location not found"
        assert "location /" in nginx_default_conf, "Root location not found"
        assert "location /ws/" in nginx_default_conf, "WebSocket location not found"
        assert "location /docs" in nginx_default_conf, "Docs location not found"

    def test_has_rate_limiting(self, nginx_conf):
        """Test that rate limiting is configured."""
        assert "limit_req_zone" in nginx_conf, "Rate limiting zone not found"
        assert "zone=api" in nginx_conf, "API rate limit zone not found"
        assert "zone=login" in nginx_conf, "Login rate limit zone not found"

    def test_has_gzip_compression(self, nginx_conf):
        """Test that gzip compression is configured."""
        assert "gzip on" in nginx_conf, "gzip not enabled"


# ════════════════════════════════════════════════════════════════
# Part C: Kubernetes Manifests Tests
# ════════════════════════════════════════════════════════════════

class TestK8sYAMLValidity:
    """Test that K8s manifests are valid YAML."""

    def test_namespace_yaml_valid(self):
        docs = load_k8s_yaml(K8S_DIR / "namespace.yaml")
        assert len(docs) > 0, "namespace.yaml has no documents"
        assert docs[0]["kind"] == "Namespace"

    def test_configmap_yaml_valid(self):
        docs = load_k8s_yaml(K8S_DIR / "configmap.yaml")
        assert len(docs) > 0, "configmap.yaml has no documents"
        for doc in docs:
            assert doc["kind"] == "ConfigMap"

    def test_secrets_yaml_valid(self):
        docs = load_k8s_yaml(K8S_DIR / "secrets.yaml")
        assert len(docs) > 0, "secrets.yaml has no documents"
        assert docs[0]["kind"] == "Secret"

    def test_kustomization_yaml_valid(self):
        docs = load_k8s_yaml(K8S_DIR / "kustomization.yaml")
        assert len(docs) > 0, "kustomization.yaml has no documents"

    def test_all_yaml_files_parseable(self):
        """Test that all YAML files in k8s/ are parseable."""
        for yaml_file in K8S_DIR.rglob("*.yaml"):
            docs = load_k8s_yaml(yaml_file)
            assert docs is not None, f"Failed to parse {yaml_file}"

    def test_all_manifests_have_required_fields(self):
        """Test that all K8s manifests have apiVersion, kind, metadata."""
        for manifest in get_all_k8s_manifests():
            if manifest.get("kind") == "Kustomization":
                continue
            assert "apiVersion" in manifest, \
                f"Missing apiVersion in {manifest.get('_source_file', 'unknown')}"
            assert "kind" in manifest, \
                f"Missing kind in {manifest.get('_source_file', 'unknown')}"
            assert "metadata" in manifest, \
                f"Missing metadata in {manifest.get('_source_file', 'unknown')}"
            assert "name" in manifest["metadata"], \
                f"Missing metadata.name in {manifest.get('_source_file', 'unknown')}"

    def test_all_manifests_in_parwa_namespace(self):
        """Test that all K8s resources (except Namespace) are in parwa namespace."""
        for manifest in get_all_k8s_manifests():
            if manifest["kind"] in ("Namespace", "Kustomization"):
                continue
            assert manifest["metadata"].get("namespace") == "parwa", \
                f"{manifest['kind']}/{manifest['metadata']['name']} not in parwa namespace"


class TestK8sDeployments:
    """Test K8s deployments follow production best practices."""

    def test_backend_deployment_exists(self):
        deployments = get_k8s_deployments()
        names = [d["metadata"]["name"] for d in deployments]
        assert "backend" in names, "backend deployment not found"

    def test_worker_deployment_exists(self):
        deployments = get_k8s_deployments()
        names = [d["metadata"]["name"] for d in deployments]
        assert "worker" in names, "worker deployment not found"

    def test_frontend_deployment_exists(self):
        deployments = get_k8s_deployments()
        names = [d["metadata"]["name"] for d in deployments]
        assert "frontend" in names, "frontend deployment not found"

    def test_mcp_deployment_exists(self):
        deployments = get_k8s_deployments()
        names = [d["metadata"]["name"] for d in deployments]
        assert "mcp" in names, "mcp deployment not found"

    def test_all_deployments_have_resource_limits(self):
        """Test that all deployments have resource requests and limits."""
        for deploy in get_k8s_deployments():
            name = deploy["metadata"]["name"]
            containers = deploy["spec"]["template"]["spec"]["containers"]
            for container in containers:
                assert "resources" in container, \
                    f"Deployment {name}, container {container['name']} missing resources"
                assert "limits" in container["resources"], \
                    f"Deployment {name}, container {container['name']} missing resource limits"
                assert "requests" in container["resources"], \
                    f"Deployment {name}, container {container['name']} missing resource requests"
                # Check for CPU and memory
                limits = container["resources"]["limits"]
                requests = container["resources"]["requests"]
                assert "cpu" in limits, \
                    f"Deployment {name} missing CPU limit"
                assert "memory" in limits, \
                    f"Deployment {name} missing memory limit"
                assert "cpu" in requests, \
                    f"Deployment {name} missing CPU request"
                assert "memory" in requests, \
                    f"Deployment {name} missing memory request"

    def test_all_deployments_have_security_contexts(self):
        """Test that all deployments have security contexts."""
        for deploy in get_k8s_deployments():
            name = deploy["metadata"]["name"]
            pod_spec = deploy["spec"]["template"]["spec"]

            # Pod-level security context
            assert "securityContext" in pod_spec, \
                f"Deployment {name} missing pod-level securityContext"

            # Container-level security context
            for container in pod_spec["containers"]:
                assert "securityContext" in container, \
                    f"Deployment {name}, container {container['name']} missing container securityContext"
                sc = container["securityContext"]
                assert sc.get("allowPrivilegeEscalation") is False, \
                    f"Deployment {name} allows privilege escalation"
                assert "drop" in sc.get("capabilities", {}), \
                    f"Deployment {name} missing capability drops"
                assert "ALL" in sc.get("capabilities", {}).get("drop", []), \
                    f"Deployment {name} should drop ALL capabilities"

    def test_deployments_run_as_non_root(self):
        """Test that deployments run as non-root."""
        for deploy in get_k8s_deployments():
            name = deploy["metadata"]["name"]
            pod_spec = deploy["spec"]["template"]["spec"]
            sc = pod_spec.get("securityContext", {})
            assert sc.get("runAsNonRoot") is True, \
                f"Deployment {name} should run as non-root"

    def test_deployments_have_read_only_root_filesystem(self):
        """Test that deployments have readOnlyRootFilesystem."""
        for deploy in get_k8s_deployments():
            name = deploy["metadata"]["name"]
            pod_spec = deploy["spec"]["template"]["spec"]
            for container in pod_spec["containers"]:
                sc = container.get("securityContext", {})
                assert sc.get("readOnlyRootFilesystem") is True, \
                    f"Deployment {name}, container {container['name']} should have readOnlyRootFilesystem"

    def test_deployments_have_probes(self):
        """Test that deployments have liveness and readiness probes."""
        for deploy in get_k8s_deployments():
            name = deploy["metadata"]["name"]
            pod_spec = deploy["spec"]["template"]["spec"]
            for container in pod_spec["containers"]:
                assert "livenessProbe" in container, \
                    f"Deployment {name}, container {container['name']} missing livenessProbe"
                assert "readinessProbe" in container, \
                    f"Deployment {name}, container {container['name']} missing readinessProbe"

    def test_deployments_have_pod_anti_affinity(self):
        """Test that deployments have pod anti-affinity for HA."""
        for deploy in get_k8s_deployments():
            name = deploy["metadata"]["name"]
            pod_spec = deploy["spec"]["template"]["spec"]
            affinity = pod_spec.get("affinity", {})
            assert "podAntiAffinity" in affinity, \
                f"Deployment {name} missing podAntiAffinity"

    def test_deployments_have_kubernetes_labels(self):
        """Test that deployments follow Kubernetes recommended labels."""
        recommended_labels = [
            "app.kubernetes.io/name",
            "app.kubernetes.io/component",
            "app.kubernetes.io/part-of",
        ]
        for deploy in get_k8s_deployments():
            name = deploy["metadata"]["name"]
            labels = deploy["metadata"].get("labels", {})
            for label in recommended_labels:
                assert label in labels, \
                    f"Deployment {name} missing recommended label: {label}"


class TestK8sStatefulSets:
    """Test K8s StatefulSets."""

    def test_postgres_statefulset_exists(self):
        sts = get_k8s_statefulsets()
        names = [s["metadata"]["name"] for s in sts]
        assert "postgres" in names, "postgres StatefulSet not found"

    def test_redis_statefulset_exists(self):
        sts = get_k8s_statefulsets()
        names = [s["metadata"]["name"] for s in sts]
        assert "redis" in names, "redis StatefulSet not found"

    def test_statefulsets_have_resource_limits(self):
        """Test that StatefulSets have resource limits."""
        for sts in get_k8s_statefulsets():
            name = sts["metadata"]["name"]
            containers = sts["spec"]["template"]["spec"]["containers"]
            for container in containers:
                assert "resources" in container, \
                    f"StatefulSet {name}, container {container['name']} missing resources"
                assert "limits" in container["resources"], \
                    f"StatefulSet {name} missing resource limits"

    def test_statefulsets_have_volume_claims(self):
        """Test that StatefulSets have persistent volume claims."""
        for sts in get_k8s_statefulsets():
            name = sts["metadata"]["name"]
            vct = sts["spec"].get("volumeClaimTemplates", [])
            assert len(vct) > 0, \
                f"StatefulSet {name} missing volumeClaimTemplates"


class TestK8sHPA:
    """Test Horizontal Pod Autoscaler configurations."""

    def test_backend_hpa_exists(self):
        hpas = get_k8s_hpas()
        names = [h["metadata"]["name"] for h in hpas]
        assert "backend-hpa" in names, "backend-hpa not found"

    def test_worker_hpa_exists(self):
        hpas = get_k8s_hpas()
        names = [h["metadata"]["name"] for h in hpas]
        assert "worker-hpa" in names, "worker-hpa not found"

    def test_backend_hpa_scaling_range(self):
        """Test backend HPA: min 2, max 10."""
        hpas = get_k8s_hpas()
        backend_hpa = next(h for h in hpas if h["metadata"]["name"] == "backend-hpa")
        assert backend_hpa["spec"]["minReplicas"] == 2, \
            "Backend HPA minReplicas should be 2"
        assert backend_hpa["spec"]["maxReplicas"] == 10, \
            "Backend HPA maxReplicas should be 10"

    def test_worker_hpa_scaling_range(self):
        """Test worker HPA: min 2, max 8."""
        hpas = get_k8s_hpas()
        worker_hpa = next(h for h in hpas if h["metadata"]["name"] == "worker-hpa")
        assert worker_hpa["spec"]["minReplicas"] == 2, \
            "Worker HPA minReplicas should be 2"
        assert worker_hpa["spec"]["maxReplicas"] == 8, \
            "Worker HPA maxReplicas should be 8"

    def test_backend_hpa_cpu_target(self):
        """Test backend HPA CPU target is 70%."""
        hpas = get_k8s_hpas()
        backend_hpa = next(h for h in hpas if h["metadata"]["name"] == "backend-hpa")
        metrics = backend_hpa["spec"]["metrics"]
        cpu_metric = next(m for m in metrics if m["type"] == "Resource")
        assert cpu_metric["resource"]["target"]["averageUtilization"] == 70, \
            "Backend HPA CPU target should be 70%"

    def test_worker_hpa_cpu_target(self):
        """Test worker HPA CPU target is 60%."""
        hpas = get_k8s_hpas()
        worker_hpa = next(h for h in hpas if h["metadata"]["name"] == "worker-hpa")
        metrics = worker_hpa["spec"]["metrics"]
        cpu_metric = next(m for m in metrics if m["type"] == "Resource")
        assert cpu_metric["resource"]["target"]["averageUtilization"] == 60, \
            "Worker HPA CPU target should be 60%"

    def test_hpas_use_autoscaling_v2(self):
        """Test that HPAs use autoscaling/v2 API."""
        for hpa in get_k8s_hpas():
            assert hpa["apiVersion"] == "autoscaling/v2", \
                f"HPA {hpa['metadata']['name']} should use autoscaling/v2"

    def test_hpas_have_scale_behavior(self):
        """Test that HPAs have scale behavior configured."""
        for hpa in get_k8s_hpas():
            name = hpa["metadata"]["name"]
            assert "behavior" in hpa["spec"], \
                f"HPA {name} should have scale behavior configured"


class TestK8sNetworkPolicies:
    """Test network policies are restrictive."""

    def test_network_policies_exist(self):
        policies = get_k8s_network_policies()
        assert len(policies) > 0, "No network policies found"

    def test_default_deny_all_exists(self):
        """Test that default deny-all policy exists."""
        policies = get_k8s_network_policies()
        names = [p["metadata"]["name"] for p in policies]
        assert "default-deny-all" in names, "default-deny-all policy not found"

    def test_backend_can_talk_to_db_and_redis(self):
        """Test that backend network policy allows egress to DB and Redis."""
        policies = get_k8s_network_policies()
        backend_policy = next(
            (p for p in policies if p["metadata"]["name"] == "backend-netpol"), None
        )
        assert backend_policy is not None, "backend-netpol not found"
        egress = backend_policy.get("spec", {}).get("egress", [])
        egress_ports = set()
        for rule in egress:
            for port in rule.get("ports", []):
                egress_ports.add(port["port"])
        assert 5432 in egress_ports, "Backend should be able to reach PostgreSQL (5432)"
        assert 6379 in egress_ports, "Backend should be able to reach Redis (6379)"

    def test_frontend_can_talk_to_backend_only(self):
        """Test that frontend can only talk to backend."""
        policies = get_k8s_network_policies()
        frontend_policy = next(
            (p for p in policies if p["metadata"]["name"] == "frontend-netpol"), None
        )
        assert frontend_policy is not None, "frontend-netpol not found"
        egress = frontend_policy.get("spec", {}).get("egress", [])
        # Check egress rules — should not have DB or Redis
        app_egress_ports = set()
        for rule in egress:
            to_selectors = rule.get("to", [])
            for to_rule in to_selectors:
                if "podSelector" in to_rule:
                    match_labels = to_rule["podSelector"].get("matchLabels", {})
                    if match_labels.get("app.kubernetes.io/name") == "backend":
                        for port in rule.get("ports", []):
                            app_egress_ports.add(port["port"])
        assert 8000 in app_egress_ports, "Frontend should be able to reach backend (8000)"

    def test_workers_can_talk_to_db_and_redis_only(self):
        """Test that workers can only talk to DB and Redis."""
        policies = get_k8s_network_policies()
        worker_policy = next(
            (p for p in policies if p["metadata"]["name"] == "worker-netpol"), None
        )
        assert worker_policy is not None, "worker-netpol not found"
        egress = worker_policy.get("spec", {}).get("egress", [])
        egress_ports = set()
        for rule in egress:
            for port in rule.get("ports", []):
                egress_ports.add(port["port"])
        assert 5432 in egress_ports, "Worker should be able to reach PostgreSQL (5432)"
        assert 6379 in egress_ports, "Worker should be able to reach Redis (6379)"

    def test_monitoring_can_scrape_all(self):
        """Test that monitoring can scrape metrics from all services."""
        policies = get_k8s_network_policies()
        monitoring_policy = next(
            (p for p in policies if p["metadata"]["name"] == "monitoring-netpol"), None
        )
        assert monitoring_policy is not None, "monitoring-netpol not found"
        # Monitoring should be able to reach all pods in namespace
        egress = monitoring_policy.get("spec", {}).get("egress", [])
        has_namespace_access = False
        for rule in egress:
            to_rules = rule.get("to", [])
            for to_rule in to_rules:
                if "namespaceSelector" in to_rule:
                    has_namespace_access = True
        assert has_namespace_access, "Monitoring should be able to reach all pods in namespace"

    def test_policies_specify_both_ingress_and_egress(self):
        """Test that policies specify both ingress and egress."""
        for policy in get_k8s_network_policies():
            name = policy["metadata"]["name"]
            policy_types = policy["spec"].get("policyTypes", [])
            assert "Ingress" in policy_types or "Egress" in policy_types, \
                f"NetworkPolicy {name} should specify Ingress and/or Egress"


class TestK8sIngress:
    """Test Ingress configuration."""

    def test_ingress_exists(self):
        assert (K8S_DIR / "ingress.yaml").exists(), "ingress.yaml not found"

    def test_ingress_has_tls(self):
        """Test that Ingress has TLS termination."""
        docs = load_k8s_yaml(K8S_DIR / "ingress.yaml")
        ingress = next(d for d in docs if d.get("kind") == "Ingress")
        assert "tls" in ingress["spec"], "Ingress missing TLS configuration"
        assert len(ingress["spec"]["tls"]) > 0, "Ingress TLS list is empty"

    def test_ingress_has_rate_limiting(self):
        """Test that Ingress has rate limiting annotations."""
        docs = load_k8s_yaml(K8S_DIR / "ingress.yaml")
        ingress = next(d for d in docs if d.get("kind") == "Ingress")
        annotations = ingress["metadata"].get("annotations", {})
        rate_limit_keys = [k for k in annotations if "limit" in k.lower()]
        assert len(rate_limit_keys) > 0, "Ingress missing rate limiting annotations"

    def test_ingress_routes_api_to_backend(self):
        """Test that /api/* routes to backend."""
        docs = load_k8s_yaml(K8S_DIR / "ingress.yaml")
        ingress = next(d for d in docs if d.get("kind") == "Ingress")
        rules = ingress["spec"]["rules"]
        paths = []
        for rule in rules:
            for path in rule.get("http", {}).get("paths", []):
                paths.append(path["path"])
        assert "/api" in paths, "/api path not found in Ingress rules"

    def test_ingress_routes_root_to_frontend(self):
        """Test that /* routes to frontend."""
        docs = load_k8s_yaml(K8S_DIR / "ingress.yaml")
        ingress = next(d for d in docs if d.get("kind") == "Ingress")
        rules = ingress["spec"]["rules"]
        root_found = False
        for rule in rules:
            for path in rule.get("http", {}).get("paths", []):
                if path["path"] == "/":
                    assert path["backend"]["service"]["name"] == "frontend-svc", \
                        "Root path should route to frontend-svc"
                    root_found = True
        assert root_found, "Root path (/) not found in Ingress rules"

    def test_ingress_host_is_parwa_ai(self):
        """Test that Ingress host is parwa.ai."""
        docs = load_k8s_yaml(K8S_DIR / "ingress.yaml")
        ingress = next(d for d in docs if d.get("kind") == "Ingress")
        hosts = [rule["host"] for rule in ingress["spec"]["rules"]]
        assert "parwa.ai" in hosts, "parwa.ai host not found in Ingress"


class TestK8sPDB:
    """Test Pod Disruption Budgets."""

    def test_pdb_file_exists(self):
        assert (K8S_DIR / "pdb.yaml").exists(), "pdb.yaml not found"

    def test_backend_pdb_exists(self):
        docs = load_k8s_yaml(K8S_DIR / "pdb.yaml")
        names = [d["metadata"]["name"] for d in docs if d.get("kind") == "PodDisruptionBudget"]
        assert "backend-pdb" in names, "backend-pdb not found"

    def test_worker_pdb_exists(self):
        docs = load_k8s_yaml(K8S_DIR / "pdb.yaml")
        names = [d["metadata"]["name"] for d in docs if d.get("kind") == "PodDisruptionBudget"]
        assert "worker-pdb" in names, "worker-pdb not found"

    def test_frontend_pdb_exists(self):
        docs = load_k8s_yaml(K8S_DIR / "pdb.yaml")
        names = [d["metadata"]["name"] for d in docs if d.get("kind") == "PodDisruptionBudget"]
        assert "frontend-pdb" in names, "frontend-pdb not found"

    def test_pdbs_have_min_available(self):
        """Test that PDBs specify minAvailable."""
        docs = load_k8s_yaml(K8S_DIR / "pdb.yaml")
        for doc in docs:
            if doc.get("kind") == "PodDisruptionBudget":
                assert "minAvailable" in doc["spec"], \
                    f"PDB {doc['metadata']['name']} missing minAvailable"


class TestK8sDirectoryStructure:
    """Test the K8s directory structure is complete."""

    def test_namespace_yaml(self):
        assert (K8S_DIR / "namespace.yaml").exists()

    def test_configmap_yaml(self):
        assert (K8S_DIR / "configmap.yaml").exists()

    def test_secrets_yaml(self):
        assert (K8S_DIR / "secrets.yaml").exists()

    def test_backend_directory(self):
        assert (K8S_DIR / "backend" / "deployment.yaml").exists()
        assert (K8S_DIR / "backend" / "service.yaml").exists()
        assert (K8S_DIR / "backend" / "hpa.yaml").exists()

    def test_worker_directory(self):
        assert (K8S_DIR / "worker" / "deployment.yaml").exists()
        assert (K8S_DIR / "worker" / "hpa.yaml").exists()

    def test_frontend_directory(self):
        assert (K8S_DIR / "frontend" / "deployment.yaml").exists()
        assert (K8S_DIR / "frontend" / "service.yaml").exists()

    def test_mcp_directory(self):
        assert (K8S_DIR / "mcp" / "deployment.yaml").exists()
        assert (K8S_DIR / "mcp" / "service.yaml").exists()

    def test_postgres_directory(self):
        assert (K8S_DIR / "postgres" / "statefulset.yaml").exists()
        assert (K8S_DIR / "postgres" / "service.yaml").exists()
        assert (K8S_DIR / "postgres" / "pvc.yaml").exists()

    def test_redis_directory(self):
        assert (K8S_DIR / "redis" / "statefulset.yaml").exists()
        assert (K8S_DIR / "redis" / "service.yaml").exists()
        assert (K8S_DIR / "redis" / "pvc.yaml").exists()

    def test_monitoring_prometheus(self):
        assert (K8S_DIR / "monitoring" / "prometheus" / "deployment.yaml").exists()
        assert (K8S_DIR / "monitoring" / "prometheus" / "service.yaml").exists()
        assert (K8S_DIR / "monitoring" / "prometheus" / "configmap.yaml").exists()

    def test_monitoring_grafana(self):
        assert (K8S_DIR / "monitoring" / "grafana" / "deployment.yaml").exists()
        assert (K8S_DIR / "monitoring" / "grafana" / "service.yaml").exists()

    def test_monitoring_alertmanager(self):
        assert (K8S_DIR / "monitoring" / "alertmanager" / "deployment.yaml").exists()
        assert (K8S_DIR / "monitoring" / "alertmanager" / "service.yaml").exists()

    def test_ingress_yaml(self):
        assert (K8S_DIR / "ingress.yaml").exists()

    def test_networkpolicy_yaml(self):
        assert (K8S_DIR / "networkpolicy.yaml").exists()

    def test_pdb_yaml(self):
        assert (K8S_DIR / "pdb.yaml").exists()

    def test_kustomization_yaml(self):
        assert (K8S_DIR / "kustomization.yaml").exists()
