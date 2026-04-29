"""
Per-Conversation Token Budget Service (F-156).

Track token usage within a single conversation thread.
Context overflow protection with atomic Redis Lua scripts.

GAP-006 FIX: All token operations use Redis INCRBY with Lua scripts
for atomic check+deduct. Reserve-then-finalize pattern prevents
race conditions between concurrent requests for the same conversation.

Redis key structure:
  token_budget:{conversation_id}:used      — current used tokens (int)
  token_budget:{conversation_id}:reserved  — currently reserved tokens (int)
  token_budget:{conversation_id}:max       — max budget (int)
  token_budget:{conversation_id}:info      — hash with company_id, variant_type, timestamps
  token_budget:{conversation_id}:messages  — list of TokenEntry (JSON)

BC-001: Scoped to company_id / conversation_id.
BC-008: Never crash — graceful degradation with in-memory fallback.
"""

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# VARIANT TOKEN BUDGET CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

VARIANT_TOKEN_BUDGETS: dict[str, dict[str, Any]] = {
    "mini_parwa": {
        "max_tokens": 4096,
        "warning_threshold": 0.7,
        "critical_threshold": 0.9,
    },
    "parwa": {
        "max_tokens": 8192,
        "warning_threshold": 0.7,
        "critical_threshold": 0.9,
    },
    "high_parwa": {
        "max_tokens": 16384,
        "warning_threshold": 0.7,
        "critical_threshold": 0.9,
    },
}

DEFAULT_VARIANT_TYPE: str = "parwa"

# Safety margin: reserve 10% of budget for system prompts and overhead
SAFETY_MARGIN_PERCENT: float = 0.10

# TTL for Redis keys (24 hours — conversations auto-expire)
REDIS_KEY_TTL_SECONDS: int = 86400


# ═══════════════════════════════════════════════════════════════════
# GAP-006 FIX: ATOMIC LUA SCRIPTS
# ═══════════════════════════════════════════════════════════════════

# Atomic reserve: check current + requested <= max, then INCRBY.
# Returns new value on success, -1 on overflow.
RESERVE_LUA: str = """
local key = KEYS[1]
local requested = tonumber(ARGV[1])
local max = tonumber(ARGV[2])
local current = tonumber(redis.call('GET', key) or '0')
if current + requested <= max then
    redis.call('INCRBY', key, requested)
    return current + requested
else
    return -1
end
"""

# Atomic finalize: decrement by the difference (reserved - actual).
# Returns the amount returned to the pool.
FINALIZE_LUA: str = """
local key = KEYS[1]
local reserved = tonumber(ARGV[1])
local actual = tonumber(ARGV[2])
if reserved > actual then
    local diff = reserved - actual
    local current = tonumber(redis.call('GET', key) or '0')
    local new_val = math.max(0, current - diff)
    redis.call('SET', key, new_val)
    return diff
else
    return 0
end
"""

# Atomic add: increment used tokens by a fixed amount.
# Returns new value.
ADD_TOKENS_LUA: str = """
local key = KEYS[1]
local amount = tonumber(ARGV[1])
local current = tonumber(redis.call('GET', key) or '0')
local new_val = current + amount
redis.call('SET', key, new_val)
return new_val
"""


# ═══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TokenBudget:
    """Full budget state for a conversation."""
    conversation_id: str
    company_id: str
    variant_type: str
    max_tokens: int
    reserved_tokens: int
    used_tokens: int
    available_tokens: int
    created_at: datetime
    updated_at: datetime


@dataclass
class ReserveResult:
    """Result of an atomic token reservation attempt."""
    success: bool
    reserved_amount: int
    remaining_after_reserve: int
    error: str | None


@dataclass
class TokenBudgetStatus:
    """Current budget status with warning levels."""
    conversation_id: str
    max_tokens: int
    used_tokens: int
    reserved_tokens: int
    available_tokens: int
    percentage_used: float
    warning_level: str  # normal, warning, critical, exhausted


@dataclass
class OverflowCheck:
    """Result of checking if estimated tokens would overflow."""
    can_fit: bool
    remaining_tokens: int
    overflow_amount: int
    truncation_needed: bool
    suggested_truncation_tokens: int


@dataclass
class ContextStrategy:
    """Recommended strategy for managing context window."""
    strategy: str  # keep_all, truncate_old, summarize_old, sliding_window
    reason: str
    tokens_to_remove: int
    messages_to_remove: int
    priority_messages: list[str]  # message_ids to keep


@dataclass
class TokenEntry:
    """Per-message token usage record."""
    message_id: str
    role: str  # user, assistant, system
    tokens: int
    timestamp: datetime


# ═══════════════════════════════════════════════════════════════════
# TOKEN BUDGET SERVICE
# ═══════════════════════════════════════════════════════════════════

class TokenBudgetService:
    """
    Per-conversation token budget manager with context overflow protection.

    Tracks token usage within a single conversation thread. Uses Redis Lua
    scripts for atomic operations (GAP-006 FIX). Falls back to an
    in-memory dict when Redis is unavailable.

    Reserve-then-finalize pattern:
      1. Call reserve_tokens() before the LLM API call.
      2. Call finalize_tokens() after the LLM responds with actual usage.
      3. Unused reserved tokens are returned to the pool atomically.
    """

    def __init__(self, redis_client: Any = None) -> None:
        self._redis = redis_client
        self._in_memory: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._lua_scripts_loaded: bool = False
        self._reserve_script: Any = None
        self._finalize_script: Any = None
        self._add_script: Any = None

    # ── Lua Script Loading ────────────────────────────────────────

    def _ensure_lua_scripts(self) -> None:
        """Lazily load and cache Lua scripts on the Redis connection.

        Called once on first Redis operation.  Idempotent.
        """
        if self._lua_scripts_loaded or self._redis is None:
            return
        try:
            self._reserve_script = self._redis.register_script(RESERVE_LUA)
            self._finalize_script = self._redis.register_script(FINALIZE_LUA)
            self._add_script = self._redis.register_script(ADD_TOKENS_LUA)
            self._lua_scripts_loaded = True
            logger.debug("token_budget_lua_scripts_loaded")
        except Exception as exc:
            logger.warning(
                "token_budget_lua_load_failed",
                extra={"error": str(exc)},
            )
            self._redis = None  # Force in-memory fallback

    # ── Redis Key Helpers ─────────────────────────────────────────

    @staticmethod
    def _key_used(conversation_id: str) -> str:
        return f"token_budget:{conversation_id}:used"

    @staticmethod
    def _key_reserved(conversation_id: str) -> str:
        return f"token_budget:{conversation_id}:reserved"

    @staticmethod
    def _key_max(conversation_id: str) -> str:
        return f"token_budget:{conversation_id}:max"

    @staticmethod
    def _key_info(conversation_id: str) -> str:
        return f"token_budget:{conversation_id}:info"

    @staticmethod
    def _key_messages(conversation_id: str) -> str:
        return f"token_budget:{conversation_id}:messages"

    # ── Redis vs In-Memory Dispatch ───────────────────────────────

    def _is_redis_available(self) -> bool:
        return self._redis is not None

    async def _redis_get(self, key: str) -> int:
        """Get integer value from Redis, return 0 if missing."""
        try:
            val = self._redis.get(key)
            if val is None:
                return 0
            return int(val)
        except Exception as exc:
            logger.warning(
                "token_budget_redis_get_failed",
                extra={"key": key, "error": str(exc)},
            )
            return 0

    async def _redis_set(self, key: str, value: int) -> None:
        """Set integer value in Redis with TTL."""
        try:
            self._redis.set(key, value, ex=REDIS_KEY_TTL_SECONDS)
        except Exception as exc:
            logger.warning(
                "token_budget_redis_set_failed",
                extra={"key": key, "error": str(exc)},
            )

    async def _redis_hset(self, key: str, mapping: dict[str, str]) -> None:
        """Set hash fields in Redis with TTL."""
        try:
            self._redis.hset(key, mapping=mapping)
            self._redis.expire(key, REDIS_KEY_TTL_SECONDS)
        except Exception as exc:
            logger.warning(
                "token_budget_redis_hset_failed",
                extra={"key": key, "error": str(exc)},
            )

    async def _redis_hgetall(self, key: str) -> dict[str, str]:
        """Get all hash fields from Redis."""
        try:
            result = self._redis.hgetall(key)
            if not result:
                return {}
            # Decode bytes if necessary
            decoded: dict[str, str] = {}
            for k, v in result.items():
                decoded_key = k.decode() if isinstance(k, bytes) else k
                decoded_val = v.decode() if isinstance(v, bytes) else v
                decoded[decoded_key] = decoded_val
            return decoded
        except Exception as exc:
            logger.warning(
                "token_budget_redis_hgetall_failed",
                extra={"key": key, "error": str(exc)},
            )
            return {}

    async def _redis_rpush(self, key: str, value: str) -> None:
        """Push JSON entry to a Redis list with TTL."""
        try:
            self._redis.rpush(key, value)
            self._redis.expire(key, REDIS_KEY_TTL_SECONDS)
        except Exception as exc:
            logger.warning(
                "token_budget_redis_rpush_failed",
                extra={"key": key, "error": str(exc)},
            )

    async def _redis_lrange(self, key: str) -> list[str]:
        """Get all entries from a Redis list."""
        try:
            result = self._redis.lrange(key, 0, -1)
            if not result:
                return []
            return [
                item.decode() if isinstance(item, bytes) else item
                for item in result
            ]
        except Exception as exc:
            logger.warning(
                "token_budget_redis_lrange_failed",
                extra={"key": key, "error": str(exc)},
            )
            return []

    async def _redis_delete(self, key: str) -> None:
        """Delete a Redis key."""
        try:
            self._redis.delete(key)
        except Exception as exc:
            logger.warning(
                "token_budget_redis_delete_failed",
                extra={"key": key, "error": str(exc)},
            )

    # ── In-Memory Fallback ────────────────────────────────────────

    def _mem_get(self, conversation_id: str, field_name: str) -> int:
        bucket = self._in_memory.get(conversation_id, {})
        return int(bucket.get(field_name, 0))

    def _mem_set(
            self,
            conversation_id: str,
            field_name: str,
            value: int) -> None:
        if conversation_id not in self._in_memory:
            self._in_memory[conversation_id] = {}
        self._in_memory[conversation_id][field_name] = value

    def _mem_get_info(self, conversation_id: str) -> dict[str, str]:
        bucket = self._in_memory.get(conversation_id, {})
        return bucket.get("info", {})

    def _mem_set_info(self, conversation_id: str,
                      info: dict[str, str]) -> None:
        if conversation_id not in self._in_memory:
            self._in_memory[conversation_id] = {}
        self._in_memory[conversation_id]["info"] = info

    def _mem_get_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        bucket = self._in_memory.get(conversation_id, {})
        return list(bucket.get("messages", []))

    def _mem_add_message(self, conversation_id: str,
                         entry: dict[str, Any]) -> None:
        if conversation_id not in self._in_memory:
            self._in_memory[conversation_id] = {}
        if "messages" not in self._in_memory[conversation_id]:
            self._in_memory[conversation_id]["messages"] = []
        self._in_memory[conversation_id]["messages"].append(entry)

    def _mem_reset(self, conversation_id: str) -> None:
        self._in_memory.pop(conversation_id, None)

    # ── Variant Config ────────────────────────────────────────────

    def _get_variant_config(self, variant_type: str) -> dict[str, Any]:
        """Get budget config for a variant type, defaulting to 'parwa'."""
        return VARIANT_TOKEN_BUDGETS.get(
            variant_type, VARIANT_TOKEN_BUDGETS[DEFAULT_VARIANT_TYPE])

    def _effective_max_tokens(self, variant_type: str) -> int:
        """Return max tokens minus safety margin."""
        config = self._get_variant_config(variant_type)
        raw_max = config["max_tokens"]
        margin = int(raw_max * SAFETY_MARGIN_PERCENT)
        return raw_max - margin

    # ── Public API: Initialize Budget ─────────────────────────────

    async def initialize_budget(
        self,
        conversation_id: str,
        company_id: str,
        variant_type: str,
    ) -> TokenBudget:
        """
        Set initial token budget for a conversation.

        Sets max, used (0), and reserved (0) counters. Stores metadata
        in the info hash. Idempotent — safe to call multiple times.

        Args:
            conversation_id: Unique conversation identifier.
            company_id: Tenant identifier (BC-001).
            variant_type: One of mini_parwa, parwa, high_parwa.

        Returns:
            TokenBudget with the initialized state.
        """
        try:
            now = datetime.now(timezone.utc)
            effective_max = self._effective_max_tokens(variant_type)
            now_iso = now.isoformat()

            if self._is_redis_available():
                self._ensure_lua_scripts()
                used_key = self._key_used(conversation_id)
                reserved_key = self._key_reserved(conversation_id)
                max_key = self._key_max(conversation_id)
                info_key = self._key_info(conversation_id)

                # Set budget counters with TTL
                await self._redis_set(used_key, 0)
                await self._redis_set(reserved_key, 0)
                await self._redis_set(max_key, effective_max)

                # Store metadata
                await self._redis_hset(info_key, {
                    "company_id": company_id,
                    "variant_type": variant_type,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                })
            else:
                # In-memory fallback (thread-safe)
                with self._lock:
                    self._mem_set(conversation_id, "used", 0)
                    self._mem_set(conversation_id, "reserved", 0)
                    self._mem_set(conversation_id, "max", effective_max)
                    self._mem_set_info(conversation_id, {
                        "company_id": company_id,
                        "variant_type": variant_type,
                        "created_at": now_iso,
                        "updated_at": now_iso,
                    })

            budget = TokenBudget(
                conversation_id=conversation_id,
                company_id=company_id,
                variant_type=variant_type,
                max_tokens=effective_max,
                reserved_tokens=0,
                used_tokens=0,
                available_tokens=effective_max,
                created_at=now,
                updated_at=now,
            )

            logger.info(
                "token_budget_initialized",
                extra={
                    "conversation_id": conversation_id,
                    "company_id": company_id,
                    "variant_type": variant_type,
                    "max_tokens": effective_max,
                },
            )

            return budget

        except Exception as exc:
            logger.error(
                "token_budget_init_failed",
                extra={
                    "conversation_id": conversation_id,
                    "company_id": company_id,
                    "error": str(exc),
                },
            )
            # BC-008: Return a minimal budget rather than crashing
            now = datetime.now(timezone.utc)
            return TokenBudget(
                conversation_id=conversation_id,
                company_id=company_id,
                variant_type=variant_type,
                max_tokens=0,
                reserved_tokens=0,
                used_tokens=0,
                available_tokens=0,
                created_at=now,
                updated_at=now,
            )

    # ── Public API: Reserve Tokens ────────────────────────────────

    async def reserve_tokens(
        self,
        conversation_id: str,
        tokens: int,
    ) -> ReserveResult:
        """
        Atomically reserve tokens before an LLM API call.

        Uses the RESERVE_LUA script (GAP-006 FIX) to atomically
        check+increment. If the reservation would exceed the budget,
        returns failure with remaining capacity info.

        Args:
            conversation_id: Unique conversation identifier.
            tokens: Number of tokens to reserve (estimated).

        Returns:
            ReserveResult with success/failure and remaining capacity.
        """
        try:
            if tokens <= 0:
                # Zero or negative tokens always succeed trivially
                return ReserveResult(
                    success=True,
                    reserved_amount=0,
                    remaining_after_reserve=0,
                    error=None,
                )

            if self._is_redis_available():
                self._ensure_lua_scripts()
                return await self._reserve_tokens_redis(conversation_id, tokens)
            else:
                return self._reserve_tokens_memory(conversation_id, tokens)

        except Exception as exc:
            logger.error(
                "token_reserve_failed",
                extra={
                    "conversation_id": conversation_id,
                    "tokens": tokens,
                    "error": str(exc),
                },
            )
            # BC-008: Fail open — allow the request but log error
            return ReserveResult(
                success=True,
                reserved_amount=tokens,
                remaining_after_reserve=0,
                error=f"Reservation error (graceful degradation): {str(exc)}",
            )

    async def _reserve_tokens_redis(
        self,
        conversation_id: str,
        tokens: int,
    ) -> ReserveResult:
        """Reserve tokens using atomic Redis Lua script."""
        used_key = self._key_used(conversation_id)
        max_key = self._key_max(conversation_id)
        max_tokens = await self._redis_get(max_key)

        if max_tokens <= 0:
            return ReserveResult(
                success=False,
                reserved_amount=0,
                remaining_after_reserve=0,
                error="Budget not initialized (max_tokens is 0)",
            )

        result = self._reserve_script(
            keys=[used_key], args=[
                tokens, max_tokens])

        if result == -1:
            # Overflow: reservation denied
            current_used = await self._redis_get(used_key)
            remaining = max(0, max_tokens - current_used)
            return ReserveResult(
                success=False,
                reserved_amount=0,
                remaining_after_reserve=remaining,
                error=(
                    f"Token budget overflow: cannot reserve {tokens} tokens. "
                    f"Remaining capacity: {remaining}. "
                    "Consider truncating older messages."
                ),
            )

        new_used = int(result)
        remaining = max(0, max_tokens - new_used)

        logger.debug(
            "token_reserve_success",
            extra={
                "conversation_id": conversation_id,
                "reserved": tokens,
                "new_used": new_used,
                "remaining": remaining,
            },
        )

        return ReserveResult(
            success=True,
            reserved_amount=tokens,
            remaining_after_reserve=remaining,
            error=None,
        )

    def _reserve_tokens_memory(
        self,
        conversation_id: str,
        tokens: int,
    ) -> ReserveResult:
        """Reserve tokens using thread-safe in-memory counter."""
        with self._lock:
            max_tokens = self._mem_get(conversation_id, "max")
            current_used = self._mem_get(conversation_id, "used")

            if max_tokens <= 0:
                return ReserveResult(
                    success=False,
                    reserved_amount=0,
                    remaining_after_reserve=0,
                    error="Budget not initialized (max_tokens is 0)",
                )

            if current_used + tokens > max_tokens:
                remaining = max(0, max_tokens - current_used)
                return ReserveResult(
                    success=False,
                    reserved_amount=0,
                    remaining_after_reserve=remaining,
                    error=(
                        f"Token budget overflow: cannot reserve {tokens} tokens. "
                        f"Remaining capacity: {remaining}."
                    ),
                )

            self._mem_set(conversation_id, "used", current_used + tokens)
            new_remaining = max(0, max_tokens - current_used - tokens)

            return ReserveResult(
                success=True,
                reserved_amount=tokens,
                remaining_after_reserve=new_remaining,
                error=None,
            )

    # ── Public API: Finalize Tokens ───────────────────────────────

    async def finalize_tokens(
        self,
        conversation_id: str,
        reserved: int,
        actual: int,
    ) -> None:
        """
        Finalize token usage after an LLM call completes.

        Returns unused reserved tokens to the budget pool using the
        FINALIZE_LUA atomic script. If actual > reserved (rare),
        the excess is charged but does not overflow.

        Args:
            conversation_id: Unique conversation identifier.
            reserved: Tokens that were reserved before the call.
            actual: Tokens actually consumed by the LLM.
        """
        try:
            if reserved <= 0 and actual <= 0:
                return

            if self._is_redis_available():
                self._ensure_lua_scripts()
                await self._finalize_tokens_redis(conversation_id, reserved, actual)
            else:
                self._finalize_tokens_memory(conversation_id, reserved, actual)

            logger.debug(
                "token_finalize_success",
                extra={
                    "conversation_id": conversation_id,
                    "reserved": reserved,
                    "actual": actual,
                    "returned": max(0, reserved - actual),
                },
            )

        except Exception as exc:
            logger.error(
                "token_finalize_failed",
                extra={
                    "conversation_id": conversation_id,
                    "reserved": reserved,
                    "actual": actual,
                    "error": str(exc),
                },
            )
            # BC-008: Don't crash, but budget may be slightly off

    async def _finalize_tokens_redis(
        self,
        conversation_id: str,
        reserved: int,
        actual: int,
    ) -> None:
        """Finalize tokens using atomic Redis Lua script."""
        used_key = self._key_used(conversation_id)
        # The finalize script decrements by (reserved - actual)
        # to return unused tokens to the pool.
        self._finalize_script(keys=[used_key], args=[reserved, actual])

    def _finalize_tokens_memory(
        self,
        conversation_id: str,
        reserved: int,
        actual: int,
    ) -> None:
        """Finalize tokens using thread-safe in-memory counter."""
        with self._lock:
            current_used = self._mem_get(conversation_id, "used")
            if reserved > actual:
                diff = reserved - actual
                new_used = max(0, current_used - diff)
            else:
                # Actual exceeded reserved: charge the excess
                excess = actual - reserved
                new_used = current_used + excess
            self._mem_set(conversation_id, "used", new_used)

    # ── Public API: Budget Status ─────────────────────────────────

    async def get_budget_status(
            self, conversation_id: str) -> TokenBudgetStatus:
        """
        Get current budget status for a conversation.

        Returns usage stats, remaining capacity, percentage used,
        and a warning level (normal, warning, critical, exhausted).

        Args:
            conversation_id: Unique conversation identifier.

        Returns:
            TokenBudgetStatus with full state snapshot.
        """
        try:
            if self._is_redis_available():
                return await self._status_redis(conversation_id)
            else:
                return self._status_memory(conversation_id)

        except Exception as exc:
            logger.error(
                "budget_status_failed",
                extra={
                    "conversation_id": conversation_id,
                    "error": str(exc),
                },
            )
            return TokenBudgetStatus(
                conversation_id=conversation_id,
                max_tokens=0,
                used_tokens=0,
                reserved_tokens=0,
                available_tokens=0,
                percentage_used=0.0,
                warning_level="normal",
            )

    async def _status_redis(self, conversation_id: str) -> TokenBudgetStatus:
        """Get budget status from Redis."""
        used_key = self._key_used(conversation_id)
        reserved_key = self._key_reserved(conversation_id)
        max_key = self._key_max(conversation_id)
        info_key = self._key_info(conversation_id)

        used = await self._redis_get(used_key)
        reserved = await self._redis_get(reserved_key)
        max_tokens = await self._redis_get(max_key)
        info = await self._redis_hgetall(info_key)

        variant_type = info.get("variant_type", DEFAULT_VARIANT_TYPE)
        available = max(0, max_tokens - used)
        pct = (used / max_tokens * 100.0) if max_tokens > 0 else 0.0
        warning = self._compute_warning_level(variant_type, pct)

        return TokenBudgetStatus(
            conversation_id=conversation_id,
            max_tokens=max_tokens,
            used_tokens=used,
            reserved_tokens=reserved,
            available_tokens=available,
            percentage_used=round(pct, 2),
            warning_level=warning,
        )

    def _status_memory(self, conversation_id: str) -> TokenBudgetStatus:
        """Get budget status from in-memory store."""
        used = self._mem_get(conversation_id, "used")
        reserved = self._mem_get(conversation_id, "reserved")
        max_tokens = self._mem_get(conversation_id, "max")
        info = self._mem_get_info(conversation_id)

        variant_type = info.get("variant_type", DEFAULT_VARIANT_TYPE)
        available = max(0, max_tokens - used)
        pct = (used / max_tokens * 100.0) if max_tokens > 0 else 0.0
        warning = self._compute_warning_level(variant_type, pct)

        return TokenBudgetStatus(
            conversation_id=conversation_id,
            max_tokens=max_tokens,
            used_tokens=used,
            reserved_tokens=reserved,
            available_tokens=available,
            percentage_used=round(pct, 2),
            warning_level=warning,
        )

    def _compute_warning_level(self, variant_type: str, pct: float) -> str:
        """Determine warning level based on percentage used."""
        config = self._get_variant_config(variant_type)
        critical_threshold = config["critical_threshold"] * 100.0
        warning_threshold = config["warning_threshold"] * 100.0

        if pct >= 100.0:
            return "exhausted"
        if pct >= critical_threshold:
            return "critical"
        if pct >= warning_threshold:
            return "warning"
        return "normal"

    # ── Public API: Check Overflow ────────────────────────────────

    async def check_overflow(
        self,
        conversation_id: str,
        estimated_tokens: int,
    ) -> OverflowCheck:
        """
        Check if adding estimated tokens would overflow the budget.

        Returns whether the tokens can fit, remaining capacity,
        overflow amount, and whether truncation is needed.

        Args:
            conversation_id: Unique conversation identifier.
            estimated_tokens: Estimated tokens for the next message.

        Returns:
            OverflowCheck with detailed analysis.
        """
        try:
            status = await self.get_budget_status(conversation_id)

            if estimated_tokens <= 0:
                return OverflowCheck(
                    can_fit=True,
                    remaining_tokens=status.available_tokens,
                    overflow_amount=0,
                    truncation_needed=False,
                    suggested_truncation_tokens=0,
                )

            if status.available_tokens >= estimated_tokens:
                return OverflowCheck(
                    can_fit=True,
                    remaining_tokens=status.available_tokens
                    - estimated_tokens,
                    overflow_amount=0,
                    truncation_needed=False,
                    suggested_truncation_tokens=0,
                )

            # Overflow
            overflow = estimated_tokens - status.available_tokens
            # Suggest truncating enough old messages to fit
            truncation = overflow + int(estimated_tokens * 0.1)  # 10% buffer

            return OverflowCheck(
                can_fit=False,
                remaining_tokens=status.available_tokens,
                overflow_amount=overflow,
                truncation_needed=True,
                suggested_truncation_tokens=truncation,
            )

        except Exception as exc:
            logger.error(
                "overflow_check_failed",
                extra={
                    "conversation_id": conversation_id,
                    "estimated_tokens": estimated_tokens,
                    "error": str(exc)},
            )
            # BC-008: Assume can fit on error
            return OverflowCheck(
                can_fit=True,
                remaining_tokens=0,
                overflow_amount=0,
                truncation_needed=False,
                suggested_truncation_tokens=0,
            )

    # ── Public API: Context Management Strategy ───────────────────

    async def get_context_management_strategy(
        self,
        conversation_id: str,
        estimated_new_tokens: int,
    ) -> ContextStrategy:
        """
        Determine the best strategy for managing context window.

        When approaching the token limit, suggests one of:
        - keep_all: plenty of room, no action needed.
        - truncate_old: remove oldest messages to free space.
        - summarize_old: summarize older messages (preserve context).
        - sliding_window: keep only recent messages in a fixed window.

        Args:
            conversation_id: Unique conversation identifier.
            estimated_new_tokens: Estimated tokens for the new message.

        Returns:
            ContextStrategy with recommended approach.
        """
        try:
            status = await self.get_budget_status(conversation_id)
            messages = await self.get_conversation_history_tokens(conversation_id)
            pct = status.percentage_used
            variant_type = "parwa"  # default for config lookup
            info = await self._get_info(conversation_id)
            if info:
                variant_type = info.get("variant_type", variant_type)

            config = self._get_variant_config(variant_type)
            warning_threshold = config["warning_threshold"] * 100.0
            critical_threshold = config["critical_threshold"] * 100.0

            # Strategy selection based on usage level
            if pct < warning_threshold:
                return ContextStrategy(
                    strategy="keep_all",
                    reason=(
                        f"Usage at {pct:.1f}% (below {warning_threshold:.0f}% "
                        "warning threshold). No context management needed."
                    ),
                    tokens_to_remove=0,
                    messages_to_remove=0,
                    priority_messages=[],
                )

            if pct < critical_threshold:
                # Warning zone: consider light truncation of oldest messages
                return await self._compute_truncate_strategy(
                    conversation_id=conversation_id,
                    messages=messages,
                    estimated_new_tokens=estimated_new_tokens,
                    status=status,
                    strategy_type="truncate_old",
                    reason=(
                        f"Usage at {pct:.1f}% (warning zone). "
                        "Recommend truncating oldest messages to free space."
                    ),
                )

            if pct < 100.0:
                # Critical zone: aggressive truncation or summarization
                return await self._compute_summarize_strategy(
                    conversation_id=conversation_id,
                    messages=messages,
                    estimated_new_tokens=estimated_new_tokens,
                    status=status,
                    reason=(
                        f"Usage at {pct:.1f}% (critical zone). "
                        "Recommend summarizing older messages to preserve context."
                    ),
                )

            # Exhausted: sliding window as last resort
            return await self._compute_sliding_window_strategy(
                conversation_id=conversation_id,
                messages=messages,
                estimated_new_tokens=estimated_new_tokens,
                status=status,
                reason=(
                    f"Usage at {pct:.1f}% (exhausted). "
                    "Must use sliding window — only keeping recent messages."
                ),
            )

        except Exception as exc:
            logger.error(
                "context_strategy_failed",
                extra={
                    "conversation_id": conversation_id,
                    "estimated_new_tokens": estimated_new_tokens,
                    "error": str(exc),
                },
            )
            # BC-008: Safe default — keep all, don't truncate
            return ContextStrategy(
                strategy="keep_all",
                reason=f"Strategy computation error (graceful degradation): {
                    str(exc)}",
                tokens_to_remove=0,
                messages_to_remove=0,
                priority_messages=[],
            )

    async def _compute_truncate_strategy(
        self,
        conversation_id: str,
        messages: list[TokenEntry],
        estimated_new_tokens: int,
        status: TokenBudgetStatus,
        strategy_type: str,
        reason: str,
    ) -> ContextStrategy:
        """Compute a truncation strategy removing oldest non-system messages."""
        tokens_needed = max(0, estimated_new_tokens - status.available_tokens)
        tokens_to_remove = tokens_needed + \
            int(tokens_needed * 0.15)  # 15% buffer

        # Identify removable messages (oldest first, keep system messages)
        non_system = [m for m in messages if m.role != "system"]
        system_ids = [m.message_id for m in messages if m.role == "system"]

        tokens_accumulated = 0
        messages_to_remove = 0
        remove_ids: list[str] = []

        for msg in non_system:
            if tokens_accumulated >= tokens_to_remove:
                break
            tokens_accumulated += msg.tokens
            messages_to_remove += 1
            remove_ids.append(msg.message_id)

        # Priority messages: keep all system messages and the most recent
        priority = list(system_ids)
        if messages:
            # Keep the last 2 user/assistant exchanges
            recent = [m.message_id for m in messages[-4:]]
            priority.extend(recent)
            # deduplicate, preserve order
            priority = list(dict.fromkeys(priority))

        return ContextStrategy(
            strategy=strategy_type,
            reason=reason,
            tokens_to_remove=tokens_accumulated,
            messages_to_remove=messages_to_remove,
            priority_messages=priority,
        )

    async def _compute_summarize_strategy(
        self,
        conversation_id: str,
        messages: list[TokenEntry],
        estimated_new_tokens: int,
        status: TokenBudgetStatus,
        reason: str,
    ) -> ContextStrategy:
        """Compute a summarization strategy for older messages."""
        tokens_needed = max(0, estimated_new_tokens - status.available_tokens)
        tokens_to_remove = tokens_needed + \
            int(tokens_needed * 0.2)  # 20% buffer

        non_system = [m for m in messages if m.role != "system"]
        system_ids = [m.message_id for m in messages if m.role == "system"]

        tokens_accumulated = 0
        messages_to_remove = 0

        for msg in non_system:
            if tokens_accumulated >= tokens_to_remove:
                break
            tokens_accumulated += msg.tokens
            messages_to_remove += 1

        priority = list(system_ids)
        if messages:
            # Keep the last 3 user/assistant exchanges
            recent = [m.message_id for m in messages[-6:]]
            priority.extend(recent)
            priority = list(dict.fromkeys(priority))

        return ContextStrategy(
            strategy="summarize_old",
            reason=reason,
            tokens_to_remove=tokens_accumulated,
            messages_to_remove=messages_to_remove,
            priority_messages=priority,
        )

    async def _compute_sliding_window_strategy(
        self,
        conversation_id: str,
        messages: list[TokenEntry],
        estimated_new_tokens: int,
        status: TokenBudgetStatus,
        reason: str,
    ) -> ContextStrategy:
        """Compute a sliding window strategy keeping only recent messages."""
        max_tokens = status.max_tokens
        window_budget = int(max_tokens * 0.6)  # Use 60% for window
        tokens_target = max(0, window_budget - estimated_new_tokens)

        system_ids = [m.message_id for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        # Keep newest messages until we fill the window budget
        kept_tokens = 0
        kept_count = 0
        for msg in reversed(non_system):
            if kept_tokens + msg.tokens > tokens_target:
                break
            kept_tokens += msg.tokens
            kept_count += 1

        total_non_system = len(non_system)
        messages_to_remove = max(0, total_non_system - kept_count)
        tokens_to_remove = sum(
            m.tokens for m in non_system[:messages_to_remove])

        priority = list(system_ids)
        # Keep the messages that fit in the window
        recent_kept = [
            m.message_id for m in non_system[-kept_count:]] if kept_count > 0 else []
        priority.extend(recent_kept)
        priority = list(dict.fromkeys(priority))

        return ContextStrategy(
            strategy="sliding_window",
            reason=reason,
            tokens_to_remove=tokens_to_remove,
            messages_to_remove=messages_to_remove,
            priority_messages=priority,
        )

    async def _get_info(self, conversation_id: str) -> dict[str, str]:
        """Get the info hash for a conversation."""
        if self._is_redis_available():
            return await self._redis_hgetall(self._key_info(conversation_id))
        return self._mem_get_info(conversation_id)

    # ── Public API: Reset Budget ──────────────────────────────────

    async def reset_budget(self, conversation_id: str) -> None:
        """
        Reset all token counters for a conversation.

        Clears used, reserved, max, info, and message history.
        Used when a conversation is closed or restarted.

        Args:
            conversation_id: Unique conversation identifier.
        """
        try:
            if self._is_redis_available():
                await self._redis_delete(self._key_used(conversation_id))
                await self._redis_delete(self._key_reserved(conversation_id))
                await self._redis_delete(self._key_max(conversation_id))
                await self._redis_delete(self._key_info(conversation_id))
                await self._redis_delete(self._key_messages(conversation_id))
            else:
                with self._lock:
                    self._mem_reset(conversation_id)

            logger.info(
                "token_budget_reset",
                extra={"conversation_id": conversation_id},
            )

        except Exception as exc:
            logger.error(
                "token_budget_reset_failed",
                extra={
                    "conversation_id": conversation_id,
                    "error": str(exc),
                },
            )
            # BC-008: Don't crash

    # ── Public API: Conversation History Tokens ───────────────────

    async def get_conversation_history_tokens(
        self,
        conversation_id: str,
    ) -> list[TokenEntry]:
        """
        Get per-message token usage for a conversation.

        Returns a list of TokenEntry records in chronological order,
        each containing message_id, role, token count, and timestamp.

        Args:
            conversation_id: Unique conversation identifier.

        Returns:
            List of TokenEntry records.
        """
        try:
            if self._is_redis_available():
                raw_entries = await self._redis_lrange(
                    self._key_messages(conversation_id),
                )
            else:
                raw_entries = [
                    json.dumps(entry)
                    for entry in self._mem_get_messages(conversation_id)
                ]

            entries: list[TokenEntry] = []
            for raw in raw_entries:
                try:
                    data = json.loads(raw)
                    entry = TokenEntry(
                        message_id=data["message_id"],
                        role=data["role"],
                        tokens=int(data["tokens"]),
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                    )
                    entries.append(entry)
                except (json.JSONDecodeError, KeyError, ValueError) as parse_err:
                    logger.warning(
                        "token_entry_parse_failed",
                        extra={"raw": raw, "error": str(parse_err)},
                    )
                    continue

            return entries

        except Exception as exc:
            logger.error(
                "conversation_history_tokens_failed",
                extra={
                    "conversation_id": conversation_id,
                    "error": str(exc),
                },
            )
            return []

    # ── Public API: Add Message Tokens ────────────────────────────

    async def add_message_tokens(
        self,
        conversation_id: str,
        message_id: str,
        role: str,
        tokens: int,
    ) -> None:
        """
        Record per-message token usage for a conversation.

        Appends a TokenEntry to the message history list. This is
        separate from the reserve/finalize flow and used for
        tracking and analytics purposes.

        Args:
            conversation_id: Unique conversation identifier.
            message_id: Unique message identifier.
            role: Message role (user, assistant, system).
            tokens: Token count for this message.
        """
        try:
            now = datetime.now(timezone.utc).isoformat()
            entry_data = {
                "message_id": message_id,
                "role": role,
                "tokens": tokens,
                "timestamp": now,
            }
            entry_json = json.dumps(entry_data)

            if self._is_redis_available():
                await self._redis_rpush(
                    self._key_messages(conversation_id),
                    entry_json,
                )
            else:
                with self._lock:
                    self._mem_add_message(conversation_id, entry_data)

            logger.debug(
                "message_tokens_recorded",
                extra={
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "role": role,
                    "tokens": tokens,
                },
            )

        except Exception as exc:
            logger.error(
                "add_message_tokens_failed",
                extra={
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "error": str(exc),
                },
            )
            # BC-008: Don't crash

    # ── Public API: Bulk Helpers ──────────────────────────────────

    async def get_total_message_tokens(
        self,
        conversation_id: str,
    ) -> int:
        """Sum all recorded message tokens for a conversation."""
        entries = await self.get_conversation_history_tokens(conversation_id)
        return sum(e.tokens for e in entries)

    async def get_message_count(self, conversation_id: str) -> int:
        """Count the number of recorded messages for a conversation."""
        entries = await self.get_conversation_history_tokens(conversation_id)
        return len(entries)

    async def get_tokens_by_role(
        self,
        conversation_id: str,
    ) -> dict[str, int]:
        """Get token counts grouped by role (user, assistant, system)."""
        entries = await self.get_conversation_history_tokens(conversation_id)
        role_totals: dict[str, int] = {}
        for entry in entries:
            role_totals[entry.role] = role_totals.get(
                entry.role, 0) + entry.tokens
        return role_totals


# ═══════════════════════════════════════════════════════════════════
# MODULE-LEVEL SINGLETON & FACTORY
# ═══════════════════════════════════════════════════════════════════

_token_budget_service: TokenBudgetService | None = None


def get_token_budget_service(redis_client: Any = None) -> TokenBudgetService:
    """Get or create the singleton TokenBudgetService instance."""
    global _token_budget_service
    if _token_budget_service is None:
        _token_budget_service = TokenBudgetService(redis_client=redis_client)
    return _token_budget_service


def reset_token_budget_service() -> None:
    """Reset the singleton (used in tests)."""
    global _token_budget_service
    _token_budget_service = None
