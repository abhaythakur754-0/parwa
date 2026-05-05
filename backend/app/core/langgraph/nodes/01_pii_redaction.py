"""
PII Redaction Node — Group 1 (First node in the pipeline)

Scans the incoming message for Personally Identifiable Information (PII)
and produces a redacted version safe for downstream processing.

Tier Behavior:
  Mini: Basic regex-only redaction (fast, cheap, catches common patterns)
  Pro:  Regex + NER (Named Entity Recognition) for better detection of
        names, addresses, and non-standard PII formats
  High: Regex + NER + tenant-specific PII rules (custom patterns per tenant,
        regulatory compliance patterns like GDPR/CCPA specific fields)

State Contract:
  Reads:  message, tenant_id, variant_tier
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


def _apply_ner_redaction(message: str, existing_entities: List[Dict[str, Any]], tenant_id: str) -> Dict[str, Any]:
    """
    Apply NER (Named Entity Recognition) based PII detection.

    Uses the production NER engine to detect names, addresses,
    organizations, and other entity types that regex patterns miss.
    Only runs for Pro and High tiers.

    Args:
        message: The message text to scan.
        existing_entities: Entities already found by regex.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        Dict with 'pii_redacted_message' and 'pii_entities_found'.
    """
    try:
        from app.core.ner_engine import detect_pii_entities  # type: ignore[import-untyped]

        ner_result = detect_pii_entities(message, tenant_id=tenant_id)
        ner_entities = ner_result.get("entities_found", [])

        # Merge NER entities with regex entities (deduplicate)
        existing_spans = {(e.get("start", -1), e.get("end", -1)) for e in existing_entities}
        new_entities = [
            e for e in ner_entities
            if (e.get("start", -1), e.get("end", -1)) not in existing_spans
        ]
        all_entities = existing_entities + new_entities

        # Apply redaction for new entities
        redacted = message
        for entity in new_entities:
            value = entity.get("value", "")
            if value and value in redacted:
                entity_type = entity.get("type", "UNKNOWN")
                replacement = f"[{entity_type}_REDACTED]"
                redacted = redacted.replace(value, replacement, 1)

        logger.info(
            "pii_ner_entities_found",
            tenant_id=tenant_id,
            ner_new_entities=len(new_entities),
            total_entities=len(all_entities),
        )

        return {
            "pii_redacted_message": redacted,
            "pii_entities_found": all_entities,
        }

    except ImportError:
        logger.info(
            "pii_ner_engine_unavailable",
            tenant_id=tenant_id,
            note="NER engine not installed; skipping NER-based PII detection",
        )
    except Exception as ner_exc:
        logger.warning(
            "pii_ner_engine_error",
            tenant_id=tenant_id,
            error=str(ner_exc),
        )

    # NER unavailable — return existing results unchanged
    return {
        "pii_redacted_message": message,
        "pii_entities_found": existing_entities,
    }


def _apply_tenant_rules(message: str, existing_entities: List[Dict[str, Any]], tenant_id: str) -> Dict[str, Any]:
    """
    Apply tenant-specific PII rules for custom patterns.

    Loads tenant-specific regex patterns and compliance rules
    (e.g., GDPR-specific fields, CCPA-specific fields, industry
    patterns like medical record numbers, policy numbers).
    Only runs for High tier.

    Args:
        message: The message text to scan.
        existing_entities: Entities already found by regex + NER.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        Dict with 'pii_redacted_message' and 'pii_entities_found'.
    """
    try:
        from app.core.tenant_pii_rules import apply_tenant_redaction  # type: ignore[import-untyped]

        tenant_result = apply_tenant_redaction(
            message=message,
            existing_entities=existing_entities,
            tenant_id=tenant_id,
        )

        logger.info(
            "pii_tenant_rules_applied",
            tenant_id=tenant_id,
            additional_entities=len(tenant_result.get("entities_found", [])) - len(existing_entities),
        )

        return {
            "pii_redacted_message": tenant_result.get("redacted_message", message),
            "pii_entities_found": tenant_result.get("entities_found", existing_entities),
        }

    except ImportError:
        logger.info(
            "pii_tenant_rules_unavailable",
            tenant_id=tenant_id,
            note="Tenant PII rules module not installed; skipping",
        )
    except Exception as tenant_exc:
        logger.warning(
            "pii_tenant_rules_error",
            tenant_id=tenant_id,
            error=str(tenant_exc),
        )

    # Tenant rules unavailable — return existing results unchanged
    return {
        "pii_redacted_message": message,
        "pii_entities_found": existing_entities,
    }


def pii_redaction_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    PII Redaction Node — LangGraph agent node.

    Detects and redacts personally identifiable information from the
    incoming message. Behavior varies by variant_tier:

      Mini: Basic regex-only redaction (fast, cheap)
      Pro:  Regex + NER for better entity detection
      High: Regex + NER + tenant-specific PII rules

    Uses the production PII redaction engine when available;
    falls back to regex-based detection otherwise.

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with pii_redacted_message, pii_entities_found,
        and optionally errors.
    """
    tenant_id = state.get("tenant_id", "unknown")
    variant_tier = state.get("variant_tier", "mini")
    message = state.get("message", "")

    logger.info(
        "pii_redaction_node_start",
        tenant_id=tenant_id,
        variant_tier=variant_tier,
        message_length=len(message),
    )

    try:
        # ── Attempt production PII engine ───────────────────────
        try:
            from app.core.pii_redaction_engine import redact_pii  # type: ignore[import-untyped]

            result = redact_pii(message, tenant_id=tenant_id, variant_tier=variant_tier)

            redacted_message = result.get("redacted_message", message)
            entities_found = result.get("entities_found", [])

            logger.info(
                "pii_redaction_engine_success",
                tenant_id=tenant_id,
                variant_tier=variant_tier,
                entities_count=len(entities_found),
                entity_types=[e.get("type", "unknown") for e in entities_found],
            )

            # ── Tier upgrades after production engine ────────────
            # Even if production engine succeeded, apply tier-specific
            # upgrades for Pro (NER) and High (tenant rules)
            if variant_tier in ("pro", "high"):
                ner_result = _apply_ner_redaction(redacted_message, entities_found, tenant_id)
                if ner_result.get("pii_entities_found") != entities_found:
                    redacted_message = ner_result["pii_redacted_message"]
                    entities_found = ner_result["pii_entities_found"]

            if variant_tier == "high":
                tenant_result = _apply_tenant_rules(redacted_message, entities_found, tenant_id)
                if tenant_result.get("pii_entities_found") != entities_found:
                    redacted_message = tenant_result["pii_redacted_message"]
                    entities_found = tenant_result["pii_entities_found"]

            return {
                "pii_redacted_message": redacted_message,
                "pii_entities_found": entities_found,
            }

        except ImportError:
            logger.warning(
                "pii_redaction_engine_unavailable_using_fallback",
                tenant_id=tenant_id,
                variant_tier=variant_tier,
            )
        except Exception as engine_exc:
            logger.warning(
                "pii_redaction_engine_error_using_fallback",
                tenant_id=tenant_id,
                variant_tier=variant_tier,
                error=str(engine_exc),
            )

        # ── Fallback: regex-based redaction (always runs) ────────
        fallback_result = _fallback_redact(message)
        redacted_message = fallback_result["pii_redacted_message"]
        entities_found = fallback_result["pii_entities_found"]

        # ── Pro tier: add NER on top of regex ────────────────────
        if variant_tier in ("pro", "high"):
            ner_result = _apply_ner_redaction(redacted_message, entities_found, tenant_id)
            if ner_result.get("pii_entities_found") != entities_found:
                redacted_message = ner_result["pii_redacted_message"]
                entities_found = ner_result["pii_entities_found"]

        # ── High tier: add tenant-specific rules on top ──────────
        if variant_tier == "high":
            tenant_result = _apply_tenant_rules(redacted_message, entities_found, tenant_id)
            if tenant_result.get("pii_entities_found") != entities_found:
                redacted_message = tenant_result["pii_redacted_message"]
                entities_found = tenant_result["pii_entities_found"]

        logger.info(
            "pii_redaction_fallback_success",
            tenant_id=tenant_id,
            variant_tier=variant_tier,
            entities_count=len(entities_found),
            ner_applied=variant_tier in ("pro", "high"),
            tenant_rules_applied=variant_tier == "high",
        )

        return {
            "pii_redacted_message": redacted_message,
            "pii_entities_found": entities_found,
        }

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
