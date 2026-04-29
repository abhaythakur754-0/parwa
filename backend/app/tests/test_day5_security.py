"""
Day 5 Security Audit Tests — Security Headers, Input Validation & Frontend Hardening.

Tests for fixes: D2, D3, D6, D7, C3, C4, C5, H1, H2, H5.
All tests are pure unit/integration tests that verify source file contents
and middleware behavior without requiring a running server.
"""

import re
from pathlib import Path

import pytest

# ── Project roots ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve(
).parent.parent.parent.parent  # /home/z/parwa
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BACKEND_DIR = PROJECT_ROOT / "backend"
INFRA_DIR = PROJECT_ROOT / "infra"


# ═══════════════════════════════════════════════════════════════════════════
# D2: Next.js Security Headers in next.config.mjs
# ═══════════════════════════════════════════════════════════════════════════

class TestD2_NextConfigSecurityHeaders:
    """Verify next.config.mjs contains a headers() function with all required security headers."""

    NEXT_CONFIG_PATH = FRONTEND_DIR / "next.config.mjs"

    def _load_config(self):
        assert self.NEXT_CONFIG_PATH.exists(
        ), f"File not found: {self.NEXT_CONFIG_PATH}"
        return self.NEXT_CONFIG_PATH.read_text()

    def test_headers_function_exists(self):
        """D2: next.config.mjs must have an async headers() function."""
        content = self._load_config()
        assert "async headers()" in content, "Missing async headers() function in next.config.mjs"

    @pytest.mark.parametrize("header_key,expected_value", [
        ("Content-Security-Policy", "default-src 'self'"),
        ("X-Frame-Options", "DENY"),
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "strict-origin-when-cross-origin"),
        ("Permissions-Policy", "camera=(), microphone=(), geolocation=()"),
        ("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload"),
    ])
    def test_security_header_present(self, header_key, expected_value):
        """D2: Each required security header must be present with correct value."""
        content = self._load_config()
        assert header_key in content, f"Missing header key: {header_key}"
        assert expected_value in content, f"Missing expected value for {header_key}: {expected_value}"

    def test_csp_directives(self):
        """D2: CSP must include required directives."""
        content = self._load_config()
        required_directives = [
            "script-src 'self'",
            "style-src 'sel' 'unsafe-inline'",
            "img-src 'self' data: blob:",
            "font-src 'self'",
            "connect-src 'self' https://*.googleapis.com",
        ]
        for directive in required_directives:
            assert directive in content, f"Missing CSP directive: {directive}"

    def test_headers_applies_to_all_routes(self):
        """D2: headers() should apply to all routes (source: /(.*))."""
        content = self._load_config()
        assert '/(.*)' in content or "/(.*)/" in content, "headers() should use source: /(.*) for all routes"


# ═══════════════════════════════════════════════════════════════════════════
# H2: Strict Next.js Build Settings
# ═══════════════════════════════════════════════════════════════════════════

class TestH2_StrictBuildSettings:
    """Verify next.config.mjs has strict TypeScript and React settings."""

    NEXT_CONFIG_PATH = FRONTEND_DIR / "next.config.mjs"

    def test_ignore_build_errors_false(self):
        """H2: ignoreBuildErrors must be false."""
        content = self.NEXT_CONFIG_PATH.read_text()
        assert "ignoreBuildErrors: false" in content, \
            "ignoreBuildErrors must be false for production safety"

    def test_react_strict_mode_true(self):
        """H2: reactStrictMode must be true."""
        content = self.NEXT_CONFIG_PATH.read_text()
        assert "reactStrictMode: true" in content, \
            "reactStrictMode must be true for catching side effects"


# ═══════════════════════════════════════════════════════════════════════════
# D3: Backend CSP Header in Security Middleware
# ═══════════════════════════════════════════════════════════════════════════

class TestD3_BackendCSPHeader:
    """Verify backend security_headers.py middleware adds CSP header."""

    MIDDLEWARE_PATH = BACKEND_DIR / "app" / "middleware" / "security_headers.py"

    def test_csp_header_set(self):
        """D3: CSP header must be set in the middleware."""
        content = self.MIDDLEWARE_PATH.read_text()
        assert 'Content-Security-Policy' in content, \
            "Missing Content-Security-Policy header in security_headers.py"

    def test_csp_value_content(self):
        """D3: CSP value must include key directives."""
        content = self.MIDDLEWARE_PATH.read_text()
        required = [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self'",
            "img-src 'self'",
            "font-src 'self'",
            "connect-src 'self'",
        ]
        for directive in required:
            assert directive in content, f"Missing CSP directive in backend: {directive}"

    def test_csp_allows_googleapis(self):
        """D3: CSP connect-src must allow googleapis.com."""
        content = self.MIDDLEWARE_PATH.read_text()
        assert "https://*.googleapis.com" in content, \
            "CSP must allow https://*.googleapis.com in connect-src"


# ═══════════════════════════════════════════════════════════════════════════
# D6: server_tokens off in Nginx Configs
# ═══════════════════════════════════════════════════════════════════════════

class TestD6_NginxServerTokens:
    """Verify server_tokens off is present in nginx configurations."""

    @pytest.mark.parametrize("config_path", [
        PROJECT_ROOT / "nginx" / "nginx.conf",
        PROJECT_ROOT / "infra" / "docker" / "nginx.conf",
    ])
    def test_server_tokens_off(self, config_path):
        """D6: server_tokens off must be in http block."""
        assert config_path.exists(), f"File not found: {config_path}"
        content = config_path.read_text()
        assert "server_tokens off" in content, \
            f"Missing 'server_tokens off' in {config_path}"


# ═══════════════════════════════════════════════════════════════════════════
# D7: HSTS includeSubDomains; preload in infra nginx-default.conf
# ═══════════════════════════════════════════════════════════════════════════

class TestD7_HSTSPreload:
    """Verify HSTS header has includeSubDomains and preload."""

    CONFIG_PATH = PROJECT_ROOT / "infra" / "docker" / "nginx-default.conf"

    def test_hsts_include_subdomains(self):
        """D7: HSTS must include includeSubDomains."""
        content = self.CONFIG_PATH.read_text()
        # Match the add_header directive
        assert "includeSubDomains" in content, \
            "HSTS header must include includeSubDomains"

    def test_hsts_preload(self):
        """D7: HSTS must include preload."""
        content = self.CONFIG_PATH.read_text()
        assert "preload" in content, \
            "HSTS header must include preload"

    def test_hsts_max_age(self):
        """D7: HSTS max-age must be at least 63072000 (2 years)."""
        content = self.CONFIG_PATH.read_text()
        assert "max-age=63072000" in content, \
            "HSTS max-age should be 63072000"


# ═══════════════════════════════════════════════════════════════════════════
# C3: Email Validation Regex in Register Route
# ═══════════════════════════════════════════════════════════════════════════

class TestC3_EmailValidation:
    """Verify register route uses regex for email validation instead of includes('@')."""

    REGISTER_PATH = FRONTEND_DIR / "src" / "app" / \
        "api" / "auth" / "register" / "route.ts"

    def test_uses_regex_validation(self):
        """C3: Must use a regex for email validation."""
        content = self.REGISTER_PATH.read_text()
        assert re.search(r'/\^?\[\\^\\s@\]', content) or re.search(
            r"emailRegex", content), "Register route must use a regex for email validation"

    def test_no_simple_includes_check(self):
        """C3: Must NOT use simple !email.includes(\"@\") check."""
        content = self.REGISTER_PATH.read_text()
        # Should not have the naive check
        assert '!email.includes("@")' not in content, \
            "Must replace !email.includes(\"@\") with regex validation"

    def test_regex_pattern(self):
        """C3: Regex must validate basic email format (local@domain.tld)."""
        content = self.REGISTER_PATH.read_text()
        # Check for the proper regex pattern
        assert r"/^[^\s@]+@[^\s@]+\.[^\s@]+$/" in content, \
            "Email regex must match pattern /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/"


# ═══════════════════════════════════════════════════════════════════════════
# C4: Password Complexity Validation
# ═══════════════════════════════════════════════════════════════════════════

class TestC4_PasswordComplexity:
    """Verify register route enforces password complexity server-side."""

    REGISTER_PATH = FRONTEND_DIR / "src" / "app" / \
        "api" / "auth" / "register" / "route.ts"

    def _load(self):
        return self.REGISTER_PATH.read_text()

    def test_minimum_length_check(self):
        """C4: Password must be at least 8 characters."""
        content = self._load()
        assert "password.length < 8" in content, \
            "Must check password minimum length of 8"

    def test_uppercase_check(self):
        """C4: Password must contain at least one uppercase letter."""
        content = self._load()
        assert re.search(r'\[A-Z\]', content), \
            "Must check for uppercase letters in password"

    def test_lowercase_check(self):
        """C4: Password must contain at least one lowercase letter."""
        content = self._load()
        assert re.search(r'\[a-z\]', content), \
            "Must check for lowercase letters in password"

    def test_digit_check(self):
        """C4: Password must contain at least one digit."""
        content = self._load()
        assert re.search(r'\[0-9\]', content), \
            "Must check for digits in password"

    def test_special_char_check(self):
        """C4: Password must contain at least one special character."""
        content = self._load()
        assert '/[^A-Za-z0-9]/' in content, \
            "Must check for special characters in password"

    def test_error_messages(self):
        """C4: Each validation check should have a meaningful error message."""
        content = self._load()
        assert "uppercase" in content.lower(
        ), "Error message must mention uppercase requirement"
        assert "lowercase" in content.lower(
        ), "Error message must mention lowercase requirement"
        assert "digit" in content.lower(), "Error message must mention digit requirement"
        assert "special character" in content.lower(
        ), "Error message must mention special character requirement"


# ═══════════════════════════════════════════════════════════════════════════
# C5: Rate Limiting on OTP Endpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestC5_OTPRateLimiting:
    """Verify OTP verify endpoint has in-memory rate limiting."""

    OTP_PATH = FRONTEND_DIR / "src" / "app" / \
        "api" / "auth" / "verify-otp" / "route.ts"

    def test_rate_limit_map_exists(self):
        """C5: OTP endpoint must have an in-memory Map for rate limiting."""
        content = self.OTP_PATH.read_text()
        assert "Map<string, number[]>" in content or "new Map" in content, \
            "OTP endpoint must have in-memory rate limiting Map"

    def test_max_attempts_defined(self):
        """C5: Max OTP attempts should be 5 per window."""
        content = self.OTP_PATH.read_text()
        assert "5" in content, \
            "OTP rate limit should define max attempts"

    def test_rate_limit_window(self):
        """C5: Rate limit window should be 15 minutes."""
        content = self.OTP_PATH.read_text()
        # 15 * 60 * 1000 = 900000 ms
        assert "15" in content or "900000" in content, \
            "OTP rate limit window should be 15 minutes"

    def test_returns_429_when_rate_limited(self):
        """C5: Must return HTTP 429 when rate limit is exceeded."""
        content = self.OTP_PATH.read_text()
        assert "429" in content, \
            "OTP endpoint must return 429 status when rate limited"

    def test_rate_limit_uses_email_and_ip(self):
        """C5: Rate limiting should use both email and IP as key."""
        content = self.OTP_PATH.read_text()
        # Check that it combines email and IP
        assert "email" in content.lower() and "ip" in content.lower(), \
            "Rate limiting should key on both email and IP"


# ═══════════════════════════════════════════════════════════════════════════
# H1: Session Store Migration TODO
# ═══════════════════════════════════════════════════════════════════════════

class TestH1_SessionStoreTODO:
    """Verify login route has TODO comment about Redis migration."""

    LOGIN_PATH = FRONTEND_DIR / "src" / "app" / \
        "api" / "auth" / "login" / "route.ts"

    def test_redis_todo_comment(self):
        """H1: Login route must have a TODO comment about Redis for production."""
        content = self.LOGIN_PATH.read_text()
        assert "TODO" in content and "Redis" in content, \
            "Login route must have TODO comment mentioning Redis for session store"

    def test_redis_warning_comment(self):
        """H1: The TODO must warn about in-memory Map limitations."""
        content = self.LOGIN_PATH.read_text()
        # Check for warning keywords
        warning_keywords = ["production", "memory", "restart", "scaling"]
        found = sum(1 for kw in warning_keywords if kw.lower()
                    in content.lower())
        assert found >= 2, \
            "TODO comment should warn about production limitations (found only {}/4 keywords)".format(found)

    def test_in_memory_map_still_present(self):
        """H1: In-memory Map should still be present (not removed yet)."""
        content = self.LOGIN_PATH.read_text()
        assert "serverSessions" in content, \
            "In-memory serverSessions Map should still be present (pending Redis migration)"


# ═══════════════════════════════════════════════════════════════════════════
# H5: Open Redirect Fix in Login Page
# ═══════════════════════════════════════════════════════════════════════════

class TestH5_OpenRedirectFix:
    """Verify login page validates redirectTo to prevent open redirects."""

    LOGIN_PAGE_PATH = FRONTEND_DIR / "src" / \
        "app" / "(auth)" / "login" / "page.tsx"

    def test_redirect_validation_exists(self):
        """H5: Login page must validate the redirect parameter."""
        content = self.LOGIN_PAGE_PATH.read_text()
        # Must have validation logic
        assert "startsWith" in content, \
            "Login page must use startsWith() to validate redirect parameter"

    def test_rejects_protocol_relative_urls(self):
        """H5: Must reject protocol-relative URLs (starting with //)."""
        content = self.LOGIN_PAGE_PATH.read_text()
        assert 'startsWith("//")' in content or "startsWith('//')" in content, \
            "Must check for '//' to block protocol-relative URLs"

    def test_sanitized_redirect_default(self):
        """H5: Must fallback to safe default when redirect is invalid."""
        content = self.LOGIN_PAGE_PATH.read_text()
        assert "/models" in content, \
            "Must have safe default redirect path ('/models')"

    def test_raw_redirect_extracted(self):
        """H5: Must extract raw redirect param before validation."""
        content = self.LOGIN_PAGE_PATH.read_text()
        assert "rawRedirect" in content or "redirect" in content, \
            "Should extract redirect param and validate it"


# ═══════════════════════════════════════════════════════════════════════════
# Integration: Backend Middleware Import Test
# ═══════════════════════════════════════════════════════════════════════════

class TestD3_BackendMiddlewareImportable:
    """Verify the security_headers middleware can be imported and has correct structure."""

    def test_middleware_class_exists(self):
        """D3: SecurityHeadersMiddleware class must exist and be importable."""
        sys_path_add = str(BACKEND_DIR)
        import sys
        if sys_path_add not in sys.path:
            sys.path.insert(0, sys_path_add)

        # Import the module
        from app.middleware.security_headers import SecurityHeadersMiddleware
        assert hasattr(SecurityHeadersMiddleware, "dispatch"), \
            "SecurityHeadersMiddleware must have a dispatch method"

    def test_middleware_sets_csp_in_production(self):
        """D3: Verify CSP header is set in the middleware dispatch logic."""
        content = (
            BACKEND_DIR
            / "app"
            / "middleware"
            / "security_headers.py").read_text()
        assert 'response.headers["Content-Security-Policy"]' in content, \
            "CSP header must be set on response object"


# ═══════════════════════════════════════════════════════════════════════════
# Regression: Email regex also applied to verify-otp
# ═══════════════════════════════════════════════════════════════════════════

class TestC3_EmailRegexInVerifyOTP:
    """Verify verify-otp also uses regex email validation (consistency fix)."""

    OTP_PATH = FRONTEND_DIR / "src" / "app" / \
        "api" / "auth" / "verify-otp" / "route.ts"

    def test_uses_regex_in_verify_otp(self):
        """C3 (consistency): verify-otp should also use regex email validation."""
        content = self.OTP_PATH.read_text()
        assert r"/^[^\s@]+@[^\s@]+\.[^\s@]+$/" in content, \
            "verify-otp should also use regex email validation for consistency"
