"""
Comprehensive tests for TokenBudgetService (F-156).

Tests cover: initialization, reservation, finalization, status, overflow,
context management, in-memory fallback, Redis mode, variant configs,
safety margins, and BC-008 graceful degradation.

CRITICAL: effective_max = raw_max * (1 - SAFETY_MARGIN_PERCENT) = raw_max * 0.9
  mini_parwa:  4096 * 0.9 = 3686
  parwa:       8192 * 0.9 = 7372
  parwa_high: 16384 * 0.9 = 14745
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.token_budget_service import (
    TokenBudgetService,
    TokenBudget,
    ReserveResult,
    TokenBudgetStatus,
    OverflowCheck,
    ContextStrategy,
    TokenEntry,
    VARIANT_TOKEN_BUDGETS,
    DEFAULT_VARIANT_TYPE,
    SAFETY_MARGIN_PERCENT,
    REDIS_KEY_TTL_SECONDS,
    RESERVE_LUA,
    FINALIZE_LUA,
    ADD_TOKENS_LUA,
)

# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _effective_max(raw: int) -> int:
    # Matches source: raw - int(raw * SAFETY_MARGIN_PERCENT)
    # Note: raw - int(raw*0.10) != int(raw*0.9) due to int truncation
    return raw - int(raw * SAFETY_MARGIN_PERCENT)


# Precompute: raw - int(raw * 0.10)
# 4096 - 409 = 3687, 8192 - 819 = 7373, 16384 - 1638 = 14746
EFFECTIVE = {
    v: _effective_max(c["max_tokens"]) for v, c in VARIANT_TOKEN_BUDGETS.items()
}


def _make_service(redis=None):
    return TokenBudgetService(redis_client=redis)


def _make_mock_redis():
    """Create a mock Redis client with async/sync methods."""
    m = MagicMock()
    m.get = MagicMock(return_value=None)
    m.set = MagicMock()
    m.delete = MagicMock()
    m.hset = MagicMock()
    m.hgetall = MagicMock(return_value={})
    m.rpush = MagicMock()
    m.lrange = MagicMock(return_value=[])
    m.expire = MagicMock()
    m.register_script = MagicMock(return_value=MagicMock())
    return m


# ═══════════════════════════════════════════════════════════════════
# Constants & Config Tests
# ═══════════════════════════════════════════════════════════════════


class TestConstantsAndConfig:
    """Tests for module-level constants and variant configuration."""

    def test_variant_budgets_has_three_variants(self):
        assert set(VARIANT_TOKEN_BUDGETS.keys()) == {
            "mini_parwa",
            "parwa",
            "parwa_high",
        }

    def test_mini_parwa_max_tokens(self):
        assert VARIANT_TOKEN_BUDGETS["mini_parwa"]["max_tokens"] == 4096

    def test_parwa_max_tokens(self):
        assert VARIANT_TOKEN_BUDGETS["parwa"]["max_tokens"] == 8192

    def test_parwa_high_max_tokens(self):
        assert VARIANT_TOKEN_BUDGETS["parwa_high"]["max_tokens"] == 16384

    def test_warning_threshold(self):
        for v in VARIANT_TOKEN_BUDGETS.values():
            assert v["warning_threshold"] == 0.7

    def test_critical_threshold(self):
        for v in VARIANT_TOKEN_BUDGETS.values():
            assert v["critical_threshold"] == 0.9

    def test_safety_margin_is_10_percent(self):
        assert SAFETY_MARGIN_PERCENT == 0.10

    def test_default_variant_is_parwa(self):
        assert DEFAULT_VARIANT_TYPE == "parwa"

    def test_redis_ttl_is_24_hours(self):
        assert REDIS_KEY_TTL_SECONDS == 86400

    def test_reserve_lua_is_string(self):
        assert isinstance(RESERVE_LUA, str)
        assert "INCRBY" in RESERVE_LUA

    def test_finalize_lua_is_string(self):
        assert isinstance(FINALIZE_LUA, str)
        assert "diff" in FINALIZE_LUA

    def test_add_tokens_lua_is_string(self):
        assert isinstance(ADD_TOKENS_LUA, str)
        assert "SET" in ADD_TOKENS_LUA


# ═══════════════════════════════════════════════════════════════════
# Effective Max Tokens Tests
# ═══════════════════════════════════════════════════════════════════


class TestEffectiveMaxTokens:
    """Tests for _effective_max_tokens (safety margin)."""

    def test_mini_parwa_effective_max(self):
        svc = _make_service()
        assert svc._effective_max_tokens("mini_parwa") == EFFECTIVE["mini_parwa"]

    def test_parwa_effective_max(self):
        svc = _make_service()
        assert svc._effective_max_tokens("parwa") == EFFECTIVE["parwa"]

    def test_parwa_high_effective_max(self):
        svc = _make_service()
        assert svc._effective_max_tokens("parwa_high") == EFFECTIVE["parwa_high"]

    def test_unknown_variant_falls_back_to_parwa(self):
        svc = _make_service()
        assert svc._effective_max_tokens("unknown_variant") == EFFECTIVE["parwa"]

    def test_effective_max_matches_source_formula(self):
        # Source formula: raw - int(raw * SAFETY_MARGIN_PERCENT)
        for variant, raw in [
            ("mini_parwa", 4096),
            ("parwa", 8192),
            ("parwa_high", 16384),
        ]:
            svc = _make_service()
            effective = svc._effective_max_tokens(variant)
            expected = raw - int(raw * SAFETY_MARGIN_PERCENT)
            assert (
                effective == expected
            ), f"{variant}: expected {expected}, got {effective}"
            assert effective < raw, f"{variant}: effective must be less than raw"

    def test_variant_config_returns_dict(self):
        svc = _make_service()
        cfg = svc._get_variant_config("parwa")
        assert isinstance(cfg, dict)
        assert "max_tokens" in cfg


# ═══════════════════════════════════════════════════════════════════
# Redis Key Helpers Tests
# ═══════════════════════════════════════════════════════════════════


class TestRedisKeyHelpers:
    """Tests for static Redis key generation methods."""

    def test_key_used(self):
        assert TokenBudgetService._key_used("conv123") == "token_budget:conv123:used"

    def test_key_reserved(self):
        assert (
            TokenBudgetService._key_reserved("conv123")
            == "token_budget:conv123:reserved"
        )

    def test_key_max(self):
        assert TokenBudgetService._key_max("conv123") == "token_budget:conv123:max"

    def test_key_info(self):
        assert TokenBudgetService._key_info("conv123") == "token_budget:conv123:info"

    def test_key_messages(self):
        assert (
            TokenBudgetService._key_messages("conv123")
            == "token_budget:conv123:messages"
        )

    def test_key_used_different_conversation(self):
        assert TokenBudgetService._key_used("abc") != TokenBudgetService._key_used(
            "xyz"
        )


# ═══════════════════════════════════════════════════════════════════
# Service Initialization Tests
# ═══════════════════════════════════════════════════════════════════


class TestServiceInit:
    """Tests for TokenBudgetService initialization."""

    def test_init_without_redis(self):
        svc = _make_service()
        assert svc._redis is None
        assert svc._in_memory == {}
        assert not svc._lua_scripts_loaded

    def test_init_with_redis(self):
        redis = _make_mock_redis()
        svc = _make_service(redis)
        assert svc._redis is redis
        assert not svc._lua_scripts_loaded  # Lazy

    def test_is_redis_available_true(self):
        svc = _make_service(_make_mock_redis())
        assert svc._is_redis_available() is True

    def test_is_redis_available_false(self):
        svc = _make_service()
        assert svc._is_redis_available() is False


# ═══════════════════════════════════════════════════════════════════
# Data Classes Tests
# ═══════════════════════════════════════════════════════════════════


class TestDataClasses:
    """Tests for all dataclasses."""

    def test_token_budget_creation(self):
        now = datetime.now(timezone.utc)
        tb = TokenBudget(
            conversation_id="c1",
            company_id="co1",
            variant_type="parwa",
            max_tokens=7372,
            reserved_tokens=0,
            used_tokens=0,
            available_tokens=7372,
            created_at=now,
            updated_at=now,
        )
        assert tb.max_tokens == 7372
        assert tb.available_tokens == 7372

    def test_reserve_result_success(self):
        r = ReserveResult(
            success=True, reserved_amount=100, remaining_after_reserve=7272, error=None
        )
        assert r.success is True
        assert r.error is None

    def test_reserve_result_failure(self):
        r = ReserveResult(
            success=False,
            reserved_amount=0,
            remaining_after_reserve=0,
            error="overflow",
        )
        assert r.success is False
        assert "overflow" in r.error

    def test_token_budget_status(self):
        s = TokenBudgetStatus(
            conversation_id="c1",
            max_tokens=7372,
            used_tokens=100,
            reserved_tokens=0,
            available_tokens=7272,
            percentage_used=1.36,
            warning_level="normal",
        )
        assert s.warning_level == "normal"

    def test_overflow_check_fit(self):
        o = OverflowCheck(
            can_fit=True,
            remaining_tokens=7000,
            overflow_amount=0,
            truncation_needed=False,
            suggested_truncation_tokens=0,
        )
        assert o.can_fit is True

    def test_overflow_check_no_fit(self):
        o = OverflowCheck(
            can_fit=False,
            remaining_tokens=100,
            overflow_amount=500,
            truncation_needed=True,
            suggested_truncation_tokens=550,
        )
        assert o.can_fit is False
        assert o.truncation_needed is True

    def test_context_strategy(self):
        c = ContextStrategy(
            strategy="keep_all",
            reason="plenty of room",
            tokens_to_remove=0,
            messages_to_remove=0,
            priority_messages=[],
        )
        assert c.strategy == "keep_all"

    def test_token_entry(self):
        t = TokenEntry(
            message_id="m1",
            role="user",
            tokens=50,
            timestamp=datetime.now(timezone.utc),
        )
        assert t.role == "user"
        assert t.tokens == 50


# ═══════════════════════════════════════════════════════════════════
# In-Memory Fallback Tests
# ═══════════════════════════════════════════════════════════════════


class TestInMemoryFallback:
    """Tests for in-memory fallback operations."""

    def test_mem_get_default_zero(self):
        svc = _make_service()
        assert svc._mem_get("conv1", "used") == 0

    def test_mem_set_and_get(self):
        svc = _make_service()
        svc._mem_set("conv1", "used", 100)
        assert svc._mem_get("conv1", "used") == 100

    def test_mem_set_overwrite(self):
        svc = _make_service()
        svc._mem_set("conv1", "used", 100)
        svc._mem_set("conv1", "used", 200)
        assert svc._mem_get("conv1", "used") == 200

    def test_mem_get_info_default_empty(self):
        svc = _make_service()
        assert svc._mem_get_info("conv1") == {}

    def test_mem_set_and_get_info(self):
        svc = _make_service()
        info = {"company_id": "co1", "variant_type": "parwa"}
        svc._mem_set_info("conv1", info)
        assert svc._mem_get_info("conv1")["company_id"] == "co1"

    def test_mem_get_messages_default_empty(self):
        svc = _make_service()
        assert svc._mem_get_messages("conv1") == []

    def test_mem_add_message(self):
        svc = _make_service()
        svc._mem_add_message("conv1", {"message_id": "m1", "tokens": 50})
        msgs = svc._mem_get_messages("conv1")
        assert len(msgs) == 1
        assert msgs[0]["message_id"] == "m1"

    def test_mem_add_multiple_messages(self):
        svc = _make_service()
        svc._mem_add_message("conv1", {"message_id": "m1"})
        svc._mem_add_message("conv1", {"message_id": "m2"})
        assert len(svc._mem_get_messages("conv1")) == 2

    def test_mem_reset(self):
        svc = _make_service()
        svc._mem_set("conv1", "used", 100)
        svc._mem_reset("conv1")
        assert svc._mem_get("conv1", "used") == 0

    def test_mem_conversation_isolation(self):
        svc = _make_service()
        svc._mem_set("conv1", "used", 100)
        svc._mem_set("conv2", "used", 200)
        assert svc._mem_get("conv1", "used") == 100
        assert svc._mem_get("conv2", "used") == 200


# ═══════════════════════════════════════════════════════════════════
# Initialize Budget — In-Memory Tests
# ═══════════════════════════════════════════════════════════════════


class TestInitializeBudgetInMemory:
    """Tests for initialize_budget using in-memory fallback."""

    @pytest.mark.asyncio
    async def test_initialize_parwa(self):
        svc = _make_service()
        budget = await svc.initialize_budget("conv1", "co1", "parwa")
        assert budget.max_tokens == EFFECTIVE["parwa"]
        assert budget.used_tokens == 0
        assert budget.reserved_tokens == 0
        assert budget.available_tokens == EFFECTIVE["parwa"]
        assert budget.variant_type == "parwa"
        assert budget.company_id == "co1"

    @pytest.mark.asyncio
    async def test_initialize_mini_parwa(self):
        svc = _make_service()
        budget = await svc.initialize_budget("conv1", "co1", "mini_parwa")
        assert budget.max_tokens == EFFECTIVE["mini_parwa"]

    @pytest.mark.asyncio
    async def test_initialize_parwa_high(self):
        svc = _make_service()
        budget = await svc.initialize_budget("conv1", "co1", "parwa_high")
        assert budget.max_tokens == EFFECTIVE["parwa_high"]

    @pytest.mark.asyncio
    async def test_initialize_is_idempotent(self):
        svc = _make_service()
        b1 = await svc.initialize_budget("conv1", "co1", "parwa")
        b2 = await svc.initialize_budget("conv1", "co1", "parwa")
        assert b1.max_tokens == b2.max_tokens

    @pytest.mark.asyncio
    async def test_initialize_sets_memory_fields(self):
        svc = _make_service()
        await svc.initialize_budget("conv1", "co1", "parwa")
        assert svc._mem_get("conv1", "max") == EFFECTIVE["parwa"]
        assert svc._mem_get("conv1", "used") == 0
        assert svc._mem_get("conv1", "reserved") == 0

    @pytest.mark.asyncio
    async def test_initialize_stores_metadata(self):
        svc = _make_service()
        await svc.initialize_budget("conv1", "co1", "parwa")
        info = svc._mem_get_info("conv1")
        assert info["company_id"] == "co1"
        assert info["variant_type"] == "parwa"

    @pytest.mark.asyncio
    async def test_initialize_returns_timestamps(self):
        svc = _make_service()
        budget = await svc.initialize_budget("conv1", "co1", "parwa")
        assert isinstance(budget.created_at, datetime)
        assert isinstance(budget.updated_at, datetime)


# ═══════════════════════════════════════════════════════════════════
# Initialize Budget — Redis Tests
# ═══════════════════════════════════════════════════════════════════


class TestInitializeBudgetRedis:
    """Tests for initialize_budget using Redis."""

    @pytest.mark.asyncio
    async def test_initialize_with_redis(self):
        redis = _make_mock_redis()
        svc = _make_service(redis)
        budget = await svc.initialize_budget("conv1", "co1", "parwa")
        assert budget.max_tokens == EFFECTIVE["parwa"]
        assert budget.used_tokens == 0

    @pytest.mark.asyncio
    async def test_initialize_calls_redis_set(self):
        redis = _make_mock_redis()
        svc = _make_service(redis)
        await svc.initialize_budget("conv1", "co1", "parwa")
        assert redis.set.call_count >= 3  # used, reserved, max

    @pytest.mark.asyncio
    async def test_initialize_calls_hset_for_info(self):
        redis = _make_mock_redis()
        svc = _make_service(redis)
        await svc.initialize_budget("conv1", "co1", "parwa")
        redis.hset.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_loads_lua_scripts(self):
        redis = _make_mock_redis()
        svc = _make_service(redis)
        await svc.initialize_budget("conv1", "co1", "parwa")
        assert svc._lua_scripts_loaded is True
        assert redis.register_script.call_count == 3

    @pytest.mark.asyncio
    async def test_initialize_redis_failure_silently_continues(self):
        """BC-008: Redis set fails silently, budget still returned normally."""
        redis = _make_mock_redis()
        redis.set.side_effect = Exception("Redis down")
        svc = _make_service(redis)
        budget = await svc.initialize_budget("conv1", "co1", "parwa")
        # _redis_set catches errors internally, init continues
        assert budget.max_tokens == EFFECTIVE["parwa"]


# ═══════════════════════════════════════════════════════════════════
# Reserve Tokens — In-Memory Tests
# ═══════════════════════════════════════════════════════════════════


class TestReserveTokensInMemory:
    """Tests for reserve_tokens using in-memory fallback."""

    @pytest.mark.asyncio
    async def test_reserve_success(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        result = await svc.reserve_tokens("c1", 1000)
        assert result.success is True
        assert result.reserved_amount == 1000
        assert result.remaining_after_reserve == EFFECTIVE["parwa"] - 1000

    @pytest.mark.asyncio
    async def test_reserve_updates_used(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.reserve_tokens("c1", 500)
        assert svc._mem_get("c1", "used") == 500

    @pytest.mark.asyncio
    async def test_reserve_multiple(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.reserve_tokens("c1", 3000)
        await svc.reserve_tokens("c1", 2000)
        assert svc._mem_get("c1", "used") == 5000
        result = await svc.reserve_tokens("c1", 1000)
        assert result.remaining_after_reserve == EFFECTIVE["parwa"] - 6000

    @pytest.mark.asyncio
    async def test_reserve_overflow(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "mini_parwa")
        max_tokens = EFFECTIVE["mini_parwa"]
        await svc.reserve_tokens("c1", max_tokens - 10)
        result = await svc.reserve_tokens("c1", 100)
        assert result.success is False
        assert result.remaining_after_reserve == 10

    @pytest.mark.asyncio
    async def test_reserve_exact_max(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        result = await svc.reserve_tokens("c1", EFFECTIVE["parwa"])
        assert result.success is True
        assert result.remaining_after_reserve == 0

    @pytest.mark.asyncio
    async def test_reserve_one_over_max(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        result = await svc.reserve_tokens("c1", EFFECTIVE["parwa"] + 1)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_reserve_zero_tokens(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        result = await svc.reserve_tokens("c1", 0)
        assert result.success is True
        assert result.reserved_amount == 0

    @pytest.mark.asyncio
    async def test_reserve_negative_tokens(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        result = await svc.reserve_tokens("c1", -5)
        assert result.success is True
        assert result.reserved_amount == 0

    @pytest.mark.asyncio
    async def test_reserve_without_initialize(self):
        svc = _make_service()
        result = await svc.reserve_tokens("c1", 100)
        assert result.success is False
        assert "not initialized" in result.error.lower()

    @pytest.mark.asyncio
    async def test_reserve_different_conversations_isolated(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.initialize_budget("c2", "co1", "parwa")
        r1 = await svc.reserve_tokens("c1", 5000)
        r2 = await svc.reserve_tokens("c2", 1000)
        assert r1.remaining_after_reserve == EFFECTIVE["parwa"] - 5000
        assert r2.remaining_after_reserve == EFFECTIVE["parwa"] - 1000


# ═══════════════════════════════════════════════════════════════════
# Reserve Tokens — Redis Tests
# ═══════════════════════════════════════════════════════════════════


class TestReserveTokensRedis:
    """Tests for reserve_tokens using Redis."""

    @pytest.mark.asyncio
    async def test_reserve_redis_success(self):
        redis = _make_mock_redis()
        script_mock = MagicMock(return_value=1000)
        redis.register_script = MagicMock(return_value=script_mock)

        def mock_get(key):
            if ":max" in str(key):
                return str(EFFECTIVE["parwa"])
            return "0"

        redis.get = MagicMock(side_effect=mock_get)
        svc = _make_service(redis)
        await svc.initialize_budget("c1", "co1", "parwa")
        redis.get = MagicMock(side_effect=mock_get)
        result = await svc.reserve_tokens("c1", 1000)
        assert result.success is True
        assert result.reserved_amount == 1000

    @pytest.mark.asyncio
    async def test_reserve_redis_overflow(self):
        redis = _make_mock_redis()
        script_mock = MagicMock(return_value=-1)
        redis.register_script = MagicMock(return_value=script_mock)

        def mock_get(key):
            if ":max" in str(key):
                return str(EFFECTIVE["parwa"])
            if ":used" in str(key):
                return str(EFFECTIVE["parwa"])
            return "0"

        redis.get = MagicMock(side_effect=mock_get)
        svc = _make_service(redis)
        await svc.initialize_budget("c1", "co1", "parwa")
        redis.get = MagicMock(side_effect=mock_get)
        result = await svc.reserve_tokens("c1", 10000)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_reserve_redis_not_initialized(self):
        redis = _make_mock_redis()
        redis.get = MagicMock(return_value="0")
        script_mock = MagicMock()
        redis.register_script = MagicMock(return_value=script_mock)
        svc = _make_service(redis)
        result = await svc.reserve_tokens("c1", 100)
        assert result.success is False
        assert "not initialized" in result.error.lower()


# ═══════════════════════════════════════════════════════════════════
# Finalize Tokens — In-Memory Tests
# ═══════════════════════════════════════════════════════════════════


class TestFinalizeTokensInMemory:
    """Tests for finalize_tokens using in-memory fallback."""

    @pytest.mark.asyncio
    async def test_finalize_returns_unused(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.reserve_tokens("c1", 2000)
        await svc.finalize_tokens("c1", reserved=2000, actual=1500)
        assert svc._mem_get("c1", "used") == 1500

    @pytest.mark.asyncio
    async def test_finalize_exact_match(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.reserve_tokens("c1", 1000)
        await svc.finalize_tokens("c1", reserved=1000, actual=1000)
        assert svc._mem_get("c1", "used") == 1000

    @pytest.mark.asyncio
    async def test_finalize_actual_exceeds_reserved(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.reserve_tokens("c1", 500)
        await svc.finalize_tokens("c1", reserved=500, actual=800)
        # Excess charged: used was 500, excess = 800-500=300, new = 500+300=800
        assert svc._mem_get("c1", "used") == 800

    @pytest.mark.asyncio
    async def test_finalize_all_unused(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.reserve_tokens("c1", 3000)
        await svc.finalize_tokens("c1", reserved=3000, actual=0)
        assert svc._mem_get("c1", "used") == 0

    @pytest.mark.asyncio
    async def test_finalize_zero_reserved_zero_actual(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.finalize_tokens("c1", 0, 0)
        assert svc._mem_get("c1", "used") == 0

    @pytest.mark.asyncio
    async def test_finalize_negative_reserved_and_actual(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.finalize_tokens("c1", -1, -1)
        assert svc._mem_get("c1", "used") == 0

    @pytest.mark.asyncio
    async def test_reserve_finalize_cycle(self):
        """Full cycle: init → reserve → finalize → verify available."""
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.reserve_tokens("c1", 2000)
        await svc.finalize_tokens("c1", 2000, 1500)
        status = await svc.get_budget_status("c1")
        assert status.available_tokens == EFFECTIVE["parwa"] - 1500

    @pytest.mark.asyncio
    async def test_finalize_does_not_go_below_zero(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        # Use 100 tokens
        svc._mem_set("c1", "used", 100)
        # Finalize with reserved=200, actual=50 → return 150
        # But used is only 100, so new = max(0, 100-150) = 0
        await svc.finalize_tokens("c1", reserved=200, actual=50)
        assert svc._mem_get("c1", "used") == 0


# ═══════════════════════════════════════════════════════════════════
# Finalize Tokens — Redis Tests
# ═══════════════════════════════════════════════════════════════════


class TestFinalizeTokensRedis:
    """Tests for finalize_tokens using Redis."""

    @pytest.mark.asyncio
    async def test_finalize_redis_calls_script(self):
        redis = _make_mock_redis()
        script_mock = MagicMock(return_value=1000)
        redis.register_script = MagicMock(return_value=script_mock)
        svc = _make_service(redis)
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.finalize_tokens("c1", reserved=2000, actual=1500)
        script_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_finalize_redis_args(self):
        redis = _make_mock_redis()
        script_mock = MagicMock()
        redis.register_script = MagicMock(return_value=script_mock)
        svc = _make_service(redis)
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.finalize_tokens("c1", reserved=2000, actual=1500)
        call_args = script_mock.call_args
        assert call_args[1]["args"] == [2000, 1500]


# ═══════════════════════════════════════════════════════════════════
# Budget Status Tests
# ═══════════════════════════════════════════════════════════════════


class TestBudgetStatus:
    """Tests for get_budget_status."""

    @pytest.mark.asyncio
    async def test_status_after_init(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        status = await svc.get_budget_status("c1")
        assert status.max_tokens == EFFECTIVE["parwa"]
        assert status.used_tokens == 0
        assert status.percentage_used == 0.0
        assert status.warning_level == "normal"

    @pytest.mark.asyncio
    async def test_status_after_usage(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.reserve_tokens("c1", 4000)
        await svc.finalize_tokens("c1", 4000, 4000)
        status = await svc.get_budget_status("c1")
        expected_pct = round(4000 / EFFECTIVE["parwa"] * 100, 2)
        assert status.percentage_used == expected_pct

    @pytest.mark.asyncio
    async def test_status_warning_level_normal(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.reserve_tokens("c1", 100)
        await svc.finalize_tokens("c1", 100, 100)
        status = await svc.get_budget_status("c1")
        assert status.warning_level == "normal"

    @pytest.mark.asyncio
    async def test_status_warning_level_warning(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        # Use 75% of budget
        usage = int(EFFECTIVE["parwa"] * 0.75)
        svc._mem_set("c1", "used", usage)
        status = await svc.get_budget_status("c1")
        assert status.warning_level == "warning"

    @pytest.mark.asyncio
    async def test_status_warning_level_critical(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        usage = int(EFFECTIVE["parwa"] * 0.92)
        svc._mem_set("c1", "used", usage)
        status = await svc.get_budget_status("c1")
        assert status.warning_level == "critical"

    @pytest.mark.asyncio
    async def test_status_warning_level_exhausted(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        svc._mem_set("c1", "used", EFFECTIVE["parwa"])
        status = await svc.get_budget_status("c1")
        assert status.warning_level == "exhausted"

    @pytest.mark.asyncio
    async def test_status_available_tokens(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        svc._mem_set("c1", "used", 2000)
        status = await svc.get_budget_status("c1")
        assert status.available_tokens == EFFECTIVE["parwa"] - 2000

    @pytest.mark.asyncio
    async def test_status_reserved_tokens(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        svc._mem_set("c1", "reserved", 500)
        status = await svc.get_budget_status("c1")
        assert status.reserved_tokens == 500

    @pytest.mark.asyncio
    async def test_status_uninitialized_conversation(self):
        svc = _make_service()
        status = await svc.get_budget_status("nonexistent")
        assert status.max_tokens == 0
        assert status.warning_level == "normal"


# ═══════════════════════════════════════════════════════════════════
# Warning Level Computation Tests
# ═══════════════════════════════════════════════════════════════════


class TestWarningLevelComputation:
    """Tests for _compute_warning_level."""

    def test_normal_below_70(self):
        svc = _make_service()
        assert svc._compute_warning_level("parwa", 50.0) == "normal"

    def test_normal_at_69(self):
        svc = _make_service()
        assert svc._compute_warning_level("parwa", 69.99) == "normal"

    def test_warning_at_70(self):
        svc = _make_service()
        assert svc._compute_warning_level("parwa", 70.0) == "warning"

    def test_warning_at_89(self):
        svc = _make_service()
        assert svc._compute_warning_level("parwa", 89.99) == "warning"

    def test_critical_at_90(self):
        svc = _make_service()
        assert svc._compute_warning_level("parwa", 90.0) == "critical"

    def test_critical_at_99(self):
        svc = _make_service()
        assert svc._compute_warning_level("parwa", 99.99) == "critical"

    def test_exhausted_at_100(self):
        svc = _make_service()
        assert svc._compute_warning_level("parwa", 100.0) == "exhausted"

    def test_exhausted_over_100(self):
        svc = _make_service()
        assert svc._compute_warning_level("parwa", 150.0) == "exhausted"

    def test_zero_percent(self):
        svc = _make_service()
        assert svc._compute_warning_level("parwa", 0.0) == "normal"

    def test_variant_does_not_affect_thresholds(self):
        svc = _make_service()
        # All variants have same thresholds (0.7, 0.9)
        assert svc._compute_warning_level("mini_parwa", 70.0) == "warning"
        assert svc._compute_warning_level("parwa_high", 90.0) == "critical"


# ═══════════════════════════════════════════════════════════════════
# Overflow Check Tests
# ═══════════════════════════════════════════════════════════════════


class TestOverflowCheck:
    """Tests for check_overflow."""

    @pytest.mark.asyncio
    async def test_can_fit_within_budget(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        result = await svc.check_overflow("c1", 1000)
        assert result.can_fit is True
        assert result.overflow_amount == 0
        assert result.truncation_needed is False

    @pytest.mark.asyncio
    async def test_overflow_detected(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        svc._mem_set("c1", "used", EFFECTIVE["parwa"] - 100)
        result = await svc.check_overflow("c1", 500)
        assert result.can_fit is False
        assert result.overflow_amount == 400
        assert result.truncation_needed is True
        assert result.suggested_truncation_tokens > 0

    @pytest.mark.asyncio
    async def test_zero_estimated_tokens(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        result = await svc.check_overflow("c1", 0)
        assert result.can_fit is True

    @pytest.mark.asyncio
    async def test_negative_estimated_tokens(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        result = await svc.check_overflow("c1", -10)
        assert result.can_fit is True

    @pytest.mark.asyncio
    async def test_exact_fit(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        result = await svc.check_overflow("c1", EFFECTIVE["parwa"])
        assert result.can_fit is True
        assert result.remaining_tokens == 0

    @pytest.mark.asyncio
    async def test_one_over(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        result = await svc.check_overflow("c1", EFFECTIVE["parwa"] + 1)
        assert result.can_fit is False
        assert result.overflow_amount == 1

    @pytest.mark.asyncio
    async def test_remaining_tokens_after_fit(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        result = await svc.check_overflow("c1", 1000)
        assert result.remaining_tokens == EFFECTIVE["parwa"] - 1000


# ═══════════════════════════════════════════════════════════════════
# Context Management Strategy Tests
# ═══════════════════════════════════════════════════════════════════


class TestContextManagementStrategy:
    """Tests for get_context_management_strategy."""

    @pytest.mark.asyncio
    async def test_keep_all_when_below_warning(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        strategy = await svc.get_context_management_strategy("c1", 1000)
        assert strategy.strategy == "keep_all"
        assert strategy.tokens_to_remove == 0
        assert strategy.messages_to_remove == 0

    @pytest.mark.asyncio
    async def test_truncate_when_in_warning_zone(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        svc._mem_set("c1", "used", int(EFFECTIVE["parwa"] * 0.75))
        strategy = await svc.get_context_management_strategy("c1", 1000)
        assert strategy.strategy == "truncate_old"

    @pytest.mark.asyncio
    async def test_summarize_when_in_critical_zone(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        svc._mem_set("c1", "used", int(EFFECTIVE["parwa"] * 0.92))
        strategy = await svc.get_context_management_strategy("c1", 1000)
        assert strategy.strategy == "summarize_old"

    @pytest.mark.asyncio
    async def test_sliding_window_when_exhausted(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        svc._mem_set("c1", "used", EFFECTIVE["parwa"])
        strategy = await svc.get_context_management_strategy("c1", 100)
        assert strategy.strategy == "sliding_window"

    @pytest.mark.asyncio
    async def test_priority_messages_includes_system(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        svc._mem_set("c1", "used", int(EFFECTIVE["parwa"] * 0.75))
        # Add some messages
        await svc.add_message_tokens("c1", "sys1", "system", 100)
        await svc.add_message_tokens("c1", "u1", "user", 200)
        strategy = await svc.get_context_management_strategy("c1", 1000)
        assert "sys1" in strategy.priority_messages


# ═══════════════════════════════════════════════════════════════════
# Conversation History Tests
# ═══════════════════════════════════════════════════════════════════


class TestConversationHistory:
    """Tests for conversation history tracking."""

    @pytest.mark.asyncio
    async def test_record_and_retrieve_history(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        entry = TokenEntry(
            message_id="m1",
            role="user",
            tokens=50,
            timestamp=datetime.now(timezone.utc),
        )
        await svc.add_message_tokens("c1", entry.message_id, entry.role, entry.tokens)
        history = await svc.get_conversation_history_tokens("c1")
        assert len(history) == 1
        assert history[0].message_id == "m1"

    @pytest.mark.asyncio
    async def test_multiple_messages_in_order(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        for i in range(5):
            entry = TokenEntry(
                message_id=f"m{i}",
                role="user",
                tokens=10 * (i + 1),
                timestamp=datetime.now(timezone.utc),
            )
            await svc.add_message_tokens(
                "c1", entry.message_id, entry.role, entry.tokens
            )
        history = await svc.get_conversation_history_tokens("c1")
        assert len(history) == 5
        assert history[0].message_id == "m0"
        assert history[4].message_id == "m4"

    @pytest.mark.asyncio
    async def test_history_empty_for_new_conversation(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        history = await svc.get_conversation_history_tokens("c1")
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_total_tokens_calculated(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        for i in range(3):
            entry = TokenEntry(
                message_id=f"m{i}",
                role="user",
                tokens=100,
                timestamp=datetime.now(timezone.utc),
            )
            await svc.add_message_tokens(
                "c1", entry.message_id, entry.role, entry.tokens
            )
        history = await svc.get_conversation_history_tokens("c1")
        total = sum(m.tokens for m in history)
        assert total == 300


# ═══════════════════════════════════════════════════════════════════
# Budget Reset Tests
# ═══════════════════════════════════════════════════════════════════


class TestBudgetReset:
    """Tests for budget reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_clears_budget(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.reserve_tokens("c1", 3000)
        await svc.reset_budget("c1")
        status = await svc.get_budget_status("c1")
        assert status.max_tokens == 0
        assert status.used_tokens == 0

    @pytest.mark.asyncio
    async def test_reset_nonexistent_conversation(self):
        svc = _make_service()
        # Should not raise
        await svc.reset_budget("nonexistent")


# ═══════════════════════════════════════════════════════════════════
# BC-008 Graceful Degradation Tests
# ═══════════════════════════════════════════════════════════════════


class TestGracefulDegradation:
    """Tests for BC-008 graceful degradation (never crash)."""

    @pytest.mark.asyncio
    async def test_status_on_error_returns_safe_default(self):
        svc = _make_service()
        # Force an error in _status_memory by corrupting internal state
        with patch.object(svc, "_status_memory", side_effect=Exception("test error")):
            status = await svc.get_budget_status("c1")
            assert status.max_tokens == 0
            assert status.warning_level == "normal"
            assert status.percentage_used == 0.0

    @pytest.mark.asyncio
    async def test_overflow_check_on_error_returns_can_fit(self):
        svc = _make_service()
        with patch.object(svc, "get_budget_status", side_effect=Exception("test")):
            result = await svc.check_overflow("c1", 1000)
            assert result.can_fit is True

    @pytest.mark.asyncio
    async def test_context_strategy_on_error_returns_keep_all(self):
        svc = _make_service()
        with patch.object(svc, "get_budget_status", side_effect=Exception("test")):
            strategy = await svc.get_context_management_strategy("c1", 1000)
            assert strategy.strategy == "keep_all"

    @pytest.mark.asyncio
    async def test_reserve_on_error_fails_open(self):
        svc = _make_service()
        with patch.object(svc, "_reserve_tokens_memory", side_effect=Exception("fail")):
            result = await svc.reserve_tokens("c1", 100)
            # BC-008: fail open
            assert result.success is True
            assert result.reserved_amount == 100

    @pytest.mark.asyncio
    async def test_finalize_on_error_does_not_raise(self):
        svc = _make_service()
        # Should not raise even with bad inputs
        await svc.finalize_tokens("nonexistent", 100, 50)

    @pytest.mark.asyncio
    async def test_init_redis_errors_silently_caught(self):
        redis = _make_mock_redis()
        redis.set.side_effect = Exception("Redis connection refused")
        redis.hset.side_effect = Exception("Redis connection refused")
        svc = _make_service(redis)
        budget = await svc.initialize_budget("c1", "co1", "parwa")
        # _redis_set/hset catch errors silently, budget still returned normally
        assert budget.max_tokens == EFFECTIVE["parwa"]

    @pytest.mark.asyncio
    async def test_lua_load_failure_forces_memory_fallback(self):
        redis = _make_mock_redis()
        redis.register_script.side_effect = Exception("Script load failed")
        svc = _make_service(redis)
        # Lua load fails → redis set to None → in-memory fallback
        svc._ensure_lua_scripts()
        assert svc._redis is None
        assert not svc._is_redis_available()


# ═══════════════════════════════════════════════════════════════════
# Edge Cases Tests
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_reserve_very_large_amount(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "mini_parwa")
        result = await svc.reserve_tokens("c1", 999999)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_multiple_conversations_independent(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.initialize_budget("c2", "co2", "mini_parwa")
        r1 = await svc.reserve_tokens("c1", EFFECTIVE["parwa"])
        r2 = await svc.reserve_tokens("c2", EFFECTIVE["mini_parwa"])
        assert r1.success is True
        assert r2.success is True
        s1 = await svc.get_budget_status("c1")
        s2 = await svc.get_budget_status("c2")
        assert s1.max_tokens == EFFECTIVE["parwa"]
        assert s2.max_tokens == EFFECTIVE["mini_parwa"]

    @pytest.mark.asyncio
    async def test_reinitialize_resets_counters(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.reserve_tokens("c1", 5000)
        # Re-init should reset
        budget = await svc.initialize_budget("c1", "co1", "parwa")
        assert budget.used_tokens == 0
        assert budget.available_tokens == EFFECTIVE["parwa"]

    @pytest.mark.asyncio
    async def test_overflow_suggestion_includes_buffer(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        svc._mem_set("c1", "used", EFFECTIVE["parwa"] - 50)
        result = await svc.check_overflow("c1", 200)
        assert result.suggested_truncation_tokens > result.overflow_amount  # 10% buffer

    @pytest.mark.asyncio
    async def test_percentage_used_precision(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        svc._mem_set("c1", "used", 1)
        status = await svc.get_budget_status("c1")
        expected = round(1 / EFFECTIVE["parwa"] * 100, 2)
        assert status.percentage_used == expected

    @pytest.mark.asyncio
    async def test_reserve_and_finalize_different_conversations(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        await svc.initialize_budget("c2", "co1", "parwa")
        await svc.reserve_tokens("c1", 3000)
        await svc.finalize_tokens("c2", 1000, 500)  # Different conversation
        s1 = await svc.get_budget_status("c1")
        s2 = await svc.get_budget_status("c2")
        assert s1.used_tokens == 3000
        # c2 had no reserve, finalize adjusts from 0:
        # reserved(1000)>actual(500), diff=500, new=max(0,0-500)=0
        assert s2.used_tokens == 0


# ═══════════════════════════════════════════════════════════════════
# Redis Helper Method Tests
# ═══════════════════════════════════════════════════════════════════


class TestRedisHelpers:
    """Tests for Redis helper methods."""

    @pytest.mark.asyncio
    async def test_redis_get_returns_zero_for_none(self):
        redis = _make_mock_redis()
        redis.get.return_value = None
        svc = _make_service(redis)
        result = await svc._redis_get("key")
        assert result == 0

    @pytest.mark.asyncio
    async def test_redis_get_returns_int_for_string(self):
        redis = _make_mock_redis()
        redis.get.return_value = "500"
        svc = _make_service(redis)
        result = await svc._redis_get("key")
        assert result == 500

    @pytest.mark.asyncio
    async def test_redis_get_returns_zero_on_error(self):
        redis = _make_mock_redis()
        redis.get.side_effect = Exception("connection error")
        svc = _make_service(redis)
        result = await svc._redis_get("key")
        assert result == 0

    @pytest.mark.asyncio
    async def test_redis_get_returns_int_for_int(self):
        redis = _make_mock_redis()
        redis.get.return_value = 500
        svc = _make_service(redis)
        result = await svc._redis_get("key")
        assert result == 500

    @pytest.mark.asyncio
    async def test_redis_set_with_ttl(self):
        redis = _make_mock_redis()
        svc = _make_service(redis)
        await svc._redis_set("key", 100)
        redis.set.assert_called_once_with("key", 100, ex=REDIS_KEY_TTL_SECONDS)

    @pytest.mark.asyncio
    async def test_redis_hgetall_decodes_bytes(self):
        redis = _make_mock_redis()
        redis.hgetall.return_value = {b"key1": b"val1", b"key2": b"val2"}
        svc = _make_service(redis)
        result = await svc._redis_hgetall("key")
        assert result == {"key1": "val1", "key2": "val2"}

    @pytest.mark.asyncio
    async def test_redis_hgetall_handles_string_keys(self):
        redis = _make_mock_redis()
        redis.hgetall.return_value = {"key1": "val1"}
        svc = _make_service(redis)
        result = await svc._redis_hgetall("key")
        assert result == {"key1": "val1"}

    @pytest.mark.asyncio
    async def test_redis_hgetall_empty(self):
        redis = _make_mock_redis()
        redis.hgetall.return_value = {}
        svc = _make_service(redis)
        result = await svc._redis_hgetall("key")
        assert result == {}

    @pytest.mark.asyncio
    async def test_redis_hgetall_on_error(self):
        redis = _make_mock_redis()
        redis.hgetall.side_effect = Exception("error")
        svc = _make_service(redis)
        result = await svc._redis_hgetall("key")
        assert result == {}

    @pytest.mark.asyncio
    async def test_redis_lrange_decodes_bytes(self):
        redis = _make_mock_redis()
        redis.lrange.return_value = [b'{"msg": 1}', b'{"msg": 2}']
        svc = _make_service(redis)
        result = await svc._redis_lrange("key")
        assert result == ['{"msg": 1}', '{"msg": 2}']

    @pytest.mark.asyncio
    async def test_redis_lrange_empty(self):
        redis = _make_mock_redis()
        redis.lrange.return_value = []
        svc = _make_service(redis)
        result = await svc._redis_lrange("key")
        assert result == []

    @pytest.mark.asyncio
    async def test_redis_delete_called(self):
        redis = _make_mock_redis()
        svc = _make_service(redis)
        await svc._redis_delete("key")
        redis.delete.assert_called_once_with("key")

    @pytest.mark.asyncio
    async def test_redis_rpush_and_expire(self):
        redis = _make_mock_redis()
        svc = _make_service(redis)
        await svc._redis_rpush("key", '{"data": 1}')
        redis.rpush.assert_called_once_with("key", '{"data": 1}')
        redis.expire.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# Full Pipeline Integration Tests
# ═══════════════════════════════════════════════════════════════════


class TestFullPipeline:
    """End-to-end pipeline tests."""

    @pytest.mark.asyncio
    async def test_full_reserve_finalize_check_cycle(self):
        svc = _make_service()
        # 1. Initialize
        budget = await svc.initialize_budget("c1", "co1", "parwa")
        assert budget.available_tokens == EFFECTIVE["parwa"]

        # 2. Reserve tokens for LLM call
        reserve = await svc.reserve_tokens("c1", 2000)
        assert reserve.success is True

        # 3. Check overflow before adding more
        overflow = await svc.check_overflow("c1", 5000)
        assert overflow.can_fit is True

        # 4. Finalize with actual usage
        await svc.finalize_tokens("c1", 2000, 1500)

        # 5. Verify status
        status = await svc.get_budget_status("c1")
        assert status.used_tokens == 1500
        assert status.available_tokens == EFFECTIVE["parwa"] - 1500
        assert status.warning_level == "normal"

    @pytest.mark.asyncio
    async def test_full_pipeline_until_exhausted(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "mini_parwa")
        max_t = EFFECTIVE["mini_parwa"]
        chunk = 500
        total_reserved = 0

        # Reserve until overflow
        while True:
            result = await svc.reserve_tokens("c1", chunk)
            if not result.success:
                break
            await svc.finalize_tokens("c1", chunk, chunk)
            total_reserved += chunk

        status = await svc.get_budget_status("c1")
        assert status.warning_level in ("critical", "exhausted")
        assert total_reserved >= max_t - chunk

    @pytest.mark.asyncio
    async def test_pipeline_with_context_strategy(self):
        svc = _make_service()
        await svc.initialize_budget("c1", "co1", "parwa")
        # Use enough to be firmly in warning zone (>70%)
        usage = int(EFFECTIVE["parwa"] * 0.75)
        svc._mem_set("c1", "used", usage)
        status = await svc.get_budget_status("c1")
        assert status.percentage_used >= 70.0

        strategy = await svc.get_context_management_strategy("c1", 500)
        assert strategy.strategy in ("truncate_old", "summarize_old")
        assert strategy.tokens_to_remove >= 0
