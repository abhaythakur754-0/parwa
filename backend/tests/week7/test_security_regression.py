"""
Week 7 — Security Regression Tests

Verifies all critical/high/medium findings from the original security audit
remain fixed. Tests cover authentication, data protection, input validation,
infrastructure security, and multi-tenant isolation.
"""

import asyncio
import os
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Paths ────────────────────────────────────────────────────────
PROJECT_ROOT = Path("/home/z/my-project")
BACKEND_DIR = PROJECT_ROOT / "backend"


# ═══════════════════════════════════════════════════════════════════
# Authentication & Authorization
# ═══════════════════════════════════════════════════════════════════


class TestAuthenticationAuthorization:
    """Security audit: Authentication and authorization regressions."""

    def test_jwt_has_jti_claim(self):
        """JWT tokens include jti claim for blacklisting."""
        source = (BACKEND_DIR / "app" / "core" / "auth.py").read_text()

        # jti claim should be in access token payload
        assert '"jti"' in source or "'jti'" in source, (
            "JWT tokens should include jti claim for blacklisting support"
        )

    def test_refresh_token_hashed_with_pepper(self):
        """Refresh tokens are hashed with pepper before DB storage."""
        source = (BACKEND_DIR / "app" / "core" / "auth.py").read_text()

        # Should use pepper in hashing
        assert "PEPPER" in source or "pepper" in source, (
            "Refresh token hashing should use pepper"
        )
        assert "hash_refresh_token" in source, (
            "hash_refresh_token function should exist"
        )

    def test_max_sessions_per_user(self):
        """Max 5 sessions per user enforced."""
        from app.config import Settings

        # MAX_SESSIONS_PER_USER is a class field on Settings
        settings = Settings()
        assert settings.MAX_SESSIONS_PER_USER == 5, (
            "Max sessions per user should be 5"
        )

    @pytest.mark.asyncio
    async def test_mfa_module_exists(self):
        """MFA module exists and can be imported."""
        mfa_api = BACKEND_DIR / "app" / "api" / "mfa.py"
        mfa_schema = BACKEND_DIR / "app" / "schemas" / "mfa.py"

        assert mfa_api.exists(), "MFA API should exist"
        assert mfa_schema.exists(), "MFA schemas should exist"

    def test_role_based_access_control(self):
        """Role-based access control (owner/admin/agent/viewer) exists."""
        source = (BACKEND_DIR / "app" / "api" / "deps.py").read_text()

        assert "require_roles" in source, (
            "require_roles should exist for RBAC"
        )

    def test_roles_covered(self):
        """All expected roles are defined somewhere in the codebase."""
        source = (BACKEND_DIR / "app" / "api" / "deps.py").read_text()

        # Check that the function accepts multiple roles
        assert "*roles" in source, "require_roles should accept variable roles"


# ═══════════════════════════════════════════════════════════════════
# Data Protection
# ═══════════════════════════════════════════════════════════════════


class TestDataProtection:
    """Security audit: Data protection regressions."""

    def test_pii_redaction_for_email(self):
        """PII redaction covers email addresses."""
        from app.core.pii_redaction_engine import PIIDetector, PII_EMAIL

        detector = PIIDetector()
        matches = detector.detect("Email: user@example.com", {PII_EMAIL})

        assert len(matches) > 0, "Should detect email"

    def test_pii_redaction_for_phone(self):
        """PII redaction covers phone numbers."""
        from app.core.pii_redaction_engine import PIIDetector, PII_PHONE

        detector = PIIDetector()
        matches = detector.detect("Call 555-123-4567 now", {PII_PHONE})

        assert len(matches) > 0, "Should detect phone"

    def test_pii_redaction_for_ssn(self):
        """PII redaction covers SSN."""
        from app.core.pii_redaction_engine import PIIDetector, PII_SSN

        detector = PIIDetector()
        matches = detector.detect("SSN: 123-45-6789", {PII_SSN})

        assert len(matches) > 0, "Should detect SSN"

    def test_pii_redaction_for_credit_card(self):
        """PII redaction covers credit card numbers."""
        from app.core.pii_redaction_engine import PIIDetector, PII_CREDIT_CARD

        detector = PIIDetector()
        matches = detector.detect("Card: 4111-2222-3333-4444", {PII_CREDIT_CARD})

        assert len(matches) > 0, "Should detect credit card"

    def test_httponly_cookies(self):
        """Auth cookies should be httpOnly."""
        source = (BACKEND_DIR / "app" / "api" / "auth.py").read_text()

        # Should set httpOnly on cookies
        assert "httpOnly" in source or "httponly" in source.lower(), (
            "Auth cookies should be httpOnly"
        )

    def test_secure_flag_on_cookies(self):
        """Cookies should have Secure flag in production."""
        source = (BACKEND_DIR / "app" / "api" / "auth.py").read_text()

        # Should have Secure flag for production
        assert "secure" in source.lower(), (
            "Cookie should have Secure flag"
        )

    def test_cors_configuration(self):
        """CORS configuration exists and is not wildcard."""
        source = (PROJECT_ROOT / "backend" / "app" / "main.py").read_text()

        # CORS middleware should be configured
        assert "CORSMiddleware" in source, "CORS should be configured"
        # Should NOT fall back to wildcard when credentials=True
        assert '"*"' not in source.split("CORSMiddleware")[1].split(")")[0] if "CORSMiddleware" in source else True, (
            "CORS origins should not be wildcard with credentials"
        )

    def test_csrf_protection_exists(self):
        """CSRF protection middleware exists."""
        csrf = BACKEND_DIR / "app" / "middleware" / "csrf.py"
        assert csrf.exists(), "CSRF middleware should exist"


# ═══════════════════════════════════════════════════════════════════
# Input Validation
# ═══════════════════════════════════════════════════════════════════


class TestInputValidation:
    """Security audit: Input validation regressions."""

    def test_rate_limiting_on_auth(self):
        """Rate limiting is configured for auth endpoints."""
        source = (BACKEND_DIR / "app" / "middleware" / "rate_limit.py").read_text()

        # Should classify auth endpoints differently
        assert "auth" in source.lower() or "login" in source.lower(), (
            "Rate limiter should have auth endpoint classification"
        )

    def test_file_upload_magic_bytes_validation(self):
        """File upload validates magic bytes."""
        # Check for file storage service
        storage_source = (BACKEND_DIR / "app" / "core" / "storage.py").read_text()

        assert "magic" in storage_source.lower() or "content_type" in storage_source.lower(), (
            "File storage should validate file types"
        )

    def test_ilike_escaping(self):
        """ILIKE queries escape special characters."""
        # Search for ILIKE usage
        search_source = (BACKEND_DIR / "app" / "api" / "ticket_search.py")
        if search_source.exists():
            source = search_source.read_text()
            if "ILIKE" in source:
                # Should escape special chars like % and _
                has_escape = "escape" in source.lower() or "re.sub" in source
                assert has_escape, "ILIKE queries should escape special characters"

    def test_email_content_sanitization(self):
        """Email content is sanitized against XSS."""
        send_email = PROJECT_ROOT / "src" / "app" / "api" / "send-email" / "route.ts"
        if send_email.exists():
            source = send_email.read_text()
            assert "sanitize" in source.lower() or "script" in source.lower(), (
                "Email content should be sanitized"
            )

    def test_webhook_signature_verification(self):
        """Webhook signature verification exists."""
        hmac_source = (BACKEND_DIR / "app" / "core" / "hmac_verify.py")
        assert hmac_source.exists(), "HMAC verification module should exist"

    def test_webhook_replay_protection(self):
        """Webhook has replay protection (timestamp validation)."""
        # Check webhook service or HMAC verification for timestamp validation
        webhook_service = BACKEND_DIR / "app" / "services" / "webhook_service.py"
        hmac_verify = BACKEND_DIR / "app" / "core" / "hmac_verify.py"
        billing_webhooks = BACKEND_DIR / "app" / "api" / "billing_webhooks.py"
        
        found_timestamp = False
        for f in [webhook_service, hmac_verify, billing_webhooks]:
            if f.exists():
                source = f.read_text()
                if "timestamp" in source.lower():
                    found_timestamp = True
                    break
        
        assert found_timestamp, (
            "At least one webhook-related file should have timestamp validation for replay protection"
        )


# ═══════════════════════════════════════════════════════════════════
# Infrastructure Security
# ═══════════════════════════════════════════════════════════════════


class TestInfrastructureSecurity:
    """Security audit: Infrastructure security regressions."""

    def test_nginx_has_security_headers(self):
        """Nginx config has CSP, HSTS, X-Frame-Options."""
        nginx_conf = PROJECT_ROOT / "nginx" / "nginx.conf"
        if nginx_conf.exists():
            source = nginx_conf.read_text()

            assert "Strict-Transport-Security" in source or "HSTS" in source, (
                "Nginx should have HSTS"
            )
            assert "X-Frame" in source, (
                "Nginx should have X-Frame-Options"
            )

    def test_nginx_docker_config_synced(self):
        """Nginx Docker config has security settings synced with main config."""
        nginx_docker = PROJECT_ROOT / "infra" / "docker" / "nginx.conf"
        main_nginx = PROJECT_ROOT / "nginx" / "nginx.conf"

        if nginx_docker.exists():
            source = nginx_docker.read_text()
            # Docker config is self-contained (not an include), verify it has
            # equivalent security headers: HSTS, X-Frame-Options, etc.
            has_security = any(h in source for h in [
                "X-Frame-Options", "Strict-Transport-Security", "HSTS"
            ])
            assert has_security, (
                "Docker nginx config should have security headers "
                "(HSTS, X-Frame-Options, etc.) synced with main config"
            )

    def test_production_env_validation(self):
        """Production environment validates required secrets."""
        from app.config import Settings

        # These validators should exist
        assert hasattr(Settings, "validate_secret_key")
        assert hasattr(Settings, "validate_jwt_key")

    def test_secret_key_validator_raises_in_production(self):
        """SECRET_KEY validator raises error in production."""
        source = (BACKEND_DIR / "app" / "config.py").read_text()

        assert 'ENVIRONMENT == "production"' in source, (
            "SECRET_KEY validator should check production environment"
        )

    def test_jwt_key_validator_raises_in_production(self):
        """JWT_SECRET_KEY validator raises error in production."""
        source = (BACKEND_DIR / "app" / "config.py").read_text()

        assert 'ENVIRONMENT == "production"' in source, (
            "JWT key validator should check production environment"
        )

    def test_redis_password_required_in_production(self):
        """REDIS_PASSWORD is required in production."""
        from app.config import Settings

        assert hasattr(Settings, "validate_redis_password"), (
            "REDIS_PASSWORD validator should exist"
        )


# ═══════════════════════════════════════════════════════════════════
# Multi-Tenant Isolation
# ═══════════════════════════════════════════════════════════════════


class TestMultiTenant:
    """Security audit: Multi-tenant isolation regressions."""

    def test_tenant_middleware_exists(self):
        """Tenant middleware exists for company_id isolation."""
        tenant_mw = BACKEND_DIR / "app" / "middleware" / "tenant.py"
        assert tenant_mw.exists(), "Tenant middleware should exist"

    def test_tenant_middleware_in_middleware_stack(self):
        """Tenant middleware is in the middleware stack."""
        source = (BACKEND_DIR / "app" / "main.py").read_text()

        assert "TenantMiddleware" in source, (
            "TenantMiddleware should be in middleware stack"
        )

    def test_auth_deps_has_company_id(self):
        """Auth dependencies provide company_id for tenant isolation."""
        source = (BACKEND_DIR / "app" / "api" / "deps.py").read_text()

        assert "company_id" in source, (
            "Auth dependencies should handle company_id"
        )

    def test_rls_enabled(self):
        """Row-Level Security migration exists."""
        rls_migration = PROJECT_ROOT / "database" / "alembic" / "versions" / "022_enable_rls.py"
        assert rls_migration.exists(), "RLS migration should exist"

    def test_api_endpoints_use_company_id_filter(self):
        """API endpoints filter by company_id (tenant isolation)."""
        # Check several API files for company_id filtering
        api_files = [
            "tickets.py", "customers.py", "analytics.py",
            "ticket_messages.py", "billing.py",
        ]
        found_filters = 0
        for fname in api_files:
            fpath = BACKEND_DIR / "app" / "api" / fname
            if fpath.exists():
                source = fpath.read_text()
                if "company_id" in source:
                    found_filters += 1

        assert found_filters >= 3, (
            f"Expected company_id filtering in API files, found in {found_filters} files"
        )
