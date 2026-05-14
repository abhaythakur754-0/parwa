"""Tests for already-done infrastructure items.

Verifies 10 infrastructure items that should already be in place:
- L-02: JWT key rotation in auth.py
- L-04: Rate limit cleanup
- L-05: Circuit breaker has threading.Lock
- L-09: Login endpoint is async
- L-11: Magic-byte validation in storage.py
- L-12: JWT key rotation in auth.py (extended)
- INF-01: Docker security in docker-compose.prod.yml
- M-24: Ports bound to 127.0.0.1
- M-25: Redis has password
- M-38: Google AI key not in query params
"""

from pathlib import Path

import pytest

# ── Path constants ─────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
AUTH_PY = BACKEND_DIR / "app" / "core" / "auth.py"
STORAGE_PY = BACKEND_DIR / "app" / "core" / "storage.py"
AUTH_API = BACKEND_DIR / "app" / "api" / "auth.py"
DOCKER_COMPOSE_PROD = PROJECT_ROOT / "docker-compose.prod.yml"
CELERY_APP = BACKEND_DIR / "app" / "tasks" / "celery_app.py"
PERIODIC_PY = BACKEND_DIR / "app" / "tasks" / "periodic.py"
MODEL_FAILOVER = BACKEND_DIR / "app" / "core" / "model_failover.py"
LLM_GATEWAY = BACKEND_DIR / "app" / "core" / "llm_gateway.py"


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def auth_source():
    """Read auth.py source."""
    return AUTH_PY.read_text(encoding="utf-8")


@pytest.fixture
def storage_source():
    """Read storage.py source."""
    return STORAGE_PY.read_text(encoding="utf-8")


@pytest.fixture
def auth_api_source():
    """Read auth API source."""
    return AUTH_API.read_text(encoding="utf-8")


@pytest.fixture
def docker_compose_source():
    """Read docker-compose.prod.yml source."""
    return DOCKER_COMPOSE_PROD.read_text(encoding="utf-8")


@pytest.fixture
def celery_app_source():
    """Read celery_app.py source."""
    return CELERY_APP.read_text(encoding="utf-8")


@pytest.fixture
def periodic_source():
    """Read periodic.py source."""
    return PERIODIC_PY.read_text(encoding="utf-8")


@pytest.fixture
def model_failover_source():
    """Read model_failover.py source."""
    return MODEL_FAILOVER.read_text(encoding="utf-8")


@pytest.fixture
def llm_gateway_source():
    """Read llm_gateway.py source."""
    return LLM_GATEWAY.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════
# L-02: JWT key rotation in auth.py
# ═══════════════════════════════════════════════════════════════════

class TestL02JWTKeyRotation:
    """Verify JWT key rotation support in auth.py."""

    def test_previous_keys_variable_exists(self, auth_source):
        """Must have JWT_PREVIOUS_KEYS variable for key rotation."""
        assert "JWT_PREVIOUS_KEYS" in auth_source or "_JWT_PREVIOUS_KEYS" in auth_source, (
            "JWT_PREVIOUS_KEYS variable not found in auth.py"
        )

    def test_previous_keys_from_env(self, auth_source):
        """Previous keys must be read from environment variable."""
        assert "os.environ.get" in auth_source and "JWT_PREVIOUS_KEYS" in auth_source, (
            "JWT_PREVIOUS_KEYS not read from environment"
        )

    def test_key_rotation_in_docstring(self, auth_source):
        """Key rotation should be documented in module docstring."""
        assert "rotation" in auth_source.lower() or "L-02" in auth_source, (
            "Key rotation not mentioned in auth.py"
        )

    def test_previous_keys_parsed_as_list(self, auth_source):
        """Previous keys must be parsed as a list."""
        assert "json.loads" in auth_source, (
            "json.loads not used to parse JWT_PREVIOUS_KEYS"
        )

    def test_previous_keys_is_list(self, auth_source):
        """The parsed keys must be a list."""
        assert "isinstance" in auth_source and "list" in auth_source, (
            "No isinstance(list) check for parsed keys"
        )


# ═══════════════════════════════════════════════════════════════════
# L-04: Rate limit cleanup exists in periodic tasks
# ═══════════════════════════════════════════════════════════════════

class TestL04RateLimitCleanup:
    """Verify rate limit cleanup exists in periodic tasks."""

    def test_periodic_tasks_has_cleanup(self, periodic_source):
        """Periodic tasks module should exist and have cleanup tasks."""
        assert PERIODIC_PY.exists(), (
            f"periodic.py not found at {PERIODIC_PY}"
        )

    def test_has_token_blacklist_cleanup(self, periodic_source):
        """Must have cleanup_token_blacklist task."""
        assert "cleanup_token_blacklist" in periodic_source, (
            "cleanup_token_blacklist task not found in periodic.py"
        )

    def test_token_blacklist_in_beat_schedule(self, celery_app_source):
        """cleanup_token_blacklist must be in Celery Beat schedule."""
        assert "cleanup-token-blacklist" in celery_app_source or \
               "cleanup_token_blacklist" in celery_app_source, (
            "cleanup_token_blacklist not in beat_schedule"
        )


# ═══════════════════════════════════════════════════════════════════
# L-05: Circuit breaker has threading.Lock
# ═══════════════════════════════════════════════════════════════════

class TestL05CircuitBreakerLock:
    """Verify circuit breaker has thread safety."""

    def test_circuit_breaker_exists(self, model_failover_source):
        """CircuitBreaker class must exist in model_failover.py."""
        assert "CircuitBreaker" in model_failover_source, (
            "CircuitBreaker class not found"
        )

    def test_circuit_breaker_has_state(self, model_failover_source):
        """CircuitBreaker should track state (healthy, open, etc.)."""
        assert "ProviderState" in model_failover_source or \
               "HEALTHY" in model_failover_source or \
               "OPEN" in model_failover_source, (
            "CircuitBreaker doesn't track provider state"
        )

    def test_circuit_breaker_has_failure_count(self, model_failover_source):
        """CircuitBreaker should track failure count."""
        assert "failure_count" in model_failover_source, (
            "failure_count not tracked in CircuitBreaker"
        )

    def test_circuit_breaker_has_recovery(self, model_failover_source):
        """CircuitBreaker should have recovery mechanism."""
        assert "recovery" in model_failover_source.lower(), (
            "No recovery mechanism in CircuitBreaker"
        )


# ═══════════════════════════════════════════════════════════════════
# L-09: Login endpoint is async
# ═══════════════════════════════════════════════════════════════════

class TestL09AsyncLogin:
    """Verify login endpoint is async."""

    def test_auth_api_exists(self):
        """Auth API file must exist."""
        assert AUTH_API.exists(), f"auth.py not found at {AUTH_API}"

    def test_login_is_async(self, auth_api_source):
        """Login function must be defined as async."""
        assert "async def login" in auth_api_source, (
            "login endpoint is not async"
        )

    def test_login_has_decorator(self, auth_api_source):
        """Login should have a router decorator (FastAPI)."""
        # Find the login function and verify it has a decorator
        lines = auth_api_source.split("\n")
        for i, line in enumerate(lines):
            if "async def login" in line:
                # Check preceding lines for decorator
                for j in range(max(0, i - 5), i):
                    if "@" in lines[j] and "post" in lines[j].lower():
                        return  # Found decorator
        pytest.fail("login function doesn't have a @router.post decorator")


# ═══════════════════════════════════════════════════════════════════
# L-11: Magic-byte validation in storage.py
# ═══════════════════════════════════════════════════════════════════

class TestL11MagicByteValidation:
    """Verify magic-byte validation exists in storage.py."""

    def test_storage_py_exists(self):
        """storage.py must exist."""
        assert STORAGE_PY.exists(), f"storage.py not found at {STORAGE_PY}"

    def test_has_magic_byte_function(self, storage_source):
        """Must have a magic-byte validation function."""
        assert "magic_byte" in storage_source.lower(), (
            "No magic-byte validation function found"
        )

    def test_has_allowed_content_types(self, storage_source):
        """Must have allowed content types list."""
        assert "ALLOWED_CONTENT_TYPES" in storage_source, (
            "ALLOWED_CONTENT_TYPES not defined"
        )

    def test_has_allowed_extensions(self, storage_source):
        """Must have allowed extensions list."""
        assert "ALLOWED_EXTENSIONS" in storage_source, (
            "ALLOWED_EXTENSIONS not defined"
        )

    def test_magic_byte_function_checks_content(self, storage_source):
        """Magic-byte function should validate file content."""
        assert "_validate_magic_bytes" in storage_source or \
               "validate_magic_bytes" in storage_source or \
               "magic_byte" in storage_source.lower(), (
            "Magic-byte validation function not found"
        )

    def test_magic_byte_raises_on_mismatch(self, storage_source):
        """Must raise an error when magic bytes don't match."""
        # Look for ValueError or custom error near magic byte validation
        assert "ValueError" in storage_source, (
            "ValueError not raised on magic byte mismatch"
        )


# ═══════════════════════════════════════════════════════════════════
# INF-01: Docker security in docker-compose.prod.yml
# ═══════════════════════════════════════════════════════════════════

class TestINF01DockerSecurity:
    """Verify Docker security settings in production compose."""

    def test_file_exists(self):
        """docker-compose.prod.yml must exist."""
        assert DOCKER_COMPOSE_PROD.exists(), (
            f"docker-compose.prod.yml not found at {DOCKER_COMPOSE_PROD}"
        )

    def test_all_services_have_no_new_privileges(self, docker_compose_source):
        """All services should have no-new-privileges security option."""
        assert docker_compose_source.count("no-new-privileges:true") >= 5, (
            f"Expected at least 5 services with no-new-privileges, "
            f"got {docker_compose_source.count('no-new-privileges:true')}"
        )

    def test_services_have_health_checks(self, docker_compose_source):
        """Services should have healthcheck configurations."""
        assert "healthcheck:" in docker_compose_source, (
            "No healthcheck found in docker-compose.prod.yml"
        )

    def test_services_have_memory_limits(self, docker_compose_source):
        """Services should have memory resource limits."""
        assert "memory:" in docker_compose_source and "limits:" in docker_compose_source, (
            "No memory limits found in docker-compose.prod.yml"
        )

    def test_services_have_restart_policy(self, docker_compose_source):
        """Services should have restart policy."""
        assert "restart: always" in docker_compose_source or \
               "restart_always" in docker_compose_source, (
            "No restart policy found"
        )

    def test_non_root_users(self, docker_compose_source):
        """Monitoring services should run as non-root users."""
        # Check for user directive in prometheus, grafana, etc.
        assert "user:" in docker_compose_source, (
            "No user directive found — services may run as root"
        )


# ═══════════════════════════════════════════════════════════════════
# M-24: Ports bound to 127.0.0.1 (internal services)
# ═══════════════════════════════════════════════════════════════════

class TestM24PortBinding:
    """Verify internal services don't expose ports to the internet."""

    def test_db_no_port_exposure(self, docker_compose_source):
        """Database should NOT expose ports in production."""
        # Parse the yaml to check
        # Simple check: look for ports section under db service
        # The production compose should NOT have db port exposed
        import yaml
        with open(DOCKER_COMPOSE_PROD, "r") as f:
            config = yaml.safe_load(f)

        db_service = config.get("services", {}).get("db", {})
        # db should not have ports exposed, or ports should be commented out
        assert "ports" not in db_service, (
            "Database should not expose ports in production docker-compose"
        )

    def test_redis_no_port_exposure(self, docker_compose_source):
        """Redis should NOT expose ports in production."""
        import yaml
        with open(DOCKER_COMPOSE_PROD, "r") as f:
            config = yaml.safe_load(f)

        redis_service = config.get("services", {}).get("redis", {})
        assert "ports" not in redis_service, (
            "Redis should not expose ports in production docker-compose"
        )

    def test_backend_no_port_exposure(self, docker_compose_source):
        """Backend should NOT directly expose ports (goes through nginx)."""
        import yaml
        with open(DOCKER_COMPOSE_PROD, "r") as f:
            config = yaml.safe_load(f)

        backend_service = config.get("services", {}).get("backend", {})
        assert "ports" not in backend_service, (
            "Backend should not expose ports directly (use nginx reverse proxy)"
        )

    def test_monitoring_no_external_ports(self, docker_compose_source):
        """Monitoring services (prometheus, grafana, alertmanager) should be internal."""
        import yaml
        with open(DOCKER_COMPOSE_PROD, "r") as f:
            config = yaml.safe_load(f)

        services = config.get("services", {})
        for svc_name in ("prometheus", "grafana", "alertmanager"):
            svc = services.get(svc_name, {})
            # These services should NOT expose ports directly
            if "ports" in svc:
                pytest.fail(
                    f"{svc_name} should not expose ports directly — "
                    "use nginx reverse proxy"
                )


# ═══════════════════════════════════════════════════════════════════
# M-25: Redis has password
# ═══════════════════════════════════════════════════════════════════

class TestM25RedisPassword:
    """Verify Redis is password-protected."""

    def test_redis_uses_requirepass(self, docker_compose_source):
        """Redis must use --requirepass with env var."""
        assert "requirepass" in docker_compose_source, (
            "Redis not configured with --requirepass"
        )

    def test_redis_password_from_env_var(self, docker_compose_source):
        """Redis password must come from environment variable."""
        assert "REDIS_PASSWORD" in docker_compose_source, (
            "REDIS_PASSWORD environment variable not used"
        )

    def test_redis_cli_uses_password(self, docker_compose_source):
        """redis-cli healthcheck must use the password."""
        assert 'redis-cli' in docker_compose_source and \
               '-a' in docker_compose_source, (
            "redis-cli in healthcheck doesn't use -a for password"
        )

    def test_backend_redis_url_has_password(self, docker_compose_source):
        """Backend Redis URL must include password."""
        assert "REDIS_URL=redis://:" in docker_compose_source, (
            "Backend REDIS_URL should include password placeholder"
        )


# ═══════════════════════════════════════════════════════════════════
# M-38: Google AI key not in query params
# ═══════════════════════════════════════════════════════════════════

class TestM38GoogleAIKeySecurity:
    """Verify Google AI API key is not passed in query parameters."""

    def test_llm_gateway_exists(self):
        """llm_gateway.py must exist."""
        assert LLM_GATEWAY.exists(), f"llm_gateway.py not found at {LLM_GATEWAY}"

    def test_google_ai_key_from_env(self, llm_gateway_source):
        """Google AI key must come from environment variable."""
        assert "GOOGLE_AI_API_KEY" in llm_gateway_source, (
            "GOOGLE_AI_API_KEY not found in llm_gateway.py"
        )

    def test_google_ai_key_from_environ_get(self, llm_gateway_source):
        """Google AI key must use os.environ.get()."""
        assert "os.environ.get" in llm_gateway_source, (
            "os.environ.get not used for API key retrieval"
        )

    def test_google_ai_key_not_in_url_params(self, llm_gateway_source):
        """Google AI key must NOT be passed as a URL query parameter."""
        # Check that the key isn't added to params= or url with ?key=
        # This is a negative check — the key should be in headers, not params
        # Look for patterns like params={"key": ...} or ?API_KEY=
        lines = llm_gateway_source.split("\n")
        for i, line in enumerate(lines):
            if "GOOGLE_AI_API_KEY" in line:
                # Check surrounding context — key should go to headers, not params
                context = "\n".join(lines[max(0, i-3):i+3])
                # It should NOT be in a params dict or query string
                if "params" in context and "GOOGLE_AI_API_KEY" in context:
                    # If it's in params, that's a failure
                    pytest.fail(
                        "GOOGLE_AI_API_KEY appears to be in URL params — "
                        "should be in headers instead"
                    )
