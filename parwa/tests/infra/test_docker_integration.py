#!/usr/bin/env python3
"""
PARWA Day 3 Morning — Docker Integration Tests
Full Docker stack validation: Dockerfiles, compose files, security,
networks, volumes, and service configuration.
"""
import os
import re
import yaml
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCKER_DIR = os.path.join(PROJECT_ROOT, "infra", "docker")
DEV_COMPOSE = os.path.join(PROJECT_ROOT, "docker-compose.yml")
PROD_COMPOSE = os.path.join(PROJECT_ROOT, "docker-compose.prod.yml")


def load_file(path):
    with open(path) as f:
        return f.read()


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# 1. Dockerfile paths exist and COPY sources are valid
# ---------------------------------------------------------------------------
class TestDockerfileValidity:
    """All Dockerfile paths must exist and reference valid COPY sources."""

    DOCKERFILES = [
        "backend.Dockerfile",
        "worker.Dockerfile",
        "mcp.Dockerfile",
        "frontend.Dockerfile",
        "frontend.prod.Dockerfile",
        "nginx.Dockerfile",
        "redis.Dockerfile",
        "postgres.Dockerfile",
        "backup.Dockerfile",
    ]

    def test_all_dockerfiles_exist(self):
        """All expected Dockerfiles must exist in infra/docker/."""
        for name in self.DOCKERFILES:
            path = os.path.join(DOCKER_DIR, name)
            assert os.path.isfile(path), f"Dockerfile missing: {name}"

    @pytest.mark.parametrize("dockerfile", DOCKERFILES)
    def test_dockerfile_copy_sources_exist(self, dockerfile):
        """COPY source files referenced in Dockerfiles must exist relative to build context."""
        path = os.path.join(DOCKER_DIR, dockerfile)
        content = load_file(path)
        # Parse COPY instructions: COPY [--flag...] <src>... <dest>
        # Skip --from= lines (multi-stage build copies from another stage)
        for line in content.split('\n'):
            stripped = line.strip()
            if not stripped.upper().startswith('COPY '):
                continue
            # Skip multi-stage COPY --from=
            if '--from=' in stripped:
                continue
            # Remove COPY keyword and split
            parts = stripped[5:].split()
            # Filter out flags (start with --)
            non_flag_parts = [p for p in parts if not p.startswith('--')]
            if len(non_flag_parts) < 2:
                continue  # Malformed COPY, skip
            # All but the last are sources, last is destination
            sources = non_flag_parts[:-1]
            for src in sources:
                # Skip glob patterns and absolute paths
                if '*' in src or src.startswith('/'):
                    continue
                # Check relative to project root (the build context)
                src_path = os.path.join(PROJECT_ROOT, src)
                assert os.path.exists(src_path), \
                    f"{dockerfile}: COPY source '{src}' does not exist (line: {stripped})"


# ---------------------------------------------------------------------------
# 2-4. Compose file parsing and deprecation checks
# ---------------------------------------------------------------------------
class TestComposeParsing:
    """Docker Compose files must parse as valid YAML and avoid deprecated keys."""

    def test_dev_compose_parses(self):
        """docker-compose.yml (dev) parses as valid YAML."""
        data = load_yaml(DEV_COMPOSE)
        assert "services" in data, "Dev compose missing 'services' key"

    def test_prod_compose_parses(self):
        """docker-compose.prod.yml parses as valid YAML."""
        data = load_yaml(PROD_COMPOSE)
        assert "services" in data, "Prod compose missing 'services' key"

    def test_no_deprecated_version_key_in_dev(self):
        """Dev compose should not have deprecated 'version: "3.9"' (Docker Compose V2)."""
        content = load_file(DEV_COMPOSE)
        # version: "3.9" or version: '3.9' is deprecated in Compose V2
        assert not re.search(r'^version:\s*["\']?3\.9["\']?', content, re.MULTILINE), \
            "Dev compose uses deprecated 'version: \"3.9\"' — remove for Compose V2"

    def test_no_deprecated_version_key_in_prod(self):
        """Prod compose should not have deprecated 'version: "3.9"' (Docker Compose V2)."""
        content = load_file(PROD_COMPOSE)
        assert not re.search(r'^version:\s*["\']?3\.9["\']?', content, re.MULTILINE), \
            "Prod compose uses deprecated 'version: \"3.9\"' — remove for Compose V2"


# ---------------------------------------------------------------------------
# 5. Health checks on prod services
# ---------------------------------------------------------------------------
class TestProdHealthChecks:
    """All production services must have health checks (except exporters, node-exporter)."""

    EXEMPT_SERVICES = {"redis-exporter", "postgres-exporter", "node-exporter"}

    def test_all_prod_services_have_health_checks(self):
        """Services in prod compose must define healthcheck, except exporters/node-exporter."""
        data = load_yaml(PROD_COMPOSE)
        for svc_name, svc_config in data["services"].items():
            if svc_name in self.EXEMPT_SERVICES:
                continue
            assert "healthcheck" in svc_config, \
                f"Prod service '{svc_name}' is missing a healthcheck"


# ---------------------------------------------------------------------------
# 6-8. Security: Redis auth, PostgreSQL auth, Nginx
# ---------------------------------------------------------------------------
class TestProdSecurity:
    """Production compose must enforce auth on data stores and include nginx."""

    def test_redis_requires_auth_in_prod(self):
        """Redis must require authentication in prod (REDIS_PASSWORD in command)."""
        data = load_yaml(PROD_COMPOSE)
        redis = data["services"]["redis"]
        command = redis.get("command", "")
        if isinstance(command, list):
            command = " ".join(command)
        assert "REDIS_PASSWORD" in command or "requirepass" in command, \
            "Redis in prod compose does not require authentication"

    def test_postgresql_requires_auth_in_prod(self):
        """PostgreSQL must require authentication in prod (POSTGRES_PASSWORD env)."""
        data = load_yaml(PROD_COMPOSE)
        db = data["services"]["db"]
        env = db.get("environment", {})
        # Can be dict or list of strings
        if isinstance(env, dict):
            assert "POSTGRES_PASSWORD" in env, \
                "PostgreSQL in prod compose missing POSTGRES_PASSWORD"
        elif isinstance(env, list):
            assert any("POSTGRES_PASSWORD" in str(e) for e in env), \
                "PostgreSQL in prod compose missing POSTGRES_PASSWORD"

    def test_nginx_configured_in_prod(self):
        """Nginx must be configured in prod compose."""
        data = load_yaml(PROD_COMPOSE)
        assert "nginx" in data["services"], \
            "Nginx service not found in prod compose"


# ---------------------------------------------------------------------------
# 9. Backup service is NOT in Docker Compose
# ---------------------------------------------------------------------------
class TestBackupNotInCompose:
    """Backup runs as a K8s CronJob, not as a Docker Compose service."""

    def test_backup_service_not_in_dev_compose(self):
        """Dev compose must not contain a backup service."""
        data = load_yaml(DEV_COMPOSE)
        assert "backup" not in data["services"], \
            "Backup service should NOT be in dev compose (it's a K8s CronJob)"

    def test_backup_service_not_in_prod_compose(self):
        """Prod compose must not contain a backup service."""
        data = load_yaml(PROD_COMPOSE)
        assert "backup" not in data["services"], \
            "Backup service should NOT be in prod compose (it's a K8s CronJob)"


# ---------------------------------------------------------------------------
# 10. Named volumes (not relative paths)
# ---------------------------------------------------------------------------
class TestNamedVolumes:
    """All volumes in prod compose must be named (not relative host paths)."""

    def test_prod_data_volumes_are_named(self):
        """Volume mounts for data persistence must use named volumes, not relative paths."""
        data = load_yaml(PROD_COMPOSE)
        data_services = ["db", "redis", "backend", "worker", "prometheus", "grafana", "alertmanager"]
        for svc_name in data_services:
            if svc_name not in data["services"]:
                continue
            svc = data["services"][svc_name]
            volumes = svc.get("volumes", [])
            for vol in volumes:
                if isinstance(vol, str) and ":" in vol:
                    host_part = vol.split(":")[0]
                    # Named volumes don't start with ./ or / or contain ..
                    if host_part.startswith("./") or host_part.startswith("/"):
                        # Allow read-only config mounts (e.g., ./monitoring/...)
                        if vol.endswith(":ro"):
                            continue
                        # Relative path data volumes are a risk
                        assert False, \
                            f"Service '{svc_name}' uses relative/absolute host path for volume: {vol}"


# ---------------------------------------------------------------------------
# 11. Logging limits
# ---------------------------------------------------------------------------
class TestLoggingLimits:
    """Production services should have logging limits configured."""

    def test_prod_services_have_logging_config(self):
        """Check whether prod compose services have logging limits (informational)."""
        data = load_yaml(PROD_COMPOSE)
        services_without_logging = []
        for svc_name, svc_config in data["services"].items():
            if "logging" not in svc_config:
                services_without_logging.append(svc_name)
        # This is an informational test — logging limits are best practice
        # but may be set at the Docker daemon level instead
        if services_without_logging:
            pytest.skip(
                f"Services without logging config: {', '.join(services_without_logging)} "
                "(may be set at daemon level)"
            )


# ---------------------------------------------------------------------------
# 12. Network isolation
# ---------------------------------------------------------------------------
class TestNetworkIsolation:
    """Networks must be properly isolated in prod compose."""

    def test_backend_network_is_internal(self):
        """backend_network must be internal (not externally accessible)."""
        data = load_yaml(PROD_COMPOSE)
        networks = data.get("networks", {})
        backend_net = networks.get("backend_network", {})
        assert backend_net.get("internal") is True, \
            "backend_network must be marked as internal: true"

    def test_monitoring_network_is_internal(self):
        """monitoring_network must be internal (not externally accessible)."""
        data = load_yaml(PROD_COMPOSE)
        networks = data.get("networks", {})
        monitoring_net = networks.get("monitoring_network", {})
        assert monitoring_net.get("internal") is True, \
            "monitoring_network must be marked as internal: true"

    def test_frontend_network_is_not_internal(self):
        """frontend_network must NOT be internal (needs external access for nginx)."""
        data = load_yaml(PROD_COMPOSE)
        networks = data.get("networks", {})
        frontend_net = networks.get("frontend_network", {})
        # frontend_network should not have internal: true
        assert frontend_net.get("internal") is not True, \
            "frontend_network should NOT be internal (nginx needs external access)"
