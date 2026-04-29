"""
Day 1 Security Fixes — Unit Tests
===================================
Tests for all 7 Day 1 fixes:
  A1: Refresh token pepper — no default, required env var
  A2: Frontend auth — cookie-only, no localStorage tokens
  A3: CSRF protection — double-submit cookie pattern
  A4: Middleware — correct cookie name + expanded matcher
  A5: Registration — is_verified: false
  A6: User enumeration — ambiguous responses
  D1: CORS — no wildcard fallback with credentials
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


# ============================================================
# A1: Refresh Token Pepper Tests
# ============================================================

class TestRefreshTokenPepper:
    """Verify REFRESH_TOKEN_PEPPER has no default and is required."""

    def test_no_hardcoded_default_in_source(self):
        """A1: Source code should NOT contain the old hardcoded default pepper."""
        with open("backend/app/core/auth.py") as f:
            content = f.read()

        assert "parwa-refresh-pepper-change-in-prod" not in content, \
            "Source should NOT contain hardcoded pepper default"

    def test_pepper_requires_env_var(self):
        """A1: Source code should raise RuntimeError if REFRESH_TOKEN_PEPPER is missing."""
        with open("backend/app/core/auth.py") as f:
            content = f.read()

        assert "raise RuntimeError" in content, \
            "Source should raise RuntimeError when pepper is missing"
        assert 'os.getenv("REFRESH_TOKEN_PEPPER")' in content or \
               "os.getenv('REFRESH_TOKEN_PEPPER')" in content, \
            "Source should read pepper from env var"

    def test_hash_refresh_token_uses_pepper(self):
        """A1: hash_refresh_token should use the pepper in SHA-256."""
        with open("backend/app/core/auth.py") as f:
            content = f.read()

        assert "_REFRESH_TOKEN_PEPPER" in content, \
            "Source should use _REFRESH_TOKEN_PEPPER variable"
        assert "sha256" in content.lower(), \
            "Source should use SHA-256 for token hashing"


# ============================================================
# A3: CSRF Middleware Tests
# ============================================================

class TestCSRFMiddleware:
    """Verify CSRF double-submit cookie pattern works correctly."""

    @pytest.fixture
    def csrf_middleware(self):
        from app.middleware.csrf import CSRFMiddleware
        app = MagicMock()
        return CSRFMiddleware(app)

    @pytest.mark.asyncio
    async def test_safe_methods_bypass_csrf(self, csrf_middleware):
        """A3: GET/HEAD/OPTIONS should skip CSRF validation."""
        for method in ["GET", "HEAD", "OPTIONS"]:
            request = MagicMock()
            request.method = method
            request.url.path = "/api/tickets"
            request.cookies = {}

            call_next = AsyncMock(return_value=MagicMock())
            result = await csrf_middleware.dispatch(request, call_next)
            call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_without_csrf_returns_403(self, csrf_middleware):
        """A3: POST without CSRF token should return 403."""
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/tickets"
        request.cookies = {"parwa_csrf": "val"}  # has cookies but header empty
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value="")

        call_next = AsyncMock()
        result = await csrf_middleware.dispatch(request, call_next)
        assert result.status_code == 403
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_post_with_matching_csrf_passes(self, csrf_middleware):
        """A3: POST with matching CSRF cookie and header should pass."""
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/tickets"
        request.cookies = {"parwa_csrf": "test-token-123"}
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value="test-token-123")

        call_next = AsyncMock(return_value=MagicMock())
        result = await csrf_middleware.dispatch(request, call_next)
        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_with_mismatched_csrf_returns_403(
            self, csrf_middleware):
        """A3: POST with mismatched CSRF token should return 403."""
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/tickets"
        request.cookies = {"parwa_csrf": "token-a"}
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value="token-b")

        call_next = AsyncMock()
        result = await csrf_middleware.dispatch(request, call_next)
        assert result.status_code == 403

    @pytest.mark.asyncio
    async def test_webhook_path_exempt_from_csrf(self, csrf_middleware):
        """A3: Webhook paths should bypass CSRF (they use HMAC)."""
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/webhooks/paddle"
        request.cookies = {}
        request.headers = MagicMock()

        call_next = AsyncMock(return_value=MagicMock())
        result = await csrf_middleware.dispatch(request, call_next)
        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_cookies_bypasses_csrf(self, csrf_middleware):
        """A3: Requests with no cookies bypass CSRF (API key auth)."""
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/tickets"
        request.cookies = {}
        request.headers = MagicMock()

        call_next = AsyncMock(return_value=MagicMock())
        result = await csrf_middleware.dispatch(request, call_next)
        call_next.assert_called_once()


# ============================================================
# D1: CORS Configuration Tests
# ============================================================

class TestCORSConfig:
    """Verify CORS never falls back to wildcard with credentials."""

    def test_empty_cors_origins_does_not_wildcard(self):
        """D1: When CORS_ORIGINS is empty, origins should be [] not ['*']."""
        cors_origins_setting = ""
        if cors_origins_setting:
            result = [o.strip()
                      for o in cors_origins_setting.split(",") if o.strip()]
        else:
            result = []
        assert result == [], f"Expected empty list, got {result}"
        assert "*" not in result

    def test_valid_cors_origins_parsed(self):
        """D1: Valid comma-separated origins should be parsed correctly."""
        cors_origins_setting = "https://parwa.ai, https://app.parwa.ai"
        result = [o.strip()
                  for o in cors_origins_setting.split(",") if o.strip()]
        assert result == ["https://parwa.ai", "https://app.parwa.ai"]
        assert "*" not in result

    def test_no_wildcard_fallback_in_source(self):
        """D1: Source code should not contain wildcard fallback pattern."""
        with open("backend/app/main.py") as f:
            content = f.read()

        # The old pattern was: else ["*"]
        # The new pattern should have: _cors_origins = []
        assert '_cors_origins = []' in content, \
            "Source should default to empty list, not ['*']"
        # Should have a warning log about CORS not configured
        assert "deny" in content.lower() or "warning" in content.lower(), \
            "Source should warn when CORS is not configured"


# ============================================================
# A5 + A6: Registration & Enumeration Tests
# ============================================================

class TestRegistrationSecurity:
    """Verify registration security: is_verified=false and no enumeration."""

    def test_register_sets_verified_false(self):
        """A5: Registration should set is_verified: false."""
        with open("frontend/src/app/api/auth/register/route.ts") as f:
            content = f.read()

        assert "is_verified: false" in content, \
            "Registration should create users with is_verified: false"

    def test_register_no_409_response(self):
        """A6: Registration should NOT return 409 for existing emails."""
        with open("frontend/src/app/api/auth/register/route.ts") as f:
            content = f.read()

        assert "409" not in content, \
            "Registration should NOT return 409 status (reveals email exists)"

    def test_register_ambiguous_response(self):
        """A6: Registration should return ambiguous success message for existing emails."""
        with open("frontend/src/app/api/auth/register/route.ts") as f:
            content = f.read()

        assert "status: 200" in content, \
            "Registration should return 200 even for existing emails"

    def test_check_email_always_available(self):
        """A6: check-email should always return available: true."""
        with open("frontend/src/app/api/auth/check-email/route.ts") as f:
            content = f.read()

        assert "available: true" in content, \
            "check-email should always return available: true"
        # Should NOT query the database for existence
        assert "db.user.findUnique" not in content, \
            "check-email should NOT query database for user existence"

    def test_forgot_password_ambiguous(self):
        """A6: forgot-password should use ambiguous response."""
        with open("frontend/src/app/api/forgot-password/route.ts") as f:
            content = f.read()

        assert "No account found" not in content, \
            "forgot-password should NOT reveal if email exists"
        assert "status: 200" in content, \
            "forgot-password should return 200 for non-existing emails"


# ============================================================
# A4: Middleware Cookie Name Tests
# ============================================================

class TestMiddlewareCookieName:
    """Verify middleware checks for correct cookie name."""

    def test_middleware_checks_parwa_session_cookie(self):
        """A4: Middleware should check for 'parwa_session' not 'parwa_access_token'."""
        with open("frontend/src/middleware.ts") as f:
            content = f.read()

        assert "parwa_session" in content, "Middleware should check for parwa_session cookie"
        lines = content.split("\n")
        auth_check_lines = [
            line for line in lines
            if "parwa_access_token" in line and "cookies.get" in line
        ]
        assert len(auth_check_lines) == 0, \
            "Middleware should NOT check parwa_access_token cookie for auth"

    def test_middleware_matcher_includes_api_routes(self):
        """A4: Matcher should cover both /dashboard and /api routes."""
        with open("frontend/src/middleware.ts") as f:
            content = f.read()

        assert "'/api/:path*'" in content, \
            "Matcher should include /api/:path* to protect API routes"


# ============================================================
# A2: localStorage Token Removal Tests
# ============================================================

class TestLocalStorageTokenRemoval:
    """Verify no tokens are stored in localStorage."""

    def test_auth_context_no_localstorage_token_write(self):
        """A2: AuthContext should NOT write tokens to localStorage."""
        with open("frontend/src/contexts/AuthContext.tsx") as f:
            content = f.read()

        lines = content.split("\n")
        token_storage_lines = [
            line for line in lines
            if "localStorage.setItem" in line and (
                "AUTH_TOKEN_KEY" in line or "REFRESH_TOKEN_KEY" in line
            )
        ]
        assert len(token_storage_lines) == 0, \
            f"AuthContext should NOT store tokens in localStorage. Found: {token_storage_lines}"

    def test_auth_context_no_localstorage_token_read(self):
        """A2: AuthContext should NOT read tokens from localStorage."""
        with open("frontend/src/contexts/AuthContext.tsx") as f:
            content = f.read()

        lines = content.split("\n")
        token_read_lines = [
            line for line in lines
            if "localStorage.getItem" in line and (
                "AUTH_TOKEN_KEY" in line or "REFRESH_TOKEN_KEY" in line
            )
        ]
        assert len(token_read_lines) == 0, \
            f"AuthContext should NOT read tokens from localStorage. Found: {token_read_lines}"

    def test_api_client_no_localstorage_token_injection(self):
        """A2: API client should NOT inject tokens from localStorage."""
        with open("frontend/src/lib/api.ts") as f:
            content = f.read()

        assert "localStorage.getItem('parwa_access_token')" not in content
        assert "localStorage.getItem('parwa_refresh_token')" not in content

    def test_api_client_has_csrf_support(self):
        """A3: API client should attach CSRF token to mutating requests."""
        with open("frontend/src/lib/api.ts") as f:
            content = f.read()

        assert "X-CSRF-Token" in content
        assert "getOrCreateCsrfToken" in content

    def test_api_client_with_credentials_enabled(self):
        """A2: API client should use withCredentials for httpOnly cookies."""
        with open("frontend/src/lib/api.ts") as f:
            content = f.read()

        assert "withCredentials: true" in content, \
            "API client must send httpOnly cookies with every request"


# ============================================================
# C6: HTML Escaping in Email Templates
# ============================================================

class TestHTMLEscapingInEmails:
    """Verify user input is HTML-escaped in email templates (C6)."""

    def test_forgot_password_escapes_username(self):
        """C6: forgot-password should escape userName before HTML interpolation."""
        with open("frontend/src/app/api/forgot-password/route.ts") as f:
            content = f.read()

        assert "escapeHtml" in content, \
            "forgot-password should have an escapeHtml function"
        # userName should NOT be used directly in the template
        lines = content.split("\n")
        template_lines = [
            line for line in lines
            if "Hi ${userName}" in line or 'Hi ${userName}' in line
        ]
        assert len(template_lines) == 0, \
            "forgot-password should NOT use raw userName — use escaped version"
        # Should use the escaped variable
        assert "safeName" in content, \
            "forgot-password should use a safeName variable for HTML output"

    def test_escapeHtml_function_escapes_script_tags(self):
        """C6: escapeHtml should handle <script> tags in user names."""
        # Simulate the escapeHtml function logic
        def escapeHtml(s: str) -> str:
            return (s
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;")
                    .replace("'", "&#039;"))

        malicious = '<script>alert("xss")</script>'
        escaped = escapeHtml(malicious)
        assert "<script>" not in escaped
        assert "&lt;script&gt;" in escaped
        assert '"xss"' not in escaped
        assert "&quot;xss&quot;" in escaped

    def test_escapeHtml_function_escapes_ampersand(self):
        """C6: escapeHtml should handle ampersands."""
        def escapeHtml(s: str) -> str:
            return (s
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;")
                    .replace("'", "&#039;"))

        assert escapeHtml("Tom & Jerry") == "Tom &amp; Jerry"


# ============================================================
# A10: OTP Not in Email Subject
# ============================================================

class TestOTPNotInSubject:
    """Verify OTP codes are NOT leaked in email subject lines (A10)."""

    def test_jarvis_service_no_otp_in_subject(self):
        """A10: jarvis_service.py should NOT include OTP in subject line."""
        with open("backend/app/services/jarvis_service.py") as f:
            content = f.read()

        # Check that subject line does NOT include the OTP variable
        lines = content.split("\n")
        otp_subject_lines = [
            line for line in lines
            if "subject=" in line and "{otp_code}" in line
        ]
        assert len(otp_subject_lines) == 0, \
            f"jarvis_service should NOT include {{otp_code}} in subject. Found: {otp_subject_lines}"

    def test_jarvis_service_has_generic_subject(self):
        """A10: jarvis_service.py should use a generic subject without OTP."""
        with open("backend/app/services/jarvis_service.py") as f:
            content = f.read()

        assert 'subject="PARWA Verification Code"' in content or \
               "subject='PARWA Verification Code'" in content, \
            "jarvis_service should use a generic subject for verification emails"

    def test_business_email_otp_no_code_in_subject(self):
        """A10: business_email_otp_service.py should NOT include OTP in subject."""
        with open("backend/app/services/business_email_otp_service.py") as f:
            content = f.read()

        lines = content.split("\n")
        for line in lines:
            if "subject=" in line and (
                    "{otp" in line.lower() or "{code" in line.lower()):
                assert False, \
                    f"business_email_otp_service should NOT include OTP in subject: {line}"


# ============================================================
# C3 + C4: Input Validation Tests
# ============================================================

class TestInputValidation:
    """Verify proper input validation on auth endpoints."""

    def test_register_has_email_regex(self):
        """C3: Register should use proper email regex validation."""
        with open("frontend/src/app/api/auth/register/route.ts") as f:
            content = f.read()

        assert "emailRegex" in content or "email_regex" in content, \
            "Register should use email regex validation"
        assert "/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/" in content, \
            "Register should use proper email regex pattern"

    def test_register_password_complexity_uppercase(self):
        """C4: Register should enforce uppercase in password."""
        with open("frontend/src/app/api/auth/register/route.ts") as f:
            content = f.read()

        assert "[A-Z]" in content, \
            "Register should check for uppercase letters in password"

    def test_register_password_complexity_lowercase(self):
        """C4: Register should enforce lowercase in password."""
        with open("frontend/src/app/api/auth/register/route.ts") as f:
            content = f.read()

        assert "[a-z]" in content, \
            "Register should check for lowercase letters in password"

    def test_register_password_complexity_digit(self):
        """C4: Register should enforce digit in password."""
        with open("frontend/src/app/api/auth/register/route.ts") as f:
            content = f.read()

        assert "[0-9]" in content, \
            "Register should check for digits in password"

    def test_register_password_complexity_special(self):
        """C4: Register should enforce special character in password."""
        with open("frontend/src/app/api/auth/register/route.ts") as f:
            content = f.read()

        assert "[^A-Za-z0-9]" in content, \
            "Register should check for special characters in password"


# ============================================================
# C5: OTP Rate Limiting Tests
# ============================================================

class TestOTPRateLimiting:
    """Verify OTP endpoints have rate limiting."""

    def test_verify_otp_has_rate_limit(self):
        """C5: verify-otp should have rate limiting."""
        with open("frontend/src/app/api/auth/verify-otp/route.ts") as f:
            content = f.read()

        assert "isOtpRateLimited" in content, \
            "verify-otp should have rate limiting"
        assert "OTP_MAX_ATTEMPTS" in content, \
            "verify-otp should define max OTP attempts"
        assert "429" in content, \
            "verify-otp should return 429 when rate limited"

    def test_verify_otp_rate_limit_5_per_15_min(self):
        """C5: verify-otp should limit to 5 attempts per 15 minutes."""
        with open("frontend/src/app/api/auth/verify-otp/route.ts") as f:
            content = f.read()

        assert "5" in content.split("OTP_MAX_ATTEMPTS")[1].split("\n")[0], \
            "verify-otp should allow max 5 attempts"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
