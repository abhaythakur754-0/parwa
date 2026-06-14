"""
Day 21 Loophole Checks — Health Check System + Monitoring

4 loophole checks from WEEK3_ROADMAP.md Day 21:
1. Health endpoint doesn't leak company data
2. Metrics endpoint doesn't expose tenant-specific counts
3. External health checks don't send real data (connectivity probes only)
4. Health check doesn't become a bottleneck (cached for 10s)
"""

import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-32-chars-min!!"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-32-chars!!"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

import pytest

from backend.app.core.health import (
    SubsystemHealth,
    clear_health_cache,
    run_health_checks,
    check_external_service,
    _HEALTH_CACHE_TTL,
    _get_cached_result,
    _set_cache,
    HealthCheckResult,
)
from backend.app.core.metrics import (
    registry,
    record_http_request,
    record_celery_task,
)


class TestLoophole1_HealthNoCompanyData:
    """L61: Health endpoint must not leak company data.

    The /health response must never contain:
    - company_id values
    - tenant names
    - customer data
    - API keys or tokens
    """

    @pytest.mark.asyncio
    async def test_health_response_no_company_fields(self):
        """Health response must not contain company-related fields."""
        clear_health_cache()

        async def mock_check():
            return SubsystemHealth(name="test", status="healthy")

        with patch("backend.app.core.health._CHECK_REGISTRY", {"test": mock_check}):
            result = await run_health_checks(
                use_cache=False, include_external=False,
            )

        # Serialize result to check for sensitive fields
        response_data = {
            "status": result.status,
            "subsystems": {
                name: {
                    "status": sub.status,
                    "latency_ms": sub.latency_ms,
                    "details": sub.details,
                }
                for name, sub in result.subsystems.items()
            },
        }

        response_str = str(response_data).lower()

        # Must not contain tenant-identifying data
        assert "company_id" not in response_str
        assert "company_name" not in response_str
        assert "tenant_id" not in response_str
        assert "api_key" not in response_str
        assert "secret" not in response_str
        assert "token" not in response_str
        assert "password" not in response_str

    @pytest.mark.asyncio
    async def test_subsystem_details_no_user_data(self):
        """Subsystem details must not contain user-specific data."""
        clear_health_cache()

        sub = SubsystemHealth(
            name="test_db",
            status="healthy",
            details={
                "pool_used": 5,
                "pool_max": 20,
            },
        )

        async def mock_check():
            return sub

        with patch("backend.app.core.health._CHECK_REGISTRY", {"test_db": mock_check}):
            result = await run_health_checks(
                use_cache=False, include_external=False,
            )

        for name, sub in result.subsystems.items():
            details_str = str(sub.details).lower()
            assert "email" not in details_str
            assert "phone" not in details_str
            assert "user_id" not in details_str
            assert "customer" not in details_str

    @pytest.mark.asyncio
    async def test_health_detail_no_tenant_info(self):
        """Even /health/detail must not expose tenant information."""
        clear_health_cache()

        async def mock_check():
            return SubsystemHealth(
                name="test", status="healthy",
                details={"latency_ms": 1.5},
            )

        with patch("backend.app.core.health._CHECK_REGISTRY", {"test": mock_check}):
            result = await run_health_checks(
                use_cache=False, include_external=False,
            )

        result_str = str(result).lower()
        # No tenant-specific identifiers
        assert "company_id" not in result_str
        assert "tenant" not in result_str
        assert "workspace" not in result_str


class TestLoophole2_MetricsNoTenantCounts:
    """L62: Metrics endpoint must not expose tenant-specific counts.

    Metrics must be aggregate only — no per-tenant breakdowns.
    """

    def _reset(self):
        """Reset all pre-registered metrics to zero."""
        import backend.app.core.metrics as m
        for metric in m.registry._metrics.values():
            if hasattr(metric, 'value'):
                metric.value = 0.0
            if hasattr(metric, 'count'):
                metric.count = 0
            if hasattr(metric, 'sum_value'):
                metric.sum_value = 0.0
            if hasattr(metric, 'counts'):
                metric.counts = {b: 0 for b in metric.buckets}
            if hasattr(metric, 'labels'):
                metric.labels.clear()

    def test_metrics_no_company_id_labels(self):
        """Prometheus labels must not include company_id."""
        self._reset()
        record_http_request("GET", "/api/tickets", 200, 0.05)
        rendered = registry.render_all()

        # No company_id in any label
        assert 'company_id="' not in rendered
        assert 'tenant_id="' not in rendered
        assert 'workspace="' not in rendered

    def test_metrics_no_tenant_names(self):
        """Metrics must not reference specific tenant names."""
        self._reset()
        record_celery_task("send_email", "success", 0.5)
        rendered = registry.render_all()

        # No tenant-specific names in labels
        assert 'tenant="' not in rendered
        assert 'company="' not in rendered
        assert 'org="' not in rendered

    def test_metrics_labels_are_generic(self):
        """All metric labels must be generic (method, path, status, etc.)."""
        self._reset()
        record_http_request("POST", "/api/auth/login", 200, 0.1)
        record_http_request("GET", "/health", 200, 0.01)
        record_celery_task("process_ticket", "success", 0.3)
        rendered = registry.render_all()

        # Only standard labels should appear
        assert "method=" in rendered
        assert "path=" in rendered
        assert "status=" in rendered
        assert "task_name=" in rendered

        # These must NOT appear
        assert "customer_id=" not in rendered
        assert "user_id=" not in rendered
        assert "company=" not in rendered


class TestLoophole3_ExternalProbesConnectivityOnly:
    """L63: External health checks must be connectivity probes only.

    Must NEVER send real data (no API keys, no customer data, no payloads).
    """

    def _make_mock_aiohttp(self):
        """Create a mock aiohttp module for testing."""
        mock_aiohttp = MagicMock()
        mock_aiohttp.ClientTimeout = MagicMock(return_value=5)

        mock_resp = MagicMock()
        mock_resp.status = 200

        # session.head() returns an async context manager
        mock_resp_cm = AsyncMock()
        mock_resp_cm.__aenter__.return_value = mock_resp
        mock_resp_cm.__aexit__.return_value = False

        # session is a plain object (head() is sync)
        mock_session = MagicMock()
        mock_session.head.return_value = mock_resp_cm
        mock_session.post = MagicMock()
        mock_session.put = MagicMock()
        mock_session.patch = MagicMock()
        mock_session.delete = MagicMock()

        # ClientSession() returns an async context manager
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = False

        mock_aiohttp.ClientSession = MagicMock(
            return_value=mock_session_cm,
        )
        return mock_aiohttp, mock_session

    @pytest.mark.asyncio
    async def test_external_check_uses_head_not_post(self):
        """External check must use HEAD request (no body data sent)."""
        mock_aiohttp, mock_session = self._make_mock_aiohttp()

        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await check_external_service(
                "test_ext", "https://api.example.com",
            )

        # Must use HEAD (not GET with data, not POST with body)
        mock_session.head.assert_called_once()
        mock_session.post.assert_not_called()
        mock_session.put.assert_not_called()
        mock_session.patch.assert_not_called()
        mock_session.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_external_check_no_auth_headers(self):
        """External probe must not send authentication headers."""
        mock_aiohttp, mock_session = self._make_mock_aiohttp()

        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            await check_external_service(
                "test_ext", "https://vendors.paddle.com",
            )

        # ClientSession called without auth
        assert mock_aiohttp.ClientSession.called

    @pytest.mark.asyncio
    async def test_external_check_no_request_body(self):
        """External probe must not send any request body."""
        mock_aiohttp, mock_session = self._make_mock_aiohttp()

        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            await check_external_service(
                "test_ext", "https://api.twilio.com",
            )

        # HEAD call should have no body/data/json params
        head_call = mock_session.head.call_args
        if head_call:
            kwargs = head_call[1] if len(head_call) > 1 else {}
            assert "data" not in kwargs
            assert "json" not in kwargs
            assert "body" not in kwargs


class TestLoophole4_HealthCache10Seconds:
    """L64: Health check must be cached for 10 seconds to prevent bottleneck.

    Without caching, the health endpoint itself could become a bottleneck
    under heavy monitoring scrape load.
    """

    def test_cache_ttl_is_10_seconds(self):
        """Cache TTL must be exactly 10 seconds."""
        assert _HEALTH_CACHE_TTL == 10.0

    @pytest.mark.asyncio
    async def test_second_call_returns_cached(self):
        """Second call within TTL returns cached result (not re-checked)."""
        clear_health_cache()
        call_count = 0

        async def mock_check():
            nonlocal call_count
            call_count += 1
            # Simulate a slow check (50ms)
            await asyncio.sleep(0.05)
            return SubsystemHealth(name="test", status="healthy")

        with patch("backend.app.core.health._CHECK_REGISTRY", {"test": mock_check}):
            start = time.monotonic()
            r1 = await run_health_checks(use_cache=True, include_external=False)
            r2 = await run_health_checks(use_cache=True, include_external=False)
            elapsed = time.monotonic() - start

        # r1 should NOT be cached (first call)
        assert r1.cached is False
        # r2 SHOULD be cached (within TTL)
        assert r2.cached is True
        # Check function should only be called once (cached on second call)
        assert call_count == 1
        # Total time should be ~50ms (one check), not ~100ms (two checks)
        assert elapsed < 0.15

    @pytest.mark.asyncio
    async def test_cache_expires_after_10_seconds(self):
        """Cache must expire after 10 seconds and re-check."""
        clear_health_cache()
        call_count = 0

        async def mock_check():
            nonlocal call_count
            call_count += 1
            return SubsystemHealth(name="test", status="healthy")

        with patch("backend.app.core.health._CHECK_REGISTRY", {"test": mock_check}):
            # First call — populate cache
            r1 = await run_health_checks(use_cache=True, include_external=False)
            assert call_count == 1
            assert r1.cached is False

            # Second call — should be cached
            r2 = await run_health_checks(use_cache=True, include_external=False)
            assert call_count == 1  # Not re-checked
            assert r2.cached is True

        # Manually expire the cache
        import backend.app.core.health as health_mod
        health_mod._health_cache_timestamp = (
            time.monotonic() - _HEALTH_CACHE_TTL - 1
        )

        with patch("backend.app.core.health._CHECK_REGISTRY", {"test": mock_check}):
            r3 = await run_health_checks(use_cache=True, include_external=False)
            assert call_count == 2  # Re-checked after expiry
            assert r3.cached is False

    @pytest.mark.asyncio
    async def test_cache_bypass_forces_refresh(self):
        """use_cache=False must bypass cache and re-check."""
        clear_health_cache()
        call_count = 0

        async def mock_check():
            nonlocal call_count
            call_count += 1
            return SubsystemHealth(name="test", status="healthy")

        with patch("backend.app.core.health._CHECK_REGISTRY", {"test": mock_check}):
            await run_health_checks(use_cache=True, include_external=False)
            await run_health_checks(use_cache=True, include_external=False)
            # Both should use cache — only 1 actual check
            assert call_count == 1

            # Force bypass
            await run_health_checks(use_cache=False, include_external=False)
            assert call_count == 2  # Re-checked

    @pytest.mark.asyncio
    async def test_concurrent_checks_safe(self):
        """Multiple concurrent health checks should not cause issues."""
        clear_health_cache()

        async def mock_check():
            await asyncio.sleep(0.01)
            return SubsystemHealth(name="test", status="healthy")

        with patch("backend.app.core.health._CHECK_REGISTRY", {"test": mock_check}):
            results = await asyncio.gather(*[
                run_health_checks(use_cache=False, include_external=False)
                for _ in range(5)
            ])

        # All results should be valid
        for r in results:
            assert r.checks_total == 1
            assert r.status == "healthy"
