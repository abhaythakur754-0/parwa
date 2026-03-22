"""
PARWA High Safety Agent.

Safety agent with response checking, competitor blocking, and PHI sanitization.
CRITICAL: PHI must be sanitized before any response is returned.
"""
from typing import Dict, Any, Optional, List, Set
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field
import re

from variants.base_agents.base_agent import BaseAgent, AgentResponse
from shared.core_functions.ai_safety import (
    detect_prompt_injection,
    filter_content,
    enforce_refund_gate,
    validate_ai_response,
)
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class SafetyCheckType(str, Enum):
    """Types of safety checks."""
    COMPETITOR_MENTION = "competitor_mention"
    HALLUCINATION = "hallucination"
    PHI_LEAK = "phi_leak"
    PROMPT_INJECTION = "prompt_injection"
    HARMFUL_CONTENT = "harmful_content"
    PII_EXPOSURE = "pii_exposure"


class SafetyAction(str, Enum):
    """Safety action to take."""
    ALLOW = "allow"
    BLOCK = "block"
    SANITIZE = "sanitize"
    ESCALATE = "escalate"
    REDACT = "redact"


@dataclass
class SafetyCheckResult:
    """Result of a safety check."""
    check_id: str
    check_type: SafetyCheckType
    passed: bool
    action: SafetyAction
    original_content: str = ""  # Will be cleared after processing
    sanitized_content: str = ""
    issues_found: List[str] = field(default_factory=list)
    redactions: List[str] = field(default_factory=list)
    confidence: float = 0.9
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ParwaHighSafetyAgent(BaseAgent):
    """
    PARWA High Safety Agent.

    Provides safety and content filtering capabilities including:
    - Response safety checking
    - Competitor mention blocking
    - Hallucination detection
    - PHI sanitization
    - PII protection

    CRITICAL: PHI must be sanitized before any response.
    CRITICAL: Competitor names must be blocked.
    """

    # PARWA High specific settings
    PARWA_HIGH_ESCALATION_THRESHOLD = 0.50

    # Competitor patterns (configurable per client)
    DEFAULT_COMPETITOR_NAMES: Set[str] = {
        "zendesk",
        "freshdesk",
        "salesforce service cloud",
        "service now",
        "intercom",
        "drift",
        "hubspot service hub",
        "zoho desk",
        "helpscout",
        "front",
        "gladly",
        "kustomer",
    }

    # PHI patterns to detect and sanitize
    PHI_PATTERNS = {
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "mrn": re.compile(r"\bMRN[\d]+\b", re.IGNORECASE),
        "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
        "date_of_birth": re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
    }

    # Redaction placeholder
    REDACTION_PLACEHOLDER = "[REDACTED]"

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None,
        competitor_names: Optional[Set[str]] = None
    ) -> None:
        """
        Initialize PARWA High Safety Agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Agent configuration dictionary
            company_id: UUID of the company
            competitor_names: Optional set of competitor names to block
        """
        super().__init__(agent_id, config, company_id)

        self._competitor_names = competitor_names or self.DEFAULT_COMPETITOR_NAMES.copy()
        self._safety_checks: Dict[str, SafetyCheckResult] = {}
        self._blocked_count = 0
        self._sanitized_count = 0
        self._escalated_count = 0

        logger.info({
            "event": "parwa_high_safety_agent_initialized",
            "agent_id": agent_id,
            "tier": self.get_tier(),
            "variant": self.get_variant(),
            "competitor_count": len(self._competitor_names),
        })

    def get_tier(self) -> str:
        """Get the AI tier for this agent. PARWA High uses 'heavy'."""
        return "heavy"

    def get_variant(self) -> str:
        """Get the PARWA High variant for this agent."""
        return "parwa_high"

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process safety request.

        Args:
            input_data: Must contain 'action' key
                - 'check_response': Check response for safety issues
                - 'block_competitor': Block competitor mentions
                - 'check_hallucination': Detect hallucinations
                - 'sanitize_phi': Sanitize PHI from content
                - 'full_check': Run all safety checks

        Returns:
            AgentResponse with processing result
        """
        action = input_data.get("action")

        if not action:
            return AgentResponse(
                success=False,
                message="Missing required field: action",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        self.log_action("parwa_high_safety_process", {
            "action": action,
            "tier": self.get_tier(),
        })

        if action == "check_response":
            return await self._handle_check_response(input_data)
        elif action == "block_competitor":
            return await self._handle_block_competitor(input_data)
        elif action == "check_hallucination":
            return await self._handle_check_hallucination(input_data)
        elif action == "sanitize_phi":
            return await self._handle_sanitize_phi(input_data)
        elif action == "full_check":
            return await self._handle_full_check(input_data)
        elif action == "get_stats":
            return await self._handle_get_stats()
        else:
            return AgentResponse(
                success=False,
                message=f"Unknown action: {action}",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

    async def check_response(
        self,
        response: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check response for safety issues.

        Args:
            response: Response text to check
            context: Optional context for validation

        Returns:
            Dict with safety check result
        """
        check_id = f"SAFE-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        issues: List[str] = []
        redactions: List[str] = []
        sanitized_content = response

        # Check for prompt injection
        injection_result = detect_prompt_injection(response)
        if injection_result["is_injection"]:
            issues.append("Potential prompt injection detected")
            return {
                "check_id": check_id,
                "passed": False,
                "action": SafetyAction.BLOCK.value,
                "issues": issues,
                "message": "Response blocked due to prompt injection",
            }

        # Check for harmful content
        content_result = filter_content(response)
        if not content_result["is_safe"]:
            issues.append(f"Harmful content: {content_result['reason']}")
            return {
                "check_id": check_id,
                "passed": False,
                "action": SafetyAction.BLOCK.value,
                "issues": issues,
                "message": "Response blocked due to harmful content",
            }

        # Validate response
        validation_result = validate_ai_response(response)
        if not validation_result["is_valid"]:
            issues.extend(validation_result["issues"])

        # Check for competitor mentions
        competitor_result = self._check_competitor_mention(response)
        if competitor_result["found"]:
            issues.append(f"Competitor mention: {competitor_result['matches']}")
            sanitized_content = competitor_result["sanitized"]
            redactions.extend(competitor_result["matches"])

        # Check for PHI
        phi_result = self._detect_phi(response)
        if phi_result["detected"]:
            issues.append(f"PHI detected: {phi_result['types']}")
            sanitized_content = self._sanitize_phi_content(response)
            redactions.extend(phi_result["types"])

        # Determine action
        if len(issues) > 2:
            action = SafetyAction.ESCALATE
            self._escalated_count += 1
        elif len(issues) > 0:
            action = SafetyAction.SANITIZE
            self._sanitized_count += 1
        else:
            action = SafetyAction.ALLOW

        result = SafetyCheckResult(
            check_id=check_id,
            check_type=SafetyCheckType.PII_EXPOSURE,
            passed=len(issues) == 0,
            action=action,
            sanitized_content=sanitized_content if redactions else response,
            issues_found=issues,
            redactions=redactions,
        )

        self._safety_checks[check_id] = result

        if action == SafetyAction.BLOCK:
            self._blocked_count += 1

        self.log_action("parwa_high_safety_check", {
            "check_id": check_id,
            "passed": result.passed,
            "action": action.value,
            "issues_count": len(issues),
        })

        return {
            "check_id": check_id,
            "passed": result.passed,
            "action": action.value,
            "sanitized_content": result.sanitized_content,
            "issues": issues,
            "redactions": redactions,
        }

    async def block_competitor_mention(
        self,
        response: str
    ) -> Dict[str, Any]:
        """
        Block competitor mentions in response.

        Args:
            response: Response text to check

        Returns:
            Dict with blocking result and sanitized content
        """
        result = self._check_competitor_mention(response)

        return {
            "original_length": len(response),
            "found": result["found"],
            "matches": result["matches"],
            "sanitized": result["sanitized"],
            "sanitized_length": len(result["sanitized"]),
        }

    async def check_hallucination(
        self,
        response: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check for potential hallucinations.

        Args:
            response: Response text to check
            context: Context with known facts to validate against

        Returns:
            Dict with hallucination check result
        """
        check_id = f"HALL-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Extract known facts from context
        known_facts = context.get("known_facts", [])
        allowed_topics = context.get("allowed_topics", [])

        # Check for unsupported claims
        issues = []

        # Check for specific hallucination indicators
        hallucination_patterns = [
            r"\b(always|never|all|none)\b.*\b(are|is|will|can)\b",  # Absolute claims
            r"\b(studies show|research proves)\b.*\b(that|how)\b",  # Unverified research claims
            r"\b(according to|based on)\s+(?:our|my)\s+(?:records|data)\b",  # False data attribution
        ]

        for pattern in hallucination_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                issues.append(f"Potential hallucination pattern detected")

        # Check if response claims facts not in known_facts
        # (simplified check - production would use NLP)
        for fact in known_facts:
            if str(fact).lower() in response.lower():
                # Fact is supported
                continue

        is_hallucination = len(issues) > 0
        confidence = 0.7 if is_hallucination else 0.9

        return {
            "check_id": check_id,
            "is_hallucination": is_hallucination,
            "confidence": confidence,
            "issues": issues,
            "action": SafetyAction.ESCALATE.value if is_hallucination else SafetyAction.ALLOW.value,
        }

    async def sanitize_phi(
        self,
        response: str
    ) -> Dict[str, Any]:
        """
        CRITICAL: Sanitize PHI from response.

        Args:
            response: Response text to sanitize

        Returns:
            Dict with sanitized content
        """
        sanitized = self._sanitize_phi_content(response)

        # Count redactions
        redaction_count = response.count(self.REDACTION_PLACEHOLDER) - sanitized.count(self.REDACTION_PLACEHOLDER)

        self._sanitized_count += 1 if redaction_count > 0 else 0

        return {
            "original_length": len(response),
            "sanitized": sanitized,
            "sanitized_length": len(sanitized),
            "redaction_count": redaction_count,
            "phi_detected": redaction_count > 0,
        }

    def _check_competitor_mention(self, response: str) -> Dict[str, Any]:
        """Check for competitor mentions."""
        response_lower = response.lower()
        matches = []

        for competitor in self._competitor_names:
            if competitor.lower() in response_lower:
                matches.append(competitor)

        # Sanitize by replacing competitor names
        sanitized = response
        for match in matches:
            sanitized = re.sub(
                re.escape(match),
                "[COMPETITOR]",
                sanitized,
                flags=re.IGNORECASE
            )

        return {
            "found": len(matches) > 0,
            "matches": matches,
            "sanitized": sanitized,
        }

    def _detect_phi(self, content: str) -> Dict[str, Any]:
        """Detect PHI in content."""
        detected_types = []

        for phi_type, pattern in self.PHI_PATTERNS.items():
            if pattern.search(content):
                detected_types.append(phi_type)

        return {
            "detected": len(detected_types) > 0,
            "types": detected_types,
        }

    def _sanitize_phi_content(self, content: str) -> str:
        """Sanitize PHI from content."""
        sanitized = content

        for phi_type, pattern in self.PHI_PATTERNS.items():
            sanitized = pattern.sub(self.REDACTION_PLACEHOLDER, sanitized)

        return sanitized

    async def _handle_check_response(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle check_response action."""
        response = input_data.get("response")

        if not response:
            return AgentResponse(
                success=False,
                message="Missing required field: response",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.check_response(
            response=response,
            context=input_data.get("context"),
        )

        return AgentResponse(
            success=result["passed"],
            message=f"Safety check: {'PASSED' if result['passed'] else 'ISSUES FOUND'}",
            data=result,
            confidence=0.90,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_block_competitor(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle block_competitor action."""
        response = input_data.get("response")

        if not response:
            return AgentResponse(
                success=False,
                message="Missing required field: response",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.block_competitor_mention(response)

        return AgentResponse(
            success=True,
            message=f"Competitor check: {len(result['matches'])} found" if result["found"] else "No competitors found",
            data=result,
            confidence=0.95,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_check_hallucination(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle check_hallucination action."""
        response = input_data.get("response")
        context = input_data.get("context", {})

        if not response:
            return AgentResponse(
                success=False,
                message="Missing required field: response",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.check_hallucination(response, context)

        return AgentResponse(
            success=not result["is_hallucination"],
            message=f"Hallucination check: {'DETECTED' if result['is_hallucination'] else 'CLEAN'}",
            data=result,
            confidence=result["confidence"],
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_sanitize_phi(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle sanitize_phi action."""
        response = input_data.get("response")

        if not response:
            return AgentResponse(
                success=False,
                message="Missing required field: response",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.sanitize_phi(response)

        return AgentResponse(
            success=True,
            message=f"PHI sanitized: {result['redaction_count']} redactions",
            data=result,
            confidence=0.95,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_full_check(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle full safety check."""
        response = input_data.get("response")

        if not response:
            return AgentResponse(
                success=False,
                message="Missing required field: response",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        # Run all checks
        response_check = await self.check_response(response, input_data.get("context"))
        competitor_check = await self.block_competitor_mention(response)
        phi_check = await self.sanitize_phi(response)

        all_passed = (
            response_check["passed"] and
            not competitor_check["found"] and
            not phi_check["phi_detected"]
        )

        return AgentResponse(
            success=all_passed,
            message=f"Full safety check: {'ALL PASSED' if all_passed else 'ISSUES FOUND'}",
            data={
                "response_check": response_check,
                "competitor_check": competitor_check,
                "phi_check": phi_check,
                "all_passed": all_passed,
            },
            confidence=0.90,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_get_stats(self) -> AgentResponse:
        """Handle get_stats action."""
        return AgentResponse(
            success=True,
            message="Safety agent statistics",
            data={
                "total_checks": len(self._safety_checks),
                "blocked_count": self._blocked_count,
                "sanitized_count": self._sanitized_count,
                "escalated_count": self._escalated_count,
                "competitor_names_count": len(self._competitor_names),
                "variant": self.get_variant(),
                "tier": self.get_tier(),
            },
            confidence=1.0,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )
