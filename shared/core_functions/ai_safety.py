"""
PARWA AI Safety Module
Provides guardrails, prompt injection detection, and content filtering
for all AI agent interactions.
Depends on: config.py (Week 1 Day 2), logger.py (Week 1 Day 3)
"""

import re
from typing import Any, Dict, List, Optional

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)

# --- Prompt Injection Detection ---

INJECTION_PATTERNS: List[str] = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+the\s+above",
    r"disregard\s+(all\s+)?previous",
    r"you\s+are\s+now\s+a",
    r"pretend\s+you\s+are",
    r"act\s+as\s+if",
    r"system\s*:\s*",
    r"<\|im_start\|>",
    r"\[INST\]",
    r"forget\s+(everything|all)",
    r"new\s+instructions?\s*:",
    r"override\s+(your\s+)?instructions",
    r"jailbreak",
    r"dan\s+mode",
]


def detect_prompt_injection(text: str) -> Dict[str, Any]:
    """Detect potential prompt injection attempts in user input.

    Args:
        text: The user input text to analyze.

    Returns:
        A dict with 'is_injection' (bool) and 'matched_patterns' (list).
    """
    if not text or not isinstance(text, str):
        return {"is_injection": False, "matched_patterns": []}

    matched = []
    text_lower = text.lower()

    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            matched.append(pattern)

    is_injection = len(matched) > 0

    if is_injection:
        logger.warning(
            {"event": "prompt_injection_detected", "context": {"pattern_count": len(matched)}}
        )

    return {"is_injection": is_injection, "matched_patterns": matched}


# --- Content Filtering ---

BLOCKED_CONTENT_PATTERNS: List[str] = [
    r"\b(kill|murder|suicide|self[- ]harm)\b",
    r"\b(bomb|explosive|weapon)\b",
    r"\b(hack|exploit|crack)\b",
]

MEDICAL_ADVICE_PATTERNS: List[str] = [
    r"\b(diagnose|diagnosis|prescribe|prescription)\b",
    r"\b(take\s+\d+\s*mg)\b",
    r"\b(you\s+(have|might\s+have)\s+(a\s+)?disease)\b",
]


def filter_content(text: str) -> Dict[str, Any]:
    """Filter content for harmful or inappropriate material.

    Args:
        text: The text content to filter.

    Returns:
        A dict with 'is_safe' (bool), 'reason' (str), and 'category' (str).
    """
    if not text or not isinstance(text, str):
        return {"is_safe": True, "reason": "", "category": ""}

    text_lower = text.lower()

    for pattern in BLOCKED_CONTENT_PATTERNS:
        if re.search(pattern, text_lower):
            logger.warning(
                {"event": "blocked_content_detected", "context": {"category": "harmful_content"}}
            )
            return {
                "is_safe": False,
                "reason": "Content contains harmful material",
                "category": "harmful_content",
            }

    for pattern in MEDICAL_ADVICE_PATTERNS:
        if re.search(pattern, text_lower):
            logger.warning(
                {"event": "medical_advice_pattern_detected", "context": {"category": "medical_advice"}}
            )
            return {
                "is_safe": False,
                "reason": "AI must not provide medical advice — route to human",
                "category": "medical_advice",
            }

    return {"is_safe": True, "reason": "", "category": ""}


# --- Refund Gate Enforcement ---


def enforce_refund_gate(
    action: str,
    has_pending_approval: bool,
    approval_status: Optional[str] = None,
) -> Dict[str, Any]:
    """Enforce the sacred refund gate: Stripe NEVER called without approval.

    Args:
        action: The action being attempted (e.g. 'execute_refund').
        has_pending_approval: Whether a pending_approval record exists.
        approval_status: The status of the approval ('approved', 'denied', 'pending').

    Returns:
        A dict with 'allowed' (bool) and 'reason' (str).

    This is a CRITICAL safety function. The refund gate is non-negotiable.
    """
    if action != "execute_refund":
        return {"allowed": True, "reason": "Not a refund action"}

    if not has_pending_approval:
        logger.error(
            {"event": "refund_gate_breach_attempt", "context": {"action": action}}
        )
        return {
            "allowed": False,
            "reason": "No pending_approval record exists. Stripe MUST NOT be called.",
        }

    if approval_status != "approved":
        logger.warning(
            {"event": "refund_attempt_without_approval", "context": {"status": approval_status}}
        )
        return {
            "allowed": False,
            "reason": f"Approval status is '{approval_status}', not 'approved'. Stripe MUST NOT be called.",
        }

    logger.info(
        {"event": "refund_gate_passed", "context": {"action": action, "status": approval_status}}
    )
    return {"allowed": True, "reason": "Approval confirmed. Stripe call permitted."}


# --- AI Output Validation ---


def validate_ai_response(
    response: str, max_length: int = 5000
) -> Dict[str, Any]:
    """Validate AI-generated response before sending to user.

    Args:
        response: The AI-generated response text.
        max_length: Maximum allowed response length.

    Returns:
        A dict with 'is_valid' (bool) and 'issues' (list of strings).
    """
    issues: List[str] = []

    if not response or not isinstance(response, str):
        return {"is_valid": False, "issues": ["Response is empty or not a string"]}

    if len(response) > max_length:
        issues.append(f"Response exceeds max length of {max_length}")

    # Check for leaked system prompts
    system_leak_patterns = [
        r"you\s+are\s+an?\s+AI\s+assistant",
        r"my\s+instructions\s+say",
        r"according\s+to\s+my\s+system\s+prompt",
    ]
    for pattern in system_leak_patterns:
        if re.search(pattern, response, re.IGNORECASE):
            issues.append("Response may contain leaked system prompt information")
            break

    # Check for PII patterns that should not appear
    pii_patterns = [
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
        r"\b\d{16}\b",  # Credit card (16 digits)
    ]
    for pattern in pii_patterns:
        if re.search(pattern, response):
            issues.append("Response may contain PII (SSN or credit card number)")
            break

    return {"is_valid": len(issues) == 0, "issues": issues}
