"""
Week 8 Tests: DEPLOY-01 — Docker Compose Production Configuration

Validates docker-compose.prod.yml for:
- All services have non-root users
- Resource limits on all services
- Health checks on all services
- Network isolation (backend_network, monitoring_network are internal)
- Security options (no-new-privileges)
- Correct startup order (depends_on with condition: service_healthy)
- No unnecessary port exposure
"""

import os
import pytest
import yaml


COMPOSE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "docker-compose.prod.yml"
)


def _load_compose():
    """Load docker-compose.prod.yml safely."""
    with open(COMPOSE_PATH, "r") as f:
        return yaml.safe_load(f)


class TestDockerComposeProductionStructure:
    """Validate docker-compose.prod.yml structure and security."""

    def test_compose_file_exists(self):
        """docker-compose.prod.yml must exist."""
        assert os.path.exists(COMPOSE_PATH), "docker-compose.prod.yml not found"

    def test_compose_version(self):
        """docker-compose must use version 3.9+."""
        compose = _load_compose()
        assert compose.get("version", "") == "3.9"

    def test_all_services_have_restart_policy(self):
        """Every service must have restart: always."""
        compose = _load_compose()
        services = compose.get("services", {})
        for name, config in services.items():
            assert config.get("restart") == "always", (
                f"Service '{name}' missing restart: always"
            )

    def test_services_count(self):
        """Should have at least 12 production services."""
        compose = _load_compose()
        services = compose.get("services", {})
        assert len(services) >= 12, f"Expected >= 12 services, got {len(services)}"


class TestNonRootUsers:
    """Verify all containers run as non-root."""

    def test_nginx_non_root_user(self):
        """nginx container must run as nginx user."""
        compose = _load_compose()
        nginx = compose["services"]["nginx"]
        assert nginx.get("image", "").startswith("nginx"), "Wrong nginx image"
        # Check Dockerfile-based nginx has USER directive
        assert "USER nginx" in open(
            os.path.join(os.path.dirname(__file__), "..", "..", "..",
                         "infra", "docker", "nginx.Dockerfile"), "r"
        ).read()

    def test_backend_non_root_in_dockerfile(self):
        """Backend Dockerfile must have USER parwa directive."""
        dockerfile_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "infra", "docker", "backend.Dockerfile"
        )
        content = open(dockerfile_path, "r").read()
        assert "USER parwa" in content, "Backend Dockerfile missing USER parwa"

    def test_prometheus_non_root(self):
        """Prometheus must run as nobody (65534:65534)."""
        compose = _load_compose()
        prom = compose["services"]["prometheus"]
        assert prom.get("user") == "65534:65534", "Prometheus not running as nobody"

    def test_grafana_non_root(self):
        """Grafana must run as grafana user (472:472)."""
        compose = _load_compose()
        grafana = compose["services"]["grafana"]
        assert grafana.get("user") == "472:472", "Grafana not running as grafana user"

    def test_alertmanager_non_root(self):
        """Alertmanager must run as nobody (65534:65534)."""
        compose = _load_compose()
        am = compose["services"]["alertmanager"]
        assert am.get("user") == "65534:65534", "Alertmanager not running as nobody"


class TestResourceLimits:
    """Verify all services have memory resource limits."""

    @pytest.fixture
    def compose(self):
        return _load_compose()

    @pytest.mark.parametrize("service", [
        "db", "redis", "backend", "worker", "mcp", "frontend",
        "prometheus", "grafana", "alertmanager", "nginx",
    ])
    def test_service_has_memory_limit(self, compose, service):
        """Each service must have deploy.resources.limits.memory."""
        svc = compose["services"][service]
        limits = svc.get("deploy", {}).get("resources", {}).get("limits", {})
        assert "memory" in limits, f"'{service}' missing memory limit"

    @pytest.mark.parametrize("service", [
        "db", "redis", "backend", "worker", "frontend",
    ])
    def test_service_has_memory_reservation(self, compose, service):
        """Core services must have memory reservations."""
        svc = compose["services"][service]
        reservations = svc.get("deploy", {}).get("resources", {}).get("reservations", {})
        assert "memory" in reservations, f"'{service}' missing memory reservation"


class TestHealthChecks:
    """Verify all services have health checks."""

    @pytest.fixture
    def compose(self):
        return _load_compose()

    @pytest.mark.parametrize("service", [
        "db", "redis", "backend", "frontend", "mcp",
        "prometheus", "grafana", "alertmanager", "nginx",
    ])
    def test_service_has_healthcheck(self, compose, service):
        """Each service must have a healthcheck defined."""
        svc = compose["services"][service]
        assert "healthcheck" in svc, f"'{service}' missing healthcheck"
        hc = svc["healthcheck"]
        assert "test" in hc, f"'{service}' healthcheck missing test command"
        assert "interval" in hc, f"'{service}' healthcheck missing interval"


class TestNetworkIsolation:
    """Verify network isolation configuration."""

    def test_backend_network_is_internal(self):
        """backend_network must be internal (no external access)."""
        compose = _load_compose()
        nets = compose.get("networks", {})
        assert nets["backend_network"].get("internal") is True

    def test_monitoring_network_is_internal(self):
        """monitoring_network must be internal."""
        compose = _load_compose()
        nets = compose.get("networks", {})
        assert nets["monitoring_network"].get("internal") is True

    def test_frontend_network_not_internal(self):
        """frontend_network must allow external access (for nginx)."""
        compose = _load_compose()
        nets = compose.get("networks", {})
        assert nets["frontend_network"].get("internal") is not True

    def test_three_networks_defined(self):
        """Exactly 3 networks must be defined."""
        compose = _load_compose()
        nets = compose.get("networks", {})
        assert set(nets.keys()) == {
            "backend_network", "frontend_network", "monitoring_network"
        }


class TestSecurityOptions:
    """Verify security options on all services."""

    @pytest.fixture
    def compose(self):
        return _load_compose()

    @pytest.mark.parametrize("service", [
        "db", "redis", "backend", "worker", "mcp", "frontend",
        "prometheus", "grafana", "alertmanager", "nginx",
    ])
    def test_no_new_privileges(self, compose, service):
        """Each service must have security_opt: no-new-privileges:true."""
        svc = compose["services"][service]
        sec_opts = svc.get("security_opt", [])
        assert any("no-new-privileges:true" in str(o) for o in sec_opts), (
            f"'{service}' missing no-new-privileges:true"
        )


class TestStartupOrder:
    """Verify correct startup order with depends_on."""

    def test_backend_depends_on_db_and_redis(self):
        """Backend must wait for DB and Redis to be healthy."""
        compose = _load_compose()
        deps = compose["services"]["backend"].get("depends_on", {})
        assert "db" in deps
        assert "redis" in deps
        assert deps["db"].get("condition") == "service_healthy"
        assert deps["redis"].get("condition") == "service_healthy"

    def test_worker_depends_on_db_and_redis(self):
        """Worker must wait for DB and Redis to be healthy."""
        compose = _load_compose()
        deps = compose["services"]["worker"].get("depends_on", {})
        assert "db" in deps
        assert "redis" in deps

    def test_frontend_depends_on_backend(self):
        """Frontend must wait for backend to be healthy."""
        compose = _load_compose()
        deps = compose["services"]["frontend"].get("depends_on", {})
        assert "backend" in deps
        assert deps["backend"].get("condition") == "service_healthy"

    def test_grafana_depends_on_prometheus(self):
        """Grafana must wait for Prometheus."""
        compose = _load_compose()
        deps = compose["services"]["grafana"].get("depends_on", {})
        assert "prometheus" in deps


class TestPortExposure:
    """Verify minimal port exposure (security)."""

    def test_db_no_port_exposure(self):
        """Database must NOT expose ports externally."""
        compose = _load_compose()
        db = compose["services"]["db"]
        ports = db.get("ports", [])
        assert len(ports) == 0, "DB ports should not be exposed"

    def test_redis_no_port_exposure(self):
        """Redis must NOT expose ports externally."""
        compose = _load_compose()
        redis = compose["services"]["redis"]
        ports = redis.get("ports", [])
        assert len(ports) == 0, "Redis ports should not be exposed"

    def test_backend_no_port_exposure(self):
        """Backend must NOT expose ports (accessed via nginx)."""
        compose = _load_compose()
        backend = compose["services"]["backend"]
        ports = backend.get("ports", [])
        assert len(ports) == 0, "Backend ports should not be exposed"

    def test_nginx_exposes_80_and_443(self):
        """Nginx must expose ports 80 and 443 only."""
        compose = _load_compose()
        nginx = compose["services"]["nginx"]
        ports = nginx.get("ports", [])
        port_strs = [str(p) for p in ports]
        assert any("80" in p for p in port_strs)
        assert any("443" in p for p in port_strs)


class TestVolumesDefined:
    """Verify persistent volumes are defined."""

    def test_volumes_count(self):
        """Should define persistent volumes for data services."""
        compose = _load_compose()
        volumes = compose.get("volumes", {})
        assert "postgres_prod_data" in volumes
        assert "redis_prod_data" in volumes
        assert "prometheus_data" in volumes
        assert "grafana_data" in volumes
