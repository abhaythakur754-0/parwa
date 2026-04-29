"""
AI Engine Cold Start Service (SG-30).

Handles first-request latency when no cache/warm models exist.
Implements:
  1. Warm-up probe on tenant activation
  2. Pre-warm common model+technique combos
  3. Loading indicator / readiness status
  4. Fallback to Light model if Heavy not ready within 5s

BC-001: company_id is second parameter.
BC-007: All AI through Smart Router.
BC-008: Graceful degradation.
BC-012: UTC timestamps.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from app.exceptions import ParwaBaseError

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

HEAVY_WARMUP_TIMEOUT_MS = 5000  # BC-008: 5s max for Heavy model

# P21: Cooldown between system-wide prewarm calls (seconds)
_PREWARM_COOLDOWN_SECONDS = 60


# ── Enums ────────────────────────────────────────────────────────────


class WarmupStatus(str, Enum):
    cold = "cold"
    warming = "warming"
    warm = "warm"
    cooling = "cooling"


# ── Dataclasses ──────────────────────────────────────────────────────


@dataclass
class ModelWarmupState:
    provider: str
    model_id: str
    tier: str
    status: WarmupStatus = WarmupStatus.cold
    last_warmed_at: Optional[str] = None  # ISO-8601 UTC (BC-012)
    warmup_latency_ms: int = 0
    warmup_success: bool = False
    error_message: Optional[str] = None
    probe_query: str = ""
    probe_response: Optional[str] = None


@dataclass
class TenantWarmupState:
    company_id: str
    variant_type: str
    overall_status: WarmupStatus = WarmupStatus.cold
    models_warmed: Dict[str, ModelWarmupState] = field(default_factory=dict)
    started_at: Optional[str] = None  # ISO-8601 UTC (BC-012)
    completed_at: Optional[str] = None  # ISO-8601 UTC (BC-012)
    time_to_warm_ms: int = 0
    fallback_used: bool = False


@dataclass
class PREWARM_COMBO:
    """A model+technique combination to pre-warm."""
    model_id: str
    provider: str
    tier: str
    probe_query: str
    max_acceptable_latency_ms: int


# ── Pre-warm Combinations ────────────────────────────────────────────
# Common model+technique combos across providers and tiers.

PREWARM_COMBOS: List[PREWARM_COMBO] = [
    # LIGHT tier
    PREWARM_COMBO(
        model_id="llama-3.1-8b",
        provider="cerebras",
        tier="light",
        probe_query="Hello",
        max_acceptable_latency_ms=2000,
    ),
    PREWARM_COMBO(
        model_id="llama-3.1-8b",
        provider="groq",
        tier="light",
        probe_query="Hello",
        max_acceptable_latency_ms=2000,
    ),
    PREWARM_COMBO(
        model_id="gemma-3-27b-it",
        provider="google",
        tier="light",
        probe_query="Hi",
        max_acceptable_latency_ms=2000,
    ),
    # MEDIUM tier
    PREWARM_COMBO(
        model_id="gemini-2.0-flash-lite",
        provider="google",
        tier="medium",
        probe_query="Classify: refund",
        max_acceptable_latency_ms=5000,
    ),
    PREWARM_COMBO(
        model_id="llama-3.3-70b-versatile",
        provider="groq",
        tier="medium",
        probe_query="Classify: billing",
        max_acceptable_latency_ms=5000,
    ),
    PREWARM_COMBO(
        model_id="qwen3-32b",
        provider="groq",
        tier="medium",
        probe_query="Analyze: inquiry",
        max_acceptable_latency_ms=5000,
    ),
    # HEAVY tier
    PREWARM_COMBO(
        model_id="gpt-oss-120b",
        provider="groq",
        tier="heavy",
        probe_query="Complex analysis",
        max_acceptable_latency_ms=8000,
    ),
    PREWARM_COMBO(
        model_id="llama-4-scout-instruct",
        provider="groq",
        tier="heavy",
        probe_query="Complex analysis",
        max_acceptable_latency_ms=8000,
    ),
    # GUARDRAIL tier
    PREWARM_COMBO(
        model_id="llama-guard-4-12b",
        provider="groq",
        tier="guardrail",
        probe_query="Is this safe",
        max_acceptable_latency_ms=3000,
    ),
]

# ── Variant → Tiers mapping ──────────────────────────────────────────
# Which tiers each variant type is entitled to warm.

VARIANT_TIER_MAP: Dict[str, List[str]] = {
    "mini_parwa": ["light", "guardrail"],
    "parwa": ["light", "medium", "guardrail"],
    "high_parwa": ["light", "medium", "heavy", "guardrail"],
}


def _utcnow() -> str:
    """Return current UTC time as ISO-8601 string (BC-012)."""
    return datetime.now(timezone.utc).isoformat()


# ── Cold Start Service ───────────────────────────────────────────────


class ColdStartService:
    """
    Main service for AI Engine cold start management.

    Handles:
      - Tenant-level warmup on activation
      - System-wide provider pre-warming
      - Readiness status tracking
      - Graceful fallback to lighter models (BC-008)
    """

    def __init__(self, max_tenant_states: int = 10000) -> None:
        # P8 FIX: Use OrderedDict for LRU eviction instead of plain dict.
        # Plain dict preserves insertion order (Python 3.7+), which means
        # oldest SIGNUPS get evicted, not least-recently-used tenants.
        self._tenant_states: OrderedDict[str,
                                         TenantWarmupState] = OrderedDict()
        self._max_tenant_states = max_tenant_states
        # P7: Track last accessed time for each tenant for LRU eviction
        # and for future persistence/recovery on restart.
        self._last_accessed: Dict[str, float] = {}
        # P21: Guard against rapid prewarm calls
        self._last_prewarm_time: float = 0.0
        self._prewarm_lock = threading.Lock()

    # ── Public API ───────────────────────────────────────────────────

    def get_tenant_status(
            self,
            company_id: str) -> Optional[TenantWarmupState]:
        """Get warmup status for a tenant. BC-001: company_id is second param."""
        if not company_id:
            return None
        state = self._tenant_states.get(company_id)
        if state:
            # P8: Update LRU access time
            self._last_accessed[company_id] = time.monotonic()
            self._tenant_states.move_to_end(company_id)
        return state

    def is_ready(self, company_id: str, tier: str = "light") -> bool:
        """Is the tenant's AI ready for a specific tier?"""
        if not company_id:
            return False
        state = self._tenant_states.get(company_id)
        if state is None:
            return False
        # P8: Touch LRU on access
        self._last_accessed[company_id] = time.monotonic()
        self._tenant_states.move_to_end(company_id)
        tier = tier.lower()
        for model_state in state.models_warmed.values():
            if model_state.tier == tier and model_state.warmup_success:
                return True
        return False

    def is_any_ready(self, company_id: str) -> bool:
        """Is at least LIGHT ready?"""
        return self.is_ready(company_id, tier="light")

    def warmup_tenant(
        self, company_id: str, variant_type: str
    ) -> TenantWarmupState:
        """
        Start warmup for all relevant models based on variant_type.
        BC-001: company_id is second parameter.
        BC-008: If Heavy exceeds 5s, mark fallback_used=True.
        """
        if not company_id:
            raise ParwaBaseError(
                message="company_id is required for tenant warmup",
                error_code="COLD_START_INVALID_COMPANY",
                status_code=400,
            )

        # Default to mini_parwa for unknown variant types
        if variant_type not in VARIANT_TIER_MAP:
            logger.warning(
                "Unknown variant_type '%s', defaulting to mini_parwa",
                variant_type,
            )
            variant_type = "mini_parwa"

        tiers_to_warm = VARIANT_TIER_MAP[variant_type]

        # Get combos for the tiers this variant supports
        combos = [
            c for c in PREWARM_COMBOS if c.tier in tiers_to_warm
        ]

        state = TenantWarmupState(
            company_id=company_id,
            variant_type=variant_type,
            overall_status=WarmupStatus.warming,
            started_at=_utcnow(),
        )

        self._tenant_states[company_id] = state
        self._last_accessed[company_id] = time.monotonic()

        # P8 FIX: Evict least-recently-used tenants (not oldest signups).
        # OrderedDict preserves insertion order, and move_to_end() is called
        # on every access, so the front of the dict is the LRU entry.
        if len(self._tenant_states) > self._max_tenant_states:
            evict_count = len(self._tenant_states) // 4  # Evict 25%
            evicted = []
            for _ in range(evict_count):
                if self._tenant_states:
                    k, _ = self._tenant_states.popitem(last=False)
                    self._last_accessed.pop(k, None)
                    evicted.append(k[:8])
            logger.info(
                "LRU evicted %d tenant states: %s",
                evict_count,
                evicted,
            )

        start_time = time.monotonic()

        for combo in combos:
            # BC-008: Enforce Heavy tier 5s timeout
            effective_timeout = combo.max_acceptable_latency_ms
            if combo.tier == "heavy":
                effective_timeout = min(
                    effective_timeout, HEAVY_WARMUP_TIMEOUT_MS)

            model_state = self._warmup_single_model(
                company_id, combo, timeout_ms=effective_timeout,
            )
            key = f"{combo.provider}:{combo.model_id}"
            state.models_warmed[key] = model_state

            # BC-008: Check if Heavy exceeds 5s, set fallback flag
            if combo.tier == "heavy" and not model_state.warmup_success:
                state.fallback_used = True
                logger.warning(
                    "Heavy model warmup failed for tenant %s, "
                    "fallback_used=True: %s",
                    company_id,
                    model_state.error_message,
                )

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        state.time_to_warm_ms = elapsed_ms
        state.completed_at = _utcnow()

        # Determine overall status
        any_success = any(
            ms.warmup_success for ms in state.models_warmed.values()
        )
        all_success = all(
            ms.warmup_success for ms in state.models_warmed.values()
        )

        if all_success:
            state.overall_status = WarmupStatus.warm
        elif any_success:
            state.overall_status = WarmupStatus.warm  # Partial warm is usable
            state.fallback_used = True
        else:
            state.overall_status = WarmupStatus.cooling
            state.fallback_used = True

        return state

    def prewarm_all_providers(self) -> dict:
        """
        Warm up ALL providers (system-wide, not tenant-specific).
        Call each provider's LIGHT model with a simple probe.
        P21 FIX: Rate-limited to prevent rapid repeated calls generating
        unnecessary API costs.
        """
        # P21: Cooldown guard
        now = time.monotonic()
        with self._prewarm_lock:
            if now - self._last_prewarm_time < _PREWARM_COOLDOWN_SECONDS:
                remaining = int(_PREWARM_COOLDOWN_SECONDS -
                                (now - self._last_prewarm_time))
                return {
                    "status": "cooldown",
                    "message": f"Prewarm on cooldown. Retry in {remaining}s.",
                    "cooldown_remaining_seconds": remaining,
                }
            self._last_prewarm_time = now

        light_combos = [c for c in PREWARM_COMBOS if c.tier == "light"]
        results: Dict[str, Any] = {}

        for combo in light_combos:
            try:
                state = self._warmup_single_model("system", combo)
                results[f"{combo.provider}/{combo.model_id}"] = {
                    "status": state.status.value,
                    "success": state.warmup_success,
                    "latency_ms": state.warmup_latency_ms,
                    "error": state.error_message,
                }
            except Exception as exc:
                # BC-008: Never crash
                logger.error(
                    "Provider prewarm failed for %s/%s: %s",
                    combo.provider,
                    combo.model_id,
                    exc,
                )
                results[f"{combo.provider}/{combo.model_id}"] = {
                    "status": "error",
                    "success": False,
                    "error": str(exc),
                }

        return results

    def check_model_readiness(
        self, provider: str, model_id: str
    ) -> ModelWarmupState:
        """Check if a specific model is warm across all tenants."""
        latest_state: Optional[ModelWarmupState] = None

        key = f"{provider}:{model_id}"
        for tenant_state in self._tenant_states.values():
            ms = tenant_state.models_warmed.get(key)
            if ms:
                if latest_state is None or (
                    ms.warmup_success and not latest_state.warmup_success
                ):
                    latest_state = ms

        if latest_state is not None:
            return latest_state

        # Model not found in any tenant — return cold state
        return ModelWarmupState(
            provider=provider,
            model_id=model_id,
            tier="unknown",
            status=WarmupStatus.cold,
        )

    def get_cold_fallback_model(
        self, company_id: str, variant_type: str
    ) -> dict:
        """
        Get the fastest available model as fallback (BC-008).
        Returns {provider, model_id, tier, reason}.
        Always returns something — never fails.
        """
        # Hardcoded fallback chain: light → medium → heavy
        fallback_chain = [
            ("cerebras", "llama-3.1-8b", "light"),
            ("groq", "llama-3.1-8b", "light"),
            ("google", "gemma-3-27b-it", "light"),
            ("google", "gemini-2.0-flash-lite", "medium"),
            ("groq", "llama-3.3-70b-versatile", "medium"),
            ("groq", "qwen3-32b", "medium"),
            ("groq", "gpt-oss-120b", "heavy"),
            ("cerebras", "gpt-oss-120b", "heavy"),
        ]

        # If tenant has warmup state, find the best warm model
        if company_id:
            tenant_state = self._tenant_states.get(company_id)
            if tenant_state:
                # Prefer light models that succeeded
                for provider, model_id, tier in fallback_chain:
                    ms_key = f"{provider}:{model_id}"
                    ms = tenant_state.models_warmed.get(ms_key)
                    if ms and ms.warmup_success:
                        return {
                            "provider": provider,
                            "model_id": model_id,
                            "tier": tier,
                            "reason": "warm_model_available",
                        }

        # No warm model found — return fastest light model as fallback
        return {
            "provider": "cerebras",
            "model_id": "llama-3.1-8b",
            "tier": "light",
            "reason": "cold_fallback_to_lightest",
        }

    def invalidate_warmup(self, company_id: str) -> None:
        """Reset tenant warmup state (e.g., after config change)."""
        if company_id and company_id in self._tenant_states:
            del self._tenant_states[company_id]
            self._last_accessed.pop(company_id, None)
            logger.info("Warmup state invalidated for tenant %s", company_id)

    # P7: Recovery — find tenants marked completed but without warmup state.
    # Call this on startup to re-warm active tenants after deploy/restart.
    def recover_tenant_warmup(
            self,
            company_id: str,
            variant_type: str) -> Optional[TenantWarmupState]:
        """
        Re-trigger warmup for a tenant that should be warm but isn't
        (e.g., after server restart). Call from startup recovery.
        """
        if company_id in self._tenant_states:
            return self._tenant_states[company_id]
        return self.warmup_tenant(company_id, variant_type)

    def get_all_tenant_statuses(self) -> dict:
        """Overview of all tenant warmup states for monitoring."""
        result: Dict[str, Any] = {}
        for cid, state in self._tenant_states.items():
            result[cid] = {
                "variant_type": state.variant_type,
                "overall_status": state.overall_status.value,
                "models_count": len(
                    state.models_warmed),
                "models_ready": sum(
                    1 for ms in state.models_warmed.values() if ms.warmup_success),
                "time_to_warm_ms": state.time_to_warm_ms,
                "fallback_used": state.fallback_used,
                "started_at": state.started_at,
                "completed_at": state.completed_at,
            }
        return result

    # ── Private Methods ──────────────────────────────────────────────

    def _warmup_single_model(
        self, company_id: str, combo: PREWARM_COMBO,
        timeout_ms: Optional[int] = None,
    ) -> ModelWarmupState:
        """
        Send a probe query to a model, measure latency, record result.
        """
        model_state = ModelWarmupState(
            provider=combo.provider,
            model_id=combo.model_id,
            tier=combo.tier,
            probe_query=combo.probe_query,
        )

        start_time = time.monotonic()

        try:
            effective_timeout = timeout_ms or combo.max_acceptable_latency_ms
            result = self._probe_llm_api(
                provider=combo.provider,
                model_id=combo.model_id,
                query=combo.probe_query,
                timeout_ms=effective_timeout,
            )

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            model_state.warmup_latency_ms = elapsed_ms
            model_state.last_warmed_at = _utcnow()

            if result.get("success"):
                model_state.status = WarmupStatus.warm
                model_state.warmup_success = True
                model_state.probe_response = result.get("response", "")
            else:
                model_state.status = WarmupStatus.cooling
                model_state.warmup_success = False
                model_state.error_message = result.get(
                    "error", "Unknown error")

        except Exception as exc:
            # BC-008: Never crash
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            model_state.warmup_latency_ms = elapsed_ms
            model_state.status = WarmupStatus.cooling
            model_state.warmup_success = False
            model_state.error_message = f"Warmup exception: {exc}"
            logger.error(
                "Model warmup failed for %s/%s (tenant %s): %s",
                combo.provider,
                combo.model_id,
                company_id,
                exc,
            )

        return model_state

    # P19 FIX: Renamed from _simulate_llm_call to _probe_llm_api.
    # The old name was misleading — it suggested a mock/simulation but
    # actually makes REAL HTTP requests to production LLM APIs.
    # Future developers would see "simulate" and try to mock it,
    # thinking it's already fake.
    def _probe_llm_api(
        self,
        provider: str,
        model_id: str,
        query: str,
        timeout_ms: int,
    ) -> dict:
        """
        Probe a real LLM API endpoint with a test query to warm the model.
        Uses urllib.request with timeout.
        In tests, mock this method.

        Returns dict with keys: success (bool), response (str), error (str).
        """
        from app.config import get_settings
        try:
            settings = get_settings()
        except Exception:
            # If settings unavailable (e.g., during testing), use empty keys
            settings = None

        provider_urls = {
            "cerebras": "https://api.cerebras.ai/v1/chat/completions",
            "groq": "https://api.groq.com/openai/v1/chat/completions",
            "google": (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model_id}:generateContent"
            ),
        }

        url = provider_urls.get(provider)
        if not url:
            return {
                "success": False,
                "error": f"Unknown provider: {provider}",
            }

        timeout_sec = max(timeout_ms / 1000, 1.0)

        # Build headers with API keys
        headers = {"Content-Type": "application/json"}
        if provider == "cerebras" and settings:
            api_key = getattr(settings, "CEREBRAS_API_KEY", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
        elif provider == "groq" and settings:
            api_key = getattr(settings, "GROQ_API_KEY", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
        # P9 FIX: Use x-goog-api-key header instead of URL query parameter.
        # API keys in URLs appear in server logs, proxy logs, error messages,
        # and exception stack traces — a security audit failure.
        elif provider == "google" and settings:
            api_key = getattr(settings, "GOOGLE_AI_API_KEY", "")
            if api_key:
                headers["x-goog-api-key"] = api_key

        if provider == "google":
            payload = json.dumps({
                "contents": [{"parts": [{"text": query}]}],
            }).encode("utf-8")
        else:
            payload = json.dumps({
                "model": model_id,
                "messages": [{"role": "user", "content": query}],
                "max_tokens": 10,
            }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers=headers,
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                # Extract text from various provider response formats
                if provider == "google":
                    text = (
                        body.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                    )
                else:
                    text = (
                        body.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                return {"success": True, "response": text[:200]}

        except urllib.error.HTTPError as exc:
            return {
                "success": False,
                "error": f"HTTP {exc.code}: {exc.reason}",
            }
        except urllib.error.URLError as exc:
            return {
                "success": False,
                "error": f"URL error: {exc.reason}",
            }
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
            }


# ── Module-level singleton ───────────────────────────────────────────

_cold_start_service: Optional[ColdStartService] = None


def get_cold_start_service() -> ColdStartService:
    """Get or create the ColdStartService singleton."""
    global _cold_start_service
    if _cold_start_service is None:
        _cold_start_service = ColdStartService()
    return _cold_start_service
