import pytest

from app.security.outbound_url import validate_public_https_url


def test_rejects_non_https_webhook_url():
    with pytest.raises(ValueError):
        validate_public_https_url("http://example.com/hook")


@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/hook",
        "https://127.0.0.1/hook",
        "https://10.0.0.5/hook",
        "https://169.254.169.254/latest/meta-data",
        "https://service.internal/hook",
    ],
)
def test_rejects_private_and_metadata_destinations(url):
    with pytest.raises(ValueError):
        validate_public_https_url(url)


def test_rejects_public_hostname_that_resolves_to_private_ip(monkeypatch):
    import socket

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.10", 443))
        ],
    )
    with pytest.raises(ValueError):
        validate_public_https_url("https://customer.example/hook")


def test_accepts_public_https_destination(monkeypatch):
    import socket

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )
    assert validate_public_https_url("https://customer.example/hook") == "https://customer.example/hook"
