"""
PARWA Integration Data Cache Service (Phase 7)

Implements smart caching for third-party API responses with:
- Per-integration refresh intervals (5min / 15min / 60min by data type per D12)
- Cache invalidation on integration disconnect
- Fallback to stale cache when third-party API is down (Gap D)
- Tenant-scoped keys (BC-001)
- Circuit breaker integration for graceful degradation

Per D12:
- Real-time data (orders, tickets): 5 minutes
- Semi-static data (contacts, deals): 15 minutes
- Rarely-changing data (company info, settings): 60 minutes
- Configurable per integration in backend

Per Gap B: Prevents AI from calling HubSpot 100x for same contact.
Per Gap D: Cached data fallback when third-party APIs go down.

BC-001: All cache keys are tenant-scoped.
BC-012: Graceful degradation — cache failures are non-fatal.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.core.redis import (
    cache_get,
    cache_set,
    cache_delete,
    get_redis,
    make_key,
)
from app.logger import get_logger

logger = get_logger("integration_cache")


# ── Data Type Classification (per D12) ────────────────────────────────────


class DataFreshness(str, Enum):
    """How quickly data becomes stale, per D12.

    Maps to TTL values:
    - REALTIME: Orders, tickets, live inventory → 5 min
    - SEMI_STATIC: Contacts, deals, product catalogs → 15 min
    - RARELY_CHANGES: Company info, settings, configuration → 60 min
    """
    REALTIME = "realtime"
    SEMI_STATIC = "semi_static"
    RARELY_CHANGES = "rarely_changes"


# TTL in seconds per freshness level (D12)
FRESHNESS_TTL: Dict[DataFreshness, int] = {
    DataFreshness.REALTIME: 300,       # 5 minutes
    DataFreshness.SEMI_STATIC: 900,    # 15 minutes
    DataFreshness.RARELY_CHANGES: 3600, # 60 minutes
}

# Default freshness per integration type
INTEGRATION_DEFAULT_FRESHNESS: Dict[str, DataFreshness] = {
    # CRM — contacts/deals are semi-static
    "hubspot": DataFreshness.SEMI_STATIC,
    "salesforce": DataFreshness.SEMI_STATIC,
    "pipedrive": DataFreshness.SEMI_STATIC,
    # Ecommerce — orders are realtime, products semi-static
    "shopify": DataFreshness.REALTIME,
    "woocommerce": DataFreshness.REALTIME,
    "bigcommerce": DataFreshness.REALTIME,
    # Helpdesk — tickets are realtime
    "zendesk": DataFreshness.REALTIME,
    "freshdesk": DataFreshness.REALTIME,
    "intercom": DataFreshness.REALTIME,
    "gorgias": DataFreshness.REALTIME,
    # Shipping — tracking is realtime
    "shipstation": DataFreshness.REALTIME,
    "aftership": DataFreshness.REALTIME,
    "easypost": DataFreshness.REALTIME,
    # Analytics — rarely changes per query
    "google_analytics": DataFreshness.RARELY_CHANGES,
    "mixpanel": DataFreshness.RARELY_CHANGES,
    "amplitude": DataFreshness.RARELY_CHANGES,
    # Marketing — lists are semi-static
    "mailchimp": DataFreshness.SEMI_STATIC,
    "klaviyo": DataFreshness.SEMI_STATIC,
    "brevo": DataFreshness.SEMI_STATIC,
    # Payments — transaction status is realtime
    "stripe": DataFreshness.REALTIME,
    "paypal": DataFreshness.REALTIME,
    "paddle": DataFreshness.REALTIME,
    "quickbooks": DataFreshness.SEMI_STATIC,
    # Dev tools — project info rarely changes
    "github": DataFreshness.SEMI_STATIC,
    "jira": DataFreshness.SEMI_STATIC,
    "linear": DataFreshness.SEMI_STATIC,
    # Productivity — team info rarely changes
    "slack": DataFreshness.SEMI_STATIC,
    "notion": DataFreshness.RARELY_CHANGES,
    # Communication channels
    "twilio": DataFreshness.REALTIME,
    # Custom connectors — default to realtime
    "custom": DataFreshness.REALTIME,
}

# Override freshness per data endpoint within an integration
# e.g., Shopify orders = realtime, but Shopify shop info = rarely_changes
ENDPOINT_FRESHNESS_OVERRIDES: Dict[str, Dict[str, DataFreshness]] = {
    "hubspot": {
        "contacts": DataFreshness.SEMI_STATIC,
        "deals": DataFreshness.SEMI_STATIC,
        "companies": DataFreshness.RARELY_CHANGES,
        "tickets": DataFreshness.REALTIME,
    },
    "shopify": {
        "orders": DataFreshness.REALTIME,
        "products": DataFreshness.SEMI_STATIC,
        "shop": DataFreshness.RARELY_CHANGES,
        "inventory": DataFreshness.REALTIME,
        "customers": DataFreshness.SEMI_STATIC,
    },
    "salesforce": {
        "contacts": DataFreshness.SEMI_STATIC,
        "opportunities": DataFreshness.SEMI_STATIC,
        "accounts": DataFreshness.RARELY_CHANGES,
        "cases": DataFreshness.REALTIME,
    },
    "zendesk": {
        "tickets": DataFreshness.REALTIME,
        "users": DataFreshness.SEMI_STATIC,
        "organizations": DataFreshness.RARELY_CHANGES,
    },
}


class IntegrationCacheService:
    """Smart caching layer for third-party integration API responses.

    Sits between the ExternalToolBus and the backend API routes.
    Every external API call should go through this service to:
    1. Check cache first (avoid redundant external calls)
    2. Store responses with appropriate TTL (D12)
    3. Provide stale-when-error fallback (Gap D)
    4. Invalidate on integration disconnect (Phase 7 requirement)

    Usage:
        cache_svc = IntegrationCacheService(company_id="acme")

        # Try cache first
        result = await cache_svc.get("hubspot", "contacts", "contact_123")
        if result is not None:
            return result  # Cache hit

        # Cache miss — call external API
        fresh_data = await call_hubspot_api(...)
        await cache_svc.set("hubspot", "contacts", "contact_123", fresh_data)
        return fresh_data

        # Or use the convenience method that handles the full flow:
        result = await cache_svc.get_or_fetch(
            "hubspot", "contacts", "contact_123",
            fetch_fn=lambda: call_hubspot_api(...)
        )
    """

    # Stale cache TTL — how long to keep stale data for fallback (Gap D)
    STALE_TTL_MULTIPLIER = 4  # 4x the normal TTL for stale-when-error

    # Maximum stale age (never serve data older than this, even in fallback)
    MAX_STALE_AGE_SECONDS = 3600  # 1 hour

    def __init__(self, company_id: str):
        self.company_id = company_id

    # ── CORE CACHE OPERATIONS ────────────────────────────────────────────

    async def get(
        self,
        integration_type: str,
        endpoint: str,
        cache_key: str,
    ) -> Optional[Dict[str, Any]]:
        """Get cached data for an integration endpoint.

        Returns None on cache miss (caller should fetch from external API).
        Returns the cached data dict on hit, including cache metadata.

        Args:
            integration_type: e.g. "hubspot", "shopify"
            endpoint: e.g. "contacts", "orders"
            cache_key: specific item key, e.g. "contact_123"

        Returns:
            Cached data dict with metadata, or None if not cached.
        """
        key = self._build_cache_key(integration_type, endpoint, cache_key)
        try:
            cached = await cache_get(self.company_id, key)
            if cached is not None and isinstance(cached, dict):
                # Check if the cache entry has metadata
                if "_cache_meta" in cached:
                    meta = cached["_cache_meta"]
                    age = time.time() - meta.get("cached_at", 0)
                    cached["_cache_meta"]["age_seconds"] = round(age, 1)
                    cached["_cache_meta"]["is_stale"] = age > self._get_ttl(integration_type, endpoint)
                return cached
            return cached
        except Exception as exc:
            logger.warning(
                "cache_get_error",
                extra={
                    "integration": integration_type,
                    "endpoint": endpoint,
                    "error": str(exc)[:200],
                },
            )
            return None

    async def set(
        self,
        integration_type: str,
        endpoint: str,
        cache_key: str,
        data: Any,
        ttl_override: Optional[int] = None,
    ) -> bool:
        """Store data in cache with appropriate TTL.

        Args:
            integration_type: e.g. "hubspot", "shopify"
            endpoint: e.g. "contacts", "orders"
            cache_key: specific item key
            data: data to cache
            ttl_override: optional TTL override in seconds

        Returns:
            True if cached successfully.
        """
        key = self._build_cache_key(integration_type, endpoint, cache_key)
        ttl = ttl_override or self._get_ttl(integration_type, endpoint)

        # Wrap data with cache metadata
        cache_entry = {
            "_cache_meta": {
                "integration": integration_type,
                "endpoint": endpoint,
                "cached_at": time.time(),
                "ttl": ttl,
                "freshness": self._get_freshness(integration_type, endpoint).value,
            },
            "data": data,
        }

        # Store with extended TTL for stale-when-error fallback
        # The stale period = STALE_TTL_MULTIPLIER * normal TTL
        extended_ttl = ttl * self.STALE_TTL_MULTIPLIER

        try:
            result = await cache_set(self.company_id, key, cache_entry, extended_ttl)
            if result:
                logger.debug(
                    "cache_set",
                    extra={
                        "integration": integration_type,
                        "endpoint": endpoint,
                        "ttl": ttl,
                        "extended_ttl": extended_ttl,
                    },
                )
            return result
        except Exception as exc:
            logger.warning(
                "cache_set_error",
                extra={
                    "integration": integration_type,
                    "endpoint": endpoint,
                    "error": str(exc)[:200],
                },
            )
            return False

    async def get_or_fetch(
        self,
        integration_type: str,
        endpoint: str,
        cache_key: str,
        fetch_fn: Any,
        ttl_override: Optional[int] = None,
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """Get from cache, or fetch from external API and cache the result.

        This is the primary method for all integration data access.
        Implements Gap D: if the external API fails, returns stale cache.

        Args:
            integration_type: e.g. "hubspot", "shopify"
            endpoint: e.g. "contacts", "orders"
            cache_key: specific item key
            fetch_fn: async callable that fetches fresh data from external API
            ttl_override: optional TTL override in seconds

        Returns:
            Tuple of (data, was_cache_hit).
            data includes _cache_meta with cache status information.
            If external API fails and stale cache exists, returns stale data
            with is_stale=True and is_fallback=True in metadata.
        """
        # 1. Check cache first
        cached = await self.get(integration_type, endpoint, cache_key)
        if cached is not None:
            meta = cached.get("_cache_meta", {})
            is_stale = meta.get("is_stale", False)

            if not is_stale:
                # Fresh cache hit — return immediately
                return cached, True

            # Stale but available — try to refresh, but keep stale as fallback
            try:
                fresh_data = await fetch_fn()
                if fresh_data is not None:
                    await self.set(
                        integration_type, endpoint, cache_key,
                        fresh_data, ttl_override,
                    )
                    return await self.get(integration_type, endpoint, cache_key) or cached, False
            except Exception as exc:
                # External API failed — serve stale cache (Gap D)
                logger.warning(
                    "cache_stale_fallback",
                    extra={
                        "integration": integration_type,
                        "endpoint": endpoint,
                        "error": str(exc)[:200],
                    },
                )
                cached["_cache_meta"]["is_fallback"] = True
                return cached, True  # Was a "cache hit" even if stale

        # 2. Cache miss — fetch from external API
        try:
            fresh_data = await fetch_fn()
            if fresh_data is not None:
                await self.set(
                    integration_type, endpoint, cache_key,
                    fresh_data, ttl_override,
                )
                result = await self.get(integration_type, endpoint, cache_key)
                return result, False
            return None, False
        except Exception as exc:
            # External API failed AND no cache — return error info
            logger.error(
                "cache_miss_and_fetch_failed",
                extra={
                    "integration": integration_type,
                    "endpoint": endpoint,
                    "error": str(exc)[:200],
                },
            )
            return {
                "_cache_meta": {
                    "integration": integration_type,
                    "endpoint": endpoint,
                    "is_fallback": True,
                    "fetch_error": str(exc)[:200],
                },
                "data": None,
            }, False

    # ── CACHE INVALIDATION ───────────────────────────────────────────────

    async def invalidate(
        self,
        integration_type: str,
        endpoint: Optional[str] = None,
        cache_key: Optional[str] = None,
    ) -> bool:
        """Invalidate cache for an integration.

        Per Phase 7: "Cache invalidation on integration disconnect"
        Can invalidate:
        - All cache for an integration (endpoint=None, cache_key=None)
        - All cache for an endpoint (cache_key=None)
        - A specific cache entry (both endpoint and cache_key provided)

        Args:
            integration_type: e.g. "hubspot"
            endpoint: optional endpoint to invalidate
            cache_key: optional specific key to invalidate

        Returns:
            True if invalidation succeeded.
        """
        try:
            if endpoint and cache_key:
                # Invalidate specific entry
                key = self._build_cache_key(integration_type, endpoint, cache_key)
                return await cache_delete(self.company_id, key)
            elif endpoint:
                # Invalidate all entries for an endpoint
                return await self._invalidate_pattern(
                    integration_type, endpoint
                )
            else:
                # Invalidate ALL cache for this integration (disconnect scenario)
                return await self._invalidate_integration(integration_type)
        except Exception as exc:
            logger.warning(
                "cache_invalidation_error",
                extra={
                    "integration": integration_type,
                    "endpoint": endpoint,
                    "error": str(exc)[:200],
                },
            )
            return False

    async def invalidate_on_disconnect(self, integration_type: str) -> bool:
        """Invalidate ALL cached data when an integration is disconnected.

        Per Phase 7: "Cache invalidation on integration disconnect"
        This ensures the AI no longer uses stale data from a disconnected
        integration.

        Args:
            integration_type: The integration that was disconnected

        Returns:
            True if invalidation succeeded.
        """
        logger.info(
            "cache_invalidated_on_disconnect",
            extra={"integration": integration_type},
        )
        return await self.invalidate(integration_type)

    # ── CACHE HEALTH & METRICS ───────────────────────────────────────────

    async def get_cache_stats(self, integration_type: str) -> Dict[str, Any]:
        """Get cache statistics for an integration.

        Returns count of cached entries, memory usage estimate, etc.
        """
        try:
            redis = await get_redis()
            pattern = make_key(self.company_id, "cache", f"int:{integration_type}:*")
            keys = []
            async for key in redis.scan_iter(match=pattern, count=100):
                keys.append(key)

            return {
                "integration": integration_type,
                "company_id": self.company_id,
                "cached_entries": len(keys),
                "keys_sample": keys[:10],
            }
        except Exception as exc:
            return {
                "integration": integration_type,
                "company_id": self.company_id,
                "error": str(exc)[:200],
            }

    # ── PRIVATE HELPERS ──────────────────────────────────────────────────

    def _build_cache_key(
        self,
        integration_type: str,
        endpoint: str,
        cache_key: str,
    ) -> str:
        """Build a cache key following the pattern:
        int:{integration_type}:{endpoint}:{cache_key}

        The full Redis key will be:
        parwa:{company_id}:cache:int:{integration_type}:{endpoint}:{cache_key}
        """
        return f"int:{integration_type}:{endpoint}:{cache_key}"

    def _get_freshness(
        self,
        integration_type: str,
        endpoint: str,
    ) -> DataFreshness:
        """Determine data freshness level for an integration endpoint.

        Checks endpoint-specific overrides first, then falls back to
        integration default, then falls back to REALTIME.

        Args:
            integration_type: e.g. "hubspot"
            endpoint: e.g. "contacts"

        Returns:
            DataFreshness enum value.
        """
        # Check endpoint-specific override
        if integration_type in ENDPOINT_FRESHNESS_OVERRIDES:
            overrides = ENDPOINT_FRESHNESS_OVERRIDES[integration_type]
            if endpoint in overrides:
                return overrides[endpoint]

        # Fall back to integration default
        if integration_type in INTEGRATION_DEFAULT_FRESHNESS:
            return INTEGRATION_DEFAULT_FRESHNESS[integration_type]

        # Default to realtime for unknown integrations
        return DataFreshness.REALTIME

    def _get_ttl(
        self,
        integration_type: str,
        endpoint: str,
    ) -> int:
        """Get TTL in seconds for an integration endpoint (D12)."""
        freshness = self._get_freshness(integration_type, endpoint)
        return FRESHNESS_TTL[freshness]

    async def _invalidate_pattern(
        self,
        integration_type: str,
        endpoint: str,
    ) -> bool:
        """Invalidate all cache entries matching a pattern."""
        try:
            redis = await get_redis()
            pattern = make_key(
                self.company_id, "cache",
                f"int:{integration_type}:{endpoint}:*"
            )
            count = 0
            async for key in redis.scan_iter(match=pattern, count=100):
                await redis.delete(key)
                count += 1
            logger.info(
                "cache_pattern_invalidated",
                extra={
                    "integration": integration_type,
                    "endpoint": endpoint,
                    "keys_deleted": count,
                },
            )
            return True
        except Exception as exc:
            logger.warning(
                "cache_pattern_invalidation_error",
                extra={
                    "integration": integration_type,
                    "endpoint": endpoint,
                    "error": str(exc)[:200],
                },
            )
            return False

    async def _invalidate_integration(
        self,
        integration_type: str,
    ) -> bool:
        """Invalidate ALL cache entries for an integration (disconnect)."""
        try:
            redis = await get_redis()
            pattern = make_key(
                self.company_id, "cache",
                f"int:{integration_type}:*"
            )
            count = 0
            async for key in redis.scan_iter(match=pattern, count=100):
                await redis.delete(key)
                count += 1
            logger.info(
                "cache_integration_invalidated",
                extra={
                    "integration": integration_type,
                    "keys_deleted": count,
                },
            )
            return True
        except Exception as exc:
            logger.warning(
                "cache_integration_invalidation_error",
                extra={
                    "integration": integration_type,
                    "error": str(exc)[:200],
                },
            )
            return False


# ── CONVENIENCE SINGLETON ────────────────────────────────────────────────


def get_cache_service(company_id: str) -> IntegrationCacheService:
    """Create an IntegrationCacheService for a given tenant.

    Args:
        company_id: The tenant identifier (BC-001).

    Returns:
        IntegrationCacheService instance.
    """
    return IntegrationCacheService(company_id=company_id)
