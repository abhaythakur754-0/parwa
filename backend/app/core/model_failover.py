"""
Model Failover System (F-055): Automatic Provider Fallback Chain.

Detects rate limits, timeouts, degraded responses, and server errors.
Falls through to backup providers without dropping conversations.
Tracks provider health for circuit-breaker patterns.

BC-007: All AI through Smart Router.
BC-004: Retry with exponential backoff.
BC-008: Never drop a conversation — always find a working provider.
BC-001: company_id is second parameter.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Enums ──────────────────────────────────────────────────────────


class FailoverReason(str, Enum):
    """Why a provider failed and triggered failover."""
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"
    DEGRADED_RESPONSE = "degraded_response"
    INVALID_RESPONSE = "invalid_response"
    CONNECTION_ERROR = "connection_error"
    AUTH_ERROR = "auth_error"
    UNKNOWN = "unknown"


class ProviderState(str, Enum):
    """Current health state of a provider+model circuit."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CIRCUIT_OPEN = "circuit_open"


# ── Data Classes ───────────────────────────────────────────────────


@dataclass
class FailoverEvent:
    """Record of a single failover occurrence."""
    provider: str
    model_id: str
    reason: FailoverReason
    error_message: str
    timestamp: str  # UTC ISO-8601 (BC-012)
    latency_ms: int = 0
    http_status_code: int = 0
    response_snippet: str = ""


@dataclass
class CircuitBreaker:
    """Circuit breaker state for one provider+model combination."""
    provider: str
    model_id: str
    state: ProviderState = ProviderState.HEALTHY
    failure_count: int = 0
    success_count: int = 0
    last_failure_at: Optional[str] = None  # UTC ISO-8601
    last_success_at: Optional[str] = None  # UTC ISO-8601
    recovery_threshold: int = 3  # failures to open circuit
    recovery_timeout_seconds: float = 60.0  # seconds before half-open
    half_open_max_calls: int = 1
    half_open_call_count: int = 0
    total_failures: int = 0  # lifetime failures
    total_successes: int = 0  # lifetime successes
    total_latency_ms: int = 0  # cumulative for averaging

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model_id}"

    @property
    def avg_latency_ms(self) -> float:
        total = self.total_failures + self.total_successes
        if total == 0:
            return 0.0
        return self.total_latency_ms / total


# ── Provider + Model Registry ─────────────────────────────────────
# Default provider chain: google → cerebras → groq
# Default model per tier — will be overridden by Smart Router / config

DEFAULT_PROVIDERS = ["google", "cerebras", "groq"]

DEFAULT_MODELS: Dict[str, str] = {
    "google": "gemini-3.1-flash-lite",
    "cerebras": "llama-3.1-8b",
    "groq": "llama-3.1-8b",
}

# Tier → ordered list of (provider, model_id)
# Model IDs must match SmartRouter MODEL_REGISTRY keys.
# Each tier has its own chain; on full exhaustion, falls to lower tier.
FAILOVER_CHAINS: Dict[str, List[Tuple[str, str]]] = {
    "light": [
        ("cerebras", "llama-3.1-8b"),
        ("groq", "llama-3.1-8b"),
        ("google", "gemma-3-27b-it"),
    ],
    "medium": [
        ("google", "gemini-3.1-flash-lite"),  # Primary: 500 RPD, 250K TPM
        ("google", "gemini-2.5-flash-preview-05-20"),  # Backup: 1500 RPD
        ("groq", "llama-3.3-70b-versatile"),
        ("groq", "qwen3-32b"),
        # Falls to LIGHT if all MEDIUM exhausted
        ("cerebras", "llama-3.1-8b"),
    ],
    "heavy": [
        ("cerebras", "gpt-oss-120b"),
        ("groq", "gpt-oss-120b"),
        ("groq", "llama-4-scout-instruct"),
        # Falls to MEDIUM then LIGHT
        ("google", "gemini-3.1-flash-lite"),
        ("cerebras", "llama-3.1-8b"),
    ],
    "guardrail": [
        ("groq", "llama-guard-4-12b"),
        # Guardrail has no fallback tier
        ("cerebras", "llama-3.1-8b"),
    ],
}


# ── Degraded Response Detector ─────────────────────────────────────


class DegradedResponseDetector:
    """
    Analyzes LLM responses to detect degraded or broken output.

    Checks for:
    - Empty / whitespace-only responses
    - Responses below minimum length
    - Error message patterns in response text
    - Refusal patterns (model refusing to answer)
    - Repetitive / looped text
    - Gibberish detection (low unique character ratio)
    """

    # Patterns that indicate the model returned an error instead of content
    ERROR_PATTERNS: List[str] = [
        r"internal\s+server\s+error",
        r"500\s+error",
        r"502\s+bad\s+gateway",
        r"503\s+service\s+unavailable",
        r"rate\s+limit",
        r"too\s+many\s+requests",
        r"\berror\b.*\boccurred\b",
        r"\bfailed\b.*\bprocess\b",
        r"\bunable\b.*\bcomplete\b",
        r"\bservice\b.*\bunavailable\b",
        r"\bapi\b.*\berror\b",
        r"\btimeout\b.*\bexceeded\b",
        r"\bconnection\b.*\brefused\b",
        r"\bquota\b.*\bexceeded\b",
    ]

    # Refusal patterns where the model declines to answer
    REFUSAL_PATTERNS: List[str] = [
        r"i\s+(?:can'?t|cannot|am\s+unable\s+to)\s+(?:answer|respond|help|provide)",
        r"i\s+(?:don'?t|do\s+not)\s+have\s+(?:access|information|the\s+ability)",
        r"i'?m\s+(?:not\s+able|unable)\s+to\s+(?:assist|help|respond|provide)",
        r"as\s+an?\s+ai\s+.*(?:can'?t|cannot|unable)",
        r"i\s+must\s+(?:decline|refuse|politely\s+pass)",
    ]

    # Repetition: same short phrase repeated 3+ times
    REPETITION_PATTERN = re.compile(
        r"(.{5,50}?)\1{2,}", re.DOTALL | re.IGNORECASE
    )

    def is_degraded(
        self, response_text: str, expected_min_length: int = 50
    ) -> Tuple[bool, str]:
        """
        Check if a response is degraded.

        Returns:
            (is_degraded, reason_string)
        """
        if not response_text or not response_text.strip():
            return True, "empty_response"

        text = response_text.strip()

        if len(text) < expected_min_length:
            return True, f"too_short ({
                len(text)} < {expected_min_length} chars)"

        for pattern in self.ERROR_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True, f"error_pattern: {pattern[:30]}"

        for pattern in self.REFUSAL_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True, f"refusal_pattern: {pattern[:30]}"

        if self._is_repetitive(text):
            return True, "repetitive_text"

        if self._is_gibberish(text):
            return True, "gibberish_text"

        return False, "ok"

    def check_response_quality(
        self, response: dict
    ) -> Tuple[bool, float, str]:
        """
        Assess the quality of a structured response dict.

        Args:
            response: Dict with at least a 'content' or 'text' key.

        Returns:
            (is_good, quality_score_0_to_1, reason)
        """
        # Extract text from various response formats
        text = response.get("content") or response.get(
            "text") or response.get("message", "")

        if isinstance(text, dict):
            text = text.get("content", "")
        if not isinstance(text, str):
            text = str(text)

        score = 1.0
        reason_parts: List[str] = []

        # Empty check
        if not text or not text.strip():
            return False, 0.0, "empty_response"

        text = text.strip()

        # Length scoring
        length = len(text)
        if length < 20:
            score -= 0.55
            reason_parts.append("very_short")
        elif length < 50:
            score -= 0.25
            reason_parts.append("short")

        # Error pattern check (heavy penalty)
        for pattern in self.ERROR_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                score -= 0.55
                reason_parts.append("error_pattern")
                break

        # Refusal check (0-0.20 penalty)
        for pattern in self.REFUSAL_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                score -= 0.20
                reason_parts.append("refusal_pattern")
                break

        # Repetition check (0-0.15 penalty)
        if self._is_repetitive(text):
            score -= 0.15
            reason_parts.append("repetitive")

        # Gibberish check (0-0.15 penalty)
        if self._is_gibberish(text):
            score -= 0.15
            reason_parts.append("gibberish")

        # Clamp score
        score = max(0.0, min(1.0, score))
        is_good = score >= 0.5

        reason = "; ".join(reason_parts) if reason_parts else "ok"
        return is_good, score, reason

    def _is_repetitive(self, text: str) -> bool:
        """Detect if text contains repetitive loops."""
        match = self.REPETITION_PATTERN.search(text)
        if match:
            # The repeated portion should be a significant fraction
            repeated = match.group(0)
            return len(repeated) > len(text) * 0.3
        return False

    def _is_gibberish(self, text: str) -> bool:
        """
        Rough gibberish detection based on unique character ratio
        and word-like token ratio.
        """
        if len(text) < 20:
            return False

        # Check unique character ratio — gibberish tends to have
        # either very low or very high ratios
        unique_chars = len(set(text.lower()))
        total_chars = len(text)
        unique_ratio = unique_chars / total_chars if total_chars > 0 else 0

        # Very low uniqueness = repetitive (but normal English
        # text at 300 chars has ~0.10-0.15 ratio, so use conservative
        # threshold)
        if unique_ratio < 0.06:
            return True

        # Check word quality: ratio of alphanumeric tokens
        words = re.findall(r"\b\w+\b", text)
        if not words:
            return True

        # Ratio of "real-looking" words (length >= 2, contains vowels)
        vowel_pattern = re.compile(r"[aeiou]")
        real_words = sum(
            1 for w in words if len(w) >= 2 and vowel_pattern.search(w.lower())
        )
        word_quality = real_words / len(words) if words else 0

        return word_quality < 0.3


# ── Failover Manager ───────────────────────────────────────────────


class FailoverManager:
    """
    Central manager for provider health tracking and failover routing.

    Maintains circuit breakers for all provider+model combos and
    provides ordered failover chains that skip unhealthy providers.
    """

    def __init__(
        self,
        chains: Optional[Dict[str, List[Tuple[str, str]]]] = None,
        recovery_threshold: int = 3,
        recovery_timeout_seconds: float = 60.0,
    ):
        self._chains = chains or dict(FAILOVER_CHAINS)
        self._recovery_threshold = recovery_threshold
        self._recovery_timeout_seconds = recovery_timeout_seconds
        self._circuits: Dict[str, CircuitBreaker] = {}
        self._events: List[FailoverEvent] = []
        self._max_events = 10000  # Prevent unbounded memory growth
        self._stats_per_company: Dict[str,
                                      List[FailoverEvent]] = defaultdict(list)

        self._init_circuits()

    def _init_circuits(self) -> None:
        """Create circuit breakers for all provider+model combos."""
        for tier_entries in self._chains.values():
            for provider, model_id in tier_entries:
                key = f"{provider}:{model_id}"
                if key not in self._circuits:
                    self._circuits[key] = CircuitBreaker(
                        provider=provider,
                        model_id=model_id,
                        recovery_threshold=self._recovery_threshold,
                        recovery_timeout_seconds=self._recovery_timeout_seconds,
                    )

    def _utc_now(self) -> str:
        """Return current UTC time as ISO-8601 string (BC-012)."""
        return datetime.now(timezone.utc).isoformat()

    def _get_circuit(self, provider: str, model_id: str) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        key = f"{provider}:{model_id}"
        if key not in self._circuits:
            self._circuits[key] = CircuitBreaker(
                provider=provider,
                model_id=model_id,
                recovery_threshold=self._recovery_threshold,
                recovery_timeout_seconds=self._recovery_timeout_seconds,
            )
        return self._circuits[key]

    # ── Success / Failure Reporting ──────────────────────────────

    def report_success(
        self,
        provider: str,
        model_id: str,
        latency_ms: int,
        response: dict,
    ) -> None:
        """
        Record a successful call. Resets failure count and transitions
        circuit from half_open → closed if applicable.
        """
        circuit = self._get_circuit(provider, model_id)
        now = self._utc_now()

        circuit.success_count += 1
        circuit.total_successes += 1
        circuit.total_latency_ms += latency_ms
        circuit.last_success_at = now

        # Close circuit if half-open or degraded
        if circuit.state in (
                ProviderState.DEGRADED,
                ProviderState.CIRCUIT_OPEN):
            circuit.state = ProviderState.HEALTHY
            circuit.failure_count = 0
            circuit.half_open_call_count = 0
        elif circuit.failure_count > 0:
            # Partial recovery: reduce failure count on success
            circuit.failure_count = max(0, circuit.failure_count - 1)
            logger.info(
                "Circuit closed for %s after successful call",
                circuit.key,
            )

    def report_failure(
        self,
        provider: str,
        model_id: str,
        reason: FailoverReason,
        error_msg: str,
        latency_ms: int = 0,
        http_status: int = 0,
        company_id: Optional[str] = None,
    ) -> None:
        """
        Record a failed call. Increments failure count and opens
        circuit if threshold is reached.
        """
        circuit = self._get_circuit(provider, model_id)
        now = self._utc_now()

        circuit.failure_count += 1
        circuit.total_failures += 1
        circuit.total_latency_ms += latency_ms
        circuit.last_failure_at = now

        # Record event
        event = FailoverEvent(
            provider=provider,
            model_id=model_id,
            reason=reason,
            error_message=error_msg,
            timestamp=now,
            latency_ms=latency_ms,
            http_status_code=http_status,
        )
        self._events.append(event)

        # Trim old events to prevent memory leak
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events // 2:]
            logger.debug("Trimmed failover events to %d", len(self._events))

        if company_id:
            self._stats_per_company[company_id].append(event)

        # Open circuit if threshold reached
        if circuit.failure_count >= circuit.recovery_threshold:
            circuit.state = ProviderState.CIRCUIT_OPEN
            circuit.half_open_call_count = 0
            logger.warning(
                "Circuit OPEN for %s after %d failures (reason: %s)",
                circuit.key,
                circuit.failure_count,
                reason.value,
            )
        elif circuit.failure_count >= 1:
            circuit.state = ProviderState.DEGRADED

        logger.info(
            "Failure reported for %s: %s — %s",
            circuit.key,
            reason.value,
            error_msg[:100],
        )

    # ── State Queries ────────────────────────────────────────────

    def get_provider_state(
            self,
            provider: str,
            model_id: str) -> ProviderState:
        """Return current circuit state, checking recovery timeouts."""
        self._check_recovery(provider, model_id)
        circuit = self._get_circuit(provider, model_id)
        return circuit.state

    def is_available(self, provider: str, model_id: str) -> bool:
        """Can this provider+model be used right now?"""
        state = self.get_provider_state(provider, model_id)
        return state in (ProviderState.HEALTHY, ProviderState.DEGRADED)

    def get_failover_chain(self, tier: str) -> List[Tuple[str, str]]:
        """
        Return ordered list of (provider, model_id) for a tier,
        skipping circuit-open providers.
        """
        chain = self._chains.get(tier, [])
        available: List[Tuple[str, str]] = []
        for provider, model_id in chain:
            if self.is_available(provider, model_id):
                available.append((provider, model_id))
            else:
                logger.warning(
                    "Skipping %s:%s in failover chain — circuit is %s",
                    provider,
                    model_id,
                    self.get_provider_state(provider, model_id).value,
                )
        return available

    def get_all_circuit_states(self) -> Dict[str, Dict[str, Any]]:
        """Overview of all circuit breaker states."""
        result: Dict[str, Dict[str, Any]] = {}
        for key, circuit in self._circuits.items():
            self._check_recovery(circuit.provider, circuit.model_id)
            result[key] = {
                "provider": circuit.provider,
                "model_id": circuit.model_id,
                "state": circuit.state.value,
                "failure_count": circuit.failure_count,
                "total_failures": circuit.total_failures,
                "total_successes": circuit.total_successes,
                "avg_latency_ms": round(circuit.avg_latency_ms, 1),
                "last_failure_at": circuit.last_failure_at,
                "last_success_at": circuit.last_success_at,
            }
        return result

    def get_failover_stats(
        self, company_id: str, hours: int = 24
    ) -> Dict[str, Any]:
        """
        Aggregate failover stats for a company over the last N hours.

        BC-001: company_id is the first parameter (stats context).
        """
        now = datetime.now(timezone.utc)
        cutoff = now.timestamp() - (hours * 3600)

        events = self._stats_per_company.get(company_id, [])
        recent = []
        for event in events:
            try:
                event_time = datetime.fromisoformat(
                    event.timestamp).timestamp()
                if event_time >= cutoff:
                    recent.append(event)
            except (ValueError, TypeError):
                continue

        # Aggregate by provider
        provider_stats: Dict[str, Dict[str, Any]] = {}
        for event in recent:
            prov = event.provider
            if prov not in provider_stats:
                provider_stats[prov] = {
                    "failures": 0,
                    "reasons": defaultdict(int),
                    "last_error": None,
                }
            provider_stats[prov]["failures"] += 1
            provider_stats[prov]["reasons"][event.reason.value] += 1
            provider_stats[prov]["last_error"] = event.timestamp

        # Convert defaultdicts
        for prov in provider_stats:
            provider_stats[prov]["reasons"] = dict(
                provider_stats[prov]["reasons"]
            )

        circuit_states = self.get_all_circuit_states()

        return {
            "company_id": company_id,
            "period_hours": hours,
            "total_failovers": len(recent),
            "provider_stats": provider_stats,
            "circuit_states": circuit_states,
            "generated_at": self._utc_now(),
        }

    def reset_circuit(self, provider: str, model_id: str) -> bool:
        """Manually reset a circuit breaker to healthy state."""
        circuit = self._get_circuit(provider, model_id)
        circuit.state = ProviderState.HEALTHY
        circuit.failure_count = 0
        circuit.success_count = 0
        circuit.half_open_call_count = 0
        logger.info("Circuit manually reset for %s", circuit.key)
        return True

    def _check_recovery(self, provider: str, model_id: str) -> None:
        """
        Check if a circuit should transition:
          circuit_open → healthy (after recovery_timeout)

        Simplified model: after timeout, circuit goes back to healthy
        so it gets a chance to prove itself.
        """
        circuit = self._get_circuit(provider, model_id)
        if circuit.state != ProviderState.CIRCUIT_OPEN:
            return

        if circuit.last_failure_at is None:
            return

        try:
            last_fail = datetime.fromisoformat(circuit.last_failure_at)
            elapsed = (datetime.now(timezone.utc) - last_fail).total_seconds()
        except (ValueError, TypeError):
            return

        if elapsed >= circuit.recovery_timeout_seconds:
            circuit.state = ProviderState.HEALTHY
            circuit.failure_count = 0
            circuit.half_open_call_count = 0
            logger.info(
                "Circuit recovered (open → healthy) for %s after %.1fs",
                circuit.key,
                elapsed,
            )


# ── Failover Chain Executor ────────────────────────────────────────


class FailoverChainExecutor:
    """
    Executes LLM calls through a failover chain, automatically
    retrying with backup providers on failure.

    BC-004: Retry with exponential backoff.
    BC-008: Never drop a conversation — always return something.
    BC-001: company_id is second parameter.
    """

    # Exception types that should trigger failover
    FAILOVER_EXCEPTIONS = (
        ConnectionError,
        TimeoutError,
        OSError,
    )

    def __init__(self, failover_manager: FailoverManager):
        self.manager = failover_manager
        self.detector = DegradedResponseDetector()

    def execute_with_failover(
        self,
        company_id: str,
        chain: List[Tuple[str, str]],
        call_fn: Callable,
        max_retries: int = 3,
    ) -> dict:
        """
        Execute an LLM call through the failover chain.

        Args:
            company_id: Tenant identifier (BC-001).
            chain: Ordered list of (provider, model_id) to try.
            call_fn: callable(provider, model_id, ...) -> dict.
                     Must raise on failure. Returns response dict.
            max_retries: Max retries per provider before moving on.

        Returns:
            First successful response dict, or a graceful error dict
            if ALL providers fail (BC-008).
        """
        if not chain:
            logger.error("Empty failover chain for company %s", company_id)
            return self._build_error_response([])

        failover_events: List[FailoverEvent] = []

        for provider, model_id in chain:
            # Check circuit breaker
            if not self.manager.is_available(provider, model_id):
                event = FailoverEvent(
                    provider=provider,
                    model_id=model_id,
                    reason=FailoverReason.SERVER_ERROR,
                    error_message="Circuit breaker open",
                    timestamp=self.manager._utc_now(),
                )
                failover_events.append(event)
                continue

            # Try the provider with retries
            for attempt in range(1, max_retries + 1):
                try:
                    result = self._execute_single(
                        provider, model_id, call_fn
                    )
                    latency_ms = result.get("latency_ms", 0)

                    # Check for degraded response
                    response_text = (
                        result.get("content")
                        or result.get("text")
                        or result.get("message", "")
                    )
                    if isinstance(response_text, dict):
                        response_text = response_text.get("content", "")
                    if not isinstance(response_text, str):
                        response_text = str(response_text)

                    is_degraded, degradation_reason = self.detector.is_degraded(
                        response_text)

                    if is_degraded:
                        logger.warning(
                            "Degraded response from %s:%s: %s",
                            provider,
                            model_id,
                            degradation_reason,
                        )
                        # Report as degraded but still use it if no other
                        # option
                        self.manager.report_failure(
                            provider=provider,
                            model_id=model_id,
                            reason=FailoverReason.DEGRADED_RESPONSE,
                            error_msg=degradation_reason,
                            latency_ms=latency_ms,
                            company_id=company_id,
                        )
                        # If we have more providers in chain, continue
                        if provider != chain[-1][0]:
                            failover_events.append(
                                FailoverEvent(
                                    provider=provider,
                                    model_id=model_id,
                                    reason=FailoverReason.DEGRADED_RESPONSE,
                                    error_message=degradation_reason,
                                    timestamp=self.manager._utc_now(),
                                    latency_ms=latency_ms,
                                    response_snippet=response_text[:200],
                                )
                            )
                            break  # Move to next provider
                        else:
                            # Last provider — return even if degraded
                            result["_failover_used"] = True
                            result["_degraded"] = True
                            result["_degradation_reason"] = degradation_reason
                            self.manager.report_success(
                                provider=provider,
                                model_id=model_id,
                                latency_ms=latency_ms,
                                response=result,
                            )
                            return result

                    # Success!
                    self.manager.report_success(
                        provider=provider,
                        model_id=model_id,
                        latency_ms=latency_ms,
                        response=result,
                    )
                    result["_failover_used"] = failover_events and True or False
                    return result

                except self.FAILOVER_EXCEPTIONS as exc:
                    reason, http_status = self._classify_exception(exc)
                    logger.warning(
                        "Attempt %d/%d failed for %s:%s — %s",
                        attempt,
                        max_retries,
                        provider,
                        model_id,
                        str(exc)[:100],
                    )

                    # Exponential backoff (BC-004)
                    if attempt < max_retries:
                        backoff = min(2 ** (attempt - 1), 8)  # max 8s
                        time.sleep(backoff)

                    self.manager.report_failure(
                        provider=provider,
                        model_id=model_id,
                        reason=reason,
                        error_msg=str(exc),
                        latency_ms=0,
                        http_status=http_status,
                        company_id=company_id,
                    )

            # Provider exhausted retries — record and move on
            failover_events.append(
                FailoverEvent(
                    provider=provider,
                    model_id=model_id,
                    reason=FailoverReason.UNKNOWN,
                    error_message="All retries exhausted",
                    timestamp=self.manager._utc_now(),
                )
            )

        # ALL providers failed — graceful degradation (BC-008)
        logger.error(
            "ALL providers failed for company %s — returning graceful error",
            company_id,
        )
        return self._build_error_response(failover_events)

    async def async_execute_with_failover(
        self,
        company_id: str,
        chain: List[Tuple[str, str]],
        call_fn: Callable,
        max_retries: int = 3,
    ) -> dict:
        """Async version of execute_with_failover for MAKER concurrent calls.

        Same logic but uses asyncio.sleep instead of time.sleep
        and awaits async call_fn.
        """
        if not chain:
            logger.error(
                "Empty async failover chain for company %s",
                company_id)
            return self._build_error_response([])

        failover_events: List[FailoverEvent] = []

        for provider, model_id in chain:
            if not self.manager.is_available(provider, model_id):
                event = FailoverEvent(
                    provider=provider,
                    model_id=model_id,
                    reason=FailoverReason.SERVER_ERROR,
                    error_message="Circuit breaker open",
                    timestamp=self.manager._utc_now(),
                )
                failover_events.append(event)
                continue

            for attempt in range(1, max_retries + 1):
                try:
                    # Support both sync and async call_fn
                    if asyncio.iscoroutinefunction(call_fn):
                        result = await call_fn(provider, model_id)
                    else:
                        result = call_fn(provider, model_id)
                    if not isinstance(result, dict):
                        result = {"content": str(result)}

                    latency_ms = result.get("latency_ms", 0)

                    response_text = (
                        result.get("content")
                        or result.get("text")
                        or result.get("message", "")
                    )
                    if isinstance(response_text, dict):
                        response_text = response_text.get("content", "")
                    if not isinstance(response_text, str):
                        response_text = str(response_text)

                    is_degraded, degradation_reason = self.detector.is_degraded(
                        response_text)

                    if is_degraded:
                        logger.warning(
                            "Async degraded response from %s:%s: %s",
                            provider, model_id, degradation_reason,
                        )
                        self.manager.report_failure(
                            provider=provider,
                            model_id=model_id,
                            reason=FailoverReason.DEGRADED_RESPONSE,
                            error_msg=degradation_reason,
                            latency_ms=latency_ms,
                            company_id=company_id,
                        )
                        if provider != chain[-1][0]:
                            failover_events.append(
                                FailoverEvent(
                                    provider=provider,
                                    model_id=model_id,
                                    reason=FailoverReason.DEGRADED_RESPONSE,
                                    error_message=degradation_reason,
                                    timestamp=self.manager._utc_now(),
                                    latency_ms=latency_ms,
                                    response_snippet=response_text[:200],
                                )
                            )
                            break
                        else:
                            result["_failover_used"] = True
                            result["_degraded"] = True
                            result["_degradation_reason"] = degradation_reason
                            self.manager.report_success(
                                provider=provider,
                                model_id=model_id,
                                latency_ms=latency_ms,
                                response=result,
                            )
                            return result

                    self.manager.report_success(
                        provider=provider,
                        model_id=model_id,
                        latency_ms=latency_ms,
                        response=result,
                    )
                    result["_failover_used"] = bool(failover_events)
                    return result

                except self.FAILOVER_EXCEPTIONS as exc:
                    reason, http_status = self._classify_exception(exc)
                    logger.warning(
                        "Async attempt %d/%d failed for %s:%s — %s",
                        attempt, max_retries, provider, model_id,
                        str(exc)[:100],
                    )
                    if attempt < max_retries:
                        backoff = min(2 ** (attempt - 1), 8)
                        await asyncio.sleep(backoff)

                    self.manager.report_failure(
                        provider=provider,
                        model_id=model_id,
                        reason=reason,
                        error_msg=str(exc),
                        latency_ms=0,
                        http_status=http_status,
                        company_id=company_id,
                    )

            failover_events.append(
                FailoverEvent(
                    provider=provider,
                    model_id=model_id,
                    reason=FailoverReason.UNKNOWN,
                    error_message="All retries exhausted",
                    timestamp=self.manager._utc_now(),
                )
            )

        logger.error(
            "ALL providers failed (async) for company %s — returning graceful error",
            company_id,
        )
        return self._build_error_response(failover_events)

    def _execute_single(
        self,
        provider: str,
        model_id: str,
        call_fn: Callable,
    ) -> dict:
        """
        Execute a single provider call with error handling.

        Raises on failure so the executor can trigger failover.
        """
        try:
            result = call_fn(provider, model_id)
            if not isinstance(result, dict):
                result = {"content": str(result)}
            return result
        except self.FAILOVER_EXCEPTIONS:
            raise
        except Exception as exc:
            # Wrap unknown exceptions as ConnectionError for uniform handling
            raise ConnectionError(
                f"Unexpected error calling {provider}/{model_id}: {str(exc)}"
            ) from exc

    def _classify_exception(
        self, exc: Exception
    ) -> Tuple[FailoverReason, int]:
        """Map exception type to FailoverReason and HTTP status code."""
        msg = str(exc).lower()

        if isinstance(exc, TimeoutError) or "timeout" in msg:
            return FailoverReason.TIMEOUT, 504
        if "rate" in msg or "429" in msg or "too many" in msg:
            return FailoverReason.RATE_LIMIT, 429
        if "auth" in msg or "401" in msg or "403" in msg:
            return FailoverReason.AUTH_ERROR, 403
        if isinstance(exc, ConnectionError) or "connection" in msg:
            return FailoverReason.CONNECTION_ERROR, 503
        if "500" in msg or "502" in msg or "503" in msg:
            return FailoverReason.SERVER_ERROR, 500

        return FailoverReason.UNKNOWN, 0

    def _build_error_response(
            self,
            failover_events: List[FailoverEvent]) -> dict:
        """
        Build a graceful error response when ALL providers fail.

        BC-008: Never drop a conversation — always return something
        the system can work with.
        """
        provider_summary = [
            {
                "provider": e.provider,
                "model_id": e.model_id,
                "reason": e.reason.value,
                "error": e.error_message[:100],
            }
            for e in failover_events
        ]

        return {
            "content": (
                "I apologize, but I'm experiencing temporary difficulties "
                "processing your request. Our team has been notified and "
                "is working on a resolution. Please try again in a moment."
            ),
            "text": (
                "I apologize, but I'm experiencing temporary difficulties "
                "processing your request. Our team has been notified and "
                "is working on a resolution. Please try again in a moment."
            ),
            "_failover_used": True,
            "_all_providers_failed": True,
            "_failover_events": provider_summary,
            "_graceful_degradation": True,
            "_error_code": "F055_ALL_PROVIDERS_FAILED",
        }
