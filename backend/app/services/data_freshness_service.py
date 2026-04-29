"""
Data Freshness Service — SG-34: Data Freshness for RAG

Ensures RAG pipeline uses fresh data by tracking staleness across
knowledge base documents, extracted signals, conversation context,
and cached RAG results. Provides cache invalidation on KB updates,
staleness detection (>5min re-extract trigger), and context
freshness checks.

Storage Pattern:
- Freshness timestamps in Redis:
  parwa:{company_id}:freshness:{entity_type}:{entity_id}
- JSON payload: {updated_at, entity_type, entity_id, company_id}
- TTL-based expiry for automatic cleanup

BC-001: All keys scoped by company_id.
BC-008: Graceful degradation — never crash on Redis failure.
W9-GAP-027: Uses Redis EXPIRETIME for accurate staleness when
  available, falls back to stored timestamp.
W9-GAP-028: Batch freshness check via pipeline for performance.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("data_freshness_service")

ENTITY_TYPES = (
    "signal",
    "context",
    "rag_cache",
    "embedding",
    "kb_document",
    "technique_cache",
)

KBCallback = Callable[[str, str, str], None]


class FreshnessStatus(str, Enum):
    """Freshness status of a cached entity."""

    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


@dataclass
class FreshnessCheckResult:
    """Result of a freshness check for a single entity."""

    status: FreshnessStatus
    age_seconds: float
    max_age_seconds: float
    is_fresh: bool
    last_updated: Optional[str]
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StalenessConfig:
    """Configurable freshness thresholds per entity type.

    Defaults: signals=5min, context=30min, rag_cache=2min,
    embeddings=1hr, kb_document=1hr.
    """

    signal_max_age_seconds: float = 300.0
    context_max_age_seconds: float = 1800.0
    rag_cache_max_age_seconds: float = 120.0
    embedding_max_age_seconds: float = 3600.0
    kb_document_max_age_seconds: float = 3600.0


class DataFreshnessService:
    """SG-34: Data freshness tracking and cache invalidation for RAG.

    All Redis keys follow BC-001 tenant isolation:
    parwa:{company_id}:freshness:{entity_type}:{entity_id}
    All Redis operations degrade gracefully per BC-008.

    Usage::

        svc = DataFreshnessService()
        result = await svc.check_signal_freshness(
            query_hash="abc", company_id="t1",
            variant_type="sentiment",
        )
        if not result.is_fresh:
            ...  # Re-extract signals
        await svc.invalidate_kb_caches("doc1", "t1")
    """

    def __init__(
        self,
        config: Optional[StalenessConfig] = None,
    ) -> None:
        """Initialize with configurable thresholds."""
        self.config = config or StalenessConfig()
        self._kb_listeners: List[KBCallback] = []

    # ── Freshness Checks ───────────────────────────────────────────

    async def check_cache_freshness(
        self,
        cache_key: str,
        company_id: str,
    ) -> FreshnessCheckResult:
        """Check freshness of a generic cache entry."""
        return await self._safe_check(
            company_id=company_id,
            entity_type="rag_cache",
            entity_id=cache_key,
            source="cache",
            log_label="check_cache_freshness_error",
            log_key=cache_key,
        )

    async def check_signal_freshness(
        self,
        query_hash: str,
        company_id: str,
        variant_type: str,
    ) -> FreshnessCheckResult:
        """Check if extracted signals are still fresh (<5 min)."""
        entity_id = f"signal:{variant_type}:{query_hash}"
        return await self._safe_check(
            company_id=company_id,
            entity_type="signal",
            entity_id=entity_id,
            source="signal",
            log_label="check_signal_freshness_error",
            log_key=entity_id,
            extra_meta={"variant_type": variant_type},
        )

    async def check_context_freshness(
        self,
        conversation_id: str,
        company_id: str,
    ) -> FreshnessCheckResult:
        """Check conversation context freshness (<30 min)."""
        return await self._safe_check(
            company_id=company_id,
            entity_type="context",
            entity_id=conversation_id,
            source="context",
            log_label="check_context_freshness_error",
            log_key=conversation_id,
        )

    async def check_rag_freshness(
        self,
        query: str,
        company_id: str,
        variant_type: str,
    ) -> FreshnessCheckResult:
        """Check RAG cache freshness (<2 min)."""
        qh = self._hash_query(query)
        entity_id = f"rag:{variant_type}:{qh}"
        return await self._safe_check(
            company_id=company_id,
            entity_type="rag_cache",
            entity_id=entity_id,
            source="rag_cache",
            log_label="check_rag_freshness_error",
            log_key=entity_id,
            extra_meta={"variant_type": variant_type},
        )

    # ── Batch Check (W9-GAP-028) ───────────────────────────────────

    async def batch_check_freshness(
        self,
        keys: List[Dict[str, str]],
        company_id: str,
    ) -> Dict[str, FreshnessCheckResult]:
        """Check freshness of multiple keys in one Redis round trip.

        W9-GAP-028: Uses Redis pipeline for performance.

        Each key dict: {entity_type, entity_id, source?}.
        """
        results: Dict[str, FreshnessCheckResult] = {}
        if not keys:
            return results

        try:
            client = await self._get_redis()
            pipe = client.pipeline()
            redis_keys = []
            for ks in keys:
                et = ks.get("entity_type", "signal")
                eid = ks["entity_id"]
                rk = self._fkey(company_id, et, eid)
                redis_keys.append(rk)
                pipe.get(rk)
                pipe.expiretime(rk)

            pipe_results = await pipe.execute()
            now = time.time()

            for i, ks in enumerate(keys):
                et = ks.get("entity_type", "signal")
                eid = ks["entity_id"]
                src = ks.get("source", et)
                ma = self._max_age(et)
                jv = pipe_results[i * 2]
                ep = pipe_results[i * 2 + 1]
                results[eid] = self._evaluate(
                    jv,
                    ep,
                    ma,
                    src,
                    et,
                    eid,
                    company_id,
                    now,
                )
        except Exception as exc:
            logger.warning(
                "batch_check_freshness_error",
                error=str(exc),
                key_count=len(keys),
                company_id=company_id,
            )
            for ks in keys:
                eid = ks["entity_id"]
                et = ks.get("entity_type", "signal")
                ma = self._max_age(et)
                results[eid] = FreshnessCheckResult(
                    status=FreshnessStatus.UNKNOWN,
                    age_seconds=0.0,
                    max_age_seconds=ma,
                    is_fresh=False,
                    last_updated=None,
                    source=ks.get("source", et),
                    metadata={"error": str(exc)},
                )
        return results

    # ── Cache Invalidation ─────────────────────────────────────────

    async def invalidate_cache(
        self,
        cache_key: str,
        company_id: str,
    ) -> bool:
        """Delete a single stale cache entry from Redis."""
        fk = self._fkey(company_id, "rag_cache", cache_key)
        dk = self._dkey(company_id, "rag_cache", cache_key)
        try:
            client = await self._get_redis()
            pipe = client.pipeline()
            pipe.delete(fk)
            pipe.delete(dk)
            res = await pipe.execute()
            deleted = sum(1 for r in res if r)
            logger.info(
                "cache_invalidated",
                cache_key=cache_key[:64],
                company_id=company_id,
                keys_deleted=deleted,
            )
            return deleted > 0
        except Exception as exc:
            logger.warning(
                "invalidate_cache_error",
                error=str(exc),
                cache_key=cache_key[:64],
                company_id=company_id,
            )
            return False

    async def invalidate_kb_caches(
        self,
        document_id: str,
        company_id: str,
    ) -> int:
        """Invalidate all RAG caches related to a KB document.

        Uses SCAN for non-blocking iteration. Triggers registered
        KB update listeners after invalidation.
        """
        from app.core.redis import make_key

        pattern = make_key(
            company_id,
            "freshness",
            "rag_cache",
            "*",
        )
        total = 0

        try:
            client = await self._get_redis()
            cursor = 0
            while True:
                cursor, keys = await client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100,
                )
                if keys:
                    pipe = client.pipeline()
                    for k in keys:
                        pipe.get(k)
                    vals = await pipe.execute()

                    del_keys, data_keys = [], []
                    for k, v in zip(keys, vals):
                        if not v:
                            continue
                        try:
                            d = json.loads(v)
                            if d.get("document_id") == document_id:
                                del_keys.append(k)
                                data_keys.append(
                                    k.replace(
                                        ":freshness:",
                                        ":cache:",
                                    )
                                )
                        except (json.JSONDecodeError, TypeError):
                            continue

                    if del_keys:
                        dp = client.pipeline()
                        for dk in del_keys + data_keys:
                            dp.delete(dk)
                        dr = await dp.execute()
                        total += sum(1 for r in dr if r)

                if cursor == 0:
                    break

            logger.info(
                "kb_caches_invalidated",
                document_id=document_id,
                company_id=company_id,
                keys_invalidated=total,
            )
        except Exception as exc:
            logger.warning(
                "invalidate_kb_caches_error",
                error=str(exc),
                document_id=document_id,
                company_id=company_id,
            )

        await self._notify_kb_listeners(document_id, company_id)
        return total

    # ── Update Recording ───────────────────────────────────────────

    async def record_update(
        self,
        entity_type: str,
        entity_id: str,
        company_id: str,
    ) -> None:
        """Record that an entity was updated.

        Stores a freshness timestamp in Redis with automatic
        TTL cleanup (2x the max age for safety margin).
        """
        if entity_type not in ENTITY_TYPES:
            logger.warning(
                "record_update_invalid_type",
                entity_type=entity_type,
                entity_id=entity_id[:64],
                company_id=company_id,
            )
            return

        rk = self._fkey(company_id, entity_type, entity_id)
        ma = self._max_age(entity_type)
        ttl = int(ma * 2)
        now = datetime.now(timezone.utc)
        payload = {
            "updated_at": now.isoformat(),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "company_id": company_id,
        }

        try:
            client = await self._get_redis()
            pipe = client.pipeline()
            pipe.set(rk, json.dumps(payload), ex=ttl)
            dk = self._dkey(company_id, entity_type, entity_id)
            pipe.expire(dk, ttl)
            await pipe.execute()
            logger.debug(
                "recorded_update",
                entity_type=entity_type,
                entity_id=entity_id[:64],
                company_id=company_id,
                ttl=ttl,
            )
        except Exception as exc:
            logger.warning(
                "record_update_error",
                error=str(exc),
                entity_type=entity_type,
                entity_id=entity_id[:64],
                company_id=company_id,
            )

    # ── Freshness Report ───────────────────────────────────────────

    async def get_freshness_report(
        self,
        company_id: str,
    ) -> Dict[str, Any]:
        """Aggregate freshness status across all entity types.

        Scans all freshness keys for the tenant and returns
        counts by status and entity type.
        """
        from app.core.redis import make_key

        pattern = make_key(company_id, "freshness", "*")
        report: Dict[str, Any] = {
            "company_id": company_id,
            "checked_at": datetime.now(
                timezone.utc,
            ).isoformat(),
            "summary": {
                "fresh": 0,
                "stale": 0,
                "expired": 0,
                "unknown": 0,
                "total": 0,
            },
            "by_entity_type": {},
        }
        now = time.time()

        try:
            client = await self._get_redis()
            cursor = 0
            while True:
                cursor, keys = await client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=200,
                )
                if keys:
                    pipe = client.pipeline()
                    for k in keys:
                        pipe.get(k)
                        pipe.expiretime(k)
                    pr = await pipe.execute()

                    for i, k in enumerate(keys):
                        jv = pr[i * 2]
                        ep = pr[i * 2 + 1]
                        et = self._extract_et(k, company_id) or "unknown"
                        ma = self._max_age(et)
                        r = self._evaluate(
                            jv,
                            ep,
                            ma,
                            et,
                            et,
                            "",
                            company_id,
                            now,
                        )
                        sk = r.status.value
                        report["summary"][sk] += 1
                        report["summary"]["total"] += 1

                        if et not in report["by_entity_type"]:
                            report["by_entity_type"][et] = {
                                "fresh": 0,
                                "stale": 0,
                                "expired": 0,
                                "unknown": 0,
                                "total": 0,
                            }
                        report["by_entity_type"][et][sk] += 1
                        report["by_entity_type"][et]["total"] += 1

                if cursor == 0:
                    break
        except Exception as exc:
            logger.warning(
                "get_freshness_report_error",
                error=str(exc),
                company_id=company_id,
            )
        return report

    # ── Convenience Predicates ─────────────────────────────────────

    async def needs_re_extraction(
        self,
        query_hash: str,
        company_id: str,
        variant_type: str,
    ) -> bool:
        """Returns True if signals need re-extraction."""
        r = await self.check_signal_freshness(
            query_hash,
            company_id,
            variant_type,
        )
        return not r.is_fresh

    async def needs_rag_refresh(
        self,
        query: str,
        company_id: str,
        variant_type: str,
    ) -> bool:
        """Returns True if RAG results need refresh."""
        r = await self.check_rag_freshness(
            query,
            company_id,
            variant_type,
        )
        return not r.is_fresh

    # ── KB Update Listener ─────────────────────────────────────────

    def register_kb_update_listener(
        self,
        callback: KBCallback,
    ) -> None:
        """Register callback for KB document updates."""
        self._kb_listeners.append(callback)
        logger.info(
            "kb_update_listener_registered",
            listener_count=len(self._kb_listeners),
        )

    async def _notify_kb_listeners(
        self,
        document_id: str,
        company_id: str,
    ) -> None:
        """Invoke all registered KB update listeners (BC-008)."""
        for cb in self._kb_listeners:
            try:
                result = cb(document_id, company_id, "kb_document")
                if hasattr(result, "__await__"):
                    await result
            except Exception as exc:
                logger.warning(
                    "kb_listener_error",
                    error=str(exc),
                    document_id=document_id,
                    company_id=company_id,
                    callback=getattr(
                        cb,
                        "__name__",
                        str(cb),
                    ),
                )

    # ── Internal: Redis Interaction ────────────────────────────────

    async def _get_redis(self):
        from app.core.redis import get_redis

        return await get_redis()

    async def _safe_check(
        self,
        company_id: str,
        entity_type: str,
        entity_id: str,
        source: str,
        log_label: str,
        log_key: str,
        extra_meta: Optional[Dict] = None,
    ) -> FreshnessCheckResult:
        """Wrap a freshness check with error handling (BC-008)."""
        rk = self._fkey(company_id, entity_type, entity_id)
        ma = self._max_age(entity_type)
        try:
            client = await self._get_redis()
            pipe = client.pipeline()
            pipe.get(rk)
            pipe.expiretime(rk)
            results = await pipe.execute()
            return self._evaluate(
                results[0],
                results[1],
                ma,
                source,
                entity_type,
                entity_id,
                company_id,
                time.time(),
            )
        except Exception as exc:
            logger.warning(
                log_label,
                error=str(exc),
                entity_id=log_key[:64],
                company_id=company_id,
            )
            meta: Dict[str, Any] = {"error": str(exc)}
            if extra_meta:
                meta.update(extra_meta)
            return FreshnessCheckResult(
                status=FreshnessStatus.UNKNOWN,
                age_seconds=0.0,
                max_age_seconds=ma,
                is_fresh=False,
                last_updated=None,
                source=source,
                metadata=meta,
            )

    def _evaluate(
        self,
        json_val: Any,
        expire_epoch: Any,
        max_age: float,
        source: str,
        entity_type: str,
        entity_id: str,
        company_id: str,
        now: float,
    ) -> FreshnessCheckResult:
        """Evaluate freshness from Redis GET + EXPIRETIME.

        W9-GAP-027: Prefers EXPIRETIME for accurate staleness,
        falls back to stored updated_at timestamp.
        """
        meta: Dict[str, Any] = {
            "entity_type": entity_type,
            "company_id": company_id,
        }

        # Key does not exist
        if expire_epoch == -2 or (json_val is None and expire_epoch is None):
            return FreshnessCheckResult(
                FreshnessStatus.EXPIRED,
                0.0,
                max_age,
                False,
                None,
                source,
                meta,
            )

        # W9-GAP-027: Use EXPIRETIME when available
        if expire_epoch is not None and expire_epoch > 0:
            ttl = expire_epoch - now
            if ttl <= 0:
                return FreshnessCheckResult(
                    FreshnessStatus.EXPIRED,
                    max_age,
                    max_age,
                    False,
                    self._updated_at(json_val),
                    source,
                    {**meta, "method": "expiretime"},
                )
            age = max_age - ttl
            st = self._status(age, max_age)
            return FreshnessCheckResult(
                st,
                round(age, 2),
                max_age,
                st == FreshnessStatus.FRESH,
                self._updated_at(json_val),
                source,
                {**meta, "method": "expiretime"},
            )

        # Fallback: parse stored timestamp
        ua = self._updated_at(json_val)
        if ua is None:
            return FreshnessCheckResult(
                FreshnessStatus.UNKNOWN,
                0.0,
                max_age,
                False,
                None,
                source,
                {**meta, "method": "fallback_no_ts"},
            )
        try:
            dt = datetime.fromisoformat(ua)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age = max(0.0, now - dt.timestamp())
        except (ValueError, TypeError, OSError):
            return FreshnessCheckResult(
                FreshnessStatus.UNKNOWN,
                0.0,
                max_age,
                False,
                ua,
                source,
                {**meta, "method": "fallback_parse_err"},
            )
        st = self._status(age, max_age)
        return FreshnessCheckResult(
            st,
            round(age, 2),
            max_age,
            st == FreshnessStatus.FRESH,
            ua,
            source,
            {**meta, "method": "fallback_ts"},
        )

    # ── Internal: Helpers ──────────────────────────────────────────

    @staticmethod
    def _status(age: float, max_age: float) -> FreshnessStatus:
        """Compute status: FRESH <= max, STALE <= 1.5x, else EXPIRED."""
        if age <= max_age:
            return FreshnessStatus.FRESH
        if age <= max_age * 1.5:
            return FreshnessStatus.STALE
        return FreshnessStatus.EXPIRED

    def _max_age(self, entity_type: str) -> float:
        """Get max age threshold for an entity type."""
        m = {
            "signal": self.config.signal_max_age_seconds,
            "context": self.config.context_max_age_seconds,
            "rag_cache": (self.config.rag_cache_max_age_seconds),
            "embedding": (self.config.embedding_max_age_seconds),
            "kb_document": (self.config.kb_document_max_age_seconds),
            "technique_cache": (self.config.rag_cache_max_age_seconds),
        }
        return m.get(
            entity_type,
            self.config.rag_cache_max_age_seconds,
        )

    def _fkey(
        self,
        company_id: str,
        et: str,
        eid: str,
    ) -> str:
        """Build freshness Redis key (BC-001)."""
        from app.core.redis import make_key

        return make_key(company_id, "freshness", et, eid)

    def _dkey(
        self,
        company_id: str,
        et: str,
        eid: str,
    ) -> str:
        """Build data Redis key (BC-001)."""
        from app.core.redis import make_key

        return make_key(company_id, "cache", et, eid)

    @staticmethod
    def _hash_query(query: str) -> str:
        """SHA-256 hash of query for cache keys."""
        return hashlib.sha256(
            query.encode("utf-8"),
        ).hexdigest()[:32]

    @staticmethod
    def _updated_at(json_val: Any) -> Optional[str]:
        """Extract updated_at from JSON value."""
        if json_val is None:
            return None
        try:
            d = json.loads(json_val) if isinstance(json_val, str) else json_val
            if isinstance(d, dict):
                return d.get("updated_at")
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    @staticmethod
    def _extract_et(
        redis_key: str,
        company_id: str,
    ) -> Optional[str]:
        """Extract entity_type from Redis key."""
        try:
            p = f"parwa:{company_id}:freshness:"
            if redis_key.startswith(p):
                return redis_key[len(p) :].split(":")[0]
        except (IndexError, AttributeError):
            pass
        return None
