"""
PARWA AI Guardrails.

Provides guardrails for AI responses to ensure:
- No hallucinations or fabricated information
- No competitor mentions
- No PII exposure
- Safe and compliant AI outputs

CRITICAL: These guardrails protect all AI-generated content.
"""
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from enum import Enum
import re
import os

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class GuardrailRule(str, Enum):
    """Types of guardrail rules."""
    HALLUCINATION = "hallucination"
    COMPETITOR_MENTION = "competitor_mention"
    PII_EXPOSURE = "pii_exposure"
    PROFANITY = "profanity"
    FINANCIAL_ADVICE = "financial_advice"
    LEGAL_ADVICE = "legal_advice"
    MEDICAL_ADVICE = "medical_advice"


class GuardrailResult(BaseModel):
    """Result from a guardrail check."""
    passed: bool = Field(default=True)
    rule: GuardrailRule
    violations: List[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)
    sanitized_content: Optional[str] = None
    processing_time_ms: float = Field(default=0)

    model_config = ConfigDict(use_enum_values=True)


class GuardrailsConfig(BaseModel):
    """Configuration for guardrails."""
    enable_hallucination_check: bool = Field(default=True)
    enable_competitor_check: bool = Field(default=True)
    enable_pii_check: bool = Field(default=True)
    enable_profanity_check: bool = Field(default=True)
    hallucination_threshold: float = Field(default=0.7, ge=0, le=1)
    competitor_block_mode: str = Field(default="strict")  # strict, warn, off
    pii_mask_char: str = Field(default="*")
    log_all_violations: bool = Field(default=True)

    model_config = ConfigDict()


class GuardrailsManager:
    """
    AI Guardrails Manager for PARWA.

    Provides comprehensive guardrails for AI-generated content:
    - Hallucination detection (fabricated information)
    - Competitor mention blocking
    - PII exposure detection and masking
    - Response sanitization

    Example:
        manager = GuardrailsManager()
        result = manager.check_hallucination(response, context)
        if not result.passed:
            response = manager.sanitize_response(response, ["hallucination"])
    """

    # Default competitor list - loaded from config in production
    DEFAULT_COMPETITORS = [
        "zendesk", "freshdesk", "intercom", "helpscout",
        "salesforce service cloud", "hubspot service hub",
        "zoho desk", "kayako", "gorilladesk"
    ]

    # PII patterns for detection
    PII_PATTERNS = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone_us": r'\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
        "phone_intl": r'\b\+?\d{1,3}[-.\s]?\d{1,14}\b',
        "ssn": r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
        "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        "ip_address": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        "date_of_birth": r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b',
        "api_key": r'\b(?:api[_-]?key|token|secret)[\s:=]+["\']?\w{16,}["\']?',
    }

    # Hallucination indicators
    HALLUCINATION_INDICATORS = [
        r'\bI (?:checked|verified|confirmed) with (?:our|the) (?:team|department|records)\b',
        r'\bAccording to (?:our|the) (?:database|records|system)\b',
        r'\bI can confirm that\b',
        r'\bI\'ve (?:reviewed|checked|verified)\b',
        r'\bThe (?:exact|specific) (?:amount|date|time) is\b',
        r'\bI have access to your (?:account|records|history)\b',
        r'\bI can see that\b',
        r'\bour records show\b',
    ]

    def __init__(
        self,
        config: Optional[GuardrailsConfig] = None,
        competitors: Optional[List[str]] = None
    ) -> None:
        """
        Initialize Guardrails Manager.

        Args:
            config: Optional configuration override
            competitors: Optional list of competitor names to block
        """
        self.config = config or GuardrailsConfig()

        # Load competitors from env or use defaults
        env_competitors = os.getenv("BLOCKED_COMPETITORS", "")
        if env_competitors:
            self._competitors = set(
                c.strip().lower() for c in env_competitors.split(",")
                if c.strip()
            )
        else:
            self._competitors = set(
                c.lower() for c in (competitors or self.DEFAULT_COMPETITORS)
            )

        # Tracking
        self._checks_performed = 0
        self._violations_detected = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "guardrails_initialized",
            "competitors_count": len(self._competitors),
            "hallucination_check": self.config.enable_hallucination_check,
            "competitor_check": self.config.enable_competitor_check,
            "pii_check": self.config.enable_pii_check,
        })

    def check_hallucination(
        self,
        response: str,
        context: Optional[Dict[str, Any]] = None
    ) -> GuardrailResult:
        """
        Check response for hallucination indicators.

        Detects fabricated information that the AI could not actually
        verify or confirm.

        Args:
            response: AI-generated response text
            context: Optional context with verified facts

        Returns:
            GuardrailResult with pass status and violations
        """
        start_time = datetime.now()
        violations = []

        if not self.config.enable_hallucination_check:
            return GuardrailResult(rule=GuardrailRule.HALLUCINATION)

        response_lower = response.lower()

        # Check for hallucination indicators
        for pattern in self.HALLUCINATION_INDICATORS:
            matches = re.findall(pattern, response_lower, re.IGNORECASE)
            if matches:
                violations.extend(matches)

        # Check for specific claims without context support
        if context:
            violations.extend(self._check_unsupported_claims(response, context))

        # Calculate confidence
        confidence = 1.0 - (len(violations) * 0.2)
        confidence = max(0.0, min(1.0, confidence))

        passed = len(violations) == 0 or confidence >= self.config.hallucination_threshold

        result = GuardrailResult(
            passed=passed,
            rule=GuardrailRule.HALLUCINATION,
            violations=violations[:5],  # Limit violations
            confidence=confidence,
            processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000
        )

        self._record_check(result)

        return result

    def check_competitor_mention(
        self,
        response: str
    ) -> GuardrailResult:
        """
        Check response for competitor mentions.

        Blocks or flags responses that mention competitor products
        or services.

        Args:
            response: AI-generated response text

        Returns:
            GuardrailResult with pass status and competitor names found
        """
        start_time = datetime.now()
        violations = []

        if not self.config.enable_competitor_check:
            return GuardrailResult(rule=GuardrailRule.COMPETITOR_MENTION)

        if self.config.competitor_block_mode == "off":
            return GuardrailResult(rule=GuardrailRule.COMPETITOR_MENTION)

        response_lower = response.lower()

        # Check for competitor names
        for competitor in self._competitors:
            if competitor in response_lower:
                violations.append(competitor)

        passed = len(violations) == 0

        result = GuardrailResult(
            passed=passed,
            rule=GuardrailRule.COMPETITOR_MENTION,
            violations=violations,
            processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000
        )

        self._record_check(result)

        return result

    def check_pii_exposure(
        self,
        response: str
    ) -> GuardrailResult:
        """
        Check response for PII exposure.

        Detects personally identifiable information that should
        not be exposed in AI responses.

        Args:
            response: AI-generated response text

        Returns:
            GuardrailResult with pass status and detected PII types
        """
        start_time = datetime.now()
        violations = []

        if not self.config.enable_pii_check:
            return GuardrailResult(rule=GuardrailRule.PII_EXPOSURE)

        # Check each PII pattern
        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = re.findall(pattern, response)
            if matches:
                violations.append(f"{pii_type}: {len(matches)} instance(s)")

        passed = len(violations) == 0

        result = GuardrailResult(
            passed=passed,
            rule=GuardrailRule.PII_EXPOSURE,
            violations=violations,
            processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000
        )

        self._record_check(result)

        return result

    def sanitize_response(
        self,
        response: str,
        rules: Optional[List[str]] = None
    ) -> str:
        """
        Sanitize response by applying guardrail rules.

        Args:
            response: Original response text
            rules: List of rules to apply (default: all enabled)

        Returns:
            Sanitized response text
        """
        sanitized = response
        rules_to_apply = rules or [
            GuardrailRule.HALLUCINATION.value,
            GuardrailRule.COMPETITOR_MENTION.value,
            GuardrailRule.PII_EXPOSURE.value,
        ]

        # Apply hallucination sanitization
        if GuardrailRule.HALLUCINATION.value in rules_to_apply:
            sanitized = self._sanitize_hallucinations(sanitized)

        # Apply competitor sanitization
        if GuardrailRule.COMPETITOR_MENTION.value in rules_to_apply:
            sanitized = self._sanitize_competitors(sanitized)

        # Apply PII sanitization
        if GuardrailRule.PII_EXPOSURE.value in rules_to_apply:
            sanitized = self._sanitize_pii(sanitized)

        if sanitized != response:
            logger.info({
                "event": "response_sanitized",
                "rules_applied": rules_to_apply,
                "original_length": len(response),
                "sanitized_length": len(sanitized),
            })

        return sanitized

    def get_blocked_patterns(self) -> List[str]:
        """
        Get list of blocked patterns.

        Returns:
            List of blocked competitor names and patterns
        """
        return list(self._competitors)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get guardrails statistics.

        Returns:
            Dict with stats
        """
        return {
            "checks_performed": self._checks_performed,
            "violations_detected": self._violations_detected,
            "violation_rate": (
                self._violations_detected / self._checks_performed
                if self._checks_performed > 0 else 0
            ),
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._checks_performed
                if self._checks_performed > 0 else 0
            ),
            "competitors_blocked": len(self._competitors),
        }

    def _check_unsupported_claims(
        self,
        response: str,
        context: Dict[str, Any]
    ) -> List[str]:
        """Check for claims not supported by context."""
        violations = []

        # Check for specific amounts mentioned
        amount_pattern = r'\$[\d,]+(?:\.\d{2})?'
        amounts = re.findall(amount_pattern, response)
        context_amounts = context.get("verified_amounts", [])

        for amount in amounts:
            if amount not in context_amounts:
                violations.append(f"Unverified amount: {amount}")

        # Check for specific dates mentioned
        date_pattern = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'
        dates = re.findall(date_pattern, response)
        context_dates = context.get("verified_dates", [])

        for date in dates:
            if date not in context_dates:
                violations.append(f"Unverified date: {date}")

        return violations

    def _sanitize_hallucinations(self, text: str) -> str:
        """Remove or modify hallucination indicators."""
        sanitized = text

        # Replace definitive claims with hedged language
        replacements = {
            "I can confirm that": "Based on the information available,",
            "I've verified": "It appears that",
            "I have access to your": "Regarding your",
            "our records show": "the information suggests",
            "I can see that": "It seems that",
        }

        for old, new in replacements.items():
            sanitized = sanitized.replace(old, new)

        return sanitized

    def _sanitize_competitors(self, text: str) -> str:
        """Mask competitor names in text."""
        sanitized = text

        for competitor in self._competitors:
            # Case-insensitive replacement
            pattern = re.compile(re.escape(competitor), re.IGNORECASE)
            sanitized = pattern.sub("[competitor]", sanitized)

        return sanitized

    def _sanitize_pii(self, text: str) -> str:
        """Mask PII in text."""
        sanitized = text
        mask = self.config.pii_mask_char

        # Mask emails
        sanitized = re.sub(
            self.PII_PATTERNS["email"],
            f"{mask * 3}@{mask * 3}.{mask * 3}",
            sanitized
        )

        # Mask phone numbers
        sanitized = re.sub(
            self.PII_PATTERNS["phone_us"],
            f"{mask * 3}-{mask * 3}-{mask * 4}",
            sanitized
        )

        # Mask SSN
        sanitized = re.sub(
            self.PII_PATTERNS["ssn"],
            f"{mask * 3}-{mask * 2}-{mask * 4}",
            sanitized
        )

        # Mask credit cards
        sanitized = re.sub(
            self.PII_PATTERNS["credit_card"],
            f"{mask * 4}-{mask * 4}-{mask * 4}-{mask * 4}",
            sanitized
        )

        return sanitized

    def _record_check(self, result: GuardrailResult) -> None:
        """Record check result for stats."""
        self._checks_performed += 1
        self._total_processing_time += result.processing_time_ms

        if not result.passed:
            self._violations_detected += 1

            if self.config.log_all_violations:
                logger.warning({
                    "event": "guardrail_violation",
                    "rule": result.rule,
                    "violations": result.violations,
                    "confidence": result.confidence,
                })


def get_guardrails_manager() -> GuardrailsManager:
    """
    Get a GuardrailsManager instance.

    Returns:
        GuardrailsManager instance
    """
    return GuardrailsManager()
