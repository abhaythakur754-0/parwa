"""Validation for user-configured outbound webhook destinations.

These URLs are fetched by the Parwa server, so they must not target local,
private, link-local, reserved, or cloud metadata addresses.
"""
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit


_BLOCKED_HOSTS = {
    "localhost",
    "metadata",
    "metadata.google.internal",
}


def _resolve_public_destination(value: str):
    """Parse a public HTTPS destination and return its vetted IP addresses."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Webhook URL is required")

    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() != "https":
        raise ValueError("Webhook URL must use HTTPS")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Webhook URL must have a valid host and no embedded credentials")
    if parsed.fragment:
        raise ValueError("Webhook URL must not contain a fragment")

    host = parsed.hostname.rstrip(".").lower()
    if (
        host in _BLOCKED_HOSTS
        or host.endswith((".localhost", ".local", ".internal", ".lan", ".home.arpa"))
    ):
        raise ValueError("Webhook URL host is not publicly routable")

    try:
        port = parsed.port or 443
    except ValueError as exc:
        raise ValueError("Webhook URL has an invalid port") from exc

    try:
        try:
            addresses = [ipaddress.ip_address(host)]
        except ValueError:
            resolved = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            addresses = [
                ipaddress.ip_address(item[4][0].split("%", 1)[0])
                for item in resolved
            ]
    except (OSError, ValueError) as exc:
        raise ValueError("Webhook URL host could not be safely resolved") from exc

    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Webhook URL must resolve only to public IP addresses")

    # Bound connection attempts even if a hostname publishes many A/AAAA
    # records. Every returned address was checked before this cap is applied.
    addresses = list(dict.fromkeys(addresses))[:8]
    return parsed, host, port, addresses


def validate_public_https_url(value: str) -> str:
    """Return a normalized public HTTPS URL or raise ValueError."""
    parsed, _host, _port, _addresses = _resolve_public_destination(value)
    return parsed.geturl()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection pinned to an already-vetted IP, retaining hostname TLS."""

    def __init__(self, host: str, port: int, address: str, timeout: float):
        super().__init__(
            host,
            port=port,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
        self._pinned_address = address

    def connect(self) -> None:
        # Connect directly to the vetted IP (no second DNS lookup), but retain
        # the original hostname for SNI and certificate hostname validation.
        raw_socket = socket.create_connection(
            (self._pinned_address, self.port),
            self.timeout,
        )
        try:
            self.sock = self._context.wrap_socket(
                raw_socket,
                server_hostname=self.host,
            )
        except Exception:
            raw_socket.close()
            raise


def post_public_https_url(
    value: str,
    payload: str,
    headers: dict[str, str],
    timeout: float = 10.0,
) -> tuple[int, str]:
    """POST to a validated HTTPS URL while pinning the DNS result.

    DNS is resolved and checked once per delivery, and the socket connects to
    that exact vetted IP. TLS SNI and certificate verification still use the
    original hostname. Redirects and ambient proxy environment variables are
    not involved.
    """
    parsed, host, port, addresses = _resolve_public_destination(value)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    host_header = f"[{host}]" if ":" in host else host
    if port != 443:
        host_header = f"{host_header}:{port}"

    request_headers = dict(headers)
    request_headers["Host"] = host_header
    request_headers["Connection"] = "close"

    last_error = None
    for address in addresses:
        connection = _PinnedHTTPSConnection(
            host=host,
            port=port,
            address=str(address),
            timeout=timeout,
        )
        try:
            connection.request(
                "POST",
                path,
                body=payload.encode("utf-8"),
                headers=request_headers,
            )
            response = connection.getresponse()
            response_body = response.read(65536).decode("utf-8", errors="replace")
            return response.status, response_body
        except Exception as exc:
            last_error = exc
        finally:
            connection.close()

    raise RuntimeError("Webhook destination connection failed") from last_error
