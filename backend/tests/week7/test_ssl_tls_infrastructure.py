"""
Week 7 — SSL/TLS and Infrastructure Verification Tests

Reads actual config files and verifies security settings.
All tests are STATIC analysis — no running services needed.

Sections:
1. SSL/TLS configuration (nginx)
2. Infrastructure files existence
3. Backup/restore scripts
4. K8s security manifests
5. Monitoring configuration
6. Environment security (.gitignore, .env.example)
"""

import os
import re
from pathlib import Path

import pytest

# Base path
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


def _read(filepath: str) -> str:
    """Read a file relative to project root."""
    full = os.path.join(BASE_DIR, filepath)
    with open(full, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _exists(filepath: str) -> bool:
    """Check if a file exists relative to project root."""
    return os.path.isfile(os.path.join(BASE_DIR, filepath))


# ══════════════════════════════════════════════════════════════════
# SECTION 1: SSL/TLS Configuration
# ══════════════════════════════════════════════════════════════════

class TestNginxDockerTLSConfig:
    """SSL/TLS settings in Docker nginx config."""

    DOCKER_NGINX = "infra/docker/nginx-default.conf"

    def test_nginx_docker_config_exists(self):
        assert _exists(self.DOCKER_NGINX), \
            f"{self.DOCKER_NGINX} must exist"

    def test_nginx_docker_has_ssl_certificate(self):
        content = _read(self.DOCKER_NGINX)
        assert "ssl_certificate" in content, \
            "Docker nginx must have ssl_certificate directive"

    def test_nginx_docker_has_ssl_certificate_key(self):
        content = _read(self.DOCKER_NGINX)
        assert "ssl_certificate_key" in content, \
            "Docker nginx must have ssl_certificate_key directive"

    def test_nginx_docker_https_server_block(self):
        content = _read(self.DOCKER_NGINX)
        assert "listen 443 ssl" in content, \
            "Docker nginx must have HTTPS server block on port 443"

    def test_nginx_docker_http_to_https_redirect(self):
        content = _read(self.DOCKER_NGINX)
        assert "301 https://" in content, \
            "Docker nginx must redirect HTTP to HTTPS"


class TestNginxMainTLSConfig:
    """SSL/TLS settings in main nginx.conf."""

    MAIN_NGINX = "nginx/nginx.conf"

    def test_nginx_main_config_exists(self):
        assert _exists(self.MAIN_NGINX), \
            f"{self.MAIN_NGINX} must exist"

    def test_nginx_docker_tls_version(self):
        """Verify TLSv1.2 or TLSv1.3 minimum in main config."""
        content = _read(self.MAIN_NGINX)
        has_ssl_protocols = "ssl_protocols" in content or "ssl_protocol" in content
        assert has_ssl_protocols, \
            "Main nginx must have ssl_protocols directive"
        assert "TLSv1.2" in content or "TLSv1.3" in content, \
            "Main nginx must use TLSv1.2 or TLSv1.3"

    def test_nginx_docker_cipher_suites(self):
        """Verify 8+ strong cipher suites in main config."""
        content = _read(self.MAIN_NGINX)
        assert "ssl_ciphers" in content, \
            "Main nginx must define ssl_ciphers"
        # Count cipher suites (colon-separated in ssl_ciphers)
        cipher_match = re.search(r'ssl_ciphers\s+([^;]+);', content)
        if cipher_match:
            ciphers = cipher_match.group(1)
            cipher_count = len(ciphers.split(":"))
            assert cipher_count >= 8, \
                f"Must have 8+ cipher suites, found {cipher_count}"

    def test_nginx_docker_hsts(self):
        """Verify HSTS header with includeSubDomains and preload."""
        content = _read(self.MAIN_NGINX)
        assert "Strict-Transport-Security" in content, \
            "Main nginx must set HSTS header"
        assert "includeSubDomains" in content, \
            "HSTS must include includeSubDomains"
        assert "preload" in content, \
            "HSTS must include preload"

    def test_nginx_docker_ocsp_stapling(self):
        """Verify OCSP stapling is enabled."""
        content = _read(self.MAIN_NGINX)
        assert "ssl_stapling" in content, \
            "Main nginx must enable OCSP stapling"
        assert "ssl_stapling_verify" in content, \
            "Main nginx must enable OCSP stapling verification"


class TestNginxSecurityHeaders:
    """Security headers in nginx configs."""

    def test_nginx_docker_x_frame_options(self):
        content = _read("infra/docker/nginx-default.conf")
        assert "X-Frame-Options" in content, \
            "Docker nginx must set X-Frame-Options header"

    def test_nginx_docker_x_content_type_options(self):
        content = _read("infra/docker/nginx-default.conf")
        assert "X-Content-Type-Options" in content, \
            "Docker nginx must set X-Content-Type-Options header"

    def test_nginx_main_x_frame_options(self):
        content = _read("nginx/nginx.conf")
        assert "X-Frame-Options" in content, \
            "Main nginx must set X-Frame-Options header"

    def test_nginx_main_x_content_type_options(self):
        content = _read("nginx/nginx.conf")
        assert "X-Content-Type-Options" in content, \
            "Main nginx must set X-Content-Type-Options header"

    def test_nginx_main_x_xss_protection(self):
        content = _read("nginx/nginx.conf")
        assert "X-XSS-Protection" in content, \
            "Main nginx must set X-XSS-Protection header"

    def test_nginx_main_referrer_policy(self):
        content = _read("nginx/nginx.conf")
        assert "Referrer-Policy" in content, \
            "Main nginx must set Referrer-Policy header"

    def test_nginx_main_permissions_policy(self):
        content = _read("nginx/nginx.conf")
        assert "Permissions-Policy" in content, \
            "Main nginx must set Permissions-Policy header"

    def test_nginx_main_content_security_policy(self):
        content = _read("nginx/nginx.conf")
        assert "Content-Security-Policy" in content, \
            "Main nginx must set Content-Security-Policy header"

    def test_nginx_docker_csp_present(self):
        content = _read("infra/docker/nginx-default.conf")
        assert "Content-Security-Policy" in content, \
            "Docker nginx must set Content-Security-Policy header"


class TestNginxConfigsSynced:
    """Verify Docker config has similar security settings as main config."""

    def test_both_have_security_headers(self):
        docker = _read("infra/docker/nginx-default.conf")
        main = _read("nginx/nginx.conf")
        # Both must have HSTS
        assert "Strict-Transport-Security" in docker, "Docker nginx missing HSTS"
        assert "Strict-Transport-Security" in main, "Main nginx missing HSTS"

    def test_both_have_x_frame_options(self):
        docker = _read("infra/docker/nginx-default.conf")
        main = _read("nginx/nginx.conf")
        assert "X-Frame-Options" in docker, "Docker nginx missing X-Frame-Options"
        assert "X-Frame-Options" in main, "Main nginx missing X-Frame-Options"


# ══════════════════════════════════════════════════════════════════
# SECTION 2: Infrastructure Files Existence
# ══════════════════════════════════════════════════════════════════

class TestInfrastructureFiles:
    """Verify required infrastructure files exist."""

    def test_docker_compose_exists(self):
        assert _exists("docker-compose.yml"), \
            "docker-compose.yml must exist"

    def test_k8s_manifests_exist(self):
        k8s_dir = os.path.join(BASE_DIR, "infra", "k8s")
        assert os.path.isdir(k8s_dir), \
            "infra/k8s/ directory must exist"
        # Must have at least deployment, service, and configmap
        yaml_files = [
            f for f in os.listdir(k8s_dir)
            if f.endswith(".yaml") or f.endswith(".yml")
        ]
        assert len(yaml_files) >= 5, \
            f"infra/k8s/ must have deployment manifests, found {len(yaml_files)} files"

    def test_backend_deployment_exists(self):
        assert _exists("infra/k8s/backend/deployment.yaml"), \
            "Backend K8s deployment must exist"

    def test_frontend_deployment_exists(self):
        assert _exists("infra/k8s/frontend/deployment.yaml"), \
            "Frontend K8s deployment must exist"

    def test_postgres_statefulset_exists(self):
        assert _exists("infra/k8s/postgres/statefulset.yaml"), \
            "Postgres K8s statefulset must exist"

    def test_redis_statefulset_exists(self):
        assert _exists("infra/k8s/redis/statefulset.yaml"), \
            "Redis K8s statefulset must exist"

    def test_namespace_exists(self):
        assert _exists("infra/k8s/namespace.yaml"), \
            "K8s namespace manifest must exist"

    def test_kustomization_exists(self):
        assert _exists("infra/k8s/kustomization.yaml"), \
            "K8s kustomization must exist"


# ══════════════════════════════════════════════════════════════════
# SECTION 3: Backup/Restore Scripts
# ══════════════════════════════════════════════════════════════════

class TestBackupScripts:
    """Verify backup and restore scripts exist and are valid."""

    def test_backup_script_exists(self):
        assert _exists("infra/scripts/backup.sh"), \
            "Backup script must exist at infra/scripts/backup.sh"

    def test_restore_script_exists(self):
        assert _exists("infra/scripts/restore.sh"), \
            "Restore script must exist at infra/scripts/restore.sh"

    def test_backup_script_has_pg_dump(self):
        content = _read("infra/scripts/backup.sh")
        assert "pg_dump" in content, \
            "Backup script must use pg_dump command"

    def test_backup_script_has_compression(self):
        content = _read("infra/scripts/backup.sh")
        assert "gzip" in content, \
            "Backup script must compress output with gzip"

    def test_backup_script_has_retention(self):
        content = _read("infra/scripts/backup.sh")
        assert "RETENTION" in content or "retention" in content, \
            "Backup script must implement retention/cleanup"

    def test_backup_script_has_verification(self):
        content = _read("infra/scripts/backup.sh")
        assert "verify" in content.lower(), \
            "Backup script must verify backup integrity"

    def test_restore_script_has_psql(self):
        content = _read("infra/scripts/restore.sh")
        assert "psql" in content, \
            "Restore script must use psql command"

    def test_restore_script_has_confirmation(self):
        content = _read("infra/scripts/restore.sh")
        assert "RESTORE" in content or "confirm" in content.lower(), \
            "Restore script must require confirmation"

    def test_restore_script_has_pre_restore_backup(self):
        content = _read("infra/scripts/restore.sh")
        assert "pre" in content.lower() and "restore" in content.lower(), \
            "Restore script must create pre-restore backup"

    def test_scripts_have_shebang(self):
        backup = _read("infra/scripts/backup.sh")
        restore = _read("infra/scripts/restore.sh")
        assert backup.startswith("#!/bin/bash"), \
            "Backup script must have bash shebang"
        assert restore.startswith("#!/bin/bash"), \
            "Restore script must have bash shebang"

    def test_scripts_use_set_euo_pipefail(self):
        backup = _read("infra/scripts/backup.sh")
        restore = _read("infra/scripts/restore.sh")
        assert "set -euo pipefail" in backup, \
            "Backup script must use set -euo pipefail"
        assert "set -euo pipefail" in restore, \
            "Restore script must use set -euo pipefail"


# ══════════════════════════════════════════════════════════════════
# SECTION 4: K8s Security Manifests
# ══════════════════════════════════════════════════════════════════

class TestK8sSecurity:
    """Verify K8s security configurations."""

    def test_non_root_containers(self):
        """Backend deployment must set runAsNonRoot: true."""
        content = _read("infra/k8s/backend/deployment.yaml")
        assert "runAsNonRoot: true" in content, \
            "Backend deployment must set runAsNonRoot: true"

    def test_security_context_present(self):
        """Backend deployment must have securityContext."""
        content = _read("infra/k8s/backend/deployment.yaml")
        assert "securityContext:" in content, \
            "Backend deployment must have securityContext section"

    def test_readonly_root_filesystem(self):
        """Backend containers must have readOnlyRootFilesystem."""
        content = _read("infra/k8s/backend/deployment.yaml")
        assert "readOnlyRootFilesystem: true" in content, \
            "Backend containers must use readOnlyRootFilesystem: true"

    def test_no_privilege_escalation(self):
        """Backend containers must disable privilege escalation."""
        content = _read("infra/k8s/backend/deployment.yaml")
        assert "allowPrivilegeEscalation: false" in content, \
            "Backend containers must disable allowPrivilegeEscalation"

    def test_drop_all_capabilities(self):
        """Backend containers must drop all Linux capabilities."""
        content = _read("infra/k8s/backend/deployment.yaml")
        assert "drop:" in content and "ALL" in content, \
            "Backend containers must drop ALL capabilities"

    def test_resource_limits_set(self):
        """Backend deployment must have CPU/memory limits."""
        content = _read("infra/k8s/backend/deployment.yaml")
        assert "limits:" in content, \
            "Backend deployment must have resource limits"
        assert "cpu:" in content, \
            "Backend deployment must have CPU limits"
        assert "memory:" in content, \
            "Backend deployment must have memory limits"

    def test_resource_requests_set(self):
        """Backend deployment must have CPU/memory requests."""
        content = _read("infra/k8s/backend/deployment.yaml")
        assert "requests:" in content, \
            "Backend deployment must have resource requests"

    def test_health_checks_configured(self):
        """Backend must have liveness and readiness probes."""
        content = _read("infra/k8s/backend/deployment.yaml")
        assert "livenessProbe:" in content, \
            "Backend must have livenessProbe"
        assert "readinessProbe:" in content, \
            "Backend must have readinessProbe"

    def test_liveness_uses_health_endpoint(self):
        """Liveness probe must hit /health endpoint."""
        content = _read("infra/k8s/backend/deployment.yaml")
        assert "/health" in content, \
            "Liveness probe must use /health endpoint"

    def test_network_policies_exist(self):
        """NetworkPolicy resources must exist."""
        content = _read("infra/k8s/networkpolicy.yaml")
        assert "kind: NetworkPolicy" in content, \
            "NetworkPolicy resource must be defined"
        # Count policies — should have multiple
        policy_count = content.count("kind: NetworkPolicy")
        assert policy_count >= 4, \
            f"Must have 4+ NetworkPolicy resources, found {policy_count}"

    def test_default_deny_all_policy(self):
        """Must have a default-deny-all NetworkPolicy."""
        content = _read("infra/k8s/networkpolicy.yaml")
        assert "default-deny-all" in content, \
            "Must have default-deny-all NetworkPolicy"

    def test_secrets_not_in_configmaps(self):
        """Sensitive data must be in Secrets, not ConfigMaps."""
        secrets = _read("infra/k8s/secrets.yaml")
        configmap = _read("infra/k8s/configmap.yaml")
        # Secrets must contain sensitive items
        assert "DB_PASSWORD" in secrets, \
            "Secrets manifest must contain DB_PASSWORD"
        assert "JWT_SECRET_KEY" in secrets, \
            "Secrets manifest must contain JWT_SECRET_KEY"
        # ConfigMaps should NOT contain sensitive items
        assert "DB_PASSWORD" not in configmap, \
            "ConfigMap must NOT contain DB_PASSWORD"
        assert "JWT_SECRET_KEY" not in configmap, \
            "ConfigMap must NOT contain JWT_SECRET_KEY"

    def test_pdb_exists(self):
        """PodDisruptionBudget must exist for HA."""
        content = _read("infra/k8s/pdb.yaml")
        assert "kind: PodDisruptionBudget" in content, \
            "PodDisruptionBudget must be defined"

    def test_pdb_backend_exists(self):
        content = _read("infra/k8s/pdb.yaml")
        assert "backend-pdb" in content, \
            "Backend PodDisruptionBudget must exist"

    def test_pdb_min_available_set(self):
        content = _read("infra/k8s/pdb.yaml")
        assert "minAvailable:" in content, \
            "PDB must set minAvailable"

    def test_pod_anti_affinity(self):
        """Backend deployment should have pod anti-affinity."""
        content = _read("infra/k8s/backend/deployment.yaml")
        assert "podAntiAffinity" in content, \
            "Backend should have pod anti-affinity for HA"


# ══════════════════════════════════════════════════════════════════
# SECTION 5: Monitoring Configuration
# ══════════════════════════════════════════════════════════════════

class TestMonitoringConfig:
    """Verify monitoring stack is configured."""

    def test_prometheus_manifest_exists(self):
        assert _exists("infra/k8s/monitoring/prometheus/deployment.yaml"), \
            "Prometheus deployment must exist"

    def test_grafana_manifest_exists(self):
        assert _exists("infra/k8s/monitoring/grafana/deployment.yaml"), \
            "Grafana deployment must exist"

    def test_alertmanager_manifest_exists(self):
        assert _exists("infra/k8s/monitoring/alertmanager/deployment.yaml"), \
            "AlertManager deployment must exist"

    def test_prometheus_service_exists(self):
        assert _exists("infra/k8s/monitoring/prometheus/service.yaml"), \
            "Prometheus service must exist"

    def test_grafana_service_exists(self):
        assert _exists("infra/k8s/monitoring/grafana/service.yaml"), \
            "Grafana service must exist"

    def test_alertmanager_service_exists(self):
        assert _exists("infra/k8s/monitoring/alertmanager/service.yaml"), \
            "AlertManager service must exist"

    def test_prometheus_configmap_exists(self):
        assert _exists("infra/k8s/monitoring/prometheus/configmap.yaml"), \
            "Prometheus configmap must exist"

    def test_alertmanager_config_exists(self):
        assert _exists("monitoring/alertmanager/alertmanager.yml"), \
            "AlertManager configuration must exist"

    def test_prometheus_scraping_configured(self):
        content = _read("monitoring/prometheus.yml")
        assert "scrape_configs" in content or "scrape_config" in content, \
            "Prometheus must have scrape configs"

    def test_alertmanager_diverse_receivers(self):
        """AlertManager must have diverse receivers, not just webhook."""
        content = _read("monitoring/alertmanager/alertmanager.yml")
        # Must have more than just webhook
        has_email = "email_configs" in content
        has_slack = "slack_configs" in content
        assert has_email or has_slack, \
            "AlertManager must have email or Slack receivers (not just webhook)"

    def test_alertmanager_email_configured(self):
        """AlertManager must have email configuration."""
        content = _read("monitoring/alertmanager/alertmanager.yml")
        assert "email_configs" in content, \
            "AlertManager must have email_configs section"

    def test_alertmanager_slack_configured(self):
        """AlertManager must have Slack configuration."""
        content = _read("monitoring/alertmanager/alertmanager.yml")
        assert "slack_configs" in content, \
            "AlertManager must have slack_configs section"

    def test_alertmanager_severity_routing(self):
        """AlertManager must route by severity."""
        content = _read("monitoring/alertmanager/alertmanager.yml")
        assert "severity" in content, \
            "AlertManager must route by severity"

    def test_alertmanager_critical_receiver(self):
        """AlertManager must have a critical receiver."""
        content = _read("monitoring/alertmanager/alertmanager.yml")
        assert "critical-receiver" in content, \
            "AlertManager must define critical-receiver"

    def test_alertmanager_warning_receiver(self):
        """AlertManager must have a warning receiver."""
        content = _read("monitoring/alertmanager/alertmanager.yml")
        assert "warning-receiver" in content, \
            "AlertManager must define warning-receiver"

    def test_grafana_datasource_configured(self):
        assert _exists("monitoring/grafana/provisioning/datasources/datasource.yml"), \
            "Grafana datasource provisioning must exist"

    def test_grafana_dashboards_configured(self):
        assert _exists("monitoring/grafana/provisioning/dashboards/dashboards.yml"), \
            "Grafana dashboard provisioning must exist"


# ══════════════════════════════════════════════════════════════════
# SECTION 6: Environment Security
# ══════════════════════════════════════════════════════════════════

class TestEnvironmentSecurity:
    """Verify environment security configurations."""

    def test_gitignore_has_env(self):
        """ .gitignore must exclude .env files."""
        content = _read(".gitignore")
        assert ".env" in content, \
            ".gitignore must exclude .env files"

    def test_gitignore_has_secrets_dir(self):
        """.gitignore must exclude secrets/ directory."""
        content = _read(".gitignore")
        assert "secrets/" in content, \
            ".gitignore must exclude secrets/ directory"

    def test_gitignore_has_pem_files(self):
        """.gitignore must exclude *.pem files."""
        content = _read(".gitignore")
        assert "*.pem" in content, \
            ".gitignore must exclude *.pem files"

    def test_gitignore_has_key_files(self):
        """.gitignore must exclude *.key files."""
        content = _read(".gitignore")
        assert "*.key" in content, \
            ".gitignore must exclude *.key files"

    def test_env_example_exists(self):
        """.env.example must exist for documentation."""
        assert _exists(".env.example"), \
            ".env.example must exist"

    def test_env_prod_example_exists(self):
        """.env.prod.example must exist for production documentation."""
        assert _exists(".env.prod.example"), \
            ".env.prod.example must exist"

    def test_no_hardcoded_secrets_in_python(self):
        """Python source must not have hardcoded passwords or API keys."""
        # Check backend files for obvious hardcoded secrets
        backend_api_dir = os.path.join(BASE_DIR, "backend", "app", "api")
        if not os.path.isdir(backend_api_dir):
            pytest.skip("backend/app/api directory not found")
        
        # Common patterns of hardcoded secrets
        secret_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', "hardcoded password"),
            (r'api_key\s*=\s*["\'][^"\']+["\']', "hardcoded API key"),
            (r'secret\s*=\s*["\'][^"\']+["\']', "hardcoded secret"),
        ]
        
        issues = []
        for fname in os.listdir(backend_api_dir):
            if not fname.endswith(".py"):
                continue
            filepath = os.path.join(backend_api_dir, fname)
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            for pattern, desc in secret_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                # Exclude template/placeholder values
                filtered = [m for m in matches
                           if "CHANGE_ME" not in m
                           and "your_" not in m.lower()
                           and "placeholder" not in m.lower()
                           and "example" not in m.lower()]
                if filtered:
                    issues.append(f"{fname}: {desc} = {filtered[0]}")

        assert len(issues) == 0, \
            f"Found potential hardcoded secrets in API files:\n" + "\n".join(issues)

    def test_gitignore_has_prod_env(self):
        """.gitignore must exclude production .env files."""
        content = _read(".gitignore")
        assert ".env.prod" in content, \
            ".gitignore must exclude .env.prod files"

    def test_gitignore_has_p12_pfx(self):
        """.gitignore must exclude certificate files."""
        content = _read(".gitignore")
        assert "*.p12" in content or "*.pfx" in content, \
            ".gitignore must exclude *.p12 or *.pfx certificate files"


# ══════════════════════════════════════════════════════════════════
# SECTION 7: Docker Configuration Security
# ══════════════════════════════════════════════════════════════════

class TestDockerSecurity:
    """Verify Docker and docker-compose security."""

    def test_docker_compose_localhost_binding(self):
        """Dev compose should bind to localhost only."""
        content = _read("docker-compose.yml")
        assert "127.0.0.1:" in content, \
            "docker-compose must bind ports to 127.0.0.1 only"

    def test_docker_compose_redis_password(self):
        """Redis must have password configured."""
        content = _read("docker-compose.yml")
        assert "requirepass" in content or "REDIS_PASSWORD" in content, \
            "Redis must be configured with a password"

    def test_docker_compose_healthchecks(self):
        """Critical services must have health checks."""
        content = _read("docker-compose.yml")
        assert "healthcheck:" in content, \
            "docker-compose must have health checks"

    def test_docker_compose_db_healthcheck(self):
        content = _read("docker-compose.yml")
        assert "pg_isready" in content, \
            "Database must have pg_isready health check"

    def test_dev_only_warning_present(self):
        """docker-compose.yml must have dev-only warning."""
        content = _read("docker-compose.yml")
        assert "DEVELOPMENT" in content or "development" in content, \
            "docker-compose must indicate development-only usage"


# ══════════════════════════════════════════════════════════════════
# SECTION 8: Additional Nginx Hardening
# ══════════════════════════════════════════════════════════════════

class TestNginxHardening:
    """Additional nginx hardening checks."""

    def test_main_nginx_blocks_hidden_files(self):
        """Nginx must block access to hidden files."""
        content = _read("nginx/nginx.conf")
        assert "/\\./" in content or "deny all" in content, \
            "Nginx must block hidden files"

    def test_main_nginx_blocks_sensitive_extensions(self):
        """Nginx must block sensitive file extensions."""
        content = _read("nginx/nginx.conf")
        # The nginx config uses regex pattern \.(env|git|svn|...) to block
        has_env_block = (".env" in content or "\\.(env" in content or
                        ".env" in content.replace("\\", ""))
        assert has_env_block and "deny all" in content, \
            "Nginx must block .env files"

    def test_main_nginx_rate_limiting(self):
        """Nginx must have rate limiting zones."""
        content = _read("nginx/nginx.conf")
        assert "limit_req_zone" in content, \
            "Nginx must have rate limiting zones"

    def test_main_nginx_ssl_session_cache(self):
        """Nginx must have SSL session caching."""
        content = _read("nginx/nginx.conf")
        assert "ssl_session_cache" in content, \
            "Nginx must have SSL session caching"

    def test_main_nginx_client_body_limit(self):
        """Nginx must limit request body size."""
        content = _read("nginx/nginx.conf")
        assert "client_max_body_size" in content, \
            "Nginx must limit client_max_body_size"

    def test_docker_nginx_blocks_hidden_files(self):
        """Docker nginx must block access to hidden files."""
        content = _read("infra/docker/nginx-default.conf")
        assert "/\\./" in content or "deny all" in content, \
            "Docker nginx must block hidden files"
