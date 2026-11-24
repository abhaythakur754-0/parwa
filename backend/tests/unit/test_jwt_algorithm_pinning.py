from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from jose import jwt

from app.core import jwt_auth
from app.exceptions import AuthenticationError


def _settings(algorithm="HS256"):
    return SimpleNamespace(
        JWT_ALGORITHM=algorithm,
        JWT_SECRET_KEY="test-secret-that-is-long-enough-for-hs256",
        JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15,
        JWT_KID="test-key",
    )


def _token(secret, token_type="access"):
    return jwt.encode(
        {
            "sub": "user-123",
            "jti": "test-token-id",
            "type": token_type,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        secret,
        algorithm="HS256",
    )


def test_hs256_verifier_accepts_access_token_when_hs256_is_configured(monkeypatch):
    monkeypatch.setattr(jwt_auth, "get_settings", lambda: _settings("HS256"))
    payload = jwt_auth.verify_access_token(_token(_settings().JWT_SECRET_KEY))
    assert payload["sub"] == "user-123"


def test_rs256_verifier_does_not_fall_back_to_hs256(monkeypatch):
    settings = _settings("RS256")
    monkeypatch.setattr(jwt_auth, "get_settings", lambda: settings)
    monkeypatch.setattr(jwt_auth, "_load_rs256_keys", lambda: (None, None))

    with pytest.raises(AuthenticationError, match="RS256"):
        jwt_auth.verify_access_token(_token(settings.JWT_SECRET_KEY))


def test_rs256_signing_fails_if_private_key_is_missing(monkeypatch):
    settings = _settings("RS256")
    monkeypatch.setattr(jwt_auth, "get_settings", lambda: settings)
    monkeypatch.setattr(jwt_auth, "_load_rs256_keys", lambda: (None, None))

    with pytest.raises(RuntimeError, match="refusing to sign with HS256"):
        jwt_auth.create_access_token(
            user_id="user-123",
            company_id="company-456",
            email="user@example.com",
            role="owner",
        )


def test_refresh_token_is_not_accepted_as_access_token(monkeypatch):
    settings = _settings("HS256")
    monkeypatch.setattr(jwt_auth, "get_settings", lambda: settings)

    with pytest.raises(AuthenticationError, match="token type"):
        jwt_auth.verify_access_token(_token(settings.JWT_SECRET_KEY, "refresh"))
