"""
Smart Router (F-054): MAKER-Aware 3-Tier LLM Routing via Free Providers.

Selects which AI MODEL to use per atomic step (not per query).
Aware of MAKER framework: one query = 6-24 LLM calls.
Intelligently assigns tiers: technique-boosted calls use LIGHT,
only raw reasoning needs MEDIUM/HEAVY.

Providers: Google AI Studio, Cerebras, Groq (all free tiers).
Variant access: All variants get ALL model tiers; only restrictions differ.
User-validated: llama-3.1-8b (LIGHT) works best for ALL tasks.
Guardrail checks use gpt-oss-120b.

BC-007: All AI model interaction MUST go through Smart Router.
BC-001: company_id is always second parameter.
BC-008: Graceful degradation -- always has a fallback.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("parwa.smart_router")

# LiteLLM — unified LLM API (BC-007)
try:
    import litellm
    _HAS_LITELLM = True
except ImportError:
    _HAS_LITELLM = False
    litellm = None  # type: ignore[assignment]

# ── Ensure GEMINI_API_KEY is set for LiteLLM ──
# LiteLLM requires GEMINI_API_KEY for gemini/ prefix models.
# Render provides GOOGLE_AI_API_KEY; copy it so LiteLLM can find it.
if not os.environ.get("GEMINI_API_KEY") and os.environ.get("GOOGLE_AI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_AI_API_KEY"]


# ── Enums ──────────────────────────────────────────────────────────


class ModelProvider(str, Enum):
    """Supported LLM providers (all free tiers)."""
    GOOGLE = "google"
    CEREBRAS = "cerebras"
    GROQ = "groq"
    NVIDIA = "nvidia"
    AI21 = "ai21"


class ModelTier(str, Enum):
    """Model complexity tiers matching PARWA pricing."""
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"
    GUARDRAIL = "guardrail"
    BUILDER = "builder"


class AtomicStepType(str, Enum):
    """All MAKER framework atomic step types."""
    INTENT_CLASSIFICATION = "intent_classification"
    PII_REDACTION = "pii_redaction"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    CLARA_QUALITY_GATE = "clara_quality_gate"
    CRP_TOKEN_TRIM = "crp_token_trim"
    GSD_STATE_STEP = "gsd_state_step"
    MAD_DECOMPOSE = "mad_decompose"
    MAD_ATOM_SIMPLE = "mad_atom_simple"
    MAD_ATOM_REASONING = "mad_atom_reasoning"
    COT_REASONING = "cot_reasoning"
    FAKE_VOTING = "fake_voting"
    CONSENSUS_ANALYSIS = "consensus_analysis"
    DRAFT_RESPONSE_SIMPLE = "draft_response_simple"
    DRAFT_RESPONSE_MODERATE = "draft_response_moderate"
    DRAFT_RESPONSE_COMPLEX = "draft_response_complex"
    REFLEXION_CYCLE = "reflexion_cycle"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    GUARDRAIL_CHECK = "guardrail_check"


# ── Model Configuration ────────────────────────────────────────────


@dataclass
class ModelConfig:
    """Full configuration for a single model in the registry."""
    provider: ModelProvider
    model_id: str
    display_name: str
    tier: ModelTier
    priority: int  # 1 = primary within tier
    max_requests_per_day: int
    max_tokens_per_minute: int
    context_window: int
    api_endpoint_base: str
    is_openai_compatible: bool
    max_requests_per_minute: int = 0  # 0 = no per-minute limit
    recommended_for: List[AtomicStepType] = field(default_factory=list)


# ── Model Registry ─────────────────────────────────────────────────

MODEL_REGISTRY: Dict[str, ModelConfig] = {
    # ═══════════════════════════════════════════════════════════════════
    # LIGHT TIER — 90% of traffic
    # ═══════════════════════════════════════════════════════════════════

    # LIGHT priority order: Cerebras first (fastest inference), then Groq models, then AI21 last.
    "cerebras-llama3.1-8b": ModelConfig(
        provider=ModelProvider.CEREBRAS, model_id="llama3.1-8b",
        display_name="Llama 3.1 8B (Cerebras)", tier=ModelTier.LIGHT, priority=1,
        max_requests_per_day=14400, max_tokens_per_minute=60000, context_window=8192,
        api_endpoint_base="https://api.cerebras.ai/v1/chat/completions", is_openai_compatible=True,
    ),
    "groq-llama-3.1-8b-instant": ModelConfig(
        provider=ModelProvider.GROQ, model_id="llama-3.1-8b-instant",
        display_name="Llama 3.1 8B Instant (Groq)", tier=ModelTier.LIGHT, priority=2,
        max_requests_per_day=14400, max_tokens_per_minute=6000, context_window=8192,
        api_endpoint_base="https://api.groq.com/openai/v1/chat/completions", is_openai_compatible=True,
    ),
    "groq-llama-3.3-70b": ModelConfig(
        provider=ModelProvider.GROQ, model_id="llama-3.3-70b-versatile",
        display_name="Llama 3.3 70B (Groq)", tier=ModelTier.LIGHT, priority=3,
        max_requests_per_day=1000, max_tokens_per_minute=12000, context_window=32768,
        api_endpoint_base="https://api.groq.com/openai/v1/chat/completions", is_openai_compatible=True,
    ),
    "groq-llama-4-scout": ModelConfig(
        provider=ModelProvider.GROQ, model_id="meta-llama/llama-4-scout-17b-16e-instruct",
        display_name="Llama 4 Scout (Groq)", tier=ModelTier.LIGHT, priority=4,
        max_requests_per_day=1000, max_tokens_per_minute=30000, context_window=65536,
        api_endpoint_base="https://api.groq.com/openai/v1/chat/completions", is_openai_compatible=True,
    ),
    "groq-qwen3-32b": ModelConfig(
        provider=ModelProvider.GROQ, model_id="qwen/qwen3-32b",
        display_name="Qwen3 32B (Groq)", tier=ModelTier.LIGHT, priority=5,
        max_requests_per_day=1000, max_tokens_per_minute=6000, context_window=32768,
        api_endpoint_base="https://api.groq.com/openai/v1/chat/completions", is_openai_compatible=True,
    ),
    "groq-qwen3.6-27b": ModelConfig(
        provider=ModelProvider.GROQ, model_id="qwen/qwen3.6-27b",
        display_name="Qwen3.6 27B (Groq)", tier=ModelTier.LIGHT, priority=6,
        max_requests_per_day=1000, max_tokens_per_minute=8000, context_window=32768,
        api_endpoint_base="https://api.groq.com/openai/v1/chat/completions", is_openai_compatible=True,
    ),
    "groq-allam-2-7b": ModelConfig(
        provider=ModelProvider.GROQ, model_id="allam-2-7b",
        display_name="Allam 2 7B (Groq)", tier=ModelTier.LIGHT, priority=7,
        max_requests_per_day=7000, max_tokens_per_minute=6000, context_window=8192,
        api_endpoint_base="https://api.groq.com/openai/v1/chat/completions", is_openai_compatible=True,
    ),
    "groq-gpt-oss-120b-light": ModelConfig(
        provider=ModelProvider.GROQ, model_id="openai/gpt-oss-120b",
        display_name="GPT-OSS 120B (Groq)", tier=ModelTier.LIGHT, priority=8,
        max_requests_per_day=1000, max_tokens_per_minute=8000, context_window=65536,
        api_endpoint_base="https://api.groq.com/openai/v1/chat/completions", is_openai_compatible=True,
    ),
    "groq-gpt-oss-20b-light": ModelConfig(
        provider=ModelProvider.GROQ, model_id="openai/gpt-oss-20b",
        display_name="GPT-OSS 20B (Groq)", tier=ModelTier.LIGHT, priority=9,
        max_requests_per_day=1000, max_tokens_per_minute=8000, context_window=65536,
        api_endpoint_base="https://api.groq.com/openai/v1/chat/completions", is_openai_compatible=True,
    ),
    "groq-gpt-oss-safeguard-light": ModelConfig(
        provider=ModelProvider.GROQ, model_id="openai/gpt-oss-safeguard-20b",
        display_name="GPT-OSS Safeguard 20B (Groq)", tier=ModelTier.LIGHT, priority=10,
        max_requests_per_day=1000, max_tokens_per_minute=8000, context_window=65536,
        api_endpoint_base="https://api.groq.com/openai/v1/chat/completions", is_openai_compatible=True,
    ),
    "ai21-jamba-mini": ModelConfig(
        provider=ModelProvider.AI21, model_id="jamba-2.0-mini",
        display_name="Jamba Mini 2 (AI21)", tier=ModelTier.LIGHT, priority=11,
        max_requests_per_day=999999, max_tokens_per_minute=999999, context_window=256000,
        api_endpoint_base="https://api.ai21.com/studio/v1/chat/completions", is_openai_compatible=True,
    ),
    "ai21-jamba-large": ModelConfig(
        provider=ModelProvider.AI21, model_id="jamba-1.7-large",
        display_name="Jamba Large 1.7 (AI21)", tier=ModelTier.LIGHT, priority=12,
        max_requests_per_day=999999, max_tokens_per_minute=999999, context_window=256000,
        api_endpoint_base="https://api.ai21.com/studio/v1/chat/completions", is_openai_compatible=True,
    ),

    # ═══════════════════════════════════════════════════════════════════
    # MEDIUM TIER — 8% of traffic
    # ═══════════════════════════════════════════════════════════════════

    # MEDIUM priority: Cerebras first (fastest), then Google, then NVIDIA last.
    "cerebras-gpt-oss-120b-medium": ModelConfig(
        provider=ModelProvider.CEREBRAS, model_id="gpt-oss-120b",
        display_name="GPT-OSS 120B (Cerebras)", tier=ModelTier.MEDIUM, priority=1,
        max_requests_per_day=14400, max_tokens_per_minute=60000, context_window=65536,
        api_endpoint_base="https://api.cerebras.ai/v1/chat/completions", is_openai_compatible=True,
    ),
    "google-gemini-3.5-flash": ModelConfig(
        provider=ModelProvider.GOOGLE, model_id="gemini-3.5-flash",
        display_name="Gemini 3.5 Flash (Google)", tier=ModelTier.MEDIUM, priority=2,
        max_requests_per_day=20, max_tokens_per_minute=999999, context_window=1048576,
        api_endpoint_base="https://generativelanguage.googleapis.com/v1beta/models", is_openai_compatible=False,
    ),
    "nvidia-glm-5.2-medium": ModelConfig(
        provider=ModelProvider.NVIDIA, model_id="z-ai/glm-5.2",
        display_name="GLM 5.2 (NVIDIA)", tier=ModelTier.MEDIUM, priority=3,
        max_requests_per_day=999999, max_tokens_per_minute=999999, context_window=1048576,
        api_endpoint_base="https://integrate.api.nvidia.com/v1/chat/completions", is_openai_compatible=True,
    ),

    # ═══════════════════════════════════════════════════════════════════
    # HEAVY TIER — 2% of traffic
    # ═══════════════════════════════════════════════════════════════════

    # HEAVY priority: Google first (best reasoning), then Cerebras, then NVIDIA last.
    "google-gemini-2.5-flash": ModelConfig(
        provider=ModelProvider.GOOGLE, model_id="gemini-2.5-flash",
        display_name="Gemini 2.5 Flash (Google)", tier=ModelTier.HEAVY, priority=1,
        max_requests_per_day=20, max_tokens_per_minute=999999, context_window=1048576,
        api_endpoint_base="https://generativelanguage.googleapis.com/v1beta/models", is_openai_compatible=False,
    ),
    "cerebras-gpt-oss-120b-heavy": ModelConfig(
        provider=ModelProvider.CEREBRAS, model_id="gpt-oss-120b",
        display_name="GPT-OSS 120B (Cerebras)", tier=ModelTier.HEAVY, priority=2,
        max_requests_per_day=14400, max_tokens_per_minute=60000, context_window=65536,
        api_endpoint_base="https://api.cerebras.ai/v1/chat/completions", is_openai_compatible=True,
    ),
    "nvidia-glm-5.2-heavy": ModelConfig(
        provider=ModelProvider.NVIDIA, model_id="z-ai/glm-5.2",
        display_name="GLM 5.2 (NVIDIA)", tier=ModelTier.HEAVY, priority=3,
        max_requests_per_day=999999, max_tokens_per_minute=999999, context_window=1048576,
        api_endpoint_base="https://integrate.api.nvidia.com/v1/chat/completions", is_openai_compatible=True,
    ),

    # ═══════════════════════════════════════════════════════════════════
    # BUILDER TIER — agent creation only (NVIDIA dedicated)
    # ═══════════════════════════════════════════════════════════════════

    "nvidia-glm-5.2-builder": ModelConfig(
        provider=ModelProvider.NVIDIA, model_id="z-ai/glm-5.2",
        display_name="GLM 5.2 (NVIDIA) — Builder", tier=ModelTier.BUILDER, priority=1,
        max_requests_per_day=999999, max_tokens_per_minute=999999, context_window=1048576,
        api_endpoint_base="https://integrate.api.nvidia.com/v1/chat/completions", is_openai_compatible=True,
    ),

    # ═══════════════════════════════════════════════════════════════════
    # GUARDRAIL TIER
    # ═══════════════════════════════════════════════════════════════════

    "groq-gpt-oss-safeguard-guardrail": ModelConfig(
        provider=ModelProvider.GROQ, model_id="openai/gpt-oss-safeguard-20b",
        display_name="GPT-OSS Safeguard 20B (Groq)", tier=ModelTier.GUARDRAIL, priority=1,
        max_requests_per_day=1000, max_tokens_per_minute=8000, context_window=65536,
        api_endpoint_base="https://api.groq.com/openai/v1/chat/completions", is_openai_compatible=True,
        recommended_for=[AtomicStepType.GUARDRAIL_CHECK],
    ),
}

# ── Variant Model Access (SG-03) ──────────────────────────────────

VARIANT_MODEL_ACCESS: Dict[str, Set[ModelTier]] = {
    # All variants get ALL model tiers including BUILDER.
    "mini_parwa": {ModelTier.LIGHT, ModelTier.MEDIUM, ModelTier.HEAVY, ModelTier.GUARDRAIL},
    "parwa": {ModelTier.LIGHT, ModelTier.MEDIUM, ModelTier.HEAVY, ModelTier.GUARDRAIL, ModelTier.BUILDER},
    "parwa_high": {ModelTier.LIGHT, ModelTier.MEDIUM, ModelTier.HEAVY, ModelTier.GUARDRAIL, ModelTier.BUILDER},
}

# ── Step -> Tier Mapping ──────────────────────────────────────────

STEP_TIER_MAPPING: Dict[AtomicStepType, ModelTier] = {
    # LIGHT: 15 calls per normal ticket (Node 1, 3, 4 simple, 5, 6 quality, 7)
    AtomicStepType.INTENT_CLASSIFICATION: ModelTier.LIGHT,
    AtomicStepType.PII_REDACTION: ModelTier.LIGHT,
    AtomicStepType.SENTIMENT_ANALYSIS: ModelTier.LIGHT,
    AtomicStepType.CLARA_QUALITY_GATE: ModelTier.LIGHT,
    AtomicStepType.CRP_TOKEN_TRIM: ModelTier.LIGHT,
    AtomicStepType.GSD_STATE_STEP: ModelTier.LIGHT,
    AtomicStepType.MAD_DECOMPOSE: ModelTier.LIGHT,
    AtomicStepType.MAD_ATOM_SIMPLE: ModelTier.LIGHT,
    AtomicStepType.COT_REASONING: ModelTier.LIGHT,
    AtomicStepType.FAKE_VOTING: ModelTier.LIGHT,
    AtomicStepType.CONSENSUS_ANALYSIS: ModelTier.LIGHT,
    AtomicStepType.DRAFT_RESPONSE_SIMPLE: ModelTier.LIGHT,
    AtomicStepType.DRAFT_RESPONSE_MODERATE: ModelTier.LIGHT,
    AtomicStepType.ESCALATE_TO_HUMAN: ModelTier.LIGHT,
    # MEDIUM: 3 calls per ticket (Node 4 complex, Node 4.5 CoVe, Node 6 format)
    AtomicStepType.MAD_ATOM_REASONING: ModelTier.MEDIUM,
    AtomicStepType.DRAFT_RESPONSE_COMPLEX: ModelTier.MEDIUM,
    AtomicStepType.REFLEXION_CYCLE: ModelTier.MEDIUM,
    # GUARDRAIL: safety checks
    AtomicStepType.GUARDRAIL_CHECK: ModelTier.GUARDRAIL,
}

# Tier fallback order: if a tier is unavailable, try next lower tier
TIER_FALLBACK_ORDER: List[ModelTier] = [
    ModelTier.BUILDER,
    ModelTier.HEAVY,
    ModelTier.MEDIUM,
    ModelTier.LIGHT,
]

# ── Per-Provider RPM Limits (sliding 60s window) ───────────────────
# RPM is tracked PER PROVIDER (shared across all of that provider's models).
# When count == limit, we WAIT for the oldest timestamp to fall out of the
# 60s window — we do NOT switch providers for RPM. Provider switching only
# happens for: API errors, daily limits, broken APIs.
PROVIDER_RPM_LIMITS: Dict[ModelProvider, int] = {
    ModelProvider.CEREBRAS: 1000,  # token-based, effectively unlimited
    ModelProvider.GROQ: 30,        # 30 RPM shared across ALL Groq models
    ModelProvider.NVIDIA: 30,      # 30 RPM (safe; actual is 40)
    ModelProvider.GOOGLE: 20,
    ModelProvider.AI21: 200,       # credit-based, $10 free tier
}

# ── Provider Usage Tracking ────────────────────────────────────────


@dataclass
class ProviderUsage:
    """Tracks usage and health for a single provider+model combination."""
    provider: ModelProvider
    model_id: str
    daily_count: int = 0
    daily_limit: int = 14400
    # RPM tracking (requests per minute — the real bottleneck)
    rpm_count: int = 0
    rpm_limit: int = 30
    rpm_window_start: float = 0.0
    # Legacy token tracking (kept for compatibility)
    minute_count: int = 0
    minute_limit: int = 30000
    minute_window_start: float = 0.0
    rate_limited_until: float = 0.0
    consecutive_failures: int = 0
    last_error: str = ""
    is_healthy: bool = True
    marked_unhealthy_at: float = 0.0

    @property
    def registry_key(self) -> str:
        return f"{self.model_id}-{self.provider.value}"

    def get_rpm_available(self) -> int:
        """How many more requests can we make this minute?"""
        import time as _t
        now = _t.time()
        # Reset window every 60 seconds
        if now - self.rpm_window_start > 60:
            self.rpm_window_start = now
            self.rpm_count = 0
            # Auto-recover from unhealthy state when window resets
            if not self.is_healthy:
                self.is_healthy = True
                self.consecutive_failures = 0
        return max(0, self.rpm_limit - self.rpm_count)


class ProviderHealthTracker:
    """Tracks health and rate limits for all provider+model combinations.

    BC-008: Never crashes. Tracks failures, rate limits, and provides
    availability checks for the Smart Router's fallback logic.
    Uses class-level shared state so all SmartRouter instances across
    workers see the same health data.
    """

    CONSECUTIVE_FAILURE_THRESHOLD = 3
    RATE_LIMIT_COOLDOWN_SECONDS = 60
    RATE_LIMIT_RETRY_AFTER_DEFAULT = 60  # seconds when 429 has no Retry-After

    # Class-level shared state — all instances share the same tracker
    _shared_usage: Dict[str, ProviderUsage] = {}
    _shared_last_daily_reset: str = ""
    # Per-provider RPM sliding window: provider -> deque of call timestamps
    # Shared across ALL models of that provider (e.g. all Groq models share
    # the same 30 RPM budget). Tracked at the PROVIDER level, not per-model.
    _shared_provider_rpm: Dict[ModelProvider, Deque[float]] = {}
    _shared_provider_rpm_locks: Dict[ModelProvider, threading.Lock] = {}

    def __init__(self) -> None:
        # Use class-level shared state for multi-worker consistency
        self._usage = ProviderHealthTracker._shared_usage
        self._last_daily_reset = ProviderHealthTracker._shared_last_daily_reset
        self._provider_rpm = ProviderHealthTracker._shared_provider_rpm
        self._provider_rpm_locks = ProviderHealthTracker._shared_provider_rpm_locks
        self._reset_daily_if_needed()

    def _reset_daily_if_needed(self) -> None:
        """Reset daily counters at midnight UTC (BC-012)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._last_daily_reset:
            logger.info(
                "Daily usage reset triggered for %s (was %s)",
                today, self._last_daily_reset,
            )
            self._last_daily_reset = today
            ProviderHealthTracker._shared_last_daily_reset = today
            for usage in self._usage.values():
                usage.daily_count = 0

    def _ensure_usage(self, registry_key: str, config: ModelConfig) -> ProviderUsage:
        """Get or create ProviderUsage for a registry key."""
        if registry_key not in self._usage:
            # Set RPM limit based on provider (free tier limits)
            _RPM_LIMITS = {
                ModelProvider.GROQ: 28,       # 30 RPM, use 28 for safety
                ModelProvider.CEREBRAS: 28,   # 30 RPM, use 28 for safety
                ModelProvider.GOOGLE: 14,     # 15 RPM, use 14 for safety
                ModelProvider.NVIDIA: 38,     # 40 RPM shared, use 38 for safety
                ModelProvider.AI21: 190,      # 200 RPM, use 190 for safety
            }
            rpm_limit = _RPM_LIMITS.get(config.provider, 25)  # default 25 for unknown
            self._usage[registry_key] = ProviderUsage(
                provider=config.provider,
                model_id=config.model_id,
                daily_limit=config.max_requests_per_day,
                rpm_limit=rpm_limit,
                minute_limit=config.max_tokens_per_minute,
            )
        return self._usage[registry_key]

    def record_success(
        self,
        provider: ModelProvider,
        model_id: str,
        tokens_used: int = 0,
    ) -> None:
        """Record a successful API call. Resets consecutive failure count."""
        registry_key = f"{model_id}-{provider.value}"
        # Find the config to get limits
        config = None
        for k, c in MODEL_REGISTRY.items():
            if k == registry_key:
                config = c
                break

        usage = self._ensure_usage(
            registry_key,
            config or ModelConfig(
                provider=provider,
                model_id=model_id,
                display_name=model_id,
                tier=ModelTier.LIGHT,
                priority=99,
                max_requests_per_day=14400,
                max_tokens_per_minute=30000,
                context_window=8192,
                api_endpoint_base="",
                is_openai_compatible=True,
            ),
        )

        self._reset_daily_if_needed()
        usage.consecutive_failures = 0
        usage.last_error = ""
        usage.is_healthy = True
        usage.daily_count += 1

        # RPM tracking — increment request count per minute
        now = time.time()
        if now - usage.rpm_window_start > 60:
            usage.rpm_window_start = now
            usage.rpm_count = 1
        else:
            usage.rpm_count += 1

        # Legacy token tracking (kept for compatibility)
        if now - usage.minute_window_start > 60:
            usage.minute_window_start = now
            usage.minute_count = tokens_used
        else:
            usage.minute_count += tokens_used

        logger.debug(
            "Recorded success for %s (daily=%d, rpm=%d/%d, minute_tokens=%d)",
            registry_key, usage.daily_count, usage.rpm_count, usage.rpm_limit, usage.minute_count,
        )

    def record_rate_limit(
        self,
        provider: ModelProvider,
        model_id: str,
        retry_after_seconds: int = 0,
    ) -> None:
        """Record a 429 rate limit response. Sets cooldown timer.

        Respects Retry-After header if provided by the API.
        """
        registry_key = f"{model_id}-{provider.value}"
        config = None
        for k, c in MODEL_REGISTRY.items():
            if k == registry_key:
                config = c
                break

        usage = self._ensure_usage(
            registry_key,
            config or ModelConfig(
                provider=provider, model_id=model_id,
                display_name=model_id, tier=ModelTier.LIGHT,
                priority=99, max_requests_per_day=14400,
                max_tokens_per_minute=30000, context_window=8192,
                api_endpoint_base="", is_openai_compatible=True,
            ),
        )

        cooldown = max(
            retry_after_seconds if retry_after_seconds > 0 else self.RATE_LIMIT_RETRY_AFTER_DEFAULT,
            self.RATE_LIMIT_COOLDOWN_SECONDS,
        )
        usage.rate_limited_until = time.time() + cooldown
        usage.last_error = f"rate_limited_for_{cooldown}s"
        # Mark as temporarily unhealthy — will auto-recover when RPM window resets
        usage.is_healthy = False
        usage.marked_unhealthy_at = time.time()
        # Cap RPM count at limit so other providers get used
        usage.rpm_count = usage.rpm_limit
        logger.warning(
            "Rate limited: %s for %d seconds (retry_after=%d) — marked unhealthy, will auto-recover in 60s",
            registry_key, cooldown, retry_after_seconds,
        )

    def record_failure(
        self,
        provider: ModelProvider,
        model_id: str,
        error_msg: str = "Unknown error",
    ) -> None:
        """Record a failed API call. Marks unhealthy after threshold."""
        registry_key = f"{model_id}-{provider.value}"
        config = None
        for k, c in MODEL_REGISTRY.items():
            if k == registry_key:
                config = c
                break

        usage = self._ensure_usage(
            registry_key,
            config or ModelConfig(
                provider=provider,
                model_id=model_id,
                display_name=model_id,
                tier=ModelTier.LIGHT,
                priority=99,
                max_requests_per_day=14400,
                max_tokens_per_minute=30000,
                context_window=8192,
                api_endpoint_base="",
                is_openai_compatible=True,
            ),
        )

        usage.consecutive_failures += 1
        usage.last_error = error_msg

        if usage.consecutive_failures >= self.CONSECUTIVE_FAILURE_THRESHOLD:
            usage.is_healthy = False
            usage.marked_unhealthy_at = time.time()
            logger.warning(
                "Provider %s marked UNHEALTHY after %d consecutive failures: %s "
                "(will auto-recover in 60s when RPM window resets)",
                registry_key, usage.consecutive_failures, error_msg,
            )
        else:
            logger.debug(
                "Recorded failure for %s (consecutive=%d): %s",
                registry_key, usage.consecutive_failures, error_msg,
            )

    def is_available(self, provider: ModelProvider, model_id: str) -> bool:
        """Check if a provider+model is usable (healthy + under daily limits).

        NOTE: RPM is NOT checked here. RPM is enforced separately via
        ``acquire_provider_slot()`` which WAITS when the provider is at its
        RPM limit — it does not switch providers. Provider switching only
        happens for: API errors, daily limits, broken APIs.

        This checks:
        1. Rate limit cooldown: are we in a 429 penalty box?
        2. Health: is the provider marked unhealthy? (auto-recovers in 60s)
        3. Daily limit: have we hit the daily cap?
        """
        registry_key = f"{model_id}-{provider.value}"
        if registry_key not in self._usage:
            return True  # No usage data = assume available

        usage = self._usage[registry_key]
        self._reset_daily_if_needed()

        # Check rate limit cooldown (429 penalty)
        if usage.rate_limited_until > time.time():
            return False

        # Auto-recover health flag when RPM window resets
        # (calls get_rpm_available which resets the window)
        usage.get_rpm_available()

        # If still unhealthy after window reset, provider is genuinely down
        if not usage.is_healthy:
            return False

        # Check daily limit
        if usage.daily_count >= usage.daily_limit:
            logger.debug(
                "%s: daily limit reached (%d/%d)",
                registry_key, usage.daily_count, usage.daily_limit,
            )
            return False

        return True

    # ── Per-Provider RPM Sliding Window ──────────────────────────
    #
    # RPM is tracked PER PROVIDER (shared across all of that provider's
    # models). When count == limit, we WAIT for the oldest timestamp to
    # fall out of the 60s window — we do NOT switch providers for RPM.
    #
    # User rule: "Only wait when literally at 0 — no preemptive waiting".
    # So if even 1 slot is left, we take it immediately without waiting.

    def _get_provider_lock(self, provider: ModelProvider) -> threading.Lock:
        """Get or create the per-provider lock for RPM slot acquisition."""
        if provider not in self._provider_rpm_locks:
            self._provider_rpm_locks[provider] = threading.Lock()
        return self._provider_rpm_locks[provider]

    def _get_provider_timestamps(self, provider: ModelProvider) -> Deque[float]:
        """Get or create the per-provider timestamp deque."""
        if provider not in self._provider_rpm:
            self._provider_rpm[provider] = deque()
        return self._provider_rpm[provider]

    @staticmethod
    def _prune_provider_timestamps(timestamps: Deque[float]) -> None:
        """Remove timestamps older than 60s from the front of the deque."""
        now = time.time()
        while timestamps and timestamps[0] <= now - 60:
            timestamps.popleft()

    def acquire_provider_slot(
        self,
        provider: ModelProvider,
        max_wait_seconds: float = 65.0,
    ) -> bool:
        """Atomically wait for and acquire an RPM slot for a provider.

        Behavior (per user spec):
        - If under limit (even by 1) → acquire immediately, no waiting.
        - If at limit (0 remaining) → calculate wait = 60 - (now - oldest),
          sleep, then retry SAME provider. Does NOT switch providers.
        - Returns True if slot acquired, False if max_wait_seconds exceeded.

        This is a BLOCKING call. Safe to use from sync code and from async
        code running in a worker thread (each pipeline runs in its own thread
        with its own event loop, so blocking is acceptable).
        """
        limit = PROVIDER_RPM_LIMITS.get(provider, 30)
        lock = self._get_provider_lock(provider)

        with lock:
            timestamps = self._get_provider_timestamps(provider)
            self._prune_provider_timestamps(timestamps)

            if len(timestamps) < limit:
                # Slot available — take it immediately
                timestamps.append(time.time())
                return True

            # At limit — calculate wait time for oldest timestamp to expire
            oldest = timestamps[0]
            wait_seconds = 60 - (time.time() - oldest)

            if wait_seconds <= 0:
                # Edge case: oldest already expired between prune and now
                self._prune_provider_timestamps(timestamps)
                if len(timestamps) < limit:
                    timestamps.append(time.time())
                    return True
                wait_seconds = 1.0  # fallback

            if wait_seconds > max_wait_seconds:
                logger.warning(
                    "Provider %s RPM wait %.1fs exceeds max_wait %.1fs — skipping slot acquire",
                    provider.value, wait_seconds, max_wait_seconds,
                )
                return False

            logger.info(
                "Provider %s at RPM limit (%d/%d) — waiting %.1fs for slot",
                provider.value, len(timestamps), limit, wait_seconds,
            )
            time.sleep(wait_seconds + 0.1)  # small buffer for safety

            # Re-prune and acquire
            self._prune_provider_timestamps(timestamps)
            if len(timestamps) < limit:
                timestamps.append(time.time())
                return True

            # Still at limit after wait (very high contention) — bail out
            logger.warning(
                "Provider %s still at RPM limit after waiting %.1fs",
                provider.value, wait_seconds,
            )
            return False

    def get_provider_rpm_status(self) -> Dict[str, Dict[str, Any]]:
        """Return per-provider RPM status for monitoring/debugging."""
        status: Dict[str, Dict[str, Any]] = {}
        for provider in ModelProvider:
            timestamps = self._provider_rpm.get(provider, deque())
            self._prune_provider_timestamps(timestamps)
            limit = PROVIDER_RPM_LIMITS.get(provider, 30)
            status[provider.value] = {
                "rpm_used": len(timestamps),
                "rpm_limit": limit,
                "rpm_available": max(0, limit - len(timestamps)),
            }
        return status

    def get_daily_usage(self, provider: ModelProvider, model_id: str) -> int:
        """Get today's usage count for a provider+model."""
        registry_key = f"{model_id}-{provider.value}"
        self._reset_daily_if_needed()
        if registry_key not in self._usage:
            return 0
        return self._usage[registry_key].daily_count

    def get_daily_remaining(
        self, provider: ModelProvider, model_id: str,
    ) -> int:
        """Get remaining daily requests for a provider+model."""
        registry_key = f"{model_id}-{provider.value}"
        self._reset_daily_if_needed()
        if registry_key not in self._usage:
            return MODEL_REGISTRY.get(
                registry_key,
                ModelConfig(
                    provider=provider, model_id=model_id,
                    display_name=model_id, tier=ModelTier.LIGHT,
                    priority=99, max_requests_per_day=14400,
                    max_tokens_per_minute=30000, context_window=8192,
                    api_endpoint_base="", is_openai_compatible=True,
                ),
            ).max_requests_per_day
        usage = self._usage[registry_key]
        return max(0, usage.daily_limit - usage.daily_count)

    def check_rate_limit(
        self, provider: ModelProvider, model_id: str,
    ) -> bool:
        """Check if a provider+model is currently rate limited."""
        registry_key = f"{model_id}-{provider.value}"
        if registry_key not in self._usage:
            return False
        usage = self._usage[registry_key]
        return usage.rate_limited_until > time.time()

    def reset_daily_counts(self) -> None:
        """Force-reset all daily counters."""
        for usage in self._usage.values():
            usage.daily_count = 0
        self._last_daily_reset = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        logger.info("Daily counts force-reset")

    def get_all_status(self) -> dict:
        """Return health overview for all tracked provider+model combos."""
        self._reset_daily_if_needed()
        status: Dict[str, dict] = {}
        for registry_key, usage in self._usage.items():
            rpm_available = usage.get_rpm_available()
            status[registry_key] = {
                "provider": usage.provider.value,
                "rpm_used": usage.rpm_count,
                "rpm_limit": usage.rpm_limit,
                "rpm_available": rpm_available,
                "is_healthy": usage.is_healthy,
                "daily_count": usage.daily_count,
                "daily_limit": usage.daily_limit,
                "model_id": usage.model_id,
                "daily_remaining": max(0, usage.daily_limit - usage.daily_count),
                "minute_count": usage.minute_count,
                "minute_limit": usage.minute_limit,
                "consecutive_failures": usage.consecutive_failures,
                "last_error": usage.last_error,
                "rate_limited": usage.rate_limited_until > time.time(),
            }
        # Attach per-provider RPM sliding-window status (the real enforcement)
        status["_provider_rpm"] = self.get_provider_rpm_status()
        return status


# ── Exceptions ──────────────────────────────────────────────────────


class RateLimitError(Exception):
    """Raised when a provider returns HTTP 429 rate limit.

    Carries provider/model info so the caller can record the cooldown.
    """

    def __init__(
        self,
        provider: ModelProvider,
        model_id: str,
        retry_after: int = 0,
        detail: str = "",
    ) -> None:
        self.provider = provider
        self.model_id = model_id
        self.retry_after = retry_after
        self.detail = detail
        super().__init__(
            f"Rate limited: {model_id} ({provider.value}), "
            f"retry_after={retry_after}s, detail={detail}"
        )


# ── Routing Decision ───────────────────────────────────────────────


@dataclass
class RoutingDecision:
    """Result of the Smart Router's routing decision for one atomic step."""
    atomic_step_type: AtomicStepType
    model_config: ModelConfig
    provider: ModelProvider
    tier: ModelTier
    variant_type: str
    routing_reason: str
    fallback_models: List[ModelConfig] = field(default_factory=list)
    estimated_tokens: int = 0
    technique_boosted: bool = False
    routed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


# ── Smart Router ───────────────────────────────────────────────────


class SmartRouter:
    """MAKER-Aware 3-Tier LLM Router (F-054).

    Selects which AI model to use PER ATOMIC STEP (not per query).
    One customer query = 6-24 LLM calls via MAKER framework.
    Technique-boosted calls use LIGHT tier; only raw reasoning
    needs MEDIUM/HEAVY.

    BC-007: All AI model interaction MUST go through Smart Router.
    BC-001: company_id is always second parameter.
    BC-008: Graceful degradation -- never crash.
    """

    MAX_RETRIES = 2
    REQUEST_TIMEOUT_SECONDS = 30

    def __init__(self, config: Any = None) -> None:
        """Initialize the router with model registry and shared health tracker."""
        self._config = config
        # Share health tracker across all instances
        self._health = ProviderHealthTracker()
        logger.info(
            "Smart Router initialized with %d models across %d tiers",
            len(MODEL_REGISTRY),
            len({m.tier for m in MODEL_REGISTRY.values()}),
        )

    # ── Public API ──────────────────────────────────────────────

    def route(
        self,
        company_id: str,
        variant_type: str,
        atomic_step: AtomicStepType,
        query_signals: Optional[dict] = None,
    ) -> RoutingDecision:
        """MAIN METHOD -- route one atomic step to a model.

        BC-001: company_id is always second parameter.
        BC-008: Always returns a valid RoutingDecision.
        """
        try:
            return self._route_safe(
                company_id=company_id,
                variant_type=variant_type,
                atomic_step=atomic_step,
                query_signals=query_signals or {},
            )
        except Exception:
            # BC-008: Absolute safety net -- never crash
            logger.exception(
                "Smart Router routing failed, returning safe LIGHT fallback "
                "(company_id=%s, step=%s, variant=%s)",
                company_id, atomic_step.value, variant_type,
            )
            # Return first LIGHT model as ultimate fallback
            first_light = self._get_first_light_model()
            return RoutingDecision(
                atomic_step_type=atomic_step,
                model_config=first_light,
                provider=first_light.provider,
                tier=ModelTier.LIGHT,
                variant_type=variant_type,
                routing_reason="emergency_fallback_all_checks_failed",
            )

    def route_batch(
        self,
        company_id: str,
        variant_type: str,
        steps: List[AtomicStepType],
        query_signals: Optional[dict] = None,
    ) -> List[RoutingDecision]:
        """Route multiple steps for a MAKER chain.

        Returns a RoutingDecision for each atomic step, allowing
        the MAKER orchestrator to execute calls in parallel or sequence.
        """
        decisions: List[RoutingDecision] = []
        signals = query_signals or {}
        for step in steps:
            try:
                decision = self.route(company_id, variant_type, step, signals)
                decisions.append(decision)
            except Exception:
                # BC-008: Even in batch mode, never crash
                logger.exception(
                    "Batch routing failed for step=%s, inserting fallback",
                    step.value,
                )
                first_light = self._get_first_light_model()
                decisions.append(RoutingDecision(
                    atomic_step_type=step,
                    model_config=first_light,
                    provider=first_light.provider,
                    tier=ModelTier.LIGHT,
                    variant_type=variant_type,
                    routing_reason="batch_emergency_fallback",
                ))
        logger.info(
            "Batch routing complete: %d steps for company_id=%s, variant=%s",
            len(decisions), company_id, variant_type,
        )
        return decisions

    def execute_llm_call(
        self,
        company_id: str,
        routing_decision: RoutingDecision,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> dict:
        """Execute an LLM API call using the routing decision.

        Handles retry + fallback across providers.
        Uses sync wrapper over async HTTP calls.

        BC-001: company_id is always second parameter.
        BC-008: Always returns a dict with 'content' key.
        """
        try:
            return self._execute_llm_call_safe(
                company_id, routing_decision, messages,
                temperature, max_tokens,
            )
        except Exception:
            # BC-008: Last resort fallback
            logger.exception(
                "execute_llm_call failed entirely (company_id=%s, model=%s)",
                company_id, routing_decision.model_config.model_id,
            )
            return {
                "content": "",
                "model": routing_decision.model_config.model_id,
                "provider": routing_decision.provider.value,
                "tier": routing_decision.tier.value,
                "atomic_step": routing_decision.atomic_step_type.value,
                "company_id": company_id,
                "fallback_used": True,
                "error": "All providers exhausted",
                "finish_reason": "error",
            }

    async def async_execute_llm_call(
        self,
        company_id: str,
        routing_decision: RoutingDecision,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> dict:
        """Async version of execute_llm_call for MAKER concurrent execution.

        Runs directly in the caller's event loop — no new_event_loop().
        BC-001: company_id is always second parameter.
        BC-008: Always returns a dict with 'content' key.
        """
        try:
            return await self._execute_llm_call_safe_async(
                company_id, routing_decision, messages,
                temperature, max_tokens,
            )
        except Exception:
            logger.exception(
                "async_execute_llm_call failed (company_id=%s, model=%s)",
                company_id, routing_decision.model_config.model_id,
            )
            return {
                "content": "",
                "model": routing_decision.model_config.model_id,
                "provider": routing_decision.provider.value,
                "tier": routing_decision.tier.value,
                "atomic_step": routing_decision.atomic_step_type.value,
                "company_id": company_id,
                "fallback_used": True,
                "error": "All providers exhausted",
                "finish_reason": "error",
            }

    def get_variant_info(self, variant_type: str) -> dict:
        """Return variant access info (SG-03)."""
        allowed = self._get_allowed_tiers(variant_type)
        models_by_tier: Dict[str, List[str]] = {}
        for key, config in MODEL_REGISTRY.items():
            tier_val = config.tier.value
            if tier_val not in models_by_tier:
                models_by_tier[tier_val] = []
            if config.tier in allowed:
                models_by_tier[tier_val].append(
                    f"{config.display_name} ({config.provider.value})"
                )
        return {
            "variant_type": variant_type,
            "allowed_tiers": sorted(t.value for t in allowed),
            "available_models": models_by_tier,
            "total_available": sum(len(v) for v in models_by_tier.values()),
        }

    def get_provider_status(self) -> dict:
        """Return all provider health status."""
        return self._health.get_all_status()

    # ── Internal Routing Logic ──────────────────────────────────

    def _route_safe(
        self,
        company_id: str,
        variant_type: str,
        atomic_step: AtomicStepType,
        query_signals: dict,
    ) -> RoutingDecision:
        """Safe routing with fallback chain."""
        allowed_tiers = self._get_allowed_tiers(variant_type)
        target_tier = self._get_step_tier(atomic_step, allowed_tiers, query_signals)

        # GUARDRAIL is special -- always allowed, never downgraded
        if target_tier == ModelTier.GUARDRAIL:
            model, fallbacks = self._select_model(ModelTier.GUARDRAIL, query_signals)
            return RoutingDecision(
                atomic_step_type=atomic_step,
                model_config=model,
                provider=model.provider,
                tier=ModelTier.GUARDRAIL,
                variant_type=variant_type,
                routing_reason=f"guardrail_step_always_guardrail_model",
                fallback_models=fallbacks,
                estimated_tokens=200,
            )

        # Try target tier first
        model, fallbacks = self._select_model(target_tier, query_signals)
        if model is not None and self._is_model_available(model):
            reason = self._build_routing_reason(
                target_tier, model, query_signals, atomic_step, variant_type,
            )
            return RoutingDecision(
                atomic_step_type=atomic_step,
                model_config=model,
                provider=model.provider,
                tier=target_tier,
                variant_type=variant_type,
                routing_reason=reason,
                fallback_models=fallbacks,
                estimated_tokens=self._estimate_tokens(atomic_step),
                technique_boosted=self._is_technique_boosted(atomic_step),
            )

        # Fallback within same tier
        fallback_model = self._fallback_within_tier(target_tier)
        if fallback_model is not None:
            logger.warning(
                "Primary model unavailable for tier=%s step=%s, "
                "using fallback within tier: %s",
                target_tier.value, atomic_step.value,
                fallback_model.display_name,
            )
            return RoutingDecision(
                atomic_step_type=atomic_step,
                model_config=fallback_model,
                provider=fallback_model.provider,
                tier=target_tier,
                variant_type=variant_type,
                routing_reason=f"fallback_within_{target_tier.value}",
                estimated_tokens=self._estimate_tokens(atomic_step),
            )

        # Fallback to lower tier
        lower_model = self._fallback_to_lower_tier(target_tier, allowed_tiers)
        if lower_model is not None:
            logger.warning(
                "All models in tier=%s unavailable for step=%s, "
                "degraded to tier=%s: %s",
                target_tier.value, atomic_step.value,
                lower_model.tier.value, lower_model.display_name,
            )
            return RoutingDecision(
                atomic_step_type=atomic_step,
                model_config=lower_model,
                provider=lower_model.provider,
                tier=lower_model.tier,
                variant_type=variant_type,
                routing_reason=(
                    f"degraded_from_{target_tier.value}_"
                    f"to_{lower_model.tier.value}"
                ),
                estimated_tokens=self._estimate_tokens(atomic_step),
            )

        # BC-008: Absolute fallback -- first LIGHT model
        first_light = self._get_first_light_model()
        logger.error(
            "All tiers exhausted for step=%s, using absolute LIGHT fallback: %s",
            atomic_step.value, first_light.display_name,
        )
        return RoutingDecision(
            atomic_step_type=atomic_step,
            model_config=first_light,
            provider=first_light.provider,
            tier=ModelTier.LIGHT,
            variant_type=variant_type,
            routing_reason="absolute_emergency_light_fallback",
            estimated_tokens=self._estimate_tokens(atomic_step),
        )

    def _get_allowed_tiers(self, variant_type: str) -> Set[ModelTier]:
        """Get allowed tiers for a variant type (SG-03).

        Unknown variant types default to mini_parwa (safest).
        """
        if variant_type not in VARIANT_MODEL_ACCESS:
            logger.warning(
                "Unknown variant_type=%s, defaulting to mini_parwa (safest)",
                variant_type,
            )
            return VARIANT_MODEL_ACCESS["mini_parwa"]
        return VARIANT_MODEL_ACCESS[variant_type]

    def _get_step_tier(
        self,
        atomic_step: AtomicStepType,
        allowed_tiers: Set[ModelTier],
        query_signals: dict,
    ) -> ModelTier:
        """Pick the tier for a given atomic step.

        Respects variant gating: if recommended tier is not allowed,
        degrades to the highest allowed tier.
        """
        recommended = STEP_TIER_MAPPING.get(atomic_step, ModelTier.LIGHT)

        # GUARDRAIL tier is always allowed regardless of variant
        if recommended == ModelTier.GUARDRAIL:
            return ModelTier.GUARDRAIL

        # Check if recommended tier is allowed by variant
        if recommended in allowed_tiers:
            return recommended

        # Degrade to highest allowed tier
        for tier in TIER_FALLBACK_ORDER:
            if tier in allowed_tiers:
                logger.info(
                    "Step %s: recommended tier=%s not allowed by variant, "
                    "degraded to tier=%s",
                    atomic_step.value, recommended.value, tier.value,
                )
                return tier

        # LIGHT is always allowed (it's in every variant)
        return ModelTier.LIGHT

    def _select_model(
        self,
        tier: ModelTier,
        query_signals: dict,
    ) -> Tuple[Optional[ModelConfig], List[ModelConfig]]:
        """Pick primary model + list of fallbacks for a tier.

        Models within a tier are sorted by priority (1 = best).
        Returns (primary_model, fallback_models_list).
        """
        tier_models = [
            config for config in MODEL_REGISTRY.values()
            if config.tier == tier
        ]
        tier_models.sort(key=lambda m: m.priority)

        primary: Optional[ModelConfig] = None
        fallbacks: List[ModelConfig] = []

        for model in tier_models:
            if primary is None:
                if self._is_model_available(model):
                    primary = model
                else:
                    fallbacks.append(model)
            else:
                fallbacks.append(model)

        # If no model is available, return first model anyway (BC-008)
        if primary is None and tier_models:
            primary = tier_models[0]
            fallbacks = tier_models[1:]
            logger.warning(
                "No available model in tier=%s, forcing primary: %s",
                tier.value, primary.display_name,
            )

        return primary, fallbacks

    def _is_model_available(self, model_config: ModelConfig) -> bool:
        """Check if a model's provider is healthy and under rate limits."""
        return self._health.is_available(
            model_config.provider, model_config.model_id,
        )

    def _fallback_within_tier(self, tier: ModelTier) -> Optional[ModelConfig]:
        """Find next available model in the same tier."""
        tier_models = [
            config for config in MODEL_REGISTRY.values()
            if config.tier == tier
        ]
        tier_models.sort(key=lambda m: m.priority)

        for model in tier_models:
            if self._is_model_available(model):
                return model
        return None

    def _fallback_to_lower_tier(
        self,
        current_tier: ModelTier,
        allowed_tiers: Set[ModelTier],
    ) -> Optional[ModelConfig]:
        """Degrade to the next lower available tier."""
        tier_order = [ModelTier.HEAVY, ModelTier.MEDIUM, ModelTier.LIGHT]
        try:
            current_idx = tier_order.index(current_tier)
        except ValueError:
            current_idx = 0

        for i in range(current_idx + 1, len(tier_order)):
            lower_tier = tier_order[i]
            if lower_tier not in allowed_tiers:
                continue
            model = self._fallback_within_tier(lower_tier)
            if model is not None:
                return model

        return None

    def _get_first_light_model(self) -> ModelConfig:
        """Get the first LIGHT model as ultimate fallback."""
        for config in MODEL_REGISTRY.values():
            if config.tier == ModelTier.LIGHT:
                return config
        # Should never happen, but BC-008 demands a return
        return ModelConfig(
            provider=ModelProvider.CEREBRAS,
            model_id="gpt-oss-120b",
            display_name="Emergency Fallback GPT-OSS 120B",
            tier=ModelTier.LIGHT,
            priority=99,
            max_requests_per_day=14400,
            max_tokens_per_minute=60000,
            context_window=8192,
            api_endpoint_base="https://api.cerebras.ai/v1/chat/completions",
            is_openai_compatible=True,
        )

    def _build_routing_reason(
        self,
        tier: ModelTier,
        model: ModelConfig,
        query_signals: dict,
        atomic_step: AtomicStepType,
        variant_type: str,
    ) -> str:
        """Build human-readable routing reason string."""
        parts = [f"step={atomic_step.value}"]
        parts.append(f"tier={tier.value}")

        if query_signals.get("query_complexity", 0) > 0.7:
            parts.append("high_complexity")
        if query_signals.get("sentiment_score", 0.7) < 0.3:
            parts.append("low_sentiment")
        if query_signals.get("customer_tier") == "vip":
            parts.append("vip_customer")

        if self._is_technique_boosted(atomic_step):
            parts.append("technique_boosted")

        parts.append(f"variant={variant_type}")
        parts.append(f"model={model.display_name}")

        return "|".join(parts)

    @staticmethod
    def _estimate_tokens(atomic_step: AtomicStepType) -> int:
        """Rough token estimate per atomic step."""
        estimates = {
            AtomicStepType.INTENT_CLASSIFICATION: 100,
            AtomicStepType.PII_REDACTION: 150,
            AtomicStepType.SENTIMENT_ANALYSIS: 80,
            AtomicStepType.CLARA_QUALITY_GATE: 60,
            AtomicStepType.CRP_TOKEN_TRIM: 50,
            AtomicStepType.GSD_STATE_STEP: 70,
            AtomicStepType.MAD_DECOMPOSE: 120,
            AtomicStepType.MAD_ATOM_SIMPLE: 100,
            AtomicStepType.MAD_ATOM_REASONING: 400,
            AtomicStepType.COT_REASONING: 350,
            AtomicStepType.FAKE_VOTING: 80,
            AtomicStepType.CONSENSUS_ANALYSIS: 150,
            AtomicStepType.DRAFT_RESPONSE_SIMPLE: 200,
            AtomicStepType.DRAFT_RESPONSE_MODERATE: 500,
            AtomicStepType.DRAFT_RESPONSE_COMPLEX: 800,
            AtomicStepType.REFLEXION_CYCLE: 400,
            AtomicStepType.ESCALATE_TO_HUMAN: 50,
            AtomicStepType.GUARDRAIL_CHECK: 100,
        }
        return estimates.get(atomic_step, 200)

    @staticmethod
    def _is_technique_boosted(atomic_step: AtomicStepType) -> bool:
        """Check if this step's intelligence comes from a technique, not model."""
        technique_boosted_steps = {
            AtomicStepType.COT_REASONING,
            AtomicStepType.FAKE_VOTING,
            AtomicStepType.CONSENSUS_ANALYSIS,
            AtomicStepType.CLARA_QUALITY_GATE,
            AtomicStepType.CRP_TOKEN_TRIM,
            AtomicStepType.GSD_STATE_STEP,
        }
        return atomic_step in technique_boosted_steps

    # ── LLM Execution ───────────────────────────────────────────

    def _execute_llm_call_safe(
        self,
        company_id: str,
        routing_decision: RoutingDecision,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Execute LLM call via LiteLLM with retry + fallback (sync).

        BC-001: company_id is always second parameter.
        BC-008: Always returns a dict with 'content' key.
        """
        config = routing_decision.model_config
        provider = config.provider
        model_id = config.model_id

        # Try LiteLLM first, fall back to raw HTTP on auth/missing errors
        use_litellm = _HAS_LITELLM and litellm is not None
        api_key = self._get_api_key(provider) if use_litellm else None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                # Acquire per-provider RPM slot (waits at 0, never switches)
                self._health.acquire_provider_slot(provider)

                if use_litellm and api_key:
                    result = self._call_litellm_sync(
                        provider=provider,
                        model_id=model_id,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    self._health.record_success(
                        provider, model_id,
                        tokens_used=result.get("tokens_used", 0),
                    )
                    return result
                else:
                    # Fallback to raw HTTP if litellm not available or no API key
                    result = self._call_provider(
                        provider=provider,
                        model_id=model_id,
                        config=config,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        company_id=company_id,
                    )
                    self._health.record_success(
                        provider, model_id,
                        tokens_used=result.get("tokens_used", 0),
                    )
                    return result
            except RateLimitError as rle:
                self._health.record_rate_limit(
                    provider, model_id,
                    retry_after_seconds=rle.retry_after,
                )
                logger.warning(
                    "Rate limited: %s model=%s attempt=%d retry_after=%d",
                    provider.value, model_id, attempt + 1, rle.retry_after,
                )
                if attempt < self.MAX_RETRIES:
                    continue
            except Exception as exc:
                # If litellm auth fails, switch to raw HTTP for remaining retries
                if use_litellm and api_key and ("auth" in str(exc).lower() or "api_key" in str(exc).lower()):
                    logger.warning(
                        "LiteLLM auth failed, switching to raw HTTP: %s",
                        str(exc),
                    )
                    use_litellm = False
                    api_key = None
                    continue
                self._health.record_failure(provider, model_id, str(exc))
                logger.warning(
                    "Call failed: %s model=%s attempt=%d error=%s",
                    provider.value, model_id, attempt + 1, str(exc),
                )
                if attempt < self.MAX_RETRIES:
                    continue

        # All retries exhausted, try fallback models
        for fb in routing_decision.fallback_models:
            if self._is_model_available(fb):
                try:
                    # Acquire RPM slot for the FALLBACK provider (may differ
                    # from primary provider — track per-provider, not per-model)
                    self._health.acquire_provider_slot(fb.provider)

                    if _HAS_LITELLM and litellm is not None:
                        result = self._call_litellm_sync(
                            provider=fb.provider,
                            model_id=fb.model_id,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                        )
                        self._health.record_success(fb.provider, fb.model_id)
                        result["fallback_used"] = True
                        return result
                except Exception as exc:
                    logger.warning(
                        "Fallback failed: %s model=%s error=%s",
                        fb.provider.value, fb.model_id, str(exc),
                    )
                    continue

        # BC-008: Return empty fallback
        return {
            "content": "",
            "model": model_id,
            "provider": provider.value,
            "tier": routing_decision.tier.value,
            "atomic_step": routing_decision.atomic_step_type.value,
            "company_id": company_id,
            "fallback_used": True,
            "error": "All providers exhausted",
            "finish_reason": "error",
        }

    async def _execute_llm_call_safe_async(
        self,
        company_id: str,
        routing_decision: RoutingDecision,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Execute LLM call via LiteLLM with retry + fallback (async).

        BC-001: company_id is always second parameter.
        BC-008: Always returns a dict with 'content' key.
        """
        config = routing_decision.model_config
        provider = config.provider
        model_id = config.model_id

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                # Acquire per-provider RPM slot (waits at 0, never switches).
                # Blocking call — acceptable because each pipeline runs in its
                # own worker thread with its own event loop.
                self._health.acquire_provider_slot(provider)

                if _HAS_LITELLM and litellm is not None:
                    result = await self._call_litellm_async(
                        provider=provider,
                        model_id=model_id,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    self._health.record_success(
                        provider, model_id,
                        tokens_used=result.get("tokens_used", 0),
                    )
                    return result
                else:
                    # Fallback to raw async HTTP if litellm not available
                    if config.is_openai_compatible:
                        result = await self._call_openai_compatible_async(
                            model_config=config,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                        )
                    else:
                        result = await self._call_google_async(
                            model_config=config,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                        )
                    self._health.record_success(
                        provider, model_id,
                        tokens_used=result.get("tokens_used", 0),
                    )
                    return result
            except RateLimitError as rle:
                self._health.record_rate_limit(
                    provider, model_id,
                    retry_after_seconds=rle.retry_after,
                )
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(1)
                    continue
            except Exception as exc:
                self._health.record_failure(provider, model_id, str(exc))
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(1)
                    continue

        # All retries exhausted, try fallback models
        for fb in routing_decision.fallback_models:
            if self._is_model_available(fb):
                try:
                    # Acquire RPM slot for the FALLBACK provider (may differ
                    # from primary provider — track per-provider, not per-model)
                    self._health.acquire_provider_slot(fb.provider)

                    if _HAS_LITELLM and litellm is not None:
                        result = await self._call_litellm_async(
                            provider=fb.provider,
                            model_id=fb.model_id,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                        )
                        self._health.record_success(fb.provider, fb.model_id)
                        result["fallback_used"] = True
                        return result
                    elif fb.is_openai_compatible:
                        result = await self._call_openai_compatible_async(
                            model_config=fb,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                        )
                        self._health.record_success(fb.provider, fb.model_id)
                        result["fallback_used"] = True
                        return result
                except Exception as exc:
                    logger.warning("fallback_model_failed provider=%s error=%s", fb.provider.value, str(exc)[:150])
                    continue

        return {
            "content": "",
            "model": model_id,
            "provider": provider.value,
            "tier": routing_decision.tier.value,
            "atomic_step": routing_decision.atomic_step_type.value,
            "company_id": company_id,
            "fallback_used": True,
            "error": "All providers exhausted",
            "finish_reason": "error",
        }

    # ── LiteLLM Integration (BC-007) ──────────────────────────────

    @staticmethod
    def _build_litellm_model_name(provider: ModelProvider, model_id: str) -> str:
        """Build the LiteLLM model name from provider and model_id.

        LiteLLM uses format: provider/model_id for custom providers.
        For OpenAI-compatible: openai/model_id or just model_id.
        """
        mapping = {
            ModelProvider.CEREBRAS: f"cerebras/{model_id}",
            ModelProvider.GROQ: f"groq/{model_id}",
            ModelProvider.GOOGLE: f"gemini/{model_id}",
            ModelProvider.NVIDIA: f"nvidia/{model_id}",
            ModelProvider.AI21: f"ai21/{model_id}",
        }
        return mapping.get(provider, f"openai/{model_id}")

    def _call_litellm_sync(
        self,
        provider: ModelProvider,
        model_id: str,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Make a synchronous LLM call via LiteLLM.

        Uses LiteLLM's unified API which handles provider-specific
        payload formatting, retries, and token counting.

        BC-007: All AI interaction through Smart Router.
        """
        litellm_model = self._build_litellm_model_name(provider, model_id)

        # Set API keys from environment
        api_key = self._get_api_key(provider)
        kwargs: Dict[str, Any] = {
            "model": litellm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": self.REQUEST_TIMEOUT_SECONDS,
        }
        if api_key:
            kwargs["api_key"] = api_key

        response = litellm.completion(**kwargs)  # type: ignore[union-attr]
        choice = response.choices[0]
        content = choice.message.content or ""
        usage = response.usage

        return {
            "content": content,
            "model": model_id,
            "provider": provider.value,
            "finish_reason": choice.finish_reason or "stop",
            "tokens_used": getattr(usage, 'total_tokens', 0),
            "prompt_tokens": getattr(usage, 'prompt_tokens', 0),
            "completion_tokens": getattr(usage, 'completion_tokens', 0),
        }

    async def _call_litellm_async(
        self,
        provider: ModelProvider,
        model_id: str,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Make an async LLM call via LiteLLM.

        BC-007: All AI interaction through Smart Router.
        """
        litellm_model = self._build_litellm_model_name(provider, model_id)

        api_key = self._get_api_key(provider)
        kwargs: Dict[str, Any] = {
            "model": litellm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": self.REQUEST_TIMEOUT_SECONDS,
        }
        if api_key:
            kwargs["api_key"] = api_key

        response = await litellm.acompletion(**kwargs)  # type: ignore[union-attr]
        choice = response.choices[0]
        content = choice.message.content or ""
        usage = response.usage

        return {
            "content": content,
            "model": model_id,
            "provider": provider.value,
            "finish_reason": choice.finish_reason or "stop",
            "tokens_used": getattr(usage, 'total_tokens', 0),
            "prompt_tokens": getattr(usage, 'prompt_tokens', 0),
            "completion_tokens": getattr(usage, 'completion_tokens', 0),
        }

    def _get_api_key(self, provider: ModelProvider) -> Optional[str]:
        """Get API key for a provider from environment variables or Settings.

        Checks multiple env var names for compatibility:
        - Google: GOOGLE_API_KEY, GEMINI_API_KEY, GOOGLE_AI_API_KEY
        - Groq: GROQ_API_KEY
        - Cerebras: CEREBRAS_API_KEY
        """
        key_map = {
            ModelProvider.CEREBRAS: (
                os.environ.get("CEREBRAS_API_KEY")
            ),
            ModelProvider.GROQ: (
                os.environ.get("GROQ_API_KEY")
            ),
            ModelProvider.GOOGLE: (
                os.environ.get("GOOGLE_API_KEY")
                or os.environ.get("GEMINI_API_KEY")
                or os.environ.get("GOOGLE_AI_API_KEY")
            ),
            ModelProvider.NVIDIA: (
                os.environ.get("NVIDIA_API_KEY")
            ),
            ModelProvider.AI21: (
                os.environ.get("AI21_API_KEY")
            ),
        }
        key = key_map.get(provider)

        # Also try loading from Settings class (pydantic-settings)
        if not key:
            try:
                from app.config import get_settings
                settings = get_settings()
                if provider == ModelProvider.CEREBRAS:
                    key = getattr(settings, "CEREBRAS_API_KEY", None)
                elif provider == ModelProvider.GROQ:
                    key = getattr(settings, "GROQ_API_KEY", None)
                elif provider == ModelProvider.GOOGLE:
                    key = (
                        getattr(settings, "GOOGLE_AI_API_KEY", None)
                        or getattr(settings, "GOOGLE_API_KEY", None)
                        or getattr(settings, "GEMINI_API_KEY", None)
                    )
            except Exception:
                pass  # Settings not available (missing required vars)

        return key or None

    def _call_provider(
        self,
        model_config: ModelConfig,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Call the appropriate LLM provider API.

        Sync wrapper -- runs async call in event loop.
        """
        # Use httpx synchronous client instead of asyncio.new_event_loop()
        # to avoid "attached to a different loop" errors in FastAPI.
        import httpx

        headers = {}
        body: dict = {}

        if model_config.is_openai_compatible:
            api_url = model_config.base_url
            api_key = model_config.api_key or ""
            headers["Authorization"] = f"Bearer {api_key}"
            headers["Content-Type"] = "application/json"
            body = {
                "model": model_config.model_id,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        else:
            # Google AI Studio
            api_key = model_config.api_key or ""
            headers["x-goog-api-key"] = api_key
            headers["Content-Type"] = "application/json"
            # Google API uses a different structure
            body = {
                "contents": [],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                },
            }
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if isinstance(content, str):
                    body["contents"].append({"role": role, "parts": [{"text": content}]})
                elif isinstance(content, list):
                    parts = [{"text": p.get("text", "")} for p in content if isinstance(p, dict)]
                    body["contents"].append({"role": role, "parts": parts})

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(model_config.base_url, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()

            if model_config.is_openai_compatible:
                return data
            else:
                # Parse Google format
                candidates = data.get("candidates", [])
                if candidates:
                    text_parts = candidates[0].get("content", {}).get("parts", [])
                    return {
                        "choices": [{
                            "message": {"role": "assistant", "content": text_parts[0].get("text", "")}
                        }],
                        "usage": data.get("usageMetadata", {}),
                    }
                return {"choices": [{"message": {"role": "assistant", "content": ""}}]}
        except Exception as exc:
            raise RuntimeError(f"LLM call failed for {model_config.model_id}: {exc}") from exc

    @staticmethod
    async def _call_google_async(
        model_config: ModelConfig,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Call Google AI Studio API (async)."""
        import aiohttp

        # Lazy import of config for API key
        from app.config import get_settings
        settings = get_settings()
        api_key = settings.GOOGLE_AI_API_KEY

        if not api_key:
            raise ValueError("GOOGLE_AI_API_KEY not configured")

        url = (
            f"{model_config.api_endpoint_base}/"
            f"{model_config.model_id}:generateContent?key={api_key}"
        )

        # Convert OpenAI-style messages to Google format
        # Use systemInstruction for system messages (Google-native)
        contents = []
        system_instruction = None
        for msg in messages:
            role = msg.get("role", "user")
            text = msg.get("content", "")
            if role == "system":
                # Google supports system via systemInstruction field
                system_instruction = text
            else:
                contents.append({"role": role, "parts": [{"text": text}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status == 429:
                    # Rate limited — extract Retry-After if present
                    retry_after = int(resp.headers.get("Retry-After", 0))
                    text = await resp.text()
                    # Raise a specific exception so caller can record rate limit
                    raise RateLimitError(
                        provider=model_config.provider,
                        model_id=model_config.model_id,
                        retry_after=retry_after,
                        detail=text,
                    )
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(
                        f"Google API error {resp.status}: {text}"
                    )
                data = await resp.json()

        # Parse response
        candidates = data.get("candidates", [])
        if not candidates:
            return {
                "content": "",
                "model": model_config.model_id,
                "provider": "google",
                "finish_reason": "empty",
            }

        content_parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in content_parts)

        usage = data.get("usageMetadata", {})
        total_tokens = usage.get("totalTokenCount", 0)

        return {
            "content": text,
            "model": model_config.model_id,
            "provider": "google",
            "finish_reason": candidates[0].get("finishReason", "stop"),
            "total_tokens": total_tokens,
        }

    @staticmethod
    async def _call_openai_compatible_async(
        model_config: ModelConfig,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Call OpenAI-compatible API -- Cerebras or Groq (async)."""
        import aiohttp

        from app.config import get_settings
        settings = get_settings()

        # Select API key based on provider
        if model_config.provider == ModelProvider.CEREBRAS:
            api_key = settings.CEREBRAS_API_KEY
            if not api_key:
                raise ValueError("CEREBRAS_API_KEY not configured")
        elif model_config.provider == ModelProvider.GROQ:
            api_key = settings.GROQ_API_KEY
            if not api_key:
                raise ValueError("GROQ_API_KEY not configured")
        else:
            raise ValueError(f"Unsupported provider: {model_config.provider}")

        payload = {
            "model": model_config.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        timeout = aiohttp.ClientTimeout(total=30)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                model_config.api_endpoint_base,
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 0))
                    text = await resp.text()
                    raise RateLimitError(
                        provider=model_config.provider,
                        model_id=model_config.model_id,
                        retry_after=retry_after,
                        detail=text,
                    )
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(
                        f"{model_config.provider.value} API error "
                        f"{resp.status}: {text}"
                    )
                data = await resp.json()

        # Parse OpenAI-compatible response
        choices = data.get("choices", [])
        if not choices:
            return {
                "content": "",
                "model": model_config.model_id,
                "provider": model_config.provider.value,
                "finish_reason": "empty",
            }

        content = choices[0].get("message", {}).get("content", "")
        finish_reason = choices[0].get("finish_reason", "stop")

        usage = data.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)

        return {
            "content": content,
            "model": model_config.model_id,
            "provider": model_config.provider.value,
            "finish_reason": finish_reason,
            "total_tokens": total_tokens,
        }
