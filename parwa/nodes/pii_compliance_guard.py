"""Node 15: PII_COMPLIANCE_GUARD — Redacts PII and enforces compliance rules.

Compliance Agent node. Detects and redacts personally identifiable
information (email, phone, SSN, credit card) from the response
before it's sent to the customer or stored in logs.
"""

from __future__ import annotations

import re
from typing import Any

from parwa.utils.node_base import safe_node


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


@safe_node("PII_COMPLIANCE_GUARD", fallback={"pii_detected": False, "pii_redacted_message": ""})
async def pii_compliance_guard(state: dict[str, Any]) -> dict[str, Any]:
    """Detect and redact PII from the response (async).

    Reads: final_response (or raw_message if no response yet)
    Writes: pii_detected, pii_redacted_message
    """
    # Check BOTH the final response AND the raw customer message for PII.
    # The final_response is what gets sent to the customer (must not contain PII).
    # The raw_message is what the customer sent to us (must be flagged if it contains PII).
    final_response = state.get("final_response", "")
    raw_message = state.get("raw_message", "")

    # Guard: ensure strings
    if not isinstance(final_response, str):
        final_response = str(final_response) if final_response else ""
    if not isinstance(raw_message, str):
        raw_message = str(raw_message) if raw_message else ""

    try:
        # Always check raw_message for PII (customer may have sent SSN, CC, etc.)
        raw_pii_detected, raw_found_items = _detect_pii(raw_message)
        
        # Also check the final response for PII leakage
        resp_pii_detected, resp_found_items = _detect_pii(final_response)
        
        # Combined detection
        pii_detected = raw_pii_detected or resp_pii_detected
        found_items = {}
        for k, v in raw_found_items.items():
            found_items[f"raw_{k}"] = v
        for k, v in resp_found_items.items():
            found_items[f"response_{k}"] = v
        
        # Redact PII from the final response
        redacted_message = _redact_pii(final_response) if resp_pii_detected else final_response
    except Exception as exc:
        import logging
        logging.getLogger("parwa.node.pii_compliance_guard").warning(
            "PII_COMPLIANCE_GUARD: PII detection/redaction failed: %s", exc,
        )
        # If PII detection fails, return the message as-is (don't block the pipeline)
        pii_detected = False
        redacted_message = message

    return {
        "pii_detected": pii_detected,
        "pii_redacted_message": redacted_message,
    }
