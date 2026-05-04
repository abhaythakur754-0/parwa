"""
PII Redaction Node — Group 1 (First node in the pipeline)

Scans the incoming message for Personally Identifiable Information (PII)
and produces a redacted version safe for downstream processing.

State Contract:
  Reads:  message, tenant_id
  Writes: pii_redacted_message, pii_entities_found, errors

BC-008: Never crash — if PII engine is unavailable, pass message through
        unredacted and log the failure.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from app.core.langgraph.config import get_variant_config
from app.logger import get_logger

logger = get_logger("node_pii_redaction")


# ──────────────────────────────────────────────────────────────
# Fallback regex patterns for basic PII detection when engine
# is unavailable. These catch common patterns: emails, phone
# numbers, SSN-like sequences, credit-card-like numbers.
# ──────────────────────────────────────────────────────────────

_FALLBACK_PII_PATTERNS: List[Dict[str, Any]] = [
    {
        "name": "email",
        "pattern": re.compile(
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE
        ),
        "replacement": "[EMAIL_REDACTED]",
    },
    {
        "name": "phone_us",
        "pattern": re.compile(
            r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
        ),
        "replacement": "[PHONE_REDACTED]",
    },
    {
        "name": "ssn",
        "pattern": re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),
        "replacement": "[SSN_REDACTED]",
    },
    {
        "name": "credit_card",
        "pattern": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
        "replacement": "[CC_REDACTED]",
    },
]


def _fallback_redact(message: str) -> Dict[str, Any]:
    """
    Apply regex-based PII redaction as a fallback when the
    pii_redaction_engine module is unavailable.

    Args:
        message: Raw message text to redact.

    Returns:
        Dict with 'pii_redacted_message' and 'pii_entities_found'.
    """
    redacted = message
    entities: List[Dict[str, Any]] = []

    for pattern_def in _FALLBACK_PII_PATTERNS:
        for match in pattern_def["pattern"].finditer(message):
            entities.append(
                {
                    "type": pattern_def["name"],
                    "value": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "replacement": pattern_def["replacement"],
                }
            )
            redacted = redacted.replace(match.group(), pattern_def["replacement"], 1)

    return {
        "pii_redacted_message": redacted,
        "pii_entities_found": entities,
    }


def pii_redaction_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    PII Redaction Node — LangGraph agent node.

    Detects and redacts personally identifiable information from the
    incoming message. Uses the production PII redaction engine when
    available; falls back to regex-based detection otherwise.

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with pii_redacted_message, pii_entities_found,
        and optionally errors.
    """
    tenant_id = state.get("tenant_id", "unknown")
    message = state.get("message", "")

    logger.info(
        "pii_redaction_node_start",
        tenant_id=tenant_id,
        message_length=len(message),
    )

    try:
        # ── Attempt production PII engine ───────────────────────
        try:
            from app.core.pii_redaction_engine import redact_pii  # type: ignore[import-untyped]

            result = redact_pii(message, tenant_id=tenant_id)

            redacted_message = result.get("redacted_message", message)
            entities_found = result.get("entities_found", [])

            logger.info(
                "pii_redaction_engine_success",
                tenant_id=tenant_id,
                entities_count=len(entities_found),
                entity_types=[e.get("type", "unknown") for e in entities_found],
            )

            return {
                "pii_redacted_message": redacted_message,
                "pii_entities_found": entities_found,
            }

        except ImportError:
            logger.warning(
                "pii_redaction_engine_unavailable_using_fallback",
                tenant_id=tenant_id,
            )
        except Exception as engine_exc:
            logger.warning(
                "pii_redaction_engine_error_using_fallback",
                tenant_id=tenant_id,
                error=str(engine_exc),
            )

        # ── Fallback: regex-based redaction ─────────────────────
        fallback_result = _fallback_redact(message)

        logger.info(
            "pii_redaction_fallback_success",
            tenant_id=tenant_id,
            entities_count=len(fallback_result["pii_entities_found"]),
        )

        return fallback_result

    except Exception as exc:
        # ── Total failure: pass message through unredacted ──────
        logger.error(
            "pii_redaction_node_failed",
            tenant_id=tenant_id,
            error=str(exc),
        )
        return {
            "pii_redacted_message": state.get("message", ""),
            "pii_entities_found": [],
            "errors": [f"PII redaction failed: {exc}"],
        }
