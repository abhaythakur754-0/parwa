"""
PARWA Safety Agent.

Handles safety checks including competitor mention blocking,
hallucination detection, and content validation.
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
import re

from variants.base_agents.base_agent import BaseAgent, AgentResponse
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


# Default competitor patterns (can be customized per company)
DEFAULT_COMPETITOR_PATTERNS: List[str] = [
    r"\bZendesk\b",
    r"\bFreshdesk\b",
    r"\bIntercom\b",
    r"\bHelp Scout\b",
    r"\bSalesforce Service Cloud\b",
]


class ParwaSafetyAgent(BaseAgent):
    """
    PARWA Safety Agent.

    Provides safety checks for AI-generated responses including:
    - Competitor mention detection and blocking
    - Hallucination detection
    - Content validation

    This agent ensures responses meet safety standards before
    being sent to customers.
    """

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize PARWA Safety Agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Optional configuration dictionary
            company_id: Company UUID for data isolation
        """
        super().__init__(agent_id, config, company_id)
        self._competitor_patterns = DEFAULT_COMPETITOR_PATTERNS.copy()
        # Load custom competitor patterns from config
        if config and "competitor_patterns" in config:
            self._competitor_patterns.extend(config["competitor_patterns"])

    def get_tier(self) -> str:
        """Return the processing tier for PARWA agents."""
        return "medium"

    def get_variant(self) -> str:
        """Return the PARWA variant identifier."""
        return "parwa"

    async def check_response(self, response: str) -> Dict[str, Any]:
        """
        Check a response for all safety issues.

        Runs all safety checks and returns a comprehensive report.

        Args:
            response: The response text to check

        Returns:
            Dict with overall safety status and individual check results
        """
        if not response:
            return {
                "safe": False,
                "reason": "Empty response",
                "checks": {},
            }

        checks: Dict[str, Dict[str, Any]] = {}
        all_safe = True
        issues: List[str] = []

        # Check for competitor mentions
        competitor_check = await self.block_competitor_mention(response)
        checks["competitor_mention"] = competitor_check
        if not competitor_check.get("safe", True):
            all_safe = False
            issues.append("Competitor mention detected")

        # Check for hallucination indicators
        hallucination_check = await self.check_hallucination(response, {})
        checks["hallucination"] = hallucination_check
        if hallucination_check.get("detected", False):
            all_safe = False
            issues.append("Potential hallucination detected")

        # Check content quality
        quality_check = self._check_content_quality(response)
        checks["content_quality"] = quality_check
        if not quality_check.get("passed", True):
            all_safe = False
            issues.append(quality_check.get("reason", "Content quality issue"))

        result = {
            "safe": all_safe,
            "issues": issues,
            "checks": checks,
            "response_length": len(response),
        }

        if not all_safe:
            logger.warning({
                "event": "safety_check_failed",
                "agent_id": self._agent_id,
                "issues": issues,
            })

        self.log_action("check_response", {
            "safe": all_safe,
            "issues_count": len(issues),
        })

        return result

    async def block_competitor_mention(
        self,
        response: str
    ) -> Dict[str, Any]:
        """
        Check for and block competitor mentions.

        Scans response for competitor names and returns blocking
        information if found.

        Args:
            response: The response text to check

        Returns:
            Dict with 'safe' boolean and 'matches' list if unsafe
        """
        if not response:
            return {"safe": True, "matches": []}

        matches: List[Dict[str, Any]] = []

        for pattern in self._competitor_patterns:
            found = re.findall(pattern, response, re.IGNORECASE)
            if found:
                matches.append({
                    "pattern": pattern,
                    "matches": list(set(found)),
                })

        is_safe = len(matches) == 0

        if not is_safe:
            logger.warning({
                "event": "competitor_mention_blocked",
                "agent_id": self._agent_id,
                "matches": [m["matches"] for m in matches],
            })

        self.log_action("block_competitor_mention", {
            "safe": is_safe,
            "matches_count": len(matches),
        })

        return {
            "safe": is_safe,
            "matches": matches,
            "sanitized_response": self._sanitize_competitors(response) if not is_safe else response,
        }

    async def check_hallucination(
        self,
        response: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Detect potential hallucinations in responses.

        Checks for common hallucination indicators like made-up
        facts, fabricated statistics, or inconsistent information.

        Args:
            response: The response text to check
            context: Context containing source information

        Returns:
            Dict with 'detected' boolean and 'indicators' list
        """
        if not response:
            return {"detected": False, "indicators": []}

        indicators: List[str] = []

        # Check for made-up statistics without sources
        stat_pattern = r"\d+(?:\.\d+)?%"
        stats = re.findall(stat_pattern, response)
        if stats and "sources" not in context:
            indicators.append("Statistics without source context")

        # Check for fabricated URLs
        url_pattern = r"https?://[^\s]+"
        urls = re.findall(url_pattern, response)
        for url in urls:
            # Check if URL seems legitimate (not obviously fake)
            if any(fake in url.lower() for fake in ["example.com", "fake", "test"]):
                indicators.append(f"Potentially fabricated URL: {url}")

        # Check for specific claims without context
        claim_patterns = [
            r"studies show",
            r"research indicates",
            r"experts say",
            r"according to experts",
        ]
        for pattern in claim_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                if "sources" not in context or not context["sources"]:
                    indicators.append(f"Unsubstantiated claim pattern: {pattern}")

        # Check for overly confident language without basis
        confident_patterns = [
            r"definitely",
            r"absolutely certain",
            r"guaranteed to",
        ]
        for pattern in confident_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                indicators.append(f"Overly confident language: {pattern}")

        detected = len(indicators) > 0

        if detected:
            logger.warning({
                "event": "hallucination_detected",
                "agent_id": self._agent_id,
                "indicators": indicators,
            })

        self.log_action("check_hallucination", {
            "detected": detected,
            "indicators_count": len(indicators),
        })

        return {
            "detected": detected,
            "indicators": indicators,
            "confidence": 0.7 if detected else 0.95,
        }

    def _check_content_quality(self, response: str) -> Dict[str, Any]:
        """
        Check content quality standards.

        Args:
            response: Response text to check

        Returns:
            Dict with quality check results
        """
        issues: List[str] = []

        # Check minimum length
        if len(response) < 10:
            issues.append("Response too short")

        # Check for repetition
        words = response.lower().split()
        if len(words) > 5:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < 0.3:
                issues.append("High word repetition detected")

        # Check for incomplete sentences
        if response and not response.rstrip().endswith((".", "!", "?")):
            issues.append("Response doesn't end with punctuation")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "reason": issues[0] if issues else None,
        }

    def _sanitize_competitors(self, response: str) -> str:
        """
        Sanitize response by removing competitor mentions.

        Args:
            response: Response text to sanitize

        Returns:
            Sanitized response with competitor names replaced
        """
        sanitized = response
        for pattern in self._competitor_patterns:
            sanitized = re.sub(
                pattern,
                "[COMPETITOR]",
                sanitized,
                flags=re.IGNORECASE
            )
        return sanitized

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process a safety check request.

        Args:
            input_data: Must contain 'action' and relevant data

        Returns:
            AgentResponse with safety check result
        """
        action = input_data.get("action", "check_response")
        response_text = input_data.get("response", "")

        if action == "check_response":
            result = await self.check_response(response_text)
        elif action == "block_competitor":
            result = await self.block_competitor_mention(response_text)
        elif action == "check_hallucination":
            result = await self.check_hallucination(
                response_text,
                input_data.get("context", {})
            )
        else:
            return AgentResponse(
                success=False,
                message=f"Unknown action: {action}",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        return AgentResponse(
            success=True,
            message=f"Safety action '{action}' completed",
            data=result,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    def add_competitor_pattern(self, pattern: str) -> None:
        """Add a custom competitor pattern."""
        self._competitor_patterns.append(pattern)

    def get_competitor_patterns(self) -> List[str]:
        """Get current competitor patterns."""
        return self._competitor_patterns.copy()
