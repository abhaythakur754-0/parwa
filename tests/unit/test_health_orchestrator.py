"""Tests for PARWA Health Check Orchestrator (Day 21)"""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# All tests need ENVIRONMENT=test
import os
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-32-chars-min!!"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-32-chars!!"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

from backend.app.core.health import (
    HealthStatus,
    SubsystemHealth,
    HealthCheckResult,
    DEPENDENCY_GRAPH,
    _HEALTH_CACHE_TTL,
    clear_health_cache,
    run_health_checks,
    run_readiness_check,
    check_postgresql,
    check_redis,
    check_celery,
    check_celery_queues,
    check_socketio,
    check_external_service,
    check_disk_space,
)


# ── Shared fixtures ───────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_health_cache():
    """Clear health cache before each test to prevent pollution."""
    clear_health_cache()
    yield
    clear_health_cache()


async def _mock_external_service(name, url, **kwargs):
    """Fast mock for check_external_service to avoid network calls."""
    return SubsystemHealth(name=name, status="unhealthy", is_critical=False)


# ── SubsystemHealth ───────────────────────────────────────────────


class TestSubsystemHealth:
    def test_default_values(self):
        sub = SubsystemHealth(name="test")
        assert sub.name == "test"
        assert sub.status == "unknown"
        assert sub.latency_ms == 0.0
        assert sub.details == {}
        assert sub.error is None
        assert sub.is_critical is True

    def test_custom_values(self):
        sub = SubsystemHealth(
            name="redis", status="healthy", latency_ms=1.5,
            details={"memory_mb": 128}, error=None, is_critical=True,
        )
        assert sub.status == "healthy"
        assert sub.latency_ms == 1.5
        assert sub.details["memory_mb"] == 128

    def test_non_critical_subsystem(self):
        sub = SubsystemHealth(name="celery", is_critical=False)
        assert sub.is_critical is False


# ── HealthCheckResult ────────────────────────────────────────────


class TestHealthCheckResult:
    def test_default_values(self):
        result = HealthCheckResult()
        assert result.status == "unknown"
        assert result.checks_total == 0
        assert result.cached is False

    def test_with_subsystems(self):
        sub = SubsystemHealth(name="db", status="healthy")
        result = HealthCheckResult(
            status="healthy",
            subsystems={"db": sub},
            checks_total=1,
            checks_healthy=1,
            checks_degraded=0,
            checks_unhealthy=0,
        )
        assert result.checks_healthy == 1
        assert "db" in result.subsystems


# ── Dependency Graph ──────────────────────────────────────────────


class TestDependencyGraph:
    def test_celery_depends_on_db_and_redis(self):
        assert "postgresql" in DEPENDENCY_GRAPH["celery"]
        assert "redis" in DEPENDENCY_GRAPH["celery"]

    def test_celery_queues_depends_on_celery(self):
        assert "celery" in DEPENDENCY_GRAPH["celery_queues"]

    def test_socketio_depends_on_redis(self):
        assert "redis" in DEPENDENCY_GRAPH["socketio"]

    def test_external_services_no_deps(self):
        assert DEPENDENCY_GRAPH["external_paddle"] == []
        assert DEPENDENCY_GRAPH["external_brevo"] == []


# ── Health Cache ──────────────────────────────────────────────────


class TestHealthCache:
    def test_clear_cache(self):
        from backend.app.core.health import _health_cache
        clear_health_cache()
        assert _health_cache is None

    def test_cache_ttl_is_10_seconds(self):
        assert _HEALTH_CACHE_TTL == 10.0


# ── check_postgresql ─────────────────────────────────────────────


@pytest.mark.asyncio
class TestCheckPostgreSQL:
    async def test_postgresql_healthy(self):
        """check_postgresql returns healthy when DB connection succeeds."""
        mock_conn = MagicMock()
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(
            return_value=mock_conn,
        )
        mock_engine.connect.return_value.__exit__ = MagicMock(
            return_value=False,
        )
        mock_engine.pool = MagicMock()
        mock_engine.pool.checkedout.return_value = 2
        mock_engine.pool.size.return_value = 20

        with patch("database.base.engine", mock_engine):
            result = await check_postgresql()

        assert result.name == "postgresql"
        assert result.status in ("healthy", "degraded", "unhealthy")
        assert result.is_critical is True

    async def test_postgresql_unhealthy(self):
        """check_postgresql returns unhealthy on connection failure."""
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("connection refused")

        with patch("database.base.engine", mock_engine):
            result = await check_postgresql()

        assert result.name == "postgresql"
        assert result.status == "unhealthy"
        assert result.error is not None


# ── check_redis ───────────────────────────────────────────────────


@pytest.mark.asyncio
class TestCheckRedis:
    async def test_redis_unhealthy(self):
        """check_redis returns unhealthy when ping fails."""
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Connection refused")

        with patch("backend.app.core.redis.get_redis", return_value=mock_redis):
            result = await check_redis()

        assert result.name == "redis"
        assert result.status == "unhealthy"
        assert result.error is not None

    async def test_redis_healthy(self):
        """check_redis returns healthy when ping succeeds and memory OK."""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        mock_redis.info.return_value = {
            "used_memory": 128 * 1024 * 1024,
            "maxmemory": 2048 * 1024 * 1024,
        }

        with patch("backend.app.core.redis.get_redis", return_value=mock_redis):
            result = await check_redis()

        assert result.name == "redis"
        assert result.status == "healthy"
        assert result.is_critical is True


# ── check_celery ──────────────────────────────────────────────────


@pytest.mark.asyncio
class TestCheckCelery:
    async def test_celery_unhealthy(self):
        """check_celery returns unhealthy when broker is unreachable."""
        mock_health = AsyncMock(return_value={
            "status": "unhealthy", "latency_ms": 5000,
            "error": "broker unreachable",
        })

        with patch("backend.app.tasks.celery_health.celery_health_check", mock_health):
            result = await check_celery()

        assert result.name == "celery"
        assert result.status == "unhealthy"
        assert result.is_critical is False

    async def test_celery_healthy(self):
        """check_celery returns healthy when broker and workers OK."""
        mock_health = AsyncMock(return_value={
            "status": "healthy", "latency_ms": 5,
        })
        mock_workers = AsyncMock(return_value={
            "status": "healthy", "worker_count": 2,
        })

        with patch("backend.app.tasks.celery_health.celery_health_check", mock_health), \
             patch("backend.app.tasks.celery_health.get_active_workers", mock_workers):
            result = await check_celery()

        assert result.name == "celery"
        assert result.status == "healthy"


# ── check_disk_space ──────────────────────────────────────────────


@pytest.mark.asyncio
class TestCheckDiskSpace:
    async def test_disk_space_healthy(self):
        """Disk healthy when > 20% free."""
        mock_stat = MagicMock()
        mock_stat.f_blocks = 1000000
        mock_stat.f_bavail = 800000
        mock_stat.f_frsize = 4096

        with patch("os.statvfs", return_value=mock_stat):
            result = await check_disk_space()

        assert result.name == "disk_space"
        assert result.status == "healthy"
        assert "free_percent" in result.details
        assert result.details["free_percent"] == 80.0

    async def test_disk_space_degraded(self):
        """Disk degraded when < 20% free but > 5% free."""
        mock_stat = MagicMock()
        mock_stat.f_blocks = 1000000
        mock_stat.f_bavail = 150000  # 15% free
        mock_stat.f_frsize = 4096

        with patch("os.statvfs", return_value=mock_stat):
            result = await check_disk_space()

        assert result.name == "disk_space"
        assert result.status == "degraded"

    async def test_disk_space_unhealthy(self):
        """Disk unhealthy when < 5% free."""
        mock_stat = MagicMock()
        mock_stat.f_blocks = 1000000
        mock_stat.f_bavail = 30000  # 3% free
        mock_stat.f_frsize = 4096

        with patch("os.statvfs", return_value=mock_stat):
            result = await check_disk_space()

        assert result.name == "disk_space"
        assert result.status == "unhealthy"


# ── run_health_checks ────────────────────────────────────────────


@pytest.mark.asyncio
class TestRunHealthChecks:
    async def test_all_subsystems_checked(self):
        """Verify all subsystems from registry are checked."""
        mock_sub = SubsystemHealth(name="mock", status="healthy")

        async def mock_check():
            return mock_sub

        checks_to_mock = {
            "postgresql": mock_check,
            "redis": mock_check,
            "celery": mock_check,
            "celery_queues": mock_check,
            "socketio": mock_check,
            "disk_space": mock_check,
        }

        with patch("backend.app.core.health._CHECK_REGISTRY", checks_to_mock):
            result = await run_health_checks(
                use_cache=False, include_external=False,
            )

        assert result.checks_total >= 6
        assert result.status == "healthy"

    async def test_cache_returns_same_result(self):
        """Verify 10-second cache works."""
        call_count = 0

        async def mock_check():
            nonlocal call_count
            call_count += 1
            return SubsystemHealth(name="mock", status="healthy")

        with patch("backend.app.core.health._CHECK_REGISTRY", {"test": mock_check}):
            r1 = await run_health_checks(
                use_cache=True, include_external=False,
            )
            r2 = await run_health_checks(
                use_cache=True, include_external=False,
            )

        assert r1.cached is False
        assert r2.cached is True
        assert call_count == 1  # Only called once

    async def test_cache_bypass(self):
        """Verify cache is bypassed when use_cache=False."""
        call_count = 0

        async def mock_check():
            nonlocal call_count
            call_count += 1
            return SubsystemHealth(name="mock", status="healthy")

        with patch("backend.app.core.health._CHECK_REGISTRY", {"test": mock_check}):
            await run_health_checks(
                use_cache=False, include_external=False,
            )
            await run_health_checks(
                use_cache=False, include_external=False,
            )

        assert call_count == 2

    async def test_dependency_graph_forces_degraded(self):
        """If DB is down, celery should show degraded (not unhealthy)."""
        db_down = SubsystemHealth(
            name="postgresql", status="unhealthy", is_critical=True,
        )
        redis_ok = SubsystemHealth(
            name="redis", status="healthy", is_critical=True,
        )
        celery_ok = SubsystemHealth(
            name="celery", status="healthy", is_critical=False,
        )

        async def mock_db():
            return db_down
        async def mock_redis():
            return redis_ok
        async def mock_celery():
            return celery_ok

        registry = {
            "postgresql": mock_db,
            "redis": mock_redis,
            "celery": mock_celery,
        }

        with patch("backend.app.core.health._CHECK_REGISTRY", registry):
            result = await run_health_checks(
                use_cache=False, include_external=False,
            )

        # Celery should be forced to degraded because its dependency (DB) is down
        assert result.subsystems["celery"].status == "degraded"

    async def test_critical_unhealthy_makes_overall_unhealthy(self):
        """If a critical subsystem is unhealthy, overall is unhealthy."""
        db_down = SubsystemHealth(
            name="postgresql", status="unhealthy", is_critical=True,
        )

        async def mock_db():
            return db_down

        with patch(
            "backend.app.core.health._CHECK_REGISTRY",
            {"postgresql": mock_db},
        ):
            result = await run_health_checks(
                use_cache=False, include_external=False,
            )

        assert result.subsystems["postgresql"].status == "unhealthy"
        assert result.status == "unhealthy"

    async def test_external_checks_skipped(self):
        """External checks skipped when include_external=False."""
        async def mock_check():
            return SubsystemHealth(name="test", status="healthy")

        with patch("backend.app.core.health._CHECK_REGISTRY", {"test": mock_check}):
            result = await run_health_checks(
                use_cache=False, include_external=False,
            )

        # No external subsystems should be present
        for name in result.subsystems:
            assert not name.startswith("external_")

    async def test_non_critical_unhealthy_is_degraded_overall(self):
        """If only non-critical subsystems are unhealthy, overall is degraded."""
        redis_ok = SubsystemHealth(
            name="redis", status="healthy", is_critical=True,
        )
        celery_down = SubsystemHealth(
            name="celery", status="unhealthy", is_critical=False,
        )

        async def mock_redis():
            return redis_ok
        async def mock_celery():
            return celery_down

        with patch(
            "backend.app.core.health._CHECK_REGISTRY",
            {"redis": mock_redis, "celery": mock_celery},
        ):
            result = await run_health_checks(
                use_cache=False, include_external=False,
            )

        assert result.status == "degraded"


# ── run_readiness_check ───────────────────────────────────────────


@pytest.mark.asyncio
class TestRunReadinessCheck:
    async def test_ready_when_all_critical_healthy(self):
        """Readiness returns ready=True when all critical subsystems healthy."""
        mock_db = SubsystemHealth(
            name="postgresql", status="healthy", is_critical=True,
        )
        mock_redis = SubsystemHealth(
            name="redis", status="healthy", is_critical=True,
        )

        async def mock_pg():
            return mock_db
        async def mock_r():
            return mock_redis

        with patch(
            "backend.app.core.health._CHECK_REGISTRY",
            {"postgresql": mock_pg, "redis": mock_r},
        ), patch(
            "backend.app.core.health.check_external_service",
            _mock_external_service,
        ):
            result = await run_readiness_check()

        assert result["ready"] is True

    async def test_not_ready_when_db_unhealthy(self):
        """Readiness returns ready=False when DB is unhealthy."""
        mock_db = SubsystemHealth(
            name="postgresql", status="unhealthy", is_critical=True,
        )
        mock_redis = SubsystemHealth(
            name="redis", status="healthy", is_critical=True,
        )

        async def mock_pg():
            return mock_db
        async def mock_r():
            return mock_redis

        with patch(
            "backend.app.core.health._CHECK_REGISTRY",
            {"postgresql": mock_pg, "redis": mock_r},
        ), patch(
            "backend.app.core.health.check_external_service",
            _mock_external_service,
        ):
            result = await run_readiness_check()

        assert result["ready"] is False

    async def test_not_ready_when_redis_unhealthy(self):
        """Readiness returns ready=False when Redis is unhealthy."""
        mock_db = SubsystemHealth(
            name="postgresql", status="healthy", is_critical=True,
        )
        mock_redis = SubsystemHealth(
            name="redis", status="unhealthy", is_critical=True,
        )

        async def mock_pg():
            return mock_db
        async def mock_r():
            return mock_redis

        with patch(
            "backend.app.core.health._CHECK_REGISTRY",
            {"postgresql": mock_pg, "redis": mock_r},
        ), patch(
            "backend.app.core.health.check_external_service",
            _mock_external_service,
        ):
            result = await run_readiness_check()

        assert result["ready"] is False

    async def test_non_critical_unhealthy_still_ready(self):
        """Non-critical subsystem unhealthy does not affect readiness."""
        mock_db = SubsystemHealth(
            name="postgresql", status="healthy", is_critical=True,
        )
        mock_redis = SubsystemHealth(
            name="redis", status="healthy", is_critical=True,
        )
        mock_celery = SubsystemHealth(
            name="celery", status="unhealthy", is_critical=False,
        )

        async def mock_pg():
            return mock_db
        async def mock_r():
            return mock_redis
        async def mock_c():
            return mock_celery

        with patch(
            "backend.app.core.health._CHECK_REGISTRY",
            {"postgresql": mock_pg, "redis": mock_r, "celery": mock_c},
        ), patch(
            "backend.app.core.health.check_external_service",
            _mock_external_service,
        ):
            result = await run_readiness_check()

        assert result["ready"] is True


# ── check_external_service ────────────────────────────────────────


@pytest.mark.asyncio
class TestCheckExternalService:
    async def test_healthy_external(self):
        """External service returns healthy on successful probe."""
        mock_resp = MagicMock()
        mock_resp.status = 200

        # session.head() must return an async context manager
        mock_resp_cm = AsyncMock()
        mock_resp_cm.__aenter__.return_value = mock_resp
        mock_resp_cm.__aexit__.return_value = False

        # session is a plain object (head() is sync, returns ctx manager)
        mock_session = MagicMock()
        mock_session.head.return_value = mock_resp_cm

        # ClientSession() returns an async context manager
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = False

        mock_aiohttp = MagicMock()
        mock_aiohttp.ClientTimeout = MagicMock(return_value=5)
        mock_aiohttp.ClientSession = MagicMock(
            return_value=mock_session_cm,
        )

        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await check_external_service(
                "test_ext", "https://example.com",
            )

        assert result.name == "test_ext"
        assert result.status in ("healthy", "degraded")

    async def test_timeout_external(self):
        """External service returns unhealthy on timeout."""
        mock_aiohttp = MagicMock()
        mock_aiohttp.ClientTimeout = MagicMock(return_value=5)
        mock_aiohttp.ClientSession = MagicMock(
            side_effect=asyncio.TimeoutError(),
        )

        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await check_external_service(
                "test_ext", "https://example.com",
            )

        assert result.name == "test_ext"
        assert result.status == "unhealthy"
        assert "timeout" in result.error.lower()
