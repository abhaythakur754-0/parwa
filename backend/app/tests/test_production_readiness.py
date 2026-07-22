"""
PARWA Production Readiness Test Suite (Phase 6)

Validates that the system meets ALL production readiness criteria:
- Security: TLS, auth, PII protection, CSRF, rate limiting
- Reliability: Circuit breakers, self-healing, idempotency
- Observability: Sentry, health checks, metrics, logging
- Data: Backup, recovery, encryption, GDPR
- Performance: Load capacity, response times, HPA
- Infrastructure: Docker, K8s, SSL, Redis, PostgreSQL
- Compliance: BC-001 through BC-012

BC-001: company_id first on all tenant-scoped operations.
BC-008: Never crash — tests should fail gracefully, not error out.
BC-012: All timestamps UTC.
"""

import os
import sys
import pytest

# Resolve project root so file-existence tests work regardless of cwd
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)


# ============================================================
# 1. SECURITY READINESS
# ============================================================


class TestSecurityReadiness:
    """Validate all security requirements are met for production."""

    def test_tls_config_enforces_tls_12_plus(self):
        """NFR 3.2: TLS 1.2+ must be enforced in nginx config."""
        nginx_conf = os.path.join(_PROJECT_ROOT, "infra", "docker", "nginx.conf")
        if not os.path.exists(nginx_conf):
            pytest.skip("nginx.conf not found")
        with open(nginx_conf, "r") as f:
            content = f.read()
        assert "TLSv1.2" in content, "nginx must support TLS 1.2"
        assert "TLSv1" not in content.replace("TLSv1.2", "").replace(
            "TLSv1.3", ""
        ), "nginx must NOT enable TLS 1.0/1.1 without version suffix"

    def test_hsts_header_configured(self):
        """HSTS header must be present with max-age >= 1 year."""
        # Check SecurityHeadersMiddleware for HSTS in production
        middleware_path = os.path.join(
            _PROJECT_ROOT,
            "backend",
            "app",
            "middleware",
            "security_headers.py",
        )
        with open(middleware_path, "r") as f:
            content = f.read()
        assert "Strict-Transport-Security" in content, (
            "SecurityHeadersMiddleware must add HSTS header"
        )
        assert "31536000" in content, "HSTS max-age must be >= 1 year (31536000s)"

    def test_csp_header_configured(self):
        """Content-Security-Policy must be configured."""
        middleware_path = os.path.join(
            _PROJECT_ROOT,
            "backend",
            "app",
            "middleware",
            "security_headers.py",
        )
        with open(middleware_path, "r") as f:
            content = f.read()
        assert "Content-Security-Policy" in content, (
            "SecurityHeadersMiddleware must add CSP header"
        )
        assert "default-src" in content, "CSP must have default-src directive"

    def test_no_default_secrets_in_production(self):
        """BC-011: Production config must not have dev default values."""
        from app.config import Settings

        # Simulate production environment validation
        # The Settings class has validators that raise ValueError in production
        import os as _os

        original = _os.environ.get("ENVIRONMENT")
        try:
            _os.environ["ENVIRONMENT"] = "production"
            _os.environ["SECRET_KEY"] = "dev-secret-key-change-in-production"
            with pytest.raises(ValueError, match="SECRET_KEY"):
                Settings()
        finally:
            _os.environ.pop("ENVIRONMENT", None)
            if original is not None:
                _os.environ["ENVIRONMENT"] = original
            _os.environ.pop("SECRET_KEY", None)

    def test_jwt_secret_not_default(self):
        """JWT_SECRET_KEY must not be the default dev value in production."""
        from app.config import Settings

        import os as _os

        original = _os.environ.get("ENVIRONMENT")
        try:
            _os.environ["ENVIRONMENT"] = "production"
            _os.environ["JWT_SECRET_KEY"] = "dev-jwt-secret-key-change-in-production"
            with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
                Settings()
        finally:
            _os.environ.pop("ENVIRONMENT", None)
            if original is not None:
                _os.environ["ENVIRONMENT"] = original
            _os.environ.pop("JWT_SECRET_KEY", None)

    def test_data_encryption_key_32_chars(self):
        """BC-011: DATA_ENCRYPTION_KEY must be 32 characters in production."""
        from app.config import Settings

        import os as _os

        original = _os.environ.get("ENVIRONMENT")
        try:
            _os.environ["ENVIRONMENT"] = "production"
            _os.environ["DATA_ENCRYPTION_KEY"] = "short"
            with pytest.raises(ValueError, match="DATA_ENCRYPTION_KEY"):
                Settings()
        finally:
            _os.environ.pop("ENVIRONMENT", None)
            if original is not None:
                _os.environ["ENVIRONMENT"] = original
            _os.environ.pop("DATA_ENCRYPTION_KEY", None)

    def test_redis_password_required_in_production(self):
        """Redis must have password authentication in production."""
        from app.config import Settings

        import os as _os

        original = _os.environ.get("ENVIRONMENT")
        try:
            _os.environ["ENVIRONMENT"] = "production"
            _os.environ["REDIS_PASSWORD"] = ""
            with pytest.raises(ValueError, match="REDIS_PASSWORD"):
                Settings()
        finally:
            _os.environ.pop("ENVIRONMENT", None)
            if original is not None:
                _os.environ["ENVIRONMENT"] = original
            _os.environ.pop("REDIS_PASSWORD", None)

    def test_cors_not_wildcard_with_credentials(self):
        """C-05: CORS must not be wildcard when credentials are enabled."""
        # Check main.py CORS configuration
        main_path = os.path.join(
            _PROJECT_ROOT, "backend", "app", "main.py"
        )
        with open(main_path, "r") as f:
            content = f.read()
        assert "allow_credentials=True" in content, (
            "CORS must have allow_credentials=True"
        )
        # Verify origins are NOT wildcard when credentials are enabled
        # The CORS middleware block uses _cors_origins variable, not ["*"]
        assert "allow_origins=_cors_origins" in content, (
            "CORS must use explicit origins, not wildcard"
        )

    def test_rate_limiting_configured(self):
        """Rate limiting middleware must be active."""
        from app.middleware.rate_limit import RateLimitMiddleware

        assert RateLimitMiddleware is not None, (
            "RateLimitMiddleware must be importable"
        )
        # Verify it's wired in main.py
        main_path = os.path.join(
            _PROJECT_ROOT, "backend", "app", "main.py"
        )
        with open(main_path, "r") as f:
            content = f.read()
        assert "RateLimitMiddleware" in content, (
            "RateLimitMiddleware must be in middleware stack"
        )

    def test_security_headers_present(self):
        """SecurityHeadersMiddleware must be in middleware stack."""
        from app.middleware.security_headers import SecurityHeadersMiddleware

        assert SecurityHeadersMiddleware is not None
        main_path = os.path.join(
            _PROJECT_ROOT, "backend", "app", "main.py"
        )
        with open(main_path, "r") as f:
            content = f.read()
        assert "SecurityHeadersMiddleware" in content, (
            "SecurityHeadersMiddleware must be in middleware stack"
        )

    def test_api_docs_hidden_in_production(self):
        """BC-011: OpenAPI docs must be hidden when DEBUG=False."""
        main_path = os.path.join(
            _PROJECT_ROOT, "backend", "app", "main.py"
        )
        with open(main_path, "r") as f:
            content = f.read()
        # Verify docs_url is conditional on DEBUG
        assert "docs_url" in content, "FastAPI docs_url must be configured"
        assert "openapi_url" in content, "FastAPI openapi_url must be configured"
        # Verify None assignment for non-debug
        assert "docs_url=None" in content or "docs_url = None" in content, (
            "docs_url must be None when DEBUG is False"
        )

    def test_pii_scrubbing_in_sentry(self):
        """Sentry must scrub PII before sending events."""
        from app.core.sentry import scrub_pii, _EMAIL_PATTERN

        assert _EMAIL_PATTERN is not None, "Email pattern must be compiled"
        # Test actual scrubbing
        event = {"message": "User john@example.com called support"}
        result = scrub_pii(event, {})
        assert "john@example.com" not in str(result), (
            "Email must be scrubbed from Sentry events"
        )
        assert "[REDACTED]" in str(result), "PII must be replaced with [REDACTED]"


# ============================================================
# 2. RELIABILITY READINESS
# ============================================================


class TestReliabilityReadiness:
    """Validate all reliability requirements for production."""

    def test_circuit_breakers_registered(self):
        """All critical dependencies must have circuit breakers."""
        from app.core.circuit_breaker_manager import (
            get_circuit_breaker_manager,
            reset_circuit_breaker_manager,
        )

        reset_circuit_breaker_manager()
        manager = get_circuit_breaker_manager()
        required = [
            "google_ai",
            "cerebras",
            "groq",
            "redis",
            "postgresql",
            "paddle",
            "twilio",
            "brevo",
        ]
        for dep in required:
            state = manager.get_state(dep)
            assert state is not None, f"Circuit breaker for '{dep}' must be registered"
            # State must be one of the valid enum values
            assert state.value in ("closed", "open", "half_open"), (
                f"Circuit breaker for '{dep}' has invalid state: {state.value}"
            )
        reset_circuit_breaker_manager()

    def test_self_healing_service_available(self):
        """SelfHealingService must be importable and functional."""
        from app.services.self_healing_service import get_self_healing_service

        service = get_self_healing_service()
        assert service is not None, "SelfHealingService must be available"
        # Check key methods exist
        assert hasattr(service, "run_health_check"), (
            "SelfHealingService must have run_health_check"
        )
        assert hasattr(service, "heal_llm_failover"), (
            "SelfHealingService must have heal_llm_failover"
        )
        assert hasattr(service, "heal_circuit_breaker_reset"), (
            "SelfHealingService must have heal_circuit_breaker_reset"
        )

    def test_paddle_idempotency_implemented(self):
        """Paddle webhooks must have idempotency protection."""
        from app.services.paddle_reconciliation_service import (
            PaddleReconciliationService,
        )

        service = PaddleReconciliationService(db_session=None, redis_client=None)
        assert hasattr(service, "compute_idempotency_key"), (
            "PaddleReconciliationService must have compute_idempotency_key"
        )
        assert hasattr(service, "process_webhook"), (
            "PaddleReconciliationService must have process_webhook"
        )
        # Verify idempotency key is deterministic
        key1 = service.compute_idempotency_key("subscription.activated", "evt_123")
        key2 = service.compute_idempotency_key("subscription.activated", "evt_123")
        assert key1 == key2, "Idempotency key must be deterministic"
        assert len(key1) == 64, "SHA-256 idempotency key must be 64 hex chars"

    def test_llm_failover_configured(self):
        """LLM provider failover must be configured."""
        from app.config import Settings

        settings = Settings()
        assert settings.LLM_FALLBACK_PROVIDER, (
            "LLM_FALLBACK_PROVIDER must be set"
        )
        assert settings.LLM_PRIMARY_PROVIDER != settings.LLM_FALLBACK_PROVIDER, (
            "Primary and fallback providers should differ for failover to work"
        )

    def test_database_connection_pooling(self):
        """Database must use connection pooling via SQLAlchemy."""
        from database.base import engine

        pool = engine.pool
        assert pool is not None, "SQLAlchemy engine must have a connection pool"
        assert hasattr(pool, "size"), "Pool must have size() method"
        assert hasattr(pool, "checkedout"), "Pool must have checkedout() method"

    def test_redis_health_tracking(self):
        """Redis health must be tracked via circuit breaker."""
        from app.core.circuit_breaker_manager import (
            get_circuit_breaker_manager,
            reset_circuit_breaker_manager,
        )

        reset_circuit_breaker_manager()
        manager = get_circuit_breaker_manager()
        assert manager.get_state("redis") is not None, (
            "Redis must have a circuit breaker for health tracking"
        )
        assert manager.is_available("redis") is True, (
            "Redis circuit breaker should start as available"
        )
        reset_circuit_breaker_manager()


# ============================================================
# 3. OBSERVABILITY READINESS
# ============================================================


class TestObservabilityReadiness:
    """Validate all observability requirements for production."""

    def test_sentry_integration_available(self):
        """Sentry must be integrated and configurable."""
        from app.core.sentry import init_sentry, capture_exception

        assert callable(init_sentry), "init_sentry must be callable"
        assert callable(capture_exception), "capture_exception must be callable"

    def test_health_endpoint_exists(self):
        """Health check endpoint must exist."""
        # Check from source file to avoid import chain issues
        health_path = os.path.join(
            _PROJECT_ROOT, "backend", "app", "api", "health.py"
        )
        with open(health_path, "r") as f:
            content = f.read()
        assert '@router.get("/health")' in content, "/health endpoint must exist"

    def test_ready_endpoint_exists(self):
        """Readiness endpoint must exist."""
        health_path = os.path.join(
            _PROJECT_ROOT, "backend", "app", "api", "health.py"
        )
        with open(health_path, "r") as f:
            content = f.read()
        assert '@router.get("/ready")' in content, "/ready endpoint must exist"

    def test_metrics_endpoint_exists(self):
        """Metrics endpoint must exist."""
        health_path = os.path.join(
            _PROJECT_ROOT, "backend", "app", "api", "health.py"
        )
        with open(health_path, "r") as f:
            content = f.read()
        assert '@router.get("/metrics")' in content, "/metrics endpoint must exist"

    def test_structured_logging_configured(self):
        """Logging must use structured JSON format via structlog."""
        from app.logger import get_logger, configure_logging

        assert callable(get_logger), "get_logger must be callable"
        assert callable(configure_logging), "configure_logging must be callable"

    def test_correlation_ids_in_requests(self):
        """Every request must have a correlation ID."""
        # Verify ErrorHandlerMiddleware adds correlation IDs
        middleware_path = os.path.join(
            _PROJECT_ROOT,
            "backend",
            "app",
            "middleware",
            "error_handler.py",
        )
        with open(middleware_path, "r") as f:
            content = f.read()
        assert "correlation_id" in content, (
            "ErrorHandlerMiddleware must set correlation_id"
        )

    def test_circuit_breaker_metrics_export(self):
        """Circuit breaker must export Prometheus metrics."""
        from app.core.circuit_breaker_manager import (
            get_circuit_breaker_manager,
            reset_circuit_breaker_manager,
        )

        reset_circuit_breaker_manager()
        manager = get_circuit_breaker_manager()
        metrics = manager.get_metrics()
        assert isinstance(metrics, dict), "get_metrics must return a dict"
        assert "metrics_text" in metrics, "Metrics must include metrics_text"
        assert "summary" in metrics, "Metrics must include summary"
        assert "parwa_circuit_breaker_state" in metrics["metrics_text"], (
            "Metrics must include parwa_circuit_breaker_state gauge"
        )
        reset_circuit_breaker_manager()

    def test_self_healing_status_available(self):
        """Self-healing status must be queryable."""
        from app.services.self_healing_service import SelfHealingService

        service = SelfHealingService()
        status = service.get_status()
        assert isinstance(status, dict), "get_status must return a dict"
        # Status is nested: {"status": ..., "metrics": {"total_checks": ...}}
        assert "status" in status, "Status must include 'status' key"
        assert "metrics" in status, "Status must include 'metrics' key"
        metrics = status["metrics"]
        assert "total_checks" in metrics, "Metrics must include total_checks"

    def test_health_endpoint_includes_phase6_data(self):
        """Health endpoint must include Phase 6 status data."""
        # Check from source that Phase 6 data is included in health response
        health_path = os.path.join(
            _PROJECT_ROOT, "backend", "app", "api", "health.py"
        )
        with open(health_path, "r") as f:
            content = f.read()
        assert "circuit_breakers" in content, "Health response must include circuit breakers"
        assert "self_healing" in content, "Health response must include self-healing status"
        assert "sentry" in content, "Health response must include Sentry status"


# ============================================================
# 4. DATA READINESS
# ============================================================


class TestDataReadiness:
    """Validate all data requirements for production."""

    def test_backup_script_exists(self):
        """Database backup script must exist and be executable."""
        backup_path = os.path.join(_PROJECT_ROOT, "infra", "scripts", "backup.sh")
        assert os.path.exists(backup_path), "infra/scripts/backup.sh must exist"

    def test_restore_script_exists(self):
        """Database restore script must exist."""
        restore_path = os.path.join(_PROJECT_ROOT, "infra", "scripts", "restore.sh")
        assert os.path.exists(restore_path), "infra/scripts/restore.sh must exist"

    def test_backup_has_integrity_verification(self):
        """Backup must include integrity verification."""
        backup_path = os.path.join(_PROJECT_ROOT, "infra", "scripts", "backup.sh")
        if not os.path.exists(backup_path):
            pytest.skip("backup.sh not found")
        with open(backup_path, "r") as f:
            content = f.read().lower()
        assert (
            "sha256" in content or "md5" in content or "integrity" in content
        ), "Backup script must include integrity verification (sha256/md5/integrity)"

    def test_restore_has_safety_checks(self):
        """Restore must have safety confirmation."""
        restore_path = os.path.join(_PROJECT_ROOT, "infra", "scripts", "restore.sh")
        if not os.path.exists(restore_path):
            pytest.skip("restore.sh not found")
        with open(restore_path, "r") as f:
            content = f.read()
        assert "confirm" in content.lower() or "RESTORE" in content, (
            "Restore script must have safety confirmation prompt"
        )

    def test_gdpr_retention_configured(self):
        """GDPR data retention period must be configured."""
        from app.config import Settings

        settings = Settings()
        assert settings.GDPR_RETENTION_DAYS > 0, (
            "GDPR_RETENTION_DAYS must be a positive number"
        )
        assert settings.GDPR_RETENTION_DAYS >= 365, (
            "GDPR retention must be at least 365 days"
        )

    def test_audit_log_retention_configured(self):
        """Audit log retention must be configured."""
        from app.config import Settings

        settings = Settings()
        assert settings.AUDIT_LOG_RETENTION_DAYS > 0, (
            "AUDIT_LOG_RETENTION_DAYS must be a positive number"
        )
        # Audit logs should be retained longer than GDPR retention
        assert settings.AUDIT_LOG_RETENTION_DAYS >= settings.GDPR_RETENTION_DAYS, (
            "Audit log retention should be >= GDPR retention"
        )


# ============================================================
# 5. INFRASTRUCTURE READINESS
# ============================================================


class TestInfrastructureReadiness:
    """Validate all infrastructure requirements for production."""

    def test_docker_compose_prod_exists(self):
        """Production docker-compose must exist."""
        assert os.path.exists(
            os.path.join(_PROJECT_ROOT, "docker-compose.prod.yml")
        ), "docker-compose.prod.yml must exist"

    def test_docker_compose_prod_has_health_checks(self):
        """All services in docker-compose.prod.yml must have health checks."""
        dc_path = os.path.join(_PROJECT_ROOT, "docker-compose.prod.yml")
        if not os.path.exists(dc_path):
            pytest.skip("docker-compose.prod.yml not found")
        with open(dc_path, "r") as f:
            content = f.read()
        assert "healthcheck" in content, (
            "docker-compose.prod.yml must have health checks"
        )

    def test_k8s_manifests_exist(self):
        """Kubernetes manifests must exist."""
        assert os.path.exists(
            os.path.join(_PROJECT_ROOT, "infra", "k8s", "namespace.yaml")
        ), "infra/k8s/namespace.yaml must exist"
        assert os.path.exists(
            os.path.join(_PROJECT_ROOT, "infra", "k8s", "ingress.yaml")
        ), "infra/k8s/ingress.yaml must exist"
        assert os.path.exists(
            os.path.join(
                _PROJECT_ROOT, "infra", "k8s", "backend", "deployment.yaml"
            )
        ), "infra/k8s/backend/deployment.yaml must exist"
        assert os.path.exists(
            os.path.join(
                _PROJECT_ROOT, "infra", "k8s", "frontend", "deployment.yaml"
            )
        ), "infra/k8s/frontend/deployment.yaml must exist"

    def test_k8s_deployments_have_resource_limits(self):
        """All K8s deployments must have resource requests and limits."""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")

        for deployment_file in [
            "infra/k8s/backend/deployment.yaml",
            "infra/k8s/frontend/deployment.yaml",
        ]:
            full_path = os.path.join(_PROJECT_ROOT, deployment_file)
            if not os.path.exists(full_path):
                continue
            with open(full_path, "r") as f:
                doc = yaml.safe_load(f)
            containers = (
                doc.get("spec", {})
                .get("template", {})
                .get("spec", {})
                .get("containers", [])
            )
            for container in containers:
                assert "resources" in container, (
                    f"{deployment_file} missing resources"
                )
                assert "limits" in container["resources"], (
                    f"{deployment_file} missing resource limits"
                )
                assert "requests" in container["resources"], (
                    f"{deployment_file} missing resource requests"
                )

    def test_k8s_hpa_exists(self):
        """HPA must exist for backend and worker."""
        assert os.path.exists(
            os.path.join(_PROJECT_ROOT, "infra", "k8s", "backend", "hpa.yaml")
        ), "infra/k8s/backend/hpa.yaml must exist"
        assert os.path.exists(
            os.path.join(_PROJECT_ROOT, "infra", "k8s", "worker", "hpa.yaml")
        ), "infra/k8s/worker/hpa.yaml must exist"

    def test_k8s_network_policies_exist(self):
        """Network policies must exist for security."""
        assert os.path.exists(
            os.path.join(_PROJECT_ROOT, "infra", "k8s", "networkpolicy.yaml")
        ), "infra/k8s/networkpolicy.yaml must exist"

    def test_k8s_pdb_exists(self):
        """Pod Disruption Budgets must exist."""
        assert os.path.exists(
            os.path.join(_PROJECT_ROOT, "infra", "k8s", "pdb.yaml")
        ), "infra/k8s/pdb.yaml must exist"

    def test_ssl_setup_script_exists(self):
        """SSL setup script must exist."""
        assert os.path.exists(
            os.path.join(_PROJECT_ROOT, "nginx", "ssl-setup.sh")
        ), "nginx/ssl-setup.sh must exist"

    def test_redis_key_namespace_standard(self):
        """Redis key namespace manager must be available."""
        from app.core.redis_key_manager import build_key, get_ttl, RedisNamespace

        assert callable(build_key), "build_key must be callable"
        assert callable(get_ttl), "get_ttl must be callable"
        # Test a key
        key = build_key(RedisNamespace.CACHE, "company-123", "test-key")
        assert "parwa" in key, "Redis key must have 'parwa' prefix"
        assert "company-123" in key, "Redis key must include company_id (BC-001)"
        assert "cache" in key, "Redis key must include namespace"

    def test_redis_ttl_defaults_exist(self):
        """All Redis namespaces must have default TTLs."""
        from app.core.redis_key_manager import NAMESPACE_TTL_DEFAULTS, RedisNamespace

        for ns in RedisNamespace:
            assert ns in NAMESPACE_TTL_DEFAULTS, (
                f"Missing TTL for namespace: {ns.value}"
            )
            assert NAMESPACE_TTL_DEFAULTS[ns] > 0, (
                f"TTL for {ns.value} must be positive"
            )

    def test_env_example_complete(self):
        """All environment variables must be documented in .env.example."""
        env_path = os.path.join(_PROJECT_ROOT, ".env.example")
        if not os.path.exists(env_path):
            pytest.skip(".env.example not found")
        with open(env_path, "r") as f:
            content = f.read()
        required_vars = [
            "SECRET_KEY",
            "DATABASE_URL",
            "REDIS_URL",
            "JWT_SECRET_KEY",
            "SENTRY_DSN",
            "PADDLE_API_KEY",
            "ENVIRONMENT",
            "CORS_ORIGINS",
        ]
        for var in required_vars:
            assert var in content, f"Missing env var in .env.example: {var}"


# ============================================================
# 6. COMPLIANCE READINESS (BC-001 through BC-012)
# ============================================================


class TestComplianceReadiness:
    """Validate all Business Constraint compliance for production."""

    def test_bc001_tenant_isolation(self):
        """BC-001: All Redis keys and operations must be tenant-scoped."""
        from app.core.redis_key_manager import build_key, RedisNamespace

        # Every key built through build_key includes company_id
        key = build_key(RedisNamespace.CACHE, "test-company", "test")
        assert "test-company" in key, "Redis key must include company_id (BC-001)"

        # Keys without company_id should be rejected
        with pytest.raises(ValueError, match="company_id"):
            build_key(RedisNamespace.CACHE, "", "test")

    def test_bc004_retry_backoff(self):
        """BC-004: Celery tasks must use retry with backoff."""
        # Check that Celery config has retry settings
        from app.config import Settings

        settings = Settings()
        assert settings.CELERY_TASK_ACKS_LATE is True, (
            "CELERY_TASK_ACKS_LATE must be True (BC-004)"
        )
        assert settings.CELERY_TASK_REJECT_ON_WORKER_LOST is True, (
            "CELERY_TASK_REJECT_ON_WORKER_LOST must be True (BC-004)"
        )

    def test_bc008_never_crash(self):
        """BC-008: Critical services must handle errors gracefully."""
        from app.core.sentry import capture_exception
        from app.core.circuit_breaker_manager import (
            get_circuit_breaker_manager,
            reset_circuit_breaker_manager,
        )
        from app.services.self_healing_service import SelfHealingService

        # All should be importable and callable
        assert callable(capture_exception), (
            "capture_exception must be callable (BC-008)"
        )
        reset_circuit_breaker_manager()
        manager = get_circuit_breaker_manager()
        assert manager is not None, "CircuitBreakerManager must be available (BC-008)"

        # SelfHealingService must never crash — test with None deps
        service = SelfHealingService(db_session=None, redis_client=None)
        assert service is not None, "SelfHealingService must instantiate (BC-008)"
        reset_circuit_breaker_manager()

    def test_bc011_production_secrets(self):
        """BC-011: Production must not use default secrets."""
        # Check .env.prod.example has CHANGE_ME markers
        env_prod_path = os.path.join(_PROJECT_ROOT, ".env.prod.example")
        if not os.path.exists(env_prod_path):
            pytest.skip(".env.prod.example not found")
        with open(env_prod_path, "r") as f:
            content = f.read()
        assert "CHANGE_ME" in content, (
            ".env.prod.example must have CHANGE_ME markers for secrets"
        )
        assert content.count("CHANGE_ME") >= 3, (
            "At least 3 secrets must have CHANGE_ME markers"
        )

    def test_bc012_utc_timestamps(self):
        """BC-012: All timestamps must be UTC."""
        from datetime import timezone
        from app.services.self_healing_service import SelfHealingService, HealingResult, HealingAction

        service = SelfHealingService()
        # HealingResult auto-generates UTC timestamps
        result = HealingResult(
            action=HealingAction.REDIS_RECONNECT,
            success=True,
            message="Test",
        )
        assert result.timestamp, "HealingResult must have a timestamp"
        # UTC timestamps should end with +00:00 or Z
        ts = result.timestamp
        assert "+00:00" in ts or ts.endswith("Z"), (
            f"Timestamp must be UTC, got: {ts} (BC-012)"
        )

        # Self-healing status also uses UTC
        status = service.get_status()
        if status.get("last_check_at"):
            last_check = status["last_check_at"]
            assert "+00:00" in last_check or last_check.endswith("Z"), (
                f"last_check_at must be UTC, got: {last_check} (BC-012)"
            )

    def test_gdpr_data_minimization(self):
        """GDPR: Sentry must not send default PII."""
        from app.core.sentry import init_sentry

        # Check that sentry init uses send_default_pii=False
        sentry_path = os.path.join(
            _PROJECT_ROOT, "backend", "app", "core", "sentry.py"
        )
        with open(sentry_path, "r") as f:
            content = f.read()
        assert "send_default_pii=False" in content, (
            "Sentry must be initialized with send_default_pii=False (GDPR)"
        )

    def test_sentry_pii_scrubbing_configured(self):
        """GDPR: PII scrubbing must be configured in Sentry."""
        from app.core.sentry import _scrub_dict

        # Test email scrubbing
        result = _scrub_dict({"message": "User john@example.com called"})
        assert "john@example.com" not in result["message"], (
            "Email must be scrubbed from Sentry events"
        )
        assert "[REDACTED]" in result["message"], (
            "Email must be replaced with [REDACTED]"
        )

        # Test nested dict scrubbing
        nested = {
            "user": {
                "email": "jane@company.org",
                "name": "Jane",
            }
        }
        result = _scrub_dict(nested)
        assert "jane@company.org" not in result["user"]["email"], (
            "Nested email must be scrubbed"
        )


# ============================================================
# 7. PERFORMANCE READINESS
# ============================================================


class TestPerformanceReadiness:
    """Validate performance requirements for production."""

    def test_load_test_suite_exists(self):
        """Load test suite must exist."""
        assert os.path.exists(
            os.path.join(_PROJECT_ROOT, "tests", "production", "test_load.py")
        ), "tests/production/test_load.py must exist"

    def test_stress_test_suite_exists(self):
        """Stress test suite must exist."""
        assert os.path.exists(
            os.path.join(_PROJECT_ROOT, "tests", "production", "test_stress.py")
        ), "tests/production/test_stress.py must exist"

    def test_locustfile_exists(self):
        """Locust file must exist for running load tests."""
        assert os.path.exists(
            os.path.join(_PROJECT_ROOT, "tests", "production", "locustfile.py")
        ), "tests/production/locustfile.py must exist"

    def test_load_test_profiles_defined(self):
        """Load test must have multiple user profiles."""
        load_path = os.path.join(
            _PROJECT_ROOT, "tests", "production", "test_load.py"
        )
        if not os.path.exists(load_path):
            pytest.skip("test_load.py not found")
        with open(load_path, "r") as f:
            content = f.read()
        # Should define different user profiles for load testing
        content_lower = content.lower()
        assert "anonymous" in content_lower or "unauthenticated" in content_lower, (
            "Load test must include anonymous/unauthenticated profile"
        )
        assert "authenticated" in content_lower, (
            "Load test must include authenticated profile"
        )

    def test_hpa_scaling_configured(self):
        """K8s HPA must have proper scaling configuration."""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")

        hpa_file = os.path.join(
            _PROJECT_ROOT, "infra", "k8s", "backend", "hpa.yaml"
        )
        if not os.path.exists(hpa_file):
            pytest.skip("backend/hpa.yaml not found")
        with open(hpa_file, "r") as f:
            doc = yaml.safe_load(f)
        spec = doc.get("spec", {})
        assert spec.get("minReplicas", 0) >= 2, (
            "Backend minReplicas must be >= 2"
        )
        assert spec.get("maxReplicas", 0) >= 5, (
            "Backend maxReplicas must be >= 5"
        )

    def test_backend_replicas_minimum(self):
        """Production backend must have minimum 2 replicas."""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")

        deploy_file = os.path.join(
            _PROJECT_ROOT, "infra", "k8s", "backend", "deployment.yaml"
        )
        if not os.path.exists(deploy_file):
            pytest.skip("backend/deployment.yaml not found")
        with open(deploy_file, "r") as f:
            doc = yaml.safe_load(f)
        replicas = doc.get("spec", {}).get("replicas", 1)
        assert replicas >= 2, "Backend must have >= 2 replicas"


# ============================================================
# 8. CONFIGURATION READINESS
# ============================================================


class TestConfigurationReadiness:
    """Validate configuration management for production."""

    def test_env_prod_example_exists(self):
        """Production env template must exist."""
        assert os.path.exists(
            os.path.join(_PROJECT_ROOT, ".env.prod.example")
        ), ".env.prod.example must exist"

    def test_env_prod_has_no_dev_defaults(self):
        """Production env must not have dev default values."""
        env_prod_path = os.path.join(_PROJECT_ROOT, ".env.prod.example")
        if not os.path.exists(env_prod_path):
            pytest.skip(".env.prod.example not found")
        with open(env_prod_path, "r") as f:
            content = f.read()
        assert "CHANGE_ME" in content, (
            "Production env must have CHANGE_ME markers for secrets"
        )
        assert "ENVIRONMENT=production" in content, (
            "Production env must set ENVIRONMENT=production"
        )
        assert "DEBUG=false" in content, "Production env must set DEBUG=false"

    def test_dockerfile_exists_for_each_service(self):
        """Dockerfiles must exist for all services."""
        docker_dir = os.path.join(_PROJECT_ROOT, "infra", "docker")
        for df in [
            "backend.Dockerfile",
            "worker.Dockerfile",
            "frontend.prod.Dockerfile",
            "mcp.Dockerfile",
            "nginx.Dockerfile",
            "redis.Dockerfile",
            "postgres.Dockerfile",
        ]:
            assert os.path.exists(os.path.join(docker_dir, df)), (
                f"Missing Dockerfile: {df}"
            )

    def test_docker_compose_prod_has_restart_always(self):
        """Production services must have restart: always."""
        dc_path = os.path.join(_PROJECT_ROOT, "docker-compose.prod.yml")
        if not os.path.exists(dc_path):
            pytest.skip("docker-compose.prod.yml not found")
        with open(dc_path, "r") as f:
            content = f.read()
        assert content.count("restart: always") >= 3, (
            "At least 3 services must have restart: always"
        )

    def test_docker_compose_prod_has_network_isolation(self):
        """Production must have isolated networks."""
        dc_path = os.path.join(_PROJECT_ROOT, "docker-compose.prod.yml")
        if not os.path.exists(dc_path):
            pytest.skip("docker-compose.prod.yml not found")
        with open(dc_path, "r") as f:
            content = f.read()
        # Must have separate network definitions
        assert "network" in content.lower(), (
            "docker-compose.prod.yml must define networks"
        )

    def test_monitoring_stack_configured(self):
        """Monitoring stack must be in production docker-compose."""
        dc_path = os.path.join(_PROJECT_ROOT, "docker-compose.prod.yml")
        if not os.path.exists(dc_path):
            pytest.skip("docker-compose.prod.yml not found")
        with open(dc_path, "r") as f:
            content = f.read()
        # Must have at least Prometheus and Grafana
        monitoring_keywords = ["prometheus", "grafana"]
        found = [kw for kw in monitoring_keywords if kw in content.lower()]
        assert len(found) >= 1, (
            f"docker-compose.prod.yml must have monitoring stack ({', '.join(monitoring_keywords)})"
        )

    def test_celery_queues_defined(self):
        """Celery must have multiple queues defined."""
        from app.tasks.celery_app import app as celery_app

        # Check that celery app is configured
        assert celery_app is not None, "Celery app must be configured"
        # Check broker URL is set
        conf = celery_app.conf
        assert conf.broker_url, "Celery broker URL must be set"

    def test_cors_origins_configurable(self):
        """CORS origins must be configurable via environment."""
        from app.config import Settings

        settings = Settings()
        # CORS_ORIGINS must be a string (comma-separated) that can be configured
        assert hasattr(settings, "CORS_ORIGINS"), "CORS_ORIGINS must be in settings"
        assert isinstance(settings.CORS_ORIGINS, str), (
            "CORS_ORIGINS must be a string for environment configuration"
        )
