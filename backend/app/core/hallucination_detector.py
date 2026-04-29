"""
SG-27: Hallucination Detection Patterns (BC-007, BC-012)

12 hallucination detection patterns that catch AI making things up.
Each pattern has a detection function + confidence score (0.0-1.0).

Patterns:
1. Contradiction with KB — response contradicts known facts
2. Fabricated URLs/IDs — response contains fake links or IDs
3. Overconfident wrong answers — high confidence on wrong info
4. Plausible-sounding nonsense — grammatically correct but meaningless
5. Date/math errors — incorrect dates, calculations, or temporal claims
6. Entity confusion — mixing up people, products, companies
7. Policy fabrication — making up policies, terms, or conditions
8. False feature claims — claiming features that don't exist
9. Circular reasoning — response loops back to its own premise
10. Source attribution without source — citing sources that don't exist
11. Numerical precision hallucination — overly precise fake numbers
12. Temporal inconsistency — contradicting earlier parts of conversation

BC-001: company_id on all operations.
BC-012: Graceful failure — detection errors don't crash pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

from app.logger import get_logger

logger = get_logger("parwa.hallucination_detector")


# ══════════════════════════════════════════════════════════════════
# Compiled Regex Patterns (module-level for performance)
# ══════════════════════════════════════════════════════════════════

# URL detection
RE_URL = re.compile(r"https?://[^\s]+")

# Suspicious / placeholder domains
RE_SUSPICIOUS_DOMAINS = re.compile(
    r"https?://(?:"
    r"example\.com|"
    r"example\.org|"
    r"test\.com|"
    r"placeholder\.com|"
    r"dontexist\.com|"
    r"fakeurl\.com"
    r")[^\s]*",
    re.IGNORECASE,
)

# Internal path patterns that shouldn't appear in customer responses
RE_INTERNAL_PATHS = re.compile(
    r"https?://parwa\.ai/(?:support|admin|internal|api|docs|dev)[/\w\-]*",
    re.IGNORECASE,
)

# Overconfident phrases
RE_OVERCONFIDENT = re.compile(
    r"\b(?:"
    r"definitely|absolutely|certainly|"
    r"without a doubt|guaranteed|"
    r"without question|unequivocally|"
    r"indisputably|undoubtedly"
    r")\b",
    re.IGNORECASE,
)

# Speculative language
RE_SPECULATIVE = re.compile(
    r"\b(?:"
    r"I think|probably|might be|"
    r"perhaps|possibly|it seems|"
    r"I believe|it appears|"
    r"could be|may be|may cause|might cause|likely"
    r")\b",
    re.IGNORECASE,
)

# Date patterns (various formats)
RE_DATE_MDY = re.compile(
    r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",
)
RE_DATE_TEXT = re.compile(
    r"\b(?:January|February|March|April|May|June|July|"
    r"August|September|October|November|December)\s+"
    r"(\d{1,2}),?\s+(\d{4})\b",
    re.IGNORECASE,
)

# Arithmetic in text: "X years from YYYY" or "YYYY plus X years"
RE_ARITHMETIC_TEMPORAL = re.compile(
    r"(\d+)\s*(?:years?|months?|days?|weeks?)\s+"
    r"(?:from|after|since|before|later|ago)\s+"
    r"(\d{4})",
    re.IGNORECASE,
)

# PARWA-specific known entities
KNOWN_PLANS: Dict[str, float] = {
    "mini parwa": 999.0,
    "parwa": 2499.0,
    "parwa high": 3999.0,
}

KNOWN_PLAN_NAMES: Set[str] = {
    "mini parwa",
    "parwa",
    "parwa high",
}

# Policy fabrication phrases
RE_POLICY_CLAIMS = re.compile(
    r"\b(?:"
    r"our policy states|according to our terms|"
    r"per our agreement|our terms state|"
    r"as per our policy|our terms and conditions|"
    r"our service agreement|per the contract"
    r")\b",
    re.IGNORECASE,
)

RE_REFUND_SLA_CLAIMS = re.compile(
    r"(?:"
    r"full refund within|refund within \d+ days|"
    r"\d+% refund|money.back guarantee|"
    r"sla of \d+ hours|response time of \d+|"
    r"uptime of \d+(?:\.\d+)?%"
    r")",
    re.IGNORECASE,
)

# Feature claim patterns
RE_FEATURE_CLAIMS = re.compile(
    r"\b(?:"
    r"we support|you can|the system will|"
    r"our platform (?:offers|provides|includes|has)|"
    r"PARWA (?:can|will|supports?|offers?|provides?)|"
    r"the AI (?:can|will|is able to|is capable of)"
    r")\b",
    re.IGNORECASE,
)

# Known feature names from FEATURE_REGISTRY
KNOWN_FEATURE_PHRASES: Set[str] = {
    "knowledge base",
    "semantic search",
    "sentiment analysis",
    "intent classification",
    "multi-language",
    "tone adjustment",
    "chain of thought",
    "few-shot",
    "react",
    "reflexion",
    "hallucination detection",
    "pii redaction",
    "prompt injection",
    "content policy",
    "toxicity detection",
    "a/b testing",
    "brand voice",
    "response personalization",
    "auto-summarization",
    "human handof",
    "escalation",
    "context window",
    "conversation thread",
    "email channel",
    "chat channel",
    "sms channel",
    "voice channel",
    "ticket routing",
    "urgency detection",
    "language detection",
    "spam detection",
    "complexity scoring",
    "emotion analysis",
    "topic classification",
    "customer tier",
}

# Circular reasoning patterns
RE_CIRCULAR_STARTERS = re.compile(
    r"\b(?:"
    r"as mentioned|as I said|which means that|"
    r"therefore,?\s*because|this is because|"
    r"as stated above|as explained earlier|"
    r"going back to|as previously noted"
    r")\b",
    re.IGNORECASE,
)

# Fake source attribution patterns
RE_SOURCE_ATTRIBUTION = re.compile(
    r"\b(?:"
    r"according to|as stated in|per documentation|"
    r"per the documentation|see section|"
    r"as described in|refer to|consult|"
    r"as outlined in|as specified in|as defined in"
    r")\b",
    re.IGNORECASE,
)

RE_FAKE_DOC_REFS = re.compile(
    r"(?:Section|Article|Clause|Paragraph|Chapter)\s+"
    r"(?:\d+\.?\d*[a-z]?|I{1,3}V?|IV|VI{0,3}|IX|X{1,3}V?|XIV|XV|XVI|XVII|XVIII|XIX|XX)",
    re.IGNORECASE,
)

RE_PAGE_REFS = re.compile(
    r"\b(?:Page|p\.|pp\.)\s*\d+\b",
    re.IGNORECASE,
)

# Numerical precision patterns
RE_PRECISE_PERCENTAGE = re.compile(
    r"\b\d{1,3}\.\d+%\.?",  # e.g. 99.73%, 67.4% (1+ decimal places)
)
RE_PRECISE_DECIMAL = re.compile(
    r"\b\d+\.\d{2,}\b",  # e.g. 1.23, 45.678 — standalone precise decimal
)
RE_PRECISE_CURRENCY = re.compile(
    r"\$\d{1,3}(?:,\d{3})+\.\d{2}\b",  # e.g. $1,234.56
)
RE_PRECISE_COUNT = re.compile(
    r"\b\d{1,3}(?:,\d{3})+\b",  # e.g. 2,847
)

# Buzzword list for plausible nonsense detection
BUZZWORDS: Set[str] = {
    "leverage",
    "synergy",
    "paradigm",
    "holistic",
    "streamline",
    "optimize",
    "empower",
    "disrupt",
    "innovate",
    "transformative",
    "actionable",
    "robust",
    "scalable",
    "cutting-edge",
    "next-generation",
    "best-in-class",
    "world-class",
    "enterprise-grade",
    "future-proof",
    "seamless",
    "frictionless",
    "end-to-end",
    "turnkey",
    "agile",
    "cloud-native",
    "data-driven",
    "AI-powered",
    "machine learning",
    "deep learning",
    "neural network",
    "natural language processing",
    "predictive analytics",
    "big data",
    "blockchain",
    "metaverse",
    "quantum",
    "gamification",
    "omnichannel",
    "hyper-personalization",
}

# Negation patterns for KB contradiction
RE_NEGATION = re.compile(
    r"\b(?:"
    r"is not|isn't|does not have|doesn't have|"
    r"does not include|doesn't include|"
    r"doesn't provide|doesn't offer|"
    r"no longer|not available|not supported|"
    r"doesn't support|isn't available|cannot|can't|"
    r"will not|won't|hasn't|haven't"
    r")\b",
    re.IGNORECASE,
)

# Days per month (index = month, 0-based, so 1=Jan)
_DAYS_IN_MONTH: Dict[int, int] = {
    1: 31,
    2: 28,
    3: 31,
    4: 30,
    5: 31,
    6: 30,
    7: 31,
    8: 31,
    9: 30,
    10: 31,
    11: 30,
    12: 31,
}

_MONTH_NAMES: Dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


# ══════════════════════════════════════════════════════════════════
# Data Classes
# ══════════════════════════════════════════════════════════════════


@dataclass
class HallucinationMatch:
    """A single hallucination detection match from one pattern."""

    pattern_id: str
    pattern_name: str
    confidence: float
    evidence: str
    start: int
    end: int
    severity: str  # "low", "medium", "high", "critical"

    def __post_init__(self) -> None:
        """Validate confidence is in [0.0, 1.0] and severity is valid."""
        if not (0.0 <= self.confidence <= 1.0):
            logger.warning(
                "HallucinationMatch confidence out of range: %.3f, clamping to [0.0, 1.0]",
                self.confidence,
            )
            self.confidence = max(0.0, min(1.0, self.confidence))
        valid_severities = {"low", "medium", "high", "critical"}
        if self.severity not in valid_severities:
            logger.warning(
                "Invalid severity '%s', defaulting to 'medium'",
                self.severity,
            )
            self.severity = "medium"


@dataclass
class HallucinationReport:
    """Aggregated hallucination detection report for a response."""

    is_hallucination: bool
    overall_confidence: float
    matches: List[HallucinationMatch] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    recommendation: str = "safe"  # "safe", "review", "block"

    def __post_init__(self) -> None:
        """Validate and normalize report fields."""
        if not (0.0 <= self.overall_confidence <= 1.0):
            logger.warning(
                "HallucinationReport overall_confidence out of range: %.3f, clamping",
                self.overall_confidence,
            )
            self.overall_confidence = max(0.0, min(1.0, self.overall_confidence))
        valid_recommendations = {"safe", "review", "block"}
        if self.recommendation not in valid_recommendations:
            logger.warning(
                "Invalid recommendation '%s', defaulting to 'review'",
                self.recommendation,
            )
            self.recommendation = "review"


# ══════════════════════════════════════════════════════════════════
# Recommendation Thresholds
# ══════════════════════════════════════════════════════════════════

_BLOCK_THRESHOLD: float = 0.85
_REVIEW_THRESHOLD: float = 0.50


# ══════════════════════════════════════════════════════════════════
# Hallucination Detector
# ══════════════════════════════════════════════════════════════════


class HallucinationDetector:
    """SG-27: Hallucination Detection Engine.

    Runs 12 detection patterns against an AI response to identify
    hallucinations — cases where the AI is making things up.

    BC-001: company_id is required on all operations.
    BC-012: Graceful failure — detection errors never crash the pipeline.
    """

    def __init__(self) -> None:
        self._company_id: str = ""
        self._patterns_run: int = 0
        self._patterns_failed: int = 0

    # ── Public API ──────────────────────────────────────────────

    def detect(
        self,
        response: str,
        query: str,
        knowledge_context: str | None = None,
        conversation_history: list[dict] | None = None,
        company_id: str = "",
    ) -> HallucinationReport:
        """Run all 12 hallucination detection patterns on a response.

        Args:
            response: The AI-generated response to analyze.
            query: The original user query.
            knowledge_context: Optional KB context the AI was given.
            conversation_history: Optional list of prior turns
                (each dict with 'role' and 'content').
            company_id: Tenant company ID (BC-001).

        Returns:
            HallucinationReport with all matches, confidence, and
            recommendation.
        """
        self._company_id = company_id
        self._patterns_run = 0
        self._patterns_failed = 0

        if not response or not response.strip():
            return HallucinationReport(
                is_hallucination=False,
                overall_confidence=0.0,
                matches=[],
                summary={
                    "total_patterns": 12,
                    "patterns_run": 0,
                    "patterns_failed": 0,
                    "reason": "empty_response",
                },
                recommendation="safe",
            )

        matches: List[HallucinationMatch] = []

        # Run all 12 detection patterns — each is wrapped so
        # individual failures don't crash the pipeline (BC-012)
        pattern_methods: List[Tuple[str, Any]] = [
            (
                "P01_kb_contradiction",
                lambda: self._detect_kb_contradiction(
                    response,
                    knowledge_context or "",
                ),
            ),
            ("P02_fabricated_urls", lambda: self._detect_fabricated_urls(response)),
            (
                "P03_overconfident_claims",
                lambda: self._detect_overconfident_claims(
                    response,
                    0.7,
                ),
            ),
            (
                "P04_plausible_nonsense",
                lambda: self._detect_plausible_nonsense(response),
            ),
            ("P05_date_math_errors", lambda: self._detect_date_math_errors(response)),
            ("P06_entity_confusion", lambda: self._detect_entity_confusion(response)),
            (
                "P07_policy_fabrication",
                lambda: self._detect_policy_fabrication(response),
            ),
            (
                "P08_false_feature_claims",
                lambda: self._detect_false_feature_claims(response),
            ),
            (
                "P09_circular_reasoning",
                lambda: self._detect_circular_reasoning(response),
            ),
            (
                "P10_fake_source_attribution",
                lambda: self._detect_fake_source_attribution(response),
            ),
            (
                "P11_numerical_precision",
                lambda: self._detect_numerical_precision_hallucination(response),
            ),
            (
                "P12_temporal_inconsistency",
                lambda: self._detect_temporal_inconsistency(
                    response,
                    conversation_history or [],
                ),
            ),
        ]

        for pattern_id, pattern_fn in pattern_methods:
            try:
                self._patterns_run += 1
                match = pattern_fn()
                if match is not None:
                    matches.append(match)
            except Exception:
                self._patterns_failed += 1
                logger.warning(
                    "Pattern %s failed (BC-012: continuing), company_id=%s",
                    pattern_id,
                    company_id,
                    exc_info=True,
                )

        # Aggregate results
        return self._build_report(matches, query, response)

    # ── Report Building ─────────────────────────────────────────

    def _build_report(
        self,
        matches: List[HallucinationMatch],
        query: str,
        response: str,
    ) -> HallucinationReport:
        """Aggregate matches into a final HallucinationReport."""
        if not matches:
            return HallucinationReport(
                is_hallucination=False,
                overall_confidence=0.0,
                matches=[],
                summary={
                    "total_patterns": 12,
                    "patterns_run": self._patterns_run,
                    "patterns_failed": self._patterns_failed,
                    "matches_found": 0,
                },
                recommendation="safe",
            )

        # Overall confidence = max of individual match confidences,
        # boosted slightly if multiple patterns fire
        max_confidence = max(m.confidence for m in matches)
        count_boost = min(0.1, len(matches) * 0.02)
        overall_confidence = min(1.0, max_confidence + count_boost)

        # Recommendation thresholds
        if overall_confidence >= _BLOCK_THRESHOLD:
            recommendation = "block"
        elif overall_confidence >= _REVIEW_THRESHOLD:
            recommendation = "review"
        else:
            recommendation = "safe"

        # Severity summary
        severity_counts: Dict[str, int] = {
            "low": 0,
            "medium": 0,
            "high": 0,
            "critical": 0,
        }
        for m in matches:
            severity_counts[m.severity] = severity_counts.get(m.severity, 0) + 1

        has_critical = severity_counts.get("critical", 0) > 0

        # Elevate to "block" if any critical match exists
        if has_critical and recommendation != "block":
            recommendation = "block"
            overall_confidence = max(overall_confidence, _BLOCK_THRESHOLD)

        summary: Dict[str, Any] = {
            "total_patterns": 12,
            "patterns_run": self._patterns_run,
            "patterns_failed": self._patterns_failed,
            "matches_found": len(matches),
            "severity_breakdown": severity_counts,
            "pattern_ids": [m.pattern_id for m in matches],
            "response_length": len(response),
            "query_length": len(query),
        }

        return HallucinationReport(
            is_hallucination=True,
            overall_confidence=round(overall_confidence, 4),
            matches=matches,
            summary=summary,
            recommendation=recommendation,
        )

    # ── Pattern 1: KB Contradiction ─────────────────────────────

    def _detect_kb_contradiction(
        self,
        response: str,
        knowledge_context: str,
    ) -> HallucinationMatch | None:
        """P01: Check if response contradicts known KB facts.

        Looks for negation patterns ("is not", "doesn't have", etc.)
        followed by claims that contradict the knowledge context.
        Confidence: 0.7-0.9.
        """
        if not knowledge_context or not knowledge_context.strip():
            return None

        negation_matches = list(RE_NEGATION.finditer(response))
        if not negation_matches:
            return None

        # Extract key factual statements from KB context
        kb_sentences: List[str] = re.split(r"[.!?]\s+", knowledge_context.strip())
        kb_sentences = [s.strip() for s in kb_sentences if len(s.strip()) > 15]

        if not kb_sentences:
            return None

        # Check if any negated part of the response contradicts KB
        for neg_match in negation_matches:
            neg_start = max(0, neg_match.start() - 30)
            neg_end = min(len(response), neg_match.end() + 80)
            neg_context = response[neg_start:neg_end].lower()

            for kb_sent in kb_sentences:
                kb_words = set(re.findall(r"\b\w{4,}\b", kb_sent.lower()))
                neg_words = set(re.findall(r"\b\w{4,}\b", neg_context))
                overlap = kb_words & neg_words

                # If >40% of KB sentence's significant words appear
                # near a negation in the response, likely contradiction
                if kb_words and len(overlap) / len(kb_words) >= 0.3:
                    confidence = 0.7 + 0.2 * min(1.0, len(overlap) / len(kb_words))
                    severity = "high" if confidence >= 0.85 else "medium"
                    return HallucinationMatch(
                        pattern_id="P01_kb_contradiction",
                        pattern_name="Contradiction with KB",
                        confidence=round(min(0.9, confidence), 4),
                        evidence=f"Negation near KB fact overlap: '{neg_context.strip()}' vs KB: '{kb_sent[:100]}'",
                        start=neg_start,
                        end=neg_end,
                        severity=severity,
                    )

        return None

    # ── Pattern 2: Fabricated URLs ──────────────────────────────

    def _detect_fabricated_urls(
        self,
        response: str,
    ) -> HallucinationMatch | None:
        """P02: Detect fabricated URLs in the response.

        Checks for placeholder domains, internal paths, and
        suspicious URL patterns. Confidence: 0.8-0.95.
        """
        urls = RE_URL.findall(response)
        if not urls:
            return None

        suspicious_urls: List[str] = []
        for url in urls:
            if RE_SUSPICIOUS_DOMAINS.search(url):
                suspicious_urls.append(url)
            elif RE_INTERNAL_PATHS.search(url):
                suspicious_urls.append(url)

        if not suspicious_urls:
            return None

        # Confidence based on count and type
        has_placeholder = any(RE_SUSPICIOUS_DOMAINS.search(u) for u in suspicious_urls)
        has_internal = any(RE_INTERNAL_PATHS.search(u) for u in suspicious_urls)

        confidence = 0.85
        if has_placeholder and has_internal:
            confidence = 0.95
        elif has_placeholder:
            confidence = 0.90

        evidence = f"Fabricated URLs found: {', '.join(suspicious_urls[:3])}"
        first_match = RE_URL.search(response)
        start = first_match.start() if first_match else 0

        return HallucinationMatch(
            pattern_id="P02_fabricated_urls",
            pattern_name="Fabricated URLs/IDs",
            confidence=round(confidence, 4),
            evidence=evidence,
            start=start,
            end=start + len(evidence),
            severity="high" if confidence >= 0.9 else "medium",
        )

    # ── Pattern 3: Overconfident Claims ─────────────────────────

    def _detect_overconfident_claims(
        self,
        response: str,
        confidence_score: float,
    ) -> HallucinationMatch | None:
        """P03: Detect overconfident claims that may be wrong.

        Flags when absolute language (definitely, guaranteed) appears
        near speculative language (I think, probably). Confidence: 0.5-0.7.
        """
        overconfident_matches = list(RE_OVERCONFIDENT.finditer(response))
        if not overconfident_matches:
            return None

        # Even without speculative language, many overconfident phrases =
        # suspicious
        if len(overconfident_matches) >= 3 and confidence_score < 0.85:
            first = overconfident_matches[0]
            return HallucinationMatch(
                pattern_id="P03_overconfident_claims",
                pattern_name="Overconfident wrong answers",
                confidence=0.55,
                evidence=f"Multiple overconfident phrases ({
                    len(overconfident_matches)}) with low system confidence ({
                    confidence_score:.2f})",
                start=first.start(),
                end=first.end(),
                severity="low",
            )

        speculative_matches = list(RE_SPECULATIVE.finditer(response))
        if not speculative_matches:
            return None

        # Check proximity: overconfident within 60 chars of speculative
        for oc in overconfident_matches:
            for spec in speculative_matches:
                distance = abs(oc.start() - spec.end())
                if distance <= 60:
                    combined = response[
                        min(oc.start(), spec.start()) : max(oc.end(), spec.end())
                    ]
                    confidence = 0.5 + 0.2 * (1.0 - distance / 60.0)
                    return HallucinationMatch(
                        pattern_id="P03_overconfident_claims",
                        pattern_name="Overconfident wrong answers",
                        confidence=round(min(0.7, confidence), 4),
                        evidence=f"Overconfident + speculative: '{combined.strip()}'",
                        start=min(oc.start(), spec.start()),
                        end=max(oc.end(), spec.end()),
                        severity="low",
                    )

        return None

    # ── Pattern 4: Plausible-Sounding Nonsense ──────────────────

    def _detect_plausible_nonsense(
        self,
        response: str,
    ) -> HallucinationMatch | None:
        """P04: Detect grammatically correct but meaningless text.

        Checks for long sentences with high buzzword density and
        no concrete nouns. Confidence: 0.4-0.6.
        """
        sentences: List[str] = re.split(r"[.!?]+", response)
        flagged_sentences: List[str] = []

        for sentence in sentences:
            sentence = sentence.strip()
            words = sentence.split()
            if len(words) < 15:
                continue

            # Buzzword density
            sentence_lower = sentence.lower()
            buzz_count = sum(1 for bw in BUZZWORDS if bw in sentence_lower)
            buzz_density = buzz_count / len(words) if words else 0

            # Concrete noun check (capitalized words that aren't
            # at the start of sentence = likely proper nouns / entities)
            proper_nouns = re.findall(
                r"(?<!^)(?<!\.\s)[A-Z][a-z]+(?:\s[A-Z][a-z]+)*",
                sentence,
            )

            # Number presence (concrete data)
            has_numbers = bool(re.search(r"\d", sentence))

            # High buzzword + no concrete data = suspicious
            if buzz_density >= 0.15 and len(proper_nouns) == 0 and not has_numbers:
                flagged_sentences.append(sentence)

        if not flagged_sentences:
            return None

        # Confidence based on buzzword density of worst sentence
        worst = max(
            flagged_sentences,
            key=lambda s: sum(1 for bw in BUZZWORDS if bw in s.lower())
            / max(1, len(s.split())),
        )
        worst_density = sum(1 for bw in BUZZWORDS if bw in worst.lower()) / max(
            1, len(worst.split())
        )

        confidence = 0.4 + 0.2 * min(1.0, worst_density / 0.3)

        idx = response.find(worst)
        start = idx if idx >= 0 else 0

        return HallucinationMatch(
            pattern_id="P04_plausible_nonsense",
            pattern_name="Plausible-sounding nonsense",
            confidence=round(min(0.6, confidence), 4),
            evidence=f"Buzzword-dense sentence without concrete data: '{worst[:120]}...'",
            start=start,
            end=start + len(worst),
            severity="low",
        )

    # ── Pattern 5: Date/Math Errors ─────────────────────────────

    def _detect_date_math_errors(
        self,
        response: str,
    ) -> HallucinationMatch | None:
        """P05: Detect incorrect dates or arithmetic errors.

        Checks for impossible dates (Feb 30, month > 12) and
        temporal arithmetic errors. Confidence: 0.7-0.9.
        """
        errors: List[str] = []
        error_positions: List[Tuple[int, int]] = []

        # Check MM/DD/YYYY format dates
        for m in RE_DATE_MDY.finditer(response):
            month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if month < 1 or month > 12:
                errors.append(f"Invalid month {month} in date {m.group(0)}")
                error_positions.append((m.start(), m.end()))
            elif day < 1 or day > _DAYS_IN_MONTH.get(month, 31):
                # Special case: Feb 29 only valid in leap years
                if month == 2 and day == 29:
                    if not self._is_leap_year(year):
                        errors.append(f"Feb 29 in non-leap year {year}")
                        error_positions.append((m.start(), m.end()))
                else:
                    errors.append(f"Invalid day {day} for month {month} in date {
                            m.group(0)}")
                    error_positions.append((m.start(), m.end()))

        # Check text month dates (e.g., "February 30, 2024")
        for m in RE_DATE_TEXT.finditer(response):
            day, year = int(m.group(1)), int(m.group(2))
            # Extract month name from the match
            month_name_match = re.match(
                r"(January|February|March|April|May|June|July|"
                r"August|September|October|November|December)",
                m.group(0),
                re.IGNORECASE,
            )
            if month_name_match:
                month_num = _MONTH_NAMES.get(month_name_match.group(1).lower(), 0)
                if month_num and (day < 1 or day > _DAYS_IN_MONTH.get(month_num, 31)):
                    if month_num == 2 and day == 29 and self._is_leap_year(year):
                        continue
                    errors.append(f"Invalid day {day} for {
                            month_name_match.group(1)} {year}")
                    error_positions.append((m.start(), m.end()))

        # Check temporal arithmetic (e.g., "3 years from 2020")
        for m in RE_ARITHMETIC_TEMPORAL.finditer(response):
            amount = int(m.group(1))
            base_year = int(m.group(2))
            # Extract the unit
            unit_match = re.search(
                r"(years?|months?|days?|weeks?)",
                m.group(0),
                re.IGNORECASE,
            )
            if unit_match:
                unit = unit_match.group(1).lower()
                if "year" in unit:
                    expected = base_year + amount
                    # Check if the result year appears nearby in the text
                    nearby = response[m.end() : m.end() + 30]
                    year_in_text = re.search(r"\b(\d{4})\b", nearby)
                    if year_in_text:
                        stated_result = int(year_in_text.group(1))
                        if stated_result != expected:
                            errors.append(
                                f"Arithmetic error: {amount} years from "
                                f"{base_year} should be {expected}, "
                                f"not {stated_result}"
                            )
                            error_positions.append((m.start(), m.end() + 30))

        if not errors:
            return None

        confidence = 0.85 if len(errors) >= 2 else 0.75
        start = error_positions[0][0] if error_positions else 0
        end = error_positions[-1][1] if error_positions else 0

        return HallucinationMatch(
            pattern_id="P05_date_math_errors",
            pattern_name="Date/math errors",
            confidence=round(confidence, 4),
            evidence=f"Date/arithmetic errors: {'; '.join(errors[:3])}",
            start=start,
            end=end,
            severity="high",
        )

    # ── Pattern 6: Entity Confusion ─────────────────────────────

    def _detect_entity_confusion(
        self,
        response: str,
    ) -> HallucinationMatch | None:
        """P06: Detect confusion between known entities.

        Checks for PARWA plan name/price mixups and common
        entity swaps. Confidence: 0.8-0.95.
        """
        response_lower = response.lower()
        errors: List[str] = []
        error_positions: List[Tuple[int, int]] = []

        # Sort plan names by length descending so we match the most
        # specific (longest) plan name first at each position.
        # This prevents "parwa" from matching inside "mini parwa".
        sorted_plans = sorted(
            KNOWN_PLANS.items(), key=lambda x: len(x[0]), reverse=True
        )
        # (start, end, plan_name)
        matched_positions: List[Tuple[int, int, str]] = []

        for plan_name, correct_price in sorted_plans:
            # Use regex with word boundaries to avoid substring matches
            plan_pattern = re.compile(
                r"\b" + re.escape(plan_name) + r"\b", re.IGNORECASE
            )
            for m in plan_pattern.finditer(response_lower):
                plan_start, plan_end = m.start(), m.end()
                # Skip if this position overlaps with an already-matched
                # more specific plan name
                overlaps = any(
                    plan_start < existing_end and plan_end > existing_start
                    for existing_start, existing_end, _ in matched_positions
                )
                if overlaps:
                    continue
                matched_positions.append((plan_start, plan_end, plan_name))

                nearby = response[
                    max(0, plan_start - 20) : min(len(response), plan_end + 50)
                ]

                # Extract dollar amounts from nearby text
                prices_nearby = re.findall(r"\$\s*([\d,]+(?:\.\d{1,2})?)", nearby)
                for price_str in prices_nearby:
                    price_str_clean = price_str.replace(",", "")
                    try:
                        mentioned_price = float(price_str_clean)
                    except ValueError:
                        continue

                    # Check if the mentioned price matches known plans
                    # but NOT the correct one
                    for other_plan, other_price in KNOWN_PLANS.items():
                        if (
                            other_plan != plan_name
                            and abs(mentioned_price - other_price) < 1
                        ):
                            errors.append(f"Plan '{plan_name}' priced at ${
                                    mentioned_price:.0f}, " f"but that's the price of '{other_plan}' (${
                                    correct_price:.0f})")
                            error_positions.append(
                                (
                                    max(0, plan_start - 20),
                                    min(len(response), plan_end + 50),
                                )
                            )

        # Check for plan names with wrong casing / spacing used
        # to refer to different plans
        plan_variants: Dict[str, str] = {
            "mini parwa": "Mini PARWA ($999)",
            "parwa": "PARWA ($2,499)",
            "parwa high": "PARWA High ($3,999)",
        }
        for variant, full_name in plan_variants.items():
            if variant in response_lower:
                idx = response_lower.index(variant)
                # Check if it's mixed with wrong price in same sentence
                sentence_start = response.rfind(".", 0, idx) + 1
                sentence_end = response.find(".", idx)
                if sentence_end == -1:
                    sentence_end = len(response)
                sentence = response[sentence_start:sentence_end].lower()

                other_prices = {p: v for p, v in KNOWN_PLANS.items() if p != variant}
                for other_plan, other_price in other_prices.items():
                    price_pattern = rf"\${other_price:,.0f}"
                    if (
                        re.search(price_pattern, sentence)
                        and other_plan not in sentence
                    ):
                        errors.append(
                            f"Price ${
                                other_price:,.0f} associated with wrong plan '{variant}'"
                        )
                        error_positions.append((sentence_start, sentence_end))

        if not errors:
            return None

        confidence = 0.9 if len(errors) >= 2 else 0.80
        start = error_positions[0][0] if error_positions else 0
        end = error_positions[-1][1] if error_positions else len(response)

        return HallucinationMatch(
            pattern_id="P06_entity_confusion",
            pattern_name="Entity confusion",
            confidence=round(confidence, 4),
            evidence=f"Entity errors: {'; '.join(errors[:3])}",
            start=start,
            end=end,
            severity="high" if confidence >= 0.9 else "medium",
        )

    # ── Pattern 7: Policy Fabrication ───────────────────────────

    def _detect_policy_fabrication(
        self,
        response: str,
    ) -> HallucinationMatch | None:
        """P07: Detect fabricated policies, terms, or conditions.

        Flags when policy language is followed by specific claims
        about refunds, SLAs, or guarantees. Confidence: 0.6-0.8.
        """
        policy_matches = list(RE_POLICY_CLAIMS.finditer(response))
        if not policy_matches:
            return None

        for pm in policy_matches:
            # Check if followed by specific claims within 120 chars
            after = response[pm.end() : pm.end() + 120]
            specific_claims = RE_REFUND_SLA_CLAIMS.findall(after)

            if specific_claims:
                # Count specific claims to boost confidence
                claim_count = len(specific_claims)
                confidence = 0.6 + min(0.2, claim_count * 0.05)
                severity = "high" if confidence >= 0.75 else "medium"
                evidence_text = response[pm.start() : pm.end() + 120].strip()
                return HallucinationMatch(
                    pattern_id="P07_policy_fabrication",
                    pattern_name="Policy fabrication",
                    confidence=round(confidence, 4),
                    evidence=f"Policy claim with specific details: '{evidence_text[:150]}'",
                    start=pm.start(),
                    end=pm.end() + 120,
                    severity=severity,
                )

        # Even without specific claims, multiple policy references is
        # suspicious in a customer-facing response
        if len(policy_matches) >= 2:
            first = policy_matches[0]
            last = policy_matches[-1]
            return HallucinationMatch(
                pattern_id="P07_policy_fabrication",
                pattern_name="Policy fabrication",
                confidence=0.60,
                evidence=f"Multiple policy references ({
                    len(policy_matches)}) without verifiable source",
                start=first.start(),
                end=last.end(),
                severity="medium",
            )

        return None

    # ── Pattern 8: False Feature Claims ─────────────────────────

    def _detect_false_feature_claims(
        self,
        response: str,
    ) -> HallucinationMatch | None:
        """P08: Detect claims about features that may not exist.

        Checks feature claims against known feature names from
        FEATURE_REGISTRY. Confidence: 0.7-0.9.
        """
        feature_matches = list(RE_FEATURE_CLAIMS.finditer(response))
        if not feature_matches:
            return None

        response_lower = response.lower()

        # Try to import FEATURE_REGISTRY from variant_capability_service
        known_features: Set[str] = set(KNOWN_FEATURE_PHRASES)
        try:
            from app.services.variant_capability_service import (
                FEATURE_REGISTRY as _FR,
            )  # noqa: E501

            for _fid, finfo in _FR.items():
                feat_name = finfo.get("name", "").lower()
                if feat_name:
                    known_features.add(feat_name)
        except Exception:
            logger.debug(
                "Could not import FEATURE_REGISTRY, using built-in list",
            )

        suspicious_claims: List[str] = []
        claim_positions: List[Tuple[int, int]] = []

        for fm in feature_matches:
            # Extract the claim context (the feature claim + ~60 chars)
            claim_start = fm.start()
            claim_end = min(len(response), fm.end() + 80)
            claim_text = response[claim_start:claim_end].lower()

            # Extract what feature is being claimed
            words_after = claim_text[fm.end() - fm.start() :]
            # Look for feature-like nouns after the claim verb
            feature_nouns = re.findall(
                r"(?:[\w\s-]{2,25}?)(?:\.|,|;|$)",
                words_after,
            )

            for noun_phrase in feature_nouns[:2]:
                noun_phrase_clean = noun_phrase.strip().rstrip(".,;:")
                if len(noun_phrase_clean) < 3:
                    continue

                # Check if this feature phrase is known
                is_known = any(known in noun_phrase_clean for known in known_features)

                if not is_known:
                    suspicious_claims.append(
                        f"Claimed feature not in registry: '{noun_phrase_clean[:50]}'"
                    )
                    claim_positions.append((claim_start, claim_end))
                    break  # One suspicious claim per feature match is enough

        if not suspicious_claims:
            return None

        confidence = 0.7 + min(0.2, len(suspicious_claims) * 0.05)
        start = claim_positions[0][0] if claim_positions else 0
        end = claim_positions[-1][1] if claim_positions else len(response)

        return HallucinationMatch(
            pattern_id="P08_false_feature_claims",
            pattern_name="False feature claims",
            confidence=round(confidence, 4),
            evidence=f"Unverified feature claims: {'; '.join(suspicious_claims[:3])}",
            start=start,
            end=end,
            severity="medium" if confidence < 0.85 else "high",
        )

    # ── Pattern 9: Circular Reasoning ───────────────────────────

    def _detect_circular_reasoning(
        self,
        response: str,
    ) -> HallucinationMatch | None:
        """P09: Detect circular reasoning in the response.

        Looks for phrases that loop back to their own premise
        and repeated phrases. Confidence: 0.5-0.7.
        """
        # Check for circular reasoning starters
        circular_matches = list(RE_CIRCULAR_STARTERS.finditer(response))
        if not circular_matches:
            # Also check for direct repetition
            return self._detect_repeated_phrases(response)

        circular_count = len(circular_matches)

        # Check for specific circular structures
        # "X is true. Therefore, X is true."
        sentences = re.split(r"[.!?]+", response)
        sentence_set: Set[str] = set()
        repeated_count = 0

        for sent in sentences:
            sent_clean = re.sub(r"\s+", " ", sent.strip().lower())
            if len(sent_clean) < 20:
                continue
            if sent_clean in sentence_set:
                repeated_count += 1
            sentence_set.add(sent_clean)

        # Check for "X because X" pattern within the same sentence
        because_circular = 0
        for sent in sentences:
            sent_lower = sent.strip().lower()
            if "because" in sent_lower:
                # Split on "because" and check if the clause after
                # restates the clause before
                parts = sent_lower.split("because")
                if len(parts) >= 2:
                    before_words = set(re.findall(r"\b\w{4,}\b", parts[0]))
                    after_words = set(re.findall(r"\b\w{4,}\b", parts[1]))
                    if before_words and after_words:
                        overlap = before_words & after_words
                        # Check pairwise overlap OR check if any word
                        # appears 2+ times across all parts (repetition)
                        ratio = len(overlap) / min(len(before_words), len(after_words))
                        all_parts_words = re.findall(r"\b\w{4,}\b", sent_lower)
                        word_counts = {}
                        for w in all_parts_words:
                            word_counts[w] = word_counts.get(w, 0) + 1
                        repeated_key_words = sum(
                            1 for c in word_counts.values() if c >= 2
                        )
                        if ratio >= 0.2 or repeated_key_words >= 2:
                            because_circular += 1

        # Combine signals
        if circular_count >= 2 or repeated_count >= 2 or because_circular >= 1:
            confidence = 0.5 + min(
                0.2, (circular_count + repeated_count + because_circular) * 0.05
            )
            first_circular = circular_matches[0] if circular_matches else None
            start = first_circular.start() if first_circular else 0
            evidence_parts: List[str] = []
            if circular_count > 0:
                evidence_parts.append(f"circular starters: {circular_count}")
            if repeated_count > 0:
                evidence_parts.append(f"repeated sentences: {repeated_count}")
            if because_circular > 0:
                evidence_parts.append(f"'because' circular: {because_circular}")

            return HallucinationMatch(
                pattern_id="P09_circular_reasoning",
                pattern_name="Circular reasoning",
                confidence=round(min(0.7, confidence), 4),
                evidence=f"Circular reasoning detected: {'; '.join(evidence_parts)}",
                start=start,
                end=start + 100,
                severity="medium" if confidence >= 0.6 else "low",
            )

        return None

    def _detect_repeated_phrases(
        self,
        response: str,
    ) -> HallucinationMatch | None:
        """Helper: detect repeated phrases (fallback for P09)."""
        # Look for repeated word sequences of 5+ words
        words = response.split()
        phrase_len = 5
        phrase_counts: Dict[str, List[int]] = {}

        for i in range(len(words) - phrase_len + 1):
            phrase = " ".join(w.lower() for w in words[i : i + phrase_len])
            if phrase not in phrase_counts:
                phrase_counts[phrase] = []
            phrase_counts[phrase].append(i)

        for phrase, positions in phrase_counts.items():
            if len(positions) >= 2:
                # Build position in original string
                first_pos = sum(len(w) + 1 for w in words[: positions[0]])
                return HallucinationMatch(
                    pattern_id="P09_circular_reasoning",
                    pattern_name="Circular reasoning",
                    confidence=0.55,
                    evidence=f"Repeated phrase: '{phrase}'",
                    start=first_pos,
                    end=first_pos + len(phrase),
                    severity="low",
                )

        return None

    # ── Pattern 10: Fake Source Attribution ─────────────────────

    def _detect_fake_source_attribution(
        self,
        response: str,
    ) -> HallucinationMatch | None:
        """P10: Detect source citations that can't be verified.

        Flags 'according to', 'see section', etc. not backed by
        real references. Confidence: 0.6-0.8.
        """
        source_matches = list(RE_SOURCE_ATTRIBUTION.finditer(response))
        if not source_matches:
            return None

        suspicious_attributions: List[str] = []
        attr_positions: List[Tuple[int, int]] = []

        for sm in source_matches:
            after_text = response[sm.end() : sm.end() + 100]
            before_text = response[max(0, sm.start() - 30) : sm.start()]

            # Check if followed by a fake document reference
            has_fake_ref = bool(RE_FAKE_DOC_REFS.search(after_text))
            has_page_ref = bool(RE_PAGE_REFS.search(after_text))

            # Check if preceded by a real URL (which would be verifiable)
            has_real_url = bool(RE_URL.search(before_text))

            if (has_fake_ref or has_page_ref) and not has_real_url:
                full_text = response[sm.start() : sm.end() + 100].strip()
                suspicious_attributions.append(full_text[:120])
                attr_positions.append((sm.start(), sm.end() + 100))

        # Also flag source attributions that are vague
        for sm in source_matches:
            after_text = response[sm.end() : sm.end() + 60]
            # If followed by very generic text with no specific reference
            if (
                not RE_FAKE_DOC_REFS.search(after_text)
                and not RE_PAGE_REFS.search(after_text)
                and not RE_URL.search(after_text)
            ):
                # Vague source attribution
                words_after = after_text.split()[:5]
                if len(words_after) < 3:
                    full_text = response[sm.start() : sm.end() + 60].strip()
                    # Avoid duplicate from the loop above
                    if full_text[:80] not in [a[:80] for a in suspicious_attributions]:
                        suspicious_attributions.append(full_text[:120])
                        attr_positions.append((sm.start(), sm.end() + 60))

        if not suspicious_attributions:
            return None

        confidence = 0.6 + min(0.2, len(suspicious_attributions) * 0.05)
        start = attr_positions[0][0] if attr_positions else 0
        end = attr_positions[-1][1] if attr_positions else len(response)
        severity = "high" if confidence >= 0.75 else "medium"

        return HallucinationMatch(
            pattern_id="P10_fake_source_attribution",
            pattern_name="Source attribution without source",
            confidence=round(confidence, 4),
            evidence=f"Unverifiable source citations: {'; '.join(suspicious_attributions[:3])}",
            start=start,
            end=end,
            severity=severity,
        )

    # ── Pattern 11: Numerical Precision Hallucination ───────────

    def _detect_numerical_precision_hallucination(
        self,
        response: str,
    ) -> HallucinationMatch | None:
        """P11: Detect overly precise numbers that are likely fabricated.

        Flags suspiciously precise percentages (>2 decimal places),
        exact counts with commas, and oddly precise currency amounts.
        Confidence: 0.4-0.6.
        """
        flags: List[str] = []
        flag_positions: List[Tuple[int, int]] = []

        # Check for overly precise percentages (>2 decimal places)
        for m in RE_PRECISE_PERCENTAGE.finditer(response):
            pct_str = m.group(0)
            # Extract decimal part — any decimal precision is suspicious
            decimal_match = re.search(r"\.(\d+)%", pct_str)
            if decimal_match and len(decimal_match.group(1)) >= 1:
                flags.append(f"Overly precise percentage: {pct_str}")
                flag_positions.append((m.start(), m.end()))

        # Check for precise currency amounts (X,XXX.XX format)
        for m in RE_PRECISE_CURRENCY.finditer(response):
            flags.append(f"Suspiciously precise currency: {m.group(0)}")
            flag_positions.append((m.start(), m.end()))

        # Check for precise counts (X,XXX format with comma)
        for m in RE_PRECISE_COUNT.finditer(response):
            # Skip if it's a year (4 digits)
            num_str = m.group(0).replace(",", "")
            try:
                num_val = int(num_str)
                if 1900 <= num_val <= 2100:
                    continue  # Likely a year
            except ValueError:
                continue
            flags.append(f"Suspiciously precise count: {m.group(0)}")
            flag_positions.append((m.start(), m.end()))

        # Check for standalone precise decimals (not percentages, currency, or
        # counts)
        for m in RE_PRECISE_DECIMAL.finditer(response):
            # Skip if this is part of a percentage (already caught above)
            if response[m.end() : m.end() + 1] == "%":
                continue
            # Skip if preceded by $ (currency)
            if m.start() > 0 and response[m.start() - 1] == "$":
                continue
            decimal_val = m.group(0)
            decimal_match = re.search(r"\.(\d+)", decimal_val)
            if decimal_match and len(decimal_match.group(1)) >= 2:
                flags.append(f"Overly precise decimal: {decimal_val}")
                flag_positions.append((m.start(), m.end()))

        if not flags:
            return None

        # Confidence scales with number of flags
        confidence = 0.4 + min(0.2, len(flags) * 0.03)
        start = flag_positions[0][0] if flag_positions else 0
        end = flag_positions[-1][1] if flag_positions else len(response)

        return HallucinationMatch(
            pattern_id="P11_numerical_precision",
            pattern_name="Numerical precision hallucination",
            confidence=round(min(0.6, confidence), 4),
            evidence=f"Overly precise numbers: {'; '.join(flags[:4])}",
            start=start,
            end=end,
            severity="low",
        )

    # ── Pattern 12: Temporal Inconsistency ──────────────────────

    def _detect_temporal_inconsistency(
        self,
        response: str,
        conversation_history: list[dict],
    ) -> HallucinationMatch | None:
        """P12: Detect contradictions of dates/facts across conversation turns."""
        if not conversation_history:
            return None

        # Extract dates from conversation history (assistant messages only)
        history_dates: List[dict] = []
        for turn in conversation_history:
            content = turn.get("content", "")
            role = turn.get("role", "")
            if role != "assistant" or not content:
                continue
            # Extract MM/DD/YYYY dates
            for m in RE_DATE_MDY.finditer(content):
                history_dates.append(
                    {
                        "raw": m.group(0),
                        "month": int(m.group(1)),
                        "day": int(m.group(2)),
                        "year": int(m.group(3)),
                        "context": content[max(0, m.start() - 30) : m.end() + 10],
                    }
                )
            # Extract text month dates
            for m in RE_DATE_TEXT.finditer(content):
                month_name = re.match(
                    r"(January|February|March|April|May|June|July|"
                    r"August|September|October|November|December)",
                    m.group(0),
                    re.IGNORECASE,
                )
                if month_name:
                    month_num = _MONTH_NAMES.get(month_name.group(1).lower(), 0)
                    if month_num:
                        history_dates.append(
                            {
                                "raw": m.group(0),
                                "month": month_num,
                                "day": int(m.group(1)),
                                "year": int(m.group(2)),
                                "context": content[
                                    max(0, m.start() - 30) : m.end() + 10
                                ],
                            }
                        )

        if not history_dates:
            return None

        # Extract dates from current response
        response_dates: List[dict] = []
        for m in RE_DATE_MDY.finditer(response):
            response_dates.append(
                {
                    "raw": m.group(0),
                    "month": int(m.group(1)),
                    "day": int(m.group(2)),
                    "year": int(m.group(3)),
                }
            )
        for m in RE_DATE_TEXT.finditer(response):
            month_name = re.match(
                r"(January|February|March|April|May|June|July|"
                r"August|September|October|November|December)",
                m.group(0),
                re.IGNORECASE,
            )
            if month_name:
                month_num = _MONTH_NAMES.get(month_name.group(1).lower(), 0)
                if month_num:
                    response_dates.append(
                        {
                            "raw": m.group(0),
                            "month": month_num,
                            "day": int(m.group(1)),
                            "year": int(m.group(2)),
                        }
                    )

        if not response_dates:
            return None

        # Compare dates: find contradictions
        for hist_date in history_dates:
            for resp_date in response_dates:
                # If month or year or day differ, it's a contradiction
                if (
                    hist_date["month"] != resp_date["month"]
                    or hist_date["day"] != resp_date["day"]
                    or hist_date["year"] != resp_date["year"]
                ):
                    # But only if they reference similar context
                    # (similar surrounding words indicate same entity)
                    hist_context_words = set(
                        re.findall(r"\b\w{4,}\b", hist_date.get("context", "").lower())
                    )
                    resp_nearby = response
                    resp_context_words = set(
                        re.findall(r"\b\w{4,}\b", resp_nearby.lower())
                    )
                    # Check if there's any contextual overlap
                    overlap = hist_context_words & resp_context_words
                    if overlap or not hist_context_words:
                        # If there's overlap or we can't determine context,
                        # flag as temporal inconsistency
                        confidence = 0.75 if overlap else 0.60
                        evidence = f"Date contradiction: history said '{
                                hist_date['raw']}' " f"but response says '{
                                resp_date['raw']}'"
                        return HallucinationMatch(
                            pattern_id="P12_temporal_inconsistency",
                            pattern_name="Temporal inconsistency",
                            confidence=round(confidence, 4),
                            evidence=evidence,
                            start=0,
                            end=len(response),
                            severity="medium" if confidence < 0.7 else "high",
                        )

        return None

    # ── Helper Methods ──────────────────────────────────────────

    @staticmethod
    def _is_leap_year(year: int) -> bool:
        """Check if a year is a leap year."""
        if year % 4 != 0:
            return False
        if year % 100 != 0:
            return True
        return year % 400 == 0

    @staticmethod
    def _extract_claims(text: str) -> List[str]:
        """Extract factual claim sentences from text.

        Returns sentences that contain numbers, prices, dates,
        or copula verbs (is/are/was/were).
        """
        sentences = re.split(r"[.!?]+", text)
        claims: List[str] = []
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 10:
                continue
            # Must contain a factual indicator
            has_factual = bool(
                re.search(
                    r"\b\d\b|\$|is\s|are\s|was\s|were\s",
                    sent,
                    re.IGNORECASE,
                )
            )
            if has_factual:
                claims.append(sent)
        return claims
