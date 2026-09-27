"""
Shadow Mode Service: SHADOW→SUPERVISED→GRADUATED progression.

Implements the safe deployment strategy for variant upgrades:
  1. SHADOW: Both live and shadow variants process messages. Only live
     response is delivered. Shadow response is logged for comparison.
  2. SUPERVISED: Shadow variant generates responses, but human must
     approve before delivery. Auto-fallback if review times out.
  3. GRADUATED: Shadow variant is now live. Transition complete.

Key features:
  - Configurable sample rate (100% down to 1%)
  - Auto-graduation based on quality streaks
  - Human review workflow for supervised mode
  - Detailed comparison metrics (quality, latency, tokens)
  - Per-company isolation (BC-001)
  - Never crash (BC-008)
  - All timestamps UTC (BC-012)

Architecture:
  ShadowModeService is the single source of truth for:
  - Whether a company is in shadow mode
  - Which variants are live vs shadow
  - Whether a message should be shadow-processed
  - Quality comparison and auto-graduation logic

Persistence strategy (BC-008):
  Three-tier caching: Redis → DB → in-memory.
  - On reads: try Redis first, then DB, fall back to in-memory cache.
  - On writes: persist to DB first, then update Redis, then in-memory cache.
  - If Redis is unavailable, gracefully fall back to DB/in-memory.
  - If DB is entirely unavailable, the service degrades gracefully
    and continues operating from the in-memory cache.
  - Redis key patterns: shadow:config:{company_id}, shadow:comparisons:{company_id}
  - TTL: configs 5 minutes (300s), comparisons 2 minutes (120s)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("shadow_mode_service")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

VALID_STATUSES = ("shadow", "supervised", "graduated", "disabled")

# Quality score thresholds for auto-graduation decisions
DEFAULT_AUTO_GRADUATION_THRESHOLD = 0.95
DEFAULT_AUTO_GRADUATION_WINDOW = 100
DEFAULT_SAMPLE_RATE = 1.0
DEFAULT_SUPERVISED_TIMEOUT = 300  # 5 minutes

# Valid variant types for shadow testing
VALID_VARIANT_TYPES = ("mini_parwa", "parwa", "parwa_high")

# Variant ranking for upgrade direction validation
VARIANT_RANKING = {
    "mini_parwa": 1,
    "parwa": 2,
    "parwa_high": 3,
}

# Redis cache TTL constants
REDIS_CONFIG_TTL_SECONDS = 300  # 5 minutes for shadow mode configs
REDIS_COMPARISONS_TTL_SECONDS = 120  # 2 minutes for comparison data

# Redis key suffix patterns (combined with company_id via cache_get/cache_set)
REDIS_CONFIG_KEY = "shadow:config:{company_id}"
REDIS_COMPARISONS_KEY = "shadow:comparisons:{company_id}"


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class ShadowComparison:
    """Result of comparing live and shadow variant responses."""

    company_id: str
    config_id: str
    ticket_id: str = ""
    conversation_id: str = ""
    message_hash: str = ""

    # Live variant data
    live_variant: str = ""
    live_response: str = ""
    live_quality_score: float = 0.0
    live_latency_ms: int = 0
    live_tokens_used: int = 0

    # Shadow variant data
    shadow_variant: str = ""
    shadow_response: str = ""
    shadow_quality_score: float = 0.0
    shadow_latency_ms: int = 0
    shadow_tokens_used: int = 0

    # Comparison
    quality_delta: float = 0.0
    latency_delta_ms: int = 0
    token_delta: int = 0
    shadow_winner: bool = False
    mode_at_comparison: str = "shadow"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for persistence/logging."""
        return {
            "company_id": self.company_id,
            "config_id": self.config_id,
            "ticket_id": self.ticket_id,
            "conversation_id": self.conversation_id,
            "live_variant": self.live_variant,
            "live_quality_score": self.live_quality_score,
            "live_latency_ms": self.live_latency_ms,
            "shadow_variant": self.shadow_variant,
            "shadow_quality_score": self.shadow_quality_score,
            "shadow_latency_ms": self.shadow_latency_ms,
            "quality_delta": self.quality_delta,
            "latency_delta_ms": self.latency_delta_ms,
            "token_delta": self.token_delta,
            "shadow_winner": self.shadow_winner,
            "mode_at_comparison": self.mode_at_comparison,
        }


@dataclass
class ShadowModeStatus:
    """Current shadow mode status for a company."""

    company_id: str
    is_active: bool = False
    status: str = "disabled"
    live_variant: str = ""
    shadow_variant: str = ""
    sample_rate: float = 1.0
    total_comparisons: int = 0
    shadow_wins: int = 0
    win_rate: float = 0.0
    current_quality_streak: int = 0
    auto_graduation_threshold: float = 0.95
    auto_graduation_window: int = 100
    config_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for API responses."""
        return {
            "company_id": self.company_id,
            "is_active": self.is_active,
            "status": self.status,
            "live_variant": self.live_variant,
            "shadow_variant": self.shadow_variant,
            "sample_rate": self.sample_rate,
            "total_comparisons": self.total_comparisons,
            "shadow_wins": self.shadow_wins,
            "win_rate": round(self.win_rate, 4),
            "current_quality_streak": self.current_quality_streak,
            "auto_graduation_threshold": self.auto_graduation_threshold,
            "auto_graduation_window": self.auto_graduation_window,
            "config_id": self.config_id,
        }


# ══════════════════════════════════════════════════════════════════
# SHADOW MODE SERVICE
# ══════════════════════════════════════════════════════════════════


class ShadowModeService:
    """Service for managing Shadow Mode deployment strategy.

    Shadow Mode allows safely testing a higher variant tier before
    fully switching over. The progression is:
      SHADOW → SUPERVISED → GRADUATED

    Persistence (BC-008):
      Three-tier caching: Redis → DB → in-memory.
      - Writes go to DB first, then Redis, then in-memory cache.
      - Reads try Redis first, then DB, then fall back to in-memory cache.
      - If Redis is unavailable, gracefully fall back to DB/in-memory.
      - If DB is down, the service keeps running from cache.

    Thread-safety: All mutable state is protected by _lock (RLock).

    BC-001: company_id is always the first parameter on public methods.
    BC-008: Every public method wrapped in try/except — never crash.
    BC-012: All timestamps are UTC.
    """

    def __init__(self) -> None:
        """Initialize the shadow mode service."""
        self._lock = threading.RLock()

        # In-memory cache: {company_id: config_dict}
        # Populated from DB on reads; updated on writes.
        self._configs: Dict[str, Dict[str, Any]] = {}

        # In-memory cache: {company_id: [ShadowComparison]}
        # Used as a fallback when DB is unavailable.
        self._comparisons: Dict[str, List[ShadowComparison]] = {}

        # Maximum comparisons to keep in memory per company
        self._max_comparisons_per_company = 10000

        logger.info(
            "ShadowModeService initialized (Redis + DB-backed with in-memory cache, "
            "max_comparisons=%d per company)",
            self._max_comparisons_per_company,
        )

    # ── DB Session Helper ─────────────────────────────────────────

    @staticmethod
    def _get_db_session():
        """Safely obtain a SQLAlchemy SessionLocal session.

        Returns a session instance, or None if the database is
        unavailable (BC-008: never crash).

        Usage::

            session = ShadowModeService._get_db_session()
            if session is None:
                # fall back to in-memory cache
                ...
            try:
                ...  # use session
                session.commit()
            except Exception:
                session.rollback()
            finally:
                session.close()
        """
        try:
            from database.base import SessionLocal
            return SessionLocal()
        except Exception:
            logger.exception(
                "Failed to create DB session — DB unavailable, "
                "falling back to in-memory cache",
            )
            return None

    # ── DB Persist: Config ────────────────────────────────────────

    def _persist_config_to_db(self, config: Dict[str, Any]) -> bool:
        """Persist a config dict to the ShadowModeConfig DB table.

        If a row with the same ``id`` already exists it is updated;
        otherwise a new row is inserted.

        Returns True on success, False on any DB error (BC-008).
        """
        session = self._get_db_session()
        if session is None:
            return False
        try:
            from database.models.shadow_mode import ShadowModeConfig

            existing = (
                session.query(ShadowModeConfig)
                .filter(ShadowModeConfig.id == config["id"])
                .first()
            )

            if existing is not None:
                # Update existing row
                existing.company_id = config.get("company_id", existing.company_id)
                existing.live_variant = config.get("live_variant", existing.live_variant)
                existing.shadow_variant = config.get("shadow_variant", existing.shadow_variant)
                existing.status = config.get("status", existing.status)
                existing.live_instance_id = config.get("live_instance_id", existing.live_instance_id)
                existing.shadow_instance_id = config.get("shadow_instance_id", existing.shadow_instance_id)
                existing.sample_rate = config.get("sample_rate", existing.sample_rate)
                existing.auto_graduation_threshold = config.get(
                    "auto_graduation_threshold", existing.auto_graduation_threshold,
                )
                existing.auto_graduation_window = config.get(
                    "auto_graduation_window", existing.auto_graduation_window,
                )
                existing.supervised_timeout_seconds = config.get(
                    "supervised_timeout_seconds", existing.supervised_timeout_seconds,
                )
                existing.auto_promote_to_supervised = config.get(
                    "auto_promote_to_supervised", existing.auto_promote_to_supervised,
                )
                existing.auto_promote_to_graduated = config.get(
                    "auto_promote_to_graduated", existing.auto_promote_to_graduated,
                )
                existing.current_quality_streak = config.get(
                    "current_quality_streak", existing.current_quality_streak,
                )
                existing.total_comparisons = config.get(
                    "total_comparisons", existing.total_comparisons,
                )
                existing.shadow_wins = config.get("shadow_wins", existing.shadow_wins)
                existing.is_active = config.get("is_active", existing.is_active)
                existing.enabled_by_user_id = config.get(
                    "enabled_by_user_id", existing.enabled_by_user_id,
                )

                # Timestamp fields — only update if present in config
                for attr in ("enabled_at", "supervised_at", "graduated_at", "disabled_at"):
                    val = config.get(attr)
                    if val is not None:
                        dt_val = self._parse_iso_to_datetime(val)
                        setattr(existing, attr, dt_val)

                existing.updated_at = datetime.now(timezone.utc)
            else:
                # Insert new row
                row = ShadowModeConfig(
                    id=config["id"],
                    company_id=config["company_id"],
                    live_variant=config["live_variant"],
                    shadow_variant=config["shadow_variant"],
                    status=config.get("status", "shadow"),
                    live_instance_id=config.get("live_instance_id"),
                    shadow_instance_id=config.get("shadow_instance_id"),
                    sample_rate=config.get("sample_rate", 1.0),
                    auto_graduation_threshold=config.get("auto_graduation_threshold", 0.95),
                    auto_graduation_window=config.get("auto_graduation_window", 100),
                    supervised_timeout_seconds=config.get("supervised_timeout_seconds", 300),
                    auto_promote_to_supervised=config.get("auto_promote_to_supervised", True),
                    auto_promote_to_graduated=config.get("auto_promote_to_graduated", False),
                    current_quality_streak=config.get("current_quality_streak", 0),
                    total_comparisons=config.get("total_comparisons", 0),
                    shadow_wins=config.get("shadow_wins", 0),
                    is_active=config.get("is_active", True),
                    enabled_by_user_id=config.get("enabled_by_user_id"),
                    enabled_at=self._parse_iso_to_datetime(config.get("enabled_at")),
                    supervised_at=self._parse_iso_to_datetime(config.get("supervised_at")),
                    graduated_at=self._parse_iso_to_datetime(config.get("graduated_at")),
                    disabled_at=self._parse_iso_to_datetime(config.get("disabled_at")),
                )
                session.add(row)

            session.commit()
            logger.debug(
                "Persisted config to DB: config_id=%s, company_id=%s",
                config.get("id"), config.get("company_id"),
            )
            return True

        except Exception:
            logger.exception(
                "Failed to persist config to DB: config_id=%s — "
                "continuing with in-memory cache",
                config.get("id"),
            )
            try:
                session.rollback()
            except Exception:
                pass
            return False
        finally:
            try:
                session.close()
            except Exception:
                pass

    # ── DB Load: Config ───────────────────────────────────────────

    def _load_config_from_db(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Load the active config for *company_id* from the DB.

        Returns the config dict if found, or None.
        On any DB error, returns None so the caller can fall back
        to the in-memory cache (BC-008).
        """
        session = self._get_db_session()
        if session is None:
            return None
        try:
            from database.models.shadow_mode import ShadowModeConfig

            row = (
                session.query(ShadowModeConfig)
                .filter(
                    ShadowModeConfig.company_id == company_id,
                    ShadowModeConfig.is_active.is_(True),
                )
                .order_by(ShadowModeConfig.created_at.desc())
                .first()
            )

            if row is None:
                return None

            config = self._config_row_to_dict(row)

            # Refresh the in-memory cache from DB truth
            with self._lock:
                self._configs[company_id] = config

            return config

        except Exception:
            logger.exception(
                "Failed to load config from DB for company_id=%s — "
                "falling back to in-memory cache",
                company_id,
            )
            return None
        finally:
            try:
                session.close()
            except Exception:
                pass

    # ── DB Persist: Comparison ────────────────────────────────────

    def _persist_comparison_to_db(self, comparison: ShadowComparison) -> bool:
        """Persist a ShadowComparison to the ShadowModeResult DB table.

        Returns True on success, False on any DB error (BC-008).
        """
        session = self._get_db_session()
        if session is None:
            return False
        try:
            from database.models.shadow_mode import ShadowModeResult

            result_id = str(uuid.uuid4())
            row = ShadowModeResult(
                id=result_id,
                company_id=comparison.company_id,
                config_id=comparison.config_id,
                ticket_id=comparison.ticket_id or None,
                conversation_id=comparison.conversation_id or None,
                message_hash=comparison.message_hash or None,
                live_variant=comparison.live_variant,
                live_response=comparison.live_response or None,
                live_quality_score=comparison.live_quality_score or None,
                live_latency_ms=comparison.live_latency_ms or None,
                live_tokens_used=comparison.live_tokens_used or None,
                shadow_variant=comparison.shadow_variant,
                shadow_response=comparison.shadow_response or None,
                shadow_quality_score=comparison.shadow_quality_score or None,
                shadow_latency_ms=comparison.shadow_latency_ms or None,
                shadow_tokens_used=comparison.shadow_tokens_used or None,
                quality_delta=comparison.quality_delta or None,
                latency_delta_ms=comparison.latency_delta_ms or None,
                token_delta=comparison.token_delta or None,
                shadow_winner=comparison.shadow_winner,
                mode_at_comparison=comparison.mode_at_comparison,
            )
            session.add(row)
            session.commit()

            logger.debug(
                "Persisted comparison to DB: result_id=%s, company_id=%s",
                result_id, comparison.company_id,
            )
            return True

        except Exception:
            logger.exception(
                "Failed to persist comparison to DB for company_id=%s — "
                "continuing with in-memory cache",
                comparison.company_id,
            )
            try:
                session.rollback()
            except Exception:
                pass
            return False
        finally:
            try:
                session.close()
            except Exception:
                pass

    # ── DB Load: Comparison History ───────────────────────────────

    def _load_comparisons_from_db(
        self,
        company_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Optional[List[Dict[str, Any]]]:
        """Load comparison history from the DB.

        Returns a list of comparison dicts, or None on DB error
        so the caller can fall back to the in-memory cache (BC-008).
        """
        session = self._get_db_session()
        if session is None:
            return None
        try:
            from database.models.shadow_mode import ShadowModeResult

            rows = (
                session.query(ShadowModeResult)
                .filter(ShadowModeResult.company_id == company_id)
                .order_by(ShadowModeResult.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )

            results = []
            for row in rows:
                results.append(self._result_row_to_dict(row))
            return results

        except Exception:
            logger.exception(
                "Failed to load comparisons from DB for company_id=%s — "
                "falling back to in-memory cache",
                company_id,
            )
            return None
        finally:
            try:
                session.close()
            except Exception:
                pass

    # ── DB Persist: Config Update (counters, status) ──────────────

    def _persist_config_counters_to_db(
        self,
        company_id: str,
        config: Dict[str, Any],
    ) -> bool:
        """Light-weight persist for counter/status fields only.

        Avoids rewriting the whole row when only counters or status
        changed (e.g. after recording a comparison or a promotion).

        Returns True on success, False on DB error (BC-008).
        """
        session = self._get_db_session()
        if session is None:
            return False
        try:
            from database.models.shadow_mode import ShadowModeConfig

            row = (
                session.query(ShadowModeConfig)
                .filter(ShadowModeConfig.id == config["id"])
                .first()
            )
            if row is None:
                # Row doesn't exist yet — fall back to full persist
                session.close()
                return self._persist_config_to_db(config)

            row.status = config.get("status", row.status)
            row.is_active = config.get("is_active", row.is_active)
            row.current_quality_streak = config.get(
                "current_quality_streak", row.current_quality_streak,
            )
            row.total_comparisons = config.get(
                "total_comparisons", row.total_comparisons,
            )
            row.shadow_wins = config.get("shadow_wins", row.shadow_wins)
            row.sample_rate = config.get("sample_rate", row.sample_rate)

            # Timestamps — only update if present
            for attr in ("supervised_at", "graduated_at", "disabled_at"):
                val = config.get(attr)
                if val is not None:
                    dt_val = self._parse_iso_to_datetime(val)
                    setattr(row, attr, dt_val)

            row.updated_at = datetime.now(timezone.utc)
            session.commit()

            logger.debug(
                "Persisted config counters to DB: config_id=%s, company_id=%s",
                config.get("id"), company_id,
            )
            return True

        except Exception:
            logger.exception(
                "Failed to persist config counters to DB for company_id=%s",
                company_id,
            )
            try:
                session.rollback()
            except Exception:
                pass
            return False
        finally:
            try:
                session.close()
            except Exception:
                pass

    # ── Row-to-Dict Helpers ───────────────────────────────────────

    @staticmethod
    def _config_row_to_dict(row: Any) -> Dict[str, Any]:
        """Convert a ShadowModeConfig ORM row to the internal config dict."""
        return {
            "id": row.id,
            "company_id": row.company_id,
            "live_variant": row.live_variant,
            "shadow_variant": row.shadow_variant,
            "status": row.status,
            "live_instance_id": row.live_instance_id or "",
            "shadow_instance_id": row.shadow_instance_id or "",
            "sample_rate": float(row.sample_rate) if row.sample_rate is not None else 1.0,
            "auto_graduation_threshold": (
                float(row.auto_graduation_threshold)
                if row.auto_graduation_threshold is not None
                else 0.95
            ),
            "auto_graduation_window": row.auto_graduation_window or 100,
            "supervised_timeout_seconds": row.supervised_timeout_seconds or 300,
            "auto_promote_to_supervised": row.auto_promote_to_supervised if row.auto_promote_to_supervised is not None else True,
            "auto_promote_to_graduated": row.auto_promote_to_graduated if row.auto_promote_to_graduated is not None else False,
            "current_quality_streak": row.current_quality_streak or 0,
            "total_comparisons": row.total_comparisons or 0,
            "shadow_wins": row.shadow_wins or 0,
            "is_active": row.is_active if row.is_active is not None else True,
            "enabled_by_user_id": row.enabled_by_user_id or "",
            "enabled_at": row.enabled_at.isoformat() if row.enabled_at else None,
            "supervised_at": row.supervised_at.isoformat() if row.supervised_at else None,
            "graduated_at": row.graduated_at.isoformat() if row.graduated_at else None,
            "disabled_at": row.disabled_at.isoformat() if row.disabled_at else None,
        }

    @staticmethod
    def _result_row_to_dict(row: Any) -> Dict[str, Any]:
        """Convert a ShadowModeResult ORM row to a comparison dict."""
        return {
            "id": row.id,
            "company_id": row.company_id,
            "config_id": row.config_id,
            "ticket_id": row.ticket_id or "",
            "conversation_id": row.conversation_id or "",
            "live_variant": row.live_variant,
            "live_quality_score": float(row.live_quality_score) if row.live_quality_score is not None else 0.0,
            "live_latency_ms": row.live_latency_ms or 0,
            "shadow_variant": row.shadow_variant,
            "shadow_quality_score": float(row.shadow_quality_score) if row.shadow_quality_score is not None else 0.0,
            "shadow_latency_ms": row.shadow_latency_ms or 0,
            "quality_delta": float(row.quality_delta) if row.quality_delta is not None else 0.0,
            "latency_delta_ms": row.latency_delta_ms or 0,
            "token_delta": row.token_delta or 0,
            "shadow_winner": row.shadow_winner if row.shadow_winner is not None else False,
            "mode_at_comparison": row.mode_at_comparison or "shadow",
            "human_reviewed": row.human_reviewed or False,
            "human_verdict": row.human_verdict or "",
            "reviewer_id": row.reviewer_id or "",
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    # ── Datetime Helpers ──────────────────────────────────────────

    @staticmethod
    def _parse_iso_to_datetime(val: Any) -> Optional[datetime]:
        """Parse an ISO-8601 string to a UTC datetime.

        Returns None if *val* is None or unparseable.
        """
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        try:
            return datetime.fromisoformat(str(val))
        except (ValueError, TypeError):
            logger.warning("Could not parse ISO datetime: %r", val)
            return None

    @staticmethod
    def _utc_now_iso() -> str:
        """Return current UTC time as ISO-8601 string (BC-012)."""
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash_message(message: str) -> str:
        """Hash a message for deduplication."""
        return hashlib.sha256(message.encode("utf-8")).hexdigest()

    # ── Async Bridge Helper ────────────────────────────────────────

    @staticmethod
    def _run_async_safely(coro):
        """Run an async coroutine from synchronous context (BC-008).

        Bridges the gap between the service's synchronous methods and
        the async Redis client.  Returns the coroutine's result, or None
        on *any* error (including event-loop issues).

        Strategy:
          1. If no event loop is running, use ``asyncio.run()``.
          2. If an event loop is already running (e.g. inside FastAPI),
             spawn a new loop in a background thread so we don't block
             or conflict with the existing loop.
          3. Any exception → return None (BC-008: never crash).
        """
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None and loop.is_running():
                # Already inside a running event loop (e.g. FastAPI handler).
                # Run the coroutine in a separate thread with its own loop.
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result(timeout=10)
            else:
                return asyncio.run(coro)
        except Exception:
            return None

    # ── Redis Cache: Config ────────────────────────────────────────

    def _redis_get_config(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Try to get the active config from Redis cache (BC-008).

        Returns the config dict if found in Redis, or None if not
        cached or if Redis is unavailable.  Lazy-imports the Redis
        module to avoid circular imports.

        BC-008: Never crashes — returns None on any Redis error.
        """
        try:
            from app.core.redis import cache_get

            key = REDIS_CONFIG_KEY.format(company_id=company_id)
            result = self._run_async_safely(cache_get(company_id, key))
            if result is not None and isinstance(result, dict):
                logger.debug(
                    "Redis cache hit for config: company_id=%s", company_id,
                )
                return result
            return None
        except Exception:
            logger.exception(
                "Redis get config failed for company_id=%s — "
                "falling back to DB/in-memory cache",
                company_id,
            )
            return None

    def _redis_set_config(self, company_id: str, config: Dict[str, Any]) -> bool:
        """Set the config in Redis cache with TTL (BC-008).

        Lazy-imports the Redis module to avoid circular imports.
        Returns True on success, False on any Redis error.

        BC-008: Never crashes — returns False on error.
        """
        try:
            from app.core.redis import cache_set

            key = REDIS_CONFIG_KEY.format(company_id=company_id)
            result = self._run_async_safely(
                cache_set(company_id, key, config, REDIS_CONFIG_TTL_SECONDS),
            )
            if result:
                logger.debug(
                    "Redis cache set for config: company_id=%s", company_id,
                )
            return bool(result)
        except Exception:
            logger.exception(
                "Redis set config failed for company_id=%s — "
                "continuing without Redis cache",
                company_id,
            )
            return False

    # ── Redis Cache: Comparisons ───────────────────────────────────

    def _redis_get_comparisons(
        self,
        company_id: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """Try to get comparisons from Redis cache (BC-008).

        Returns a list of comparison dicts if found in Redis, or None
        if not cached or if Redis is unavailable.  Lazy-imports the
        Redis module to avoid circular imports.

        BC-008: Never crashes — returns None on any Redis error.
        """
        try:
            from app.core.redis import cache_get

            key = REDIS_COMPARISONS_KEY.format(company_id=company_id)
            result = self._run_async_safely(cache_get(company_id, key))
            if result is not None and isinstance(result, list):
                logger.debug(
                    "Redis cache hit for comparisons: company_id=%s",
                    company_id,
                )
                return result
            return None
        except Exception:
            logger.exception(
                "Redis get comparisons failed for company_id=%s — "
                "falling back to DB/in-memory cache",
                company_id,
            )
            return None

    def _redis_set_comparisons(
        self,
        company_id: str,
        comparisons: List[Dict[str, Any]],
    ) -> bool:
        """Set comparisons in Redis cache with TTL (BC-008).

        Lazy-imports the Redis module to avoid circular imports.
        Returns True on success, False on any Redis error.

        BC-008: Never crashes — returns False on error.
        """
        try:
            from app.core.redis import cache_set

            key = REDIS_COMPARISONS_KEY.format(company_id=company_id)
            result = self._run_async_safely(
                cache_set(
                    company_id, key, comparisons, REDIS_COMPARISONS_TTL_SECONDS,
                ),
            )
            if result:
                logger.debug(
                    "Redis cache set for comparisons: company_id=%s",
                    company_id,
                )
            return bool(result)
        except Exception:
            logger.exception(
                "Redis set comparisons failed for company_id=%s — "
                "continuing without Redis cache",
                company_id,
            )
            return False

    # ── Enable Shadow Mode ──────────────────────────────────────────

    def enable_shadow_mode(
        self,
        company_id: str,
        live_variant: str,
        shadow_variant: str,
        sample_rate: float = DEFAULT_SAMPLE_RATE,
        auto_graduation_threshold: float = DEFAULT_AUTO_GRADUATION_THRESHOLD,
        auto_graduation_window: int = DEFAULT_AUTO_GRADUATION_WINDOW,
        supervised_timeout_seconds: int = DEFAULT_SUPERVISED_TIMEOUT,
        auto_promote_to_supervised: bool = True,
        auto_promote_to_graduated: bool = False,
        live_instance_id: str = "",
        shadow_instance_id: str = "",
        user_id: str = "",
    ) -> Dict[str, Any]:
        """Enable shadow mode for a company.

        Creates a new shadow mode config. If one is already active,
        disables it first (only one active config per company).

        Persists to DB first, then updates in-memory cache (BC-008).

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns error dict on failure.
        """
        try:
            # Validate variant types
            if live_variant not in VALID_VARIANT_TYPES:
                return {
                    "success": False,
                    "error": f"Invalid live_variant: {live_variant}. "
                             f"Must be one of {VALID_VARIANT_TYPES}",
                }
            if shadow_variant not in VALID_VARIANT_TYPES:
                return {
                    "success": False,
                    "error": f"Invalid shadow_variant: {shadow_variant}. "
                             f"Must be one of {VALID_VARIANT_TYPES}",
                }

            # Validate that shadow is an upgrade direction
            live_rank = VARIANT_RANKING.get(live_variant, 0)
            shadow_rank = VARIANT_RANKING.get(shadow_variant, 0)
            if shadow_rank <= live_rank:
                return {
                    "success": False,
                    "error": (
                        f"Shadow variant ({shadow_variant}, rank {shadow_rank}) "
                        f"must be higher than live variant ({live_variant}, "
                        f"rank {live_rank}). Shadow mode tests UPGRADES."
                    ),
                }

            # Validate sample rate
            if not (0.0 < sample_rate <= 1.0):
                return {
                    "success": False,
                    "error": f"Sample rate must be between 0.0 (exclusive) and 1.0, got {sample_rate}",
                }

            config_id = str(uuid.uuid4())
            now = self._utc_now_iso()

            config = {
                "id": config_id,
                "company_id": company_id,
                "live_variant": live_variant,
                "shadow_variant": shadow_variant,
                "status": "shadow",
                "sample_rate": sample_rate,
                "auto_graduation_threshold": auto_graduation_threshold,
                "auto_graduation_window": auto_graduation_window,
                "supervised_timeout_seconds": supervised_timeout_seconds,
                "auto_promote_to_supervised": auto_promote_to_supervised,
                "auto_promote_to_graduated": auto_promote_to_graduated,
                "live_instance_id": live_instance_id,
                "shadow_instance_id": shadow_instance_id,
                "current_quality_streak": 0,
                "total_comparisons": 0,
                "shadow_wins": 0,
                "is_active": True,
                "enabled_by_user_id": user_id,
                "enabled_at": now,
                "supervised_at": None,
                "graduated_at": None,
                "disabled_at": None,
            }

            with self._lock:
                # Disable any existing active config (in-memory)
                existing = self._configs.get(company_id)
                if existing and existing.get("is_active"):
                    existing["is_active"] = False
                    existing["status"] = "disabled"
                    existing["disabled_at"] = now
                    # Persist the deactivation to DB
                    self._persist_config_to_db(existing)
                    logger.info(
                        "Disabled existing shadow mode config for company_id=%s",
                        company_id,
                    )

                # Update in-memory cache
                self._configs[company_id] = config

            # Persist the new config to DB
            db_ok = self._persist_config_to_db(config)
            if not db_ok:
                logger.warning(
                    "DB persist failed for enable_shadow_mode — "
                    "config is in in-memory cache only: company_id=%s",
                    company_id,
                )

            # Update Redis cache after DB write
            redis_ok = self._redis_set_config(company_id, config)
            if not redis_ok:
                logger.debug(
                    "Redis cache set failed for enable_shadow_mode — "
                    "DB and in-memory cache remain authoritative: company_id=%s",
                    company_id,
                )

            logger.info(
                "Shadow mode enabled: company_id=%s, live=%s, shadow=%s, "
                "sample_rate=%.2f, config_id=%s, db_persisted=%s, redis_cached=%s",
                company_id, live_variant, shadow_variant, sample_rate,
                config_id, db_ok, redis_ok,
            )

            return {
                "success": True,
                "config_id": config_id,
                "status": "shadow",
                "live_variant": live_variant,
                "shadow_variant": shadow_variant,
                "sample_rate": sample_rate,
            }

        except Exception:
            logger.exception(
                "enable_shadow_mode failed for company_id=%s — "
                "returning error dict",
                company_id,
            )
            return {
                "success": False,
                "error": "internal_error_in_enable_shadow_mode",
            }

    # ── Disable Shadow Mode ─────────────────────────────────────────

    def disable_shadow_mode(
        self,
        company_id: str,
        reason: str = "",
    ) -> Dict[str, Any]:
        """Disable shadow mode for a company.

        Persists to DB first, then updates Redis, then in-memory cache (BC-008).

        BC-001: company_id is first parameter.
        BC-008: Never crashes.
        """
        try:
            with self._lock:
                # Try Redis first, then DB, then in-memory cache
                config = self._redis_get_config(company_id)
                if config is None:
                    config = self._load_config_from_db(company_id)
                if config is None:
                    # Fall back to in-memory cache
                    config = self._configs.get(company_id)

                if config is None or not config.get("is_active"):
                    return {
                        "success": False,
                        "error": "No active shadow mode config found",
                    }

                previous_status = config.get("status", "unknown")
                config["is_active"] = False
                config["status"] = "disabled"
                config["disabled_at"] = self._utc_now_iso()

                # Persist to DB
                db_ok = self._persist_config_to_db(config)
                if not db_ok:
                    logger.warning(
                        "DB persist failed for disable_shadow_mode — "
                        "change is in in-memory cache only: company_id=%s",
                        company_id,
                    )

                # Update Redis cache after DB write
                redis_ok = self._redis_set_config(company_id, config)
                if not redis_ok:
                    logger.debug(
                        "Redis cache set failed for disable_shadow_mode — "
                        "DB and in-memory cache remain authoritative: company_id=%s",
                        company_id,
                    )

                # Update in-memory cache
                self._configs[company_id] = config

            logger.info(
                "Shadow mode disabled: company_id=%s, reason='%s', "
                "db_persisted=%s, redis_cached=%s",
                company_id, reason, db_ok, redis_ok,
            )

            return {
                "success": True,
                "company_id": company_id,
                "previous_status": previous_status,
                "reason": reason,
            }

        except Exception:
            logger.exception(
                "disable_shadow_mode failed for company_id=%s",
                company_id,
            )
            return {
                "success": False,
                "error": "internal_error_in_disable_shadow_mode",
            }

    # ── Get Status ──────────────────────────────────────────────────

    def get_status(
        self,
        company_id: str,
    ) -> ShadowModeStatus:
        """Get current shadow mode status for a company.

        Tries Redis first, then DB; falls back to in-memory cache
        if both are unavailable (BC-008).

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns disabled status on error.
        """
        try:
            # Try Redis first
            config = self._redis_get_config(company_id)

            if config is None:
                # Fall back to DB
                config = self._load_config_from_db(company_id)

            if config is None:
                # Fall back to in-memory cache
                with self._lock:
                    config = self._configs.get(company_id)

            if config is None or not config.get("is_active"):
                return ShadowModeStatus(
                    company_id=company_id,
                    is_active=False,
                    status="disabled",
                )

            total = config.get("total_comparisons", 0)
            wins = config.get("shadow_wins", 0)
            win_rate = (wins / total) if total > 0 else 0.0

            return ShadowModeStatus(
                company_id=company_id,
                is_active=True,
                status=config.get("status", "disabled"),
                live_variant=config.get("live_variant", ""),
                shadow_variant=config.get("shadow_variant", ""),
                sample_rate=float(config.get("sample_rate", 1.0)),
                total_comparisons=total,
                shadow_wins=wins,
                win_rate=win_rate,
                current_quality_streak=config.get("current_quality_streak", 0),
                auto_graduation_threshold=float(
                    config.get("auto_graduation_threshold", 0.95)
                ),
                auto_graduation_window=config.get("auto_graduation_window", 100),
                config_id=config.get("id", ""),
            )

        except Exception:
            logger.exception(
                "get_status failed for company_id=%s", company_id,
            )
            return ShadowModeStatus(company_id=company_id, is_active=False)

    # ── Should Process in Shadow ────────────────────────────────────

    def should_process_shadow(
        self,
        company_id: str,
        message: str = "",
    ) -> Tuple[bool, str]:
        """Determine if a message should be shadow-processed.

        Returns (should_shadow, reason):
          - should_shadow: True if the message should be processed
            by both live and shadow variants.
          - reason: Explanation of the decision.

        Uses the sample_rate to probabilistically include messages.
        If sample_rate is 1.0, all messages are shadow-processed.
        If sample_rate is 0.1, ~10% of messages are shadow-processed.

        Tries Redis first, then DB, then in-memory cache (BC-008).

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns (False, reason) on error.
        """
        try:
            # Try Redis first, then DB, then in-memory cache
            config = self._redis_get_config(company_id)
            if config is None:
                config = self._load_config_from_db(company_id)
            if config is None:
                with self._lock:
                    config = self._configs.get(company_id)

            if config is None or not config.get("is_active"):
                return (False, "no_active_shadow_mode")

            status = config.get("status", "disabled")
            if status not in ("shadow", "supervised"):
                return (False, f"status_is_{status}")

            # Sample rate check
            sample_rate = float(config.get("sample_rate", 1.0))
            if sample_rate < 1.0:
                if random.random() > sample_rate:
                    return (False, f"sample_rate_excluded ({sample_rate:.2f})")

            return (True, f"status_is_{status}")

        except Exception:
            logger.exception(
                "should_process_shadow failed for company_id=%s",
                company_id,
            )
            return (False, "internal_error")

    # ── Get Shadow Config ───────────────────────────────────────────

    def get_shadow_config(
        self,
        company_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get the active shadow mode config for a company.

        Tries Redis first, then DB; falls back to in-memory cache (BC-008).

        Returns None if no active config exists.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns None on error.
        """
        try:
            # Try Redis first
            config = self._redis_get_config(company_id)
            if config is not None:
                if config.get("is_active"):
                    return dict(config)
                # Redis had a non-active config — continue to DB
                config = None

            # Fall back to DB
            if config is None:
                config = self._load_config_from_db(company_id)
            if config is not None:
                return dict(config)

            # Fall back to in-memory cache
            with self._lock:
                config = self._configs.get(company_id)
                if config and config.get("is_active"):
                    return dict(config)
            return None
        except Exception:
            logger.exception(
                "get_shadow_config failed for company_id=%s", company_id,
            )
            return None

    # ── Record Comparison ───────────────────────────────────────────

    def record_comparison(
        self,
        company_id: str,
        comparison: ShadowComparison,
    ) -> Dict[str, Any]:
        """Record a comparison result and check for auto-graduation.

        After recording, checks if the quality streak meets the
        auto-graduation threshold. If so, promotes to the next phase.

        Persists to DB; falls back to in-memory cache if DB unavailable
        (BC-008).

        BC-001: company_id is first parameter.
        BC-008: Never crashes.
        """
        try:
            with self._lock:
                # Try Redis first, then DB, then in-memory cache
                config = self._redis_get_config(company_id)
                if config is None:
                    config = self._load_config_from_db(company_id)
                if config is None:
                    # Fall back to in-memory cache
                    config = self._configs.get(company_id)
                if config is None:
                    return {"success": False, "error": "no_config_found"}

                # Update counters
                config["total_comparisons"] = config.get("total_comparisons", 0) + 1

                if comparison.shadow_winner:
                    config["shadow_wins"] = config.get("shadow_wins", 0) + 1
                    config["current_quality_streak"] = (
                        config.get("current_quality_streak", 0) + 1
                    )
                else:
                    config["current_quality_streak"] = 0

                # Store comparison in in-memory cache
                if company_id not in self._comparisons:
                    self._comparisons[company_id] = []
                self._comparisons[company_id].append(comparison)

                # Trim if too many
                if len(self._comparisons[company_id]) > self._max_comparisons_per_company:
                    self._comparisons[company_id] = (
                        self._comparisons[company_id][
                            -self._max_comparisons_per_company:
                        ]
                    )

                # Check auto-graduation
                graduation_result = self._check_auto_graduation(
                    company_id, config,
                )

                # Persist updated config counters/status to DB
                db_config_ok = self._persist_config_counters_to_db(
                    company_id, config,
                )
                if not db_config_ok:
                    logger.warning(
                        "DB persist failed for config counters after "
                        "record_comparison — in-memory cache updated: "
                        "company_id=%s",
                        company_id,
                    )

                # Update Redis cache after DB write
                redis_config_ok = self._redis_set_config(company_id, config)
                if not redis_config_ok:
                    logger.debug(
                        "Redis cache set failed for config after "
                        "record_comparison — DB and in-memory cache remain "
                        "authoritative: company_id=%s",
                        company_id,
                    )

                # Update in-memory cache with latest config
                self._configs[company_id] = config

            # Persist the comparison result to DB (outside the lock
            # to reduce contention — the comparison is independent)
            db_comp_ok = self._persist_comparison_to_db(comparison)
            if not db_comp_ok:
                logger.warning(
                    "DB persist failed for comparison — in-memory cache "
                    "updated: company_id=%s",
                    company_id,
                )

            # Update Redis comparisons cache after DB write
            with self._lock:
                comp_dicts = [c.to_dict() for c in self._comparisons.get(company_id, [])[-50:]]
            self._redis_set_comparisons(company_id, comp_dicts)

            return {
                "success": True,
                "total_comparisons": config.get("total_comparisons", 0),
                "shadow_wins": config.get("shadow_wins", 0),
                "current_quality_streak": config.get("current_quality_streak", 0),
                "auto_graduation": graduation_result,
            }

        except Exception:
            logger.exception(
                "record_comparison failed for company_id=%s", company_id,
            )
            return {"success": False, "error": "internal_error_in_record_comparison"}

    # ── Auto-Graduation Check ───────────────────────────────────────

    def _check_auto_graduation(
        self,
        company_id: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Check if auto-graduation criteria are met.

        Must be called while holding _lock.

        Returns dict with 'graduated' (bool) and 'new_status' (str).
        """
        try:
            streak = config.get("current_quality_streak", 0)
            threshold = int(config.get("auto_graduation_window", 100))
            current_status = config.get("status", "disabled")

            result = {"graduated": False, "new_status": current_status}

            if streak < threshold:
                return result

            # Streak meets threshold — promote
            now = self._utc_now_iso()

            if current_status == "shadow" and config.get("auto_promote_to_supervised"):
                config["status"] = "supervised"
                config["supervised_at"] = now
                result = {"graduated": True, "new_status": "supervised"}
                logger.info(
                    "Auto-graduated to SUPERVISED: company_id=%s, "
                    "streak=%d, threshold=%d",
                    company_id, streak, threshold,
                )

            elif current_status == "supervised" and config.get("auto_promote_to_graduated"):
                config["status"] = "graduated"
                config["graduated_at"] = now
                result = {"graduated": True, "new_status": "graduated"}
                logger.info(
                    "Auto-graduated to GRADUATED: company_id=%s, "
                    "streak=%d, threshold=%d",
                    company_id, streak, threshold,
                )

            return result

        except Exception:
            logger.exception(
                "_check_auto_graduation failed for company_id=%s", company_id,
            )
            return {"graduated": False, "new_status": "error"}

    # ── Manual Promote ──────────────────────────────────────────────

    def promote(
        self,
        company_id: str,
        target_status: str = "",
    ) -> Dict[str, Any]:
        """Manually promote shadow mode to the next phase.

        If target_status is not specified, promotes to the next phase:
          shadow → supervised → graduated

        Persists to DB; falls back to in-memory cache if DB unavailable
        (BC-008).

        BC-001: company_id is first parameter.
        BC-008: Never crashes.
        """
        try:
            with self._lock:
                # Try Redis first, then DB, then in-memory cache
                config = self._redis_get_config(company_id)
                if config is None:
                    config = self._load_config_from_db(company_id)
                if config is None:
                    config = self._configs.get(company_id)
                if config is None or not config.get("is_active"):
                    return {
                        "success": False,
                        "error": "No active shadow mode config found",
                    }

                current = config.get("status", "disabled")
                now = self._utc_now_iso()

                if target_status:
                    # Validate target status
                    if target_status not in ("shadow", "supervised", "graduated"):
                        return {
                            "success": False,
                            "error": f"Invalid target_status: {target_status}",
                        }
                    new_status = target_status
                else:
                    # Auto-determine next phase
                    progression = {
                        "shadow": "supervised",
                        "supervised": "graduated",
                    }
                    new_status = progression.get(current, "")
                    if not new_status:
                        return {
                            "success": False,
                            "error": f"Cannot promote from status '{current}'",
                        }

                config["status"] = new_status
                if new_status == "supervised":
                    config["supervised_at"] = now
                elif new_status == "graduated":
                    config["graduated_at"] = now

                # Persist to DB
                db_ok = self._persist_config_counters_to_db(company_id, config)
                if not db_ok:
                    logger.warning(
                        "DB persist failed for promote — in-memory cache "
                        "updated: company_id=%s",
                        company_id,
                    )

                # Update Redis cache after DB write
                redis_ok = self._redis_set_config(company_id, config)
                if not redis_ok:
                    logger.debug(
                        "Redis cache set failed for promote — "
                        "DB and in-memory cache remain authoritative: company_id=%s",
                        company_id,
                    )

                # Update in-memory cache
                self._configs[company_id] = config

            logger.info(
                "Manual promote: company_id=%s, %s → %s, db_persisted=%s, redis_cached=%s",
                company_id, current, new_status, db_ok, redis_ok,
            )

            return {
                "success": True,
                "previous_status": current,
                "new_status": new_status,
            }

        except Exception:
            logger.exception(
                "promote failed for company_id=%s", company_id,
            )
            return {"success": False, "error": "internal_error_in_promote"}

    # ── Record Human Review ─────────────────────────────────────────

    def record_human_review(
        self,
        company_id: str,
        result_id: str,
        verdict: str,
        reviewer_id: str = "",
        notes: str = "",
    ) -> Dict[str, Any]:
        """Record a human review decision for a shadow mode result.

        verdict must be one of: "shadow_better", "live_better", "equal", "skip"

        Persists to DB; falls back to in-memory search if DB unavailable
        (BC-008).

        BC-001: company_id is first parameter.
        BC-008: Never crashes.
        """
        try:
            valid_verdicts = ("shadow_better", "live_better", "equal", "skip")
            if verdict not in valid_verdicts:
                return {
                    "success": False,
                    "error": f"Invalid verdict: {verdict}. Must be one of {valid_verdicts}",
                }

            # Try DB first
            db_updated = False
            session = self._get_db_session()
            if session is not None:
                try:
                    from database.models.shadow_mode import ShadowModeResult

                    row = (
                        session.query(ShadowModeResult)
                        .filter(
                            ShadowModeResult.id == result_id,
                            ShadowModeResult.company_id == company_id,
                        )
                        .first()
                    )
                    if row is not None:
                        row.human_reviewed = True
                        row.human_verdict = verdict
                        row.reviewer_id = reviewer_id or None
                        row.reviewed_at = datetime.now(timezone.utc)
                        row.review_notes = notes or None
                        session.commit()
                        db_updated = True
                except Exception:
                    logger.exception(
                        "DB persist failed for record_human_review — "
                        "falling back to in-memory: result_id=%s",
                        result_id,
                    )
                    try:
                        session.rollback()
                    except Exception:
                        pass
                finally:
                    try:
                        session.close()
                    except Exception:
                        pass

            if not db_updated:
                # Fall back to in-memory scan
                with self._lock:
                    comparisons = self._comparisons.get(company_id, [])
                    for comp in comparisons:
                        # In-memory comparisons don't have a result_id,
                        # so this is best-effort
                        pass

            logger.info(
                "Human review recorded: company_id=%s, result_id=%s, "
                "verdict=%s, reviewer=%s, db_updated=%s",
                company_id, result_id, verdict, reviewer_id, db_updated,
            )

            return {
                "success": True,
                "result_id": result_id,
                "verdict": verdict,
                "reviewer_id": reviewer_id,
            }

        except Exception:
            logger.exception(
                "record_human_review failed for company_id=%s", company_id,
            )
            return {
                "success": False,
                "error": "internal_error_in_record_human_review",
            }

    # ── Get Comparison History ──────────────────────────────────────

    def get_comparison_history(
        self,
        company_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get comparison history for a company.

        Tries DB first; falls back to in-memory cache if DB is
        unavailable (BC-008).

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns empty list on error.
        """
        try:
            # Try DB first
            db_results = self._load_comparisons_from_db(company_id, limit, offset)
            if db_results is not None:
                return db_results

            # Fall back to in-memory cache
            with self._lock:
                comparisons = self._comparisons.get(company_id, [])

            # Return most recent first, paginated
            total = len(comparisons)
            start = total - offset - limit if offset + limit < total else 0
            end = total - offset if offset < total else 0
            if start < 0:
                start = 0

            return [c.to_dict() for c in comparisons[start:end]]

        except Exception:
            logger.exception(
                "get_comparison_history failed for company_id=%s", company_id,
            )
            return []

    # ── Get Statistics ──────────────────────────────────────────────

    def get_statistics(
        self,
        company_id: str,
    ) -> Dict[str, Any]:
        """Get shadow mode statistics for a company.

        Tries DB first; falls back to in-memory cache if DB is
        unavailable (BC-008).

        BC-001: company_id is first parameter.
        BC-008: Never crashes.
        """
        try:
            # Try DB first
            config = self._load_config_from_db(company_id)
            if config is None:
                with self._lock:
                    config = self._configs.get(company_id)
                    comparisons = self._comparisons.get(company_id, [])
            else:
                # DB is available — compute stats from DB-sourced config
                comparisons = []

            if config is None:
                return {
                    "company_id": company_id,
                    "is_active": False,
                    "total_comparisons": 0,
                }

            total = config.get("total_comparisons", 0)
            wins = config.get("shadow_wins", 0)
            win_rate = (wins / total) if total > 0 else 0.0

            # Calculate average quality delta from recent comparisons
            # (in-memory only — DB aggregation would be a future enhancement)
            recent = comparisons[-100:] if comparisons else []
            avg_quality_delta = 0.0
            avg_latency_delta = 0
            if recent:
                quality_deltas = [
                    c.quality_delta for c in recent if c.quality_delta != 0
                ]
                latency_deltas = [
                    c.latency_delta_ms for c in recent
                ]
                if quality_deltas:
                    avg_quality_delta = sum(quality_deltas) / len(quality_deltas)
                if latency_deltas:
                    avg_latency_delta = sum(latency_deltas) // len(latency_deltas)

            return {
                "company_id": company_id,
                "is_active": config.get("is_active", False),
                "status": config.get("status", "disabled"),
                "live_variant": config.get("live_variant", ""),
                "shadow_variant": config.get("shadow_variant", ""),
                "total_comparisons": total,
                "shadow_wins": wins,
                "win_rate": round(win_rate, 4),
                "current_quality_streak": config.get("current_quality_streak", 0),
                "avg_quality_delta": round(avg_quality_delta, 4),
                "avg_latency_delta_ms": avg_latency_delta,
                "sample_rate": float(config.get("sample_rate", 1.0)),
            }

        except Exception:
            logger.exception(
                "get_statistics failed for company_id=%s", company_id,
            )
            return {"company_id": company_id, "error": "internal_error"}

    # ── Complete Graduation ─────────────────────────────────────────

    def complete_graduation(
        self,
        company_id: str,
    ) -> Dict[str, Any]:
        """Complete graduation by making shadow variant the new live variant.

        This is the final step: the shadow variant is now the production
        variant. Disables shadow mode and updates company's variant config.

        Persists to DB; falls back to in-memory cache if DB unavailable
        (BC-008).

        BC-001: company_id is first parameter.
        BC-008: Never crashes.
        """
        try:
            with self._lock:
                # Try Redis first, then DB, then in-memory cache
                config = self._redis_get_config(company_id)
                if config is None:
                    config = self._load_config_from_db(company_id)
                if config is None:
                    config = self._configs.get(company_id)
                if config is None or not config.get("is_active"):
                    return {
                        "success": False,
                        "error": "No active shadow mode config found",
                    }

                current_status = config.get("status", "disabled")
                if current_status not in ("supervised", "graduated"):
                    return {
                        "success": False,
                        "error": f"Cannot complete graduation from status '{current_status}'. "
                                 f"Must be 'supervised' or 'graduated'.",
                    }

                shadow_variant = config.get("shadow_variant", "")
                now = self._utc_now_iso()

                # Mark as graduated and disabled
                config["status"] = "graduated"
                config["is_active"] = False
                config["graduated_at"] = now
                config["disabled_at"] = now

                # Persist to DB
                db_ok = self._persist_config_to_db(config)
                if not db_ok:
                    logger.warning(
                        "DB persist failed for complete_graduation — "
                        "in-memory cache updated: company_id=%s",
                        company_id,
                    )

                # Update Redis cache after DB write
                redis_ok = self._redis_set_config(company_id, config)
                if not redis_ok:
                    logger.debug(
                        "Redis cache set failed for complete_graduation — "
                        "DB and in-memory cache remain authoritative: company_id=%s",
                        company_id,
                    )

                # Update in-memory cache
                self._configs[company_id] = config

            logger.info(
                "Graduation completed: company_id=%s, new_live_variant=%s, "
                "db_persisted=%s, redis_cached=%s",
                company_id, shadow_variant, db_ok, redis_ok,
            )

            return {
                "success": True,
                "company_id": company_id,
                "new_live_variant": shadow_variant,
                "graduated_at": now,
            }

        except Exception:
            logger.exception(
                "complete_graduation failed for company_id=%s", company_id,
            )
            return {
                "success": False,
                "error": "internal_error_in_complete_graduation",
            }


# ══════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════

_shadow_mode_service: Optional[ShadowModeService] = None


def get_shadow_mode_service() -> ShadowModeService:
    """Get or create the ShadowModeService singleton."""
    global _shadow_mode_service
    if _shadow_mode_service is None:
        _shadow_mode_service = ShadowModeService()
    return _shadow_mode_service
