"""
Tests for Data Freshness Service (SG-34) — Data Freshness for RAG

Covers: freshness status enum, staleness config, check results,
cache/signal/context/RAG freshness checks, invalidation, update
recording, batch checks, freshness reports, convenience predicates.

Target: 80+ tests
"""

import json
import time
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Module-level stubs — populated by the autouse fixture below.
# These satisfy pyflakes F821 checks; the real imports happen
# inside the fixture after the logger is mocked.
DataFreshnessService = None  # type: ignore[assignment,misc]
FreshnessCheckResult = None  # type: ignore[assignment,misc]
FreshnessStatus = None  # type: ignore[assignment,misc]
StalenessConfig = None  # type: ignore[assignment,misc]


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — import source modules with mocked logger
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("app.logger.get_logger", return_value=MagicMock()):
        from app.services.data_freshness_service import (
            DataFreshnessService,
            FreshnessCheckResult,
            FreshnessStatus,
            StalenessConfig,
        )

        globals().update(
            {
                "DataFreshnessService": DataFreshnessService,
                "FreshnessCheckResult": FreshnessCheckResult,
                "FreshnessStatus": FreshnessStatus,
                "StalenessConfig": StalenessConfig,
            }
        )


# ═══════════════════════════════════════════════════════════════════════
# Helper utilities
# ═══════════════════════════════════════════════════════════════════════


def _make_key(company_id: str, *parts: str) -> str:
    """Mirror the real make_key: parwa:{company_id}:{parts...}."""
    return f"parwa:{company_id}:" + ":".join(parts)


def _freshness_payload(seconds_ago: float = 0) -> str:
    """Create a freshness JSON payload with a given age."""
    dt = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    return json.dumps({"updated_at": dt.isoformat()})


def _setup_redis(pipe_results=None, scan_results=None):
    """Build a mock Redis client with an async pipeline."""
    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    if pipe_results is not None:
        mock_pipe.execute = AsyncMock(return_value=pipe_results)
    else:
        mock_pipe.execute = AsyncMock(return_value=[None, -2])
    if scan_results is not None:
        mock_redis.scan = AsyncMock(side_effect=scan_results)
    return mock_redis, mock_pipe


def _redis_patches(mock_redis, *, track_keys=False):
    """Return (ExitStack, optional called_keys list).

    Usage::

        stack, keys = _redis_patches(mock, track_keys=True)
        with stack:
            result = await svc.method(...)
        assert "c1" in keys
    """
    stack = ExitStack()
    stack.enter_context(
        patch(
            "app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ),
    )
    called_keys: list = []
    if track_keys:

        def _track(*args):
            k = _make_key(*args)
            called_keys.append(k)
            return k

        stack.enter_context(
            patch("app.core.redis.make_key", side_effect=_track),
        )
    else:
        stack.enter_context(
            patch("app.core.redis.make_key", side_effect=_make_key),
        )
    return stack, called_keys


# ═══════════════════════════════════════════════════════════════════════
# 1. TestFreshnessStatus (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestFreshnessStatus:

    def test_fresh_value(self):
        assert FreshnessStatus.FRESH == "fresh"

    def test_stale_value(self):
        assert FreshnessStatus.STALE == "stale"

    def test_expired_value(self):
        assert FreshnessStatus.EXPIRED == "expired"

    def test_unknown_value(self):
        assert FreshnessStatus.UNKNOWN == "unknown"


# ═══════════════════════════════════════════════════════════════════════
# 2. TestStalenessConfig (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestStalenessConfig:

    def test_default_signal_max_age(self):
        c = StalenessConfig()
        assert c.signal_max_age_seconds == 300.0

    def test_default_context_max_age(self):
        c = StalenessConfig()
        assert c.context_max_age_seconds == 1800.0

    def test_default_rag_cache_max_age(self):
        c = StalenessConfig()
        assert c.rag_cache_max_age_seconds == 120.0

    def test_default_embedding_max_age(self):
        c = StalenessConfig()
        assert c.embedding_max_age_seconds == 3600.0

    def test_custom_config_overrides_defaults(self):
        c = StalenessConfig(signal_max_age_seconds=600.0)
        assert c.signal_max_age_seconds == 600.0
        assert c.context_max_age_seconds == 1800.0

    def test_all_values_positive(self):
        c = StalenessConfig()
        assert c.signal_max_age_seconds > 0
        assert c.context_max_age_seconds > 0
        assert c.rag_cache_max_age_seconds > 0
        assert c.embedding_max_age_seconds > 0
        assert c.kb_document_max_age_seconds > 0

    def test_custom_config_preserves_unset_values(self):
        c = StalenessConfig(context_max_age_seconds=900.0)
        assert c.signal_max_age_seconds == 300.0
        assert c.context_max_age_seconds == 900.0
        assert c.rag_cache_max_age_seconds == 120.0

    def test_values_are_floats(self):
        c = StalenessConfig()
        assert isinstance(c.signal_max_age_seconds, float)
        assert isinstance(c.context_max_age_seconds, float)
        assert isinstance(c.rag_cache_max_age_seconds, float)
        assert isinstance(c.embedding_max_age_seconds, float)


# ═══════════════════════════════════════════════════════════════════════
# 3. TestFreshnessCheckResult (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestFreshnessCheckResult:

    def test_default_metadata_is_empty_dict(self):
        r = FreshnessCheckResult(
            FreshnessStatus.FRESH,
            10.0,
            300.0,
            True,
            "2024-01-01T00:00:00+00:00",
            "signal",
        )
        assert r.metadata == {}

    def test_fresh_status_is_fresh_true(self):
        r = FreshnessCheckResult(
            FreshnessStatus.FRESH,
            10.0,
            300.0,
            True,
            "2024-01-01",
            "signal",
        )
        assert r.is_fresh is True
        assert r.status == FreshnessStatus.FRESH

    def test_stale_status_is_fresh_false(self):
        r = FreshnessCheckResult(
            FreshnessStatus.STALE,
            400.0,
            300.0,
            False,
            "2024-01-01",
            "signal",
        )
        assert r.is_fresh is False

    def test_expired_status_is_fresh_false(self):
        r = FreshnessCheckResult(
            FreshnessStatus.EXPIRED,
            500.0,
            300.0,
            False,
            "2024-01-01",
            "signal",
        )
        assert r.is_fresh is False

    def test_unknown_status_is_fresh_false(self):
        r = FreshnessCheckResult(
            FreshnessStatus.UNKNOWN,
            0.0,
            300.0,
            False,
            None,
            "signal",
        )
        assert r.is_fresh is False
        assert r.last_updated is None

    def test_age_seconds_stored(self):
        r = FreshnessCheckResult(
            FreshnessStatus.FRESH,
            42.5,
            300.0,
            True,
            "2024-01-01",
            "signal",
        )
        assert r.age_seconds == 42.5

    def test_max_age_seconds_stored(self):
        r = FreshnessCheckResult(
            FreshnessStatus.STALE,
            400.0,
            300.0,
            False,
            "2024-01-01",
            "context",
        )
        assert r.max_age_seconds == 300.0

    def test_source_and_metadata_set(self):
        r = FreshnessCheckResult(
            FreshnessStatus.FRESH,
            10.0,
            120.0,
            True,
            "2024-01-01",
            "rag_cache",
            metadata={"method": "expiretime", "entity_type": "rag_cache"},
        )
        assert r.source == "rag_cache"
        assert r.metadata["method"] == "expiretime"


# ═══════════════════════════════════════════════════════════════════════
# 4. TestCheckCacheFreshness (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCheckCacheFreshness:

    def setup_method(self):
        self.svc = DataFreshnessService()

    @pytest.mark.asyncio
    async def test_fresh_cache_entry(self):
        """Positive TTL → FRESH."""
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 60],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_cache_freshness("my_key", "c1")
        assert result.status == FreshnessStatus.FRESH
        assert result.is_fresh is True

    @pytest.mark.asyncio
    async def test_stale_cache_entry(self):
        """Fallback timestamp between max_age and 1.5×max_age → STALE."""
        # rag_cache max_age=120; stale when 120 < age <= 180
        payload = _freshness_payload(seconds_ago=150)
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, None],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_cache_freshness("my_key", "c1")
        assert result.status == FreshnessStatus.STALE
        assert result.is_fresh is False

    @pytest.mark.asyncio
    async def test_expired_cache_entry(self):
        """Non-existent key (expiretime=-2) → EXPIRED."""
        mock_redis, _ = _setup_redis(pipe_results=[None, -2])
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_cache_freshness("missing", "c1")
        assert result.status == FreshnessStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_non_existent_key_returns_expired(self):
        """Both json_val and expiretime indicate missing key."""
        mock_redis, _ = _setup_redis(pipe_results=[None, -2])
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_cache_freshness("ghost", "c1")
        assert result.status == FreshnessStatus.EXPIRED
        assert result.is_fresh is False
        assert result.last_updated is None

    @pytest.mark.asyncio
    async def test_redis_error_returns_unknown(self):
        """Redis failure → UNKNOWN (fail-open per BC-008)."""
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = Exception("connection lost")
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_cache_freshness("key1", "c1")
        assert result.status == FreshnessStatus.UNKNOWN
        assert result.is_fresh is False
        assert "error" in result.metadata

    @pytest.mark.asyncio
    async def test_custom_max_age_respected(self):
        """Custom rag_cache_max_age changes threshold."""
        svc = DataFreshnessService(
            config=StalenessConfig(rag_cache_max_age_seconds=600.0),
        )
        payload = _freshness_payload(seconds_ago=150)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 450],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await svc.check_cache_freshness("key1", "c1")
        assert result.max_age_seconds == 600.0
        assert result.is_fresh is True

    @pytest.mark.asyncio
    async def test_last_updated_extracted_from_json(self):
        """updated_at is extracted from the JSON payload."""
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 60],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_cache_freshness("key1", "c1")
        assert result.last_updated is not None
        assert "T" in result.last_updated

    @pytest.mark.asyncio
    async def test_company_isolation_in_key(self):
        """Company ID appears in the Redis freshness key."""
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 60],
        )
        stack, called_keys = _redis_patches(mock_redis, track_keys=True)
        with stack:
            await self.svc.check_cache_freshness("key1", "c1")
        assert any("c1" in k for k in called_keys)
        assert any("freshness" in k for k in called_keys)
        assert any("rag_cache" in k for k in called_keys)


# ═══════════════════════════════════════════════════════════════════════
# 5. TestCheckSignalFreshness (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCheckSignalFreshness:

    def setup_method(self):
        self.svc = DataFreshnessService()

    @pytest.mark.asyncio
    async def test_recent_signal_fresh(self):
        """Signal updated < 5 min ago → FRESH."""
        payload = _freshness_payload(seconds_ago=60)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 240],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_signal_freshness(
                "abc123",
                "c1",
                "sentiment",
            )
        assert result.status == FreshnessStatus.FRESH
        assert result.is_fresh is True

    @pytest.mark.asyncio
    async def test_old_signal_expired(self):
        """Signal updated > 5 min ago (fallback path) → EXPIRED."""
        # max_age=300, 1.5×=450; 600 > 450 → EXPIRED
        payload = _freshness_payload(seconds_ago=600)
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, None],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_signal_freshness(
                "abc123",
                "c1",
                "sentiment",
            )
        assert result.status == FreshnessStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_non_existent_signal(self):
        """Signal key missing → EXPIRED."""
        mock_redis, _ = _setup_redis(pipe_results=[None, -2])
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_signal_freshness(
                "missing",
                "c1",
                "sentiment",
            )
        assert result.status == FreshnessStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_redis_error_unknown(self):
        """Redis failure → UNKNOWN."""
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = Exception("timeout")
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_signal_freshness(
                "q1",
                "c1",
                "intent",
            )
        assert result.status == FreshnessStatus.UNKNOWN
        assert result.is_fresh is False

    @pytest.mark.asyncio
    async def test_company_and_variant_in_key(self):
        """Entity ID includes variant_type and query_hash."""
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 200],
        )
        stack, called_keys = _redis_patches(mock_redis, track_keys=True)
        with stack:
            await self.svc.check_signal_freshness(
                "qhash99",
                "compX",
                "sentiment",
            )
        assert any("sentiment" in k for k in called_keys)
        assert any("qhash99" in k for k in called_keys)

    @pytest.mark.asyncio
    async def test_query_hash_in_key(self):
        """Query hash is embedded in the entity ID."""
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 200],
        )
        stack, called_keys = _redis_patches(mock_redis, track_keys=True)
        with stack:
            await self.svc.check_signal_freshness(
                "my_hash",
                "c1",
                "intent",
            )
        assert any("my_hash" in k for k in called_keys)

    @pytest.mark.asyncio
    async def test_default_config_300s(self):
        """Default signal max_age is 300 seconds."""
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 200],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_signal_freshness(
                "h1",
                "c1",
                "v1",
            )
        assert result.max_age_seconds == 300.0

    @pytest.mark.asyncio
    async def test_custom_config_respected(self):
        """Custom signal_max_age overrides default 300s."""
        svc = DataFreshnessService(
            config=StalenessConfig(signal_max_age_seconds=60.0),
        )
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 50],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await svc.check_signal_freshness("h1", "c1", "v1")
        assert result.max_age_seconds == 60.0


# ═══════════════════════════════════════════════════════════════════════
# 6. TestCheckContextFreshness (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCheckContextFreshness:

    def setup_method(self):
        self.svc = DataFreshnessService()

    @pytest.mark.asyncio
    async def test_recent_context_fresh(self):
        """Context < 30 min → FRESH."""
        payload = _freshness_payload(seconds_ago=300)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 1500],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_context_freshness("conv1", "c1")
        assert result.status == FreshnessStatus.FRESH

    @pytest.mark.asyncio
    async def test_old_context_stale(self):
        """Context between 30-45 min (fallback) → STALE."""
        # max_age=1800; stale when 1800 < age <= 2700
        payload = _freshness_payload(seconds_ago=2000)
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, None],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_context_freshness("conv1", "c1")
        assert result.status == FreshnessStatus.STALE

    @pytest.mark.asyncio
    async def test_very_old_context_expired(self):
        """Context > 45 min (fallback) → EXPIRED."""
        # > 2700 seconds → EXPIRED
        payload = _freshness_payload(seconds_ago=3600)
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, None],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_context_freshness("conv1", "c1")
        assert result.status == FreshnessStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_non_existent_context(self):
        """Missing context → EXPIRED."""
        mock_redis, _ = _setup_redis(pipe_results=[None, -2])
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_context_freshness("ghost", "c1")
        assert result.status == FreshnessStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_conversation_id_in_key(self):
        """Conversation ID is the entity_id in the Redis key."""
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 1000],
        )
        stack, called_keys = _redis_patches(mock_redis, track_keys=True)
        with stack:
            await self.svc.check_context_freshness("conv_42", "c1")
        assert any("conv_42" in k for k in called_keys)
        assert any("context" in k for k in called_keys)

    @pytest.mark.asyncio
    async def test_custom_config(self):
        """Custom context_max_age overrides the default 1800s."""
        svc = DataFreshnessService(
            config=StalenessConfig(context_max_age_seconds=60.0),
        )
        payload = _freshness_payload(seconds_ago=30)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 30],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await svc.check_context_freshness("c1", "c1")
        assert result.max_age_seconds == 60.0
        assert result.is_fresh is True


# ═══════════════════════════════════════════════════════════════════════
# 7. TestCheckRAGFreshness (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCheckRAGFreshness:

    def setup_method(self):
        self.svc = DataFreshnessService()

    @pytest.mark.asyncio
    async def test_recent_rag_fresh(self):
        """RAG < 2 min → FRESH."""
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 100],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_rag_freshness(
                "what is refund?",
                "c1",
                "sentiment",
            )
        assert result.status == FreshnessStatus.FRESH

    @pytest.mark.asyncio
    async def test_old_rag_expired(self):
        """RAG > 2 min (fallback) → EXPIRED."""
        # max_age=120, 1.5×=180; 200 > 180 → EXPIRED
        payload = _freshness_payload(seconds_ago=200)
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, None],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_rag_freshness("query", "c1", "v1")
        assert result.status == FreshnessStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_non_existent_rag(self):
        """Missing RAG key → EXPIRED."""
        mock_redis, _ = _setup_redis(pipe_results=[None, -2])
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_rag_freshness("q", "c1", "v")
        assert result.status == FreshnessStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_redis_error_unknown(self):
        """Redis failure → UNKNOWN."""
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = Exception("down")
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_rag_freshness("q", "c1", "v")
        assert result.status == FreshnessStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_query_and_variant_in_key(self):
        """Query hash and variant_type appear in the entity ID."""
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 100],
        )
        stack, called_keys = _redis_patches(mock_redis, track_keys=True)
        with stack:
            await self.svc.check_rag_freshness(
                "hello world",
                "c1",
                "sentiment",
            )
        assert any("sentiment" in k for k in called_keys)
        assert any("rag:" in k for k in called_keys)

    @pytest.mark.asyncio
    async def test_default_120s_config(self):
        """Default RAG cache max_age is 120 seconds."""
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 100],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.check_rag_freshness("q", "c1", "v")
        assert result.max_age_seconds == 120.0


# ═══════════════════════════════════════════════════════════════════════
# 8. TestInvalidateCache (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestInvalidateCache:

    def setup_method(self):
        self.svc = DataFreshnessService()

    @pytest.mark.asyncio
    async def test_existing_key_returns_true(self):
        """Deleting an existing key returns True."""
        mock_redis, _ = _setup_redis(pipe_results=[1, 1])
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.invalidate_cache("key1", "c1")
        assert result is True

    @pytest.mark.asyncio
    async def test_non_existent_key_returns_false(self):
        """Deleting a non-existent key returns False."""
        mock_redis, _ = _setup_redis(pipe_results=[0, 0])
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.invalidate_cache("ghost", "c1")
        assert result is False

    @pytest.mark.asyncio
    async def test_redis_error_returns_false(self):
        """Redis failure → False (fail-open)."""
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = Exception("conn lost")
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.invalidate_cache("k", "c1")
        assert result is False

    @pytest.mark.asyncio
    async def test_company_isolation(self):
        """Company ID is present in the constructed Redis keys."""
        mock_redis, _ = _setup_redis(pipe_results=[1, 1])
        stack, called_keys = _redis_patches(mock_redis, track_keys=True)
        with stack:
            await self.svc.invalidate_cache("key1", "my_company")
        assert any("my_company" in k for k in called_keys)

    @pytest.mark.asyncio
    async def test_deletes_freshness_and_data_keys(self):
        """Pipeline deletes both the freshness key and the data key."""
        mock_redis, mock_pipe = _setup_redis(pipe_results=[1, 1])
        stack, _ = _redis_patches(mock_redis)
        with stack:
            await self.svc.invalidate_cache("key1", "c1")
        assert mock_pipe.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_boolean_type(self):
        """Return type is always bool."""
        mock_redis, _ = _setup_redis(pipe_results=[1, 0])
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.invalidate_cache("k", "c1")
        assert isinstance(result, bool)


# ═══════════════════════════════════════════════════════════════════════
# 9. TestInvalidateKBCaches (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestInvalidateKBCaches:

    def setup_method(self):
        self.svc = DataFreshnessService()

    @pytest.mark.asyncio
    async def test_single_document_invalidation(self):
        """Caches for a specific document are invalidated."""
        fk = _make_key("c1", "freshness", "rag_cache", "doc_rag")
        doc_payload = json.dumps(
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "document_id": "doc1",
            }
        )
        mock_redis = MagicMock()
        mock_redis.scan = AsyncMock(return_value=[0, [fk]])
        mock_pipe_get = MagicMock()
        mock_pipe_get.execute = AsyncMock(return_value=[doc_payload])
        mock_pipe_del = MagicMock()
        mock_pipe_del.execute = AsyncMock(return_value=[1, 1])
        mock_redis.pipeline.side_effect = [mock_pipe_get, mock_pipe_del]

        stack, _ = _redis_patches(mock_redis)
        with stack:
            count = await self.svc.invalidate_kb_caches("doc1", "c1")
        assert count >= 1

    @pytest.mark.asyncio
    async def test_multiple_keys_invalidated(self):
        """Multiple matching keys are all deleted."""
        fk1 = _make_key("c1", "freshness", "rag_cache", "rag1")
        fk2 = _make_key("c1", "freshness", "rag_cache", "rag2")
        doc_payload = json.dumps(
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "document_id": "shared_doc",
            }
        )
        mock_redis = MagicMock()
        mock_redis.scan = AsyncMock(return_value=[0, [fk1, fk2]])
        mock_pipe_get = MagicMock()
        mock_pipe_get.execute = AsyncMock(
            return_value=[doc_payload, doc_payload],
        )
        mock_pipe_del = MagicMock()
        mock_pipe_del.execute = AsyncMock(return_value=[1, 1, 1, 1])
        mock_redis.pipeline.side_effect = [mock_pipe_get, mock_pipe_del]

        stack, _ = _redis_patches(mock_redis)
        with stack:
            count = await self.svc.invalidate_kb_caches(
                "shared_doc",
                "c1",
            )
        assert count >= 2

    @pytest.mark.asyncio
    async def test_non_existent_document_returns_zero(self):
        """No matching documents → 0 keys invalidated."""
        fk = _make_key("c1", "freshness", "rag_cache", "rag1")
        other_payload = json.dumps(
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "document_id": "other_doc",
            }
        )
        mock_redis = MagicMock()
        mock_redis.scan = AsyncMock(return_value=[0, [fk]])
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[other_payload])
        mock_redis.pipeline.return_value = mock_pipe

        stack, _ = _redis_patches(mock_redis)
        with stack:
            count = await self.svc.invalidate_kb_caches(
                "nonexistent",
                "c1",
            )
        assert count == 0

    @pytest.mark.asyncio
    async def test_redis_error_returns_zero(self):
        """Redis SCAN failure → 0 (fail-open)."""
        mock_redis = MagicMock()
        mock_redis.scan = AsyncMock(
            side_effect=Exception("scan error"),
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            count = await self.svc.invalidate_kb_caches("doc1", "c1")
        assert count == 0

    @pytest.mark.asyncio
    async def test_returns_count_type(self):
        """Return type is int."""
        mock_redis = MagicMock()
        mock_redis.scan = AsyncMock(return_value=[0, []])
        stack, _ = _redis_patches(mock_redis)
        with stack:
            count = await self.svc.invalidate_kb_caches("doc1", "c1")
        assert isinstance(count, int)

    @pytest.mark.asyncio
    async def test_company_isolation(self):
        """SCAN pattern is scoped to the given company_id."""
        mock_redis = MagicMock()
        mock_redis.scan = AsyncMock(return_value=[0, []])
        with patch(
            "app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            with patch(
                "app.core.redis.make_key",
                side_effect=_make_key,
            ) as mk:
                await self.svc.invalidate_kb_caches(
                    "doc1",
                    "company_42",
                )
                call_args = mk.call_args[0]
                assert call_args[0] == "company_42"


# ═══════════════════════════════════════════════════════════════════════
# 10. TestRecordUpdate (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestRecordUpdate:

    def setup_method(self):
        self.svc = DataFreshnessService()

    @pytest.mark.asyncio
    async def test_records_timestamp_in_redis(self):
        """Stores a freshness payload in Redis via SET."""
        mock_redis, mock_pipe = _setup_redis()
        stack, _ = _redis_patches(mock_redis)
        with stack:
            await self.svc.record_update("signal", "sig1", "c1")
        mock_pipe.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_company_id_in_key(self):
        """Company ID appears in the Redis key."""
        mock_redis, _ = _setup_redis()
        stack, called_keys = _redis_patches(mock_redis, track_keys=True)
        with stack:
            await self.svc.record_update("signal", "s1", "my_co")
        assert any("my_co" in k for k in called_keys)

    @pytest.mark.asyncio
    async def test_entity_type_in_key(self):
        """Entity type is part of the Redis key."""
        mock_redis, _ = _setup_redis()
        stack, called_keys = _redis_patches(mock_redis, track_keys=True)
        with stack:
            await self.svc.record_update("context", "conv1", "c1")
        assert any("context" in k for k in called_keys)
        assert any("freshness" in k for k in called_keys)

    @pytest.mark.asyncio
    async def test_redis_error_no_crash(self):
        """Redis failure does not raise an exception (BC-008)."""
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = Exception("set failed")
        stack, _ = _redis_patches(mock_redis)
        with stack:
            await self.svc.record_update("signal", "s1", "c1")
        # No exception raised — test passes implicitly

    @pytest.mark.asyncio
    async def test_overwrites_previous_timestamp(self):
        """Calling twice issues SET twice (idempotent overwrite)."""
        mock_redis, mock_pipe = _setup_redis()
        stack, _ = _redis_patches(mock_redis)
        with stack:
            await self.svc.record_update("signal", "s1", "c1")
            await self.svc.record_update("signal", "s1", "c1")
        assert mock_pipe.set.call_count == 2

    @pytest.mark.asyncio
    async def test_timestamp_format_valid_iso(self):
        """Stored payload contains a valid ISO-8601 timestamp."""
        mock_redis, mock_pipe = _setup_redis()
        stack, _ = _redis_patches(mock_redis)
        with stack:
            await self.svc.record_update("signal", "s1", "c1")
        set_call = mock_pipe.set.call_args
        payload_str = set_call[0][1]
        payload = json.loads(payload_str)
        dt = datetime.fromisoformat(payload["updated_at"])
        assert dt.tzinfo is not None


# ═══════════════════════════════════════════════════════════════════════
# 11. TestNeedsReExtraction (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestNeedsReExtraction:

    def setup_method(self):
        self.svc = DataFreshnessService()

    @pytest.mark.asyncio
    async def test_fresh_signals_returns_false(self):
        """Fresh signals → no re-extraction needed."""
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 200],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.needs_re_extraction("h1", "c1", "v1")
        assert result is False

    @pytest.mark.asyncio
    async def test_stale_signals_returns_true(self):
        """Stale/expired signals → re-extraction needed."""
        # max_age=300, 1.5×=450; 400 in (300, 450] → STALE
        payload = _freshness_payload(seconds_ago=400)
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, None],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.needs_re_extraction("h1", "c1", "v1")
        assert result is True

    @pytest.mark.asyncio
    async def test_non_existent_returns_true(self):
        """Missing signals → re-extraction (safe default)."""
        mock_redis, _ = _setup_redis(pipe_results=[None, -2])
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.needs_re_extraction("h1", "c1", "v1")
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_error_returns_true(self):
        """Redis failure → re-extraction (safe default)."""
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = Exception("down")
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.needs_re_extraction("h1", "c1", "v1")
        assert result is True

    @pytest.mark.asyncio
    async def test_company_and_variant_isolation(self):
        """Different company/variant → different Redis keys."""
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 200],
        )
        stack, called_keys = _redis_patches(mock_redis, track_keys=True)
        with stack:
            await self.svc.needs_re_extraction("h1", "co99", "sentiment")
        assert any("co99" in k for k in called_keys)
        assert any("sentiment" in k for k in called_keys)


# ═══════════════════════════════════════════════════════════════════════
# 12. TestNeedsRAGRefresh (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestNeedsRAGRefresh:

    def setup_method(self):
        self.svc = DataFreshnessService()

    @pytest.mark.asyncio
    async def test_fresh_rag_returns_false(self):
        """Fresh RAG → no refresh needed."""
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 100],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.needs_rag_refresh("query", "c1", "v1")
        assert result is False

    @pytest.mark.asyncio
    async def test_stale_rag_returns_true(self):
        """Stale RAG → refresh needed."""
        # max_age=120; 150 in (120, 180] → STALE → is_fresh=False
        payload = _freshness_payload(seconds_ago=150)
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, None],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.needs_rag_refresh("q", "c1", "v1")
        assert result is True

    @pytest.mark.asyncio
    async def test_non_existent_returns_true(self):
        """Missing RAG → refresh (safe default)."""
        mock_redis, _ = _setup_redis(pipe_results=[None, -2])
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.needs_rag_refresh("q", "c1", "v")
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_error_returns_true(self):
        """Redis failure → refresh (safe default)."""
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = Exception("error")
        stack, _ = _redis_patches(mock_redis)
        with stack:
            result = await self.svc.needs_rag_refresh("q", "c1", "v")
        assert result is True

    @pytest.mark.asyncio
    async def test_company_and_variant_isolation(self):
        """Company and variant appear in the Redis keys."""
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 100],
        )
        stack, called_keys = _redis_patches(mock_redis, track_keys=True)
        with stack:
            await self.svc.needs_rag_refresh(
                "my query",
                "co42",
                "intent",
            )
        assert any("co42" in k for k in called_keys)
        assert any("intent" in k for k in called_keys)


# ═══════════════════════════════════════════════════════════════════════
# 13. TestBatchCheckFreshness (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestBatchCheckFreshness:

    def setup_method(self):
        self.svc = DataFreshnessService()

    @pytest.mark.asyncio
    async def test_multiple_keys_checked(self):
        """Batch evaluates multiple keys in one pipeline round trip."""
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[
                payload,
                now + 100,  # key 1: get, expiretime
                payload,
                now + 100,  # key 2: get, expiretime
            ],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            keys = [
                {"entity_type": "signal", "entity_id": "s1"},
                {"entity_type": "context", "entity_id": "c1"},
            ]
            results = await self.svc.batch_check_freshness(keys, "co1")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_mixed_fresh_stale_results(self):
        """Batch returns correct status per key."""
        fresh_payload = _freshness_payload(seconds_ago=10)
        stale_payload = _freshness_payload(seconds_ago=400)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[
                fresh_payload,
                now + 100,  # key 1: FRESH
                stale_payload,
                None,  # key 2: STALE via fallback
            ],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            keys = [
                {"entity_type": "signal", "entity_id": "fresh1"},
                {"entity_type": "signal", "entity_id": "stale1"},
            ]
            results = await self.svc.batch_check_freshness(keys, "c1")
        assert results["fresh1"].status == FreshnessStatus.FRESH
        assert results["stale1"].status == FreshnessStatus.STALE

    @pytest.mark.asyncio
    async def test_empty_key_list_returns_empty(self):
        """Empty keys → empty results dict."""
        results = await self.svc.batch_check_freshness([], "c1")
        assert results == {}

    @pytest.mark.asyncio
    async def test_redis_error_all_unknown(self):
        """Redis failure → every result is UNKNOWN."""
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = Exception("pipeline error")
        stack, _ = _redis_patches(mock_redis)
        with stack:
            keys = [
                {"entity_type": "signal", "entity_id": "s1"},
                {"entity_type": "signal", "entity_id": "s2"},
            ]
            results = await self.svc.batch_check_freshness(keys, "c1")
        assert all(r.status == FreshnessStatus.UNKNOWN for r in results.values())
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_returns_dict_of_results(self):
        """Results keyed by entity_id."""
        payload = _freshness_payload(seconds_ago=10)
        now = time.time()
        mock_redis, _ = _setup_redis(
            pipe_results=[payload, now + 100],
        )
        stack, _ = _redis_patches(mock_redis)
        with stack:
            keys = [{"entity_type": "signal", "entity_id": "e1"}]
            results = await self.svc.batch_check_freshness(keys, "c1")
        assert isinstance(results, dict)
        assert "e1" in results
        assert isinstance(results["e1"], FreshnessCheckResult)


# ═══════════════════════════════════════════════════════════════════════
# 14. TestGetFreshnessReport (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestGetFreshnessReport:

    def setup_method(self):
        self.svc = DataFreshnessService()

    @pytest.mark.asyncio
    async def test_empty_company_returns_default_report(self):
        """No freshness keys → default report with zero counts."""
        mock_redis = MagicMock()
        mock_redis.scan = AsyncMock(return_value=[0, []])
        stack, _ = _redis_patches(mock_redis)
        with stack:
            report = await self.svc.get_freshness_report("c1")
        assert report["company_id"] == "c1"
        assert report["summary"]["total"] == 0
        assert report["summary"]["fresh"] == 0

    @pytest.mark.asyncio
    async def test_report_includes_all_entity_types(self):
        """Report aggregates freshness by entity type."""
        signal_key = _make_key("c1", "freshness", "signal", "s1")
        context_key = _make_key("c1", "freshness", "context", "conv1")
        fresh_payload = _freshness_payload(seconds_ago=10)
        now = time.time()

        mock_redis = MagicMock()
        mock_redis.scan = AsyncMock(
            return_value=[0, [signal_key, context_key]],
        )
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock(
            return_value=[
                fresh_payload,
                now + 200,  # signal
                fresh_payload,
                now + 1000,  # context
            ]
        )
        mock_redis.pipeline.return_value = mock_pipe

        stack, _ = _redis_patches(mock_redis)
        with stack:
            report = await self.svc.get_freshness_report("c1")
        assert "signal" in report["by_entity_type"]
        assert "context" in report["by_entity_type"]
        assert report["summary"]["total"] == 2

    @pytest.mark.asyncio
    async def test_aggregated_stats(self):
        """Summary counts match per-entity-type counts."""
        signal_key = _make_key("c1", "freshness", "signal", "s1")
        mock_redis = MagicMock()
        mock_redis.scan = AsyncMock(return_value=[0, [signal_key]])
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[None, -2])
        mock_redis.pipeline.return_value = mock_pipe

        stack, _ = _redis_patches(mock_redis)
        with stack:
            report = await self.svc.get_freshness_report("c1")
        assert report["summary"]["expired"] == 1
        assert report["summary"]["total"] == 1
        assert report["by_entity_type"]["signal"]["expired"] == 1
        assert report["by_entity_type"]["signal"]["total"] == 1

    @pytest.mark.asyncio
    async def test_company_isolation(self):
        """SCAN pattern scoped to the given company_id."""
        mock_redis = MagicMock()
        mock_redis.scan = AsyncMock(return_value=[0, []])
        with patch(
            "app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            with patch(
                "app.core.redis.make_key",
                side_effect=_make_key,
            ) as mk:
                await self.svc.get_freshness_report("company_X")
                call_args = mk.call_args[0]
                assert call_args[0] == "company_X"
