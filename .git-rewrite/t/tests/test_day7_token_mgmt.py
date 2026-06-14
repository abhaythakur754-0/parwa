"""
PARWA Security Day 7 — Token Management & Defense in Depth
Unit Tests for 13 findings: H-06, M-02, M-03, M-06, M-07, M-09,
M-10, M-11, M-12, M-26, M-29, M-37, L-02

Run: pytest tests/test_day7_token_mgmt.py -v
"""

import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ── H-06: Standardized IP extraction ────────────────────────────────


class TestH06StandardizedIPExtraction:
    """H-06: All middleware use TRUSTED_PROXY_COUNT consistently."""

    def test_ip_allowlist_uses_trusted_proxy_count(self):
        """ip_allowlist.py uses rightmost trusted IP from X-Forwarded-For."""
        os.environ["TRUSTED_PROXY_COUNT"] = "2"
        # Force reimport to pick up new env var
        import importlib
        mod = importlib.import_module(
            "app.middleware.ip_allowlist"
        )
        importlib.reload(mod)
        middleware = mod.IPAllowlistMiddleware(app=MagicMock())
        scope = {
            "type": "http",
            "headers": [
                (b"x-forwarded-for",
                 b"spoofed1,spoofed2,10.0.0.5,192.168.1.100"),
            ],
            "client": ("127.0.0.1", 12345),
        }
        ip = middleware._get_client_ip(scope)
        # With TRUSTED_PROXY_COUNT=2, should take ips[-2] = 10.0.0.5
        assert ip == "10.0.0.5", (
            f"Expected 10.0.0.5 but got {ip}"
        )
        os.environ.pop("TRUSTED_PROXY_COUNT", None)

    def test_ip_allowlist_fallback_when_fewer_ips(self):
        """Falls back to client IP when fewer IPs than TRUSTED_PROXY_COUNT."""
        os.environ["TRUSTED_PROXY_COUNT"] = "5"
        import importlib
        mod = importlib.import_module(
            "app.middleware.ip_allowlist"
        )
        importlib.reload(mod)
        middleware = mod.IPAllowlistMiddleware(app=MagicMock())
        scope = {
            "type": "http",
            "headers": [
                (b"x-forwarded-for", b"10.0.0.1,10.0.0.2"),
            ],
            "client": ("172.16.0.1", 12345),
        }
        ip = middleware._get_client_ip(scope)
        # Only 2 IPs but need 5 → falls back to client
        assert ip == "172.16.0.1"
        os.environ.pop("TRUSTED_PROXY_COUNT", None)

    def test_request_logger_uses_trusted_proxy_count(self):
        """request_logger.py uses rightmost trusted IP consistently."""
        os.environ["TRUSTED_PROXY_COUNT"] = "1"
        import importlib
        mod = importlib.import_module(
            "app.middleware.request_logger"
        )
        importlib.reload(mod)
        request = MagicMock()
        request.headers.get.side_effect = lambda k: {
            "X-Forwarded-For": (
                "spoofed,10.0.0.5,192.168.1.1"
            ),
            "X-Real-IP": None,
        }.get(k)
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ip = mod._get_client_ip(request)
        # TRUSTED_PROXY_COUNT=1 → ips[-1] = "192.168.1.1"
        assert ip == "192.168.1.1", (
            f"Expected 192.168.1.1 but got {ip}"
        )
        os.environ.pop("TRUSTED_PROXY_COUNT", None)

    def test_rate_limit_uses_trusted_proxy_count(self):
        """rate_limit.py already uses TRUSTED_PROXY_COUNT (verify)."""
        import importlib
        mod = importlib.import_module(
            "app.middleware.rate_limit"
        )
        importlib.reload(mod)
        assert hasattr(mod, "_TRUSTED_PROXY_COUNT")
        assert mod._TRUSTED_PROXY_COUNT > 0


# ── M-02: No double body parsing in identity ────────────────────────


class TestM02NoDoubleBodyParsing:
    """M-02: Identity resolve endpoint uses only Pydantic model."""

    def test_resolve_identity_no_request_body_parsing(self):
        """The resolve_identity endpoint does not call request.json()."""
        import inspect
        import app.api.identity as identity_mod
        source = inspect.getsource(
            identity_mod.resolve_identity
        )
        assert "request.json()" not in source, (
            "resolve_identity still has raw body parsing"
        )
        assert "await request.body()" not in source, (
            "resolve_identity still reads raw body"
        )


# ── M-03: Per-user rate limit on batch identity ────────────────────


class TestM03BatchIdentityRateLimit:
    """M-03: Batch identity endpoint has per-user rate limiting."""

    def test_batch_endpoint_imports_rate_limit_service(self):
        """Batch endpoint uses rate_limit_service for per-user limits."""
        import inspect
        import app.api.identity as identity_mod
        source = inspect.getsource(
            identity_mod.batch_resolve_identities
        )
        assert "rate_limit" in source.lower(), (
            "batch_resolve_identities missing rate limit check"
        )
        assert "RATE_LIMIT_EXCEEDED" in source, (
            "batch_resolve_identities missing 429 response"
        )


# ── M-06: API key auth logging on pass-through ─────────────────────


class TestM06APIKeyAuthLogging:
    """M-06: API key auth middleware logs pass-through decisions."""

    def test_no_bearer_token_logged(self):
        """Middleware logs when no Bearer token is present."""
        import inspect
        import app.middleware.api_key_auth as auth_mod
        source = inspect.getsource(
            auth_mod.APIKeyAuthMiddleware.dispatch
        )
        assert "api_key_auth_no_bearer_token" in source, (
            "Missing debug log for no bearer token"
        )

    def test_invalid_key_logged(self):
        """Middleware logs when API key validation fails."""
        import inspect
        import app.middleware.api_key_auth as auth_mod
        source = inspect.getsource(
            auth_mod.APIKeyAuthMiddleware.dispatch
        )
        assert "api_key_auth_invalid_key" in source, (
            "Missing warning log for invalid key"
        )


# ── M-07: DB session dependency injection ───────────────────────────


class TestM07DBSessionDependencyInjection:
    """M-07: Middleware uses context manager for DB sessions."""

    def test_api_key_auth_uses_context_manager(self):
        """api_key_auth uses contextmanager for DB session."""
        import inspect
        import app.middleware.api_key_auth as auth_mod
        source = inspect.getsource(
            auth_mod.APIKeyAuthMiddleware._validate_db
        )
        assert "contextmanager" in source, (
            "_validate_db missing contextmanager pattern"
        )

    def test_ai_entitlement_uses_context_manager(self):
        """ai_entitlement uses contextmanager for DB session."""
        import inspect
        import app.middleware.ai_entitlement as entitlement_mod
        source = inspect.getsource(
            entitlement_mod.AIEntitlementMiddleware.dispatch
        )
        assert "contextmanager" in source, (
            "ai_entitlement missing contextmanager pattern"
        )


# ── M-09: MFA route uses AuthenticationError ────────────────────────


class TestM09MFAExceptionHandling:
    """M-09: MFA route catches raw exceptions properly."""

    def test_mfa_verify_wraps_exceptions(self):
        """MFA verify route wraps service call in try/except."""
        import inspect
        import app.api.mfa as mfa_mod
        source = inspect.getsource(
            mfa_mod.mfa_verify_login
        )
        assert "except AuthenticationError" in source, (
            "MFA verify missing AuthenticationError re-raise"
        )
        assert "except Exception" in source, (
            "MFA verify missing generic exception catch"
        )


# ── M-10: JWT jti claim for blacklisting ────────────────────────────


class TestM10JWTJtiClaim:
    """M-10: JWTs include jti claim for token blacklisting."""

    def test_access_token_has_jti(self):
        """create_access_token includes jti in payload."""
        import importlib
        auth_mod = importlib.import_module("app.core.auth")
        importlib.reload(auth_mod)

        with patch.object(auth_mod, "get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                JWT_SECRET_KEY="test-secret-key-for-day7",
                JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15,
            )
            token = auth_mod.create_access_token(
                user_id="user-123",
                company_id="company-456",
                email="test@parwa.ai",
                role="agent",
                plan="growth",
            )
            from jose import jwt as jose_jwt
            payload = jose_jwt.decode(
                token, "test-secret-key-for-day7",
                algorithms=["HS256"],
            )
            assert "jti" in payload, "JWT missing jti claim"
            assert len(payload["jti"]) > 16, "jti too short"

    def test_get_token_jti_extracts_jti(self):
        """get_token_jti correctly extracts jti from token."""
        import importlib
        auth_mod = importlib.import_module("app.core.auth")
        importlib.reload(auth_mod)

        with patch.object(auth_mod, "get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                JWT_SECRET_KEY="test-secret-key-for-jti",
                JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15,
            )
            token = auth_mod.create_access_token(
                user_id="user-jti-test",
                company_id="company-jti",
                email="jti@test.com",
                role="owner",
            )
            jti = auth_mod.get_token_jti(token)
            assert jti is not None, "get_token_jti returned None"
            assert len(jti) > 10

    def test_get_token_jti_returns_none_for_invalid(self):
        """get_token_jti returns None for invalid tokens."""
        import importlib
        auth_mod = importlib.import_module("app.core.auth")
        importlib.reload(auth_mod)
        assert auth_mod.get_token_jti("not.a.jwt") is None


# ── M-11: Cache-Control no-store on auth responses ──────────────────


class TestM11CacheControlNoStore:
    """M-11: Auth responses have Cache-Control: no-store."""

    def test_security_headers_auth_path_detection(self):
        """SecurityHeadersMiddleware has AUTH_PATH_PREFIXES."""
        import importlib
        mod = importlib.import_module(
            "app.middleware.security_headers"
        )
        importlib.reload(mod)
        assert hasattr(mod, "AUTH_PATH_PREFIXES")
        assert "/api/auth/" in mod.AUTH_PATH_PREFIXES

    def test_cache_control_set_for_auth_paths(self):
        """Source code contains Cache-Control: no-store for auth."""
        import inspect
        import app.middleware.security_headers as sh_mod
        source = inspect.getsource(
            sh_mod.SecurityHeadersMiddleware.dispatch
        )
        assert "no-store" in source, (
            "Missing Cache-Control: no-store"
        )
        assert "no-cache" in source, (
            "Missing Pragma: no-cache"
        )


# ── M-12: API key hashing upgraded to bcrypt ───────────────────────


class TestM12APIKeyBcryptHashing:
    """M-12: API keys are hashed with bcrypt."""

    def test_hash_api_key_uses_bcrypt(self):
        """hash_api_key produces bcrypt hash with ak$ prefix."""
        import importlib
        api_keys_mod = importlib.import_module(
            "security.api_keys"
        )
        importlib.reload(api_keys_mod)

        hashed = api_keys_mod.hash_api_key("test-api-key-123")
        assert hashed.startswith("ak$"), (
            f"Expected ak$ prefix, got {hashed[:10]}"
        )
        # bcrypt hash is typically 60 chars
        assert len(hashed) > 63, (
            f"Hash too short: {len(hashed)}"
        )

    def test_verify_api_key_bcrypt(self):
        """verify_api_key works with bcrypt hashes."""
        import importlib
        api_keys_mod = importlib.import_module(
            "security.api_keys"
        )
        importlib.reload(api_keys_mod)

        raw_key = "parwa_live_" + "a" * 32
        hashed = api_keys_mod.hash_api_key(raw_key)
        assert api_keys_mod.verify_api_key(raw_key, hashed), (
            "bcrypt key verification failed"
        )
        assert not api_keys_mod.verify_api_key(
            "wrong-key", hashed
        ), "Wrong key should not verify"

    def test_verify_api_key_legacy_sha256_fallback(self):
        """verify_api_key falls back to SHA-256 for legacy hashes."""
        import importlib
        api_keys_mod = importlib.import_module(
            "security.api_keys"
        )
        importlib.reload(api_keys_mod)

        raw_key = "legacy-key-123"
        legacy_hash = hashlib.sha256(
            raw_key.encode("utf-8")
        ).hexdigest()
        assert api_keys_mod.verify_api_key(
            raw_key, legacy_hash
        ), "Legacy SHA-256 verification failed"
        assert not api_keys_mod.verify_api_key(
            "wrong", legacy_hash
        ), "Wrong key should not verify against legacy hash"

    def test_hash_api_key_raises_on_empty(self):
        """hash_api_key raises ValueError on empty key."""
        import importlib
        api_keys_mod = importlib.import_module(
            "security.api_keys"
        )
        importlib.reload(api_keys_mod)
        with pytest.raises(ValueError):
            api_keys_mod.hash_api_key("")


# ── M-26: Next.js security headers ─────────────────────────────────


class TestM26NextJsSecurityHeaders:
    """M-26: Next.js middleware adds security headers."""

    def test_middleware_has_security_headers(self):
        """src/middleware.ts defines SECURITY_HEADERS constant."""
        middleware_path = "/home/z/my-project/parwa-day6/src/middleware.ts"
        with open(middleware_path) as f:
            source = f.read()
        assert "SECURITY_HEADERS" in source, (
            "Missing SECURITY_HEADERS constant"
        )
        assert "X-Content-Type-Options" in source
        assert "X-Frame-Options" in source
        assert "Referrer-Policy" in source
        assert "Permissions-Policy" in source

    def test_middleware_has_add_security_headers_fn(self):
        """addSecurityHeaders function is defined and used."""
        middleware_path = "/home/z/my-project/parwa-day6/src/middleware.ts"
        with open(middleware_path) as f:
            source = f.read()
        assert "addSecurityHeaders" in source, (
            "Missing addSecurityHeaders function"
        )
        # Should be called for public paths
        assert "return addSecurityHeaders" in source, (
            "addSecurityHeaders not wired to responses"
        )

    def test_auth_cache_control_in_middleware(self):
        """Next.js middleware adds Cache-Control for auth paths."""
        middleware_path = "/home/z/my-project/parwa-day6/src/middleware.ts"
        with open(middleware_path) as f:
            source = f.read()
        assert "AUTH_PATH_PREFIXES" in source, (
            "Missing AUTH_PATH_PREFIXES"
        )
        assert "no-store" in source, (
            "Missing no-store for auth paths"
        )


# ── M-29: Mock data banner ─────────────────────────────────────────


class TestM29MockDataBanner:
    """M-29: Mock analytics data is flagged with _mock."""

    def test_apiFetch_marks_mock_data(self):
        """apiFetch adds _mock: true when returning fallback data."""
        analytics_path = (
            "/home/z/my-project/parwa-day6/src/lib/analytics-api.ts"
        )
        with open(analytics_path) as f:
            source = f.read()
        assert "_mock" in source, (
            "Missing _mock flag in analytics API"
        )
        assert "_mock: true" in source, (
            "Missing _mock: true assignment"
        )
        assert "MOCK DATA" in source, (
            "Missing console warning about mock data"
        )


# ── M-37: Hardcoded phone number fixed ─────────────────────────────


class TestM37HardcodedPhoneFix:
    """M-37: SMS uses customer phone, not hardcoded number."""

    def test_no_hardcoded_phone_in_notifications(self):
        """notifications.ts does not have hardcoded +1234567890."""
        notif_path = (
            "/home/z/my-project/parwa-day6/"
            "dashboard/src/lib/notifications.ts"
        )
        with open(notif_path) as f:
            source = f.read()
        assert "+1234567890" not in source, (
            "Hardcoded phone number still present"
        )

    def test_uses_customer_phone(self):
        """notifications.ts uses customerPhone from payload."""
        notif_path = (
            "/home/z/my-project/parwa-day6/"
            "dashboard/src/lib/notifications.ts"
        )
        with open(notif_path) as f:
            source = f.read()
        assert "customerPhone" in source, (
            "Missing customerPhone usage"
        )
        assert "recipientPhone" in source, (
            "Missing recipientPhone variable"
        )


# ── L-02: JWT key rotation mechanism ───────────────────────────────


class TestL02JWTKeyRotation:
    """L-02: JWT key rotation via JWT_PREVIOUS_KEYS."""

    def test_verify_with_previous_key(self):
        """Token signed with old key is still valid after rotation."""
        import importlib
        auth_mod = importlib.import_module("app.core.auth")
        importlib.reload(auth_mod)

        old_key = "old-secret-key-v1"
        new_key = "new-secret-key-v2"

        # Create token with old key
        payload = {
            "sub": "user-rotation",
            "company_id": "company-r",
            "email": "rotate@test.com",
            "role": "agent",
            "plan": "growth",
            "type": "access",
            "exp": (
                datetime.now(timezone.utc) + timedelta(hours=1)
            ),
            "iat": datetime.now(timezone.utc),
            "nbf": datetime.now(timezone.utc),
            "jti": "test-jti-rotation",
        }
        from jose import jwt as jose_jwt
        token = jose_jwt.encode(
            payload, old_key, algorithm="HS256"
        )

        # Set up env vars to simulate rotation
        os.environ["JWT_SECRET_KEY"] = new_key
        os.environ["JWT_PREVIOUS_KEYS"] = json.dumps([old_key])
        os.environ["ENVIRONMENT"] = "development"
        os.environ["REFRESH_TOKEN_PEPPER"] = "test-pepper"

        importlib.reload(auth_mod)

        with patch.object(auth_mod, "get_settings") as mock_s:
            mock_s.return_value = MagicMock(
                JWT_SECRET_KEY=new_key,
                JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15,
            )
            # Token signed with old key should still verify
            result = auth_mod.verify_access_token(token)
            assert result["sub"] == "user-rotation"
            assert result["email"] == "rotate@test.com"

        # Clean up
        os.environ.pop("JWT_PREVIOUS_KEYS", None)
        os.environ.pop("JWT_SECRET_KEY", None)
        os.environ.pop("ENVIRONMENT", None)
        os.environ.pop("REFRESH_TOKEN_PEPPER", None)

    def test_get_jwt_previous_keys(self):
        """get_jwt_previous_keys returns the list of previous keys."""
        import importlib
        auth_mod = importlib.import_module("app.core.auth")
        importlib.reload(auth_mod)

        os.environ["JWT_PREVIOUS_KEYS"] = json.dumps(
            ["key1", "key2"]
        )
        importlib.reload(auth_mod)
        keys = auth_mod.get_jwt_previous_keys()
        assert "key1" in keys
        assert "key2" in keys
        os.environ.pop("JWT_PREVIOUS_KEYS", None)

    def test_token_signed_with_new_key_only(self):
        """Token signed with new key works after rotation."""
        import importlib
        auth_mod = importlib.import_module("app.core.auth")
        importlib.reload(auth_mod)

        new_key = "brand-new-key-v3"
        os.environ["JWT_PREVIOUS_KEYS"] = json.dumps(
            ["old-key-1"]
        )
        os.environ["REFRESH_TOKEN_PEPPER"] = "test-pepper"

        with patch.object(auth_mod, "get_settings") as mock_s:
            mock_s.return_value = MagicMock(
                JWT_SECRET_KEY=new_key,
                JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15,
            )
            token = auth_mod.create_access_token(
                user_id="user-new",
                company_id="company-n",
                email="new@test.com",
                role="admin",
            )
            result = auth_mod.verify_access_token(token)
            assert result["sub"] == "user-new"

        os.environ.pop("JWT_PREVIOUS_KEYS", None)
        os.environ.pop("REFRESH_TOKEN_PEPPER", None)


# ── Integration-style tests ────────────────────────────────────────


class TestDay7Integration:
    """Cross-cutting tests verifying multiple Day 7 fixes interact."""

    def test_jti_present_in_all_new_tokens(self):
        """Every new JWT has a unique jti claim."""
        import importlib
        auth_mod = importlib.import_module("app.core.auth")
        importlib.reload(auth_mod)

        with patch.object(auth_mod, "get_settings") as mock_s:
            mock_s.return_value = MagicMock(
                JWT_SECRET_KEY="integration-test-key",
                JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15,
            )
            jtis = set()
            for _ in range(100):
                token = auth_mod.create_access_token(
                    user_id="u", company_id="c",
                    email="e@t.com", role="agent",
                )
                jti = auth_mod.get_token_jti(token)
                assert jti not in jtis, "Duplicate jti detected"
                jtis.add(jti)
            assert len(jtis) == 100

    def test_bcrypt_hash_different_each_time(self):
        """bcrypt produces different hashes for same key (salt)."""
        import importlib
        api_keys_mod = importlib.import_module(
            "security.api_keys"
        )
        importlib.reload(api_keys_mod)

        raw = "same-key-value"
        h1 = api_keys_mod.hash_api_key(raw)
        h2 = api_keys_mod.hash_api_key(raw)
        assert h1 != h2, "bcrypt hashes should differ (salt)"
        assert api_keys_mod.verify_api_key(raw, h1)
        assert api_keys_mod.verify_api_key(raw, h2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
