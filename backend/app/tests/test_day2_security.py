"""
Day 2 Security Fixes — Unit Tests
===================================
Tests for all 12 Day 2 infrastructure & docker hardening fixes:
  F1:  Bind all dev compose ports to 127.0.0.1 only
  F2:  Add Redis password to dev compose
  F3:  Remove default database passwords
  F4:  Remove Prometheus --web.enable-lifecycle
  F5:  Remove port 3000 from production frontend
  F6:  Add healthcheck to Celery worker in production
  F7:  Add non-root USER directives to Dockerfiles
  F8:  Restrict /docs and /openapi.json to internal IPs
  F9:  Add network isolation in dev compose
  F10: Remove Grafana admin default
  F11: Remove --without-heartbeat from Celery worker
  F12: Fix Redis exporter auth
"""

import os
import pytest

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)


def _read(rel_path: str) -> str:
    """Read a file relative to project root."""
    full_path = os.path.join(PROJECT_ROOT, rel_path)
    with open(full_path) as f:
        return f.read()


def _extract_service(content: str, service_key: str) -> str:
    """Extract a service block from docker-compose content by its key (e.g. 'db:')."""
    lines = content.split("\n")
    in_service = False
    service_lines = []
    for line in lines:
        stripped = line.lstrip()
        if not in_service:
            if stripped == service_key and line == "  " + service_key:
                in_service = True
                service_lines.append(line)
                continue
        else:
            # End of service: next 2-space indent key or top-level key
            if (
                line
                and not line.startswith("    ")
                and not line.startswith("#")
                and stripped
            ):
                break
            service_lines.append(line)
    return "\n".join(service_lines)


# ============================================================
# F1: Bind all dev compose ports to 127.0.0.1 only
# ============================================================


class TestF1DevPortsBindToLocalhost:
    """All exposed ports in docker-compose.yml must be bound to 127.0.0.1."""

    def test_postgres_port_localhost(self):
        content = _read("docker-compose.yml")
        assert (
            '"127.0.0.1:5432:5432"' in content
        ), "PostgreSQL port must be bound to 127.0.0.1"

    def test_redis_port_localhost(self):
        content = _read("docker-compose.yml")
        assert (
            '"127.0.0.1:6379:6379"' in content
        ), "Redis port must be bound to 127.0.0.1"

    def test_backend_port_localhost(self):
        content = _read("docker-compose.yml")
        assert (
            '"127.0.0.1:8000:8000"' in content
        ), "Backend port must be bound to 127.0.0.1"

    def test_frontend_port_localhost(self):
        content = _read("docker-compose.yml")
        assert (
            '"127.0.0.1:3000:3000"' in content
        ), "Frontend port must be bound to 127.0.0.1"

    def test_no_unbound_ports_in_dev(self):
        """F1: No bare PORT:PORT patterns without 127.0.0.1 binding."""
        import re

        content = _read("docker-compose.yml")
        # Match lines like "    - '5432:5432'" that are NOT 127.0.0.1 bound
        port_pattern = re.compile(r'^\s+-\s+"([^"]+)"', re.MULTILINE)
        for match in port_pattern.finditer(content):
            port_val = match.group(1)
            # Skip if it's already bound to 127.0.0.1 or is a non-port config
            if port_val.startswith("127.0.0.1:"):
                continue
            # Check if it looks like a port mapping (contains colon and
            # numbers)
            if re.match(r"^\d+:\d+$", port_val):
                pytest.fail(f"Port '{port_val}' is not bound to 127.0.0.1")


# ============================================================
# F2: Add Redis password to dev compose
# ============================================================


class TestF2RedisPasswordDev:
    """Redis service in dev compose must require a password."""

    def test_redis_has_requirepass_command(self):
        content = _read("docker-compose.yml")
        assert (
            "redis-server --requirepass" in content
        ), "Redis must use --requirepass in dev compose"

    def test_redis_healthcheck_uses_password(self):
        content = _read("docker-compose.yml")
        # After the redis requirepass fix, healthcheck should use -a flag
        assert (
            "redis-cli" in content and "-a" in content
        ), "Redis healthcheck must authenticate with password"

    def test_backend_redis_url_has_password(self):
        content = _read("docker-compose.yml")
        assert (
            "REDIS_URL=redis://:${REDIS_PASSWORD" in content
        ), "Backend REDIS_URL must include password"

    def test_worker_redis_url_has_password(self):
        content = _read("docker-compose.yml")
        # The worker REDIS_URL should also contain password
        lines = content.split("\n")
        redis_url_lines = [item for item in lines if "REDIS_URL" in item]
        for line in redis_url_lines:
            assert (
                "${REDIS_PASSWORD" in line
            ), f"All REDIS_URL entries must include password: {line}"


# ============================================================
# F3: Remove default database passwords
# ============================================================


class TestF3NoDefaultDbPasswords:
    """POSTGRES_PASSWORD must use :? required syntax, not :- defaults."""

    def test_db_service_password_required(self):
        content = _read("docker-compose.yml")
        assert (
            "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}" in content
        ), "db service POSTGRES_PASSWORD must use :? required syntax"

    def test_no_parwa_dev_default(self):
        content = _read("docker-compose.yml")
        assert (
            "POSTGRES_PASSWORD:-parwa_dev" not in content
        ), "POSTGRES_PASSWORD must not have 'parwa_dev' default"

    def test_backend_database_url_required(self):
        content = _read("docker-compose.yml")
        assert (
            "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}" in content
        ), "Backend DATABASE_URL must use required POSTGRES_PASSWORD"

    def test_worker_database_url_required(self):
        content = _read("docker-compose.yml")
        # Both DATABASE_URL entries should use :? syntax
        lines = content.split("\n")
        db_url_lines = [item for item in lines if "DATABASE_URL" in item]
        for line in db_url_lines:
            assert (
                "${POSTGRES_PASSWORD:?" in line
            ), f"DATABASE_URL must use required POSTGRES_PASSWORD: {line}"


# ============================================================
# F4: Remove Prometheus --web.enable-lifecycle
# ============================================================


class TestF4PrometheusLifecycleRemoved:
    """Prometheus must not have --web.enable-lifecycle flag."""

    def test_no_enable_lifecycle(self):
        content = _read("docker-compose.prod.yml")
        assert (
            "--web.enable-lifecycle" not in content
        ), "Prometheus must not have --web.enable-lifecycle flag"


# ============================================================
# F5: Remove port 3000 from production frontend
# ============================================================


class TestF5ProdFrontendNoPort:
    """Production frontend service must not expose ports directly."""

    def test_no_ports_in_frontend_service(self):
        content = _read("docker-compose.prod.yml")
        # Extract the frontend service block (2-space indent key)
        # and verify it doesn't contain a ports: directive
        lines = content.split("\n")
        in_frontend = False
        for line in lines:
            stripped = line.lstrip()
            # Match '  frontend:' at exactly 2-space indent
            if stripped == "frontend:" and line == "  frontend:":
                in_frontend = True
                continue
            if in_frontend:
                # End of frontend block: next 2-space indent key or 0-indent
                # key
                if (
                    line
                    and not line.startswith("    ")
                    and not line.startswith("#")
                    and stripped
                ):
                    break
                if stripped.startswith("ports:"):
                    pytest.fail("Production frontend should not have a ports section")


# ============================================================
# F6: Add healthcheck to Celery worker in production
# ============================================================


class TestF6WorkerHealthcheck:
    """Production worker service must have a healthcheck."""

    def test_worker_has_healthcheck(self):
        content = _read("docker-compose.prod.yml")
        assert (
            "pgrep -f 'backend.worker'" in content
        ), "Worker must have healthcheck with pgrep command"

    def test_worker_healthcheck_celery(self):
        content = _read("docker-compose.prod.yml")
        assert (
            "pgrep -" in content and "backend.worker" in content
        ), "Worker healthcheck must check for backend.worker process"


# ============================================================
# F7: Add non-root USER directives to Dockerfiles
# ============================================================


class TestF7NonRootUsers:
    """Infrastructure Dockerfiles must run as non-root users."""

    def test_nginx_uses_nonroot_user(self):
        content = _read("infra/docker/nginx.Dockerfile")
        assert (
            "USER nginx" in content
        ), "nginx.Dockerfile must have USER nginx directive"

    def test_postgres_uses_nonroot_user(self):
        content = _read("infra/docker/postgres.Dockerfile")
        assert (
            "USER postgres" in content
        ), "postgres.Dockerfile must have USER postgres directive"

    def test_redis_uses_nonroot_user(self):
        content = _read("infra/docker/redis.Dockerfile")
        assert (
            "USER redis" in content
        ), "redis.Dockerfile must have USER redis directive"

    def test_nginx_user_before_cmd(self):
        """USER directive must come before the final standalone CMD."""
        content = _read("infra/docker/nginx.Dockerfile")
        user_pos = content.index("USER nginx")
        # Find CMD that starts at beginning of line (not inside HEALTHCHECK)
        import re

        cmd_matches = list(re.finditer(r"^CMD\b", content, re.MULTILINE))
        assert len(cmd_matches) >= 1, "Must find a standalone CMD directive"
        last_cmd_pos = cmd_matches[-1].start()
        assert (
            user_pos < last_cmd_pos
        ), "USER nginx must appear before CMD in nginx.Dockerfile"

    def test_postgres_user_before_cmd(self):
        """USER directive must come before the final standalone CMD."""
        content = _read("infra/docker/postgres.Dockerfile")
        user_pos = content.index("USER postgres")
        import re

        cmd_matches = list(re.finditer(r"^CMD\b", content, re.MULTILINE))
        assert len(cmd_matches) >= 1, "Must find a standalone CMD directive"
        last_cmd_pos = cmd_matches[-1].start()
        assert (
            user_pos < last_cmd_pos
        ), "USER postgres must appear before CMD in postgres.Dockerfile"

    def test_redis_user_before_cmd(self):
        """USER directive must come before the final standalone CMD."""
        content = _read("infra/docker/redis.Dockerfile")
        user_pos = content.index("USER redis")
        import re

        cmd_matches = list(re.finditer(r"^CMD\b", content, re.MULTILINE))
        assert len(cmd_matches) >= 1, "Must find a standalone CMD directive"
        last_cmd_pos = cmd_matches[-1].start()
        assert (
            user_pos < last_cmd_pos
        ), "USER redis must appear before CMD in redis.Dockerfile"


# ============================================================
# F8: Restrict /docs and /openapi.json to internal IPs
# ============================================================


class TestF8DocsIPRestriction:
    """Nginx must restrict /docs and /openapi.json to private IP ranges."""

    def test_docs_location_has_allow_deny(self):
        content = _read("infra/docker/nginx-default.conf")
        assert "allow 10.0.0.0/8" in content, "nginx config must allow 10.0.0.0/8"
        assert "allow 172.16.0.0/12" in content, "nginx config must allow 172.16.0.0/12"
        assert (
            "allow 192.168.0.0/16" in content
        ), "nginx config must allow 192.168.0.0/16"
        assert "deny all" in content, "nginx config must deny all"

    def test_docs_restricted(self):
        """F8: /docs location must have IP restrictions."""
        content = _read("infra/docker/nginx-default.conf")
        # Find the /docs location block
        lines = content.split("\n")
        in_docs = False
        has_deny_all = False
        for line in lines:
            if "location /docs" in line:
                in_docs = True
                continue
            if in_docs:
                if "}" in line:
                    break
                if "deny all" in line:
                    has_deny_all = True
        assert has_deny_all, "/docs location block must contain 'deny all'"

    def test_openapi_restricted(self):
        """F8: /openapi.json location must have IP restrictions."""
        content = _read("infra/docker/nginx-default.conf")
        lines = content.split("\n")
        in_openapi = False
        has_deny_all = False
        for line in lines:
            if "location /openapi.json" in line:
                in_openapi = True
                continue
            if in_openapi:
                if "}" in line:
                    break
                if "deny all" in line:
                    has_deny_all = True
        assert has_deny_all, "/openapi.json location block must contain 'deny all'"


# ============================================================
# F9: Add network isolation in dev compose
# ============================================================


class TestF9DevNetworkIsolation:
    """Dev compose must define and assign explicit backend and frontend networks."""

    def test_backend_network_defined(self):
        content = _read("docker-compose.yml")
        assert (
            "backend_network:" in content
        ), "docker-compose.yml must define backend_network"

    def test_frontend_network_defined(self):
        content = _read("docker-compose.yml")
        assert (
            "frontend_network:" in content
        ), "docker-compose.yml must define frontend_network"

    def test_backend_network_is_internal(self):
        content = _read("docker-compose.yml")
        assert "internal: true" in content, "backend_network should be internal"

    def test_networks_have_driver_bridge(self):
        content = _read("docker-compose.yml")
        # At least one network should use bridge driver
        assert "driver: bridge" in content, "Networks should use bridge driver"

    def test_db_assigned_to_backend_network(self):
        """F9: db service must be on backend_network only."""
        content = _read("docker-compose.yml")
        service = _extract_service(content, "db:")
        assert (
            "backend_network" in service
        ), "db service must be assigned to backend_network"
        # db should NOT be on frontend_network
        assert (
            "frontend_network" not in service
        ), "db service must not be on frontend_network"

    def test_redis_assigned_to_backend_network(self):
        """F9: redis service must be on backend_network only."""
        content = _read("docker-compose.yml")
        service = _extract_service(content, "redis:")
        assert (
            "backend_network" in service
        ), "redis service must be assigned to backend_network"
        assert (
            "frontend_network" not in service
        ), "redis service must not be on frontend_network"

    def test_backend_assigned_to_both_networks(self):
        """F9: backend service must be on both backend and frontend networks."""
        content = _read("docker-compose.yml")
        service = _extract_service(content, "backend:")
        assert (
            "backend_network" in service
        ), "backend service must be assigned to backend_network"
        assert (
            "frontend_network" in service
        ), "backend service must be assigned to frontend_network"

    def test_worker_assigned_to_backend_network(self):
        """F9: worker service must be on backend_network only."""
        content = _read("docker-compose.yml")
        service = _extract_service(content, "worker:")
        assert (
            "backend_network" in service
        ), "worker service must be assigned to backend_network"
        assert (
            "frontend_network" not in service
        ), "worker service must not be on frontend_network"

    def test_frontend_assigned_to_frontend_network(self):
        """F9: frontend service must be on frontend_network only."""
        content = _read("docker-compose.yml")
        service = _extract_service(content, "frontend:")
        assert (
            "frontend_network" in service
        ), "frontend service must be assigned to frontend_network"
        assert (
            "backend_network" not in service
        ), "frontend service must not be on backend_network"


# ============================================================
# F10: Remove Grafana admin default
# ============================================================


class TestF10GrafanaNoDefaultAdmin:
    """Grafana admin user and password must be required, not default."""

    def test_grafana_admin_required(self):
        content = _read("docker-compose.prod.yml")
        assert (
            "${GRAFANA_ADMIN_USER:?GRAFANA_ADMIN_USER required}" in content
        ), "GRAFANA_ADMIN_USER must use :? required syntax"

    def test_no_grafana_admin_default(self):
        content = _read("docker-compose.prod.yml")
        assert (
            "GRAFANA_ADMIN_USER:-admin" not in content
        ), "GRAFANA_ADMIN_USER must not default to 'admin'"

    def test_grafana_admin_password_required(self):
        """F10: GF_SECURITY_ADMIN_PASSWORD must use :? required syntax."""
        content = _read("docker-compose.prod.yml")
        assert (
            "${GRAFANA_ADMIN_PASSWORD:?GF_SECURITY_ADMIN_PASSWORD must be set}"
            in content
        ), "GF_SECURITY_ADMIN_PASSWORD must use :? required syntax"

    def test_no_grafana_password_default(self):
        """F10: GF_SECURITY_ADMIN_PASSWORD must not use :- default."""
        content = _read("docker-compose.prod.yml")
        assert (
            "GRAFANA_ADMIN_PASSWORD:-" not in content
        ), "GRAFANA_ADMIN_PASSWORD must not have a default value"


# ============================================================
# F11: Remove --without-heartbeat from Celery worker
# ============================================================


class TestF11WorkerHeartbeat:
    """Celery worker must NOT use --without-heartbeat flag."""

    def test_no_without_heartbeat(self):
        content = _read("scripts/run_worker.py")
        assert (
            "--without-heartbeat" not in content
        ), "run_worker.py must not contain --without-heartbeat flag"

    def test_worker_has_queues(self):
        content = _read("scripts/run_worker.py")
        assert "--queues=" in content, "run_worker.py should still have --queues config"


# ============================================================
# F12: Fix Redis exporter auth
# ============================================================


class TestF12RedisExporterAuth:
    """Redis exporter must authenticate with password."""

    def test_redis_exporter_addr_has_password(self):
        content = _read("docker-compose.prod.yml")
        assert (
            "REDIS_ADDR=redis://:${REDIS_PASSWORD}@redis:6379" in content
        ), "Redis exporter REDIS_ADDR must include password"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
