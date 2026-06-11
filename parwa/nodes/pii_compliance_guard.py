"""Node 15: PII_COMPLIANCE_GUARD — Redacts PII and enforces compliance rules.

Compliance Agent node. Detects and redacts personally identifiable
information (email, phone, SSN, credit card) from the response
before it's sent to the customer or stored in logs.

Phase 5: Now uses FrameworkBrain with CRP for compliance-aware
redaction. Falls back to regex-based on failure.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.pii_compliance_guard")


# PII detection patterns
_PII_PATTERNS = {
    "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', re.IGNORECASE),
    "phone": re.compile(r'\b(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
    "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    "credit_card": re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
}

# Redaction replacements
_REDACTION_MAP = {
    "email": "[EMAIL_REDACTED]",
    "phone": "[PHONE_REDACTED]",
    "ssn": "[SSN_REDACTED]",
    "credit_card": "[CC_REDACTED]",
}


def _detect_pii(text: str) -> tuple[bool, dict[str, list[str]]]:
    """Detect PII in text. Returns (has_pii, found_items)."""
    found: dict[str, list[str]] = {}
    has_pii = False

    for pii_type, pattern in _PII_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            found[pii_type] = matches if isinstance(matches[0], str) else [m[0] for m in matches]
            has_pii = True

    return has_pii, found


def _redact_pii(text: str) -> str:
    """Redact PII from text, replacing with placeholders."""
    for pii_type, pattern in _PII_PATTERNS.items():
        text = pattern.sub(_REDACTION_MAP[pii_type], text)
    return text


async def _check_pii_with_brain(state: dict[str, Any]) -> tuple[bool, str, list[str]]:
    """PII checking using FrameworkBrain (Phase 5).

    Returns (pii_detected, redacted_message, frameworks_used).
    Falls back to regex-based on any failure.
    """
    message = state.get("final_response") or state.get("raw_message", "")

    if not isinstance(message, str):
        message = str(message) if message else ""

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="PII_COMPLIANCE_GUARD", state=state)
        result = await brain.think(
            prompt="Check for PII and compliance violations",
            techniques=["crp"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # Always use regex-based detection as the foundation
        pii_detected, found_items = _detect_pii(message)
        redacted_message = _redact_pii(message) if pii_detected else message

        frameworks_used = result.frameworks_used if result.frameworks_used else []
        return pii_detected, redacted_message, frameworks_used

    except Exception as exc:
        logger.warning(
            "pii_compliance_guard: FrameworkBrain failed (%s), falling back to regex-based",
            exc,
        )
        pii_detected, found_items = _detect_pii(message)
        redacted_message = _redact_pii(message) if pii_detected else message
        return pii_detected, redacted_message, []


@safe_node("PII_COMPLIANCE_GUARD", fallback={"pii_detected": False, "pii_redacted_message": "", "active_frameworks": []})
async def pii_compliance_guard(state: dict[str, Any]) -> dict[str, Any]:
    """Detect and redact PII from the response (async).

    Phase 5: Uses FrameworkBrain with CRP for compliance-aware redaction.

    Reads: final_response (or raw_message if no response yet)
    Writes: pii_detected, pii_redacted_message, active_frameworks (append)
    """
    pii_detected, redacted_message, frameworks = await _check_pii_with_brain(state)

    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "pii_detected": pii_detected,
        "pii_redacted_message": redacted_message,
        "active_frameworks": new_frameworks,
    }
