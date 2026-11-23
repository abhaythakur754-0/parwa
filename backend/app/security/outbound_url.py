"""Validation for user-configured outbound webhook destinations.

These URLs are fetched by the Parwa server, so they must not target local,
private, link-local, reserved, or cloud metadata addresses.
"""
import ipaddress
import socket
from urllib.parse import urlsplit


_BLOCKED_HOSTS = {
    "localhost",
    "metadata",
    "metadata.google.internal",
}


def validate_public_https_url(value: str) -> str:
    """Return a normalized public HTTPS URL or raise ValueError."""
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

    return parsed.geturl()
