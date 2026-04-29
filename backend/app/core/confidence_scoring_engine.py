"""
F-059: Confidence Scoring Engine (BC-001, BC-008)

Every AI response gets a confidence score (0-100). Seven weighted signals
are evaluated independently and combined into a single overall score.

Signals Evaluated:
1. Semantic Relevance    (weight 0.25) — keyword overlap between query and response
2. Response Completeness (weight 0.15) — does response address all parts of the query
3. PII Safety Score      (weight 0.20) — based on PII pattern detection (no PII = high)
4. Hallucination Risk    (weight 0.20) — inverse of hallucination marker detection
5. Sentiment Alignment   (weight 0.10) — does response sentiment match expected tone
6. Token Efficiency      (weight 0.05) — response length vs query complexity ratio
7. Provider Confidence   (weight 0.05) — model tier and health reliability score

BC-001: company_id is always first parameter on all public methods.
BC-008: Never crash — always return a valid ConfidenceResult.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from app.logger import get_logger

logger = get_logger("confidence_scoring")


# ══════════════════════════════════════════════════════════════════
# COMPILED REGEX PATTERNS (module-level, never recompiled)
# ══════════════════════════════════════════════════════════════════


# ── PII Detection Patterns (for PII Safety signal) ──────────────

_RE_PII_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
)

_RE_PII_PHONE = re.compile(
    r"(?:\b\+?1[-.\s]?)?"
    r"(?:\(?\d{3}\)?[-.\s]?)"
    r"\d{3}[-.\s]?"
    r"\d{4}\b"
    r"|(?<!\w)\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b",
)

_RE_PII_SSN = re.compile(
    r"\b(?!000|666|9\d{2})(\d{3})[-\s](?!00)\d{2}[-\s](?!0000)\d{4}\b",
)

_RE_PII_CREDIT_CARD = re.compile(
    r"\b(?:4\d{3}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}"
    r"|(?:5[1-5]\d{2}|2[2-7]\d{2})[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}"
    r"|3[47]\d{2}[-\s]?\d{6}[-\s]?\d{5})\b",
)

_RE_PII_API_KEY = re.compile(
    r"\b(?:sk-[A-Za-z0-9_\-]{20,}"
    r"|key_[A-Za-z0-9_\-]{16,}"
    r"|ghp_[A-Za-z0-9]{36}"
    r"|csk-[A-Za-z0-9_\-]{20,}"
    r"|xox[bpra]-[A-Za-z0-9\-]{10,}"
    r"|AIza[A-Za-z0-9_\-]{35})\b",
)

_RE_PII_IPV4 = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\b",
)

_RE_PII_STREET_ADDRESS = re.compile(
    r"\b\d{1,5}\s+[A-Za-z0-9\s]{2,40}"
    r"(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|"
    r"Way|Court|Ct|Place|Pl|Circle|Cir|Trail|Trl|"
    r"Parkway|Pkwy|Highway|Hwy)\b",
    re.IGNORECASE,
)


# ── Hallucination Detection Patterns (for Hallucination Risk signal) ──

_RE_HALLUC_FABRICATED_STATS = re.compile(
    r"\b\d{1,3}(?:\.\d+)?% (?:of|increase|decrease|reduction|growth).*?"
    r"(?:according to|reported by|based on)\s+(?:a |the |our )?"
    r"(?:recent|latest|new|202[0-5])\b",
    re.IGNORECASE,
)

_RE_HALLUC_FAKE_URLS = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"[a-z]+\d{4}\.(?:com|org|net|io)\b",
    re.IGNORECASE,
)

_RE_HALLUC_TEMPORAL_CLAIMS = re.compile(
    r"\b(as of (?:my |the )?(?:latest|last) (?:update|training|knowledge).*?202[0-5]|"
    r"I (?:recently|just) learned that|according to (?:my|the) (?:latest|recent) (?:data|info)|"
    r"studies (?:from|in) 202[0-5] (?:show|suggest|indicate)|"
    r"a (?:recent|new|latest) (?:report|study|survey) (?:from|in) 202[0-5])\b", re.IGNORECASE, )

_RE_HALLUC_UNCERTAIN_CLAIMS = re.compile(
    r"\b(I (?:believe|think|assume|estimate) (?:that )?"
    r"(?:the|it|this) (?:exact|precise) (?:number|figure|value|date) is|"
    r"(?:approximately|roughly|about|around) \d{4,} (?:customers|users|clients)|"
    r"(?:studies|research) (?:show|suggest|indicate|prove) that.*\d+(?:\.\d+)?%)\b",
    re.IGNORECASE,
)

_RE_HALLUC_OVERCONFIDENT = re.compile(
    r"\b(?:definitely|absolutely|certainly|without a doubt|guaranteed|"
    r"without question|unequivocally|indisputably|undoubtedly)\b",
    re.IGNORECASE,
)

_RE_HALLUC_SPECULATIVE = re.compile(
    r"\b(?:I think|probably|might be|perhaps|possibly|it seems|"
    r"I believe|it appears|could be|may be|likely)\b",
    re.IGNORECASE,
)

_RE_HALLUC_SOURCE_ATTRIBUTION = re.compile(
    r"\b(?:according to|as stated in|per documentation|"
    r"per the documentation|see section|as described in|"
    r"refer to|consult|as outlined in|as specified in)\b",
    re.IGNORECASE,
)

_RE_HALLUC_FAKE_DOC_REF = re.compile(
    r"(?:Section|Article|Clause|Paragraph|Chapter)\s+"
    r"(?:\d+\.?\d*[a-z]?|I{1,3}V?|IV|VI{0,3}|IX|X{1,3}V?|XIV|XV|XVI|XVII|XVIII|XIX|XX)",
    re.IGNORECASE,
)

_RE_HALLUC_PLACEHOLDER_DOMAINS = re.compile(
    r"https?://(?:example\.com|example\.org|test\.com|"
    r"placeholder\.com|dontexist\.com|fakeurl\.com)[^\s]*",
    re.IGNORECASE,
)


# ── Sentiment Word Lists (for Sentiment Alignment signal) ──────

_POSITIVE_WORDS: Set[str] = {
    "great", "excellent", "happy", "pleased", "satisfied", "wonderful",
    "perfect", "love", "enjoy", "best", "amazing", "fantastic",
    "thankful", "grateful", "appreciate", "helpful", "friendly",
    "professional", "quality", "reliable", "efficient", "outstanding",
    "superb", "brilliant", "awesome", "good", "nice", "welcome",
    "understand", "resolved", "solution", "success", "glad",
}

_NEGATIVE_WORDS: Set[str] = {
    "terrible", "awful", "horrible", "worst", "hate", "angry",
    "frustrated", "disappointed", "unhappy", "useless", "broken",
    "unacceptable", "ridiculous", "stupid", "waste", "garbage",
    "pathetic", "annoying", "disgusting", "inferior", "complaint",
    "problem", "issue", "error", "fault", "failed", "wrong",
    "bad", "poor", "slow", "rude", "unprofessional",
}

_EMERGENCY_WORDS: Set[str] = {
    "urgent", "emergency", "immediately", "asap", "critical",
    "desperate", "urgent", "help", "danger", "risk", "safety",
    "legal", "threat", "violation", "breach", "complaint",
    "lawsuit", "attorney", "sue", "regulatory", "compliance",
}


# ── Question / Completeness Detection Patterns ──────────────────

_RE_QUESTION_WORDS = re.compile(
    r"\b(?:what|who|when|where|why|how|which|whom|whose|can|could|"
    r"would|should|is|are|do|does|did|will|shall|may|might)\b",
    re.IGNORECASE,
)

_RE_MULTI_PART_SPLITTERS = re.compile(
    r"(?:\band\b|\balso\b|\bas well\b|\bfurthermore\b|\bmoreover\b|"
    r"\bin addition\b|\bbesides\b|\bplus\b|\badditionally\b|"
    r"\bnot only\b|\balong with\b)",
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class SignalName(str, Enum):
    """Canonical names for all confidence signals."""
    SEMANTIC_RELEVANCE = "semantic_relevance"
    RESPONSE_COMPLETENESS = "response_completeness"
    PII_SAFETY = "pii_safety"
    HALLUCINATION_RISK = "hallucination_risk"
    SENTIMENT_ALIGNMENT = "sentiment_alignment"
    TOKEN_EFFICIENCY = "token_efficiency"
    PROVIDER_CONFIDENCE = "provider_confidence"


class VariantType(str, Enum):
    """PARWA variant identifiers with associated quality tiers."""
    MINI_PARWA = "mini_parwa"
    PARWA = "parwa"
    PARWA_HIGH = "high_parwa"


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class SignalScore:
    """Score and metadata for a single confidence signal.

    Attributes:
        signal_name: Canonical signal identifier from SignalName enum.
        score: Individual signal score in [0.0, 100.0].
        weight: This signal's weight in the weighted average (0.0-1.0).
        contribution: Weighted contribution (score * weight).
        metadata: Structured details about how the score was computed.
        passed: True if score >= the configured threshold.
    """
    signal_name: str
    score: float  # 0-100
    weight: float
    contribution: float  # score * weight
    metadata: Dict[str, Any] = field(default_factory=dict)
    passed: bool = True

    def __post_init__(self) -> None:
        """Clamp score to [0, 100] and compute contribution."""
        self.score = max(0.0, min(100.0, self.score))
        self.contribution = round(self.score * self.weight, 4)


@dataclass
class ConfidenceResult:
    """Aggregated result of a confidence scoring evaluation.

    Attributes:
        overall_score: Weighted average of all signal scores [0.0, 100.0].
        passed: True if overall_score >= threshold.
        threshold: Minimum score required to pass.
        signals: Detailed breakdown per signal.
        variant_type: PARWA variant used for threshold/weights.
        company_id: Tenant identifier (BC-001).
        scored_at: UTC ISO 8601 timestamp of when scoring completed.
        scoring_duration_ms: Wall-clock time for the scoring operation.
    """
    overall_score: float  # 0-100
    passed: bool  # True if overall_score >= threshold
    threshold: float
    signals: List[SignalScore] = field(default_factory=list)
    variant_type: str = "parwa"
    company_id: str = ""
    scored_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    scoring_duration_ms: float = 0.0

    def __post_init__(self) -> None:
        """Clamp overall_score to [0, 100] and determine passed."""
        self.overall_score = max(0.0, min(100.0, self.overall_score))
        self.passed = self.overall_score >= self.threshold


@dataclass
class ConfidenceConfig:
    """Per-tenant confidence scoring configuration.

    Attributes:
        company_id: Tenant identifier (BC-001).
        variant_type: PARWA variant (mini_parwa, parwa, high_parwa).
        threshold: Minimum overall score to pass (0-100).
        signal_weights: Override default weights per signal name.
        enabled_signals: Which signals to evaluate (empty = all).
    """
    company_id: str
    variant_type: str = "parwa"
    threshold: float = 85.0
    signal_weights: Dict[str, float] = field(default_factory=dict)
    enabled_signals: List[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
# DEFAULT WEIGHTS AND THRESHOLDS
# ══════════════════════════════════════════════════════════════════

# Default signal weights — sum to 1.0
DEFAULT_SIGNAL_WEIGHTS: Dict[str, float] = {
    SignalName.SEMANTIC_RELEVANCE.value: 0.25,
    SignalName.RESPONSE_COMPLETENESS.value: 0.15,
    SignalName.PII_SAFETY.value: 0.20,
    SignalName.HALLUCINATION_RISK.value: 0.20,
    SignalName.SENTIMENT_ALIGNMENT.value: 0.10,
    SignalName.TOKEN_EFFICIENCY.value: 0.05,
    SignalName.PROVIDER_CONFIDENCE.value: 0.05,
}

# Default confidence thresholds per variant:
# Mini PARWA = 95 (high confidence required for limited AI)
# PARWA = 85 (standard balanced threshold)
# PARWA High = 75 (more autonomous, enterprise trust)
DEFAULT_THRESHOLDS: Dict[str, float] = {
    VariantType.MINI_PARWA.value: 95.0,
    VariantType.PARWA.value: 85.0,
    VariantType.PARWA_HIGH.value: 75.0,
}

# All signal names (canonical ordering)
ALL_SIGNAL_NAMES: List[str] = [
    SignalName.SEMANTIC_RELEVANCE.value,
    SignalName.RESPONSE_COMPLETENESS.value,
    SignalName.PII_SAFETY.value,
    SignalName.HALLUCINATION_RISK.value,
    SignalName.SENTIMENT_ALIGNMENT.value,
    SignalName.TOKEN_EFFICIENCY.value,
    SignalName.PROVIDER_CONFIDENCE.value,
]

# Known model tiers and their reliability scores (0-100)
MODEL_TIER_RELIABILITY: Dict[str, float] = {
    "tier_1": 95.0,    # GPT-4o, Claude 3.5 Sonnet
    "tier_2": 85.0,    # GPT-4o-mini, Claude 3 Haiku
    "tier_3": 70.0,    # GPT-3.5-turbo, lighter models
    "unknown": 75.0,    # Default when tier is not provided
}


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def _tokenize(text: str) -> Set[str]:
    """Simple whitespace + punctuation tokenizer for keyword analysis.

    Converts text to lowercase, splits on non-alphanumeric, and
    returns a set of tokens (filtering out very short ones).

    Args:
        text: The text to tokenize.

    Returns:
        Set of unique tokens with length >= 3.
    """
    tokens = re.split(r"[^a-zA-Z0-9]+", text.lower())
    return {t for t in tokens if len(t) >= 3}


def _jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """Compute Jaccard similarity between two sets.

    Jaccard(A, B) = |A ∩ B| / |A ∪ B|.

    Args:
        set_a: First token set.
        set_b: Second token set.

    Returns:
        Similarity in [0.0, 1.0]. Returns 0.0 if both sets are empty.
    """
    if not set_a and not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    intersection = set_a & set_b
    return len(intersection) / len(union)


def _safe_divide(
        numerator: float,
        denominator: float,
        fallback: float = 0.0) -> float:
    """Safely divide two numbers, returning fallback on zero denominator.

    Args:
        numerator: The value to divide.
        denominator: The value to divide by.
        fallback: Value returned when denominator is zero.

    Returns:
        numerator / denominator, or fallback.
    """
    if denominator == 0:
        return fallback
    return numerator / denominator


# ══════════════════════════════════════════════════════════════════
# CONFIDENCE SCORING ENGINE
# ══════════════════════════════════════════════════════════════════


class ConfidenceScoringEngine:
    """F-059: Confidence Scoring Engine.

    Evaluates AI responses across 7 weighted signals to produce a
    single confidence score (0-100). Supports per-tenant configuration
    overrides, variant-specific thresholds, and batch scoring.

    BC-001: company_id is always the first parameter on public methods.
    BC-008: Never crashes — always returns a valid ConfidenceResult.
    """

    def __init__(self) -> None:
        """Initialize the scoring engine with an empty tenant config cache."""
        self._tenant_configs: Dict[str, ConfidenceConfig] = {}
        logger.info("confidence_scoring_engine_initialized")

    # ── Public API ──────────────────────────────────────────────

    def score_response(
        self,
        company_id: str,
        query: str,
        response: str,
        context: Optional[Dict[str, Any]] = None,
        config: Optional[ConfidenceConfig] = None,
    ) -> ConfidenceResult:
        """Score a single AI response for confidence.

        Evaluates all 7 signals (or a filtered set from config),
        computes a weighted average, and compares against the threshold.

        Args:
            company_id: Tenant identifier (BC-001).
            query: The original customer query.
            response: The AI-generated response to score.
            context: Optional dict with additional signal context:
                - model_tier: str (tier_1, tier_2, tier_3)
                - model_health: float (0-100)
                - pii_redacted: bool (whether PII was already redacted)
                - expected_tone: str (positive, neutral, empathetic)
                - knowledge_context: str (KB context used for generation)
            config: Optional per-call config override.

        Returns:
            ConfidenceResult with overall score, per-signal breakdown,
            and pass/fail determination.
        """
        start_time = time.monotonic()
        ctx = context or {}

        # Resolve configuration
        resolved_config = self._resolve_config(
            company_id=company_id,
            config=config,
        )

        # Build effective weights from config
        weights = self._get_effective_weights(resolved_config)
        threshold = self._get_effective_threshold(resolved_config)

        # Determine which signals to evaluate
        enabled = resolved_config.enabled_signals
        signals_to_eval = enabled if enabled else ALL_SIGNAL_NAMES

        # Evaluate each signal
        signals: List[SignalScore] = []
        total_contribution = 0.0
        total_weight = 0.0

        for signal_name in signals_to_eval:
            if signal_name not in weights:
                continue

            try:
                signal = self._evaluate_signal(
                    signal_name=signal_name,
                    query=query,
                    response=response,
                    context=ctx,
                    weight=weights[signal_name],
                    threshold=threshold,
                )
            except Exception:
                # BC-008: Never crash. Default to 50.0 on error.
                logger.warning(
                    "signal_evaluation_failed_using_default",
                    extra={
                        "company_id": company_id,
                        "signal_name": signal_name,
                    },
                    exc_info=True,
                )
                signal = SignalScore(
                    signal_name=signal_name,
                    score=50.0,
                    weight=weights[signal_name],
                    contribution=round(50.0 * weights[signal_name], 4),
                    metadata={"error": "evaluation_failed", "fallback": True},
                    passed=False,
                )

            signal.passed = signal.score >= threshold
            signals.append(signal)
            total_contribution += signal.contribution
            total_weight += signal.weight

        # Compute overall score (weighted average)
        overall = _safe_divide(total_contribution, total_weight, fallback=0.0)

        duration_ms = (time.monotonic() - start_time) * 1000.0

        result = ConfidenceResult(
            overall_score=round(overall, 2),
            passed=overall >= threshold,
            threshold=threshold,
            signals=signals,
            variant_type=resolved_config.variant_type,
            company_id=company_id,
            scored_at=datetime.now(timezone.utc).isoformat(),
            scoring_duration_ms=round(duration_ms, 2),
        )

        logger.info(
            "response_scored",
            extra={
                "company_id": company_id,
                "overall_score": result.overall_score,
                "passed": result.passed,
                "threshold": threshold,
                "variant_type": result.variant_type,
                "signals_evaluated": len(signals),
                "duration_ms": duration_ms,
            },
        )

        return result

    def score_batch(
        self,
        company_id: str,
        items: List[Dict[str, Any]],
        config: Optional[ConfidenceConfig] = None,
    ) -> List[ConfidenceResult]:
        """Score multiple AI responses in a single call.

        Each item in the batch must contain 'query' and 'response' keys.
        Optional keys: 'context', 'config'.

        Args:
            company_id: Tenant identifier (BC-001).
            items: List of dicts, each with 'query' (str), 'response' (str),
                and optionally 'context' (dict) and 'config' (ConfidenceConfig).
            config: Default config to use for all items (per-item overrides).

        Returns:
            List of ConfidenceResult in the same order as input items.
        """
        results: List[ConfidenceResult] = []

        for idx, item in enumerate(items):
            try:
                query = item.get("query", "")
                response = item.get("response", "")
                item_context = item.get("context")
                item_config = item.get("config") or config

                result = self.score_response(
                    company_id=company_id,
                    query=query,
                    response=response,
                    context=item_context,
                    config=item_config,
                )
            except Exception:
                # BC-008: Never crash batch processing
                logger.warning(
                    "batch_item_scoring_failed",
                    extra={
                        "company_id": company_id,
                        "item_index": idx,
                    },
                    exc_info=True,
                )
                result = ConfidenceResult(
                    overall_score=0.0,
                    passed=False,
                    threshold=config.threshold if config else 85.0,
                    variant_type=config.variant_type if config else "parwa",
                    company_id=company_id,
                    scored_at=datetime.now(timezone.utc).isoformat(),
                    scoring_duration_ms=0.0,
                    signals=[],
                )
            results.append(result)

        logger.info(
            "batch_scored",
            extra={
                "company_id": company_id,
                "total_items": len(items),
                "passed_count": sum(1 for r in results if r.passed),
                "failed_count": sum(1 for r in results if not r.passed),
            },
        )

        return results

    def get_signal_weights(self, variant_type: str) -> Dict[str, float]:
        """Get the default signal weights for a variant type.

        Args:
            variant_type: PARWA variant (mini_parwa, parwa, high_parwa).

        Returns:
            Dict mapping signal names to their default weights.
        """
        # All variants share the same default weights unless
        # a tenant override is configured.
        return dict(DEFAULT_SIGNAL_WEIGHTS)

    def get_threshold(self, variant_type: str) -> float:
        """Get the default confidence threshold for a variant type.

        Args:
            variant_type: PARWA variant (mini_parwa, parwa, high_parwa).

        Returns:
            Threshold score (0-100) required to pass.
        """
        return DEFAULT_THRESHOLDS.get(variant_type, 85.0)

    def update_config(self, company_id: str, config: ConfidenceConfig) -> None:
        """Cache a tenant-specific confidence configuration.

        Args:
            company_id: Tenant identifier (BC-001).
            config: The configuration to cache for this tenant.
        """
        config.company_id = company_id
        self._tenant_configs[company_id] = config
        logger.info(
            "tenant_config_updated",
            extra={
                "company_id": company_id,
                "variant_type": config.variant_type,
                "threshold": config.threshold,
                "weight_overrides": list(config.signal_weights.keys()),
                "enabled_signals": config.enabled_signals or "all",
            },
        )

    def get_config(self, company_id: str) -> ConfidenceConfig:
        """Get the cached tenant-specific configuration.

        Falls back to a default config if no tenant override exists.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            ConfidenceConfig for the tenant.
        """
        if company_id in self._tenant_configs:
            return self._tenant_configs[company_id]
        return ConfidenceConfig(
            company_id=company_id,
            variant_type="parwa",
            threshold=DEFAULT_THRESHOLDS[VariantType.PARWA.value],
        )

    # ── Configuration Resolution ───────────────────────────────

    def _resolve_config(
        self,
        company_id: str,
        config: Optional[ConfidenceConfig] = None,
    ) -> ConfidenceConfig:
        """Resolve the effective configuration for a scoring call.

        Priority: call-level config > tenant cached config > defaults.

        Args:
            company_id: Tenant identifier.
            config: Optional call-level config override.

        Returns:
            Fully resolved ConfidenceConfig.
        """
        if config is not None:
            # Merge with defaults for any unset fields
            variant = config.variant_type or "parwa"
            threshold = config.threshold or self.get_threshold(variant)
            return ConfidenceConfig(
                company_id=config.company_id or company_id,
                variant_type=variant,
                threshold=threshold,
                signal_weights=config.signal_weights or {},
                enabled_signals=config.enabled_signals or [],
            )

        # Fall back to cached tenant config
        tenant_config = self._tenant_configs.get(company_id)
        if tenant_config is not None:
            threshold = tenant_config.threshold or self.get_threshold(
                tenant_config.variant_type,
            )
            return ConfidenceConfig(
                company_id=company_id,
                variant_type=tenant_config.variant_type,
                threshold=threshold,
                signal_weights=tenant_config.signal_weights or {},
                enabled_signals=tenant_config.enabled_signals or [],
            )

        # Use defaults
        return ConfidenceConfig(
            company_id=company_id,
            variant_type="parwa",
            threshold=DEFAULT_THRESHOLDS[VariantType.PARWA.value],
        )

    def _get_effective_weights(
            self, config: ConfidenceConfig) -> Dict[str, float]:
        """Build effective weights by merging defaults with tenant overrides.

        Args:
            config: Resolved tenant configuration.

        Returns:
            Dict of signal_name -> weight. Sum may not equal 1.0 if
            overrides changed individual values (caller normalizes).
        """
        weights = dict(DEFAULT_SIGNAL_WEIGHTS)
        for signal_name, override_weight in config.signal_weights.items():
            if signal_name in weights:
                weights[signal_name] = override_weight
        return weights

    def _get_effective_threshold(self, config: ConfidenceConfig) -> float:
        """Get the effective threshold for this configuration.

        Args:
            config: Resolved tenant configuration.

        Returns:
            Threshold value from config, or variant default.
        """
        if config.threshold is not None and config.threshold > 0:
            return config.threshold
        return self.get_threshold(config.variant_type)

    # ── Signal Dispatcher ──────────────────────────────────────

    def _evaluate_signal(
        self,
        signal_name: str,
        query: str,
        response: str,
        context: Dict[str, Any],
        weight: float,
        threshold: float,
    ) -> SignalScore:
        """Dispatch to the appropriate signal evaluator.

        Args:
            signal_name: Canonical signal name from SignalName enum.
            query: Original customer query.
            response: AI-generated response.
            context: Additional signal context.
            weight: This signal's weight in the average.
            threshold: Score threshold for pass/fail.

        Returns:
            SignalScore with score, weight, and metadata.
        """
        evaluators: Dict[str, Any] = {
            SignalName.SEMANTIC_RELEVANCE.value: self._eval_semantic_relevance,
            SignalName.RESPONSE_COMPLETENESS.value: self._eval_response_completeness,
            SignalName.PII_SAFETY.value: self._eval_pii_safety,
            SignalName.HALLUCINATION_RISK.value: self._eval_hallucination_risk,
            SignalName.SENTIMENT_ALIGNMENT.value: self._eval_sentiment_alignment,
            SignalName.TOKEN_EFFICIENCY.value: self._eval_token_efficiency,
            SignalName.PROVIDER_CONFIDENCE.value: self._eval_provider_confidence,
        }

        evaluator = evaluators.get(signal_name)
        if evaluator is None:
            logger.warning(
                "unknown_signal_name",
                extra={"signal_name": signal_name},
            )
            return SignalScore(
                signal_name=signal_name,
                score=50.0,
                weight=weight,
                contribution=round(50.0 * weight, 4),
                metadata={"error": "unknown_signal"},
                passed=False,
            )

        return evaluator(query, response, context, weight)

    # ═══════════════════════════════════════════════════════════
    # SIGNAL EVALUATORS (internal)
    # ═══════════════════════════════════════════════════════════

    def _eval_semantic_relevance(
        self,
        query: str,
        response: str,
        context: Dict[str, Any],
        weight: float,
    ) -> SignalScore:
        """Evaluate semantic relevance via keyword overlap.

        Computes Jaccard similarity and keyword overlap ratio between
        the query and response tokens. Higher overlap = more relevant.

        Scoring:
        - Jaccard similarity * 60 + overlap ratio * 40 = raw (0-100)
        - Score of 100 means perfect token overlap.

        Args:
            query: Original customer query.
            response: AI-generated response.
            context: Unused for this signal.
            weight: Signal weight.

        Returns:
            SignalScore for semantic_relevance.
        """
        if not query or not query.strip() or not response or not response.strip():
            return SignalScore(
                signal_name=SignalName.SEMANTIC_RELEVANCE.value,
                score=50.0,
                weight=weight,
                contribution=round(50.0 * weight, 4),
                metadata={"reason": "empty_query_or_response"},
            )

        query_tokens = _tokenize(query)
        response_tokens = _tokenize(response)

        # Filter out common stop words for more meaningful comparison
        stop_words: Set[str] = {
            "the", "and", "for", "are", "but", "not", "you", "all",
            "can", "had", "her", "was", "one", "our", "out", "has",
            "have", "from", "been", "some", "them", "than", "its",
            "over", "that", "this", "with", "will", "each", "make",
            "like", "just", "into", "could", "would", "should",
            "about", "which", "their", "what", "when", "where",
            "does", "also", "very", "more", "other", "your",
        }

        query_tokens_filtered = query_tokens - stop_words
        response_tokens_filtered = response_tokens - stop_words

        # Jaccard similarity (intersection / union)
        jaccard = _jaccard_similarity(
            query_tokens_filtered,
            response_tokens_filtered)

        # Keyword overlap ratio (how many query tokens appear in response)
        if query_tokens_filtered:
            overlap = query_tokens_filtered & response_tokens_filtered
            overlap_ratio = len(overlap) / len(query_tokens_filtered)
        else:
            overlap_ratio = 0.0

        # Compute score: Jaccard * 60 + overlap_ratio * 40
        raw_score = (jaccard * 60.0) + (overlap_ratio * 40.0)
        score = round(min(100.0, raw_score * 100.0), 2)

        return SignalScore(
            signal_name=SignalName.SEMANTIC_RELEVANCE.value,
            score=score,
            weight=weight,
            contribution=round(score * weight, 4),
            metadata={
                "jaccard_similarity": round(jaccard, 4),
                "overlap_ratio": round(overlap_ratio, 4),
                "query_token_count": len(query_tokens_filtered),
                "response_token_count": len(response_tokens_filtered),
                "overlap_token_count": len(
                    query_tokens_filtered & response_tokens_filtered,
                ),
            },
        )

    def _eval_response_completeness(
        self,
        query: str,
        response: str,
        context: Dict[str, Any],
        weight: float,
    ) -> SignalScore:
        """Evaluate whether the response addresses all parts of the query.

        Checks for:
        1. Multi-part queries (split on "and", "also", "furthermore", etc.)
        2. Question word coverage
        3. Whether each sub-topic gets attention in the response

        Scoring:
        - Full coverage of all sub-topics = 90-100
        - Partial coverage = 50-89
        - Minimal coverage = 0-49

        Args:
            query: Original customer query.
            response: AI-generated response.
            context: Unused for this signal.
            weight: Signal weight.

        Returns:
            SignalScore for response_completeness.
        """
        if not query or not query.strip() or not response or not response.strip():
            return SignalScore(
                signal_name=SignalName.RESPONSE_COMPLETENESS.value,
                score=50.0,
                weight=weight,
                contribution=round(50.0 * weight, 4),
                metadata={"reason": "empty_query_or_response"},
            )

        # Extract question words from the query
        question_words = set(
            w.lower() for w in re.findall(r"\b\w+\b", query) if w.lower()
        ) - {"the", "and", "is", "a", "an", "to", "o", "in", "for", "it"}

        # Check if query contains multiple sub-questions
        query_lower = query.lower()
        sub_parts = _RE_MULTI_PART_SPLITTERS.split(query_lower)
        sub_parts = [p.strip() for p in sub_parts if len(p.strip()) > 5]

        if len(sub_parts) <= 1:
            # Single-topic query — check that response covers the key topic
            query_tokens = _tokenize(query)
            response_tokens = _tokenize(response)
            stop_words = {
                "the", "and", "for", "are", "but", "not", "you", "all",
                "can", "was", "our", "out", "has", "have", "from", "been",
                "some", "than", "its", "over", "that", "this", "with",
                "will", "each", "make", "like", "into", "could", "would",
                "about", "which", "their", "what", "when", "where", "does",
                "also", "very", "more", "other", "your", "how", "please",
            }
            query_content_tokens = query_tokens - stop_words
            response_content_tokens = response_tokens - stop_words

            if not query_content_tokens:
                score = 80.0
            else:
                covered = query_content_tokens & response_content_tokens
                coverage_ratio = len(covered) / len(query_content_tokens)
                score = round(min(100.0, coverage_ratio * 100.0), 2)

            return SignalScore(
                signal_name=SignalName.RESPONSE_COMPLETENESS.value,
                score=score,
                weight=weight,
                contribution=round(score * weight, 4),
                metadata={
                    "multi_part": False,
                    "sub_parts_count": 1,
                    "coverage_ratio": round(
                        len(covered) / len(query_content_tokens), 4
                    ) if query_content_tokens else 1.0,
                    "tokens_covered": len(covered),
                    "total_content_tokens": len(query_content_tokens),
                },
            )

        # Multi-part query: check each sub-topic
        response_lower = response.lower()
        response_tokens = _tokenize(response)
        stop_words = {
            "the", "and", "for", "are", "but", "not", "you", "all",
            "can", "was", "our", "out", "has", "have", "from", "been",
            "some", "than", "its", "over", "that", "this", "with",
            "will", "each", "make", "like", "into", "could", "would",
            "about", "which", "their", "what", "when", "where", "does",
            "also", "very", "more", "other", "your", "how", "please",
        }

        parts_addressed = 0
        part_details: List[Dict[str, Any]] = []

        for part in sub_parts:
            part_tokens = _tokenize(part) - stop_words
            if not part_tokens:
                parts_addressed += 1
                part_details.append(
                    {"part": part[:50], "covered": True, "ratio": 1.0})
                continue

            covered = part_tokens & response_tokens
            ratio = len(covered) / len(part_tokens)

            if ratio >= 0.3:
                parts_addressed += 1
                part_details.append({
                    "part": part[:50],
                    "covered": True,
                    "ratio": round(ratio, 4),
                })
            else:
                part_details.append({
                    "part": part[:50],
                    "covered": False,
                    "ratio": round(ratio, 4),
                })

        completeness_ratio = parts_addressed / len(sub_parts)
        score = round(min(100.0, completeness_ratio * 100.0), 2)

        return SignalScore(
            signal_name=SignalName.RESPONSE_COMPLETENESS.value,
            score=score,
            weight=weight,
            contribution=round(score * weight, 4),
            metadata={
                "multi_part": True,
                "sub_parts_count": len(sub_parts),
                "parts_addressed": parts_addressed,
                "completeness_ratio": round(completeness_ratio, 4),
                "part_details": part_details,
            },
        )

    def _eval_pii_safety(
        self,
        query: str,
        response: str,
        context: Dict[str, Any],
        weight: float,
    ) -> SignalScore:
        """Evaluate PII safety in the response.

        Scans the response for PII patterns (emails, phones, SSNs,
        credit cards, API keys, IP addresses, street addresses).
        High score = no PII detected. Each PII finding reduces score
        based on its sensitivity level.

        Scoring:
        - No PII detected = 100
        - Low-sensitivity PII (phone, DOB, address) = -10 per finding
        - High-sensitivity PII (SSN, credit card, API key) = -25 per finding
        - Minimum score is 0.

        Args:
            query: Original customer query (for context, not scanned).
            response: AI-generated response to scan for PII.
            context: Optional 'pii_redacted' flag indicating if PII
                was already redacted from the response.
            weight: Signal weight.

        Returns:
            SignalScore for pii_safety.
        """
        if not response or not response.strip():
            return SignalScore(
                signal_name=SignalName.PII_SAFETY.value,
                score=100.0,
                weight=weight,
                contribution=round(100.0 * weight, 4),
                metadata={"reason": "empty_response"},
            )

        # If PII was already redacted, give high safety score
        if context.get("pii_redacted"):
            return SignalScore(
                signal_name=SignalName.PII_SAFETY.value,
                score=95.0,
                weight=weight,
                contribution=round(95.0 * weight, 4),
                metadata={"reason": "pii_pre_redacted"},
            )

        score = 100.0
        findings: List[Dict[str, Any]] = []

        # Define PII checks: (compiled_regex, sensitivity, label, penalty)
        pii_checks: List[Tuple[re.Pattern, str, str, float]] = [
            (_RE_PII_EMAIL, "medium", "EMAIL", 10.0),
            (_RE_PII_PHONE, "low", "PHONE", 8.0),
            (_RE_PII_SSN, "critical", "SSN", 30.0),
            (_RE_PII_CREDIT_CARD, "critical", "CREDIT_CARD", 25.0),
            (_RE_PII_API_KEY, "critical", "API_KEY", 30.0),
            (_RE_PII_IPV4, "low", "IP_ADDRESS", 5.0),
            (_RE_PII_STREET_ADDRESS, "medium", "STREET_ADDRESS", 10.0),
        ]

        for pattern, sensitivity, label, penalty in pii_checks:
            matches = list(pattern.finditer(response))
            if matches:
                score -= (penalty * len(matches))
                for m in matches:
                    findings.append({
                        "type": label,
                        "sensitivity": sensitivity,
                        "match_preview": m.group()[:40],
                        "penalty": penalty,
                    })

        score = max(0.0, min(100.0, score))
        score = round(score, 2)

        return SignalScore(
            signal_name=SignalName.PII_SAFETY.value,
            score=score,
            weight=weight,
            contribution=round(score * weight, 4),
            metadata={
                "pii_findings": findings,
                "finding_count": len(findings),
                "safety_level": "safe" if score >= 90 else (
                    "caution" if score >= 60 else "unsafe"
                ),
            },
        )

    def _eval_hallucination_risk(
        self,
        query: str,
        response: str,
        context: Dict[str, Any],
        weight: float,
    ) -> SignalScore:
        """Evaluate hallucination risk — inverse of hallucination detection.

        Checks for common hallucination markers: fabricated statistics,
        fake URLs, uncertain claims, overconfident statements near
        speculative language, unverified source attributions, and
        placeholder domains.

        Scoring:
        - No markers = 100 (low risk)
        - Each marker type detected = -10 to -25 points
        - Score is clamped to [0, 100]

        Args:
            query: Original customer query.
            response: AI-generated response to analyze.
            context: Unused for this signal.
            weight: Signal weight.

        Returns:
            SignalScore for hallucination_risk (high = safe, low = risky).
        """
        if not response or not response.strip():
            return SignalScore(
                signal_name=SignalName.HALLUCINATION_RISK.value,
                score=100.0,
                weight=weight,
                contribution=round(100.0 * weight, 4),
                metadata={"reason": "empty_response"},
            )

        score = 100.0
        markers: List[Dict[str, str]] = []

        # Check fabricated statistics
        if _RE_HALLUC_FABRICATED_STATS.search(response):
            score -= 15.0
            match = _RE_HALLUC_FABRICATED_STATS.search(response)
            markers.append({
                "type": "fabricated_statistics",
                "preview": (match.group()[:80] if match else ""),
            })

        # Check fake URLs
        if _RE_HALLUC_FAKE_URLS.search(response):
            score -= 12.0
            match = _RE_HALLUC_FAKE_URLS.search(response)
            markers.append({
                "type": "fake_urls",
                "preview": (match.group()[:80] if match else ""),
            })

        # Check temporal claims
        if _RE_HALLUC_TEMPORAL_CLAIMS.search(response):
            score -= 10.0
            match = _RE_HALLUC_TEMPORAL_CLAIMS.search(response)
            markers.append({
                "type": "temporal_claims",
                "preview": (match.group()[:80] if match else ""),
            })

        # Check uncertain claims
        if _RE_HALLUC_UNCERTAIN_CLAIMS.search(response):
            score -= 10.0
            match = _RE_HALLUC_UNCERTAIN_CLAIMS.search(response)
            markers.append({
                "type": "uncertain_claims",
                "preview": (match.group()[:80] if match else ""),
            })

        # Check overconfident + speculative proximity
        overconfident = list(_RE_HALLUC_OVERCONFIDENT.finditer(response))
        speculative = list(_RE_HALLUC_SPECULATIVE.finditer(response))
        has_proximity_issue = False
        for oc in overconfident:
            for spec in speculative:
                if abs(oc.start() - spec.end()) <= 50:
                    has_proximity_issue = True
                    break
            if has_proximity_issue:
                break

        if has_proximity_issue:
            score -= 8.0
            markers.append({
                "type": "overconfident_plus_speculative",
                "preview": "overconfident language near speculative language",
            })

        # Check unverified source attributions
        if _RE_HALLUC_SOURCE_ATTRIBUTION.search(response):
            score -= 5.0
            match = _RE_HALLUC_SOURCE_ATTRIBUTION.search(response)
            markers.append({
                "type": "source_attribution",
                "preview": (match.group()[:80] if match else ""),
            })

        # Check fake document references
        if _RE_HALLUC_FAKE_DOC_REF.search(response):
            score -= 10.0
            match = _RE_HALLUC_FAKE_DOC_REF.search(response)
            markers.append({
                "type": "fake_document_reference",
                "preview": (match.group()[:80] if match else ""),
            })

        # Check placeholder domains
        if _RE_HALLUC_PLACEHOLDER_DOMAINS.search(response):
            score -= 15.0
            match = _RE_HALLUC_PLACEHOLDER_DOMAINS.search(response)
            markers.append({
                "type": "placeholder_domains",
                "preview": (match.group()[:80] if match else ""),
            })

        score = max(0.0, min(100.0, round(score, 2)))

        risk_level = "low" if score >= 80 else (
            "medium" if score >= 50 else "high"
        )

        return SignalScore(
            signal_name=SignalName.HALLUCINATION_RISK.value,
            score=score,
            weight=weight,
            contribution=round(score * weight, 4),
            metadata={
                "markers_found": markers,
                "marker_count": len(markers),
                "risk_level": risk_level,
            },
        )

    def _eval_sentiment_alignment(
        self,
        query: str,
        response: str,
        context: Dict[str, Any],
        weight: float,
    ) -> SignalScore:
        """Evaluate whether response sentiment matches expected tone.

        Performs simple positive/negative/neutral word counting on both
        query and response, then checks if the response tone is
        appropriate given the query sentiment and the expected tone
        from context.

        Scoring rules:
        - Neutral query + neutral response = high score
        - Negative query + empathetic/positive response = high score
        - Negative query + negative response = low score (inappropriate)
        - Positive query + positive response = high score
        - Emergency query + professional response = high score

        Args:
            query: Original customer query.
            response: AI-generated response.
            context: Optional 'expected_tone' key (positive, neutral,
                empathetic, professional).
            weight: Signal weight.

        Returns:
            SignalScore for sentiment_alignment.
        """
        if not query or not query.strip() or not response or not response.strip():
            return SignalScore(
                signal_name=SignalName.SENTIMENT_ALIGNMENT.value,
                score=70.0,
                weight=weight,
                contribution=round(70.0 * weight, 4),
                metadata={"reason": "empty_query_or_response"},
            )

        query_lower = query.lower()
        response_lower = response.lower()

        # Count sentiment words
        query_positive = sum(1 for w in _POSITIVE_WORDS if w in query_lower)
        query_negative = sum(1 for w in _NEGATIVE_WORDS if w in query_lower)
        query_emergency = sum(1 for w in _EMERGENCY_WORDS if w in query_lower)

        response_positive = sum(
            1 for w in _POSITIVE_WORDS if w in response_lower)
        response_negative = sum(
            1 for w in _NEGATIVE_WORDS if w in response_lower)

        # Determine query sentiment
        if query_emergency > 0:
            query_sentiment = "emergency"
        elif query_negative > query_positive:
            query_sentiment = "negative"
        elif query_positive > query_negative:
            query_sentiment = "positive"
        else:
            query_sentiment = "neutral"

        # Determine response sentiment
        if response_negative > response_positive:
            response_sentiment = "negative"
        elif response_positive > response_negative:
            response_sentiment = "positive"
        else:
            response_sentiment = "neutral"

        # Score based on alignment
        expected_tone = context.get("expected_tone", "")

        if query_sentiment == "emergency":
            # Emergency queries: response should be professional, not casual
            if response_sentiment == "neutral" or response_positive > 0:
                score = 85.0
                reason = "appropriate_emergency_tone"
            elif response_sentiment == "negative":
                score = 40.0
                reason = "negative_tone_for_emergency"
            else:
                score = 70.0
                reason = "acceptable_emergency_tone"

        elif query_sentiment == "negative":
            # Negative queries: response should be empathetic/positive
            if response_sentiment == "positive" or response_positive > response_negative:
                score = 90.0
                reason = "empathetic_response_to_negative_query"
            elif response_sentiment == "negative":
                score = 30.0
                reason = "negative_tone_mirrors_customer_frustration"
            else:
                score = 70.0
                reason = "neutral_response_to_negative_query"

        elif query_sentiment == "positive":
            # Positive queries: response should match positive tone
            if response_sentiment == "positive":
                score = 90.0
                reason = "matching_positive_tone"
            elif response_sentiment == "negative":
                score = 35.0
                reason = "negative_tone_for_positive_query"
            else:
                score = 75.0
                reason = "neutral_response_to_positive_query"

        else:
            # Neutral queries: neutral or slightly positive response is best
            if response_sentiment == "neutral":
                score = 90.0
                reason = "appropriate_neutral_tone"
            elif response_sentiment == "positive":
                score = 85.0
                reason = "slightly_positive_for_neutral_query"
            else:
                score = 50.0
                reason = "negative_tone_for_neutral_query"

        # Apply expected tone override from context
        if expected_tone:
            if expected_tone == "professional" and response_sentiment == "neutral":
                score = max(score, 90.0)
            elif expected_tone == "positive" and response_sentiment == "positive":
                score = max(score, 95.0)
            elif expected_tone == "empathetic" and response_positive > 0:
                score = max(score, 90.0)

        score = max(0.0, min(100.0, round(score, 2)))

        return SignalScore(
            signal_name=SignalName.SENTIMENT_ALIGNMENT.value,
            score=score,
            weight=weight,
            contribution=round(score * weight, 4),
            metadata={
                "query_sentiment": query_sentiment,
                "response_sentiment": response_sentiment,
                "query_positive_count": query_positive,
                "query_negative_count": query_negative,
                "query_emergency_count": query_emergency,
                "response_positive_count": response_positive,
                "response_negative_count": response_negative,
                "expected_tone": expected_tone or "auto",
                "alignment_reason": reason,
            },
        )

    def _eval_token_efficiency(
        self,
        query: str,
        response: str,
        context: Dict[str, Any],
        weight: float,
    ) -> SignalScore:
        """Evaluate response length efficiency relative to query complexity.

        Measures the ratio of response length to query complexity.
        Penalizes both overly terse responses (insufficient detail)
        and excessively verbose responses (wasteful).

        Scoring rules:
        - Response 3x-10x query length = optimal (90-100)
        - Response 1.5x-3x query length = adequate (70-89)
        - Response 10x-20x query length = verbose (50-69)
        - Response < 1.5x query length = too short (30-49)
        - Response > 20x query length = excessively verbose (20-29)

        Query complexity is measured by unique token count.

        Args:
            query: Original customer query.
            response: AI-generated response.
            context: Unused for this signal.
            weight: Signal weight.

        Returns:
            SignalScore for token_efficiency.
        """
        if not query or not query.strip() or not response or not response.strip():
            return SignalScore(
                signal_name=SignalName.TOKEN_EFFICIENCY.value,
                score=50.0,
                weight=weight,
                contribution=round(50.0 * weight, 4),
                metadata={"reason": "empty_query_or_response"},
            )

        query_len = len(query.strip())
        response_len = len(response.strip())
        query_tokens = len(query.split())
        response_tokens = len(response.split())

        # Compute length ratio
        ratio = _safe_divide(response_len, query_len, fallback=0.0)

        # Compute token ratio
        token_ratio = _safe_divide(
            response_tokens, max(
                1, query_tokens), fallback=0.0)

        # Determine score based on ratio
        if ratio <= 0:
            score = 10.0
            efficiency = "empty_response"
        elif ratio < 1.5:
            score = 30.0 + (ratio / 1.5) * 20.0  # 30-50
            efficiency = "too_short"
        elif ratio < 3.0:
            score = 70.0 + ((ratio - 1.5) / 1.5) * 20.0  # 70-90
            efficiency = "adequate"
        elif ratio <= 10.0:
            score = 85.0 + ((ratio - 3.0) / 7.0) * 15.0  # 85-100
            efficiency = "optimal"
        elif ratio <= 20.0:
            score = 50.0 + ((20.0 - ratio) / 10.0) * 20.0  # 50-70
            efficiency = "verbose"
        else:
            # Excessively verbose — steep penalty
            score = max(10.0, 50.0 - (ratio - 20.0) * 2.0)
            efficiency = "excessively_verbose"

        # Small response penalty (too short to be useful)
        if response_tokens < 10:
            score = min(score, 30.0)
            efficiency = "critically_short"

        score = max(0.0, min(100.0, round(score, 2)))

        return SignalScore(
            signal_name=SignalName.TOKEN_EFFICIENCY.value,
            score=score,
            weight=weight,
            contribution=round(score * weight, 4),
            metadata={
                "query_length": query_len,
                "response_length": response_len,
                "length_ratio": round(ratio, 4),
                "query_tokens": query_tokens,
                "response_tokens": response_tokens,
                "token_ratio": round(token_ratio, 4),
                "efficiency_level": efficiency,
            },
        )

    def _eval_provider_confidence(
        self,
        query: str,
        response: str,
        context: Dict[str, Any],
        weight: float,
    ) -> SignalScore:
        """Evaluate provider/model confidence based on tier and health.

        Uses the model tier and health information from context to
        assess the reliability of the provider that generated the
        response. Higher-tier models with better health scores get
        higher provider confidence.

        Scoring:
        - Base score from model tier reliability (70-95)
        - Adjusted by model health (0-100) if provided
        - Adjusted by query complexity match (complex queries need higher tiers)

        Args:
            query: Original customer query.
            response: AI-generated response.
            context: Optional keys:
                - model_tier: str (tier_1, tier_2, tier_3)
                - model_health: float (0-100)
            weight: Signal weight.

        Returns:
            SignalScore for provider_confidence.
        """
        if not response or not response.strip():
            return SignalScore(
                signal_name=SignalName.PROVIDER_CONFIDENCE.value,
                score=50.0,
                weight=weight,
                contribution=round(50.0 * weight, 4),
                metadata={"reason": "empty_response"},
            )

        # Get model tier from context
        model_tier = context.get("model_tier", "unknown")
        model_health = context.get("model_health")

        # Base reliability from tier
        tier_reliability = MODEL_TIER_RELIABILITY.get(
            str(model_tier).lower(),
            MODEL_TIER_RELIABILITY["unknown"],
        )

        # Start with tier reliability
        score = tier_reliability

        # Adjust by model health if available (0-100)
        if model_health is not None:
            health_factor = max(0.0, min(100.0, float(model_health)))
            # Health adjustment: blend tier_reliability with health
            # (70% tier + 30% health)
            score = (score * 0.7) + (health_factor * 0.3)

        # Complexity adjustment: measure query complexity
        query_tokens = _tokenize(query) if query else set()
        query_word_count = len(query.split()) if query else 0
        has_multi_part = len(
            _RE_MULTI_PART_SPLITTERS.split(
                query.lower())) > 2 if query else False

        # Penalize lower tiers for complex queries
        if query_word_count > 30 or has_multi_part or len(query_tokens) > 15:
            complexity_penalty = 0.0
            if model_tier == "tier_3":
                complexity_penalty = 15.0
            elif model_tier == "tier_2":
                complexity_penalty = 5.0
            elif model_tier == "unknown":
                complexity_penalty = 10.0
            score -= complexity_penalty

        # Bonus for higher tiers handling complex queries well
        if model_tier == "tier_1" and (
                query_word_count > 30 or has_multi_part):
            score = min(100.0, score + 5.0)

        score = max(0.0, min(100.0, round(score, 2)))

        return SignalScore(
            signal_name=SignalName.PROVIDER_CONFIDENCE.value,
            score=score,
            weight=weight,
            contribution=round(score * weight, 4),
            metadata={
                "model_tier": model_tier,
                "tier_reliability": tier_reliability,
                "model_health": model_health,
                "query_word_count": query_word_count,
                "query_unique_tokens": len(query_tokens),
                "has_multi_part_query": has_multi_part,
            },
        )

    # ── Singleton Access ───────────────────────────────────────

    _instance: Optional["ConfidenceScoringEngine"] = None

    @classmethod
    def get_instance(cls) -> "ConfidenceScoringEngine":
        """Get or create the singleton engine instance.

        Returns:
            The shared ConfidenceScoringEngine instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
