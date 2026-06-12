"""ExternalToolBus — Shared HTTP client for all external API calls (PHASE 15).

Architecture:
  Frontend → BFF → Backend → ExternalToolBus → External API
  MCP Server → ExternalToolBus → External API  (same bus, no duplicate code)

Features:
  - Retry: 3x exponential backoff for retriable errors (5xx, network timeout)
  - Circuit Breaker: per integration, auto-open after 5 consecutive failures, auto-close after 60s
  - Cache: in-memory TTL cache with configurable refresh per data type (5/15/60 min per D12)
  - Structured error propagation with degraded data fallback
  - Audit trail logging for all external calls
"""

import asyncio
import json
import time
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("parwa.external_tool_bus")


# ===================== Circuit Breaker =====================

class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation — requests flow through
    OPEN = "open"          # Failing — requests are blocked, return cached/error
    HALF_OPEN = "half_open"  # Testing recovery — allow one request through


class CircuitBreaker:
    """Per-integration circuit breaker.

    Rules:
    - Auto-opens after 5 consecutive failures
    - Auto-closes after 60 seconds (enters HALF_OPEN first)
    - In HALF_OPEN, one request is allowed; if it succeeds, circuit closes; if it fails, circuit re-opens
    """

    FAILURE_THRESHOLD = 5
    RECOVERY_TIMEOUT_SECONDS = 60

    def __init__(self):
        self._circuits: Dict[str, Dict[str, Any]] = {}

    def _get_circuit(self, integration_id: str) -> Dict[str, Any]:
        if integration_id not in self._circuits:
            self._circuits[integration_id] = {
                "state": CircuitState.CLOSED,
                "failure_count": 0,
                "last_failure_time": None,
                "last_success_time": None,
            }
        return self._circuits[integration_id]

    def can_proceed(self, integration_id: str) -> bool:
        """Check if a request can proceed through the circuit."""
        circuit = self._get_circuit(integration_id)

        if circuit["state"] == CircuitState.CLOSED:
            return True

        if circuit["state"] == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if circuit["last_failure_time"]:
                elapsed = (datetime.utcnow() - circuit["last_failure_time"]).total_seconds()
                if elapsed >= self.RECOVERY_TIMEOUT_SECONDS:
                    circuit["state"] = CircuitState.HALF_OPEN
                    logger.info(f"Circuit breaker for {integration_id}: OPEN → HALF_OPEN")
                    return True
            return False

        if circuit["state"] == CircuitState.HALF_OPEN:
            # Allow one request through to test recovery
            return True

        return False

    def record_success(self, integration_id: str):
        """Record a successful call — close the circuit if it was half-open."""
        circuit = self._get_circuit(integration_id)
        circuit["failure_count"] = 0
        circuit["last_success_time"] = datetime.utcnow()

        if circuit["state"] == CircuitState.HALF_OPEN:
            circuit["state"] = CircuitState.CLOSED
            logger.info(f"Circuit breaker for {integration_id}: HALF_OPEN → CLOSED")

    def record_failure(self, integration_id: str):
        """Record a failed call — open the circuit if threshold reached."""
        circuit = self._get_circuit(integration_id)
        circuit["failure_count"] += 1
        circuit["last_failure_time"] = datetime.utcnow()

        if circuit["state"] == CircuitState.HALF_OPEN:
            circuit["state"] = CircuitState.OPEN
            logger.info(f"Circuit breaker for {integration_id}: HALF_OPEN → OPEN (test request failed)")

        elif circuit["failure_count"] >= self.FAILURE_THRESHOLD:
            circuit["state"] = CircuitState.OPEN
            logger.info(
                f"Circuit breaker for {integration_id}: CLOSED → OPEN "
                f"({circuit['failure_count']} consecutive failures)"
            )

    def get_state(self, integration_id: str) -> Dict[str, Any]:
        """Get current circuit breaker state for an integration."""
        circuit = self._get_circuit(integration_id)
        return {
            "integration_id": integration_id,
            "state": circuit["state"].value if isinstance(circuit["state"], CircuitState) else circuit["state"],
            "failure_count": circuit["failure_count"],
            "last_failure_time": circuit["last_failure_time"].isoformat() if circuit["last_failure_time"] else None,
            "last_success_time": circuit["last_success_time"].isoformat() if circuit["last_success_time"] else None,
        }

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get circuit breaker states for all tracked integrations."""
        return {iid: self.get_state(iid) for iid in self._circuits}

    def reset(self, integration_id: str):
        """Manually reset a circuit breaker."""
        if integration_id in self._circuits:
            self._circuits[integration_id] = {
                "state": CircuitState.CLOSED,
                "failure_count": 0,
                "last_failure_time": None,
                "last_success_time": None,
            }


# ===================== TTL Cache =====================

class CacheEntry:
    """A single cache entry with TTL."""

    def __init__(self, data: Any, ttl_seconds: int):
        self.data = data
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds

    @property
    def is_fresh(self) -> bool:
        return (time.time() - self.created_at) < self.ttl_seconds

    @property
    def age_seconds(self) -> int:
        return int(time.time() - self.created_at)

    @property
    def age_description(self) -> str:
        age = self.age_seconds
        if age < 60:
            return f"{age} seconds ago"
        elif age < 3600:
            return f"{age // 60} minutes ago"
        else:
            return f"{age // 3600} hours ago"


class DataCache:
    """In-memory TTL cache with configurable refresh per data type.

    Cache TTL per D12:
    - Real-time data (orders, tickets): 5 minutes
    - Semi-static data (contacts, deals): 15 minutes
    - Rarely-changing data (company info, settings): 60 minutes
    """

    # TTL in seconds per data type
    TTL_CONFIG = {
        "realtime": 300,      # 5 minutes
        "semi_static": 900,   # 15 minutes
        "static": 3600,       # 60 minutes
    }

    DEFAULT_TTL = 300  # 5 minutes default

    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}

    def _make_key(self, integration_id: str, path: str) -> str:
        return f"{integration_id}:{path}"

    def get(self, integration_id: str, path: str) -> Optional[CacheEntry]:
        """Get cached data if it exists and is fresh."""
        key = self._make_key(integration_id, path)
        entry = self._cache.get(key)
        if entry and entry.is_fresh:
            return entry
        # Return stale entry if it exists (for degraded fallback)
        return entry  # May be None or stale

    def get_stale(self, integration_id: str, path: str) -> Optional[CacheEntry]:
        """Get cached data even if stale (for degraded fallback)."""
        key = self._make_key(integration_id, path)
        return self._cache.get(key)

    def set(
        self,
        integration_id: str,
        path: str,
        data: Any,
        data_type: str = "realtime",
    ):
        """Cache data with appropriate TTL."""
        key = self._make_key(integration_id, path)
        ttl = self.TTL_CONFIG.get(data_type, self.DEFAULT_TTL)
        self._cache[key] = CacheEntry(data=data, ttl_seconds=ttl)

    def invalidate(self, integration_id: str, path: str = None):
        """Invalidate cache for an integration. If path is None, invalidate all entries."""
        if path:
            key = self._make_key(integration_id, path)
            self._cache.pop(key, None)
        else:
            # Remove all entries for this integration
            prefix = f"{integration_id}:"
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._cache[k]

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = len(self._cache)
        fresh = sum(1 for e in self._cache.values() if e.is_fresh)
        stale = total - fresh
        return {
            "total_entries": total,
            "fresh_entries": fresh,
            "stale_entries": stale,
            "ttl_config": self.TTL_CONFIG,
        }


# ===================== Structured Error Format =====================

class ToolBusError:
    """Structured error response from ExternalToolBus.

    This error format propagates through:
      ExternalToolBus → Backend → BFF → Frontend
    """

    # Error codes that map to user-facing behavior
    ERROR_CODES = {
        "external_api_down": "The external service is currently unavailable",
        "auth_failed": "Authentication with the external service failed",
        "rate_limited": "The external service rate limit has been exceeded",
        "circuit_open": "The circuit breaker is open — too many recent failures",
        "network_error": "Could not connect to the external service",
        "timeout": "The external service did not respond in time",
        "invalid_response": "The external service returned an invalid response",
        "retriable_failure": "A temporary error occurred; the request was retried",
        "all_retries_failed": "All retry attempts failed",
    }

    def __init__(
        self,
        error_code: str,
        message: str,
        integration_id: str,
        is_retriable: bool = False,
        degraded_data: Any = None,
        cache_age_description: str = None,
        retry_attempts: int = 0,
        status_code: int = None,
    ):
        self.error_code = error_code
        self.message = message
        self.integration_id = integration_id
        self.is_retriable = is_retriable
        self.degraded_data = degraded_data
        self.cache_age_description = cache_age_description
        self.retry_attempts = retry_attempts
        self.status_code = status_code

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": False,
            "error": self.error_code,
            "message": self.message,
            "integration_id": self.integration_id,
            "is_retriable": self.is_retriable,
        }
        if self.degraded_data is not None:
            result["data"] = self.degraded_data
            result["degraded"] = True
            result["data_age"] = self.cache_age_description or "unknown age"
        if self.retry_attempts > 0:
            result["retry_attempts"] = self.retry_attempts
        if self.status_code:
            result["status_code"] = self.status_code
        return result


# ===================== ExternalToolBus =====================

class ExternalToolBus:
    """Shared HTTP client for all external API calls.

    Usage:
        bus = ExternalToolBus()
        result = await bus.call(
            integration_id="hubspot",
            method="GET",
            url="https://api.hubapi.com/crm/v3/contacts",
            headers={"Authorization": "Bearer xxx"},
            data_type="semi_static",
        )
        # result is either the response data or a ToolBusError
    """

    MAX_RETRIES = 3
    BACKOFF_BASE_SECONDS = 1  # 1s, 2s, 4s
    REQUEST_TIMEOUT_SECONDS = 15

    # Status codes that are retriable
    RETRIABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

    def __init__(self):
        self.circuit_breaker = CircuitBreaker()
        self.cache = DataCache()

    async def call(
        self,
        integration_id: str,
        method: str = "GET",
        url: str = "",
        headers: Dict[str, str] = None,
        auth: tuple = None,
        body: Any = None,
        data_type: str = "realtime",
        use_cache: bool = True,
        tenant_id: str = None,
        actor: str = None,
        db=None,
    ) -> Dict[str, Any]:
        """Make an HTTP call through the tool bus with all protections.

        Returns a dict with either:
          { "success": True, "data": ..., "from_cache": bool }
          { "success": False, "error": ..., "degraded": True, "data": cached_fallback }
        """
        # 1. Check cache first (for GET requests)
        if use_cache and method.upper() == "GET":
            cached = self.cache.get(integration_id, url)
            if cached and cached.is_fresh:
                return {
                    "success": True,
                    "data": cached.data,
                    "from_cache": True,
                    "cache_age": cached.age_description,
                }

        # 2. Check circuit breaker
        if not self.circuit_breaker.can_proceed(integration_id):
            # Circuit is open — try to return cached fallback
            stale = self.cache.get_stale(integration_id, url) if use_cache else None
            error = ToolBusError(
                error_code="circuit_open",
                message=f"Circuit breaker is open for {integration_id}. Too many recent failures.",
                integration_id=integration_id,
                is_retriable=False,
                degraded_data=stale.data if stale else None,
                cache_age_description=stale.age_description if stale else None,
            )

            # Log to audit trail
            await self._log_audit(
                db=db, tenant_id=tenant_id, actor=actor,
                integration_id=integration_id, action="external_call.blocked",
                details={"reason": "circuit_open", "url": url},
                severity="warning",
            )

            return error.to_dict()

        # 3. Make the HTTP call with retry logic
        last_error = None
        retry_attempts = 0

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT_SECONDS) as client:
                    kwargs = {"headers": headers or {}}
                    if auth:
                        kwargs["auth"] = auth

                    if method.upper() == "GET":
                        resp = await client.get(url, **kwargs)
                    elif method.upper() == "POST":
                        resp = await client.post(url, content=body, **kwargs)
                    elif method.upper() == "PUT":
                        resp = await client.put(url, content=body, **kwargs)
                    elif method.upper() == "PATCH":
                        resp = await client.patch(url, content=body, **kwargs)
                    elif method.upper() == "DELETE":
                        resp = await client.delete(url, **kwargs)
                    else:
                        resp = await client.request(method, url, content=body, **kwargs)

                # Determine if this is a success
                is_success = 200 <= resp.status_code < 300

                if is_success:
                    # Success — close circuit, cache response, return data
                    self.circuit_breaker.record_success(integration_id)

                    try:
                        response_data = resp.json()
                    except Exception:
                        response_data = resp.text

                    # Cache the response for GET requests
                    if use_cache and method.upper() == "GET":
                        self.cache.set(integration_id, url, response_data, data_type)

                    # Log successful call
                    await self._log_audit(
                        db=db, tenant_id=tenant_id, actor=actor,
                        integration_id=integration_id,
                        action="external_call.success",
                        details={
                            "method": method,
                            "url": url,
                            "status_code": resp.status_code,
                            "attempt": attempt + 1,
                        },
                        severity="info",
                    )

                    return {
                        "success": True,
                        "data": response_data,
                        "status_code": resp.status_code,
                        "from_cache": False,
                    }

                # Non-success response
                error_code = self._classify_error(resp.status_code)

                # Check if this status code is retriable
                if resp.status_code in self.RETRIABLE_STATUS_CODES and attempt < self.MAX_RETRIES:
                    retry_attempts += 1
                    backoff = self.BACKOFF_BASE_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"Retriable error from {integration_id}: {resp.status_code}. "
                        f"Retry {retry_attempts}/{self.MAX_RETRIES} in {backoff}s"
                    )
                    await asyncio.sleep(backoff)
                    continue

                # Non-retriable error or all retries exhausted
                self.circuit_breaker.record_failure(integration_id)

                # Try to return cached fallback
                stale = self.cache.get_stale(integration_id, url) if use_cache else None
                error = ToolBusError(
                    error_code=error_code,
                    message=f"External API returned {resp.status_code}: {resp.text[:200]}",
                    integration_id=integration_id,
                    is_retriable=resp.status_code in self.RETRIABLE_STATUS_CODES,
                    degraded_data=stale.data if stale else None,
                    cache_age_description=stale.age_description if stale else None,
                    retry_attempts=retry_attempts,
                    status_code=resp.status_code,
                )

                # Log failure
                await self._log_audit(
                    db=db, tenant_id=tenant_id, actor=actor,
                    integration_id=integration_id,
                    action="external_call.failed",
                    details={
                        "method": method,
                        "url": url,
                        "status_code": resp.status_code,
                        "error_code": error_code,
                        "retry_attempts": retry_attempts,
                    },
                    severity="warning" if resp.status_code < 500 else "error",
                )

                return error.to_dict()

            except httpx.TimeoutException as e:
                retry_attempts += 1
                last_error = e
                if attempt < self.MAX_RETRIES:
                    backoff = self.BACKOFF_BASE_SECONDS * (2 ** attempt)
                    logger.warning(f"Timeout from {integration_id}. Retry {retry_attempts}/{self.MAX_RETRIES} in {backoff}s")
                    await asyncio.sleep(backoff)
                    continue

            except httpx.ConnectError as e:
                # Network error — not retriable usually (DNS, connection refused)
                self.circuit_breaker.record_failure(integration_id)
                stale = self.cache.get_stale(integration_id, url) if use_cache else None
                error = ToolBusError(
                    error_code="network_error",
                    message=f"Could not connect to {integration_id}: {str(e)}",
                    integration_id=integration_id,
                    is_retriable=True,
                    degraded_data=stale.data if stale else None,
                    cache_age_description=stale.age_description if stale else None,
                    retry_attempts=retry_attempts,
                )

                await self._log_audit(
                    db=db, tenant_id=tenant_id, actor=actor,
                    integration_id=integration_id,
                    action="external_call.network_error",
                    details={"method": method, "url": url, "error": str(e), "retry_attempts": retry_attempts},
                    severity="error",
                )

                return error.to_dict()

            except Exception as e:
                self.circuit_breaker.record_failure(integration_id)
                stale = self.cache.get_stale(integration_id, url) if use_cache else None
                error = ToolBusError(
                    error_code="unknown_error",
                    message=f"Unexpected error calling {integration_id}: {str(e)}",
                    integration_id=integration_id,
                    is_retriable=False,
                    degraded_data=stale.data if stale else None,
                    cache_age_description=stale.age_description if stale else None,
                    retry_attempts=retry_attempts,
                )

                await self._log_audit(
                    db=db, tenant_id=tenant_id, actor=actor,
                    integration_id=integration_id,
                    action="external_call.error",
                    details={"method": method, "url": url, "error": str(e), "retry_attempts": retry_attempts},
                    severity="error",
                )

                return error.to_dict()

        # All retries exhausted
        self.circuit_breaker.record_failure(integration_id)
        stale = self.cache.get_stale(integration_id, url) if use_cache else None
        error = ToolBusError(
            error_code="all_retries_failed",
            message=f"All {self.MAX_RETRIES} retry attempts failed for {integration_id}",
            integration_id=integration_id,
            is_retriable=False,
            degraded_data=stale.data if stale else None,
            cache_age_description=stale.age_description if stale else None,
            retry_attempts=retry_attempts,
        )

        await self._log_audit(
            db=db, tenant_id=tenant_id, actor=actor,
            integration_id=integration_id,
            action="external_call.all_retries_failed",
            details={"method": method, "url": url, "retry_attempts": retry_attempts},
            severity="error",
        )

        return error.to_dict()

    def _classify_error(self, status_code: int) -> str:
        """Classify an HTTP status code into an error code."""
        if status_code == 401 or status_code == 403:
            return "auth_failed"
        elif status_code == 429:
            return "rate_limited"
        elif 500 <= status_code < 600:
            return "external_api_down"
        elif status_code == 408:
            return "timeout"
        else:
            return "invalid_response"

    async def _log_audit(
        self,
        db=None,
        tenant_id: str = None,
        actor: str = None,
        integration_id: str = None,
        action: str = "external_call",
        details: Dict = None,
        severity: str = "info",
    ):
        """Log an audit entry if db session is available."""
        if not db or not tenant_id:
            return

        try:
            from app.models import AuditLog
            audit = AuditLog(
                tenant_id=tenant_id,
                action=action,
                actor=actor or "system:external_tool_bus",
                resource_type="integration",
                resource_id=integration_id,
                details=json.dumps(details or {}),
                severity=severity,
            )
            db.add(audit)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log audit entry: {e}")

    def get_circuit_states(self) -> Dict:
        """Get all circuit breaker states."""
        return self.circuit_breaker.get_all_states()

    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        return self.cache.get_stats()

    def invalidate_cache(self, integration_id: str, path: str = None):
        """Invalidate cache for an integration."""
        self.cache.invalidate(integration_id, path)

    def reset_circuit(self, integration_id: str):
        """Reset the circuit breaker for an integration."""
        self.circuit_breaker.reset(integration_id)


# ===================== Singleton Instance =====================

# Global singleton — shared across all routes and MCP servers
_tool_bus: Optional[ExternalToolBus] = None


def get_tool_bus() -> ExternalToolBus:
    """Get or create the singleton ExternalToolBus instance."""
    global _tool_bus
    if _tool_bus is None:
        _tool_bus = ExternalToolBus()
    return _tool_bus
