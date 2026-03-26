"""
PARWA Junior Safety Workflow.

Runs comprehensive safety checks before AI responses are sent to users.
Integrates with AI safety module and guardrails for comprehensive protection.

PARWA Junior Features:
- Competitor mention blocking
- Hallucination detection
- PII exposure prevention
- Prompt injection detection
- Content filtering
- Medical/legal advice blocking
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

from variants.parwa.config import ParwaConfig, get_parwa_config
from shared.core_functions.logger import get_logger
from shared.core_functions.ai_safety import (
    detect_prompt_injection,
    filter_content,
    enforce_refund_gate,
    validate_ai_response,
)
from shared.guardrails.guardrails import (
    GuardrailsManager,
    GuardrailsConfig,
    GuardrailRule,
    GuardrailResult,
)

logger = get_logger(__name__)


class SafetyCheckType(Enum):
    """Types of safety checks."""
    PROMPT_INJECTION = "prompt_injection"
    CONTENT_FILTER = "content_filter"
    HALLUCINATION = "hallucination"
    COMPETITOR_MENTION = "competitor_mention"
    PII_EXPOSURE = "pii_exposure"
    REFUND_GATE = "refund_gate"
    RESPONSE_VALIDATION = "response_validation"


class SafetyStatus(Enum):
    """Status of safety check."""
    PASSED = "passed"
    BLOCKED = "blocked"
    SANITIZED = "sanitized"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class SafetyCheckResult:
    """Result from a single safety check."""
    check_type: SafetyCheckType
    status: SafetyStatus
    passed: bool
    message: str = ""
    violations: List[str] = field(default_factory=list)
    sanitized_content: Optional[str] = None
    confidence: float = 1.0


@dataclass
class SafetyWorkflowResult:
    """Result from complete safety workflow."""
    passed: bool
    status: SafetyStatus
    response: str
    sanitized_response: Optional[str] = None
    checks_run: int = 0
    checks_passed: int = 0
    checks_blocked: int = 0
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SafetyWorkflow:
    """
    Comprehensive safety workflow for PARWA Junior.

    Runs multiple safety checks before responses are sent:
    1. Prompt injection detection (input)
    2. Content filtering (input/output)
    3. Hallucination detection (output)
    4. Competitor mention blocking (output)
    5. PII exposure prevention (output)
    6. Refund gate enforcement (actions)
    7. Response validation (output)

    All checks are configurable and can be run independently.

    Example:
        workflow = SafetyWorkflow()
        result = await workflow.execute({
            "input": "What is your refund policy?",
            "response": "Our refund policy allows...",
            "action": "respond"
        })
    """

    def __init__(
        self,
        parwa_config: Optional[ParwaConfig] = None,
        guardrails_config: Optional[GuardrailsConfig] = None,
    ) -> None:
        """
        Initialize safety workflow.

        Args:
            parwa_config: PARWA Junior configuration
            guardrails_config: Guardrails configuration
        """
        self._config = parwa_config or get_parwa_config()
        self._guardrails = GuardrailsManager(config=guardrails_config)
        self._check_history: List[Dict[str, Any]] = []

    async def execute(self, safety_data: Dict[str, Any]) -> SafetyWorkflowResult:
        """
        Execute the complete safety workflow.

        Args:
            safety_data: Dict with:
                - input: User input text (optional)
                - response: AI-generated response (optional)
                - action: Action being attempted (optional)
                - has_pending_approval: For refund actions
                - approval_status: Status of approval
                - context: Verified context for hallucination check

        Returns:
            SafetyWorkflowResult with comprehensive safety status
        """
        user_input = safety_data.get("input", "")
        response = safety_data.get("response", "")
        action = safety_data.get("action", "respond")
        has_pending_approval = safety_data.get("has_pending_approval", False)
        approval_status = safety_data.get("approval_status")
        context = safety_data.get("context", {})

        checks_run = 0
        checks_passed = 0
        checks_blocked = 0
        violations: List[str] = []
        warnings: List[str] = []
        sanitized_response = response

        logger.info({
            "event": "safety_workflow_started",
            "has_input": bool(user_input),
            "has_response": bool(response),
            "action": action,
        })

        # Step 1: Check prompt injection (if input provided)
        if user_input:
            injection_result = self._check_prompt_injection(user_input)
            checks_run += 1
            if not injection_result.passed:
                checks_blocked += 1
                violations.extend(injection_result.violations)
                return SafetyWorkflowResult(
                    passed=False,
                    status=SafetyStatus.BLOCKED,
                    response="",
                    checks_run=checks_run,
                    checks_passed=checks_passed,
                    checks_blocked=checks_blocked,
                    violations=violations,
                    metadata={"block_reason": "prompt_injection"},
                )
            checks_passed += 1

        # Step 2: Content filter (input)
        if user_input:
            content_result = self._check_content_filter(user_input)
            checks_run += 1
            if not content_result.passed:
                checks_blocked += 1
                violations.append(content_result.message)
                return SafetyWorkflowResult(
                    passed=False,
                    status=SafetyStatus.BLOCKED,
                    response="",
                    checks_run=checks_run,
                    checks_passed=checks_passed,
                    checks_blocked=checks_blocked,
                    violations=violations,
                    metadata={"block_reason": content_result.message},
                )
            checks_passed += 1

        # Step 3: Refund gate enforcement (for refund actions)
        if action == "execute_refund":
            refund_result = self._check_refund_gate(
                action, has_pending_approval, approval_status
            )
            checks_run += 1
            if not refund_result.passed:
                checks_blocked += 1
                violations.append(refund_result.message)
                return SafetyWorkflowResult(
                    passed=False,
                    status=SafetyStatus.BLOCKED,
                    response="",
                    checks_run=checks_run,
                    checks_passed=checks_passed,
                    checks_blocked=checks_blocked,
                    violations=violations,
                    metadata={"block_reason": "refund_gate_violation"},
                )
            checks_passed += 1

        # Step 4: Hallucination check (output)
        if response:
            hallucination_result = self._check_hallucination(response, context)
            checks_run += 1
            if not hallucination_result.passed:
                warnings.extend(hallucination_result.violations)
                sanitized_response = self._guardrails.sanitize_response(
                    sanitized_response, [GuardrailRule.HALLUCINATION.value]
                )
            else:
                checks_passed += 1

        # Step 5: Competitor mention check (output)
        if response:
            competitor_result = self._check_competitor_mention(response)
            checks_run += 1
            if not competitor_result.passed:
                checks_blocked += 1
                violations.extend(competitor_result.violations)
                sanitized_response = self._guardrails.sanitize_response(
                    sanitized_response, [GuardrailRule.COMPETITOR_MENTION.value]
                )
            else:
                checks_passed += 1

        # Step 6: PII exposure check (output)
        if response:
            pii_result = self._check_pii_exposure(response)
            checks_run += 1
            if not pii_result.passed:
                warnings.extend(pii_result.violations)
                sanitized_response = self._guardrails.sanitize_response(
                    sanitized_response, [GuardrailRule.PII_EXPOSURE.value]
                )
            else:
                checks_passed += 1

        # Step 7: Response validation (output)
        if response:
            validation_result = self._check_response_validation(response)
            checks_run += 1
            if not validation_result.passed:
                warnings.extend(validation_result.violations)
            else:
                checks_passed += 1

        # Determine final status
        if checks_blocked > 0:
            final_status = SafetyStatus.BLOCKED
        elif sanitized_response != response:
            final_status = SafetyStatus.SANITIZED
        elif warnings:
            final_status = SafetyStatus.WARNING
        else:
            final_status = SafetyStatus.PASSED

        # Record check history
        self._record_workflow_run(
            checks_run, checks_passed, checks_blocked, violations, warnings
        )

        logger.info({
            "event": "safety_workflow_complete",
            "status": final_status.value,
            "checks_run": checks_run,
            "checks_passed": checks_passed,
            "checks_blocked": checks_blocked,
            "violations_count": len(violations),
            "warnings_count": len(warnings),
        })

        return SafetyWorkflowResult(
            passed=checks_blocked == 0,
            status=final_status,
            response=sanitized_response,
            sanitized_response=sanitized_response if sanitized_response != response else None,
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_blocked=checks_blocked,
            violations=violations,
            warnings=warnings,
            metadata={
                "variant": "parwa",
                "tier": "medium",
                "config_enabled": self._config.enable_safety_checks,
            },
        )

    def _check_prompt_injection(self, text: str) -> SafetyCheckResult:
        """
        Check for prompt injection attempts.

        Args:
            text: User input text

        Returns:
            SafetyCheckResult
        """
        result = detect_prompt_injection(text)

        return SafetyCheckResult(
            check_type=SafetyCheckType.PROMPT_INJECTION,
            status=SafetyStatus.PASSED if not result["is_injection"] else SafetyStatus.BLOCKED,
            passed=not result["is_injection"],
            message="Prompt injection detected" if result["is_injection"] else "",
            violations=[p[:50] for p in result["matched_patterns"]],
        )

    def _check_content_filter(self, text: str) -> SafetyCheckResult:
        """
        Check content for harmful material.

        Args:
            text: Text to check

        Returns:
            SafetyCheckResult
        """
        result = filter_content(text)

        return SafetyCheckResult(
            check_type=SafetyCheckType.CONTENT_FILTER,
            status=SafetyStatus.PASSED if result["is_safe"] else SafetyStatus.BLOCKED,
            passed=result["is_safe"],
            message=result["reason"],
            violations=[result["category"]] if not result["is_safe"] else [],
        )

    def _check_refund_gate(
        self,
        action: str,
        has_pending_approval: bool,
        approval_status: Optional[str],
    ) -> SafetyCheckResult:
        """
        Enforce refund gate.

        CRITICAL: Paddle must NEVER be called without approval.

        Args:
            action: Action being attempted
            has_pending_approval: Whether approval exists
            approval_status: Status of approval

        Returns:
            SafetyCheckResult
        """
        result = enforce_refund_gate(action, has_pending_approval, approval_status)

        return SafetyCheckResult(
            check_type=SafetyCheckType.REFUND_GATE,
            status=SafetyStatus.PASSED if result["allowed"] else SafetyStatus.BLOCKED,
            passed=result["allowed"],
            message=result["reason"],
            violations=[result["reason"]] if not result["allowed"] else [],
        )

    def _check_hallucination(
        self,
        response: str,
        context: Dict[str, Any],
    ) -> SafetyCheckResult:
        """
        Check for hallucination indicators.

        Args:
            response: AI response
            context: Verified context

        Returns:
            SafetyCheckResult
        """
        result = self._guardrails.check_hallucination(response, context)

        return SafetyCheckResult(
            check_type=SafetyCheckType.HALLUCINATION,
            status=SafetyStatus.PASSED if result.passed else SafetyStatus.WARNING,
            passed=result.passed,
            message="Hallucination indicators detected" if not result.passed else "",
            violations=result.violations,
            confidence=result.confidence,
        )

    def _check_competitor_mention(self, response: str) -> SafetyCheckResult:
        """
        Check for competitor mentions.

        Args:
            response: AI response

        Returns:
            SafetyCheckResult
        """
        result = self._guardrails.check_competitor_mention(response)

        return SafetyCheckResult(
            check_type=SafetyCheckType.COMPETITOR_MENTION,
            status=SafetyStatus.PASSED if result.passed else SafetyStatus.BLOCKED,
            passed=result.passed,
            message="Competitor mention blocked" if not result.passed else "",
            violations=result.violations,
        )

    def _check_pii_exposure(self, response: str) -> SafetyCheckResult:
        """
        Check for PII exposure.

        Args:
            response: AI response

        Returns:
            SafetyCheckResult
        """
        result = self._guardrails.check_pii_exposure(response)

        return SafetyCheckResult(
            check_type=SafetyCheckType.PII_EXPOSURE,
            status=SafetyStatus.PASSED if result.passed else SafetyStatus.SANITIZED,
            passed=result.passed,
            message="PII detected and will be masked" if not result.passed else "",
            violations=result.violations,
        )

    def _check_response_validation(self, response: str) -> SafetyCheckResult:
        """
        Validate response format and content.

        Args:
            response: AI response

        Returns:
            SafetyCheckResult
        """
        result = validate_ai_response(response)

        return SafetyCheckResult(
            check_type=SafetyCheckType.RESPONSE_VALIDATION,
            status=SafetyStatus.PASSED if result["is_valid"] else SafetyStatus.WARNING,
            passed=result["is_valid"],
            message="Response validation issues" if not result["is_valid"] else "",
            violations=result["issues"],
        )

    def _record_workflow_run(
        self,
        checks_run: int,
        checks_passed: int,
        checks_blocked: int,
        violations: List[str],
        warnings: List[str],
    ) -> None:
        """
        Record workflow run in history.

        Args:
            checks_run: Number of checks run
            checks_passed: Number of checks passed
            checks_blocked: Number of checks blocked
            violations: List of violations
            warnings: List of warnings
        """
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks_run": checks_run,
            "checks_passed": checks_passed,
            "checks_blocked": checks_blocked,
            "violations_count": len(violations),
            "warnings_count": len(warnings),
        }
        self._check_history.append(record)

        # Keep only last 100 records
        if len(self._check_history) > 100:
            self._check_history = self._check_history[-100:]

    async def run_single_check(
        self,
        check_type: SafetyCheckType,
        data: Dict[str, Any],
    ) -> SafetyCheckResult:
        """
        Run a single safety check.

        Args:
            check_type: Type of check to run
            data: Data for the check

        Returns:
            SafetyCheckResult
        """
        if check_type == SafetyCheckType.PROMPT_INJECTION:
            return self._check_prompt_injection(data.get("text", ""))
        elif check_type == SafetyCheckType.CONTENT_FILTER:
            return self._check_content_filter(data.get("text", ""))
        elif check_type == SafetyCheckType.REFUND_GATE:
            return self._check_refund_gate(
                data.get("action", ""),
                data.get("has_pending_approval", False),
                data.get("approval_status"),
            )
        elif check_type == SafetyCheckType.HALLUCINATION:
            return self._check_hallucination(
                data.get("response", ""),
                data.get("context", {}),
            )
        elif check_type == SafetyCheckType.COMPETITOR_MENTION:
            return self._check_competitor_mention(data.get("response", ""))
        elif check_type == SafetyCheckType.PII_EXPOSURE:
            return self._check_pii_exposure(data.get("response", ""))
        elif check_type == SafetyCheckType.RESPONSE_VALIDATION:
            return self._check_response_validation(data.get("response", ""))
        else:
            return SafetyCheckResult(
                check_type=check_type,
                status=SafetyStatus.ERROR,
                passed=False,
                message=f"Unknown check type: {check_type}",
            )

    def get_workflow_name(self) -> str:
        """Get workflow name."""
        return "SafetyWorkflow"

    def get_variant(self) -> str:
        """Get variant name."""
        return "parwa"

    def get_tier(self) -> str:
        """Get AI tier used."""
        return "medium"

    def get_check_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent check history.

        Args:
            limit: Maximum records to return

        Returns:
            List of check records
        """
        return self._check_history[-limit:]

    def get_blocked_competitors(self) -> List[str]:
        """
        Get list of blocked competitor names.

        Returns:
            List of competitor names
        """
        return self._guardrails.get_blocked_patterns()
