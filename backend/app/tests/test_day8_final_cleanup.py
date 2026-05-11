"""
Day 8 Security Tests — Final Cleanup, Dev Environment & Audit (14 findings)

Tests for:
- M-24: Dev Docker Compose localhost-only port bindings
- L-07: API key ID increased to secrets.token_hex(12) (24 hex chars)
- L-09: Login endpoint is async def
- L-10: dt.utcnow() replaced with dt.now(timezone.utc)
- L-12: JWT key rotation documentation exists
- L-13: Prometheus metrics do not leak environment name
- L-14: Error logging in mark-read instead of silent pass
- L-16: CORS origins are explicit (never wildcard with credentials)
- L-17: Brevo handler stores only filename/size, no base64 content
- M-22: Password complexity enforced on reset endpoint
- M-25: Redis has requirepass in Docker Compose
"""

import ast
import json
import os
import re
import textwrap
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════════
# L-07: API key ID uses secrets.token_hex(12) — 24 hex chars
# ═══════════════════════════════════════════════════════════════════


class TestAPIKeyIDLength:
    """Verify API key IDs are generated with 24 hex chars (token_hex(12))."""

    def test_api_key_id_uses_token_hex_12(self):
        """L-07: APIKey.__init__ should use secrets.token_hex(12)."""
        import importlib
        api_keys = importlib.import_module("security.api_keys")
        key = api_keys.APIKey(
            key_hash="somehash",
            key_prefix="pk_abc123",
            company_id="test_company",
            scopes=["read"],
        )
        # token_hex(12) produces 24 hex characters
        assert len(key.id) == 24, (
            f"L-07: API key ID should be 24 hex chars (token_hex(12)), "
            f"got {len(key.id)} chars: {key.id}"
        )
        assert re.match(r'^[0-9a-f]{24}$', key.id), (
            f"L-07: API key ID should be lowercase hex, got: {key.id}"
        )

    def test_api_key_id_custom_id_preserved(self):
        """L-07: Custom IDs should be preserved."""
        import importlib
        api_keys = importlib.import_module("security.api_keys")
        key = api_keys.APIKey(
            key_hash="somehash",
            key_prefix="pk_abc123",
            company_id="test_company",
            scopes=["read"],
            id="custom_id_12345",
        )
        assert key.id == "custom_id_12345"

    def test_api_key_id_uniqueness(self):
        """L-07: Multiple generated IDs should be unique."""
        import importlib
        api_keys = importlib.import_module("security.api_keys")
        ids = set()
        for _ in range(100):
            key = api_keys.APIKey(
                key_hash="hash",
                key_prefix="pk_",
                company_id="co",
                scopes=["read"],
            )
            ids.add(key.id)
        # 100 random 24-char hex IDs should all be unique
        assert len(ids) == 100, "L-07: Generated API key IDs should be unique"


# ═══════════════════════════════════════════════════════════════════
# L-09: Login endpoint is async def
# ═══════════════════════════════════════════════════════════════════


class TestLoginAsync:
    """Verify login endpoint is async (non-blocking)."""

    def test_login_endpoint_is_async(self):
        """L-09: The /api/auth/login endpoint should be async def."""
        import inspect
        from app.api.auth import router
        for route in router.routes:
            if hasattr(route, "path") and route.path.endswith("/login"):
                if hasattr(route, "endpoint"):
                    assert inspect.iscoroutinefunction(route.endpoint), (
                        "L-09: /api/auth/login endpoint must be async def, not def"
                    )
                    return
        pytest.fail("L-09: /api/auth/login route not found")


# ═══════════════════════════════════════════════════════════════════
# L-10: dt.utcnow() replaced with dt.now(timezone.utc)
# ═══════════════════════════════════════════════════════════════════


class TestNoUtcnow:
    """Verify no deprecated dt.utcnow() calls remain in backend."""

    def test_admin_py_no_utcnow(self):
        """L-10: admin.py should not contain dt.utcnow()."""
        with open("backend/app/api/admin.py") as f:
            content = f.read()
        assert "utcnow" not in content, (
            "L-10: admin.py still contains deprecated dt.utcnow()"
        )

    def test_agent_assignment_no_utcnow(self):
        """L-10: agent_assignment_service.py should not contain dt.utcnow()."""
        with open("backend/app/services/agent_assignment_service.py") as f:
            content = f.read()
        assert "utcnow" not in content, (
            "L-10: agent_assignment_service.py still contains deprecated dt.utcnow()"
        )

    def test_admin_py_uses_timezone_aware(self):
        """L-10: admin.py should use dt.now(timezone.utc)."""
        with open("backend/app/api/admin.py") as f:
            content = f.read()
        assert "dt.now(timezone.utc)" in content, (
            "L-10: admin.py should use dt.now(timezone.utc)"
        )


# ═══════════════════════════════════════════════════════════════════
# L-13: Prometheus metrics do not leak environment name
# ═══════════════════════════════════════════════════════════════════


class TestPrometheusMetricsNoEnvLeak:
    """Verify Prometheus metrics endpoint does not expose environment."""

    def test_health_py_no_env_label(self):
        """L-13: build_info metric should not have environment label."""
        with open("backend/app/api/health.py") as f:
            content = f.read()
        # The build_info metric should NOT have environment label
        # Check that the env var is not used in build_info construction
        assert 'environment="' not in content, (
            "L-13: build_info metric should NOT expose environment label"
        )
        # Check the build_info line does not include env label
        lines = content.split("\n")
        for line in lines:
            if "parwa_build_info" in line and "#" not in line.split("parwa_build_info")[0]:
                assert "environment" not in line, (
                    f"L-13: build_info line should not have environment: {line}"
                )

    def test_health_py_env_var_not_used_in_metrics(self):
        """L-13: ENVIRONMENT should not be read for Prometheus output."""
        with open("backend/app/api/health.py") as f:
            content = f.read()
        # Find the metrics section and check env is not used
        lines = content.split("\n")
        in_metrics = False
        for line in lines:
            if "def metrics_endpoint" in line:
                in_metrics = True
            if in_metrics:
                assert 'os.environ.get("ENVIRONMENT"' not in line, (
                    "L-13: metrics_endpoint should not read ENVIRONMENT"
                )


# ═══════════════════════════════════════════════════════════════════
# L-14: Error logging in mark-read instead of silent pass
# ═══════════════════════════════════════════════════════════════════


class TestMarkReadErrorLogging:
    """Verify mark-read endpoint logs errors instead of silently passing."""

    def test_no_silent_pass_in_mark_read(self):
        """L-14: mark-read endpoint should not have bare 'except: pass'."""
        with open("backend/app/api/notifications.py") as f:
            content = f.read()
        # Should NOT have bare except pass
        assert "except Exception:\n            pass" not in content, (
            "L-14: Silent 'except: pass' found in mark-read. "
            "Should log the error instead."
        )
        assert "except Exception:\n        pass" not in content, (
            "L-14: Silent 'except: pass' found in notifications.py"
        )

    def test_logging_imported_in_notifications(self):
        """L-14: notifications.py should import logging module."""
        with open("backend/app/api/notifications.py") as f:
            content = f.read()
        assert "import logging" in content, (
            "L-14: notifications.py should import logging"
        )
        assert "logger = " in content, (
            "L-14: notifications.py should define a logger"
        )

    def test_error_logged_in_mark_read(self):
        """L-14: mark-read error handler should call logger.warning/error."""
        with open("backend/app/api/notifications.py") as f:
            content = f.read()
        # The mark-read section should have logging in the except block
        assert 'logger.warning' in content or 'logger.error' in content, (
            "L-14: mark-read should log errors with logger.warning/error"
        )


# ═══════════════════════════════════════════════════════════════════
# L-16: CORS is explicit even when OpenAPI hidden
# ═══════════════════════════════════════════════════════════════════


class TestCORSExplicit:
    """Verify CORS never falls back to wildcard with credentials."""

    def test_main_py_no_wildcard_cors(self):
        """L-16: main.py should never set CORS origins to ['*'] as actual code."""
        with open("backend/app/main.py") as f:
            content = f.read()
        # Should NOT assign wildcard as CORS origins value
        # Check that the wildcard is not used as an actual value (only in comments)
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            # Skip comment lines
            if stripped.startswith("#"):
                continue
            # Should not assign wildcard
            if '["*"]' in stripped and ("allow_origins" in stripped or "cors" in stripped.lower()):
                pytest.fail(
                    f"L-16: CORS origins should never be wildcard: {stripped}"
                )
        # Should have explicit comment about L-16
        assert "L-16" in content, (
            "L-16: main.py should reference L-16 in CORS comment"
        )

    def test_cors_fallback_is_localhost(self):
        """L-16: CORS fallback should be localhost, not wildcard."""
        with open("backend/app/main.py") as f:
            content = f.read()
        # On exception, fallback should be localhost
        assert "localhost:3000" in content, (
            "L-16: CORS fail-closed should default to localhost"
        )


# ═══════════════════════════════════════════════════════════════════
# L-17: Brevo handler stores only filename/size, no base64 content
# ═══════════════════════════════════════════════════════════════════


class TestBrevoNoBase64Content:
    """Verify Brevo handler does not store base64 content."""

    def test_no_content_b64_in_brevo_handler(self):
        """L-17: brevo_handler should not store content_b64."""
        with open("backend/app/webhooks/brevo_handler.py") as f:
            content = f.read()
        assert 'content_b64' not in content, (
            "L-17: brevo_handler should not store base64 content (content_b64)"
        )
        assert 'content_valid' not in content, (
            "L-17: brevo_handler should not validate base64 content inline"
        )
        assert 'base64.b64decode' not in content, (
            "L-17: brevo_handler should not decode base64 content"
        )

    def test_attachment_stores_only_metadata(self):
        """L-17: attachments should only store filename, content_type, size."""
        with open("backend/app/webhooks/brevo_handler.py") as f:
            content = f.read()
        # Should have filename, content_type, size
        assert '"filename"' in content, "L-17: Should store filename"
        assert '"content_type"' in content, "L-17: Should store content_type"
        assert '"size"' in content, "L-17: Should store size"

    def test_brevo_extract_attachments_no_b64(self):
        """L-17: _extract_attachments should not include base64 data."""
        from app.webhooks.brevo_handler import _extract_attachments
        attachments = [
            {
                "filename": "test.pdf",
                "content-type": "application/pdf",
                "size": 1024,
                "content": "aGVsbG8gd29ybGQ=",  # base64 "hello world"
            }
        ]
        result = _extract_attachments(attachments)
        assert len(result) == 1
        assert result[0]["filename"] == "test.pdf"
        assert result[0]["content_type"] == "application/pdf"
        assert result[0]["size"] == 1024
        assert "content_b64" not in result[0], (
            "L-17: Should not store content_b64"
        )
        assert "content_valid" not in result[0], (
            "L-17: Should not store content_valid"
        )
        assert result[0].get("has_content") is True


# ═══════════════════════════════════════════════════════════════════
# M-24: Docker Compose localhost-only port bindings
# ═══════════════════════════════════════════════════════════════════


class TestDockerComposeSecurity:
    """Verify Docker Compose is secured for dev environment."""

    def test_localhost_port_binding_db(self):
        """M-24: PostgreSQL should bind to 127.0.0.1 only."""
        with open("docker-compose.yml") as f:
            content = f.read()
        assert "127.0.0.1:5432:5432" in content, (
            "M-24: DB port should bind to 127.0.0.1, not 0.0.0.0"
        )

    def test_localhost_port_binding_redis(self):
        """M-24: Redis should bind to 127.0.0.1 only."""
        with open("docker-compose.yml") as f:
            content = f.read()
        assert "127.0.0.1:6379:6379" in content, (
            "M-24: Redis port should bind to 127.0.0.1, not 0.0.0.0"
        )

    def test_localhost_port_binding_backend(self):
        """M-24: Backend should bind to 127.0.0.1 only."""
        with open("docker-compose.yml") as f:
            content = f.read()
        assert "127.0.0.1:8000:8000" in content, (
            "M-24: Backend port should bind to 127.0.0.1, not 0.0.0.0"
        )

    def test_localhost_port_binding_frontend(self):
        """M-24: Frontend should bind to 127.0.0.1 only."""
        with open("docker-compose.yml") as f:
            content = f.read()
        assert "127.0.0.1:3000:3000" in content, (
            "M-24: Frontend port should bind to 127.0.0.1, not 0.0.0.0"
        )

    def test_dev_warning_banner(self):
        """M-24: docker-compose.yml should have a dev-only warning."""
        with open("docker-compose.yml") as f:
            content = f.read()
        assert "DEVELOPMENT ONLY" in content or "DO NOT USE IN PRODUCTION" in content, (
            "M-24: docker-compose.yml should have dev-only warning banner"
        )

    def test_no_wildcard_port_binding(self):
        """M-24: No port should bind to 0.0.0.0."""
        with open("docker-compose.yml") as f:
            content = f.read()
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            # Match port bindings like "- \"5432:5432\"" (without 127.0.0.1)
            port_match = re.match(r'^-\s*"(\d+:\d+)"', stripped)
            if port_match:
                pytest.fail(
                    f"M-24: Port binding '{stripped}' binds to 0.0.0.0. "
                    f"Should bind to 127.0.0.1"
                )


# ═══════════════════════════════════════════════════════════════════
# M-25: Redis has requirepass in Docker Compose
# ═══════════════════════════════════════════════════════════════════


class TestRedisPassword:
    """Verify Redis has password authentication in dev Docker."""

    def test_redis_requirepass(self):
        """M-25: Redis should use --requirepass."""
        with open("docker-compose.yml") as f:
            content = f.read()
        assert "requirepass" in content, (
            "M-25: Redis should require password authentication"
        )


# ═══════════════════════════════════════════════════════════════════
# L-12: JWT key rotation documentation exists
# ═══════════════════════════════════════════════════════════════════


class TestJWTKeyRotationDocs:
    """Verify JWT key rotation documentation exists."""

    def test_rotation_doc_exists(self):
        """L-12: JWT key rotation documentation file should exist."""
        assert os.path.exists("documents/JWT_KEY_ROTATION_PROCEDURE.md"), (
            "L-12: JWT_KEY_ROTATION_PROCEDURE.md should exist"
        )

    def test_rotation_doc_contains_key_steps(self):
        """L-12: Documentation should cover key rotation steps."""
        with open("documents/JWT_KEY_ROTATION_PROCEDURE.md") as f:
            content = f.read()
        assert "JWT_PREVIOUS_KEYS" in content, (
            "L-12: Doc should mention JWT_PREVIOUS_KEYS"
        )
        assert "JWT_SECRET_KEY" in content, (
            "L-12: Doc should mention JWT_SECRET_KEY"
        )
        assert "rotation" in content.lower(), (
            "L-12: Doc should describe rotation procedure"
        )

    def test_core_auth_has_rotation_support(self):
        """L-02/L-12: core/auth.py should support previous keys."""
        with open("backend/app/core/auth.py") as f:
            content = f.read()
        assert "JWT_PREVIOUS_KEYS" in content, (
            "L-02: core/auth.py should reference JWT_PREVIOUS_KEYS"
        )
        assert "candidate_keys" in content or "_JWT_PREVIOUS_KEYS" in content, (
            "L-02: core/auth.py should implement key rotation"
        )


# ═══════════════════════════════════════════════════════════════════
# M-22: Password complexity enforced on reset endpoint
# ═══════════════════════════════════════════════════════════════════


class TestPasswordComplexityOnReset:
    """Verify password complexity is enforced on reset endpoint."""

    def test_reset_uses_validate_password_strength(self):
        """M-22: reset-password should use validatePasswordStrength."""
        with open("src/app/api/auth/reset-password/route.ts") as f:
            content = f.read()
        assert "validatePasswordStrength" in content, (
            "M-22: reset-password should use validatePasswordStrength"
        )

    def test_reset_and_register_use_same_validation(self):
        """M-22: Both register and reset should use the same validation."""
        with open("src/app/api/auth/reset-password/route.ts") as f:
            reset_content = f.read()
        with open("src/app/api/auth/register/route.ts") as f:
            register_content = f.read()
        assert "validatePasswordStrength" in reset_content, (
            "M-22: reset-password should use validatePasswordStrength"
        )
        assert "validatePasswordStrength" in register_content, (
            "M-22: register should use validatePasswordStrength"
        )


# ═══════════════════════════════════════════════════════════════════
# L-15: Null-byte rejection in Paddle handler (already done)
# ═══════════════════════════════════════════════════════════════════


class TestNullByteRejection:
    """Verify null-byte rejection in Paddle event type validation."""

    def test_null_byte_rejected(self):
        """L-15: event_type with null bytes should be rejected."""
        from app.webhooks.paddle_handler import _validate_event_type
        error = _validate_event_type("subscription.created\x00evil")
        assert error is not None, (
            "L-15: event_type with null bytes should be rejected"
        )
        assert "invalid" in error.lower(), (
            "L-15: Error should mention invalid characters"
        )

    def test_valid_event_type_accepted(self):
        """L-15: valid event_type should pass."""
        from app.webhooks.paddle_handler import _validate_event_type
        error = _validate_event_type("subscription.created")
        assert error is None, (
            "L-15: Valid event_type should not produce error"
        )


# ═══════════════════════════════════════════════════════════════════
# FINAL: Full regression — verify no dt.utcnow() anywhere in backend
# ═══════════════════════════════════════════════════════════════════


class TestFinalRegression:
    """Final regression tests for Day 8."""

    def test_no_utcnow_in_day8_target_files(self):
        """FINAL: No dt.utcnow() should exist in Day 8 target files."""
        target_files = [
            "backend/app/api/admin.py",
            "backend/app/services/agent_assignment_service.py",
        ]
        for filepath in target_files:
            with open(filepath) as f:
                content = f.read()
            assert "utcnow" not in content, (
                f"FINAL: dt.utcnow() found in {filepath}. "
                f"Use dt.now(timezone.utc) instead."
            )

    def test_all_day8_files_modified(self):
        """FINAL: Verify all expected Day 8 files were modified."""
        # Just verify key indicators
        with open("security/api_keys.py") as f:
            assert "token_hex(12)" in f.read()
        with open("backend/app/api/admin.py") as f:
            assert "timezone.utc" in f.read()
        with open("backend/app/api/notifications.py") as f:
            content = f.read()
            assert "import logging" in content
            assert "logger.warning" in content
        with open("docker-compose.yml") as f:
            content = f.read()
            assert "127.0.0.1" in content
            assert "DEVELOPMENT ONLY" in content
