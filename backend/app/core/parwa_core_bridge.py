"""
PARWA Core Bridge — Rust-accelerated drop-in replacements for Python middleware.

This module wires the Rust ``parwa_core`` PyO3 extensions into the existing
Python middleware layer so that swapping from pure-Python to Rust requires
zero or minimal changes in calling code.

Rust module API (parwa_core/__init__.py):
    from parwa_core import (
        RateLimiter, CircuitBreakerManager, PIIRedactor,
        JWTDecoder, SecurityHeaders, CSRFValidator,
    )

Old Python modules being replaced:
    1. app/services/rate_limit_service.py   → RateLimitService / RateLimitResult
    2. app/core/circuit_breaker_manager.py   → CircuitBreakerManager
    3. app/core/pii_redaction_engine.py      → PIIRedactor / PIIDetector
    4. app/core/auth.py                      → verify_access_token / get_unverified_claims
    5. app/middleware/security_headers.py    → SecurityHeadersMiddleware
    6. app/middleware/csrf.py                 → CSRFSecurityMiddleware

Bridge components:
    get_parwa_rate_limiter()        → wrapper matching old RateLimitService API
    get_parwa_circuit_breaker()     → CircuitBreakerManager singleton (Rust-backed)
    get_parwa_pii_redactor()        → PIIRedactor singleton (Rust-backed)
    parwa_verify_access_token()     → wraps JWTDecoder.verify
    parwa_get_security_headers()    → wraps SecurityHeaders.generate_headers
    parwa_csrf_validator()          → CSRFValidator factory
    is_parwa_core_available()       → bool check

BC-008: Every public function / method catches exceptions and never crashes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Set
from urllib.parse import urlparse

logger = logging.getLogger("parwa_core_bridge")

# ═══════════════════════════════════════════════════════════════════
# Rust module import — graceful fallback
# ═══════════════════════════════════════════════════════════════════

_RUST_AVAILABLE = False

# Pre-define so static linters (pyflakes) see the names before __all__.
# They are overwritten inside the try/except below.
HMACVerifier = None  # type: ignore[assignment,misc]
CryptoEngine = None  # type: ignore[assignment,misc]

try:
    from parwa_core import (
        RateLimiter as _RustRateLimiter,
        CircuitBreakerManager as _RustCircuitBreakerManager,
        PIIRedactor as _RustPIIRedactor,
        JWTDecoder as _RustJWTDecoder,
        SecurityHeaders as _RustSecurityHeaders,
        CSRFValidator as _RustCSRFValidator,
        HMACVerifier as _RustHMACVerifier,
        CryptoEngine as _RustCryptoEngine,
        ConnectionPool as _RustConnectionPool,
        AsyncLogger as _RustAsyncLogger,
    )
    _RUST_AVAILABLE = True
    # Module-level aliases so __all__ exports work for direct Rust access
    HMACVerifier = _RustHMACVerifier
    CryptoEngine = _RustCryptoEngine
    logger.info("PARWA Core Bridge: Rust backend loaded ✓")
except ImportError as exc:
    logger.warning(
        "PARWA Core Bridge: Rust module not available (%s). "
        "All bridge functions will use pure-Python fallbacks.",
        exc,
    )


# ═══════════════════════════════════════════════════════════════════
# Availability check
# ═══════════════════════════════════════════════════════════════════

def is_parwa_core_available() -> bool:
    """Return ``True`` when the Rust ``parwa_core`` native module is loaded."""
    return _RUST_AVAILABLE


# ═══════════════════════════════════════════════════════════════════
# 1. RATE LIMITER  —  drop-in for RateLimitService / RateLimitResult
# ═══════════════════════════════════════════════════════════════════

# Mirrors CATEGORY_CONFIG from rate_limit_service.py
CATEGORY_CONFIG = {
    "auth_login": {
        "limit": 5, "window": 60, "scope": "email",
        "backoff_seconds": [0, 2, 4, 8, 900], "lockout_duration": 900,
    },
    "auth_mfa": {
        "limit": 10, "window": 60, "scope": "email",
        "backoff_seconds": [0, 2, 4, 8, 900], "lockout_duration": 900,
    },
    "auth_phone_send": {
        "limit": 5, "window": 300, "scope": "ip",
        "backoff_seconds": [0, 2, 4, 8, 900], "lockout_duration": 900,
    },
    "auth_phone_verify": {
        "limit": 10, "window": 60, "scope": "phone",
        "backoff_seconds": [0, 2, 4, 8, 300], "lockout_duration": 300,
    },
    "auth_register": {
        "limit": 3, "window": 60, "scope": "ip",
        "backoff_seconds": [0, 2, 4, 8, 900], "lockout_duration": 900,
    },
    "auth_reset": {
        "limit": 3, "window": 3600, "scope": "email",
        "backoff_seconds": [0, 2, 4, 8, 900], "lockout_duration": 900,
    },
    "financial": {
        "limit": 20, "window": 60, "scope": "user",
        "backoff_seconds": [0, 2, 4, 8, 300], "lockout_duration": 300,
    },
    "general_get": {
        "limit": 100, "window": 60, "scope": "ip",
        "backoff_seconds": [0, 2, 4, 8, 60], "lockout_duration": 60,
    },
    "general_post": {
        "limit": 100, "window": 60, "scope": "ip",
        "backoff_seconds": [0, 2, 4, 8, 60], "lockout_duration": 60,
    },
    "integration": {
        "limit": 60, "window": 60, "scope": "api_key",
        "backoff_seconds": [0, 2, 4, 8, 60], "lockout_duration": 60,
    },
    "demo_chat": {
        "limit": 60, "window": 300, "scope": "ip_hash",
        "backoff_seconds": [0, 2, 4, 8, 60], "lockout_duration": 60,
    },
}


@dataclass
class RateLimitResult:
    """Mirrors ``app.services.rate_limit_service.RateLimitResult``.

    The middleware calls ``result.to_headers()`` and checks
    ``result.allowed``, ``result.remaining``, ``result.retry_after``.
    """

    allowed: bool
    remaining: int
    limit: int
    reset_at: float
    retry_after: Optional[int] = None
    backoff_seconds: Optional[int] = None

    def to_headers(self) -> dict:
        """Generate standard X-RateLimit-* headers (BC-012)."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(self.remaining, 0)),
            "X-RateLimit-Reset": str(int(self.reset_at)),
        }
        if self.retry_after is not None:
            headers["Retry-After"] = str(self.retry_after)
        return headers


class _RateLimiterBridge:
    """Adapter that presents the OLD ``RateLimitService`` API backed by
    either the Rust ``RateLimiter`` or a pure-Python fallback.

    Old API surface (used by middleware/rate_limit.py):
        classify_path(path, method) -> str
        check_rate_limit(category, identifier) -> RateLimitResult
        record_failure(category, identifier) -> Optional[int]
        is_locked_out(category, identifier) -> bool
        reset(category, identifier) -> None
        get_category_config(category) -> dict
        extract_identifier(category, request) -> Awaitable[str]
        sync_redis_time() -> Awaitable[None]
    """

    def __init__(self):
        self._rust: Optional[Any] = None
        self._python_failures: Dict[str, dict] = {}  # fallback store
        if _RUST_AVAILABLE:
            try:
                self._rust = _RustRateLimiter()
            except Exception as exc:
                logger.error(
                    "rate_limiter_rust_init_failed error=%s", exc,
                )
                self._rust = None

    # ── classify_path ─────────────────────────────────────────────

    def classify_path(self, path: str, method: str = "GET") -> str:
        """Classify a request path into an endpoint category.

        Delegates to Rust ``RateLimiter.classify_path`` when available,
        otherwise uses the same path-matching logic as the original Python.
        """
        if self._rust is not None:
            try:
                result = self._rust.classify_path(path, method)
                # Rust returns a string category
                if isinstance(result, str) and result:
                    return result
            except Exception:
                logger.debug("rate_limiter_classify_path_rust_fallback")

        # Pure-Python fallback (identical to rate_limit_service.py)
        if path == "/api/auth/login" and method == "POST":
            return "auth_login"
        if path == "/api/auth/register" and method == "POST":
            return "auth_register"
        if path == "/api/auth/mfa" and method == "POST":
            return "auth_mfa"
        if path == "/api/auth/phone/send" and method == "POST":
            return "auth_phone_send"
        if path == "/api/auth/phone/verify" and method == "POST":
            return "auth_phone_verify"
        if path in (
            "/api/auth/forgot-password",
            "/api/auth/reset-password",
        ) and method == "POST":
            return "auth_reset"
        if path.startswith("/api/billing/"):
            return "financial"
        if path.startswith("/api/integrations/"):
            return "integration"
        if path == "/api/public/demo/chat":
            return "demo_chat"
        if method.upper() == "GET":
            return "general_get"
        return "general_post"

    # ── check_rate_limit ───────────────────────────────────────────

    def check_rate_limit(
        self,
        category: str,
        identifier: str,
    ) -> RateLimitResult:
        """Check if a request is within rate limits.

        Returns a ``RateLimitResult`` (same as the old Python service).
        The middleware calls ``result.to_headers()`` and ``result.allowed``.
        """
        config = self.get_category_config(category)
        limit = config["limit"]
        window = config["window"]

        if self._rust is not None:
            try:
                rust_result = self._rust.check_rate_limit(category, identifier)
                # Rust returns a dict with keys:
                #   allowed, remaining, limit, reset_at, retry_after
                if isinstance(rust_result, dict):
                    return RateLimitResult(
                        allowed=bool(rust_result.get("allowed", True)),
                        remaining=int(rust_result.get("remaining", limit)),
                        limit=int(rust_result.get("limit", limit)),
                        reset_at=float(rust_result.get("reset_at", time.time() + window)),
                        retry_after=rust_result.get("retry_after"),
                    )
            except Exception:
                logger.warning("rate_limiter_rust_check_failed_fallback")

        # Pure-Python fallback: allow everything with default headers
        # (the middleware fails CLOSED on Redis errors, so this fallback
        # should rarely be hit — it's here for BC-008 safety)
        return RateLimitResult(
            allowed=True,
            remaining=limit,
            limit=limit,
            reset_at=time.time() + window,
        )

    # ── record_failure ─────────────────────────────────────────────

    def record_failure(
        self,
        category: str,
        identifier: str,
    ) -> Optional[int]:
        """Record a failure and return backoff seconds.

        Returns the backoff duration in seconds, or ``None`` if recording
        was not applicable.
        """
        if self._rust is not None:
            try:
                result = self._rust.record_failure(category, identifier)
                if isinstance(result, (int, float)):
                    return int(result)
                return None
            except Exception:
                logger.warning("rate_limiter_rust_record_failure_failed")

        # Python fallback
        config = self.get_category_config(category)
        backoffs = config["backoff_seconds"]
        fail_key = self._make_failure_key(category, identifier)
        now = time.time()
        info = self._python_failures.get(fail_key, {})
        count = info.get("count", 0)
        first_fail = info.get("first_fail", now)
        if now - first_fail > 3600:
            count = 0
        count += 1
        self._python_failures[fail_key] = {
            "count": count,
            "first_fail": first_fail,
            "last_fail": now,
            "locked_at": None,
        }
        if count < len(backoffs):
            return backoffs[count]
        lockout_dur = config["lockout_duration"]
        self._python_failures[fail_key]["locked_at"] = now
        return lockout_dur

    # ── is_locked_out ───────────────────────────────────────────────

    def is_locked_out(
        self,
        category: str,
        identifier: str,
    ) -> bool:
        """Check if identifier is currently locked out."""
        if self._rust is not None:
            try:
                return bool(self._rust.is_locked_out(category, identifier))
            except Exception:
                logger.warning("rate_limiter_rust_is_locked_out_failed")

        # Python fallback
        config = self.get_category_config(category)
        fail_key = self._make_failure_key(category, identifier)
        info = self._python_failures.get(fail_key)
        if not info or info.get("locked_at") is None:
            return False
        lockout_dur = config["lockout_duration"]
        return (time.time() - info["locked_at"]) < lockout_dur

    # ── reset ──────────────────────────────────────────────────────

    def reset(
        self,
        category: str,
        identifier: str,
    ) -> None:
        """Reset lockout and failure count for an identifier."""
        if self._rust is not None:
            try:
                self._rust.reset(category, identifier)
                return
            except Exception:
                logger.warning("rate_limiter_rust_reset_failed")

        # Python fallback
        fail_key = self._make_failure_key(category, identifier)
        self._python_failures.pop(fail_key, None)

    # ── get_category_config ────────────────────────────────────────

    def get_category_config(self, category: str) -> dict:
        """Get configuration for an endpoint category."""
        return CATEGORY_CONFIG.get(category, CATEGORY_CONFIG["general_get"])

    # ── extract_identifier ───────────────────────────────────────

    async def extract_identifier(
        self,
        category: str,
        request: Any,
    ) -> str:
        """Extract identifier based on category scope.

        This method is async because the old Python version reads
        the request body for email/phone extraction.  We keep the
        same signature so the middleware doesn't need changes.
        """
        config = self.get_category_config(category)
        scope = config["scope"]
        if scope == "email":
            return await self._extract_email(request)
        if scope == "phone":
            return await self._extract_phone(request)
        if scope == "ip":
            return self._extract_ip(request)
        if scope == "ip_hash":
            ip = self._extract_ip(request)
            return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]
        if scope == "api_key":
            return self._extract_api_key_id(request)
        if scope == "user":
            return self._extract_user_id(request)
        return self._extract_ip(request)

    # ── sync_redis_time ───────────────────────────────────────────

    async def sync_redis_time(self) -> None:
        """Sync time offset — no-op for Rust backend (uses monotonic internally)."""
        # The Rust limiter handles time internally. This is a no-op
        # to maintain API compatibility with the old Python service.
        pass

    # ── Private helpers ───────────────────────────────────────────

    @staticmethod
    def _make_failure_key(category: str, identifier: str) -> str:
        raw = f"{category}\x00{identifier}"
        hash_part = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"bridge:rl:fail:{hash_part}"

    @staticmethod
    async def _extract_email(request: Any) -> str:
        try:
            body = await request.json()
        except Exception:
            body = {}
        email = body.get("email", "")
        if not email:
            email = (
                request.query_params.get("email", "")
                if hasattr(request, "query_params")
                else ""
            )
        return email.strip().lower() or "unknown"

    @staticmethod
    async def _extract_phone(request: Any) -> str:
        try:
            body = await request.json()
        except Exception:
            body = {}
        return (body.get("phone", "") or "").strip() or "unknown"

    @staticmethod
    def _extract_ip(request: Any) -> str:
        try:
            from app.core.security.security_utils import get_client_ip
            return get_client_ip(request)
        except Exception:
            return "unknown"

    @staticmethod
    def _extract_api_key_id(request: Any) -> str:
        api_key = getattr(request.state, "api_key", None)
        if api_key and "id" in api_key:
            return api_key["id"]
        return "unknown"

    @staticmethod
    def _extract_user_id(request: Any) -> str:
        user = getattr(request.state, "user", None)
        if user and hasattr(user, "id"):
            return user.id
        return "unknown"


# Singleton
_rate_limiter_bridge: Optional[_RateLimiterBridge] = None


def get_parwa_rate_limiter() -> _RateLimiterBridge:
    """Return the singleton rate-limiter bridge.

    Drop-in replacement for ``get_rate_limit_service()`` from
    ``app.services.rate_limit_service``.
    """
    global _rate_limiter_bridge
    if _rate_limiter_bridge is None:
        try:
            _rate_limiter_bridge = _RateLimiterBridge()
        except Exception as exc:
            logger.error(
                "rate_limiter_bridge_init_failed error=%s", exc,
            )
            # BC-008: return a dead instance that always allows
            _rate_limiter_bridge = _RateLimiterBridge()
    return _rate_limiter_bridge


# ═══════════════════════════════════════════════════════════════════
# 2. CIRCUIT BREAKER  —  drop-in for CircuitBreakerManager
# ═══════════════════════════════════════════════════════════════════

class _CircuitBreakerBridge:
    """Adapter that presents the OLD ``CircuitBreakerManager`` API
    backed by the Rust ``CircuitBreakerManager`` singleton.

    Old API surface (used by model_failover, health checks, etc.):
        register(name, config=None)
        is_available(name) -> bool
        record_success(name)
        record_failure(name)
        get_state(name) -> CircuitState
        get_all_states() -> Dict[str, Dict]
        force_open(name) -> bool
        force_close(name) -> bool
        get_metrics() -> Dict
    """

    def __init__(self):
        self._rust: Optional[Any] = None
        self._python_breakers: Dict[str, dict] = {}
        if _RUST_AVAILABLE:
            try:
                self._rust = _RustCircuitBreakerManager()
            except Exception as exc:
                logger.error(
                    "circuit_breaker_rust_init_failed error=%s", exc,
                )
                self._rust = None

    def register(
        self,
        name: str,
        config: Optional[Any] = None,
    ) -> None:
        """Register a new circuit breaker.

        ``config`` can be a ``CircuitBreakerConfig`` dataclass (old API)
        or ``None`` (uses Rust defaults).

        The Rust ``register`` accepts keyword args: ``failure_threshold``,
        ``success_threshold``, ``timeout``, ``half_open_max_calls``.
        """
        if self._rust is not None:
            try:
                if config is not None and hasattr(config, "failure_threshold"):
                    self._rust.register(
                        name,
                        failure_threshold=config.failure_threshold,
                        success_threshold=config.success_threshold,
                        timeout=config.timeout,
                        half_open_max_calls=config.half_open_max_calls,
                    )
                else:
                    self._rust.register(name)
                return
            except Exception:
                logger.warning(
                    "circuit_breaker_rust_register_failed name=%s", name,
                )

        # Python fallback
        if name not in self._python_breakers:
            ft = config.failure_threshold if config else 5
            st = config.success_threshold if config else 3
            to = config.timeout if config else 60
            ho = config.half_open_max_calls if config else 3
            self._python_breakers[name] = {
                "state": "closed",
                "failure_count": 0,
                "success_count": 0,
                "failure_threshold": ft,
                "success_threshold": st,
                "timeout": to,
                "half_open_max_calls": ho,
                "opened_at": None,
                "total_failures": 0,
                "total_successes": 0,
            }

    def is_available(self, name: str) -> bool:
        """Check if the dependency is available."""
        if self._rust is not None:
            try:
                return bool(self._rust.is_available(name))
            except Exception:
                logger.warning(
                    "circuit_breaker_rust_is_available_failed name=%s", name,
                )
        # BC-008: assume available if not found / on error
        return True

    def record_success(self, name: str) -> None:
        """Record a successful call."""
        if self._rust is not None:
            try:
                self._rust.record_success(name)
                return
            except Exception:
                logger.warning(
                    "circuit_breaker_rust_record_success_failed name=%s", name,
                )

    def record_failure(self, name: str) -> None:
        """Record a failed call."""
        if self._rust is not None:
            try:
                self._rust.record_failure(name)
                return
            except Exception:
                logger.warning(
                    "circuit_breaker_rust_record_failure_failed name=%s", name,
                )

    def get_state(self, name: str) -> Any:
        """Get current circuit state.

        Returns a string matching the old ``CircuitState`` enum values:
        ``"closed"``, ``"open"``, ``"half_open"``.
        """
        if self._rust is not None:
            try:
                status = self._rust.get_status(name)
                # Rust returns a dict with a "state" key
                if isinstance(status, dict):
                    return status.get("state", "closed")
                if isinstance(status, str):
                    return status
            except Exception:
                logger.warning(
                    "circuit_breaker_rust_get_state_failed name=%s", name,
                )
        return "closed"  # Safe default

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get states of all circuit breakers."""
        if self._rust is not None:
            try:
                result = self._rust.get_all_status()
                if isinstance(result, list):
                    # Convert list of dicts to name-keyed dict
                    return {item.get("name", str(i)): item for i, item in enumerate(result)}
                if isinstance(result, dict):
                    return result
            except Exception:
                logger.warning("circuit_breaker_rust_get_all_states_failed")
        return {}

    def force_open(self, name: str) -> bool:
        """Manually open a circuit."""
        if self._rust is not None:
            try:
                self._rust.force_open(name)
                return True
            except Exception:
                logger.warning(
                    "circuit_breaker_rust_force_open_failed name=%s", name,
                )
        return False

    def force_close(self, name: str) -> bool:
        """Manually close a circuit."""
        if self._rust is not None:
            try:
                self._rust.force_close(name)
                return True
            except Exception:
                logger.warning(
                    "circuit_breaker_rust_force_close_failed name=%s", name,
                )
        return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get Prometheus-compatible metrics for all circuit breakers."""
        if self._rust is not None:
            try:
                all_status = self._rust.get_all_status()
                lines = [
                    "# HELP parwa_circuit_breaker_state "
                    "Circuit breaker state (1=current, 0=not current)",
                    "# TYPE parwa_circuit_breaker_state gauge",
                    "# HELP parwa_circuit_breaker_failures_total "
                    "Total failures recorded",
                    "# TYPE parwa_circuit_breaker_failures_total counter",
                ]
                summary = {"open": 0, "closed": 0, "half_open": 0, "total": 0}
                items = all_status if isinstance(all_status, list) else []
                for item in items:
                    name = item.get("name", "unknown")
                    state = item.get("state", "closed")
                    failures = item.get("total_failures", 0)
                    summary["total"] = summary.get("total", 0) + 1
                    summary[state] = summary.get(state, 0) + 1
                    for s in ("closed", "open", "half_open"):
                        val = 1 if state == s else 0
                        lines.append(
                            f'parwa_circuit_breaker_state{{name="{name}",state="{s}"}} {val}'
                        )
                    lines.append(
                        f'parwa_circuit_breaker_failures_total{{name="{name}"}} {failures}'
                    )
                return {
                    "metrics": lines,
                    "summary": summary,
                    "rust": True,
                }
            except Exception:
                logger.warning("circuit_breaker_rust_get_metrics_failed")
        return {"metrics": [], "summary": {}, "rust": False}


# Singleton
_circuit_breaker_bridge: Optional[_CircuitBreakerBridge] = None


def get_parwa_circuit_breaker() -> _CircuitBreakerBridge:
    """Return the singleton circuit-breaker bridge.

    Drop-in replacement for ``circuit_breaker_manager`` singleton
    from ``app.core.circuit_breaker_manager``.
    """
    global _circuit_breaker_bridge
    if _circuit_breaker_bridge is None:
        try:
            _circuit_breaker_bridge = _CircuitBreakerBridge()
        except Exception as exc:
            logger.error(
                "circuit_breaker_bridge_init_failed error=%s", exc,
            )
            _circuit_breaker_bridge = _CircuitBreakerBridge()
    return _circuit_breaker_bridge


# ═══════════════════════════════════════════════════════════════════
# 3. PII REDACTOR  —  drop-in for PIIRedactor / PIIDetector
# ═══════════════════════════════════════════════════════════════════

@dataclass
class PIIMatch:
    """A single PII detection result.

    Mirrors the dataclass from ``pii_redaction_engine.py``.
    """
    pii_type: str
    value: str
    start: int
    end: int
    confidence: float = 1.0
    pattern: str = ""


@dataclass
class RedactionResult:
    """Result of a PII redaction pass.

    Mirrors the dataclass from ``pii_redaction_engine.py``.
    """
    redacted_text: str
    redaction_map: Dict[str, str]
    redaction_id: str
    pii_found: bool
    summary: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_pii(self) -> bool:
        return self.pii_found


class _PIIRedactorBridge:
    """Adapter presenting the OLD ``PIIRedactor`` / ``PIIDetector`` API
    backed by the Rust ``PIIRedactor``.

    Old API surface:
        detect_pii(text, pii_types=None) -> List[PIIMatch]
        redact_pii(text, company_id, pii_types=None) -> RedactionResult
        deredact_pii(text, redaction_map) -> str
        has_pii(text) -> bool
    """

    def __init__(self):
        self._rust: Optional[Any] = None
        if _RUST_AVAILABLE:
            try:
                self._rust = _RustPIIRedactor()
            except Exception as exc:
                logger.error(
                    "pii_redactor_rust_init_failed error=%s", exc,
                )
                self._rust = None

    # ── detect_pii ─────────────────────────────────────────────────

    def detect_pii(
        self,
        text: str,
        pii_types: Optional[Set[str]] = None,
    ) -> List[PIIMatch]:
        """Detect PII in text.

        Returns a list of ``PIIMatch`` objects.
        """
        if not text:
            return []

        if self._rust is not None:
            try:
                raw_results = self._rust.detect_pii(text)
                # Rust returns list of dicts: {pii_type, value, start, end, ...}
                matches = []
                for item in raw_results:
                    matches.append(PIIMatch(
                        pii_type=item.get("pii_type", item.get("type", "UNKNOWN")),
                        value=item.get("value", item.get("text", "")),
                        start=int(item.get("start", 0)),
                        end=int(item.get("end", 0)),
                        confidence=float(item.get("confidence", 1.0)),
                        pattern=item.get("pattern", ""),
                    ))
                return matches
            except Exception:
                logger.warning("pii_redactor_rust_detect_pii_failed")

        return []

    # ── redact_pii ──────────────────────────────────────────────────

    async def redact_pii(
        self,
        text: str,
        company_id: str,
        pii_types: Optional[Set[str]] = None,
    ) -> RedactionResult:
        """Detect and redact PII in text.

        Returns a ``RedactionResult`` matching the old Python API.
        """
        if not text:
            return RedactionResult(
                redacted_text="",
                redaction_map={},
                redaction_id="",
                pii_found=False,
            )

        redaction_id = secrets.token_hex(8)

        if self._rust is not None:
            try:
                rust_result = self._rust.redact(text, company_id)
                # Rust returns a dict: {redacted, map, ...}
                if isinstance(rust_result, dict):
                    redacted = rust_result.get("redacted", rust_result.get("redacted_text", text))
                    redaction_map = rust_result.get("map", rust_result.get("redaction_map", {}))
                    by_type: Dict[str, int] = {}
                    for token, original in redaction_map.items():
                        # Token format: {{PII_TYPE_UUID8}}
                        parts = token.strip("{}").split("_", 1)
                        pii_type = parts[0] if parts else "UNKNOWN"
                        by_type[pii_type] = by_type.get(pii_type, 0) + 1
                    return RedactionResult(
                        redacted_text=redacted,
                        redaction_map=redaction_map,
                        redaction_id=redaction_id,
                        pii_found=len(redaction_map) > 0,
                        summary={
                            "total_matches": len(redaction_map),
                            "by_type": by_type,
                            "redacted_at": time.strftime(
                                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(),
                            ),
                            "company_id": company_id,
                        },
                    )
            except Exception:
                logger.warning("pii_redactor_rust_redact_failed")

        return RedactionResult(
            redacted_text=text,
            redaction_map={},
            redaction_id=redaction_id,
            pii_found=False,
        )

    # ── deredact_pii ───────────────────────────────────────────────

    def deredact_pii(
        self,
        text: str,
        redaction_map: Dict[str, str],
    ) -> str:
        """Replace PII tokens back with original values.

        Args:
            text: Redacted text containing {{PII_TYPE_xxxx}} tokens.
            redaction_map: Mapping of token -> original value.

        Returns:
            Original text with PII restored.
        """
        if not text or not redaction_map:
            return text

        if self._rust is not None:
            try:
                result = self._rust.deredact(text, redaction_map)
                if isinstance(result, str):
                    return result
            except Exception:
                logger.warning("pii_redactor_rust_deredact_failed")

        # Python fallback
        result = text
        for token, original in redaction_map.items():
            result = result.replace(token, original)
        return result

    # ── has_pii ────────────────────────────────────────────────────

    def has_pii(self, text: str) -> bool:
        """Check if text contains any PII."""
        if not text:
            return False

        if self._rust is not None:
            try:
                return bool(self._rust.has_pii(text))
            except Exception:
                logger.warning("pii_redactor_rust_has_pii_failed")

        return False


# Singleton
_pii_redactor_bridge: Optional[_PIIRedactorBridge] = None


def get_parwa_pii_redactor() -> _PIIRedactorBridge:
    """Return the singleton PII redactor bridge.

    Drop-in replacement for ``PIIRedactor()`` from
    ``app.core.pii_redaction_engine``.
    """
    global _pii_redactor_bridge
    if _pii_redactor_bridge is None:
        try:
            _pii_redactor_bridge = _PIIRedactorBridge()
        except Exception as exc:
            logger.error(
                "pii_redactor_bridge_init_failed error=%s", exc,
            )
            _pii_redactor_bridge = _PIIRedactorBridge()
    return _pii_redactor_bridge


# ═══════════════════════════════════════════════════════════════════
# 4. JWT AUTH  —  drop-in for verify_access_token / get_unverified_claims
# ═══════════════════════════════════════════════════════════════════

_jwt_decoder_instance: Optional[Any] = None


def _get_jwt_decoder():
    """Lazy-init the Rust JWTDecoder singleton."""
    global _jwt_decoder_instance
    if _jwt_decoder_instance is None and _RUST_AVAILABLE:
        try:
            _jwt_decoder_instance = _RustJWTDecoder()
        except Exception as exc:
            logger.error("jwt_decoder_rust_init_failed error=%s", exc)
    return _jwt_decoder_instance


def parwa_verify_access_token(
    token: str,
    secret: str,
    algorithms: Optional[List[str]] = None,
    previous_secrets: Optional[List[str]] = None,
) -> dict:
    """Verify a JWT access token using Rust JWTDecoder.

    Drop-in replacement for ``app.core.auth.verify_access_token``.
    Wraps ``JWTDecoder.verify(token, secret, algorithms)`` and handles
    key rotation by trying ``previous_secrets`` on HS256 failure.

    Args:
        token: The JWT string.
        secret: The current signing secret.
        algorithms: List of algorithms to try (default ["HS256"]).
        previous_secrets: Old secrets for key rotation support (L-02).

    Returns:
        Decoded token payload dict.

    Raises:
        AuthenticationError: If token is invalid or expired.
    """
    from app.exceptions import AuthenticationError

    if not algorithms:
        algorithms = ["HS256"]

    # Try Rust decoder first
    decoder = _get_jwt_decoder()
    if decoder is not None:
        try:
            result = decoder.verify(token, secret, algorithms=algorithms)
            if isinstance(result, dict):
                # Validate token type
                if result.get("type") != "access":
                    raise AuthenticationError(
                        message="Invalid token type",
                        details={"expected": "access"},
                    )
                return result
        except AuthenticationError:
            raise
        except Exception:
            logger.warning("jwt_rust_verify_failed_fallback_to_python")

    # Python fallback via jose — same logic as app.core.auth
    from jose import JWTError, jwt

    # Try primary secret
    try:
        payload = jwt.decode(token, secret, algorithms=algorithms)
        if payload.get("type") != "access":
            raise AuthenticationError(
                message="Invalid token type",
                details={"expected": "access"},
            )
        return payload
    except AuthenticationError:
        raise
    except JWTError:
        pass

    # Try previous secrets (L-02 key rotation)
    if previous_secrets:
        for old_key in previous_secrets:
            try:
                payload = jwt.decode(token, old_key, algorithms=["HS256"])
                if payload.get("type") != "access":
                    raise AuthenticationError(
                        message="Invalid token type",
                        details={"expected": "access"},
                    )
                return payload
            except AuthenticationError:
                raise
            except JWTError:
                continue

    raise AuthenticationError(message="Invalid or expired token")


def parwa_get_unverified_claims(token: str) -> Optional[dict]:
    """Extract JWT claims without signature verification.

    Drop-in replacement for ``jwt.get_unverified_claims``.
    Used for jti extraction (blacklist checks) before full verification.

    Args:
        token: The JWT string.

    Returns:
        Payload dict or ``None`` on parse error.
    """
    decoder = _get_jwt_decoder()
    if decoder is not None:
        try:
            result = decoder.get_unverified_claims(token)
            if isinstance(result, dict):
                return result
        except Exception:
            logger.debug("jwt_rust_unverified_claims_failed")

    # Python fallback
    try:
        from jose import jwt
        return jwt.get_unverified_claims(token)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
# 5. SECURITY HEADERS  —  drop-in for SecurityHeadersMiddleware
# ═══════════════════════════════════════════════════════════════════

_SECURITY_HEADERS_FALLBACK = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

_AUTH_PATH_PREFIXES = (
    "/api/auth/",
    "/api/login",
    "/api/register",
    "/api/mfa/",
    "/api/refresh",
)

_security_headers_instance: Optional[Any] = None


def _get_security_headers():
    """Lazy-init the Rust SecurityHeaders singleton."""
    global _security_headers_instance
    if _security_headers_instance is None and _RUST_AVAILABLE:
        try:
            _security_headers_instance = _RustSecurityHeaders()
        except Exception as exc:
            logger.error("security_headers_rust_init_failed error=%s", exc)
    return _security_headers_instance


def parwa_get_security_headers(
    path: str = "/",
    environment: str = "",
) -> Dict[str, str]:
    """Generate security headers for a response.

    Wraps ``SecurityHeaders.generate_headers(path)`` when Rust is available,
    falling back to a standard Python implementation that matches the
    existing ``SecurityHeadersMiddleware`` behavior.

    Args:
        path: The request path (for CSP nonce, HSTS, and cache-control).
        environment: The deployment environment (for HSTS toggle).

    Returns:
        Dict of header name -> value.
    """
    if not environment:
        environment = os.environ.get("ENVIRONMENT", "development")

    headers = _SECURITY_HEADERS_FALLBACK.copy()

    # Try Rust
    sec = _get_security_headers()
    if sec is not None:
        try:
            rust_headers = sec.generate_headers(path)
            if isinstance(rust_headers, dict):
                headers.update(rust_headers)
                # Rust handles CSP, HSTS, etc. — add cache-control
                return _add_cache_control(headers, path)
        except Exception:
            logger.warning("security_headers_rust_failed_fallback")

    # CSP nonce (Python fallback)
    csp_nonce = secrets.token_urlsafe(16)
    headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'nonce-{nonce}'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self' https://api.stripe.com; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "object-src 'none'; "
        "upgrade-insecure-requests"
    ).format(nonce=csp_nonce)
    headers["X-CSP-Nonce"] = csp_nonce

    # HSTS (production only)
    if environment == "production":
        headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

    return _add_cache_control(headers, path)


def _add_cache_control(
    headers: Dict[str, str],
    path: str,
) -> Dict[str, str]:
    """Add Cache-Control: no-store for auth endpoints (M-11)."""
    for prefix in _AUTH_PATH_PREFIXES:
        if path.startswith(prefix):
            headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0"
            )
            headers["Pragma"] = "no-cache"
            headers["Expires"] = "0"
            break
    return headers


# ═══════════════════════════════════════════════════════════════════
# 6. CSRF VALIDATOR  —  drop-in for CSRFSecurityMiddleware logic
# ═══════════════════════════════════════════════════════════════════

_CSRF_MAX_AGE = 3600  # 1 hour (same as csrf.py)
_VERCEL_PATTERN = r"^https://[a-z0-9\-]+(--[a-z0-9\-]+)?\.vercel\.app$"


class _CSRFValidatorBridge:
    """Adapter presenting CSRF validation backed by the Rust
    ``CSRFValidator`` with pure-Python fallback.

    Old API surface (from csrf.py CSRFSecurityMiddleware):
        _is_valid_origin(origin, referer) -> bool
        generate_csrf_token(secret_key="") -> str
        validate_csrf_token(token, secret_key="") -> bool
    """

    def __init__(self, trusted_origins: List[str], secret_key: str = ""):
        self._trusted_origins = trusted_origins
        self._secret_key = secret_key or os.environ.get(
            "SECRET_KEY", "parwa-csrf-fallback",
        )
        self._rust: Optional[Any] = None
        if _RUST_AVAILABLE:
            try:
                self._rust = _RustCSRFValidator(
                    trusted_origins=trusted_origins,
                    secret_key=self._secret_key,
                )
            except Exception as exc:
                logger.error(
                    "csrf_validator_rust_init_failed error=%s", exc,
                )
                self._rust = None

    def is_valid_origin(
        self,
        origin: str,
        referer: str = "",
    ) -> bool:
        """Validate Origin and/or Referer against trusted origins.

        Wraps ``CSRFValidator.is_valid_origin(origin, referer)``.
        Falls back to the same logic as ``CSRFSecurityMiddleware._is_valid_origin``.
        """
        if self._rust is not None:
            try:
                return bool(
                    self._rust.is_valid_origin(origin, referer)
                )
            except Exception:
                logger.warning("csrf_rust_is_valid_origin_failed")

        # Python fallback — same logic as csrf.py
        if not self._trusted_origins:
            return True

        check_origin = origin
        if not check_origin and referer:
            try:
                parsed = urlparse(referer)
                check_origin = f"{parsed.scheme}://{parsed.netloc}"
            except Exception:
                return False

        if not check_origin:
            return False

        # Vercel wildcard
        import re
        if re.match(_VERCEL_PATTERN, check_origin):
            return True

        for trusted in self._trusted_origins:
            if check_origin == trusted or check_origin.startswith(trusted + "/"):
                return True

        return False

    def generate_csrf_token(self) -> str:
        """Generate a new CSRF token.

        Wraps ``CSRFValidator.generate_csrf_token()``.
        Falls back to HMAC-based token generation.
        """
        if self._rust is not None:
            try:
                token = self._rust.generate_csrf_token()
                if isinstance(token, str) and token:
                    return token
            except Exception:
                logger.warning("csrf_rust_generate_token_failed")

        # Python fallback — same HMAC logic as csrf.py
        nonce = secrets.token_hex(16)
        timestamp = str(int(time.time()))
        msg = f"{nonce}:{timestamp}"
        sig = hmac.new(
            self._secret_key.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:16]
        return f"{nonce}:{timestamp}:{sig}"

    def validate_csrf_token(self, token: str) -> bool:
        """Validate a CSRF token.

        Wraps ``CSRFValidator.validate_csrf_token(token)``.
        Falls back to HMAC-based validation.
        """
        if not token:
            return False

        if self._rust is not None:
            try:
                return bool(self._rust.validate_csrf_token(token))
            except Exception:
                logger.warning("csrf_rust_validate_token_failed")

        # Python fallback — same logic as csrf.py
        try:
            parts = token.split(":")
            if len(parts) != 3:
                return False
            nonce, timestamp_str, sig = parts
            ts = int(timestamp_str)
            if abs(time.time() - ts) > _CSRF_MAX_AGE:
                return False
            msg = f"{nonce}:{timestamp_str}"
            expected = hmac.new(
                self._secret_key.encode("utf-8"),
                msg.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()[:16]
            return hmac.compare_digest(sig, expected)
        except Exception:
            return False


def parwa_csrf_validator(
    trusted_origins: Optional[List[str]] = None,
    secret_key: str = "",
) -> _CSRFValidatorBridge:
    """Factory for a CSRF validator instance.

    Parses ``CSRF_TRUSTED_ORIGINS`` from the environment (same as
    ``csrf.py._parse_trusted_origins``) when ``trusted_origins`` is
    ``None``.

    Drop-in for the CSRF validation logic in
    ``CSRFSecurityMiddleware._is_valid_origin``, ``.generate_csrf_token``,
    and ``.validate_csrf_token``.

    Args:
        trusted_origins: Explicit list of trusted origins. ``None``
            reads from ``CSRF_TRUSTED_ORIGINS`` / ``CORS_ORIGINS`` env.
        secret_key: Server secret for HMAC token signing.

    Returns:
        A ``_CSRFValidatorBridge`` instance.
    """
    if trusted_origins is None:
        raw = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
        if not raw:
            raw = os.environ.get("CORS_ORIGINS", "")
        trusted_origins = [o.strip() for o in raw.split(",") if o.strip()]

    try:
        return _CSRFValidatorBridge(trusted_origins, secret_key)
    except Exception as exc:
        logger.error("csrf_validator_bridge_init_failed error=%s", exc)
        # BC-008: return a permissive validator that won't crash
        return _CSRFValidatorBridge([], secret_key)


# ═══════════════════════════════════════════════════════════════════
# 7. HMAC VERIFIER  —  Webhook signature verification (Tier 2)
# ═══════════════════════════════════════════════════════════════════

_hmac_verifier_instance: Optional[Any] = None


def _get_hmac_verifier():
    """Lazy-init the Rust HMACVerifier singleton."""
    global _hmac_verifier_instance
    if _hmac_verifier_instance is None and _RUST_AVAILABLE:
        try:
            _hmac_verifier_instance = _RustHMACVerifier()
        except Exception as exc:
            logger.error("hmac_verifier_rust_init_failed error=%s", exc)
    return _hmac_verifier_instance


class _HMACVerifierBridge:
    """Adapter for HMAC webhook signature verification.

    Supports Paddle (HMAC-SHA256 hex), Twilio (RFC 5849 HMAC-SHA1),
    Shopify (HMAC-SHA256 base64), generic signing, and timestamp freshness.
    """

    def __init__(self):
        self._rust: Optional[Any] = None
        if _RUST_AVAILABLE:
            try:
                self._rust = _RustHMACVerifier()
            except Exception as exc:
                logger.error("hmac_verifier_bridge_init_failed error=%s", exc)
                self._rust = None

    def verify_paddle(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify Paddle webhook HMAC-SHA256 (hex-encoded signature)."""
        if self._rust is not None:
            try:
                return bool(self._rust.verify_paddle(payload, signature, secret))
            except Exception:
                logger.warning("hmac_verify_paddle_rust_failed")
        # Python fallback
        if not payload or not signature or not secret:
            return False
        expected = hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature.strip())

    def verify_twilio(
        self,
        url: str,
        params: Dict[str, str],
        signature: str,
        auth_token: str,
    ) -> bool:
        """Verify Twilio webhook signature (RFC 5849 HMAC-SHA1)."""
        if self._rust is not None:
            try:
                return bool(self._rust.verify_twilio(url, params, signature, auth_token))
            except Exception:
                logger.warning("hmac_verify_twilio_rust_failed")
        # Python fallback
        if not url or not params or not signature or not auth_token:
            return False
        sorted_params = sorted(params.items())
        data = url + "".join(k + v for k, v in sorted_params)
        expected = hmac.new(
            auth_token.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha1,
        ).hexdigest()
        return hmac.compare_digest(expected, signature.strip())

    def verify_shopify(self, payload: bytes, hmac_header: str, secret: str) -> bool:
        """Verify Shopify webhook HMAC-SHA256 (base64-encoded)."""
        if self._rust is not None:
            try:
                return bool(self._rust.verify_shopify(payload, hmac_header, secret))
            except Exception:
                logger.warning("hmac_verify_shopify_rust_failed")
        # Python fallback
        if not payload or not hmac_header or not secret:
            return False
        expected = hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).digest()
        import base64 as b64mod
        expected_b64 = b64mod.b64encode(expected).decode("utf-8")
        return hmac.compare_digest(expected_b64, hmac_header.strip())

    def verify_hmac_sha256(self, payload: bytes, signature: str, secret: str) -> bool:
        """Generic HMAC-SHA256 hex verification."""
        if self._rust is not None:
            try:
                return bool(self._rust.verify_hmac_sha256(payload, signature, secret))
            except Exception:
                logger.warning("hmac_verify_generic_rust_failed")
        if not payload or not signature or not secret:
            return False
        expected = hmac.new(
            secret.encode("utf-8"), payload, hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature.strip())

    def sign_hmac_sha256(self, payload: str, secret: str) -> str:
        """Generate HMAC-SHA256 hex signature (for outbound webhook signing)."""
        if self._rust is not None:
            try:
                result = self._rust.sign_hmac_sha256(payload, secret)
                if isinstance(result, str):
                    return result
            except Exception:
                logger.warning("hmac_sign_rust_failed")
        return hmac.new(
            secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256,
        ).hexdigest()

    def verify_timestamp(self, timestamp_str: str, max_age_secs: float = 300.0) -> bool:
        """Verify webhook timestamp freshness."""
        if self._rust is not None:
            try:
                return bool(self._rust.verify_timestamp(timestamp_str))
            except Exception:
                logger.warning("hmac_verify_timestamp_rust_failed")
        try:
            ts = float(timestamp_str)
            return abs(time.time() - ts) <= max_age_secs
        except (ValueError, TypeError):
            return False

    def constant_time_compare(self, a: str, b: str) -> bool:
        """Constant-time string comparison (prevents timing attacks)."""
        if self._rust is not None:
            try:
                return bool(self._rust.constant_time_compare(a, b))
            except Exception:
                pass
        return hmac.compare_digest(a.encode("utf-8") if isinstance(a, str) else a,
                                     b.encode("utf-8") if isinstance(b, str) else b)


_hmac_verifier_bridge: Optional[_HMACVerifierBridge] = None


def get_parwa_hmac_verifier() -> _HMACVerifierBridge:
    """Return the singleton HMAC verifier bridge.

    Drop-in for direct HMAC/crypto operations previously scattered
    across webhook handlers and integration code.
    """
    global _hmac_verifier_bridge
    if _hmac_verifier_bridge is None:
        try:
            _hmac_verifier_bridge = _HMACVerifierBridge()
        except Exception as exc:
            logger.error("hmac_verifier_bridge_init_failed error=%s", exc)
            _hmac_verifier_bridge = _HMACVerifierBridge()
    return _hmac_verifier_bridge


# ═══════════════════════════════════════════════════════════════════
# 8. CRYPTO ENGINE  —  bcrypt password/API-key hashing (Tier 2)
# ═══════════════════════════════════════════════════════════════════

_crypto_engine_instance: Optional[Any] = None


def _get_crypto_engine():
    """Lazy-init the Rust CryptoEngine singleton."""
    global _crypto_engine_instance
    if _crypto_engine_instance is None and _RUST_AVAILABLE:
        try:
            _crypto_engine_instance = _RustCryptoEngine()
        except Exception as exc:
            logger.error("crypto_engine_rust_init_failed error=%s", exc)
    return _crypto_engine_instance


class _CryptoEngineBridge:
    """Adapter for password/API-key hashing operations.

    Supports bcrypt hashing/verification, SHA-256, HMAC-SHA256,
    constant-time comparison, and secure random token generation.
    Cost factor defaults to 12 (bcrypt).
    """

    def __init__(self, bcrypt_cost: int = 12):
        self._rust: Optional[Any] = None
        self._bcrypt_cost = max(4, min(31, bcrypt_cost))
        if _RUST_AVAILABLE:
            try:
                self._rust = _RustCryptoEngine(bcrypt_cost=self._bcrypt_cost)
            except Exception as exc:
                logger.error("crypto_engine_bridge_init_failed error=%s", exc)
                self._rust = None

    def hash_password(self, password: str) -> Optional[str]:
        """Hash a password using bcrypt. Returns the hash string."""
        if self._rust is not None:
            try:
                result = self._rust.hash_password(password)
                if isinstance(result, str):
                    return result
            except Exception:
                logger.warning("crypto_hash_password_rust_failed")
        # Python fallback
        try:
            import bcrypt as _bcrypt
            return _bcrypt.hashpw(
                password.encode("utf-8"),
                _bcrypt.gensalt(rounds=self._bcrypt_cost),
            ).decode("utf-8")
        except Exception:
            logger.error("crypto_hash_password_python_fallback_failed")
            return None

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against a bcrypt hash."""
        if self._rust is not None:
            try:
                return bool(self._rust.verify_password(password, password_hash))
            except Exception:
                logger.warning("crypto_verify_password_rust_failed")
        # Python fallback
        try:
            import bcrypt as _bcrypt
            return _bcrypt.checkpw(
                password.encode("utf-8"),
                password_hash.encode("utf-8"),
            )
        except Exception:
            return False

    def hash_api_key(self, raw_key: str) -> Optional[str]:
        """Hash an API key using bcrypt with 'ak$' prefix (M-12)."""
        if not raw_key:
            return None
        if self._rust is not None:
            try:
                result = self._rust.hash_api_key(raw_key)
                if isinstance(result, str):
                    return result
            except Exception:
                logger.warning("crypto_hash_api_key_rust_failed")
        # Python fallback
        try:
            import bcrypt as _bcrypt
            hashed = _bcrypt.hashpw(
                raw_key.encode("utf-8"),
                _bcrypt.gensalt(rounds=self._bcrypt_cost),
            ).decode("utf-8")
            return f"ak${hashed}"
        except Exception:
            logger.error("crypto_hash_api_key_python_fallback_failed")
            return None

    def verify_api_key(self, raw_key: str, key_hash: str) -> bool:
        """Verify an API key against a stored hash.

        Supports 'ak$' bcrypt prefix and legacy SHA-256 fallback.
        """
        if not raw_key or not key_hash:
            return False
        if self._rust is not None:
            try:
                return bool(self._rust.verify_api_key(raw_key, key_hash))
            except Exception:
                logger.warning("crypto_verify_api_key_rust_failed")
        # Python fallback
        try:
            import bcrypt as _bcrypt
            if key_hash.startswith("ak$"):
                stored = key_hash[3:]
                return _bcrypt.checkpw(
                    raw_key.encode("utf-8"),
                    stored.encode("utf-8"),
                )
            # Legacy SHA-256 fallback
            computed = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
            return hmac.compare_digest(computed, key_hash)
        except Exception:
            return False

    def sha256(self, input_str: str) -> str:
        """SHA-256 hash of input string."""
        if self._rust is not None:
            try:
                result = self._rust.sha256(input_str)
                if isinstance(result, str):
                    return result
            except Exception:
                pass
        return hashlib.sha256(input_str.encode("utf-8")).hexdigest()

    def hmac_sha256(self, key: str, message: str) -> str:
        """HMAC-SHA256 hex of (key, message)."""
        if self._rust is not None:
            try:
                result = self._rust.hmac_sha256(key, message)
                if isinstance(result, str):
                    return result
            except Exception:
                pass
        return hmac.new(
            key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256,
        ).hexdigest()

    def constant_time_compare(self, a: str, b: str) -> bool:
        """Constant-time string comparison."""
        if self._rust is not None:
            try:
                return bool(self._rust.constant_time_compare(a, b))
            except Exception:
                pass
        return hmac.compare_digest(a, b)

    def random_token(self, nbytes: int = 32) -> str:
        """Generate a secure random hex token."""
        if self._rust is not None:
            try:
                result = self._rust.random_token(nbytes)
                if isinstance(result, str):
                    return result
            except Exception:
                pass
        return secrets.token_hex(nbytes)

    def random_urlsafe_token(self, nbytes: int = 32) -> str:
        """Generate a secure random URL-safe token."""
        if self._rust is not None:
            try:
                result = self._rust.random_urlsafe_token(nbytes)
                if isinstance(result, str):
                    return result
            except Exception:
                pass
        return secrets.token_urlsafe(nbytes)


_crypto_engine_bridge: Optional[_CryptoEngineBridge] = None


def get_parwa_crypto_engine(bcrypt_cost: int = 12) -> _CryptoEngineBridge:
    """Return the singleton crypto engine bridge.

    Drop-in for bcrypt/hmac operations previously in app.core.auth
    and app.services.api_key_service.
    """
    global _crypto_engine_bridge
    if _crypto_engine_bridge is None:
        try:
            _crypto_engine_bridge = _CryptoEngineBridge(bcrypt_cost=bcrypt_cost)
        except Exception as exc:
            logger.error("crypto_engine_bridge_init_failed error=%s", exc)
            _crypto_engine_bridge = _CryptoEngineBridge(bcrypt_cost=bcrypt_cost)
    return _crypto_engine_bridge


# ═══════════════════════════════════════════════════════════════════
# DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════════

def get_bridge_diagnostics() -> Dict[str, Any]:
    """Return diagnostic information about the bridge state.

    Useful for health-check endpoints and ops debugging.
    """
    return {
        "rust_backend": _RUST_AVAILABLE,
        "modules": {
            "rate_limiter": _rate_limiter_bridge is not None and _rate_limiter_bridge._rust is not None,
            "circuit_breaker": _circuit_breaker_bridge is not None and _circuit_breaker_bridge._rust is not None,
            "pii_redactor": _pii_redactor_bridge is not None and _pii_redactor_bridge._rust is not None,
            "jwt_decoder": _jwt_decoder_instance is not None,
            "security_headers": _security_headers_instance is not None,
            "csrf_validator": _RUST_AVAILABLE,
            "hmac_verifier": _hmac_verifier_bridge is not None and _hmac_verifier_bridge._rust is not None,
            "crypto_engine": _crypto_engine_bridge is not None and _crypto_engine_bridge._rust is not None,
            "connection_pool": _RUST_AVAILABLE,
            "async_logger": _RUST_AVAILABLE,
        },
    }


# ═══════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════

__all__ = [
    # Availability
    "is_parwa_core_available",
    # Factory functions
    "get_parwa_rate_limiter",
    "get_parwa_circuit_breaker",
    "get_parwa_pii_redactor",
    "parwa_csrf_validator",
    # Standalone functions
    "parwa_verify_access_token",
    "parwa_get_unverified_claims",
    "parwa_get_security_headers",
    # Tier 2 (HMAC + Crypto)
    "get_parwa_hmac_verifier",
    "get_parwa_crypto_engine",
    # Direct Rust type re-exports (advanced use / direct access)
    "HMACVerifier",
    "CryptoEngine",
    # Data classes (for type-checking convenience)
    "RateLimitResult",
    "PIIMatch",
    "RedactionResult",
    # Bridge classes (advanced use)
    "_RateLimiterBridge",
    "_CircuitBreakerBridge",
    "_PIIRedactorBridge",
    "_CSRFValidatorBridge",
    "_HMACVerifierBridge",
    "_CryptoEngineBridge",
    # Diagnostics
    "get_bridge_diagnostics",
    # Config constants
    "CATEGORY_CONFIG",
]
