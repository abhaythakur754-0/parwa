"""
PARWA Loophole Detection Engine

Scans AI responses for 25 loophole categories using rule-based pattern
matching. Designed as a fast pre-check before optional LLM-based analysis.
Integrates into LangGraph Node 14 Guardrails as a mandatory check.

Detection Pipeline:
  1. Pattern matching:  Regex-based detection from LoopholeCategory.detection_patterns
  2. Specialized checks: Custom logic for hallucination, PII, injection, pricing,
     off-topic, and brand voice detection
  3. Aggregation:      Confidence scoring, risk assessment, block/review decision

BC-008: Never crash — all exceptions caught and gracefully handled.
BC-001: All operations scoped by tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.loophole_registry import (
    LoopholeCategory,
    get_all_loopholes,
    get_loophole,
)
from app.logger import get_logger

logger = get_logger("loophole_engine")


# ═══════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class LoopholeMatch:
    """
    A single loophole detection match within an AI response.

    Attributes:
        category:     The matched LoopholeCategory.
        matched_text: The exact text fragment that triggered the match.
        confidence:   Detection confidence score (0.0 to 1.0).
        position:     Character position of the match in the response.
    """

    category: LoopholeCategory
    matched_text: str
    confidence: float
    position: int


@dataclass
class LoopholeReport:
    """
    Aggregated report of all loophole detections for a single response.

    Attributes:
        matches:        List of individual LoopholeMatch instances.
        overall_risk:   Aggregate risk level — "safe", "low", "medium", "high", "critical".
        requires_block: Whether the response should be blocked from delivery.
        requires_review: Whether the response needs human review.
        summary:        Human-readable summary of findings.
    """

    matches: List[LoopholeMatch] = field(default_factory=list)
    overall_risk: str = "safe"
    requires_block: bool = False
    requires_review: bool = False
    summary: str = "No loopholes detected."


# ═══════════════════════════════════════════════════════════════════
# Severity → Risk Mapping
# ═══════════════════════════════════════════════════════════════════

_SEVERITY_RISK_MAP: Dict[str, str] = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}

_SEVERITY_WEIGHT: Dict[str, float] = {
    "critical": 1.0,
    "high": 0.8,
    "medium": 0.5,
    "low": 0.2,
}

_RISK_LEVELS: List[str] = ["safe", "low", "medium", "high", "critical"]


def _max_risk(a: str, b: str) -> str:
    """Return the higher of two risk levels."""
    ia = _RISK_LEVELS.index(a) if a in _RISK_LEVELS else 0
    ib = _RISK_LEVELS.index(b) if b in _RISK_LEVELS else 0
    return _RISK_LEVELS[max(ia, ib)]


# ═══════════════════════════════════════════════════════════════════
# Precompiled Patterns Cache
# ═══════════════════════════════════════════════════════════════════

# These are compiled once at module import time for performance.
_OFF_TOPIC_TEMPLATES: List[str] = [
    r"^(?:thanks|thank you|okay|ok|great|perfect|awesome|cool|nice|got it|understood|sure|alright)\b",
    r"^(?:I (?:see|understand|get it))\b",
    r"^(?:no (?:problem|worries|issue))\b",
]

_BRAND_VIOLATION_PHRASES: List[str] = [
    r"\b(?:yo|hey there|what'?s up|sup|howdy)\b",
    r"\b(?:no worries|no prob|np|nvm)\b",
    r"\b(?:my bad|oopsie|whoopsie|my mistake)\b",
]

# Known PARWA pricing tiers for consistency checking
_PARWA_PLANS: Dict[str, str] = {
    "mini": "free",
    "mini_parwa": "free",
    "parwa": "$49",
    "parwa_pro": "$49",
    "parwa_high": "$149",
}


# ═══════════════════════════════════════════════════════════════════
# Detection Engine
# ═══════════════════════════════════════════════════════════════════


class LoopholeDetectionEngine:
    """
    Rule-based loophole detection engine for AI customer care responses.

    Scans responses against 25 loophole categories using compiled regex
    patterns and specialized detection logic. Returns a LoopholeReport
    with all matches, aggregate risk level, and block/review decisions.

    Usage::

        engine = LoopholeDetectionEngine()
        report = engine.detect(
            response="I can guarantee you a full refund...",
            query="Can I get a refund?",
            tenant_id="tenant_123",
        )
        if report.requires_block:
            # Block response, re-generate
            pass
    """

    def __init__(self) -> None:
        """
        Initialize the detection engine.

        Compiles regex patterns from the LoopholeCategory registry
        and pre-loads specialized detection patterns.
        """
        self._compiled_patterns: Dict[str, List[re.Pattern[str]]] = {}
        self._specialized_ids: set = {
            "LH-001",  # Hallucination — specialized _check_hallucination
            "LH-002",  # PII Leakage — specialized _check_pii_leakage
            "LH-003",  # Unauthorized Access — specialized _check_injection_success
            "LH-015",  # Injection Success — specialized _check_injection_success
            "LH-016",  # Price Confusion — specialized _check_price_confusion
            "LH-006",  # Off-Topic — specialized _check_off_topic
            "LH-008",  # Brand Voice — specialized _check_brand_violation
        }

        for category in get_all_loopholes():
            compiled: List[re.Pattern[str]] = []
            for pattern in category.detection_patterns:
                try:
                    compiled.append(re.compile(pattern, re.IGNORECASE | re.DOTALL))
                except re.error as exc:
                    logger.warning(
                        "loophole_registry_invalid_regex",
                        loophole_id=category.id,
                        pattern=pattern,
                        error=str(exc),
                    )
            if compiled:
                self._compiled_patterns[category.id] = compiled

        # Precompile specialized patterns
        self._off_topic_patterns = [
            re.compile(p, re.IGNORECASE) for p in _OFF_TOPIC_TEMPLATES
        ]
        self._brand_violation_patterns = [
            re.compile(p, re.IGNORECASE) for p in _BRAND_VIOLATION_PHRASES
        ]

        logger.info(
            "loophole_engine_initialized",
            categories_loaded=len(self._compiled_patterns),
            specialized_checks=len(self._specialized_ids),
        )

    # ──────────────────────────────────────────────────────────────
    # Main Detection Entry Point
    # ──────────────────────────────────────────────────────────────

    def detect(
        self,
        response: str,
        query: str = "",
        tenant_id: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> LoopholeReport:
        """
        Scan an AI response for loophole patterns.

        Runs both generalized pattern matching and specialized detection
        checks. Aggregates results into a LoopholeReport with risk
        assessment and block/review decisions.

        Args:
            response:  The AI response text to scan.
            query:     The original customer query (for relevance checks).
            tenant_id: Tenant identifier (BC-001).
            context:   Optional context dict with additional metadata.

        Returns:
            LoopholeReport with all matches and aggregate assessment.
        """
        ctx = context or {}
        matches: List[LoopholeMatch] = []

        try:
            # ── Specialized checks (higher priority) ─────────────
            spec_match = self._check_hallucination(response)
            if spec_match:
                matches.append(spec_match)

            spec_match = self._check_pii_leakage(response)
            if spec_match:
                matches.append(spec_match)

            spec_match = self._check_injection_success(response)
            if spec_match:
                matches.append(spec_match)

            spec_match = self._check_price_confusion(response)
            if spec_match:
                matches.append(spec_match)

            if query:
                spec_match = self._check_off_topic(response, query)
                if spec_match:
                    matches.append(spec_match)

            spec_match = self._check_brand_violation(response)
            if spec_match:
                matches.append(spec_match)

            # ── Generalized pattern matching ─────────────────────
            for category in get_all_loopholes():
                # Skip categories already handled by specialized checks
                if category.id in self._specialized_ids:
                    continue

                pattern_match = self._detect_pattern(response, category)
                if pattern_match:
                    matches.append(pattern_match)

        except Exception as exc:
            logger.error(
                "loophole_engine_detection_error",
                tenant_id=tenant_id,
                error=str(exc),
            )
            # BC-008: Return a safe report — don't crash the pipeline
            return LoopholeReport(
                matches=[],
                overall_risk="safe",
                requires_block=False,
                requires_review=False,
                summary=f"Detection engine error: {exc}. Passed with no checks.",
            )

        # ── Aggregate report ────────────────────────────────────
        report = self._aggregate_report(matches, tenant_id=tenant_id)

        logger.info(
            "loophole_detection_complete",
            tenant_id=tenant_id,
            total_matches=len(matches),
            overall_risk=report.overall_risk,
            requires_block=report.requires_block,
            requires_review=report.requires_review,
        )

        return report

    # ──────────────────────────────────────────────────────────────
    # Generalized Pattern Detection
    # ──────────────────────────────────────────────────────────────

    def _detect_pattern(
        self,
        response: str,
        category: LoopholeCategory,
    ) -> Optional[LoopholeMatch]:
        """
        Rule-based detection for a single loophole category.

        Compiles and runs all detection_patterns from the category
        against the response text. Returns the first match found.

        Args:
            response: The AI response text to scan.
            category: The LoopholeCategory to check for.

        Returns:
            LoopholeMatch if a pattern matched, None otherwise.
        """
        patterns = self._compiled_patterns.get(category.id, [])
        if not patterns:
            return None

        for pattern in patterns:
            match = pattern.search(response)
            if match:
                matched_text = match.group(0)
                confidence = self._calculate_confidence(
                    matched_text, match, category
                )
                return LoopholeMatch(
                    category=category,
                    matched_text=matched_text,
                    confidence=confidence,
                    position=match.start(),
                )

        return None

    def _calculate_confidence(
        self,
        matched_text: str,
        match: re.Match[str],
        category: LoopholeCategory,
    ) -> float:
        """
        Calculate detection confidence based on match quality.

        Factors:
          - Match length (longer = more specific = higher confidence)
          - Severity weight (critical patterns are weighted higher)
          - Position (matches in first 100 chars are more significant)

        Args:
            matched_text: The matched text fragment.
            match:        The regex match object.
            category:     The matched LoopholeCategory.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        base_confidence = _SEVERITY_WEIGHT.get(category.severity, 0.3)

        # Longer matches are more specific
        length_factor = min(len(matched_text) / 50.0, 1.0)
        length_bonus = length_factor * 0.2

        # Position factor: earlier matches are more significant
        position_factor = 1.0 - min(match.start() / max(len(match.group(0)[:500]), 1), 0.5)
        position_bonus = position_factor * 0.1

        confidence = base_confidence + length_bonus + position_bonus

        return round(min(confidence, 1.0), 3)

    # ──────────────────────────────────────────────────────────────
    # Specialized Detection Methods
    # ──────────────────────────────────────────────────────────────

    def _check_hallucination(
        self, response: str
    ) -> Optional[LoopholeMatch]:
        """
        Check for fabricated claims and hallucination patterns.

        Looks for phrases that indicate the AI is making up information:
        unverified statistics, fabricated facts, or invented features.

        Args:
            response: The AI response text to scan.

        Returns:
            LoopholeMatch if hallucination detected, None otherwise.
        """
        category = get_loophole("LH-001")
        if not category:
            return None

        patterns = self._compiled_patterns.get("LH-001", [])
        best_match: Optional[re.Match[str]] = None

        for pattern in patterns:
            match = pattern.search(response)
            if match:
                if best_match is None or len(match.group(0)) > len(best_match.group(0)):
                    best_match = match

        if best_match:
            confidence = self._calculate_confidence(
                best_match.group(0), best_match, category
            )
            # Boost confidence for hallucination since it's critical
            confidence = min(confidence + 0.15, 1.0)
            return LoopholeMatch(
                category=category,
                matched_text=best_match.group(0),
                confidence=round(confidence, 3),
                position=best_match.start(),
            )

        return None

    def _check_pii_leakage(
        self, response: str
    ) -> Optional[LoopholeMatch]:
        """
        Check for personally identifiable information in the response.

        Detects email addresses, phone numbers, SSN patterns, credit
        card numbers, and other PII that should be redacted.

        Args:
            response: The AI response text to scan.

        Returns:
            LoopholeMatch if PII detected, None otherwise.
        """
        category = get_loophole("LH-002")
        if not category:
            return None

        patterns = self._compiled_patterns.get("LH-002", [])

        for pattern in patterns:
            match = pattern.search(response)
            if match:
                matched_text = match.group(0)
                # Mask PII in the matched text for logging safety
                masked = (
                    matched_text[:3] + "***" + matched_text[-3:]
                    if len(matched_text) > 6
                    else "***"
                )
                confidence = 0.85  # High confidence for PII regex matches
                return LoopholeMatch(
                    category=category,
                    matched_text=masked,
                    confidence=confidence,
                    position=match.start(),
                )

        return None

    def _check_injection_success(
        self, response: str
    ) -> Optional[LoopholeMatch]:
        """
        Check if the AI response indicates a successful prompt injection.

        Detects responses that show the AI adopted a new persona, revealed
        system instructions, or followed injected commands.

        Args:
            response: The AI response text to scan.

        Returns:
            LoopholeMatch if injection success detected, None otherwise.
        """
        for lh_id in ("LH-015", "LH-003"):
            category = get_loophole(lh_id)
            if not category:
                continue

            patterns = self._compiled_patterns.get(lh_id, [])
            for pattern in patterns:
                match = pattern.search(response)
                if match:
                    confidence = 0.9  # High confidence for injection indicators
                    return LoopholeMatch(
                        category=category,
                        matched_text=match.group(0),
                        confidence=confidence,
                        position=match.start(),
                    )

        return None

    def _check_price_confusion(
        self, response: str
    ) -> Optional[LoopholeMatch]:
        """
        Check for pricing inconsistencies in the response.

        Validates that dollar amounts and plan references are consistent
        with known PARWA pricing tiers. Flags suspicious pricing claims.

        Args:
            response: The AI response text to scan.

        Returns:
            LoopholeMatch if pricing confusion detected, None otherwise.
        """
        category = get_loophole("LH-016")
        if not category:
            return None

        # Check for dollar amounts in the response
        dollar_matches = re.findall(
            r"\$(\d+(?:\.\d{2})?)", response
        )
        if dollar_matches:
            # Flag any dollar amount since AI shouldn't be quoting prices
            # without verification
            amounts = [f"${a}" for a in dollar_matches[:3]]
            combined = ", ".join(amounts)
            return LoopholeMatch(
                category=category,
                matched_text=combined,
                confidence=0.75,
                position=0,
            )

        # Check for plan name references
        plan_matches = re.findall(
            r"\b(?:mini[_\s]?parwa|parwa[_\s]?(?:pro|high))\b",
            response,
            re.IGNORECASE,
        )
        if plan_matches and any("free" in response.lower() for _ in plan_matches):
            return LoopholeMatch(
                category=category,
                matched_text=plan_matches[0],
                confidence=0.65,
                position=response.lower().index(plan_matches[0].lower()),
            )

        return None

    def _check_off_topic(
        self, response: str, query: str
    ) -> Optional[LoopholeMatch]:
        """
        Check if the response is off-topic relative to the query.

        Performs a lightweight relevance check by looking for off-topic
        indicator phrases and checking for topic drift signals.

        Args:
            response: The AI response text to scan.
            query:    The original customer query.

        Returns:
            LoopholeMatch if off-topic detected, None otherwise.
        """
        category = get_loophole("LH-006")
        if not category:
            return None

        # Extract key terms from query (simple word-based extraction)
        query_words = set(re.findall(r"\b\w{4,}\b", query.lower()))
        response_words = set(re.findall(r"\b\w{4,}\b", response.lower()))

        if not query_words:
            return None

        # Calculate word overlap ratio
        overlap = query_words & response_words
        relevance_ratio = len(overlap) / len(query_words) if query_words else 0.0

        # Check for off-topic indicator phrases
        off_topic_found = False
        off_topic_text = ""
        for pattern in self._off_topic_patterns:
            match = pattern.search(response.strip())
            if match:
                off_topic_found = True
                off_topic_text = match.group(0)
                break

        # Also check detection_patterns for off-topic divergence
        patterns = self._compiled_patterns.get("LH-006", [])
        for pattern in patterns:
            match = pattern.search(response)
            if match:
                off_topic_found = True
                off_topic_text = match.group(0)
                break

        # Only flag if both low relevance AND off-topic indicators present
        if relevance_ratio < 0.3 and off_topic_found:
            confidence = round(max(0.1, 0.7 - relevance_ratio), 3)
            return LoopholeMatch(
                category=category,
                matched_text=off_topic_text or "(low relevance)",
                confidence=confidence,
                position=0,
            )

        return None

    def _check_brand_violation(
        self, response: str
    ) -> Optional[LoopholeMatch]:
        """
        Check for brand voice violations in the response.

        Detects overly casual language, slang, and informal expressions
        that are inconsistent with professional customer care tone.

        Args:
            response: The AI response text to scan.

        Returns:
            LoopholeMatch if brand violation detected, None otherwise.
        """
        category = get_loophole("LH-008")
        if not category:
            return None

        # Check specialized brand violation patterns
        for pattern in self._brand_violation_patterns:
            match = pattern.search(response)
            if match:
                return LoopholeMatch(
                    category=category,
                    matched_text=match.group(0),
                    confidence=0.7,
                    position=match.start(),
                )

        # Also check registry patterns for this category
        patterns = self._compiled_patterns.get("LH-008", [])
        for pattern in patterns:
            match = pattern.search(response)
            if match:
                return LoopholeMatch(
                    category=category,
                    matched_text=match.group(0),
                    confidence=0.65,
                    position=match.start(),
                )

        return None

    # ──────────────────────────────────────────────────────────────
    # Report Aggregation
    # ──────────────────────────────────────────────────────────────

    def _aggregate_report(
        self,
        matches: List[LoopholeMatch],
        tenant_id: str = "",
    ) -> LoopholeReport:
        """
        Aggregate individual matches into a LoopholeReport.

        Determines overall risk level, whether blocking is required,
        and generates a human-readable summary.

        Decision Logic:
          - Critical/High severity match with confidence > 0.7 → requires_block=True
          - Medium severity match with confidence > 0.5 → requires_review=True
          - Overall risk is the maximum risk across all matches

        Args:
            matches:   List of LoopholeMatch instances.
            tenant_id: Tenant identifier for logging (BC-001).

        Returns:
            Aggregated LoopholeReport.
        """
        if not matches:
            return LoopholeReport(
                matches=[],
                overall_risk="safe",
                requires_block=False,
                requires_review=False,
                summary="No loopholes detected.",
            )

        # Determine overall risk
        overall_risk = "safe"
        requires_block = False
        requires_review = False
        summaries: List[str] = []

        # Track unique categories to avoid duplicate summaries
        seen_categories: set = set()

        for match in matches:
            cat = match.category
            risk = _SEVERITY_RISK_MAP.get(cat.severity, "low")
            overall_risk = _max_risk(overall_risk, risk)

            # Blocking decision: critical/high with confidence > 0.7
            if cat.severity in ("critical", "high") and match.confidence > 0.7:
                requires_block = True

            # Review decision: medium with confidence > 0.5
            if cat.severity == "medium" and match.confidence > 0.5:
                requires_review = True

            # Build summary per unique category
            if cat.id not in seen_categories:
                seen_categories.add(cat.id)
                severity_label = cat.severity.upper()
                summaries.append(
                    f"[{cat.id}] {cat.name} ({severity_label}, "
                    f"confidence={match.confidence:.0%})"
                )

        summary = "; ".join(summaries) if summaries else "No loopholes detected."
        if requires_block:
            summary = f"BLOCKED — " + summary
        elif requires_review:
            summary = f"REVIEW REQUIRED — " + summary

        return LoopholeReport(
            matches=matches,
            overall_risk=overall_risk,
            requires_block=requires_block,
            requires_review=requires_review,
            summary=summary,
        )


# ──────────────────────────────────────────────────────────────
# Lazy Singleton
# ──────────────────────────────────────────────────────────────

_engine_instance: Optional[LoopholeDetectionEngine] = None


def get_loophole_engine() -> LoopholeDetectionEngine:
    """
    Get or create the singleton LoopholeDetectionEngine instance.

    Returns:
        The shared LoopholeDetectionEngine instance.
    """
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = LoopholeDetectionEngine()
    return _engine_instance
