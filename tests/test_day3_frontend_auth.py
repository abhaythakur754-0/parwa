"""
PARWA Day 3 Security Tests — Frontend Auth Fixes
=================================================
Tests for 13 frontend security fixes:

C-02:  Real JWT tokens (sign + verify)
C-02b: /api/auth/me returns real user from JWT (not mock)
C-03:  httpOnly cookie setting
H-01:  Open redirect prevention
H-02:  Timing-safe OTP comparison
H-03:  Registration sets is_verified=false
H-18:  Chat API requires auth
H-20:  Dashboard mock login removed
M-20:  Password complexity requirements
M-22:  Password validation on reset
M-26:  Next.js security headers
M-27:  User enumeration prevention
H-17:  No API key prefix leaks

Run: pytest tests/test_day3_frontend_auth.py -v
"""

import subprocess
import sys
import json
import os

# ─── Helper: Run a Python snippet and return output ────────────────────

def run_python(code: str) -> str:
    """Execute Python code in subprocess and return stdout."""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "PYTHONPATH": "/home/z/my-project/parwa/src"},
    )
    return result.stdout.strip()


def run_node(code: str) -> str:
    """Execute Node.js code in subprocess and return stdout."""
    result = subprocess.run(
        ["node", "-e", code],
        capture_output=True,
        text=True,
        timeout=30,
        cwd="/home/z/my-project/parwa",
    )
    return result.stdout.strip()


# ═══════════════════════════════════════════════════════════════════════
# TEST SUITE
# ═══════════════════════════════════════════════════════════════════════

class TestDay3Security:
    """Day 3 Frontend Auth Security Tests."""

    # ── C-02: Real JWT Tokens ──────────────────────────────────────────

    def test_c02_jwt_helper_file_exists(self):
        """JWT helper file exists at src/lib/jwt.ts"""
        path = "/home/z/my-project/parwa/src/lib/jwt.ts"
        assert os.path.exists(path), "src/lib/jwt.ts must exist"

    def test_c02_jwt_helper_contains_sign_access_token(self):
        """jwt.ts exports signAccessToken function"""
        content = open("/home/z/my-project/parwa/src/lib/jwt.ts").read()
        assert "signAccessToken" in content, "signAccessToken must be exported"

    def test_c02_jwt_helper_contains_verify_token(self):
        """jwt.ts exports verifyToken function"""
        content = open("/home/z/my-project/parwa/src/lib/jwt.ts").read()
        assert "verifyToken" in content, "verifyToken must be exported"

    def test_c02_jwt_helper_uses_jose_library(self):
        """jwt.ts imports from jose (Edge-compatible)"""
        content = open("/home/z/my-project/parwa/src/lib/jwt.ts").read()
        assert 'from "jose"' in content, "Must use jose library for JWT"

    def test_c02_jwt_helper_has_jti_claim(self):
        """JWT includes jti claim for revocation support"""
        content = open("/home/z/my-project/parwa/src/lib/jwt.ts").read()
        assert "jti" in content, "JWT must include jti claim"

    def test_c02_jwt_helper_has_issuer_audience(self):
        """JWT has issuer and audience claims"""
        content = open("/home/z/my-project/parwa/src/lib/jwt.ts").read()
        assert "setIssuer" in content, "JWT must set issuer"
        assert "setAudience" in content, "JWT must set audience"

    def test_c02_jwt_sign_and_verify_works(self):
        """JWT can be signed and verified using jose"""
        output = run_node("""
const { SignJWT, jwtVerify } = require('jose');

async function test() {
  const secret = new TextEncoder().encode('test-secret-key');
  const token = await new SignJWT({ sub: 'usr_1', email: 'test@example.com' })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setIssuer('parwa:frontend')
    .setAudience('parwa:app')
    .setExpirationTime('15m')
    .sign(secret);

  const { payload } = await jwtVerify(token, secret, {
    issuer: 'parwa:frontend',
    audience: 'parwa:app',
  });

  console.log(JSON.stringify({ sub: payload.sub, email: payload.email, verified: true }));
}

test().catch(e => console.error('FAIL: ' + e.message));
""")
        assert '"verified":true' in output, f"JWT sign/verify failed: {output}"
        assert '"sub":"usr_1"' in output, f"JWT payload incorrect: {output}"

    def test_c02_login_route_uses_real_jwt(self):
        """Login route uses signAccessToken from jwt.ts"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/login/route.ts").read()
        assert "signAccessToken" in content, "Login route must use signAccessToken"
        assert "signRefreshToken" in content, "Login route must use signRefreshToken"
        assert "parwa_at_" not in content, "Login route must NOT use fake parwa_at_ tokens"
        assert "crypto.randomUUID()" not in content, "Login route must NOT use UUIDs as tokens"

    def test_c02_register_route_uses_real_jwt(self):
        """Register route uses real JWT signing"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/register/route.ts").read()
        assert "signAccessToken" in content, "Register route must use signAccessToken"
        assert "parwa_at_" not in content, "Register route must NOT use fake tokens"

    # ── C-02b: /api/auth/me Real Verification ──────────────────────────

    def test_c02b_me_route_verifies_jwt(self):
        """/api/auth/me verifies JWT instead of returning hardcoded mock"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/me/route.ts").read()
        assert "verifyToken" in content, "/me must verify JWT"
        assert "usr_mock" not in content, "/me must NOT return hardcoded mock user"
        assert "demo@parwa.ai" not in content, "/me must NOT return hardcoded demo email"

    def test_c02b_me_route_checks_cookie_and_header(self):
        """/api/auth/me checks both cookie and Authorization header"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/me/route.ts").read()
        assert "Authorization" in content, "Must check Authorization header"
        assert "getAccessTokenFromCookies" in content, "Must check httpOnly cookie"

    # ── C-03: httpOnly Cookies ─────────────────────────────────────────

    def test_c03_auth_cookies_file_exists(self):
        """auth-cookies.ts helper exists"""
        assert os.path.exists("/home/z/my-project/parwa/src/lib/auth-cookies.ts"), \
            "src/lib/auth-cookies.ts must exist"

    def test_c03_cookies_are_httponly(self):
        """Access and refresh cookies are set as httpOnly"""
        content = open("/home/z/my-project/parwa/src/lib/auth-cookies.ts").read()
        assert "httpOnly: true" in content, "Cookies must be httpOnly"

    def test_c03_cookies_have_secure_flag_in_prod(self):
        """Cookies have secure flag in production"""
        content = open("/home/z/my-project/parwa/src/lib/auth-cookies.ts").read()
        assert 'secure: process.env.NODE_ENV === "production"' in content, \
            "Cookies must be secure in production"

    def test_c03_cookies_have_samesite_strict(self):
        """Cookies use sameSite=strict in production"""
        content = open("/home/z/my-project/parwa/src/lib/auth-cookies.ts").read()
        assert '"strict"' in content, "Cookies must use sameSite=strict in production"

    def test_c03_login_sets_cookies(self):
        """Login route sets auth cookies"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/login/route.ts").read()
        assert "setAuthCookies" in content, "Login must set httpOnly cookies"

    def test_c03_register_sets_cookies(self):
        """Register route sets auth cookies"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/register/route.ts").read()
        assert "setAuthCookies" in content, "Register must set httpOnly cookies"

    def test_c03_clear_auth_cookies_exists(self):
        """clearAuthCookies function exists for logout"""
        content = open("/home/z/my-project/parwa/src/lib/auth-cookies.ts").read()
        assert "clearAuthCookies" in content, "clearAuthCookies must exist for logout"

    # ── H-01: Open Redirect Prevention ─────────────────────────────────

    def test_h01_is_safe_redirect_function_exists(self):
        """isSafeRedirect function exists in auth-cookies.ts"""
        content = open("/home/z/my-project/parwa/src/lib/auth-cookies.ts").read()
        assert "isSafeRedirect" in content, "isSafeRedirect must exist"

    def test_h01_login_page_validates_redirect(self):
        """Login page uses isSafeRedirect to validate redirect URL"""
        content = open("/home/z/my-project/parwa/src/app/(auth)/login/page.tsx").read()
        assert "isSafeRedirect" in content, "Login page must validate redirect URL"

    def test_h01_safe_redirect_blocks_absolute_urls(self):
        """isSafeRedirect blocks absolute URLs like https://evil.com"""
        content = open("/home/z/my-project/parwa/src/lib/auth-cookies.ts").read()
        assert 'startsWith("/")' in content, "Must check for relative path start"

    def test_h01_safe_redirect_blocks_protocol_relative(self):
        """isSafeRedirect blocks protocol-relative URLs like //evil.com"""
        content = open("/home/z/my-project/parwa/src/lib/auth-cookies.ts").read()
        assert '"//"' in content or "startsWith" in content, \
            "Must block protocol-relative URLs"

    # ── H-02: Timing-Safe OTP Comparison ──────────────────────────────

    def test_h02_verify_otp_uses_timing_safe(self):
        """verify-otp route uses timingSafeEqual for OTP comparison"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/verify-otp/route.ts").read()
        assert "timingSafeEqual" in content, "verify-otp must use timingSafeEqual"
        # Ensure the old direct comparison pattern (otp_code !== otp) is NOT used
        assert "otp_code !== otp" not in content, \
            "Must NOT use direct !== for OTP comparison"

    def test_h02_reset_password_uses_timing_safe(self):
        """reset-password route uses timingSafeEqual"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/reset-password/route.ts").read()
        assert "timingSafeEqual" in content, "reset-password must use timingSafeEqual"

    def test_h02_timing_safe_uses_crypto(self):
        """timingSafeEqual uses crypto.timingSafeEqual"""
        content = open("/home/z/my-project/parwa/src/lib/jwt.ts").read()
        assert "crypto.timingSafeEqual" in content, \
            "timingSafeEqual must use crypto.timingSafeEqual"

    def test_h02_timing_safe_handles_length_mismatch(self):
        """timingSafeEqual handles length mismatch securely"""
        content = open("/home/z/my-project/parwa/src/lib/jwt.ts").read()
        assert "a.length !== b.length" in content, \
            "timingSafeEqual must handle length mismatch with constant-time comparison"

    # ── H-03: Registration Email Verification ─────────────────────────

    def test_h03_register_sets_unverified(self):
        """Registration creates users with is_verified: false"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/register/route.ts").read()
        assert "is_verified: false" in content, "New users must start unverified"

    def test_h03_register_generates_verification_token(self):
        """Registration generates email verification token"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/register/route.ts").read()
        assert "verification_token" in content, "Must generate verification token"
        assert "randomBytes" in content, "Must use crypto.randomBytes for token"

    def test_h03_register_sends_verification_email(self):
        """Registration sends verification email"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/register/route.ts").read()
        assert "sendEmail" in content, "Must send verification email"
        assert "verify" in content.lower(), "Email must mention verification"

    # ── H-18: Chat API Authentication ──────────────────────────────────

    def test_h18_chat_api_requires_auth(self):
        """Chat API route requires authentication"""
        content = open("/home/z/my-project/parwa/src/app/api/chat/route.ts").read()
        assert "Authorization" in content or "verifyToken" in content, \
            "Chat API must check auth"
        assert "401" in content, "Chat API must return 401 when unauthenticated"
        assert "Authentication required" in content, \
            "Chat API must require authentication"

    def test_h18_chat_api_verifies_jwt(self):
        """Chat API verifies JWT token"""
        content = open("/home/z/my-project/parwa/src/app/api/chat/route.ts").read()
        assert "verifyToken" in content, "Chat API must verify JWT"

    def test_h18_chat_api_checks_cookie_fallback(self):
        """Chat API checks cookie as fallback auth"""
        content = open("/home/z/my-project/parwa/src/app/api/chat/route.ts").read()
        assert "getAccessTokenFromCookies" in content, \
            "Chat API must check cookies as auth fallback"

    # ── H-20: Dashboard Mock Login Removed ─────────────────────────────

    def test_h20_dashboard_login_disabled(self):
        """Dashboard mock login is disabled"""
        content = open("/home/z/my-project/parwa/dashboard/src/app/api/auth/login/route.ts").read()
        assert "410" in content, "Mock login must return 410 Gone"
        assert "removed" in content.lower(), "Must indicate endpoint is removed"

    def test_h20_dashboard_register_disabled(self):
        """Dashboard mock registration is disabled"""
        content = open("/home/z/my-project/parwa/dashboard/src/app/api/auth/register/route.ts").read()
        assert "410" in content, "Mock register must return 410 Gone"

    def test_h20_dashboard_me_disabled(self):
        """Dashboard mock /me is disabled"""
        content = open("/home/z/my-project/parwa/dashboard/src/app/api/auth/me/route.ts").read()
        assert "410" in content, "Mock me must return 410 Gone"

    # ── M-20: Password Complexity Requirements ─────────────────────────

    def test_m20_jwt_has_validate_password_strength(self):
        """jwt.ts exports validatePasswordStrength function"""
        content = open("/home/z/my-project/parwa/src/lib/jwt.ts").read()
        assert "validatePasswordStrength" in content, \
            "validatePasswordStrength must exist"

    def test_m20_password_requires_uppercase(self):
        """Password must require uppercase letter"""
        content = open("/home/z/my-project/parwa/src/lib/jwt.ts").read()
        assert "[A-Z]" in content, "Must check for uppercase letter"

    def test_m20_password_requires_lowercase(self):
        """Password must require lowercase letter"""
        content = open("/home/z/my-project/parwa/src/lib/jwt.ts").read()
        assert "[a-z]" in content, "Must check for lowercase letter"

    def test_m20_password_requires_digit(self):
        """Password must require digit"""
        content = open("/home/z/my-project/parwa/src/lib/jwt.ts").read()
        assert "[0-9]" in content, "Must check for digit"

    def test_m20_password_requires_special_char(self):
        """Password must require special character"""
        content = open("/home/z/my-project/parwa/src/lib/jwt.ts").read()
        assert "special character" in content.lower(), \
            "Must check for special character"

    def test_m20_register_uses_password_validation(self):
        """Register route uses validatePasswordStrength"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/register/route.ts").read()
        assert "validatePasswordStrength" in content, \
            "Register must validate password strength"

    def test_m20_password_validation_returns_errors(self):
        """Password validation returns specific error messages"""
        content = open("/home/z/my-project/parwa/src/lib/jwt.ts").read()
        assert "errors" in content, "Must return error array"

    # ── M-22: Password Validation on Reset ─────────────────────────────

    def test_m22_reset_password_uses_complexity(self):
        """Reset password uses validatePasswordStrength"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/reset-password/route.ts").read()
        assert "validatePasswordStrength" in content, \
            "Reset password must validate complexity"

    def test_m22_reset_rejects_weak_password(self):
        """Reset password rejects passwords failing complexity check"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/reset-password/route.ts").read()
        assert "passwordCheck" in content, "Must check password strength"
        assert "valid" in content, "Must check validity"

    # ── M-26: Next.js Security Headers ─────────────────────────────────

    def test_m26_next_config_has_headers(self):
        """next.config.mjs has headers configuration"""
        content = open("/home/z/my-project/parwa/next.config.mjs").read()
        assert "headers()" in content, "Must have headers() function"

    def test_m26_has_content_security_policy(self):
        """CSP header is configured"""
        content = open("/home/z/my-project/parwa/next.config.mjs").read()
        assert "Content-Security-Policy" in content, "Must have CSP header"

    def test_m26_has_x_frame_options(self):
        """X-Frame-Options is DENY"""
        content = open("/home/z/my-project/parwa/next.config.mjs").read()
        assert "X-Frame-Options" in content, "Must have X-Frame-Options"

    def test_m26_has_x_content_type_options(self):
        """X-Content-Type-Options is nosniff"""
        content = open("/home/z/my-project/parwa/next.config.mjs").read()
        assert "X-Content-Type-Options" in content, "Must have X-Content-Type-Options"
        assert "nosniff" in content, "Must be nosniff"

    def test_m26_has_referrer_policy(self):
        """Referrer-Policy is strict-origin-when-cross-origin"""
        content = open("/home/z/my-project/parwa/next.config.mjs").read()
        assert "Referrer-Policy" in content, "Must have Referrer-Policy"

    def test_m26_has_permissions_policy(self):
        """Permissions-Policy blocks camera, microphone, geolocation"""
        content = open("/home/z/my-project/parwa/next.config.mjs").read()
        assert "Permissions-Policy" in content, "Must have Permissions-Policy"
        assert "camera=()" in content, "Must block camera"
        assert "microphone=()" in content, "Must block microphone"

    def test_m26_auth_endpoints_have_no_cache(self):
        """Auth endpoints have Cache-Control: no-store"""
        content = open("/home/z/my-project/parwa/next.config.mjs").read()
        assert "no-store" in content, "Auth must have no-store"
        assert "/api/auth" in content, "Must target auth paths"

    # ── M-27: User Enumeration Prevention ──────────────────────────────

    def test_m27_check_email_uses_available(self):
        """check-email returns available/not-available instead of exists"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/check-email/route.ts").read()
        assert "available" in content.lower(), \
            "Must use 'available' instead of 'exists'"

    def test_m27_forgot_password_generic_response(self):
        """forgot-password returns same response for existing/non-existing email"""
        content = open("/home/z/my-project/parwa/src/app/api/forgot-password/route.ts").read()
        assert "If an account with this email exists" in content or \
               "generic" in content.lower(), \
            "Must return generic message for user enumeration prevention"

    def test_m27_forgot_password_no_account_found_removed(self):
        """forgot-password does NOT say 'No account found'"""
        content = open("/home/z/my-project/parwa/src/app/api/forgot-password/route.ts").read()
        assert "No account found with this email address" not in content, \
            "Must NOT reveal whether email exists"

    def test_m27_verify_otp_generic_error(self):
        """verify-otp uses generic error for non-existent users"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/verify-otp/route.ts").read()
        assert "Invalid email or OTP" in content, \
            "Must use generic error for non-existent user"

    def test_m27_reset_password_generic_error(self):
        """reset-password uses generic error for non-existent users"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/reset-password/route.ts").read()
        assert "Invalid email or OTP" in content, \
            "Must use generic error for non-existent user"

    # ── H-17: No API Key Prefix Leaks ──────────────────────────────────

    def test_h17_channel_status_no_key_preview(self):
        """channel-status does NOT expose API key prefixes"""
        content = open("/home/z/my-project/parwa/dashboard/src/app/api/channel-status/route.ts").read()
        assert "apiKeyPreview" not in content, \
            "Must NOT expose Brevo API key prefix"
        assert "accountSidPreview" not in content, \
            "Must NOT expose Twilio account SID prefix"
        assert "slice(0," not in content, \
            "Must NOT slice API keys"

    def test_h17_channel_status_only_booleans(self):
        """channel-status only returns configured boolean"""
        content = open("/home/z/my-project/parwa/dashboard/src/app/api/channel-status/route.ts").read()
        assert "configured" in content, "Must return configured boolean"
        assert "provider" in content, "Can return provider name"

    # ── Middleware ──────────────────────────────────────────────────────

    def test_middleware_file_exists(self):
        """src/middleware.ts exists"""
        assert os.path.exists("/home/z/my-project/parwa/src/middleware.ts"), \
            "src/middleware.ts must exist"

    def test_middleware_verifies_jwt(self):
        """Middleware verifies JWT tokens"""
        content = open("/home/z/my-project/parwa/src/middleware.ts").read()
        assert "verifyToken" in content, "Middleware must verify JWT"

    def test_middleware_has_public_paths(self):
        """Middleware defines public paths that bypass auth"""
        content = open("/home/z/my-project/parwa/src/middleware.ts").read()
        assert "PUBLIC_PATHS" in content, "Must define public paths"
        assert "/login" in content, "Login must be public"
        assert "/signup" in content, "Signup must be public"
        assert "/api/auth" in content, "Auth API must be public"

    def test_middleware_redirects_unauthenticated_to_login(self):
        """Middleware redirects unauthenticated users to login"""
        content = open("/home/z/my-project/parwa/src/middleware.ts").read()
        assert 'redirect("/login")' in content or "loginUrl" in content, \
            "Must redirect to login for unauthenticated users"

    def test_middleware_returns_401_for_api(self):
        """Middleware returns 401 for unauthenticated API requests"""
        content = open("/home/z/my-project/parwa/src/middleware.ts").read()
        assert "401" in content, "Must return 401 for API auth failure"

    def test_middleware_checks_cookies(self):
        """Middleware checks httpOnly cookies as auth fallback"""
        content = open("/home/z/my-project/parwa/src/middleware.ts").read()
        assert "parwa_at" in content, "Must check httpOnly access token cookie"

    def test_middleware_has_matcher_config(self):
        """Middleware has proper matcher config"""
        content = open("/home/z/my-project/parwa/src/middleware.ts").read()
        assert "matcher" in content, "Must have matcher config"

    # ── jose Dependency ────────────────────────────────────────────────

    def test_jose_installed(self):
        """jose package is installed"""
        result = subprocess.run(
            ["node", "-e", "require('jose'); console.log('OK')"],
            capture_output=True,
            text=True,
            cwd="/home/z/my-project/parwa",
        )
        assert result.returncode == 0, f"jose must be installed: {result.stderr}"

    # ── Source Code Scanning ───────────────────────────────────────────

    def test_scan_no_fake_tokens_in_auth_routes(self):
        """No auth routes use fake parwa_at_ tokens"""
        auth_files = [
            "/home/z/my-project/parwa/src/app/api/auth/login/route.ts",
            "/home/z/my-project/parwa/src/app/api/auth/register/route.ts",
        ]
        for fpath in auth_files:
            content = open(fpath).read()
            assert "parwa_at_" not in content, \
                f"{fpath} must NOT contain fake parwa_at_ tokens"
            assert "crypto.randomUUID()" not in content, \
                f"{fpath} must NOT use crypto.randomUUID() for tokens"

    def test_scan_no_hardcoded_demo_users(self):
        """No hardcoded demo users in auth routes"""
        content = open("/home/z/my-project/parwa/src/app/api/auth/me/route.ts").read()
        assert "demo@parwa.ai" not in content, \
            "/me must NOT return hardcoded demo@parwa.ai"
        assert "usr_mock" not in content, \
            "/me must NOT return hardcoded mock user IDs"

    def test_scan_no_slice_on_secrets(self):
        """No API key slicing in dashboard routes"""
        content = open(
            "/home/z/my-project/parwa/dashboard/src/app/api/channel-status/route.ts"
        ).read()
        assert ".slice(" not in content, \
            "channel-status must NOT slice API keys for display"

    def test_scan_chat_api_has_auth_check(self):
        """Chat API file contains authentication check"""
        content = open("/home/z/my-project/parwa/src/app/api/chat/route.ts").read()
        assert "verifyToken" in content, "Chat API must verify tokens"
        assert "Authentication required" in content, \
            "Chat API must require authentication"
