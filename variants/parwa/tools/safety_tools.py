"""
PARWA Safety Tools.

Tools for performing safety checks on AI-generated content
including competitor mention detection, hallucination checks,
and content validation.
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone
import re

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class SafetyTools:
    """
    Tools for safety checks on AI responses.

    Provides utility functions for:
    - Competitor mention detection
    - Hallucination detection
    - Content validation
    - Response sanitization

    These tools are used by ParwaSafetyAgent and can also be
    used independently in workflows.
    """

    # Default competitor patterns
    COMPETITOR_PATTERNS: List[str] = [
        r"\bZendesk\b",
        r"\bFreshdesk\b",
        r"\bIntercom\b",
        r"\bHelp Scout\b",
        r"\bSalesforce Service Cloud\b",
    ]

    # Hallucination indicator patterns
    HALLUCINATION_PATTERNS: List[str] = [
        r"studies show that",
        r"research indicates",
        r"experts say that",
        r"according to experts",
        r"scientists have proven",
        r"it is a known fact",
    ]

    def __init__(
        self,
        company_id: Optional[UUID] = None,
        custom_competitor_patterns: Optional[List[str]] = None
    ) -> None:
        """
        Initialize Safety Tools.

        Args:
            company_id: Company UUID for data isolation
            custom_competitor_patterns: Additional competitor patterns
        """
        self._company_id = company_id
        self._competitor_patterns = self.COMPETITOR_PATTERNS.copy()
        if custom_competitor_patterns:
            self._competitor_patterns.extend(custom_competitor_patterns)

        self._check_history: List[Dict[str, Any]] = []

    async def check_competitor_mentions(
        self,
        text: str
    ) -> Dict[str, Any]:
        """
        Check for competitor mentions in text.

        Args:
            text: Text to check

        Returns:
            Dict with has_competitors boolean and matches list
        """
        if not text:
            return {"has_competitors": False, "matches": []}

        matches: List[Dict[str, str]] = []

        for pattern in self._competitor_patterns:
            found = re.findall(pattern, text, re.IGNORECASE)
            if found:
                matches.append({
                    "pattern": pattern,
                    "found": list(set(found)),
                })

        result = {
            "has_competitors": len(matches) > 0,
            "matches": matches,
            "check_time": datetime.now(timezone.utc).isoformat(),
        }

        if matches:
            logger.warning({
                "event": "competitor_mentions_found",
                "match_count": len(matches),
            })

        return result

    async def check_hallucination_indicators(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check for hallucination indicators.

        Detects patterns that might indicate fabricated or
        unverified information.

        Args:
            text: Text to check
            context: Optional context with source information

        Returns:
            Dict with indicators and confidence
        """
        if not text:
            return {"indicators": [], "risk_level": "none"}

        indicators: List[Dict[str, Any]] = []
        text_lower = text.lower()

        # Check for unsubstantiated claims
        for pattern in self.HALLUCINATION_PATTERNS:
            if re.search(pattern, text_lower):
                indicators.append({
                    "type": "unsubstantiated_claim",
                    "pattern": pattern,
                    "detail": f"Found pattern: {pattern}",
                })

        # Check for statistics without sources
        if context and not context.get("sources"):
            stat_matches = re.findall(r"\d+(?:\.\d+)?%", text)
            if stat_matches:
                indicators.append({
                    "type": "statistics_without_source",
                    "detail": f"Found {len(stat_matches)} statistics without source context",
                })

        # Check for fabricated URLs
        url_matches = re.findall(r"https?://[^\s]+", text)
        for url in url_matches:
            if any(fake in url.lower() for fake in ["example", "test", "fake"]):
                indicators.append({
                    "type": "suspicious_url",
                    "detail": f"Potentially fabricated URL: {url}",
                })

        # Calculate risk level
        if len(indicators) >= 3:
            risk_level = "high"
        elif len(indicators) >= 1:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "indicators": indicators,
            "indicator_count": len(indicators),
            "risk_level": risk_level,
            "check_time": datetime.now(timezone.utc).isoformat(),
        }

    async def validate_content(
        self,
        text: str,
        min_length: int = 10,
        max_length: int = 5000
    ) -> Dict[str, Any]:
        """
        Validate content quality.

        Args:
            text: Text to validate
            min_length: Minimum allowed length
            max_length: Maximum allowed length

        Returns:
            Dict with validation results
        """
        issues: List[str] = []

        if not text:
            issues.append("Content is empty")
        else:
            if len(text) < min_length:
                issues.append(f"Content too short (min {min_length} chars)")

            if len(text) > max_length:
                issues.append(f"Content too long (max {max_length} chars)")

            # Check for repetition
            words = text.lower().split()
            if len(words) > 10:
                unique_ratio = len(set(words)) / len(words)
                if unique_ratio < 0.3:
                    issues.append("High word repetition detected")

            # Check for incomplete sentences
            if text and not text.rstrip().endswith((".", "!", "?")):
                issues.append("Text doesn't end with proper punctuation")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "length": len(text) if text else 0,
        }

    async def sanitize_response(
        self,
        text: str,
        remove_competitors: bool = True
    ) -> Dict[str, Any]:
        """
        Sanitize a response by removing unsafe content.

        Args:
            text: Text to sanitize
            remove_competitors: Whether to remove competitor mentions

        Returns:
            Dict with sanitized text and modifications made
        """
        if not text:
            return {"sanitized": "", "modifications": []}

        sanitized = text
        modifications: List[Dict[str, str]] = []

        if remove_competitors:
            for pattern in self._competitor_patterns:
                matches = re.findall(pattern, sanitized, re.IGNORECASE)
                if matches:
                    sanitized = re.sub(
                        pattern,
                        "[COMPETITOR]",
                        sanitized,
                        flags=re.IGNORECASE
                    )
                    modifications.append({
                        "type": "competitor_removed",
                        "pattern": pattern,
                    })

        return {
            "sanitized": sanitized,
            "modifications": modifications,
            "was_modified": len(modifications) > 0,
        }

    async def run_full_safety_check(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run comprehensive safety check.

        Args:
            text: Text to check
            context: Optional context

        Returns:
            Complete safety report
        """
        check_time = datetime.now(timezone.utc).isoformat()

        # Run all checks
        competitor_check = await self.check_competitor_mentions(text)
        hallucination_check = await self.check_hallucination_indicators(text, context)
        content_check = await self.validate_content(text)
        sanitize_result = await self.sanitize_response(text)

        # Determine overall safety
        is_safe = (
            not competitor_check["has_competitors"]
            and hallucination_check["risk_level"] in ["low", "none"]
            and content_check["valid"]
        )

        report = {
            "is_safe": is_safe,
            "check_time": check_time,
            "checks": {
                "competitor_mentions": competitor_check,
                "hallucination": hallucination_check,
                "content_validation": content_check,
            },
            "sanitized_version": sanitize_result["sanitized"] if sanitize_result["was_modified"] else None,
            "issues": [],
        }

        # Compile issues
        if competitor_check["has_competitors"]:
            report["issues"].append("Competitor mentions detected")
        if hallucination_check["risk_level"] not in ["low", "none"]:
            report["issues"].append(f"Hallucination risk: {hallucination_check['risk_level']}")
        report["issues"].extend(content_check["issues"])

        # Track history
        self._check_history.append({
            "check_time": check_time,
            "is_safe": is_safe,
            "issues_count": len(report["issues"]),
        })

        self.log_check(report)

        return report

    def log_check(self, report: Dict[str, Any]) -> None:
        """Log safety check result."""
        logger.info({
            "event": "safety_check_completed",
            "is_safe": report["is_safe"],
            "issues_count": len(report.get("issues", [])),
        })

    def add_competitor_pattern(self, pattern: str) -> None:
        """Add a custom competitor pattern."""
        self._competitor_patterns.append(pattern)

    def get_stats(self) -> Dict[str, Any]:
        """Get safety tools statistics."""
        total_checks = len(self._check_history)
        safe_checks = sum(1 for c in self._check_history if c["is_safe"])

        return {
            "total_checks": total_checks,
            "safe_checks": safe_checks,
            "unsafe_checks": total_checks - safe_checks,
            "safety_rate": safe_checks / total_checks if total_checks > 0 else 1.0,
        }

    async def execute(
        self,
        action: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Execute a safety tool action.

        Args:
            action: Action to perform
            **kwargs: Action-specific arguments

        Returns:
            Result dict
        """
        text = kwargs.get("text", "")

        if action == "check_competitors":
            return await self.check_competitor_mentions(text)
        elif action == "check_hallucination":
            return await self.check_hallucination_indicators(
                text,
                kwargs.get("context")
            )
        elif action == "validate":
            return await self.validate_content(
                text,
                kwargs.get("min_length", 10),
                kwargs.get("max_length", 5000)
            )
        elif action == "sanitize":
            return await self.sanitize_response(
                text,
                kwargs.get("remove_competitors", True)
            )
        elif action == "full_check":
            return await self.run_full_safety_check(
                text,
                kwargs.get("context")
            )
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}
