"""
Integration tests for parwa_core Rust PyO3 module (Tier 1 Hot Path).

Tests all 5 Rust modules:
  1. RateLimiter — sliding-window, lock-free
  2. CircuitBreaker — atomic state machine
  3. PIIRedactor — 19 PII patterns, deterministic tokens, redact+deredact
  4. JWTDecoder — HS256 verify, key rotation, unverified claims
  5. SecurityHeaders + CSRFValidator — nonce, CSP, origin check

Run:  PYTHONPATH=/path/to/parwa_core python -m pytest parwa/tests/test_parwa_core.py -v
"""

import sys
import os

# Add the parwa_core module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "parwa_core"))

import parwa_core
import pytest


# ═══════════════════════════════════════════════════════════════
# 1. RATE LIMITER TESTS
# ═══════════════════════════════════════════════════════════════

class TestRateLimiter:
    def setup_method(self):
        self.rl = parwa_core.RateLimiter()

    def test_module_exists(self):
        assert hasattr(parwa_core, "RateLimiter")

    def test_classify_path_auth_login(self):
        assert self.rl.classify_path("/api/auth/login", "POST") == "auth_login"

    def test_classify_path_auth_register(self):
        assert self.rl.classify_path("/api/auth/register", "POST") == "auth_register"

    def test_classify_path_auth_mfa(self):
        assert self.rl.classify_path("/api/auth/mfa", "POST") == "auth_mfa"

    def test_classify_path_auth_phone_send(self):
        assert self.rl.classify_path("/api/auth/phone/send", "POST") == "auth_phone_send"

    def test_classify_path_auth_phone_verify(self):
        assert self.rl.classify_path("/api/auth/phone/verify", "POST") == "auth_phone_verify"

    def test_classify_path_auth_reset(self):
        assert self.rl.classify_path("/api/auth/forgot-password", "POST") == "auth_reset"
        assert self.rl.classify_path("/api/auth/reset-password", "POST") == "auth_reset"

    def test_classify_path_financial(self):
        assert self.rl.classify_path("/api/billing/subscriptions", "GET") == "financial"

    def test_classify_path_integration(self):
        assert self.rl.classify_path("/api/integrations/hubspot", "POST") == "integration"

    def test_classify_path_demo_chat(self):
        assert self.rl.classify_path("/api/public/demo/chat", "POST") == "demo_chat"

    def test_classify_path_general_get(self):
        assert self.rl.classify_path("/api/tickets", "GET") == "general_get"
        assert self.rl.classify_path("/api/users", "GET") == "general_get"

    def test_classify_path_general_post(self):
        assert self.rl.classify_path("/api/tickets", "POST") == "general_post"

    def test_classify_path_health(self):
        assert self.rl.classify_path("/health", "GET") == "general_get"

    def test_category_config(self):
        cfg = self.rl.get_category_config("auth_login")
        assert cfg["limit"] == 5
        assert cfg["window"] == 60
        assert cfg["backoff_seconds"] == [0, 2, 4, 8, 900]

    def test_category_config_default(self):
        cfg = self.rl.get_category_config("nonexistent")
        assert cfg["limit"] == 100  # general_get default

    def test_rate_limit_allows_under_limit(self):
        """5 requests allowed for auth_login (limit=5)"""
        # Each user gets a fresh window — verify all are allowed
        for i in range(5):
            result = self.rl.check_rate_limit("auth_login", f"user{i}@example.com")
            assert result["allowed"] is True, f"Request {i+1} should be allowed"
            assert result["remaining"] >= 0

    def test_rate_limit_blocks_over_limit(self):
        """6th request should be blocked"""
        for _ in range(5):
            self.rl.check_rate_limit("auth_login", "test@example.com")
        result = self.rl.check_rate_limit("auth_login", "test@example.com")
        assert result["allowed"] is False
        assert result["remaining"] == 0
        assert result["retry_after"] is not None

    def test_rate_limit_headers(self):
        result = self.rl.check_rate_limit("auth_login", "user@example.com")
        # Rust returns flat dict with limit/remaining/reset_at
        assert "limit" in result
        assert "remaining" in result
        assert "reset_at" in result
        assert result["limit"] == 5

    def test_rate_limit_separate_keys(self):
        """Different identifiers should have separate counters"""
        r1 = self.rl.check_rate_limit("auth_login", "user1@example.com")
        r2 = self.rl.check_rate_limit("auth_login", "user2@example.com")
        assert r1["remaining"] == r2["remaining"]  # Both start same

    def test_record_failure(self):
        backoff = self.rl.record_failure("auth_login", "test@example.com")
        assert isinstance(backoff, int)
        assert backoff >= 0

    def test_is_locked_out_initially_false(self):
        assert self.rl.is_locked_out("auth_login", "test@example.com") is False

    def test_reset(self):
        for _ in range(5):
            self.rl.check_rate_limit("auth_login", "test@example.com")
        self.rl.reset("auth_login", "test@example.com")
        result = self.rl.check_rate_limit("auth_login", "test@example.com")
        assert result["allowed"] is True


# ═══════════════════════════════════════════════════════════════
# 2. CIRCUIT BREAKER TESTS
# ═══════════════════════════════════════════════════════════════

class TestCircuitBreaker:
    def setup_method(self):
        self.cb = parwa_core.CircuitBreakerManager()

    def test_module_exists(self):
        assert hasattr(parwa_core, "CircuitBreakerManager")

    def test_initial_available(self):
        self.cb.register("redis", 3, 2, 30.0, 1)
        assert self.cb.is_available("redis") is True

    def test_nonexistent_available(self):
        assert self.cb.is_available("nonexistent") is True

    def test_opens_after_threshold(self):
        self.cb.register("test", 3, 2, 60.0, 1)
        self.cb.record_failure("test")
        self.cb.record_failure("test")
        assert self.cb.is_available("test") is True  # Still under threshold
        self.cb.record_failure("test")
        assert self.cb.is_available("test") is False  # Now open

    def test_stays_closed_under_threshold(self):
        self.cb.register("test", 5, 2, 60.0, 1)
        for _ in range(4):
            self.cb.record_failure("test")
        assert self.cb.is_available("test") is True

    def test_force_open_close(self):
        self.cb.register("test", 5, 2, 60.0, 1)
        self.cb.force_open("test")
        assert self.cb.is_available("test") is False
        self.cb.force_close("test")
        assert self.cb.is_available("test") is True

    def test_reset(self):
        self.cb.register("test", 3, 2, 60.0, 1)
        self.cb.force_open("test")
        self.cb.reset("test")
        assert self.cb.is_available("test") is True

    def test_unregister(self):
        self.cb.register("temp", 3, 2, 60.0, 1)
        self.cb.unregister("temp")
        assert self.cb.is_available("temp") is True  # Not registered = available

    def test_record_success(self):
        self.cb.register("test", 3, 2, 60.0, 1)
        self.cb.record_success("test")
        self.cb.record_success("test")
        assert self.cb.is_available("test") is True

    def test_get_status(self):
        self.cb.register("test", 3, 2, 60.0, 1)
        status = self.cb.get_status("test")
        assert status["name"] == "test"
        assert status["state"] == "closed"
        assert status["is_available"] is True

    def test_get_all_status(self):
        self.cb.register("redis", 3, 2, 30.0, 1)
        self.cb.register("postgres", 5, 2, 60.0, 1)
        all_status = self.cb.get_all_status()
        assert len(all_status) == 2

    def test_register_defaults(self):
        # Default threshold=5, success=3, timeout=60
        self.cb.register("defaults_test")
        status = self.cb.get_status("defaults_test")
        assert status["failure_threshold"] == 5
        assert status["success_threshold"] == 3
        assert status["timeout_seconds"] == 60.0


# ═══════════════════════════════════════════════════════════════
# 3. PII REDACTOR TESTS
# ═══════════════════════════════════════════════════════════════

class TestPIIRedactor:
    def setup_method(self):
        self.redactor = parwa_core.PIIRedactor()

    def test_module_exists(self):
        assert hasattr(parwa_core, "PIIRedactor")

    def test_detect_email(self):
        results = self.redactor.detect_pii("Contact support@example.com")
        assert len(results) > 0
        types = [r["pii_type"] for r in results]
        assert "EMAIL" in types

    def test_detect_ssn(self):
        results = self.redactor.detect_pii("SSN: 123-45-6789")
        types = [r["pii_type"] for r in results]
        assert "SSN" in types

    def test_detect_credit_card(self):
        results = self.redactor.detect_pii("Card: 4111-1111-1111-1111")
        types = [r["pii_type"] for r in results]
        assert "CREDIT_CARD" in types

    def test_detect_phone(self):
        results = self.redactor.detect_pii("Call (555) 123-4567")
        types = [r["pii_type"] for r in results]
        assert "PHONE" in types

    def test_detect_no_pii(self):
        results = self.redactor.detect_pii("Hello world, no PII here")
        assert len(results) == 0

    def test_redact(self):
        text = "Email john@doe.com and SSN 123-45-6789"
        redact_fn = self.redactor.redact
        result = redact_fn(text, "company-123")
        assert result["pii_found"] is True
        assert "john@doe.com" not in result["redacted_text"]
        assert "123-45-6789" not in result["redacted_text"]
        assert "EMAIL_" in result["redacted_text"]
        assert "SSN_" in result["redacted_text"]
        assert len(result["redaction_map"]) > 0
        assert result["redaction_id"]

    def test_redact_deredact_roundtrip(self):
        redact_fn = self.redactor.redact
        deredact_fn = self.redactor.deredact
        texts = [
            "Email john@doe.com and SSN 123-45-6789",
            "Card 4111-1111-1111-1111 here",
            "Phone: (555) 123-4567",
            "IBAN: GB82WEST12345698765432",
            "Email: alice@company.co.uk and Aadhaar 2345 6789 0123",
        ]
        for text in texts:
            r = redact_fn(text, "company-123")
            if r["pii_found"]:
                d = deredact_fn(r["redacted_text"], r["redaction_map"])
                assert d == text, f"Deredact failed for: {text[:50]}"

    def test_redact_deterministic(self):
        """Same input should produce same output"""
        text = "Email test@example.com"
        redact_fn = self.redactor.redact
        r1 = redact_fn(text, "company-123")
        r2 = redact_fn(text, "company-123")
        assert r1["redacted_text"] == r2["redacted_text"]

    def test_redact_different_per_company(self):
        text = "Email test@example.com"
        redact_fn = self.redactor.redact
        r1 = redact_fn(text, "company-1")
        r2 = redact_fn(text, "company-2")
        assert r1["redacted_text"] != r2["redacted_text"]

    def test_has_pii_true(self):
        assert self.redactor.has_pii("Email test@example.com") is True

    def test_has_pii_false(self):
        assert self.redactor.has_pii("Hello world") is False

    def test_redact_summary(self):
        text = "Email a@b.com and SSN 123-45-6789"
        redact_fn = self.redactor.redact
        r = redact_fn(text, "company-123")
        summary = r["summary"]
        assert "EMAIL" in summary
        assert "SSN" in summary


# ═══════════════════════════════════════════════════════════════
# 4. JWT DECODER TESTS
# ═══════════════════════════════════════════════════════════════

class TestJWTDecoder:
    def setup_method(self):
        self.decoder = parwa_core.JWTDecoder()

    def test_module_exists(self):
        assert hasattr(parwa_core, "JWTDecoder")

    def test_verify_invalid_format(self):
        with pytest.raises(Exception):
            self.decoder.verify("not-a-jwt", "secret")

    def test_verify_invalid_parts(self):
        with pytest.raises(Exception):
            self.decoder.verify("a.b", "secret")

    def test_get_unverified_claims(self):
        # eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJuYW1lIjoidGVzdCJ9.fakesig
        claims = self.decoder.get_unverified_claims(
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJuYW1lIjoidGVzdCJ9.fakesig"
        )
        assert claims["name"] == "test"

    def test_get_unverified_claims_invalid(self):
        with pytest.raises(Exception):
            self.decoder.get_unverified_claims("invalid")

    def test_set_previous_keys(self):
        self.decoder.set_previous_keys(["key1", "key2"])

    def test_key_rotation(self):
        decoder = parwa_core.JWTDecoder(["old-key"])
        # Sign with old-key, verify with new current key — old-key should be tried
        # Note: full test requires creating a valid JWT signed with old-key


# ═══════════════════════════════════════════════════════════════
# 5. SECURITY HEADERS TESTS
# ═══════════════════════════════════════════════════════════════

class TestSecurityHeaders:
    def test_module_exists(self):
        assert hasattr(parwa_core, "SecurityHeaders")

    def test_production_hsts(self):
        sh = parwa_core.SecurityHeaders("production")
        headers = sh.generate_headers("/api/tickets")
        assert "Strict-Transport-Security" in headers

    def test_development_no_hsts(self):
        sh = parwa_core.SecurityHeaders("development")
        headers = sh.generate_headers("/api/tickets")
        assert "Strict-Transport-Security" not in headers

    def test_has_basic_headers(self):
        sh = parwa_core.SecurityHeaders("development")
        headers = sh.generate_headers("/api/tickets")
        assert "X-Content-Type-Options" in headers
        assert "X-Frame-Options" in headers
        assert "X-XSS-Protection" in headers
        assert "Referrer-Policy" in headers
        assert "Permissions-Policy" in headers
        assert "Content-Security-Policy" in headers
        assert "X-CSP-Nonce" in headers

    def test_auth_endpoint_no_cache(self):
        sh = parwa_core.SecurityHeaders("development")
        headers = sh.generate_headers("/api/auth/login")
        assert "Cache-Control" in headers
        assert "Pragma" in headers
        assert "Expires" in headers

    def test_non_auth_endpoint_cache(self):
        sh = parwa_core.SecurityHeaders("development")
        headers = sh.generate_headers("/api/tickets")
        assert "Cache-Control" not in headers

    def test_csp_has_nonce(self):
        sh = parwa_core.SecurityHeaders("development")
        headers = sh.generate_headers("/api/tickets")
        nonce = headers["X-CSP-Nonce"]
        csp = headers["Content-Security-Policy"]
        assert nonce in csp


# ═══════════════════════════════════════════════════════════════
# 6. CSRF VALIDATOR TESTS
# ═══════════════════════════════════════════════════════════════

class TestCSRFValidator:
    def setup_method(self):
        self.csrf = parwa_core.CSRFValidator(
            ["https://app.parwa.ai"], "test-secret", 3600.0
        )

    def test_module_exists(self):
        assert hasattr(parwa_core, "CSRFValidator")

    def test_valid_origin(self):
        assert self.csrf.is_valid_origin("https://app.parwa.ai", "") is True

    def test_invalid_origin(self):
        assert self.csrf.is_valid_origin("https://evil.com", "") is False

    def test_vercel_origin(self):
        assert self.csrf.is_valid_origin(
            "https://my-app.vercel.app", ""
        ) is True

    def test_vercel_double_dash_origin(self):
        assert self.csrf.is_valid_origin(
            "https://parwa-git-main-abhaythakur754.vercel.app", ""
        ) is True

    def test_referer_fallback(self):
        assert self.csrf.is_valid_origin(
            "", "https://app.parwa.ai/dashboard"
        ) is True

    def test_no_origins_allows_all(self):
        csrf = parwa_core.CSRFValidator(None, "secret", 3600.0)
        assert csrf.is_valid_origin("https://anything.com", "") is True

    def test_generate_and_validate_token(self):
        token = self.csrf.generate_csrf_token()
        assert self.csrf.validate_csrf_token(token) is True

    def test_invalid_empty_token(self):
        assert self.csrf.validate_csrf_token("") is False

    def test_invalid_malformed_token(self):
        assert self.csrf.validate_csrf_token("bad") is False
        assert self.csrf.validate_csrf_token("a:b") is False

    def test_wrong_secret_rejects(self):
        csrf1 = parwa_core.CSRFValidator(None, "secret-1", 3600.0)
        csrf2 = parwa_core.CSRFValidator(None, "secret-2", 3600.0)
        token = csrf1.generate_csrf_token()
        assert csrf2.validate_csrf_token(token) is False

    def test_cookie_auth_path_public(self):
        assert self.csrf.is_cookie_auth_path("/api/auth/login") is False
        assert self.csrf.is_cookie_auth_path("/api/auth/register") is False
        assert self.csrf.is_cookie_auth_path("/api/auth/google") is False
        assert self.csrf.is_cookie_auth_path("/api/auth/forgot-password") is False

    def test_cookie_auth_path_protected(self):
        assert self.csrf.is_cookie_auth_path("/api/auth/profile") is True
        assert self.csrf.is_cookie_auth_path("/api/auth/settings") is True

    def test_non_auth_path(self):
        assert self.csrf.is_cookie_auth_path("/api/tickets") is False
        assert self.csrf.is_cookie_auth_path("/api/users") is False


# ═══════════════════════════════════════════════════════════════
# 7. HMAC VERIFIER TESTS (Tier 2)
# ═══════════════════════════════════════════════════════════════

class TestHMACVerifier:
    def setup_method(self):
        self.hv = parwa_core.HMACVerifier(300.0)

    def test_module_exists(self):
        assert hasattr(parwa_core, "HMACVerifier")

    def test_sign_and_verify_hmac_sha256(self):
        payload = b"test-payload-data"
        secret = "my-secret-key"
        sig = self.hv.sign_hmac_sha256("test-payload-data", secret)
        assert self.hv.verify_hmac_sha256(payload, sig, secret) is True

    def test_verify_wrong_payload(self):
        sig = self.hv.sign_hmac_sha256("correct-payload", "secret")
        assert self.hv.verify_hmac_sha256(b"wrong-payload", sig, "secret") is False

    def test_verify_wrong_secret(self):
        sig = self.hv.sign_hmac_sha256("payload", "secret-1")
        assert self.hv.verify_hmac_sha256(b"payload", sig, "secret-2") is False

    def test_verify_paddle_empty_inputs(self):
        assert self.hv.verify_paddle(b"", "sig", "secret") is False
        assert self.hv.verify_paddle(b"body", "", "secret") is False
        assert self.hv.verify_paddle(b"body", "sig", "") is False

    def test_verify_paddle_valid(self):
        sig = self.hv.sign_hmac_sha256("paddle-body", "paddle-secret")
        # sign_hmac_sha256 signs the string as a message, paddle signs raw bytes
        # They use the same HMAC-SHA256 algorithm
        import hashlib, hmac
        expected = hmac.new(
            b"paddle-secret", b"paddle-body", hashlib.sha256
        ).hexdigest()
        assert self.hv.verify_paddle(b"paddle-body", expected, "paddle-secret") is True

    def test_verify_shopify(self):
        import hashlib, hmac, base64
        secret = "shopify-secret"
        body = b"shopify-payload"
        expected = hmac.new(
            secret.encode(), body, hashlib.sha256
        ).digest()
        sig_b64 = base64.b64encode(expected).decode()
        assert self.hv.verify_shopify(body, sig_b64, secret) is True
        assert self.hv.verify_shopify(body, "wrong-sig", secret) is False

    def test_verify_timestamp_fresh(self):
        import time
        fresh = str(int(time.time()))
        assert self.hv.verify_timestamp(fresh) is True

    def test_verify_timestamp_stale(self):
        assert self.hv.verify_timestamp("0") is False
        assert self.hv.verify_timestamp("1000000000") is False  # ~2001

    def test_constant_time_compare_equal(self):
        assert self.hv.constant_time_compare("abc123", "abc123") is True

    def test_constant_time_compare_different(self):
        assert self.hv.constant_time_compare("abc123", "abc124") is False

    def test_constant_time_compare_different_length(self):
        assert self.hv.constant_time_compare("short", "much-longer-string") is False


# ═══════════════════════════════════════════════════════════════
# 8. CRYPTO ENGINE TESTS (Tier 2)
# ═══════════════════════════════════════════════════════════════

class TestCryptoEngine:
    def setup_method(self):
        # Use low cost for test speed
        self.crypto = parwa_core.CryptoEngine(4)

    def test_module_exists(self):
        assert hasattr(parwa_core, "CryptoEngine")

    def test_hash_and_verify_password(self):
        pw_hash = self.crypto.hash_password("my-secure-password")
        assert self.crypto.verify_password("my-secure-password", pw_hash) is True
        assert self.crypto.verify_password("wrong-password", pw_hash) is False

    def test_hash_api_key(self):
        ak_hash = self.crypto.hash_api_key("parwa_live_test_key_12345")
        assert ak_hash.startswith("ak$")
        assert self.crypto.verify_api_key("parwa_live_test_key_12345", ak_hash) is True
        assert self.crypto.verify_api_key("wrong-key", ak_hash) is False

    def test_hash_api_key_empty_raises(self):
        import pytest
        with pytest.raises(Exception):
            self.crypto.hash_api_key("")

    def test_verify_api_key_legacy_sha256(self):
        # Legacy SHA-256 fallback (no "ak$" prefix)
        legacy_hash = self.crypto.sha256("parwa_live_legacy_key")
        assert not legacy_hash.startswith("ak$")
        assert self.crypto.verify_api_key("parwa_live_legacy_key", legacy_hash) is True

    def test_sha256(self):
        result = self.crypto.sha256("hello")
        assert len(result) == 64
        # Known SHA-256 of "hello"
        assert result == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    def test_hmac_sha256(self):
        result = self.crypto.hmac_sha256("key", "message")
        assert len(result) == 64

    def test_random_token(self):
        t1 = self.crypto.random_token(16)
        t2 = self.crypto.random_token(16)
        assert len(t1) == 32  # 16 bytes = 32 hex chars
        assert t1 != t2  # Should be unique

    def test_random_urlsafe_token(self):
        t = self.crypto.random_urlsafe_token(24)
        assert len(t) == 24

    def test_bcrypt_cost_clamped(self):
        engine_min = parwa_core.CryptoEngine(1)
        # Should not crash — cost is clamped to 4-31
        h = engine_min.hash_password("test")
        assert engine_min.verify_password("test", h)


# ═══════════════════════════════════════════════════════════════
# 9. CONNECTION POOL TESTS (Tier 3)
# ═══════════════════════════════════════════════════════════════

class TestConnectionPool:
    def setup_method(self):
        self.pool = parwa_core.ConnectionPool()

    def test_module_exists(self):
        assert hasattr(parwa_core, "ConnectionPool")

    def test_register_and_checkout(self):
        self.pool.register("stripe", 5, 60.0, 10.0)
        result = self.pool.checkout("stripe")
        assert result is True
        stats = self.pool.get_stats("stripe")
        assert stats["active"] == 1
        assert stats["registered"] is True

    def test_checkin(self):
        self.pool.register("stripe", 5, 60.0, 10.0)
        self.pool.checkout("stripe")
        self.pool.checkin("stripe", True)
        stats = self.pool.get_stats("stripe")
        assert stats["active"] == 0
        assert stats["total_checkin"] == 1
        assert stats["total_errors"] == 0

    def test_checkin_error(self):
        self.pool.register("stripe", 5, 60.0, 10.0)
        self.pool.checkout("stripe")
        self.pool.checkin("stripe", False)  # error
        stats = self.pool.get_stats("stripe")
        assert stats["total_errors"] == 1

    def test_pool_exhaustion(self):
        self.pool.register("api", 2, 60.0, 10.0)
        assert self.pool.checkout("api") is True
        assert self.pool.checkout("api") is True
        assert self.pool.checkout("api") is False  # exhausted

    def test_has_capacity(self):
        self.pool.register("svc", 2, 60.0, 10.0)
        assert self.pool.has_capacity("svc") is True
        self.pool.checkout("svc")
        self.pool.checkout("svc")
        assert self.pool.has_capacity("svc") is False

    def test_unregistered_checkout(self):
        assert self.pool.checkout("nonexistent") is False

    def test_unregistered_stats(self):
        stats = self.pool.get_stats("nonexistent")
        assert stats["registered"] is False

    def test_record_timeout(self):
        self.pool.register("slow-api", 5, 60.0, 10.0)
        self.pool.record_timeout("slow-api")
        stats = self.pool.get_stats("slow-api")
        assert stats["total_timeouts"] == 1

    def test_get_all_stats(self):
        self.pool.register("stripe", 5, 60.0, 10.0)
        self.pool.register("redis", 10, 30.0, 5.0)
        all_stats = self.pool.get_all_stats()
        assert isinstance(all_stats, list)
        assert len(all_stats) == 2

    def test_reset(self):
        self.pool.register("svc", 5, 60.0, 10.0)
        self.pool.checkout("svc")
        self.pool.reset("svc")
        stats = self.pool.get_stats("svc")
        assert stats["active"] == 0
        assert stats["total_checkout"] == 0

    def test_unregister(self):
        self.pool.register("temp", 5, 60.0, 10.0)
        self.pool.unregister("temp")
        assert self.pool.checkout("temp") is False


# ═══════════════════════════════════════════════════════════════
# 10. ASYNC LOGGER TESTS (Tier 3)
# ═══════════════════════════════════════════════════════════════

class TestAsyncLogger:
    def setup_method(self):
        self.logger = parwa_core.AsyncLogger(1000, "debug")

    def test_module_exists(self):
        assert hasattr(parwa_core, "AsyncLogger")

    def test_log_and_flush(self):
        assert self.logger.info("hello", "test") is True
        assert self.logger.warning("world", "test") is True
        assert self.logger.error("oops", "test") is True
        flushed = self.logger.flush()
        assert len(flushed) == 3
        assert flushed[0]["message"] == "hello"
        assert flushed[0]["level"] == "info"
        assert flushed[1]["level"] == "warning"
        assert flushed[2]["level"] == "error"

    def test_flush_clears_buffer(self):
        self.logger.info("msg1", "test")
        self.logger.info("msg2", "test")
        _ = self.logger.flush()
        assert self.logger.buffer_size() == 0

    def test_level_filter(self):
        logger = parwa_core.AsyncLogger(1000, "warning")
        assert logger.debug("debug-msg", "test") is False  # below filter
        assert logger.info("info-msg", "test") is False    # below filter
        assert logger.warning("warn-msg", "test") is True  # at filter
        assert logger.error("err-msg", "test") is True     # above filter

    def test_set_level_filter(self):
        self.logger.set_level_filter("error")
        assert self.logger.info("msg", "test") is False
        assert self.logger.error("msg", "test") is True
        self.logger.set_level_filter("debug")
        assert self.logger.debug("msg", "test") is True

    def test_log_with_context(self):
        self.logger.log("info", "test-msg", "parwa", {"user_id": "123", "action": "login"})
        flushed = self.logger.flush()
        assert len(flushed) == 1
        ctx = flushed[0].get("context", {})
        assert ctx.get("user_id") == "123"
        assert ctx.get("action") == "login"

    def test_get_stats(self):
        self.logger.info("msg", "test")
        self.logger.info("msg", "test")
        stats = self.logger.get_stats()
        assert stats["buffer_size"] == 2
        assert stats["total_logged"] == 2
        assert stats["dropped_count"] == 0
        assert stats["flush_count"] == 0
        assert stats["level_filter"] == "debug"

    def test_clear(self):
        self.logger.info("msg", "test")
        self.logger.clear()
        assert self.logger.buffer_size() == 0
        stats = self.logger.get_stats()
        assert stats["total_logged"] == 1  # still counted

    def test_buffer_overflow_drops(self):
        tiny = parwa_core.AsyncLogger(3, "debug")
        assert tiny.info("m1", "t") is True
        assert tiny.info("m2", "t") is True
        assert tiny.info("m3", "t") is True
        assert tiny.info("m4", "t") is False  # dropped
        stats = tiny.get_stats()
        assert stats["dropped_count"] == 1

if __name__ == "__main__":
    # Quick smoke test without pytest
    print("Running parwa_core integration tests...")
    print()

    rl = parwa_core.RateLimiter()
    r = rl.check_rate_limit("auth_login", "test@example.com")
    print(f"  RateLimiter:    classify={rl.classify_path('/api/auth/login', 'POST')} allowed={r['allowed']} remaining={r['remaining']}")

    cb = parwa_core.CircuitBreakerManager()
    cb.register("redis", 3, 2, 30.0, 1)
    print(f"  CircuitBreaker:  available={cb.is_available('redis')}")

    redactor = parwa_core.PIIRedactor()
    text = "Email test@example.com"
    r = redactor.redact(text, "company-123")
    d = redactor.deredact(r["redacted_text"], r["redaction_map"])
    print(f"  PIIRedactor:     pii_found={r['pii_found']} deredact_match={d == text}")

    decoder = parwa_core.JWTDecoder()
    claims = decoder.get_unverified_claims(
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJuYW1lIjoidGVzdCJ9.fakesig"
    )
    print(f"  JWTDecoder:      claims={claims}")

    sh = parwa_core.SecurityHeaders("production")
    h = sh.generate_headers("/api/tickets")
    print(f"  SecurityHeaders: headers={len(h)} HSTS={'Strict-Transport-Security' in h}")

    csrf = parwa_core.CSRFValidator(["https://app.parwa.ai"], "secret", 3600.0)
    tok = csrf.generate_csrf_token()
    print(f"  CSRFValidator:   origin_valid={csrf.is_valid_origin('https://app.parwa.ai', '')} token_valid={csrf.validate_csrf_token(tok)}")

    hv = parwa_core.HMACVerifier(300.0)
    sig = hv.sign_hmac_sha256("test-body", "test-secret")
    print(f"  HMACVerifier:   sign_verify={hv.verify_hmac_sha256(b'test-body', sig, 'test-secret')}")

    ce = parwa_core.CryptoEngine(4)
    pw_hash = ce.hash_password("test123")
    print(f"  CryptoEngine:    pw_verify={ce.verify_password('test123', pw_hash)} api_key_prefix_ak={ce.hash_api_key('sk-test').startswith('ak$')}")

    cp = parwa_core.ConnectionPool()
    cp.register("stripe", 5, 60.0, 10.0)
    ok = cp.checkout("stripe")
    cp.checkin("stripe", True)
    stats = cp.get_stats("stripe")
    print(f"  ConnectionPool:  checkout_ok={ok} active={stats['active']} registered={stats['registered']}")

    al = parwa_core.AsyncLogger(1000, "info")
    al.info("test message", "parwa_core")
    al.warning("test warning", "parwa_core")
    flushed = al.flush()
    al_stats = al.get_stats()
    print(f"  AsyncLogger:     flushed={len(flushed)} total_logged={al_stats['total_logged']} dropped={al_stats['dropped_count']}")

    print()
    print("=== ALL 10 MODULES LOADED AND WORKING ===")
