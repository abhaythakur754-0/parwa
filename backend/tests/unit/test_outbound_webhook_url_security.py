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


def test_pinned_https_connection_uses_vetted_ip_and_original_tls_hostname(monkeypatch):
    import socket
    from app.security import outbound_url

    seen = {}

    class FakeSocket:
        def close(self):
            pass

    class FakeTLSContext:
        def wrap_socket(self, raw_socket, server_hostname):
            seen["server_hostname"] = server_hostname
            return raw_socket

    fake_socket = FakeSocket()
    monkeypatch.setattr(
        outbound_url.ssl,
        "create_default_context",
        lambda: FakeTLSContext(),
    )
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda address, timeout: seen.update(address=address, timeout=timeout) or fake_socket,
    )

    connection = outbound_url._PinnedHTTPSConnection(
        host="customer.example",
        port=443,
        address="93.184.216.34",
        timeout=3.0,
    )
    connection.connect()

    assert seen["address"] == ("93.184.216.34", 443)
    assert seen["server_hostname"] == "customer.example"
    connection.close()


def test_post_public_https_url_connects_to_resolved_ip(monkeypatch):
    import socket
    from app.security import outbound_url

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )

    captured = {}

    class FakeResponse:
        status = 204

        def read(self, _limit):
            return b"accepted"

    class FakeConnection:
        def __init__(self, host, port, address, timeout):
            captured.update(host=host, port=port, address=address, timeout=timeout)

        def request(self, method, path, body, headers):
            captured.update(method=method, path=path, body=body, headers=headers)

        def getresponse(self):
            return FakeResponse()

        def close(self):
            pass

    monkeypatch.setattr(outbound_url, "_PinnedHTTPSConnection", FakeConnection)

    status, body = outbound_url.post_public_https_url(
        "https://customer.example/hooks?source=parwa",
        '{"event":"test"}',
        {"Content-Type": "application/json"},
    )

    assert status == 204
    assert body == "accepted"
    assert captured["address"] == "93.184.216.34"
    assert captured["host"] == "customer.example"
    assert captured["path"] == "/hooks?source=parwa"
    assert captured["method"] == "POST"
    assert captured["headers"]["Host"] == "customer.example"


def test_post_rejects_dns_rebinding_to_private_address_before_connect(monkeypatch):
    import socket
    from app.security import outbound_url

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ],
    )

    def unexpected_connection(*_args, **_kwargs):
        raise AssertionError("private destination must be rejected before connect")

    monkeypatch.setattr(outbound_url, "_PinnedHTTPSConnection", unexpected_connection)
    with pytest.raises(ValueError, match="public IP"):
        outbound_url.post_public_https_url(
            "https://customer.example/hook",
            "{}",
            {"Content-Type": "application/json"},
        )
