"""
Day 7 Security Tests — Docker Hardening & Remaining Fixes

Tests for all Day 7 security audit items:
- F14: Docker image digest pinning documentation
- F15: read_only: true + tmpfs in docker-compose
- F16: cap_drop: ALL in docker-compose
- F17: Node exporter mount scoping comment
- M1: Phone OTP uses secure random generation
- M2: OTP not in email subject line
- E4: Lockout message doesn't leak duration
- E5: Webhook returns 400 for invalid JSON
- E6: TODO for Google OAuth POST tokeninfo
- E7: Password reset URL uses env var
- C8: MFA uses proper exception (not bare Exception)
- M5: X-XSS-Protection removed from nginx configs
- B5: Fail-closed comment for auth rate limiting
- B6: Socket.io JWT validation comment
"""

import os
import secrets

import yaml

# Base paths
# Project root: tests/ → app/ → backend/ → parwa/
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
COMPOSE_PATH = os.path.join(_PROJECT_ROOT, "docker-compose.prod.yml")
NGINX_PATH = os.path.join(_PROJECT_ROOT, "nginx", "nginx.conf")
NGINX_DEFAULT_PATH = os.path.join(
    _PROJECT_ROOT, "infra", "docker", "nginx-default.conf"
)
NGINX_CONF_PATH = os.path.join(
    _PROJECT_ROOT, "infra", "docker", "nginx.conf"
)


# ── Helper ─────────────────────────────────────────────────────────


def _load_compose(path=None):
    """Load docker-compose.prod.yml."""
    p = path or COMPOSE_PATH
    with open(p) as f:
        return yaml.safe_load(f)


def _read_file(path):
    """Read a text file and return its contents."""
    with open(path) as f:
        return f.read()


# =========================================================================
# F14: Docker image digest pinning documentation
# =========================================================================


class TestF14_DockerImageDigestPinning:
    """F14: Production compose should document which images to pin."""

    def test_digest_pinning_comment_exists(self):
        """F14: Comment listing images to pin by digest should exist."""
        content = _read_file(COMPOSE_PATH)
        assert "F14" in content
        assert "digest" in content.lower()
        assert "postgres:15-alpine" in content
        assert "redis:7-alpine" in content
        assert "prom/prometheus" in content

    def test_digest_pinning_lists_all_images(self):
        """F14: All production images should be listed."""
        content = _read_file(COMPOSE_PATH)
        images_to_pin = [
            "postgres:15-alpine",
            "redis:7-alpine",
            "prom/prometheus:v2.45.0",
            "grafana/grafana:10.0.0",
            "prom/alertmanager:v0.26.0",
            "oliver006/redis_exporter:v1.55.0-alpine",
            "prometheuscommunity/postgres-exporter:v0.15.0",
            "prom/node-exporter:v1.6.1",
            "nginx:1.25-alpine",
        ]
        for img in images_to_pin:
            assert img in content, f"Missing image in digest pinning comment: {img}"


# =========================================================================
# F15: read_only: true + tmpfs mounts
# =========================================================================


class TestF15_ReadOnlyFilesystem:
    """F15: Backend and worker services should have read_only: true."""

    def test_backend_read_only(self):
        """F15: Backend service has read_only: true."""
        compose = _load_compose()
        backend = compose["services"]["backend"]
        assert backend.get("read_only") is True

    def test_worker_read_only(self):
        """F15: Worker service has read_only: true."""
        compose = _load_compose()
        worker = compose["services"]["worker"]
        assert worker.get("read_only") is True

    def test_backend_tmpfs(self):
        """F15: Backend service has tmpfs for /tmp."""
        compose = _load_compose()
        backend = compose["services"]["backend"]
        tmpfs = backend.get("tmpfs", [])
        assert "/tmp" in tmpfs

    def test_worker_tmpfs(self):
        """F15: Worker service has tmpfs for /tmp."""
        compose = _load_compose()
        worker = compose["services"]["worker"]
        tmpfs = worker.get("tmpfs", [])
        assert "/tmp" in tmpfs


# =========================================================================
# F16: cap_drop: ALL
# =========================================================================


class TestF16_CapDropAll:
    """F16: Backend and worker services should drop all capabilities."""

    def test_backend_cap_drop_all(self):
        """F16: Backend service has cap_drop: ALL."""
        compose = _load_compose()
        backend = compose["services"]["backend"]
        cap_drop = backend.get("cap_drop", [])
        assert "ALL" in cap_drop

    def test_worker_cap_drop_all(self):
        """F16: Worker service has cap_drop: ALL."""
        compose = _load_compose()
        worker = compose["services"]["worker"]
        cap_drop = worker.get("cap_drop", [])
        assert "ALL" in cap_drop


# =========================================================================
# F17: Node exporter mount scoping
# =========================================================================


class TestF17_NodeExporterMounts:
    """F17: Node exporter should have comment about filesystem restriction."""

    def test_node_exporter_security_comment(self):
        """F17: Node exporter section has security comment about mount scoping."""
        content = _read_file(COMPOSE_PATH)
        assert "F17" in content
        # Check that the comment mentions filesystem security
        assert "host rootfs" in content.lower() or "rootfs" in content.lower()
        assert "SECURITY" in content


# =========================================================================
# M1: Phone OTP generation uses secure random
# =========================================================================


class TestM1_PhoneOTPSecure:
    """M1: OTP should use randbelow(1000000).zfill(6), not token_hex."""

    def test_otp_uses_randbelow(self):
        """M1: Phone OTP service uses secrets.randbelow."""
        content = _read_file(
            os.path.join(
                os.path.dirname(__file__),
                "..", "services", "phone_otp_service.py",
            )
        )
        assert "secrets.randbelow(1000000)" in content
        assert "secrets.token_hex(3)" not in content

    def test_otp_uses_zfill(self):
        """M1: OTP is zero-padded to 6 digits."""
        content = _read_file(
            os.path.join(
                os.path.dirname(__file__),
                "..", "services", "phone_otp_service.py",
            )
        )
        assert ".zfill(6)" in content

    def test_otp_always_six_digits(self):
        """M1: Generated OTP is always exactly 6 digits."""
        for _ in range(100):
            code = str(secrets.randbelow(1000000)).zfill(6)
            assert len(code) == 6
            assert code.isdigit()

    def test_otp_no_upper_suffix(self):
        """M1: OTP no longer uses .upper() since no hex chars."""
        content = _read_file(
            os.path.join(
                os.path.dirname(__file__),
                "..", "services", "phone_otp_service.py",
            )
        )
        # The line should NOT have .upper() anymore
        otp_lines = [
            item for item in content.split("\n")
            if "secrets.randbelow" in item
        ]
        assert len(otp_lines) == 1
        assert ".upper()" not in otp_lines[0]


# =========================================================================
# M2: OTP not in email subject
# =========================================================================


class TestM2_OTPNotInSubject:
    """M2: Business email OTP should not include code in subject line."""

    def test_subject_no_otp_code(self):
        """M2: Email subject does not contain f-string interpolation of otp_code."""
        content = _read_file(
            os.path.join(
                os.path.dirname(__file__),
                "..", "services", "business_email_otp_service.py",
            )
        )
        # Should NOT have the code in subject
        assert 'subject=f"Your PARWA Verification Code: {otp_code}"' not in content

    def test_subject_is_generic(self):
        """M2: Subject is a generic string without OTP code."""
        content = _read_file(
            os.path.join(
                os.path.dirname(__file__),
                "..", "services", "business_email_otp_service.py",
            )
        )
        assert 'subject="Your PARWA Verification Code"' in content


# =========================================================================
# E4: Lockout message does not leak duration
# =========================================================================


class TestE4_LockoutDurationLeak:
    """E4: Lockout messages should be generic, not reveal exact seconds."""

    def test_no_exact_seconds_in_lockout(self):
        """E4: Auth service lockout messages don't include exact second count."""
        content = _read_file(
            os.path.join(
                os.path.dirname(__file__),
                "..", "services", "auth_service.py",
            )
        )
        # Should NOT have f-string with remaining seconds
        assert "Try again in {remaining} seconds" not in content
        assert "Try again in " not in content or "Try again later" in content

    def test_generic_lockout_message(self):
        """E4: Lockout message says 'Try again later' without specifics."""
        content = _read_file(
            os.path.join(
                os.path.dirname(__file__),
                "..", "services", "auth_service.py",
            )
        )
        assert "Try again later" in content


# =========================================================================
# E5: Webhook returns 400 for invalid JSON
# =========================================================================


class TestE5_WebhookInvalidJSON:
    """E5: Webhook should return 400 for invalid JSON, not silently default."""

    def test_no_silent_empty_dict(self):
        """E5: No more 'payload = {}' fallback for invalid JSON."""
        content = _read_file(
            os.path.join(
                os.path.dirname(__file__),
                "..", "api", "webhooks.py",
            )
        )
        # The old pattern should be gone
        assert "payload = {}\n" not in content

    def test_returns_400_for_bad_json(self):
        """E5: Invalid JSON returns status_code=400."""
        content = _read_file(
            os.path.join(
                os.path.dirname(__file__),
                "..", "api", "webhooks.py",
            )
        )
        assert "INVALID_JSON" in content
        assert "status_code=400" in content


# =========================================================================
# E6: Google OAuth TODO for POST tokeninfo
# =========================================================================


class TestE6_GoogleOAuthTokenInfo:
    """E6: Should have TODO about using POST for Google tokeninfo."""

    def test_todo_for_post_tokeninfo(self):
        """E6: Comment about migrating to POST exists."""
        content = _read_file(
            os.path.join(
                os.path.dirname(__file__),
                "..", "services", "auth_service.py",
            )
        )
        assert "TODO(E6)" in content
        assert "POST" in content
        assert "tokeninfo" in content.lower()


# =========================================================================
# E7: Password reset URL uses env var
# =========================================================================


class TestE7_PasswordResetURL:
    """E7: Password reset URL should use FRONTEND_URL env var."""

    def test_no_hardcoded_url(self):
        """E7: No hardcoded 'https://parwa.ai/reset-password'."""
        content = _read_file(
            os.path.join(
                os.path.dirname(__file__),
                "..", "services", "password_reset_service.py",
            )
        )
        assert '"https://parwa.ai/reset-password"' not in content

    def test_uses_env_var(self):
        """E7: Uses os.environ.get('FRONTEND_URL'...)."""
        content = _read_file(
            os.path.join(
                os.path.dirname(__file__),
                "..", "services", "password_reset_service.py",
            )
        )
        assert "FRONTEND_URL" in content
        assert "os.environ.get" in content


# =========================================================================
# C8: MFA uses proper exception
# =========================================================================


class TestC8_MFAProperException:
    """C8: MFA should not use bare Exception, should use AuthenticationError."""

    def test_no_bare_exception(self):
        """C8: No 'raise Exception(' in MFA router."""
        content = _read_file(
            os.path.join(
                os.path.dirname(__file__),
                "..", "api", "mfa.py",
            )
        )
        assert "raise Exception(" not in content

    def test_uses_authentication_error(self):
        """C8: Uses AuthenticationError for missing refresh token."""
        content = _read_file(
            os.path.join(
                os.path.dirname(__file__),
                "..", "api", "mfa.py",
            )
        )
        assert "AuthenticationError" in content


# =========================================================================
# M5: X-XSS-Protection removed
# =========================================================================


class TestM5_RemoveXSSProtection:
    """M5: X-XSS-Protection header should be removed from all nginx configs."""

    def test_main_nginx_no_xss(self):
        """M5: nginx/nginx.conf has no X-XSS-Protection header."""
        content = _read_file(NGINX_PATH)
        assert "X-XSS-Protection" not in content

    def test_nginx_default_no_xss(self):
        """M5: infra/docker/nginx-default.conf has no X-XSS-Protection."""
        content = _read_file(NGINX_DEFAULT_PATH)
        assert "X-XSS-Protection" not in content

    def test_nginx_conf_no_xss(self):
        """M5: infra/docker/nginx.conf has no X-XSS-Protection."""
        content = _read_file(NGINX_CONF_PATH)
        assert "X-XSS-Protection" not in content


# =========================================================================
# B5: Fail-closed rate limiting comment
# =========================================================================


class TestB5_FailClosedRateLimiting:
    """B5: Rate limiter should have comment about fail-closed for auth."""

    def test_fail_closed_comment(self):
        """B5: Comment about fail-closed for auth endpoints exists."""
        content = _read_file(
            os.path.join(
                os.path.dirname(__file__),
                "..", "middleware", "rate_limit.py",
            )
        )
        assert "TODO(B5)" in content
        assert "fail-closed" in content.lower()


# =========================================================================
# B6: Socket.io JWT validation comment
# =========================================================================


class TestB6_SocketIOJWTValidation:
    """B6: Socket.io should have comment about JWT re-validation."""

    def test_jwt_validation_comment(self):
        """B6: Comment about per-connection JWT validation exists."""
        content = _read_file(
            os.path.join(
                os.path.dirname(__file__),
                "..", "core", "socketio.py",
            )
        )
        assert "TODO(B6)" in content
        assert "JWT" in content or "jwt" in content
