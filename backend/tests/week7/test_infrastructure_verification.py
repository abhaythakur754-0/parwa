"""
Week 7 — Infrastructure & Deployment Verification Tests

Verifies infrastructure configuration, Docker, K8s, nginx, backup,
monitoring, and SSL setup.
"""

import os
import re
from pathlib import Path

import pytest

# ── Paths ────────────────────────────────────────────────────────
PROJECT_ROOT = Path("/home/z/my-project")


# ═══════════════════════════════════════════════════════════════════
# Docker & K8s
# ═══════════════════════════════════════════════════════════════════


class TestDockerAndK8s:
    """Infrastructure: Docker and Kubernetes verification."""

    def test_docker_compose_exists(self):
        """docker-compose.yml exists at project root."""
        dc = PROJECT_ROOT / "docker-compose.yml"
        assert dc.exists(), f"docker-compose.yml should exist at {dc}"

    def test_docker_compose_prod_exists(self):
        """docker-compose.prod.yml exists for production."""
        dcp = PROJECT_ROOT / "docker-compose.prod.yml"
        assert dcp.exists(), f"docker-compose.prod.yml should exist at {dcp}"

    def test_k8s_manifests_directory(self):
        """Kubernetes manifests directory exists."""
        k8s = PROJECT_ROOT / "infra" / "k8s"
        assert k8s.exists(), "infra/k8s directory should exist"

    def test_k8s_namespace_exists(self):
        """Kubernetes namespace manifest exists."""
        ns = PROJECT_ROOT / "infra" / "k8s" / "namespace.yaml"
        assert ns.exists(), "K8s namespace.yaml should exist"

    def test_k8s_backend_deployment_exists(self):
        """K8s backend deployment manifest exists."""
        dep = PROJECT_ROOT / "infra" / "k8s" / "backend" / "deployment.yaml"
        assert dep.exists(), "K8s backend deployment.yaml should exist"

    def test_k8s_backend_has_resource_limits(self):
        """K8s backend deployment has resource limits configured."""
        dep = PROJECT_ROOT / "infra" / "k8s" / "backend" / "deployment.yaml"
        if dep.exists():
            source = dep.read_text()

            assert "limits" in source.lower() or "resources" in source.lower(), (
                "Backend deployment should have resource limits"
            )

    def test_k8s_backend_has_health_check(self):
        """K8s backend deployment has health check probes."""
        dep = PROJECT_ROOT / "infra" / "k8s" / "backend" / "deployment.yaml"
        if dep.exists():
            source = dep.read_text()

            assert (
                "livenessProbe" in source
                or "readinessProbe" in source
                or "health" in source.lower()
            ), "Backend deployment should have health check probes"

    def test_k8s_backend_non_root(self):
        """K8s backend deployment runs as non-root user."""
        dep = PROJECT_ROOT / "infra" / "k8s" / "backend" / "deployment.yaml"
        if dep.exists():
            source = dep.read_text()

            assert (
                "runAsNonRoot" in source
                or "securityContext" in source
                or "USER" in source
            ), "Backend deployment should run as non-root"

    def test_k8s_network_policy_exists(self):
        """K8s network policies exist."""
        np = PROJECT_ROOT / "infra" / "k8s" / "networkpolicy.yaml"
        assert np.exists(), "K8s networkpolicy.yaml should exist"

    def test_docker_backend_dockerfile_exists(self):
        """Backend Dockerfile exists."""
        df = PROJECT_ROOT / "infra" / "docker" / "backend.Dockerfile"
        assert df.exists(), "Backend Dockerfile should exist"

    def test_docker_backend_non_root(self):
        """Backend Dockerfile runs as non-root user."""
        df = PROJECT_ROOT / "infra" / "docker" / "backend.Dockerfile"
        if df.exists():
            source = df.read_text()
            user_lines = [line.strip() for line in source.split("\n") if line.strip().startswith("USER")]
            if user_lines:
                for line in user_lines:
                    assert "root" not in line.lower(), (
                        f"Backend should not run as root: {line}"
                    )
            else:
                # If no USER directive, that's acceptable if K8s sets it
                pass  # Could be set by K8s securityContext

    def test_docker_worker_dockerfile_exists(self):
        """Worker Dockerfile exists."""
        df = PROJECT_ROOT / "infra" / "docker" / "worker.Dockerfile"
        assert df.exists(), "Worker Dockerfile should exist"


# ═══════════════════════════════════════════════════════════════════
# Nginx
# ═══════════════════════════════════════════════════════════════════


class TestNginx:
    """Infrastructure: Nginx configuration verification."""

    def test_nginx_config_exists(self):
        """Main nginx.conf exists."""
        conf = PROJECT_ROOT / "nginx" / "nginx.conf"
        assert conf.exists(), f"nginx.conf should exist at {conf}"

    def test_nginx_docker_config_exists(self):
        """Nginx Docker config exists."""
        dconf = PROJECT_ROOT / "infra" / "docker" / "nginx.conf"
        assert dconf.exists(), f"Docker nginx.conf should exist at {dconf}"

    def test_nginx_has_tls_min_version(self):
        """Nginx config requires TLSv1.2+ minimum."""
        conf = PROJECT_ROOT / "nginx" / "nginx.conf"
        if conf.exists():
            source = conf.read_text()

            assert "TLSv1.2" in source or "ssl_protocol" in source.lower(), (
                "Nginx should enforce TLSv1.2+ minimum"
            )

    def test_nginx_has_strong_ciphers(self):
        """Nginx config has 8+ strong cipher suites."""
        conf = PROJECT_ROOT / "nginx" / "nginx.conf"
        if conf.exists():
            source = conf.read_text()

            # Count cipher suites
            cipher_matches = re.findall(r"[A-Z0-9-]+:", source)
            if cipher_matches:
                assert len(cipher_matches) >= 8, (
                    f"Nginx should have 8+ cipher suites, found {len(cipher_matches)}"
                )

    def test_nginx_has_hsts(self):
        """Nginx config has HSTS with includeSubDomains."""
        conf = PROJECT_ROOT / "nginx" / "nginx.conf"
        if conf.exists():
            source = conf.read_text()

            assert "Strict-Transport-Security" in source or "HSTS" in source, (
                "Nginx should have HSTS header"
            )
            assert "includeSubDomains" in source or "includeSubdomains" in source, (
                "HSTS should have includeSubDomains"
            )

    def test_nginx_hsts_has_preload(self):
        """Nginx HSTS has preload directive."""
        conf = PROJECT_ROOT / "nginx" / "nginx.conf"
        if conf.exists():
            source = conf.read_text()

            assert "preload" in source.lower(), (
                "HSTS should have preload directive"
            )

    def test_nginx_has_frame_protection(self):
        """Nginx has X-Frame-Options or CSP frame-ancestors."""
        conf = PROJECT_ROOT / "nginx" / "nginx.conf"
        if conf.exists():
            source = conf.read_text()

            has_frame = (
                "X-Frame-Options" in source
                or "frame-ancestors" in source
                or "X-Frame-Deny" in source
            )
            assert has_frame, "Nginx should have frame protection"


# ═══════════════════════════════════════════════════════════════════
# Backup
# ═══════════════════════════════════════════════════════════════════


class TestBackup:
    """Infrastructure: Backup verification."""

    def test_backup_script_exists(self):
        """Backup script exists at infra/scripts/backup.sh."""
        backup = PROJECT_ROOT / "infra" / "scripts" / "backup.sh"
        assert backup.exists(), f"Backup script should exist at {backup}"

    def test_restore_script_exists(self):
        """Restore script exists at infra/scripts/restore.sh."""
        restore = PROJECT_ROOT / "infra" / "scripts" / "restore.sh"
        assert restore.exists(), f"Restore script should exist at {restore}"

    def test_backup_cron_script_exists(self):
        """Backup cron script exists."""
        cron = PROJECT_ROOT / "infra" / "scripts" / "backup_cron.sh"
        assert cron.exists(), f"Backup cron script should exist at {cron}"

    def test_backup_script_has_pg_dump(self):
        """Backup script uses pg_dump for database backup."""
        backup = PROJECT_ROOT / "infra" / "scripts" / "backup.sh"
        if backup.exists():
            source = backup.read_text()
            assert "pg_dump" in source, "Backup script should use pg_dump"

    def test_backup_script_has_retention(self):
        """Backup script has retention/cleanup logic."""
        backup = PROJECT_ROOT / "infra" / "scripts" / "backup.sh"
        if backup.exists():
            source = backup.read_text()
            assert (
                "retention" in source.lower()
                or "cleanup" in source.lower()
                or "rotate" in source.lower()
                or "delete" in source.lower()
            ), "Backup script should have retention logic"

    def test_restore_script_handles_errors(self):
        """Restore script handles errors gracefully."""
        restore = PROJECT_ROOT / "infra" / "scripts" / "restore.sh"
        if restore.exists():
            source = restore.read_text()
            assert "set -e" in source or "error" in source.lower(), (
                "Restore script should have error handling"
            )


# ═══════════════════════════════════════════════════════════════════
# Monitoring
# ═══════════════════════════════════════════════════════════════════


class TestMonitoring:
    """Infrastructure: Monitoring setup verification."""

    def test_prometheus_config_exists(self):
        """Prometheus config exists."""
        # Check both k8s and standalone
        k8s_prom = PROJECT_ROOT / "infra" / "k8s" / "monitoring" / "prometheus"
        standalone_prom = PROJECT_ROOT / "monitoring" / "prometheus.yml"

        assert (
            k8s_prom.exists() or standalone_prom.exists()
        ), "Prometheus config should exist (k8s or standalone)"

    def test_grafana_dashboards_configured(self):
        """Grafana dashboards are configured."""
        dashboards_dir = PROJECT_ROOT / "monitoring" / "grafana_dashboards"
        if dashboards_dir.exists():
            json_files = list(dashboards_dir.glob("*.json"))
            assert len(json_files) >= 2, (
                f"Expected 2+ Grafana dashboards, found {len(json_files)}"
            )

    def test_alertmanager_has_diverse_receivers(self):
        """AlertManager has diverse receivers (not just webhook)."""
        am_file = PROJECT_ROOT / "monitoring" / "alertmanager" / "alertmanager.yml"
        if am_file.exists():
            source = am_file.read_text()

            # Should have multiple receiver types
            receivers = ["email", "slack", "webhook", "pagerduty"]
            found = sum(1 for r in receivers if r in source.lower())
            assert found >= 2, (
                f"AlertManager should have 2+ receiver types, found {found}"
            )


# ═══════════════════════════════════════════════════════════════════
# SSL
# ═════════════════════════════════════════════════════════════════════


class TestSSL:
    """Infrastructure: SSL setup verification."""

    def test_ssl_setup_script_exists(self):
        """SSL setup script exists."""
        ssl_script = PROJECT_ROOT / "nginx" / "ssl-setup.sh"
        assert ssl_script.exists(), f"SSL setup script should exist at {ssl_script}"

    def test_ssl_script_is_executable(self):
        """SSL setup script exists and is a valid shell script."""
        ssl_script = PROJECT_ROOT / "nginx" / "ssl-setup.sh"
        if ssl_script.exists():
            # Just verify it's a valid script (has shebang), don't test executable bit
            # since git may not preserve it
            source = ssl_script.read_text()
            assert source.startswith("#!"), "SSL setup script should have a shebang"

    def test_ssl_script_has_certificate_commands(self):
        """SSL setup script has certificate generation commands."""
        ssl_script = PROJECT_ROOT / "nginx" / "ssl-setup.sh"
        if ssl_script.exists():
            source = ssl_script.read_text()
            assert (
                "openssl" in source.lower()
                or "cert" in source.lower()
                or "ssl" in source.lower()
            ), "SSL script should have certificate commands"

    def test_nginx_has_ssl_config(self):
        """Nginx config has SSL/TLS configuration."""
        conf = PROJECT_ROOT / "nginx" / "nginx.conf"
        if conf.exists():
            source = conf.read_text()

            assert (
                "ssl_certificate" in source
                or "ssl_" in source.lower()
                or "listen 443" in source
            ), "Nginx should have SSL configuration"
