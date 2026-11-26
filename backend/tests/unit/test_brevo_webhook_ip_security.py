"""Regression tests for spoof-resistant Brevo webhook IP verification."""

from types import SimpleNamespace

from starlette.requests import Request


def _request_with_forwarded_chain(value: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "server": ("api.parwa.buzz", 443),
            "path": "/api/webhooks/brevo",
            "query_string": b"",
            "headers": [(b"x-forwarded-for", value.encode("ascii"))],
            "client": ("127.0.0.1", 12345),
        }
    )


def test_brevo_allowlist_uses_rightmost_trusted_proxy_ip(monkeypatch):
    from app.api.webhooks import _verify_provider_signature
    from app.core.security import security_utils

    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: SimpleNamespace(BREVO_INBOUND_IPS="185.107.232.0/24"),
    )
    monkeypatch.setattr(security_utils, "_TRUSTED_PROXY_COUNT", 1)

    # A forged allowed address at the left of XFF must not override the
    # actual client address appended by the trusted ingress proxy.
    request = _request_with_forwarded_chain("185.107.232.1, 8.8.8.8")
    assert _verify_provider_signature("brevo", request, {}, b"{}") is False


def test_brevo_allowlist_accepts_real_client_ip_from_trusted_proxy_chain(monkeypatch):
    from app.api.webhooks import _verify_provider_signature
    from app.core.security import security_utils

    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: SimpleNamespace(BREVO_INBOUND_IPS="185.107.232.0/24"),
    )
    monkeypatch.setattr(security_utils, "_TRUSTED_PROXY_COUNT", 1)

    request = _request_with_forwarded_chain("8.8.8.8, 185.107.232.1")
    assert _verify_provider_signature("brevo", request, {}, b"{}") is True
