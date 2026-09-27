"""
Tests for IP Allowlist Middleware (BC-012)

Tests cover:
- Allowed IP passes through
- Blocked IP gets 403
- Test environment skips check (ENVIRONMENT=test)
- Empty allowlist blocks all (when enabled)
- Redis failure fail-open
- 403 has structured JSON error format (BC-012)
"""

import json
import os


class TestIPAllowlistMiddleware:
    """IP Allowlist ASGI middleware tests."""

    def _make_scope(
        self, path="/api/webhooks/paddle",
        client_ip="1.2.3.4", headers=None,
    ):
        """Build a mock ASGI HTTP scope."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": path,
            "query_string": b"",
            "headers": headers or [],
            "client": (client_ip, 12345),
        }
        return scope

    async def _call_middleware(
        self, scope, enabled=False,
        ip_allowlist=None,
    ):
        """Call the middleware and return response."""
        # Save and restore env
        old_env = os.environ.get("ENVIRONMENT", "")
        old_enabled = os.environ.get("IP_ALLOWLIST_ENABLED", "")

        os.environ["ENVIRONMENT"] = "production"
        os.environ["IP_ALLOWLIST_ENABLED"] = (
            "true" if enabled else "false"
        )

        try:
            from backend.app.middleware.ip_allowlist import (
                IPAllowlistMiddleware,
            )

            # Track what downstream received
            downstream_called = False

            async def app(scope, receive, send):
                nonlocal downstream_called
                downstream_called = True
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [[b"content-type", b"application/json"]],
                })
                await send({
                    "type": "http.response.body",
                    "body": b'{"ok": true}',
                })

            middleware = IPAllowlistMiddleware(app)

            # Setup Redis mock if ip_allowlist is provided
            if ip_allowlist is not None:
                self._setup_redis_mock(
                    scope, ip_allowlist,
                )

            responses = []

            async def receive():
                return {"type": "http.request"}

            async def send(message):
                responses.append(message)

            await middleware(scope, receive, send)
            return responses, downstream_called
        finally:
            os.environ["ENVIRONMENT"] = old_env
            os.environ["IP_ALLOWLIST_ENABLED"] = old_enabled

    def _setup_redis_mock(self, scope, ip_allowlist):
        """Mock Redis to return the given allowlist."""
        import unittest.mock as mock

        from backend.app.core import redis as redis_module

        # Create a mock redis client
        mock_redis = mock.AsyncMock()
        mock_redis.get = mock.AsyncMock(
            return_value=json.dumps(ip_allowlist).encode()
            if ip_allowlist is not None
            else None,
        )

        # Patch get_redis to return our mock
        patcher = mock.patch.object(
            redis_module, "get_redis",
            mock.AsyncMock(return_value=mock_redis),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_test_environment_skips_check(self):
        """ENVIRONMENT=test skips IP check entirely."""
        old = os.environ.get("ENVIRONMENT", "")
        os.environ["ENVIRONMENT"] = "test"

        try:
            from backend.app.middleware.ip_allowlist import (
                IPAllowlistMiddleware,
            )

            downstream_called = False

            async def app(scope, receive, send):
                nonlocal downstream_called
                downstream_called = True
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [],
                })
                await send({
                    "type": "http.response.body",
                    "body": b"ok",
                })

            middleware = IPAllowlistMiddleware(app)

            async def run():
                scope = self._make_scope(client_ip="0.0.0.0")
                responses = []

                async def receive():
                    return {"type": "http.request"}

                async def send(msg):
                    responses.append(msg)

                await middleware(scope, receive, send)
                return responses, downstream_called

            import asyncio
            responses, called = asyncio.get_event_loop().run_until_complete(
                run()
            )
            assert called is True
            assert responses[0]["status"] == 200
        finally:
            os.environ["ENVIRONMENT"] = old

    def test_disabled_by_default(self):
        """Middleware passes through when disabled."""
        import asyncio

        async def run():
            scope = self._make_scope()
            responses, called = await self._call_middleware(
                scope, enabled=False,
            )
            return responses, called

        responses, called = asyncio.get_event_loop().run_until_complete(
            run()
        )
        assert called is True
        assert responses[0]["status"] == 200

    def test_no_allowlist_passes_through(self):
        """No allowlist in Redis (None) -> pass through."""
        import asyncio
        import unittest.mock as mock
        from backend.app.core import redis as redis_module

        mock_redis = mock.AsyncMock()
        mock_redis.get = mock.AsyncMock(return_value=None)
        patcher = mock.patch.object(
            redis_module, "get_redis",
            mock.AsyncMock(return_value=mock_redis),
        )
        patcher.start()

        async def run():
            scope = self._make_scope()
            responses, called = await self._call_middleware(
                scope, enabled=True,
            )
            return responses, called

        try:
            responses, called = asyncio.get_event_loop(
            ).run_until_complete(run())
            assert called is True
        finally:
            patcher.stop()

    def test_blocked_ip_gets_403(self):
        """IP not in allowlist gets 403."""
        import asyncio
        import unittest.mock as mock
        from backend.app.core import redis as redis_module

        mock_redis = mock.AsyncMock()
        mock_redis.get = mock.AsyncMock(
            return_value=json.dumps(
                ["10.0.0.0/8"]
            ).encode()
        )
        patcher = mock.patch.object(
            redis_module, "get_redis",
            mock.AsyncMock(return_value=mock_redis),
        )
        patcher.start()

        async def run():
            scope = self._make_scope(
                client_ip="1.2.3.4",
            )
            responses, called = await self._call_middleware(
                scope, enabled=True,
            )
            return responses, called

        try:
            responses, called = asyncio.get_event_loop(
            ).run_until_complete(run())
            assert called is False
            assert responses[0]["status"] == 403
        finally:
            patcher.stop()

    def test_allowed_ip_passes_through(self):
        """IP in allowlist passes through."""
        import asyncio
        import unittest.mock as mock
        from backend.app.core import redis as redis_module

        mock_redis = mock.AsyncMock()
        mock_redis.get = mock.AsyncMock(
            return_value=json.dumps(
                ["10.0.0.0/8"]
            ).encode()
        )
        patcher = mock.patch.object(
            redis_module, "get_redis",
            mock.AsyncMock(return_value=mock_redis),
        )
        patcher.start()

        async def run():
            scope = self._make_scope(
                client_ip="10.1.2.3",
            )
            responses, called = await self._call_middleware(
                scope, enabled=True,
            )
            return responses, called

        try:
            responses, called = asyncio.get_event_loop(
            ).run_until_complete(run())
            assert called is True
            assert responses[0]["status"] == 200
        finally:
            patcher.stop()

    def test_forbidden_has_structured_json(self):
        """403 response has BC-012 structured JSON error."""
        import asyncio
        import unittest.mock as mock
        from backend.app.core import redis as redis_module

        mock_redis = mock.AsyncMock()
        mock_redis.get = mock.AsyncMock(
            return_value=json.dumps(
                ["10.0.0.0/8"]
            ).encode()
        )
        patcher = mock.patch.object(
            redis_module, "get_redis",
            mock.AsyncMock(return_value=mock_redis),
        )
        patcher.start()

        async def run():
            scope = self._make_scope(
                client_ip="8.8.8.8",
            )
            responses, called = await self._call_middleware(
                scope, enabled=True,
            )
            return responses, called

        try:
            responses, called = asyncio.get_event_loop(
            ).run_until_complete(run())
            body = json.loads(responses[1]["body"])
            assert "error" in body
            assert body["error"]["code"] == "FORBIDDEN"
            assert body["error"]["message"] is not None
            assert body["error"]["details"] is None
        finally:
            patcher.stop()

    def test_empty_allowlist_blocks_all(self):
        """Empty allowlist blocks all IPs."""
        import asyncio
        import unittest.mock as mock
        from backend.app.core import redis as redis_module

        mock_redis = mock.AsyncMock()
        mock_redis.get = mock.AsyncMock(
            return_value=json.dumps([]).encode()
        )
        patcher = mock.patch.object(
            redis_module, "get_redis",
            mock.AsyncMock(return_value=mock_redis),
        )
        patcher.start()

        async def run():
            scope = self._make_scope(
                client_ip="10.1.2.3",
            )
            responses, called = await self._call_middleware(
                scope, enabled=True,
            )
            return responses, called

        try:
            responses, called = asyncio.get_event_loop(
            ).run_until_complete(run())
            assert called is False
            assert responses[0]["status"] == 403
        finally:
            patcher.stop()

    def test_redis_failure_fail_open(self):
        """Redis failure -> pass through (fail-open)."""
        import asyncio
        import unittest.mock as mock
        from backend.app.core import redis as redis_module

        mock_redis = mock.AsyncMock()
        mock_redis.get = mock.AsyncMock(
            side_effect=ConnectionError("Redis down"),
        )
        patcher = mock.patch.object(
            redis_module, "get_redis",
            mock.AsyncMock(return_value=mock_redis),
        )
        patcher.start()

        async def run():
            scope = self._make_scope(
                client_ip="1.2.3.4",
            )
            responses, called = await self._call_middleware(
                scope, enabled=True,
            )
            return responses, called

        try:
            responses, called = asyncio.get_event_loop(
            ).run_until_complete(run())
            # Fail-open: should pass through on Redis error
            assert called is True
            assert responses[0]["status"] == 200
        finally:
            patcher.stop()

    def test_non_http_request_passes_through(self):
        """Non-HTTP requests (websocket) pass through."""
        import asyncio

        old = os.environ.get("ENVIRONMENT", "")
        old_enabled = os.environ.get("IP_ALLOWLIST_ENABLED", "")
        os.environ["ENVIRONMENT"] = "production"
        os.environ["IP_ALLOWLIST_ENABLED"] = "true"

        try:
            from backend.app.middleware.ip_allowlist import (
                IPAllowlistMiddleware,
            )

            downstream_called = False

            async def app(scope, receive, send):
                nonlocal downstream_called
                downstream_called = True
                await send({"type": "websocket.accept"})

            middleware = IPAllowlistMiddleware(app)

            async def run():
                scope = {
                    "type": "websocket",
                    "path": "/ws",
                    "client": ("1.2.3.4", 12345),
                }
                responses = []

                async def receive():
                    return {"type": "websocket.connect"}

                async def send(msg):
                    responses.append(msg)

                await middleware(scope, receive, send)
                return downstream_called

            called = asyncio.get_event_loop().run_until_complete(
                run()
            )
            assert called is True
        finally:
            os.environ["ENVIRONMENT"] = old
            os.environ["IP_ALLOWLIST_ENABLED"] = old_enabled

    def test_x_forwarded_for_used(self):
        """X-Forwarded-For header is used for IP extraction."""
        import asyncio
        import unittest.mock as mock
        from backend.app.core import redis as redis_module

        mock_redis = mock.AsyncMock()
        mock_redis.get = mock.AsyncMock(
            return_value=json.dumps(
                ["10.0.0.0/8"]
            ).encode()
        )
        patcher = mock.patch.object(
            redis_module, "get_redis",
            mock.AsyncMock(return_value=mock_redis),
        )
        patcher.start()

        async def run():
            scope = self._make_scope(
                client_ip="1.2.3.4",  # direct IP is blocked
                headers=[
                    [b"x-forwarded-for", b"10.5.5.5"],
                ],
            )
            responses, called = await self._call_middleware(
                scope, enabled=True,
            )
            return responses, called

        try:
            responses, called = asyncio.get_event_loop(
            ).run_until_complete(run())
            assert called is True
        finally:
            patcher.stop()
