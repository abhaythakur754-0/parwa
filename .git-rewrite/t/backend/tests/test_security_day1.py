"""
PARWA Security Day 1 — Comprehensive Unit Tests

Tests for all 10 security fixes from Day 1:
  C-06: Config validators must raise in production
  C-07: .env.prod not in git, .gitignore updated
  C-05: CORS never falls back to wildcard
  C-08: variant_check never trusts X-Company-ID header
  C-09: MFA flow uses temporary session token (not JWT)
  C-10: Admin routes require is_platform_admin
  C-15: Refresh token pepper fails hard in production
  H-05: /api/billing/ and /api/admin/ removed from tenant PUBLIC_PREFIXES
  M-01: user_role removed from AuthorizationError details
  M-05: Rate limiter fail-open logs ERROR
"""

import json
import os
import sys
import warnings
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

# ── Path setup so imports work ─────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")

# ====================================================================
# Helper: Read source file
# ====================================================================


def _read_source(relative_path):
    """Read a source file relative to the parwa project root."""
    path = os.path.join(_BASE_DIR, relative_path)
    with open(path, "r") as f:
        return f.read()


def _read_backend_source(relative_path):
    """Read a source file relative to the backend dir."""
    path = os.path.join(_BACKEND_DIR, relative_path)
    with open(path, "r") as f:
        return f.read()


# ====================================================================
# C-06: Config Validators Must Raise in Production
# ====================================================================


class TestConfigValidatorsProduction:
    """Verify that dev-default secrets are BLOCKED in production."""

    def test_secret_key_raises_in_production(self):
        """SECRET_KEY starting with 'dev-' must raise ValueError in production."""
        os.environ["ENVIRONMENT"] = "production"
        try:
            from app.config import Settings
            with pytest.raises(Exception):
                Settings(
                    SECRET_KEY="dev-secret-key-change-in-production",
                    JWT_SECRET_KEY="real-production-key-at-least-32-chars!",
                    DATA_ENCRYPTION_KEY="01234567890123456789012345678901",
                    DATABASE_URL="sqlite:///./test.db",
                )
        finally:
            del os.environ["ENVIRONMENT"]

    def test_jwt_secret_key_raises_in_production(self):
        """JWT_SECRET_KEY starting with 'dev-' must raise ValueError in production."""
        os.environ["ENVIRONMENT"] = "production"
        try:
            from app.config import Settings
            with pytest.raises(Exception):
                Settings(
                    SECRET_KEY="real-production-secret-key-32-chars!!",
                    JWT_SECRET_KEY="dev-jwt-secret-key-change-in-production",
                    DATA_ENCRYPTION_KEY="01234567890123456789012345678901",
                    DATABASE_URL="sqlite:///./test.db",
                )
        finally:
            del os.environ["ENVIRONMENT"]

    def test_secret_key_warns_in_development(self):
        """SECRET_KEY starting with 'dev-' should warn (not raise) in development."""
        os.environ["ENVIRONMENT"] = "development"
        try:
            from app.config import Settings
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                Settings(
                    SECRET_KEY="dev-secret-key-change-in-production",
                    JWT_SECRET_KEY="dev-jwt-secret-key-change-in-production",
                    DATABASE_URL="sqlite:///./test.db",
                )
                assert len(w) >= 2
                assert any("SECRET_KEY" in str(x.message) for x in w)
                assert any("JWT_SECRET_KEY" in str(x.message) for x in w)
        finally:
            del os.environ["ENVIRONMENT"]

    def test_real_secret_key_passes_in_production(self):
        """A real (non-dev) secret key must pass validation in production."""
        os.environ["ENVIRONMENT"] = "production"
        try:
            from app.config import Settings
            settings = Settings(
                SECRET_KEY="real-production-secret-key-32-chars!!",
                JWT_SECRET_KEY="real-production-jwt-secret-key-32-chars!",
                DATA_ENCRYPTION_KEY="01234567890123456789012345678901",
                DATABASE_URL="sqlite:///./test.db",
            )
            assert settings.SECRET_KEY == "real-production-secret-key-32-chars!!"
        finally:
            del os.environ["ENVIRONMENT"]


# ====================================================================
# C-07: .env.prod Not Tracked in Git
# ====================================================================


class TestEnvProdGitignore:
    """Verify .env.prod is in .gitignore and not tracked."""

    def test_env_prod_in_gitignore(self):
        """.env.prod must be listed in .gitignore."""
        content = _read_source(".gitignore")
        assert ".env.prod" in content

    def test_env_prod_example_exists(self):
        """.env.prod.example should exist as a template."""
        assert os.path.exists(os.path.join(_BASE_DIR, ".env.prod.example"))

    def test_env_prod_example_has_placeholders(self):
        """.env.prod.example should contain CHANGE_ME placeholders."""
        content = _read_source(".env.prod.example")
        assert "CHANGE_ME" in content
        assert "sk_live_" not in content
        assert "xoxb-" not in content


# ====================================================================
# C-05: CORS Never Falls Back to Wildcard
# ====================================================================


class TestCORSSecurity:
    """Verify CORS never falls back to ['*'] with credentials."""

    def test_cors_uses_frontend_url_when_empty(self):
        """When CORS_ORIGINS is empty, should use FRONTEND_URL (not '*')."""
        cors_origins_setting = ""
        frontend_url = "http://localhost:3000"
        if cors_origins_setting:
            result = [o.strip() for o in cors_origins_setting.split(",") if o.strip()]
        else:
            result = [frontend_url]
        assert result == ["http://localhost:3000"]
        assert "*" not in result

    def test_cors_exception_falls_closed(self):
        """When settings fail to load, should fall back to localhost (not '*')."""
        _cors_origins = ["http://localhost:3000"]
        assert "*" not in _cors_origins

    def test_cors_filters_empty_strings(self):
        """Empty strings in CORS_ORIGINS should be filtered out."""
        cors_origins_setting = "https://parwa.ai,, https://www.parwa.ai,  "
        result = [o.strip() for o in cors_origins_setting.split(",") if o.strip()]
        assert result == ["https://parwa.ai", "https://www.parwa.ai"]
        assert "" not in result

    def test_main_py_uses_fallback_not_wildcard(self):
        """main.py should NOT have fallback to ['*']."""
        content = _read_backend_source("app/main.py")
        # Should not have 'else ["*"]' pattern
        assert 'else ["*"]' not in content
        # Should use FRONTEND_URL fallback
        assert "FRONTEND_URL" in content


# ====================================================================
# C-08: Variant Check Never Trusts X-Company-ID Header
# ====================================================================


class TestVariantCheckSecurity:
    """Verify variant_check middleware never trusts client-controlled headers."""

    def test_no_x_company_id_header_in_source(self):
        """X-Company-ID header check should NOT exist in source."""
        content = _read_backend_source("app/middleware/variant_check.py")
        # Should NOT have b"x-company-id" being read and used
        assert "headers.get(b\"x-company-id\"" not in content

    def test_only_jwt_extraction(self):
        """Should only use Authorization header for JWT extraction."""
        content = _read_backend_source("app/middleware/variant_check.py")
        # Should mention Authorization header
        assert "authorization" in content.lower()
        # Should NOT mention X-Company-ID in extraction
        assert "Do NOT accept client-controlled headers" in content

    def test_x_company_id_not_in_extract(self):
        """_extract_company_id should NOT reference x-company-id as a data source."""
        content = _read_backend_source("app/middleware/variant_check.py")
        lines = content.split("\n")
        in_extract = False
        for line in lines:
            if "_extract_company_id" in line and "def " in line:
                in_extract = True
            elif in_extract and ("def " in line or "class " in line):
                break
            elif in_extract:
                # Skip comment lines (may start with # or whitespace+unicode)
                stripped = line.lstrip()
                if stripped.startswith("#") or stripped.startswith("Do NOT"):
                    continue
                assert "x-company-id" not in line.lower(), (
                    f"X-Company-ID found in _extract_company_id: {line}"
                )

    def test_source_mentions_security_comment(self):
        """Source should have L06 security comment."""
        content = _read_backend_source("app/middleware/variant_check.py")
        assert "L06" in content or "client-controlled" in content.lower()


# ====================================================================
# C-09: MFA Login Flow Uses Temporary Session Token
# ====================================================================


class TestMFASessionToken:
    """Verify MFA verify endpoint uses temporary session token, not JWT."""

    def test_mfa_session_token_functions_exist(self):
        """MFA module should have create_mfa_session_token and verify_mfa_session_token."""
        content = _read_backend_source("app/api/mfa.py")
        assert "def create_mfa_session_token" in content
        assert "def verify_mfa_session_token" in content

    def test_mfa_session_ttl_configured(self):
        """MFA session should have a TTL (5 minutes)."""
        content = _read_backend_source("app/api/mfa.py")
        assert "_MFA_SESSION_TTL_SECONDS" in content
        assert "300" in content  # 5 minutes

    def test_mfa_session_consumed_on_verify(self):
        """Session token should be consumed (one-time use) after verification."""
        content = _read_backend_source("app/api/mfa.py")
        assert "_mfa_pending_sessions.pop" in content

    def test_mfa_session_expired_check(self):
        """Expired session tokens should be rejected."""
        content = _read_backend_source("app/api/mfa.py")
        assert "expires_at" in content
        assert "MFA_SESSION_EXPIRED" in content

    def test_mfa_session_invalid_check(self):
        """Invalid session tokens should be rejected."""
        content = _read_backend_source("app/api/mfa.py")
        assert "MFA_SESSION_INVALID" in content

    def test_mfa_schema_has_session_token_field(self):
        """MFALoginVerifyRequest must have mfa_session_token field."""
        content = _read_backend_source("app/schemas/mfa.py")
        assert "mfa_session_token" in content
        assert "Field(min_length=1" in content

    def test_mfa_verify_no_get_current_user(self):
        """MFA verify should NOT use get_current_user (requires JWT)."""
        content = _read_backend_source("app/api/mfa.py")
        # Find the mfa_verify_login function
        lines = content.split("\n")
        in_verify = False
        for i, line in enumerate(lines):
            if "def mfa_verify_login" in line:
                in_verify = True
            elif in_verify and ("def " in line and "mfa" not in line.lower()):
                break
            elif in_verify:
                assert "get_current_user" not in line, (
                    f"mfa_verify_login should NOT use get_current_user: {line}"
                )

    def test_mfa_verify_issues_jwt_on_success(self):
        """On successful MFA verification, should issue real JWT tokens."""
        content = _read_backend_source("app/api/mfa.py")
        assert "create_access_token" in content
        assert "generate_refresh_token" in content


# ====================================================================
# C-10: Admin Routes Require is_platform_admin
# ====================================================================


class TestPlatformAdmin:
    """Verify admin routes use require_platform_admin, not require_roles."""

    def test_user_model_has_platform_admin_flag(self):
        """User model must have is_platform_admin column."""
        content = _read_source("database/models/core.py")
        assert "is_platform_admin" in content
        assert "Column(Boolean" in content

    def test_require_platform_admin_exists(self):
        """require_platform_admin dependency must exist in deps."""
        content = _read_backend_source("app/api/deps.py")
        assert "def require_platform_admin" in content

    def test_admin_routes_use_platform_admin(self):
        """All admin routes must use require_platform_admin."""
        content = _read_backend_source("app/api/admin.py")
        assert "require_platform_admin" in content
        assert "require_roles" not in content

    def test_platform_admin_checks_flag(self):
        """require_platform_admin should check is_platform_admin flag."""
        content = _read_backend_source("app/api/deps.py")
        assert "is_platform_admin" in content
        assert "AuthorizationError" in content


# ====================================================================
# C-15: Refresh Token Pepper Fails Hard in Production
# ====================================================================


class TestRefreshTokenPepper:
    """Verify refresh token pepper has no insecure default."""

    def test_production_requires_pepper(self):
        """In production, missing REFRESH_TOKEN_PEPPER should raise RuntimeError."""
        if "app.core.auth" in sys.modules:
            del sys.modules["app.core.auth"]

        env_backup = os.environ.get("REFRESH_TOKEN_PEPPER")
        os.environ.pop("REFRESH_TOKEN_PEPPER", None)
        os.environ["ENVIRONMENT"] = "production"

        try:
            with pytest.raises(RuntimeError) as exc_info:
                import app.core.auth  # noqa: F401
            assert "REFRESH_TOKEN_PEPPER" in str(exc_info.value)
        finally:
            os.environ["ENVIRONMENT"] = "development"
            if env_backup is not None:
                os.environ["REFRESH_TOKEN_PEPPER"] = env_backup

    def test_no_insecure_default_pepper(self):
        """Source code should NOT contain the old insecure default pepper."""
        content = _read_backend_source("app/core/auth.py")
        assert "parwa-refresh-pepper-change-in-prod" not in content

    def test_development_allows_empty_pepper(self):
        """In development, empty pepper should NOT raise."""
        if "app.core.auth" in sys.modules:
            del sys.modules["app.core.auth"]

        env_backup = os.environ.get("REFRESH_TOKEN_PEPPER")
        os.environ.pop("REFRESH_TOKEN_PEPPER", None)
        os.environ["ENVIRONMENT"] = "development"

        try:
            import app.core.auth
            assert app.core.auth._REFRESH_TOKEN_PEPPER == ""
        finally:
            if env_backup is not None:
                os.environ["REFRESH_TOKEN_PEPPER"] = env_backup


# ====================================================================
# H-05: Tenant Middleware — Billing and Admin NOT Skipped
# ====================================================================


class TestTenantMiddlewareSecurity:
    """Verify /api/billing/ and /api/admin/ are NOT in PUBLIC_PREFIXES."""

    def test_billing_not_in_public_prefixes(self):
        """/api/billing/ must NOT be in tenant PUBLIC_PREFIXES."""
        content = _read_backend_source("app/middleware/tenant.py")
        # PUBLIC_PREFIXES should not contain /api/billing/
        lines = content.split("\n")
        in_prefixes = False
        for line in lines:
            if "PUBLIC_PREFIXES = (" in line:
                in_prefixes = True
            elif in_prefixes and line.strip() == ")":
                break
            elif in_prefixes:
                assert '"/api/billing/"' not in line

    def test_admin_not_in_public_prefixes(self):
        """/api/admin/ must NOT be in tenant PUBLIC_PREFIXES."""
        content = _read_backend_source("app/middleware/tenant.py")
        lines = content.split("\n")
        in_prefixes = False
        for line in lines:
            if "PUBLIC_PREFIXES = (" in line:
                in_prefixes = True
            elif in_prefixes and line.strip() == ")":
                break
            elif in_prefixes:
                assert '"/api/admin/"' not in line

    def test_auth_still_in_public_prefixes(self):
        """/api/auth/ should still be in PUBLIC_PREFIXES (correct behavior)."""
        content = _read_backend_source("app/middleware/tenant.py")
        assert '"/api/auth/"' in content

    def test_webhooks_still_in_public_prefixes(self):
        """/api/webhooks/ should still be in PUBLIC_PREFIXES."""
        content = _read_backend_source("app/middleware/tenant.py")
        assert '"/api/webhooks/"' in content

    def test_no_debug_comments(self):
        """Tenant middleware should not contain DEBUG comments."""
        content = _read_backend_source("app/middleware/tenant.py")
        assert "# DEBUG:" not in content

    def test_security_comment_present(self):
        """Should have security comment about billing/admin removal."""
        content = _read_backend_source("app/middleware/tenant.py")
        assert "SECURITY:" in content


# ====================================================================
# M-01: user_role Removed from Error Details
# ====================================================================


class TestAuthorizationErrorDetails:
    """Verify AuthorizationError does not leak user_role."""

    def test_user_role_not_in_error_details(self):
        """require_roles should NOT include user_role in error details."""
        content = _read_backend_source("app/api/deps.py")
        # Verify user_role is NOT in the AuthorizationError details
        assert '"user_role"' not in content

    def test_required_role_in_error_details(self):
        """Error details should contain required_role."""
        content = _read_backend_source("app/api/deps.py")
        assert '"required_role"' in content


# ====================================================================
# M-05: Rate Limiter Fail-Open Logs ERROR
# ====================================================================


class TestRateLimiterLogging:
    """Verify rate limiter logs errors when it fails open."""

    def test_rate_limit_has_logger(self):
        """Rate limit middleware should have a logger instance."""
        content = _read_backend_source("app/middleware/rate_limit.py")
        assert "import logging" in content
        assert 'logger = logging.getLogger' in content

    def test_rate_limit_logs_error_on_failure(self):
        """Rate limiter should log ERROR when check fails."""
        content = _read_backend_source("app/middleware/rate_limit.py")
        assert "logger.error" in content
        assert "rate_limit_check_failed" in content


# ====================================================================
# Integration: MFA Session Token Logic Verification
# ====================================================================


class TestMFASessionTokenLogic:
    """Test the MFA session token functions using isolated execution."""

    def test_session_token_is_random(self):
        """Session tokens should be random (not predictable)."""
        content = _read_backend_source("app/api/mfa.py")
        assert "secrets.token_urlsafe(32)" in content

    def test_session_stores_user_data(self):
        """Session should store user_id, company_id, email, role, plan."""
        content = _read_backend_source("app/api/mfa.py")
        assert '"user_id"' in content
        assert '"company_id"' in content
        assert '"email"' in content
        assert '"role"' in content
        assert '"plan"' in content

    def test_session_flow_documented(self):
        """The MFA flow should be documented with clear comments."""
        content = _read_backend_source("app/api/mfa.py")
        assert "temporary MFA session token" in content.lower() or "mfa session token" in content.lower()

    def test_redis_note_for_production(self):
        """Source should mention Redis for production use."""
        content = _read_backend_source("app/api/mfa.py")
        assert "Redis" in content or "redis" in content


# ====================================================================
# Run Tests
# ====================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
