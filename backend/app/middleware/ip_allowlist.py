"""
IP Allowlist Middleware (BC-006, BC-012)

ASGI middleware that restricts access based on client IP.
- Configurable via ALLOWED_IPS environment variable
  (comma-separated list, supports individual IPs and CIDRs)
- Skip prefixes for health/monitoring paths
- Fail-open on missing IP (X-Forwarded-For support)
- Fail-open on Redis errors (infrastructure resilience)
- Returns 403 with structured JSON error (BC-012)
- FIX L34: Added comprehensive logging for all decisions
- FIX L35: Log Redis errors instead of silently passing

Configuration:
    ALLOWED_IPS: Comma-separated IP/CIDR list (env var)
    IP_ALLOWLIST_SKIP_PREFIXES: Comma-separated path prefixes
        to skip (env var, default: /health,/ready,/metrics)
    IP_ALLOWLIST_ENABLED: bool — Master switch (default false)
"""

import ipaddress
import json
import logging
import os

logger = logging.getLogger("parwa.ip_allowlist")

# Skip prefixes: health and monitoring endpoints
DEFAULT_SKIP_PREFIXES = ["/health", "/ready", "/metrics"]


class IPAllowlistMiddleware:
    """ASGI middleware for IP-based access control.

    Checks client IP against configured allowlists.
    Supports both config-based ALLOWED_IPS (env var) and
    Redis-based per-route allowlists.

    Priority:
        1. If path is in skip prefixes -> allow
        2. If ALLOWED_IPS is set in env -> use config list
        3. If Redis has route-specific key -> use Redis list
        4. If Redis has global key -> use global list
        5. No allowlist configured -> fail-open
    """

    def __init__(self, app):
        self.app = app
        self._environment = os.environ.get(
            "ENVIRONMENT", "development",
        )
        self._allowed_ips = self._parse_allowed_ips()
        self._skip_prefixes = (
            self._parse_skip_prefixes()
        )

    def _parse_allowed_ips(self) -> list:
        """Parse ALLOWED_IPS from environment variable."""
        raw = os.environ.get("ALLOWED_IPS", "")
        if not raw:
            return []
        ips = [ip.strip() for ip in raw.split(",") if ip.strip()]
        logger.info(
            "ip_allowlist_configured source=%s count=%d",
            "env", len(ips),
        )
        return ips

    def _parse_skip_prefixes(self) -> list:
        """Parse IP_ALLOWLIST_SKIP_PREFIXES from env."""
        raw = os.environ.get(
            "IP_ALLOWLIST_SKIP_PREFIXES", "",
        )
        if not raw:
            return list(DEFAULT_SKIP_PREFIXES)
        return [
            p.strip() for p in raw.split(",")
            if p.strip()
        ]

    def _is_enabled(self) -> bool:
        """Check if IP allowlist is enabled."""
        return os.environ.get(
            "IP_ALLOWLIST_ENABLED", "false",
        ).lower() == "true"

    async def __call__(self, scope, receive, send):
        """Process ASGI request through IP allowlist."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Fail-open in test environment
        if self._environment == "test":
            await self.app(scope, receive, send)
            return

        # Check if middleware is enabled
        if not self._is_enabled():
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")

        # Skip health/monitoring paths
        if self._should_skip(path):
            await self.app(scope, receive, send)
            return

        # Get client IP
        client_ip = self._get_client_ip(scope)
        if not client_ip:
            # FIX L36: Log when IP can't be determined.
            # Fail-open by design (BC-006) but log it.
            logger.warning(
                "ip_allowlist_no_client_ip path=%s",
                path,
            )
            await self.app(scope, receive, send)
            return

        # Check IP against allowlist
        allowed = await self._check_ip_allowed(
            client_ip, path,
        )
        if not allowed:
            logger.warning(
                "ip_allowlist_blocked client_ip=%s path=%s",
                client_ip, path,
            )
            await self._send_forbidden(
                scope, receive, send,
                "Access denied: IP not in allowlist",
            )
            return

        await self.app(scope, receive, send)

    def _should_skip(self, path: str) -> bool:
        """Check if path should skip IP allowlist."""
        for prefix in self._skip_prefixes:
            if path == prefix or path.startswith(
                prefix + "/",
            ):
                return True
        return False

    def _get_client_ip(self, scope: dict) -> str:
        """Extract client IP from ASGI scope.

        Checks X-Forwarded-For header first (behind proxy),
        then falls back to client address.
        """
        headers = dict(scope.get("headers", []))
        forwarded = headers.get(
            b"x-forwarded-for", b"",
        ).decode("utf-8", errors="ignore")
        if forwarded:
            return forwarded.split(",")[0].strip()

        client = scope.get("client")
        if client:
            return client[0]
        return ""

    async def _check_ip_allowed(
        self, client_ip: str, path: str,
    ) -> bool:
        """Check if client IP is in the allowlist.

        Priority:
            1. Config-based ALLOWED_IPS (if set)
            2. Redis route-specific allowlist
            3. Redis global allowlist
            4. No allowlist -> fail-open

        Returns:
            True if IP is allowed.
        """
        try:
            ip_obj = ipaddress.ip_address(
                client_ip.strip(),
            )
        except ValueError:
            logger.warning(
                "ip_allowlist_invalid_ip_format client_ip=%s",
                client_ip,
            )
            return False

        # Config-based ALLOWED_IPS takes priority
        if self._allowed_ips:
            return self._ip_in_ranges(
                ip_obj, self._allowed_ips,
            )

        # Fall back to Redis-based allowlist
        route_key = self._get_route_key(path)

        try:
            allowed_ips = await self._get_redis_allowlist(
                route_key,
            )
            if allowed_ips is not None:
                return self._ip_in_ranges(
                    ip_obj, allowed_ips,
                )

            global_ips = await self._get_redis_allowlist(
                "global",
            )
            if global_ips is not None:
                return self._ip_in_ranges(
                    ip_obj, global_ips,
                )
        except Exception as exc:
            # FIX L35: Log Redis errors instead of
            # silently passing (fail-open still applies)
            logger.warning(
                "ip_allowlist_redis_error_fail_open path=%s "
                "route_key=%s error=%s",
                path, route_key, exc,
            )

        # No allowlist configured -> fail-open
        return True

    def _get_route_key(self, path: str) -> str:
        """Convert path to a route key for Redis lookup."""
        parts = path.strip("/").split("/")
        if len(parts) >= 3:
            return f"{parts[1]}_{parts[2]}"
        if len(parts) >= 1:
            return parts[0]
        return "global"

    async def _get_redis_allowlist(
        self, key: str,
    ) -> list | None:
        """Get allowlist from Redis."""
        try:
            from backend.app.core.redis import get_redis
            redis_client = await get_redis()
            redis_key = f"parwa:ip_allowlist:{key}"
            raw = await redis_client.get(redis_key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            raise

    def _ip_in_ranges(
        self, ip_obj, ranges: list,
    ) -> bool:
        """Check if an IP falls within any CIDR range."""
        for cidr in ranges:
            try:
                if ip_obj in ipaddress.ip_network(
                    cidr, strict=False,
                ):
                    return True
            except Exception:
                continue
        return False

    async def _send_forbidden(
        self, scope, receive, send,
        message: str,
    ):
        """Send a 403 JSON response (BC-012)."""
        body = json.dumps({
            "error": {
                "code": "FORBIDDEN",
                "message": message,
                "details": None,
            }
        }).encode("utf-8")

        await send({
            "type": "http.response.start",
            "status": 403,
            "headers": [
                [b"content-type", b"application/json"],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
