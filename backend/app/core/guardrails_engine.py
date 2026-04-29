"""
F-057: Guardrails AI Engine (BC-007, BC-009, BC-010)

Multi-layer safety engine that screens AI responses before they
reach customers. Blocks harmful, off-topic, hallucinated, and
policy-violating responses.

Guardrail Layers:
1. CONTENT_SAFETY -- Blocks harmful/dangerous content
2. TOPIC_RELEVANCE -- Blocks off-topic responses
3. HALLUCINATION_CHECK -- Blocks fabricated information
4. POLICY_COMPLIANCE -- Blocks policy-violating responses
5. TONE_VALIDATION -- Blocks inappropriate tone
6. LENGTH_CONTROL -- Blocks excessively long/short responses
7. PII_LEAK_PREVENTION -- Blocks responses leaking PII
8. CONFIDENCE_GATE -- Blocks low-confidence responses

Day 4 additions (security audit):
9. INFO_LEAK_PREVENTION -- Blocks internal system disclosure (see info_leak_guard.py)
10. PROMPT_INJECTION_OUTPUT -- Scans LLM output for prompt injection remnants
11. PII_OUTPUT_SCAN -- Ensures PII check runs on LLM OUTPUT (not just input)

TODO(Day4): Wire the following Day 4 guardrails into the live AI pipeline:
  - app.core.info_leak_guard.InfoLeakGuard.scan() should be called AFTER
    the LLM generates a response, BEFORE it reaches the customer.
  - app.core.pii_redaction_engine.PIIDetector.detect() should be called
    on LLM OUTPUT to catch any PII the model regurgitates.
  - app.core.prompt_injection_defense.PromptInjectionDetector.scan() should
    be called on LLM OUTPUT to catch injection patterns that may have
    slipped through to the generated text.
  Integration point: the smart_router / ai_pipeline should invoke these
  guards in sequence: PII redaction → prompt injection check → info leak guard →
  guardrails_engine full scan → deliver to customer.

TODO(Day6 — I3): Wire the full GuardrailsEngine to the production AI pipeline.
  Currently guardrails_engine.run_full_scan() is called from test code and
  the blocked_response_manager, but NOT from the live request path
  (smart_router → ai_pipeline → customer).  The integration point is
  app.core.ai_pipeline.AI._stage_response_generation() and
  app.core.smart_router.SmartRouter.process_query().  Add a post-generation
  guardrail step that:
    1. Runs GuardrailsEngine.run_full_scan() on the LLM output
    2. If overall_action == "block", returns a safe fallback response
    3. If overall_action == "flag_for_review", logs and delivers with a
       review flag in the response metadata
  See also: app.core.blocked_response_manager for the blocked-response
  handling flow and BC-009 approval workflow.

BC-001: All checks scoped by company_id.
BC-007: All AI through Smart Router.
BC-009: Approval workflow for blocked responses.
BC-010: Data lifecycle compliance.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from app.logger import get_logger

logger = get_logger("guardrails_engine")


# ══════════════════════════════════════════════════════════════════
# COMPILED REGEX PATTERNS (module-level, never recompiled)
# ══════════════════════════════════════════════════════════════════


# ── Content Safety Patterns ─────────────────────────────────────

# Severity: CRITICAL
_RE_HATE_SPEECH = re.compile(
    r"\b(hate\s*speech|racial slur|ethnic cleansing|white supremacy|"
    r"black supremacy|master race|ethnic purity|genocide|ethnic hatred|"
    r"racial superiority|neo.?nazi|racial segregation)\b",
    re.IGNORECASE,
)

_RE_VIOLENCE_GRAPHIC = re.compile(
    r"\b(mass murder|serial killer|torture method|how to kill|"
    r"bomb making|make a bomb|weaponize|bioweapon|chemical weapon|"
    r"murder someone|torture someone|behead|dismember)\b",
    re.IGNORECASE,
)

_RE_SELF_HARM = re.compile(
    r"\b(kill myself|end my life|suicide method|how to hang|"
    r"self.?harm method|cut myself|overdose intentionally|"
    r"suicide plan|ways to die|painless death)\b",
    re.IGNORECASE,
)

_RE_CHILD_EXPLOITATION = re.compile(
    r"\b(child pornography|child exploitation|underage exploitation|minor abuse|"
    r"pedophil|child grooming|child sex|sex with minor)\b",
    re.IGNORECASE,
)

# Severity: HIGH
_RE_ILLEGAL_ACTIVITIES = re.compile(
    r"\b(drug manufacturing|how to make meth|cocaine recipe|"
    r"money laundering scheme|identity theft how|credit card fraud|"
    r"hack into|bypass security|steal data|blackmail|extortion|"
    r"counterfeit currency|illegal weapons|sell drugs online)\b",
    re.IGNORECASE,
)

_RE_SEXUAL_CONTENT_EXPLICIT = re.compile(
    r"\b(hardcore porn|explicit sexual|pornographic|xxx\s+content|"
    r"naked photos|nude photos|sex tape|erotic content explicit|"
    r"orgasm|porn video)\b",
    re.IGNORECASE,
)

# Severity: MEDIUM
_RE_VIOLENCE_MODERATE = re.compile(
    r"\b(beat up|fight someone|physical assault|break bones|"
    r"stab someone|shoot someone|hurt someone badly|"
    r"violent act|use violence)\b",
    re.IGNORECASE,
)

_RE_SEXUAL_CONTENT_MODERATE = re.compile(
    r"\b(sexual suggest|inappropriate touch|dirty talk|"
    r"send nudes|naked picture|sexually explicit)\b",
    re.IGNORECASE,
)

_RE_HATE_SPEECH_MODERATE = re.compile(
    r"\b(racist remark|discriminat|prejudice against|"
    r"bigot|supremacist|chauvinist|sexist remark)\b",
    re.IGNORECASE,
)


# ── Policy Compliance Patterns ──────────────────────────────────

_RE_PRICING_GUARANTEE = re.compile(
    r"\b(we guarantee.*price|price is guaranteed|lowest price guaranteed|"
    r"price match guarantee|we will beat any price|best price promise|"
    r"price lock guarantee|never pay more)\b",
    re.IGNORECASE,
)

_RE_LEGAL_ADVICE = re.compile(
    r"\b(you should sue|legal action against|I recommend you (to )?(file|sue)|"
    r"you have a legal right to|this is legally binding|"
    r"you can take them to court|statute of limitations|"
    r"legal grounds to|pursue legal|consult an attorney|"
    r"hire a lawyer|legal obligation|liable for|sue for damages)\b",
    re.IGNORECASE,
)

_RE_PROFESSIONAL_ADVICE = re.compile(
    r"\b(you should take|I recommend you take|you need medication|"
    r"stop taking.*medication|diagnosis is|you likely have|"
    r"medical condition.*is|prescription for|dosage of|"
    r"side effects include|you are suffering from|treatment for|"
    r"you definitely have|this will cure|medical advice|"
    r"consult your doctor about|diagnosed with)\b",
    re.IGNORECASE,
)

_RE_SLA_PROMISES = re.compile(
    r"\b(we guarantee.*uptime|99\.\d+% uptime|100% uptime|"
    r"zero downtime guaranteed|always available|never go down|"
    r"SLA of \d+%|service level.*guarantee|response within.*seconds guaranteed)\b",
    re.IGNORECASE,
)

_RE_REFUND_PROMISES = re.compile(
    r"\b(full refund guaranteed|money.?back guarantee|we will refund|"
    r"no questions asked refund|guaranteed refund|refund.*any time|"
    r"return.*full amount|100% money back|guaranteed money back|"
    r"guarantee.*refund)\b",
    re.IGNORECASE,
)

_RE_FINANCIAL_CLAIMS = re.compile(
    r"\b(guaranteed return|guaranteed profit|risk.?free investment|"
    r"double your money|get rich quick|sure thing investment|"
    r"can'?t lose.*investment|guaranteed dividend|certain profit|"
    r"financial advice.*is)\b",
    re.IGNORECASE,
)


# ── Tone Validation Patterns ────────────────────────────────────

_RE_AGGRESSIVE_TONE = re.compile(
    r"\b(you'?re being (ridiculous|unreasonable|absurd|stupid)|"
    r"that'?s (nonsense|garbage|bullshit|ridiculous)|"
    r"you (obviously|clearly) don'?t (know|understand)|"
    r"that'?s completely wrong|you'?re wrong about|"
    r"stop wasting (my|our) time|listen to me carefully|"
    r"I don'?t have time for this|get your facts straight)\b",
    re.IGNORECASE,
)

_RE_DISMISSIVE_TONE = re.compile(
    r"\b(that'?s not (our|my) problem|not my (concern|job|responsibility)|"
    r"I don'?t care about|whatever you say|it is what it is|"
    r"deal with it|not interested in hearing|that'?s irrelevant|"
    r"who cares about that|just move on|get over it)\b",
    re.IGNORECASE,
)

_RE_CONDESCENDING_TONE = re.compile(
    r"\b(obviously|clearly|as (anyone|everyone) knows|it'?s quite simple|"
    r"even a child (could|would|knows)|let me explain (this to you|slowly)|"
    r"you should (already )?know (this|that)|simply put(,| for you)|"
    r"I'?m sure (even )?you (can|could)|as I said|like I explained)\b",
    re.IGNORECASE,
)

_RE_OVERLY_CASUAL_SERIOUS = re.compile(
    r"\b(yo|bruh|lol|lmao|rofl|omg|smh|nvm|idk|imo|tbh)\b",
    re.IGNORECASE,
)


# ── PII Detection Patterns ──────────────────────────────────────

_RE_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
)

_RE_PHONE = re.compile(
    r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    r"|\b(?:\+\d{1,3}[-.\s]?)?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b",
)

_RE_SSN = re.compile(
    r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b",
)

_RE_CREDIT_CARD = re.compile(
    r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
)

_RE_DATE_OF_BIRTH = re.compile(
    r"\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b",
)

_RE_STREET_ADDRESS = re.compile(
    r"\b\d+\s+[A-Za-z]+\s+(Street|St|Avenue|Ave|Boulevard|Blvd|"
    r"Road|Rd|Lane|Ln|Drive|Dr|Court|Ct|Way|Place|Pl)\b",
    re.IGNORECASE,
)

_RE_PASSPORT_NUMBER = re.compile(
    r"\b[A-Z][A-Z]\d{6,8}\b",
)

_RE_IP_ADDRESS = re.compile(
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
)


# ── Hallucination Patterns ──────────────────────────────────────

_RE_HALLUCINATION_MARKERS = re.compile(
    r"\b(as of (my |the )?(latest|last) (update|training|knowledge).*?2024|"
    r"I (recently|just) learned that|according to (my|the) (latest|recent) (data|info)|"
    r"studies (from|in) 2024 (show|suggest|indicate)|"
    r"a (recent|new|latest) (report|study|survey) (from|in) 202[0-4]|"
    r"the (current|latest) version is \d+\.\d+\.?\d*|"
    r"the (official|current) website (is|states)|"
    r"(breaking|just announced|just confirmed) (news|update))\b",
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class GuardrailLayer(str, Enum):
    """All guardrail layer identifiers."""

    CONTENT_SAFETY = "content_safety"
    TOPIC_RELEVANCE = "topic_relevance"
    HALLUCINATION_CHECK = "hallucination_check"
    POLICY_COMPLIANCE = "policy_compliance"
    TONE_VALIDATION = "tone_validation"
    LENGTH_CONTROL = "length_control"
    PII_LEAK_PREVENTION = "pii_leak_prevention"
    CONFIDENCE_GATE = "confidence_gate"


class SeverityLevel(str, Enum):
    """Severity levels for guardrail violations."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GuardAction(str, Enum):
    """Actions the guardrail engine can take."""

    ALLOW = "allow"
    BLOCK = "block"
    FLAG_FOR_REVIEW = "flag_for_review"
    REWRITE = "rewrite"


class StrictnessLevel(str, Enum):
    """How strictly guardrails are applied."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class GuardrailResult:
    """Result of a single guardrail check.

    Attributes:
        passed: Whether the text passed this guard.
        layer: Which guardrail layer produced this result.
        severity: Severity of the violation (if any).
        reason: Human-readable explanation.
        blocked_content: The specific content that triggered the block.
        action: One of "allow", "block", "flag_for_review", "rewrite".
        metadata: Additional structured data about the check.
    """

    passed: bool
    layer: str
    severity: str = "low"
    reason: str = ""
    blocked_content: Optional[str] = None
    action: str = GuardAction.ALLOW.value
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GuardrailConfig:
    """Per-tenant guardrail configuration.

    Attributes:
        company_id: Tenant identifier (BC-001).
        variant_type: PARWA variant (mini_parwa, parwa, high_parwa).
        strictness_level: How strict to apply guards.
        enabled_layers: Which guard layers are active.
        custom_rules: Tenant-specific custom rules.
        blocked_keywords: Additional blocked keyword patterns.
        max_response_length: Maximum allowed response characters.
        min_response_length: Minimum allowed response characters.
        tone_requirements: Allowed tone categories.
        pii_check_enabled: Whether PII leak check is on.
        confidence_threshold: Minimum AI confidence score (0-100).
    """

    company_id: str
    variant_type: str = "parwa"
    strictness_level: str = StrictnessLevel.MEDIUM.value
    enabled_layers: List[str] = field(
        default_factory=lambda: [layer.value for layer in GuardrailLayer]
    )
    custom_rules: List[Dict[str, Any]] = field(default_factory=list)
    blocked_keywords: List[str] = field(default_factory=list)
    max_response_length: int = 2000
    min_response_length: int = 20
    tone_requirements: List[str] = field(
        default_factory=lambda: [
            "professional",
            "empathetic",
        ]
    )
    pii_check_enabled: bool = True
    confidence_threshold: float = 85.0


@dataclass
class GuardrailsReport:
    """Aggregated report from a full guardrail scan.

    Attributes:
        passed: Whether the response passed ALL guardrail checks.
        results: Individual results from each guard layer.
        blocked_count: How many layers returned a BLOCK action.
        flagged_count: How many layers returned a FLAG_FOR_REVIEW action.
        overall_action: The most restrictive action across all layers.
    """

    passed: bool
    results: List[GuardrailResult] = field(default_factory=list)
    blocked_count: int = 0
    flagged_count: int = 0
    overall_action: str = GuardAction.ALLOW.value
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


# ══════════════════════════════════════════════════════════════════
# VARIANT DEFAULTS
# ══════════════════════════════════════════════════════════════════

# Default strictness per variant type:
# Mini PARWA = high (most cautious, limited AI)
# PARWA = medium (balanced)
# PARWA High = low (more autonomous, enterprise trust)
VARIANT_STRICTNESS: Dict[str, StrictnessLevel] = {
    "mini_parwa": StrictnessLevel.HIGH,
    "parwa": StrictnessLevel.MEDIUM,
    "high_parwa": StrictnessLevel.LOW,
}

# Default confidence thresholds per variant:
# Mini PARWA = 95 (needs high confidence)
# PARWA = 85 (standard)
# PARWA High = 75 (more autonomous, can handle uncertainty)
VARIANT_CONFIDENCE_THRESHOLDS: Dict[str, float] = {
    "mini_parwa": 95.0,
    "parwa": 85.0,
    "high_parwa": 75.0,
}

# Strictness-to-action mapping (controls how violations are handled)
STRICTNESS_ACTION_MAP: Dict[str, Dict[str, str]] = {
    StrictnessLevel.LOW.value: {
        SeverityLevel.LOW.value: GuardAction.FLAG_FOR_REVIEW.value,
        SeverityLevel.MEDIUM.value: GuardAction.FLAG_FOR_REVIEW.value,
        SeverityLevel.HIGH.value: GuardAction.BLOCK.value,
        SeverityLevel.CRITICAL.value: GuardAction.BLOCK.value,
    },
    StrictnessLevel.MEDIUM.value: {
        SeverityLevel.LOW.value: GuardAction.FLAG_FOR_REVIEW.value,
        SeverityLevel.MEDIUM.value: GuardAction.BLOCK.value,
        SeverityLevel.HIGH.value: GuardAction.BLOCK.value,
        SeverityLevel.CRITICAL.value: GuardAction.BLOCK.value,
    },
    StrictnessLevel.HIGH.value: {
        SeverityLevel.LOW.value: GuardAction.BLOCK.value,
        SeverityLevel.MEDIUM.value: GuardAction.BLOCK.value,
        SeverityLevel.HIGH.value: GuardAction.BLOCK.value,
        SeverityLevel.CRITICAL.value: GuardAction.BLOCK.value,
    },
}


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def _resolve_action(severity: str, strictness: str) -> str:
    """Determine the guard action based on severity and strictness.

    Args:
        severity: The severity level of the violation.
        strictness: The configured strictness level.

    Returns:
        Action string: "allow", "block", "flag_for_review", or "rewrite".
    """
    strictness_map = STRICTNESS_ACTION_MAP.get(strictness, {})
    return strictness_map.get(severity, GuardAction.BLOCK.value)


def _tokenize(text: str) -> Set[str]:
    """Simple whitespace + punctuation tokenizer for keyword overlap.

    Converts text to lowercase, splits on non-alphanumeric, and
    returns a set of tokens (filtering out very short ones).

    Args:
        text: The text to tokenize.

    Returns:
        Set of unique tokens with length >= 3.
    """
    tokens = re.split(r"[^a-zA-Z0-9]+", text.lower())
    return {t for t in tokens if len(t) >= 3}


def _build_config(
    company_id: str,
    variant_type: str,
    override_config: Optional[GuardrailConfig] = None,
) -> GuardrailConfig:
    """Build a GuardrailConfig with variant-appropriate defaults.

    If override_config is provided, uses it as the base (merging
    variant defaults for any unset fields).

    Args:
        company_id: Tenant identifier.
        variant_type: PARWA variant type.
        override_config: Optional config overrides.

    Returns:
        Fully resolved GuardrailConfig.
    """
    # Get variant defaults
    strictness = VARIANT_STRICTNESS.get(
        variant_type,
        StrictnessLevel.MEDIUM,
    )
    confidence = VARIANT_CONFIDENCE_THRESHOLDS.get(
        variant_type,
        85.0,
    )

    if override_config is not None:
        # GAP FIX: Merge variant defaults with override_config.
        # Previously returned override as-is, losing variant-specific
        # confidence_threshold when only strictness_level was overridden.
        merged = GuardrailConfig(
            company_id=override_config.company_id or company_id,
            variant_type=override_config.variant_type or variant_type,
            strictness_level=override_config.strictness_level or strictness.value,
            enabled_layers=(
                override_config.enabled_layers
                if override_config.enabled_layers
                else [layer.value for layer in GuardrailLayer]
            ),
            custom_rules=override_config.custom_rules,
            blocked_keywords=override_config.blocked_keywords,
            max_response_length=(
                override_config.max_response_length
                if override_config.max_response_length != 2000
                else 2000
            ),
            min_response_length=(
                override_config.min_response_length
                if override_config.min_response_length != 20
                else 20
            ),
            tone_requirements=(
                override_config.tone_requirements
                if override_config.tone_requirements
                else ["professional", "empathetic"]
            ),
            pii_check_enabled=override_config.pii_check_enabled,
            confidence_threshold=(
                override_config.confidence_threshold
                if override_config.confidence_threshold != 85.0
                else confidence
            ),
        )
        return merged

    return GuardrailConfig(
        company_id=company_id,
        variant_type=variant_type,
        strictness_level=strictness.value,
        confidence_threshold=confidence,
    )


# ══════════════════════════════════════════════════════════════════
# INDIVIDUAL GUARD CLASSES
# ══════════════════════════════════════════════════════════════════


class ContentSafetyGuard:
    """Blocks harmful, dangerous, and policy-violating content.

    Categories checked:
    - Hate speech (CRITICAL / MEDIUM)
    - Violence (CRITICAL / MEDIUM)
    - Self-harm (CRITICAL)
    - Child exploitation (CRITICAL)
    - Illegal activities (HIGH)
    - Sexual content (HIGH / MEDIUM)

    Uses keyword + pattern matching. No external NLP APIs.
    """

    LAYER_NAME: str = GuardrailLayer.CONTENT_SAFETY.value

    # (compiled_regex, severity, category_description)
    _PATTERNS: List[tuple] = [
        (_RE_HATE_SPEECH, SeverityLevel.CRITICAL.value, "hate speech"),
        (_RE_VIOLENCE_GRAPHIC, SeverityLevel.CRITICAL.value, "graphic violence"),
        (_RE_SELF_HARM, SeverityLevel.CRITICAL.value, "self-harm"),
        (_RE_CHILD_EXPLOITATION, SeverityLevel.CRITICAL.value, "child exploitation"),
        (_RE_ILLEGAL_ACTIVITIES, SeverityLevel.HIGH.value, "illegal activities"),
        (
            _RE_SEXUAL_CONTENT_EXPLICIT,
            SeverityLevel.HIGH.value,
            "explicit sexual content",
        ),
        (_RE_VIOLENCE_MODERATE, SeverityLevel.MEDIUM.value, "moderate violence"),
        (
            _RE_SEXUAL_CONTENT_MODERATE,
            SeverityLevel.MEDIUM.value,
            "moderate sexual content",
        ),
        (_RE_HATE_SPEECH_MODERATE, SeverityLevel.MEDIUM.value, "moderate hate speech"),
    ]

    def check(
        self,
        text: str,
        config: GuardrailConfig,
    ) -> GuardrailResult:
        """Check text for harmful content.

        Args:
            text: The AI response text to check.
            config: Tenant-specific guardrail configuration.

        Returns:
            GuardrailResult with pass/block outcome.
        """
        if not text or not text.strip():
            return GuardrailResult(
                passed=True,
                layer=self.LAYER_NAME,
                reason="Empty text, nothing to check",
            )

        # Also check tenant-specific blocked keywords
        for keyword in config.blocked_keywords:
            if keyword and keyword.lower() in text.lower():
                return GuardrailResult(
                    passed=False,
                    layer=self.LAYER_NAME,
                    severity=SeverityLevel.HIGH.value,
                    reason=f"Blocked keyword detected: '{keyword}'",
                    blocked_content=keyword,
                    action=_resolve_action(
                        SeverityLevel.HIGH.value,
                        config.strictness_level,
                    ),
                    metadata={"category": "custom_blocked_keyword"},
                )

        # Check custom rules
        for rule in config.custom_rules:
            if rule.get("layer") != self.LAYER_NAME:
                continue
            pattern = rule.get("pattern")
            if pattern and isinstance(pattern, str):
                try:
                    if re.search(pattern, text, re.IGNORECASE):
                        rule_severity = rule.get(
                            "severity",
                            SeverityLevel.HIGH.value,
                        )
                        return GuardrailResult(
                            passed=False,
                            layer=self.LAYER_NAME,
                            severity=rule_severity,
                            reason=rule.get(
                                "reason",
                                f"Custom rule matched: {pattern}",
                            ),
                            blocked_content=pattern,
                            action=_resolve_action(
                                rule_severity,
                                config.strictness_level,
                            ),
                            metadata={"category": "custom_rule", "rule": rule},
                        )
                except re.error:
                    logger.warning(
                        "Invalid custom rule regex pattern: %s",
                        pattern,
                    )

        # Run through all content safety patterns (worst match wins)
        worst_match: Optional[tuple] = None
        worst_match_text: Optional[str] = None

        for compiled_re, severity, category in self._PATTERNS:
            match = compiled_re.search(text)
            if match:
                if worst_match is None or self._severity_ordinal(
                    severity,
                ) > self._severity_ordinal(worst_match[1]):
                    worst_match = (compiled_re, severity, category)
                    worst_match_text = match.group()

        if worst_match:
            _, severity, category = worst_match
            return GuardrailResult(
                passed=False,
                layer=self.LAYER_NAME,
                severity=severity,
                reason=f"Content safety violation: {category}",
                blocked_content=worst_match_text,
                action=_resolve_action(severity, config.strictness_level),
                metadata={"category": category},
            )

        return GuardrailResult(
            passed=True,
            layer=self.LAYER_NAME,
            reason="No harmful content detected",
        )

    @staticmethod
    def _severity_ordinal(severity: str) -> int:
        """Convert severity to comparable ordinal value."""
        ordinals = {
            SeverityLevel.LOW.value: 1,
            SeverityLevel.MEDIUM.value: 2,
            SeverityLevel.HIGH.value: 3,
            SeverityLevel.CRITICAL.value: 4,
        }
        return ordinals.get(severity, 0)


class TopicRelevanceGuard:
    """Blocks off-topic AI responses.

    Uses keyword overlap scoring between the original query and
    the AI response. Requires a minimum of 30% keyword overlap
    to pass. Also detects potential topic drift.

    BC-007: Ensures AI stays within its domain.
    """

    LAYER_NAME: str = GuardrailLayer.TOPIC_RELEVANCE.value
    MIN_OVERLAP_THRESHOLD: float = 0.30  # 30% of query keywords

    def check(
        self,
        query: str,
        response: str,
        config: GuardrailConfig,
    ) -> GuardrailResult:
        """Check if response is relevant to the original query.

        Args:
            query: The customer's original query.
            response: The AI-generated response.
            config: Tenant-specific guardrail configuration.

        Returns:
            GuardrailResult with pass/block outcome.
        """
        if not query or not query.strip():
            return GuardrailResult(
                passed=True,
                layer=self.LAYER_NAME,
                reason="No query provided, cannot check relevance",
            )

        if not response or not response.strip():
            return GuardrailResult(
                passed=False,
                layer=self.LAYER_NAME,
                severity=SeverityLevel.MEDIUM.value,
                reason="Empty response -- no relevant content",
                action=GuardAction.BLOCK.value,
            )

        query_tokens = _tokenize(query)
        response_tokens = _tokenize(response)

        if not query_tokens:
            return GuardrailResult(
                passed=True,
                layer=self.LAYER_NAME,
                reason="Query has no meaningful tokens for comparison",
            )

        overlap = query_tokens & response_tokens
        overlap_ratio = len(overlap) / len(query_tokens)

        metadata: Dict[str, Any] = {
            "query_token_count": len(query_tokens),
            "response_token_count": len(response_tokens),
            "overlap_token_count": len(overlap),
            "overlap_ratio": round(overlap_ratio, 4),
            "threshold": self.MIN_OVERLAP_THRESHOLD,
        }

        if overlap_ratio < self.MIN_OVERLAP_THRESHOLD:
            severity = (
                SeverityLevel.HIGH.value
                if overlap_ratio < 0.10
                else SeverityLevel.MEDIUM.value
            )
            return GuardrailResult(
                passed=False,
                layer=self.LAYER_NAME,
                severity=severity,
                reason=(
                    "Response has low topic relevance: "
                    f"{overlap_ratio:.1%} keyword overlap "
                    f"(minimum {self.MIN_OVERLAP_THRESHOLD:.0%})"
                ),
                action=_resolve_action(severity, config.strictness_level),
                metadata=metadata,
            )

        return GuardrailResult(
            passed=True,
            layer=self.LAYER_NAME,
            reason=("Response is on-topic: " f"{overlap_ratio:.1%} keyword overlap"),
            metadata=metadata,
        )


class HallucinationCheckGuard:
    """Blocks responses likely containing fabricated information.

    Detects common hallucination patterns such as fabricated
    statistics, fake citations, invented URLs, and overly
    specific claims that signal hallucination.

    Pure Python -- no external NLP libraries.
    """

    LAYER_NAME: str = GuardrailLayer.HALLUCINATION_CHECK.value

    def check(
        self,
        query: str,
        response: str,
        config: GuardrailConfig,
    ) -> GuardrailResult:
        """Check for hallucination markers in the response.

        Args:
            query: The customer's original query (for context).
            response: The AI-generated response.
            config: Tenant-specific guardrail configuration.

        Returns:
            GuardrailResult with pass/block outcome.
        """
        if not response or not response.strip():
            return GuardrailResult(
                passed=True,
                layer=self.LAYER_NAME,
                reason="Empty response, nothing to check",
            )

        hallucination_markers_found: List[str] = []

        # Check for temporal hallucination markers
        match = _RE_HALLUCINATION_MARKERS.search(response)
        if match:
            hallucination_markers_found.append(match.group())

        # Check for fabricated statistics patterns
        fabricated_stat_re = re.compile(
            r"\b\d{1,3}(?:\.\d+)?% (of|increase|decrease|reduction|growth).*?"
            r"(according to|reported by|based on)\s+(?:a |the |our )?"
            r"(recent|latest|new|2024)\b",
            re.IGNORECASE,
        )
        stat_match = fabricated_stat_re.search(response)
        if stat_match:
            hallucination_markers_found.append(stat_match.group())

        # Check for fake URL/citation patterns
        fake_url_re = re.compile(
            r"(?:https?://)?(?:www\.)?" r"[a-z]+\d{4}\.(?:com|org|net|io)\b",
            re.IGNORECASE,
        )
        url_match = fake_url_re.search(response)
        if url_match:
            hallucination_markers_found.append(url_match.group())

        # Check for overly specific uncertain claims
        uncertain_claims_re = re.compile(
            r"\b(I (believe|think|assume|estimate) (that )?"
            r"(the|it|this) (?:exact|precise) (?:number|figure|value|date) is|"
            r"(approximately|roughly|about|around) \d{4,} (customers|users|clients)|"
            r"(studies|research) (show|suggest|indicate|prove) that.*\d+(?:\.\d+)?%)\b",
            re.IGNORECASE,
        )
        uncertain_match = uncertain_claims_re.search(response)
        if uncertain_match:
            hallucination_markers_found.append(uncertain_match.group())

        if hallucination_markers_found:
            severity = SeverityLevel.HIGH.value
            return GuardrailResult(
                passed=False,
                layer=self.LAYER_NAME,
                severity=severity,
                reason=(
                    "Potential hallucination detected: "
                    f"{len(hallucination_markers_found)} marker(s) found"
                ),
                blocked_content="; ".join(hallucination_markers_found[:3]),
                action=_resolve_action(severity, config.strictness_level),
                metadata={
                    "marker_count": len(hallucination_markers_found),
                    "markers": [m[:100] for m in hallucination_markers_found],
                },
            )

        return GuardrailResult(
            passed=True,
            layer=self.LAYER_NAME,
            reason="No hallucination markers detected",
        )


class PolicyComplianceGuard:
    """Blocks responses that violate business policy rules.

    Detects: pricing guarantees, legal advice, professional advice,
    SLA promises, refund promises, and financial claims.

    All patterns are configurable per tenant via custom_rules.
    """

    LAYER_NAME: str = GuardrailLayer.POLICY_COMPLIANCE.value

    # (compiled_regex, severity, category, description)
    _POLICY_PATTERNS: List[tuple] = [
        (
            _RE_PRICING_GUARANTEE,
            SeverityLevel.HIGH.value,
            "pricing_guarantee",
            "Pricing guarantee detected",
        ),
        (
            _RE_LEGAL_ADVICE,
            SeverityLevel.HIGH.value,
            "legal_advice",
            "Legal advice detected",
        ),
        (
            _RE_PROFESSIONAL_ADVICE,
            SeverityLevel.HIGH.value,
            "professional_advice",
            "Professional advice detected",
        ),
        (
            _RE_SLA_PROMISES,
            SeverityLevel.HIGH.value,
            "sla_promise",
            "SLA promise detected",
        ),
        (
            _RE_REFUND_PROMISES,
            SeverityLevel.HIGH.value,
            "refund_promise",
            "Refund guarantee detected",
        ),
        (
            _RE_FINANCIAL_CLAIMS,
            SeverityLevel.HIGH.value,
            "financial_claim",
            "Financial claim detected",
        ),
    ]

    def check(
        self,
        text: str,
        config: GuardrailConfig,
    ) -> GuardrailResult:
        """Check text for policy compliance violations.

        Args:
            text: The AI response text to check.
            config: Tenant-specific guardrail configuration.

        Returns:
            GuardrailResult with pass/block outcome.
        """
        if not text or not text.strip():
            return GuardrailResult(
                passed=True,
                layer=self.LAYER_NAME,
                reason="Empty text, nothing to check",
            )

        violations: List[Dict[str, Any]] = []

        for compiled_re, severity, category, description in self._POLICY_PATTERNS:
            match = compiled_re.search(text)
            if match:
                violations.append(
                    {
                        "pattern_match": match.group(),
                        "severity": severity,
                        "category": category,
                        "description": description,
                    }
                )

        # Check tenant custom rules
        for rule in config.custom_rules:
            if rule.get("layer") != self.LAYER_NAME:
                continue
            pattern = rule.get("pattern")
            if pattern and isinstance(pattern, str):
                try:
                    if re.search(pattern, text, re.IGNORECASE):
                        violations.append(
                            {
                                "pattern_match": pattern,
                                "severity": rule.get(
                                    "severity",
                                    SeverityLevel.HIGH.value,
                                ),
                                "category": "custom_rule",
                                "description": rule.get(
                                    "reason",
                                    "Custom policy rule",
                                ),
                            }
                        )
                except re.error:
                    logger.warning(
                        "Invalid custom policy regex: %s",
                        pattern,
                    )

        if violations:
            # Use the highest severity violation
            worst = max(
                violations,
                key=lambda v: ContentSafetyGuard._severity_ordinal(
                    v["severity"],
                ),
            )
            return GuardrailResult(
                passed=False,
                layer=self.LAYER_NAME,
                severity=worst["severity"],
                reason=(
                    f"Policy compliance violation: {worst['description']}. "
                    f"{len(violations)} violation(s) found."
                ),
                blocked_content=worst["pattern_match"],
                action=_resolve_action(
                    worst["severity"],
                    config.strictness_level,
                ),
                metadata={
                    "violations": violations,
                    "violation_count": len(violations),
                },
            )

        return GuardrailResult(
            passed=True,
            layer=self.LAYER_NAME,
            reason="No policy compliance violations detected",
        )


class ToneValidationGuard:
    """Validates that AI response tone matches requirements.

    Detects: aggressive, dismissive, condescending, and
    overly casual (for serious topics) tone patterns.

    Tone categories: professional, empathetic, urgent, casual.
    """

    LAYER_NAME: str = GuardrailLayer.TONE_VALIDATION.value

    # (compiled_regex, tone_category, description)
    _TONE_PATTERNS: List[tuple] = [
        (_RE_AGGRESSIVE_TONE, "aggressive", "Aggressive tone detected"),
        (_RE_DISMISSIVE_TONE, "dismissive", "Dismissive tone detected"),
        (_RE_CONDESCENDING_TONE, "condescending", "Condescending tone detected"),
        (_RE_OVERLY_CASUAL_SERIOUS, "overly_casual", "Overly casual language detected"),
    ]

    # Tone categories that are generally considered serious
    _SERIOUS_TONES: Set[str] = {"professional", "empathetic", "urgent"}

    def check(
        self,
        text: str,
        config: GuardrailConfig,
    ) -> GuardrailResult:
        """Check text for inappropriate tone.

        Args:
            text: The AI response text to check.
            config: Tenant-specific guardrail configuration.

        Returns:
            GuardrailResult with pass/block outcome.
        """
        if not text or not text.strip():
            return GuardrailResult(
                passed=True,
                layer=self.LAYER_NAME,
                reason="Empty text, nothing to check",
            )

        tone_violations: List[Dict[str, Any]] = []

        for compiled_re, tone_category, description in self._TONE_PATTERNS:
            match = compiled_re.search(text)
            if match:
                # Casual tone is only a violation if the context
                # requires a serious tone
                if tone_category == "overly_casual":
                    if self._SERIOUS_TONES.intersection(config.tone_requirements):
                        tone_violations.append(
                            {
                                "match": match.group(),
                                "tone_category": tone_category,
                                "description": description,
                                "severity": SeverityLevel.MEDIUM.value,
                            }
                        )
                else:
                    severity = (
                        SeverityLevel.HIGH.value
                        if tone_category in ("aggressive", "dismissive")
                        else SeverityLevel.MEDIUM.value
                    )
                    tone_violations.append(
                        {
                            "match": match.group(),
                            "tone_category": tone_category,
                            "description": description,
                            "severity": severity,
                        }
                    )

        if tone_violations:
            worst = max(
                tone_violations,
                key=lambda v: ContentSafetyGuard._severity_ordinal(
                    v["severity"],
                ),
            )
            return GuardrailResult(
                passed=False,
                layer=self.LAYER_NAME,
                severity=worst["severity"],
                reason=(
                    f"Tone violation: {worst['description']}. "
                    f"{len(tone_violations)} issue(s) found."
                ),
                blocked_content=worst["match"],
                action=_resolve_action(
                    worst["severity"],
                    config.strictness_level,
                ),
                metadata={
                    "violations": tone_violations,
                    "required_tones": config.tone_requirements,
                },
            )

        return GuardrailResult(
            passed=True,
            layer=self.LAYER_NAME,
            reason="Tone is appropriate",
            metadata={"required_tones": config.tone_requirements},
        )


class LengthControlGuard:
    """Enforces response length boundaries.

    Flags wall-of-text responses (>500 chars by default) and
    responses that are too short to be helpful (<20 chars).
    Configurable per tenant via max/min_response_length.
    """

    LAYER_NAME: str = GuardrailLayer.LENGTH_CONTROL.value
    # Internal thresholds that override tenant config only
    # if tenant hasn't set them explicitly
    DEFAULT_WALL_OF_TEXT_THRESHOLD: int = 500
    DEFAULT_TOO_SHORT_THRESHOLD: int = 20

    def check(
        self,
        text: str,
        config: GuardrailConfig,
    ) -> GuardrailResult:
        """Check response length against configured limits.

        Args:
            text: The AI response text to check.
            config: Tenant-specific guardrail configuration.

        Returns:
            GuardrailResult with pass/block outcome.
        """
        if not text or not text.strip():
            return GuardrailResult(
                passed=False,
                layer=self.LAYER_NAME,
                severity=SeverityLevel.MEDIUM.value,
                reason="Empty response",
                action=GuardAction.BLOCK.value,
                metadata={"length": 0},
            )

        length = len(text.strip())
        max_len = config.max_response_length
        min_len = config.min_response_length

        metadata: Dict[str, Any] = {
            "length": length,
            "max_length": max_len,
            "min_length": min_len,
        }

        if length > max_len:
            return GuardrailResult(
                passed=False,
                layer=self.LAYER_NAME,
                severity=(
                    SeverityLevel.HIGH.value
                    if length > max_len * 2
                    else SeverityLevel.MEDIUM.value
                ),
                reason=(
                    "Response exceeds maximum length: "
                    f"{length} chars (max {max_len})"
                ),
                action=_resolve_action(
                    SeverityLevel.MEDIUM.value,
                    config.strictness_level,
                ),
                metadata=metadata,
            )

        if length < min_len:
            return GuardrailResult(
                passed=False,
                layer=self.LAYER_NAME,
                severity=SeverityLevel.MEDIUM.value,
                reason=(
                    "Response below minimum length: " f"{length} chars (min {min_len})"
                ),
                action=_resolve_action(
                    SeverityLevel.MEDIUM.value,
                    config.strictness_level,
                ),
                metadata=metadata,
            )

        # Flag wall-of-text even if under absolute max
        if length > self.DEFAULT_WALL_OF_TEXT_THRESHOLD:
            return GuardrailResult(
                passed=True,
                layer=self.LAYER_NAME,
                severity=SeverityLevel.LOW.value,
                reason=(
                    "Response is a wall-of-text: "
                    f"{length} chars (flagged, not blocked)"
                ),
                action=GuardAction.FLAG_FOR_REVIEW.value,
                metadata={**metadata, "flag": "wall_of_text"},
            )

        return GuardrailResult(
            passed=True,
            layer=self.LAYER_NAME,
            reason=f"Response length OK: {length} chars",
            metadata=metadata,
        )


class PIILeakGuard:
    """Detects if AI response contains PII that shouldn't be exposed.

    Uses regex patterns from pii_redaction_engine to detect:
    - Email addresses
    - Phone numbers
    - SSN numbers
    - Credit card numbers
    - Dates of birth
    - Street addresses
    - Passport numbers
    - IP addresses

    Flags responses that include customer PII unnecessarily.
    """

    LAYER_NAME: str = GuardrailLayer.PII_LEAK_PREVENTION.value

    # (compiled_regex, pii_category)
    _PII_PATTERNS: List[tuple] = [
        (_RE_EMAIL, "email"),
        (_RE_PHONE, "phone"),
        (_RE_SSN, "ssn"),
        (_RE_CREDIT_CARD, "credit_card"),
        (_RE_DATE_OF_BIRTH, "date_of_birth"),
        (_RE_STREET_ADDRESS, "street_address"),
        (_RE_PASSPORT_NUMBER, "passport"),
        (_RE_IP_ADDRESS, "ip_address"),
    ]

    def check(
        self,
        text: str,
        config: GuardrailConfig,
    ) -> GuardrailResult:
        """Check text for PII leakage.

        Args:
            text: The AI response text to check.
            config: Tenant-specific guardrail configuration.

        Returns:
            GuardrailResult with pass/block outcome.
        """
        if not config.pii_check_enabled:
            return GuardrailResult(
                passed=True,
                layer=self.LAYER_NAME,
                reason="PII check disabled for this tenant",
                metadata={"pii_check_enabled": False},
            )

        if not text or not text.strip():
            return GuardrailResult(
                passed=True,
                layer=self.LAYER_NAME,
                reason="Empty text, nothing to check",
            )

        pii_findings: List[Dict[str, Any]] = []

        for compiled_re, category in self._PII_PATTERNS:
            matches = compiled_re.findall(text)
            for match_text in matches:
                # Mask the match for safety in logs
                masked = self._mask_value(str(match_text), category)
                pii_findings.append(
                    {
                        "category": category,
                        "masked_value": masked,
                        "raw_length": len(str(match_text)),
                    }
                )

        if pii_findings:
            # High severity for sensitive PII (SSN, credit card)
            sensitive_categories = {"ssn", "credit_card", "passport"}
            has_sensitive = any(
                f["category"] in sensitive_categories for f in pii_findings
            )
            severity = (
                SeverityLevel.HIGH.value
                if has_sensitive
                else SeverityLevel.MEDIUM.value
            )
            return GuardrailResult(
                passed=False,
                layer=self.LAYER_NAME,
                severity=severity,
                reason=(
                    "PII detected in response: "
                    f"{len(pii_findings)} finding(s) across "
                    f"{len(set(f['category'] for f in pii_findings))} "
                    "category(ies)"
                ),
                blocked_content="; ".join(f["category"] for f in pii_findings),
                action=_resolve_action(severity, config.strictness_level),
                metadata={
                    "pii_findings": pii_findings,
                    "finding_count": len(pii_findings),
                    "categories": list({f["category"] for f in pii_findings}),
                    "has_sensitive_pii": has_sensitive,
                },
            )

        return GuardrailResult(
            passed=True,
            layer=self.LAYER_NAME,
            reason="No PII detected in response",
        )

    @staticmethod
    def _mask_value(value: str, category: str) -> str:
        """Mask PII value for safe logging.

        Args:
            value: The raw PII value.
            category: The PII category.

        Returns:
            Masked version safe for logging.
        """
        if category == "ssn":
            return "***-**-" + value[-4:] if len(value) >= 4 else "***"
        if category == "credit_card":
            return "****-****-****-" + value[-4:] if len(value) >= 4 else "****"
        if category == "email":
            parts = value.split("@")
            if len(parts) == 2:
                name = parts[0]
                return name[0] + "***@" + parts[1]
            return "***"
        if category == "phone":
            return "***-***-" + value[-4:] if len(value) >= 4 else "***"
        if category == "passport":
            return value[:2] + "******" if len(value) > 4 else "******"
        # Default: show first 2 chars, mask rest
        return value[:2] + "***" if len(value) > 2 else "***"


class ConfidenceGateGuard:
    """Blocks responses below the confidence threshold.

    The AI model provides a confidence score for each response.
    Responses below the threshold are blocked or flagged.

    Default thresholds per variant:
    - Mini PARWA: 95 (needs high confidence)
    - PARWA: 85 (standard)
    - PARWA High: 75 (more autonomous)
    """

    LAYER_NAME: str = GuardrailLayer.CONFIDENCE_GATE.value

    def check(
        self,
        confidence_score: float,
        config: GuardrailConfig,
    ) -> GuardrailResult:
        """Check if response confidence meets the threshold.

        Args:
            confidence_score: AI confidence score (0.0 to 100.0).
            config: Tenant-specific guardrail configuration.

        Returns:
            GuardrailResult with pass/block outcome.
        """
        threshold = config.confidence_threshold

        metadata: Dict[str, Any] = {
            "confidence_score": round(confidence_score, 2),
            "threshold": threshold,
            "gap": round(confidence_score - threshold, 2),
        }

        if confidence_score < threshold:
            gap = threshold - confidence_score
            # Severity depends on how far below threshold
            if gap > 30:
                severity = SeverityLevel.HIGH.value
                reason = (
                    f"Very low confidence: {confidence_score:.1f}% "
                    f"(threshold {threshold:.1f}%, gap {gap:.1f})"
                )
            elif gap > 15:
                severity = SeverityLevel.MEDIUM.value
                reason = (
                    f"Low confidence: {confidence_score:.1f}% "
                    f"(threshold {threshold:.1f}%, gap {gap:.1f})"
                )
            else:
                severity = SeverityLevel.LOW.value
                reason = (
                    f"Below confidence threshold: {confidence_score:.1f}% "
                    f"(threshold {threshold:.1f}%, gap {gap:.1f})"
                )

            action = _resolve_action(severity, config.strictness_level)
            # Low strictness: flag for review instead of block for
            # small gaps
            if (
                config.strictness_level == StrictnessLevel.LOW.value
                and severity == SeverityLevel.LOW.value
            ):
                action = GuardAction.FLAG_FOR_REVIEW.value

            return GuardrailResult(
                passed=False,
                layer=self.LAYER_NAME,
                severity=severity,
                reason=reason,
                action=action,
                metadata=metadata,
            )

        return GuardrailResult(
            passed=True,
            layer=self.LAYER_NAME,
            reason=(
                f"Confidence OK: {confidence_score:.1f}% "
                f"(threshold {threshold:.1f}%)"
            ),
            metadata=metadata,
        )


# ══════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════


class GuardrailsEngine:
    """Main orchestrator that runs all enabled guard layers.

    Executes guards in a defined order, short-circuiting on
    the first BLOCK action. Aggregates all results into a
    GuardrailsReport.

    BC-001: All checks scoped by company_id.
    BC-007: AI responses screened before delivery.
    BC-009: Blocked responses logged for approval workflow.
    BC-010: Data lifecycle compliance (log retention).
    """

    def __init__(self) -> None:
        """Initialize the engine with all guard instances."""
        self._content_safety = ContentSafetyGuard()
        self._topic_relevance = TopicRelevanceGuard()
        self._hallucination_check = HallucinationCheckGuard()
        self._policy_compliance = PolicyComplianceGuard()
        self._tone_validation = ToneValidationGuard()
        self._length_control = LengthControlGuard()
        self._pii_leak = PIILeakGuard()
        self._confidence_gate = ConfidenceGateGuard()

        # Guard registry: layer -> (guard_instance, needs_query)
        self._guards: Dict[
            str,
            tuple[Any, bool],
        ] = {
            GuardrailLayer.CONTENT_SAFETY.value: (
                self._content_safety,
                False,
            ),
            GuardrailLayer.TOPIC_RELEVANCE.value: (
                self._topic_relevance,
                True,
            ),
            GuardrailLayer.HALLUCINATION_CHECK.value: (
                self._hallucination_check,
                True,
            ),
            GuardrailLayer.POLICY_COMPLIANCE.value: (
                self._policy_compliance,
                False,
            ),
            GuardrailLayer.TONE_VALIDATION.value: (
                self._tone_validation,
                False,
            ),
            GuardrailLayer.LENGTH_CONTROL.value: (
                self._length_control,
                False,
            ),
            GuardrailLayer.PII_LEAK_PREVENTION.value: (
                self._pii_leak,
                False,
            ),
            GuardrailLayer.CONFIDENCE_GATE.value: (
                self._confidence_gate,
                False,
            ),
        }

        logger.info(
            "Guardrails Engine initialized with %d layers",
            len(self._guards),
        )

    # ── Public API ──────────────────────────────────────────────

    def run_full_check(
        self,
        query: str,
        response: str,
        confidence: float,
        company_id: str,
        variant_type: str = "parwa",
        config: Optional[GuardrailConfig] = None,
    ) -> GuardrailsReport:
        """Run all enabled guard layers on an AI response.

        Args:
            query: The customer's original query.
            response: The AI-generated response.
            confidence: AI confidence score (0-100).
            company_id: Tenant identifier (BC-001).
            variant_type: PARWA variant type.
            config: Optional tenant config override.

        Returns:
            GuardrailsReport with all results and overall pass/fail.
        """
        guard_config = _build_config(company_id, variant_type, config)
        report = GuardrailsReport(passed=True)

        enabled_layers = set(guard_config.enabled_layers)

        for layer_name, (guard_instance, needs_query) in self._guards.items():
            # Skip disabled layers
            if layer_name not in enabled_layers:
                continue

            try:
                result = self._run_single_guard(
                    guard_instance=guard_instance,
                    layer_name=layer_name,
                    needs_query=needs_query,
                    query=query,
                    response=response,
                    confidence=confidence,
                    config=guard_config,
                )
            except Exception:
                # BC-008: Never crash. Log and continue.
                logger.exception(
                    "Guard layer %s raised an exception " "(company_id=%s, variant=%s)",
                    layer_name,
                    company_id,
                    variant_type,
                )
                result = GuardrailResult(
                    passed=True,
                    layer=layer_name,
                    reason=f"Guard {layer_name} failed internally, allowed by default",
                    metadata={"internal_error": True},
                )

            report.results.append(result)

            # Track counts
            if result.action == GuardAction.BLOCK.value:
                report.blocked_count += 1
            elif result.action == GuardAction.FLAG_FOR_REVIEW.value:
                report.flagged_count += 1

            # Short-circuit on first BLOCK
            if result.action == GuardAction.BLOCK.value:
                report.passed = False
                report.overall_action = GuardAction.BLOCK.value
                logger.warning(
                    "Guardrail BLOCK by %s (company_id=%s): %s",
                    layer_name,
                    company_id,
                    result.reason,
                )
                break
            elif result.action == GuardAction.FLAG_FOR_REVIEW.value:
                # Flag doesn't short-circuit, but note it
                if report.overall_action == GuardAction.ALLOW.value:
                    report.overall_action = GuardAction.FLAG_FOR_REVIEW.value

        # Final determination
        if report.passed and report.flagged_count > 0:
            report.overall_action = GuardAction.FLAG_FOR_REVIEW.value

        logger.info(
            "Guardrails check complete (company_id=%s, variant=%s): "
            "passed=%s, blocked=%d, flagged=%d, action=%s",
            company_id,
            variant_type,
            report.passed,
            report.blocked_count,
            report.flagged_count,
            report.overall_action,
        )

        return report

    def run_single_layer(
        self,
        layer_name: str,
        query: str,
        response: str,
        confidence: float,
        company_id: str,
        variant_type: str = "parwa",
        config: Optional[GuardrailConfig] = None,
    ) -> GuardrailResult:
        """Run a single guard layer (for targeted re-checks).

        Args:
            layer_name: The specific guard layer to run.
            query: The customer's original query.
            response: The AI-generated response.
            confidence: AI confidence score (0-100).
            company_id: Tenant identifier (BC-001).
            variant_type: PARWA variant type.
            config: Optional tenant config override.

        Returns:
            GuardrailResult from the single layer.

        Raises:
            ValueError: If layer_name is not a valid layer.
        """
        if layer_name not in self._guards:
            raise ValueError(
                f"Unknown guard layer: {layer_name}. "
                f"Valid layers: {list(self._guards.keys())}"
            )

        guard_instance, needs_query = self._guards[layer_name]
        guard_config = _build_config(company_id, variant_type, config)

        return self._run_single_guard(
            guard_instance=guard_instance,
            layer_name=layer_name,
            needs_query=needs_query,
            query=query,
            response=response,
            confidence=confidence,
            config=guard_config,
        )

    def get_config_for_variant(
        self,
        company_id: str,
        variant_type: str,
    ) -> GuardrailConfig:
        """Get the default config for a variant type.

        Args:
            company_id: Tenant identifier.
            variant_type: PARWA variant type.

        Returns:
            GuardrailConfig with variant-appropriate defaults.
        """
        return _build_config(company_id, variant_type)

    # ── Internal Methods ────────────────────────────────────────

    @staticmethod
    def _run_single_guard(
        guard_instance: Any,
        layer_name: str,
        needs_query: bool,
        query: str,
        response: str,
        confidence: float,
        config: GuardrailConfig,
    ) -> GuardrailResult:
        """Dispatch to the appropriate guard check method.

        Args:
            guard_instance: The guard class instance.
            layer_name: Name of the guard layer.
            needs_query: Whether this guard requires the query.
            query: Customer query text.
            response: AI response text.
            confidence: AI confidence score.
            config: Tenant guardrail configuration.

        Returns:
            GuardrailResult from the guard.
        """
        # Confidence gate uses its own interface
        if layer_name == GuardrailLayer.CONFIDENCE_GATE.value:
            return guard_instance.check(confidence, config)

        # Guards that need both query and response
        if needs_query:
            return guard_instance.check(query, response, config)

        # Guards that only need the response text
        return guard_instance.check(response, config)


# ══════════════════════════════════════════════════════════════════
# BLOCKED RESPONSE MANAGER
# ══════════════════════════════════════════════════════════════════


class BlockedResponseManager:
    """Manages blocked AI responses for approval workflow.

    Logs blocked responses to Redis for BC-009 approval workflow
    and BC-010 data lifecycle compliance.

    Redis keys follow tenant-scoped pattern:
        parwa:{company_id}:guardrails:blocked:{entry_id}

    BC-001: All data scoped by company_id.
    BC-009: Approval workflow integration.
    BC-010: Data lifecycle (TTL-based retention).
    """

    # Redis key pattern
    BLOCKED_KEY_PREFIX = "guardrails:blocked"
    STATS_KEY = "guardrails:stats"
    # TTL for blocked entries: 90 days (BC-010 compliance)
    BLOCKED_ENTRY_TTL = 90 * 24 * 60 * 60  # seconds

    async def log_blocked(
        self,
        company_id: str,
        query: str,
        response: str,
        guard_result: GuardrailResult,
        variant_type: str,
    ) -> str:
        """Log a blocked response for approval workflow.

        Args:
            company_id: Tenant identifier (BC-001).
            query: The customer's original query.
            response: The blocked AI response.
            guard_result: The guardrail result that caused the block.
            variant_type: PARWA variant type.

        Returns:
            The entry ID for the blocked response record.
        """
        entry_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        entry: Dict[str, Any] = {
            "entry_id": entry_id,
            "company_id": company_id,
            "query": query[:500],  # Truncate for storage
            "response": response[:2000],  # Truncate for storage
            "layer": guard_result.layer,
            "severity": guard_result.severity,
            "reason": guard_result.reason,
            "action": guard_result.action,
            "variant_type": variant_type,
            "created_at": now,
            "status": "pending_review",  # BC-009
            "metadata": guard_result.metadata,
        }

        try:
            from app.core.redis import get_redis, make_key

            redis = await get_redis()
            key = make_key(
                company_id,
                self.BLOCKED_KEY_PREFIX,
                entry_id,
            )
            serialized = json.dumps(entry, default=str)
            await redis.set(
                key,
                serialized,
                ex=self.BLOCKED_ENTRY_TTL,
            )

            # Increment stats counter
            await self._increment_stats(redis, company_id, guard_result)

            logger.info(
                "Blocked response logged (company_id=%s, entry=%s, "
                "layer=%s, action=%s)",
                company_id,
                entry_id,
                guard_result.layer,
                guard_result.action,
            )
        except Exception:
            logger.exception(
                "Failed to log blocked response to Redis " "(company_id=%s, layer=%s)",
                company_id,
                guard_result.layer,
            )

        return entry_id

    async def get_blocked_list(
        self,
        company_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get a paginated list of blocked responses.

        Args:
            company_id: Tenant identifier (BC-001).
            limit: Maximum entries to return.
            offset: Number of entries to skip.

        Returns:
            List of blocked response entries.
        """
        try:
            from app.core.redis import get_redis, make_key

            redis = await get_redis()
            pattern = make_key(
                company_id,
                self.BLOCKED_KEY_PREFIX,
                "*",
            )
            keys = []
            async for key in redis.scan_iter(match=pattern, count=100):
                keys.append(key)

            # Sort keys (most recent first — Redis returns unordered)
            keys.sort(reverse=True)

            # Paginate
            paginated_keys = keys[offset : offset + limit]

            entries: List[Dict[str, Any]] = []
            for key in paginated_keys:
                try:
                    raw = await redis.get(key)
                    if raw:
                        entry = json.loads(raw)
                        # Don't return full response in list
                        entry.pop("response", None)
                        entries.append(entry)
                except (json.JSONDecodeError, TypeError):
                    continue

            return entries
        except Exception:
            logger.exception(
                "Failed to get blocked list (company_id=%s)",
                company_id,
            )
            return []

    async def get_stats(self, company_id: str) -> Dict[str, Any]:
        """Get guardrail blocking statistics for a tenant.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            Dict with blocking stats by layer, severity, and totals.
        """
        try:
            from app.core.redis import get_redis, make_key

            redis = await get_redis()
            stats_key = make_key(company_id, self.STATS_KEY)
            raw = await redis.get(stats_key)

            if raw:
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    pass

            return {
                "company_id": company_id,
                "total_blocked": 0,
                "total_flagged": 0,
                "by_layer": {},
                "by_severity": {},
                "by_variant": {},
            }
        except Exception:
            logger.exception(
                "Failed to get guardrails stats (company_id=%s)",
                company_id,
            )
            return {
                "company_id": company_id,
                "total_blocked": 0,
                "total_flagged": 0,
                "by_layer": {},
                "by_severity": {},
                "by_variant": {},
            }

    async def _increment_stats(
        self,
        redis: Any,
        company_id: str,
        guard_result: GuardrailResult,
    ) -> None:
        """Increment stats counters in Redis.

        Uses a single hash per tenant to track blocking statistics.

        Args:
            redis: Redis client instance.
            company_id: Tenant identifier.
            guard_result: The guardrail result to record.
        """
        try:
            from app.core.redis import make_key

            stats_key = make_key(company_id, self.STATS_KEY)

            # Get existing stats
            raw = await redis.get(stats_key)
            if raw:
                stats = json.loads(raw)
            else:
                stats: Dict[str, Any] = {
                    "total_blocked": 0,
                    "total_flagged": 0,
                    "by_layer": {},
                    "by_severity": {},
                    "by_variant": {},
                }

            # Increment totals
            if guard_result.action == GuardAction.BLOCK.value:
                stats["total_blocked"] = stats.get("total_blocked", 0) + 1
            elif guard_result.action == GuardAction.FLAG_FOR_REVIEW.value:
                stats["total_flagged"] = stats.get("total_flagged", 0) + 1

            # Increment by layer
            layer = guard_result.layer
            if "by_layer" not in stats:
                stats["by_layer"] = {}
            stats["by_layer"][layer] = stats["by_layer"].get(layer, 0) + 1

            # Increment by severity
            severity = guard_result.severity
            if "by_severity" not in stats:
                stats["by_severity"] = {}
            stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1

            # Serialize and store
            await redis.set(
                stats_key,
                json.dumps(stats),
                ex=self.BLOCKED_ENTRY_TTL,
            )
        except Exception:
            logger.exception(
                "Failed to increment guardrails stats (company_id=%s)",
                company_id,
            )


# ══════════════════════════════════════════════════════════════════
# MODULE-LEVEL SINGLETON
# ══════════════════════════════════════════════════════════════════

# Eager singleton for the guardrails engine.
# BC-008: Safe to import and use anywhere without initialization concerns.
guardrails_engine = GuardrailsEngine()

# Eager singleton for the blocked response manager.
blocked_response_manager = BlockedResponseManager()
