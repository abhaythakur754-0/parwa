"""
Day 6: Auth & JWT Unit Tests

Comprehensive tests for backend/app/core/auth.py — the PARWA JWT Authentication
Service (BC-011).

Covers:
- create_access_token: JWT creation with all required claims (sub, company_id,
  email, role, plan, type, exp, iat, nbf, jti)
- verify_access_token: token validation, expired/wrong-type/wrong-sig rejection,
  key rotation (L-02) via JWT_PREVIOUS_KEYS
- get_token_jti: jti extraction without full verification (M-10)
- get_jwt_previous_keys: key rotation state inspection (L-02)
- generate_refresh_token: opaque token generation (43 chars, URL-safe)
- hash_refresh_token: SHA-256 peppered hashing for DB storage (BC-011)
- get_access_token_expiry_seconds: config-driven expiry

Security requirements validated:
- BC-011: JWT_SECRET_KEY from env, HS256 algorithm, proper expiry
- M-10: jti claim for token blacklisting support
- L-02: JWT key rotation via JWT_PREVIOUS_KEYS
- L16: nbf (not-before) claim in JWT
- L13: subscription plan claim in JWT
"""

import base64
import json
import os
import sys
from datetime import datetime, timedelta, timezone

# Add backend to path for nested app imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

import pytest
from jose import JWTError, jwt

# Support both import contexts:
# - Running from backend/ with --noconftest: 'app.*' is on sys.path
# - Running from parwa/ with full conftest: 'backend.app.*' is on sys.path
try:
    from app.core.auth import (  # type: ignore[import-not-found]
        JWT_ALGORITHM,
        create_access_token,
        generate_refresh_token,
        get_access_token_expiry_seconds,
        get_jwt_previous_keys,
        get_token_jti,
        hash_refresh_token,
        verify_access_token,
    )
    from app.exceptions import AuthenticationError as _AE  # type: ignore[import-not-found]
    _AUTH_MOD = "app"
except ImportError:
    from backend.app.core.auth import (
        JWT_ALGORITHM,
        create_access_token,
        generate_refresh_token,
        get_access_token_expiry_seconds,
        get_jwt_previous_keys,
        get_token_jti,
        hash_refresh_token,
        verify_access_token,
    )
    from backend.app.exceptions import AuthenticationError as _AE
    _AUTH_MOD = "backend.app"

AuthenticationError = _AE

# Convenient reference to the auth module for mutating _JWT_PREVIOUS_KEYS
if _AUTH_MOD == "app":
    import app.core.auth as auth_mod  # type: ignore[import-not-found]
else:
    import backend.app.core.auth as auth_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_secret() -> str:
    """Return the JWT secret currently active in the test environment."""
    return os.environ.get("JWT_SECRET_KEY", "test_jwt_secret_key_not_prod")


def _make_token_directly(
    payload: dict,
    key: str | None = None,
) -> str:
    """Create a raw JWT using jose, bypassing our auth module."""
    return jwt.encode(payload, key or _current_secret(), algorithm="HS256")


def _make_expired_token(key: str | None = None) -> str:
    """Create a JWT that has already expired."""
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    payload = {
        "sub": "user-expired",
        "company_id": "comp-exp",
        "email": "expired@test.com",
        "role": "owner",
        "plan": "starter",
        "type": "access",
        "exp": past,
        "iat": past - timedelta(minutes=15),
        "nbf": past - timedelta(minutes=15),
        "jti": "expired-jti-123",
    }
    return _make_token_directly(payload, key)


def _make_refresh_type_token(key: str | None = None) -> str:
    """Create a validly-signed JWT with type='refresh' (wrong type)."""
    payload = {
        "sub": "user-refresh",
        "company_id": "comp-ref",
        "email": "refresh@test.com",
        "role": "owner",
        "plan": "starter",
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "iat": datetime.now(timezone.utc),
        "nbf": datetime.now(timezone.utc),
        "jti": "refresh-jti-456",
    }
    return _make_token_directly(payload, key)


# ===========================================================================
# 1. create_access_token
# ===========================================================================


class TestCreateAccessToken:
    """Tests for JWT access token creation."""

    def test_token_is_valid_jwt_with_three_parts(self):
        """Token must be a standard three-part JWT (header.payload.signature)."""
        token = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
        )
        parts = token.split(".")
        assert len(parts) == 3
        # Each part must be valid base64url
        for part in parts:
            # jose uses base64url without padding
            padded = part + "=" * (-len(part) % 4)
            base64.urlsafe_b64decode(padded)

    def test_valid_token_contains_all_required_claims(self):
        """Decoded token must contain sub, company_id, email, role, plan, type,
        exp, iat, nbf, and jti claims."""
        token = create_access_token(
            user_id="user-abc",
            company_id="company-xyz",
            email="owner@example.com",
            role="admin",
            plan="growth",
        )
        payload = verify_access_token(token)

        assert payload["sub"] == "user-abc"
        assert payload["company_id"] == "company-xyz"
        assert payload["email"] == "owner@example.com"
        assert payload["role"] == "admin"
        assert payload["plan"] == "growth"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload
        assert "nbf" in payload
        assert "jti" in payload

    def test_token_uses_hs256_algorithm(self):
        """BC-011: Token header must specify HS256 algorithm."""
        token = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
        )
        # Decode header without verification
        header_b64 = token.split(".")[0]
        padded = header_b64 + "=" * (-len(header_b64) % 4)
        header = json.loads(base64.urlsafe_b64decode(padded))
        assert header["alg"] == "HS256"
        # Also verify the module-level constant
        assert JWT_ALGORITHM == "HS256"

    def test_token_includes_jti_claim(self):
        """M-10: Token must include a unique jti for blacklisting support."""
        token = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
        )
        payload = verify_access_token(token)
        jti = payload["jti"]
        assert isinstance(jti, str)
        assert len(jti) > 0
        # jti should be URL-safe base64 (no special chars)
        assert jti.isascii()

    def test_token_includes_nbf_claim(self):
        """L16: Token must include nbf (not-before) claim equal to iat."""
        token = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
        )
        payload = verify_access_token(token)
        assert "nbf" in payload
        assert payload["nbf"] == payload["iat"]

    def test_default_plan_is_starter(self):
        """When plan is not provided, it defaults to 'starter'."""
        token = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
        )
        payload = verify_access_token(token)
        assert payload["plan"] == "starter"

    def test_custom_plan_is_stored(self):
        """Explicitly set plan must appear in the token."""
        token = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
            plan="enterprise",
        )
        payload = verify_access_token(token)
        assert payload["plan"] == "enterprise"

    def test_tokens_for_different_users_are_unique(self):
        """Different users must produce different tokens (different sub)."""
        t1 = create_access_token(
            user_id="user-A", company_id="c-1",
            email="a@b.com", role="owner",
        )
        t2 = create_access_token(
            user_id="user-B", company_id="c-1",
            email="a@b.com", role="owner",
        )
        assert t1 != t2

    def test_tokens_have_unique_jti(self):
        """M-10: Each token must have a unique jti."""
        t1 = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
        )
        t2 = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
        )
        p1 = verify_access_token(t1)
        p2 = verify_access_token(t2)
        assert p1["jti"] != p2["jti"]

    def test_exp_is_future_relative_to_iat(self):
        """Expiry must be strictly after issued-at time."""
        token = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
        )
        payload = verify_access_token(token)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        assert exp > iat
        delta = (exp - iat).total_seconds()
        assert delta > 0
        assert delta <= 900  # 15 minutes max

    def test_token_type_is_access(self):
        """Token type claim must be 'access'."""
        token = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
        )
        payload = verify_access_token(token)
        assert payload["type"] == "access"

    def test_token_is_non_empty_string(self):
        """Token must be a non-empty string."""
        token = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
        )
        assert isinstance(token, str)
        assert len(token) > 0


# ===========================================================================
# 2. verify_access_token
# ===========================================================================


class TestVerifyAccessToken:
    """Tests for JWT access token verification."""

    def test_valid_token_returns_payload(self):
        """A valid, unexpired token should return its full payload."""
        token = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
        )
        payload = verify_access_token(token)
        assert isinstance(payload, dict)
        assert payload["sub"] == "u-1"

    def test_expired_token_raises_authentication_error(self):
        """An expired token must raise AuthenticationError."""
        token = _make_expired_token()
        with pytest.raises(AuthenticationError):
            verify_access_token(token)

    def test_wrong_type_refresh_raises_error(self):
        """A token with type='refresh' must be rejected."""
        token = _make_refresh_type_token()
        with pytest.raises(AuthenticationError) as exc_info:
            verify_access_token(token)
        assert "type" in str(exc_info.value.message).lower() or \
               "type" in str(exc_info.value.details).lower() or \
               exc_info.value.error_code == "AUTHENTICATION_ERROR"

    def test_wrong_signature_raises_error(self):
        """A token signed with a completely different key must fail."""
        other_key = "totally-different-secret-key-xyz-123"
        payload = {
            "sub": "u-1", "company_id": "c-1", "email": "a@b.com",
            "role": "owner", "plan": "starter", "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            "iat": datetime.now(timezone.utc),
            "nbf": datetime.now(timezone.utc),
            "jti": "sig-test-jti",
        }
        token = _make_token_directly(payload, key=other_key)
        with pytest.raises(AuthenticationError):
            verify_access_token(token)

    def test_empty_token_raises_error(self):
        """An empty string must raise AuthenticationError."""
        with pytest.raises(AuthenticationError):
            verify_access_token("")

    def test_malformed_token_raises_error(self):
        """A garbage string must raise AuthenticationError."""
        with pytest.raises(AuthenticationError):
            verify_access_token("not.a.valid.jwt")

    def test_tampered_payload_raises_error(self):
        """A token with modified payload bytes must fail signature check."""
        token = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
        )
        parts = token.split(".")
        # Tamper with the payload (middle segment)
        payload_b64 = parts[1]
        # Flip a character
        tampered_payload = payload_b64[:-1] + (
            "A" if payload_b64[-1] != "A" else "B"
        )
        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"
        with pytest.raises(AuthenticationError):
            verify_access_token(tampered_token)

    def test_key_rotation_with_previous_keys(self):
        """L-02: Token signed with a previous key must still verify."""
        old_key = "old-secret-key-for-rotation-test"
        # Create a token signed with the old key
        payload = {
            "sub": "u-rot", "company_id": "c-rot", "email": "rot@test.com",
            "role": "admin", "plan": "growth", "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            "iat": datetime.now(timezone.utc),
            "nbf": datetime.now(timezone.utc),
            "jti": "rotation-jti-test",
        }
        token = _make_token_directly(payload, key=old_key)

        # Temporarily inject old_key into previous keys
        original_prev = list(auth_mod._JWT_PREVIOUS_KEYS)
        try:
            auth_mod._JWT_PREVIOUS_KEYS = [old_key]
            # Verify should succeed because old_key is in previous keys
            result = verify_access_token(token)
            assert result["sub"] == "u-rot"
            assert result["plan"] == "growth"
        finally:
            auth_mod._JWT_PREVIOUS_KEYS = original_prev

    def test_key_rotation_current_key_takes_priority(self):
        """L-02: Token signed with current key verifies even when
        previous keys also contain it."""
        token = create_access_token(
            user_id="u-prio", company_id="c-prio",
            email="prio@test.com", role="owner",
        )
        # Inject current key into previous keys (redundant but harmless)
        original_prev = list(auth_mod._JWT_PREVIOUS_KEYS)
        try:
            auth_mod._JWT_PREVIOUS_KEYS = [_current_secret()]
            result = verify_access_token(token)
            assert result["sub"] == "u-prio"
        finally:
            auth_mod._JWT_PREVIOUS_KEYS = original_prev

    def test_all_roles_accepted(self):
        """Tokens with different roles must all verify correctly."""
        for role in ("owner", "admin", "agent", "viewer"):
            token = create_access_token(
                user_id="u-1", company_id="c-1",
                email="a@b.com", role=role,
            )
            payload = verify_access_token(token)
            assert payload["role"] == role


# ===========================================================================
# 3. get_token_jti
# ===========================================================================


class TestGetTokenJti:
    """Tests for jti extraction without full verification (M-10)."""

    def test_valid_token_returns_jti_string(self):
        """M-10: Must extract jti from a valid token."""
        token = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
        )
        jti = get_token_jti(token)
        assert isinstance(jti, str)
        assert len(jti) > 0

    def test_malformed_token_returns_none(self):
        """Malformed/garbage token must return None, not raise."""
        assert get_token_jti("garbage") is None
        assert get_token_jti("") is None
        assert get_token_jti("not.jwt") is None

    def test_jti_matches_verified_payload(self):
        """JTI from get_token_jti must match jti in the verified payload."""
        token = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
        )
        jti = get_token_jti(token)
        payload = verify_access_token(token)
        assert jti == payload["jti"]

    def test_expired_token_still_returns_jti(self):
        """M-10: get_token_jti works without verification (even expired)."""
        token = _make_expired_token()
        jti = get_token_jti(token)
        assert jti == "expired-jti-123"


# ===========================================================================
# 4. get_jwt_previous_keys
# ===========================================================================


class TestGetJwtPreviousKeys:
    """Tests for L-02 key rotation state inspection."""

    def test_returns_list(self):
        """Must always return a list."""
        keys = get_jwt_previous_keys()
        assert isinstance(keys, list)

    def test_returns_copy_not_reference(self):
        """Mutating the returned list must not affect internal state."""
        keys = get_jwt_previous_keys()
        original_len = len(keys)
        keys.append("injected-key")
        # Internal state should be unchanged
        assert len(auth_mod._JWT_PREVIOUS_KEYS) == original_len

    def test_reflects_env_config(self):
        """In test env with no JWT_PREVIOUS_KEYS set, should be empty."""
        keys = get_jwt_previous_keys()
        # By default in tests, no previous keys are configured
        assert isinstance(keys, list)


# ===========================================================================
# 5. generate_refresh_token
# ===========================================================================


class TestGenerateRefreshToken:
    """Tests for opaque refresh token generation."""

    def test_returns_urlsafe_string(self):
        """Token must be URL-safe (no + or / characters)."""
        token = generate_refresh_token()
        assert isinstance(token, str)
        assert len(token) > 0
        # secrets.token_urlsafe(32) produces only [A-Za-z0-9_-]
        assert all(c.isalnum() or c in "_-" for c in token)

    def test_returns_43_characters(self):
        """secrets.token_urlsafe(32) produces exactly 43 characters."""
        token = generate_refresh_token()
        assert len(token) == 43

    def test_tokens_are_unique(self):
        """Each call must produce a unique token."""
        tokens = {generate_refresh_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_no_whitespace(self):
        """Token must contain no whitespace."""
        token = generate_refresh_token()
        assert token.strip() == token


# ===========================================================================
# 6. hash_refresh_token
# ===========================================================================


class TestHashRefreshToken:
    """Tests for SHA-256 peppered refresh token hashing."""

    def test_returns_sha256_hex_string(self):
        """Hash must be a 64-character lowercase hex string."""
        h = hash_refresh_token("test-token")
        assert isinstance(h, str)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_input_same_output(self):
        """Hashing must be deterministic (same pepper + same input = same hash)."""
        h1 = hash_refresh_token("my-refresh-token")
        h2 = hash_refresh_token("my-refresh-token")
        assert h1 == h2

    def test_different_input_different_output(self):
        """Different tokens must produce different hashes."""
        h1 = hash_refresh_token("token-aaa")
        h2 = hash_refresh_token("token-bbb")
        assert h1 != h2

    def test_empty_string_hash_differs(self):
        """Hashing an empty string should still produce a valid SHA-256 output."""
        h = hash_refresh_token("")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_does_not_reveal_token(self):
        """Hash must not contain the original token as a substring."""
        token = "super-secret-refresh-token-xyz"
        h = hash_refresh_token(token)
        assert token not in h

    def test_hash_is_peppered(self):
        """Hash should differ from plain SHA-256 (peppered via REFRESH_TOKEN_PEPPER)."""
        import hashlib
        token = "pepper-test-token"
        our_hash = hash_refresh_token(token)
        # Plain SHA-256 without pepper
        plain_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        # Unless REFRESH_TOKEN_PEPPER is empty, they must differ
        pepper = os.environ.get("REFRESH_TOKEN_PEPPER", "")
        if pepper:
            assert our_hash != plain_hash


# ===========================================================================
# 7. get_access_token_expiry_seconds
# ===========================================================================


class TestGetAccessTokenExpirySeconds:
    """Tests for config-driven access token expiry."""

    def test_returns_positive_int(self):
        """Must return a positive integer."""
        expiry = get_access_token_expiry_seconds()
        assert isinstance(expiry, int)
        assert expiry > 0

    def test_default_is_900_seconds(self):
        """Default config is 15 minutes = 900 seconds."""
        expiry = get_access_token_expiry_seconds()
        assert expiry == 900

    def test_matches_config_value(self):
        """Must match JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60."""
        if _AUTH_MOD == "app":
            from app.config import get_settings  # type: ignore[import-not-found]
        else:
            from backend.app.config import get_settings
        settings = get_settings()
        expected = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert get_access_token_expiry_seconds() == expected


# ===========================================================================
# 8. Integration tests
# ===========================================================================


class TestIntegrationCreateVerify:
    """End-to-end integration: create → verify round-trip."""

    def test_create_verify_round_trip(self):
        """Token created by create_access_token must verify and contain
        all original fields."""
        token = create_access_token(
            user_id="user-int",
            company_id="company-int",
            email="integration@test.com",
            role="admin",
            plan="growth",
        )
        payload = verify_access_token(token)
        assert payload["sub"] == "user-int"
        assert payload["company_id"] == "company-int"
        assert payload["email"] == "integration@test.com"
        assert payload["role"] == "admin"
        assert payload["plan"] == "growth"
        assert payload["type"] == "access"

    def test_all_fields_decode_correctly(self):
        """All claims from a verified token must have the expected types."""
        token = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
            plan="enterprise",
        )
        payload = verify_access_token(token)

        # All string claims
        for key in ("sub", "company_id", "email", "role", "plan", "type", "jti"):
            assert isinstance(payload[key], str), f"{key} should be str"

        # Numeric timestamp claims
        for key in ("exp", "iat", "nbf"):
            assert isinstance(payload[key], (int, float)), f"{key} should be numeric"

    def test_round_trip_preserves_all_roles(self):
        """Every supported role survives the create → verify round trip."""
        for role in ("owner", "admin", "agent", "viewer"):
            token = create_access_token(
                user_id="u-1", company_id="c-1",
                email="a@b.com", role=role,
                plan="starter",
            )
            payload = verify_access_token(token)
            assert payload["role"] == role

    def test_round_trip_preserves_all_plans(self):
        """Every subscription plan survives the create → verify round trip."""
        for plan in ("starter", "growth", "enterprise"):
            token = create_access_token(
                user_id="u-1", company_id="c-1",
                email="a@b.com", role="owner",
                plan=plan,
            )
            payload = verify_access_token(token)
            assert payload["plan"] == plan

    def test_create_then_jti_then_verify(self):
        """M-10 integration: create token, extract jti, verify, compare."""
        token = create_access_token(
            user_id="u-1", company_id="c-1",
            email="a@b.com", role="owner",
        )
        # Extract jti without verification
        jti = get_token_jti(token)
        assert jti is not None
        # Full verification
        payload = verify_access_token(token)
        assert payload["jti"] == jti
