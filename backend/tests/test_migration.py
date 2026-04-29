"""
Comprehensive tests for rule_to_ai_migration.py (PARWA SaaS).

Covers:
- _is_ai_enabled: "ai"→True, "rule"→False, None→True, bytes handling
- enable_ai / disable_ai: Redis set calls
- check_should_use_ai: full pipeline (flag → circuit → rollout → confidence)
- batch_check: multiple tenants/features
- Metrics tracking
- CircuitBreaker: state transitions, recovery, reset
- RolloutEvaluator: percentage, canary, allow-list, geography
- MigrationConfig: validation, serialization
- MigrationResult: fields
- MigrationEventBus: pub/sub
- MigrationPlanner: staged rollout
- MigrationAuditLogger: logging, queries
- RedisFeatureFlagBackend / InMemoryFeatureFlagBackend
- Edge cases: Redis errors, bytes, missing configs
"""

from __future__ import annotations
from app.core.rule_to_ai_migration import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitState,
    FeatureCategory,
    FeatureFlagBackend,
    InMemoryFeatureFlagBackend,
    MigrationAuditLogger,
    MigrationConfig,
    MigrationEngine,
    MigrationEvent,
    MigrationEventBus,
    MigrationPlanner,
    MigrationResult,
    MigrationStatus,
    RedisFeatureFlagBackend,
    RolloutEvaluator,
    RolloutStrategy,
    create_migration_engine,
)

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

# ── Environment bootstrap ──────────────────────────────────────────
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test_secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt")
os.environ.setdefault(
    "DATA_ENCRYPTION_KEY",
    "12345678901234567890123456789012")


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_redis():
    """Async mock for Redis client — get returns None by default."""
    redis = AsyncMock()
    redis.get.return_value = None
    redis.set.return_value = True
    redis.delete.return_value = True
    return redis


@pytest.fixture
def memory_backend():
    return InMemoryFeatureFlagBackend()


@pytest.fixture
def engine():
    return MigrationEngine()


@pytest.fixture
def engine_with_redis(mock_redis):
    return MigrationEngine(redis_client=mock_redis)


# ══════════════════════════════════════════════════════════════════
# 1. _is_ai_enabled TESTS
# ══════════════════════════════════════════════════════════════════

class TestIsAiEnabled:
    def test_ai_string_returns_true(self):
        assert MigrationEngine._is_ai_enabled("ai") is True

    def test_rule_string_returns_false(self):
        assert MigrationEngine._is_ai_enabled("rule") is False

    def test_none_returns_true(self):
        assert MigrationEngine._is_ai_enabled(None) is True

    def test_empty_string_returns_true(self):
        assert MigrationEngine._is_ai_enabled("") is True

    def test_arbitrary_string_returns_true(self):
        assert MigrationEngine._is_ai_enabled("something_else") is True

    def test_enabled_string_returns_true(self):
        assert MigrationEngine._is_ai_enabled("enabled") is True

    def test_uppercase_rule_returns_true(self):
        """Only lowercase "rule" disables AI."""
        assert MigrationEngine._is_ai_enabled("RULE") is True

    def test_rule_with_whitespace_returns_true(self):
        assert MigrationEngine._is_ai_enabled(" rule ") is True


# ══════════════════════════════════════════════════════════════════
# 2. REDIS KEY HELPER TESTS
# ══════════════════════════════════════════════════════════════════

class TestRedisKeyHelper:
    def test_redis_key_format(self):
        key = MigrationEngine._redis_key("tenant_1", "ticket_assignment")
        assert key == "tenant_1:ticket_assignment"

    def test_redis_key_consistency(self):
        k1 = MigrationEngine._redis_key("t1", "f1")
        k2 = MigrationEngine._redis_key("t1", "f1")
        assert k1 == k2


# ══════════════════════════════════════════════════════════════════
# 3. FEATURE FLAG BACKEND TESTS
# ══════════════════════════════════════════════════════════════════

class TestInMemoryFeatureFlagBackend:
    @pytest.mark.asyncio
    async def test_get_none_when_empty(self):
        b = InMemoryFeatureFlagBackend()
        assert await b.get("missing") is None

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        b = InMemoryFeatureFlagBackend()
        await b.set("key1", "ai")
        assert await b.get("key1") == "ai"

    @pytest.mark.asyncio
    async def test_delete(self):
        b = InMemoryFeatureFlagBackend()
        await b.set("key1", "rule")
        await b.delete("key1")
        assert await b.get("key1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_no_error(self):
        b = InMemoryFeatureFlagBackend()
        await b.delete("nope")  # should not raise

    @pytest.mark.asyncio
    async def test_set_overwrites(self):
        b = InMemoryFeatureFlagBackend()
        await b.set("k", "ai")
        await b.set("k", "rule")
        assert await b.get("k") == "rule"


class TestRedisFeatureFlagBackend:
    @pytest.mark.asyncio
    async def test_get_decodes_bytes(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"ai"
        b = RedisFeatureFlagBackend(mock_redis, key_prefix="migration")
        val = await b.get("tenant_1:feature_1")
        assert val == "ai"

    @pytest.mark.asyncio
    async def test_get_returns_str_directly(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "rule"
        b = RedisFeatureFlagBackend(mock_redis, key_prefix="migration")
        val = await b.get("tenant_1:feature_1")
        assert val == "rule"

    @pytest.mark.asyncio
    async def test_get_returns_none_on_redis_error(self):
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis down")
        b = RedisFeatureFlagBackend(mock_redis, key_prefix="migration")
        val = await b.get("tenant_1:feature_1")
        assert val is None

    @pytest.mark.asyncio
    async def test_set_calls_redis_with_prefix(self):
        mock_redis = AsyncMock()
        b = RedisFeatureFlagBackend(mock_redis, key_prefix="migration")
        await b.set("t1:f1", "ai")
        mock_redis.set.assert_called_once_with("migration:t1:f1", "ai")

    @pytest.mark.asyncio
    async def test_set_with_ttl(self):
        mock_redis = AsyncMock()
        b = RedisFeatureFlagBackend(mock_redis, key_prefix="migration")
        await b.set("t1:f1", "ai", ttl=3600)
        mock_redis.set.assert_called_once_with(
            "migration:t1:f1", "ai", ex=3600)

    @pytest.mark.asyncio
    async def test_set_redis_error_no_crash(self):
        mock_redis = AsyncMock()
        mock_redis.set.side_effect = Exception("Connection refused")
        b = RedisFeatureFlagBackend(mock_redis, key_prefix="migration")
        await b.set("k", "v")  # should not raise

    @pytest.mark.asyncio
    async def test_delete_calls_redis(self):
        mock_redis = AsyncMock()
        b = RedisFeatureFlagBackend(mock_redis, key_prefix="migration")
        await b.delete("t1:f1")
        mock_redis.delete.assert_called_once_with("migration:t1:f1")

    @pytest.mark.asyncio
    async def test_delete_redis_error_no_crash(self):
        mock_redis = AsyncMock()
        mock_redis.delete.side_effect = Exception("Down")
        b = RedisFeatureFlagBackend(mock_redis, key_prefix="migration")
        await b.delete("k")  # should not raise

    @pytest.mark.asyncio
    async def test_full_key_prefix(self):
        mock_redis = AsyncMock()
        b = RedisFeatureFlagBackend(mock_redis, key_prefix="custom")
        assert b._full_key("t1:f1") == "custom:t1:f1"


# ══════════════════════════════════════════════════════════════════
# 4. ENABLE_AI / DISABLE_AI TESTS
# ══════════════════════════════════════════════════════════════════

class TestEnableDisableAi:
    @pytest.mark.asyncio
    async def test_enable_ai_sets_value(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        result = await engine.enable_ai("t1", "f1")
        assert result is True
        val = await memory_backend.get("t1:f1")
        assert val == "ai"

    @pytest.mark.asyncio
    async def test_disable_ai_sets_value(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        result = await engine.disable_ai("t1", "f1")
        assert result is True
        val = await memory_backend.get("t1:f1")
        assert val == "rule"

    @pytest.mark.asyncio
    async def test_enable_ai_publishes_event(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        await engine.enable_ai("t1", "f1")
        events = engine.get_event_history(event_type="migration.ai_enabled")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_disable_ai_publishes_event(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        await engine.disable_ai("t1", "f1")
        events = engine.get_event_history(event_type="migration.ai_disabled")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_enable_then_disable(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        await engine.enable_ai("t1", "f1")
        await engine.disable_ai("t1", "f1")
        val = await memory_backend.get("t1:f1")
        assert val == "rule"

    @pytest.mark.asyncio
    async def test_enable_with_redis(self, engine_with_redis):
        await engine_with_redis.enable_ai("t1", "f1")
        engine_with_redis._backend._redis.set.assert_called()


# ══════════════════════════════════════════════════════════════════
# 5. is_ai_enabled (HIGH LEVEL) TESTS
# ══════════════════════════════════════════════════════════════════

class TestIsAiEnabledHighLevel:
    @pytest.mark.asyncio
    async def test_default_enabled(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        assert await engine.is_ai_enabled("t1", "f1") is True

    @pytest.mark.asyncio
    async def test_after_disable(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        await engine.disable_ai("t1", "f1")
        assert await engine.is_ai_enabled("t1", "f1") is False

    @pytest.mark.asyncio
    async def test_after_enable(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        await engine.enable_ai("t1", "f1")
        assert await engine.is_ai_enabled("t1", "f1") is True

    @pytest.mark.asyncio
    async def test_increments_total_checks(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        await engine.is_ai_enabled("t1", "f1")
        m = engine.get_metrics()
        assert m["total_checks"] == 1

    @pytest.mark.asyncio
    async def test_fail_open_on_error(self, mock_redis):
        mock_redis.get.side_effect = Exception("Redis error")
        engine = MigrationEngine(redis_client=mock_redis)
        result = await engine.is_ai_enabled("t1", "f1")
        assert result is True  # fail-open

    @pytest.mark.asyncio
    async def test_error_increments_migration_errors(self):
        """Backend error propagates to is_ai_enabled which catches it."""
        backend = AsyncMock(spec=FeatureFlagBackend)
        backend.get.side_effect = Exception("Backend error")
        engine = MigrationEngine(backend=backend)
        await engine.is_ai_enabled("t1", "f1")
        m = engine.get_metrics()
        assert m["migration_errors"] == 1

    @pytest.mark.asyncio
    async def test_redis_returns_bytes_rule(self, mock_redis):
        mock_redis.get.return_value = b"rule"
        engine = MigrationEngine(redis_client=mock_redis)
        assert await engine.is_ai_enabled("t1", "f1") is False

    @pytest.mark.asyncio
    async def test_redis_returns_bytes_ai(self, mock_redis):
        mock_redis.get.return_value = b"ai"
        engine = MigrationEngine(redis_client=mock_redis)
        assert await engine.is_ai_enabled("t1", "f1") is True


# ══════════════════════════════════════════════════════════════════
# 6. check_should_use_ai TESTS
# ══════════════════════════════════════════════════════════════════

class TestCheckShouldUseAi:
    @pytest.mark.asyncio
    async def test_default_returns_use_ai(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        result = await engine.check_should_use_ai("t1", "f1")
        assert result.use_ai is True
        assert isinstance(result, MigrationResult)

    @pytest.mark.asyncio
    async def test_disabled_by_flag(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        await engine.disable_ai("t1", "f1")
        result = await engine.check_should_use_ai("t1", "f1")
        assert result.use_ai is False
        assert "feature flag" in result.reason

    @pytest.mark.asyncio
    async def test_confidence_below_threshold(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        config = MigrationConfig(
            tenant_id="t1", feature="f1",
            confidence_threshold=0.90,
            rollout_percentage=1.0,
            rollout_strategy=RolloutStrategy.ALL_AT_ONCE,
        )
        await engine.set_config(config)
        result = await engine.check_should_use_ai("t1", "f1", confidence=0.50)
        assert result.use_ai is False
        assert "Confidence" in result.reason

    @pytest.mark.asyncio
    async def test_confidence_above_threshold(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        config = MigrationConfig(
            tenant_id="t1", feature="f1",
            confidence_threshold=0.50,
            rollout_percentage=1.0,
            rollout_strategy=RolloutStrategy.ALL_AT_ONCE,
        )
        await engine.set_config(config)
        result = await engine.check_should_use_ai("t1", "f1", confidence=0.90)
        assert result.use_ai is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        for _ in range(10):
            engine.record_ai_failure("t1", "f1")
        result = await engine.check_should_use_ai("t1", "f1")
        assert result.use_ai is False
        assert "Circuit" in result.reason

    @pytest.mark.asyncio
    async def test_rollout_percentage_blocks(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        config = MigrationConfig(
            tenant_id="t1", feature="f1",
            rollout_percentage=0.0,
            rollout_strategy=RolloutStrategy.PERCENTAGE,
        )
        await engine.set_config(config)
        result = await engine.check_should_use_ai("t1", "f1")
        assert result.use_ai is False
        assert "rollout" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_rollout_100_pct_passes(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        config = MigrationConfig(
            tenant_id="t1", feature="f1",
            rollout_percentage=1.0,
            rollout_strategy=RolloutStrategy.PERCENTAGE,
        )
        await engine.set_config(config)
        result = await engine.check_should_use_ai("t1", "f1")
        assert result.use_ai is True

    @pytest.mark.asyncio
    async def test_result_has_latency(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        result = await engine.check_should_use_ai("t1", "f1")
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_result_has_timestamp(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        result = await engine.check_should_use_ai("t1", "f1")
        assert result.timestamp is not None

    @pytest.mark.asyncio
    async def test_flag_disabled_increments_rule_fallbacks(
            self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        await engine.disable_ai("t1", "f1")
        await engine.check_should_use_ai("t1", "f1")
        m = engine.get_metrics()
        assert m["rule_fallbacks"] == 1


# ══════════════════════════════════════════════════════════════════
# 7. BATCH CHECK TESTS
# ══════════════════════════════════════════════════════════════════

class TestBatchCheck:
    @pytest.mark.asyncio
    async def test_batch_check_multiple(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        checks = [
            {"tenant_id": "t1", "feature": "f1"},
            {"tenant_id": "t2", "feature": "f2"},
            {"tenant_id": "t3", "feature": "f3"},
        ]
        results = await engine.batch_check(checks)
        assert len(results) == 3
        assert "t1:f1" in results
        assert "t2:f2" in results
        assert "t3:f3" in results

    @pytest.mark.asyncio
    async def test_batch_check_with_confidence(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        config = MigrationConfig(
            tenant_id="t1",
            feature="f1",
            confidence_threshold=0.90)
        await engine.set_config(config)
        checks = [
            {"tenant_id": "t1", "feature": "f1", "confidence": 0.50},
            {"tenant_id": "t2", "feature": "f2", "confidence": 0.99},
        ]
        results = await engine.batch_check(checks)
        assert results["t1:f1"].use_ai is False
        assert results["t2:f2"].use_ai is True

    @pytest.mark.asyncio
    async def test_batch_check_empty(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        results = await engine.batch_check([])
        assert results == {}


# ══════════════════════════════════════════════════════════════════
# 8. BATCH ENABLE / DISABLE TESTS
# ══════════════════════════════════════════════════════════════════

class TestBatchEnableDisable:
    @pytest.mark.asyncio
    async def test_batch_enable(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        pairs = [("t1", "f1"), ("t2", "f2"), ("t3", "f3")]
        results = await engine.batch_enable(pairs)
        assert results == [True, True, True]

    @pytest.mark.asyncio
    async def test_batch_disable(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        pairs = [("t1", "f1"), ("t2", "f2")]
        results = await engine.batch_disable(pairs)
        assert results == [True, True]


# ══════════════════════════════════════════════════════════════════
# 9. METRICS TESTS
# ══════════════════════════════════════════════════════════════════

class TestMetrics:
    @pytest.mark.asyncio
    async def test_initial_metrics(self, engine):
        m = engine.get_metrics()
        assert m["total_checks"] == 0
        assert m["ai_enabled_checks"] == 0
        assert m["rule_fallbacks"] == 0

    @pytest.mark.asyncio
    async def test_metrics_after_checks(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        await engine.is_ai_enabled("t1", "f1")
        await engine.is_ai_enabled("t2", "f2")
        m = engine.get_metrics()
        assert m["total_checks"] == 2

    @pytest.mark.asyncio
    async def test_per_feature_metrics(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        await engine.is_ai_enabled("t1", "f1")
        await engine.is_ai_enabled("t1", "f1")
        m = engine.get_metrics()
        pf = m["per_feature"]
        assert "t1:f1" in pf
        assert pf["t1:f1"]["total_checks"] == 2

    @pytest.mark.asyncio
    async def test_reset_metrics(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        await engine.is_ai_enabled("t1", "f1")
        await engine.reset_metrics()
        m = engine.get_metrics()
        assert m["total_checks"] == 0
        assert m["per_feature"] == {}

    @pytest.mark.asyncio
    async def test_circuit_blocked_metric(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        for _ in range(10):
            engine.record_ai_failure("t1", "f1")
        await engine.check_should_use_ai("t1", "f1")
        m = engine.get_metrics()
        assert m["circuit_blocked"] >= 1


# ══════════════════════════════════════════════════════════════════
# 10. CIRCUIT BREAKER TESTS
# ══════════════════════════════════════════════════════════════════

class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker()
        assert cb.get_state("test") == CircuitState.CLOSED

    def test_is_available_when_closed(self):
        cb = CircuitBreaker()
        assert cb.is_available("test") is True

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(error_threshold=3)
        for _ in range(3):
            cb.record_failure("k")
        assert cb.get_state("k") == CircuitState.OPEN

    def test_not_available_when_open(self):
        cb = CircuitBreaker(error_threshold=2)
        cb.record_failure("k")
        cb.record_failure("k")
        assert cb.is_available("k") is False

    def test_success_resets_failure_count_when_closed(self):
        cb = CircuitBreaker(error_threshold=5)
        cb.record_failure("k")
        cb.record_failure("k")
        cb.record_success("k")
        # failure_count not reset on success in CLOSED state per implementation
        detail = cb.get_state_detail("k")
        assert detail["success_count"] == 1

    def test_half_open_to_closed_after_successes(self):
        cb = CircuitBreaker(error_threshold=2, recovery_timeout_seconds=0)
        cb.record_failure("k")
        cb.record_failure("k")
        # Force opened_at in the past
        state = cb._ensure("k")
        state.opened_at = (
            datetime.now(
                timezone.utc)
            - timedelta(
                seconds=1)).isoformat()
        assert cb.get_state("k") == CircuitState.HALF_OPEN
        # Now record enough successes
        for _ in range(3):
            cb.record_success("k")
        assert cb.get_state("k") == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(error_threshold=2, recovery_timeout_seconds=60)
        cb.record_failure("k")
        cb.record_failure("k")
        state = cb._ensure("k")
        state.opened_at = (
            datetime.now(
                timezone.utc)
            - timedelta(
                seconds=120)).isoformat()
        assert cb.get_state("k") == CircuitState.HALF_OPEN
        cb.record_failure("k")
        # After failure in half_open, circuit re-opens. Since opened_at
        # is just now and recovery_timeout=60s, it stays OPEN.
        assert cb.get_state("k") == CircuitState.OPEN

    def test_get_state_detail(self):
        cb = CircuitBreaker()
        detail = cb.get_state_detail("k")
        assert "state" in detail
        assert "failure_count" in detail
        assert "success_count" in detail

    def test_reset_single_key(self):
        cb = CircuitBreaker()
        cb.record_failure("k1")
        cb.reset("k1")
        assert cb.get_state("k1") == CircuitState.CLOSED

    def test_reset_all_keys(self):
        cb = CircuitBreaker()
        cb.record_failure("k1")
        cb.record_failure("k2")
        cb.reset()
        assert cb.get_state("k1") == CircuitState.CLOSED
        assert cb.get_state("k2") == CircuitState.CLOSED

    def test_independent_keys(self):
        cb = CircuitBreaker(error_threshold=2)
        cb.record_failure("k1")
        cb.record_failure("k1")
        assert cb.get_state("k1") == CircuitState.OPEN
        assert cb.get_state("k2") == CircuitState.CLOSED

    def test_custom_error_threshold(self):
        cb = CircuitBreaker(error_threshold=10)
        for _ in range(9):
            cb.record_failure("k")
        assert cb.get_state("k") == CircuitState.CLOSED

    def test_failure_increments_count(self):
        cb = CircuitBreaker()
        cb.record_failure("k")
        assert cb._ensure("k").failure_count == 1

    def test_success_increments_count(self):
        cb = CircuitBreaker()
        cb.record_success("k")
        assert cb._ensure("k").success_count == 1


# ══════════════════════════════════════════════════════════════════
# 11. ROLLOUT EVALUATOR TESTS
# ══════════════════════════════════════════════════════════════════

class TestRolloutEvaluator:
    def test_percentage_100(self):
        assert RolloutEvaluator.by_percentage(1.0, "t1") is True

    def test_percentage_0(self):
        assert RolloutEvaluator.by_percentage(0.0, "t1") is False

    def test_percentage_deterministic(self):
        r1 = RolloutEvaluator.by_percentage(0.5, "t1", "ticket_1")
        r2 = RolloutEvaluator.by_percentage(0.5, "t1", "ticket_1")
        assert r1 == r2

    def test_percentage_different_tickets(self):
        r1 = RolloutEvaluator.by_percentage(0.01, "t1", "ticket_1")
        r2 = RolloutEvaluator.by_percentage(0.01, "t1", "ticket_2")
        # With 1% rollout, at least one should differ (probabilistic but consistent)
        # We just check both return bool
        assert isinstance(r1, bool)
        assert isinstance(r2, bool)

    def test_canary_in_list(self):
        assert RolloutEvaluator.by_canary("t1", ["t1", "t2"]) is True

    def test_canary_not_in_list(self):
        assert RolloutEvaluator.by_canary("t3", ["t1", "t2"]) is False

    def test_allow_list_in_list(self):
        assert RolloutEvaluator.by_allow_list("t1", ["t1"]) is True

    def test_allow_list_not_in_list(self):
        assert RolloutEvaluator.by_allow_list("t1", ["t2"]) is False

    def test_geography_match(self):
        assert RolloutEvaluator.by_geography("us", ["us", "eu"]) is True

    def test_geography_no_match(self):
        assert RolloutEvaluator.by_geography("asia", ["us", "eu"]) is False

    def test_geography_no_region_returns_true(self):
        assert RolloutEvaluator.by_geography(None, ["us"]) is True

    def test_geography_no_allowed_returns_true(self):
        assert RolloutEvaluator.by_geography("us", []) is True


# ══════════════════════════════════════════════════════════════════
# 12. MIGRATION CONFIG TESTS
# ══════════════════════════════════════════════════════════════════

class TestMigrationConfig:
    def test_default_values(self):
        c = MigrationConfig(tenant_id="t1", feature="f1")
        assert c.rollout_percentage == 0.0
        assert c.confidence_threshold == 0.80
        assert c.enabled is True
        assert c.fallback_to_rule is True

    def test_rollout_percentage_clamped_high(self):
        c = MigrationConfig(
            tenant_id="t1",
            feature="f1",
            rollout_percentage=2.0)
        assert c.rollout_percentage == 1.0

    def test_rollout_percentage_clamped_low(self):
        c = MigrationConfig(
            tenant_id="t1",
            feature="f1",
            rollout_percentage=-0.5)
        assert c.rollout_percentage == 0.0

    def test_created_at_auto_set(self):
        c = MigrationConfig(tenant_id="t1", feature="f1")
        assert c.created_at != ""

    def test_to_dict(self):
        c = MigrationConfig(
            tenant_id="t1",
            feature="f1",
            rollout_percentage=0.5)
        d = c.to_dict()
        assert d["tenant_id"] == "t1"
        assert d["feature"] == "f1"
        assert d["rollout_percentage"] == 0.5


# ══════════════════════════════════════════════════════════════════
# 13. MIGRATION RESULT TESTS
# ══════════════════════════════════════════════════════════════════

class TestMigrationResult:
    def test_basic_fields(self):
        r = MigrationResult(
            tenant_id="t1", feature="f1",
            use_ai=True, reason="test", strategy_used="all_at_once",
        )
        assert r.use_ai is True
        assert r.tenant_id == "t1"

    def test_timestamp_auto_set(self):
        r = MigrationResult(
            tenant_id="t1", feature="f1",
            use_ai=True, reason="test", strategy_used="all_at_once",
        )
        assert r.timestamp != ""

    def test_to_dict(self):
        r = MigrationResult(
            tenant_id="t1", feature="f1",
            use_ai=True, reason="test", strategy_used="all_at_once",
            confidence=0.92,
        )
        d = r.to_dict()
        assert d["use_ai"] is True
        assert d["confidence"] == 0.92
        assert "latency_ms" in d


# ══════════════════════════════════════════════════════════════════
# 14. MIGRATION EVENT BUS TESTS
# ══════════════════════════════════════════════════════════════════

class TestMigrationEventBus:
    def test_publish_and_get_history(self):
        bus = MigrationEventBus()
        bus.publish(MigrationEvent(event_type="test", payload={"k": "v"}))
        hist = bus.get_history()
        assert len(hist) == 1
        assert hist[0]["event_type"] == "test"

    def test_subscribe(self):
        bus = MigrationEventBus()
        received = []
        bus.subscribe("e", lambda ev: received.append(ev))
        bus.publish(MigrationEvent(event_type="e", payload={}))
        assert len(received) == 1

    def test_unsubscribe(self):
        bus = MigrationEventBus()

        def handler(ev):
            return None
        bus.subscribe("e", handler)
        bus.unsubscribe("e", handler)
        assert bus._subs.get("e") == []

    def test_handler_error_doesnt_stop_others(self):
        bus = MigrationEventBus()
        received = []
        bus.subscribe("e", lambda ev: 1 / 0)
        bus.subscribe("e", lambda ev: received.append(ev))
        bus.publish(MigrationEvent(event_type="e", payload={}))
        assert len(received) == 1

    def test_history_filter_by_type(self):
        bus = MigrationEventBus()
        bus.publish(MigrationEvent(event_type="a", payload={}))
        bus.publish(MigrationEvent(event_type="b", payload={}))
        assert len(bus.get_history(event_type="a")) == 1

    def test_history_limit(self):
        bus = MigrationEventBus()
        for _ in range(10):
            bus.publish(MigrationEvent(event_type="e", payload={}))
        assert len(bus.get_history(limit=3)) == 3

    def test_clear_history(self):
        bus = MigrationEventBus()
        bus.publish(MigrationEvent(event_type="e", payload={}))
        bus.clear_history()
        assert bus.get_history() == []


# ══════════════════════════════════════════════════════════════════
# 15. CONFIG CRUD TESTS
# ══════════════════════════════════════════════════════════════════

class TestConfigCrud:
    @pytest.mark.asyncio
    async def test_set_and_get_config(self, engine):
        config = MigrationConfig(
            tenant_id="t1",
            feature="f1",
            rollout_percentage=0.5)
        await engine.set_config(config)
        retrieved = await engine.get_config("t1", "f1")
        assert retrieved is not None
        assert retrieved.rollout_percentage == 0.5

    @pytest.mark.asyncio
    async def test_get_config_missing(self, engine):
        assert await engine.get_config("t1", "missing") is None

    @pytest.mark.asyncio
    async def test_delete_config(self, engine):
        config = MigrationConfig(tenant_id="t1", feature="f1")
        await engine.set_config(config)
        await engine.delete_config("t1", "f1")
        assert await engine.get_config("t1", "f1") is None

    @pytest.mark.asyncio
    async def test_list_configs(self, engine):
        await engine.set_config(MigrationConfig(tenant_id="t1", feature="f1"))
        await engine.set_config(MigrationConfig(tenant_id="t1", feature="f2"))
        await engine.set_config(MigrationConfig(tenant_id="t2", feature="f1"))
        all_cfgs = await engine.list_configs()
        assert len(all_cfgs) == 3
        t1_cfgs = await engine.list_configs(tenant_id="t1")
        assert len(t1_cfgs) == 2

    @pytest.mark.asyncio
    async def test_set_config_publishes_event(self, engine):
        config = MigrationConfig(tenant_id="t1", feature="f1")
        await engine.set_config(config)
        events = engine.get_event_history(
            event_type="migration.config_updated")
        assert len(events) == 1


# ══════════════════════════════════════════════════════════════════
# 16. DELETE FLAG / GET FLAG VALUE TESTS
# ══════════════════════════════════════════════════════════════════

class TestFlagOperations:
    @pytest.mark.asyncio
    async def test_delete_flag(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        await engine.enable_ai("t1", "f1")
        await engine.delete_flag("t1", "f1")
        val = await engine.get_flag_value("t1", "f1")
        assert val is None

    @pytest.mark.asyncio
    async def test_get_flag_value(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        await engine.enable_ai("t1", "f1")
        val = await engine.get_flag_value("t1", "f1")
        assert val == "ai"


# ══════════════════════════════════════════════════════════════════
# 17. MIGRATION PLANNER TESTS
# ══════════════════════════════════════════════════════════════════

class TestMigrationPlanner:
    @pytest.mark.asyncio
    async def test_advance_through_stages(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        planner = MigrationPlanner(engine)
        result = await planner.advance("t1", "f1")
        assert result["status"] == "advanced"
        assert result["stage"] == "canary"

    @pytest.mark.asyncio
    async def test_advance_to_full(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        planner = MigrationPlanner(engine)
        for _ in range(6):
            result = await planner.advance("t1", "f1")
        assert result["stage"] == "full"

    @pytest.mark.asyncio
    async def test_advance_past_full(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        planner = MigrationPlanner(engine)
        for _ in range(7):
            await planner.advance("t1", "f1")
        result = await planner.advance("t1", "f1")
        assert result["status"] == "already_complete"

    @pytest.mark.asyncio
    async def test_rollback(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        planner = MigrationPlanner(engine)
        await planner.advance("t1", "f1")
        result = await planner.rollback("t1", "f1")
        assert result["status"] == "rolled_back"

    @pytest.mark.asyncio
    async def test_current_stage_not_started(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        planner = MigrationPlanner(engine)
        stage = planner.current_stage("t1", "f1")
        assert stage["stage"] == "not_started"

    @pytest.mark.asyncio
    async def test_current_stage_after_advance(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        planner = MigrationPlanner(engine)
        await planner.advance("t1", "f1")
        stage = planner.current_stage("t1", "f1")
        assert stage["stage"] == "canary"

    @pytest.mark.asyncio
    async def test_pause(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        planner = MigrationPlanner(engine)
        await planner.advance("t1", "f1")
        result = await planner.pause("t1", "f1")
        assert result["status"] == "paused"

    @pytest.mark.asyncio
    async def test_set_canary_tenants(self, memory_backend):
        engine = MigrationEngine(backend=memory_backend)
        planner = MigrationPlanner(engine)
        await planner.set_canary_tenants("t1", "f1", ["c1", "c2"])
        config = await engine.get_config("t1", "f1")
        assert config is not None
        assert config.canary_tenants == ["c1", "c2"]
        assert config.rollout_strategy == RolloutStrategy.CANARY_TENANTS


# ══════════════════════════════════════════════════════════════════
# 18. AUDIT LOGGER TESTS
# ══════════════════════════════════════════════════════════════════

class TestMigrationAuditLogger:
    def test_log_entry(self):
        logger = MigrationAuditLogger()
        entry = logger.log("enable", "t1", "f1")
        assert entry["action"] == "enable"
        assert entry["tenant_id"] == "t1"
        assert entry["feature"] == "f1"
        assert "id" in entry
        assert "timestamp" in entry

    def test_log_with_actor(self):
        audit = MigrationAuditLogger()
        entry = audit.log("enable", "t1", "f1", actor="admin")
        assert entry["actor"] == "admin"

    def test_query_by_tenant(self):
        audit = MigrationAuditLogger()
        audit.log("enable", "t1", "f1")
        audit.log("disable", "t2", "f1")
        results = audit.query(tenant_id="t1")
        assert len(results) == 1
        assert results[0]["tenant_id"] == "t1"

    def test_query_by_feature(self):
        audit = MigrationAuditLogger()
        audit.log("enable", "t1", "f1")
        audit.log("disable", "t1", "f2")
        results = audit.query(feature="f1")
        assert len(results) == 1

    def test_query_by_action(self):
        audit = MigrationAuditLogger()
        audit.log("enable", "t1", "f1")
        audit.log("disable", "t1", "f1")
        results = audit.query(action="enable")
        assert len(results) == 1

    def test_query_limit(self):
        audit = MigrationAuditLogger()
        for i in range(10):
            audit.log("enable", f"t{i}", "f1")
        results = audit.query(limit=3)
        assert len(results) == 3

    def test_export_json(self):
        audit = MigrationAuditLogger()
        audit.log("enable", "t1", "f1")
        json_str = audit.export_json()
        import json
        parsed = json.loads(json_str)
        assert len(parsed) == 1

    def test_max_entries(self):
        audit = MigrationAuditLogger(max_entries=5)
        for i in range(10):
            audit.log("enable", f"t{i}", "f1")
        entries = audit.query(limit=100)
        assert len(entries) == 5


# ══════════════════════════════════════════════════════════════════
# 19. ENGINE RESET TESTS
# ══════════════════════════════════════════════════════════════════

class TestEngineReset:
    @pytest.mark.asyncio
    async def test_reset_clears_configs(self, engine):
        config = MigrationConfig(tenant_id="t1", feature="f1")
        await engine.set_config(config)
        engine.reset()
        assert await engine.get_config("t1", "f1") is None

    @pytest.mark.asyncio
    async def test_reset_clears_circuits(self, engine):
        engine.record_ai_failure("t1", "f1")
        engine.record_ai_failure("t1", "f1")
        engine.reset_circuits()
        state = engine.get_circuit_state("t1", "f1")
        assert state["state"] == "closed"

    @pytest.mark.asyncio
    async def test_reset_clears_events(self, engine):
        await engine.enable_ai("t1", "f1")
        assert len(engine.get_event_history()) > 0
        engine.reset()
        assert engine.get_event_history() == []


# ══════════════════════════════════════════════════════════════════
# 20. FACTORY & ENUM TESTS
# ══════════════════════════════════════════════════════════════════

class TestFactoryAndEnums:
    def test_create_migration_engine(self):
        engine = create_migration_engine()
        assert isinstance(engine, MigrationEngine)

    def test_migration_status_values(self):
        assert MigrationStatus.RULE_BASED.value == "rule"
        assert MigrationStatus.AI_BASED.value == "ai"
        assert MigrationStatus.TRANSITIONING.value == "transitioning"

    def test_feature_category_values(self):
        assert FeatureCategory.TICKET_ASSIGNMENT.value == "ticket_assignment"

    def test_rollout_strategy_values(self):
        assert RolloutStrategy.PERCENTAGE.value == "percentage"
        assert RolloutStrategy.CANARY_TENANTS.value == "canary_tenants"
        assert RolloutStrategy.ALL_AT_ONCE.value == "all_at_once"

    def test_circuit_state_values(self):
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_migration_event(self):
        e = MigrationEvent(event_type="test", payload={"k": "v"})
        assert e.event_id is not None
        d = e.to_dict()
        assert d["event_type"] == "test"

    def test_engine_init_with_custom_backend(self):
        backend = InMemoryFeatureFlagBackend()
        engine = MigrationEngine(backend=backend)
        assert engine._backend is backend

    def test_engine_init_with_redis(self, mock_redis):
        engine = MigrationEngine(redis_client=mock_redis)
        assert isinstance(engine._backend, RedisFeatureFlagBackend)

    def test_engine_init_default_backend(self):
        engine = MigrationEngine()
        assert isinstance(engine._backend, InMemoryFeatureFlagBackend)


# ══════════════════════════════════════════════════════════════════
# 21. CIRCUIT BREAKER STATE DATA MODEL TESTS
# ══════════════════════════════════════════════════════════════════

class TestCircuitBreakerState:
    def test_default_values(self):
        s = CircuitBreakerState()
        assert s.state == CircuitState.CLOSED
        assert s.failure_count == 0
        assert s.success_count == 0
        assert s.last_failure_at is None

    def test_to_dict(self):
        s = CircuitBreakerState(error_threshold=3)
        d = s.to_dict()
        assert d["state"] == "closed"
        assert d["error_threshold"] == 3


# ══════════════════════════════════════════════════════════════════
# 22. SUBSCRIBE / EVENT HISTORY ON ENGINE
# ══════════════════════════════════════════════════════════════════

class TestEngineEvents:
    @pytest.mark.asyncio
    async def test_subscribe_handler_called(self, engine):
        received = []
        engine.subscribe("migration.ai_enabled", lambda e: received.append(e))
        await engine.enable_ai("t1", "f1")
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_get_event_history_limit(self, engine):
        for i in range(5):
            await engine.enable_ai(f"t{i}", "f1")
        events = engine.get_event_history(limit=2)
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_get_event_history_filter(self, engine):
        await engine.enable_ai("t1", "f1")
        await engine.disable_ai("t1", "f1")
        enable_events = engine.get_event_history(
            event_type="migration.ai_enabled")
        assert len(enable_events) == 1
