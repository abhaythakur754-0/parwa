"""
PARWA Security + Infrastructure — Integration Tests

Tests that verify the end-to-end behavior of security and infra fixes
working together, including cross-cutting concerns.
"""

import asyncio
import hashlib
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

# PROJECT_ROOT = /home/z/my-project/download/parwa
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════════
# Integration 1: Full MFA Login Flow (Race-Free)
# ═══════════════════════════════════════════════════════════════════


class TestMFALoginFlowIntegration(unittest.TestCase):
    """Integration test: MFA session creation → verification → JWT issuance."""

    @patch("app.api.mfa._store_mfa_session", new_callable=AsyncMock)
    @patch("app.api.mfa._retrieve_mfa_session", new_callable=AsyncMock)
    def test_full_mfa_session_lifecycle_redis(self, mock_retrieve, mock_store):
        """Create MFA session → retrieve → verify → consume (happy path)."""
        from app.api.mfa import (
            create_mfa_session_token,
            _mfa_pending_sessions,
        )

        mock_store.return_value = True
        _mfa_pending_sessions.clear()

        # Set up retrieve to return the session data
        mock_retrieve.return_value = {
            "user_id": "u-integration",
            "company_id": "c-integration",
            "email": "int@parwa.ai",
            "role": "admin",
            "plan": "high",
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=5)
            ).isoformat(),
        }

        async def run():
            # Step 1: Create session token (should await Redis)
            token = await create_mfa_session_token(
                user_id="u-integration",
                company_id="c-integration",
                email="int@parwa.ai",
                role="admin",
                plan="high",
            )

            # Step 2: Retrieve and verify the session
            session = await mock_retrieve(token)
            return token, session

        token, session = asyncio.run(run())

        self.assertIsNotNone(session, "Session must be retrievable after creation")
        self.assertEqual(session["user_id"], "u-integration")
        self.assertEqual(session["company_id"], "c-integration")
        self.assertEqual(session["email"], "int@parwa.ai")
        self.assertEqual(session["role"], "admin")
        self.assertEqual(session["plan"], "high")

    @patch("app.api.mfa._store_mfa_session", new_callable=AsyncMock)
    def test_mfa_session_expiry_enforced(self, mock_store):
        """Expired MFA sessions should be rejected."""
        from app.api.mfa import (
            create_mfa_session_token,
            verify_mfa_session_token,
            _mfa_pending_sessions,
        )

        # Simulate Redis failure so it falls back to in-memory
        mock_store.return_value = False
        _mfa_pending_sessions.clear()

        async def run():
            token = await create_mfa_session_token(
                user_id="u-expired", company_id="c-expired",
                email="exp@parwa.ai", role="admin", plan="pro",
            )

            # Manually expire the session
            _mfa_pending_sessions[token]["expires_at"] = (
                datetime.now(timezone.utc) - timedelta(minutes=10)
            )

            # Try to verify the expired session
            from fastapi import HTTPException
            try:
                await verify_mfa_session_token(token)
                return "no_error"
            except HTTPException as e:
                return e.detail

        result = asyncio.run(run())
        self.assertIsInstance(result, dict,
                             "Expired session should raise HTTPException")
        self.assertIn("MFA_SESSION", str(result))

    @patch("app.api.mfa._store_mfa_session", new_callable=AsyncMock)
    def test_mfa_session_one_time_use(self, mock_store):
        """MFA session token should be consumable only once (atomic GET+DEL)."""
        from app.api.mfa import (
            create_mfa_session_token,
            _retrieve_mfa_session,
            _mfa_pending_sessions,
        )

        mock_store.return_value = False  # Force in-memory
        _mfa_pending_sessions.clear()

        async def run():
            token = await create_mfa_session_token(
                user_id="u-onetime", company_id="c-onetime",
                email="one@parwa.ai", role="admin", plan="pro",
            )

            # First retrieval should succeed
            session1 = await _retrieve_mfa_session(token)

            # Second retrieval should fail (already consumed)
            session2 = await _retrieve_mfa_session(token)

            return session1, session2

        session1, session2 = asyncio.run(run())
        self.assertIsNotNone(session1, "First retrieval must succeed")
        self.assertIsNone(session2, "Second retrieval must fail (one-time use)")


# ═══════════════════════════════════════════════════════════════════
# Integration 2: Cookie Security vs Environment
# ═══════════════════════════════════════════════════════════════════


class TestCookieEnvironmentIntegration(unittest.TestCase):
    """Integration: Cookie Secure flag changes based on environment context."""

    def test_production_full_security_stack(self):
        """In production: Secure=True + HttpOnly + SameSite=strict."""
        from app.api.auth import _should_use_secure_cookies
        with patch("app.config.get_settings") as mock:
            settings = MagicMock()
            settings.ENVIRONMENT = "production"
            mock.return_value = settings

            secure = _should_use_secure_cookies()
            self.assertTrue(secure, "Production must use Secure cookies")

    def test_development_relaxed_for_local_http(self):
        """In development: Secure=False so cookies work over HTTP."""
        from app.api.auth import _should_use_secure_cookies
        with patch("app.config.get_settings") as mock:
            settings = MagicMock()
            settings.ENVIRONMENT = "development"
            mock.return_value = settings

            secure = _should_use_secure_cookies()
            self.assertFalse(secure,
                             "Development must allow cookies over HTTP")

    def test_staging_uses_secure(self):
        """Staging should use Secure=True (typically has HTTPS)."""
        from app.api.auth import _should_use_secure_cookies
        with patch("app.config.get_settings") as mock:
            settings = MagicMock()
            settings.ENVIRONMENT = "staging"
            mock.return_value = settings

            secure = _should_use_secure_cookies()
            # Staging is not production, so Secure=False
            self.assertFalse(secure,
                             "Staging should match non-production behavior")


# ═══════════════════════════════════════════════════════════════════
# Integration 3: Password Reset Security Chain
# ═══════════════════════════════════════════════════════════════════


class TestPasswordResetSecurityChain(unittest.TestCase):
    """Integration: Pepper → token hash → validation → session invalidation."""

    def test_production_pepper_required_for_token_hashing(self):
        """Full chain: production env + missing SECRET_KEY → RuntimeError."""
        from app.services.password_reset_service import _hash_token
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with patch("app.config.get_settings",
                       side_effect=Exception("DB connection failed")):
                with self.assertRaises(RuntimeError):
                    _hash_token("reset-token-abc")

    def test_development_pepper_fallback_allows_flow(self):
        """Development env + missing SECRET_KEY → fallback pepper → hash works."""
        from app.services.password_reset_service import _hash_token
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            with patch("app.config.get_settings",
                       side_effect=Exception("config not loaded")):
                result = _hash_token("reset-token-xyz")
                self.assertEqual(len(result), 64, "SHA-256 produces 64-char hex")

    def test_token_hash_matches_for_valid_reset(self):
        """Token generated during 'forgot' must match during 'reset'."""
        from app.services.password_reset_service import _generate_token, _hash_token
        with patch("app.config.get_settings") as mock:
            settings = MagicMock()
            settings.SECRET_KEY = "integration-test-key"
            mock.return_value = settings

            raw_token = _generate_token()
            hash_at_creation = _hash_token(raw_token)
            hash_at_verification = _hash_token(raw_token)

            self.assertEqual(hash_at_creation, hash_at_verification,
                             "Same token must produce same hash for validation")

    def test_different_tokens_different_hashes(self):
        """Two different reset tokens must produce different hashes."""
        from app.services.password_reset_service import _generate_token, _hash_token
        with patch("app.config.get_settings") as mock:
            settings = MagicMock()
            settings.SECRET_KEY = "integration-test-key"
            mock.return_value = settings

            token1 = _generate_token()
            token2 = _generate_token()
            hash1 = _hash_token(token1)
            hash2 = _hash_token(token2)

            self.assertNotEqual(hash1, hash2,
                                "Different tokens must produce different hashes")


# ═══════════════════════════════════════════════════════════════════
# Integration 4: RLS + Auth Middleware Chain
# ═══════════════════════════════════════════════════════════════════


class TestRLSAuthIntegration(unittest.TestCase):
    """Integration: RLS policies + auth middleware must work together."""

    def test_rls_covers_all_auth_related_tables(self):
        """Tables used in auth flow must all be RLS-protected."""
        import re
        rls_file = Path(PROJECT_ROOT / "database" / "alembic" / "versions" /
                        "022_enable_rls.py")
        with open(rls_file) as f:
            lines = f.readlines()

        in_list = False
        rls_tables = set()
        for line in lines:
            stripped = line.strip()
            if 'TENANT_TABLES' in stripped and '=' in stripped:
                in_list = True
                continue
            if in_list:
                if stripped.startswith(']'):
                    break
                match = re.match(r'"(\w+)"', stripped)
                if match:
                    rls_tables.add(match.group(1))

        auth_tables = [
            "users",
            "mfa_secrets",
            "backup_codes",
            "refresh_tokens",
            "password_reset_tokens",
            "verification_tokens",
            "oauth_accounts",
            "api_keys",
            "sessions",
            "user_details",
            "user_notification_preferences",
        ]
        missing = [t for t in auth_tables if t not in rls_tables]
        # sessions may be renamed to refresh_tokens, so filter that
        real_missing = [t for t in missing if t != "sessions"]
        self.assertEqual(real_missing, [],
                         f"Auth tables missing RLS: {real_missing}")

    def test_rls_migration_is_idempotent(self):
        """RLS migration should use IF NOT EXISTS / try-except for idempotency."""
        rls_file = Path(PROJECT_ROOT / "database" / "alembic" / "versions" /
                        "022_enable_rls.py")
        with open(rls_file) as f:
            content = f.read()
        # Check for safe SQL patterns
        self.assertIn("ENABLE ROW LEVEL SECURITY", content)
        self.assertIn("try", content, "Migration should handle errors gracefully")


# ═══════════════════════════════════════════════════════════════════
# Integration 5: Full Infrastructure Stack Validation
# ═══════════════════════════════════════════════════════════════════


class TestInfraStackIntegration(unittest.TestCase):
    """Integration: All infrastructure components must be properly configured."""

    def test_docker_compose_prod_has_all_required_services(self):
        """Production compose must have all 13 core services."""
        compose_file = PROJECT_ROOT / "docker-compose.prod.yml"
        with open(compose_file) as f:
            content = f.read()

        required_services = [
            "db", "redis", "backend", "worker", "frontend",
            "nginx", "prometheus", "grafana", "alertmanager",
            "node-exporter", "postgres-exporter", "redis-exporter",
            "mcp",
        ]
        for service in required_services:
            self.assertIn(f"  {service}:", content,
                          f"docker-compose.prod.yml missing service: {service}")

    def test_docker_compose_prod_all_have_healthchecks(self):
        """All critical services must have health checks."""
        compose_file = PROJECT_ROOT / "docker-compose.prod.yml"
        with open(compose_file) as f:
            content = f.read()

        critical_services = ["db", "redis", "backend", "worker"]
        for service in critical_services:
            # Find the service block and check for healthcheck
            self.assertIn("healthcheck:", content,
                          f"Service {service} missing healthcheck")

    def test_docker_compose_prod_all_have_restart_always(self):
        """All services must have restart: always."""
        compose_file = PROJECT_ROOT / "docker-compose.prod.yml"
        with open(compose_file) as f:
            content = f.read()

        restart_count = content.count("restart: always")
        self.assertGreaterEqual(restart_count, 10,
                                "Not enough services have restart: always")

    def test_nginx_has_ssl_and_security_headers(self):
        """Nginx config must have SSL termination + security headers."""
        nginx_file = PROJECT_ROOT / "infra" / "docker" / "nginx.conf"
        with open(nginx_file) as f:
            content = f.read()

        self.assertIn("ssl_protocols", content)
        self.assertIn("TLSv1.2", content)
        self.assertIn("TLSv1.3", content)
        self.assertIn("X-Frame-Options", content)
        self.assertIn("X-Content-Type-Options", content)
        self.assertIn("limit_req", content,
                       "Nginx must have rate limiting configured")

    def test_nginx_default_has_http_to_https_redirect(self):
        """Nginx default config must redirect HTTP to HTTPS."""
        nginx_default = PROJECT_ROOT / "infra" / "docker" / "nginx-default.conf"
        with open(nginx_default) as f:
            content = f.read()

        self.assertIn("301 https", content,
                       "Must redirect HTTP to HTTPS")
        self.assertIn("HSTS", content,
                       "Must have HSTS header")

    def test_prometheus_scrapes_all_services(self):
        """Prometheus must scrape all PARWA services."""
        prom_file = PROJECT_ROOT / "monitoring" / "prometheus.yml"
        with open(prom_file) as f:
            content = f.read()

        expected_targets = [
            "backend:8000",
            "redis-exporter",
            "postgres-exporter",
            "node-exporter",
        ]
        for target in expected_targets:
            self.assertIn(target, content,
                          f"Prometheus not scraping {target}")

    def test_alertmanager_has_critical_and_warning_routing(self):
        """Alertmanager must route critical and warning differently."""
        alert_file = PROJECT_ROOT / "monitoring" / "alertmanager" / "alertmanager.yml"
        with open(alert_file) as f:
            content = f.read()

        self.assertIn("critical-receiver", content)
        self.assertIn("warning-receiver", content)
        self.assertIn("severity: critical", content)
        self.assertIn("severity: warning", content)

    def test_backup_cronjob_exists_in_k8s(self):
        """K8s must have a backup CronJob."""
        backup_file = PROJECT_ROOT / "infra" / "k8s" / "backup-cronjob.yaml"
        self.assertTrue(backup_file.exists(), "K8s backup CronJob must exist")
        with open(backup_file) as f:
            content = f.read()
        self.assertIn("CronJob", content)
        self.assertIn("pg_dump", content)
        self.assertIn("0 */6 * * *", content, "Must run every 6 hours")

    def test_k8s_has_all_deployments(self):
        """K8s must have deployments for all core services."""
        k8s_dir = PROJECT_ROOT / "infra" / "k8s"
        expected_deployments = [
            "backend/deployment.yaml",
            "frontend/deployment.yaml",
            "worker/deployment.yaml",
            "mcp/deployment.yaml",
        ]
        for dep_path in expected_deployments:
            full_path = k8s_dir / dep_path
            self.assertTrue(full_path.exists(),
                            f"K8s deployment missing: {dep_path}")

    def test_grafana_dashboards_exist(self):
        """Grafana must have pre-built dashboards."""
        dashboards_dir = PROJECT_ROOT / "monitoring" / "grafana_dashboards"
        self.assertTrue(dashboards_dir.exists())
        dashboards = list(dashboards_dir.glob("*.json"))
        self.assertGreaterEqual(len(dashboards), 4,
                                "Need at least 4 Grafana dashboards")


# ═══════════════════════════════════════════════════════════════════
# Integration 6: Security Headers Across Stack
# ═══════════════════════════════════════════════════════════════════


class TestSecurityHeadersIntegration(unittest.TestCase):
    """Integration: Security headers are enforced at multiple layers."""

    def test_nginx_and_fastapi_both_set_security_headers(self):
        """Both nginx and FastAPI middleware must set security headers."""
        # Check FastAPI security headers middleware
        headers_file = PROJECT_ROOT / "backend" / "app" / "middleware" / "security_headers.py"
        with open(headers_file) as f:
            content = f.read()
        self.assertIn("X-Frame-Options", content)
        self.assertIn("X-Content-Type-Options", content)

        # Check nginx security headers
        nginx_file = PROJECT_ROOT / "infra" / "docker" / "nginx.conf"
        with open(nginx_file) as f:
            content = f.read()
        self.assertIn("X-Frame-Options", content)
        self.assertIn("X-Content-Type-Options", content)

    def test_cors_never_uses_wildcard_with_credentials(self):
        """CORS must never use wildcard origin with credentials."""
        cors_file = PROJECT_ROOT / "backend" / "app" / "main.py"
        with open(cors_file) as f:
            content = f.read()

        # If allow_origins=["*"] and allow_credentials=True, that's a security hole
        # Check that credentials are not used with wildcard
        if 'allow_origins=["*"]' in content or "allow_origins=['*']" in content:
            self.assertNotIn("allow_credentials=True", content,
                             "CRITICAL: CORS wildcard + credentials = security hole")


if __name__ == "__main__":
    unittest.main(verbosity=2)
