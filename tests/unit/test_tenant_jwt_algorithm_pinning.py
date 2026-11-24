import pytest
from starlette.requests import Request

from app.core import jwt_auth
from app.middleware.tenant import _extract_company_id_from_jwt


def _request(token: str) -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/api/protected",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
        "query_string": b"",
        "server": ("testserver", 80),
        "scheme": "http",
        "client": ("127.0.0.1", 12345),
    })


def test_tenant_middleware_uses_configured_jwt_verifier(monkeypatch):
    seen = []
    monkeypatch.setattr(
        jwt_auth,
        "verify_access_token",
        lambda token: (seen.append(token) or {"company_id": "company-123"}),
    )

    assert _extract_company_id_from_jwt(_request("signed-token")) == "company-123"
    assert seen == ["signed-token"]


def test_tenant_middleware_does_not_recover_claims_when_verification_fails(monkeypatch):
    def reject(_token):
        raise jwt_auth.AuthenticationError(message="invalid token")

    monkeypatch.setattr(jwt_auth, "verify_access_token", reject)

    assert _extract_company_id_from_jwt(_request("forged-hs256-token")) is None


def test_tenant_middleware_ignores_api_key_tokens():
    assert _extract_company_id_from_jwt(_request("parwa_live_example")) is None
